"""Local update of a design after roads are drawn / edited: the new roads get their reserve surface, and only the blocks they
cross (or the land a removed road frees) are re-plotted by the planner's method. The rest of the plan, manual edits included, stays."""
import os, json, re
import numpy as np


def _w(props):
    for k in ('width_ft', 'reserve_ft'):
        try:
            v = float(props.get(k))
            if v > 0: return v
        except Exception: pass
    m = re.search(r'(\d+(?:\.\d+)?)\s*ft', str(props.get('class') or ''))
    return float(m.group(1)) if m else 30.0


def _class_name(w):
    return {30: '30 ft local road', 40: '40 ft collector', 60: '60 ft main road', 100: '100 ft road reserve'}.get(int(round(w)), f'{w:.0f} ft road')


def update(project_dir, work, log=print):
    import geopandas as gpd, pandas as pd, shapely, time as _tm
    _t0 = _tm.time(); TIMES = []
    from shapely.geometry import shape, LineString
    from shapely.ops import unary_union
    from localplots import subdivide_blocks
    AC = 43560.0
    fp, fr, fc, fl = (work + f for f in ('plots_landuse.gpkg', 'reserves_landuse.gpkg', 'layout_centrelines.gpkg', 'layout_roads.gpkg'))
    if not all(os.path.exists(f) for f in (fp, fc, fl)): return dict(ok=False, msg='no plan yet: run the design first')
    # current roads (planner's design roads + existing roads to keep)
    cur = []
    for k in ('roads', 'existing'):
        f = os.path.join(project_dir, f'{k}.geojson')
        if not os.path.exists(f): continue
        for ft in json.load(open(f, encoding='utf-8')).get('features', []):
            g = ft.get('geometry')
            if g and g.get('type') in ('LineString', 'MultiLineString'): cur.append((shape(g), _w(ft.get('properties') or {})))
    if not cur: return dict(ok=False, msg='no roads')
    C = gpd.GeoDataFrame(dict(w=[w for _, w in cur]), geometry=[g for g, _ in cur], crs=4326).to_crs(2136)
    sf = os.path.join(project_dir, 'site.geojson')                       # the plan covers the site only: roads are compared inside it
    if os.path.exists(sf):
        S_ = gpd.read_file(sf).to_crs(2136).union_all().buffer(5); C['geometry'] = C.geometry.intersection(S_)
    C = C.explode(index_parts=False).reset_index(drop=True); C = C[(C.geom_type == 'LineString') & (C.length > 5)]
    OLD = gpd.read_file(fc); RD = gpd.read_file(fl)
    TIMES.append(('read', round(_tm.time() - _t0, 1)))
    snap = os.path.join(project_dir, '_plan_roads')                      # the drawn roads the plan was made from (exact comparison)
    exact = os.path.isdir(snap) and any(os.path.exists(os.path.join(snap, f'{k}.geojson')) for k in ('roads', 'existing'))
    if exact:
        prev = []
        for k in ('roads', 'existing'):
            f = os.path.join(snap, f'{k}.geojson')
            if os.path.exists(f):
                for ft in json.load(open(f, encoding='utf-8')).get('features', []):
                    g = ft.get('geometry')
                    if g and g.get('type') in ('LineString', 'MultiLineString'): prev.append((shape(g), _w(ft.get('properties') or {})))
        PV = gpd.GeoDataFrame(dict(width_ft=[w for _, w in prev]), geometry=[g for g, _ in prev], crs=4326).to_crs(2136) if prev else OLD.iloc[:0]
        if os.path.exists(sf) and len(PV): PV['geometry'] = PV.geometry.intersection(S_)
        OLD_CMP = PV
    else: OLD_CMP = OLD                                                 # older plan: compare with its centrelines, additions only
    oldU, curU = OLD_CMP.union_all(), C.union_all()
    OB, CB = oldU.buffer(8, quad_segs=2), curU.buffer(8, quad_segs=2)          # buffered once (8 ft tolerance)
    # new pieces of road (not in the plan) and removed pieces (in the plan, no longer drawn)
    added = []
    min_len = 50 if exact else 150                                     # no record of the plan's roads: only whole new roads count (not small mismatches)
    for g, w in zip(C.geometry, C.w):
        for q in shapely.get_parts(g.difference(OB)):          # 8 ft / 50 ft: small differences at road ends and joins are not changes
            if q.geom_type == 'LineString' and q.length > min_len: added.append((q, w))
    removed = []
    for g, w in (zip(OLD_CMP.geometry, OLD_CMP.width_ft) if exact else []):
        for q in shapely.get_parts(g.difference(CB)):
            if q.geom_type == 'LineString' and q.length > 50: removed.append((q, w))
    TIMES.append(('diff', round(_tm.time() - _t0, 1)))
    if not added and not removed: return dict(ok=True, msg='the plan already matches the roads', plots=0)
    OTHERS = unary_union([g for g in C.geometry])
    def band(l, w):                                                        # reserve band; an end that stops in open land is carried half a width on,
        c = np.array(l.coords)[:, :2]; u0 = c[0] - c[1]; u1 = c[-1] - c[-2]  # an end on another road stops at its centreline (no overshoot past the far kerb)
        u0 = u0 / (np.linalg.norm(u0) + 1e-9); u1 = u1 / (np.linalg.norm(u1) + 1e-9)
        others = OTHERS.difference(l.buffer(1))
        e0 = 0 if others.distance(shapely.Point(c[0])) < 3 else w / 2; e1 = 0 if others.distance(shapely.Point(c[-1])) < 3 else w / 2
        ext = LineString([tuple(c[0] + u0 * e0)] + [tuple(x) for x in c] + [tuple(c[-1] + u1 * e1)])
        return ext.buffer(w / 2, cap_style=2)
    chg = unary_union([l for l, _ in added] + [l for l, _ in removed]); WIN = chg.buffer(700).envelope       # work only around the change
    RS0 = unary_union([g.intersection(WIN) for g in RD.geometry])
    add_res = unary_union([band(l, w) for l, w in added]) if added else shapely.Polygon()
    near_ = [(g, w) for g, w in zip(C.geometry, C.w) if g.intersects(WIN)]
    keep_lines = unary_union([g.buffer(w / 2, cap_style=2) for g, w in near_]) if near_ else shapely.Polygon()   # reserves of every road still drawn
    rem_res = unary_union([band(l, w) for l, w in removed]).difference(keep_lines) if removed else shapely.Polygon()
    rem_res = rem_res.intersection(RS0) if not rem_res.is_empty else rem_res
    RS = RS0.difference(rem_res.buffer(0.05)).union(add_res) if not rem_res.is_empty else RS0.union(add_res)
    if added:                                                           # kerb returns where the new roads meet others (15 ft radius)
        J = unary_union([shapely.Point(l.coords[k]).buffer(70) for l, _ in added for k in (0, -1)] + [l.intersection(OTHERS.difference(l.buffer(1))).buffer(70) for l, _ in added])
        fil = RS.intersection(J).buffer(15, quad_segs=6).buffer(-15, quad_segs=6)
        FIL = fil.difference(RS); add_res = add_res.union(FIL); RS = RS.union(fil)
    else: FIL = shapely.Polygon()
    touched = add_res.union(rem_res).buffer(1)
    TIMES.append(('surface', round(_tm.time() - _t0, 1)))
    # plots: residential plots the change touches are re-plotted; other uses (facilities) are only cut by the new road
    P = gpd.read_file(fp); R = gpd.read_file(fr) if os.path.exists(fr) else None
    hit = P.geometry.intersects(touched)
    RESU = ['RE', 'RA', 'MU']
    if os.path.exists(work + 'layout_blocks.gpkg'):                      # whole blocks the change touches are re-plotted, not only the plots under the road
        BLK = gpd.read_file(work + 'layout_blocks.gpkg'); BLK = BLK[BLK.intersects(touched)]
        BU = unary_union([b.buffer(3) for b in BLK.geometry]) if len(BLK) else None                    # buffered once
        inblk = P.geometry.representative_point().within(BU) if BU is not None else hit & False
        res_hit = P[(hit | inblk) & P.use.isin(RESU)]
    else: res_hit = P[hit & P.use.isin(RESU)]
    oth_hit = P[hit & ~P.use.isin(RESU)]
    region = unary_union(list(res_hit.geometry) + ([rem_res] if not rem_res.is_empty else []))
    region = region.difference(RS.buffer(0.05)) if not region.is_empty else region
    blocks = [q for q in shapely.get_parts(region) if q.geom_type == 'Polygon' and q.area > 2000]
    plots, spare = subdivide_blocks(blocks, RS) if blocks else ([], [])
    TIMES.append(('subdivide', round(_tm.time() - _t0, 1)))
    for i in oth_hit.index:                                                # facility plots: cut by the road, largest piece keeps the use
        g = P.geometry[i].difference(add_res.buffer(0.05))
        P.at[i, 'geometry'] = max(shapely.get_parts(g), key=lambda q: q.area) if not g.is_empty else g
    P = P.drop(index=res_hit.index)
    use_of = lambda q: (res_hit[res_hit.geometry.intersects(q.buffer(-1))].assign(a=lambda d: d.geometry.intersection(q).area).sort_values('a').use.iloc[-1]
                        if len(res_hit[res_hit.geometry.intersects(q.buffer(-1))]) else 'RE')
    newp = gpd.GeoDataFrame(dict(block=[-9000 - k for k in range(len(plots))], how=[h for _, h in plots], use=[use_of(q) for q, _ in plots], label=[''] * len(plots)),
                            geometry=[q for q, _ in plots], crs=P.crs)
    newp['area'] = newp.area
    P = gpd.GeoDataFrame(pd.concat([P, newp], ignore_index=True), crs=P.crs)
    P = P[~P.geometry.is_empty & (P.area > 500)].reset_index(drop=True); P['area'] = P.area
    if 'chamfered' in P: P['chamfered'] = P['chamfered'].fillna(0)
    P.to_file(fp)
    TIMES.append(('plots written', round(_tm.time() - _t0, 1)))
    if R is not None and len(R):
        R['geometry'] = [g.difference(add_res.buffer(0.05)) if g.intersects(add_res) else g for g in R.geometry]
        R = R[~R.geometry.is_empty]; R['geometry'] = [max(shapely.get_parts(g), key=lambda q: q.area) if g.geom_type != 'Polygon' else g for g in R.geometry]
        if spare:
            S_ = gpd.GeoDataFrame(dict(use=['GRN'] * len(spare), label=['Landscaped green'] * len(spare)), geometry=spare, crs=R.crs); R = gpd.GeoDataFrame(pd.concat([R, S_], ignore_index=True), crs=R.crs)
        R.to_file(fr)
    # road reserves (by class) and centrelines
    for l, w in added:
        name = _class_name(w); g = band(l, w)
        if name in set(RD.Class): k = RD.index[RD.Class == name][0]; RD.at[k, 'geometry'] = RD.geometry[k].union(g)
        else: RD = gpd.GeoDataFrame(pd.concat([RD, gpd.GeoDataFrame(dict(Class=[name]), geometry=[g], crs=RD.crs)], ignore_index=True), crs=RD.crs)
    if added and not FIL.is_empty:                                       # the kerb returns belong to the new road's reserve
        name = _class_name(added[0][1]); k = RD.index[RD.Class == name][0]; RD.at[k, 'geometry'] = RD.geometry[k].union(FIL)
    if not rem_res.is_empty: RD['geometry'] = [g.difference(rem_res.buffer(0.05)) for g in RD.geometry]
    RD.to_file(fl)
    TIMES.append(('roads written', round(_tm.time() - _t0, 1)))
    CL = OLD                                                           # centrelines: the plan's, minus removed pieces, plus the new ones
    if removed: CL['geometry'] = [g.difference(unary_union([l.buffer(8) for l, _ in removed])) for g in CL.geometry]; CL = CL[~CL.geometry.is_empty]
    if added: CL = gpd.GeoDataFrame(pd.concat([CL, gpd.GeoDataFrame(dict(width_ft=[w for _, w in added]), geometry=[l for l, _ in added], crs=2136)], ignore_index=True), crs=2136)
    CL.to_file(fc)
    import shutil
    os.makedirs(snap, exist_ok=True)                                     # the plan now matches the drawn roads
    for k in ('roads', 'existing'):
        f = os.path.join(project_dir, f'{k}.geojson')
        if os.path.exists(f): shutil.copy2(f, os.path.join(snap, f'{k}.geojson'))
    msg = f'{len(added)} new road piece(s), {len(removed)} removed: {len(res_hit)} plots re-plotted into {len(newp)} in {len(blocks)} block(s)'
    log('local update: ' + msg)
    return dict(times=TIMES, ok=True, msg=msg, plots=len(newp), blocks=len(blocks), added=len(added), removed=len(removed))
