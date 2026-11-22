"""Roads edited after the plan was made -> banner 'Update the plan' (re-run from the roads stage)."""
import os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'webapp'))
def patch(p, a, b):
    s = open(p, encoding='utf-8').read(); assert s.count(a) == 1, (p, s.count(a), a[:80]); open(p, 'w', encoding='utf-8').write(s.replace(a, b))

# ---------------- server: fingerprint of the roads a plan was made from ----------------
patch('app.py', "@app.get('/api/projects/<pid>/status')", '''def roads_hash(pid):
    """fingerprint of the planner's roads (design roads + existing roads to keep)"""
    import hashlib
    h = hashlib.md5()
    for k in ('roads', 'existing'):
        f = os.path.join(pdir(pid), f'{k}.geojson')
        if os.path.exists(f): h.update(open(f, 'rb').read())
    return h.hexdigest()
def roads_changed(pid):
    """the roads were edited after the current plan (plots + land use) was made from them"""
    m = meta(pid)
    if m.get('workflow') != 'design' or not os.path.exists(os.path.join(outdir(pid), '_work', 'plots_landuse.gpkg')): return False
    if not m.get('plan_roads_hash'):                                    # plans made before this check: compare file times
        f = os.path.join(pdir(pid), 'roads.geojson')
        return os.path.exists(f) and os.path.getmtime(f) > os.path.getmtime(os.path.join(outdir(pid), '_work', 'plots_landuse.gpkg')) + 5
    return m['plan_roads_hash'] != roads_hash(pid)
@app.get('/api/projects/<pid>/status')''')
patch('app.py', "    return jsonify(running=running, log=txt[-20000:], stages=stages, finished=len(done), failed=bool(failed), returncode=rc, pending_load=pend, progress=prog, notes=note, failure=failure_summary(txt, stages, len(done)) if failed else None)",
      "    return jsonify(running=running, log=txt[-20000:], stages=stages, finished=len(done), failed=bool(failed), returncode=rc, pending_load=pend, progress=prog, notes=note, failure=failure_summary(txt, stages, len(done)) if failed else None,\n                   roads_changed=(not running) and roads_changed(pid))")
patch('app.py', "    m['last_run'] = time.strftime('%Y-%m-%d %H:%M'); m['pid'] = RUNS[pid].pid; save_meta(pid, m)\n    return jsonify(ok=True, cmd=cmd[3:])",
      "    m['last_run'] = time.strftime('%Y-%m-%d %H:%M'); m['pid'] = RUNS[pid].pid\n"
      "    if wf == 'design' and ('--from' not in cmd or cmd[cmd.index('--from') + 1] in ('site', 'roads')) and ('--only' not in cmd or 'roads' in cmd[cmd.index('--only') + 1].split(',')):\n"
      "        m['plan_roads_hash'] = roads_hash(pid)                         # this run makes the plan from the roads as they are now\n"
      "    save_meta(pid, m)\n    return jsonify(ok=True, cmd=cmd[3:])")

# ---------------- page: banner on the map ----------------
patch('static/app.js', "  const fe = $('#runFail');", """  showRoadsChanged(!!s.roads_changed);
  const fe = $('#runFail');""")
patch('static/app.js', "$('#delProj').onclick = async () => {", """// ---- roads edited after the plan was made: offer to update the plan ----
const rcBox = L.DomUtil.create('div', 'rcbox', map.getContainer()); rcBox.hidden = true; L.DomEvent.disableClickPropagation(rcBox);
let rcLater = null;
function showRoadsChanged(on) {
  if (!on) { rcBox.hidden = true; return; }
  if (rcLater === P?.id) return;
  rcBox.innerHTML = `<b>You changed the roads after this plan was made.</b> The plots and land use do not show the new roads yet.
    <div class="mini">Updating re-runs roads, plots, land use${$('#chamfer')?.checked ? ', corner chamfers' : ''} and the audit from the roads as they are now. Manual edits to plots or land use are replaced.</div>
    <div class="row"><button id="rcGo">Update the plan</button><button id="rcLater" class="ghost">Later</button></div>`;
  rcBox.hidden = false;
  $('#rcGo').onclick = async () => { try { await post(`/api/projects/${P.id}/run`, { workflow: 'design', from: 'roads', chamfer: !!$('#chamfer')?.checked, steep: +$('#steep').value, stream_buffer: +$('#streamBuf').value }); rcBox.hidden = true; $$('.tabs button')[1].click(); refreshStatus(); alert('Updating the plan from the new roads: the map refreshes when the run finishes.'); } catch (e) { alert(e.message); } };
  $('#rcLater').onclick = () => { rcLater = P.id; rcBox.hidden = true; };
}
$('#delProj').onclick = async () => {""")
# a road edit brings the banner back even after 'Later'
patch('static/app.js', "  if (kind === 'roads' || kind === 'existing') { updateAngles(); drawReserves(); }\n}",
      "  if (kind === 'roads' || kind === 'existing') { updateAngles(); drawReserves(); rcLater = null; setTimeout(refreshStatus, 600); }\n}")
open('static/app.css', 'a', encoding='utf-8').write("""
/* roads changed after the plan: update banner */
.rcbox { position: absolute; left: 50%; transform: translateX(-50%); bottom: 26px; z-index: 1003; width: min(520px, 90%); background: #fff8e1; border: 1px solid #ffca28; border-left: 5px solid #ff8f00; border-radius: 6px; padding: 9px 12px; box-shadow: 0 6px 18px rgba(0,0,0,.25); font-size: 13px; }
.rcbox .row { margin-top: 7px; gap: 8px; }
""")
print('ok')
