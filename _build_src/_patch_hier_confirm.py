def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
patch('webapp/static/app.js', [
 # LUSPA: unconfirmed class
 ("'VAC': ['Open / yard, no building', '#FFFFFF', null, '#9E9E9E'] };", "'VAC': ['Open / yard, no building', '#FFFFFF', null, '#9E9E9E'], 'UNC': ['Use NOT confirmed: please verify', '#FFFFFF', '#FF6D00', '#FF6D00'] };"),
 ("'Agricultural': 'Ag', 'Open / yard (no building)': 'VAC' };", "'Agricultural': 'Ag', 'Open / yard (no building)': 'VAC', 'Unconfirmed (verify)': 'UNC', 'Utility': 'SU' };"),
 ("const luspaStyle = (code, base = {}) => { const c = LUSPA[code] || LUSPA.VAC; return { color: c[3] || c[2] || '#222', weight: c[3] ? 2 : c[2] ? 1.6 : .8, dashArray: c[2] && !c[3] ? '4 3' : null, fillColor: c[1], fillOpacity: .85, ...base }; };",
  "const luspaStyle = (code, base = {}) => { const c = LUSPA[code] || LUSPA.VAC; return { color: c[3] || c[2] || '#222', weight: code === 'UNC' ? 2.5 : c[3] ? 2 : c[2] ? 1.6 : .8, dashArray: code === 'UNC' ? '6 4' : c[2] && !c[3] ? '4 3' : null, fillColor: c[1], fillOpacity: .85, ...base }; };"),
 # road hierarchy on click + reserve bands
 ("function onFeatureClick(kind, l, e) { if (typeof Editor !== 'undefined') Editor.onClick(kind, l, e); }",
  r"""function onFeatureClick(kind, l, e) {
  if (typeof Editor !== 'undefined') Editor.onClick(kind, l, e);
  const busy = (typeof Editor !== 'undefined' && Editor.tool) || (typeof FE !== 'undefined' && FE.active);
  if (!busy && (kind === 'roads' || kind === 'existing')) roadHierarchy(kind, l, e.latlng);
}
// ---- click a road: change its hierarchy (reserve width); the reserve band and everything drawn from it update straight away ----
const HIER = [['Local road', 24], ['Local road', 30], ['Collector', 40], ['Main road', 60], ['Arterial', 80], ['Arterial', 100], ['Arterial', 120]];
function roadHierarchy(kind, l, ll) {
  const w = +(l.feature.properties.width_ft || 30);
  const html = `<div class="hier"><b>Road hierarchy</b><div class="mini">now ${w} ft (${(w * FT).toFixed(1)} m reserve)</div>` +
    HIER.map(([n, v]) => `<button data-w="${v}" class="${v === w ? 'on' : ''}">${n} <b>${v} ft</b></button>`).join('') +
    `<div class="row"><input id="hw" type="number" min="6" placeholder="custom ft" style="width:90px"><button data-w="c">Set</button></div></div>`;
  const pop = L.popup({ maxWidth: 240 }).setLatLng(ll).setContent(html).openOn(map);
  setTimeout(() => document.querySelectorAll('.hier button[data-w]').forEach(b => b.onclick = () => {
    const nw = b.dataset.w === 'c' ? +document.getElementById('hw').value : +b.dataset.w; if (!(nw > 0)) return;
    if (typeof Editor !== 'undefined') Editor.push();
    l.feature.properties.width_ft = nw; l.feature.properties.class = (HIER.find(h => h[1] === nw) || ['Road'])[0] + ` ${nw} ft`; markMine(l); styleInput(kind, l); saveInput(kind); map.closePopup(pop);
  }), 30);
}
const reserveLayer = L.layerGroup().addTo(map);
let resT = null;
function drawReserves() { clearTimeout(resT); resT = setTimeout(() => { reserveLayer.clearLayers();
  for (const k of ['roads', 'existing']) inputs[k].eachLayer(l => { try { const w = +(l.feature?.properties?.width_ft || (k === 'existing' ? 40 : 30));
    const poly = turf.buffer(lineOf(l), w * FT / 2, { units: 'meters', steps: 4 });
    L.geoJSON(poly, { interactive: false, style: { color: '#555', weight: .6, fillColor: k === 'existing' ? '#9e9e9e' : '#bdbdbd', fillOpacity: .45 } }).addTo(reserveLayer); } catch (er) {} });
  reserveLayer.eachLayer(x => x.bringToBack?.()); }, 150); }"""),
])
s = open('webapp/static/app.js', encoding='utf-8').read()
# saveInput: redraw the reserve bands after every road change
a = "  if (kind === 'roads' || kind === 'existing') updateAngles();\n}"
if a in s: s = s.replace(a, "  if (kind === 'roads' || kind === 'existing') { updateAngles(); drawReserves(); }\n}")
# ---- Confirm uses: step through plots whose use is a guess ----
s = s.replace("$('#mClose').onclick = () => $('#modal').hidden = true;", r"""$('#mClose').onclick = () => $('#modal').hidden = true;
// ---- uses that are guesses: alert + step-by-step confirmation ----
const confirmBox = L.DomUtil.create('div', 'confirmbox', map.getContainer()); confirmBox.hidden = true; L.DomEvent.disableClickPropagation(confirmBox);
let CQ = [], CI = 0, CL = null;
function unconfirmedPlots() { const L_ = LAYER_INDEX.find(l => l.kind === 'plots'); const g = L_ && results[L_.path]; return g ? g.getLayers().filter(l => (l.feature.properties.ex_use || '').startsWith('Unconfirmed')) : []; }
function checkUnconfirmed() {
  const n = unconfirmedPlots().length, el = $('#confirmAlert');
  if (!el) return; el.hidden = !n; el.innerHTML = `<b>${n} plot(s)</b> have a use that could not be confirmed from OSM or the building database. They are shown white with an orange dashed outline. <button id="cuBtn">Confirm uses</button>`;
  if (n) $('#cuBtn').onclick = startConfirm;
}
function startConfirm() { CQ = unconfirmedPlots(); CI = 0; if (!CQ.length) return alert('All uses are confirmed.'); confirmBox.hidden = false; showConfirm(); }
function showConfirm() {
  if (CI >= CQ.length) { confirmBox.hidden = true; checkUnconfirmed(); return alert('Done. Run "Update map" (Plots group) to refresh the map and tables.'); }
  CL = CQ[CI]; const p = CL.feature.properties; map.fitBounds(CL.getBounds(), { maxZoom: 19, padding: [80, 80] }); CL.setStyle({ color: '#00e5ff', weight: 4 });
  const opts = Object.keys(EXIST_LUSPA).filter(u => !u.startsWith('Unconfirmed')).map(u => `<option ${u === p.use_guess ? 'selected' : ''}>${u}</option>`).join('');
  confirmBox.innerHTML = `<div class="wh"><b>Confirm use</b> <span class="mini">${CI + 1} of ${CQ.length} &middot; plot ${p.plot_id}</span><button class="x" id="cuX">&times;</button></div>
    <div class="wb"><div class="mini">Guess from the rules: <b>${p.use_guess || 'none'}</b></div>
    <div class="row"><button id="cuOk">Accept guess</button><button class="ghost" id="cuSkip">Skip</button></div>
    <div class="row"><select id="cuSel">${opts}</select><button id="cuSet">Set this use</button></div>
    <div class="row"><button class="ghost small" id="cuAll">Accept all remaining guesses</button></div></div>`;
  const L_ = LAYER_INDEX.find(l => l.kind === 'plots');
  const setUse = async (fids, use) => post(`/api/projects/${P.id}/edit/op`, { path: L_.path, op: 'update_attrs', fids, properties: { ex_use: use, use_conf: 'confirmed (planner)' } });
  $('#cuX').onclick = () => { confirmBox.hidden = true; results[L_.path]?.resetStyle?.(CL); };
  $('#cuSkip').onclick = () => { results[L_.path]?.resetStyle?.(CL); CI++; showConfirm(); };
  const apply = async use => { await setUse([p._fid], use); p.ex_use = use; p.use_conf = 'confirmed (planner)'; CL.setStyle(styleFor('plots')(CL.feature)); CI++; showConfirm(); };
  $('#cuOk').onclick = () => apply(p.use_guess || 'Residential'); $('#cuSet').onclick = () => apply($('#cuSel').value);
  $('#cuAll').onclick = async () => { const rest = CQ.slice(CI); if (!confirm(`Accept the guessed use for ${rest.length} plot(s)?`)) return;
    for (const l of rest) { const q = l.feature.properties; await setUse([q._fid], q.use_guess || 'Residential'); q.ex_use = q.use_guess || 'Residential'; l.setStyle(styleFor('plots')(l.feature)); } CI = CQ.length; showConfirm(); };
}""", 1)
s = s.replace("  renderDownloads(r);\n", "  renderDownloads(r);\n  setTimeout(checkUnconfirmed, 1500);\n", 1)
open('webapp/static/app.js', 'w', encoding='utf-8').write(s)
patch('webapp/static/index.html', [('        <div class="card"><div class="cardh">Map layers</div>', '        <div id="confirmAlert" class="alertbox" hidden></div>\n        <div class="card"><div class="cardh">Map layers</div>')])
c = 'webapp/static/app.css'; t = open(c, encoding='utf-8').read()
t += """
.hier button { display: block; width: 100%; text-align: left; margin: 2px 0; padding: 3px 8px; background: #fff; color: #1f2328; border-color: #ddd; font-size: 12px; }
.hier button.on { background: #d6e8f7; border-color: #1f5f8b; }
.alertbox { background: #fff3e0; border: 1px solid #ffb74d; border-left: 4px solid #ff6d00; border-radius: 6px; padding: 8px 10px; margin: 10px 0; font-size: 13px; }
.alertbox button { margin-top: 6px; display: block; }
.confirmbox { position: absolute; right: 12px; top: 120px; z-index: 1002; width: 300px; background: #fff; border: 1px solid #b9c1cb; border-radius: 6px; box-shadow: 0 6px 18px rgba(0,0,0,.25); font-size: 13px; }
.confirmbox .wh { display: flex; justify-content: space-between; align-items: center; gap: 6px; padding: 7px 10px; background: #fff3e0; border-bottom: 1px solid #ffe0b2; }
.confirmbox .wh .x { background: none; border: none; color: #444; font-size: 18px; padding: 0 4px; }
.confirmbox .wb { padding: 8px 10px; } .confirmbox select { flex: 1; min-width: 0; }
"""
open(c, 'w', encoding='utf-8').write(t)
print('ok')
