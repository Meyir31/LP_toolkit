import re
def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:80]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
# ---------------- header: progress reporting ----------------
patch('toolkit_src/header.py', [("PROFILE_THRESHOLD_M2 = 70                            # median image-digitized building below this -> compact",
"""PROFILE_THRESHOLD_M2 = 70                            # median image-digitized building below this -> compact
PROFILE_THRESHOLD_DB_M2 = 56                         # same test on database / OSM footprints (they are drawn tighter: Osu 61, La 51)
CUR_STAGE = {'name': None}
def progress(pct, note=''):
    \"\"\"progress line for the web app: '@@progress <stage> <percent> <note>'\"\"\"
    print(f"@@progress {CUR_STAGE['name']} {max(0, min(100, pct)):.0f} {note}", flush=True)""")])
# ---------------- fetch progress + footprints stage ----------------
patch('toolkit_src/new_stages.py', [
 ("    r = rasterio.open(WORK + 'img_z19_3857.tif'); print('   imagery', r.shape, 'px at', round(r.res[0], 3), 'm', flush=True)",
  "    r = rasterio.open(WORK + 'img_z19_3857.tif'); print('   imagery', r.shape, 'px at', round(r.res[0], 3), 'm', flush=True); progress(55, 'imagery')"),
 ("    print(f'   OSM: {len(O)} buildings, {len(Rd)} road segments {Rd.highway.value_counts().to_dict()}, {len(Pp)} POIs')",
  "    print(f'   OSM: {len(O)} buildings, {len(Rd)} road segments {Rd.highway.value_counts().to_dict()}, {len(Pp)} POIs'); progress(70, 'OpenStreetMap')"),
 ("    M = gpd.GeoDataFrame(geometry=geoms, crs=4326).to_crs(2136); M = M[M.intersects(S.buffer(30))]; M.to_file(WORK + 'ms_buildings.gpkg'); print('   Microsoft footprints', len(M))",
  "    M = gpd.GeoDataFrame(geometry=geoms, crs=4326).to_crs(2136); M = M[M.intersects(S.buffer(30))]; M.to_file(WORK + 'ms_buildings.gpkg'); print('   Microsoft footprints', len(M)); progress(85, 'Microsoft')"),
])
s = open('toolkit_src/new_stages.py', encoding='utf-8').read()
s += '''
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
'''
open('toolkit_src/new_stages.py', 'w', encoding='utf-8').write(s)
# ---------------- cli: buildings route, progress, stage lists ----------------
patch('toolkit_src/cli.py', [
 ("EXISTING = [('fetch', st_fetch), ('sam', st_sam), ('digitize', st_digitize), ('compare', st_compare), ('clean', st_clean),\n            ('database', st_database), ('roads', st_roads),",
  "EXISTING_FULL = [('fetch', st_fetch), ('sam', st_sam), ('digitize', st_digitize), ('compare', st_compare), ('clean', st_clean),\n            ('database', st_database), ('roads', st_roads),"),
 ("OPTIONAL = {", "EXISTING = EXISTING_FULL\nEXISTING_FAST = [('fetch', st_fetch), ('footprints', st_footprints)] + EXISTING_FULL[6:]\nOPTIONAL = {"),
 ("    f = ctx['D'] + ctx['PFX'] + 'Buildings.shp'\n", "    f = ctx['D'] + ctx['PFX'] + 'Buildings.shp'\n    thr = PROFILE_THRESHOLD_DB_M2 if ctx.get('buildings') == 'fast' else PROFILE_THRESHOLD_M2\n"),
 ("    p = 'compact' if med < PROFILE_THRESHOLD_M2 else 'planned'\n    print(f'   profile {p} (median image-digitized building {med:.0f} m2, threshold {PROFILE_THRESHOLD_M2})'); return p",
  "    p = 'compact' if med < thr else 'planned'\n    print(f'   profile {p} (median building {med:.0f} m2, threshold {thr})'); return p"),
 ("        t0 = time.time(); print(f'== {n}', flush=True)", "        t0 = time.time(); print(f'== {n}', flush=True); CUR_STAGE['name'] = n; progress(0)"),
 ("        fns[n](ctx); print(f'   done in {time.time() - t0:.0f}s', flush=True)", "        fns[n](ctx); progress(100); print(f'   done in {time.time() - t0:.0f}s', flush=True)"),
 ("        if c == 'existing': p.add_argument('--profile', default='auto', choices=['auto', 'planned', 'compact']); p.add_argument('--with', dest='with_', default='')",
  "        if c == 'existing':\n            p.add_argument('--profile', default='auto', choices=['auto', 'planned', 'compact']); p.add_argument('--with', dest='with_', default='')\n            p.add_argument('--buildings', choices=['fast', 'full'], default='fast', help='fast: OSM + building database (minutes); full: + image detection with SAM (hours)')"),
 ("               TITLE=a.title or name,", "               TITLE=a.title or name, buildings=getattr(a, 'buildings', 'fast'),"),
 ("    ctx = make_ctx(a, a.cmd); run(EXISTING if a.cmd == 'existing' else DESIGN, ctx, a)",
  "    ctx = make_ctx(a, a.cmd); run((EXISTING_FAST if ctx.get('buildings') == 'fast' else EXISTING_FULL) if a.cmd == 'existing' else DESIGN, ctx, a)"),
 ("        print('existing:', [n for n, _ in EXISTING], '+ optional', list(OPTIONAL));", "        print('existing (fast):', [n for n, _ in EXISTING_FAST]); print('existing (full, with SAM):', [n for n, _ in EXISTING_FULL], '+ optional', list(OPTIONAL));"),
])
# ---------------- build.py: SAM only on tiles over the site, tile progress; walls helper from clean ----------------
patch('toolkit_src/build.py', [("add_existing('st_sam', ['ml5/sam_run.py'], 'Segment Anything masks over the image in 1024 px tiles (tiles already done are skipped).')",
"""def sam_fix(s):
    s = must(s, "jobs = [(y, x) for y in ys for x in xs]", "jobs = [(y, x) for y in ys for x in xs]\\nimport geopandas as _gpd\\nfrom shapely.geometry import box as _box\\n_S = _gpd.read_file(SITE_KML).to_crs(3857).geometry.iloc[0].buffer(30)\\n_n0 = len(jobs); jobs = [(y, x) for y, x in jobs if _box(*(T * (x, min(H, y + TS))), *(T * (min(W, x + TS), y))).intersects(_S)]\\nprint(f'tiles over the site: {len(jobs)} of {_n0}', flush=True)", 1, 'sam')
    s = must(s, "    if os.path.exists(out): continue", "    if os.path.exists(out): progress(100 * (k + 1) / len(jobs), f'tile {k + 1} of {len(jobs)}'); continue", 1, 'sam')
    s = must(s, "    print(f'tile {k + 1}/{len(jobs)} ({y0},{x0}): {len(masks)} masks, {time.time() - t0:.0f}s', flush=True)", "    print(f'tile {k + 1}/{len(jobs)} ({y0},{x0}): {len(masks)} masks, {time.time() - t0:.0f}s', flush=True); progress(100 * (k + 1) / len(jobs), f'tile {k + 1} of {len(jobs)}')", 1, 'sam')
    return s
add_existing('st_sam', ['ml5/sam_run.py'], 'Segment Anything masks over the image in 1024 px tiles over the site (tiles already done are skipped).', extra=sam_fix)
cl = rd('ml5/clean_t5.py'); w0 = cl.index('# ---------- 3. walls'); w1 = cl.index('with pd.ExcelWriter')
open(SP + 'toolkit_src/_walls.py', 'w', encoding='utf-8').write("import math, numpy as np, pandas as pd, geopandas as gpd, rasterio, cv2, shapely\nfrom shapely.geometry import LineString, Point\nfrom shapely.ops import unary_union, transform as shp_transform, linemerge\nK = ctx['_K']\nsite = gpd.read_file('D:/Work/2026/Machine Learning/Test 5.kml').to_crs(2136).geometry.iloc[0]\\n" + cl[w0:w1].replace("import walls as W_; import importlib\\n", ''))
add_existing('_walls_body', ['toolkit_src/_walls.py'], 'Walls / fences on the image, off roofs and roads (used by the fast footprints route).')""")])
s = open('toolkit_src/build.py', encoding='utf-8').read()
a = "full = rd('toolkit_src/header.py')"
assert a in s
s = s.replace(a, """stages.append('''def _walls_from_image(ctx, K):
    import numpy as np, geopandas as gpd, pandas as pd, rasterio, cv2, shapely, math
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union, transform as shp_transform, linemerge
    ctx = dict(ctx); ctx['_K'] = K
    _walls_body(ctx)

''')
""" + a, 1)
open('toolkit_src/build.py', 'w', encoding='utf-8').write(s)
print('ok')
