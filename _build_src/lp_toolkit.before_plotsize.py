#!/usr/bin/env python
"""LP Toolkit: one script for local plan preparation (existing-situation mapping of built-up areas and new layouts).

Usage (from the LP_Toolkit folder, with its own Python: run.bat ... or env\\Scripts\\python.exe lp_toolkit.py ...):

  python lp_toolkit.py existing --site "D:/.../Test 6.kml" --name "Test 6" [--title "Test 6 (Teshie)"] [--out DIR]
                                [--profile auto|planned|compact] [--from STAGE] [--only STAGE[,STAGE]] [--with footpaths,proposals]
  python lp_toolkit.py design   --site SITE.kml --name NAME --roads ROADS.shp|auto|draft [--existing ROADS.shp] [--stream STREAM.shp --stream-buffer 100]
                                [--out DIR] [--from STAGE] [--only STAGE[,STAGE]]
  python lp_toolkit.py db       --site SITE.kml [--out FILE.gpkg]        export the building database for a site
  python lp_toolkit.py guide                                              print the guide and write LP_Toolkit_Guide.md
  python lp_toolkit.py stages                                             list the stages

Existing stages: fetch, sam, digitize, compare, clean, database, roads, landuse, reserves, trees, blocks, plots, map
                 (+ optional footpaths, proposals with --with)
Design stages:   site, roads, subdivide, landuse, audit

Outputs go to <site folder>/<name> outputs/ (working files in its _work/ sub-folder). Stages already done can be re-run alone.
The full guide (processes, rules, standards, data sources, lessons) is in GUIDE below.
"""
import os, sys, re, json, math, glob, time, pickle, shutil, argparse, warnings
import numpy as np
warnings.filterwarnings('ignore')
TOOLKIT = os.path.dirname(os.path.abspath(__file__))
SAM_CKPT_DEFAULT = os.path.join(TOOLKIT, 'models', 'sam_vit_b_01ec64.pth').replace('\\', '/')
MS_CACHE = os.path.join(TOOLKIT, 'cache', 'ms').replace('\\', '/')
OBM_ROOT = 'D:/Work/2026/Data'                       # building database (see guide section 2)
USER_AGENT = 'gis-planning-client'                   # never send personal details to outside services
FT = 0.3048
# plot subdivision profiles for existing areas (guide section 4)
PROFILES = {
    'planned': dict(wmin=12, wmax=25, single_row=45, halve_depth=65, recut_area=1000, recut_depth=50),
    'compact': dict(wmin=9, wmax=18, single_row=30, halve_depth=40, recut_area=500, recut_depth=36),
}

# =====================================================================================================================
# LUSPA colour codes: Revised Zoning Guidelines and Planning Standards (2025), Table 1 (broad uses) and Table 2 (specific uses)
# code: (name, fill, pattern colour, matplotlib hatch, edge colour)  - pattern / hatch only where the Guidelines specify one
# =====================================================================================================================
LUSPA = {
    'Re':   ('Residential', '#DC7C24', None, None, None),
    'Re A': ('Residential Zone A', '#CC7722', None, None, None),
    'Re B': ('Residential Zone B', '#E5AA70', None, None, None),
    'Re C': ('Residential Zone C', '#BB8855', None, None, None),
    'Re D': ('Residential Zone D', '#98623C', None, None, None),
    'Com':  ('Commercial', '#73B2FF', None, None, None),
    'CBD':  ('Central Business District', '#2E4DA7', None, None, None),
    'BM':   ('Mixed Business / Residential', '#73B2FF', '#FFAA57', '//', None),
    'BI':   ('Informal Business', '#73B2FF', '#000000', '..', None),
    'TL':   ('Transportation and Logistics', '#D6D6D6', '#000000', '++', None),
    'CC':   ('Civic and Culture', '#FF7F7F', None, None, None),
    'PW':   ('Place of Worship', '#FF7F7F', '#000000', '^^', None),
    'H':    ('Health', '#FF0000', None, None, None),
    'BG':   ('Government Business', '#FF7F7F', '#000000', '..', None),
    'T':    ('Tourist / Heritage', '#FF0080', None, None, None),
    'SU':   ('Special / Utility', '#FF7F7F', '#000000', '//', None),
    'SZ':   ('Security', '#FF7F7F', '#000000', '--', None),
    'InD':  ('Industrial', '#F4AFF4', None, None, None),
    'LI':   ('Light Industrial', '#E8BEFF', None, None, None),
    'IS':   ('Service Industry', '#EE82EE', None, None, None),
    'Ed':   ('Educational', '#FFFF00', None, None, '#C00000'),
    'Ed P': ('Education Zone A: Pre-school and Basic School', '#FFFF00', '#000000', '..', '#C00000'),
    'Ed S': ('Education Zone B: Senior High and TVET', '#FFFF00', '#000000', '||', '#C00000'),
    'Ed T': ('Education Zone C: Tertiary', '#FFFF00', '#000000', '--', '#C00000'),
    'PS':   ('Public Space', '#00FF00', None, None, None),
    'CA':   ('Conservation', '#32CD32', None, None, None),
    'CZ':   ('Protected Coastal / Waterfront', '#20B2AA', None, None, None),
    'Ag':   ('Agriculture', '#ADFF2F', None, None, None),
    'VAC':  ('Open / yard, no building (not a zoning class)', '#FFFFFF', '#9E9E9E', None, '#9E9E9E'),
    'UNC':  ('Use NOT CONFIRMED: please verify', '#FFFFFF', '#FF6D00', None, '#FF6D00'),
}
EXIST_LUSPA = {'Residential': 'Re', 'Mixed use (shop + residence)': 'BM', 'Commercial / mixed use': 'BM', 'Commercial': 'Com', 'Commercial (hotel)': 'Com',
               'Commercial (fuel)': 'Com', 'Commercial (entertainment)': 'Com', 'Commercial (wholesale / storage)': 'Com', 'Commercial (parking)': 'TL', 'Office': 'Com',
               'Market': 'Com', 'Transport terminal': 'TL', 'Health': 'H', 'Education': 'Ed', 'Religious': 'PW', 'Religious / assembly': 'PW', 'Civic': 'CC',
               'Institutional / large commercial (verify)': 'CC', 'Recreation': 'PS', 'Industrial': 'InD', 'Mixed use (industrial + commercial)': 'IS',
               'Mixed use (commercial + industrial)': 'IS', 'Agricultural': 'Ag', 'Open / yard (no building)': 'VAC', 'Unconfirmed (verify)': 'UNC', 'Utility': 'SU'}
DESIGN_LUSPA = {'RE': 'Re B', 'RA': 'Re A', 'MU': 'BM', 'BM': 'BM', 'Com A': 'Com', 'CIV': 'CC', 'TR': 'TL', 'PW': 'PW', 'H Po': 'H', 'Ed P': 'Ed P',
                'POS': 'PS', 'GRN': 'CA', 'SU': 'SU', '': 'VAC'}
def luspa_draw(ax, gdf, col, mapping, lw=.5, ec='#222'):
    """fill each feature with its LUSPA colour and pattern; returns {code: count}"""
    import matplotlib as mpl
    counts = {}
    codes = gdf[col].map(lambda u: mapping.get(u, 'VAC'))
    for code in codes.unique():
        sub = gdf[codes == code]; name, fill, pc, hatch, edge = LUSPA[code]; counts[code] = len(sub)
        sub.plot(ax=ax, color=fill, ec=edge or ec, lw=lw if not edge else max(lw, 1.2), linestyle='--' if code == 'UNC' else '-')
        if hatch == '^^':                                          # 'black triangular pattern fill' (no triangle hatch in matplotlib): small triangles on a grid
            import shapely
            from shapely.geometry import Point as _Pt
            for g in sub.geometry:
                x0, y0, x1, y1 = g.bounds; st = 22.0
                pts = [(x, y + (st / 2 if int((x - x0) / st) % 2 else 0)) for x in np.arange(x0 + st / 2, x1, st) for y in np.arange(y0 + st / 2, y1, st)]
                pts = [q for q in pts if g.contains(_Pt(q))]
                if pts: ax.scatter([q[0] for q in pts], [q[1] for q in pts], marker='^', s=9, c=pc, linewidths=0, zorder=3)
        elif hatch:
            with mpl.rc_context({'hatch.color': pc, 'hatch.linewidth': 1.4 if pc not in (None, '#000000') else .8}): sub.plot(ax=ax, facecolor='none', ec=pc, lw=0, hatch=hatch * 2)
    return counts
def luspa_handles(counts, suffix=lambda code, n: f' ({n})'):
    from matplotlib.patches import Patch
    import matplotlib as mpl
    hs = []
    for code in [c for c in LUSPA if c in counts]:
        name, fill, pc, hatch, edge = LUSPA[code]
        with mpl.rc_context({'hatch.color': pc or '#000000', 'hatch.linewidth': 1.4 if pc not in (None, '#000000') else .8}): hs.append(Patch(facecolor=fill, edgecolor=edge or pc or '#555555', hatch=('**' if hatch == '^^' else hatch * 2 if hatch else None), lw=1.2 if edge else .8, label=f'{code if code not in ("VAC", "UNC") else ""}  {name}{suffix(code, counts[code])}'.strip()))
    return hs

PROFILE_THRESHOLD_M2 = 70                            # median image-digitized building below this -> compact
PROFILE_THRESHOLD_DB_M2 = 56                         # same test on database / OSM footprints (they are drawn tighter: Osu 61, La 51)
CUR_STAGE = {'name': None}
def progress(pct, note=''):
    """progress line for the web app: '@@progress <stage> <percent> <note>'"""
    print(f"@@progress {CUR_STAGE['name']} {max(0, min(100, pct)):.0f} {note}", flush=True)

# =====================================================================================================================
# Shared helpers: mask features / classification / outlines (digitizing), walls, building database, road surface
# =====================================================================================================================
# ---- from toolkit_src/roadsplit.py ----
"""Split a merged road surface into one polygon per road centreline (EPSG:2136, feet).
Junctions go to the higher road (trunk > primary > secondary > ...); left-over slivers join the piece they touch most."""
RANK = {'motorway': 0, 'trunk': 1, 'primary': 2, 'secondary': 3, 'tertiary': 4, 'unclassified': 5, 'residential': 6, 'living_street': 6,
        'service': 7, 'track': 8, 'pedestrian': 8, 'footway': 9, 'path': 9}


def _poly(g):
    """valid, polygon-only version of g"""
    import shapely
    from shapely.geometry import MultiPolygon
    g = shapely.make_valid(g)
    ps = [p for p in shapely.get_parts(g) if p.geom_type == 'Polygon' and not p.is_empty]
    ps += [q for p in shapely.get_parts(g) if p.geom_type == 'MultiPolygon' for q in p.geoms]
    return ps[0] if len(ps) == 1 else MultiPolygon(ps) if ps else shapely.Polygon()


def split_surface_per_road(surface, R, FT=0.3048):
    """surface: shapely (Multi)Polygon; R: GeoDataFrame of centrelines (same CRS) with optional name / highway / carriage_w.
    returns a GeoDataFrame: one row per road, with the road's attributes, area_m2 and geometry"""
    import geopandas as gpd, shapely
    from shapely.strtree import STRtree
    from shapely.ops import unary_union
    S = shapely.make_valid(surface).buffer(0)
    R = R[R.geometry.notna() & ~R.geometry.is_empty].copy().reset_index(drop=True)
    if not len(R) or S.is_empty: return None
    hw = R['highway'] if 'highway' in R else None
    R['_r'] = hw.map(RANK).fillna(6) if hw is not None else 6
    cw = R['carriage_w'].fillna(7.0) if 'carriage_w' in R else 7.0
    R['_w'] = (cw / 2 + 2.5) / FT                                  # half carriageway + footway, in feet
    R['_len'] = R.length
    order = R.sort_values(['_r', '_len'], ascending=[True, False]).index
    pieces, taken = {}, []
    tree_taken = None
    for i in order:
        buf = R.geometry[i].buffer(R._w[i] * 1.15, cap_style='flat')
        part = S.intersection(buf)
        if part.is_empty: continue
        if taken:
            near = [taken[k] for k in STRtree(taken).query(part)] if len(taken) > 1 else taken
            if near: part = part.difference(unary_union(near))
        part = _poly(part)
        if part.is_empty or part.area * FT * FT < 1: continue
        pieces[i] = part; taken.append(part)
    if not pieces: return None
    # left-overs (junction corners, kerb returns): join the piece they share the longest edge with
    rest = _poly(S.difference(unary_union(list(pieces.values()))))
    keys = list(pieces); tree = STRtree([pieces[k] for k in keys])
    for q in shapely.get_parts(rest):
        if q.area * FT * FT < 0.5: continue
        cand = [keys[j] for j in tree.query(q.buffer(1))]
        if not cand:
            cand = [min(keys, key=lambda k: pieces[k].distance(q))]
        best = max(cand, key=lambda k: pieces[k].buffer(0.5).intersection(q.boundary).length)
        pieces[best] = _poly(pieces[best].union(q))
    rows = []
    keep = [c for c in ('osm_id', 'name', 'highway', 'carriage_w', 'reserve_m') if c in R.columns]
    for i, g in pieces.items():
        g2 = _poly(g.buffer(0.2).buffer(-0.2))
        g = g2 if not g2.is_empty and g2.area > 0.995 * g.area else g
        if g.is_empty: continue
        r = {c: R.at[i, c] for c in keep}; r['area_m2'] = round(g.area * FT * FT, 1); r['geometry'] = g; rows.append(r)
    return gpd.GeoDataFrame(rows, geometry='geometry', crs=R.crs)


def split_file(surface_shp, centrelines_shp, backup=True):
    """convert an existing merged Road_surface.shp in place (the merged original is kept as *_merged.shp)"""
    import geopandas as gpd, os, shutil, glob
    S = gpd.read_file(surface_shp)
    if 'highway' in S.columns or 'name' in S.columns or not os.path.exists(centrelines_shp): return False
    R = gpd.read_file(centrelines_shp)
    if S.crs is None: S = S.set_crs(2136)
    R = R.to_crs(S.crs) if R.crs else R.set_crs(S.crs)
    out = split_surface_per_road(S.union_all(), R)
    if out is None or len(out) < 2: return False
    if backup:
        base = surface_shp[:-4]
        for x in glob.glob(base + '.*'): shutil.copy(x, base + '_merged' + os.path.splitext(x)[1])
    out.to_file(surface_shp)
    return True

# ---- from ml4/classify.py ----
"""Classify SAM masks into buildings / foundations (uncompleted) and drop trees, yards, cars, roads; regularize outlines."""
import numpy as np, cv2, math
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
import shapely
PX = 0.299                                                # m per pixel (z19, 3857 at this latitude ~ ground metres)
def features(poly_px, img, edges):
    H_, W_ = img.shape[:2]; x0, y0, x1, y1 = [int(v) for v in poly_px.bounds]
    x0, y0 = max(0, x0 - 3), max(0, y0 - 3); x1, y1 = min(W_, x1 + 4), min(H_, y1 + 4)
    if x1 - x0 < 3 or y1 - y0 < 3: return None
    img = img[y0:y1, x0:x1]; edges = edges[y0:y1, x0:x1]
    m = np.zeros(img.shape[:2], np.uint8)
    cv2.fillPoly(m, [(np.array(poly_px.exterior.coords) - [x0, y0]).astype(np.int32)], 1); sel = m.astype(bool)
    if sel.sum() < 10: return None
    px = img[sel].astype(float); R, G, B = px[:, 0], px[:, 1], px[:, 2]
    mx, mn = px.max(1), px.min(1); sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    er = cv2.erode(m, np.ones((5, 5), np.uint8)).astype(bool)                   # interior only (ignore the outline)
    ed = edges[er].mean() if er.sum() > 20 else 0
    q = list(poly_px.minimum_rotated_rectangle.exterior.coords); a_, b_ = sorted([math.dist(q[0], q[1]), math.dist(q[1], q[2])])
    gray = img[sel].mean(1)
    return dict(area_m2=poly_px.area * PX * PX, fill=poly_px.area / max(a_ * b_, 1), aspect=b_ / max(a_, 1), short_m=a_ * PX,
                R=R.mean(), G=G.mean(), B=B.mean(), bright=px.mean(), sat=float(np.median(sat)), green=float((G - (R + B) / 2).mean()),
                tex=float(gray.std()), edge=float(ed))
def classify(f):
    if f is None: return 'drop', 'empty'
    if f['area_m2'] < 9: return 'drop', 'too small (object)'
    if f['area_m2'] < 16 and f['aspect'] > 1.7: return 'drop', 'vehicle'
    if f['area_m2'] > 2500: return 'drop', 'too large (yard / block)'
    if (f['green'] > 18 and f['bright'] < 115) or (f['green'] > 14 and f['sat'] > 0.33 and f['bright'] < 110): return 'drop', 'tree / vegetation'
    if f['aspect'] > 6 and f['area_m2'] > 120: return 'drop', 'road / strip'
    if f['R'] > f['G'] + 6 and f['G'] > f['B'] + 6 and f['edge'] < 0.12 and f['tex'] < 22 and f['area_m2'] > 60: return 'drop', 'bare ground / yard'
    if f['short_m'] < 2.2: return 'drop', 'thin strip'
    if f['sat'] < 0.10 and f['edge'] > 0.22 and 105 < f['bright'] < 185 and f['area_m2'] > 40 and f['tex'] > 25: return 'foundation', 'grey concrete with internal wall lines (uncompleted / foundation)'
    return 'building', 'roof'
def orthogonalize(poly_px, tol=2.5):
    """square an outline to its own main direction: edges become parallel / perpendicular to the dominant axis"""
    from shapely import affinity
    q = list(poly_px.minimum_rotated_rectangle.exterior.coords); e = np.array(q[1]) - np.array(q[0])
    th = math.degrees(math.atan2(e[1], e[0])); c = poly_px.centroid
    r_ = affinity.rotate(poly_px, -th, origin=c).simplify(tol)
    if r_.geom_type != 'Polygon': return None
    pts = np.array(r_.exterior.coords)[:-1]
    if len(pts) < 4: return None
    out = [pts[0].copy()]
    for i in range(1, len(pts) + 1):
        prev = out[-1]; cur = pts[i % len(pts)].copy()
        if abs(cur[0] - prev[0]) > abs(cur[1] - prev[1]): cur[1] = prev[1]
        else: cur[0] = prev[0]
        if i < len(pts): out.append(cur)
        else: out[0][0 if abs(cur[0] - prev[0]) <= abs(cur[1] - prev[1]) else 1] = cur[0 if abs(cur[0] - prev[0]) <= abs(cur[1] - prev[1]) else 1]
    poly = Polygon(out).buffer(0)
    if poly.is_empty: return None
    poly = max(shapely.get_parts(poly), key=lambda g: g.area)
    return affinity.rotate(poly, th, origin=c)
def regularize(poly_px):
    rect = poly_px.minimum_rotated_rectangle
    if poly_px.area / rect.area >= 0.85: return rect
    o = orthogonalize(poly_px)
    if o is not None and o.is_valid and 0.8 < o.area / poly_px.area < 1.2 and o.intersection(poly_px).area / poly_px.area > 0.8: return o
    p = poly_px.simplify(2.0)
    return p if p.is_valid and not p.is_empty else poly_px
def drop_containers(polys, keep_idx, return_containers=False):
    """a mask that covers two or more other kept masks is a yard / compound outline, not a building"""
    out = []; cont = []
    tree = shapely.STRtree([polys[i] for i in keep_idx])
    for k, i in enumerate(keep_idx):
        cand = tree.query(polys[i])
        inside = [keep_idx[j] for j in cand if keep_idx[j] != i and polys[keep_idx[j]].area < 0.7 * polys[i].area and polys[keep_idx[j]].intersection(polys[i]).area > 0.7 * polys[keep_idx[j]].area]
        if len(inside) >= 2: cont.append(i); continue
        out.append(i)
    return (out, cont) if return_containers else out
def dedupe(polys, scores, thr=0.5):
    """non-maximum suppression on overlapping masks: keep the higher-scoring one"""
    order = np.argsort(-np.asarray(scores)); kept = []; tree = shapely.STRtree(polys); taken = np.zeros(len(polys), bool)
    for i in order:
        if taken[i]: continue
        kept.append(i)
        for j in tree.query(polys[i]):
            if j == i or taken[j]: continue
            inter = polys[i].intersection(polys[j]).area
            if inter / min(polys[i].area, polys[j].area) > thr and min(polys[i].area, polys[j].area) / max(polys[i].area, polys[j].area) > 0.5: taken[j] = True
    return kept

# ---- from ml4/walls.py ----
"""Wall / fence line detection: thin bright ridges (wall tops) with straight-line fitting, outside buildings."""
import numpy as np, cv2, shapely
from skimage.filters import sato
from skimage.morphology import skeletonize, remove_small_objects
from skimage.transform import probabilistic_hough_line
from shapely.geometry import LineString
from shapely.ops import unary_union
def detect_walls(rgb, building_polys_px, px=0.299, min_len_m=4.5):
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(float) / 255
    rid = sato(g, sigmas=[1.0, 1.5], black_ridges=False)                       # bright thin lines (wall tops)
    thr = np.percentile(rid, 93); m = rid > thr
    m = remove_small_objects(m, 25)
    sk = skeletonize(m)
    lines = probabilistic_hough_line(sk, threshold=8, line_length=int(min_len_m / px), line_gap=3, rng=0)
    B = unary_union([p.buffer(3) for p in building_polys_px]) if building_polys_px else None
    # road surface: wide uniform grey areas (low local texture, low saturation, medium brightness)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV); gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(float)
    mu = cv2.blur(gray, (15, 15)); sd = np.sqrt(np.maximum(cv2.blur(gray * gray, (15, 15)) - mu * mu, 0))
    road = (sd < 9) & (hsv[:, :, 1] < 40) & (gray > 70) & (gray < 150)
    road = cv2.morphologyEx(road.astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8)).astype(bool)
    out = []
    for (x0, y0), (x1, y1) in lines:
        s = LineString([(x0, y0), (x1, y1)])
        if B is not None and s.intersection(B).length > 0.5 * s.length: continue
        n = max(2, int(s.length)); xs = np.linspace(x0, x1, n).astype(int); ys = np.linspace(y0, y1, n).astype(int)
        if road[np.clip(ys, 0, road.shape[0] - 1), np.clip(xs, 0, road.shape[1] - 1)].mean() > 0.5: continue
        out.append(s)
    # merge near-collinear overlapping segments
    merged = shapely.line_merge(unary_union([s.buffer(1.2, cap_style=2) for s in out]).boundary) if out else None
    return out, road

# ---- from ml4/road_surface.py ----
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
_rs_unit = lambda v: np.asarray(v, float) / (np.linalg.norm(v) + 1e-12)
def _out_dir(l, at_start):
    c = np.array(l.coords)[:, :2]
    k = 1
    while k < len(c) - 1 and np.linalg.norm(c[k] - c[0] if at_start else c[-1 - k] - c[-1]) < 1e-6: k += 1
    return _rs_unit(c[0] - c[k]) if at_start else _rs_unit(c[-1] - c[-1 - k])        # pointing out of the line at that end
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

# ---- from ml4/obm.py ----
"""Building footprint database (D:/Work/2026/Data): OpenBuildingMap-style merge of Google Open Buildings, OSM and Microsoft,
with GEM-taxonomy occupancy and height. One GeoPackage per level-6 quadkey tile, layer 'building', EPSG:4326.
Fields: id, floorspace, occupancy, relation_id, quadkey, last_update, source_id (0 OSM, 1 Google, 2 Microsoft), height ('HBET:1-5' = 1-5 storeys).
Tiles on disk: 033331 (western Ghana / Takoradi-Kumasi belt), 033333 (Accra / south-east), 122220 (north)."""
import math, os, pyogrio, geopandas as gpd
SOURCE = {0: 'OSM', 1: 'Google Open Buildings', 2: 'Microsoft'}
# GEM building taxonomy occupancy -> planning land-use class
OCC = {'RES': 'Residential', 'RES1': 'Residential', 'RES2': 'Residential', 'RES3': 'Residential',
       'COM': 'Commercial', 'COM1': 'Commercial', 'COM2': 'Commercial (wholesale / storage)', 'COM3': 'Office', 'COM4': 'Commercial (hotel)',
       'COM5': 'Commercial (entertainment)', 'COM6': 'Civic', 'COM7': 'Commercial (parking)', 'COM8': 'Transport terminal', 'COM9': 'Transport terminal',
       'COM10': 'Transport terminal', 'COM11': 'Recreation',
       'MIX': 'Mixed use (shop + residence)', 'MIX1': 'Mixed use (shop + residence)', 'MIX2': 'Mixed use (shop + residence)', 'MIX3': 'Mixed use (shop + residence)',
       'MIX4': 'Mixed use (industrial + commercial)', 'MIX5': 'Mixed use (industrial + commercial)', 'MIX6': 'Mixed use (commercial + industrial)',
       'IND': 'Industrial', 'IND1': 'Industrial', 'IND2': 'Industrial',
       'AGR': 'Agricultural', 'AGR1': 'Agricultural', 'AGR2': 'Agricultural', 'AGR3': 'Agricultural',
       'EDU': 'Education', 'EDU1': 'Education', 'EDU2': 'Education', 'EDU3': 'Education', 'EDU4': 'Education',
       'GOV': 'Civic', 'GOV1': 'Civic', 'GOV2': 'Civic', 'ASS': 'Religious / assembly', 'ASS1': 'Religious', 'ASS2': 'Recreation', 'ASS3': 'Recreation', 'ASS4': 'Religious / assembly'}
def _obm_quadkey(lat, lon, z):
    x = (lon + 180) / 360; s = math.sin(math.radians(lat)); y = 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)
    tx, ty = int(x * 2 ** z), int(y * 2 ** z); q = ''
    for i in range(z, 0, -1):
        d = 0; m = 1 << (i - 1)
        if tx & m: d += 1
        if ty & m: d += 2
        q += str(d)
    return q
def tile_path(qk6): return f'{OBM_ROOT}/building.{qk6}.gpkg/building.{qk6}.gpkg'
def obm_load(site, buffer_deg=0.0005, crs=2136):
    """Buildings intersecting `site` (a GeoSeries / GeoDataFrame in any CRS). Returns GeoDataFrame in `crs` with decoded source and use."""
    s4 = site.to_crs(4326); geom = s4.union_all().buffer(0); w, so, e, n = s4.total_bounds
    tiles = {_obm_quadkey(la, lo, 6) for la in (so, n) for lo in (w, e)}; parts = []
    for qk in tiles:
        f = tile_path(qk)
        if not os.path.exists(f): print(f'obm: tile {qk} not on disk ({f})'); continue
        g = pyogrio.read_dataframe(f, layer='building', bbox=(w - buffer_deg, so - buffer_deg, e + buffer_deg, n + buffer_deg))
        parts.append(g[g.intersects(geom.buffer(buffer_deg))])
    if not parts: return gpd.GeoDataFrame(columns=['id', 'occupancy', 'height', 'source', 'use_obm', 'geometry'], geometry='geometry', crs=crs)
    import pandas as pd
    G = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326).drop_duplicates('id')
    G['source'] = G.source_id.map(SOURCE).fillna('unknown'); G['use_obm'] = G.occupancy.map(OCC)
    return G.to_crs(crs).reset_index(drop=True)


GUIDE = r"""# LP Toolkit: local plan preparation guide

Everything learned while preparing the test local plans (test.kml, Tests 2 to 5, Obusomase, Phase One, STMA scheme study) in one place.
This guide is printed by `python lp_toolkit.py guide` and is also written next to the script as `LP_Toolkit_Guide.md`.

## 1. What the toolkit does

Two workflows, each a chain of stages that read and write files in one output folder.

**A. Existing situation (upgrading areas, built-up land).** Run with `existing`.

| Stage | What it does | Main outputs |
|---|---|---|
| fetch | Esri World Imagery z19 (0.3 m), OSM buildings / roads / POIs, Microsoft footprints, building database | `_work/img_z19_3857.tif`, `_work/osm_*.gpkg`, `_work/ms_buildings.gpkg` |
| sam | Segment Anything (vit_b) masks over the image in 1024 px tiles, 160 px overlap | `_work/tiles/*.pkl` |
| digitize | Mask classification (roof, tree, vehicle, road, bare ground, foundation), duplicate and container removal, orthogonal outlines, wall lines | `<P>Buildings.shp`, `<P>Walls.shp` |
| compare | Check against OSM + Microsoft: shift the reference onto the image, merge split roofs, keep the outline that fits roof edges, add missed roofs | `<P>Buildings_corrected.shp`, `<P>comparison_report.json` |
| clean | Drop vehicles, vegetation, bare ground, blobs; flag foundations; final walls | `<P>Buildings_final.shp`, `<P>Walls_final.shp`, `<P>digitizing_summary.xlsx` |
| database | Check against the building database (Google / OSM / Microsoft with occupancy): split our blobs, swap better outlines, add missing buildings, attach occupancy and height | `<P>Buildings_final.shp` (backup `_pre_obm`), `<P>database_check_report.json` |
| roads | Carriageway width per road measured on the image; walls on the carriageway removed | `<P>Carriageways.shp` |
| landuse | Road reserves (building line to building line), existing use per building (OSM tag, then database occupancy, then rules), vacant land | `<P>Roads_existing.shp`, `<P>Existing_land_use_buildings.shp`, `<P>Vacant_open_land.shp` |
| reserves | Road centrelines realigned to the image; reserves re-measured; pinch points | `<P>Road_pinch_points.shp` |
| trees | Continuous tree belt / drain corridor from the image (its own land use) | `<P>Tree_belt_raw.shp` |
| blocks | Road surface (carriageway + 2 m footways) and blocks | `<P>Blocks_existing.shp`, `<P>Road_surface.shp` |
| plots | Existing plot subdivision by the halving rule (section 4) | `<P>Plots_existing.shp`, `<P>Tree_belt_existing.shp` |
| map | Existing land use map and tables | `<P>Existing_land_use_map.png`, `<P>Existing_land_use_tables.xlsx` |
| footpaths | OPTIONAL TRIAL: footpaths from open space between buildings (not reliable in dense cores) | `<P>Footpaths_TRIAL.shp` |
| proposals | OPTIONAL: upgrading proposals (mixed-use corridor, greenway, pocket parks, refuse points, facility gaps). Only when the user asks for proposals | `<P>Upgrading_plan_*.{png,xlsx}` |

**B. New layout (greenfield local plan).** Run with `design`.

| Stage | What it does |
|---|---|
| site | Imagery and Copernicus 30 m DEM warped to EPSG:2136, buildings from the database, site analysis map |
| roads | Road layout, three options: (1) `--roads file`: the planner's centrelines (with `width_ft`); (2) `--roads auto`: the toolkit designs the roads from the rules in section 6; (3) `--roads draft`: the toolkit drafts `<P>Roads_draft.shp`, the planner edits it and reruns with `--roads <edited> --from roads`. Then reserves (T-branch ends trimmed), blocks and the concept file |
| subdivide | Plots by the Phase One rule (section 5) |
| landuse | Facility programme (LUSPA + STMA rates and site shapes, section 7) |
| audit | Design audit: every flaw with location and suggested fix (section 8). Run after every design |

**Web app.** `run_webapp.bat` opens the same workflows in the browser (http://localhost:5050; `run_webapp.bat --lan` lets other computers on the office network open it). Projects are kept in `D:/Work/2026/Machine Learning/LP_Projects/`. Draw or upload the site, roads (with widths), existing roads and streams on the satellite map; choose the road option; run with a live log; view the results as map layers (plots by use, audit findings) and download everything as a zip.

**Site analysis comes first.** The `site` stage prepares the terrain before any road is drawn: Copernicus 30 m DEM, contours at an interval adapted to the relief (1, 2, 5, 10 m...), slope in percent, slope classes (flat 0-5%, gentle 5-10%, moderate 10-18%, steep 18-30%: no roads straight downhill, very steep > 30%: keep green) and the steep-slope reserve (slopes >= `--steep` %, default 30, pieces >= 0.5 ac kept green and excluded from blocks). Outputs: `<P>Contours.shp`, `<P>Slope_classes.shp`, `<P>Slope_percent.tif`, `<P>Steep_slope_reserve.shp`, `<P>Terrain_summary.json`, `<P>Site_analysis.png`, map overlays. In the web app: "Prepare site analysis", then review the terrain layers before planning roads.

**Three road patterns** (`--pattern grid | curvilinear | ringband`; `--roads draft` drafts all three and compares them in `<P>Roads_patterns.png/.json`):
- Grid iron: straight two-row blocks along the parcel's main road edge.
- Curvilinear: rows are nested parallel curves of the parcel's contour line, 230 ft apart; cross roads are normals to that curve (square to every parallel). Follows the user's nested-curve rule and the Tokunaso / Beposo curved distributors. On steep sites the parallels drift off the true contour away from the centre line, so check the steep-road figure.
- Ring and band: the user's N1 method: a 200 ft band of plots along the parcel edges behind a 30 ft ring road with rounded corners, an inner grid in the core, cross roads continued through the ring to the outer roads (4-way).
All patterns keep the stream and steep-slope reserves green and are scored for road length steeper than 18%. Obusomase (hilly, 161 m relief): grid 1,382 plots / 4.9 km steep road; curvilinear 1,361 / 5.2 km; ring and band 1,411 / 4.8 km (suggested).

The automatic road layout (option 2) keeps existing roads on their alignment and carries them into the site, splits parcels over 35 ac with 40 ft collectors, lays a grid in each parcel along its highest-order road edge (30 ft roads 230 ft apart for two 100 ft plot rows, cross roads 520 ft apart for seven 70 ft plots), tries several grid offsets and orientations and keeps the one with the most standard blocks and fewest building conflicts, and bends sharp arrivals square. It is a draft: on Test 3 it gave 437 residential plots (80% standard) but 10 high audit findings (junction angles, staggered T junctions) against 0 for the hand-tuned layout. Always review the audit, and prefer option 3 (draft and edit) for real plans.

`<P>` is the file prefix (the site name without spaces, for example `Test5_`). Every stage can be re-run alone (`--only`) or from a point onwards (`--from`).

## 2. Data sources and how to get them

| Source | Use | Notes |
|---|---|---|
| Satellite imagery (contextily, zoom 19): Google satellite by default (user choice 2026-11-17, Esri kept dropping connections), Esri World Imagery as the fallback (`--imagery esri` to prefer Esri) | Digitizing, checks, map backgrounds | 0.3 m/px at 5.5 N; 8 retries per tile, then a slow single-connection pass, then the other source. Google's terms allow its imagery only through official Google tools: fine for internal planning, use Esri or licensed imagery for published maps. The digitizing colour rules were calibrated on Esri (green cast): check the first Google runs against the building database |
| **Building database** `D:/Work/2026/Data` | Footprints, occupancy, storey height | One GeoPackage per level-6 quadkey tile, layer `building`, EPSG:4326, ODbL. Tiles on disk: 033331, 033333 (Accra / south-east, 4.1 M buildings), 122220. Fields: id, occupancy (GEM taxonomy), height (`HBET:1-5` = 1 to 5 storeys), floorspace (rare), source_id (0 OSM, 1 Google Open Buildings, 2 Microsoft). Occupancy is good where OSM is rich (Osu 78% known), almost all UNK in indigenous cores (La). The `Ghana buildings.gdb` beside it is an empty ArcGIS project geodatabase |
| OSM via Overpass | Roads (with names and class), POI tags, buildings | Overpass servers are often overloaded (502/504). The toolkit tries overpass-api.de, kumi, private.coffee, mail.ru, then falls back to the main OSM API `/api/0.6/map?bbox=` (works for sites up to about 0.25 sq deg / 50,000 nodes) |
| Microsoft Global ML Building Footprints | Reference footprints | `dataset-links.csv` + level-9 quadkey tile (Accra = 033333111); cached in `LP_Toolkit/cache/ms` |
| Copernicus DEM 30 m (AWS) | Terrain, slope, drainage, facility siting | `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N05_00_W001_00_DEM/...` (tile by integer lat/lon) |
| STMA scheme study | Learned plot / block / road / facility statistics | `D:/Work/2026/Machine Learning/Results_STMA_Schemes/STMA_Scheme_Design_Rules.md` (section 7) |
| User's local plans | Layout patterns | `All Scaned Maps Arranged` root: Tokunaso (sections A/B/C), Beposo extension, Prestea-Brumasi industrial park, Wassa Mampong (Fig. 10), Cosmax/Hemax LP1 |
| LUSPA training deck | Design principles and flaws | "LOCAL PLAN PREPARATION II.pptx" slides 40 to 55 (section 8) |
| Zoning Guidelines and Planning Standards (LUSPA 2025) | Governing standards | Govern wherever the past schemes differ (for example 30 ft minimum access road) |

Coordinate system for all planning work: **EPSG:2136 (Ghana National Grid, Gold Coast feet)**. 1 ft = 0.3048 m; 1 acre = 43,560 sq ft.

Privacy: never send the user's name, e-mail or project names to outside services. Use the generic user agent `gis-planning-client`.

## 3. Digitizing from imagery: settings that worked

- SAM vit_b checkpoint `models/sam_vit_b_01ec64.pth`, `points_per_side=48`, `pred_iou_thresh=0.82`, `stability_score_thresh=0.88`, `min_mask_region_area=50`. About 3 minutes per 1024 px tile on CPU (16 threads); a 55 ac site is 12 tiles, 163 ac is 25 tiles. The computer must not sleep during the run (tiles already done are skipped on restart).
- Classification rules (per mask, cropped to its bounding box for speed): drop under 9 m2; vehicle = small and elongated; over 2,500 m2 = yard / block; tree if (green > 18 and bright < 115) or (green > 14 and sat > 0.33 and bright < 110), calibrated for the green cast of Esri imagery; foundation = grey (sat < 0.10), many internal edges (edge > 0.22), bright 105 to 185, area > 40, texture > 25.
- Duplicate removal only between masks of similar size (ratio > 0.5), otherwise roofs inside compounds disappear. Compound outlines (containers) are removed.
- Outlines: rectangle if fill >= 0.85, else orthogonalized.
- Walls: Sato ridge filter, skeleton, probabilistic Hough, segments off roofs and off road surface, collinear pieces joined. Interior compound walls are incomplete.
- Foundations cannot be told apart from flat grey roofs reliably: they are flagged "possible uncompleted / foundation - verify", not dropped.
- Comparison: shift the reference onto the image first (Osu OSM was about 0.6 m off; database about 0.5 to 0.9 m). Merge only when two or more of our pieces sit inside one reference building. On a 1:1 match keep the outline with the higher mean image gradient along it (fits the roof edge).
- **Always check footprints against the building database.** In dense indigenous cores (La) SAM misses many small roofs and Microsoft draws one blob over several houses; Google footprints in the database are far better there. Expected after the database step: Osu 2,223 -> 2,908 buildings; La 1,006 -> 1,785.
- Footpaths in dense cores cannot be mapped reliably from 0.3 m imagery: houses touch and roofs overhang the alleys. Use field GPS, midday drone imagery or local knowledge. The `footpaths` stage is a trial only.

## 4. Existing plot subdivision (upgrading areas)

The user's rule (2026-11-16): **subdivision follows the same principle everywhere. A block 200 ft or 240 ft wide is divided by 2, whether it is straight or curved. Try this before any other method.**

How the toolkit applies it:
1. Blocks = site minus road surface (carriageway buffers + 2 m footways). The tree belt is removed first as its own use.
2. Straight blocks (fill of the minimum rotated rectangle >= 0.72): split along the long axis at the line that cuts the least building (within +-25% of the middle, mild preference for the middle). Blocks narrower than the single-row depth stay one row.
3. Curved or irregular blocks: every point goes to the nearer of the two long opposite frontages (distance field at 0.15 m), so the row line is the curve halfway between them.
4. Plot lines square to the frontage (normal to the curve on curved roads), placed by dynamic programming to cut as little building as possible, with a bonus where a detected wall runs; frontage within the profile range.
5. Block ends: oversized end wedges are re-cut square to the side street they run along (plots facing the side street).
6. Any plot still deeper than the profile maximum is halved again at the line of least building cut, never through a large (> 500 m2, image-confirmed) building. Back plots with no road are flagged `Interior (access lane not mapped - verify)`; plots on the site boundary are `Site edge (road outside site)`.
7. Plot use = the plot's most specific tagged building (OSM tag / database occupancy), else its largest building.

Profiles (chosen automatically from the median size of image-digitized buildings, threshold 70 m2, or set with `--profile`):

| Profile | For | Frontage | Single row if block narrower than | Halve plots deeper than | End-wedge re-cut |
|---|---|---|---|---|---|
| planned | Planned / estate areas (Osu) | 12 to 25 m | 45 m | 65 m | area > 1,000 m2 and depth > 50 m |
| compact | Indigenous / compound cores (La) | 9 to 18 m | 30 m | 40 m | area > 500 m2 and depth > 36 m |

Methods that failed and must not be used again: Voronoi partition between buildings (spikes, 115% coverage); piece-level Voronoi rows (diagonal bisectors); band buffers with leftover attachment (spikes); frontage rows plus interior core for superblocks (blobs). The width test for curved blocks uses the equal area and perimeter rectangle on a 6 m simplified outline, never 2A/(P/2).

## 5. New plot subdivision (Phase One rule)

1. Offset the front road line by 100 ft (offset the curve on curved blocks): a 200 ft block becomes two 100 ft halves. Extend the mid line to touch the road lines at both block ends.
2. Cut at the chosen frontage, perpendicular to the mid line, each cut road edge to road edge. On curves size each plot to at least frontage x 100 sq ft, close to the standard dimensions.
3. Measure the whole block length first. **Only the first and last plots absorb the leftover** (510 ft gives 80, 70, 70, 70, 70, 70, 80). Middle plots stay exactly the standard. Never below 65 ft frontage.
4. Size options 65, 70, 75, 80 ft, always 100 ft deep, one size per block: pick the size where each end plot takes at most +10 ft, smallest leftover; ties go to 70, then 75, 65, 80. If none fits, mix sizes symmetrically with the larger at the ends.
5. Front row always 100 ft deep; in deeper blocks the back row takes the extra depth. 80 ft frontage on major roads. Residential B minimum 0.16 ac (6,970 sq ft).
6. Act 925 s72(3)(a): a local plan needs at least 20 plots, each at least 110 m2.
7. Do not put an access road through the middle of a block that already lies between two roads.

## 6. Road layout: how the user designs (the planner draws, the tool assists)

The road layout is the planner's decision. The user stopped automatic designs and asked the tool to learn from how they draw in Line.shp (watch edits read-only; never write to Line.shp while they edit). Rules learned:

- **Junctions 80 to 90 degrees** (never below 70). Bend road ends to arrive square. No Y or knife-edge junctions, no wedge blocks.
- **No staggered T junctions.** Every road reaching a road from one side lines up with a road on the other side (4-way) or has nothing opposite. Existing roads arriving at the site are carried straight in first; the grid is built off them.
- **No double frontage**: no single-row blocks between two parallel roads.
- **Blocks run parallel to the highest-order road beside them**, so few roads enter it. Hierarchy: 100 ft > 60 ft > 40 ft collector > 30 ft local; only 40 ft collectors join the 60 / 100 ft roads.
- Grid direction per parcel follows the edge facing the main connecting road, not simply the straightest edge.
- Bands: a 200 ft band along edges behind a 30 ft road; inner 30 ft grid roads square to the main edge, 200 ft apart (two rows of 100 ft plots); blocks about 400 to 520 ft long, never over 600 to 700 ft; break blocks where cross roads arrive.
- Large faces (60 to 70 ac) are first split by curved 30 ft connectors into 25 to 40 ac parcels. Strongly curved edges get nested curved inner roads offset 200 ft + road, not a straight grid.
- Every road end trimmed to the crossing road edge; edge lines join at corners with no overshoots, no lines across road mouths, no hairline gaps; never delete the back line of plots where a road dead-ends against a block.
- Cul-de-sacs no longer than 200 m (656 ft). Short corner blocks about 200 x 200 to 250 ft are fine.
- Blend patterns (grid + curved / crescent + cul-de-sac), not one pattern only.
- Patterns from the user's local plans: (1) streams as a continuous green buffer with blocks backing onto it and roads crossing only where needed; (2) existing roads kept on alignment and existing built-up areas retained as blocks; (3) a straight grid of two-row blocks per sector, orientation following each sector's main road; (4) triangular wedges where grids meet become worship / open space / S.A / clinic / corner shop, not odd plots; (5) curved distributors with fanned blocks; (6) mixed commercial-residential frontage on main roads; (7) neighbourhood clusters: basic school + playground, S.A + U.T pairs, corner shops, day care.
- Terrain: schools, health and football parks on the flattest well-drained blocks; S.A on low ground by the green, at least 300 ft from schools and clinics; UT (water tanks and masts) on high ground, at least 300 ft from schools, day cares and clinics; flag roads steeper than about 18% running straight downhill.
- Learned road widths (STMA): 20-25 ft lanes (49%), 30-35 ft (18%), 40-45 ft (19%), 50 ft and over (6%). The 2025 Guidelines require 30 ft minimum access roads.

Input for `design --roads`: a line file (shp / gpkg / kml) of road centrelines with a `width_ft` field (or a `class` text containing the width, for example "40 ft collector"). Optional `--stream` polygon or line file with `--stream-buffer` (ft).

## 7. Land use programme and facility rules

Programme: LUSPA Manual 4.6.3 + the 2025 Guidelines mandatory list. Rates, site sizes and shapes learned from 65 approved STMA schemes (39,846 plots); the Guidelines govern where they differ.

| Facility | Learned rate | Learned site | Shape |
|---|---|---|---|
| School | 1 per 144 plots | 1.82 ac (0.92 to 3.02), about 265 x 380 ft | full small block, 79% near-square |
| Place of worship | 1 per 159 plots | 0.90 ac (0.68 to 1.21) | compact, 2 rows deep, 2 to 3 plots long |
| Market / commercial | 1 per 229 plots | 0.59 ac (0.23 to 1.58) | elongated along the road, often a corner |
| Open space | 1 per 271 plots | 1.37 ac (0.49 to 2.70) | defined scheme-sized P.O.S only |
| Sanitary area | 1 per 356 plots | 0.28 ac, about 100 x 155 ft | 1 to 2 plots |
| Health | 1 per 653 plots | 0.88 ac (Guidelines minimum 0.5 ac for a health post) | compact |
| Civic / community, police, nursery, lorry park | 1 per 600 to 1,700 plots | 0.8 to 0.9 ac | compact near-square |
| Utility | 1 per 613 plots | 0.20 ac, about one plot | |
| Cemetery | 1 per 1,475 plots | 2.6 ac | |

- Community uses take a whole block depth as compact 2 x 2 or 2 x 3 plot squares across both rows, never single plots or strips along one row.
- No open space inside school land; no undefined football / sports field (none appears in any scheme).
- Market and health post on the gateway corners (collector x main road); school as a clean whole block on the collector; worship one each side of the main road.
- Access: every home within 800 m of a basic school (stricter than the Guidelines' 2.5 km); open space within about 400 m; S.A within 500 m (2025 standard).
- LUSPA standards: primary school per neighbourhood of 5,000; JHS per 10,000; SHS per 20,000; worship catchment up to 15,000; local shop up to 500 persons; local market up to 30,000 (+20 to 50% parking); police and fire up to 35,000; hydrants every 120 m on major roads.
- Population for checks: 7.2 persons per plot (Obusomase assumption) for new layouts. For existing areas: 1.5 storeys average, 60 m2 per household, 3.4 persons per household (provisional, Osu).
- Harmony: no S.A beside a playground, school or clinic.

## 8. Checks to run before presenting anything (self-audit)

The user reviews like a planning officer. Catch the flaws before they do.

Layout (`design` audit):
- Junction angles (80 to 90; flag under 70), staggered T, Y junctions, dead ends over 200 m, block length over 600 ft, blocks over two lines of 8 plots without a break, double frontage, landlocked plots, plots below the standard, uneven splits, facility shapes (compact, near-square), harmony distances, riparian buffers.

Existing situation:
- Footprints: compare counts and roof-area IoU with the building database; look at a crop in the dense core and a crop in a planned area before accepting.
- Plots: buildings cut by plot lines, plots deeper than 60 m, open / yard plots, interior plots, overlap = 0, coverage about 100%. Look at curved blocks and block ends on the image before presenting.
- Maps: legend outside the map frame (never covering the site); building outlines in a colour distinct from plot lines; no empty legend entries; title with the place name.

Reporting rules: say what failed and what is uncertain; give numbers; no proposals unless asked; no em dashes in documents (use colons, commas or parentheses).

## 9. Operational lessons

- Close output files in ArcGIS / image viewers before a run: Windows locks open files. The map stage saves `_v2.png` when the map is open elsewhere. ArcGIS Pro also locks file geodatabases ("permission denied").
- Shapefile field names are cut to 10 characters (carriage_w_m -> carriage_w); the toolkit reads the short names.
- KML polygons carry Z: always force 2D.
- Filter degenerate geometries (non-polygons, under 10 sq ft) before rectangle metrics.
- Keep working files out of temporary folders. The toolkit keeps them in `<output>/_work/`.
- The Python environment is `LP_Toolkit/env` (copied from the working environment; packages: geopandas, shapely 2, rasterio, opencv, scikit-image, scipy, networkx, contextily, pyogrio, torch CPU, segment_anything, matplotlib, openpyxl). Run with `LP_Toolkit\run.bat ...` or `env\Scripts\python.exe lp_toolkit.py ...`.

## 10. Reference runs

| Site | Area | Buildings (final) | Blocks | Plots | Notes |
|---|---|---|---|---|---|
| Test 4, Osu (planned) | 163.7 ac | 2,908 | 58 | 788 | profile planned; 335 buildings cut; commercial strip along Oxford St from database occupancy |
| Test 5, La (compact core) | 55.2 ac | 1,785 | 18 | 441 | profile compact; 131 interior plots (unmapped footpaths); occupancy unknown in database |
| Test 3 (greenfield, stream) | 142 ac | | 49 | 389 residential | design workflow; open issue: NE sector landlocked pockets |
"""


# =====================================================================================================================
# Stage: fetch (existing workflow) - imagery, OSM (Overpass with fallbacks, then the OSM API), Microsoft footprints, database
# =====================================================================================================================
OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter',
            'https://overpass.private.coffee/api/interpreter', 'https://maps.mail.ru/osm/tools/overpass/api/interpreter']
def _http(url, data=None, timeout=180):
    import urllib.request, urllib.parse
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()
def overpass(query, timeout=60):
    for u in OVERPASS:
        try:
            txt = _http(u, {'data': query}, timeout=timeout).decode('utf-8')
            if '"elements"' in txt: return json.loads(txt)
            print('   overpass busy:', u, flush=True)
        except Exception as e: print('   overpass failed:', u, str(e)[:80], flush=True)
        time.sleep(3)
    return None
def osm_api_map(w, s, e, n, _depth=0):
    """main OSM API: returns nodes {id: (lon, lat, tags)} and ways [(id, tags, coords)].
    The API refuses areas with more than 50,000 nodes (HTTP 400): the box is then cut into 4 tiles (recursively) and merged."""
    import xml.etree.ElementTree as ET, urllib.error
    try: raw = _http(f'https://api.openstreetmap.org/api/0.6/map?bbox={w},{s},{e},{n}')
    except urllib.error.HTTPError as ex:
        if ex.code in (429, 509) and _depth < 8: time.sleep(20); return osm_api_map(w, s, e, n, _depth + 1)        # rate limited: wait and retry
        if ex.code != 400 or _depth >= 6: raise
        if _depth == 0: print('   OSM API: area too dense for one call, fetching it in tiles', flush=True)
        mx, my = (w + e) / 2, (s + n) / 2; nodes, seen, ways = {}, set(), []
        for bb in ((w, s, mx, my), (mx, s, e, my), (w, my, mx, n), (mx, my, e, n)):
            nd, wy = osm_api_map(*bb, _depth=_depth + 1); nodes.update(nd)
            for it in wy:
                if it[0] not in seen: seen.add(it[0]); ways.append(it)
        return nodes, ways
    root = ET.fromstring(raw)
    nodes = {}; ways = []
    for nd in root.iter('node'): nodes[nd.get('id')] = (float(nd.get('lon')), float(nd.get('lat')), {t.get('k'): t.get('v') for t in nd.iter('tag')})
    for wy in root.iter('way'):
        ref = [nodes[x.get('ref')][:2] for x in wy.iter('nd') if x.get('ref') in nodes]
        ways.append((int(wy.get('id')), {t.get('k'): t.get('v') for t in wy.iter('tag')}, ref))
    return nodes, ways
POI_KEYS = ('amenity', 'shop', 'office', 'healthcare', 'tourism', 'leisure', 'landuse', 'building')
def quadkey(lat, lon, z):
    x = (lon + 180) / 360; s = math.sin(math.radians(lat)); y = 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)
    tx, ty = int(x * 2 ** z), int(y * 2 ** z); q = ''
    for i in range(z, 0, -1):
        d = 0; m = 1 << (i - 1)
        if tx & m: d += 1
        if ty & m: d += 2
        q += str(d)
    return q

GOOGLE_SAT = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
IMAGERY_PREF = 'google'                                 # set by --imagery google | esri
def robust_tiles(w, s, e, n, zoom, path=None, ll=True):
    """satellite tiles with retries (8 per tile): preferred source (Google by default), then slowly on 1 connection, then the other source.
    path given: writes a GeoTIFF (EPSG:3857) and returns None; otherwise returns (image, extent) like contextily.bounds2img"""
    import contextily as cx
    G = [('Google satellite', GOOGLE_SAT, 4), ('Google satellite (slow, 1 connection)', GOOGLE_SAT, 1)]
    E = [('Esri World Imagery', cx.providers.Esri.WorldImagery, 4), ('Esri World Imagery (slow, 1 connection)', cx.providers.Esri.WorldImagery, 1)]
    tries = (E + G) if IMAGERY_PREF == 'esri' else (G + E)
    last = None
    for k, (name, src, nc) in enumerate(tries):
        try:
            if path: cx.bounds2raster(w, s, e, n, path, zoom=zoom, source=src, ll=ll, max_retries=8, wait=2, n_connections=nc, timeout=60); out = None
            else: out = cx.bounds2img(w, s, e, n, zoom=zoom, source=src, ll=ll, max_retries=8, wait=2, n_connections=nc, timeout=60)
            print(f'   imagery source: {name}', flush=True)
            if path: open(path + '.source.txt', 'w').write(name + (' (fallback)' if not name.lower().startswith(IMAGERY_PREF) else ''))
            return out
        except Exception as ex:
            last = ex; print(f'   imagery download failed ({name}): {str(ex)[:120]}; trying again in 20 s', flush=True); time.sleep(20)
    raise RuntimeError(f'satellite imagery could not be downloaded (Google and Esri both failed): {last}')
def st_fetch(ctx):
    import geopandas as gpd, pandas as pd, contextily as cx, rasterio, gzip, urllib.request
    from shapely.geometry import Polygon, LineString, Point, shape
    WORK, SITE_KML = ctx['WORK'], ctx['SITE_KML']
    site = gpd.read_file(SITE_KML); site['geometry'] = site.geometry.force_2d(); S = site.to_crs(2136).geometry.iloc[0]
    w, s, e, n = site.total_bounds; b = 0.0006
    # ---- imagery ----
    sf = WORK + 'img_z19_3857.tif.source.txt'
    src_now = open(sf).read() if os.path.exists(sf) else ''
    if os.path.exists(WORK + 'img_z19_3857.tif') and '(fallback)' in src_now:
        print(f'   keeping the imagery from the last download ({src_now}); the preferred source was unavailable then. To try {IMAGERY_PREF} again, delete _work/img_z19_3857.tif', flush=True)
    elif os.path.exists(WORK + 'img_z19_3857.tif') and src_now and not src_now.lower().startswith(IMAGERY_PREF):
        print(f'   imagery source changed to {IMAGERY_PREF}: downloading again (detection tiles from the old imagery are cleared)', flush=True)
        os.remove(WORK + 'img_z19_3857.tif'); [os.remove(f) for f in glob.glob(WORK + 'tiles/*.pkl')]
    if not os.path.exists(WORK + 'img_z19_3857.tif'):
        robust_tiles(w - b, s - b, e + b, n + b, 19, path=WORK + 'img_z19_3857.tif')
    r = rasterio.open(WORK + 'img_z19_3857.tif'); print('   imagery', r.shape, 'px at', round(r.res[0], 3), 'm', flush=True); progress(55, 'imagery')
    # ---- OSM ----
    BB = f'{s - b},{w - b},{n + b},{e + b}'
    small = (e - w + 2 * b) * (n - s + 2 * b) < 0.04
    dB = None if small else overpass(f'[out:json][timeout:50];(way["building"]({BB});relation["building"]({BB}););out geom;')
    dR = overpass(f'[out:json][timeout:50];way["highway"]({BB});out geom;') if dB is not None else None      # all servers busy: go straight to the OSM API
    dP = None if dR is None else overpass('[out:json][timeout:120];(' + ''.join(f'nwr["{k}"]({BB});' for k in POI_KEYS[:-1]) + f'nwr["building"]["building"!="yes"]({BB}););out center tags;'.replace('timeout:120', 'timeout:50'))
    brows, rrows, prows = [], [], []
    if dB is not None and dR is not None and dP is not None:
        for el in dB['elements']:
            if el['type'] == 'way' and len(el.get('geometry', [])) >= 4: brows.append(dict(osm_id=el['id'], building=el['tags'].get('building'), geometry=Polygon([(p['lon'], p['lat']) for p in el['geometry']])))
        for el in dR['elements']:
            if len(el.get('geometry', [])) >= 2: t = el['tags']; rrows.append(dict(osm_id=el['id'], highway=t.get('highway'), name=t.get('name'), lanes=t.get('lanes'), width=t.get('width'), geometry=LineString([(p['lon'], p['lat']) for p in el['geometry']])))
        for el in dP['elements']:
            c = (el.get('lon'), el.get('lat')) if el['type'] == 'node' else (el.get('center', {}).get('lon'), el.get('center', {}).get('lat'))
            if c[0] is None: continue
            t = el.get('tags', {}); key = next((k for k in POI_KEYS if k in t), None)
            prows.append(dict(osm=f"{el['type']}/{el['id']}", key=key, val=t.get(key), name=t.get('name'), geometry=Point(c)))
    else:
        print('   OSM API map call' + ('' if small else ' (Overpass unavailable)'), flush=True); nodes, ways = osm_api_map(w - b, s - b, e + b, n + b)
        for nid, (lo, la, t) in nodes.items():
            key = next((k for k in POI_KEYS[:-1] if k in t), None)
            if key: prows.append(dict(osm=f'node/{nid}', key=key, val=t[key], name=t.get('name'), geometry=Point(lo, la)))
        for wid, t, ref in ways:
            if 'highway' in t and len(ref) >= 2: rrows.append(dict(osm_id=wid, highway=t['highway'], name=t.get('name'), lanes=t.get('lanes'), width=t.get('width'), geometry=LineString(ref)))
            if len(ref) >= 4 and ref[0] == ref[-1]:
                if 'building' in t: brows.append(dict(osm_id=wid, building=t['building'], geometry=Polygon(ref)))
                key = next((k for k in POI_KEYS if k in t and not (k == 'building' and t[k] == 'yes')), None)
                if key: prows.append(dict(osm=f'way/{wid}', key=key, val=t[key], name=t.get('name'), geometry=Polygon(ref).centroid))
    O = gpd.GeoDataFrame(brows, geometry='geometry', crs=4326) if brows else gpd.GeoDataFrame(columns=['osm_id', 'building', 'geometry'], geometry='geometry', crs=4326)
    O = O.to_crs(2136); O = O[O.intersects(S.buffer(30))]; O.to_file(WORK + 'osm_buildings.gpkg')
    Rd = gpd.GeoDataFrame(rrows, geometry='geometry', crs=4326).to_crs(2136); Rd = Rd[Rd.intersects(S.buffer(100))]; Rd.to_file(WORK + 'osm_roads.gpkg')
    Pp = gpd.GeoDataFrame(prows, geometry='geometry', crs=4326) if prows else gpd.GeoDataFrame(columns=['osm', 'key', 'val', 'name', 'geometry'], geometry='geometry', crs=4326)
    Pp = Pp.to_crs(2136); Pp = Pp[Pp.within(S.buffer(50))]; Pp.to_file(WORK + 'osm_poi.gpkg')
    print(f'   OSM: {len(O)} buildings, {len(Rd)} road segments {Rd.highway.value_counts().to_dict()}, {len(Pp)} POIs'); progress(70, 'OpenStreetMap')
    try: fetch_osm_sites(w - b, s - b, e + b, n + b, S, WORK)
    except Exception as ex: print('   OSM site outlines not available:', str(ex)[:100], flush=True)
    # ---- Microsoft footprints (level-9 quadkey tile, cached) ----
    os.makedirs(MS_CACHE, exist_ok=True); links_f = MS_CACHE + '/dataset-links.csv'
    if not os.path.exists(links_f): open(links_f, 'wb').write(_http('https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv'))
    links = pd.read_csv(links_f); geoms = []
    for qk in {quadkey(la, lo, 9) for la in (s, n) for lo in (w, e)}:
        for url in links[links.QuadKey.astype(str).str.zfill(9) == qk].Url:
            fn = MS_CACHE + '/' + url.split('/')[-1]
            if not os.path.exists(fn): urllib.request.urlretrieve(url, fn)
            with gzip.open(fn, 'rt') as f:
                for line in f:
                    g = shape(json.loads(line)['geometry']); c = g.centroid
                    if w - 0.001 < c.x < e + 0.001 and s - 0.001 < c.y < n + 0.001: geoms.append(g)
    M = gpd.GeoDataFrame(geometry=geoms, crs=4326).to_crs(2136); M = M[M.intersects(S.buffer(30))]; M.to_file(WORK + 'ms_buildings.gpkg'); print('   Microsoft footprints', len(M)); progress(85, 'Microsoft')
    # ---- building database ----
    G = obm_load(site); G.to_file(WORK + 'obm_buildings.gpkg'); print('   building database', len(G), G.source.value_counts().to_dict() if len(G) else '')

# =====================================================================================================================
# Design workflow: site (imagery + DEM + database buildings), roads (planner's centrelines -> reserves, blocks, concept)
# =====================================================================================================================
def fetch_dem(site4326, out_tif, buf=0.004):
    import rasterio
    from rasterio.windows import from_bounds
    w, s, e, n = site4326.total_bounds; w, s, e, n = w - buf, s - buf, e + buf, n + buf
    lat, lon = math.floor((s + n) / 2), math.floor((w + e) / 2)
    tile = f"Copernicus_DSM_COG_10_{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00_{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00_DEM"
    url = f'https://copernicus-dem-30m.s3.amazonaws.com/{tile}/{tile}.tif'
    with rasterio.open(url) as r:
        win = from_bounds(w, s, e, n, r.transform); a = r.read(1, window=win); t = r.window_transform(win)
        prof = {k: v for k, v in r.profile.items() if k not in ('blockxsize', 'blockysize', 'tiled', 'compress', 'interleave')}
        prof.update(height=a.shape[0], width=a.shape[1], transform=t, driver='GTiff')
        with rasterio.open(out_tif, 'w', **prof) as d: d.write(a, 1)
    print('   DEM', a.shape, 'elevation', float(np.nanmin(a)), '-', float(np.nanmax(a)), 'm')
def st_design_site(ctx):
    import geopandas as gpd
    WORK, SITE_KML = ctx['WORK'], ctx['SITE_KML']
    site = gpd.read_file(SITE_KML)
    if not os.path.exists(WORK + 'dem.tif'): fetch_dem(site, WORK + 'dem.tif')
    G = obm_load(site); G.to_file(WORK + 'buildings.gpkg'); print('   existing buildings (database)', len(G))
    fetch_osm_roads_water(site, WORK)
    _design_site_analysis(ctx)
    terrain_products(ctx)
def _width_of(row):
    for k in ('width_ft', 'WIDTH_FT', 'width', 'Width', 'reserve_ft'):
        if k in row and row[k] is not None and str(row[k]) not in ('', 'nan', 'None'):
            try: return float(row[k])
            except Exception: pass
    for k in ('class', 'Class', 'CLASS', 'name', 'Name', 'type'):
        if k in row and isinstance(row[k], str):
            m = re.search(r'(\d+(?:\.\d+)?)\s*(ft|feet|\')', row[k])
            if m: return float(m.group(1))
    return 30.0
def st_design_roads(ctx):
    """planner's road centrelines (width_ft or a class text with the width) -> layout_roads / layout_centrelines / layout_blocks / concept"""
    import geopandas as gpd, shapely
    from shapely.geometry import Polygon, Point, LineString, box
    from shapely.ops import unary_union
    WORK, SITE_KML = ctx['WORK'], ctx['SITE_KML']
    mode = (ctx.get('roads') or '').lower()
    if mode in ('auto', 'draft'):
        st_design_autoroads(ctx)
        if mode == 'draft':
            print(f"   DRAFT written: {ctx['D']}{ctx['PFX']}Roads_draft.shp (+ .png). Edit it, then run: design ... --roads <edited file> --from roads"); ctx['stop'] = True; return
    if not ctx.get('roads'): raise SystemExit('design roads: give the planner road centrelines with --roads (field width_ft, or a class text such as "40 ft collector")')
    site = gpd.read_file(SITE_KML).to_crs(2136); S = shapely.force_2d(site.geometry.iloc[0]); S = Polygon(S.exterior.coords)
    RL = gpd.read_file(ctx['roads']).to_crs(2136); RL['geometry'] = RL.geometry.force_2d(); RL = RL.explode(index_parts=False)
    RL = RL[RL.geom_type == 'LineString'].reset_index(drop=True); RL['w'] = [_width_of(r_) for _, r_ in RL.iterrows()]
    if RL.empty: raise SystemExit('NO ROADS: the roads file has no road lines. Draw roads (or use "Design the roads for me") before running the layout.')
    # node the network: split every line where it crosses another (keeps each piece's width)
    noded = shapely.get_parts(shapely.node(shapely.geometry.MultiLineString(list(RL.geometry))))
    seg_w = []
    for p in noded:
        mid = p.interpolate(0.5, normalized=True); k = int(np.argmin([g.distance(mid) for g in RL.geometry])); seg_w.append(RL.w.iloc[k])
    SURF = road_surface(list(noded), [wft / 2 for wft in seg_w], tol=3.0, clip=None, fillet=15.0)
    far = Point(-1e7, -1e7).buffer(1)
    name = lambda wft: {30: '30 ft local road', 40: '40 ft collector', 60: '60 ft main road', 100: '100 ft road reserve'}.get(int(round(wft)), f'{wft:.0f} ft road')
    classes = {}
    for p, wft in zip(noded, seg_w): classes.setdefault(name(wft), []).append(p.buffer(wft / 2 + 0.5, cap_style=2))
    rows = {k: unary_union(v).intersection(SURF) for k, v in classes.items()}
    for k in ('30 ft local road', '40 ft collector'): rows.setdefault(k, far)
    gpd.GeoDataFrame(dict(Class=list(rows)), geometry=list(rows.values()), crs=2136).to_file(WORK + 'layout_roads.gpkg')
    gpd.GeoDataFrame(dict(width_ft=seg_w), geometry=list(noded), crs=2136).to_file(WORK + 'layout_centrelines.gpkg')
    wmax = max(seg_w); MAIN = rows.get(name(wmax), far) if wmax >= 40 else far
    if ctx.get('stream'):
        st = gpd.read_file(ctx['stream']).to_crs(2136); st['geometry'] = st.geometry.force_2d()
        SR = st.union_all().buffer(float(ctx.get('stream_buffer') or 0) or 0.01).intersection(S)
    else: SR = far
    STP = steep_reserve(ctx)
    if STP is not None: SR = STP if SR.equals(far) else SR.union(STP); print(f'   steep-slope reserve kept green: {STP.area / 43560:.1f} ac')
    x0, y0, x1, y1 = S.bounds; WZ = S.intersection(box(x0 - 10, y0 - 10, S.centroid.x, y1 + 10))
    gpd.GeoDataFrame(dict(Part=['Site', '60 ft existing road', 'Stream reserve', 'West zone']), geometry=[S, MAIN.intersection(S) if not MAIN.equals(far) else far, SR, WZ], crs=2136).to_file(WORK + 'concept.gpkg')
    BL = [g for g in shapely.get_parts(S.difference(SURF).difference(SR if not SR.equals(far) else Point(0, 0).buffer(0.001))) if g.area > 2000]
    gpd.GeoDataFrame(geometry=BL, crs=2136).to_file(WORK + 'layout_blocks.gpkg')
    print(f'   roads {len(noded)} segments {pd_counts(seg_w)} | blocks {len(BL)} | stream reserve {"yes" if not SR.equals(far) else "no"}')
def pd_counts(v):
    from collections import Counter; return dict(Counter(int(round(x)) for x in v))

def fetch_osm_roads_water(site, WORK):
    """existing roads (highways) and streams (waterways) around a design site -> osm_roads.gpkg, osm_water.gpkg (EPSG:2136)"""
    import geopandas as gpd
    from shapely.geometry import LineString
    w, s, e, n = site.to_crs(4326).total_bounds; b = 0.003; BB = f'{s - b},{w - b},{n + b},{e + b}'
    rows = []; d = None
    small = (e - w + 2 * b) * (n - s + 2 * b) < 0.04                      # OSM API map call handles areas up to ~0.25 sq deg / 50,000 nodes
    if small:
        try: nodes, ways = osm_api_map(w - b, s - b, e + b, n + b)
        except Exception as ex: print('   OSM API failed, trying Overpass:', str(ex)[:80], flush=True); small = False
    if not small: d = overpass(f'[out:json][timeout:50];(way["highway"]({BB});way["waterway"]({BB}););out geom;')
    if d is not None:
        for el in d['elements']:
            t = el.get('tags', {})
            if len(el.get('geometry', [])) >= 2: rows.append(dict(highway=t.get('highway'), waterway=t.get('waterway'), name=t.get('name'), geometry=LineString([(p['lon'], p['lat']) for p in el['geometry']])))
    else:
        if not small: nodes, ways = osm_api_map(w - b, s - b, e + b, n + b)
        for wid, t, ref in ways:
            if len(ref) >= 2 and ('highway' in t or 'waterway' in t): rows.append(dict(highway=t.get('highway'), waterway=t.get('waterway'), name=t.get('name'), geometry=LineString(ref)))
    G = gpd.GeoDataFrame(rows, geometry='geometry', crs=4326) if rows else gpd.GeoDataFrame(columns=['highway', 'waterway', 'name', 'geometry'], geometry='geometry', crs=4326)
    G = G.to_crs(2136)
    G[G.highway.notna()].to_file(WORK + 'osm_roads.gpkg'); G[G.waterway.isin(['stream', 'river', 'canal', 'drain', 'ditch'])].to_file(WORK + 'osm_water.gpkg')
    print(f'   OSM: {int(G.highway.notna().sum())} roads, {int(G.waterway.notna().sum())} waterways')

SLOPE_CLASSES = [(0, 5, 'Flat (0-5%)', '#1a9850'), (5, 10, 'Gentle (5-10%)', '#91cf60'), (10, 18, 'Moderate (10-18%)', '#fee08b'),
                 (18, 30, 'Steep (18-30%): no roads straight downhill', '#fc8d59'), (30, 1e9, 'Very steep (> 30%): keep green', '#d73027')]
def contour_interval(relief_m):
    return next(c for c in (1, 2, 5, 10, 20, 50) if relief_m / c <= 40)
def terrain_products(ctx):
    """slope (%) raster, slope classes, contours (interval adapted to the relief), steep-slope reserve; summary in the log"""
    import geopandas as gpd, rasterio, shapely
    from rasterio import features as rfeat
    from shapely.geometry import Polygon, LineString, shape
    from shapely.ops import unary_union
    from skimage.measure import find_contours
    WORK, D, PFX = ctx['WORK'], ctx['D'], ctx['PFX']
    S = shapely.force_2d(gpd.read_file(ctx['SITE_KML']).to_crs(2136).geometry.iloc[0]); S = Polygon(S.exterior.coords)
    r = rasterio.open(WORK + 'dem_2136.tif'); dem = r.read(1).astype(float); T = r.transform; px_m = abs(T.a) * FT
    gy, gx = np.gradient(dem, px_m); slope = np.hypot(gx, gy) * 100
    prof = r.profile.copy(); prof.update(dtype='float32', nodata=-9999)
    with rasterio.open(D + PFX + 'Slope_percent.tif', 'w', **prof) as o: o.write(np.where(np.isnan(slope), -9999, slope).astype('float32'), 1)
    inside = rfeat.rasterize([S], out_shape=dem.shape, transform=T).astype(bool)
    cls = np.zeros(dem.shape, np.uint8)
    for k, (a, b, lab, col) in enumerate(SLOPE_CLASSES, 1): cls[(slope >= a) & (slope < b)] = k
    cls[~inside | np.isnan(slope)] = 0
    rows = []
    for k, (a, b, lab, col) in enumerate(SLOPE_CLASSES, 1):
        polys = [shape(g) for g, v in rfeat.shapes(cls, mask=cls == k, transform=T) if v == k]
        if not polys: continue
        g = unary_union(polys).buffer(10).buffer(-10).simplify(8).intersection(S)
        if g.is_empty: continue
        rows.append(dict(cls=lab, pct_from=a, pct_to=(b if b < 1e8 else 999), area_ac=round(g.area / 43560, 2), share=round(g.area / S.area * 100, 1), geometry=g))
    SC = gpd.GeoDataFrame(rows, geometry='geometry', crs=2136); SC.to_file(D + PFX + 'Slope_classes.shp')
    zin = dem[inside & ~np.isnan(dem)]; relief = float(zin.max() - zin.min()); CI = contour_interval(relief)
    lines = []
    for z in np.arange(np.floor(np.nanmin(dem) / CI) * CI, np.nanmax(dem) + CI, CI):
        for c in find_contours(np.nan_to_num(dem, nan=-9999), z):
            if len(c) < 3: continue
            xy = [T * (cc[1] + 0.5, cc[0] + 0.5) for cc in c]
            lines.append(dict(elev_m=float(z), major=int(round(z / CI)) % 5 == 0, geometry=LineString(xy).simplify(3)))
    CT = gpd.GeoDataFrame(lines, geometry='geometry', crs=2136); CT = CT[CT.intersects(S.buffer(300))]; CT['geometry'] = CT.intersection(S.buffer(300))
    CT['geometry'] = [shapely.line_merge(shapely.union_all([q for q in shapely.get_parts(x) if q.geom_type in ('LineString', 'MultiLineString')])) for x in CT.geometry]   # lines only: a clip can leave points
    CT = CT[~CT.is_empty & CT.geom_type.isin(['LineString', 'MultiLineString'])]; CT.to_file(D + PFX + 'Contours.shp')
    steep = float(ctx.get('steep_pct', 30) or 0)
    if steep > 0:
        m = (slope >= steep) & inside
        polys = [shape(g) for g, v in rfeat.shapes(m.astype(np.uint8), mask=m, transform=T) if v == 1]
        g = unary_union(polys).buffer(-15).buffer(15) if polys else Polygon()
        g = unary_union([q for q in shapely.get_parts(g) if q.area >= 0.5 * 43560]).intersection(S) if not g.is_empty else g
        g = shapely.union_all([q for q in shapely.get_parts(g) if q.geom_type in ('Polygon', 'MultiPolygon') and q.area > 0]) if not g.is_empty else g   # areas only: the clip can leave slivers of line / point
        g = g if (not g.is_empty and g.geom_type in ('Polygon', 'MultiPolygon')) else Polygon()
        GS = gpd.GeoDataFrame(dict(reserve=[f'Steep slope (>= {steep:.0f}%): green / conservation'], area_ac=[round(g.area / 43560, 2)]), geometry=[g], crs=2136)
        GS.to_file(WORK + 'steep_reserve.gpkg'); GS.to_file(D + PFX + 'Steep_slope_reserve.shp')
    if os.path.exists(WORK + 'site_analysis.png'): shutil.copy(WORK + 'site_analysis.png', D + PFX + 'Site_analysis.png')
    terrain_overlays(ctx, S)
    summ = dict(elev_min=round(float(zin.min()), 1), elev_max=round(float(zin.max()), 1), relief=round(relief, 1), contour_interval=CI, mean_slope_pct=round(float(np.nanmean(slope[inside])), 1),
                classes=[dict(cls=rr.cls, area_ac=rr.area_ac, share=rr.share) for _, rr in SC.iterrows()], steep_pct=steep,
                steep_reserve_ac=(round(float(GS.area_ac.iloc[0]), 1) if steep > 0 else 0))
    json.dump(summ, open(D + PFX + 'Terrain_summary.json', 'w'), indent=1)
    print(f'   terrain: elevation {zin.min():.0f}-{zin.max():.0f} m (relief {relief:.0f} m), contours every {CI} m, mean slope {np.nanmean(slope[inside]):.1f}%')
    for _, rr in SC.iterrows(): print(f'     {rr.cls:45s} {rr.area_ac:7.1f} ac  {rr.share:5.1f}%')
    if steep > 0: print(f'   steep-slope reserve (>= {steep:.0f}%, pieces >= 0.5 ac): {GS.area_ac.iloc[0]:.1f} ac kept green')
def steep_reserve(ctx):
    import geopandas as gpd
    f = ctx['WORK'] + 'steep_reserve.gpkg'
    if float(ctx.get('steep_pct', 30) or 0) <= 0 or not os.path.exists(f): return None
    g = gpd.read_file(f).union_all(); return None if g.is_empty else g

def terrain_overlays(ctx, S):
    """web-map overlays (EPSG:3857 PNG + lat/lon bounds): elevation with hillshade, slope classes"""
    import rasterio, matplotlib, geopandas as gpd
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from rasterio import features as rfeat
    from pyproj import Transformer
    WORK, D, PFX = ctx['WORK'], ctx['D'], ctx['PFX']
    with rasterio.open(WORK + 'dem_2136.tif') as r:
        t, w, h = calculate_default_transform(r.crs, 'EPSG:3857', r.width, r.height, *r.bounds, resolution=3)
        z = np.full((h, w), np.nan, 'float32'); reproject(rasterio.band(r, 1), z, src_transform=r.transform, src_crs=r.crs, dst_transform=t, dst_crs='EPSG:3857', resampling=Resampling.bilinear, dst_nodata=np.nan)
    S3 = gpd.GeoSeries([S], crs=2136).to_crs(3857).iloc[0]
    near = rfeat.rasterize([S3.buffer(90)], out_shape=z.shape, transform=t).astype(bool) & ~np.isnan(z)
    gy, gx = np.gradient(np.nan_to_num(z, nan=np.nanmean(z)), 3.0); slope = np.hypot(gx, gy) * 100
    az, alt = np.radians(315), np.radians(45); asp = np.arctan2(-gx, gy)
    hs = np.clip(np.sin(alt) * np.cos(np.arctan(np.hypot(gx, gy))) + np.cos(alt) * np.sin(np.arctan(np.hypot(gx, gy))) * np.cos(az - asp), 0, 1)
    zin = z[near]; zn = (z - zin.min()) / max(zin.max() - zin.min(), 1)
    rgb = matplotlib.colormaps['terrain'](np.clip(zn * 0.85 + 0.12, 0, 1))[:, :, :3] * (0.45 + 0.55 * hs[:, :, None])
    dem_png = np.dstack([rgb, near * 0.85]); dem_png[~near] = 0
    cols = np.zeros(z.shape + (4,))
    for a, b, lab, col in SLOPE_CLASSES:
        m = (slope >= a) & (slope < b) & near; c = matplotlib.colors.to_rgb(col); cols[m] = (*c, 0.75)
    tr = Transformer.from_crs(3857, 4326, always_xy=True); x0, y1 = t.c, t.f; x1, y0 = t.c + w * t.a, t.f + h * t.e
    (lo0, la0), (lo1, la1) = tr.transform(x0, y0), tr.transform(x1, y1)
    bounds = [[la0, lo0], [la1, lo1]]
    for name, arr in (('Elevation_overlay.png', dem_png), ('Slope_overlay.png', cols)):
        matplotlib.image.imsave(D + PFX + name, np.clip(arr, 0, 1)); json.dump(dict(bounds=bounds), open(D + PFX + name.replace('.png', '.json'), 'w'))

# =====================================================================================================================
# Stage: footprints (fast route) - OpenStreetMap + building database in one step, no image detection (SAM)
# =====================================================================================================================
def st_footprints(ctx):
    """OSM outlines where they exist, building-database outlines (Google / Microsoft / OSM) where OSM has none; occupancy and height
    attached to every building; walls / fences detected on the image. Replaces sam, digitize, compare, clean and database."""
    import geopandas as gpd, pandas as pd, shapely
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    D, PFX, WORK = ctx['D'], ctx['PFX'], ctx['WORK']
    S = shapely.force_2d(gpd.read_file(ctx['SITE_KML']).to_crs(2136).geometry.iloc[0]); S = Polygon(S.exterior.coords)
    O = gpd.read_file(WORK + 'osm_buildings.gpkg').to_crs(2136); O = O[O.intersects(S) & O.geometry.is_valid].reset_index(drop=True)
    G = gpd.read_file(WORK + 'obm_buildings.gpkg') if os.path.exists(WORK + 'obm_buildings.gpkg') else obm_load(gpd.read_file(ctx['SITE_KML']))
    G = G.to_crs(2136); G = G[G.intersects(S)].reset_index(drop=True); progress(10, 'inputs read')
    gt = shapely.STRtree(list(G.geometry)); rows = []
    for g in O.geometry:                                              # 1. OSM outlines, with database attributes by best overlap
        g = g.buffer(0)
        if g.is_empty or g.area * FT * FT < 6: continue
        c = [(G.geometry[j].intersection(g).area, j) for j in gt.query(g)]; c = [x for x in c if x[0] > 0.3 * min(g.area, G.geometry[x[1]].area)]
        j = max(c)[1] if c else None
        rows.append(dict(geometry=g, src='OSM', action='OSM footprint', j=j))
    progress(45, 'OSM footprints')
    U = unary_union([r_['geometry'] for r_ in rows]) if rows else None; added = 0
    for j, g in enumerate(G.geometry):                                # 2. database outlines where OSM has nothing
        if g.area * FT * FT < 9: continue
        if U is not None and g.intersection(U).area > 0.3 * g.area: continue
        rows.append(dict(geometry=g, src=f'database ({G.source[j]})', action=f'added from database ({G.source[j]})', j=j)); added += 1
    progress(70, 'database footprints')
    F = gpd.GeoDataFrame(rows, geometry='geometry', crs=2136)
    col = lambda k: [G[k][int(j)] if j is not None and not pd.isna(j) else None for j in F.j]
    F['db_id'], F['db_source'], F['occupancy'], F['use_db'], F['height'] = col('id'), col('source'), col('occupancy'), col('use_obm'), col('height')
    F['class'] = 'Building'; F['reason'] = 'OSM / building database'; F['area_m2'] = (F.area * FT * FT).round(1); F['bld_id'] = range(1, len(F) + 1)
    F = F[['bld_id', 'class', 'area_m2', 'src', 'action', 'reason', 'db_id', 'db_source', 'occupancy', 'use_db', 'height', 'geometry']]
    F.to_file(D + PFX + 'Buildings_final.shp'); F.to_file(D + PFX + 'Buildings.shp')
    print(f'   buildings: {len(F)} ({len(F) - added} OSM outlines, {added} from the database {G.source.value_counts().to_dict() if len(G) else ""}) | occupancy known for {int((F.occupancy.notna() & (F.occupancy != "UNK")).sum())}', flush=True)
    ctx['footprint_source'] = 'database'
    _walls_from_image(ctx, F); progress(100, 'walls')

# OSM tags of service / utility sites that are kept as ONE plot (never subdivided), with their land use
SITE_TAGS = {('amenity', 'school'): 'Education', ('amenity', 'kindergarten'): 'Education', ('amenity', 'college'): 'Education', ('amenity', 'university'): 'Education',
             ('amenity', 'hospital'): 'Health', ('amenity', 'clinic'): 'Health', ('healthcare', 'hospital'): 'Health', ('healthcare', 'clinic'): 'Health',
             ('amenity', 'police'): 'Civic', ('amenity', 'fire_station'): 'Civic', ('amenity', 'prison'): 'Civic', ('amenity', 'townhall'): 'Civic',
             ('amenity', 'courthouse'): 'Civic', ('amenity', 'post_office'): 'Civic', ('amenity', 'community_centre'): 'Civic', ('office', 'government'): 'Civic',
             ('landuse', 'military'): 'Civic', ('military', 'barracks'): 'Civic', ('amenity', 'place_of_worship'): 'Religious', ('landuse', 'religious'): 'Religious',
             ('amenity', 'marketplace'): 'Market', ('amenity', 'bus_station'): 'Transport terminal', ('amenity', 'fuel'): 'Commercial (fuel)',
             ('power', 'substation'): 'Utility', ('power', 'plant'): 'Utility', ('man_made', 'water_works'): 'Utility', ('man_made', 'wastewater_plant'): 'Utility',
             ('landuse', 'cemetery'): 'Civic', ('amenity', 'grave_yard'): 'Civic', ('leisure', 'stadium'): 'Recreation', ('leisure', 'sports_centre'): 'Recreation'}
def fetch_osm_sites(w, s, e, n, S, WORK):
    """outlines of service / utility sites (closed ways with the tags above) -> osm_sites.gpkg (EPSG:2136)"""
    import geopandas as gpd
    from shapely.geometry import Polygon
    small = (e - w) * (n - s) < 0.04; rows = []
    if small: nodes, ways = osm_api_map(w, s, e, n); items = [(t, ref) for _, t, ref in ways]
    else:
        BB = f'{s},{w},{n},{e}'; q = ''.join(f'way["{k}"="{v}"]({BB});' for k, v in SITE_TAGS)
        d = overpass(f'[out:json][timeout:60];({q});out geom;'); items = [(el.get('tags', {}), [(p['lon'], p['lat']) for p in el.get('geometry', [])]) for el in (d or {}).get('elements', [])]
    for t, ref in items:
        if len(ref) < 4 or ref[0] != ref[-1]: continue
        hit = next(((k, v) for (k, v) in SITE_TAGS if t.get(k) == v), None)
        if hit and 'building' not in t: rows.append(dict(tag=f'{hit[0]}={hit[1]}', use=SITE_TAGS[hit], name=t.get('name'), geometry=Polygon(ref)))
    G = gpd.GeoDataFrame(rows, geometry='geometry', crs=4326) if rows else gpd.GeoDataFrame(columns=['tag', 'use', 'name', 'geometry'], geometry='geometry', crs=4326)
    G = G.to_crs(2136); G = G[G.intersects(S)]; G.to_file(WORK + 'osm_sites.gpkg'); print(f'   OSM site outlines (schools, hospitals, police, utilities ...): {len(G)}', flush=True)


# =====================================================================================================================
# Stage: chamfer (design, optional) - corner truncations on corner plots (LUSPA Guidelines 2025, s.10.1.1): the triangle cut
# off a plot is added to the road reserve. Distance by the higher road at the corner: local / cul-de-sac 3.5 m, collector 5 m,
# major arterial 10 m; never more than 15 % of the plot's shorter side (small plots get smaller chamfers).
# =====================================================================================================================
CHAMFER_M = [(60, 10.0), (40, 5.0), (0, 3.5)]          # road reserve width ft >= key -> truncation in metres
def st_design_chamfer(ctx):
    """Corner truncations (chamfers) on corner plots; plots and road reserves updated together (guide section 6)."""
    if not ctx.get('chamfer'): print('   corner chamfers not requested (--chamfer)'); return
    import geopandas as gpd, numpy as np, re, math, shapely
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    W = ctx['WORK']; FTM = 0.3048
    RD = gpd.read_file(W + 'layout_roads.gpkg'); width = lambda c: float(re.search(r'(\d+(?:\.\d+)?)\s*ft', c).group(1)) if re.search(r'(\d+(?:\.\d+)?)\s*ft', str(c)) else 30.0
    RD['w'] = [width(c) for c in RD.Class]; ROAD = RD.union_all(); tree = shapely.STRtree(list(RD.geometry))
    def road_at(seg):
        """the reserve width of the road an edge fronts (None: not a road edge)"""
        b = seg.buffer(3); best = None
        for k in tree.query(b):
            a = RD.geometry.iloc[k].intersection(b).area
            if a > 0.4 * seg.length * 3 and (best is None or a > best[0]): best = (a, RD.w.iloc[k], k)
        return best
    gain, loss = {}, {}; n_cut = 0                                       # per road reserve: land it gains (chamfers) / gives back (rounded corners squared)
    def chamfer(g):
        """square the corner to the plot, then cut the straight chamfer at the LUSPA distance"""
        nonlocal n_cut
        if g.geom_type != 'Polygon': return g
        c = np.array(g.exterior.simplify(3.0).coords)[:-1]; n = len(c); new = g
        E = [(c[q], c[(q + 1) % n]) for q in range(n)]; L_ = [np.linalg.norm(b - a) for a, b in E]
        RF = [road_at(shapely.LineString([a, b])) if L_[q] >= 25 else None for q, (a, b) in enumerate(E)]
        for q in range(n):                                                 # a long road edge, short pieces (the kerb curve), then the next long road edge
            if not RF[q]: continue
            t = (q + 1) % n; short = 0.0
            while L_[t] < 25 and t != q: short += L_[t]; t = (t + 1) % n
            if t == q or short > 45 or not RF[t]: continue
            (a1, b1), (a2, b2) = E[q], E[t]; u1, u2 = (b1 - a1) / L_[q], (b2 - a2) / L_[t]
            den = u1[0] * u2[1] - u1[1] * u2[0]
            if abs(den) < 1e-6: continue
            tt = ((a2 - a1)[0] * u2[1] - (a2 - a1)[1] * u2[0]) / den; v = a1 + u1 * tt          # the corner the two edges would make
            e1, e2 = -u1 * L_[q], u2 * L_[t]; l1, l2 = L_[q], L_[t]
            ang = math.degrees(math.acos(max(-1, min(1, (e1 @ e2) / (l1 * l2)))))
            if not 45 <= ang <= 120: continue
            r1, r2 = RF[q], RF[t]
            k = r1[2] if r1[1] >= r2[1] else r2[2]; wmax = max(r1[1], r2[1])
            d = min(next(m for w0, m in CHAMFER_M if wmax >= w0) / FTM, 0.25 * min(l1, l2))      # LUSPA distance, at most a quarter of the plot side
            if d < 4: continue
            big = Polygon([tuple(v), tuple(v + e1 / l1 * min(l1, d + 25)), tuple(v + e2 / l2 * min(l2, d + 25))])
            sq = new.union(big.intersection(ROAD)).buffer(0.01).buffer(-0.01)  # the corner squared (the kerb curve's land back to the plot)
            tri = Polygon([tuple(v), tuple(v + e1 / l1 * d), tuple(v + e2 / l2 * d)])
            nn = sq.difference(tri.buffer(0.01))
            nn = max(shapely.get_parts(nn), key=lambda q: q.area) if nn.geom_type != 'Polygon' else nn
            back, taken = nn.difference(new), new.difference(nn)
            if taken.area < 2 and back.area < 2: continue
            gain.setdefault(k, []).append(taken); loss.setdefault(k, []).append(back); new = nn; n_cut += 1
        return new
    for f in ('plots_landuse.gpkg', 'reserves_landuse.gpkg'):
        if not os.path.exists(W + f): continue
        G = gpd.read_file(W + f)
        if 'chamfered' not in G: G['chamfered'] = 0
        n0 = n_cut; out_ = []
        for g, done_ in zip(G.geometry, G.chamfered):
            if done_: out_.append(g); continue                              # chamfered on an earlier run: left as it is
            k0 = n_cut; out_.append(chamfer(g))
        G['chamfered'] = [1 if (d_ or g2 is not g1) else 0 for d_, g1, g2 in zip(G.chamfered, G.geometry, out_)]; G['geometry'] = out_
        if 'area' in G: G['area'] = G.area
        G.to_file(W + f)
    back_all = unary_union([t for ts in loss.values() for t in ts]) if loss else None   # squared corners go back to the plots, whichever reserve held them
    for k in range(len(RD)):
        g_ = unary_union([RD.geometry.iloc[k]] + gain.get(k, []))
        if back_all is not None and not back_all.is_empty: g_ = g_.difference(back_all.buffer(0.01))
        RD.at[RD.index[k], 'geometry'] = g_.buffer(0.05).buffer(-0.05)
    RD.drop(columns='w').to_file(W + 'layout_roads.gpkg')
    tot = (sum(t.area for ts in gain.values() for t in ts) - sum(t.area for ts in loss.values() for t in ts)) * FTM * FTM
    print(f'   corner chamfers: {n_cut} plot corners truncated (local 3.5 m, collector 5 m, arterial 10 m; max 25 % of the plot side; rounded kerb corners squared to a straight chamfer), net {tot:+.0f} m2 to the road reserves', flush=True)

# =====================================================================================================================
# Automatic road layout (design --roads auto | draft). Applies the planner's rules (guide section 6) to any site.
# =====================================================================================================================
GRADE_MAX = {'local': 0.10, 'collector': 0.08}                         # LUSPA Table 26: max incline, local roads 10 %, collectors 8 %
AUTO = dict(band=200.0, local=30.0, collector=40.0, block_len=490.0, max_sector_ac=35.0, min_seg=120.0, arrive_back=140.0, min_angle=70.0,
            entry_gap=1000.0, entry_cost=60000.0)   # fewest junctions on the highest-order road: >= 1,000 ft apart (user rule: blocks parallel to the highest road)
HIGHWAY_WIDTH = {'motorway': 100, 'trunk': 100, 'primary': 100, 'secondary': 80, 'tertiary': 60, 'unclassified': 40, 'residential': 40, 'track': 40, 'service': 30}
def _u(v): v = np.asarray(v, float); return v / (np.linalg.norm(v) + 1e-12)
def _tangent(l, s, h=8.0):
    return _u(np.array(l.interpolate(min(l.length, s + h)).coords[0])[:2] - np.array(l.interpolate(max(0, s - h)).coords[0])[:2])
def _cubic(p0, d0, p3, d3, k=16):
    L = np.linalg.norm(p3 - p0) / 3; p1, p2 = p0 + d0 * L, p3 - d3 * L; t = np.linspace(0, 1, k)[:, None]
    return [tuple(x) for x in (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3]
def _long_line(c, d, L=1e5):
    from shapely.geometry import LineString
    return LineString([tuple(c - d * L), tuple(c + d * L)])
def _road_edges(sector, reserves):
    """pieces of the sector outline that face a road reserve, with the width of that road: [(LineString, width)]"""
    import shapely
    from shapely.ops import linemerge
    out = []
    ring = sector.exterior
    for poly, w in reserves:
        near = ring.intersection(poly.buffer(2.0))
        for g in shapely.get_parts(near):
            if g.geom_type == 'LineString' and g.length > 60: out.append((g, w))
            elif g.geom_type == 'MultiLineString':
                for q in shapely.get_parts(linemerge(g)):
                    if q.length > 60: out.append((q, w))
    return out
def _edge_direction(edge):
    """dominant direction of an edge (length-weighted, ignoring sign)"""
    c = np.array(edge.coords)[:, :2]; v = np.diff(c, axis=0); L = np.linalg.norm(v, axis=1)
    if L.sum() == 0: return np.array([1.0, 0.0])
    ang = np.arctan2(v[:, 1], v[:, 0]) * 2                       # doubled angles: direction without sign
    a = math.atan2((np.sin(ang) * L).sum(), (np.cos(ang) * L).sum()) / 2
    return np.array([math.cos(a), math.sin(a)])
def _grid_lines(sector, u, ref_pt, phase, far_is_road):
    """rows parallel to u (from the reference edge, 200 ft bands) and cross roads along n (block_len apart, shifted by phase)"""
    import shapely
    from shapely.geometry import LineString
    n = np.array([-u[1], u[0]]); P = np.array(sector.exterior.coords)[:, :2]
    pn = (P - ref_pt) @ n
    if abs(pn.min()) > abs(pn.max()): n = -n; pn = -pn                  # n points into the sector
    pu = (P - ref_pt) @ u; ext = pn.max()
    B, Lr, BL = AUTO['band'], AUTO['local'], AUTO['block_len']
    rows, offs = [], []
    o = B + Lr / 2
    while o + Lr / 2 + 100 <= ext: offs.append(o); o += B + Lr
    if offs:
        left = ext - offs[-1] - Lr / 2
        if left < 100 or (far_is_road and left < 180): offs = offs[:-1]
    for o in offs:
        g = _long_line(ref_pt + n * o, u).intersection(sector)
        rows += [q for q in shapely.get_parts(g) if q.geom_type == 'LineString' and q.length > AUTO['min_seg']]
    crosses = []
    s = pu.min() + phase
    while s < pu.max():
        if s - pu.min() > 150 and pu.max() - s > 150:
            g = _long_line(ref_pt + u * s, n).intersection(sector)
            crosses += [q for q in shapely.get_parts(g) if q.geom_type == 'LineString' and q.length > AUTO['min_seg']]
        s += BL + Lr
    return rows, crosses
def _score(sector, lines, bld, reserves_poly):
    """usable standard blocks minus building conflicts minus sharp arrivals"""
    import shapely
    from shapely.ops import unary_union
    if not lines: return -1e9, []
    surf = unary_union([l.buffer(AUTO['local'] / 2, cap_style=2) for l in lines])
    blocks = [b for b in shapely.get_parts(sector.difference(surf)) if b.area > 2000]
    good = 0.0
    for b in blocks:
        q = np.array(b.minimum_rotated_rectangle.exterior.coords); a, c = sorted([np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[1])])
        fill = b.area / max(b.minimum_rotated_rectangle.area, 1)
        w = 1.0 if (170 <= a <= 240 and fill > 0.85) else (0.7 if (90 <= a <= 120 and fill > 0.85) else 0.35)
        good += b.area * w
    conflict, n_cut = 0.0, 0
    if bld is not None:
        conflict = surf.intersection(bld).area
        n_cut = sum(1 for b in shapely.get_parts(bld) if b.area > 200 and surf.intersection(b).area > 0.15 * b.area)   # buildings the road reserve would cut into
    return good - 40 * conflict - 20000 * n_cut, blocks
def _arrive_square(line, target_union, min_angle):
    import shapely
    """bend the last stretch of a line so it meets the road it runs into at ~90 deg (if it would meet below min_angle)"""
    from shapely.geometry import LineString, Point
    out = line
    for at_end in (True, False):
        l = out if at_end else LineString(list(out.coords)[::-1])
        p = Point(l.coords[-1]); near = target_union if target_union.geom_type in ('LineString', 'MultiLineString') else shapely.line_merge(target_union.boundary)
        if near.distance(p) > 25: out = l if at_end else LineString(list(l.coords)[::-1]); continue
        s_t = near.project(p); tg = _tangent(near, s_t); d = _u(np.array(l.coords[-1])[:2] - np.array(l.coords[-2])[:2])
        ang = math.degrees(math.acos(min(1, abs(float(d @ tg)))))
        if ang < min_angle and l.length > AUTO['arrive_back'] + 40:
            sA = l.length - AUTO['arrive_back']; A = np.array(l.interpolate(sA).coords[0])[:2]
            T = np.array(near.interpolate(near.project(Point(A))).coords[0])[:2]; d3 = _u(T - A)
            from shapely.ops import substring
            l = LineString(list(substring(l, 0, sA).coords) + _cubic(A, d, T, d3)[1:])
        out = l if at_end else LineString(list(l.coords)[::-1])
    return out
class _Terrain:
    """DEM sampler on EPSG:2136 ft: elevation, steep road length, contour direction of a parcel"""
    def __init__(self, path):
        import rasterio
        r = rasterio.open(path); self.z = r.read(1).astype(float); self.T = r.transform; self.Ti = ~r.transform
        self.px_m = abs(r.transform.a) * FT; gy, gx = np.gradient(self.z, self.px_m); self.gx, self.gy = gx, -gy     # map y up
    def at(self, x, y):
        c, r_ = self.Ti * (x, y); r_, c = int(r_), int(c)
        return self.z[r_, c] if 0 <= r_ < self.z.shape[0] and 0 <= c < self.z.shape[1] else np.nan
    def steep_len(self, lines, limit=0.18, step=30.0):
        L = 0.0
        for l in lines:
            n = max(2, int(l.length / step)); pts = [l.interpolate(t) for t in np.linspace(0, l.length, n)]
            zs = np.array([self.at(p.x, p.y) for p in pts]); ds = l.length / (n - 1) * FT
            g = np.abs(np.diff(zs)) / ds; L += float(np.nansum((g > limit) * l.length / (n - 1)))
        return L
    def contour_through(self, poly):
        """longest contour piece inside the parcel at its median elevation"""
        from rasterio import features as rfeat
        from skimage.measure import find_contours
        from shapely.geometry import LineString
        import shapely
        m = rfeat.rasterize([poly], out_shape=self.z.shape, transform=self.T).astype(bool); zz = self.z[m]
        if zz.size < 10 or np.nanmax(zz) - np.nanmin(zz) < 2: return None
        best = None
        for c in find_contours(np.nan_to_num(self.z, nan=-9999), float(np.nanmedian(zz))):
            if len(c) < 3: continue
            l = LineString([self.T * (cc[1] + .5, cc[0] + .5) for cc in c]).intersection(poly)
            for q in shapely.get_parts(l):
                if q.geom_type == 'LineString' and (best is None or q.length > best.length): best = q
        return best if best is not None and best.length > 300 else None
    def contour_dir(self, poly):
        from rasterio import features as rfeat
        m = rfeat.rasterize([poly], out_shape=self.z.shape, transform=self.T).astype(bool)
        gx, gy = self.gx[m], self.gy[m]; mag = np.hypot(gx, gy); ok = ~np.isnan(mag) & (mag > 0)
        if ok.sum() < 10: return None, 0.0
        ang = np.arctan2(gy[ok], gx[ok]) * 2; a = math.atan2((np.sin(ang) * mag[ok]).sum(), (np.cos(ang) * mag[ok]).sum()) / 2
        g = np.array([math.cos(a), math.sin(a)]); return np.array([-g[1], g[0]]), float(np.nanmean(mag[ok]))

PATTERNS = {'mixed': 'Blended (best pattern per parcel)', 'grid': 'Grid iron', 'curvilinear': 'Curvilinear (follows the contours)'}     # ring and band removed (user: 'horrible')
def _chaikin(coords, it=2):
    c = np.asarray(coords, float)[:, :2]
    for _ in range(it):
        if len(c) < 3: break
        q = 0.75 * c[:-1] + 0.25 * c[1:]; r = 0.25 * c[:-1] + 0.75 * c[1:]
        c = np.vstack([c[:1], np.column_stack([q, r]).reshape(-1, 2), c[-1:]])
    return [tuple(x) for x in c]
def _extend(l, L=3000):
    from shapely.geometry import LineString
    c = np.array(l.coords)[:, :2]; d0 = _u(c[0] - c[1]); d1 = _u(c[-1] - c[-2])
    return LineString([tuple(c[0] + d0 * L)] + [tuple(x) for x in c] + [tuple(c[-1] + d1 * L)])
def _curvi_lines(sec, base, phase):
    """nested parallel curves of `base` (rows) + normals to it (cross roads): normals of a curve stay square to all its parallels"""
    import shapely
    from shapely.geometry import LineString
    B, Lr, BL = AUTO['band'], AUTO['local'], AUTO['block_len']
    step_rows, step_cross = B + Lr, BL + Lr
    b = LineString(_chaikin(base.simplify(30).coords, 3)); b = _extend(b, 2500)
    P = np.array(sec.exterior.coords)[:, :2]; span = max(np.ptp(P[:, 0]), np.ptp(P[:, 1])) + 500
    rows = []; k0 = int(span / step_rows) + 1
    for k in range(-k0, k0 + 1):
        d = phase + k * step_rows
        try: o = b.offset_curve(d, join_style=1) if abs(d) > 1 else b
        except Exception: continue
        for q in shapely.get_parts(o.intersection(sec)):
            if q.geom_type == 'LineString' and q.length > AUTO['min_seg']: rows.append(LineString(_chaikin(q.simplify(10).coords, 1)))
    crosses = []; bc = b.intersection(sec.buffer(400)); parts = [x for x in shapely.get_parts(bc) if x.geom_type == 'LineString']
    if parts:
        bc = max(parts, key=lambda x: x.length); s0 = (phase * 2.3) % step_cross
        for s_ in np.arange(s0, bc.length, step_cross):
            if s_ < 150 or bc.length - s_ < 150: continue
            p = np.array(bc.interpolate(s_).coords[0])[:2]; t = _tangent(bc, s_, 40); n = np.array([-t[1], t[0]])
            for q in shapely.get_parts(_long_line(p, n, span).intersection(sec)):
                if q.geom_type == 'LineString' and q.length > AUTO['min_seg']: crosses.append(q)
    return rows, crosses
def _ringband_lines(sec, S, R, u, ref, phase):
    """ring road 200 ft + half a road inside the road edges (100 ft inside the site boundary), rounded corners; inner grid; cross roads run through the band to the outer roads"""
    import shapely
    from shapely.ops import unary_union
    from shapely.geometry import LineString
    B, Lr = AUTO['band'], AUTO['local']
    ed = _road_edges(sec, R); redges = unary_union([e for e, w in ed]) if ed else None
    bnd = sec.exterior.intersection(S.exterior.buffer(3))
    core = sec
    if redges is not None and not redges.is_empty: core = core.difference(redges.buffer(B + Lr / 2))
    if not bnd.is_empty: core = core.difference(bnd.buffer(100 + Lr / 2))
    core = core.buffer(-150).buffer(150)                                  # rounded ring corners, small notches ignored
    parts = [c for c in shapely.get_parts(core) if c.geom_type == 'Polygon' and c.area > 2 * 43560]
    if not parts: return None
    rings = [LineString(_chaikin(c.exterior.simplify(60).coords, 3)) for c in parts]                    # smooth loop, not every bend of a reserve edge
    rows, crosses = _grid_lines(sec, u, ref, phase, far_is_road=False)
    inner = unary_union([c.buffer(-(B / 2)) for c in parts])
    rows = [q for r_ in rows for q in shapely.get_parts(r_.intersection(inner)) if q.geom_type == 'LineString' and q.length > AUTO['min_seg']]
    open_ = sec.difference(bnd.buffer(100 + Lr)) if not bnd.is_empty else sec      # cross roads stop at the ring on the site-boundary side
    U = unary_union(parts)
    crosses = [q for c_ in crosses for q in shapely.get_parts(c_.intersection(open_)) if q.geom_type == 'LineString' and q.length > AUTO['min_seg'] and q.intersects(U)]
    links = []
    if redges is not None and not redges.is_empty:
        for rg in rings:
            n_conn = sum(1 for c_ in crosses if c_.intersects(rg.buffer(3)))
            if n_conn >= 2: continue
            cand = []
            for t in np.linspace(0, rg.length, 24, endpoint=False):
                pt = rg.interpolate(t); q = redges.interpolate(redges.project(pt)); d = pt.distance(q)
                if d < 400: cand.append((d, pt, q))
            cand.sort(key=lambda x: x[0]); used = []
            for d, pt, q in cand:
                if len(used) >= 2 - n_conn: break
                if all(pt.distance(u) > rg.length / 4 for u in used):
                    links.append(LineString([pt.coords[0], q.coords[0]])); used.append(pt)
    return rings + rows, crosses + links

def auto_roads(S, existing, stream_poly=None, buildings=None, log=print, terrain=None, pattern='mixed', zones=None, only_zones=False):
    """S: site polygon (EPSG:2136 ft); existing: [(LineString, width_ft[, kind])] (kind 'locked' = planner's roads, kept exactly);
    zones: [(Polygon, pattern)] redesign areas; only_zones: new roads only inside the zones. Returns [(LineString, width_ft, kind)]"""
    zones = zones or []
    from shapely.ops import substring
    ZU = None
    if zones:
        from shapely.ops import unary_union as _uu
        ZU = _uu([z for z, _ in zones])
    def zone_of(sec):
        best = None
        for z, pt in zones:
            a = z.intersection(sec).area
            if a > 0.4 * sec.area and (best is None or a > best[0]): best = (a, pt or 'mixed')
        return None if best is None else best[1]
    import shapely
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union, nearest_points
    out = []
    # ---- 1. existing roads: kept on alignment, carried straight in to the boundary or the next road ----
    ex = []
    for it in existing:
        l, w = it[0], it[1]; kind = it[2] if len(it) > 2 else 'existing'
        if kind == 'locked':                                              # planner's roads: kept exactly as drawn
            ex.append((l, w)); out.append((l, w, 'locked')); continue
        g = l.intersection(S.buffer(w))
        for q in shapely.get_parts(g):
            if q.geom_type != 'LineString' or q.length < 50: continue
            c = list(q.coords)
            for at_end in (True, False):
                p = np.array(c[-1] if at_end else c[0])[:2]
                if Point(p).distance(S.exterior) < 10: continue
                d = _u(np.array(c[-1])[:2] - np.array(c[-2])[:2]) if at_end else _u(np.array(c[0])[:2] - np.array(c[1])[:2])
                ray = LineString([tuple(p), tuple(p + d * 3000)]); others = unary_union([o[0] for o in existing if o[0] is not l] + [S.exterior])
                h = ray.intersection(others)
                if not h.is_empty:
                    hp = min([pp for pp in shapely.get_parts(h) if pp.geom_type == 'Point'] or [Point(ray.coords[-1])], key=lambda pp: pp.distance(Point(p)))
                    if hp.distance(Point(p)) < 2000: c = c + [tuple(np.array(hp.coords[0]))] if at_end else [tuple(np.array(hp.coords[0]))] + c
            ex.append((LineString(c), w)); out.append((LineString(c), w, kind))
    SR = stream_poly.intersection(S) if stream_poly is not None and not stream_poly.is_empty else None
    def reserves_of(lines):
        return [(l.buffer(w / 2, cap_style=2).intersection(S.buffer(1)), w) for l, w, *_ in lines]
    # ---- 2. access: a site with no road gets a collector from its longest edge through the centre ----
    if not ex:
        q = np.array(S.minimum_rotated_rectangle.exterior.coords)[:, :2]; e1, e2 = q[1] - q[0], q[2] - q[1]
        d = _u(e2 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e1); c = np.array(S.centroid.coords[0])
        g = _long_line(c, d).intersection(S); g = max(shapely.get_parts(g), key=lambda x: x.length)
        out.append((g, AUTO['collector'], 'collector')); log('   no existing road: collector across the site through the centre')
    # ---- 3. collectors: split large parcels (> max_sector_ac) square to their main road edge, through the centre ----
    for level in range(3):
        R = reserves_of(out); blocked = unary_union([p for p, _ in R] + ([SR] if SR is not None else []))
        sectors = [g for g in shapely.get_parts(S.difference(blocked)) if g.area > 43560]
        added = False
        if only_zones and ZU is not None: sectors = [q for g in sectors for q in shapely.get_parts(g.intersection(ZU)) if q.geom_type == 'Polygon' and q.area > 43560]
        for sec in sectors:
            if sec.area / 43560 <= AUTO['max_sector_ac']: continue
            edges = _road_edges(sec, R)
            if edges:
                e, w = max(edges, key=lambda t: t[0].length * t[1]); d = _edge_direction(e); d = np.array([-d[1], d[0]])
            else:
                q = np.array(sec.minimum_rotated_rectangle.exterior.coords)[:, :2]; e1, e2 = q[1] - q[0], q[2] - q[1]
                d = _u(e2 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e1)
            c = np.array(sec.centroid.coords[0]); best = None
            d0 = d
            for shift, turn in [(sh, tn) for sh in np.linspace(-0.25, 0.25, 11) for tn in ((0, -10, 10, -20, 20) if terrain is not None else (0,))]:   # fewest buildings, gentlest grade, near the middle
                q = np.array(sec.minimum_rotated_rectangle.exterior.coords)[:, :2]; span = max(np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[1]))
                ca, sa = math.cos(math.radians(turn)), math.sin(math.radians(turn)); d = np.array([d0[0] * ca - d0[1] * sa, d0[0] * sa + d0[1] * ca])
                cc = c + np.array([-d0[1], d0[0]]) * shift * span
                g = _long_line(cc, d).intersection(sec.buffer(AUTO['collector']))
                parts = [x for x in shapely.get_parts(g) if x.geom_type == 'LineString']
                if not parts: continue
                g = max(parts, key=lambda x: x.length)
                cost = (g.buffer(AUTO['collector'] / 2).intersection(buildings).area if buildings is not None else 0) + abs(shift) * 2000 + abs(turn) * 150
                if terrain is not None: cost += 250 * terrain.steep_len([g], GRADE_MAX['collector'])
                if best is None or cost < best[0]: best = (cost, g)
            if best is None: continue
            out.append((best[1], AUTO['collector'], 'collector')); added = True
            log(f'   collector splits a {sec.area / 43560:.0f} ac parcel')
        if not added: break
    # ---- 4. grid per parcel ----
    w_top = max([w for _, w, k in out if k in ('existing', 'locked', 'collector')] or [0])     # the highest road in the area, whatever its width
    TOP = unary_union([l for l, w, k in out if k in ('existing', 'locked', 'collector') and w == w_top]) if w_top > 0 else None
    TOPZ = TOP.buffer(w_top / 2 + 85) if TOP is not None else None          # a new road ending here would be joined to the top road (step 5 reaches 80 ft)
    def entries(lines):
        if TOPZ is None: return 0
        return sum(1 for l in lines for e in (l.coords[0], l.coords[-1]) if TOPZ.contains(Point(e)))
    R = reserves_of(out); blocked = unary_union([p for p, _ in R] + ([SR] if SR is not None else []))
    sectors = [g for g in shapely.get_parts(S.difference(blocked)) if g.area > 30000]
    if only_zones and ZU is not None: sectors = [q for g in sectors for q in shapely.get_parts(g.intersection(ZU)) if q.geom_type == 'Polygon' and q.area > 30000]
    bld = unary_union(list(buildings.geoms)) if buildings is not None and hasattr(buildings, 'geoms') else buildings
    RES_U = unary_union([p_ for p_, _ in R])
    def staggered(lines):
        n_ = 0
        for l in lines:
            c_ = np.array(l.coords)[:, :2]
            for e_, d_ in ((c_[-1], _u(c_[-1] - c_[-2])), (c_[0], _u(c_[0] - c_[1]))):
                for p_ in prev_ends:
                    pv = np.array(p_.coords[0]) - e_
                    if np.linalg.norm(pv) > 260: continue
                    if not LineString([tuple(e_), p_.coords[0]]).intersects(RES_U): continue     # only across a road
                    off = abs(d_[0] * pv[1] - d_[1] * pv[0])
                    if 3 < off < 131: n_ += 1
        return n_
    for sec in sectors:
        prev_ends = [Point(e) for l, w, k in out if k == 'local' for e in (l.coords[0], l.coords[-1]) if sec.distance(Point(e)) < 120]
        edges = _road_edges(sec, R)
        cands = []
        if edges:
            for e, w in sorted(edges, key=lambda t: -t[0].length * t[1])[:2]:
                cands.append((_edge_direction(e), np.array(e.interpolate(0.5, normalized=True).coords[0])[:2], w))
        q = np.array(sec.minimum_rotated_rectangle.exterior.coords)[:, :2]; e1, e2 = q[1] - q[0], q[2] - q[1]
        cands.append((_u(e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2), q[0], 0))
        hilly = False
        if terrain is not None:                                          # rows along the contours (cross roads take the slope over short lengths)
            cd, mg = terrain.contour_dir(sec)
            if cd is not None:
                hilly = mg > 0.08; cands.append((cd, q[0], 0))
                if edges: cands.append((cd, np.array(edges[0][0].interpolate(0.5, normalized=True).coords[0])[:2], 0))
        best = None
        pat = zone_of(sec) or pattern
        def options(pattern):
            if pattern == 'ringband': pattern = 'mixed'                 # removed pattern (older redesign areas may still name it)
            if pattern == 'mixed':
                for pt in ('grid', 'curvilinear'): yield from options(pt)
                return
            if pattern == 'curvilinear':
                from shapely.geometry import LineString
                bases = []
                if terrain is not None:
                    cl = terrain.contour_through(sec)
                    if cl is not None: bases.append((cl, 0))
                if not bases: bases += [(e, w) for e, w in sorted(edges, key=lambda t: -t[0].length * t[1])[:2]]      # contour first: the pattern follows the terrain
                if not bases: bases.append((LineString([tuple(q[0]), tuple(q[1])]), 0))
                for b, w in bases:
                    for phase in np.linspace(0, AUTO['band'] + AUTO['local'], 5)[:-1]:
                        yield (w,) + _curvi_lines(sec, b, phase)
            else:
                for u, ref, w in cands:
                    Pp = np.array(sec.exterior.coords)[:, :2]; pu0 = ((Pp - ref) @ u).min(); per = AUTO['block_len'] + AUTO['local']
                    al = [((np.array(p_.coords[0]) - ref) @ u - pu0) % per for p_ in prev_ends]      # positions that line cross roads up with roads across the street
                    for phase in list(np.linspace(0, per, 7)[:-1]) + al[:12]:
                        if pattern == 'ringband':
                            rb = _ringband_lines(sec, S, R, u, ref, phase)
                            if rb is not None: yield (w,) + rb; continue
                        yield (w,) + _grid_lines(sec, u, ref, phase, far_is_road=False)
        for w, rows, crosses in options(pat):
            sc, _ = _score(sec, rows + crosses, bld, None)
            sc -= 30000 * staggered(rows + crosses)                      # T junctions 1-40 m off a road end across the street
            sc += w * 50                                                 # prefer running along the highest-order road
            sc -= AUTO['entry_cost'] * entries(rows + crosses)            # every junction on the highest-order road costs (blocks run parallel to it)
            if terrain is not None:                                      # hills: road length over the LUSPA max grade (10 %) and over 18 % both cost
                sc -= (1500 if hilly else 400) * terrain.steep_len(rows + crosses, 0.18) + (500 if hilly else 120) * terrain.steep_len(rows + crosses, GRADE_MAX['local'])
            if best is None or sc > best[0]: best = (sc, rows, crosses)
        if best is None: continue
        for l in best[1] + best[2]: out.append((l, AUTO['local'], 'local'))
    # ---- 4b. kept roads cut at a redesign-area edge: carry them into the area to the first new road ----
    if only_zones and ZU is not None:
        newl = unary_union([l for l, w, k in out if k in ('local', 'collector')]); fixed = []
        for l, w, k in out:
            if k == 'locked' and not newl.is_empty:
                c = list(l.coords)
                for at_end in (True, False):
                    p = Point(c[-1] if at_end else c[0])
                    if p.distance(ZU.boundary) > 5: continue
                    d = _u(np.array(c[-1])[:2] - np.array(c[-2])[:2]) if at_end else _u(np.array(c[0])[:2] - np.array(c[1])[:2])
                    h = LineString([p.coords[0], tuple(np.array(p.coords[0]) + d * 600)]).intersection(newl)
                    pts = [q for q in shapely.get_parts(h) if q.geom_type == 'Point' and q.distance(p) > 1]
                    if pts:
                        hp = min(pts, key=lambda q: q.distance(p)).coords[0]
                        c = c + [hp] if at_end else [hp] + c
                l = LineString(c)
            fixed.append((l, w, k))
        out = fixed
    # ---- 5. connect: extend local ends to the road centreline / boundary they face; bend sharp arrivals square ----
    allc = unary_union([l for l, *_ in out]); fin = []
    for l, w, k in out:
        if k == 'local':
            c = list(l.coords)
            for at_end in (True, False):
                p = np.array(c[-1] if at_end else c[0])[:2]; d = _u(np.array(c[-1])[:2] - np.array(c[-2])[:2]) if at_end else _u(np.array(c[0])[:2] - np.array(c[1])[:2])
                ray = LineString([tuple(p + d * 0.5), tuple(p + d * 80)])
                tgt = unary_union([x for x, *_ in out if x is not l] + [S.exterior]); h = ray.intersection(tgt)
                if not h.is_empty:
                    hp = min([pp for pp in shapely.get_parts(h) if pp.geom_type == 'Point'] or [Point(ray.coords[-1])], key=lambda pp: pp.distance(Point(p)))
                    c = c + [tuple(np.array(hp.coords[0]))] if at_end else [tuple(np.array(hp.coords[0]))] + c
            l = LineString(c)
            others = unary_union([x for x, ww, kk in out if kk != 'local'])
            if not others.is_empty: l = _arrive_square(l, others, AUTO['min_angle'])
        fin.append((l, w, k))
    # ---- 6. junctions on the highest-order road: >= entry_gap apart, as crossroads (both sides aligned); other local roads stop at the first parallel road ----
    if TOP is not None:
        topl = shapely.line_merge(TOP) if TOP.geom_type == 'MultiLineString' else TOP
        topl = max(shapely.get_parts(topl), key=lambda x: x.length) if topl.geom_type != 'LineString' else topl
        ent = []                                                           # (index in fin, end, position along the top road, side, fixed)
        for i, (l, w, k) in enumerate(fin):
            if k not in ('local', 'collector') or (k == 'collector' and w == w_top): continue      # a collector that IS the highest road is not an entry into it
            for at_end in (True, False):
                e = Point(l.coords[-1] if at_end else l.coords[0])
                if e.distance(TOP) <= w_top / 2 + 6:
                    sp = topl.project(e); tg = _tangent(topl, sp); v = np.array(e.coords[0])[:2] - np.array(topl.interpolate(sp).coords[0])[:2]
                    inner = Point(l.interpolate(min(40, l.length / 2)) if not at_end else l.interpolate(max(0, l.length - 40)))
                    vi = np.array(inner.coords[0])[:2] - np.array(topl.interpolate(sp).coords[0])[:2]
                    ent.append((i, at_end, sp, 1 if (tg[0] * vi[1] - tg[1] * vi[0]) > 0 else -1, k == 'collector'))
        kept = sorted(sp for i, a, sp, sd, fx in ent if fx)
        for i, a, sp, sd, fx in sorted(ent, key=lambda t: t[2]):
            if fx: continue
            if all(abs(sp - k_) >= AUTO['entry_gap'] for k_ in kept) or any(abs(sp - k_) <= 60 for k_ in kept): kept.append(sp)   # spaced, or opposite an entry already kept (crossroads)
        cut = 0
        for i, a, sp, sd, fx in ent:
            if fx or any(abs(sp - k_) <= 60 for k_ in kept): continue
            l, w, k = fin[i]; others = unary_union([x for j, (x, *_r) in enumerate(fin) if j != i and _r[1] != 'existing'])
            end = Point(l.coords[-1] if a else l.coords[0]); hits = [q for q in shapely.get_parts(l.intersection(others)) if q.geom_type == 'Point' and q.distance(end) > 30]
            if not hits: continue                                          # no parallel road to stop at: keep the access
            h = min(hits, key=lambda q: q.distance(end)); s_h = l.project(h)
            nl = substring(l, 0, s_h) if a else substring(l, s_h, l.length)
            if nl.length > AUTO['min_seg'] / 2: fin[i] = (nl, w, k); cut += 1
        n_top = sum(1 for i, a, sp, sd, fx in ent if fx or any(abs(sp - k_) <= 60 for k_ in kept))
        log(f'   junctions on the {w_top:.0f} ft road: {n_top} kept (>= {AUTO["entry_gap"]:.0f} ft apart, as crossroads); {cut} local roads now end at the parallel road')
    if terrain is not None:
        for kk in ('collector', 'local'):
            ls_ = [l for l, w, k in fin if k == kk]
            if ls_:
                over = terrain.steep_len(ls_, GRADE_MAX[kk]) * FT; tot = sum(l.length for l in ls_) * FT
                log(f"   {kk} roads steeper than the LUSPA {GRADE_MAX[kk] * 100:.0f} % maximum: {over:.0f} m of {tot:.0f} m" + ('  -> check these on the slope layer' if over > 0 else ''))
    # ---- 7. no staggered T junctions: two local roads meeting a road from opposite sides within 40 m become one crossroads ----
    from shapely import affinity as _aff
    def _tan_at(m, sp):
        a_ = np.array(m.interpolate(max(0, sp - 5)).coords[0])[:2]; b_ = np.array(m.interpolate(min(m.length, sp + 5)).coords[0])[:2]; return _u(b_ - a_)
    fixed_n = 0
    for _round in range(60):
        moved = False
        roads_ = [l for l, *_ in fin]
        ends_ = []                                                          # (line idx, at_end, road idx, position on road, side)
        for i, (l, w, k) in enumerate(fin):
            if k != 'local': continue
            for at_end in (True, False):
                e = Point(l.coords[-1] if at_end else l.coords[0])
                for j, m in enumerate(roads_):
                    if j == i or m.distance(e) > 3: continue
                    sp = m.project(e)
                    if sp < 1 or sp > m.length - 1: continue
                    t = _tan_at(m, sp); inner = np.array(l.interpolate(max(0, l.length - 30) if at_end else min(l.length, 30)).coords[0])[:2] - np.array(e.coords[0])[:2]
                    ends_.append((i, at_end, j, sp, 1 if (t[0] * inner[1] - t[1] * inner[0]) > 0 else -1))
        for x in ends_:
            for y in ends_:
                if moved or x[2] != y[2] or x[0] >= y[0] or x[4] == y[4]: continue
                gap = abs(x[3] - y[3])
                if not (3 < gap < 131): continue                            # 1-40 m apart on opposite sides: staggered
                mv, st = (x, y) if fin[x[0]][0].length <= fin[y[0]][0].length else (y, x)
                road = roads_[mv[2]]; t = _tan_at(road, mv[3]) * (st[3] - mv[3])
                l, w, k = fin[mv[0]]; nl = _aff.translate(l, xoff=t[0], yoff=t[1]).intersection(S.buffer(1))
                if nl.geom_type != 'LineString' or nl.length < 0.8 * l.length: continue
                far = Point(nl.coords[0] if mv[1] else nl.coords[-1])          # the other end must still reach a road or the boundary
                if min([r.distance(far) for jj, r in enumerate(roads_) if jj != mv[0]] + [S.exterior.distance(far)]) > 5: continue
                fin[mv[0]] = (nl, w, k); fixed_n += 1; moved = True
        if not moved: break
    if fixed_n: log(f'   staggered T junctions aligned into crossroads: {fixed_n}')
    log(f"   auto layout: {sum(1 for *_, k in fin if k == 'existing')} existing, {sum(1 for *_, k in fin if k == 'collector')} collectors, {sum(1 for *_, k in fin if k == 'local')} local roads")
    return fin
def st_design_autoroads(ctx):
    """--roads auto | draft: design the roads from the rules; writes <P>Roads_draft.shp (editable) and a preview"""
    import geopandas as gpd, shapely
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    WORK, D, PFX = ctx['WORK'], ctx['D'], ctx['PFX']
    site = gpd.read_file(ctx['SITE_KML']).to_crs(2136); S = Polygon(shapely.force_2d(site.geometry.iloc[0]).exterior.coords)
    existing = []
    if ctx.get('existing'):                                             # the planner's existing roads (always used)
        E = gpd.read_file(ctx['existing']).to_crs(2136); E['geometry'] = E.geometry.force_2d()
        for _, r_ in E.explode(index_parts=False).iterrows():
            if r_.geometry.geom_type == 'LineString': existing.append((r_.geometry, _width_of(r_) if any(k in r_ for k in ('width_ft', 'class', 'Class')) else 40.0))
    if ctx.get('lock'):                                                   # roads the planner keeps (drawn / edited / outside a redesign area)
        Lk = gpd.read_file(ctx['lock']).to_crs(2136); Lk['geometry'] = Lk.geometry.force_2d()
        for _, r_ in Lk.explode(index_parts=False).iterrows():
            if r_.geometry.geom_type == 'LineString': existing.append((r_.geometry, _width_of(r_), 'locked'))
        print(f'   kept roads (locked): {len(Lk)}')
    if os.path.exists(WORK + 'osm_roads.gpkg'):                         # OpenStreetMap roads: always, unless the planner already gave that road
        O = gpd.read_file(WORK + 'osm_roads.gpkg'); given = unary_union([e[0] for e in existing]).buffer(25) if existing else None; n_osm = 0
        for g, h in zip(O.geometry, O.highway):
            if h in HIGHWAY_WIDTH and g.intersects(S.buffer(100)) and g.intersection(S).length > 100:
                if given is not None and g.intersection(given).length > 0.6 * g.length: continue
                existing.append((g, float(HIGHWAY_WIDTH[h]))); n_osm += 1
        print(f'   OpenStreetMap roads kept on their alignment: {n_osm}', flush=True)
    stream = None; stream_src = ''
    if ctx.get('stream'):
        st = gpd.read_file(ctx['stream']).to_crs(2136); st['geometry'] = st.geometry.force_2d()
        if len(st): stream = st.union_all().buffer(float(ctx.get('stream_buffer') or 0) or 0.01); stream_src = 'drawn by the planner'
    if stream is None and os.path.exists(WORK + 'osm_water.gpkg'):
        Wt = gpd.read_file(WORK + 'osm_water.gpkg')
        if len(Wt):
            st_ = Wt.union_all().buffer(float(ctx.get('stream_buffer') or 110))
            if st_.intersects(S): stream = st_; ctx['stream_poly'] = stream; stream_src = f'OpenStreetMap waterways ({len(Wt)})'
    STP = steep_reserve(ctx)
    if STP is not None: stream_src = (stream_src + ' + ' if stream is not None else '') + 'steep slopes'; stream = STP if stream is None else stream.union(STP); print(f'   steep-slope reserve kept green: {STP.area / 43560:.1f} ac')
    terrain = _Terrain(WORK + 'dem_2136.tif') if os.path.exists(WORK + 'dem_2136.tif') else None
    bld = None
    if os.path.exists(WORK + 'buildings.gpkg'):
        Bd = gpd.read_file(WORK + 'buildings.gpkg').to_crs(2136); Bd = Bd[Bd.intersects(S)]
        if len(Bd): bld = unary_union(list(Bd.geometry))
    print(f'   inputs: {len(existing)} existing roads, green reserve {("yes: " + stream_src) if stream is not None else "no"}, {0 if bld is None else len(shapely.get_parts(bld))} existing buildings')
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    pat = (ctx.get('pattern') or 'mixed').lower()
    zones = []
    if ctx.get('zones'):
        Zg = gpd.read_file(ctx['zones']).to_crs(2136)
        for _, z in Zg.iterrows():
            if z.geometry is not None and z.geometry.geom_type in ('Polygon', 'MultiPolygon'): zones.append((shapely.force_2d(z.geometry), (z.get('pattern') or pat)))
        print(f'   redesign areas: {len(zones)} ({", ".join(PATTERNS.get(p_, p_) for _, p_ in zones)})')
    saved = dict(AUTO)
    for k, ck in (('band', 'band'), ('block_len', 'block_len'), ('local', 'local_width'), ('collector', 'collector_width'), ('max_sector_ac', 'max_parcel_ac')):
        if ctx.get(ck): AUTO[k] = float(ctx[ck])
    print(f"   parameters: block depth {AUTO['band']:.0f} ft, block length {AUTO['block_len']:.0f} ft, local roads {AUTO['local']:.0f} ft, collectors {AUTO['collector']:.0f} ft, parcels up to {AUTO['max_sector_ac']:.0f} ac")
    pats = list(PATTERNS) if pat == 'all' else [pat]
    res = {}
    for pt in pats:
        print(f'   -- pattern: {PATTERNS[pt]}', flush=True)
        L = auto_roads(S, existing, stream, bld, log=print, terrain=terrain, pattern=pt, zones=zones, only_zones=bool(ctx.get('only_zones')))
        new = [l for l, w, k in L if k not in ('existing', 'locked')]
        surf = road_surface([l for l, *_ in L], [w / 2 for _, w, _ in L], tol=3.0, clip=S)
        blocked = surf.union(stream.intersection(S)) if stream is not None else surf
        blocks = [b for b in shapely.get_parts(S.difference(blocked)) if b.area > 2000]
        met = dict(pattern=pt, name=PATTERNS[pt], new_road_km=round(sum(l.length for l in new) * FT / 1000, 2),
                   road_share_pct=round(surf.area / S.area * 100, 1),
                   steep_road_m=round(terrain.steep_len(new) * FT) if terrain is not None else None,
                   developable_ac=round(sum(b.area for b in blocks) / 43560, 1), approx_plots=int(sum(b.area for b in blocks) * 0.85 / 7000),
                   blocks=len(blocks))
        G = gpd.GeoDataFrame(dict(width_ft=[w for _, w, _ in L], kind=[k for *_, k in L]), geometry=[l for l, *_ in L], crs=2136)
        suffix = '' if len(pats) == 1 else '_' + pt
        G.to_file(WORK + f'auto_roads{suffix}.gpkg'); G.to_file(D + PFX + f'Roads_draft{suffix}.shp')
        res[pt] = (G, met); print('      ' + ', '.join(f'{k} {v}' for k, v in met.items() if k not in ('pattern', 'name')), flush=True)
    json.dump([m for _, m in res.values()], open(D + PFX + 'Roads_patterns.json', 'w'), indent=1)
    if stream is not None and not ctx.get('stream'):
        gpd.GeoDataFrame(geometry=[stream], crs=2136).to_file(WORK + 'auto_stream.gpkg'); ctx['stream'] = WORK + 'auto_stream.gpkg'; ctx['stream_buffer'] = 0
    img = None
    if os.path.exists(WORK + 'imagery_2136.tif'):
        import rasterio
        r = rasterio.open(WORK + 'imagery_2136.tif'); img = (np.moveaxis(r.read(), 0, -1)[:, :, :3], r.bounds)
    fig, axs = plt.subplots(1, len(res), figsize=(9 * len(res), 9)); axs = np.atleast_1d(axs)
    for ax, (pt, (G, met)) in zip(axs, res.items()):
        if img is not None: b = img[1]; ax.imshow(img[0], extent=(b.left, b.right, b.bottom, b.top), alpha=.55)
        if os.path.exists(D + PFX + 'Contours.shp'):
            C = gpd.read_file(D + PFX + 'Contours.shp'); C[C.major].plot(ax=ax, color='#8d6e63', lw=.6); C[~C.major].plot(ax=ax, color='#bcaaa4', lw=.25)
        gpd.GeoSeries([S]).boundary.plot(ax=ax, color='red', lw=2)
        if stream is not None: gpd.GeoSeries([stream.intersection(S)]).plot(ax=ax, color='#2e8b57', alpha=.45)
        for k, c_, lw in (('existing', 'black', 3.5), ('locked', '#7b1fa2', 2.2), ('collector', '#f5a142', 2.6), ('local', '#1f5fd1', 1.3)):
            s_ = G[G.kind == k]
            if len(s_): s_.plot(ax=ax, color=c_, lw=lw)
        x0, y0, x1, y1 = S.bounds; ax.set_xlim(x0 - 100, x1 + 100); ax.set_ylim(y0 - 100, y1 + 100); ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"{met['name']}\n{met['new_road_km']} km new road | steep road {met['steep_road_m']} m | ~{met['approx_plots']} plots | {met['developable_ac']} ac developable", fontsize=11)
    fig.suptitle(f"{ctx['NAME']}: road layout patterns (green = stream / steep-slope reserve)", fontsize=14)
    plt.savefig(D + PFX + ('Roads_patterns.png' if len(res) > 1 else 'Roads_draft.png'), bbox_inches='tight', dpi=60)
    AUTO.clear(); AUTO.update(saved)
    if len(pats) == 1: ctx['roads'] = WORK + 'auto_roads.gpkg'
    else:
        bestp = max(res, key=lambda k: res[k][1]['approx_plots'] - (res[k][1]['steep_road_m'] or 0) / 10)
        shutil.copy(WORK + f'auto_roads_{bestp}.gpkg', WORK + 'auto_roads.gpkg'); ctx['roads'] = WORK + 'auto_roads.gpkg'
        print(f'   suggested pattern: {PATTERNS[bestp]} (most plots for the least steep road)')


def st_sam(ctx):
    """Segment Anything masks over the image in 1024 px tiles over the site (tiles already done are skipped)."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    """Run SAM automatic masks over the whole image in overlapping tiles; save each tile's mask polygons (map coordinates)."""
    import rasterio, numpy as np, time, torch, cv2, pickle, os, sys
    from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
    torch.set_num_threads(16)
    r = rasterio.open(WORK + 'img_z19_3857.tif'); a = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); H, W = a.shape[:2]; T = r.transform
    sam = sam_model_registry['vit_b'](checkpoint=SAM_CKPT)
    gen = SamAutomaticMaskGenerator(sam, points_per_side=48, pred_iou_thresh=0.82, stability_score_thresh=0.88, min_mask_region_area=50, points_per_batch=128)
    TS, OV = 1024, 160
    ys = list(range(0, max(1, H - OV), TS - OV)); xs = list(range(0, max(1, W - OV), TS - OV))
    jobs = [(y, x) for y in ys for x in xs]
    import geopandas as _gpd
    from shapely.geometry import box as _box
    _S = _gpd.read_file(SITE_KML).to_crs(3857).geometry.iloc[0].buffer(30)
    _n0 = len(jobs); jobs = [(y, x) for y, x in jobs if _box(*(T * (x, min(H, y + TS))), *(T * (min(W, x + TS), y))).intersects(_S)]
    print(f'tiles over the site: {len(jobs)} of {_n0}', flush=True)
    print('tiles', len(jobs), flush=True)
    for k, (y0, x0) in enumerate(jobs):
        out = WORK + f'tiles/t_{y0}_{x0}.pkl'
        if os.path.exists(out): progress(100 * (k + 1) / len(jobs), f'tile {k + 1} of {len(jobs)}'); continue
        tile = a[y0:min(H, y0 + TS), x0:min(W, x0 + TS)]
        if tile.shape[0] < 64 or tile.shape[1] < 64: continue
        t0 = time.time(); masks = gen.generate(tile); polys = []
        for m in masks:
            seg = m['segmentation'].astype(np.uint8)
            cs, _ = cv2.findContours(seg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in cs:
                if len(c) < 4: continue
                c = c[:, 0, :].astype(float); c[:, 0] += x0; c[:, 1] += y0
                xy = [T * (px + 0.5, py + 0.5) for px, py in c]
                edge = (c[:, 0].min() <= x0 + 2) or (c[:, 1].min() <= y0 + 2) or (c[:, 0].max() >= x0 + tile.shape[1] - 3) or (c[:, 1].max() >= y0 + tile.shape[0] - 3)
                polys.append(dict(xy=xy, iou=m['predicted_iou'], stab=m['stability_score'], area_px=int(m['area']), touches_tile_edge=bool(edge)))
        pickle.dump(polys, open(out, 'wb'))
        print(f'tile {k + 1}/{len(jobs)} ({y0},{x0}): {len(masks)} masks, {time.time() - t0:.0f}s', flush=True); progress(100 * (k + 1) / len(jobs), f'tile {k + 1} of {len(jobs)}')
    print('ALL DONE', flush=True)

def _walls_body(ctx):
    """Walls / fences on the image, off roofs and roads (used by the fast footprints route)."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    import math, numpy as np, pandas as pd, geopandas as gpd, rasterio, cv2, shapely
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union, transform as shp_transform, linemerge
    K = ctx['_K']
    site = gpd.read_file(SITE_KML).to_crs(2136).geometry.iloc[0]
    # ---------- 3. walls: stronger detection, joined, off roofs and roads ----------
    r = rasterio.open(WORK + 'img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); T = r.transform; Ti = ~r.transform
    K3 = K.to_crs(3857); bpx = [shp_transform(lambda x, y, z=None: Ti * (x, y), g) for g in K3.geometry]
    from skimage.filters import sato
    from skimage.morphology import skeletonize, remove_small_objects
    from skimage.transform import probabilistic_hough_line
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(float) / 255
    rid = sato(g, sigmas=[1.0, 1.5], black_ridges=False)
    m = remove_small_objects(rid > np.percentile(rid, 90), 20); sk = skeletonize(m)
    segs = probabilistic_hough_line(sk, threshold=7, line_length=int(4.0 / 0.299), line_gap=4, rng=0)
    BU = unary_union([p.buffer(2.5) for p in bpx])
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV); gr = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(float)
    mu = cv2.blur(gr, (21, 21)); sd = np.sqrt(np.maximum(cv2.blur(gr * gr, (21, 21)) - mu * mu, 0))
    road = (sd < 11) & (hsv[:, :, 1] < 45) & (gr > 60) & (gr < 160); road = cv2.morphologyEx(road.astype(np.uint8), cv2.MORPH_OPEN, np.ones((13, 13), np.uint8)).astype(bool)
    keep_s = []
    for (x0, y0), (x1, y1) in segs:
        s = LineString([(x0, y0), (x1, y1)])
        if s.intersection(BU).length > 0.4 * s.length: continue
        n = max(2, int(s.length)); xs = np.clip(np.linspace(x0, x1, n).astype(int), 0, road.shape[1] - 1); ys = np.clip(np.linspace(y0, y1, n).astype(int), 0, road.shape[0] - 1)
        if road[ys, xs].mean() > 0.4: continue
        keep_s.append(s)
    # join: snap near-collinear segments that touch / overlap (buffer-dissolve then centrelines via skeleton of the dissolved strip)
    strip = unary_union([s.buffer(0.9, cap_style=2) for s in keep_s])
    joined = []
    for part in shapely.get_parts(strip):
        q = list(part.minimum_rotated_rectangle.exterior.coords); e1 = np.array(q[1]) - np.array(q[0]); e2 = np.array(q[2]) - np.array(q[1])
        L, Wd = (e1, e2) if np.linalg.norm(e1) >= np.linalg.norm(e2) else (e2, e1)
        if np.linalg.norm(Wd) < 4:                                               # straight strip -> one wall line
            c = np.array(part.minimum_rotated_rectangle.centroid.coords[0]); u = L / np.linalg.norm(L)
            joined.append(LineString([tuple(c - u * np.linalg.norm(L) / 2), tuple(c + u * np.linalg.norm(L) / 2)]))
        else:                                                                    # corner / L-shaped: keep its member segments
            joined += [s for s in keep_s if s.within(part.buffer(0.1))]
    joined = [s for s in joined if s.length * 0.299 >= 4]
    WL = gpd.GeoDataFrame(geometry=[shp_transform(lambda x, y, z=None: T * (x, y), s) for s in joined], crs=3857).to_crs(2136)
    WL = WL[WL.intersects(site)].reset_index(drop=True); WL['length_m'] = (WL.length * 0.3048).round(1)
    # wall type: along a road edge (street frontage) or between plots
    RDm = gpd.GeoSeries([shp_transform(lambda x, y, z=None: T * (x, y), p) for p in shapely.get_parts(shapely.geometry.MultiPolygon([shapely.geometry.Polygon(c[:, 0, :]) for c in cv2.findContours(road.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0] if len(c) >= 4]).buffer(0))], crs=3857).to_crs(2136).union_all()
    WL['wall_type'] = ['Street frontage wall' if g.distance(RDm) < 8 else 'Plot boundary wall' for g in WL.geometry]
    WL['wall_id'] = range(1, len(WL) + 1); WL = WL[['wall_id', 'wall_type', 'length_m', 'geometry']]
    WL.to_file(D + PFX + 'Walls_final.shp')
    print('walls', len(WL), WL['wall_type'].value_counts().to_dict(), 'total m', round(WL.length_m.sum()))

def st_digitize(ctx):
    """Masks -> classified building / foundation footprints and wall lines."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    """the site: assemble SAM tile masks into building / foundation footprints and detect walls, all from the satellite image (no OSM / external footprints)."""
    import glob, pickle, sys, os, numpy as np, cv2, rasterio, geopandas as gpd, pandas as pd, shapely, math
    from shapely.geometry import Polygon, LineString
    from shapely.ops import unary_union, transform as shp_transform
    OUT_DIR = D; os.makedirs(OUT_DIR, exist_ok=True)
    r = rasterio.open(WORK + 'img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); H, W = img.shape[:2]; T = r.transform; Ti = ~T
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY); edges = (cv2.Canny(gray, 40, 110) > 0).astype(float)
    site = gpd.read_file(SITE_KML).to_crs(3857).geometry.iloc[0]
    site = Polygon([(x, y) for x, y, *_ in site.exterior.coords])
    # ---------- 1. masks from all tiles (pixel space) ----------
    polys, scores = [], []
    for f in sorted(glob.glob(WORK + 'tiles/t_*.pkl')):
        for m in pickle.load(open(f, 'rb')):
            px = np.array([Ti * xy for xy in m['xy']])
            if m['touches_tile_edge']:
                if not (px[:, 0].min() <= 3 or px[:, 1].min() <= 3 or px[:, 0].max() >= W - 4 or px[:, 1].max() >= H - 4): continue   # covered by the neighbouring tile
            p = Polygon(px).buffer(0)
            if p.is_empty: continue
            p = max(shapely.get_parts(p), key=lambda q: q.area)
            if p.area > 20: polys.append(p); scores.append(m['iou'] * m['stab'])
    print('masks from tiles', len(polys))
    kept = dedupe(polys, scores); print('after duplicate removal', len(kept))
    cls = {i: classify(features(polys[i], img, edges)) for i in kept}
    from collections import Counter; print(Counter(c[1] for c in cls.values()))
    cand = [i for i in kept if cls[i][0] in ('building', 'foundation')]
    big = [i for i in kept if cls[i][1] == 'too large (yard / block)' and polys[i].area * 0.299 ** 2 < 6000]
    bld, cont = drop_containers(polys, cand + big, return_containers=True); bld = [i for i in bld if i not in big]
    print('buildings + foundations', len(bld), '| compound outlines', len(cont))
    # ---------- 2. regularize, to map coordinates, clip to site ----------
    def to_map(g): return shp_transform(lambda x, y, z=None: T * (x, y), g)
    rows = []
    for i in bld:
        g = regularize(polys[i]); g = to_map(g)
        if not g.intersects(site): continue
        f = features(polys[i], img, edges)
        rows.append(dict(geometry=g, cls=cls[i][0], conf=round(float(scores[i]), 3), roof_rgb=f'{f["R"]:.0f},{f["G"]:.0f},{f["B"]:.0f}'))
    B = gpd.GeoDataFrame(rows, crs=3857).to_crs(2136)
    # overlapping regularized footprints: keep the larger, trim the smaller
    B = B.sort_values('conf', ascending=False).reset_index(drop=True); acc = []
    for i, g in enumerate(B.geometry):
        for j in acc:
            if g.intersects(B.geometry[j]): g = g.difference(B.geometry[j])
        g = max(shapely.get_parts(g), key=lambda q: q.area) if not g.is_empty else g
        B.at[i, 'geometry'] = g; acc.append(i)
    B = B[B.area > 9 / 0.0929].reset_index(drop=True)
    B['class'] = B.cls.map({'building': 'Building', 'foundation': 'Foundation / uncompleted'})
    B['area_m2'] = (B.area * 0.0929).round(1); B['area_sqft'] = B.area.round(0); B['bld_id'] = range(1, len(B) + 1)
    B = B[['bld_id', 'class', 'area_m2', 'area_sqft', 'conf', 'roof_rgb', 'geometry']]
    # ---------- 3. walls ----------
    bpx = [regularize(polys[i]) for i in bld]
    wl, road = detect_walls(img, bpx)
    WL = gpd.GeoDataFrame(geometry=[to_map(w) for w in wl], crs=3857).to_crs(2136)
    WL = WL[WL.intersects(gpd.GeoSeries([site], crs=3857).to_crs(2136).iloc[0])].reset_index(drop=True)
    WL['length_m'] = (WL.length * 0.3048).round(1); WL['wall_id'] = range(1, len(WL) + 1); WL['type'] = 'Wall / fence line'
    # compound outlines that SAM drew (enclosing >= 2 buildings) -> wall lines too
    cw = []
    BU = unary_union([g.buffer(3) for g in bpx])
    for i in cont:
        ring = regularize(polys[i]).exterior.difference(BU)
        cw += [to_map(sg) for sg in shapely.get_parts(ring) if sg.length >= 15]
    if cw:
        CW = gpd.GeoDataFrame(dict(type=['Compound wall (outline)'] * len(cw)), geometry=cw, crs=3857).to_crs(2136); CW['length_m'] = (CW.length * 0.3048).round(1)
        WL = pd.concat([WL, CW], ignore_index=True); WL['wall_id'] = range(1, len(WL) + 1)
    WL = gpd.GeoDataFrame(WL, geometry='geometry', crs=2136)[['wall_id', 'type', 'length_m', 'geometry']]
    # ---------- outputs ----------
    B.to_file(OUT_DIR + PFX + 'Buildings.shp'); WL.to_file(OUT_DIR + PFX + 'Walls.shp')
    B.to_file(OUT_DIR + PFX + 'digitized.gpkg', layer='buildings'); WL.to_file(OUT_DIR + PFX + 'digitized.gpkg', layer='walls')
    print(B['class'].value_counts().to_dict(), '| footprint area m2', round(B.area_m2.sum()), '| median m2', B.area_m2.median(), '| walls', len(WL), 'total m', round(WL.length_m.sum()))

def st_compare(ctx):
    """Check footprints against OSM + Microsoft and correct the shapes."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    """Compare the image-digitized footprints with OSM (and Microsoft) and correct the shapes.
    Rules: OSM shifted onto the image first; several of our pieces inside one OSM building -> merged; 1:1 matches -> keep the outline that sits
    better on the roof edges in the image; OSM-only -> added only if the image there looks like a roof; ours-only -> kept, flagged."""
    import sys, numpy as np, cv2, rasterio, geopandas as gpd, pandas as pd, shapely, json
    from shapely.geometry import Polygon, Point
    from shapely.ops import unary_union, transform as shp_transform
    from shapely import affinity
    OUT_DIR = D
    r = rasterio.open(WORK + 'img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); T = r.transform; Ti = ~T
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(float); edges = (cv2.Canny(gray.astype(np.uint8), 40, 110) > 0).astype(float)
    gm = np.hypot(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3), cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3))
    site = gpd.read_file(SITE_KML).to_crs(2136).geometry.iloc[0]
    A = gpd.read_file(OUT_DIR + PFX + 'Buildings.shp'); O = gpd.read_file(WORK + 'osm_buildings.gpkg'); M = gpd.read_file(WORK + 'ms_buildings.gpkg')
    # the site: OSM has only a handful of buildings here, so the reference = OSM + Microsoft footprints not covered by OSM
    O = gpd.GeoDataFrame(pd.concat([O[['geometry']], M[~M.intersects(O.union_all())][['geometry']]], ignore_index=True), crs=2136) if len(O) else M[['geometry']].copy()
    print('reference footprints (OSM + Microsoft)', len(O))
    to_px = lambda g: shp_transform(lambda x, y, z=None: Ti * (x, y), gpd.GeoSeries([g], crs=2136).to_crs(3857).iloc[0])
    def edge_score(g):
        """mean image gradient along the outline (higher = outline sits on the roof edge)"""
        p = to_px(g); b = p.exterior; n = max(8, int(b.length))
        pts = np.array([b.interpolate(t).coords[0] for t in np.linspace(0, b.length, n)]).astype(int)
        pts[:, 0] = np.clip(pts[:, 0], 0, gm.shape[1] - 1); pts[:, 1] = np.clip(pts[:, 1], 0, gm.shape[0] - 1)
        return float(gm[pts[:, 1], pts[:, 0]].mean())
    def looks_like_roof(g):
        p = to_px(g); p = max(shapely.get_parts(p.buffer(0)), key=lambda q: q.area)
        f = features(p, img, edges); c = classify(f)
        return c[0] in ('building', 'foundation') or (c[1] == 'too large (yard / block)')
    # ---------- 1. OSM alignment to the image ----------
    sh = []
    for g in O.geometry.sample(min(300, len(O)), random_state=0):
        m = A[A.intersects(g)]
        if len(m) == 1:
            ia = m.geometry.iloc[0].intersection(g).area / m.geometry.iloc[0].union(g).area
            if ia > 0.4: sh.append(np.array(m.geometry.iloc[0].centroid.coords[0]) - np.array(g.centroid.coords[0]))
    shift = np.median(np.array(sh), axis=0) if len(sh) > 20 else np.zeros(2)
    best = (np.mean([edge_score(g) for g in O.geometry.iloc[:150]]), np.zeros(2))
    for dx in np.arange(-9, 9.1, 1.5):                                           # refine: shift that puts OSM outlines on image edges (ft)
        for dy in np.arange(-9, 9.1, 1.5):
            v = shift + [dx, dy]; sc = np.mean([edge_score(affinity.translate(g, *v)) for g in O.geometry.iloc[:150]])
            if sc > best[0]: best = (sc, v)
    shift = best[1]; O['geometry'] = O.geometry.apply(lambda g: affinity.translate(g, *shift))
    print(f'OSM shifted by {shift[0] * 0.3048:.1f} m E, {shift[1] * 0.3048:.1f} m N to sit on the image')
    # ---------- 2. matching ----------
    A['src'] = 'image'; A['action'] = 'kept (image)'
    tree = shapely.STRtree(list(O.geometry)); used_osm = set(); new_rows = []; drop_a = set()
    # 2a. merges: two or more of ours mostly inside one OSM building
    for oi, og in enumerate(O.geometry):
        cand = A.index[A.geometry.intersects(og)]
        inside = [i for i in cand if A.geometry[i].intersection(og).area > 0.6 * A.geometry[i].area]
        if len(inside) >= 2 and sum(A.geometry[i].intersection(og).area for i in inside) > 0.5 * og.area:
            merged = unary_union([A.geometry[i] for i in inside])
            g = og if edge_score(og) >= edge_score(merged.convex_hull) * 0.9 else regularize(merged.convex_hull)
            new_rows.append(dict(geometry=g, src='image+OSM', action=f'merged {len(inside)} roof pieces into one building (OSM outline)', cls_='Building'))
            drop_a.update(inside); used_osm.add(oi)
    # 2b. one-to-one: keep the outline that fits the roof edges better
    nsw = 0
    for i in A.index:
        if i in drop_a: continue
        g = A.geometry[i]; cand = [oi for oi in tree.query(g) if oi not in used_osm]
        if not cand: continue
        ious = [(g.intersection(O.geometry[oi]).area / g.union(O.geometry[oi]).area, oi) for oi in cand]
        iou, oi = max(ious)
        if iou < 0.3: continue
        used_osm.add(oi); A.at[i, 'iou_osm'] = round(iou, 2)
        so, sa = edge_score(O.geometry[oi]), edge_score(g)
        if so > sa * 1.05 and 0.5 < O.geometry[oi].area / g.area < 2.0:
            A.at[i, 'geometry'] = O.geometry[oi]; A.at[i, 'src'] = 'image+OSM'; A.at[i, 'action'] = 'outline corrected to reference (OSM/Microsoft) shape (fits roof edges better)'; nsw += 1
        else: A.at[i, 'src'] = 'image+OSM'; A.at[i, 'action'] = 'kept (image outline fits better / agrees with OSM)'
    A = A.drop(index=list(drop_a))
    # 2c. OSM-only buildings: add if the image shows a roof there and nothing of ours covers it
    added = 0; Au = unary_union(list(A.geometry) + [r_['geometry'] for r_ in new_rows])
    for oi, og in enumerate(O.geometry):
        if oi in used_osm or not og.intersects(site): continue
        if og.intersection(Au).area > 0.3 * og.area: continue
        if looks_like_roof(og): new_rows.append(dict(geometry=og, src='OSM/Microsoft (checked on image)', action='missed by image pass; reference outline, roof confirmed on image', cls_='Building')); added += 1
    # 2d. ours-only: confirmed by Microsoft?
    mt = shapely.STRtree(list(M.geometry))
    for i in A.index:
        if A.at[i, 'src'] != 'image': continue
        g = A.geometry[i]; ms_hit = any(g.intersection(M.geometry[j]).area > 0.3 * g.area for j in mt.query(g))
        A.at[i, 'action'] = 'image only (also in Microsoft footprints)' if ms_hit else 'image only (not in OSM or Microsoft - check: new building or false detection)'
    NEW = gpd.GeoDataFrame(new_rows, crs=2136).rename(columns={'cls_': 'class'})
    F = pd.concat([A, NEW], ignore_index=True); F = gpd.GeoDataFrame(F, geometry='geometry', crs=2136)
    F = F[F.intersects(site)].reset_index(drop=True)
    # overlaps after replacement: keep the larger
    F = F.assign(_a=F.area).sort_values('_a', ascending=False).drop(columns='_a').reset_index(drop=True); keep = []
    for i, g in enumerate(F.geometry):
        gg = g
        for j in keep:
            if gg.intersects(F.geometry[j]): gg = gg.difference(F.geometry[j])
        if gg.is_empty or gg.area < 9 / 0.0929: continue
        F.at[i, 'geometry'] = max(shapely.get_parts(gg), key=lambda q: q.area); keep.append(i)
    F = F.loc[keep].reset_index(drop=True)
    F['class'] = F['class'].fillna('Building') if 'class' in F else 'Building'; F['iou_osm'] = F['iou_osm'] if 'iou_osm' in F else np.nan; F['area_m2'] = (F.area * 0.0929).round(1); F['bld_id'] = range(1, len(F) + 1)
    F = F[['bld_id', 'class', 'area_m2', 'src', 'action', 'iou_osm', 'geometry']]
    F.to_file(OUT_DIR + PFX + 'Buildings_corrected.shp'); F.to_file(OUT_DIR + PFX + 'digitized.gpkg', layer='buildings_corrected')
    # ---------- report ----------
    Oin = O[O.intersects(site)]; Min = M[M.intersects(site)]
    rep = dict(osm_shift_m=[round(shift[0] * 0.3048, 1), round(shift[1] * 0.3048, 1)], image_buildings=int(len(gpd.read_file(OUT_DIR + PFX + 'Buildings.shp'))), osm_buildings=int(len(Oin)), microsoft_buildings=int(len(Min)),
               merged_groups=int(sum(1 for r_ in new_rows if r_['action'].startswith('merged'))), pieces_merged=len(drop_a), outlines_corrected_to_osm=nsw, osm_only_added=added,
               final_buildings=int(len(F)), final_by_action=F.action.value_counts().to_dict(), median_iou_with_osm=float(np.nanmedian(F.iou_osm.astype(float))) if F.iou_osm.notna().any() else None)
    json.dump(rep, open(OUT_DIR + PFX + 'comparison_report.json', 'w'), indent=1); print(json.dumps(rep, indent=1))

def st_clean(ctx):
    """Drop false detections, flag foundations, final walls."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    import sys, numpy as np, cv2, rasterio, geopandas as gpd, pandas as pd, shapely
    from shapely.ops import transform as shp_transform
    D = D
    r = rasterio.open(WORK + 'img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); Ti = ~r.transform
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY); edges = (cv2.Canny(gray, 40, 110) > 0).astype(float)
    C = gpd.read_file(D + PFX + 'Buildings_corrected.shp'); A = gpd.read_file(D + PFX + 'Buildings.shp')
    C3 = C.to_crs(3857); rows = []
    for i, g in enumerate(C3.geometry):
        p = shp_transform(lambda x, y, z=None: Ti * (x, y), g); p = max(shapely.get_parts(p.buffer(0)), key=lambda q: q.area)
        f = features(p, img, edges) or {}
        q = list(g.minimum_rotated_rectangle.exterior.coords); import math
        f['rect_fill'] = g.area / g.minimum_rotated_rectangle.area; f['nverts'] = len(g.exterior.coords) - 1
        m = A[A.intersects(C.geometry[i])]; f['conf'] = float(m.conf.max()) if len(m) else np.nan
        rows.append(f)
    F = pd.concat([C.drop(columns='geometry'), pd.DataFrame(rows).drop(columns='area_m2', errors='ignore')], axis=1)
    grp = np.where(F.action.str.startswith('image only (not'), 'unconfirmed', np.where(F.src.str.contains('OSM') | F.action.str.contains('Microsoft'), 'confirmed', 'other'))
    F['grp'] = grp; F.to_csv(WORK + 'final_feats.csv', index=False)
    print(F.groupby('grp')[['area_m2', 'rect_fill', 'nverts', 'conf', 'green', 'tex', 'edge', 'sat', 'bright']].median().round(2).to_string())
    u = F[F.grp == 'unconfirmed']
    print('unconfirmed area bins', pd.cut(u.area_m2, [0, 12, 20, 40, 80, 200, 5000]).value_counts().sort_index().to_dict())
    print('unconfirmed rect_fill bins', pd.cut(u.rect_fill, [0, .6, .7, .8, .9, 1.01]).value_counts().sort_index().to_dict())

    """Final cleaning for the site: unconfirmed footprints, foundations, walls."""
    import sys, math, numpy as np, pandas as pd, geopandas as gpd, rasterio, cv2, shapely
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union, transform as shp_transform, linemerge
    D = D
    C = gpd.read_file(D + PFX + 'Buildings_corrected.shp'); F = pd.read_csv(WORK + 'final_feats.csv')
    site = gpd.read_file(SITE_KML).to_crs(2136).geometry.iloc[0]
    def aspect(g):
        q = list(g.minimum_rotated_rectangle.exterior.coords); a, b = sorted([math.dist(q[0], q[1]), math.dist(q[1], q[2])]); return b / max(a, 1e-6)
    F['aspect'] = [aspect(g) for g in C.geometry]
    # ---------- 1. buildings: keep / drop / review ----------
    def verdict(f):
        vehicle = f.area_m2 < 22 and f.aspect >= 1.8
        if f.grp != 'unconfirmed': return 'keep', 'confirmed by OSM / Microsoft'
        if f.area_m2 < 12: return 'drop', 'too small (object)'
        if vehicle: return 'drop', 'vehicle-like (small, elongated)'
        if f.green > 16 and f.bright < 120: return 'drop', 'vegetation'
        if f.rect_fill < 0.8 and f.R > f.G + 8 and f.G > f.B + 8 and f.edge < 0.15: return 'drop', 'bare ground'
        if f.rect_fill < 0.7 and f.area_m2 < 80: return 'drop', 'irregular blob'
        if f.rect_fill >= 0.8: return 'keep', 'regular roof shape (image only)'
        if f.area_m2 >= 25 and f.rect_fill >= 0.72: return 'keep', 'roof (image only, slightly irregular)'
        return 'drop', 'doubtful (small / irregular)'
    v = F.apply(verdict, axis=1, result_type='expand'); C['verdict'], C['reason'] = v[0].values, v[1].values
    # ---------- 2. foundations / uncompleted buildings: open interior with room walls, grey blockwork ----------
    fnd = (F.sat < 0.16) & (F.edge > 0.30) & (F.tex > 38) & F.bright.between(100, 190) & (F.area_m2 > 40)
    C['class'] = np.where(fnd, 'Foundation / uncompleted', C['class'].fillna('Building'))
    print('foundations / uncompleted:', int(fnd.sum()))
    K = C[C.verdict == 'keep'].copy(); X = C[C.verdict == 'drop'].copy()
    K['area_m2'] = (K.area * 0.0929).round(1); K['bld_id'] = range(1, len(K) + 1)
    K = K[['bld_id', 'class', 'area_m2', 'src', 'action', 'reason', 'geometry']]
    K.to_file(D + PFX + 'Buildings_final.shp'); X[['class', 'area_m2', 'action', 'reason', 'geometry']].to_file(D + PFX + 'Buildings_removed.shp')
    print('buildings kept', len(K), '| removed', len(X), X.reason.value_counts().to_dict())
    # ---------- 3. walls: stronger detection, joined, off roofs and roads ----------
    r = rasterio.open(WORK + 'img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); T = r.transform; Ti = ~r.transform
    K3 = K.to_crs(3857); bpx = [shp_transform(lambda x, y, z=None: Ti * (x, y), g) for g in K3.geometry]
    from skimage.filters import sato
    from skimage.morphology import skeletonize, remove_small_objects
    from skimage.transform import probabilistic_hough_line
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(float) / 255
    rid = sato(g, sigmas=[1.0, 1.5], black_ridges=False)
    m = remove_small_objects(rid > np.percentile(rid, 90), 20); sk = skeletonize(m)
    segs = probabilistic_hough_line(sk, threshold=7, line_length=int(4.0 / 0.299), line_gap=4, rng=0)
    BU = unary_union([p.buffer(2.5) for p in bpx])
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV); gr = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(float)
    mu = cv2.blur(gr, (21, 21)); sd = np.sqrt(np.maximum(cv2.blur(gr * gr, (21, 21)) - mu * mu, 0))
    road = (sd < 11) & (hsv[:, :, 1] < 45) & (gr > 60) & (gr < 160); road = cv2.morphologyEx(road.astype(np.uint8), cv2.MORPH_OPEN, np.ones((13, 13), np.uint8)).astype(bool)
    keep_s = []
    for (x0, y0), (x1, y1) in segs:
        s = LineString([(x0, y0), (x1, y1)])
        if s.intersection(BU).length > 0.4 * s.length: continue
        n = max(2, int(s.length)); xs = np.clip(np.linspace(x0, x1, n).astype(int), 0, road.shape[1] - 1); ys = np.clip(np.linspace(y0, y1, n).astype(int), 0, road.shape[0] - 1)
        if road[ys, xs].mean() > 0.4: continue
        keep_s.append(s)
    # join: snap near-collinear segments that touch / overlap (buffer-dissolve then centrelines via skeleton of the dissolved strip)
    strip = unary_union([s.buffer(0.9, cap_style=2) for s in keep_s])
    joined = []
    for part in shapely.get_parts(strip):
        q = list(part.minimum_rotated_rectangle.exterior.coords); e1 = np.array(q[1]) - np.array(q[0]); e2 = np.array(q[2]) - np.array(q[1])
        L, Wd = (e1, e2) if np.linalg.norm(e1) >= np.linalg.norm(e2) else (e2, e1)
        if np.linalg.norm(Wd) < 4:                                               # straight strip -> one wall line
            c = np.array(part.minimum_rotated_rectangle.centroid.coords[0]); u = L / np.linalg.norm(L)
            joined.append(LineString([tuple(c - u * np.linalg.norm(L) / 2), tuple(c + u * np.linalg.norm(L) / 2)]))
        else:                                                                    # corner / L-shaped: keep its member segments
            joined += [s for s in keep_s if s.within(part.buffer(0.1))]
    joined = [s for s in joined if s.length * 0.299 >= 4]
    WL = gpd.GeoDataFrame(geometry=[shp_transform(lambda x, y, z=None: T * (x, y), s) for s in joined], crs=3857).to_crs(2136)
    WL = WL[WL.intersects(site)].reset_index(drop=True); WL['length_m'] = (WL.length * 0.3048).round(1)
    # wall type: along a road edge (street frontage) or between plots
    RDm = gpd.GeoSeries([shp_transform(lambda x, y, z=None: T * (x, y), p) for p in shapely.get_parts(shapely.geometry.MultiPolygon([shapely.geometry.Polygon(c[:, 0, :]) for c in cv2.findContours(road.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0] if len(c) >= 4]).buffer(0))], crs=3857).to_crs(2136).union_all()
    WL['wall_type'] = ['Street frontage wall' if g.distance(RDm) < 8 else 'Plot boundary wall' for g in WL.geometry]
    WL['wall_id'] = range(1, len(WL) + 1); WL = WL[['wall_id', 'wall_type', 'length_m', 'geometry']]
    WL.to_file(D + PFX + 'Walls_final.shp')
    print('walls', len(WL), WL['wall_type'].value_counts().to_dict(), 'total m', round(WL.length_m.sum()))
    with pd.ExcelWriter(D + PFX + 'digitizing_summary.xlsx') as xw:
        pd.DataFrame([dict(item='Buildings (final)', count=int((K['class'] == 'Building').sum()), area_m2=round(K[K['class'] == 'Building'].area_m2.sum())),
                      dict(item='Foundations / uncompleted', count=int((K['class'] != 'Building').sum()), area_m2=round(K[K['class'] != 'Building'].area_m2.sum())),
                      dict(item='Walls (m)', count=len(WL), area_m2=None), dict(item='Removed (not buildings)', count=len(X), area_m2=None)]).to_excel(xw, sheet_name='summary', index=False)
        K.drop(columns='geometry').to_excel(xw, sheet_name='buildings', index=False)
        K.groupby(['src', 'reason']).size().rename('count').reset_index().to_excel(xw, sheet_name='sources', index=False)

def st_database(ctx):
    """Check / correct footprints against the building database; attach occupancy and height."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    """Check / correct the digitized footprints against the building database (obm_load).  
    1. align the database onto our footprints; 2. our outline covering 2+ database buildings -> replaced by them (finer detail);
    3. one-to-one -> keep the outline that sits better on roof edges in the image; 4. database-only buildings added (not on the carriageway);
    5. every building gets database occupancy / height / source. Our previous file is backed up as *_pre_obm.shp."""
    import sys, os, shutil, numpy as np, cv2, rasterio, geopandas as gpd, pandas as pd, shapely, json
    from shapely.ops import unary_union, transform as shp_transform
    from shapely import affinity
    FT = 0.3048
    P = PFX
    site_g = gpd.read_file(SITE_KML); site = site_g.to_crs(2136).geometry.iloc[0]
    src = D + P + 'Buildings_final.shp'; bak = D + P + 'Buildings_final_pre_obm.shp'
    if not os.path.exists(bak):
        for ext in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
            if os.path.exists(src[:-4] + ext): shutil.copy(src[:-4] + ext, bak[:-4] + ext)
    A = gpd.read_file(bak); G = obm_load(site_g); G = G[G.intersects(site.buffer(30 / FT))].reset_index(drop=True)
    CW = gpd.read_file(D + P + 'Carriageways.shp').union_all() if os.path.exists(D + P + 'Carriageways.shp') else None
    r = rasterio.open(WORK + 'img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); Ti = ~r.transform
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(float); gm = np.hypot(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3), cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3))
    def edge_score(g):
        p = shp_transform(lambda x, y, z=None: Ti * (x, y), gpd.GeoSeries([g], crs=2136).to_crs(3857).iloc[0]); b = max(shapely.get_parts(p), key=lambda q: q.area).exterior
        pts = np.array([b.interpolate(s).coords[0] for s in np.linspace(0, b.length, max(8, int(b.length)))]).astype(int)
        pts[:, 0] = np.clip(pts[:, 0], 0, gm.shape[1] - 1); pts[:, 1] = np.clip(pts[:, 1], 0, gm.shape[0] - 1); return float(gm[pts[:, 1], pts[:, 0]].mean())
    # ---------- 1. alignment ----------
    sh = []
    for g in G.geometry.sample(min(400, len(G)), random_state=0):
        m = A[A.intersects(g)]
        if len(m) == 1:
            a = m.geometry.iloc[0]
            if a.intersection(g).area / a.union(g).area > 0.5: sh.append(np.subtract(a.centroid.coords[0], g.centroid.coords[0]))
    shift = np.median(sh, axis=0) if len(sh) >= 15 else np.zeros(2)
    G['geometry'] = G.geometry.apply(lambda g: affinity.translate(g, *shift)); print(f'database shifted {shift[0] * FT:.1f} m E, {shift[1] * FT:.1f} m N onto our footprints ({len(sh)} matches)')
    # ---------- 2-3. our buildings vs database ----------
    gt = shapely.STRtree(list(G.geometry)); used = set(); rows = []; n_split = n_swap = 0
    for i, a in zip(A.index, A.geometry):
        cand = [j for j in gt.query(a) if G.geometry[j].intersection(a).area > 0.6 * G.geometry[j].area]
        if len(cand) >= 2 and sum(G.geometry[j].intersection(a).area for j in cand) > 0.5 * a.area:          # our blob = several houses
            for j in cand: rows.append(dict(geometry=G.geometry[j], db=j, src_new='database', action=f'split: our outline covered {len(cand)} buildings -> database outlines')); used.add(j)
            n_split += 1; continue
        ov = [(G.geometry[j].intersection(a).area / G.geometry[j].union(a).area, j) for j in gt.query(a) if j not in used]
        if ov and max(ov)[0] > 0.3:
            iou, j = max(ov); used.add(j)
            if edge_score(G.geometry[j]) > edge_score(a) * 1.05: rows.append(dict(geometry=G.geometry[j], db=j, src_new='database', action='outline replaced by database (fits roof edges better)', old=i)); n_swap += 1
            else: rows.append(dict(geometry=a, db=j, src_new='image', action='image outline kept (agrees with database)', old=i))
        else: rows.append(dict(geometry=a, db=None, src_new='image', action='image only (not in database)', old=i))
    # ---------- 4. database-only buildings ----------
    n_add = 0; Au = unary_union([r_['geometry'] for r_ in rows])
    for j, g in enumerate(G.geometry):
        if j in used or not g.intersects(site) or g.area * FT * FT < 9: continue
        if g.intersection(Au).area > 0.3 * g.area: continue
        if CW is not None and g.intersection(CW).area > 0.5 * g.area: continue
        rows.append(dict(geometry=g, db=j, src_new='database', action=f'added from database ({G.source[j]})')); n_add += 1
    F = gpd.GeoDataFrame(rows, crs=2136)
    # overlaps: database outlines win over image outlines, larger over smaller
    F['_k'] = (F.src_new == 'database').astype(int) * 1e9 + F.area; F = F.sort_values('_k', ascending=False).reset_index(drop=True); keep = []
    for i, g in enumerate(F.geometry):
        gg = g
        for k in keep:
            if gg.intersects(F.geometry[k]): gg = gg.difference(F.geometry[k])
        if gg.is_empty or gg.area * FT * FT < 6: continue
        F.at[i, 'geometry'] = max(shapely.get_parts(gg), key=lambda q: q.area); keep.append(i)
    F = F.loc[keep].reset_index(drop=True); F = F[F.intersects(site)].reset_index(drop=True)
    # ---------- 5. attributes ----------
    def best_db(g, j):
        if j is not None and not pd.isna(j): return int(j)
        c = [(G.geometry[k].intersection(g).area, k) for k in gt.query(g)]; c = [x for x in c if x[0] > 0.3 * g.area]
        return max(c)[1] if c else None
    dbl = [best_db(g, j) for g, j in zip(F.geometry, F.db)]; F = F.drop(columns='db')
    ok = lambda j: j is not None and not pd.isna(j)
    col = lambda c: [G[c][int(j)] if ok(j) else None for j in dbl]
    F['db_id'] = col('id'); F['db_source'] = col('source')
    F['occupancy'] = col('occupancy'); F['use_db'] = col('use_obm')
    F['height'] = col('height')
    oldcls = A['class'] if 'class' in A else pd.Series('Building', index=A.index)
    F['class'] = [oldcls[o] if 'old' in F and not pd.isna(o) else 'Building' for o in (F['old'] if 'old' in F else [np.nan] * len(F))]
    F['src'] = np.where(F.src_new == 'database', 'database (' + F.db_source.fillna('?') + ')', [A.src[int(o)] if not pd.isna(o) else 'image' for o in F['old']] if 'old' in F else 'image')
    F['area_m2'] = (F.area * FT * FT).round(1); F['bld_id'] = range(1, len(F) + 1)
    F = F[['bld_id', 'class', 'area_m2', 'src', 'action', 'db_id', 'db_source', 'occupancy', 'use_db', 'height', 'geometry']]
    F.to_file(src)
    rep = dict(ours_before=len(A), database_in_site=int(G.intersects(site).sum()), shift_m=[round(shift[0] * FT, 2), round(shift[1] * FT, 2)],
               our_blobs_split=n_split, outlines_replaced=n_swap, database_only_added=n_add, final=len(F), by_action=F.action.str.replace(r'\d+ buildings', 'n buildings', regex=True).value_counts().to_dict(),
               occupancy_known=round(float((F.occupancy.notna() & (F.occupancy != 'UNK')).mean()), 2), occupancy=F.occupancy.value_counts().to_dict())
    json.dump(rep, open(D + P + 'database_check_report.json', 'w'), indent=1); print(json.dumps(rep, indent=1))

def st_roads(ctx):
    """Carriageway widths measured on the image; walls on the carriageway removed."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    """Carriageway width per road measured on the image (perpendicular profiles from the OSM centreline); walls on the carriageway removed."""
    import numpy as np, cv2, rasterio, geopandas as gpd, pandas as pd, shapely
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union
    D = D
    r = rasterio.open(WORK + 'img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); Ti = ~r.transform; PX = 0.299
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV); gr = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(float)
    mu = cv2.blur(gr, (7, 7)); sd = np.sqrt(np.maximum(cv2.blur(gr * gr, (7, 7)) - mu * mu, 0))
    roadlike = (hsv[:, :, 1] < 55) & (gr > 50) & (gr < 175) & (sd < 18)
    R = gpd.read_file(WORK + 'osm_roads.gpkg'); R3 = R.to_crs(3857)
    B = gpd.read_file(D + PFX + 'Buildings_final.shp').to_crs(3857).union_all()
    DEF = {'primary': 9.0, 'secondary': 7.0, 'tertiary': 5.5, 'unclassified': 4.0, 'residential': 3.5, 'service': 2.5, 'footway': 1.0, 'path': 1.0}
    half = []
    for g, hw in zip(R3.geometry, R.highway):
        ws = []
        for s in np.arange(8, g.length - 8, 15):
            p = np.array(g.interpolate(s).coords[0]); q = np.array(g.interpolate(min(g.length, s + 2)).coords[0]) - np.array(g.interpolate(max(0, s - 2)).coords[0])
            t = q / (np.linalg.norm(q) + 1e-9); n = np.array([-t[1], t[0]]); side = []
            for sg in (1, -1):
                miss, d = 0, 0.0
                for k in range(1, 100):
                    x, y = Ti * tuple(p + sg * n * k * PX); x, y = int(x), int(y)
                    if not (0 <= x < img.shape[1] and 0 <= y < img.shape[0]): break
                    if Point(p + sg * n * k * PX).within(B): break
                    if roadlike[y, x]: miss = 0; d = k * PX
                    else:
                        miss += 1
                        if miss > 4: break
                side.append(d)
            if min(side) > 0.5: ws.append(sum(side))
        w = float(np.median(ws)) if len(ws) >= 3 else 2 * DEF.get(hw, 3.0)
        w = float(np.clip(w, 2 * DEF.get(hw, 3.0) * 0.5, 2 * DEF.get(hw, 3.0) * 1.8))
        half.append(w / 2)
    R['carriage_w'] = np.round(np.array(half) * 2, 1); R.to_file(WORK + 'osm_roads_width.gpkg')
    print(R.groupby('highway').carriage_w.median().to_string())
    # carriageway polygons (metres in 3857 ~ ground metres here) and wall cleaning
    CW = gpd.GeoDataFrame(geometry=[g.buffer(h - 0.5, cap_style=2) for g, h in zip(R3.geometry, half)], crs=3857).union_all()
    W = gpd.read_file(D + PFX + 'Walls_final.shp').to_crs(3857)
    inroad = [g.intersection(CW).length > 0.5 * g.length for g in W.geometry]
    print('walls', len(W), '| on the carriageway', sum(inroad))
    Wk = W[~np.array(inroad)].copy(); Wx = W[np.array(inroad)].copy()
    # pieces partly on the road: trim to the part off the carriageway
    Wk['geometry'] = [g.difference(CW) if g.intersects(CW) else g for g in Wk.geometry]
    Wk = Wk.explode(index_parts=False); Wk = Wk[Wk.geometry.length > 3]
    Wk = Wk.to_crs(2136); Wk['length_m'] = (Wk.length * 0.3048).round(1); Wk['wall_id'] = range(1, len(Wk) + 1)
    Wk.to_file(D + PFX + 'Walls_final.shp'); Wx.to_crs(2136).to_file(D + PFX + 'Walls_removed_in_road.shp')
    gpd.GeoDataFrame(geometry=[CW], crs=3857).to_crs(2136).to_file(D + PFX + 'Carriageways.shp')
    print('walls kept', len(Wk), round(Wk.length_m.sum()), 'm | removed', len(Wx))

def st_landuse(ctx):
    """Road reserves, existing use per building (OSM tag > database occupancy > rules), vacant land."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    """the site upgrading plan - existing situation: road reserves (existing widths, pinch points), existing land use per building (OSM tags + rules), vacant land."""
    import numpy as np, geopandas as gpd, pandas as pd, rasterio, cv2, shapely, json
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union, transform as shp_transform
    D = D; FT = 0.3048
    site = gpd.read_file(SITE_KML).to_crs(2136).geometry.iloc[0]
    B = gpd.read_file(D + PFX + 'Buildings_final.shp'); W = gpd.read_file(D + PFX + 'Walls_final.shp')
    R = gpd.read_file(WORK + 'osm_roads_width.gpkg'); R = R[R.highway.isin(['primary', 'secondary', 'tertiary', 'unclassified', 'residential', 'service'])].reset_index(drop=True)
    P = gpd.read_file(WORK + 'osm_poi.gpkg')
    OBST = unary_union(list(B.geometry) + [w.buffer(0.3) for w in W.geometry])
    # ---------- 1. existing road reserves: building / wall line to building / wall line ----------
    res, pinch_pts = [], []
    for i, (g, cw) in enumerate(zip(R.geometry, R.carriage_w)):
        ws = []
        for s in np.arange(15, g.length - 15, 30):                              # every ~9 m
            p = np.array(g.interpolate(s).coords[0]); q = np.array(g.interpolate(min(g.length, s + 5)).coords[0]) - np.array(g.interpolate(max(0, s - 5)).coords[0])
            t = q / (np.linalg.norm(q) + 1e-9); n = np.array([-t[1], t[0]]); side = []
            for sg in (1, -1):
                ray = LineString([tuple(p), tuple(p + sg * n * 120)]); h = ray.intersection(OBST)
                side.append(min(Point(p).distance(x) for x in shapely.get_parts(h)) if not h.is_empty else np.nan)
            if not any(np.isnan(side)): ws.append((sum(side), Point(p)))
        if ws:
            arr = np.array([w for w, _ in ws]); med = float(np.median(arr)); mn = float(arr.min())
            res.append(dict(reserve_ft=round(med), reserve_m=round(med * FT, 1), min_ft=round(mn), min_m=round(mn * FT, 1)))
            for w_, pt in ws:
                if w_ < max(cw / FT + 6, 0.8 * med) and w_ < 30: pinch_pts.append(dict(road=R.name[i] or R.highway[i], highway=R.highway[i], width_m=round(w_ * FT, 1), geometry=pt))
        else: res.append(dict(reserve_ft=np.nan, reserve_m=np.nan, min_ft=np.nan, min_m=np.nan))
    R = pd.concat([R, pd.DataFrame(res)], axis=1); R['carriage_w_m'] = R.carriage_w
    R = gpd.GeoDataFrame(R, geometry='geometry', crs=2136); R = R[R.intersects(site.buffer(30))]
    R[['osm_id', 'name', 'highway', 'carriage_w_m', 'reserve_m', 'reserve_ft', 'min_m', 'geometry']].to_file(D + PFX + 'Roads_existing.shp')
    PP = gpd.GeoDataFrame(pinch_pts, crs=2136) if pinch_pts else gpd.GeoDataFrame(columns=['road', 'width_m', 'geometry'], crs=2136)
    # merge pinch points closer than 20 m into one location
    if len(PP):
        cl = unary_union([p.buffer(30) for p in PP.geometry]); PPc = []
        for c in shapely.get_parts(cl):
            sub = PP[PP.within(c)]; j = sub.width_m.idxmin(); PPc.append(sub.loc[j])
        PP = gpd.GeoDataFrame(PPc, crs=2136).reset_index(drop=True)
    PP = PP[PP.within(site)]; PP.to_file(D + PFX + 'Road_pinch_points.shp')
    print('roads', len(R), '| median reserve by class (m):', R.groupby('highway').reserve_m.median().round(1).to_dict(), '| pinch points', len(PP))
    # ---------- 2. existing land use per building ----------
    TAG = {'school': 'Education', 'university': 'Education', 'kindergarten': 'Education', 'library': 'Civic', 'post_office': 'Civic', 'place_of_worship': 'Religious',
           'clinic': 'Health', 'hospital': 'Health', 'pharmacy': 'Health', 'doctors': 'Health', 'restaurant': 'Commercial', 'fast_food': 'Commercial', 'bar': 'Commercial',
           'cafe': 'Commercial', 'bank': 'Commercial', 'bureau_de_change': 'Commercial', 'fuel': 'Commercial (fuel)', 'nightclub': 'Commercial', 'hotel': 'Commercial (hotel)',
           'apartment': 'Residential', 'marketplace': 'Market', 'bus_station': 'Transport terminal', 'pub': 'Commercial', 'mall': 'Commercial', 'supermarket': 'Commercial', 'office': 'Office', 'company': 'Office'}
    def tag_use(row):
        if row.key == 'shop': return 'Commercial'
        if row.key == 'office': return 'Office'
        return TAG.get(row.val)
    P['use'] = P.apply(tag_use, axis=1); P = P[P.use.notna()]
    major = R[R.highway.isin(['primary', 'secondary'])]
    MAJ = unary_union([g.buffer(cw / FT / 2 + 40) for g, cw in zip(major.geometry, major.carriage_w)])          # frontage zone ~12 m beyond the kerb
    use, how = [], []
    for g, src_, udb in zip(B.geometry, B.src, B.use_db if 'use_db' in B else [None] * len(B)):
        near = P[P.distance(g) < 5 / FT]
        if len(near): u = near.use.mode().iloc[0]; use.append(u); how.append('OSM tag: ' + ', '.join(sorted(set(near.val.astype(str))))); continue
        if isinstance(udb, str): use.append(udb); how.append('building database occupancy'); continue
        a = g.area * FT * FT
        if g.intersects(MAJ): use.append('Commercial / mixed use' if a > 150 else 'Mixed use (shop + residence)'); how.append('rule: frontage on a primary / secondary road')
        elif a > 1500 and not str(src_).startswith('OSM/Microsoft') and not isinstance(udb, str): use.append('Institutional / large commercial (verify)'); how.append('rule: very large untagged building')
        else: use.append('Residential'); how.append('rule: default')
    B['ex_use'] = use; B['use_source'] = how
    B['use_conf'] = ['confirmed' if str(h).startswith(('OSM tag', 'building database')) else 'unconfirmed' for h in how]       # rule-based guesses must be confirmed by the planner
    print('uses confirmed by OSM / database:', int((B.use_conf == 'confirmed').sum()), 'of', len(B), '| to confirm:', int((B.use_conf != 'confirmed').sum()))
    B.to_file(D + PFX + 'Existing_land_use_buildings.shp')
    print(B.ex_use.value_counts().to_dict())
    # ---------- 3. vacant / open land (no buildings, not road, bare or grass on the image) ----------
    r = rasterio.open(WORK + 'img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); T = r.transform; Ti = ~T
    B3 = B.to_crs(3857); R3 = gpd.read_file(D + PFX + 'Carriageways.shp').to_crs(3857)
    mask = np.zeros(img.shape[:2], np.uint8)
    for g in list(B3.buffer(2).geometry) + list(R3.buffer(1).geometry):
        for p in shapely.get_parts(g):
            cv2.fillPoly(mask, [np.array([Ti * c for c in p.exterior.coords], np.int32)], 1)
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV); gr = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(float)
    Rc, Gc, Bc = [img[:, :, k].astype(float) for k in range(3)]
    bare = (Rc > Gc + 4) & (Gc > Bc + 4) & (gr > 110)                          # bare soil / sand
    grass = (Gc > Rc + 4) & (Gc > Bc + 4) & (gr > 80) & (hsv[:, :, 1] > 40)   # grass / weeds (not dark tree crowns)
    open_ = (bare | grass) & (mask == 0)
    open_ = cv2.morphologyEx(open_.astype(np.uint8), cv2.MORPH_OPEN, np.ones((7, 7), np.uint8)); open_ = cv2.morphologyEx(open_, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cs, _ = cv2.findContours(open_, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); vac = []
    for c in cs:
        if len(c) < 4: continue
        p = Polygon([T * tuple(pt) for pt in c[:, 0, :].astype(float)]).buffer(0)
        if p.area >= 400: vac.append(p.simplify(1.0))
    V = gpd.GeoDataFrame(geometry=vac, crs=3857).to_crs(2136); V = V[V.intersects(site)]; V['geometry'] = V.intersection(site)
    V['area_m2'] = (V.area * FT * FT).round(0); V = V[V.area_m2 >= 400].reset_index(drop=True); V['vac_id'] = range(1, len(V) + 1)
    V.to_file(D + PFX + 'Vacant_open_land.shp')
    print('vacant / open parcels >= 400 m2:', len(V), '| total m2', V.area_m2.sum(), '| largest', V.area_m2.nlargest(5).tolist())

def st_reserves(ctx):
    """Centrelines realigned to the image; reserves re-measured; pinch points."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    """Road centrelines realigned to the image; existing reserves re-measured; pinch points by class minimum and the road's own width."""
    import numpy as np, cv2, rasterio, geopandas as gpd, pandas as pd, shapely
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union
    from shapely import affinity
    D = D; FT = 0.3048
    r = rasterio.open(WORK + 'img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); Ti = ~r.transform
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV); gr = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(float)
    mu = cv2.blur(gr, (7, 7)); sd = np.sqrt(np.maximum(cv2.blur(gr * gr, (7, 7)) - mu * mu, 0))
    roadlike = ((hsv[:, :, 1] < 55) & (gr > 50) & (gr < 175) & (sd < 18)).astype(float); roadlike = cv2.blur(roadlike, (5, 5))
    site = gpd.read_file(SITE_KML).to_crs(2136).geometry.iloc[0]
    R = gpd.read_file(D + PFX + 'Roads_existing.shp'); R3 = R.to_crs(3857)
    B = gpd.read_file(D + PFX + 'Buildings_final.shp'); W = gpd.read_file(D + PFX + 'Walls_final.shp')
    def score(line):
        pts = [line.interpolate(t) for t in np.linspace(0, line.length, max(4, int(line.length)))]; v = []
        for p in pts:
            x, y = Ti * (p.x, p.y); x, y = int(x), int(y)
            if 0 <= x < img.shape[1] and 0 <= y < img.shape[0]: v.append(roadlike[y, x])
        return np.mean(v) if v else 0
    new = []; orig = list(R3.geometry)
    for g in R3.geometry:
        best = (score(g), g)
        for off in np.arange(-6, 6.01, 0.5):
            if off == 0: continue
            try: o = g.offset_curve(off)
            except Exception: continue
            if o.is_empty or o.geom_type != 'LineString': continue
            sc = score(o)
            if sc > best[0] + 0.02: best = (sc, o)
        new.append(best[1])
    # segments are nudged one by one: ends that met before the nudge meet again (average position); ends that stopped on another road go back onto it
    ends = [(i, k, Point(g.coords[0 if k == 0 else -1])) for i, g in enumerate(orig) for k in (0, 1)]
    newc = [list(g.coords) for g in new]
    from collections import defaultdict
    groups, seen = [], set()
    for a, (i, k, p) in enumerate(ends):
        if a in seen: continue
        grp = [b for b, (j, kk, q) in enumerate(ends) if b not in seen and p.distance(q) < 1.0]
        seen.update(grp); groups.append(grp)
    for grp in groups:
        if len(grp) < 2: continue
        pts = np.array([newc[ends[b][0]][0 if ends[b][1] == 0 else -1][:2] for b in grp]); m = tuple(pts.mean(0))
        for b in grp: newc[ends[b][0]][0 if ends[b][1] == 0 else -1] = m
    for grp in groups:
        if len(grp) != 1: continue
        i, k, p = ends[grp[0]]
        hits = [j for j, g in enumerate(orig) if j != i and g.distance(p) < 1.0]
        if hits:
            j = hits[0]; gj = LineString(newc[j]); q = gj.interpolate(gj.project(Point(newc[i][0 if k == 0 else -1])))
            newc[i][0 if k == 0 else -1] = q.coords[0]
    new = [LineString(c) for c in newc]
    R3['geometry'] = new; R = R3.to_crs(2136)
    # one carriageway width per named road (single segments can measure the median or a lay-by as road)
    nm = R.name.fillna('').astype(str)
    R['carriage_w'] = np.where(nm != '', R.groupby([nm, R.highway]).carriage_w.transform('median'), R.carriage_w)
    OBST = unary_union(list(B.geometry) + [w.buffer(0.3) for w in W.geometry])
    MINW = {'service': 7.5, 'residential': 9.0, 'unclassified': 9.0, 'tertiary': 12.0, 'secondary': 15.0, 'primary': 20.0}
    res, pins, onroad = [], [], []
    for i, g in enumerate(R.geometry):
        ws = []
        for s in np.arange(20, g.length - 20, 30):
            p = np.array(g.interpolate(s).coords[0]); q = np.array(g.interpolate(min(g.length, s + 5)).coords[0]) - np.array(g.interpolate(max(0, s - 5)).coords[0])
            t = q / (np.linalg.norm(q) + 1e-9); n = np.array([-t[1], t[0]])
            if Point(p).within(OBST): onroad.append(dict(road=R.name.iloc[i] or R.highway.iloc[i], geometry=Point(p))); continue
            side = []
            for sg in (1, -1):
                h = LineString([tuple(p), tuple(p + sg * n * 130)]).intersection(OBST)
                side.append(min(Point(p).distance(x) for x in shapely.get_parts(h)) if not h.is_empty else np.nan)
            if not any(np.isnan(side)): ws.append((sum(side) * FT, Point(p)))
        if not ws: res.append(np.nan); continue
        arr = np.array([w for w, _ in ws]); med = float(np.median(arr)); res.append(round(med, 1))
        lim = min(0.8 * med, MINW.get(R.highway.iloc[i], 9.0))
        for w_, pt in ws:
            if 2.5 < w_ < lim: pins.append(dict(road=R.name.iloc[i] or R.highway.iloc[i], highway=R.highway.iloc[i], width_m=round(w_, 1), road_med_m=round(med, 1), class_min_m=MINW.get(R.highway.iloc[i], 9.0), geometry=pt))
    R['reserve_m'] = res; R.to_file(D + PFX + 'Roads_existing.shp')
    PP = gpd.GeoDataFrame(pins, crs=2136)
    if len(PP):
        cl = unary_union([p.buffer(25 / FT) for p in PP.geometry]); keep = []
        for c in shapely.get_parts(cl):
            sub = PP[PP.within(c)]; keep.append(sub.loc[sub.width_m.idxmin()])
        PP = gpd.GeoDataFrame(keep, crs=2136).reset_index(drop=True)
    PP = PP[PP.within(site)].reset_index(drop=True)
    PP['action'] = np.where(PP.width_m < 6, 'Severe: set back encroaching wall / structure; building line on redevelopment', 'Narrow: no parking, traffic calming; building line on redevelopment')
    PP.to_file(D + PFX + 'Plan_pinch_point_actions.shp'); PP.to_file(D + PFX + 'Road_pinch_points.shp')
    OR = gpd.GeoDataFrame(onroad, crs=2136); OR = OR[OR.within(site)]
    OR.to_file(D + PFX + 'Check_footprint_on_road.shp') if len(OR) else None
    print('pinch points', len(PP), PP.width_m.describe().round(1).to_dict() if len(PP) else '', '| severe (<6 m)', int((PP.width_m < 6).sum()), '| centreline samples inside a footprint (check):', len(OR))
    print(R.groupby('highway').reserve_m.median().round(1).to_dict())

def st_trees(ctx):
    """Continuous tree belt / drain corridor from the image."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    import numpy as np, geopandas as gpd, rasterio, cv2
    from shapely.geometry import Polygon
    D = D; FT = 0.3048
    site = gpd.read_file(SITE_KML).to_crs(2136).geometry.iloc[0]
    r = rasterio.open(WORK + 'img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); T = r.transform
    Rc, Gc, Bc = [img[:, :, k].astype(float) for k in range(3)]; br = img.mean(2)
    tree = ((Gc - (Rc + Bc) / 2) > 16) & (br < 120)
    tree = cv2.morphologyEx(tree.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)); tree = cv2.morphologyEx(tree, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    cs, _ = cv2.findContours(tree, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); gw = []
    for c in cs:
        if len(c) < 10: continue
        p = Polygon([T * tuple(pt) for pt in c[:, 0, :].astype(float)]).buffer(0)
        if p.is_empty: continue
        q = list(p.minimum_rotated_rectangle.exterior.coords); a_, b_ = sorted([np.hypot(*np.subtract(q[0], q[1])), np.hypot(*np.subtract(q[1], q[2]))])
        if p.area > 2500 and b_ / max(a_, 1) > 3: gw.append(p.simplify(2))      # long, continuous tree belt (> 2,500 m2, at least 3:1)
    G = gpd.GeoDataFrame(geometry=gw, crs=3857).to_crs(2136); G['geometry'] = G.intersection(site); G = G[G.area * FT * FT > 1500]
    G.to_file(D + PFX + 'Tree_belt_raw.shp') if len(G) else None; print('tree belts', len(G), round(G.area.sum() * FT * FT))

def st_blocks(ctx):
    """Road surface (T-branch ends trimmed to the crossing road) and blocks."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    """the site existing situation: blocks (land between roads) and approximate existing plots (building-based partition of each block)."""
    import numpy as np, geopandas as gpd, pandas as pd, shapely
    from shapely.geometry import Point, Polygon, MultiPoint
    from shapely.ops import unary_union
    D = D; FT = 0.3048
    site = gpd.read_file(SITE_KML).to_crs(2136).geometry.iloc[0]
    R = gpd.read_file(D + PFX + 'Roads_existing.shp')
    B = gpd.read_file(D + PFX + 'Existing_land_use_buildings.shp')
    # ---------- roads: carriageway from the realigned centrelines; footways 2 m ----------
    osm = gpd.read_file(WORK + 'osm_roads.gpkg'); fw = osm[osm.highway.isin(['footway', 'path'])]
    LN = list(R.geometry) + list(fw.geometry); HW = [max(cw, 3.0) / 2 / FT for cw in R.carriage_w] + [1.0 / FT] * len(fw)
    ROAD = road_surface(LN, HW, tol=3 / FT, clip=site, fillet=4 / FT)
    # dual carriageways: two parallel ways with the same name, 6-45 m apart -> fill the median between them
    fills = []
    named = R[R.name.notna() & (R.name.astype(str) != '') & R.highway.isin(['motorway', 'trunk', 'primary', 'secondary'])].reset_index(drop=True)
    for a in range(len(named)):
        for b in range(a + 1, len(named)):
            if named.name[a] != named.name[b]: continue
            la, lb = named.geometry[a], named.geometry[b]
            if la.distance(lb) * FT > 45: continue
            smp = [la.interpolate(t, normalized=True) for t in np.linspace(.1, .9, 9)]
            d = np.array([lb.distance(q) * FT for q in smp])
            inner = np.array([3 / FT < lb.project(q) < lb.length - 3 / FT for q in smp])        # beside lb's middle, not continuing from its end
            ua = np.subtract(la.coords[-1], la.coords[0])[:2]; ub = np.subtract(lb.coords[-1], lb.coords[0])[:2]
            if abs(float(ua @ ub)) / (np.linalg.norm(ua) * np.linalg.norm(ub) + 1e-9) < 0.94: continue   # not parallel (> 20 deg)
            ok = (d > 6) & (d < 45) & inner
            if ok.mean() < .5: continue
            sep = float(np.median(d[ok])) / FT; wa, wb = named.carriage_w[a] / 2 / FT, named.carriage_w[b] / 2 / FT
            both = unary_union([la.buffer(wa, cap_style=2), lb.buffer(wb, cap_style=2)])
            fills.append(both.buffer(sep * .6, cap_style=2, join_style=2).buffer(-sep * .6, cap_style=2, join_style=2).intersection(la.buffer(sep + wa, cap_style=2)).intersection(lb.buffer(sep + wb, cap_style=2)))
    if fills: ROAD = unary_union([ROAD] + fills).intersection(site); print('dual carriageway medians filled:', len(fills))                        # T-branch ends trimmed to the crossing road edge (no protruding caps)
    # ---------- blocks ----------
    BL = [g for g in shapely.get_parts(site.difference(ROAD)) if g.area * FT * FT > 200]
    BLK = gpd.GeoDataFrame(dict(block_id=range(1, len(BL) + 1)), geometry=BL, crs=2136)
    BLK['area_m2'] = (BLK.area * FT * FT).round(0)
    # ---------- plots: partition each block between its buildings ----------
    B['bld_area'] = B.area * FT * FT
    plots = []
    for bid, blk in zip(BLK.block_id, BLK.geometry):
        bb = B[B.representative_point().within(blk)].copy()
        if bb.empty:
            plots.append(dict(block_id=bid, main_bld=None, n_bld=0, ex_use='Vacant / open land', geometry=blk)); continue
        # small outbuildings (< 30 m2) join the nearest larger building within 10 m (same compound)
        big = bb[bb.bld_area >= 30]
        if big.empty: big = bb.nlargest(1, 'bld_area')
        owner = {}
        for i, g in zip(bb.index, bb.geometry):
            if i in big.index: owner[i] = i; continue
            d = big.geometry.distance(g); j = d.idxmin(); owner[i] = j if d.min() < 10 / FT else i
        seeds = sorted(set(owner.values()))
        if len(seeds) == 1:
            i = seeds[0]; plots.append(dict(block_id=bid, main_bld=int(B.bld_id[i]), n_bld=len(bb), ex_use=B.ex_use[i], geometry=blk)); continue
        # Voronoi on points sampled along each compound's building outlines, cells dissolved per compound
        pts, lab = [], []
        for i in seeds:
            geom = unary_union([bb.geometry[k] for k in bb.index if owner[k] == i])
            for part in shapely.get_parts(geom):
                ring = part.exterior
                for t in np.arange(0, ring.length, 6): pts.append(ring.interpolate(t)); lab.append(i)
        cells = shapely.get_parts(shapely.voronoi_polygons(MultiPoint(pts), extend_to=blk.buffer(200)))
        tree = shapely.STRtree(pts); per = {}
        for c in cells:
            k = tree.query(c.representative_point(), predicate='within')
            k = k[0] if len(k) else tree.nearest(c.representative_point()); per.setdefault(lab[k], []).append(c)
        raw = {}
        for i in seeds:
            cell = unary_union(per.get(i, [])).buffer(2).buffer(-2).intersection(blk)
            if not cell.is_empty: raw[i] = max(shapely.get_parts(cell), key=lambda q: q.area)
        # straighten: each shared boundary between two plots becomes one straight line between its end points; rebuild by polygonize
        keys = list(raw); lines = [blk.exterior] + list(blk.interiors)
        for a in range(len(keys)):
            for b_ in range(a + 1, len(keys)):
                sh = raw[keys[a]].boundary.intersection(raw[keys[b_]].boundary.buffer(0.5))
                if sh.is_empty or sh.length < 3: continue
                sh = shapely.line_merge(unary_union([g for g in shapely.get_parts(sh) if g.geom_type == 'LineString']))
                for seg in shapely.get_parts(sh):
                    if seg.geom_type != 'LineString' or seg.length < 3: continue
                    p0, p1 = np.array(seg.coords[0]), np.array(seg.coords[-1]); ext_ = (p1 - p0) / (np.linalg.norm(p1 - p0) + 1e-9) * 3
                    lines.append(shapely.geometry.LineString([tuple(p0 - ext_), tuple(p1 + ext_)]))
        faces = [f for f in shapely.get_parts(shapely.ops.polygonize(unary_union(lines))) if f.representative_point().within(blk)]
        own = {}
        for f in faces:
            hits = [i for i in raw if raw[i].contains(f.representative_point())]
            own.setdefault(hits[0] if hits else max(raw, key=lambda i: raw[i].intersection(f).area), []).append(f)
        for i in raw:
            cell = unary_union(own.get(i, [])) if own.get(i) else raw[i]
            cell = max(shapely.get_parts(cell.buffer(0.3).buffer(-0.3)), key=lambda q: q.area) if not cell.is_empty else raw[i]
            plots.append(dict(block_id=bid, main_bld=int(B.bld_id[i]), n_bld=sum(1 for k in bb.index if owner[k] == i), ex_use=B.ex_use[i], geometry=cell))
    PL = gpd.GeoDataFrame(plots, crs=2136); PL = PL[PL.area * FT * FT > 20].reset_index(drop=True)
    PL['plot_id'] = [f'{b}-{k + 1}' for b, k in zip(PL.block_id, PL.groupby('block_id').cumcount())]
    PL['area_m2'] = (PL.area * FT * FT).round(0); PL['area_ac'] = (PL.area / 43560).round(3)
    q = [list(g.minimum_rotated_rectangle.exterior.coords) for g in PL.geometry]
    PL['frontage_m'] = [round(min(np.hypot(*np.subtract(c[0], c[1])), np.hypot(*np.subtract(c[1], c[2]))) * FT, 1) for c in q]
    PL['depth_m'] = [round(max(np.hypot(*np.subtract(c[0], c[1])), np.hypot(*np.subtract(c[1], c[2]))) * FT, 1) for c in q]
    PL['coverage'] = [round(B[B.representative_point().within(g)].area.sum() / g.area, 2) for g in PL.geometry]
    BLK['n_plots'] = BLK.block_id.map(PL.groupby('block_id').size()).fillna(0).astype(int)
    BLK['coverage'] = [round(B[B.representative_point().within(g)].area.sum() / g.area, 2) for g in BLK.geometry]
    BLK.to_file(D + PFX + 'Blocks_existing.shp'); PL[['plot_id', 'block_id', 'ex_use', 'n_bld', 'main_bld', 'area_m2', 'area_ac', 'frontage_m', 'depth_m', 'coverage', 'geometry']].to_file(D + PFX + 'Plots_existing.shp')
    gpd.GeoDataFrame(geometry=[ROAD], crs=2136).to_file(D + PFX + 'Road_surface.shp')
    try:
        if split_file(D + PFX + 'Road_surface.shp', D + PFX + 'Roads_existing.shp', backup=False): print('road surface: one polygon per road', flush=True)
    except Exception as ex: print('road surface left merged:', str(ex)[:100], flush=True)
    print(f'blocks {len(BLK)} (median {BLK.area_m2.median():.0f} m2) | plots {len(PL)} (median {PL.area_m2.median():.0f} m2, {PL.frontage_m.median():.1f} x {PL.depth_m.median():.1f} m) | median plot coverage {PL.coverage.median()}')
    print(PL.ex_use.value_counts().to_dict())

def st_plots(ctx):
    """Existing plots by the halving rule (guide section 4); profile from ctx."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME, PROF = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME'], ctx['PROF']
    """Existing plots v5 (hybrid): regular blocks = v3 rows + square DP cuts; irregular / curved blocks = rows by nearest frontage
    piece (dense Voronoi, clean bisectors), cuts normal to the curved frontage by DP."""
    """Existing plots v3: rows along each block's long frontages (split at the block centreline), plot lines square to the road,
    placed by dynamic programming to cut as little building as possible (bonus where a wall runs), frontages 12-25 m."""
    import numpy as np, geopandas as gpd, pandas as pd, shapely, math
    from shapely.geometry import Point, Polygon, LineString, MultiPoint
    from shapely.ops import unary_union, split
    from shapely import affinity
    D = D; FT = 0.3048
    BLK = gpd.read_file(D + PFX + 'Blocks_existing.shp'); B = gpd.read_file(D + PFX + 'Existing_land_use_buildings.shp'); W = gpd.read_file(D + PFX + 'Walls_final.shp')
    BU_all = B.geometry.values
    BIG_SRC = [g for g, s_ in zip(B.geometry, B.src) if not str(s_).startswith('OSM/Microsoft')]      # only image-confirmed outlines count as one big building
    import os
    TB = gpd.read_file(D + PFX + 'Tree_belt_raw.shp').union_all().buffer(12 / FT).buffer(-10 / FT).simplify(3 / FT) if os.path.exists(D + PFX + 'Tree_belt_raw.shp') else Point(0, 0).buffer(0.001)            # existing tree belt / drain corridor: its own land use
    TB_GDF = gpd.GeoDataFrame(dict(ex_use=['Tree belt / drain corridor']), geometry=[TB.intersection(BLK.union_all())], crs=2136)
    unit = lambda v: np.asarray(v, float) / (np.linalg.norm(v) + 1e-12)
    WMIN, WMAX, STEP = float(ctx.get('wmin_m') or PROF['wmin']) / FT, float(ctx.get('wmax_m') or PROF['wmax']) / FT, 1 / FT
    REDO = [int(x) for x in (ctx.get('redo_blocks') or [])]
    if REDO: BLK = BLK[BLK.block_id.isin(REDO)].reset_index(drop=True); print(f'   re-demarcating blocks {REDO}', flush=True)
    WT = shapely.STRtree(list(W.geometry)) if len(W) else None
    def split_cost(ln, BUb, off):
        """cost of a rear (row) line: building length it cuts, minus walls / fences running along it (seen on the image), mild pull to the middle"""
        if ctx.get('split') == 'middle': return abs(off)
        c = (ln.intersection(BUb).length if BUb is not None else 0) + abs(off) * 0.05
        if WT is not None and not ln.is_empty:
            z = ln.buffer(1.5 / FT); parts = [g for g in shapely.get_parts(ln) if g.geom_type == 'LineString']
            if parts:
                d = unit(np.subtract(parts[0].coords[-1], parts[0].coords[0])[:2])
                for k in WT.query(z):
                    w = W.geometry.iloc[k]; dw = unit(np.subtract(w.coords[-1], w.coords[0])[:2])
                    if abs(float(d @ dw)) > 0.9: c -= 1.0 * w.intersection(z).length
        return c
    def save_plots(PL):
        if REDO and os.path.exists(D + PFX + 'Plots_existing.shp'):
            old = gpd.read_file(D + PFX + 'Plots_existing.shp'); old = old[~old.block_id.isin(REDO)]
            PL = gpd.GeoDataFrame(pd.concat([old, PL], ignore_index=True), geometry='geometry', crs=2136)
        PL.to_file(D + PFX + 'Plots_existing.shp')
    def dp_cuts(row, o, u, n, walls):
        """best cut positions along u for this row polygon"""
        pr = (np.array(row.exterior.coords)[:, :2] - o) @ u; lo, hi = float(pr.min()), float(pr.max())
        if hi - lo < 1.6 * WMIN: return []
        S = np.arange(lo + WMIN * 0.75, hi - WMIN * 0.75, STEP)
        if len(S) == 0: return []
        bl = [g for g in BU_all if g.intersects(row)]; BU = unary_union(bl) if bl else None
        cost = []
        for s in S:
            ln = LineString([tuple(o + u * s - n * 2000), tuple(o + u * s + n * 2000)]).intersection(row)
            c = ln.intersection(BU).length if (BU is not None and not ln.is_empty) else 0.0
            if any(abs(w - s) < 1.5 / FT for w in walls): c -= 15
            cost.append(c)
        cost = np.array(cost)
        def pen(w):
            return 0.0 if WMIN <= w <= WMAX else (abs(w - (WMIN if w < WMIN else WMAX)) * 3)
        N = len(S); best = np.full(N, np.inf); prev = np.full(N, -1)
        for i in range(N):
            best[i] = cost[i] + pen(S[i] - lo)
            for j in range(i):
                w = S[i] - S[j]
                if w < WMIN * 0.75 or w > WMAX * 1.6: continue
                v = best[j] + cost[i] + pen(w)
                if v < best[i]: best[i] = v; prev[i] = j
        fin = [best[i] + pen(hi - S[i]) for i in range(N)]
        if not fin: return []
        i = int(np.argmin(fin)); out = []
        if hi - lo <= WMAX * 1.3 and min(fin) > pen(hi - lo): return []          # one plot is better than any cut
        while i >= 0: out.append(S[i]); i = prev[i]
        return sorted(out)
    def walls_along(row, o, u):
        pos = []
        for wg in W[W.intersects(row)].geometry:
            d = unit(np.subtract(wg.coords[-1], wg.coords[0]))
            if abs(float(d @ u)) < 0.35: pos.append(float((np.array(wg.centroid.coords[0])[:2] - o) @ u))
        return pos
    def cut_row(row, o, u, n):
        cuts = dp_cuts(row, o, u, n, walls_along(row, o, u))
        lines = [LineString([tuple(o + u * c - n * 3000), tuple(o + u * c + n * 3000)]) for c in cuts]
        return [g for g in (shapely.get_parts(split(row, unary_union(lines))) if lines else [row]) if g.area * FT * FT > 10]
    def tang(l, s):
        a = np.array(l.interpolate(max(0, s - 3)).coords[0])[:2]; b = np.array(l.interpolate(min(l.length, s + 3)).coords[0])[:2]; return unit(b - a)
    def dp_curve(row, F, inward):
        """cut positions (arclength along frontage F) minimising building cut; plot frontage 12-25 m"""
        L = F.length
        if L < 1.6 * WMIN: return []
        S = np.arange(WMIN * 0.75, L - WMIN * 0.75, STEP)
        if len(S) == 0: return []
        bl = [g for g in BU_all if g.intersects(row)]; BU = unary_union(bl) if bl else None
        wl = [w for w in W[W.intersects(row)].geometry]
        def cutline(s):
            p = np.array(F.interpolate(s).coords[0])[:2]; t = tang(F, s); nn = np.array([-t[1], t[0]]) * inward
            return LineString([tuple(p - nn * 3), tuple(p + nn * 400)])
        cost = []
        for s in S:
            ln = cutline(s).intersection(row); c = ln.intersection(BU).length if (BU is not None and not ln.is_empty) else 0.0
            if any(ln.distance(w) < 1.5 / FT and abs(float(unit(np.subtract(w.coords[-1], w.coords[0])[:2]) @ tang(F, s))) < 0.35 for w in wl): c -= 15
            cost.append(c)
        cost = np.array(cost)
        pen = lambda w: 0.0 if WMIN <= w <= WMAX else abs(w - (WMIN if w < WMIN else WMAX)) * 3
        N = len(S); best = np.full(N, np.inf); prev = np.full(N, -1)
        for i in range(N):
            best[i] = cost[i] + pen(S[i])
            for j in range(i):
                w = S[i] - S[j]
                if WMIN * 0.75 <= w <= WMAX * 1.6:
                    v = best[j] + cost[i] + pen(w)
                    if v < best[i]: best[i] = v; prev[i] = j
        fin = np.array([best[i] + pen(L - S[i]) for i in range(N)])
        if L <= WMAX * 1.3 and fin.min() > pen(L): return []
        i = int(np.argmin(fin)); out = []
        while i >= 0: out.append(S[i]); i = prev[i]
        return [cutline(s) for s in sorted(out)]
    def cut_row_curve(row, F):
        mid = np.array(F.interpolate(F.length / 2).coords[0])[:2]; t = tang(F, F.length / 2); nn = np.array([-t[1], t[0]])
        inward = 1 if row.buffer(0.5).contains(Point(mid + nn * 6)) else -1
        lines = dp_curve(row, F, inward)
        parts = shapely.get_parts(split(row, unary_union(lines))) if lines else [row]
        return [g for g in parts if g.area * FT * FT > 10]
    def frontage_pieces(blk, turn=35):
        c = np.array(blk.exterior.simplify(1.5 / FT).coords)[:-1, :2]; n = len(c)
        ang = []
        for i in range(n):
            v1 = c[i] - c[i - 1]; v2 = c[(i + 1) % n] - c[i]
            ang.append(abs(math.degrees(math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1 @ v2))))
        corners = [i for i in range(n) if ang[i] > turn]
        if len(corners) < 2: return [LineString(list(map(tuple, c)) + [tuple(c[0])])]
        out = []
        for a, b in zip(corners, corners[1:] + [corners[0]]):
            idx = list(range(a, b + 1)) if b > a else list(range(a, n)) + list(range(0, b + 1))
            out.append(LineString([tuple(c[i % n]) for i in idx]))
        return out
    pieces = []
    from scipy import ndimage
    from rasterio import features as rfeat
    from affine import Affine
    DMAX = 30 / FT; RES = 0.5 / FT
    RS0 = gpd.read_file(D + PFX + 'Road_surface.shp').union_all().buffer(3 / FT)
    def rows_by_frontage(blk, core=False, road_only=False):
        """each pixel of the block goes to the nearest frontage piece that reaches it within DMAX (else the nearest);
        rows vectorised, simplified and made to tile the block exactly"""
        fr = [f for f in frontage_pieces(blk, turn=30) if f.length > 8 / FT]
        if road_only: fr = [f for f in fr if f.intersection(RS0).length > 0.6 * f.length]
        if not fr: return []
        x0, y0, x1, y1 = blk.buffer(2 * RES).bounds; W_, H_ = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
        T = Affine(RES, 0, x0, 0, -RES, y1)
        mask = rfeat.rasterize([blk], out_shape=(H_, W_), transform=T).astype(bool)
        D_ = []
        for F in fr:
            m = rfeat.rasterize([F.buffer(RES)], out_shape=(H_, W_), transform=T).astype(bool)
            d = ndimage.distance_transform_edt(~m) * RES; D_.append(np.where(d <= DMAX, d, d + 1e5))
        st = np.stack(D_); lab = np.argmin(st, 0).astype(np.int32)
        if core: lab[st.min(0) > 1e4] = len(fr)
        lab[~mask] = -1
        fr = fr + [None]
        raw = {}
        for geom, v in rfeat.shapes(lab, mask=mask, transform=T):
            raw.setdefault(int(v), []).append(shapely.geometry.shape(geom))
        rows, taken = [], Point(0, 0).buffer(0.01)
        CORE = unary_union(raw.pop(len(fr) - 1, [])).buffer(0).simplify(1 / FT).intersection(blk) if raw.get(len(fr) - 1) else None
        if CORE is not None and CORE.area * FT * FT < 400: raw[-9] = [CORE]; CORE = None
        if CORE is not None: taken = CORE
        for k in sorted(raw, key=lambda k: -(fr[k].length if k >= 0 else 0)):
            if k == -9: continue
            g = unary_union(raw[k]).buffer(0).simplify(1 / FT).intersection(blk).difference(taken)
            for p in shapely.get_parts(g):
                if p.geom_type == 'Polygon' and p.area * FT * FT > 5: rows.append([p, fr[k]])
            taken = taken.union(g)
        rest = blk.difference(taken)
        if raw.get(-9): rest = unary_union([rest, raw[-9][0]])
        ok = [r for r in rows if r[0].distance(r[1]) < 1.5 / FT]; bad = [r[0] for r in rows if r[0].distance(r[1]) >= 1.5 / FT] + list(shapely.get_parts(rest))
        for g in bad:
            if not ok or g.is_empty or g.area * FT * FT < 0.5: continue
            k = max(range(len(ok)), key=lambda k: ok[k][0].buffer(0.5).intersection(g).area); ok[k][0] = unary_union([ok[k][0], g])
        return (ok, CORE) if core else ok
    def do_regular(bid, blk):
        mrr = blk.minimum_rotated_rectangle; q = np.array(mrr.exterior.coords)[:, :2]
        e1, e2 = q[1] - q[0], q[2] - q[1]; L, Wd = (e1, e2) if np.linalg.norm(e1) >= np.linalg.norm(e2) else (e2, e1)
        u = unit(L); n = np.array([-u[1], u[0]]); c = np.array(mrr.centroid.coords[0]); depth = np.linalg.norm(Wd)
        o = c - u * np.linalg.norm(L) / 2
        if ctx.get('rows') == '1' or (ctx.get('rows') != '2' and depth < PROF['single_row'] / FT): rows = [blk]
        else:
            bl = [g for g in BU_all if g.intersects(blk)]; BUb = unary_union(bl) if bl else None; best = (1e18, 0.0)
            for off in np.arange(-0.25 * depth, 0.25 * depth + 1, 1 / FT):
                ln = LineString([tuple(c + n * off - u * 5000), tuple(c + n * off + u * 5000)]).intersection(blk)
                cst = split_cost(ln, BUb, off)
                if cst < best[0]: best = (cst, off)
            rows = [g for g in shapely.get_parts(split(blk, LineString([tuple(c + n * best[1] - u * 5000), tuple(c + n * best[1] + u * 5000)]))) if g.area > 50]
        for rw in rows: pieces.extend((bid, g) for g in cut_row(rw, o, u, n))
    def two_side_rows(blk):
        """halve the block: every point goes to the nearer of its two long opposite frontages (curved mid-line)"""
        fr = sorted([f for f in frontage_pieces(blk) if f.length > 8 / FT], key=lambda f: -f.length)
        if len(fr) < 2: return None
        A = fr[0]; cand = [f for f in fr[1:] if f.distance(A) > 15 / FT]
        if not cand: return None
        Bf = cand[0]
        x0, y0, x1, y1 = blk.buffer(2 * RES).bounds; W_, H_ = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
        T = Affine(RES, 0, x0, 0, -RES, y1); mask = rfeat.rasterize([blk], out_shape=(H_, W_), transform=T).astype(bool)
        d = [ndimage.distance_transform_edt(~rfeat.rasterize([F.buffer(RES)], out_shape=(H_, W_), transform=T).astype(bool)) for F in (A, Bf)]
        lab = (d[1] < d[0]).astype(np.int32); lab[~mask] = -1
        raw = {}
        for geom, v in rfeat.shapes(lab, mask=mask, transform=T): raw.setdefault(int(v), []).append(shapely.geometry.shape(geom))
        rA = unary_union(raw.get(0, [])).buffer(0).simplify(1 / FT).intersection(blk); rB = blk.difference(rA)
        rows = []
        for rg, F in ((rA, A), (rB, Bf)):
            for g in shapely.get_parts(rg):
                if g.geom_type == 'Polygon' and g.area * FT * FT > 5: rows.append([g, F])
        ok = [r for r in rows if r[0].distance(r[1]) < 1.5 / FT]
        for g in [r[0] for r in rows if r[0].distance(r[1]) >= 1.5 / FT]:
            if ok: k = max(range(len(ok)), key=lambda k: ok[k][0].buffer(0.5).intersection(g).area); ok[k][0] = unary_union([ok[k][0], g])
        return ok
    def bwidth(g):
        m = g.minimum_rotated_rectangle; q = np.array(m.exterior.coords)[:, :2]
        if g.area / m.area >= 0.72: return min(np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[1]))
        h = g.exterior.simplify(6 / FT).length / 2; return (h - math.sqrt(max(h * h - 4 * g.area, 0))) / 2      # equal-area/perimeter rectangle width (curved blocks too)
    def do_block(bid, blk):
        mrr = blk.minimum_rotated_rectangle; q = np.array(mrr.exterior.coords)[:, :2]
        fill = blk.area / mrr.area
        width = bwidth(blk)
        if fill >= 0.72: do_regular(bid, blk); return                        # straight block: halve along its length (deep halves are halved again later)
        rows = None if ctx.get('rows') == '1' else (two_side_rows(blk) if (width >= 40 / FT or ctx.get('rows') == '2') else None)             # curved / irregular block: halve between the two long frontages
        if not rows: rows = [[blk, max(frontage_pieces(blk), key=lambda f: f.length)]] if (width < 40 / FT or ctx.get('rows') == '1') else rows_by_frontage(blk)
        if not rows: pieces.append((bid, blk)); return
        for rw, F in rows:
            for part in shapely.get_parts(rw.buffer(0.2).buffer(-0.2)):
                if part.area * FT * FT > 10: pieces.extend((bid, g) for g in cut_row_curve(part, F))
    SITES = gpd.read_file(WORK + 'osm_sites.gpkg') if os.path.exists(WORK + 'osm_sites.gpkg') else None
    SITE_PIECES = []                                                            # (block id, geometry, use, name)
    if SITES is not None and len(SITES):
        SU_ = unary_union([g.buffer(0) for g in SITES.geometry])
        newb = []
        for bid_, g_ in zip(BLK.block_id, BLK.geometry):
            g_ = shapely.force_2d(g_).buffer(0)
            taken_ = None
            for _, srow in SITES.assign(_a=SITES.area).sort_values('_a', ascending=False).iterrows():     # larger sites first; overlaps counted once
                sg_ = srow.geometry.buffer(0) if taken_ is None else srow.geometry.buffer(0).difference(taken_)
                part = g_.intersection(sg_); taken_ = sg_ if taken_ is None else taken_.union(sg_)
                for q_ in shapely.get_parts(part):
                    if q_.geom_type == 'Polygon' and q_.area * FT * FT > 300: SITE_PIECES.append((bid_, q_, srow['use'], srow.get('name')))
            newb.append(g_.difference(SU_) if any(sp[0] == bid_ for sp in SITE_PIECES) else g_)
        BLK = BLK.copy(); BLK['geometry'] = newb
        print(f'   service / utility sites kept whole: {len(SITE_PIECES)}', flush=True)
    for bid, blk0 in zip(BLK.block_id, BLK.geometry):
        for blk in [g for g in shapely.get_parts(shapely.force_2d(blk0).buffer(0).difference(TB)) if g.area * FT * FT > 150]: do_block(bid, blk)
    def recut(bid, g):
        q = np.array(g.minimum_rotated_rectangle.exterior.coords)[:, :2]; e1, e2 = q[1] - q[0], q[2] - q[1]
        Lv = e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2; dep = np.linalg.norm(Lv); ul = unit(Lv)
        big = [b for b in BIG_SRC if b.intersects(g) and b.area * FT * FT > 500 and b.intersection(g).area > 0.5 * b.area]
        if g.area * FT * FT < PROF['recut_area'] or dep < PROF['recut_depth'] / FT or big: return [(bid, g)]
        fr = [f for f in frontage_pieces(g, turn=30) if f.length > 15 / FT and f.intersection(RS0).length > 0.6 * f.length]
        if not fr: return [(bid, g)]
        par = lambda f: abs(float(unit(np.subtract(f.coords[-1], f.coords[0])[:2]) @ ul))
        F = max(fr, key=lambda f: (par(f) > 0.8, f.length))                   # the side street the wedge runs along
        if par(F) < 0.8: return [(bid, g)]
        out = cut_row_curve(g, F)
        return [(bid, x) for x in out] if len(out) > 1 else [(bid, g)]
    n0 = len(pieces); pieces = [x for bid, g in pieces for x in recut(bid, g)]; print('recut: pieces', n0, '->', len(pieces))
    def halve_deep(bid, g, depth_max=PROF['halve_depth'] / FT):
        q = np.array(g.minimum_rotated_rectangle.exterior.coords)[:, :2]; e1, e2 = q[1] - q[0], q[2] - q[1]
        Lv = e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2; dep = np.linalg.norm(Lv)
        big = [b for b in BIG_SRC if b.intersects(g) and b.area * FT * FT > 500 and b.intersection(g).area > 0.5 * b.area]
        if dep <= depth_max: return [(bid, g)]
        BIG = unary_union(big) if big else None
        ul = unit(Lv); nl = np.array([-ul[1], ul[0]]); c = np.array(g.minimum_rotated_rectangle.centroid.coords[0])
        bl = [b for b in BU_all if b.intersects(g)]; BU = unary_union(bl) if bl else None; best = (1e18, 0.0)
        for off in np.arange(-0.2 * dep, 0.2 * dep + 1, 1 / FT):
            ln = LineString([tuple(c + ul * off - nl * 3000), tuple(c + ul * off + nl * 3000)]).intersection(g)
            cst = (ln.intersection(BU).length if BU is not None else 0) + abs(off) * 0.05 + (1e6 if BIG is not None and ln.intersects(BIG) else 0)
            if cst < best[0]: best = (cst, off)
        if best[0] >= 1e6: return [(bid, g)]
        parts = [x for x in shapely.get_parts(split(g, LineString([tuple(c + ul * best[1] - nl * 3000), tuple(c + ul * best[1] + nl * 3000)]))) if x.area * FT * FT > 10]
        return [y for x in parts for y in halve_deep(bid, x, depth_max)] if len(parts) > 1 else [(bid, g)]
    n0 = len(pieces); pieces = [x for bid, g in pieces for x in halve_deep(bid, g)]; print('halve deep: pieces', n0, '->', len(pieces))
    pieces += [(sp[0], sp[1]) for sp in SITE_PIECES]
    PL = gpd.GeoDataFrame(dict(block_id=[p[0] for p in pieces]), geometry=[p[1] for p in pieces], crs=2136)
    # pieces with no building and small, or corner triangles: join the neighbour sharing the longest edge
    for _ in range(3):
        PL['has_b'] = [any(g.representative_point().within(x) for g in BU_all if g.intersects(x)) for x in PL.geometry]
        sm = PL.index[(PL.area * FT * FT < 80) | ((~PL.has_b) & (PL.area * FT * FT < 200))]
        if not len(sm): break
        for i in sm:
            if PL.geometry[i] is None: continue
            nb = PL[(PL.index != i) & (PL.block_id == PL.block_id[i]) & PL.geometry.notna()]; nb = nb[nb.geometry.intersection(PL.geometry[i].buffer(0.5)).area > 1]
            if nb.empty: continue
            j = max(nb.index, key=lambda j: nb.geometry[j].intersection(PL.geometry[i].buffer(0.5)).area)
            PL.at[j, 'geometry'] = unary_union([PL.geometry[j], PL.geometry[i]]).buffer(0.2).buffer(-0.2); PL.at[i, 'geometry'] = None
        PL = PL[PL.geometry.notna()].reset_index(drop=True)
    PL['geometry'] = [max(shapely.get_parts(g), key=lambda q: q.area) for g in PL.geometry]
    PL = PL[(PL.geometry.geom_type == 'Polygon') & (PL.area * FT * FT > 10)].reset_index(drop=True)
    # land use: the largest building whose centre is in the plot
    uses, mbs, nbs, guess, conf = [], [], [], [], []
    UC = B.use_conf if 'use_conf' in B else pd.Series('confirmed', index=B.index)
    for g in PL.geometry:
        inb = B[B.representative_point().within(g)]
        if len(inb):
            tg = inb[inb.use_source.astype(str).str.startswith(('OSM tag', 'building database')) & (inb.ex_use != 'Residential')]
            j = tg.area.idxmax() if len(tg) else inb.area.idxmax(); mbs.append(int(B.bld_id[j])); nbs.append(len(inb)); guess.append(B.ex_use[j])
            if UC[j] == 'confirmed': uses.append(B.ex_use[j]); conf.append('confirmed')
            else: uses.append('Unconfirmed (verify)'); conf.append('to confirm')
        else: uses.append('Open / yard (no building)'); mbs.append(None); nbs.append(0); guess.append(''); conf.append('confirmed')
    PL['ex_use'], PL['main_bld'], PL['n_bld'], PL['use_guess'], PL['use_conf'] = uses, mbs, nbs, guess, conf
    # a site carved from OSM keeps its own use (school, hospital, police ...)
    for sp in SITE_PIECES:
        hit = PL.index[[g.representative_point().within(sp[1].buffer(1)) and g.intersection(sp[1]).area > 0.8 * g.area for g in PL.geometry]]
        for i_ in hit: PL.at[i_, 'ex_use'] = sp[2]; PL.at[i_, 'use_conf'] = 'confirmed'; PL.at[i_, 'use_guess'] = sp[2]
    # services and utilities are ONE plot: touching plots of the same service use in a block are merged
    SERVICE = {'Education', 'Health', 'Civic', 'Religious', 'Religious / assembly', 'Transport terminal', 'Market', 'Utility', 'Recreation', 'Institutional / large commercial (verify)'}
    rows_ = []; drop_ = set()
    for (bid_, use_), grp_ in PL[PL.ex_use.isin(SERVICE)].groupby(['block_id', 'ex_use']):
        if len(grp_) < 2: continue
        comps = shapely.get_parts(unary_union([g.buffer(0.5) for g in grp_.geometry]))
        for c_ in comps:
            mem = [i_ for i_ in grp_.index if grp_.geometry[i_].intersects(c_)]
            if len(mem) < 2: continue
            g_ = unary_union([PL.geometry[i_] for i_ in mem]).buffer(0.3).buffer(-0.3)
            keep_ = max(mem, key=lambda i_: PL.geometry[i_].area); PL.at[keep_, 'geometry'] = max(shapely.get_parts(g_), key=lambda x: x.area) if g_.geom_type != 'Polygon' else g_
            PL.at[keep_, 'n_bld'] = int(sum(PL.n_bld[i_] for i_ in mem)); drop_.update(i_ for i_ in mem if i_ != keep_)
    if drop_: PL = PL.drop(index=list(drop_)).reset_index(drop=True); print(f'   service plots merged into whole sites: {len(drop_)} plot lines removed', flush=True)
    RS = gpd.read_file(D + PFX + 'Road_surface.shp').union_all().buffer(2 / FT)
    SB = gpd.read_file(SITE_KML).to_crs(2136).geometry.iloc[0].boundary.buffer(3 / FT)
    PL['access'] = ['Road frontage' if g.intersects(RS) else ('Site edge (road outside site)' if g.intersection(SB).area * FT * FT > 30 else 'Interior (access lane not mapped - verify)') for g in PL.geometry]
    PL['plot_id'] = [f'{b}-{k + 1}' for b, k in zip(PL.block_id, PL.groupby('block_id').cumcount())]
    PL['area_m2'] = (PL.area * FT * FT).round(0); qq = [list(g.minimum_rotated_rectangle.exterior.coords) for g in PL.geometry]
    PL['frontage_m'] = [round(min(math.dist(c[0], c[1]), math.dist(c[1], c[2])) * FT, 1) for c in qq]; PL['depth_m'] = [round(max(math.dist(c[0], c[1]), math.dist(c[1], c[2])) * FT, 1) for c in qq]
    PL['coverage'] = [round(B[B.representative_point().within(g)].area.sum() / g.area, 2) for g in PL.geometry]
    PL = PL[['plot_id', 'block_id', 'access', 'ex_use', 'use_conf', 'use_guess', 'n_bld', 'main_bld', 'area_m2', 'frontage_m', 'depth_m', 'coverage', 'geometry']]; save_plots(PL); TB_GDF.to_file(D + PFX + 'Tree_belt_existing.shp')
    ov = gpd.overlay(PL[['plot_id', 'geometry']], PL[['plot_id', 'geometry']], how='intersection'); ov = ov[ov.plot_id_1 != ov.plot_id_2]
    cut = sum(1 for g in B.geometry if g.area * FT * FT > 25 and PL.intersects(g).sum() > 1 and PL[PL.intersects(g)].intersection(g).area.max() < 0.85 * g.area)
    print(f'plots {len(PL)} | median {PL.area_m2.median():.0f} m2 ({PL.frontage_m.median():.1f} x {PL.depth_m.median():.1f} m) | blocks covered {(PL.area.sum() + TB_GDF.area.sum()) / BLK.area.sum() * 100:.1f}% | overlap {ov.area.sum() * FT * FT / 2:.0f} m2 | buildings cut by plot lines {cut} of {len(B)}')
    print(PL.ex_use.value_counts().to_dict())
    d = PL.depth_m; f = PL.frontage_m
    print(PL.access.value_counts().to_dict()); print('block widths m', {int(i): round(bwidth(max(shapely.get_parts(shapely.force_2d(g)), key=lambda x: x.area)) * FT) for i, g in zip(BLK.block_id, BLK.geometry) if not g.is_empty}); print('depth>60:', int((d > 60).sum()), '| both >30/45:', int(((f > 30) & (d > 45)).sum()), '| median frontage', f.median())

def st_map(ctx):
    """Existing land use map (legend outside the frame) and tables."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    import geopandas as gpd, numpy as np, pandas as pd
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    D = D; FT = 0.3048
    PL = gpd.read_file(D + PFX + 'Plots_existing.shp').to_crs(3857); BL = gpd.read_file(D + PFX + 'Blocks_existing.shp').to_crs(3857); RS = gpd.read_file(D + PFX + 'Road_surface.shp').to_crs(3857)
    B = gpd.read_file(D + PFX + 'Existing_land_use_buildings.shp').to_crs(3857); TB = gpd.read_file(D + PFX + 'Tree_belt_existing.shp').to_crs(3857); site = gpd.read_file(SITE_KML).to_crs(3857)
    COL = {'Residential': '#f6e27f', 'Mixed use (shop + residence)': '#f4a259', 'Commercial / mixed use': '#e86a5a', 'Commercial': '#d62828', 'Commercial (hotel)': '#a23b72', 'Commercial (fuel)': '#6c757d',
           'Office': '#7b2cbf', 'Health': '#ff70a6', 'Education': '#1e88e5', 'Religious': '#8d6e63', 'Civic': '#00acc1', 'Market': '#ff8f00', 'Transport terminal': '#455a64', 'Institutional / large commercial (verify)': '#43a047', 'Open / yard (no building)': '#e8f5e9'}
    fig, ax = plt.subplots(figsize=(19, 19)); ax.set_facecolor('white')
    COUNTS = luspa_draw(ax, PL, 'ex_use', EXIST_LUSPA, lw=.7)
    INT = PL[PL.access.str.startswith('Interior')]; INT.plot(ax=ax, color='none', ec='#555', lw=0, hatch='///')
    TB.plot(ax=ax, color=LUSPA['CA'][1]); RS.plot(ax=ax, color='#c8c8c8'); B.plot(ax=ax, color='none', ec='#1f5fd1', lw=.45); BL.boundary.plot(ax=ax, color='black', lw=1.1); site.boundary.plot(ax=ax, color='red', lw=2.2)
    for g, i in zip(BL.geometry, BL.block_id): c = g.representative_point(); ax.text(c.x, c.y, str(i), fontsize=8, ha='center', weight='bold', color='navy', bbox=dict(fc='white', ec='none', alpha=.6, pad=.5))
    x0, y0, x1, y1 = site.total_bounds; ax.set_xlim(x0 - 20, x1 + 20); ax.set_ylim(y0 - 20, y1 + 20); ax.set_xticks([]); ax.set_yticks([])
    tb_ac = TB.to_crs(2136).area.sum() / 43560
    ax.legend(handles=luspa_handles(COUNTS, lambda code, n: f' ({n} plots)') +
              ([Patch(color=LUSPA['CA'][1], label=f'CA  Conservation: tree belt / drain corridor ({tb_ac:.1f} ac)')] if tb_ac > 0.05 else []) + [Patch(color='#c8c8c8', label='Roads'),
               Patch(fc='white', ec='#555', hatch='///', label=f'Interior plot: access lane not mapped, verify ({len(INT)})'),
               Patch(fc='none', ec='black', label='Block (number)'), Patch(fc='none', ec='#1f5fd1', lw=1.5, label='Building footprint'), Patch(fc='none', ec='#222', label='Plot boundary')], loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=11, framealpha=.95, borderaxespad=0)
    ax.set_title(TITLE + f' - existing land use (LUSPA colour codes): {len(BL)} blocks, {len(PL)} plots', fontsize=16)
    try: plt.savefig(D + PFX + 'Existing_land_use_map.png', bbox_inches='tight', dpi=70)
    except OSError: plt.savefig(D + PFX + 'Existing_land_use_map.png'.replace('.png', '_v2.png'), bbox_inches='tight', dpi=70); print('map file open elsewhere - saved as _v2')
    P2 = gpd.read_file(D + PFX + 'Plots_existing.shp'); site2 = gpd.read_file(SITE_KML).to_crs(2136).geometry.iloc[0]
    t = P2.groupby('ex_use').agg(plots=('plot_id', 'size'), area_m2=('area_m2', 'sum')).sort_values('area_m2', ascending=False)
    t.loc['Tree belt / drain corridor'] = [0, round(TB.to_crs(2136).area.sum() * FT * FT)]; t.loc['Roads'] = [0, round(gpd.read_file(D + PFX + 'Road_surface.shp').area.sum() * FT * FT)]
    t['area_ha'] = (t.area_m2 / 1e4).round(2); t['share_%'] = (t.area_m2 / (site2.area * FT * FT) * 100).round(1)
    with pd.ExcelWriter(D + PFX + 'Existing_land_use_tables.xlsx') as xw:
        t.reset_index().rename(columns={'ex_use': 'land use'}).to_excel(xw, sheet_name='land use areas', index=False)
        gpd.read_file(D + PFX + 'Blocks_existing.shp').drop(columns='geometry').to_excel(xw, sheet_name='blocks', index=False)
        P2.drop(columns='geometry').to_excel(xw, sheet_name='plots', index=False)
    print(t.to_string())

def st_footpaths(ctx):
    """OPTIONAL TRIAL: footpaths from the open space between buildings (not reliable in dense cores)."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    """the site: map footpaths from the open space between buildings.
    Free space = site - buildings - walls - mapped road surface. Its skeleton (centre line) is traced into a network; spurs that
    poke into yards are pruned; only corridors >= MIN_W wide that link to the road network are kept."""
    import numpy as np, geopandas as gpd, shapely, networkx as nx, math
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union, linemerge
    from rasterio import features as rfeat
    from affine import Affine
    from scipy import ndimage
    from skimage.morphology import skeletonize
    D = D; FT = 0.3048
    MIN_W = ctx.get('fp_min_w', 0.6) / FT
    SPUR = 10 / FT            # dead-end branches shorter than this are yard intrusions, not paths
    site = gpd.read_file(SITE_KML).to_crs(2136).geometry.iloc[0]
    B = gpd.read_file(D + PFX + 'Buildings_final.shp'); W = gpd.read_file(D + PFX + 'Walls_final.shp')
    RS = gpd.read_file(D + PFX + 'Road_surface.shp').union_all()
    OBST = unary_union([g.buffer(0.4 / FT) for g in B.geometry] + [w.buffer(0.25 / FT) for w in W.geometry])        # footprints run slightly small
    area = site.buffer(15 / FT)
    RES = 1.0                 # ft per pixel (0.3 m, the image resolution)
    x0, y0, x1, y1 = area.bounds; Wd, Ht = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
    T = Affine(RES, 0, x0, 0, -RES, y1)
    inside = rfeat.rasterize([area], out_shape=(Ht, Wd), transform=T).astype(bool)
    obst = rfeat.rasterize([g for g in shapely.get_parts(OBST)], out_shape=(Ht, Wd), transform=T).astype(bool)
    road = rfeat.rasterize([RS], out_shape=(Ht, Wd), transform=T).astype(bool)
    free = inside & ~obst & ~road
    import rasterio, cv2
    from rasterio.warp import reproject, Resampling
    from skimage.filters import sato
    src = rasterio.open(WORK + 'img_z19_3857.tif'); gimg = cv2.cvtColor(np.moveaxis(src.read(), 0, -1)[:, :, :3].copy(), cv2.COLOR_RGB2GRAY).astype(np.float32)
    gray = np.zeros((Ht, Wd), np.float32); reproject(gimg, gray, src_transform=src.transform, src_crs=src.crs, dst_transform=T, dst_crs='EPSG:2136', resampling=Resampling.bilinear)
    valley = sato(gray, sigmas=[2, 3, 4, 5], black_ridges=True)                  # dark linear corridors 1-3 m wide
    valley = valley / (np.percentile(valley[inside], 99) + 1e-6)
    shadow = gray < 85
    clear = ndimage.distance_transform_edt(free | road) * RES      # distance to nearest obstacle (roads count as open)
    sk = skeletonize(free) & (clear >= MIN_W / 2)
    # ---------- skeleton pixels -> graph ----------
    ys, xs = np.nonzero(sk); idx = {(y, x): i for i, (y, x) in enumerate(zip(ys, xs))}
    G = nx.Graph()
    for (y, x), i in idx.items():
        G.add_node(i)
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            j = idx.get((y + dy, x + dx))
            if j is not None: G.add_edge(i, j, w=math.hypot(dy, dx) * RES)
    xy = lambda i: (x0 + (xs[i] + 0.5) * RES, y1 - (ys[i] + 0.5) * RES)
    road_near = ndimage.binary_dilation(road, iterations=int(2 / FT / RES))
    touches_road = lambda i: road_near[ys[i], xs[i]]
    # ---------- prune spurs: repeatedly strip short dead ends that don't reach a road ----------
    for _ in range(6):
        removed = 0
        for comp in list(nx.connected_components(G)):
            pass
        ends = [n for n in G.nodes if G.degree(n) == 1 and not touches_road(n)]
        for e in ends:
            if e not in G: continue
            path = [e]; prev, cur = None, e; L = 0.0
            while True:
                nb = [n for n in G.neighbors(cur) if n != prev]
                if len(nb) != 1 or G.degree(cur) > 2 and cur != e: break
                L += G[cur][nb[0]]['w']; prev, cur = cur, nb[0]; path.append(cur)
                if G.degree(cur) != 2 or L > SPUR: break
            if L <= SPUR and G.degree(cur) >= 3: G.remove_nodes_from(path[:-1]); removed += 1
        if not removed: break
    G.remove_nodes_from([n for n in list(G.nodes) if G.degree(n) == 0])
    # keep components that link to the road network
    keep = set()
    for comp in nx.connected_components(G):
        if any(touches_road(n) for n in comp) and len(comp) * RES > 8 / FT: keep |= comp
    G = G.subgraph(keep).copy()
    # ---------- graph -> lines (split at junctions / ends) ----------
    lines = []; seen = set()
    nodes = [n for n in G.nodes if G.degree(n) != 2]
    for s in nodes:
        for nb in G.neighbors(s):
            if (s, nb) in seen: continue
            path = [s, nb]; prev, cur = s, nb
            while G.degree(cur) == 2:
                nxt = [n for n in G.neighbors(cur) if n != prev][0]; prev, cur = cur, nxt; path.append(cur)
            seen.add((path[-1], path[-2])); seen.add((s, nb))
            if len(path) >= 3: lines.append(LineString([xy(i) for i in path]).simplify(1.5 / FT))
    def seg_score(l):
        v, sh = [], []
        for t in np.linspace(0, l.length, max(3, int(l.length / RES))):
            p = l.interpolate(t); c, r = ~T * (p.x, p.y); r, c = int(r), int(c)
            if 0 <= r < Ht and 0 <= c < Wd: v.append(valley[r, c]); sh.append(shadow[r, c])
        return (float(np.mean(v)), float(np.mean(sh))) if v else (0.0, 0.0)
    SG = gpd.GeoDataFrame(geometry=lines, crs=2136); sc = [seg_score(l) for l in SG.geometry]
    SG['valley'] = [a for a, _ in sc]; SG['shadow'] = [b for _, b in sc]; SG['score'] = SG.valley + 0.5 * SG.shadow
    SG.to_file(D + PFX + 'footpath_candidates.shp'); print('candidate segments', len(SG), '| score pct', np.percentile(SG.score, [10, 25, 50, 75, 90]).round(2).tolist())
    import sys
    THR = ctx.get('fp_thr', 0.0)
    VERGE = RS.buffer(5 / FT)
    SG = SG[[l.intersection(VERGE).length < 0.5 * l.length for l in SG.geometry]]           # strips running along a mapped road are verges, not footpaths
    good = SG[SG.score >= THR].geometry.tolist()
    RSb = RS.buffer(2 / FT)
    for _ in range(6):                                                          # drop dangling short pieces that don't reach a road
        U = unary_union(good); ends = []
        out = []
        for l in good:
            a, b = Point(l.coords[0]), Point(l.coords[-1])
            da = a.within(RSb) or sum(1 for m in good if m is not l and m.distance(a) < 0.5) > 0
            db = b.within(RSb) or sum(1 for m in good if m is not l and m.distance(b) < 0.5) > 0
            if (da and db) or l.length > SPUR: out.append(l)
        if len(out) == len(good): break
        good = out
    comps = shapely.get_parts(unary_union(good).buffer(0.3)) if good else []
    good = [l for l in good if any(c.intersects(l) and c.intersects(RSb) for c in comps)]
    P = gpd.GeoDataFrame(geometry=[l for l in shapely.get_parts(linemerge(good)) if l.length > 3 / FT], crs=2136)
    P['geometry'] = P.geometry.difference(RS.buffer(0.5 / FT)); P = P.explode(index_parts=False); P = P[P.length > 3 / FT].reset_index(drop=True)
    P = P[P.intersects(site)]
    # width along each path: twice the median clearance at its vertices
    def width(l):
        v = []
        for t in np.linspace(0, l.length, max(3, int(l.length / 5))):
            p = l.interpolate(t); c, r = ~T * (p.x, p.y)
            if 0 <= int(r) < Ht and 0 <= int(c) < Wd: v.append(clear[int(r), int(c)])
        return round(2 * float(np.median(v)) * FT, 1) if v else np.nan
    P['width_m'] = [width(l) for l in P.geometry]
    P['length_m'] = (P.length * FT).round(1)
    P['class'] = np.where(P.width_m >= 3.0, 'Lane (vehicle access possible)', np.where(P.width_m >= 1.8, 'Footpath', np.where(P.width_m >= 1.0, 'Narrow footpath (1-1.8 m)', 'Alley under eaves (< 1 m between roofs)')))
    P['path_id'] = range(1, len(P) + 1)
    P[['path_id', 'class', 'width_m', 'length_m', 'geometry']].to_file(D + PFX + 'Footpaths_TRIAL_not_reliable.shp')
    print(f'footpaths {len(P)} | total {P.length_m.sum():.0f} m | by class', P.groupby('class').length_m.sum().round(0).to_dict(), '| median width', P.width_m.median())

    import geopandas as gpd, rasterio, numpy as np
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    D = D
    r = rasterio.open(WORK + 'img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3]; b = r.bounds
    P = gpd.read_file(D + PFX + 'Footpaths_TRIAL_not_reliable.shp').to_crs(3857); C = gpd.read_file(D + PFX + 'footpath_candidates.shp').to_crs(3857)
    RS = gpd.read_file(D + PFX + 'Road_surface.shp').to_crs(3857); S = gpd.read_file(SITE_KML).to_crs(3857); c = S.geometry.iloc[0].centroid
    fig, axs = plt.subplots(1, 3, figsize=(33, 11))
    for k, ax in enumerate(axs):
        ax.imshow(img, extent=(b.left, b.right, b.bottom, b.top)); RS.boundary.plot(ax=ax, color='white', lw=1)
        if k == 0:
            C.plot(ax=ax, column='score', cmap='RdYlGn', vmin=0.1, vmax=0.7, lw=2, legend=True); ax.set_title('candidate segments by score (green = strong path evidence)', fontsize=14)
        else:
            P.plot(ax=ax, column='class', lw=3, legend=True, cmap='cool'); ax.set_title('kept footpaths', fontsize=14)
        if k < 2: ax.set_xlim(c.x - 80, c.x + 80); ax.set_ylim(c.y - 80, c.y + 80)
        else: x0, y0, x1, y1 = S.total_bounds; ax.set_xlim(x0 - 10, x1 + 10); ax.set_ylim(y0 - 10, y1 + 10); S.boundary.plot(ax=ax, color='orange', lw=2)
        ax.set_xticks([]); ax.set_yticks([])
    plt.savefig(D + PFX + 'footpaths_preview.png', bbox_inches='tight', dpi=50)

def st_proposals(ctx):
    """OPTIONAL: upgrading proposals (only when proposals are asked for)."""
    D, PFX, WORK, SITE_KML, SAM_CKPT, TITLE, NAME = ctx['D'], ctx['PFX'], ctx['WORK'], ctx['SITE_KML'], ctx['SAM_CKPT'], ctx['TITLE'], ctx['NAME']
    """the site upgrading plan - proposals: mixed-use corridors, drainage greenway, pocket parks, pinch-point actions, refuse points, facility gaps."""
    import numpy as np, geopandas as gpd, pandas as pd, rasterio, cv2, shapely, json
    from shapely.geometry import Polygon, Point
    from shapely.ops import unary_union, transform as shp_transform
    D = D; FT = 0.3048
    site = gpd.read_file(SITE_KML).to_crs(2136).geometry.iloc[0]
    B = gpd.read_file(D + PFX + 'Existing_land_use_buildings.shp'); R = gpd.read_file(D + PFX + 'Roads_existing.shp'); PP = gpd.read_file(D + PFX + 'Road_pinch_points.shp')
    V = gpd.read_file(D + PFX + 'Vacant_open_land.shp'); CWY = gpd.read_file(D + PFX + 'Carriageways.shp').union_all()
    POP = int(round(B[B.ex_use == 'Residential'].area.sum() * FT * FT * 1.5 / 60 * 3.4, -2))                                                                  # provisional (1.5 storeys, 60 m2 per household, 3.4 persons)
    # ---------- 1. mixed-use corridors: building frontage band along the primary / secondary roads ----------
    maj = R[R.highway.isin(['primary', 'secondary'])]
    corr = unary_union([g.buffer((cw / 2 + 30) / FT) for g, cw in zip(maj.geometry, maj.carriage_w)]).intersection(site).difference(CWY)
    MU = gpd.GeoDataFrame(dict(zone=['Mixed-use corridor (commercial ground floor, residential above)']), geometry=[corr], crs=2136)
    # ---------- 2. drainage greenway: the continuous tree corridor through the site ----------
    r = rasterio.open(WORK + 'img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); T = r.transform
    Rc, Gc, Bc = [img[:, :, k].astype(float) for k in range(3)]; br = img.mean(2)
    tree = ((Gc - (Rc + Bc) / 2) > 16) & (br < 120)
    tree = cv2.morphologyEx(tree.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)); tree = cv2.morphologyEx(tree, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    cs, _ = cv2.findContours(tree, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); gw = []
    for c in cs:
        if len(c) < 10: continue
        p = Polygon([T * tuple(pt) for pt in c[:, 0, :].astype(float)]).buffer(0)
        if p.is_empty: continue
        q = list(p.minimum_rotated_rectangle.exterior.coords); a_, b_ = sorted([np.hypot(*np.subtract(q[0], q[1])), np.hypot(*np.subtract(q[1], q[2]))])
        if p.area > 2500 and b_ / max(a_, 1) > 3: gw.append(p.simplify(2))      # long, continuous tree belt (> 2,500 m2, at least 3:1)
    G = gpd.GeoDataFrame(geometry=gw, crs=3857).to_crs(2136); G['geometry'] = G.intersection(site); G = G[G.area * FT * FT > 1500]
    G['zone'] = 'Drainage greenway / linear park (protect trees, keep 15 m clear of the drain)'; G['area_m2'] = (G.area * FT * FT).round(0)
    # ---------- 3. pocket parks on vacant land ----------
    PK = V.copy(); PK['zone'] = 'Pocket park / children\'s play (on vacant land)'
    # ---------- 4. pinch points: actions ----------
    # pinch points and actions come from pinch_v2.py (realigned centrelines)
    # ---------- 5. refuse / sanitary collection points: none mapped; one per ~2,500 people, on the widest reserves at junctions, every home within 300 m ----------
    n_ref = int(np.ceil(POP / 2500)); cand = []
    for g, rw, cw in zip(R.geometry, R.reserve_m, R.carriage_w):
        if np.isnan(rw) or rw - cw < 5 or not g.intersects(site): continue           # needs >= 2.5 m of verge each side
        for s in np.arange(30, g.length - 30, 60):
            pt = g.interpolate(s)
            if pt.within(site.buffer(-30)): cand.append(pt)
    homes = list(B[B.ex_use == 'Residential'].geometry.centroid); chosen = []
    for _ in range(n_ref):
        best = None
        for c in cand:
            if any(c.distance(x) < 250 / FT for x in chosen): continue
            cov = sum(1 for h in homes[::5] if min([c.distance(h)] + [x.distance(h) for x in chosen]) < 300 / FT)
            if best is None or cov > best[0]: best = (cov, c)
        if best: chosen.append(best[1])
    RF = gpd.GeoDataFrame(dict(facility=['Refuse / sanitary collection point (skip pad in the road verge)'] * len(chosen)), geometry=chosen, crs=2136)
    # ---------- 6. facility gaps (provisional: OSM under-records facilities) ----------
    cnt = B.ex_use.value_counts()
    std = [('Basic school (primary + JHS)', 'Education', 5000, 'one per neighbourhood of ~5,000 (LUSPA neighbourhood list)'),
           ('Health post / clinic', 'Health', 5000, 'health post serves up to 5,000 (LUSPA)'),
           ('Place of worship', 'Religious', 1150, 'learned rate ~1 per 160 plots (~1,150 people)'),
           ('Market / shopping centre', 'Market', 5000, 'neighbourhood shopping centre or market per neighbourhood (LUSPA)'),
           ('Public open space / play', 'Open space', 1950, 'learned rate ~1 per 270 plots (~1,950 people)'),
           ('Refuse / sanitary point', 'Refuse', 2500, 'learned S.A rate ~1 per 2,500 people; Guidelines: within 500 m')]
    have = {'Education': int(cnt.get('Education', 0)), 'Health': int(cnt.get('Health', 0)), 'Religious': int(cnt.get('Religious', 0)), 'Market': 0, 'Open space': 0, 'Refuse': 0}
    gap = []
    for name, key, per, why in std:
        need = int(np.ceil(POP / per)); h = have[key]
        gap.append(dict(facility=name, existing_mapped=h, needed_for_20000=need, gap=max(0, need - h), basis=why,
                        proposal={'Education': 'Existing schools cover the need if capacity is adequate - verify enrolment', 'Health': 'Covered (incl. 2 hospitals) - verify',
                                  'Religious': 'Likely under-mapped in OSM - field check before any allocation', 'Market': 'Neighbourhood market: acquire / redevelop an under-used compound near the La Rd - Oxford St corner',
                                  'Open space': f'{len(PK)} pocket parks on vacant land + drainage greenway ({G.area_m2.sum():.0f} m2); remaining gap needs acquisition of under-used land',
                                  'Refuse': f'{len(RF)} skip pads in wide road verges (every home within ~300 m)'}[key]))
    GAP = pd.DataFrame(gap)
    # ---------- outputs ----------
    MU.to_file(D + PFX + 'Plan_mixed_use_corridor.shp'); G.to_file(D + PFX + 'Plan_greenway.shp'); PK.to_file(D + PFX + 'Plan_pocket_parks.shp')
    RF.to_file(D + PFX + 'Plan_refuse_points.shp')
    with pd.ExcelWriter(D + PFX + 'Upgrading_plan_tables.xlsx') as xw:
        pd.DataFrame([dict(item='Site area (ha)', value=round(site.area * FT * FT / 1e4, 1)), dict(item='Buildings', value=len(B)), dict(item='Building coverage (%)', value=round(B.area.sum() / site.area * 100, 1)),
                      dict(item='Estimated population (provisional)', value=POP), dict(item='Assumption', value='1.5 storeys average, 60 m2 per household, 3.4 persons per household'),
                      dict(item='Pinch points', value=len(PP)), dict(item='Mixed-use corridor (ha)', value=round(corr.area * FT * FT / 1e4, 1)), dict(item='Drainage greenway (m2)', value=round(G.area_m2.sum())),
                      dict(item='Pocket parks', value=len(PK)), dict(item='Refuse points', value=len(RF))]).to_excel(xw, sheet_name='summary', index=False)
        GAP.to_excel(xw, sheet_name='facility gaps', index=False)
        B.ex_use.value_counts().rename_axis('existing use').rename('buildings').reset_index().to_excel(xw, sheet_name='existing land use', index=False)
        R.drop(columns='geometry').to_excel(xw, sheet_name='roads', index=False)
        PP.drop(columns='geometry').to_excel(xw, sheet_name='pinch points', index=False)
    print(GAP[['facility', 'existing_mapped', 'needed_for_20000', 'gap']].to_string()); print('greenway m2', G.area_m2.sum(), '| corridor ha', round(corr.area * FT * FT / 1e4, 1), '| refuse points', len(RF), '| pinch points', len(PP), 'severe', int((PP.width_m < 6).sum()))
    # ---------- map ----------
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    b = r.bounds; ext = (b.left, b.right, b.bottom, b.top); S3 = gpd.GeoSeries([site], crs=2136).to_crs(3857)
    fig, ax = plt.subplots(figsize=(18, 17)); ax.imshow(img, extent=ext, alpha=.55)
    MU.to_crs(3857).plot(ax=ax, color='#e15759', alpha=.35); G.to_crs(3857).plot(ax=ax, color='#2ca02c', alpha=.6, ec='darkgreen')
    B.to_crs(3857).plot(ax=ax, color='#f4d35e', ec='k', lw=.1, alpha=.8); PK.to_crs(3857).plot(ax=ax, color='lime', ec='darkgreen', lw=1.5)
    PP.to_crs(3857).plot(ax=ax, color=np.where(PP.width_m < 6, 'red', 'orange'), markersize=90, marker='X'); RF.to_crs(3857).plot(ax=ax, color='saddlebrown', markersize=140, marker='s', ec='white')
    S3.boundary.plot(ax=ax, color='black', lw=2.5); x0, y0, x1, y1 = S3.total_bounds; ax.set_xlim(x0 - 30, x1 + 30); ax.set_ylim(y0 - 30, y1 + 30); ax.set_xticks([]); ax.set_yticks([])
    ax.legend(handles=[Patch(color='#e15759', alpha=.5, label='Mixed-use corridor (La Rd, 28th Feb Rd, Oxford St)'), Patch(color='#2ca02c', label='Drainage greenway / linear park'),
                       Patch(color='lime', label='Pocket park on vacant land'), Patch(color='#f4d35e', label='Existing buildings (retained)'),
                       Line2D([0], [0], marker='X', color='w', markerfacecolor='red', markersize=12, label='Severe pinch point (< 6 m between building lines)'),
                       Line2D([0], [0], marker='X', color='w', markerfacecolor='orange', markersize=12, label='Narrow section (below class minimum): no parking, calming'),
                       Line2D([0], [0], marker='s', color='w', markerfacecolor='saddlebrown', markersize=12, label='Refuse / sanitary collection point')], loc='lower left', fontsize=11)
    ax.set_title(TITLE + f' upgrading plan - proposals (provisional population ~{POP:,})', fontsize=16)
    plt.savefig(D + PFX + 'Upgrading_plan_proposals.png', bbox_inches='tight', dpi=60)

def _design_site_analysis(ctx):
    """Imagery (z18) and DEM warped to EPSG:2136; site analysis map."""
    WORK, SITE_KML, NAME = ctx['WORK'], ctx['SITE_KML'], ctx['NAME']
    import geopandas as gpd, numpy as np, rasterio, contextily as cx, warnings
    from rasterio.warp import reproject, Resampling, calculate_default_transform
    from rasterio.transform import from_bounds
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    warnings.filterwarnings('ignore')
    OUT = WORK
    site = gpd.read_file(SITE_KML).to_crs(2136); S = site.geometry.iloc[0]
    # ---- imagery warped to EPSG:2136 ----
    g3857 = site.to_crs(3857); w, s, e, n = g3857.buffer(220).total_bounds
    img, ext = robust_tiles(w, s, e, n, 18, ll=False)
    h, wd = img.shape[:2]; src_t = from_bounds(ext[0], ext[2], ext[1], ext[3], wd, h)
    dst_t, W, H = calculate_default_transform('EPSG:3857', 'EPSG:2136', wd, h, ext[0], ext[2], ext[1], ext[3])
    out = np.zeros((3, H, W), dtype='uint8')
    for b in range(3):
        reproject(img[:, :, b], out[b], src_transform=src_t, src_crs='EPSG:3857', dst_transform=dst_t, dst_crs='EPSG:2136', resampling=Resampling.bilinear)
    with rasterio.open(OUT + 'imagery_2136.tif', 'w', driver='GTiff', height=H, width=W, count=3, dtype='uint8', crs='EPSG:2136', transform=dst_t) as d: d.write(out)
    # ---- DEM to 2136 at 10 ft ----
    with rasterio.open(OUT + 'dem.tif') as r:
        t2, W2, H2 = calculate_default_transform(r.crs, 'EPSG:2136', r.width, r.height, *r.bounds, resolution=10)
        dem = np.full((H2, W2), np.nan, dtype='float32')
        reproject(rasterio.band(r, 1), dem, src_transform=r.transform, src_crs=r.crs, dst_transform=t2, dst_crs='EPSG:2136', resampling=Resampling.cubic, dst_nodata=np.nan)
    with rasterio.open(OUT + 'dem_2136.tif', 'w', driver='GTiff', height=H2, width=W2, count=1, dtype='float32', crs='EPSG:2136', transform=t2, nodata=np.nan) as d: d.write(dem, 1)
    dz_y, dz_x = np.gradient(dem, 10 * 0.3048)                       # metres per metre
    slope = np.degrees(np.arctan(np.hypot(dz_x, dz_y)))
    xs = t2.c + (np.arange(W2) + .5) * t2.a; ys = t2.f + (np.arange(H2) + .5) * t2.e
    X, Y = np.meshgrid(xs, ys)
    from shapely import contains_xy
    inside = contains_xy(S, X, Y)
    print(f'site elevation {np.nanmin(dem[inside]):.0f}-{np.nanmax(dem[inside]):.0f} m | slope mean {np.nanmean(slope[inside]):.1f} deg, '
          f'>8 deg {100 * np.mean(slope[inside] > 8):.0f}% , >15 deg {100 * np.mean(slope[inside] > 15):.0f}%')
    iy, ix = np.unravel_index(np.nanargmin(np.where(inside, dem, np.nan)), dem.shape); print('lowest point', round(X[iy, ix]), round(Y[iy, ix]))
    iy, ix = np.unravel_index(np.nanargmax(np.where(inside, dem, np.nan)), dem.shape); print('highest point', round(X[iy, ix]), round(Y[iy, ix]))
    # ---- maps ----
    CI = next(c for c in (1, 2, 5, 10, 20, 50) if (np.nanmax(dem[inside]) - np.nanmin(dem[inside])) / c <= 40)
    x0, y0, x1, y1 = S.buffer(250).bounds
    fig, axs = plt.subplots(1, 2, figsize=(22, 14))
    for ax, mode in zip(axs, ('img', 'terrain')):
        if mode == 'img':
            ax.imshow(np.moveaxis(out, 0, -1), extent=(dst_t.c, dst_t.c + W * dst_t.a, dst_t.f + H * dst_t.e, dst_t.f))
        else:
            im = ax.imshow(slope, extent=(t2.c, t2.c + W2 * t2.a, t2.f + H2 * t2.e, t2.f), cmap='RdYlGn_r', vmin=0, vmax=20, alpha=.8); plt.colorbar(im, ax=ax, shrink=.6, label='slope (deg)')
        cs = ax.contour(X, Y, dem, levels=np.arange(np.floor(np.nanmin(dem) / CI) * CI, np.nanmax(dem) + CI, CI), colors='cyan' if mode == 'img' else 'k', linewidths=.6)
        ax.clabel(cs, cs.levels[::2], fontsize=7, fmt='%d m')
        site.boundary.plot(ax=ax, color='yellow' if mode == 'img' else 'b', lw=2.5)
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal')
        ax.set_xticks(np.arange(round(x0, -2), x1, 200)); ax.set_yticks(np.arange(round(y0, -2), y1, 200))
        ax.tick_params(axis='x', rotation=90, labelsize=7); ax.tick_params(axis='y', labelsize=7); ax.grid(color='w' if mode == 'img' else 'grey', lw=.3)
    axs[0].set_title(f'Imagery (Esri, Maxar, Earthstar Geographics) + {CI} m contours, EPSG:2136 ft'); axs[1].set_title('Slope and contours')
    plt.savefig(OUT + 'site_analysis.png', bbox_inches='tight', dpi=80)

def st_design_subdivide(ctx):
    """Plots by the planner's Phase One method: 100 ft front row, one frontage per block (65/70/75/80), leftover only to the end plots (guide section 5)."""
    WORK, SITE_KML, NAME = ctx['WORK'], ctx['SITE_KML'], ctx['NAME']
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
    OUT = WORK; CRS = 2136; DEPTH = 100.0
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

def st_design_landuse(ctx):
    """Facility programme and land use (guide section 7)."""
    WORK, SITE_KML, NAME = ctx['WORK'], ctx['SITE_KML'], ctx['NAME']
    """the site land use. Program: LUSPA Manual 4.6.3 + Guidelines mandatory list. Rates, site sizes and shapes: learned from the STMA schemes.
    Order: community uses go first onto compact leftover sites (as in the schemes); residential plots are taken only where no suitable site exists."""
    import geopandas as gpd, pandas as pd, numpy as np, rasterio, math, json, warnings, shapely
    from rasterio.mask import mask
    from shapely.ops import unary_union
    from shapely.geometry import LineString, Point
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    warnings.filterwarnings('ignore')
    OUT = WORK; AC = 43560
    unit = lambda v: np.asarray(v, float) / np.linalg.norm(v)
    P = gpd.read_file(OUT + 'plots_final.gpkg'); R = gpd.read_file(OUT + 'reserves_final.gpkg')
    C = gpd.read_file(OUT + 'concept.gpkg').set_index('Part').geometry; RD = gpd.read_file(OUT + 'layout_roads.gpkg').set_index('Class').geometry
    SITE, MAIN = C['Site'], C['60 ft existing road']; CORR = shapely.Point(-1e7, -1e7).buffer(1); WZ = C['West zone']; SR = C['Stream reserve']; COLLR = RD['40 ft collector']; ROADS = RD.union_all()
    dem = rasterio.open(OUT + 'dem_2136.tif')
    def elev(g):
        try: a, _ = mask(dem, [g], crop=True, filled=False, all_touched=True); return float(a.compressed().mean())
        except Exception: return np.nan
    def mrr(g):
        if g is None or g.is_empty or g.area <= 0: return [1.0, 1.0]                # nothing there (small site)
        c = list(g.minimum_rotated_rectangle.exterior.coords); return sorted([math.dist(c[0], c[1]), math.dist(c[1], c[2])])
    P['use'], P['label'] = 'RE', ''
    R['use'], R['label'] = '', ''
    log = []
    # ---------- 0. plot-sized leftover pieces (80-125 ft deep, regular) are cut into plots along their road side ----------
    def split_into_plots(g, n):
        c = list(g.minimum_rotated_rectangle.exterior.coords); e = [np.array(c[1]) - np.array(c[0]), np.array(c[2]) - np.array(c[1])]
        ax_ = e[0] if np.linalg.norm(e[0]) > np.linalg.norm(e[1]) else e[1]; L = np.linalg.norm(ax_); u = ax_ / L; nrm = np.array([-u[1], u[0]])
        o = np.array(g.minimum_rotated_rectangle.centroid.coords[0]) - u * L / 2
        cuts = [LineString([tuple(o + u * L * k / n - nrm * 500), tuple(o + u * L * k / n + nrm * 500)]) for k in range(1, n)]
        parts = shapely.get_parts(shapely.ops.split(g, unary_union(cuts))) if cuts else [g]
        return [q for q in parts if q.area > 100]
    newp = []
    for i in list(R.index):
        g = R.geometry[i]; w_, l_ = mrr(g); fill = g.area / (w_ * l_)
        if 80 <= w_ <= 125 and fill >= 0.78 and g.boundary.intersection(ROADS.buffer(2)).length > 60:
            n = max(1, round(l_ / 75))
            for q in split_into_plots(g, n): newp.append(dict(geometry=q, block=-1000 - i))
            R.drop(index=i, inplace=True)
    if newp: P = pd.concat([P, gpd.GeoDataFrame(newp, crs=P.crs).assign(use='RE', label='')], ignore_index=True); P = gpd.GeoDataFrame(P, geometry='geometry', crs=R.crs)
    log.append(('Leftover pieces cut into plots', f'{len(newp)} plots', 'pieces 80-125 ft deep with road frontage'))
    P['elev'] = [elev(g) for g in P.geometry]; R['elev'] = [elev(g) for g in R.geometry]; R['ac'] = R.area / AC
    P['main'] = [g.distance(MAIN) < 3 for g in P.geometry]; P['kor'] = [g.distance(CORR) < 3 for g in P.geometry]
    # ---------- repair: plots with no road access, or small double-frontage plots, merge into the neighbour they share most boundary with ----------
    def frontage_dirs(g):
        g = max(shapely.get_parts(g), key=lambda q: q.area); c = np.array(g.exterior.simplify(1.5).coords); ns = []
        for a_, b_ in zip(c[:-1], c[1:]):
            L = np.linalg.norm(b_ - a_)
            if L < 25: continue
            m = (a_ + b_) / 2; t = (b_ - a_) / L; n = np.array([t[1], -t[0]])
            if g.contains(shapely.Point(m + n * 3)): n = -n
            if ROADS.contains(shapely.Point(m + n * 6)): ns.append(n)
        return ns
    fixed = 0
    for i in list(P.index):
        if i not in P.index: continue
        g = P.geometry[i]; ns = frontage_dirs(g)
        dbl = any(float(ns[a] @ ns[b]) < -0.8 for a in range(len(ns)) for b in range(a + 1, len(ns)))
        if ns and not (dbl and g.area < 9000) and g.area >= 6970 * 0.98: continue
        nb = P[(P.index != i) & (P.geometry.buffer(1).intersection(g).area > 30)]
        if nb.empty: continue
        j = max(nb.index, key=lambda j: P.geometry[j].buffer(1).intersection(g).area)
        ug = unary_union([P.geometry[j], g]).buffer(0.3).buffer(-0.3)
        if ug.geom_type != 'Polygon': continue
        P.at[j, 'geometry'] = ug; P.drop(index=i, inplace=True); fixed += 1
    log.append(('Plot repair', f'{fixed} plots merged into neighbours', 'no road access, or small plots with roads front and back'))
    # deep plots (> 150 ft): roads front and back -> two plots back to back; one frontage -> rear given to the plot behind if it stays <= 150 ft
    nsplit = ngive = 0; NEWH = []
    for i in list(P.index):
        g = P.geometry[i]; w_, d_ = mrr(g)
        if d_ <= 150: continue
        q = list(g.minimum_rotated_rectangle.exterior.coords); e1, e2 = np.array(q[1]) - np.array(q[0]), np.array(q[2]) - np.array(q[1])
        dv = unit(e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2); cm = np.array(g.minimum_rotated_rectangle.centroid.coords[0])
        ns = frontage_dirs(g); dbl = any(float(ns[a] @ ns[b]) < -0.8 for a in range(len(ns)) for b in range(a + 1, len(ns)))
        cut = LineString([tuple(cm - np.array([-dv[1], dv[0]]) * 400), tuple(cm + np.array([-dv[1], dv[0]]) * 400)])
        halves = [h for h in shapely.get_parts(shapely.ops.split(g, cut)) if h.area > 100]
        if dbl and len(halves) == 2 and min(h.area for h in halves) >= 6970 * 0.98:
            P.at[i, 'geometry'] = halves[0]; NEWH.append(P.loc[[i]].assign(geometry=[halves[1]])); nsplit += 1; continue
        if not dbl and ns:
            front = ns[0]; off = d_ - 120                                           # keep 120 ft from the front
            if off < 20: continue
            rear_cut = LineString([tuple(cm - front * (d_ / 2 - off) - np.array([-front[1], front[0]]) * 400), tuple(cm - front * (d_ / 2 - off) + np.array([-front[1], front[0]]) * 400)])
            parts = sorted([h for h in shapely.get_parts(shapely.ops.split(g, rear_cut)) if h.area > 50], key=lambda h: -h.area)
            if len(parts) < 2: continue
            keep, rear = parts[0], unary_union(parts[1:])
            nb = P[(P.index != i) & (P.geometry.buffer(1).intersection(rear).area > 30)]
            if nb.empty: continue
            j = max(nb.index, key=lambda j: P.geometry[j].buffer(1).intersection(rear).area); ug = unary_union([P.geometry[j], rear]).buffer(0.3).buffer(-0.3)
            if ug.geom_type == 'Polygon' and mrr(ug)[1] <= 150 and keep.area >= 6970 * 0.98:
                P.at[i, 'geometry'] = keep; P.at[j, 'geometry'] = ug; ngive += 1
    if NEWH: P = gpd.GeoDataFrame(pd.concat([P] + NEWH, ignore_index=True), geometry='geometry', crs=R.crs)
    P = P.reset_index(drop=True)
    log.append(('Deep plots', f'{nsplit} split back to back, {ngive} rear strips given to the plot behind', 'plots kept within ~150 ft depth'))
    BLK = gpd.read_file(OUT + 'layout_blocks.gpkg').geometry
    moved_ = 0
    for b in BLK:
        w_, l_ = mrr(b)
        if w_ < 170 and b.exterior.intersection(ROADS.buffer(2)).length / b.exterior.length > 0.8 and b.buffer(3).intersection(SR).area < 100:
            idx = P.index[P.geometry.representative_point().within(b.buffer(1))]
            if len(idx):
                R = pd.concat([R, gpd.GeoDataFrame(dict(use=[''], label=['']), geometry=[unary_union(list(P.loc[idx].geometry)).buffer(0.5).buffer(-0.5)], crs=P.crs)], ignore_index=True)
                P = P.drop(index=idx); moved_ += len(idx)
    R = gpd.GeoDataFrame(R, geometry='geometry', crs=P.crs); R['ac'] = R.area / AC; R['elev'] = [elev(g) for g in R.geometry]
    log.append(('Single-row blocks (roads all round)', f'{moved_} plots returned to the site pool', 'become facility sites (local-plan pattern), no double-frontage plots'))
    R['fill'] = [g.area / np.prod(mrr(g)) for g in R.geometry]; R['front'] = [g.boundary.intersection(ROADS.buffer(2)).length for g in R.geometry]
    gross = SITE.area / AC; deduct = (MAIN.area + SR.area) / AC; net = gross - deduct
    program = dict(gross_ac=round(gross, 1), existing_road_and_stream_reserve_ac=round(deduct, 1), net_ac=round(net, 1), housing_ac_at_65pct=round(net * 0.65, 1), plots_target=round(net * 0.65 * 6.2), population=round(net * 0.65 * 6.2 * 7.2, -1))
    centre = unary_union(list(P.geometry)).centroid; JPT = COLLR.intersection(MAIN.buffer(2)).centroid
    if JPT.is_empty: JPT = MAIN.boundary.interpolate(MAIN.boundary.project(centre)) if MAIN.area > 10 else centre     # no collector x main road junction: nearest point of the main road
    nres0 = len(P)
    SMALL = nres0 < 60                                # well below a neighbourhood (Guidelines: < 5,000 people): served by the surrounding neighbourhood's facilities
    NEIGH_USES = {'Ed P', 'H Po', 'Com A', 'PW', 'CIV'}
    def _skip_small(use, label):
        if SMALL and (use in NEIGH_USES or str(label).startswith('UT')):
            log.append((label, 'not placed', f'small site ({nres0} plots, well below a 5,000-person neighbourhood): served by the surrounding neighbourhood')); print(f'   {label}: not placed (small site, {nres0} plots: served by the surrounding neighbourhood)', flush=True); return True
        return False
    if SMALL: print(f'   small site: {nres0} plots - neighbourhood facilities (school, health, market, worship, civic, water tank) are not carved out; open space and sanitary sites are', flush=True)
    def compact(lo, hi, extra=None):
        asp = np.array([mrr(g)[1] / max(mrr(g)[0], 1) for g in R.geometry])
        c = R[(R.use == '') & R.ac.between(lo, hi) & (R.fill >= 0.8) & (R.front >= 100) & (asp <= 2.0)]
        return c if extra is None else c[extra(c)]
    def take(i, use, label, why):
        if _skip_small(use, label): return shapely.Polygon()
        R.at[i, 'use'] = use; R.at[i, 'label'] = label; log.append((label, f'{R.ac[i]:.2f} ac leftover site', why)); return R.geometry[i]
    def assign_plots(idx, use, label, why):
        if _skip_small(use, label): return shapely.Polygon()
        idx = [i for i in idx if i in P.index]
        if not idx:                                   # small site: nothing left to give this facility
            log.append((label, 'not placed', 'no residential plots left on this small site: served from outside the site')); print(f'   {label}: not placed (no plots left on this small site)', flush=True)
            return shapely.Polygon()
        g = unary_union(list(P.loc[idx].geometry)).buffer(0.5).buffer(-0.5); keep = idx[0]
        P.at[keep, 'geometry'] = g; P.at[keep, 'use'] = use; P.at[keep, 'label'] = label; P.drop(index=list(idx[1:]), inplace=True)
        log.append((label, f'{g.area / AC:.2f} ac ({len(idx)} plots)', why)); return g
    def best_group(cands, n, k=12):
        best = None
        for sd in list(cands)[:k]:
            g = chain(sd, n); u = unary_union(list(P.loc[g].geometry)); w_, l_ = mrr(u); sc = (w_ * l_) / u.area + 0.3 * l_ / w_ + (5 if u.area / (w_ * l_) < 0.82 else 0)
            if len(g) == n and (best is None or sc < best[0]): best = (sc, g)
        if best: return best[1]
        return chain(list(cands)[0], n) if len(list(cands)) else []
    def plots_along_frontage(poly, depth=105.0, fw=70.0):
        edges = poly.exterior.intersection(ROADS.buffer(3)); edges = shapely.line_merge(unary_union([e for e in shapely.get_parts(edges) if e.geom_type == 'LineString']))
        out, used = [], Point(0, 0).buffer(0.01)
        for e in sorted([x for x in shapely.get_parts(edges) if x.length >= 140], key=lambda x: -x.length):
            e = e.simplify(2); strip = poly.intersection(e.buffer(depth, cap_style=2)).difference(used)
            if strip.is_empty or strip.area < 6970: continue
            n = max(1, int((e.length + 3) // fw)); cuts = []
            for k in range(1, n):
                p_ = np.array(e.interpolate(e.length * k / n).coords[0]); a1 = np.array(e.interpolate(max(0, e.length * k / n - 5)).coords[0]); b1 = np.array(e.interpolate(min(e.length, e.length * k / n + 5)).coords[0]); t_ = unit(b1 - a1); nn = np.array([-t_[1], t_[0]])
                cuts.append(LineString([tuple(p_ - nn * 400), tuple(p_ + nn * 400)]))
            parts = shapely.get_parts(shapely.ops.split(strip, unary_union(cuts))) if cuts else [strip]
            for q in parts:
                if q.area >= 6970 * 0.98 and q.area <= 16000 and q.area / np.prod(mrr(q)) >= 0.65: out.append(q)
            used = used.union(strip)
        return out, poly.difference(unary_union(out)) if out else poly
    def chain_area(seed, target_ac):
        grp = chain(seed, 1)
        for k in range(2, 6):
            if unary_union(list(P.loc[grp].geometry)).area / AC >= target_ac * 0.9: break
            grp = chain(seed, k)
        return grp
    def chain(seed, n):
        pool = P[(P.use == 'RE') & (P.block == P.at[seed, 'block'])]; grp = [seed]
        while len(grp) < n:
            cur = unary_union(list(P.loc[grp].geometry)); c = pool[(~pool.index.isin(grp)) & (pool.geometry.distance(cur) < 2)]
            if c.empty: break
            def loose(i):
                u = unary_union(list(P.loc[grp + [i]].geometry)); a, b = mrr(u); return u.minimum_rotated_rectangle.area / u.area + 0.5 * b / max(a, 1)
            grp.append(min(c.index, key=loose))
        return grp
    # ---------- 1. school: whole residential block on the collector, central (learned 0.9-3.0 ac, median 1.8) ----------
    B = P[P.use == 'RE'].groupby('block').agg(n=('use', 'size'), main=('main', 'any'), kor=('kor', 'any')).reset_index()
    B['geometry'] = [unary_union(list(P[P.block == k].geometry)) for k in B.block]; B = gpd.GeoDataFrame(B, geometry='geometry', crs=P.crs); B['ac'] = B.area / AC
    B['on_coll'] = B.geometry.distance(COLLR) < 3; B['d'] = B.geometry.centroid.distance(centre); B['fill'] = [g.area / np.prod(mrr(g.convex_hull)) for g in B.geometry]
    cand = B[(~B.main) & (~B.kor) & B.ac.between(1.4, 2.6) & (B.fill >= 0.85)].sort_values('d')
    cand = cand[cand.d <= cand.d.min() + 400].sort_values(['on_coll', 'd'], ascending=[False, True])     # central first, then on a collector
    if cand.empty:                                    # no ideal block: any compact residential block of school size
        cand = B[(~B.kor) & B.ac.between(0.9, 3.0) & (B.fill >= 0.7)].sort_values(['on_coll', 'd'], ascending=[False, True])
    if len(cand):
        SCH = assign_plots(list(P.index[P.block == cand.block.iloc[0]]), 'Ed P', 'Basic School (Primary + JHS) and Nursery', 'Guidelines: nursery + primary per neighbourhood; learned school site 0.9-3.0 ac; central, on the collector')
    else:                                             # small site: no block of school size -> a group of plots near the centre
        re_ = P[P.use == 'RE']; tgt_ = min(1.8, 0.2 * re_.area.sum() / AC)
        seed_ = re_.geometry.centroid.distance(centre).idxmin(); grp_ = chain_area(seed_, tgt_)
        SCH = assign_plots(grp_, 'Ed P', 'Basic School (Primary + JHS) and Nursery', f'no residential block of school size on this site: {len(grp_)} central plots grouped; below the 3 ac primary standard - check the population needs a school here')
        if not SMALL: print(f'   school: no block of school size; {len(grp_)} central plots grouped ({SCH.area / AC:.2f} ac) - check the population needs a school here', flush=True)
    si = P.index[P.label.str.startswith('Basic School')][0] if P.label.str.startswith('Basic School').any() else None
    for i in list(R.index):                       # no open space inside school land: a leftover piece inside the school block joins the school
        if R.geometry[i].buffer(1).intersection(SCH).area > 30:
            SCH = unary_union([SCH, R.geometry[i]]).buffer(0.5).buffer(-0.5); P.at[si, 'geometry'] = SCH; R.drop(index=i, inplace=True)
    # ---------- 2. P.O.S + children's play area: compact leftover site nearest the school ----------
    c = compact(0.4, 1.4)
    if len(c) and c.geometry.distance(SCH).min() < 300: take(c.geometry.distance(SCH).idxmin(), 'POS', "P.O.S and Children's Play Area", 'next to the school (learned pairing); learned open space 0.5-2.7 ac')
    else:
        nb_ = P[(P.use == 'RE') & (P.geometry.distance(SCH) > 20) & (P.geometry.distance(SCH) < 80)]                  # across a road from the school
        if len(nb_): assign_plots(best_group(nb_.geometry.distance(SCH).sort_values().index, 4), 'POS', "P.O.S and Children's Play Area", 'across the road from the school (local-plan pattern: school + playground)')
    # ---------- 3. gateway: market on a corner where the collector meets the main road (4 plots); health post on a compact leftover site on a major road near the gateway, else 4 plots ----------
    mp = P[(P.use == 'RE') & P.main].copy()
    if mp.empty: mp = P[P.use == 'RE'].copy()                  # small site: no residential plot on a main road -> nearest plots to the gateway
    mp['d'] = mp.geometry.distance(JPT); mp = mp.sort_values('d')
    MK = assign_plots(best_group(mp.index, 4, k=8), 'Com A', 'Neighbourhood Shopping Centre / Market', 'Guidelines mandatory; learned market site 0.6 ac; gateway corner (collector x main road)')
    c = compact(0.5, 1.0, lambda c: (c.geometry.distance(MAIN.union(CORR)) < 3) & (c.geometry.distance(JPT) < 700))
    if len(c): HP = take(c.geometry.distance(JPT).idxmin(), 'H Po', 'Health Post', 'Guidelines min. 0.5 ac on a main road; learned health site 0.88 ac; near the gateway')
    else:
        o = mp[mp.index.isin(P.index)]; o = o[(P.loc[o.index, 'use'] == 'RE')]
        if o.empty: o = P[P.use == 'RE'].assign(d=lambda x: x.geometry.distance(JPT)).sort_values('d')
        HP = assign_plots(chain_area(o.index[0], 0.75), 'H Po', 'Health Post', 'Guidelines min. 0.5 ac on a main road; ~0.75 ac at the gateway')
    po = P[(P.use == 'RE') & P.main]
    if po.empty: po = P[P.use == 'RE']
    po = po.assign(d=po.geometry.distance(MK)).sort_values('d')
    if len(po) and not SMALL: P.at[po.index[0], 'use'] = 'BM'; P.at[po.index[0], 'label'] = 'Postal Agency (mixed use)'; log.append(('Postal Agency', '1 plot', 'Guidelines mandatory; beside the market'))
    # ---------- 4. places of worship (1 per ~160 plots): compact leftover sites, one each side of the main road; else 4 plots ----------
    n_pw = max(1, round(nres0 / 160))
    west_of_stream = lambda c: c.geometry.centroid.within(WZ.buffer(5))
    for side in ([lambda c: ~west_of_stream(c), west_of_stream, lambda c: ~west_of_stream(c), lambda c: ~west_of_stream(c)])[:n_pw]:
        c = compact(0.55, 1.3, side)
        c = c[[R.geometry[i].area / np.prod(mrr(R.geometry[i])) >= 0.8 for i in c.index]] if len(c) else c
        if len(c): take(c.ac.idxmax(), 'PW', 'Place of Worship', 'learned 1 per ~160 plots; site 0.68-1.21 ac, near-square')
        else:
            z = P[(P.use == 'RE') & side(P) & ~P.main & ~P.kor]; order = z.geometry.centroid.distance(z.geometry.union_all().centroid).sort_values().index
            cands_ = []
            for n_ in (4, 3, 5, 6):
                g_ = best_group(order, n_, k=40); u_ = unary_union(list(P.loc[g_].geometry)); w_, l_ = mrr(u_)
                if 0.55 <= u_.area / AC <= 1.3: cands_.append((u_.area / (w_ * l_) < 0.8, l_ / w_, g_))
            g_ = min(cands_, key=lambda t: t[:2])[2] if cands_ else best_group(order, 4)
            assign_plots(g_, 'PW', 'Place of Worship', 'learned 1 per ~160 plots; most compact plot group')
    # ---------- 5. community centre (Guidelines recommended; learned civic 0.65-1.13 ac): largest compact site left nearest the centre ----------
    c = compact(0.55, 1.3)
    if len(c): take(c.geometry.distance(centre).idxmin(), 'CIV', 'Community Centre', 'Guidelines recommended; learned civic site 0.82 ac')
    # ---------- 6. open space east of the 100 ft road, so children need not cross it ----------
    east = lambda c: c.geometry.centroid.within(WZ.buffer(5))
    if not ((R.use == 'POS') & east(R)).any():
        c = R[(R.use == '') & (R.ac >= 0.4) & east(R)]
        if len(c): take(c.ac.idxmax(), 'POS', 'P.O.S', 'west of the stream (children need not cross it)')
    # ---------- 6b. deep irregular residential plots (> 150 ft, not on a major road, e.g. where curved roads meet) -> one defined open space if together >= 0.3 ac ----------
    deep = P[(P.use == 'RE') & ~P.main & ~P.kor & np.array([mrr(g)[1] > 150 for g in P.geometry])]
    if False and len(deep):
        groups = shapely.get_parts(unary_union(list(deep.geometry.buffer(1))))
        for gg in groups:
            idx = list(deep.index[deep.geometry.intersects(gg)])
            if 0.4 <= unary_union(list(P.loc[idx].geometry)).area / AC <= 1.5: assign_plots(idx, 'POS', 'P.O.S', 'irregular land where curved roads meet (as in the schemes, open space takes the irregular land)')
    sa_sites = []
    # ---------- 7b. open space within reach (500 m), but no more sites than the scheme rate allows (1 per ~271 plots) ----------
    POS_CAP = max(1, round((P.use == 'RE').sum() / 271))
    for _ in range(4):
        homes = P[P.use == 'RE']; pts = list(homes.geometry.centroid); os_ = unary_union(list(R.geometry[R.use == 'POS']) + list(P.geometry[P.use == 'POS']))
        dmax = np.array([os_.distance(p) if not os_.is_empty else 1e9 for p in pts]) * 0.3048
        if (dmax <= 500).all() or (R.use == 'POS').sum() + (P.use == 'POS').sum() >= POS_CAP + 1: break
        unc = homes[dmax > 500]; zone = unc.geometry.union_all().convex_hull.buffer(300)
        SAU = unary_union(sa_sites) if sa_sites else shapely.Point(0, 0)
        c = R[(R.use == '') & (R.ac >= 0.4) & R.geometry.intersects(zone) & (R.geometry.distance(SAU) > 197)]
        if len(c): take(c.geometry.distance(unc.geometry.union_all().centroid).idxmin(), 'POS', 'P.O.S', 'homes more than 500 m from open space')
        else:
            unc = unc[unc.geometry.distance(SAU) > 197]
            s_ = unc.geometry.centroid.distance(unc.geometry.union_all().centroid).idxmin()
            g_ = assign_plots(chain_area(s_, 0.45), 'POS', 'P.O.S', 'homes more than 500 m from open space; compact plot group >= 0.45 ac')
    c = R[(R.use == '') & R.ac.between(0.12, 0.45)].sort_values('elev', ascending=False)
    if len(c) and c.elev.iloc[0] >= P[P.use == 'RE'].elev.max() - 1.0: take(c.index[0], 'SU', 'UT (water tank)', 'highest ground; learned utility 0.2 ac')
    elif (P.use == 'RE').any(): assign_plots(chain_area(P[P.use == 'RE'].elev.idxmax(), 0.18), 'SU', 'UT (water tank)', 'highest ground (gravity supply); learned utility site 0.2 ac')
    else: assign_plots([], 'SU', 'UT (water tank)', '')
    # ---------- 8. remaining leftover sites: facility programme first (local-plan pattern: wedges hold facilities), then open space, then merge ----------
    nres_now = (P.use == 'RE').sum()
    PROG = [('Basic School (second)', 'Ed P', 1.2, 3.0, 0, 'learned 1 school site per ~144 plots; Guidelines: basic school within walking distance'),
            ('Day Care / Nursery', 'Ed P', 0.5, 1.0, max(1, round(nres_now / 300)), 'Guidelines mandatory nursery; learned 0.65-0.97 ac'),
            ('Clinic', 'H Po', 0.5, 1.3, 1, 'second health site for ~2,700 people; learned health 0.63-1.05 ac'),
            ('Community Centre', 'CIV', 0.5, 1.3, 1 - int((R.use == 'CIV').any()), 'Guidelines recommended; learned civic 0.65-1.13 ac'),
            ('Police Post', 'CIV', 0.4, 1.1, 1, 'learned police/fire 0.58-1.09 ac'),
            ('Sub-Market / Commercial', 'Com A', 0.3, 1.6, 1, 'learned market/commercial 0.23-1.58 ac'),
            ('Lorry / Taxi Station', 'TR', 0.4, 1.4, 1 - int((R.use == 'TR').any()), 'learned transport 0.41-1.41 ac; on a collector or the main road'),
            ("Children's Playground", 'POS', 0.2, 0.6, min(2, max(1, round(nres_now / 300))), 'small play area (Tokunaso/Wassa pattern); about 1 per 300 plots'),
            ('Utility (U.T)', 'SU', 0.1, 0.35, 2, 'learned utility 0.13-0.36 ac')]
    quota = {p_[0]: p_[4] for p_ in PROG}
    homes_ = list(P[P.use == 'RE'].geometry.centroid); sch_now = P.geometry[P.use == 'Ed P'].union_all()
    pop_ = nres_now * 7.2                                                       # ~7.2 people per plot (as the population estimate below)
    far_ = max((sch_now.distance(h) for h in homes_), default=0) * 0.3048 if not sch_now.is_empty else 1e9
    NEED2 = pop_ > 5000 or far_ > 800                                          # Guidelines: 1 primary per neighbourhood of <= 5,000 people; learned: homes within ~800 m
    print(f'   second basic school: {"needed" if NEED2 else "not needed"} (population ~{pop_:.0f}, furthest home {far_:.0f} m from the school)', flush=True)
    if NEED2:                                                                   # the leftover site that brings the furthest home closest to a school, at least 400 m from the first
        away_ = lambda g: sch_now.is_empty or g.distance(sch_now) * 0.3048 >= 400
        best_s = None
        for i in R[(R.use == '') & R.ac.between(1.2, 3.0)].index:
            g = R.geometry[i]; w2, l2_ = mrr(g)
            if not away_(g): continue
            if g.area / (w2 * l2_) < 0.7 or l2_ / w2 > 2.5: continue
            u_ = sch_now.union(g); m_ = max(u_.distance(h) for h in homes_)
            if best_s is None or m_ < best_s[0]: best_s = (m_, i)
        if not best_s:                                                           # no leftover site fits: a regular residential block that best covers the furthest homes
            B2 = P[P.use == 'RE'].groupby('block').agg(n=('use', 'size'), main=('main', 'any')).reset_index()
            B2['geometry'] = [unary_union(list(P[(P.block == k) & (P.use == 'RE')].geometry)) for k in B2.block]; B2 = gpd.GeoDataFrame(B2, geometry='geometry', crs=P.crs); B2['ac'] = B2.area / AC
            B2['fill'] = [g.area / np.prod(mrr(g.convex_hull)) for g in B2.geometry]; B2 = B2[(~B2.main) & B2.ac.between(1.2, 2.6) & (B2.fill >= 0.85)]; B2 = B2[[away_(g) for g in B2.geometry]]
            if len(B2):
                sc_ = [max(sch_now.union(g).distance(h) for h in homes_) for g in B2.geometry]; kb = B2.block.iloc[int(np.argmin(sc_))]
                assign_plots(list(P.index[(P.block == kb) & (P.use == 'RE')]), 'Ed P', 'Basic School (second)', f'learned 1 school per ~144 plots; regular block placed so every home is within {min(sc_) * 0.3048:.0f} m of a school')
            else: quota['Basic School (second)'] = 1
        if best_s: take(best_s[1], 'Ed P', 'Basic School (second)', f'Guidelines: >5,000 people or homes > 800 m away; placed >= 400 m from the first, every home within {best_s[0] * 0.3048:.0f} m of a school')
    for i in R[(R.use == '')].sort_values('ac', ascending=False).index.tolist():
        g = R.geometry[i]; a_ = R.ac[i]; done = False
        near_sa = len(sa_sites) and min(g.distance(x) for x in sa_sites) < 197
        for name, use, lo, hi, _, why in PROG:
            if quota[name] <= 0 or not (lo <= a_ <= hi): continue
            if name == 'Basic School (second)' and not sch_now.is_empty and g.distance(sch_now) * 0.3048 < 400: continue      # never next to the first school
            if near_sa and use in ('POS', 'Ed P', 'H Po', 'Com A'): continue
            w2, l2_ = mrr(g)
            if use in ('Ed P', 'H Po', 'CIV', 'Com A', 'PW') and (g.area / (w2 * l2_) < 0.78 or l2_ / w2 > 2.2): continue      # buildings need compact sites
            if name == 'Lorry / Taxi Station' and g.distance(MAIN) > 3 and g.distance(COLLR) > 3: continue
            take(i, use, name, why); quota[name] -= 1; done = True; break
        if done: continue
        pos = R[R.use == 'POS']
        if a_ >= 0.6 and (len(pos) >= POS_CAP or near_sa or a_ > 2.7):      # open spaces are scheme-sized (0.5-2.7 ac): a bigger piece gets plots on its road edges first
            newp, rest_ = plots_along_frontage(g)
            if newp:
                P = gpd.GeoDataFrame(pd.concat([P, gpd.GeoDataFrame(dict(use=['RE'] * len(newp), label=[''] * len(newp), block=[-3000 - i] * len(newp), main=[q.distance(MAIN) < 3 for q in newp], kor=[False] * len(newp), elev=[elev(q) for q in newp]), geometry=newp, crs=P.crs)], ignore_index=True), geometry='geometry', crs=P.crs)
                R.at[i, 'geometry'] = rest_; R.at[i, 'ac'] = rest_.area / AC; g = rest_; a_ = R.ac[i]
                log.append(('Leftover land cut into plots', f'{len(newp)} plots', 'standard plots along the road edges of a large leftover piece'))
                if a_ < 0.05: R.at[i, 'use'] = 'DROP'; continue
        if not near_sa and len(pos) < POS_CAP and a_ >= 0.4: take(i, 'POS', 'P.O.S', 'defined open space (leftover land >= 0.4 ac, or none within 200 m)'); continue
        nb = P[(P.use == 'RE') & (P.geometry.buffer(1).intersection(g).area > 20)]          # small piece: join the neighbouring plot if it stays a sensible size
        j = max(nb.index, key=lambda j: P.geometry[j].buffer(1).intersection(g).area) if len(nb) else None
        if j is not None and (P.geometry[j].area + g.area) < 18000 and mrr(unary_union([P.geometry[j], g]))[1] < 180:
            P.at[j, 'geometry'] = unary_union([P.geometry[j], g]).buffer(0.3).buffer(-0.3); R.at[i, 'use'] = 'DROP'
        else: R.at[i, 'use'] = 'GRN'; R.at[i, 'label'] = 'Landscaped green'
    R = R[R.use != 'DROP']
    # ---------- landlocked pockets (>= 0.6 ac, little road frontage): a cul-de-sac (<= 200 m) square from the nearest road, plots along both sides ----------
    LANES = []
    ROAD_LINES = gpd.read_file(OUT + 'layout_centrelines.gpkg').geometry.union_all()
    for i in []:   # cul-de-sac step tested: few plots, created double frontage -> off
        g = R.geometry[i]; q = list(g.minimum_rotated_rectangle.exterior.coords); e1, e2 = np.array(q[1]) - np.array(q[0]), np.array(q[2]) - np.array(q[1])
        Lv = e1 if np.linalg.norm(e1) > np.linalg.norm(e2) else e2; u_ = unit(Lv); cm = np.array(g.minimum_rotated_rectangle.centroid.coords[0])
        best_l = None
        for sgn in (1, -1):                                                         # enter along the pocket's long axis from whichever end is nearer a road
            far = cm + sgn * u_ * np.linalg.norm(Lv) / 2; ray = LineString([tuple(cm), tuple(far + sgn * u_ * 900)])
            h = ray.intersection(ROAD_LINES)
            hs = [x for x in shapely.get_parts(h) if x.geom_type == 'Point']
            if not hs: continue
            hp = min(hs, key=lambda x: x.distance(Point(cm))); L_ = Point(cm).distance(hp) + np.linalg.norm(Lv) / 2 - 60
            if L_ * 0.3048 <= 200 and (best_l is None or L_ < best_l[0]): best_l = (L_, np.array(hp.coords[0]), -sgn * u_)
        if best_l is None: continue
        L_, start, dirn = best_l; end = start + dirn * L_
        lane = LineString([tuple(start), tuple(end)]); lane_poly = lane.buffer(15, cap_style=2).union(Point(end).buffer(40))     # turning head
        # plots crossed by the lane are trimmed (or merged if too small)
        hitp = P[P.geometry.intersects(lane_poly)]
        for j in hitp.index:
            ng = P.geometry[j].difference(lane_poly); ng = max(shapely.get_parts(ng), key=lambda x: x.area) if not ng.is_empty else ng
            if ng.is_empty or ng.area < 6970 * 0.98: P.at[j, 'use'] = 'DROPP'
            else: P.at[j, 'geometry'] = ng
        P = P[P.use != 'DROPP']
        ROADS = ROADS.union(lane_poly); pocket = g.difference(lane_poly)
        newp = []
        for part in shapely.get_parts(pocket):
            np_, rest_ = plots_along_frontage(part); newp += np_
        if newp:
            P = gpd.GeoDataFrame(pd.concat([P, gpd.GeoDataFrame(dict(use=['RE'] * len(newp), label=[''] * len(newp), block=[-4000 - i] * len(newp), main=[False] * len(newp), kor=[False] * len(newp), elev=[elev(q) for q in newp]), geometry=newp, crs=P.crs)], ignore_index=True), geometry='geometry', crs=P.crs)
            rem = pocket.difference(unary_union(newp)); R.at[i, 'geometry'] = rem if not rem.is_empty else Point(0, 0).buffer(0.01)
            LANES.append(lane_poly); log.append(('Cul-de-sac into a landlocked pocket', f'{L_ * 0.3048:.0f} m lane, {len(newp)} plots', 'local-plan pattern; cul-de-sac <= 200 m with turning head'))
    R = R[R.area > 200]
    if LANES: gpd.GeoDataFrame(geometry=LANES, crs=P.crs).to_file(OUT + 'lanes.gpkg')
    if quota.get('Day Care / Nursery', 0) > 0:
        big_ = R[(R.use == 'POS') & (R.area / AC > 1.6)]
        if len(big_):
            i = big_.area.idxmax(); g = R.geometry[i]; q = list(g.minimum_rotated_rectangle.exterior.coords)
            e1, e2 = np.array(q[1]) - np.array(q[0]), np.array(q[2]) - np.array(q[1]); Lv = e1 if np.linalg.norm(e1) > np.linalg.norm(e2) else e2; u_ = unit(Lv)
            o_ = np.array(g.minimum_rotated_rectangle.centroid.coords[0]) - u_ * np.linalg.norm(Lv) / 2; nn_ = np.array([-u_[1], u_[0]])
            for t_ in np.linspace(40, np.linalg.norm(Lv) - 40, 60):
                cut = LineString([tuple(o_ + u_ * t_ - nn_ * 800), tuple(o_ + u_ * t_ + nn_ * 800)]); parts = sorted(shapely.get_parts(shapely.ops.split(g, cut)), key=lambda h: h.centroid.distance(Point(o_)))
                if len(parts) == 2 and 0.6 <= parts[0].area / AC <= 1.0:
                    R.at[i, 'geometry'] = parts[1]
                    R = pd.concat([R, gpd.GeoDataFrame(dict(use=['Ed P'], label=['Day Care / Nursery']), geometry=[parts[0]], crs=R.crs)], ignore_index=True)
                    log.append(('Day Care / Nursery', f'{parts[0].area / AC:.2f} ac carved from a large open space', 'Guidelines mandatory nursery')); break
            R = gpd.GeoDataFrame(R, geometry='geometry', crs=P.crs)
    # ---------- 7. S.A: every home within 500 m (Guidelines); each site on the lowest ground of the uncovered area, >= 60 m from school/health ----------
    sens = unary_union([SCH, HP, MK] + list(R.geometry[R.use.isin(['POS', 'Ed P', 'H Po'])]) + list(P.geometry[P.use.isin(['Ed P', 'H Po', 'POS'])])); sa_sites = []
    for _ in range(4):
        homes = P[P.use == 'RE']; pts = list(homes.geometry.centroid)
        dmax = np.array([min([g.distance(p) for g in sa_sites]) if sa_sites else 1e9 for p in pts]) * 0.3048
        if (dmax <= 500).all(): break
        unc = homes[dmax > 500]; zone = unc.geometry.union_all().convex_hull.buffer(300)
        c = R[(R.use.isin(['', 'GRN'])) & R.ac.between(0.12, 0.45) & (R.geometry.distance(sens) > 197) & R.geometry.intersects(zone) & (R.geometry.distance(MAIN) > 3) & (R.geometry.distance(CORR) > 3)].sort_values('elev')
        if len(c) and c.elev.iloc[0] <= unc.elev.quantile(0.25): sa_sites.append(take(c.index[0], 'SU', 'S.A', 'lowest ground of its area; every home within 500 m (Guidelines); learned S.A 0.28 ac'))
        else:
            cand = unc[(unc.geometry.distance(sens) > 197) & ~unc.main & ~unc.kor]
            if cand.empty: break
            cen = unc.geometry.union_all().centroid; cand = cand[cand.elev <= cand.elev.quantile(0.4)]
            grp = None
            for s_ in cand.geometry.distance(cen).sort_values().index:               # low ground, as central to the uncovered homes as possible
                g_ = chain_area(s_, 0.25)
                if unary_union(list(P.loc[g_].geometry)).distance(sens) > 197: grp = g_; break
            if grp is None: break
            sa_sites.append(assign_plots(grp, 'SU', 'S.A', 'low ground, central to the homes it serves, >= 60 m from school, health, market and play areas; every home within 500 m (Guidelines)'))
    # ---------- 9. corner shops on collector corners (1 per ~230 plots) ----------
    n_sh = max(1, round(nres0 / 230))
    cand = P[(P.use == 'RE') & (P.geometry.distance(COLLR) < 3) & ~P.main].copy()
    cand['corner'] = [g.buffer(3).intersection(RD['30 ft local road']).area for g in cand.geometry]
    for s in cand.sort_values('corner', ascending=False).index[:n_sh]: P.at[s, 'use'] = 'Com A'; P.at[s, 'label'] = 'Corner Shop'
    log.append(('Corner Shop', f'{n_sh} corner plot(s) on the collector', 'learned 1 per ~230 plots'))
    # ---------- 10. deep frontage plots on the 60 ft main road / 100 ft corridor (> 140 ft deep) -> mixed use (commercial below, residential above) ----------
    mu = [i for i in P.index[P.use == 'RE'] if mrr(P.geometry[i])[1] > 140 and (P.geometry[i].distance(MAIN) < 3 or P.geometry[i].distance(CORR) < 3)]
    P.loc[mu, 'use'] = 'MU'; P.loc[mu, 'label'] = ''
    log.append(('Mixed use frontage plots', f'{len(mu)} plots', 'deep plots on the major roads; Guidelines: mixed use / commercial along major roads'))
    # ---------- larger plots with roads front and back -> commercial (local plans put shops/commercial where plots face two roads) ----------
    nc = 0
    for i in P.index[P.use == 'RE']:
        ns = frontage_dirs(P.geometry[i])
        if any(float(ns[a] @ ns[b]) < -0.8 for a in range(len(ns)) for b in range(a + 1, len(ns))): P.at[i, 'use'] = 'Com A'; P.at[i, 'label'] = 'Commercial'; nc += 1
    log.append(('Commercial (plots with two road frontages)', f'{nc} plots', 'no residential double frontage'))
    # ---------- final check: residential plots with no road access join a neighbour ----------
    for i in list(P.index[P.use == 'RE']):
        if i not in P.index or frontage_dirs(P.geometry[i]): continue
        nb = P[(P.index != i) & (P.use == 'RE') & (P.geometry.buffer(1).intersection(P.geometry[i]).area > 20)]
        if nb.empty: continue
        j = max(nb.index, key=lambda j: P.geometry[j].buffer(1).intersection(P.geometry[i]).area); ug = unary_union([P.geometry[j], P.geometry[i]]).buffer(0.3).buffer(-0.3)
        if ug.geom_type == 'Polygon': P.at[j, 'geometry'] = ug; P.drop(index=i, inplace=True)
    # ---------- open spaces are scheme-sized (median 1.4 ac, at most 2.7 ac): a bigger one gets standard plots along its road edges ----------
    for i in list(R.index[R.use == 'POS']):
        g = R.geometry[i]
        if g.area / AC <= 2.7: continue
        newp, rest_ = plots_along_frontage(g)
        if not newp: continue
        P = gpd.GeoDataFrame(pd.concat([P, gpd.GeoDataFrame(dict(use=['RE'] * len(newp), label=[''] * len(newp), block=[-4000 - i] * len(newp), main=[q.distance(MAIN) < 3 for q in newp], kor=[False] * len(newp), elev=[elev(q) for q in newp]), geometry=newp, crs=P.crs)], ignore_index=True), geometry='geometry', crs=P.crs)
        R.at[i, 'geometry'] = rest_; R.at[i, 'ac'] = rest_.area / AC
        log.append(('Open space reduced to scheme size', f'{len(newp)} plots', f'{g.area / AC:.1f} ac open space: standard plots cut along its road edges, {rest_.area / AC:.1f} ac kept as P.O.S'))
    # ---------- no plot far below the Residential B minimum: a small one joins the neighbour it shares the longest edge with ----------
    for i in list(P.index[(P.use == 'RE') & (P.area < 0.6 * 6970)]):
        if i not in P.index: continue
        g = P.geometry[i]; nb = P[(P.index != i) & (P.use == 'RE') & (P.geometry.buffer(1).intersection(g).area > 20)]
        if nb.empty: P.at[i, 'use'] = 'GRN'; P.at[i, 'label'] = 'Landscaped green (island too small for a plot)'; continue
        j = max(nb.index, key=lambda j: P.geometry[j].buffer(1).intersection(g).area); ug = unary_union([P.geometry[j], g]).buffer(0.3).buffer(-0.3)
        if ug.geom_type == 'Polygon': P.at[j, 'geometry'] = ug; P.drop(index=i, inplace=True)
    # ---------- deep plots at sector edges (150-230 ft, one frontage) -> Residential A (larger lots, LUSPA zone) ----------
    ra = []                                              # Residential A as a ZONE: whole blocks whose plots are mostly deep, never single scattered plots
    for b_, grp_ in P[P.use == 'RE'].groupby('block'):
        deep_ = [i for i in grp_.index if 150 < mrr(P.geometry[i])[1] <= 235]
        if len(grp_) >= 3 and len(deep_) >= 0.6 * len(grp_): ra += list(grp_.index)
    P.loc[ra, 'use'] = 'RA'; P.loc[ra, 'label'] = ''
    log.append(('Residential A (larger lots at sector edges)', f'{len(ra)} plots', 'whole blocks of deep plots (150-230 ft) where grids meet curved tracks / the boundary'))
    # ---------- outputs ----------
    res = P[P.use.isin(['RE', 'RA'])]
    print('program (Manual 4.6.3):', program)
    print(f'plots {len(P)} | residential {len(res)} | population ~{len(res) * 7.2:.0f}')
    for l in log: print('  ', l)
    P.to_file(OUT + 'plots_landuse.gpkg'); R.to_file(OUT + 'reserves_landuse.gpkg')
    json.dump(dict(program=program, res_plots=len(res), log=log), open(OUT + 'allocate.json', 'w'), indent=1)
    COL = {'RA': '#c96a1a', 'MU': '#b5651d', 'CIV': '#c19bd8', 'TR': '#9a9a9a', 'RE': '#DC7C24', 'BM': '#73B2FF', 'Com A': '#73B2FF', 'PW': '#FF7F7F', 'H Po': '#FF0000', 'Ed P': '#FFFF00', 'POS': '#00FF00', 'SU': '#a0522d', 'GRN': '#b8f0b8'}
    r = rasterio.open(OUT + 'imagery_2136.tif'); a = np.moveaxis(r.read(), 0, -1); bb = r.bounds
    fig, ax = plt.subplots(figsize=(15, 14)); ax.imshow(a, extent=(bb.left, bb.right, bb.bottom, bb.top), alpha=.35)
    gpd.GeoSeries([SR]).plot(ax=ax, color='#2e8b57', alpha=.8)
    for cls in RD.index: gpd.GeoSeries([RD[cls]]).plot(ax=ax, color={'30 ft local road': '#e6e6e6', '40 ft collector': '#f5c242'}.get(cls, '#8c8c8c'))
    CNT = luspa_draw(ax, R, 'use', DESIGN_LUSPA, lw=.5, ec='k'); C2 = luspa_draw(ax, P, 'use', DESIGN_LUSPA, lw=.4, ec='k')
    for k_, v_ in C2.items(): CNT[k_] = CNT.get(k_, 0) + v_
    for g, l in list(zip(P.geometry, P.label)) + list(zip(R.geometry, R.label)):
        if l and l != 'Landscaped green':
            c_ = g.representative_point(); ax.text(c_.x, c_.y, l.replace('Neighbourhood Shopping Centre / Market', 'Market').replace(' (mixed use)', '').replace(' (Primary + JHS) and Nursery', '\n(Primary, JHS, Nursery)'), fontsize=7.5, ha='center', weight='bold')
    gpd.GeoSeries([SITE]).boundary.plot(ax=ax, color='yellow', lw=2)
    ax.legend(handles=luspa_handles(CNT) + [Patch(color='#2e8b57', label='Stream reserve (wooded)'), Patch(color='#8c8c8c', label='Main / existing roads'), Patch(color='#f5c242', label='40 ft collector'), Patch(color='#e6e6e6', label='30 ft local road')], loc='lower left', fontsize=9, title='LUSPA colour codes (Zoning Guidelines 2025)')
    x0, y0, x1, y1 = SITE.buffer(80).bounds; ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(NAME + f': {len(res)} residential plots, about {round(len(res) * 7.2, -1):,.0f} people', fontsize=14)
    plt.savefig(OUT + 'landuse_preview.png', bbox_inches='tight', dpi=80)

def st_design_audit(ctx):
    """Design audit: flaws with location and fix (guide section 8)."""
    WORK, SITE_KML, NAME = ctx['WORK'], ctx['SITE_KML'], ctx['NAME']
    """Design audit: run after every design. Lists each flaw with its location and a suggested fix, and draws them on a map.
    Usage: python design_audit.py <out_dir> [stage]   stage = roads | plots | landuse (default: whatever files exist)"""
    import sys, os, math, json, warnings, numpy as np, geopandas as gpd, pandas as pd, shapely, rasterio
    from shapely.geometry import Point, LineString
    from shapely.ops import unary_union
    from collections import defaultdict
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    warnings.filterwarnings('ignore')
    OUT = WORK; FT2M = 0.3048; AC = 43560
    RD = gpd.read_file(OUT + 'layout_roads.gpkg').set_index('Class').geometry
    CL = gpd.read_file(OUT + 'layout_centrelines.gpkg').geometry
    CONC = gpd.read_file(OUT + 'concept.gpkg').set_index('Part').geometry; S = CONC['Site']; S = max(shapely.get_parts(S), key=lambda g: g.area)
    WIDTH = {'100 ft road reserve': 100, '60 ft main road': 60, '40 ft collector': 40, '30 ft local road': 30}
    ROADS = RD.union_all()
    flaws = []
    def flaw(cat, sev, where, what, fix):
        p = where if isinstance(where, Point) else Point(where); flaws.append(dict(n=len(flaws) + 1, cat=cat, sev=sev, x=p.x, y=p.y, what=what, fix=fix))
    def mrr(g):
        c = list(g.minimum_rotated_rectangle.exterior.coords); return sorted([math.dist(c[0], c[1]), math.dist(c[1], c[2])])
    def road_class(pt):
        for c in ('100 ft road reserve', '60 ft main road', '60 ft existing road', '40 ft collector', '30 ft local road'):
            if c in RD.index and RD[c].buffer(0.5).contains(pt): return c
        return None
    # ================= ROADS =================
    segs = [x for x in shapely.get_parts(shapely.node(unary_union(list(CL)))) if x.length > 3]
    J = defaultdict(list)
    for x in segs:
        c = np.array(x.coords)
        for e, s_ in ((c[0], min(25, x.length / 2)), (c[-1], max(0, x.length - min(25, x.length / 2)))):
            nb = np.array(x.interpolate(s_).coords[0]); J[(round(e[0], 1), round(e[1], 1))].append((math.degrees(math.atan2(nb[1] - e[1], nb[0] - e[0])), x))
    nodes = {k: v for k, v in J.items()}
    for k, legs in nodes.items():
        if len(legs) < 3: continue
        a = sorted(l[0] % 360 for l in legs); g = min((a[(i + 1) % len(a)] - a[i]) % 360 for i in range(len(a)))
        if g < 80: flaw('Roads', 'high', k, f'junction angle {g:.0f} deg (< 80)', 'bend the approaching road in its last 100-150 ft so it meets square')
        if len(legs) > 4: flaw('Roads', 'high', k, f'{len(legs)}-way junction', 'separate the roads so no more than 4 legs meet')
        cls = set()
        for ang, x in legs:
            p = np.array(k) + np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))]) * 40; cls.add(road_class(Point(p)))
        cls.discard(None)
        if '30 ft local road' in cls and ({'60 ft main road', '60 ft existing road', '100 ft road reserve'} & cls):
            flaw('Roads', 'medium', k, 'hierarchy skip: 30 ft local road joins ' + ' / '.join(sorted({'60 ft main road', '60 ft existing road', '100 ft road reserve'} & cls)), 'route the local road to a 40 ft collector instead, or upgrade it to 40 ft')
    for k, legs in nodes.items():
        if len(legs) == 1 and Point(k).distance(S.exterior) > 10 and S.contains(Point(k)):
            L = legs[0][1].length * FT2M
            flaw('Roads', 'high' if L > 200 else 'low', k, f'dead end ({L:.0f} m)', 'connect it to the nearest road' if L > 200 else 'acceptable cul-de-sac (<= 200 m); give it a turning head')
    # staggered T junctions
    Ts = []
    for k, legs in nodes.items():
        if len(legs) != 3: continue
        v = [np.array([math.cos(math.radians(l[0])), math.sin(math.radians(l[0]))]) for l in legs]
        pr = min([(0, 1), (0, 2), (1, 2)], key=lambda ij: float(v[ij[0]] @ v[ij[1]])); br = [q for q in range(3) if q not in pr][0]
        Ts.append((np.array(k), v[pr[0]], np.sign(v[pr[0]][0] * v[br][1] - v[pr[0]][1] * v[br][0])))
    for i in range(len(Ts)):
        for j in range(i + 1, len(Ts)):
            pa, ta, sa = Ts[i]; pb, tb, sb = Ts[j]; d = pb - pa; dd = np.linalg.norm(d)
            if 10 < dd < 131 and abs(ta @ tb) > 0.95 and abs((d / dd) @ ta) > 0.95 and sa != sb:
                flaw('Roads', 'high', (pa + pb) / 2, f'staggered T junctions {dd * FT2M:.0f} m apart', 'align them into one 4-way junction or move them >= 40 m apart')
    # junction spacing on major roads
    import re as _re
    _wd = {c: float(_re.search(r'(\d+(?:\.\d+)?)\s*ft', c).group(1)) for c in RD.index if _re.search(r'(\d+(?:\.\d+)?)\s*ft', c)}
    _top = max(_wd.values()) if _wd else 0
    _checks = [(c, 305 if w == _top else 90) for c, w in sorted(_wd.items(), key=lambda t: -t[1]) if w == _top or w >= 60]   # the highest road (any width): entries >= 1,000 ft apart
    for cls_, min_m in _checks:
        if cls_ not in RD.index: continue
        zone = RD[cls_].buffer(3)
        js = [Point(k) for k, legs in nodes.items() if len(legs) >= 3 and zone.contains(Point(k))]
        axis = max(shapely.get_parts(shapely.line_merge(unary_union([x for x in segs if x.within(RD[cls_].buffer(1))]))), key=lambda g: g.length, default=None)
        if axis is None or len(js) < 2: continue
        ss = sorted(((axis.project(p), p) for p in js), key=lambda t: t[0])           # by position only (two junctions can share one)
        for (a, pa), (b, pb) in zip(ss, ss[1:]):
            if (b - a) * FT2M < 20: continue                                    # the two sides of one crossroads
            if (b - a) * FT2M < min_m: flaw('Roads', 'medium', Point((pa.x + pb.x) / 2, (pa.y + pb.y) / 2), f'entries onto the {cls_} only {(b - a) * FT2M:.0f} m apart (< {min_m} m)', 'run blocks parallel to this road and close one entry')
    # ================= BLOCKS =================
    if os.path.exists(OUT + 'layout_blocks.gpkg'):
        for b in gpd.read_file(OUT + 'layout_blocks.gpkg').geometry:
            w, l = mrr(b); c = b.representative_point()
            on_buffer = 'Stream reserve' in CONC.index and b.buffer(3).intersection(CONC['Stream reserve']).area > 0.25 * l * 3
            if l > 600 and on_buffer and w < 200: flaw('Blocks', 'low', c, f'plot row {l:.0f} ft long backing onto the stream buffer (local-plan pattern)', 'accepted; add footpath links to the buffer every ~8 plots')
            elif l > 600 and int(l // 70) > 8:
                LU2 = gpd.read_file(OUT + 'plots_landuse.gpkg') if os.path.exists(OUT + 'plots_landuse.gpkg') else None
                nonres = 0.0
                if LU2 is not None:
                    RS2 = gpd.read_file(OUT + 'reserves_landuse.gpkg')
                    nonres = (LU2[~LU2.use.isin(['RE', 'RA'])].intersection(b).area.sum() + RS2.intersection(b).area.sum()) / b.area
                if nonres < 0.15: flaw('Blocks', 'medium', c, f'block {l:.0f} ft long ({int(l // 70)} plots a row > 8)', 'add a cross road or footpath to break it')
            sides_on_road = b.exterior.intersection(ROADS.buffer(2)).length / b.exterior.length
            LU_ = gpd.read_file(OUT + 'plots_landuse.gpkg') if os.path.exists(OUT + 'plots_landuse.gpkg') else None
            res_in = LU_ is None or ((LU_.use == 'RE') & LU_.geometry.representative_point().within(b.buffer(1))).any()
            if w < 170 and sides_on_road > 0.85 and b.area > 8000 and not on_buffer and res_in: flaw('Blocks', 'high', c, f'single-row block {w:.0f} ft deep with roads all round', 'double-frontage risk: remove or move one of the roads so the block is 2 rows deep')
    # ================= PLOTS =================
    pf = OUT + 'plots_landuse.gpkg' if os.path.exists(OUT + 'plots_landuse.gpkg') else OUT + 'plots_final.gpkg'
    if os.path.exists(pf):
        PL = gpd.read_file(pf); res = PL[PL['use'].isin(['RE', 'RA'])] if 'use' in PL else PL.assign(use='RE')
        for g, u_ in zip(res.geometry, res['use']):
            c = g.representative_point(); w, d = mrr(g); a = g.area
            segs_ = np.array(g.exterior.simplify(1.5).coords); ns = []
            for p0, p1 in zip(segs_[:-1], segs_[1:]):
                L = np.linalg.norm(p1 - p0)
                if L < 25: continue
                m = (p0 + p1) / 2; t = (p1 - p0) / L; n = np.array([t[1], -t[0]])
                if g.contains(Point(m + n * 3)): n = -n
                if ROADS.contains(Point(m + n * 6)): ns.append(n)
            if any(float(ns[i] @ ns[j]) < -0.8 for i in range(len(ns)) for j in range(i + 1, len(ns))): flaw('Plots', 'high', c, 'double frontage (roads front and back)', 'change the road so the plot backs onto another plot')
            if not ns: flaw('Plots', 'high', c, 'no road access', 'give it frontage or merge it with a neighbour')
            if a < 6970 * 0.98: flaw('Plots', 'high', c, f'plot {a:,.0f} sq ft below the Residential B minimum (0.16 ac = 6,970 sq ft)', 'widen the frontage or merge with a neighbour')
            if a > (20000 if u_ == 'RA' else 12000): flaw('Plots', 'low', c, f'large residential plot {a:,.0f} sq ft', 'split if it has enough frontage')
            if w > 95: flaw('Plots', 'low', c, f'wide frontage ({w:.0f} ft) - standard is 70 ft', 'add a plot to the row')
            if d > (235 if u_ == 'RA' else 150): flaw('Plots', 'medium', c, f'deep plot ({d:.0f} ft)', 'block too deep: tighten the road spacing')
            if w < 55: flaw('Plots', 'medium', c, f'narrow frontage ({w:.0f} ft)', 'merge with a neighbour')
            if a / (w * d) < 0.7: flaw('Plots', 'low', c, f'irregular shape (fill {a / (w * d):.2f})', 'acceptable at bends/boundaries if >= 7,000 sq ft')
        rb = res[res['use'] == 'RE']; W_ = np.array([mrr(g)[0] for g in rb.geometry]); D_ = np.array([mrr(g)[1] for g in rb.geometry]); A_ = rb.area.values
        print(f'PLOT SIZES (Residential B {len(rb)}, plus {len(res) - len(rb)} Residential A): frontage median {np.median(W_):.0f} ft ({(abs(W_ - 70) <= 5).mean() * 100:.0f}% at 70 +/- 5), depth median {np.median(D_):.0f} ft ({((D_ >= 95) & (D_ <= 115)).mean() * 100:.0f}% 95-115), area median {np.median(A_):,.0f} sq ft, below 0.16 ac: {(A_ < 6970 * 0.98).sum()}')
    # ================= LAND USE =================
    if os.path.exists(OUT + 'plots_landuse.gpkg'):
        R = gpd.read_file(OUT + 'reserves_landuse.gpkg'); F = pd.concat([PL[PL.use != 'RE'][['label', 'geometry']], R[['label', 'geometry']]]); F = gpd.GeoDataFrame(F, geometry='geometry', crs=PL.crs)
        rng = {'School': (0.9, 3.0, 'learned school sites 0.9-3.0 ac'), 'Health': (0.5, 1.2, 'Guidelines min 0.5 ac; learned 0.63-1.05'), 'Worship': (0.55, 1.3, 'learned 0.68-1.21 ac'),
               'Market': (0.25, 1.6, 'learned 0.23-1.58 ac'), 'P.O.S': (0.4, 2.7, 'learned open space 0.5-2.7 ac'), 'S.A': (0.15, 0.6, 'learned 0.18-0.39 ac'), 'UT': (0.1, 0.4, 'learned 0.13-0.36 ac'),
               'Community': (0.5, 1.2, 'learned civic 0.65-1.13 ac'), 'Nursery': (0.5, 1.0, 'learned 0.65-0.97 ac'), 'Lorry': (0.4, 1.4, 'learned transport 0.41-1.41 ac')}
        for g, l in zip(F.geometry, F.label):
            for key, (lo, hi, why) in rng.items():
                if key in str(l):
                    if not (lo <= g.area / AC <= hi): flaw('Land use', 'medium', g.representative_point(), f'{l}: {g.area / AC:.2f} ac outside {lo}-{hi} ac', f'resize ({why})')
                    break
        sch = F[F.label.str.contains('School', na=False)].geometry.union_all()
        for g, l in zip(F.geometry, F.label):
            if ('P.O.S' in str(l) or 'green' in str(l).lower()) and g.buffer(1).intersection(sch).area > 30 and g.intersection(sch.buffer(1)).length >= 0:
                if g.distance(sch) < 1 and not g.buffer(2).intersection(sch).difference(ROADS).is_empty: flaw('Land use', 'high', g.representative_point(), f'{l} shares a boundary with the school (open space in school land)', 'separate by a road or merge into the school site')
        if not sch.is_empty and sch.distance(RD.get('100 ft road reserve', Point(0, 0))) < 3: flaw('Land use', 'medium', sch.representative_point(), 'school fronts the 100 ft road (pupil safety)', 'give the school its gate on a collector or local road')
        green = R[R.label.str.contains('green', case=False, na=False)]
        for g in green.geometry:
            if g.area / AC > 0.25: flaw('Land use', 'medium', g.representative_point(), f'undefined leftover land {g.area / AC:.2f} ac (landscaped green)', 'reshape roads/blocks so it becomes plots, or give it a defined use')
        if len(green): print(f'landscaped green total {green.area.sum() / AC:.2f} ac in {len(green)} pieces')
        pts = list(PL[PL.use.isin(['RE', 'RA'])].geometry.centroid)
        for key, lim, why in (('School', 800, 'learned: 90% of homes within ~720 m'), ('S\\.A', 500, 'Guidelines: within 500 m'), ('P\\.O\\.S', 400, 'within 400 m'), ('Health', 1200, 'learned p90 1.1 km')):
            f = F[F.label.str.contains(key, na=False)]
            if not len(pts): continue                                   # no homes on the site
            if f.empty and len(pts) < 60 and key in ('School', 'Health'): flaw('Land use', 'low', S.centroid, f'no {key} site: small site ({len(pts)} homes), served by the surrounding neighbourhood', 'confirm a school / health facility is within reach outside the site'); continue
            if f.empty: flaw('Land use', 'high', S.centroid, f'no {key.replace(chr(92), "")} site', 'add one'); continue
            d = np.array([f.geometry.distance(p).min() for p in pts]) * FT2M
            if d.max() > lim: far = pts[int(d.argmax())]; flaw('Land use', 'medium', far, f'{int((d > lim).sum())} homes more than {lim} m from a {key.replace(chr(92), "")} site (max {d.max():.0f} m)', why)
        sa = F[F.label.str.contains('S\\.A', na=False)].geometry
        sens = F[F.label.str.contains('School|Health|Nursery|Market|Play|P.O.S', na=False)]
        for g in sa:
            near = sens[sens.geometry.distance(g) * FT2M < 60]
            if len(near): flaw('Land use', 'high', g.representative_point(), 'S.A within 60 m of ' + ', '.join(sorted(set(near.label))), 'move the S.A away from schools, health, food and play areas')
            if g.distance(RD.get('60 ft main road', Point(0, 0))) < 3 or g.distance(RD.get('100 ft road reserve', Point(0, 0))) < 3: flaw('Land use', 'medium', g.representative_point(), 'S.A fronts a major road', 'place it on a local road')
        for g, l in zip(F.geometry, F.label):
            if any(k in str(l) for k in ('School', 'Worship', 'Health', 'Market', 'Community')):
                w_, l_ = mrr(g); fill = g.area / (w_ * l_)
                if fill < 0.8 or l_ / w_ > (3.2 if 'Market' in str(l) else 2.2): flaw('Land use', 'medium', g.representative_point(), f'{l}: irregular site (fill {fill:.2f}, {w_:.0f} x {l_:.0f} ft)', 'use a compact near-square parcel (learned: community sites are near-square, full block depth)')
    # ================= REPORT =================
    D = pd.DataFrame(flaws)
    order = {'high': 0, 'medium': 1, 'low': 2}
    print(f'\nDESIGN AUDIT: {len(D)} findings' + ('' if D.empty else ' | ' + ', '.join(f'{k} {v}' for k, v in D.sev.value_counts().items())))
    if not D.empty:
        D = D.sort_values(['sev', 'cat'], key=lambda c: c.map(order) if c.name == 'sev' else c).reset_index(drop=True); D['n'] = range(1, len(D) + 1)
        for r in D.itertuples(): print(f'  {r.n:>2}. [{r.sev:6s}] {r.cat:8s} {r.what}  ->  {r.fix}')
        D.to_csv(OUT + 'design_audit.csv', index=False)
    img = rasterio.open(OUT + 'imagery_2136.tif'); a = np.moveaxis(img.read(), 0, -1); bb = img.bounds
    fig, ax = plt.subplots(figsize=(15, 14)); ax.imshow(a, extent=(bb.left, bb.right, bb.bottom, bb.top), alpha=.35)
    colr = {'100 ft road reserve': '#5a5a5a', '60 ft main road': '#8c8c8c', '40 ft collector': '#f5c242', '30 ft local road': '#d9d9d9'}
    for c_, g in RD.items(): gpd.GeoSeries([g]).plot(ax=ax, color=colr.get(c_, '#ccc'))
    if os.path.exists(pf): gpd.read_file(pf).plot(ax=ax, color='#f3c99a', ec='k', lw=.3)
    elif os.path.exists(OUT + 'layout_blocks.gpkg'): gpd.read_file(OUT + 'layout_blocks.gpkg').plot(ax=ax, color='#f3c99a', ec='k', lw=.5)
    sc = {'high': 'red', 'medium': 'darkorange', 'low': 'royalblue'}
    if not D.empty:
        for r in D.itertuples():
            ax.plot(r.x, r.y, 'o', mfc='none', mec=sc[r.sev], ms=18, mew=2.5); ax.text(r.x + 25, r.y + 25, str(r.n), color=sc[r.sev], fontsize=10, weight='bold')
    gpd.GeoSeries([S]).boundary.plot(ax=ax, color='yellow', lw=2)
    x0, y0, x1, y1 = S.buffer(80).bounds; ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f'Design audit: {len(D)} findings (red high, orange medium, blue low)', fontsize=15)
    plt.savefig(OUT + 'design_audit.png', bbox_inches='tight', dpi=75)

def _walls_from_image(ctx, K):
    import numpy as np, geopandas as gpd, pandas as pd, rasterio, cv2, shapely, math
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union, transform as shp_transform, linemerge
    ctx = dict(ctx); ctx['_K'] = K
    _walls_body(ctx)


# =====================================================================================================================
# Command line
# =====================================================================================================================
EXISTING_FULL = [('fetch', st_fetch), ('sam', st_sam), ('digitize', st_digitize), ('compare', st_compare), ('clean', st_clean),
            ('database', st_database), ('roads', st_roads), ('landuse', st_landuse), ('reserves', st_reserves), ('trees', st_trees),
            ('blocks', st_blocks), ('plots', st_plots), ('map', st_map)]
EXISTING = EXISTING_FULL
EXISTING_FAST = [('fetch', st_fetch), ('footprints', st_footprints)] + EXISTING_FULL[6:]
OPTIONAL = {'footpaths': st_footpaths, 'proposals': st_proposals}
DESIGN = [('site', st_design_site), ('roads', st_design_roads), ('subdivide', st_design_subdivide), ('landuse', st_design_landuse), ('chamfer', st_design_chamfer), ('audit', st_design_audit)]
def pick_profile(ctx):
    if ctx.get('profile') in PROFILES: return ctx['profile']
    import geopandas as gpd
    f = ctx['D'] + ctx['PFX'] + 'Buildings.shp'
    thr = PROFILE_THRESHOLD_DB_M2 if ctx.get('buildings') == 'fast' else PROFILE_THRESHOLD_M2
    if not os.path.exists(f): return 'planned'
    med = float((gpd.read_file(f).area * FT * FT).median())
    p = 'compact' if med < thr else 'planned'
    print(f'   profile {p} (median building {med:.0f} m2, threshold {thr})'); return p
def make_ctx(a, workflow):
    site = os.path.abspath(a.site).replace('\\', '/'); name = a.name
    out = (a.out or os.path.join(os.path.dirname(site), f'{name} outputs')).replace('\\', '/').rstrip('/') + '/'
    work = out + '_work/'; os.makedirs(work, exist_ok=True); os.makedirs(work + 'tiles', exist_ok=True)
    ctx = dict(D=out, WORK=work, PFX=re.sub(r'\W+', '', name) + '_', SITE_KML=site, SAM_CKPT=SAM_CKPT_DEFAULT, NAME=name,
               TITLE=a.title or name, buildings=getattr(a, 'buildings', 'fast'), redo_blocks=[x for x in (getattr(a, 'blocks', None) or '').split(',') if x.strip()], rows=getattr(a, 'rows', 'auto'), wmin_m=getattr(a, 'wmin', None), wmax_m=getattr(a, 'wmax', None), split=getattr(a, 'split', 'evidence'), profile=getattr(a, 'profile', 'auto'), roads=getattr(a, 'roads', None), existing=getattr(a, 'existing', None), stream=getattr(a, 'stream', None),
               stream_buffer=getattr(a, 'stream_buffer', 0), steep_pct=getattr(a, 'steep_pct', 30), pattern=getattr(a, 'pattern', None), lock=getattr(a, 'lock', None), zones=getattr(a, 'zones', None), only_zones=getattr(a, 'only_zones', False), chamfer=bool(getattr(a, 'chamfer', False)), band=getattr(a, 'band', None), block_len=getattr(a, 'block_len', None), local_width=getattr(a, 'local_width', None), collector_width=getattr(a, 'collector_width', None), max_parcel_ac=getattr(a, 'max_parcel_ac', None), fp_min_w=0.6, fp_thr=0.0, workflow=workflow)
    json.dump({k: v for k, v in ctx.items()}, open(work + 'run.json', 'w'), indent=1)
    return ctx
def run(stages, ctx, a):
    names = [n for n, _ in stages]
    todo = names
    if a.only: todo = [n for n in a.only.split(',')]
    elif getattr(a, 'from_', None): todo = names[names.index(a.from_):]
    extra = [x for x in (getattr(a, 'with_', '') or '').split(',') if x]
    fns = dict(stages); fns.update(OPTIONAL)
    for n in todo + [x for x in extra if x not in todo]:
        if n not in fns: raise SystemExit(f'unknown stage {n}; stages: {names} + optional {list(OPTIONAL)}')
        t0 = time.time(); print(f'== {n}', flush=True); CUR_STAGE['name'] = n; progress(0)
        if n == 'plots': ctx['PROF'] = PROFILES[pick_profile(ctx)]
        fns[n](ctx); progress(100); print(f'   done in {time.time() - t0:.0f}s', flush=True)
        if ctx.get('stop'): break
def main():
    ap = argparse.ArgumentParser(description='LP Toolkit (see: python lp_toolkit.py guide)'); sub = ap.add_subparsers(dest='cmd', required=True)
    for c in ('existing', 'design'):
        p = sub.add_parser(c); p.add_argument('--site', required=True); p.add_argument('--name', required=True); p.add_argument('--title'); p.add_argument('--out')
        p.add_argument('--from', dest='from_'); p.add_argument('--only')
        p.add_argument('--imagery', choices=['google', 'esri'], default='google', help='satellite imagery source (the other one is the fallback)')
        if c == 'existing':
            p.add_argument('--profile', default='auto', choices=['auto', 'planned', 'compact']); p.add_argument('--with', dest='with_', default='')
            p.add_argument('--buildings', choices=['fast', 'full'], default='fast', help='fast: OSM + building database (minutes); full: + image detection with SAM (hours)')
            p.add_argument('--blocks', help='re-demarcate only these block ids (comma list) with --only plots,map')
            p.add_argument('--rows', choices=['auto', '1', '2'], default='auto'); p.add_argument('--wmin', type=float, help='min plot frontage m'); p.add_argument('--wmax', type=float, help='max plot frontage m')
            p.add_argument('--split', choices=['evidence', 'middle'], default='evidence', help='rear line: follow walls / gaps between buildings on the image, or the exact middle')
        else:
            p.add_argument('--roads', help='planner centrelines (width_ft) | auto | draft'); p.add_argument('--existing', help='existing roads to keep (auto/draft); default OSM'); p.add_argument('--stream'); p.add_argument('--stream-buffer', dest='stream_buffer', type=float, default=0); p.add_argument('--steep', dest='steep_pct', type=float, default=30, help='keep slopes >= this %% as green (0 = off)'); p.add_argument('--pattern', choices=['mixed', 'grid', 'curvilinear', 'all'], help='road pattern for auto / draft (default mixed: best per parcel)')
            p.add_argument('--lock', help='roads to keep exactly (planner-drawn / edited)'); p.add_argument('--zones', help='redesign areas (polygons, optional field pattern)')
            p.add_argument('--only-zones', dest='only_zones', action='store_true', help='new roads only inside the redesign areas')
            p.add_argument('--chamfer', action='store_true', help='corner truncations on corner plots (LUSPA 3.5 / 5 / 10 m by road class), plots and roads updated')
            p.add_argument('--band', type=float, help='block depth ft (default 200)'); p.add_argument('--block-len', dest='block_len', type=float, help='block length ft (default 490)')
            p.add_argument('--local-width', dest='local_width', type=float); p.add_argument('--collector-width', dest='collector_width', type=float); p.add_argument('--max-parcel-ac', dest='max_parcel_ac', type=float)
    p = sub.add_parser('db'); p.add_argument('--site', required=True); p.add_argument('--out')
    sub.add_parser('guide'); sub.add_parser('stages')
    a = ap.parse_args()
    if a.cmd == 'guide':
        open(os.path.join(TOOLKIT, 'LP_Toolkit_Guide.md'), 'w', encoding='utf-8').write(GUIDE); print(GUIDE); return
    if a.cmd == 'stages':
        print('existing (fast):', [n for n, _ in EXISTING_FAST]); print('existing (full, with SAM):', [n for n, _ in EXISTING_FULL], '+ optional', list(OPTIONAL)); print('design:', [n for n, _ in DESIGN]); return
    if a.cmd == 'db':
        import geopandas as gpd
        G = obm_load(gpd.read_file(a.site)); out = a.out or os.path.splitext(a.site)[0] + '_buildings_db.gpkg'; G.to_file(out)
        print(len(G), 'buildings ->', out, '| occupancy', G.occupancy.value_counts().head(8).to_dict()); return
    global IMAGERY_PREF
    IMAGERY_PREF = getattr(a, 'imagery', 'google') or 'google'; print('imagery preference:', IMAGERY_PREF)
    ctx = make_ctx(a, a.cmd); run((EXISTING_FAST if ctx.get('buildings') == 'fast' else EXISTING_FULL) if a.cmd == 'existing' else DESIGN, ctx, a)
if __name__ == '__main__':
    main()
