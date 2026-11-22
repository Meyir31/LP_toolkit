p = 'webapp/static/app.js'; s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:60]; s = s.replace(a, b, 1)
rep("$$('input[name=rmode]').forEach(r => r.onchange = () => { const m = $('input[name=rmode]:checked').value; $('#drawRoads').hidden = m !== 'file'; $('#draftBox').hidden = m !== 'draft'; });",
    "$$('input[name=rmode]').forEach(r => r.onchange = () => { const m = $('input[name=rmode]:checked').value; $('#drawRoads').hidden = m !== 'file'; $('#draftBox').hidden = m !== 'draft'; $('#patBox').hidden = m !== 'auto'; if (m === 'draft') loadPatterns(); });")
a0 = s.index("$('#loadDraft').onclick"); a1 = s.index("\n", s.index("catch (e) { alert(e.message); } };", a0)) + 1
s = s[:a0] + """// ---- site analysis (terrain) first, then road patterns ----
async function runOnly(stage, extra = {}) {
  const body = { workflow: P.workflow, only: stage, steep: +$('#steep').value, stream_buffer: +$('#streamBuf').value, roads_mode: $('input[name=rmode]:checked').value, ...extra };
  try { await post(`/api/projects/${P.id}/run`, body); refreshStatus(); } catch (e) { alert(e.message); }
}
$('#siteBtn').onclick = () => { $('#terrState').textContent = 'running...'; runOnly('site'); };
$('#draftBtn').onclick = () => { $('#patTable').innerHTML = '<p class="hint">Drafting the three patterns (1 to 3 minutes)...</p>'; runOnly('roads', { roads_mode: 'draft' }); };
const SLOPE_COL = { 'Flat': '#1a9850', 'Gentle': '#91cf60', 'Moderate': '#fee08b', 'Steep': '#fc8d59', 'Very steep': '#d73027' };
const slopeCol = c => SLOPE_COL[Object.keys(SLOPE_COL).find(k => (c || '').startsWith(k))] || '#ccc';
async function loadTerrain() {
  if (!P || P.workflow !== 'design') return;
  const t = await api(`/api/projects/${P.id}/terrain`);
  if (!t.relief) { $('#terrSum').innerHTML = ''; $('#terrState').textContent = 'not done yet'; return; }
  $('#terrState').textContent = 'done';
  $('#terrSum').innerHTML = `<table class="mini"><tr><th colspan="2">Elevation ${t.elev_min}-${t.elev_max} m (relief ${t.relief} m), contours every ${t.contour_interval} m, mean slope ${t.mean_slope_pct}%</th></tr>` +
    t.classes.map(c => `<tr><td><span class="swatch" style="background:${slopeCol(c.cls)}"></span>${c.cls}</td><td>${c.area_ac} ac (${c.share}%)</td></tr>`).join('') +
    (t.steep_pct > 0 ? `<tr><td><b>Kept green (slopes >= ${t.steep_pct}%)</b></td><td><b>${t.steep_reserve_ac} ac</b></td></tr>` : '') + '</table>';
  const r = await api(`/api/projects/${P.id}/layers`); $('#terrLayers').innerHTML = '';
  for (const L_ of r.layers.filter(l => ['raster', 'slope', 'contours', 'steep'].includes(l.kind))) {
    const lab = document.createElement('label'); const cb = document.createElement('input'); cb.type = 'checkbox';
    cb.checked = !!(results[L_.path] && resGroup.hasLayer(results[L_.path])) || L_.label === 'Contours' || L_.label === 'Slope';
    cb.onchange = () => toggleLayer(L_, cb.checked); lab.append(cb, ' ' + L_.label); $('#terrLayers').append(lab); if (cb.checked) toggleLayer(L_, true);
  }
}
async function loadPatterns() {
  if (!P) return; const ps = await api(`/api/projects/${P.id}/patterns`);
  if (!ps.length) { if (!$('#patTable').textContent.includes('Drafting')) $('#patTable').innerHTML = ''; return; }
  const score = m => m.approx_plots - (m.steep_road_m || 0) / 10, best = ps.reduce((a, b) => score(b) > score(a) ? b : a);
  $('#patTable').innerHTML = '<table class="mini"><tr><th>Pattern</th><th>New road</th><th>Road > 18%</th><th>~Plots</th><th></th></tr>' +
    ps.map(m => `<tr class="${m === best ? 'best' : ''}"><td>${m.name}${m === best ? ' (suggested)' : ''}</td><td>${m.new_road_km} km</td><td>${m.steep_road_m ?? '-'} m</td><td>${m.approx_plots}</td>` +
      `<td><button data-show="${m.pattern}" class="ghost">Show</button> <button data-use="${m.pattern}">Use</button></td></tr>`).join('') + '</table>' +
    `<p class="hint">"Show" draws the pattern on the map; "Use" copies it into your roads for editing. Comparison image: Roads_patterns.png in Results.</p>`;
  const r = await api(`/api/projects/${P.id}/layers`);
  $$('#patTable button[data-show]').forEach(b => b.onclick = () => {
    for (const L_ of r.layers.filter(l => l.kind === 'draft')) toggleLayer(L_, L_.path.endsWith(`Roads_draft_${b.dataset.show}.shp`));
  });
  $$('#patTable button[data-use]').forEach(b => b.onclick = async () => {
    try { const fc = await post(`/api/projects/${P.id}/draft_to_roads?pattern=${b.dataset.use}`); loadInput('roads', fc);
      for (const L_ of r.layers.filter(l => l.kind === 'draft')) toggleLayer(L_, false);
      $('input[name=rmode][value=file]').checked = true; $('input[name=rmode][value=file]').onchange(); setEditGroup('roads');
      alert('Pattern copied into your roads. Edit them on the map (edit tool top left; click a road to change its width), then run from the "roads" stage.'); } catch (e) { alert(e.message); }
  });
}
""" + s[a1:]
rep("  const body = { workflow: P.workflow, profile: $('#profile').value, roads_mode: $('input[name=rmode]:checked').value, stream_buffer: +$('#streamBuf').value };",
    "  const body = { workflow: P.workflow, profile: $('#profile').value, roads_mode: $('input[name=rmode]:checked').value, stream_buffer: +$('#streamBuf').value, steep: +$('#steep').value };\n  if (body.roads_mode === 'auto') body.pattern = $('#pattern').value;")
