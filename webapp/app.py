"""LP Toolkit web app (local). Start with run_webapp.bat, then open http://localhost:5050
Projects live in D:/Work/2026/Machine Learning/LP_Projects/<project>/ ; the planning work is done by ../lp_toolkit.py."""
import os, sys, re, json, time, glob, shutil, zipfile, subprocess, threading, io, argparse
from flask import Flask, jsonify, request, send_file, send_from_directory, abort
HERE = os.path.dirname(os.path.abspath(__file__)); TOOLKIT = os.path.dirname(HERE)
PY = os.path.join(TOOLKIT, 'env', 'Scripts', 'python.exe'); SCRIPT = os.path.join(TOOLKIT, 'lp_toolkit.py')
ROOT = os.environ.get('LP_PROJECTS', 'D:/Work/2026/Machine Learning/LP_Projects')
os.makedirs(ROOT, exist_ok=True)
app = Flask(__name__, static_folder=os.path.join(HERE, 'static'), static_url_path='/static')
RUNS = {}                                                    # project id -> Popen
EXISTING_STAGES = ['fetch', 'sam', 'digitize', 'compare', 'clean', 'database', 'roads', 'landuse', 'reserves', 'trees', 'blocks', 'plots', 'map']
DESIGN_STAGES = ['site', 'roads', 'subdivide', 'landuse', 'audit']

# ------------------------------------------------------------------ helpers
def pid_alive(pid):
    """True while a process with this id is running (Windows: exit code 259 = still active)"""
    if not pid: return False
    try:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not h: return False
        code = ctypes.c_ulong(); ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code)); ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259
    except Exception: return False
def is_running(pid_):
    """running = started by this server and not finished, or a run recorded in project.json whose process is still alive (survives app restarts)"""
    p = RUNS.get(pid_)
    if p is not None: return p.poll() is None
    try: return pid_alive(meta(pid_).get('pid'))
    except Exception: return False
def slug(s): return re.sub(r'[^A-Za-z0-9 _-]+', '', s).strip() or 'project'
def pdir(pid):
    d = os.path.realpath(os.path.join(ROOT, pid))
    if not d.startswith(os.path.realpath(ROOT)) or not os.path.isdir(d): abort(404)
    return d
def meta(pid):
    f = os.path.join(pdir(pid), 'project.json')
    return json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {}
def save_meta(pid, m): json.dump(m, open(os.path.join(pdir(pid), 'project.json'), 'w', encoding='utf-8'), indent=1)
def outdir(pid): m = meta(pid); return os.path.join(pdir(pid), f"{m.get('name', pid)} outputs")
def prefix(pid): return re.sub(r'\W+', '', meta(pid).get('name', pid)) + '_'
def safe(pid, rel):
    base = os.path.realpath(pdir(pid)); f = os.path.realpath(os.path.join(base, rel))
    if not f.startswith(base) or not os.path.exists(f): abort(404)
    return f
def to_geojson(path, simplify_ft=None, layer=None):
    import geopandas as gpd
    g = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    if g.crs is None: g = g.set_crs(2136)
    if simplify_ft and g.crs.to_epsg() == 2136: g['geometry'] = g.geometry.simplify(simplify_ft)
    g = g.to_crs(4326); g['_fid'] = range(len(g))
    for c in g.columns:
        if c != 'geometry' and str(g[c].dtype).startswith(('datetime', 'object')): g[c] = g[c].astype(str)
    return json.loads(g.to_json(drop_id=True))
def read_any(file_storage, dest_geojson):
    """uploaded kml / geojson / gpkg / zipped shapefile -> GeoJSON (EPSG:4326) saved to dest"""
    import geopandas as gpd, tempfile
    name = file_storage.filename.lower(); tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, os.path.basename(name)); file_storage.save(p)
    if name.endswith('.zip'):
        zipfile.ZipFile(p).extractall(tmp); shp = glob.glob(os.path.join(tmp, '**', '*.shp'), recursive=True)
        if not shp: raise ValueError('no .shp inside the zip')
        p = shp[0]
    g = gpd.read_file(p)
    if g.crs is None: g = g.set_crs(4326)
    g['geometry'] = g.geometry.force_2d(); g = g.to_crs(4326)
    keep = [c for c in g.columns if c in ('geometry', 'width_ft', 'class', 'Class', 'name', 'Name', 'highway', 'kind')]
    g[keep].to_file(dest_geojson, driver='GeoJSON'); shutil.rmtree(tmp, ignore_errors=True)
    return len(g)

# ------------------------------------------------------------------ pages
@app.route('/')
def index(): return send_from_directory(os.path.join(HERE, 'static'), 'index.html')
@app.route('/api/guide')
def guide():
    f = os.path.join(TOOLKIT, 'LP_Toolkit_Guide.md')
    if not os.path.exists(f): subprocess.run([PY, SCRIPT, 'guide'], capture_output=True)
    return open(f, encoding='utf-8').read(), 200, {'Content-Type': 'text/plain; charset=utf-8'}

# ------------------------------------------------------------------ projects
@app.get('/api/projects')
def projects():
    out = []
    for d in sorted(os.listdir(ROOT)):
        if os.path.isdir(os.path.join(ROOT, d)) and os.path.exists(os.path.join(ROOT, d, 'project.json')):
            m = json.load(open(os.path.join(ROOT, d, 'project.json'), encoding='utf-8')); m['id'] = d
            m['running'] = is_running(d); out.append(m)
    return jsonify(out)
@app.post('/api/projects')
def create():
    j = request.get_json(force=True)
    if not str(j.get('name') or '').strip(): return jsonify(error='Give the project a name.'), 400
    name = slug(j.get('name')); pid = name
    d = os.path.join(ROOT, pid)
    if os.path.exists(d): return jsonify(error=f'A project called "{name}" already exists. Choose another name (or open it from the project list).'), 400
    os.makedirs(d); m = dict(name=name, title=j.get('title') or name, workflow=j.get('workflow', 'design'), created=time.strftime('%Y-%m-%d %H:%M'))
    json.dump(m, open(os.path.join(d, 'project.json'), 'w', encoding='utf-8'), indent=1)
    return jsonify(id=pid, **m)
@app.delete('/api/projects/<pid>')
def delete_project(pid):
    """move the project to LP_Projects/_deleted/<name>_<date-time> (recoverable: move the folder back)"""
    d = pdir(pid)
    if is_running(pid): return jsonify(error='the project is running: stop it first'), 400
    trash = os.path.join(ROOT, '_deleted'); os.makedirs(trash, exist_ok=True)
    dest = os.path.join(trash, f"{pid}_{time.strftime('%Y%m%d-%H%M%S')}")
    try: shutil.move(d, dest)
    except Exception as e: return jsonify(error=f'could not move the project folder (is a file open in ArcGIS or a viewer?): {e}'), 400
    RUNS.pop(pid, None); return jsonify(ok=True, moved_to=dest)
@app.get('/api/projects/<pid>')
def project(pid):
    m = meta(pid); m['id'] = pid; d = pdir(pid)
    m['inputs'] = {k: os.path.exists(os.path.join(d, f'{k}.geojson')) for k in ('site', 'roads', 'stream', 'existing', 'zones')}
    m['running'] = is_running(pid)
    if not m.get('profile'):                                           # older projects: read it from the last run's command line
        f = os.path.join(d, 'run.log')
        if os.path.exists(f):
            mt = re.search(r'--profile (\w+)', open(f, encoding='utf-8', errors='replace').readline())
            if mt: m['profile'] = mt.group(1)
    return jsonify(m)
@app.post('/api/projects/<pid>/meta')
def set_meta(pid):
    m = meta(pid); m.update({k: v for k, v in request.get_json(force=True).items() if k in ('title', 'workflow', 'profile', 'stream_buffer', 'imagery', 'buildings', 'plot_w', 'plot_l')}); save_meta(pid, m); return jsonify(m)
