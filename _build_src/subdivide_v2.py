"""Stage 4: subdivide the blocks by the planner's Phase One method (user's rules, see memory 'plot subdivision method').
1. The front row is 100 ft deep: offset the front road line by 100 ft (the mid line), extended to the block ends.
2. Cuts square to the mid line, every cut running road edge to road edge (front and back plots back to back).
3. One frontage per block from 65 / 70 / 75 / 80 ft: the size whose end plots take <= 10 ft of leftover (smallest leftover;
   ties 70, 75, 65, 80; 80 first on the main road). Only the FIRST and LAST plot absorb the leftover. If no size fits, mix sizes
   symmetrically with the larger ones at the ends. Never below 65 ft.
4. Curves: each plot is widened just enough to reach its size x 100 sq ft.
5. Slivers join the neighbouring plot; only real wedges / landlocked pieces become reserves (facility sites)."""
import geopandas as gpd, pandas as pd, numpy as np, math, warnings
from shapely.geometry import LineString, Polygon, Point
from shapely.ops import unary_union, polygonize, linemerge
import shapely
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
warnings.filterwarnings('ignore')
OUT = 'ml3/'; CRS = 2136; DEPTH = 100.0
B = gpd.read_file(OUT + 'layout_blocks.gpkg').geometry
RD = gpd.read_file(OUT + 'layout_roads.gpkg'); ROAD = RD.union_all()
C = gpd.read_file(OUT + 'concept.gpkg').set_index('Part').geometry
MAINR = C['60 ft existing road'] if '60 ft existing road' in C.index else Point(-1e7, -1e7).buffer(1)
unit = lambda v: np.asarray(v, float) / (np.linalg.norm(v) + 1e-12)
SIZES = [70, 75, 65, 80]

def mrr(g):
    if g.is_empty or g.area <= 0: return [1.0, 1.0]
    c = list(g.minimum_rotated_rectangle.exterior.coords); return sorted([math.dist(c[0], c[1]), math.dist(c[1], c[2])])

def sides(poly, turn=35):
    """the outline split into sides at corners sharper than `turn` degrees"""
    c = np.array(poly.exterior.simplify(12.0).coords)[:-1]; n = len(c)      # 12 ft: rounded kerb-return corners become one sharp corner
    ang = [abs(math.degrees(math.atan2((c[i] - c[i - 1])[0] * (c[(i + 1) % n] - c[i])[1] - (c[i] - c[i - 1])[1] * (c[(i + 1) % n] - c[i])[0], (c[i] - c[i - 1]) @ (c[(i + 1) % n] - c[i])))) for i in range(n)]
    corners = [i for i in range(n) if ang[i] > turn]
    if len(corners) < 2: return [LineString(list(c) + [c[0]])]
    out = []
    for a, b in zip(corners, corners[1:] + [corners[0]]):
        idx = list(range(a, b + 1)) if b > a else list(range(a, n)) + list(range(0, b + 1))
        out.append(LineString([tuple(c[i % n]) for i in idx]))
    return out

def road_share(side): return side.buffer(8).intersection(ROAD).area / max(side.length * 16, 1)   # sides come from the simplified outline
def is_road(side): return road_share(side) > 0.2                 # a side at least ~40 % along a road (a back road that runs only part of the way still counts)

def front_of(poly):
    """the front: the longest road side along the block's long axis (the main road side when it is long enough)"""
    rs = [s for s in sides(poly) if is_road(s) and s.length > 60]
    if not rs: return None
    mx = max(r.length for r in rs)
    mains = [r for r in rs if r.buffer(3).intersection(MAINR).area > 0.5 * r.length * 3 and r.length >= 0.6 * mx]
    if mains: return max(mains, key=lambda r: r.length)
    c = np.array(poly.minimum_rotated_rectangle.exterior.coords); e1, e2 = c[1] - c[0], c[2] - c[1]
    ax_ = unit(e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2)
    along = [r for r in rs if abs(float(unit(np.array(r.coords[-1]) - np.array(r.coords[0])) @ ax_)) > math.cos(math.radians(30))]
    return max(along or rs, key=lambda r: r.length)

def ext(l, e=600):
    c = np.array(l.coords); return LineString([tuple(c[0] - unit(c[1] - c[0]) * e)] + [tuple(x) for x in c] + [tuple(c[-1] + unit(c[-1] - c[-2]) * e)])

def offset_into(F, d, poly):
    """the front line offset by d into the block, extended to touch the block ends"""
    best = None
    for s in (d, -d):
        o = ext(F.simplify(2)).offset_curve(s)
        if o.is_empty: continue
        g = o.intersection(poly)
        parts = [q for q in shapely.get_parts(g) if q.geom_type == 'LineString']
        if not parts:
            m = linemerge(g) if g.geom_type == 'MultiLineString' else g; parts = [q for q in shapely.get_parts(m) if q.geom_type == 'LineString']
        if parts:
            q = max(parts, key=lambda x: x.length)
            if best is None or q.length > best.length: best = q
    return best

