"""Assemble LP_Toolkit/lp_toolkit.py from the validated working scripts (ml3 design, ml4/ml5 existing) + hand-written parts."""
import re, os, sys
SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\', '/') + '/'
SRC = SP + 'toolkit_src/'; OUT = 'D:/Work/2026/Machine Learning/LP_Toolkit/lp_toolkit.py'
rd = lambda p: open(SP + p, encoding='utf-8').read()
def must(s, old, new, count=None, name=''):
    n = s.count(old)
    if n == 0 or (count is not None and n != count): raise SystemExit(f'[{name}] expected {count or ">=1"} x {old[:70]!r}, found {n}')
    return s.replace(old, new)
def existing_subs(s, t, name):
    """paths of Test <t> -> run context"""
    s = s.replace(f"'D:/Work/2026/Machine Learning/Test {t} outputs/'", 'D')
    s = s.replace(f"'D:/Work/2026/Machine Learning/Test {t}.kml'", 'SITE_KML')
    s = s.replace(f"f'ml{t}/tiles/t_{{y0}}_{{x0}}.pkl'", "WORK + f'tiles/t_{y0}_{x0}.pkl'")
    s = s.replace("'ml4/models/sam_vit_b_01ec64.pth'", 'SAM_CKPT')
    s = re.sub(rf"'Test{t}_", "PFX + '", s)
    s = re.sub(rf"'ml{t}/", "WORK + '", s)
    left = re.findall(rf"Test ?{t}|ml{t}/|'ml4'", s)
    return s, left
def strip_imports_of_helpers(s, name):
    s = re.sub(r"^sys\.path\.insert\(0, 'ml4'\); from classify import [^\n]*\n", '', s, flags=re.M)
    s = re.sub(r"^sys\.path\.insert\(0, 'ml4'\); from walls import detect_walls\n", '', s, flags=re.M)
    s = re.sub(r"^sys\.path\.insert\(0, 'ml4'\); import obm\n", '', s, flags=re.M)
    s = re.sub(r"^import walls as W_; import importlib\n", '', s, flags=re.M)
    s = re.sub(r"^import sys; sys\.path\.insert\(0, 'ml4'\); from road_surface import road_surface\n", '', s, flags=re.M)
    return s
def wrap(fname, body, doc, keys=('D', 'PFX', 'WORK', 'SITE_KML', 'SAM_CKPT', 'TITLE', 'NAME')):
    head = f'def {fname}(ctx):\n    """{doc}"""\n    ' + ', '.join(keys) + ' = ' + ', '.join(f"ctx['{k}']" for k in keys) + '\n'
    lines = body.rstrip('\n').split('\n')
    return head + '\n'.join(('    ' + l) if l.strip() else '' for l in lines) + '\n\n'
stages = []
def add_existing(fname, files, doc, t=5, extra=None, keys=None):
    body = ''
    for f in files:
        s = strip_imports_of_helpers(rd(f), f)
        s, left = existing_subs(s, t, f)
        if extra: s = extra(s)
        s = re.sub(rf'Test ?{t}', 'the site', s)                       # remaining mentions in comments / docstrings
        left = [x for x in re.findall(rf"Test ?{t}\b|ml{t}/|'ml4'", s)]
        if left: raise SystemExit(f'[{f}] unreplaced: {set(left)}')
        body += s + '\n'
    stages.append(wrap(fname, body, doc, keys or ('D', 'PFX', 'WORK', 'SITE_KML', 'SAM_CKPT', 'TITLE', 'NAME')))
# ---------------- existing workflow ----------------
def sam_fix(s):
    s = must(s, "jobs = [(y, x) for y in ys for x in xs]", "jobs = [(y, x) for y in ys for x in xs]\nimport geopandas as _gpd\nfrom shapely.geometry import box as _box\n_S = _gpd.read_file(SITE_KML).to_crs(3857).geometry.iloc[0].buffer(30)\n_n0 = len(jobs); jobs = [(y, x) for y, x in jobs if _box(*(T * (x, min(H, y + TS))), *(T * (min(W, x + TS), y))).intersects(_S)]\nprint(f'tiles over the site: {len(jobs)} of {_n0}', flush=True)", 1, 'sam')
    s = must(s, "    if os.path.exists(out): continue", "    if os.path.exists(out): progress(100 * (k + 1) / len(jobs), f'tile {k + 1} of {len(jobs)}'); continue", 1, 'sam')
    s = must(s, "    print(f'tile {k + 1}/{len(jobs)} ({y0},{x0}): {len(masks)} masks, {time.time() - t0:.0f}s', flush=True)", "    print(f'tile {k + 1}/{len(jobs)} ({y0},{x0}): {len(masks)} masks, {time.time() - t0:.0f}s', flush=True); progress(100 * (k + 1) / len(jobs), f'tile {k + 1} of {len(jobs)}')", 1, 'sam')
    return s
