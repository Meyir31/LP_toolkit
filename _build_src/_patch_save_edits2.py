"""Save edits: 'unsaved' = an edit made in the app after the save point; a finished run becomes the new save point."""
import os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'webapp'))
def patch(p, a, b):
    s = open(p, encoding='utf-8').read(); assert s.count(a) == 1, (p, s.count(a), a[:80]); open(p, 'w', encoding='utf-8').write(s.replace(a, b))
patch('app.py', '''def edits_state(pid):
    sd = save_dir(pid); stamp = os.path.join(sd, 'saved.json')
    if not os.path.exists(stamp): return dict(saved_at=None, dirty=False)
    info = json.load(open(stamp)); t = info.get('time', 0)
    dirty = any(os.path.getmtime(f) > t + 1 for f in edit_files(pid) if not f.endswith(('.prj', '.cpg')))
    return dict(saved_at=info.get('label'), dirty=dirty)''', '''EDIT_PATHS = re.compile(r'^/api/projects/([^/]+)/(layer/|upload/|edit/op|plots/split|plots/merge|plots/undo)')
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
    return dict(saved_at=label, dirty=m.get('last_edit', 0) > t)''')
patch('app.py', '''    if is_running(pid): return jsonify(error='a run is in progress: save when it has finished'), 400
    d = pdir(pid); sd = save_dir(pid)
    if os.path.exists(sd): shutil.rmtree(sd)
    os.makedirs(sd); files = edit_files(pid)
    for f in files:
        dst = os.path.join(sd, os.path.relpath(f, d)); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(f, dst)
    label = time.strftime('%Y-%m-%d %H:%M'); json.dump(dict(time=time.time(), label=label, files=[os.path.relpath(f, d) for f in files]), open(os.path.join(sd, 'saved.json'), 'w'), indent=1)
    vd = os.path.join(d, '_versions', time.strftime('%Y%m%d-%H%M%S')); shutil.copytree(sd, vd)
    for old in sorted(glob.glob(os.path.join(d, '_versions', '*')))[:-10]: shutil.rmtree(old, ignore_errors=True)
    return jsonify(ok=True, saved_at=label, files=len(files))''', '''    if is_running(pid): return jsonify(error='a run is in progress: save when it has finished'), 400
    label, n = _save_point(pid); return jsonify(ok=True, saved_at=label, files=n)''')
patch('app.py', '''    t = info['time']
    for f in edit_files(pid):                                          # copied-back files keep their old times: mark them as matching the save point
        if os.path.relpath(f, d) in info['files']: os.utime(f, (t, t))
    return jsonify(ok=True, restored=n, saved_at=info.get('label'))''', '''    m = meta(pid); m['last_edit'] = info['time'] - 1; save_meta(pid, m)  # back at the save point: nothing unsaved
    for k in ('_edit_history', '_plot_history'): shutil.rmtree(os.path.join(d, k), ignore_errors=True)    # the undo steps belong to the discarded edits
    return jsonify(ok=True, restored=n, saved_at=info.get('label'))''')

# ---------------- page: Save / Discard buttons (Features group, both workflows), Ctrl+S, unsaved marker ----------------
patch('static/icons.js', "    edit: S(", """    save: S(`<path d="M4 4h12l4 4v12H4z" fill="${BL}" stroke="${BD}"/><rect x="7" y="4" width="8" height="5" fill="#fff" stroke="${BD}"/><rect x="7" y="13" width="10" height="7" fill="#E3F2FD" stroke="${BD}"/>`),
    discard: S(`<path d="M4 4h12l4 4v12H4z" fill="#ECEFF1" stroke="${K}"/><path d="M8 10l8 8M16 10l-8 8" stroke="${RD}" stroke-width="2.2"/>`),
    edit: S(""")
patch('static/features.js', "  rib.insertBefore(grp, rib.querySelector('.rhide'));",
      """  rib.insertBefore(grp, rib.querySelector('.rhide'));
  const sgrp = document.createElement('div'); sgrp.className = 'grp g-save';
  sgrp.innerHTML = `<div class="gb"><button data-a="save" title="Save edits (Ctrl+S): a save point of every editable layer">${IC.save}<span>Save</span></button><button data-a="discard" title="Discard edits: every editable layer back to the last save point">${IC.discard}<span>Discard</span></button></div><span class="gl">Edits</span>`;
  rib.insertBefore(sgrp, grp); L.DomEvent.disableClickPropagation(sgrp);
  async function saveEdits() { if (!P) return; try { const r = await post(`/api/projects/${P.id}/edits/save`); alert(`Edits saved (${r.saved_at}).`); markSaved(false, r.saved_at); } catch (e) { alert(e.message); } }
  async function discardEdits() { if (!P) return;
    if (!confirm('Discard all edits made since the last save point? Every editable layer returns to how it was then.')) return;
    try { const r = await post(`/api/projects/${P.id}/edits/discard`); alert(`Edits discarded: back to the save point of ${r.saved_at}.`); markSaved(false, r.saved_at); close(); await openProject(P.id); } catch (e) { alert(e.message); } }
  function markSaved(dirty, at) { const b = sgrp.querySelector('[data-a=save]'); b.classList.toggle('dirty', !!dirty);
    b.title = (dirty ? 'Unsaved edits. ' : '') + 'Save edits (Ctrl+S)' + (at ? ` - last save point ${at}` : ''); }
  window.markSaved = markSaved;
  sgrp.querySelector('[data-a=save]').onclick = saveEdits; sgrp.querySelector('[data-a=discard]').onclick = discardEdits;
  document.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveEdits(); } });""")
patch('static/app.js', "  showRoadsChanged(!!s.roads_changed);", "  showRoadsChanged(!!s.roads_changed); if (s.edits && window.markSaved) markSaved(s.edits.dirty, s.edits.saved_at);")
open('static/app.css', 'a', encoding='utf-8').write("""
/* Save edits: marked while there are unsaved edits */
.ribbon button.dirty { background: #fff3e0; border-color: #ff8f00; position: relative; }
.ribbon button.dirty::after { content: ''; position: absolute; top: 3px; right: 5px; width: 8px; height: 8px; border-radius: 50%; background: #ff6d00; }
""")
print('ok')