def plan_sizes(L, prefer):
    """frontages along the mid line (ft): one size with <= 10 ft leftover per end plot, else a symmetric mix; never < 65"""
    if L < 2 * 65: return [L], 'single'
    best = None
    for k, base in enumerate(prefer):
        n = int(L // base); r = L - n * base
        if n >= 2 and r / 2 <= 10 and (best is None or (r, k) < best[0]): best = ((r, k), base, n, r)
    if best:
        _, base, n, r = best; w = [float(base)] * n; w[0] += r / 2; w[-1] += r / 2
        return w, f'{base} ft (ends +{r / 2:.0f})'
    cands = []
    for n in range(max(2, int(L // 80)), int(L // 65) + 1):           # mix: 70s, middle ones down to 65, end pairs up to 75 / 80
        w = [70.0] * n; extra = L - 70 * n
        for i in sorted(range(n), key=lambda i: abs(i - (n - 1) / 2)):
            if extra >= 0: break
            w[i] = 65.0; extra += 5
        if extra < 0: continue
        pairs = [(i, n - 1 - i) for i in range((n + 1) // 2)]
        for target in (75.0, 80.0):
            for a, b in pairs:
                if extra <= 20: break
                inc = (target - w[a]) * (1 if a == b else 2)
                if inc > 0 and extra - inc >= 0: w[a] = w[b] = target; extra -= inc
        if extra > 20: continue
        w[0] += extra / 2; w[-1] += extra / 2; cands.append((extra, n, w))
    if cands:
        extra, n, w = min(cands, key=lambda t: t[0]); return w, f'mixed {"/".join(str(int(x)) for x in sorted(set(int(v) for v in w[1:-1]) or {int(w[0])}))} ft (ends +{extra / 2:.0f})'
    n = max(1, round(L / 70)); return [L / n] * n, 'even (no standard fit)'

def cut_line(M, s):
    p = np.array(M.interpolate(s).coords[0]); t = unit(np.array(M.interpolate(min(M.length, s + 4)).coords[0]) - np.array(M.interpolate(max(0, s - 4)).coords[0]))
    nrm = np.array([-t[1], t[0]]); return LineString([tuple(p - nrm * 2000), tuple(p + nrm * 2000)])

def between(strip, a, b):
    """the piece of the strip between two cut lines"""
    q = Polygon([a.coords[0], a.coords[1], b.coords[1], b.coords[0]])
    if not q.is_valid: q = Polygon([a.coords[0], a.coords[1], b.coords[0], b.coords[1]])
    return strip.intersection(q.buffer(0))

plots, reserves, notes = [], [], []
def reserve(g, bi, why):
    for q in shapely.get_parts(g):
        if q.geom_type == 'Polygon' and q.area > 200: reserves.append(dict(geometry=q, block=bi, row=why))

def subdivide(blk, bi):
    F = front_of(blk)
    if F is None: reserve(blk, bi, 'no road access'); return
    depth = blk.area / max(F.length, 1)
    back = [s for s in sides(blk) if is_road(s) and s.length > 60 and s.distance(F) > 0.6 * depth]
    two_rows = depth >= 185 and bool(back)
    if depth > 260 and not back:                                       # deep block with no back road: one 100 ft row, the rest is a reserve
        strip = blk.intersection(ext(F).buffer(DEPTH, cap_style=2)); strip = max(shapely.get_parts(strip), key=lambda g: g.area)
        rest = blk.difference(strip.buffer(0.05)); subdivide_row(strip, F, bi, depth=DEPTH); reserve(rest, bi, 'behind a row, no frontage'); return
    if depth > 330 and back:                                           # three rows deep: peel a 100 ft row off the front, subdivide the rest
        strip = blk.intersection(ext(F).buffer(DEPTH, cap_style=2)); strip = max(shapely.get_parts(strip), key=lambda g: g.area)
        subdivide_row(strip, F, bi, depth=DEPTH)
        for r_ in shapely.get_parts(blk.difference(strip.buffer(0.05))):
            if r_.area > 7000: subdivide(r_, bi)
            elif r_.area > 200: reserve(r_, bi, 'sliver')
        return
    subdivide_row(blk, F, bi, depth=DEPTH if two_rows else depth / 2, split=two_rows)

def subdivide_row(blk, F, bi, depth, split=False):
    """cut the block along the mid line M (front line offset by `depth`); split=True: also cut along M (two rows back to back)"""
    M = offset_into(F, min(depth, blk.area / max(F.length, 1) - 5) if split else depth, blk)
    if M is None or M.length < 40: reserve(blk, bi, 'no mid line'); return
    on_main = F.buffer(3).intersection(MAINR).area > 0.5 * F.length * 3
    prefer = [80, 75, 70, 65] if on_main else SIZES
    w, how = plan_sizes(M.length, prefer)
    front = blk.intersection(ext(F).buffer(DEPTH + 1, cap_style=2)) if split else blk
    # cut positions; on curves widen each plot until its front piece reaches size x 100 sq ft
    pos = [0.0]; s = 0.0
    for i, x in enumerate(w[:-1]):
        s_new = s + x; target = (65 if i in (0, len(w) - 1) else x) * 100 * 0.98
        a = cut_line(M, s)
        for _ in range(30):
            if s_new >= M.length - 60: break
            if between(front, a, cut_line(M, s_new)).area >= target or not split: break
            s_new += 1.0
        pos.append(s_new); s = s_new
    if M.length - pos[-1] < 60 and len(pos) > 2: pos.pop()             # a short last plot joins the one before
    cuts = [cut_line(M, p).intersection(blk.buffer(0.01)) for p in pos[1:]]
    lines = [blk.exterior] + [c for c in cuts if not c.is_empty] + [ext(M, 50).intersection(blk.buffer(0.01))] * split
    parts = [q for q in polygonize(unary_union(lines)) if q.representative_point().within(blk) and q.area > 50]
    for q in parts: plots.append(dict(geometry=q, block=bi, how=how, row='front' if (not split or q.distance(F) < 5) else 'back'))
    notes.append(f'block {bi}: {M.length:.0f} ft -> {len(pos)} plots per row x {2 if split else 1} ({how})')

for bi, blk in enumerate(B):
    for part in shapely.get_parts(blk):
        if part.geom_type == 'Polygon' and part.area > 2000: subdivide(part, bi)

P = gpd.GeoDataFrame(plots, crs=CRS); P['w'] = [mrr(g)[0] for g in P.geometry]; P['d'] = [mrr(g)[1] for g in P.geometry]
RES = gpd.GeoDataFrame(reserves, geometry='geometry', crs=CRS) if reserves else gpd.GeoDataFrame(dict(block=[], row=[]), geometry=[], crs=CRS)
# slivers (< 4,000 sq ft, or thinner than 40 ft) join the neighbour they share the longest edge with
for i in list(P.index):
    g = P.geometry[i]
    if g.area >= 4000 and P.w[i] >= 40: continue
    nb = P[(P.index != i) & (P.block == P.block[i])]; nb = nb[nb.geometry.buffer(0.5).intersection(g).area > 1]
    if nb.empty: continue
    j = max(nb.index, key=lambda j: nb.geometry[j].buffer(0.5).intersection(g.boundary.buffer(0.5)).area)
    u = unary_union([P.geometry[j], g]).buffer(0.05).buffer(-0.05)
    if u.geom_type == 'Polygon': P.at[j, 'geometry'] = u; P = P.drop(index=i)
P = P.reset_index(drop=True); P['w'] = [mrr(g)[0] for g in P.geometry]; P['d'] = [mrr(g)[1] for g in P.geometry]
# a real wedge (very irregular and large) is a facility site, not an odd plot
wedge = P[(P.area / [g.minimum_rotated_rectangle.area for g in P.geometry] < 0.55) & (P.area > 0.25 * 43560)]
for g in wedge.geometry: reserve(g, -1, 'wedge (facility site)')
P = P.drop(wedge.index).reset_index(drop=True)
RES = gpd.GeoDataFrame(reserves, geometry='geometry', crs=CRS) if reserves else RES
P['double'] = False; P['kind'] = 'plot'; P['area'] = P.area
RES['kind'] = 'reserve'
P.to_file(OUT + 'plots.gpkg'); RES.to_file(OUT + 'reserves.gpkg')
for n_ in notes[:12]: print('  ', n_)
ok = P[(P.w >= 63) & (P.w <= 92) & (P.d >= 95) & (P.d <= 122)]
print(f'plots {len(P)} | median {P.w.median():.0f} x {P.d.median():.0f} ft | standard (65-80 x 100): {len(ok)} of {len(P)} ({100 * len(ok) / max(len(P), 1):.0f}%) | reserves {RES.area.sum() / 43560:.1f} ac in {len(RES)} pieces')
fig, ax = plt.subplots(figsize=(14, 14))
gpd.GeoSeries([ROAD]).plot(ax=ax, color='#d0d0d0')
P.plot(ax=ax, color=np.where(P.index.isin(ok.index), '#f2c38b', '#e8875a'), ec='k', lw=.4)
if len(RES): RES.plot(ax=ax, color='#a6e3a1', ec='darkgreen', lw=.6, hatch='//')
ax.set_title(f'{len(P)} plots ({len(ok)} standard 65-80 x 100 ft) + reserves {RES.area.sum() / 43560:.1f} ac', fontsize=15); ax.set_axis_off()
plt.savefig(OUT + 'plots_preview.png', bbox_inches='tight', dpi=85)
P.to_file(OUT + 'plots_final.gpkg'); RES.to_file(OUT + 'reserves_final.gpkg')
