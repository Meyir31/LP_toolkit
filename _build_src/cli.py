
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
