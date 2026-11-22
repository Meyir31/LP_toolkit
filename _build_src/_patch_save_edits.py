"""Save edits / Discard edits (ArcGIS Pro style): a save point of every editable layer; discard returns to it."""
import os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'webapp'))
def patch(p, a, b):
    s = open(p, encoding='utf-8').read(); assert s.count(a) == 1, (p, s.count(a), a[:80]); open(p, 'w', encoding='utf-8').write(s.replace(a, b))

patch('app.py', "@app.get('/api/projects/<pid>/status')", '''# ------------------------------------------------------------------ save edits / discard edits
SIDE = ('.shp', '.shx', '.dbf', '.prj', '.cpg')
def edit_files(pid):
    """every file the editing tools write: inputs (roads, site, streams, zones) + the editable outputs of the workflow"""
    m = meta(pid); d = pdir(pid); O = os.path.basename(outdir(pid)); P_ = prefix(pid); out = []
    for k in ('site', 'roads', 'existing', 'stream', 'zones'):
        f = os.path.join(d, f'{k}.geojson')
        if os.path.exists(f): out.append(f)
    for wf in ('existing', 'design'):
        for _, tpl in EDITABLE.get(wf, []):
            f = os.path.join(d, tpl.format(O=O, P=P_))
            if f.endswith('.shp'): out += [f[:-4] + e for e in SIDE if os.path.exists(f[:-4] + e)]
            elif os.path.exists(f) and f not in out: out.append(f)
    for f in (os.path.join(outdir(pid), '_work', 'layout_roads.gpkg'), os.path.join(outdir(pid), '_work', 'plots_landuse.gpkg')):
        if os.path.exists(f) and f not in out: out.append(f)
    return out
def save_dir(pid): return os.path.join(pdir(pid), '_saved')
def edits_state(pid):
    sd = save_dir(pid); stamp = os.path.join(sd, 'saved.json')
    if not os.path.exists(stamp): return dict(saved_at=None, dirty=False)
    info = json.load(open(stamp)); t = info.get('time', 0)
    dirty = any(os.path.getmtime(f) > t + 1 for f in edit_files(pid) if not f.endswith(('.prj', '.cpg')))
    return dict(saved_at=info.get('label'), dirty=dirty)
@app.post('/api/projects/<pid>/edits/save')
def edits_save(pid):
    """a save point: copies of every editable file (also kept in _versions, last 10)"""
    if is_running(pid): return jsonify(error='a run is in progress: save when it has finished'), 400
    d = pdir(pid); sd = save_dir(pid)
    if os.path.exists(sd): shutil.rmtree(sd)
    os.makedirs(sd); files = edit_files(pid)
    for f in files:
        dst = os.path.join(sd, os.path.relpath(f, d)); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(f, dst)
    label = time.strftime('%Y-%m-%d %H:%M'); json.dump(dict(time=time.time(), label=label, files=[os.path.relpath(f, d) for f in files]), open(os.path.join(sd, 'saved.json'), 'w'), indent=1)
    vd = os.path.join(d, '_versions', time.strftime('%Y%m%d-%H%M%S')); shutil.copytree(sd, vd)
    for old in sorted(glob.glob(os.path.join(d, '_versions', '*')))[:-10]: shutil.rmtree(old, ignore_errors=True)
    return jsonify(ok=True, saved_at=label, files=len(files))
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
    t = info['time']
    for f in edit_files(pid):                                          # copied-back files keep their old times: mark them as matching the save point
        if os.path.relpath(f, d) in info['files']: os.utime(f, (t, t))
    return jsonify(ok=True, restored=n, saved_at=info.get('label'))
@app.get('/api/projects/<pid>/edits/state')
def edits_state_api(pid): return jsonify(edits_state(pid))
@app.get('/api/projects/<pid>/status')''')
patch('app.py', "                   roads_changed=(not running) and roads_changed(pid))",
      "                   roads_changed=(not running) and roads_changed(pid), edits=edits_state(pid))")
# a finished run is the new baseline: save automatically so its own outputs do not count as unsaved edits
print('ok')
