p = 'toolkit_src/autoroads.py'; s = open(p, encoding='utf-8').read()
def rep(a, b, n=1):
    global s
    assert s.count(a) >= 1, a[:70]; s = s.replace(a, b, n)
rep("PATTERNS = {'grid': 'Grid iron',", "PATTERNS = {'mixed': 'Blended (best pattern per parcel)', 'grid': 'Grid iron',")
rep("def auto_roads(S, existing, stream_poly=None, buildings=None, log=print, terrain=None, pattern='grid'):",
    "def auto_roads(S, existing, stream_poly=None, buildings=None, log=print, terrain=None, pattern='mixed', zones=None, only_zones=False):")
rep('''    """S: site polygon (EPSG:2136 ft); existing: [(LineString, width_ft)]; returns [(LineString, width_ft, kind)]"""''',
    '''    """S: site polygon (EPSG:2136 ft); existing: [(LineString, width_ft[, kind])] (kind 'locked' = planner's roads, kept exactly);
    zones: [(Polygon, pattern)] redesign areas; only_zones: new roads only inside the zones. Returns [(LineString, width_ft, kind)]"""
    zones = zones or []
    ZU = None
    if zones:
        from shapely.ops import unary_union as _uu
        ZU = _uu([z for z, _ in zones])
    def zone_of(sec):
        best = None
        for z, pt in zones:
            a = z.intersection(sec).area
            if a > 0.4 * sec.area and (best is None or a > best[0]): best = (a, pt or 'mixed')
        return None if best is None else best[1]''')
rep("""    for l, w in existing:
        g = l.intersection(S.buffer(w))""", """    for it in existing:
        l, w = it[0], it[1]; kind = it[2] if len(it) > 2 else 'existing'
        if kind == 'locked':                                              # planner's roads: kept exactly as drawn
            ex.append((l, w)); out.append((l, w, 'locked')); continue
        g = l.intersection(S.buffer(w))""")
rep("ray = LineString([tuple(p), tuple(p + d * 3000)]); others = unary_union([o for o, _ in existing if o is not l] + [S.exterior])",
    "ray = LineString([tuple(p), tuple(p + d * 3000)]); others = unary_union([o[0] for o in existing if o[0] is not l] + [S.exterior])")
rep("            ex.append((LineString(c), w)); out.append((LineString(c), w, 'existing'))", "            ex.append((LineString(c), w)); out.append((LineString(c), w, kind))")
# collectors only inside redesign zones when only_zones
rep("""        for sec in sectors:
            if sec.area / 43560 <= AUTO['max_sector_ac']: continue""", """        if only_zones and ZU is not None: sectors = [q for g in sectors for q in shapely.get_parts(g.intersection(ZU)) if q.geom_type == 'Polygon' and q.area > 43560]
        for sec in sectors:
            if sec.area / 43560 <= AUTO['max_sector_ac']: continue""")
rep("""    sectors = [g for g in shapely.get_parts(S.difference(blocked)) if g.area > 30000]
    bld = unary_union""", """    sectors = [g for g in shapely.get_parts(S.difference(blocked)) if g.area > 30000]
    if only_zones and ZU is not None: sectors = [q for g in sectors for q in shapely.get_parts(g.intersection(ZU)) if q.geom_type == 'Polygon' and q.area > 30000]
    bld = unary_union""")
rep("""        best = None
        def options():
            if pattern == 'curvilinear':""", """        best = None
        pat = zone_of(sec) or pattern
        def options(pattern):
            if pattern == 'mixed':
                for pt in ('grid', 'curvilinear', 'ringband'): yield from options(pt)
                return
            if pattern == 'curvilinear':""")
rep("        for w, rows, crosses in options():", "        for w, rows, crosses in options(pat):")
# ---- st_design_autoroads: lock, zones, parameters, single design by default ----
rep("""    elif os.path.exists(WORK + 'osm_roads.gpkg'):""", """    if ctx.get('lock'):                                                   # roads the planner keeps (drawn / edited / outside a redesign area)
        Lk = gpd.read_file(ctx['lock']).to_crs(2136); Lk['geometry'] = Lk.geometry.force_2d()
        for _, r_ in Lk.explode(index_parts=False).iterrows():
            if r_.geometry.geom_type == 'LineString': existing.append((r_.geometry, _width_of(r_), 'locked'))
        print(f'   kept roads (locked): {len(Lk)}')
    if ctx.get('existing') or ctx.get('lock'): pass
    elif os.path.exists(WORK + 'osm_roads.gpkg'):""")
