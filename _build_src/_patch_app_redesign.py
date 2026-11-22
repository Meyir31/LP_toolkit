p = 'webapp/app.py'; s = open(p, encoding='utf-8').read()
def rep(a, b, n=1):
    global s
    assert a in s, a[:70]; s = s.replace(a, b, n)
# zones are an input kind too
s = s.replace("('site', 'roads', 'stream', 'existing')", "('site', 'roads', 'stream', 'existing', 'zones')")
# shared launcher + design parameters
rep("@app.post('/api/projects/<pid>/run')\ndef run(pid):", '''def design_args(j):
    a = []
    for k, flag in (('band', '--band'), ('block_len', '--block-len'), ('local_width', '--local-width'), ('collector_width', '--collector-width'), ('max_parcel_ac', '--max-parcel-ac')):
        if j.get(k): a += [flag, str(j[k])]
    return a
def launch(pid, cmd, pending=None):
    d = pdir(pid)
    log = open(os.path.join(d, 'run.log'), 'w', encoding='utf-8'); log.write('$ lp_toolkit.py ' + ' '.join(f'"{c}"' if ' ' in c else c for c in cmd[5:]) + '\\n'); log.flush()
    RUNS[pid] = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=TOOLKIT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    m = meta(pid); m['last_run'] = time.strftime('%Y-%m-%d %H:%M'); m['pending_load'] = pending; save_meta(pid, m)
def base_cmd(pid, wf='design'):
    m = meta(pid); site = os.path.join(pdir(pid), 'site.geojson')
    if not os.path.exists(site): raise ValueError('draw or upload the site boundary first')
    return [PY, '-u', '-W', 'ignore', SCRIPT, wf, '--site', site, '--name', m['name'], '--title', m.get('title') or m['name']]
def site_inputs(pid, j):
    d = pdir(pid); a = []
    if os.path.exists(os.path.join(d, 'existing.geojson')): a += ['--existing', os.path.join(d, 'existing.geojson')]
    if os.path.exists(os.path.join(d, 'stream.geojson')): a += ['--stream', os.path.join(d, 'stream.geojson'), '--stream-buffer', str(j.get('stream_buffer', 100))]
    return a + ['--steep', str(j.get('steep', 30))]
def terrain_done(pid): return os.path.exists(os.path.join(outdir(pid), prefix(pid) + 'Terrain_summary.json'))
@app.post('/api/projects/<pid>/design_roads')
def design_roads(pid):
    """one blended road design for the whole site (site analysis first if it is missing); loads into the roads for editing"""
    if pid in RUNS and RUNS[pid].poll() is None: return jsonify(error='already running'), 400
    j = request.get_json(force=True)
    try: cmd = base_cmd(pid)
    except ValueError as e: return jsonify(error=str(e)), 400
    cmd += ['--roads', 'draft', '--pattern', j.get('pattern', 'mixed'), '--only', 'roads' if terrain_done(pid) else 'site,roads'] + site_inputs(pid, j) + design_args(j)
    launch(pid, cmd, pending='draft'); return jsonify(ok=True)
@app.post('/api/projects/<pid>/redesign')
def redesign(pid):
    """redesign only inside the drawn areas: roads outside them (clipped at the area edge) and the planner's own roads are kept"""
    import geopandas as gpd, shapely
    if pid in RUNS and RUNS[pid].poll() is None: return jsonify(error='already running'), 400
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
            '--zones', os.path.join(d, 'zones_run.geojson'), '--only-zones'] + site_inputs(pid, j) + design_args(j)
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
@app.post('/api/projects/<pid>/run')
def run(pid):''')
# status reports a pending load
rep("    return jsonify(running=running, log=txt[-20000:], stages=stages, finished=len(done), failed=bool(failed), returncode=None if p is None else p.poll())",
    "    pend = meta(pid).get('pending_load') if not running else None\n    return jsonify(running=running, log=txt[-20000:], stages=stages, finished=len(done), failed=bool(failed), returncode=rc, pending_load=pend)")
# a fresh design run starts without a stale lock file
rep("    cmd += ['--roads', 'draft', '--pattern', j.get('pattern', 'mixed'), '--only', 'roads' if terrain_done(pid) else 'site,roads'] + site_inputs(pid, j) + design_args(j)\n    launch(pid, cmd, pending='draft')",
    "    lf = os.path.join(pdir(pid), 'lock.geojson')\n    if os.path.exists(lf): os.remove(lf)\n    cmd += ['--roads', 'draft', '--pattern', j.get('pattern', 'mixed'), '--only', 'roads' if terrain_done(pid) else 'site,roads'] + site_inputs(pid, j) + design_args(j)\n    launch(pid, cmd, pending='draft')")
# the normal run: roads come from the planner's roads.geojson
rep("        mode = j.get('roads_mode', 'file')", "        mode = 'file'")
open(p, 'w', encoding='utf-8').write(s); print('app ok')
