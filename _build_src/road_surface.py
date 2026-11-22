"""Road surface from centrelines without protruding ends and without gaps.
At each line end p:
  - the "through road" at p = lines passing p (p not at their ends) + pairs of lines that end at p and continue in line (within 35 deg);
  - if this line is part of the through road -> untouched (round join, stays inside the road width);
  - if it ends against a through road (T-branch) -> carried right across the through road (full overlap, no gaps at oblique junctions)
    and only the part beyond the FAR edge of the through road is cut away, so nothing protrudes;
  - fillet > 0: junction corners get rounded kerb returns of that radius;
  - no through road (free dead end, L corner, Y) -> round end."""
import numpy as np, shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union, substring
unit = lambda v: np.asarray(v, float) / (np.linalg.norm(v) + 1e-12)
def _out_dir(l, at_start):
    c = np.array(l.coords)[:, :2]
    k = 1
    while k < len(c) - 1 and np.linalg.norm(c[k] - c[0] if at_start else c[-1 - k] - c[-1]) < 1e-6: k += 1
    return unit(c[0] - c[k]) if at_start else unit(c[-1] - c[-1 - k])        # pointing out of the line at that end
def _end_at(l, p, tol):
    """True/False = line starts/ends at p; None = p is not at an end of l"""
    if Point(l.coords[0]).distance(p) <= tol: return True
    if Point(l.coords[-1]).distance(p) <= tol: return False
    return None
def road_surface(lines, half, tol=3.0, clip=None, return_ends=False, fillet=0.0):
    lines = [shapely.force_2d(l) for l in lines]; tree = shapely.STRtree(lines); COS = np.cos(np.radians(35))
    pieces, log, cutaway = [], [], {}
    for i, l in enumerate(lines):
        if l.length < 1e-6: continue
        g = l; flat = {}
        for at_start in (True, False):
            p = Point(l.coords[0] if at_start else l.coords[-1])
            near = [j for j in tree.query(p.buffer(max(half) + tol)) if j != i and lines[j].distance(p) <= half[j] + tol]
            if not near: continue
            through = set(j for j in near if _end_at(lines[j], p, tol) is None)
            ends = [(j, _end_at(lines[j], p, tol)) for j in near if j not in through] + [(i, at_start)]
            dirs = {j: _out_dir(lines[j], s) for j, s in ends}
            i_through = False
            for a in range(len(ends)):
                for b in range(a + 1, len(ends)):
                    ja, jb = ends[a][0], ends[b][0]
                    if float(dirs[ja] @ -dirs[jb]) > COS:
                        if ja == i or jb == i: i_through = True
                        else: through.update([ja, jb])
            if i_through or not through: continue                      # part of the through road, or corner / dead end: leave round
            M = unary_union([lines[j].buffer(half[j]) for j in through]); hmax = max(half[j] for j in through)
            L = g.length
            if p.within(M):                                             # where the branch centreline enters the through road
                s_exit = None
                for s in np.arange(0, min(L, hmax + 2 * tol), 0.25):
                    q = g.interpolate(s if at_start else L - s)
                    if not q.within(M): s_exit = s; break
                if s_exit is None: continue                             # runs along the other road: leave it
                g = substring(g, s_exit, L) if at_start else substring(g, 0, L - s_exit)
            elif p.distance(M) > tol: continue
            # carry the branch right across the through road (full overlap, no unpaved wedge at oblique junctions) ...
            d = _out_dir(g, at_start); c = list(g.coords); e = np.array(c[0 if at_start else -1])[:2]
            reach = 2 * hmax + 2 * half[i] + p.distance(M) + 1
            q = tuple(e + d * reach)
            g = LineString([q] + c) if at_start else LineString(c + [q])
            # ... then cut away whatever would stick out beyond the FAR edge of the through road
            LT = unary_union([lines[j] for j in through]).intersection(p.buffer(reach * 3 + 50))
            ref = Point(e - d * min(2 * hmax, max(L - 1, 1)))           # a point on the branch's own side
            near_pt = LT.interpolate(LT.project(ref)) if LT.geom_type in ('LineString', 'MultiLineString') else None
            far = None
            if near_pt is not None and LT.geom_type == 'LineString':
                sN = LT.project(ref); t = np.array(LT.interpolate(min(LT.length, sN + 2)).coords[0])[:2] - np.array(LT.interpolate(max(0, sN - 2)).coords[0])[:2]
                side = np.sign(t[0] * (ref.y - near_pt.y) - t[1] * (ref.x - near_pt.x)) or 1.0      # +1 = branch on the left of LT
                big = 4 * (hmax + half[i]) + 10
                far = LT.buffer(-side * big, single_sided=True)        # the far side of the through road
            else:
                parts = [x for x in shapely.get_parts(LT) if x.geom_type == 'LineString']
                zones = []
                for x in parts:
                    sN = x.project(ref); np_ = x.interpolate(sN)
                    t = np.array(x.interpolate(min(x.length, sN + 2)).coords[0])[:2] - np.array(x.interpolate(max(0, sN - 2)).coords[0])[:2]
                    side = np.sign(t[0] * (ref.y - np_.y) - t[1] * (ref.x - np_.x)) or 1.0
                    zones.append(x.buffer(-side * (4 * (hmax + half[i]) + 10), single_sided=True))
                far = unary_union(zones) if zones else None
            if far is not None: cutaway.setdefault(i, []).append(far.difference(M))
            flat[at_start] = True; log.append((i, at_start))
        if g.length < 1e-6: continue
        if not flat: pieces.append(g.buffer(half[i]))
        else:
            body = g.buffer(half[i], cap_style=2)
            for at_start in (True, False):                              # round the ends that were not trimmed
                if not flat.get(at_start): body = body.union(Point(g.coords[0] if at_start else g.coords[-1]).buffer(half[i]))
            for z in cutaway.get(i, []): body = body.difference(z)
            pieces.append(body)
    S = unary_union(pieces)
    if fillet > 0: S = S.buffer(fillet, join_style=1).buffer(-fillet, join_style=1)      # rounded kerb returns at junction corners
    S = S.intersection(clip) if clip is not None else S
    return (S, log) if return_ends else S
