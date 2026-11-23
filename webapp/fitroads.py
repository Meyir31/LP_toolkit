"""Fit the roads to the located facilities, slightly (user 2026-11-23): around each located facility (exact outline)
1. designed roads running through it are trimmed back to its edge (the planner's own roads and existing roads never move: reported);
2. a short designed road running alongside it less than about a plot deep away is shifted onto its edge (no thin strip left);
3. sides without road frontage get a road along them;
4. road ends left loose by the trimming are joined to that edge road.
Then only the blocks these changes touch are re-plotted (localupdate) and the plots inside the outline become the facility."""
import os, json, math, time


def fit(project_dir, work, toolkit, log=print):
    import geopandas as gpd, pandas as pd, numpy as np, shapely
    from shapely.geometry import shape, mapping, LineString, Point
    from shapely.ops import unary_union, nearest_points
    rf = os.path.join(project_dir, 'roads.geojson'); sf = os.path.join(project_dir, 'facility_sites.geojson')
    if not os.path.exists(sf): return dict(ok=False, msg='no located facilities yet')
    if not os.path.exists(rf): return dict(ok=False, msg='no roads yet: design the roads first')
    ctx = dict(facilities=os.path.join(project_dir, 'facilities.json'), facility_sites=sf)
    blocks = list(gpd.read_file(work + 'layout_blocks.gpkg').to_crs(2136).geometry) if os.path.exists(work + 'layout_blocks.gpkg') else None
    SITES = toolkit.facility_site_shapes(ctx, blocks)
    if not SITES: return dict(ok=False, msg='no located facilities yet')
    R = gpd.read_file(rf)
    if R.empty: return dict(ok=False, msg='no roads yet')
    R = R.to_crs(2136); R['geometry'] = R.geometry.force_2d()
    if 'width_ft' not in R: R['width_ft'] = 30.0
    R['width_ft'] = pd.to_numeric(R['width_ft'], errors='coerce').fillna(30.0)
    if 'locked' not in R: R['locked'] = False
    mine = R['locked'].astype(str).str.lower().isin(['true', '1'])
    EX = gpd.read_file(os.path.join(project_dir, 'existing.geojson')).to_crs(2136) if os.path.exists(os.path.join(project_dir, 'existing.geojson')) else None
    exU = unary_union([g.buffer(float(w or 40) / 2) for g, w in zip(EX.geometry, EX.get('width_ft', pd.Series([40] * len(EX))))]) if EX is not None and len(EX) else None
    st = dict(trimmed=0, shifted=0, edge_roads=0, joined=0, blocked=[])
    rows = [dict(r) for _, r in R.iterrows()]
    for x in SITES:
        site = x['geometry']; nm = x['name']
        if site is None or site.is_empty: continue
        Lw = 30.0
        # 1. trim designed roads through the site
        out = []
        for r in rows:
            g = r['geometry']; w = float(r.get('width_ft') or 30)
            inside = g.intersection(site.buffer(-2)).length if g is not None else 0
            if inside <= 5: out.append(r); continue
            if str(r.get('locked')).lower() in ('true', '1'): st['blocked'].append(f'{nm}: one of your roads crosses it'); out.append(r); continue
            cut = g.difference(site.buffer(w / 2 + 0.5)); st['trimmed'] += 1
            for q in shapely.get_parts(cut):
                if q.geom_type == 'LineString' and q.length > 30: out.append(dict(r, geometry=q, _cut=True))
        rows = out
        if exU is not None and exU.intersection(site.buffer(-2)).area > 50: st['blocked'].append(f'{nm}: an existing road crosses it')
        # 2. a short designed road alongside the site, less than a plot deep away: shift it onto the site edge
        for k, r in enumerate(rows):
            g = r['geometry']
            if str(r.get('locked')).lower() in ('true', '1') or g.length > 2.5 * math.sqrt(site.area) + 200: continue
            w = float(r.get('width_ft') or 30); d = g.distance(site)
            if not (w / 2 + 5 < d < w / 2 + 100): continue
            p_site, p_road = nearest_points(site, g)
            near_len = g.intersection(site.buffer(w / 2 + 110)).length
            if near_len < 0.5 * g.length: continue
            v = np.array(p_site.coords[0]) - np.array(p_road.coords[0]); L_ = np.linalg.norm(v)
            if L_ < 1e-6: continue
            mv = v / L_ * (d - (w / 2 + 0.5))
            g2 = shapely.affinity.translate(g, mv[0], mv[1])
            if g2.intersection(site.buffer(-2)).length > 5: continue
            rows[k] = dict(r, geometry=g2); st['shifted'] += 1
        # 3. road along every side without frontage
        allR = unary_union([r['geometry'].buffer(float(r.get('width_ft') or 30) / 2 + Lw / 2) for r in rows] + ([exU.buffer(Lw / 2)] if exU is not None else []))
        ring = site.buffer(Lw / 2 + 0.5, join_style=2).exterior
        S_ = gpd.read_file(os.path.join(project_dir, 'site.geojson')).to_crs(2136).union_all()
        need = ring.difference(allR).intersection(S_.buffer(-Lw / 2))
        need = shapely.line_merge(need) if need.geom_type == 'MultiLineString' else need
        new_edges = []
        for q in shapely.get_parts(need):
            if q.geom_type == 'LineString' and q.length > 60:
                a, b = Point(q.coords[0]), Point(q.coords[-1]); c = list(q.coords)
                ends_ = unary_union([r['geometry'] for r in rows] + ([EX.union_all()] if EX is not None and len(EX) else []))
                for at_end, p_ in ((False, a), (True, b)):                       # carry each end on to the road it reaches (ring corner -> nearest road)
                    hp = nearest_points(ends_, p_)[0]
                    if p_.distance(hp) < Lw * 1.5: c = (c + [tuple(hp.coords[0])]) if at_end else ([tuple(hp.coords[0])] + c)
                new_edges.append(LineString(c))
        for q in new_edges:
            rows.append(dict(geometry=q, width_ft=Lw, locked=False, kind='fit')); st['edge_roads'] += 1
        # 4. loose ends of trimmed roads joined to the edge roads / ring
        ringU = unary_union(new_edges + [ring]) if new_edges else ring
        others = lambda k: unary_union([r['geometry'] for j, r in enumerate(rows) if j != k] + ([EX.union_all()] if EX is not None and len(EX) else []))
        for k, r in enumerate(rows):
            if not r.get('_cut'): continue
            g = r['geometry']; c = list(g.coords); changed = False
            for at_end in (True, False):
                p_ = Point(c[-1] if at_end else c[0])
                if p_.distance(site) > Lw / 2 + 40: continue
                if others(k).distance(p_) < 3: continue
                hp = nearest_points(ringU, p_)[0]
                if p_.distance(hp) < 80: c = (c + [tuple(hp.coords[0])]) if at_end else ([tuple(hp.coords[0])] + c); changed = True
            if changed: rows[k] = dict(r, geometry=LineString(c)); st['joined'] += 1
    # write the roads (one undo step on the roads layer) and re-plot only the touched blocks
    hd = os.path.join(project_dir, '_edit_history', 'roads.geojson'); os.makedirs(hd, exist_ok=True)
    gpd.read_file(rf).to_file(os.path.join(hd, time.strftime('%Y%m%d-%H%M%S-') + str(int(time.time() * 1000) % 1000) + '.gpkg'))
    keep = [c for c in R.columns if c not in ('geometry',)]
    G = gpd.GeoDataFrame([{c: r.get(c) for c in keep + ['kind']} for r in rows], geometry=[r['geometry'] for r in rows], crs=2136)
    G['locked'] = G['locked'].astype(str).str.lower().isin(['true', '1']); G.to_crs(4326).to_file(rf, driver='GeoJSON')
    import localupdate
    lu = localupdate.update(project_dir, work, log=log)
    # the plots inside each located facility become that facility (one site)
    fp = work + 'plots_landuse.gpkg'; applied = 0
    if os.path.exists(fp):
        P = gpd.read_file(fp); crs_ = P.crs; P = P.to_crs(2136)
        for x in SITES:
            site = x['geometry']; ix = list(P.index[P.geometry.representative_point().within(site.buffer(2))])
            if not ix: continue
            u = unary_union(list(P.loc[ix].geometry)).buffer(0.5).buffer(-0.5)
            if u.geom_type != 'Polygon': u = max(shapely.get_parts(u), key=lambda q: q.area)
            k0 = ix[0]; P.at[k0, 'geometry'] = u; P.at[k0, 'use'] = x['use']; P.at[k0, 'label'] = x['name']
            if 'kind' in P: P.at[k0, 'kind'] = 'site'
            P = P.drop(index=ix[1:]); applied += 1
        P = P.reset_index(drop=True); P['area'] = P.area; P.to_crs(crs_).to_file(fp)
    st.update(ok=True, sites=len(SITES), facilities_applied=applied, local_update=lu.get('msg') if isinstance(lu, dict) else str(lu))
    return st