@app.post('/api/projects/<pid>/upload/<kind>')
def upload(pid, kind):
    if kind not in ('site', 'roads', 'stream', 'existing', 'zones'): abort(400)
    try: n = read_any(request.files['file'], os.path.join(pdir(pid), f'{kind}.geojson'))
    except Exception as e:
        print('upload failed:', e, flush=True)
        return jsonify(error='This file could not be read as map data. Upload a KML / KMZ, a GeoJSON, or a zipped shapefile (.zip with the .shp, .shx, .dbf and .prj).'), 400
    return jsonify(ok=True, features=n)
@app.post('/api/projects/<pid>/layer/<kind>')
def save_layer(pid, kind):
    if kind not in ('site', 'roads', 'stream', 'existing', 'zones'): abort(400)
    fc = request.get_json(force=True)
    if not fc.get('features'):
        f = os.path.join(pdir(pid), f'{kind}.geojson')
        if os.path.exists(f): os.remove(f)
        return jsonify(ok=True, features=0)
    json.dump(fc, open(os.path.join(pdir(pid), f'{kind}.geojson'), 'w', encoding='utf-8')); return jsonify(ok=True, features=len(fc['features']))
@app.get('/api/projects/<pid>/input/<kind>')
def get_input(pid, kind):
    f = os.path.join(pdir(pid), f'{kind}.geojson')
    if not os.path.exists(f): return jsonify(type='FeatureCollection', features=[])
    return send_file(f, mimetype='application/json')
@app.get('/api/projects/<pid>/terrain')
def terrain(pid):
    f = os.path.join(outdir(pid), prefix(pid) + 'Terrain_summary.json')
    return jsonify(json.load(open(f)) if os.path.exists(f) else {})
@app.get('/api/projects/<pid>/patterns')
def patterns(pid):
    f = os.path.join(outdir(pid), prefix(pid) + 'Roads_patterns.json')
    return jsonify(json.load(open(f)) if os.path.exists(f) else [])
@app.post('/api/projects/<pid>/draft_to_roads')
def draft_to_roads(pid):
    """load the toolkit's automatic draft (<P>Roads_draft.shp) as the editable roads input"""
    pt = request.args.get('pattern', '')
    f = os.path.join(outdir(pid), prefix(pid) + (f'Roads_draft_{pt}.shp' if pt else 'Roads_draft.shp'))
    if not os.path.exists(f): f = os.path.join(outdir(pid), prefix(pid) + 'Roads_draft.shp')
    if not os.path.exists(f): return jsonify(error='no draft yet: run the roads stage with "Toolkit drafts"'), 400
    fc = to_geojson(f); json.dump(fc, open(os.path.join(pdir(pid), 'roads.geojson'), 'w', encoding='utf-8')); return jsonify(fc)

# ------------------------------------------------------------------ running the toolkit
def plot_args(pid):
    """the planner's plot size (breadth x length, ft) for the whole planning area: roads spaced for it, plots cut to it"""
    m = meta(pid); a = []
    for k, flag in (('plot_w', '--plot-w'), ('plot_l', '--plot-l')):
        try: v = float(m.get(k) or 0)
        except (TypeError, ValueError): v = 0
        if v > 0: a += [flag, f'{v:g}']
    return a
def design_args(j):
    a = []
    for k, flag in (('band', '--band'), ('block_len', '--block-len'), ('local_width', '--local-width'), ('collector_width', '--collector-width'), ('max_parcel_ac', '--max-parcel-ac')):
        if j.get(k): a += [flag, str(j[k])]
    return a
def launch(pid, cmd, pending=None):
    d = pdir(pid)
    log = open(os.path.join(d, 'run.log'), 'w', encoding='utf-8'); log.write('$ lp_toolkit.py ' + ' '.join(f'"{c}"' if ' ' in c else c for c in cmd[5:]) + '\n'); log.flush()
    RUNS[pid] = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=TOOLKIT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
    m = meta(pid); m['last_run'] = time.strftime('%Y-%m-%d %H:%M'); m['pending_load'] = pending; m['pid'] = RUNS[pid].pid; save_meta(pid, m)
def base_cmd(pid, wf='design'):
    m = meta(pid); site = os.path.join(pdir(pid), 'site.geojson')
    if not os.path.exists(site): raise ValueError('draw or upload the site boundary first')
    return [PY, '-u', '-W', 'ignore', SCRIPT, wf, '--site', site, '--name', m['name'], '--title', m.get('title') or m['name'], '--imagery', m.get('imagery', 'google')]
def _has_features(f):
    try: return os.path.exists(f) and bool(json.load(open(f, encoding='utf-8')).get('features'))
    except Exception: return False
def facility_args(pid):
    """the planner's facility programme (facilities.json) and located facilities (facility_sites.geojson)"""
    d = pdir(pid); a = []
    if os.path.exists(os.path.join(d, 'facilities.json')): a += ['--facilities', os.path.join(d, 'facilities.json')]
    if _has_features(os.path.join(d, 'facility_sites.geojson')): a += ['--facility-sites', os.path.join(d, 'facility_sites.geojson')]
    return a
def site_inputs(pid, j):
    d = pdir(pid); a = facility_args(pid)
    if _has_features(os.path.join(d, 'existing.geojson')): a += ['--existing', os.path.join(d, 'existing.geojson')]
    if _has_features(os.path.join(d, 'stream.geojson')): a += ['--stream', os.path.join(d, 'stream.geojson'), '--stream-buffer', str(j.get('stream_buffer', 100))]
    return a + ['--steep', str(j.get('steep', 30))]
def terrain_done(pid): return os.path.exists(os.path.join(outdir(pid), prefix(pid) + 'Terrain_summary.json'))
@app.post('/api/projects/<pid>/design_roads')
def design_roads(pid):
    """one blended road design for the whole site (site analysis first if it is missing); loads into the roads for editing"""
    if is_running(pid): return jsonify(error='already running'), 400
    j = request.get_json(force=True)
    try: cmd = base_cmd(pid)
    except ValueError as e: return jsonify(error=str(e)), 400
    lf = os.path.join(pdir(pid), 'lock.geojson')
    if os.path.exists(lf): os.remove(lf)
    cmd += ['--roads', 'draft', '--pattern', j.get('pattern', 'mixed'), '--only', 'roads' if terrain_done(pid) else 'site,roads'] + site_inputs(pid, j) + design_args(j) + plot_args(pid)
    launch(pid, cmd, pending='draft'); return jsonify(ok=True)
@app.post('/api/projects/<pid>/redesign')
def redesign(pid):
    """redesign only inside the drawn areas: roads outside them (clipped at the area edge) and the planner's own roads are kept"""
    import geopandas as gpd, shapely
    if is_running(pid): return jsonify(error='already running'), 400
    j = request.get_json(force=True); d = pdir(pid)
    zf, rf = os.path.join(d, 'zones.geojson'), os.path.join(d, 'roads.geojson')
    if not os.path.exists(zf): return jsonify(error='draw the area to redesign first'), 400
    Z = gpd.read_file(zf).to_crs(2136); ZU = Z.union_all()
    keep = []
    if os.path.exists(rf):
        R = gpd.read_file(rf)
        if len(R):
            R = R.to_crs(2136)
            for _, r_ in R.iterrows():
                locked = str(r_.get('locked', '')).lower() in ('true', '1')
                g = r_.geometry if locked else r_.geometry.difference(ZU)
                for q in shapely.get_parts(g):
                    if q.geom_type == 'LineString' and q.length > 30: keep.append(dict(width_ft=float(r_.get('width_ft') or 30), locked=locked, geometry=q))
    K = gpd.GeoDataFrame(keep, geometry='geometry', crs=2136) if keep else gpd.GeoDataFrame(columns=['width_ft', 'locked', 'geometry'], geometry='geometry', crs=2136)
    K.to_crs(4326).to_file(os.path.join(d, 'lock.geojson'), driver='GeoJSON')
    if 'pattern' not in Z.columns: Z['pattern'] = j.get('pattern', 'mixed')
    Z['pattern'] = Z['pattern'].fillna(j.get('pattern', 'mixed')); Z.to_crs(4326).to_file(os.path.join(d, 'zones_run.geojson'), driver='GeoJSON')
    try: cmd = base_cmd(pid)
    except ValueError as e: return jsonify(error=str(e)), 400
    cmd += ['--roads', 'draft', '--pattern', j.get('pattern', 'mixed'), '--only', 'roads' if terrain_done(pid) else 'site,roads', '--lock', os.path.join(d, 'lock.geojson'),
            '--zones', os.path.join(d, 'zones_run.geojson'), '--only-zones'] + site_inputs(pid, j) + design_args(j) + plot_args(pid)
    launch(pid, cmd, pending='redesign'); return jsonify(ok=True, kept=len(K))
