def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
patch('webapp/static/editor.js', [
 # ---- extra icons ----
 ("    hide: SV('<path d=\"M18 15l-6-6-6 6\"/>'),",
  """    measure: SV('<path d="M3 17L17 3l4 4L7 21z"/><path d="M7 13l2 2M10 10l2 2M13 7l2 2"/>'),
    redemarcate: SV('<rect x="3" y="4" width="18" height="16" rx="1"/><path d="M3 12h18M9 4v8M15 12v8"/><path d="M19 2l2 2-2 2" />'),
    psplit: SV('<path d="M4 6l8-3 8 3v12l-8 3-8-3z"/><path d="M3 21L21 3" stroke-dasharray="3 2"/>'),
    pmerge: SV('<rect x="3" y="5" width="8" height="14"/><rect x="13" y="5" width="8" height="14"/><path d="M9 12h6M13 10l2 2-2 2"/>'),
    pmap: SV('<path d="M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/>'),
    hide: SV('<path d="M18 15l-6-6-6 6"/>'),"""),
 # ---- ribbon: road groups (new layout), plot group (existing situation), measure in both ----
 ("    <button class=\"rhide\" data-a=\"hide\" title=\"Hide the tools\">${IC.hide}</button>`;",
  """    <div class="grp g-plots"><div class="gb">${B('data-t="pselect"', 'select', 'Select', 'Select plots: click; Shift+click adds')}${B('data-t="redemarcate"', 'redemarcate', 'Re-demarcate', 'Re-demarcate the selected blocks')}${B('data-t="psplit"', 'psplit', 'Split plot', 'Split plots with a line')}${B('data-t="pmerge"', 'pmerge', 'Merge', 'Merge selected plots')}${B('data-a="pundo"', 'undo', 'Undo', 'Undo the last plot edit')}${B('data-a="pmap"', 'pmap', 'Update map', 'Update the land use map and tables')}</div><span class="gl">Plots</span></div>
    <div class="grp"><div class="gb">${B('data-t="measure"', 'measure', 'Measure', 'Measure distance or area')}</div><span class="gl">Measure</span></div>
    <button class="rhide" data-a="hide" title="Hide the tools">${IC.hide}</button>`;
  rib.querySelectorAll('.grp').forEach((g, i) => { if (i < 4) g.classList.add('g-roads'); });"""),
 ("  function show(on) { rib.style.display = on ? '' : 'none'; ribTab.style.display = on ? '' : 'none'; if (!on) close(); }",
  """  let WF = 'design';
  function show(on) { mode(on ? 'design' : 'existing'); }
  function mode(wf) { WF = wf; close(); rib.querySelectorAll('.g-roads').forEach(g => g.style.display = wf === 'design' ? '' : 'none'); rib.querySelectorAll('.g-plots').forEach(g => g.style.display = wf === 'existing' ? '' : 'none'); }"""),
 # ---- widgets ----
 ("    snap: () =>", """    measure: () => `<div class="seg2"><label><input type="radio" name="mm" value="dist" checked> Distance</label><label><input type="radio" name="mm" value="area"> Area</label></div>
      <div id="mres" class="mres"><span class="mini">Click on the map to start.</span></div><p class="hint">Click to add points, double-click to finish (the next click starts a new measurement).</p><div class="wf"><button class="ghost" id="mclr">Clear</button></div>`,
    pselect: () => `<div class="psel"></div><p class="hint">Click plots to select them; Shift+click adds. Then choose a plot tool.</p>`,
    redemarcate: () => `<div class="bsel"></div><div class="g2"><span>Rows</span><select id="rr"><option value="auto">Automatic (halve if deep enough)</option><option value="2">Two rows (back to back)</option><option value="1">One row</option></select>
      <span>Min frontage</span><span><input id="rwmin" type="number" min="5" step="1" placeholder="auto" style="width:70px"> m</span>
      <span>Max frontage</span><span><input id="rwmax" type="number" min="6" step="1" placeholder="auto" style="width:70px"> m</span>
      <span>Rear line</span><select id="rsp"><option value="evidence">Follow the image (walls, gaps between buildings)</option><option value="middle">Exact middle of the block</option></select></div>
      <p class="hint">Click a plot to select its whole block (Shift+click adds blocks). Plot lines are placed where the image shows boundaries: walls and gaps between buildings.</p>
      <div class="wf"><button id="rap">Re-demarcate</button></div>`,
    psplit: () => `<div class="psel"></div><p class="hint">Optional: select the plot(s) to split. Then draw a line across them (double-click to finish). Without a selection, every plot the line crosses is split.</p><div class="wf"><button id="psd">Draw split line</button></div>`,
    pmerge: () => `<div class="psel"></div><p class="hint">Select two or more touching plots in the same block, then Merge.</p><div class="wf"><button id="pmg">Merge</button></div>`,
    snap: () =>"""),
 ("  const TITLE = { select: 'Select',", "  const TITLE = { measure: 'Measure', pselect: 'Select plots', redemarcate: 'Re-demarcate blocks', psplit: 'Split plot', pmerge: 'Merge plots', select: 'Select',"),
 # ---- wiring ----
 ("    if (t === 'snap') {", """    if (t === 'measure') { map.doubleClickZoom.disable(); wid.querySelectorAll('input[name=mm]').forEach(r => r.onchange = () => { mPts = []; mDone = false; drawMeasure(); }); q('#mclr').onclick = () => { mPts = []; mDone = false; drawMeasure(); }; drawMeasure(); }
    if (t === 'redemarcate') q('#rap').onclick = async () => {
      if (!pBlocks.size) return alert('Click a plot in each block to re-demarcate.');
      try { await post(`/api/projects/${P.id}/redemarcate`, { blocks: [...pBlocks], rows: q('#rr').value, wmin: +q('#rwmin').value || null, wmax: +q('#rwmax').value || null, split: q('#rsp').value });
        q('.hint').textContent = 'Re-demarcating... the plots reload when it is done (see 2. Run).'; refreshStatus(); } catch (e) { alert(e.message); } };
    if (t === 'psplit') q('#psd').onclick = () => { const d = new L.Draw.Polyline(map, { shapeOptions: { color: '#ff1744', weight: 3, dashArray: '6 4' } }); d.enable();
      map.once(L.Draw.Event.CREATED, async ev => { const ll = ev.layer.getLatLngs(); try { const r = await post(`/api/projects/${P.id}/plots/split`, { line: { type: 'LineString', coordinates: ll.map(p => [p.lng, p.lat]) }, plot_ids: [...pSel.keys()] });
        clearPlots(); await reloadPlots(); refresh(); } catch (e) { alert(e.message); } }); };
    if (t === 'pmerge') q('#pmg').onclick = async () => { try { await post(`/api/projects/${P.id}/plots/merge`, { plot_ids: [...pSel.keys()] }); clearPlots(); await reloadPlots(); refresh(); } catch (e) { alert(e.message); } };
    if (t === 'snap') {"""),
 # ---- clicks: measure anywhere, plots via captureResultClick ----
 ("  function onClick(kind, l, e) {\n    if (!tool || tool === 'create' || tool === 'snap') return;",
  "  function onClick(kind, l, e) {\n    if (tool === 'measure') { L.DomEvent.stop(e); measureClick(e.latlng); return; }\n    if (!tool || tool === 'create' || tool === 'snap') return;"),
 ("  map.on('click', e => { if (tool === 'offset'", "  map.on('click', e => { if (tool === 'measure') measureClick(e.latlng); });\n  map.on('dblclick', e => { if (tool === 'measure') { mDone = true; drawMeasure(); } });\n  map.on('mousemove', e => { if (tool === 'measure' && mPts.length && !mDone) drawMeasure(e.latlng); });\n  map.on('click', e => { if (tool === 'offset'"),
 ("  function close() { prev.clearLayers();", "  function close() { prev.clearLayers(); mg.clearLayers(); mPts = []; mDone = false; map.doubleClickZoom.enable(); if (['pselect', 'redemarcate', 'psplit', 'pmerge'].includes(tool) && !['pselect', 'redemarcate', 'psplit', 'pmerge'].includes(nextTool)) clearPlots();"),
 ("  function open(t) {\n", "  let nextTool = null;\n  function open(t) {\n    nextTool = t;\n"),
 ("  return { open, close, onClick, push, afterCreate, show, clearSel, get tool() { return tool; } };", r"""  // ------------------------------------------------------------------ measure
  const mg = L.layerGroup().addTo(map); let mPts = [], mDone = false;
  const fmtL = m => `${m >= 1000 ? (m / 1000).toFixed(3) + ' km' : m.toFixed(1) + ' m'} (${(m / FT).toFixed(0)} ft)`;
  function measureClick(ll) { if (mDone) { mPts = []; mDone = false; } mPts.push(ll); drawMeasure(); }
  function drawMeasure(hover) {
    mg.clearLayers(); const area = wid.querySelector('input[name=mm]:checked')?.value === 'area'; const pts = hover ? [...mPts, hover] : mPts; const out = q('#mres');
    if (!pts.length) { if (out) out.innerHTML = '<span class="mini">Click on the map to start.</span>'; return; }
    pts.forEach(p => L.circleMarker(p, { radius: 3, color: '#fff', weight: 1, fillColor: '#ff1744', fillOpacity: 1, interactive: false }).addTo(mg));
    const c = pts.map(p => [p.lng, p.lat]);
    if (area && pts.length >= 3) {
      L.polygon(pts, { color: '#ff1744', weight: 2, dashArray: mDone ? null : '5 4', fillOpacity: .12, interactive: false }).addTo(mg);
      const poly = turf.polygon([[...c, c[0]]]), a = turf.area(poly), per = turf.length(turf.lineString([...c, c[0]]), mm);
      if (out) out.innerHTML = `<b>Area</b> ${a.toFixed(0)} m&sup2; = ${(a / 1e4).toFixed(3)} ha = ${(a / 4046.856).toFixed(3)} ac (${(a / 0.092903).toFixed(0)} sq ft)<br><b>Perimeter</b> ${fmtL(per)}`;
    } else if (pts.length >= 2) {
      L.polyline(pts, { color: '#ff1744', weight: 2.5, dashArray: mDone ? null : '5 4', interactive: false }).addTo(mg);
      const tot = turf.length(turf.lineString(c), mm), seg = turf.distance(c[c.length - 2], c[c.length - 1], mm);
      const br = (turf.bearing(c[c.length - 2], c[c.length - 1]) + 360) % 360;
      if (out) out.innerHTML = `<b>Total</b> ${fmtL(tot)}<br><span class="mini">Last segment ${fmtL(seg)}, bearing ${br.toFixed(1)}&deg;</span>` + (area ? '<br><span class="mini">Add a third point for the area.</span>' : '');
    } else if (out) out.innerHTML = '<span class="mini">Click the next point.</span>';
  }
  // ------------------------------------------------------------------ plots (existing situation): select plots / blocks
  const pSel = new Map(), pBlocks = new Set();
  const PHI = { color: '#00e5ff', weight: 3 };
  function plotLayers() { const g = Object.values(results).find(x => x._kind === 'plots'); return g ? g.getLayers() : []; }
  function paintPlots() { const g = Object.values(results).find(x => x._kind === 'plots'); if (!g) return; g.eachLayer(l => { const p = l.feature.properties; if (pSel.has(p.plot_id) || pBlocks.has(p.block_id)) l.setStyle(PHI); else g.resetStyle(l); }); }
  function clearPlots() { pSel.clear(); pBlocks.clear(); paintPlots(); refresh(); }
  function captureResultClick(kind, f, l, e) {
    if (tool === 'measure') { measureClick(e.latlng); return true; }
    if (kind !== 'plots' || !['pselect', 'redemarcate', 'psplit', 'pmerge'].includes(tool)) return false;
    const p = f.properties, add = e.originalEvent.shiftKey;
    if (tool === 'redemarcate') { if (!add) pBlocks.clear(); pBlocks.has(p.block_id) ? pBlocks.delete(p.block_id) : pBlocks.add(p.block_id); }
    else { if (!add) pSel.clear(); pSel.has(p.plot_id) ? pSel.delete(p.plot_id) : pSel.set(p.plot_id, l); }
    paintPlots(); refresh(); return true;
  }
  const _refresh = refresh;
  refresh = function () { _refresh();
    wid.querySelectorAll('.psel').forEach(e => e.innerHTML = pSel.size ? `<b>${pSel.size}</b> plot(s) selected: ${[...pSel.keys()].slice(0, 6).join(', ')}${pSel.size > 6 ? '...' : ''}` : '<span class="mini">No plots selected</span>');
    wid.querySelectorAll('.bsel').forEach(e => e.innerHTML = pBlocks.size ? `Blocks selected: <b>${[...pBlocks].join(', ')}</b>` : '<span class="mini">No blocks selected: click a plot in each block</span>'); };
  rib.querySelector('[data-a=pundo]').onclick = async () => { try { await post(`/api/projects/${P.id}/plots/undo`); clearPlots(); await reloadPlots(); } catch (e) { alert(e.message); } };
  rib.querySelector('[data-a=pmap]').onclick = async () => { try { await post(`/api/projects/${P.id}/run`, { workflow: 'existing', only: 'map', buildings: P.buildings || 'fast' }); alert('Updating the land use map and tables (about a minute).'); refreshStatus(); } catch (e) { alert(e.message); } };
  return { open, close, onClick, push, afterCreate, show, mode, clearSel, captureResultClick, get tool() { return tool; } };"""),
])
s = open('webapp/static/editor.js', encoding='utf-8').read()
s = s.replace("  function refresh() {", "  let refresh = function () {", 1)
# close the function expression: the original refresh body ends before '  // ------------------------------------------------------------------ wiring of each widget'
i = s.index("  let refresh = function () {"); j = s.index("  // ------------------------------------------------------------------ wiring of each widget", i)
body = s[i:j].rstrip()
assert body.endswith('}'), body[-40:]
s = s[:i] + body + ';\n' + s[j:]
open('webapp/static/editor.js', 'w', encoding='utf-8').write(s)
print('ok')
