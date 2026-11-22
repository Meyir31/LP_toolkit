"""Draw a road -> its surface at once, and the blocks it crosses are re-plotted (local update, ~1 s)."""
import os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'webapp'))
def patch(p, a, b):
    s = open(p, encoding='utf-8').read(); assert s.count(a) == 1, (p, s.count(a), a[:80]); open(p, 'w', encoding='utf-8').write(s.replace(a, b))

# ---------------- server ----------------
patch('app.py', "@app.get('/api/projects/<pid>/status')", '''@app.post('/api/projects/<pid>/design/local_update')
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
@app.get('/api/projects/<pid>/status')''')
patch('app.py', "EDIT_PATHS = re.compile(r'^/api/projects/([^/]+)/(layer/|upload/|edit/op|plots/split|plots/merge|plots/undo)')",
      "EDIT_PATHS = re.compile(r'^/api/projects/([^/]+)/(layer/|upload/|edit/op|plots/split|plots/merge|plots/undo|design/local_update)')")

# ---------------- page ----------------
patch('static/app.js', "  if (kind === 'roads' || kind === 'existing') { updateAngles(); drawReserves(); rcLater = null; setTimeout(refreshStatus, 600); }",
      "  if (kind === 'roads' || kind === 'existing') { updateAngles(); drawReserves(); rcLater = null; queueLocalUpdate(); }")
patch('static/app.js', "$('#delProj').onclick = async () => {", """// ---- a road drawn or edited in a planned design: its surface goes in and the blocks it crosses are re-plotted (~1 s) ----
let luT = null, luBusy = false;
function queueLocalUpdate() {
  if (!P || P.workflow !== 'design' || !LAYER_INDEX.some(l => l.kind === 'plots_design')) { setTimeout(refreshStatus, 600); return; }
  clearTimeout(luT); luT = setTimeout(localUpdate, 1200);              // after the edit settles (several quick edits: one update)
}
async function localUpdate() {
  if (luBusy) { queueLocalUpdate(); return; } luBusy = true;
  try {
    const r = await post(`/api/projects/${P.id}/design/local_update`);
    if (r.ok && (r.plots || r.added || r.removed)) { await reloadKinds(['plots_design', 'reserves', 'roads', 'blocks']); alert('Plan updated: ' + r.msg); }
    else if (!r.ok && r.msg) alert(r.msg);
  } catch (e) { alert(e.message); }
  luBusy = false; refreshStatus();
}
async function reloadKinds(kinds) {
  for (const L_ of LAYER_INDEX.filter(l => kinds.includes(l.kind))) {
    const was = results[L_.path] && resGroup.hasLayer(results[L_.path]);
    if (results[L_.path]) { resGroup.removeLayer(results[L_.path]); delete results[L_.path]; }
    if (was) await toggleLayer(L_, true);
  }
}
$('#delProj').onclick = async () => {""")
# reserve bands of the drawn roads above the plots
patch('static/app.js', "const reserveLayer = L.layerGroup().addTo(map);",
      "map.createPane('reservePane'); map.getPane('reservePane').style.zIndex = 420; map.getPane('reservePane').style.pointerEvents = 'none';\nconst RES_R = L.svg({ pane: 'reservePane' });\nconst reserveLayer = L.layerGroup().addTo(map);")
patch('static/app.js', "    L.geoJSON(poly, { interactive: false, style: { color: '#555', weight: .6, fillColor: k === 'existing' ? '#9e9e9e' : '#bdbdbd', fillOpacity: .45 } }).addTo(reserveLayer); } catch (er) {} });",
      "    L.geoJSON(poly, { interactive: false, pane: 'reservePane', renderer: RES_R, style: { color: '#555', weight: .6, fillColor: k === 'existing' ? '#9e9e9e' : '#bdbdbd', fillOpacity: .75 } }).addTo(reserveLayer); } catch (er) {} });")
patch('static/app.js', "  reserveLayer.eachLayer(x => x.bringToBack?.()); }, 150); }", "  }, 150); }")
print('ok')
