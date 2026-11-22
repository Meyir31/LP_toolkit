p = 'webapp/app.py'; s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:80]; s = s.replace(a, b, 1)
# feature ids in every GeoJSON sent to the map
rep("    g = g.to_crs(4326)\n    for c in g.columns:", "    g = g.to_crs(4326); g['_fid'] = range(len(g))\n    for c in g.columns:")
rep("@app.post('/api/projects/<pid>/run')\ndef run(pid):", r'''# ------------------------------------------------------------------ generic feature editing (all result layers)
EDITABLE = {
    'existing': [('Plots / land use', '{O}/{P}Plots_existing.shp'), ('Buildings', '{O}/{P}Existing_land_use_buildings.shp'), ('Blocks', '{O}/{P}Blocks_existing.shp'),
                 ('Road surface', '{O}/{P}Road_surface.shp'), ('Road centrelines', '{O}/{P}Roads_existing.shp'), ('Walls / fences', '{O}/{P}Walls_final.shp'),
                 ('Vacant / open land', '{O}/{P}Vacant_open_land.shp'), ('Tree belt', '{O}/{P}Tree_belt_existing.shp')],
    'design': [('Roads (design)', 'roads.geojson'), ('Plots and land use', '{O}/_work/plots_landuse.gpkg'), ('Facility / green sites', '{O}/_work/reserves_landuse.gpkg'),
               ('Blocks', '{O}/_work/layout_blocks.gpkg'), ('Existing buildings', '{O}/_work/buildings.gpkg'), ('Existing roads to keep', 'existing.geojson'), ('Stream / drainage', 'stream.geojson')],
}
READONLY = {'area_m2', 'frontage_m', 'depth_m', 'coverage', 'n_bld', 'main_bld', 'length_m', 'area_ac', '_fid'}
def _edit_file(pid, rel):
    import geopandas as gpd
    f = safe(pid, rel); g = gpd.read_file(f)
    if g.crs is None: g = g.set_crs(4326 if f.endswith('.geojson') else 2136)
    return f, g
def _write(f, g):
    if f.endswith('.geojson'): g.to_crs(4326).to_file(f, driver='GeoJSON')
    else: g.to_file(f)
def _gkind(g):
    t = set(g.geom_type.dropna())
    return 'polygon' if t & {'Polygon', 'MultiPolygon'} else 'line' if t & {'LineString', 'MultiLineString'} else 'point'
@app.get('/api/projects/<pid>/edit/layers')
def edit_layers(pid):
    import geopandas as gpd
    m = meta(pid); O = os.path.basename(outdir(pid)); P_ = prefix(pid); d = pdir(pid); out = []
    for label, tpl in EDITABLE.get(m.get('workflow', 'design'), []):
        rel = tpl.format(O=O, P=P_)
        if not os.path.exists(os.path.join(d, rel)): continue
        try: g = gpd.read_file(os.path.join(d, rel), rows=50)
        except Exception: continue
        fields = [dict(name=c, type='number' if str(g[c].dtype).startswith(('int', 'float')) else 'text', readonly=c in READONLY) for c in g.columns if c != 'geometry']
        out.append(dict(label=label, path=rel, geom=_gkind(g) if len(g) else ('line' if 'road' in label.lower() or 'wall' in label.lower() or 'stream' in label.lower() else 'polygon'), fields=fields))
    return jsonify(out)
@app.get('/api/projects/<pid>/edit/feature')
def edit_feature(pid):
    f, g = _edit_file(pid, request.args.get('path', '')); i = int(request.args.get('fid'))
    one = g.iloc[[i]].to_crs(4326); one['_fid'] = [i]
    for c in one.columns:
        if c != 'geometry' and str(one[c].dtype).startswith(('datetime', 'object')): one[c] = one[c].astype(str)
    return jsonify(json.loads(one.to_json(drop_id=True)))
def _history(pid, rel):
    return os.path.join(pdir(pid), '_edit_history', re.sub(r'[^\w.-]+', '_', rel))
@app.post('/api/projects/<pid>/edit/op')
def edit_op(pid):
    """one editing operation on one layer: add, update_geom, update_attrs, delete, merge, split, reshape, undo"""
    import geopandas as gpd, pandas as pd, shapely
    from shapely.geometry import shape, LineString, Polygon
    from shapely.ops import unary_union, split as ssplit, polygonize, linemerge, substring
    from shapely import affinity as _aff
    j = request.get_json(force=True); rel = j.get('path', ''); op = j.get('op')
    hd = _history(pid, rel)
    if op == 'undo':
        hs = sorted(glob.glob(os.path.join(hd, '*.gpkg')))
        if not hs: return jsonify(error='nothing to undo on this layer'), 400
        f = safe(pid, rel); h = gpd.read_file(hs[-1]); _write(f, h); os.remove(hs[-1]); return jsonify(ok=True, left=len(hs) - 1)
    f, g = _edit_file(pid, rel); crs = g.crs
    to_g = lambda gj: gpd.GeoSeries([shape(gj)], crs=4326).to_crs(crs).iloc[0]
    fids = [int(x) for x in (j.get('fids') or [])]
    os.makedirs(hd, exist_ok=True); g.to_file(os.path.join(hd, time.strftime('%Y%m%d-%H%M%S-') + str(int(time.time() * 1000) % 1000) + '.gpkg'))
    for o in sorted(glob.glob(os.path.join(hd, '*.gpkg')))[:-40]: os.remove(o)
    changed = []
    def props_for(row_props):
        out = {}
        for k, v in (row_props or {}).items():
            if k not in g.columns or k in READONLY or k == 'geometry': continue
            if str(g[k].dtype).startswith(('int', 'float')):
                try: v = float(v) if v not in (None, '') else None
                except Exception: continue
            out[k] = v
        return out
    if op == 'add':
        geom = to_g(j['geometry']).buffer(0) if j['geometry']['type'] in ('Polygon', 'MultiPolygon') else to_g(j['geometry'])
        row = {c: None for c in g.columns if c != 'geometry'}; row.update(props_for(j.get('properties'))); row['geometry'] = geom
        if 'plot_id' in g.columns and 'block_id' in g.columns:
            blk = g[g.intersects(geom.representative_point().buffer(1))].block_id
            if len(blk): row['block_id'] = blk.iloc[0]; row['plot_id'] = next_id(g, blk.iloc[0])
        g = gpd.GeoDataFrame(pd.concat([g, gpd.GeoDataFrame([row], crs=crs)], ignore_index=True), crs=crs); changed = [len(g) - 1]
    elif op == 'update_geom':
        geom = to_g(j['geometry']); g.at[fids[0], 'geometry'] = geom.buffer(0) if geom.geom_type in ('Polygon', 'MultiPolygon') else geom; changed = fids[:1]
    elif op == 'update_attrs':
        pr = props_for(j.get('properties'))
        for i in fids:
            for k, v in pr.items(): g.at[i, k] = v
        changed = fids
    elif op == 'delete':
        g = g.drop(index=fids).reset_index(drop=True)
    elif op == 'merge':
        if len(fids) < 2: return jsonify(error='select two or more features to merge'), 400
        sub = g.loc[fids]; geom = unary_union(list(sub.geometry))
        if _gkind(g) == 'polygon':
            geom = geom.buffer(0.05).buffer(-0.05)
            if geom.geom_type != 'Polygon': return jsonify(error='the polygons must touch or overlap to merge'), 400
        else: geom = linemerge(geom) if geom.geom_type == 'MultiLineString' else geom
        keep = sub.geometry.area.idxmax() if _gkind(g) == 'polygon' else sub.geometry.length.idxmax()
        g.at[keep, 'geometry'] = geom; g = g.drop(index=[i for i in fids if i != keep]).reset_index(drop=True)
        changed = [int(sum(1 for i in range(keep) if i not in fids or i == keep) - 0)] if False else []
        changed = [list(g.geometry).index(geom)] if geom in list(g.geometry) else []
    elif op == 'split':
        line = to_g(j['geometry']); ext = _aff.scale(line, 1.02, 1.02)
        targets = fids or [i for i in g.index if g.geometry[i].intersects(line)]
        rows, drop = [], []
        for i in targets:
            geom = g.geometry[i]
            parts = [x for x in shapely.get_parts(ssplit(geom, ext)) if (x.area if _gkind(g) == 'polygon' else x.length) > 1e-6]
            if len(parts) < 2: continue
            parts.sort(key=lambda x: -(x.area if _gkind(g) == 'polygon' else x.length)); drop.append(i)
            for k, x in enumerate(parts):
                r_ = g.loc[i].copy(); r_['geometry'] = x
                if k and 'plot_id' in g.columns and 'block_id' in g.columns: r_['plot_id'] = next_id(pd.concat([g, pd.DataFrame(rows)]) if rows else g, g.block_id[i])
                rows.append(r_)
        if not drop: return jsonify(error='the line must cross the feature(s) from edge to edge'), 400
        g = gpd.GeoDataFrame(pd.concat([g.drop(index=drop), gpd.GeoDataFrame(rows, crs=crs)], ignore_index=True), crs=crs); changed = list(range(len(g) - len(rows), len(g)))
    elif op == 'reshape':
        line = to_g(j['geometry']); i = fids[0]; geom = g.geometry[i]
        if _gkind(g) == 'polygon':
            poly = max(shapely.get_parts(geom), key=lambda x: x.area) if geom.geom_type == 'MultiPolygon' else geom
            if len(shapely.get_parts(line.intersection(poly.boundary))) < 2: return jsonify(error='the reshape line must cross the outline at least twice'), 400
            mid = line.interpolate(0.5, normalized=True)
            if not poly.contains(mid):                                 # line goes out and back: add the area it encloses
                faces = [x for x in polygonize(unary_union([poly.boundary, line])) if not poly.contains(x.representative_point()) and x.boundary.intersection(line).length > 0]
                new = poly.union(unary_union(faces)) if faces else poly
            else:                                                      # line cuts across: keep the bigger part
                parts = list(shapely.get_parts(ssplit(poly, _aff.scale(line, 1.02, 1.02))))
                new = max(parts, key=lambda x: x.area) if len(parts) > 1 else poly
            g.at[i, 'geometry'] = new.buffer(0)
        else:
            ln = linemerge(geom) if geom.geom_type == 'MultiLineString' else geom
            if ln.geom_type != 'LineString': return jsonify(error='reshape works on single lines'), 400
            a, b = ln.project(shapely.geometry.Point(line.coords[0])), ln.project(shapely.geometry.Point(line.coords[-1]))
            sk = list(line.coords) if a <= b else list(line.coords)[::-1]; a, b = min(a, b), max(a, b)
            head = list(substring(ln, 0, a).coords) if a > 0 else []; tail = list(substring(ln, b, ln.length).coords) if b < ln.length else []
            g.at[i, 'geometry'] = LineString(head[:-1] + sk + tail[1:])
        changed = [i]
    else: return jsonify(error=f'unknown operation {op}'), 400
    # derived values
    if f.endswith('Plots_existing.shp') and changed: g = plot_attrs(pid, g, [c for c in changed if c < len(g)])
    FT_ = 0.3048
    if 'area_m2' in g.columns and str(crs).endswith('2136') and _gkind(g) == 'polygon' and not f.endswith('Plots_existing.shp'): g['area_m2'] = (g.area * FT_ * FT_).round(1)
    if 'length_m' in g.columns and str(crs).endswith('2136') and _gkind(g) == 'line': g['length_m'] = (g.length * FT_).round(1)
    _write(f, g)
    return jsonify(ok=True, features=len(g), changed=changed)
''' + "@app.post('/api/projects/<pid>/run')\ndef run(pid):")
open(p, 'w', encoding='utf-8').write(s); print('ok')