add_existing('st_sam', ['ml5/sam_run.py'], 'Segment Anything masks over the image in 1024 px tiles over the site (tiles already done are skipped).', extra=sam_fix)
cl = rd('ml5/clean_t5.py'); w0 = cl.index('# ---------- 3. walls'); w1 = cl.index('with pd.ExcelWriter')
WALLS_HEAD = ["import math, numpy as np, pandas as pd, geopandas as gpd, rasterio, cv2, shapely",
              "from shapely.geometry import LineString, Point",
              "from shapely.ops import unary_union, transform as shp_transform, linemerge",
              "K = ctx['_K']",
              "site = gpd.read_file('D:/Work/2026/Machine Learning/Test 5.kml').to_crs(2136).geometry.iloc[0]", ""]
open(SP + 'toolkit_src/_walls.py', 'w', encoding='utf-8').write('\n'.join(WALLS_HEAD) + cl[w0:w1].replace("import walls as W_; import importlib\n", ''))
add_existing('_walls_body', ['toolkit_src/_walls.py'], 'Walls / fences on the image, off roofs and roads (used by the fast footprints route).')
add_existing('st_digitize', ['ml5/assemble_t5.py'], 'Masks -> classified building / foundation footprints and wall lines.')
add_existing('st_compare', ['ml5/compare_t5.py'], 'Check footprints against OSM + Microsoft and correct the shapes.')
add_existing('st_clean', ['ml5/feat_final.py', 'ml5/clean_t5.py'], 'Drop false detections, flag foundations, final walls.')
def obm_fix(s):
    s = s.replace('(ml4/obm.py)', '(obm_load)').replace('usage: obm_merge.py <test number>', '')
    s = must(s, "t = int(sys.argv[1]); FT = 0.3048\n", "FT = 0.3048\n", 1, 'obm')
    s = must(s, "D = f'D:/Work/2026/Machine Learning/Test {t} outputs/'; P = f'Test{t}_'\n", "P = PFX\n", 1, 'obm')
    s = must(s, "site_g = gpd.read_file(f'D:/Work/2026/Machine Learning/Test {t}.kml')", "site_g = gpd.read_file(SITE_KML)", 1, 'obm')
    s = must(s, "rasterio.open(f'ml{t}/img_z19_3857.tif')", "rasterio.open(WORK + 'img_z19_3857.tif')", 1, 'obm')
    s = must(s, "G = obm.load(site_g)", "G = obm_load(site_g)", 1, 'obm')
    return s