rep("  if (wasRunning && !s.running) loadResults(true); wasRunning = s.running;",
    "  if (wasRunning && !s.running) { await loadResults(true); loadTerrain(); loadPatterns(); } wasRunning = s.running;")
rep("  clearResults(); refreshInputState(); refreshStatus(); loadResults();",
    "  clearResults(); refreshInputState(); refreshStatus(); await loadResults(); loadTerrain(); loadPatterns();")
rep("      case 'draft':", """      case 'slope': return { color: '#555', weight: .3, fillColor: slopeCol(p.cls), fillOpacity: .55 };
      case 'contours': return { color: '#6d4c41', weight: (p.major === true || p.major === 1 || p.major === 'True') ? 1.6 : .6, opacity: .9 };
      case 'steep': return { color: '#b71c1c', weight: 1, fillColor: '#2e7d32', fillOpacity: .45, dashArray: '4 3' };
      case 'draft':""")
rep("async function toggleLayer(L_, on) {\n  if (!on) { if (results[L_.path]) resGroup.removeLayer(results[L_.path]); return; }\n  if (!results[L_.path]) {",
    "async function toggleLayer(L_, on) {\n  if (!on) { if (results[L_.path]) resGroup.removeLayer(results[L_.path]); return; }\n  if (!results[L_.path] && L_.kind === 'raster') results[L_.path] = L.imageOverlay(`/api/projects/${P.id}/file?f=${encodeURIComponent(L_.path)}`, L_.bounds, { opacity: .75 });\n  if (!results[L_.path]) {")
rep("  const DEFAULT_ON = new Set(['plots', 'plots_design', 'reserves', 'roads', 'draft']);", "  const DEFAULT_ON = new Set(['plots', 'plots_design', 'reserves', 'roads']);")
rep("  $('#legend').innerHTML = Object.entries(leg)", "  const legS = kinds.has('slope') ? Object.entries(SLOPE_COL).map(([k, c]) => `<span><i style=\"background:${c}\"></i>${k}</span>`).join('') : '';\n  $('#legend').innerHTML = legS + Object.entries(leg)")
open(p, 'w', encoding='utf-8').write(s); print('js ok')
