p = 'webapp/app.py'; s = open(p, encoding='utf-8').read()
a = "@app.post('/api/projects/<pid>/run')\ndef run(pid):"
assert a in s
s = s.replace(a, '''# ------------------------------------------------------------------ existing plots: re-demarcate blocks, split / merge plots, undo
@app.post('/api/projects/<pid>/redemarcate')
def redemarcate(pid):
    if is_running(pid): return jsonify(error='already running'), 400
    j = request.get_json(force=True); blocks = [int(b) for b in j.get('blocks', [])]
    if not blocks: return jsonify(error='select the block(s) first'), 400
    m = meta(pid); backup_plots(pid)
    try: cmd = base_cmd(pid, 'existing')
    except ValueError as e: return jsonify(error=str(e)), 400
    cmd += ['--only', 'plots,map', '--profile', j.get('profile', 'auto'), '--buildings', m.get('buildings', 'fast'), '--blocks', ','.join(map(str, blocks)),
            '--rows', str(j.get('rows', 'auto')), '--split', j.get('split', 'evidence')]
    if j.get('wmin'): cmd += ['--wmin', str(j['wmin'])]
    if j.get('wmax'): cmd += ['--wmax', str(j['wmax'])]
    launch(pid, cmd); return jsonify(ok=True)
def plots_file(pid): return os.path.join(outdir(pid), prefix(pid) + 'Plots_existing.shp')
def backup_plots(pid):
    import geopandas as gpd
    f = plots_file(pid)
    if not os.path.exists(f): return
    bdir = os.path.join(pdir(pid), '_plot_history'); os.makedirs(bdir, exist_ok=True)
    gpd.read_file(f).to_file(os.path.join(bdir, time.strftime('%Y%m%d-%H%M%S') + '.gpkg'))
    old = sorted(glob.glob(os.path.join(bdir, '*.gpkg')))[:-30]
    for o in old: os.remove(o)
def plot_attrs(pid, P, idx):
    """area, frontage / depth, use, buildings, access for the plots in idx (EPSG:2136 ft)"""
    import geopandas as gpd, math
    FT = 0.3048; o = outdir(pid); pf = prefix(pid)
    B = gpd.read_file(os.path.join(o, pf + 'Existing_land_use_buildings.shp'))
    RS = gpd.read_file(os.path.join(o, pf + 'Road_surface.shp')).union_all().buffer(2 / FT)
    rp = B.representative_point()
    for i in idx:
        g = P.geometry[i]; inb = B[rp.within(g)]
        q = list(g.minimum_rotated_rectangle.exterior.coords); a_, b_ = sorted([math.dist(q[0], q[1]), math.dist(q[1], q[2])])
        P.at[i, 'area_m2'] = round(g.area * FT * FT); P.at[i, 'frontage_m'] = round(a_ * FT, 1); P.at[i, 'depth_m'] = round(b_ * FT, 1)
        P.at[i, 'n_bld'] = len(inb); P.at[i, 'coverage'] = round(inb.area.sum() / g.area, 2) if g.area else 0
        if len(inb): k = inb.area.idxmax(); P.at[i, 'ex_use'] = B.ex_use[k]; P.at[i, 'main_bld'] = int(B.bld_id[k])
        else: P.at[i, 'ex_use'] = 'Open / yard (no building)'; P.at[i, 'main_bld'] = None
        P.at[i, 'access'] = 'Road frontage' if g.intersects(RS) else 'Interior (access lane not mapped - verify)'
    return P
def next_id(P, blk):
    n = [int(str(x).split('-')[-1]) for x in P.plot_id[P.block_id == blk] if str(x).split('-')[-1].isdigit()]
    return f'{blk}-{(max(n) if n else 0) + 1}'
@app.post('/api/projects/<pid>/plots/split')
def plots_split(pid):
    """split plots with a drawn line: the selected plots, or every plot the line crosses"""
    import geopandas as gpd, pandas as pd, shapely
    from shapely.geometry import shape
    from shapely.ops import split as ssplit
    j = request.get_json(force=True); f = plots_file(pid)
    if not os.path.exists(f): return jsonify(error='no plots yet'), 400
    line = gpd.GeoSeries([shape(j['line'])], crs=4326).to_crs(2136).iloc[0]
    P = gpd.read_file(f); sel = set(j.get('plot_ids') or [])
    hit = [i for i in P.index if (P.plot_id[i] in sel if sel else True) and P.geometry[i].intersects(line)]
    if not hit: return jsonify(error='the line does not cross the selected plot(s)'), 400
    backup_plots(pid); new_rows, drop, changed = [], [], 0
    ext = shapely.affinity.scale(line, 1.02, 1.02)                      # a hair longer so it cuts edge to edge
    for i in hit:
        parts = [g for g in shapely.get_parts(ssplit(P.geometry[i], ext)) if g.area * 0.0929 > 5]
        if len(parts) < 2: continue
        parts.sort(key=lambda g: -g.area); drop.append(i); changed += 1
        for k, g in enumerate(parts):
            r_ = P.loc[i].copy(); r_['geometry'] = g
            if k: r_['plot_id'] = next_id(pd.concat([P, pd.DataFrame(new_rows)]) if new_rows else P, P.block_id[i])
            new_rows.append(r_)
    if not changed: return jsonify(error='the line must cross the plot from edge to edge'), 400
    P = gpd.GeoDataFrame(pd.concat([P.drop(index=drop), gpd.GeoDataFrame(new_rows, crs=P.crs)], ignore_index=True), crs=P.crs)
    P = plot_attrs(pid, P, list(range(len(P) - len(new_rows), len(P)))); P.to_file(f)
    return jsonify(ok=True, split=changed, plots=len(P))
@app.post('/api/projects/<pid>/plots/merge')
def plots_merge(pid):
    import geopandas as gpd, pandas as pd
    from shapely.ops import unary_union
    j = request.get_json(force=True); ids = list(j.get('plot_ids') or []); f = plots_file(pid)
    if len(ids) < 2: return jsonify(error='select two or more plots to merge'), 400
    P = gpd.read_file(f); sub = P[P.plot_id.isin(ids)]
    if sub.block_id.nunique() > 1: return jsonify(error='plots in different blocks (across a road) cannot be merged'), 400
    g = unary_union(list(sub.geometry)).buffer(0.05).buffer(-0.05)
    if g.geom_type != 'Polygon': return jsonify(error='the plots must touch each other'), 400
    backup_plots(pid); keep = sub.area.idxmax(); P.at[keep, 'geometry'] = g; P = P.drop(index=[i for i in sub.index if i != keep]).reset_index(drop=True)
    P = plot_attrs(pid, P, [int(P.index[P.plot_id == sub.plot_id[keep]][0])]); P.to_file(f)
    return jsonify(ok=True, plots=len(P))
@app.post('/api/projects/<pid>/plots/undo')
def plots_undo(pid):
    import geopandas as gpd
    hs = sorted(glob.glob(os.path.join(pdir(pid), '_plot_history', '*.gpkg')))
    if not hs: return jsonify(error='nothing to undo'), 400
    gpd.read_file(hs[-1]).to_file(plots_file(pid)); os.remove(hs[-1]); return jsonify(ok=True, left=len(hs) - 1)
''' + a)
open(p, 'w', encoding='utf-8').write(s); print('ok')