add_existing('st_database', ['ml4/obm_merge.py'], 'Check / correct footprints against the building database; attach occupancy and height.', t=4, extra=obm_fix)
add_existing('st_roads', ['ml5/road_widths.py'], 'Carriageway widths measured on the image; walls on the carriageway removed.')
add_existing('st_landuse', ['ml5/plan_existing.py'], 'Road reserves, existing use per building (OSM tag > database occupancy > rules), vacant land.')
add_existing('st_reserves', ['ml5/pinch_v2.py'], 'Centrelines realigned to the image; reserves re-measured; pinch points.')
add_existing('st_trees', ['ml5/trees_t5.py'], 'Continuous tree belt / drain corridor from the image.')
add_existing('st_blocks', ['ml5/blocks_plots.py'], 'Road surface (T-branch ends trimmed to the crossing road) and blocks.')
def prof(s):
    s = must(s, "WMIN, WMAX, STEP = 9 / FT, 18 / FT, 1 / FT", "WMIN, WMAX, STEP = PROF['wmin'] / FT, PROF['wmax'] / FT, 1 / FT", 1, 'plots')
    s = must(s, "if depth < 30 / FT: rows = [blk]", "if depth < PROF['single_row'] / FT: rows = [blk]", None, 'plots')
    s = must(s, "if g.area * FT * FT < 500 or dep < 36 / FT or big", "if g.area * FT * FT < PROF['recut_area'] or dep < PROF['recut_depth'] / FT or big", 1, 'plots')
    s = must(s, "def halve_deep(bid, g, depth_max=40 / FT):", "def halve_deep(bid, g, depth_max=PROF['halve_depth'] / FT):", 1, 'plots')
    s = re.sub(r"^n0 = len\(pieces\)", "n0 = len(pieces)", s, flags=re.M)
    # ---- re-demarcation of selected blocks, row / frontage options, rear line from image evidence ----
    s = must(s, "WMIN, WMAX, STEP = PROF['wmin'] / FT, PROF['wmax'] / FT, 1 / FT", """WMIN, WMAX, STEP = float(ctx.get('wmin_m') or PROF['wmin']) / FT, float(ctx.get('wmax_m') or PROF['wmax']) / FT, 1 / FT
REDO = [int(x) for x in (ctx.get('redo_blocks') or [])]
if REDO: BLK = BLK[BLK.block_id.isin(REDO)].reset_index(drop=True); print(f'   re-demarcating blocks {REDO}', flush=True)
WT = shapely.STRtree(list(W.geometry)) if len(W) else None
def split_cost(ln, BUb, off):
    \"\"\"cost of a rear (row) line: building length it cuts, minus walls / fences running along it (seen on the image), mild pull to the middle\"\"\"
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
    PL.to_file(D + PFX + 'Plots_existing.shp')""", 1, 'plots')
    s = must(s, "if depth < PROF['single_row'] / FT: rows = [blk]", "if ctx.get('rows') == '1' or (ctx.get('rows') != '2' and depth < PROF['single_row'] / FT): rows = [blk]", None, 'plots')
    s = must(s, "            cst = (ln.intersection(BUb).length if BUb is not None else 0) + abs(off) * 0.05", "            cst = split_cost(ln, BUb, off)", None, 'plots')
    s = must(s, "    rows = two_side_rows(blk) if width >= 40 / FT else None", "    rows = None if ctx.get('rows') == '1' else (two_side_rows(blk) if (width >= 40 / FT or ctx.get('rows') == '2') else None)", 1, 'plots')
    s = must(s, "    if not rows: rows = [[blk, max(frontage_pieces(blk), key=lambda f: f.length)]] if width < 40 / FT else rows_by_frontage(blk)", "    if not rows: rows = [[blk, max(frontage_pieces(blk), key=lambda f: f.length)]] if (width < 40 / FT or ctx.get('rows') == '1') else rows_by_frontage(blk)", 1, 'plots')
    s = must(s, "PL.to_file(D + PFX + 'Plots_existing.shp');", "save_plots(PL);", 1, 'plots')
    # service / utility sites (OSM outlines) are taken out of the blocks whole, before the subdivision
    s = must(s, "for bid, blk0 in zip(BLK.block_id, BLK.geometry):", """SITES = gpd.read_file(WORK + 'osm_sites.gpkg') if os.path.exists(WORK + 'osm_sites.gpkg') else None
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
for bid, blk0 in zip(BLK.block_id, BLK.geometry):""", 1, 'plots')
    s = must(s, "PL = gpd.GeoDataFrame(dict(block_id=[p[0] for p in pieces]), geometry=[p[1] for p in pieces], crs=2136)",
             "pieces += [(sp[0], sp[1]) for sp in SITE_PIECES]\nPL = gpd.GeoDataFrame(dict(block_id=[p[0] for p in pieces]), geometry=[p[1] for p in pieces], crs=2136)", 1, 'plots')
    s = must(s, "PL['ex_use'], PL['main_bld'], PL['n_bld'], PL['use_guess'], PL['use_conf'] = uses, mbs, nbs, guess, conf", """PL['ex_use'], PL['main_bld'], PL['n_bld'], PL['use_guess'], PL['use_conf'] = uses, mbs, nbs, guess, conf
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
if drop_: PL = PL.drop(index=list(drop_)).reset_index(drop=True); print(f'   service plots merged into whole sites: {len(drop_)} plot lines removed', flush=True)""", 1, 'plots')
    return s