@app.post('/api/projects/<pid>/load_draft')
def load_draft(pid):
    """toolkit draft -> the planner's editable roads; roads the planner had marked as theirs stay marked"""
    import geopandas as gpd
    d = pdir(pid); f = os.path.join(outdir(pid), prefix(pid) + 'Roads_draft.shp'); m = meta(pid); m['pending_load'] = None; save_meta(pid, m)
    if not os.path.exists(f): return jsonify(error='no draft'), 400
    G = gpd.read_file(f).to_crs(2136); G['locked'] = False
    lf = os.path.join(d, 'lock.geojson')
    if m.get('last_pending') == 'redesign' or os.path.exists(lf):
        try:
            Lk = gpd.read_file(lf).to_crs(2136); mine = Lk[Lk['locked'].astype(str).str.lower().isin(['true', '1'])] if 'locked' in Lk else Lk.iloc[0:0]
            for i, g in zip(G.index, G.geometry):
                if len(mine) and any(g.buffer(1).contains(x) or x.buffer(1).contains(g) for x in mine.geometry): G.at[i, 'locked'] = True
        except Exception: pass
    G = G.to_crs(4326); fc = json.loads(G.to_json(drop_id=True))
    json.dump(fc, open(os.path.join(d, 'roads.geojson'), 'w', encoding='utf-8')); return jsonify(fc)
