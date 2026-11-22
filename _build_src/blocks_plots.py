"""Test 5 existing situation: blocks (land between roads) and approximate existing plots (building-based partition of each block)."""
import numpy as np, geopandas as gpd, pandas as pd, shapely
from shapely.geometry import Point, Polygon, MultiPoint
from shapely.ops import unary_union
D = 'D:/Work/2026/Machine Learning/Test 5 outputs/'; FT = 0.3048
site = gpd.read_file('D:/Work/2026/Machine Learning/Test 5.kml').to_crs(2136).geometry.iloc[0]
R = gpd.read_file(D + 'Test5_Roads_existing.shp')
B = gpd.read_file(D + 'Test5_Existing_land_use_buildings.shp')
# ---------- roads: carriageway from the realigned centrelines; footways 2 m ----------
osm = gpd.read_file('ml5/osm_roads.gpkg'); fw = osm[osm.highway.isin(['footway', 'path'])]
import sys; sys.path.insert(0, 'ml4'); from road_surface import road_surface
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
BLK.to_file(D + 'Test5_Blocks_existing.shp'); PL[['plot_id', 'block_id', 'ex_use', 'n_bld', 'main_bld', 'area_m2', 'area_ac', 'frontage_m', 'depth_m', 'coverage', 'geometry']].to_file(D + 'Test5_Plots_existing.shp')
gpd.GeoDataFrame(geometry=[ROAD], crs=2136).to_file(D + 'Test5_Road_surface.shp')
print(f'blocks {len(BLK)} (median {BLK.area_m2.median():.0f} m2) | plots {len(PL)} (median {PL.area_m2.median():.0f} m2, {PL.frontage_m.median():.1f} x {PL.depth_m.median():.1f} m) | median plot coverage {PL.coverage.median()}')
print(PL.ex_use.value_counts().to_dict())