add_existing('st_plots', ['ml5/plots_v6.py'], 'Existing plots by the halving rule (guide section 4); profile from ctx.', extra=prof,
             keys=('D', 'PFX', 'WORK', 'SITE_KML', 'SAM_CKPT', 'TITLE', 'NAME', 'PROF'))
def title(s):
    return must(s, "f'Test 5 (La) - existing land use:", "TITLE + f' - existing land use:", 1, 'map')
def map_extra(s): return s
mp = rd('ml5/landuse_map.py'); mp = must(mp, "f'Test 5 (La) - existing land use (LUSPA colour codes):", "TITLE + f' - existing land use (LUSPA colour codes):", 1, 'map')
open(SP + 'toolkit_src/_map.py', 'w', encoding='utf-8').write(mp)
add_existing('st_map', ['toolkit_src/_map.py'], 'Existing land use map (legend outside the frame) and tables.')
def fp(s):
    s, n1 = re.subn(r"^MIN_W = .*$", "MIN_W = ctx.get('fp_min_w', 0.6) / FT", s, flags=re.M)
    s, n2 = re.subn(r"^THR = .*$", "THR = ctx.get('fp_thr', 0.0)", s, flags=re.M)
    if n1 != n2: raise SystemExit(f'[fp] MIN_W {n1} THR {n2}')
    s = s.replace("PFX + 'Footpaths.shp'", "PFX + 'Footpaths_TRIAL_not_reliable.shp'")
    return s
fpv = rd('ml5/fp_preview.py').replace("D + 'Test5_Footpaths.shp'", "D + 'Test5_Footpaths_TRIAL_not_reliable.shp'")
open(SP + 'toolkit_src/_fpv.py', 'w', encoding='utf-8').write(fpv)
add_existing('st_footpaths', ['ml5/footpaths.py', 'toolkit_src/_fpv.py'], 'OPTIONAL TRIAL: footpaths from the open space between buildings (not reliable in dense cores).', extra=fp)
def props(s):
    s = must(s, "POP = 20000 ", "POP = int(round(B[B.ex_use == 'Residential'].area.sum() * FT * FT * 1.5 / 60 * 3.4, -2)) ", 1, 'prop')
    s = must(s, "ax.set_title(f'Test 4 (Osu) upgrading plan", "ax.set_title(TITLE + f' upgrading plan", 1, 'prop')
    return s
pp = rd('ml4/plan_proposals.py'); pp = must(pp, "ax.set_title(f'Test 4 (Osu) upgrading plan", "ax.set_title(TITLE + f' upgrading plan", 1, 'prop')
pp = must(pp, "POP = 20000 ", "POP = int(round(B[B.ex_use == 'Residential'].area.sum() * FT * FT * 1.5 / 60 * 3.4, -2)) ", 1, 'prop')
pp = pp.replace("PFX_PLACEHOLDER", "")
open(SP + 'toolkit_src/_prop.py', 'w', encoding='utf-8').write(pp)
add_existing('st_proposals', ['toolkit_src/_prop.py'], 'OPTIONAL: upgrading proposals (only when proposals are asked for).', t=4)
# ---------------- design workflow ----------------
def design(fname, f, doc, extra=None):
    s = rd(f)
    s = s.replace("OUT = 'ml3/'", 'OUT = WORK').replace("OUT = sys.argv[1]", 'OUT = WORK')
    s = s.replace("'D:/Work/2026/Machine Learning/Test 3.kml'", 'SITE_KML')
    s = s.replace("f'Test 3: ", "NAME + f': ").replace("'Test 3: ", "NAME + ': ")
    if extra: s = extra(s)
    s = re.sub(r'Test [23]', 'the site', s)
    left = re.findall(r"ml3/|Test 3", s)
    if left: raise SystemExit(f'[{f}] unreplaced: {set(left)}')
    stages.append(wrap(fname, s, doc, ('WORK', 'SITE_KML', 'NAME')))