# ------------------------------------------------------------------ existing plots: re-demarcate blocks, split / merge plots, undo
@app.post('/api/projects/<pid>/redemarcate')
def redemarcate(pid):
    if is_running(pid): return jsonify(error='already running'), 400
    j = request.get_json(force=True); blocks = [int(b) for b in j.get('blocks', [])]
    if not blocks: return jsonify(error='select the block(s) first'), 400
    m = meta(pid); backup_plots(pid)
    try: cmd = base_cmd(pid, 'existing')
    except ValueError as e: return jsonify(error=str(e)), 400
    cmd += ['--only', 'plots,map', '--profile', j.get('profile') or m.get('profile') or 'auto', '--buildings', m.get('buildings', 'fast'), '--blocks', ','.join(map(str, blocks)),
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
        planner = 'use_conf' in P.columns and str(P.at[i, 'use_conf']).startswith('confirmed (planner)')    # a use set by the planner is kept
        if len(inb):
            k = inb.area.idxmax(); P.at[i, 'main_bld'] = int(B.bld_id[k])
            if not planner:
                ok = 'use_conf' not in B.columns or B.use_conf[k] == 'confirmed'
                P.at[i, 'ex_use'] = B.ex_use[k] if ok else 'Unconfirmed (verify)'
                if 'use_guess' in P.columns: P.at[i, 'use_guess'] = B.ex_use[k]
                if 'use_conf' in P.columns: P.at[i, 'use_conf'] = 'confirmed' if ok else 'to confirm'
        else:
            P.at[i, 'main_bld'] = None
            if not planner: P.at[i, 'ex_use'] = 'Open / yard (no building)'
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
    from shapely import affinity as _aff
    ext = _aff.scale(line, 1.02, 1.02)                      # a hair longer so it cuts edge to edge
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
# ------------------------------------------------------------------ generic feature editing (all result layers)
EDITABLE = {
    'existing': [('Plots / land use', '{O}/{P}Plots_existing.shp'), ('Buildings', '{O}/{P}Existing_land_use_buildings.shp'), ('Blocks', '{O}/{P}Blocks_existing.shp'),
                 ('Road surface', '{O}/{P}Road_surface.shp'), ('Road centrelines', '{O}/{P}Roads_existing.shp'), ('Walls / fences', '{O}/{P}Walls_final.shp'),
                 ('Vacant / open land', '{O}/{P}Vacant_open_land.shp'), ('Tree belt', '{O}/{P}Tree_belt_existing.shp'), ('Streams / rivers / water', 'stream.geojson'), ('Site boundary', 'site.geojson')],
    'design': [('Roads (design)', 'roads.geojson'), ('Plots and land use', '{O}/_work/plots_landuse.gpkg'), ('Facility / green sites', '{O}/_work/reserves_landuse.gpkg'),
               ('Blocks', '{O}/_work/layout_blocks.gpkg'), ('Existing buildings', '{O}/_work/buildings.gpkg'), ('Existing roads to keep', 'existing.geojson'), ('Streams / rivers / water', 'stream.geojson'), ('Site boundary', 'site.geojson'), ('Redesign / zone areas', 'zones.geojson')],
}
READONLY = {'area_m2', 'frontage_m', 'depth_m', 'coverage', 'n_bld', 'main_bld', 'length_m', 'area_ac', '_fid'}
def _per_road(f):
    """an older merged road surface is split into one polygon per road (once; the original is kept as *_merged.shp)"""
    if not f.endswith('Road_surface.shp'): return
    try:
        from roadsplit import split_file
        if split_file(f, f.replace('Road_surface.shp', 'Roads_existing.shp')): print('road surface split per road:', f, flush=True)
    except Exception as ex: print('road surface split failed:', ex, flush=True)
def _edit_file(pid, rel):
    import geopandas as gpd
    if rel in ('stream.geojson', 'roads.geojson', 'existing.geojson', 'zones.geojson') and not os.path.exists(os.path.join(pdir(pid), rel)):   # an input layer that is still empty
        json.dump({'type': 'FeatureCollection', 'features': []}, open(os.path.join(pdir(pid), rel), 'w'))
    f = safe(pid, rel); _per_road(f)
    g = gpd.read_file(f)
    g = g.drop(columns=[c for c in g.columns if c.lower() == 'fid'])          # an 'FID' column clashes with the GeoPackage key of the edit history
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
        if rel.endswith('.geojson') and not os.path.exists(os.path.join(d, rel)):
            json.dump({'type': 'FeatureCollection', 'features': []}, open(os.path.join(d, rel), 'w'))
        if not os.path.exists(os.path.join(d, rel)): continue
        try: g = gpd.read_file(os.path.join(d, rel), rows=50)
        except Exception: continue
        fields = [dict(name=c, type='number' if str(g[c].dtype).startswith(('int', 'float')) else 'text', readonly=c in READONLY) for c in g.columns if c != 'geometry']
        if rel == 'stream.geojson':                                    # streams / rivers / water bodies: lines or areas
            have = {f_['name'] for f_ in fields}
            fields += [dict(name=n_, type='number' if n_ == 'buffer_ft' else 'text', readonly=False) for n_ in ('name', 'type', 'buffer_ft') if n_ not in have]
            out.append(dict(label=label, path=rel, geom='any', fields=fields)); continue
        out.append(dict(label=label, path=rel, geom=_gkind(g) if len(g) else ('line' if 'road' in label.lower() or 'wall' in label.lower() or 'stream' in label.lower() else 'polygon'), fields=fields))
    return jsonify(out)
@app.get('/api/projects/<pid>/edit/feature')
def edit_feature(pid):
    f, g = _edit_file(pid, request.args.get('path', ''))
    try: i = int(request.args.get('fid'))
    except (TypeError, ValueError): return jsonify(error='fid must be a feature number'), 400
    if not 0 <= i < len(g): return jsonify(error=f'no feature {i} on this layer ({len(g)} features)'), 404
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
        if rel in ('site.geojson', 'zones.geojson', 'stream.geojson', 'roads.geojson', 'existing.geojson'): f = os.path.join(pdir(pid), rel)   # an input layer emptied by the edit (its file is gone): undo writes it again
        else: f = safe(pid, rel)
        h = gpd.read_file(hs[-1]); _write(f, h); os.remove(hs[-1]); return jsonify(ok=True, left=len(hs) - 1)
    f, g = _edit_file(pid, rel); crs = g.crs
    to_g = lambda gj: gpd.GeoSeries([shape(gj)], crs=4326).to_crs(crs).iloc[0]
    fids = [int(x) for x in (j.get('fids') or [])]
    os.makedirs(hd, exist_ok=True); HF = os.path.join(hd, time.strftime('%Y%m%d-%H%M%S-') + str(int(time.time() * 1000) % 1000) + '.gpkg'); g.to_file(HF)
    def _fail(msg):                                                   # a refused edit leaves no undo step
        try: os.remove(HF)
        except OSError: pass
        return jsonify(error=msg), 400
    for o in sorted(glob.glob(os.path.join(hd, '*.gpkg')))[:-40]: os.remove(o)
    changed = []
    def props_for(row_props):
        out = {}
        for k, v in (row_props or {}).items():
            if k not in g.columns and f.endswith('.geojson') and k not in READONLY and k != 'geometry' and not k.startswith('_'): g[k] = None   # input layers can gain fields
            if k not in g.columns or k in READONLY or k == 'geometry': continue
            if str(g[k].dtype).startswith(('int', 'float')) or k in ('buffer_ft', 'width_ft'):
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
    elif op == 'update_geoms':                                         # several features moved / rotated / scaled at once
        changed = []
        for it in j.get('items', []):
            i_ = int(it['fid']); geom = to_g(it['geometry']); g.at[i_, 'geometry'] = geom.buffer(0) if geom.geom_type in ('Polygon', 'MultiPolygon') else geom; changed.append(i_)
    elif op == 'add_many':                                             # paste: copies of features into this layer
        rows = []
        for it in j.get('items', []):
            geom = to_g(it['geometry']); row = {c: None for c in g.columns if c != 'geometry'}; row.update(props_for(it.get('properties'))); row['geometry'] = geom.buffer(0) if geom.geom_type in ('Polygon', 'MultiPolygon') else geom; rows.append(row)
        if not rows: return _fail('nothing to paste')
        g = gpd.GeoDataFrame(pd.concat([g, gpd.GeoDataFrame(rows, crs=crs)], ignore_index=True), crs=crs); changed = list(range(len(g) - len(rows), len(g)))
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
        if len(fids) < 2: return _fail('select two or more features to merge')
        sub = g.loc[fids]; geom = unary_union(list(sub.geometry))
        if _gkind(g) == 'polygon':
            geom = geom.buffer(0.05).buffer(-0.05)
            if geom.geom_type != 'Polygon': return _fail('these blocks do not touch: a road runs between them, so there is no shared boundary to remove (delete or move the road instead)' if 'block' in rel.lower() else 'the polygons must touch or overlap to merge')
        else: geom = linemerge(geom) if geom.geom_type == 'MultiLineString' else geom
        keep = sub.geometry.area.idxmax() if _gkind(g) == 'polygon' else sub.geometry.length.idxmax()
        g.at[keep, 'geometry'] = geom; g = g.drop(index=[i for i in fids if i != keep]).reset_index(drop=True)
        changed = [int(keep) - sum(1 for i in fids if i < keep and i != keep)]
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
        if not drop: return _fail('the line must cross the feature(s) from edge to edge')
        g = gpd.GeoDataFrame(pd.concat([g.drop(index=drop), gpd.GeoDataFrame(rows, crs=crs)], ignore_index=True), crs=crs); changed = list(range(len(g) - len(rows), len(g)))
    elif op == 'reshape':
        line = to_g(j['geometry']); i = fids[0]; geom = g.geometry[i]
        if _gkind(g) == 'polygon':
            poly = max(shapely.get_parts(geom), key=lambda x: x.area) if geom.geom_type == 'MultiPolygon' else geom
            if len(shapely.get_parts(line.intersection(poly.boundary))) < 2: return _fail('the reshape line must cross the outline at least twice')
            xs = [line.project(x) for x in shapely.get_parts(line.intersection(poly.boundary)) if x.geom_type == 'Point']
            mid_ = substring(line, min(xs), max(xs)) if len(xs) >= 2 and max(xs) - min(xs) > 1e-6 else line
            if mid_.intersection(poly).length < 0.5 * mid_.length:     # between its crossings the line runs outside: add the area it encloses
                faces = [x for x in polygonize(unary_union([poly.boundary, line])) if not poly.contains(x.representative_point()) and x.boundary.intersection(line).length > 0]
                new = poly.union(unary_union(faces)) if faces else poly
            else:                                                      # line cuts across: keep the bigger part
                parts = list(shapely.get_parts(ssplit(poly, _aff.scale(line, 1.02, 1.02))))
                new = max(parts, key=lambda x: x.area) if len(parts) > 1 else poly
            g.at[i, 'geometry'] = new.buffer(0)
        else:
            ln = linemerge(geom) if geom.geom_type == 'MultiLineString' else geom
            if ln.geom_type != 'LineString': return _fail('reshape works on single lines')
            a, b = ln.project(shapely.geometry.Point(line.coords[0])), ln.project(shapely.geometry.Point(line.coords[-1]))
            sk = list(line.coords) if a <= b else list(line.coords)[::-1]; a, b = min(a, b), max(a, b)
            head = list(substring(ln, 0, a).coords) if a > 0 else []; tail = list(substring(ln, b, ln.length).coords) if b < ln.length else []
            g.at[i, 'geometry'] = LineString(head[:-1] + sk + tail[1:])
        changed = [i]
    else: return jsonify(error=f'unknown operation {op}'), 400
    # derived values
    if f.endswith('Plots_existing.shp') and changed and op != 'update_attrs': g = plot_attrs(pid, g, [c for c in changed if c < len(g)])   # attribute edits (e.g. a new use) are kept as typed
    FT_ = 0.3048
    if 'area_m2' in g.columns and str(crs).endswith('2136') and _gkind(g) == 'polygon' and not f.endswith('Plots_existing.shp'): g['area_m2'] = (g.area * FT_ * FT_).round(1)
    if 'length_m' in g.columns and str(crs).endswith('2136') and _gkind(g) == 'line': g['length_m'] = (g.length * FT_).round(1)
    _write(f, g)
    return jsonify(ok=True, features=len(g), changed=changed)
@app.post('/api/projects/<pid>/run')
def run(pid):
    if is_running(pid): return jsonify(error='already running'), 400
    j = request.get_json(force=True); m = meta(pid); d = pdir(pid)
    site = os.path.join(d, 'site.geojson')
    if not os.path.exists(site): return jsonify(error='draw or upload the site boundary first'), 400
    wf = j.get('workflow', m.get('workflow', 'design')); m['workflow'] = wf
    cmd = [PY, '-u', '-W', 'ignore', SCRIPT, wf, '--site', site, '--name', m['name'], '--title', m.get('title') or m['name'], '--imagery', m.get('imagery', 'google')]
    note_ = ''
    if wf == 'design' and (j.get('from') or j.get('only') or '').split(',')[0] in ('subdivide', 'landuse', 'audit') and not os.path.exists(os.path.join(outdir(pid), '_work', 'layout_blocks.gpkg')):
        j['from'] = 'roads'; j['only'] = None; note_ = 'NOTE: the roads stage had not built the blocks yet (a draft only draws roads), so this run starts from 2. roads.' + chr(10)
    if j.get('from'): cmd += ['--from', j['from']]
    if j.get('only'): cmd += ['--only', j['only']]
    if wf == 'design' and j.get('chamfer'): cmd += ['--chamfer']
    if wf == 'existing':
        prof_ = j.get('profile') or m.get('profile') or 'auto'; m['profile'] = prof_
        cmd += ['--profile', prof_, '--buildings', j.get('buildings', m.get('buildings', 'fast'))]
        if j.get('with'): cmd += ['--with', j['with']]
    else:
        mode = 'file'
        if mode == 'file':
            if not os.path.exists(os.path.join(d, 'roads.geojson')): return jsonify(error='draw or upload the roads first (or choose automatic / draft)'), 400
            cmd += ['--roads', os.path.join(d, 'roads.geojson')]
        else:
            cmd += ['--roads', mode]
            if j.get('pattern'): cmd += ['--pattern', j['pattern']]
        cmd += ['--steep', str(j.get('steep', 30))] + plot_args(pid) + facility_args(pid)
        if _has_features(os.path.join(d, 'existing.geojson')): cmd += ['--existing', os.path.join(d, 'existing.geojson')]
        if _has_features(os.path.join(d, 'stream.geojson')): cmd += ['--stream', os.path.join(d, 'stream.geojson'), '--stream-buffer', str(j.get('stream_buffer', 100))]
    log = open(os.path.join(d, 'run.log'), 'w', encoding='utf-8'); log.write('$ lp_toolkit.py ' + ' '.join(f'"{c}"' if ' ' in c else c for c in cmd[5:]) + '\n' + note_); log.flush()
    RUNS[pid] = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=TOOLKIT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
    m['last_run'] = time.strftime('%Y-%m-%d %H:%M'); m['pid'] = RUNS[pid].pid
    if wf == 'design' and ('--from' not in cmd or cmd[cmd.index('--from') + 1] in ('site', 'roads')) and ('--only' not in cmd or 'roads' in cmd[cmd.index('--only') + 1].split(',')):
        m['plan_roads_hash'] = roads_hash(pid)                         # this run makes the plan from the roads as they are now
        snap_plan_roads(pid)                                             # the drawn roads this plan is made from (local updates compare with them)
    save_meta(pid, m)
    return jsonify(ok=True, cmd=cmd[3:])
@app.post('/api/projects/<pid>/stop')
def stop(pid):
    p = RUNS.get(pid); target = p.pid if (p and p.poll() is None) else meta(pid).get('pid')
    if target and pid_alive(target):
        subprocess.run(['taskkill', '/PID', str(target), '/T', '/F'], capture_output=True); return jsonify(ok=True)
    return jsonify(ok=False)
FAIL_HINTS = [
    (r'NO ROADS', 'There are no roads to plan with.', 'Draw roads, or use "Design the roads for me", then run again.'),
    (r'layout_blocks\.gpkg|plots_final\.gpkg|No such file', 'An earlier stage has not produced its output yet.', 'Run from an earlier stage (for example 2. roads).'),
    (r'HTTP Error 4\d\d|HTTP Error 5\d\d|URLError|timed out|RemoteDisconnected|getaddrinfo', 'An online data service (OpenStreetMap, imagery or elevation) did not answer.', 'Check the internet connection and run again; the toolkit retries other sources.'),
    (r'MemoryError|ArrayMemoryError', 'The computer ran out of memory.', 'Close other programs, or split the site into smaller parts.'),
    (r'PermissionError|being used by another process', 'A file is open in another program (for example ArcGIS or Excel).', 'Close it there and run again.'),
]
def failure_summary(txt, stages, finished):
    """the last error of a failed run in plain words: stage, what happened, what to do"""
    stage = stages[finished] if finished < len(stages) else (stages[-1] if stages else '')
    lines = [l for l in txt.strip().splitlines() if l.strip()]
    last = next((l.strip() for l in reversed(lines) if re.match(r'^\s*(\w+(Error|Exception|Exit)|[A-Z ]+:)', l.strip()) or 'Error' in l), lines[-1] if lines else '')
    for pat, what, todo in FAIL_HINTS:
        if re.search(pat, txt[-4000:]): return dict(stage=stage, what=what, todo=todo, detail=last[:300])
    return dict(stage=stage, what='The stage stopped with an unexpected error.', todo='Try running that stage again. If it fails again, send the last lines of the log.', detail=last[:300])
def roads_hash(pid, base=None):
    """fingerprint of the planner's roads (design roads + existing roads to keep); base: another folder holding them (the plan's record)"""
    import hashlib
    h = hashlib.md5()
    for k in ('roads', 'existing'):
        f = os.path.join(base or pdir(pid), f'{k}.geojson')
        if os.path.exists(f): h.update(open(f, 'rb').read())
    return h.hexdigest()
def snap_plan_roads(pid):
    sd = os.path.join(pdir(pid), '_plan_roads'); os.makedirs(sd, exist_ok=True)
    for k in ('roads', 'existing'):
        f = os.path.join(pdir(pid), f'{k}.geojson'); dst = os.path.join(sd, f'{k}.geojson')
        if os.path.exists(f): shutil.copy2(f, dst)
        elif os.path.exists(dst): os.remove(dst)
def roads_changed(pid):
    """the roads were edited after the current plan (plots + land use) was made from them"""
    m = meta(pid)
    if m.get('workflow') != 'design' or not os.path.exists(os.path.join(outdir(pid), '_work', 'plots_landuse.gpkg')): return False
    plan_f = os.path.join(outdir(pid), '_work', 'plots_landuse.gpkg'); rf = os.path.join(pdir(pid), 'roads.geojson')
    if not os.path.isdir(os.path.join(pdir(pid), '_plan_roads')) and (not os.path.exists(rf) or os.path.getmtime(rf) <= os.path.getmtime(plan_f) + 5):
        snap_plan_roads(pid); m['plan_roads_hash'] = roads_hash(pid); save_meta(pid, m)          # older plan, roads unchanged since: record them now
    if not m.get('plan_roads_hash'):                                    # plans made before this check: compare file times
        f = os.path.join(pdir(pid), 'roads.geojson')
        return os.path.exists(f) and os.path.getmtime(f) > os.path.getmtime(os.path.join(outdir(pid), '_work', 'plots_landuse.gpkg')) + 5
    return m['plan_roads_hash'] != roads_hash(pid)
# ------------------------------------------------------------------ save edits / discard edits
SIDE = ('.shp', '.shx', '.dbf', '.prj', '.cpg')
def edit_files(pid):
    """every file the editing tools write: inputs (roads, site, streams, zones) + the editable outputs of the workflow"""
    m = meta(pid); d = pdir(pid); O = os.path.basename(outdir(pid)); P_ = prefix(pid); out = []
    for k in ('site', 'roads', 'existing', 'stream', 'zones', 'facility_sites'):
        f = os.path.join(d, f'{k}.geojson')
        if os.path.exists(f): out.append(f)
    if os.path.exists(os.path.join(d, 'facilities.json')): out.append(os.path.join(d, 'facilities.json'))
    for wf in ('existing', 'design'):
        for _, tpl in EDITABLE.get(wf, []):
            f = os.path.join(d, tpl.format(O=O, P=P_))
            if f.endswith('.shp'): out += [f[:-4] + e for e in SIDE if os.path.exists(f[:-4] + e)]
            elif os.path.exists(f) and f not in out: out.append(f)
    for f in (os.path.join(outdir(pid), '_work', 'layout_roads.gpkg'), os.path.join(outdir(pid), '_work', 'plots_landuse.gpkg'), os.path.join(outdir(pid), '_work', 'reserves_landuse.gpkg'),
              os.path.join(outdir(pid), '_work', 'layout_centrelines.gpkg'), os.path.join(pdir(pid), '_plan_roads', 'roads.geojson'), os.path.join(pdir(pid), '_plan_roads', 'existing.geojson')):   # the plan's own record goes back with it
        if os.path.exists(f) and f not in out: out.append(f)
    return out
def save_dir(pid): return os.path.join(pdir(pid), '_saved')
EDIT_PATHS = re.compile(r'^/api/projects/([^/]+)/(layer/|upload/|edit/op|plots/split|plots/merge|plots/undo|design/local_update|plotsize/apply)')
@app.after_request
def _mark_edit(resp):
    """an edit made in the app: remembered so 'Save edits' can show there is something unsaved"""
    mt = EDIT_PATHS.match(request.path)
    if request.method == 'POST' and mt and resp.status_code == 200:
        try: m = meta(mt.group(1)); m['last_edit'] = time.time(); save_meta(mt.group(1), m)
        except Exception: pass
    return resp
def _save_point(pid, label=None):
    d = pdir(pid); sd = save_dir(pid)
    if os.path.exists(sd): shutil.rmtree(sd)
    os.makedirs(sd); files = edit_files(pid)
    for f in files:
        dst = os.path.join(sd, os.path.relpath(f, d)); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(f, dst)
    label = label or time.strftime('%Y-%m-%d %H:%M'); json.dump(dict(time=time.time(), label=label, files=[os.path.relpath(f, d) for f in files]), open(os.path.join(sd, 'saved.json'), 'w'), indent=1)
    vd = os.path.join(d, '_versions', time.strftime('%Y%m%d-%H%M%S')); shutil.copytree(sd, vd, dirs_exist_ok=True)
    for old in sorted(glob.glob(os.path.join(d, '_versions', '*')))[:-10]: shutil.rmtree(old, ignore_errors=True)
    return label, len(files)
def edits_state(pid):
    sd = save_dir(pid); stamp = os.path.join(sd, 'saved.json'); m = meta(pid)
    t = json.load(open(stamp)).get('time', 0) if os.path.exists(stamp) else 0
    log_ = os.path.join(pdir(pid), 'run.log')
    if not is_running(pid) and os.path.exists(log_) and os.path.getmtime(log_) > t and m.get('last_edit', 0) < os.path.getmtime(log_):
        try: _save_point(pid, time.strftime('%Y-%m-%d %H:%M') + ' (after the run)'); t = time.time()   # a finished run is the new baseline
        except Exception: pass
    label = json.load(open(stamp)).get('label') if os.path.exists(stamp) else None
    return dict(saved_at=label, dirty=m.get('last_edit', 0) > t)
@app.post('/api/projects/<pid>/edits/save')
def edits_save(pid):
    """a save point: copies of every editable file (also kept in _versions, last 10)"""
    if is_running(pid): return jsonify(error='a run is in progress: save when it has finished'), 400
    label, n = _save_point(pid); return jsonify(ok=True, saved_at=label, files=n)
@app.post('/api/projects/<pid>/edits/discard')
def edits_discard(pid):
    """every editable file back to the last save point"""
    if is_running(pid): return jsonify(error='a run is in progress'), 400
    sd = save_dir(pid); stamp = os.path.join(sd, 'saved.json')
    if not os.path.exists(stamp): return jsonify(error='nothing saved yet: use Save edits first'), 400
    info = json.load(open(stamp)); d = pdir(pid); n = 0
    for rel in info['files']:
        src = os.path.join(sd, rel)
        if os.path.exists(src): shutil.copy2(src, os.path.join(d, rel)); n += 1
    m = meta(pid); m['last_edit'] = info['time'] - 1                    # back at the save point: nothing unsaved
    pr = os.path.join(d, '_plan_roads')
    if os.path.isdir(pr): m['plan_roads_hash'] = roads_hash(pid, pr)     # the plan's own roads record came back too: 'roads changed' follows it
    save_meta(pid, m)
    for k in ('_edit_history', '_plot_history'): shutil.rmtree(os.path.join(d, k), ignore_errors=True)    # the undo steps belong to the discarded edits
    return jsonify(ok=True, restored=n, saved_at=info.get('label'))
@app.get('/api/projects/<pid>/edits/state')
def edits_state_api(pid): return jsonify(edits_state(pid))
@app.post('/api/projects/<pid>/plotsize/<what>')
def plotsize_api(pid, what):
    """plot breadth x length for selected blocks or the whole planning area after the design: preview (fit and exact) / apply one"""
    if is_running(pid): return jsonify(error='a run is in progress'), 400
    if meta(pid).get('workflow') != 'design': return jsonify(error='plot size after the design is for new layouts'), 400
    import plotsize
    j = request.get_json(force=True); work = os.path.join(outdir(pid), '_work') + '/'
    if not os.path.exists(work + 'plots_landuse.gpkg'): return jsonify(error='no plan yet: run the design first'), 400
    try: b, l = float(j.get('breadth') or 0), float(j.get('length') or 0)
    except (TypeError, ValueError): return jsonify(error='breadth and length must be numbers (feet)'), 400
    if not (30 <= b <= 400 and 30 <= l <= 600): return jsonify(error='give the plot breadth (30-400 ft) and length (30-600 ft)'), 400
    fids = [int(x) for x in (j.get('fids') or [])]; whole = bool(j.get('whole'))
    try:
        if what == 'preview':
            out = {}
            for mode in ('fit', 'exact'):
                r = plotsize.compute(work, fids, whole, b, l, mode); out[mode] = dict(stats=r['stats'], fc=plotsize.to_fc(r))
            return jsonify(out)
        if what == 'apply':
            mode = j.get('mode') if j.get('mode') in ('fit', 'exact') else 'fit'
            rel = lambda f: _history(pid, os.path.relpath(f, pdir(pid)).replace(os.sep, '/'))
            st = plotsize.apply(work, fids, whole, b, l, mode, history=(rel(work + 'plots_landuse.gpkg'), rel(work + 'reserves_landuse.gpkg')))
            return jsonify(ok=True, stats=st)
    except ValueError as ex: return jsonify(error=str(ex)), 400
    abort(404)
@app.post('/api/projects/<pid>/design/local_update')
def design_local_update(pid):
    """new / edited roads: their reserve surface into the plan and the blocks they cross re-plotted (the rest of the plan stays)"""
    if is_running(pid): return jsonify(ok=False, msg='a run is in progress'), 200
    if meta(pid).get('workflow') != 'design': return jsonify(ok=False, msg='design projects only'), 200
    import localupdate
    try: r = localupdate.update(pdir(pid), os.path.join(outdir(pid), '_work') + '/')
    except Exception as ex:
        import traceback; traceback.print_exc(); return jsonify(ok=False, msg=f'the quick update failed ({type(ex).__name__}): use "Update the plan" for a full re-run'), 200
    r.pop('times', None)
    if r.get('ok'): m = meta(pid); m['plan_roads_hash'] = roads_hash(pid); save_meta(pid, m)
    return jsonify(r)
# ------------------------------------------------------------------ facility programme (after the site analysis)
_CAT = {}
def facility_catalog(pop):
    """the toolkit's catalogue (LUSPA 2025 + the local-plan study) with the counts this population needs"""
    k = round(float(pop or 0), -1)
    if k not in _CAT:
        r = subprocess.run([PY, SCRIPT, 'facilities', '--pop', str(k)], capture_output=True, text=True, cwd=TOOLKIT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if r.returncode: raise RuntimeError(r.stderr[-500:])
        _CAT[k] = json.loads(r.stdout.strip().splitlines()[-1])
        if len(_CAT) > 50: _CAT.pop(next(iter(_CAT)))
    return _CAT[k]
def population_estimate(pid):
    """planned population before the layout: net site area x 65 % housing x 6.2 plots / ac x 7.2 persons (the toolkit's programme)"""
    import geopandas as gpd
    f = os.path.join(pdir(pid), 'site.geojson')
    if not os.path.exists(f): return 0
    try:
        S = gpd.read_file(f).to_crs(2136).union_all(); net = S.area
        sf = os.path.join(pdir(pid), 'stream.geojson')
        if _has_features(sf): net -= gpd.read_file(sf).to_crs(2136).union_all().buffer(float(meta(pid).get('stream_buffer') or 100)).intersection(S).area
        return int(round(net / 43560 * 0.65 * 6.2 * 7.2, -1))
    except Exception: return 0
@app.get('/api/projects/<pid>/facilities')
def facilities_get(pid):
    d = pdir(pid); f = os.path.join(d, 'facilities.json'); J = json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {}
    est = population_estimate(pid); pop = J.get('population') or est
    sites = json.load(open(os.path.join(d, 'facility_sites.geojson'), encoding='utf-8')) if os.path.exists(os.path.join(d, 'facility_sites.geojson')) else dict(type='FeatureCollection', features=[])
    try: cat = facility_catalog(pop)
    except Exception as ex: return jsonify(error=f'facility catalogue: {ex}'), 500
    return jsonify(mode=J.get('mode', 'auto'), items=J.get('items') or {}, population=pop, estimate=est, catalog=cat, sites=sites, decisions=J.get('decisions') or {})
@app.get('/api/facility_catalog')
def facility_catalog_api():
    try: return jsonify(facility_catalog(float(request.args.get('pop') or 0)))
    except Exception as ex: return jsonify(error=str(ex)), 500
@app.post('/api/projects/<pid>/facilities')
def facilities_post(pid):
    """save the programme: mode auto (the toolkit decides) | custom (the planner's ticks, numbers and sizes)"""
    j = request.get_json(force=True); f = os.path.join(pdir(pid), 'facilities.json')
    old = json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {}
    J = dict(mode=j.get('mode', 'auto'), population=j.get('population') or None, items=j.get('items') or {}, decisions={})          # a changed programme: earlier shortfall choices no longer apply
    if j.get('keep_decisions'): J['decisions'] = old.get('decisions') or {}
    json.dump(J, open(f, 'w', encoding='utf-8'), indent=1); m = meta(pid); m['last_edit'] = time.time(); save_meta(pid, m)
    return jsonify(ok=True)
@app.post('/api/projects/<pid>/facility_sites')
def facility_sites_post(pid):
    """located facilities: points (a site of the asked size is shaped there) or outlines; each feature has fac_id"""
    fc = request.get_json(force=True); f = os.path.join(pdir(pid), 'facility_sites.geojson')
    feats = [x for x in fc.get('features', []) if x.get('geometry') and (x.get('properties') or {}).get('fac_id')]
    if feats: json.dump(dict(type='FeatureCollection', features=feats), open(f, 'w', encoding='utf-8'))
    elif os.path.exists(f): os.remove(f)
    m = meta(pid); m['last_edit'] = time.time(); save_meta(pid, m)
    return jsonify(ok=True, n=len(feats))
@app.get('/api/projects/<pid>/shortfall')
def shortfall_get(pid):
    f = os.path.join(outdir(pid), '_work', 'shortfall.json')
    return jsonify(json.load(open(f, encoding='utf-8')) if os.path.exists(f) and not is_running(pid) else dict(items=[]))
@app.post('/api/projects/<pid>/shortfall')
def shortfall_post(pid):
    """the planner's choice for each facility that did not fit (take plots / skip / reduce:<ac>), then the run continues from land use"""
    if is_running(pid): return jsonify(error='already running'), 400
    j = request.get_json(force=True); f = os.path.join(pdir(pid), 'facilities.json')
    J = json.load(open(f, encoding='utf-8')) if os.path.exists(f) else dict(mode='auto', items={})
    dec = J.get('decisions') or {}
    for k, v in (j.get('decisions') or {}).items():
        if v == 'take' or v == 'skip' or re.match(r'^reduce:\d+(\.\d+)?$', str(v)): dec[k] = v
    J['decisions'] = dec; json.dump(J, open(f, 'w', encoding='utf-8'), indent=1)
    m = meta(pid); d = pdir(pid)
    if not os.path.exists(os.path.join(d, 'roads.geojson')): return jsonify(error='no roads'), 400
    cmd = base_cmd(pid) + ['--from', 'landuse', '--roads', os.path.join(d, 'roads.geojson'), '--steep', str(j.get('steep', 30))] + plot_args(pid) + facility_args(pid)
    if _has_features(os.path.join(d, 'existing.geojson')): cmd += ['--existing', os.path.join(d, 'existing.geojson')]
    if _has_features(os.path.join(d, 'stream.geojson')): cmd += ['--stream', os.path.join(d, 'stream.geojson'), '--stream-buffer', str(m.get('stream_buffer', 100))]
    if j.get('chamfer'): cmd += ['--chamfer']
    launch(pid, cmd); return jsonify(ok=True)
@app.get('/api/projects/<pid>/status')
def status(pid):
    f = os.path.join(pdir(pid), 'run.log'); txt = open(f, encoding='utf-8', errors='replace').read() if os.path.exists(f) else ''
    p = RUNS.get(pid); running = is_running(pid)
    stages = re.findall(r'^== (\w+)', txt, flags=re.M); done = re.findall(r'^   done in', txt, flags=re.M)
    rc = None if p is None else p.poll()
    failed = (not running) and (('Traceback' in txt) or (rc not in (None, 0)))
    pend = meta(pid).get('pending_load') if not running else None
    prog, note = {}, {}
    for mm in re.finditer(r'^@@progress (\w+) (\d+) ?(.*)$', txt, flags=re.M): prog[mm.group(1)] = int(mm.group(2)); note[mm.group(1)] = mm.group(3).strip()
    txt = re.sub(r'^@@progress .*\n?', '', txt, flags=re.M)
    paused = (not running) and (not failed) and bool(re.search(r'^@@pause shortfall', txt, flags=re.M)) and os.path.exists(os.path.join(outdir(pid), '_work', 'shortfall.json'))
    txt = re.sub(r'^@@pause .*\n?', '', txt, flags=re.M)
    return jsonify(running=running, log=txt[-20000:], stages=stages, finished=len(done), failed=bool(failed), returncode=rc, pending_load=pend, progress=prog, notes=note, failure=failure_summary(txt, stages, len(done)) if failed else None, paused=paused,
                   roads_changed=(not running) and roads_changed(pid), edits=edits_state(pid))

# ------------------------------------------------------------------ results
LAYERS = {   # (label, relative path template, kind)
    'existing': [('Plots (existing land use)', '{O}/{P}Plots_existing.shp', 'plots'), ('Buildings', '{O}/{P}Existing_land_use_buildings.shp', 'buildings'),
                 ('Blocks', '{O}/{P}Blocks_existing.shp', 'blocks'), ('Road surface', '{O}/{P}Road_surface.shp', 'roads'),
                 ('Walls / fences', '{O}/{P}Walls_final.shp', 'walls'), ('Pinch points', '{O}/{P}Road_pinch_points.shp', 'points'),
                 ('Tree belt', '{O}/{P}Tree_belt_existing.shp', 'green'), ('Road centrelines (with widths)', '{O}/{P}Roads_existing.shp', 'lines'),
                 ('Vacant / open land', '{O}/{P}Vacant_open_land.shp', 'green')],
    'design': [('Elevation (hillshade)', '{O}/{P}Elevation_overlay.png', 'raster'), ('Slope', '{O}/{P}Slope_overlay.png', 'raster'),
               ('Slope classes', '{O}/{P}Slope_classes.shp', 'slope'), ('Contours', '{O}/{P}Contours.shp', 'contours'),
               ('Steep-slope reserve (kept green)', '{O}/{P}Steep_slope_reserve.shp', 'steep'),
               ('Road draft: grid iron', '{O}/{P}Roads_draft_grid.shp', 'draft'), ('Road draft: curvilinear', '{O}/{P}Roads_draft_curvilinear.shp', 'draft'),
               ('Plots and land use', '{O}/_work/plots_landuse.gpkg', 'plots_design'), ('Facility / green sites', '{O}/_work/reserves_landuse.gpkg', 'reserves'),
               ('Plots (before land use)', '{O}/_work/plots_final.gpkg', 'blocks'), ('Road reserves', '{O}/_work/layout_roads.gpkg', 'roads'),
               ('Blocks', '{O}/_work/layout_blocks.gpkg', 'blocks'), ('Road draft (automatic)', '{O}/{P}Roads_draft.shp', 'draft'),
               ('Existing buildings', '{O}/_work/buildings.gpkg', 'buildings'), ('Design audit findings', '{O}/_work/design_audit.csv', 'audit')],
}
@app.get('/api/projects/<pid>/layers')
def layers(pid):
    m = meta(pid); O = os.path.basename(outdir(pid)); P = prefix(pid); d = pdir(pid); out = []
    for label, tpl, kind in LAYERS.get(m.get('workflow', 'design'), []):
        rel = tpl.format(O=O, P=P)
        if os.path.exists(os.path.join(d, rel)):
            L_ = dict(label=label, path=rel, kind=kind)
            if kind == 'raster':
                j = os.path.join(d, rel[:-4] + '.json')
                if not os.path.exists(j): continue
                L_['bounds'] = json.load(open(j))['bounds']
            out.append(L_)
    files = []
    for f in sorted(glob.glob(os.path.join(outdir(pid), '*'))) + sorted(glob.glob(os.path.join(outdir(pid), '_work', '*.png'))):
        if f.lower().endswith(('.png', '.xlsx', '.json', '.csv')): files.append(os.path.relpath(f, d).replace('\\', '/'))
    downloads = []
    for L_ in out:
        if L_['kind'] == 'raster': continue
        downloads.append(dict(id='L:' + L_['path'], label=L_['label'], kind='shapefile' if not L_['path'].endswith('.csv') else 'table (csv) + points shapefile', default=L_['kind'] in ('plots', 'plots_design', 'buildings', 'blocks', 'roads', 'reserves')))
    for f in files:
        nm = f.split('/')[-1]
        if nm.endswith('.json') and 'overlay' in nm: continue
        downloads.append(dict(id='F:' + f, label=nm, kind={'png': 'map / image', 'xlsx': 'Excel table', 'json': 'summary', 'csv': 'table'}.get(nm.rsplit('.', 1)[-1], 'file'), default=nm.endswith(('.png', '.xlsx')) and '_work/' not in f))
    return jsonify(layers=out, files=files, downloads=downloads)
@app.get('/api/projects/<pid>/geojson')
def geojson(pid):
    rel = request.args.get('f', ''); f = safe(pid, rel)
    if f.endswith('.csv'):                                           # design audit findings (x, y in EPSG:2136)
        import pandas as pd, geopandas as gpd
        t = pd.read_csv(f); g = gpd.GeoDataFrame(t.drop(columns=['x', 'y']), geometry=gpd.points_from_xy(t.x, t.y), crs=2136).to_crs(4326)
        return jsonify(json.loads(g.to_json(drop_id=True)))
    _per_road(f)
    return jsonify(to_geojson(f, simplify_ft=0.5))
@app.get('/api/projects/<pid>/file')
def file(pid): return send_file(safe(pid, request.args.get('f', '')))
@app.get('/api/projects/<pid>/download')
def download(pid):
    """the ticked outputs as one zip: map layers as shapefiles (EPSG:2136), maps / tables as they are"""
    import geopandas as gpd, tempfile, pandas as pd
    items = [x for x in request.args.get('items', '').split('|') if x]; d = pdir(pid); tmp = tempfile.mkdtemp(); buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for it in items:
            kind, rel = it[:2], it[2:]
            try: f = safe(pid, rel)
            except Exception: continue
            base = os.path.splitext(os.path.basename(f))[0]
            if kind == 'L:':
                if f.endswith('.csv'):
                    t = pd.read_csv(f); g = gpd.GeoDataFrame(t.drop(columns=['x', 'y']), geometry=gpd.points_from_xy(t.x, t.y), crs=2136)
                    z.write(f, f'tables/{os.path.basename(f)}')
                else:
                    g = gpd.read_file(f)
                    if g.crs is None: g = g.set_crs(2136)
                    g = g.to_crs(2136)
                for c in list(g.columns):
                    if c != 'geometry' and str(g[c].dtype) == 'object': g[c] = g[c].astype(str).str.slice(0, 250)
                for gt in sorted(set(g.geom_type.dropna())):              # a shapefile holds one geometry type
                    sub = g[g.geom_type == gt]; nm = base if len(set(g.geom_type.dropna())) == 1 else f'{base}_{gt}'
                    out = os.path.join(tmp, nm + '.shp'); sub.to_file(out)
                    for ext in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
                        if os.path.exists(out[:-4] + ext): z.write(out[:-4] + ext, f'shapefiles/{nm}{ext}')
            else:
                z.write(f, ('maps/' if f.endswith('.png') else 'tables/' if f.endswith(('.xlsx', '.csv')) else '') + os.path.basename(f))
    shutil.rmtree(tmp, ignore_errors=True); buf.seek(0)
    return send_file(buf, mimetype='application/zip', as_attachment=True, download_name=f'{meta(pid)["name"]}_outputs.zip')
@app.get('/api/projects/<pid>/zip')
def zip_outputs(pid):
    o = outdir(pid); buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in glob.glob(os.path.join(o, '*')):
            if os.path.isfile(f): z.write(f, os.path.relpath(f, o))
        for f in glob.glob(os.path.join(o, '_work', '*.gpkg')) + glob.glob(os.path.join(o, '_work', '*.png')) + glob.glob(os.path.join(o, '_work', '*.csv')):
            z.write(f, os.path.join('design_layers', os.path.basename(f)))
    buf.seek(0); return send_file(buf, mimetype='application/zip', as_attachment=True, download_name=f'{meta(pid)["name"]}_outputs.zip')

# ------------------------------------------------------------------ 3D view
@app.get('/api/projects/<pid>/dem/<int:z>/<int:x>/<int:y>.png')
def dem_tile(pid, z, x, y):
    import scene3d
    from flask import Response
    try: f, fill = scene3d.dem_for(pdir(pid), outdir(pid), os.path.join(pdir(pid), 'site.geojson'))
    except Exception: f, fill = None, 0.0                              # no elevation data: flat tiles
    r = Response(scene3d.terrarium_png(f, fill, z, x, y) if f else scene3d.flat_png(0.0), mimetype='image/png'); r.headers['Cache-Control'] = 'max-age=86400'; return r
@app.get('/api/projects/<pid>/scene3d')
def scene3d_info(pid):
    """buildings with heights + where the elevation comes from"""
    import scene3d
    try: f, fill = scene3d.dem_for(pdir(pid), outdir(pid), os.path.join(pdir(pid), 'site.geojson')); dem = 'project DEM' if '_work' in f else 'Copernicus 30 m DEM (downloaded for the 3D view)'
    except Exception as ex: dem = None
    return jsonify(buildings=scene3d.buildings_fc(outdir(pid), prefix(pid)), dem=dem)

# B20: an unexpected server error is answered in plain words (the details go to the server console only)
from werkzeug.exceptions import HTTPException
@app.errorhandler(Exception)
def _plain_error(ex):
    if isinstance(ex, HTTPException): return ex
    import traceback; traceback.print_exc()
    return jsonify(error=f'Something went wrong on the server ({type(ex).__name__}). The action was not completed; nothing was changed. Details are in the app console.'), 500

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--lan', action='store_true', help='also serve to other computers on the office network'); ap.add_argument('--port', type=int, default=5050)
    a = ap.parse_args(); print(f'LP Toolkit web app: http://localhost:{a.port}  (projects in {ROOT})')
    app.run(host='0.0.0.0' if a.lan else '127.0.0.1', port=a.port, debug=False, threaded=True)