rep("""    if ctx.get('existing'):
        E = gpd.read_file(ctx['existing'])""", """    if ctx.get('existing') and not ctx.get('lock'):
        E = gpd.read_file(ctx['existing'])""")
rep("""    pat = (ctx.get('pattern') or ('all' if (ctx.get('roads') or '').lower() == 'draft' else 'grid')).lower()""",
    """    pat = (ctx.get('pattern') or 'mixed').lower()
    zones = []
    if ctx.get('zones'):
        Zg = gpd.read_file(ctx['zones']).to_crs(2136)
        for _, z in Zg.iterrows():
            if z.geometry is not None and z.geometry.geom_type in ('Polygon', 'MultiPolygon'): zones.append((shapely.force_2d(z.geometry), (z.get('pattern') or pat)))
        print(f'   redesign areas: {len(zones)} ({", ".join(PATTERNS.get(p_, p_) for _, p_ in zones)})')
    saved = dict(AUTO)
    for k, ck in (('band', 'band'), ('block_len', 'block_len'), ('local', 'local_width'), ('collector', 'collector_width'), ('max_sector_ac', 'max_parcel_ac')):
        if ctx.get(ck): AUTO[k] = float(ctx[ck])
    print(f"   parameters: block depth {AUTO['band']:.0f} ft, block length {AUTO['block_len']:.0f} ft, local roads {AUTO['local']:.0f} ft, collectors {AUTO['collector']:.0f} ft, parcels up to {AUTO['max_sector_ac']:.0f} ac")""")
rep("        L = auto_roads(S, existing, stream, bld, log=print, terrain=terrain, pattern=pt)",
    "        L = auto_roads(S, existing, stream, bld, log=print, terrain=terrain, pattern=pt, zones=zones, only_zones=bool(ctx.get('only_zones')))")
rep("        new = [l for l, w, k in L if k != 'existing']", "        new = [l for l, w, k in L if k not in ('existing', 'locked')]")
rep("        for k, c_, lw in (('existing', 'black', 3.5), ('collector', '#f5a142', 2.6), ('local', '#1f5fd1', 1.3)):",
    "        for k, c_, lw in (('existing', 'black', 3.5), ('locked', '#7b1fa2', 2.2), ('collector', '#f5a142', 2.6), ('local', '#1f5fd1', 1.3)):")
rep("    if len(pats) == 1: ctx['roads'] = WORK + 'auto_roads.gpkg'", "    AUTO.clear(); AUTO.update(saved)\n    if len(pats) == 1: ctx['roads'] = WORK + 'auto_roads.gpkg'")
open(p, 'w', encoding='utf-8').write(s)
# ---- CLI ----
p = 'toolkit_src/cli.py'; s = open(p, encoding='utf-8').read()
a = "p.add_argument('--pattern', choices=['grid', 'curvilinear', 'ringband', 'all'], help='road pattern for auto / draft (draft default: all three)')"
assert a in s
s = s.replace(a, """p.add_argument('--pattern', choices=['mixed', 'grid', 'curvilinear', 'ringband', 'all'], help='road pattern for auto / draft (default mixed: best per parcel)')
            p.add_argument('--lock', help='roads to keep exactly (planner-drawn / edited)'); p.add_argument('--zones', help='redesign areas (polygons, optional field pattern)')
            p.add_argument('--only-zones', dest='only_zones', action='store_true', help='new roads only inside the redesign areas')
            p.add_argument('--band', type=float, help='block depth ft (default 200)'); p.add_argument('--block-len', dest='block_len', type=float, help='block length ft (default 490)')
            p.add_argument('--local-width', dest='local_width', type=float); p.add_argument('--collector-width', dest='collector_width', type=float); p.add_argument('--max-parcel-ac', dest='max_parcel_ac', type=float)""")
s = s.replace("pattern=getattr(a, 'pattern', None),", "pattern=getattr(a, 'pattern', None), lock=getattr(a, 'lock', None), zones=getattr(a, 'zones', None), only_zones=getattr(a, 'only_zones', False), band=getattr(a, 'band', None), block_len=getattr(a, 'block_len', None), local_width=getattr(a, 'local_width', None), collector_width=getattr(a, 'collector_width', None), max_parcel_ac=getattr(a, 'max_parcel_ac', None),")
open(p, 'w', encoding='utf-8').write(s)
print('ok')