def site_fix(s):
    s = must(s, "img, ext = cx.bounds2img(w, s, e, n, zoom=18, source=cx.providers.Esri.WorldImagery)", "img, ext = robust_tiles(w, s, e, n, 18, ll=False)", 1, 'site')
    s = must(s, "levels=np.arange(0, 120, 1)", "levels=np.arange(np.floor(np.nanmin(dem) / CI) * CI, np.nanmax(dem) + CI, CI)", 1, 'site')
    s = must(s, "# ---- maps ----", "# ---- maps ----\nCI = next(c for c in (1, 2, 5, 10, 20, 50) if (np.nanmax(dem[inside]) - np.nanmin(dem[inside])) / c <= 40)", 1, 'site')
    s = must(s, "'Imagery (Esri, Maxar, Earthstar Geographics) + 2 m contours, EPSG:2136 ft'", "f'Imagery (Esri, Maxar, Earthstar Geographics) + {CI} m contours, EPSG:2136 ft'", 1, 'site')
    return s
design('_design_site_analysis', 'ml3/site_analysis.py', 'Imagery (z18) and DEM warped to EPSG:2136; site analysis map.', extra=site_fix)
design('st_design_subdivide', 'ml3/subdivide_v2.py', "Plots by the planner's Phase One method: 100 ft front row, one frontage per block (65/70/75/80), leftover only to the end plots (guide section 5).")
def alloc(s):
    s = must(s, "for cls, c_ in (('30 ft local road', '#e6e6e6'), ('40 ft collector', '#f5c242'), ('60 ft existing road', '#8c8c8c')): gpd.GeoSeries([RD[cls]]).plot(ax=ax, color=c_)",
             "for cls in RD.index: gpd.GeoSeries([RD[cls]]).plot(ax=ax, color={'30 ft local road': '#e6e6e6', '40 ft collector': '#f5c242'}.get(cls, '#8c8c8c'))", 1, 'alloc')
    return must(s, "centre = unary_union(list(P.geometry)).centroid; JPT = COLLR.intersection(MAIN.buffer(2)).centroid",
                "centre = unary_union(list(P.geometry)).centroid; JPT = COLLR.intersection(MAIN.buffer(2)).centroid\n"
                "if JPT.is_empty: JPT = MAIN.boundary.interpolate(MAIN.boundary.project(centre)) if MAIN.area > 10 else centre     # no collector x main road junction: nearest point of the main road", 1, 'alloc')
design('st_design_landuse', 'ml3/allocate_t3.py', 'Facility programme and land use (guide section 7).', extra=alloc)
design('st_design_audit', 'ml3/design_audit.py', 'Design audit: flaws with location and fix (guide section 8).')
# ---------------- helpers ----------------
def helper(f, ren=None):
    s = rd(f)
    if ren:
        for a, b in ren: s = s.replace(a, b)
    return f'# ---- from {f} ----\n' + s + '\n'
helpers = helper('toolkit_src/roadsplit.py') + helper('ml4/classify.py') + helper('ml4/walls.py') + helper('ml4/road_surface.py').replace('unit = lambda', '_rs_unit = lambda').replace('unit(', '_rs_unit(') \
        + helper('ml4/obm.py', [("ROOT = 'D:/Work/2026/Data'\n", ''), ('{ROOT}', '{OBM_ROOT}'), ('def load(', 'def obm_load('), ('def quadkey(', 'def _obm_quadkey('), ('quadkey(la, lo, 6)', '_obm_quadkey(la, lo, 6)')])
guide = rd('toolkit_src/guide.md')
if '\u2014' in guide: raise SystemExit('em dash in guide')
stages.append('''def _walls_from_image(ctx, K):
    import numpy as np, geopandas as gpd, pandas as pd, rasterio, cv2, shapely, math
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union, transform as shp_transform, linemerge
    ctx = dict(ctx); ctx['_K'] = K
    _walls_body(ctx)

''')
full = rd('toolkit_src/header.py') + helpers + '\nGUIDE = r"""' + guide.replace('"""', "'''") + '"""\n\n' + rd('toolkit_src/new_stages.py') + rd('toolkit_src/autoroads.py') + '\n' + ''.join(stages) + rd('toolkit_src/cli.py')
os.makedirs(os.path.dirname(OUT), exist_ok=True); open(OUT, 'w', encoding='utf-8').write(full)
compile(full, OUT, 'exec'); print('written', OUT, len(full.splitlines()), 'lines,', len(stages), 'converted stages')
