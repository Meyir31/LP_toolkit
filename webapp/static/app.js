// LP Toolkit web app front end
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const api = (u, o = {}) => fetch(u, o).then(async r => { const j = r.headers.get('content-type')?.includes('json') ? await r.json() : await r.text(); if (!r.ok) throw new Error(j.error || j); return j; });
// messages appear as notices on the page (no blocking pop-ups); click one to close it
const toastBox = document.createElement('div'); toastBox.id = 'toasts'; document.body.appendChild(toastBox);
window.alert = msg => { const t = document.createElement('div'); t.className = 'toast'; t.textContent = String(msg); t.onclick = () => t.remove(); toastBox.appendChild(t); setTimeout(() => t.remove(), 6000); };
const post = (u, body) => api(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
const STAGES = { existing: ['fetch', 'footprints', 'roads', 'landuse', 'reserves', 'trees', 'blocks', 'plots', 'map'], existing_full: ['fetch', 'sam', 'digitize', 'compare', 'clean', 'database', 'roads', 'landuse', 'reserves', 'trees', 'blocks', 'plots', 'map'], design: ['site', 'roads', 'subdivide', 'landuse', 'audit'] };
const stagesOf = wf => wf === 'existing' && (P?.buildings === 'full') ? STAGES.existing_full : STAGES[wf];
const STAGE_HELP = { fetch: 'imagery, OSM, Microsoft, database', sam: 'building detection (slow)', digitize: 'footprints and walls', compare: 'check vs OSM / Microsoft', clean: 'remove false detections',
  database: 'check vs building database', footprints: 'OSM + building database, walls', roads: 'road widths / road reserves and blocks', landuse: 'use per building / facilities', reserves: 'reserves, pinch points', trees: 'tree belt', blocks: 'blocks', plots: 'existing plots',
  map: 'land use map', site: 'imagery, DEM, slope, contours, OSM', subdivide: 'plots (Phase One rule)', audit: 'design audit' };
const FT = 0.3048; let SNAP_M = 12, snapOn = true;
let P = null, poll = null, activeDraw = null, drawer = null, width = 30;

// ------------------------------------------------------------------ map
const map = L.map('map', { renderer: L.canvas({ tolerance: 7 }) }).setView([5.6, -0.19], 13);
const esri = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 21, maxNativeZoom: 19, attribution: 'Esri World Imagery' }).addTo(map);
const gsat = L.tileLayer('https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', { subdomains: '0123', maxZoom: 21, maxNativeZoom: 20, attribution: 'Imagery &copy; Google' });
const ghyb = L.tileLayer('https://mt{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', { subdomains: '0123', maxZoom: 21, maxNativeZoom: 20, attribution: 'Imagery &copy; Google' });
const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 21, maxNativeZoom: 19, attribution: '&copy; OpenStreetMap' });
L.control.layers({ 'Esri satellite': esri, 'Google satellite': gsat, 'Google hybrid': ghyb, 'OpenStreetMap': osm }, {}, { position: 'topright' }).addTo(map);
L.control.scale({ imperial: true }).addTo(map);
const INPUT_STYLE = { site: { color: '#ff3b30', weight: 3, fill: false }, stream: { color: '#2e8b57', weight: 4, fillOpacity: .3 }, existing: { color: '#111', weight: 6 },
  zones: { color: '#8e24aa', weight: 2, dashArray: '8 5', fillColor: '#ce93d8', fillOpacity: .15 } };
const roadStyle = (w, locked) => ({ color: w >= 80 ? '#424242' : w >= 60 ? '#757575' : w >= 40 ? '#f5a142' : '#ffffff', weight: Math.max(2.5, w / 9), opacity: .95, dashArray: locked ? null : null });
const inputs = { site: new L.FeatureGroup(), roads: new L.FeatureGroup(), stream: new L.FeatureGroup(), existing: new L.FeatureGroup(), zones: new L.FeatureGroup() };
Object.values(inputs).forEach(g => g.addTo(map));
const angleLayer = L.layerGroup().addTo(map), liveAngle = L.layerGroup().addTo(map);
let editCtl = new L.Control.Draw({ draw: false, edit: { featureGroup: inputs.roads, remove: true } }); map.addControl(editCtl);
function setEditGroup(kind) { map.removeControl(editCtl); editCtl = new L.Control.Draw({ draw: false, edit: { featureGroup: inputs[kind], remove: true } }); map.addControl(editCtl); }
// ------------------------------------------------------------------ layer transparency (per layer, remembered per project in this browser)
let OPALL = {}; try { OPALL = JSON.parse(localStorage.getItem('lp_opacity') || '{}'); } catch (e) {}
const opKey = path => `${P?.id || ''}|${path}`;
const opOf = path => { const v = OPALL[opKey(path)]; return v == null ? 1 : v; };
function setOp(path, v) { if (v >= 0.999) delete OPALL[opKey(path)]; else OPALL[opKey(path)] = v; try { localStorage.setItem('lp_opacity', JSON.stringify(OPALL)); } catch (e) {} }
const withOp = (s, v) => v >= 0.999 ? s : { ...s, opacity: (s.opacity ?? 1) * v, fillOpacity: (s.fillOpacity ?? .2) * v };
function applyOp(path) {                                                 // result layer: its style scaled by the layer's opacity
  const v = opOf(path), lyr = results[path]; if (!lyr) return;
  if (lyr.setOpacity && !lyr.eachLayer) { lyr.setOpacity(.75 * v); return; }
  if (!lyr._baseStyle) lyr._baseStyle = lyr.options.style || (() => ({}));
  const b = lyr._baseStyle; lyr.options.style = f => withOp(typeof b === 'function' ? b(f) : b, v);
  lyr.eachLayer(l => { if (l instanceof L.CircleMarker) l.setStyle({ opacity: v, fillOpacity: .95 * v }); else if (l.setStyle) l.setStyle(lyr.options.style(l.feature)); });
}
function applyInputOp(kind) { if (kind === 'reserves') { map.getPane('reservePane') && (map.getPane('reservePane').style.opacity = opOf('in:reserves')); return; } inputs[kind]?.eachLayer(l => styleInput(kind, l)); }
function opSlider(path, onChange) {                                      // 'Transparency' slider: 0 % = solid, 100 % = invisible
  const w = document.createElement('span'); w.className = 'opw'; const t0 = Math.round((1 - opOf(path)) * 100);
  w.innerHTML = `<input type="range" min="0" max="100" step="5" value="${t0}" title="Transparency"><span class="opv">${t0}%</span>`;
  const r = w.querySelector('input'); r.oninput = () => { w.querySelector('.opv').textContent = r.value + '%'; setOp(path, 1 - r.value / 100); onChange(); };
  return w;
}
function zoomBtn(ref) { const z = document.createElement('button'); z.className = 'ghost lzoom'; z.title = 'Zoom to layer (or right-click the row)'; z.innerHTML = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><circle cx="10.5" cy="10.5" r="6"/><path d="M15 15l5.5 5.5M8 10.5h5M10.5 8v5"/></svg>'; z.onclick = e => { e.preventDefault(); e.stopPropagation(); window.zoomToLayer && zoomToLayer(ref); }; return z; }
function layerRow(L_, lab, cb) { const row = document.createElement('div'); row.className = 'lrow'; row.dataset.path = L_.path; lab.append(cb, ' ' + L_.label); row.append(lab, zoomBtn({ path: L_.path }), opSlider(L_.path, () => applyOp(L_.path))); return row; }
function styleInput(kind, layer) {
  const p = layer.feature?.properties || {}, v = opOf('in:' + kind);
  if (kind === 'roads') layer.setStyle?.(withOp(roadStyle(+(p.width_ft || 30), p.locked), v));
  else if (kind === 'existing') layer.setStyle?.(withOp({ ...INPUT_STYLE.existing, weight: Math.max(3, (+(p.width_ft || 40)) / 9) }, v));
  else layer.setStyle?.(withOp(INPUT_STYLE[kind] || {}, v));
}
function addInputLayer(kind, l) {
  l.feature = l.feature || { type: 'Feature', properties: {}, geometry: null }; l.feature.properties = l.feature.properties || {};
  styleInput(kind, l); l.on('click', e => onFeatureClick(kind, l, e)); inputs[kind].addLayer(l);
  if (kind === 'roads') l.bindTooltip(() => `${l.feature.properties.width_ft || 30} ft${l.feature.properties.locked ? ' (yours, kept on redesign)' : ''}`, { sticky: true });
}
function loadInput(kind, fc) {
  inputs[kind].clearLayers();
  L.geoJSON(fc, { onEachFeature: (f, l) => { l.feature = f; f.properties = f.properties || {}; addInputLayer(kind, l); } });
  if (kind === 'roads' || kind === 'existing') { updateAngles(); drawReserves(); }
}
function fcOf(kind) { const feats = []; inputs[kind].eachLayer(l => { const f = l.toGeoJSON(); f.properties = { ...(l.feature?.properties || {}) }; feats.push(f); }); return { type: 'FeatureCollection', features: feats }; }
let saveT = {};
function saveInput(kind) {
  if (!P) return; clearTimeout(saveT[kind]);
  saveT[kind] = setTimeout(async () => { await post(`/api/projects/${P.id}/layer/${kind}`, fcOf(kind)); refreshInputState(); }, 300);
  if (kind === 'roads' || kind === 'existing') { updateAngles(); drawReserves(); rcLater = null; queueLocalUpdate(); }
}

// ------------------------------------------------------------------ geometry helpers (turf, metres)
const M = { units: 'meters' };
const lineOf = l => { let ll = l.getLatLngs(); if (Array.isArray(ll[0])) ll = ll[0]; return turf.lineString(ll.map(p => [p.lng, p.lat])); };
function setLine(l, coords) { l.setLatLngs(coords.map(c => [c[1], c[0]])); l.feature.geometry = { type: 'LineString', coordinates: coords }; }
function roadLayers(includeExisting = true) { const a = []; inputs.roads.eachLayer(l => a.push(l)); if (includeExisting) inputs.existing.eachLayer(l => a.push(l)); return a.filter(l => l.getLatLngs); }
function siteLine() { const s = inputs.site.getLayers()[0]; if (!s) return null; let ll = s.getLatLngs(); while (Array.isArray(ll[0])) ll = ll[0]; const c = ll.map(p => [p.lng, p.lat]); c.push(c[0]); return turf.lineString(c); }
function targets(except) { const t = roadLayers().filter(l => l !== except).map(lineOf); const s = siteLine(); if (s) t.push(s); return t; }
function bearingAt(line, pt) {
  const L_ = turf.length(line, M), loc = turf.nearestPointOnLine(line, pt, M).properties.location;
  return turf.bearing(turf.along(line, Math.max(0, loc - 6), M), turf.along(line, Math.min(L_, loc + 6), M));
}
const acute = (b1, b2) => { let d = Math.abs(b1 - b2) % 180; return Math.min(d, 180 - d); };
function snapEnds(l) {
  if (!snapOn) return false;
  const ln = lineOf(l), c = ln.geometry.coordinates, others = roadLayers().filter(x => x !== l).map(lineOf); let moved = false;
  for (const idx of [0, c.length - 1]) {
    let best = null;
    for (const o of others) { const np = turf.nearestPointOnLine(o, c[idx], M); if (np.properties.dist < SNAP_M && (!best || np.properties.dist < best.properties.dist)) best = np; }
    if (best && best.properties.dist > 0.05) { c[idx] = best.geometry.coordinates; moved = true; }
  }
  if (moved) setLine(l, c); return moved;
}

// ------------------------------------------------------------------ road tools: see editor.js (ArcGIS Pro style ribbon and widgets)
function markMine(l) { l.feature.properties.locked = true; l.feature.properties.kind = l.feature.properties.kind === 'existing' ? 'existing' : 'planner'; }
function onFeatureClick(kind, l, e) {
  if (typeof Editor !== 'undefined') Editor.onClick(kind, l, e);
  const busy = (typeof Editor !== 'undefined' && Editor.tool) || (typeof FE !== 'undefined' && FE.active);
  if (!busy && (kind === 'roads' || kind === 'existing')) roadHierarchy(kind, l, e.latlng);
}
// ---- click a road: change its hierarchy (reserve width); the reserve band and everything drawn from it update straight away ----
const HIER = [['Local road', 24], ['Local road', 30], ['Collector', 40], ['Main road', 60], ['Arterial', 80], ['Arterial', 100], ['Arterial', 120], ['Arterial', 150], ['Regional road (60 m)', 200], ['National road / major arterial (90 m)', 300]];
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
map.createPane('reservePane'); map.getPane('reservePane').style.zIndex = 420; map.getPane('reservePane').style.pointerEvents = 'none';
const RES_R = L.svg({ pane: 'reservePane' });
const reserveLayer = L.layerGroup().addTo(map);
let resT = null;
function drawReserves() { clearTimeout(resT); resT = setTimeout(() => { reserveLayer.clearLayers();
  for (const k of ['roads', 'existing']) inputs[k].eachLayer(l => { try { const w = +(l.feature?.properties?.width_ft || (k === 'existing' ? 40 : 30));
    const poly = turf.buffer(lineOf(l), w * FT / 2, { units: 'meters', steps: 4 });
    L.geoJSON(poly, { interactive: false, pane: 'reservePane', renderer: RES_R, style: { color: '#555', weight: .6, fillColor: k === 'existing' ? '#9e9e9e' : '#bdbdbd', fillOpacity: .75 } }).addTo(reserveLayer); } catch (er) {} });
  }, 150); }
function stopTool() { if (typeof Editor !== 'undefined') Editor.close(); }
// ------------------------------------------------------------------ drawing
map.on(L.Draw.Event.CREATED, e => { if (activeDraw) onDrawn(activeDraw, e.layer); });
function onDrawn(kind, l) {
  if (kind === 'roads' && typeof Editor !== 'undefined') Editor.push();
  l.feature = { type: 'Feature', properties: {}, geometry: null };
  if (kind === 'roads') { l.feature.properties = { width_ft: width, locked: true, kind: 'planner' }; }
  if (kind === 'existing') l.feature.properties.width_ft = +$('#exW').value;
  if (kind === 'zones') l.feature.properties.pattern = $('#dPattern').value;
  if (kind === 'site') inputs.site.clearLayers();
  addInputLayer(kind, l); if (kind === 'roads') { snapEnds(l); if (typeof Editor !== 'undefined') Editor.afterCreate(l); } saveInput(kind); liveAngle.clearLayers();
  if (kind === 'site') map.fitBounds(l.getBounds());
  if (kind === 'roads' || kind === 'existing') startDraw(kind, 'polyline'); else stopDraw();
}
map.on(L.Draw.Event.EDITED, () => { ['roads', 'existing', 'site', 'stream', 'zones'].forEach(k => { if (k === 'roads') inputs.roads.eachLayer(markMine); saveInput(k); }); });
map.on(L.Draw.Event.DELETED, () => ['roads', 'existing', 'site', 'stream', 'zones'].forEach(saveInput));
map.on('draw:drawvertex', () => {                                   // live junction angles while drawing a road
  liveAngle.clearLayers(); if (activeDraw !== 'roads' || !drawer?._poly) return;
  const ll = drawer._poly.getLatLngs(); if (ll.length < 2) return;
  const cur = turf.lineString(ll.map(p => [p.lng, p.lat])), last = turf.lineString(ll.slice(-2).map(p => [p.lng, p.lat]));
  const bl = turf.bearing(...last.geometry.coordinates);
  for (const t of roadLayers().map(lineOf)) {
    for (const h of turf.lineIntersect(last, t).features) addAngle(liveAngle, h.geometry.coordinates, acute(bl, bearingAt(t, h)));
    const endp = turf.point(ll[ll.length - 1] ? [ll[ll.length - 1].lng, ll[ll.length - 1].lat] : cur.geometry.coordinates.at(-1));
    const np = turf.nearestPointOnLine(t, endp, M); if (np.properties.dist < SNAP_M) addAngle(liveAngle, np.geometry.coordinates, acute(bl, bearingAt(t, np)));
  }
});
function startDraw(kind, shape) {
  stopDraw(); activeDraw = kind; setEditGroup(kind);
  const st = kind === 'roads' ? roadStyle(width) : (INPUT_STYLE[kind] || {});
  $$('button.draw').forEach(b => b.classList.toggle('on', b.dataset.kind === kind && b.dataset.shape === shape));
  const NAMES = { roads: `Road ${width} ft`, existing: 'Existing road', stream: 'Stream / water', site: 'Site boundary', zones: 'Redesign area' };
  Sketch.start({ shape: shape === 'polygon' ? 'polygon' : 'line', title: NAMES[kind] || kind, roads: kind === 'roads' || kind === 'existing', onCancel: () => stopDraw(),
    onDone: geom => {
      let c = geom.type === 'Polygon' ? geom.coordinates[0].slice(0, -1) : geom.coordinates;
      if ((kind === 'roads' || kind === 'existing') && geom.type === 'LineString') c = trimRoadOvershoot(c, roadLayers().map(lineOf));   // not a cross road: trimmed at the crossing
      const ll = c.map(p => [p[1], p[0]]); onDrawn(kind, shape === 'polygon' ? L.polygon(ll, st) : L.polyline(ll, st));
    } });
}
function stopDraw() { drawer?.disable(); drawer = null; if (typeof Sketch !== 'undefined' && Sketch.active) Sketch.cancel(true); activeDraw = null; liveAngle.clearLayers(); $$('button.draw').forEach(b => b.classList.remove('on')); }
$$('button.draw').forEach(b => b.onclick = () => { if (!P) return alert('Create or choose a project first'); if (b.classList.contains('on')) return stopDraw(); stopTool(); startDraw(b.dataset.kind, b.dataset.shape); });
$$('input[type=file][data-kind]').forEach(inp => inp.onchange = async () => {
  if (!P || !inp.files[0]) return; const kind = inp.dataset.kind, fd = new FormData(); fd.append('file', inp.files[0]);
  try { await api(`/api/projects/${P.id}/upload/${kind}`, { method: 'POST', body: fd }); loadInput(kind, await api(`/api/projects/${P.id}/input/${kind}`));
    if (kind === 'site' && inputs.site.getLayers().length) map.fitBounds(inputs.site.getBounds()); refreshInputState(); } catch (e) { alert(e.message); }
  inp.value = '';
});
$('#clearZones').onclick = () => { inputs.zones.clearLayers(); saveInput('zones'); };

// ------------------------------------------------------------------ junction angles
function addAngle(group, c, a) {
  const cls = a >= 80 ? 'g' : a >= 70 ? 'o' : 'r';
  group.addLayer(L.marker([c[1], c[0]], { interactive: false, icon: L.divIcon({ className: '', html: `<span class="ang ${cls}">${Math.round(a)}&deg;</span>`, iconSize: null, iconAnchor: [14, 8] }) }));
}
let angT = null;
function updateAngles() { clearTimeout(angT); angT = setTimeout(computeAngles, 250); }
function computeAngles() {
  angleLayer.clearLayers(); if (!$('#showAngles').checked) { $('#angleSum').textContent = ''; return; }
  const ls = roadLayers().map(l => ({ l, ln: lineOf(l) })); ls.forEach(o => o.bb = turf.bbox(o.ln));
  const pts = [], near = c => pts.some(p => turf.distance(p, c, M) < 3);
  const hit = (a, b) => !(a[2] < b[0] || b[2] < a[0] || a[3] < b[1] || b[3] < a[1]);
  let bad = 0, warn = 0, n = 0;
  const show = map.getZoom() >= 16;
  for (let i = 0; i < ls.length; i++) for (let j = i + 1; j < ls.length; j++) {
    const A = ls[i], B = ls[j]; if (!hit(A.bb, B.bb)) continue;
    const cand = turf.lineIntersect(A.ln, B.ln).features.map(f => f.geometry.coordinates);
    for (const [X, Y] of [[A, B], [B, A]]) { const c = X.ln.geometry.coordinates; for (const e of [c[0], c[c.length - 1]]) { const np = turf.nearestPointOnLine(Y.ln, e, M); if (np.properties.dist < 2) cand.push(np.geometry.coordinates); } }
    for (const c of cand) {
      if (near(c)) continue;
      const a = acute(bearingAt(A.ln, turf.point(c)), bearingAt(B.ln, turf.point(c)));
      const endA = turf.distance(A.ln.geometry.coordinates[0], c, M) < 2 || turf.distance(A.ln.geometry.coordinates.at(-1), c, M) < 2;
      const endB = turf.distance(B.ln.geometry.coordinates[0], c, M) < 2 || turf.distance(B.ln.geometry.coordinates.at(-1), c, M) < 2;
      if (a < 15) continue;                                          // the same road twice (two pieces, or the existing road and its copy in the design): not a junction
      pts.push(c); n++; if (a < 70) bad++; else if (a < 80) warn++;
      if (show || a < 80) addAngle(angleLayer, c, a);
    }
  }
  $('#angleSum').textContent = n ? `${n} junctions: ${bad} below 70°, ${warn} at 70-80°${show ? '' : ' (zoom in to see all)'}` : '';
}
$('#showAngles').onchange = computeAngles; map.on('zoomend', updateAngles);

// ------------------------------------------------------------------ projects
async function loadProjects(sel) {
  const ps = await api('/api/projects'); $('#projSel').innerHTML = '<option value="">Choose a project</option>' + ps.map(p => `<option value="${p.id}">${p.name} (${p.workflow === 'existing' ? 'existing' : 'new layout'})</option>`).join('');
  if (sel) { $('#projSel').value = sel; await openProject(sel); }
}
$('#projSel').onchange = e => e.target.value && openProject(e.target.value);
async function openProject(id) {
  stopTool(); if (typeof Editor !== 'undefined') Editor.close();
  $('#confirmAlert') && ($('#confirmAlert').hidden = true); document.querySelector('.confirmbox') && (document.querySelector('.confirmbox').hidden = true); map.closePopup();
  $$('.tabs button')[0]?.click(); P = await api(`/api/projects/${id}`); P.buildings = P.buildings || 'fast'; $$('input[name=bmode]').forEach(r => r.checked = r.value === P.buildings); $('#imagery').value = P.imagery || 'google'; if ($('#profile')) $('#profile').value = P.profile || 'auto'; $('#noProj').hidden = true; $('#proj').hidden = false; $('#pName').textContent = P.name; $('#pTitle').value = P.title || '';
  if ($('#pCrs')) $('#pCrs').value = String(P.crs || 2136);
  setWorkflow(P.workflow, false); if ($('#dPW')) { $('#dPW').value = P.plot_w || ''; $('#dPL').value = P.plot_l || ''; plotSizeChanged(false); }
  for (const k of Object.keys(inputs)) loadInput(k, await api(`/api/projects/${id}/input/${k}`));
  if (inputs.site.getLayers().length) map.fitBounds(inputs.site.getBounds());
  clearResults(); refreshInputState(); refreshStatus(); await loadResults(); loadTerrain(); if (typeof FE !== 'undefined') { FE.close(); FE.refreshLayers(); }
  clearInterval(poll); poll = setInterval(refreshStatus, 2500);
}
function setWorkflow(wf, save = true) {
  P.workflow = wf; $$('#wfSeg button').forEach(b => b.classList.toggle('on', b.dataset.wf === wf));
  $('#designInputs').hidden = wf !== 'design'; if ($('#chamferRow')) $('#chamferRow').hidden = wf !== 'design'; $('#existingInputs').hidden = wf !== 'existing'; $('#extras').hidden = wf !== 'existing';
  if (typeof Editor !== 'undefined') Editor.mode(wf);
  $('#stageList').innerHTML = stagesOf(wf).map((s, i) => `<label title="${STAGE_HELP[s] || ''}" data-s="${s}"><input type="radio" name="stage" value="${s}" ${i === 0 ? 'checked' : ''}> ${i + 1}. ${s}<span class="pct"></span><div class="pb"><i></i></div><span class="nt"></span></label>`).join('');
  if (save) post(`/api/projects/${P.id}/meta`, { workflow: wf });
}
$$('#wfSeg button').forEach(b => b.onclick = () => setWorkflow(b.dataset.wf));
$('#pTitle').onchange = () => post(`/api/projects/${P.id}/meta`, { title: $('#pTitle').value });
let CRS_LIST = [];
api('/api/crs').then(l => { CRS_LIST = l; window.CRS_LIST = l; const s = $('#pCrs'); if (!s) return;
  s.innerHTML = l.map(c => `<option value="${c.code}">EPSG:${c.code} ${c.name} (${c.units})</option>`).join(''); if (P) s.value = String(P.crs || 2136);
  if (window.proj4) l.forEach(c => { try { proj4.defs('EPSG:' + c.code, c.proj4); } catch (e) {} }); }).catch(() => {});
if ($('#pCrs')) $('#pCrs').onchange = async () => { if (!P) return; P.crs = +$('#pCrs').value; try { await post(`/api/projects/${P.id}/meta`, { crs: P.crs }); const c = CRS_LIST.find(x => x.code === P.crs);
  alert(`Coordinate system: EPSG:${P.crs} ${c ? c.name : ''}. Downloads and the zip now use it; every map layer is also written to the outputs folder Export_EPSG${P.crs}${P.crs === 2136 ? ' (not needed: the outputs are already in this system)' : ''}.`); } catch (e) { alert(e.message); } };
$$('input[name=bmode]').forEach(r => r.onchange = () => { P.buildings = r.value; post(`/api/projects/${P.id}/meta`, { buildings: r.value }); setWorkflow(P.workflow, false); });
$('#imagery').onchange = () => post(`/api/projects/${P.id}/meta`, { imagery: $('#imagery').value });
function refreshInputState() { const n = k => inputs[k].getLayers().length; $('#siteState').textContent = n('site') ? 'set' : 'not set'; $('#roadsState').textContent = n('roads') ? `${n('roads')} road lines` : ''; }
let newWf = 'design';
$('#newProj').onclick = () => { $('#nMsg').textContent = ''; $('#newDlg').hidden = false; $('#nName').focus(); };
$('#nCancel').onclick = () => $('#newDlg').hidden = true;
$$('#nWf button').forEach(b => b.onclick = () => { newWf = b.dataset.wf; $$('#nWf button').forEach(x => x.classList.toggle('on', x === b)); });
$('#nCreate').onclick = async () => { const msg = $('#nMsg'); msg.textContent = '';
  if (!$('#nName').value.trim()) { msg.textContent = 'Give the project a name.'; $('#nName').focus(); return; }
  try { const p = await post('/api/projects', { name: $('#nName').value, title: $('#nTitle').value, workflow: newWf }); $('#newDlg').hidden = true; $('#nName').value = ''; $('#nTitle').value = ''; loadProjects(p.id); } catch (e) { msg.textContent = e.message; } };
$('#chamferNow').onclick = async () => { if (!P) return;
  try { await post(`/api/projects/${P.id}/run`, { workflow: 'design', only: 'chamfer,audit', chamfer: true }); $$('.tabs button')[1].click(); refreshStatus(); alert('Chamfering the corner plots: the map updates when the run finishes.'); } catch (e) { alert(e.message); } };
// ---- roads edited after the plan was made: offer to update the plan ----
const rcBox = L.DomUtil.create('div', 'rcbox', map.getContainer()); rcBox.hidden = true; L.DomEvent.disableClickPropagation(rcBox);
let rcLater = null;
function showRoadsChanged(on) {
  if (!on) { rcBox.hidden = true; return; }
  if (luT || luBusy) return;                                          // a quick update is about to bring the plan in line
  if (rcLater === P?.id || !rcBox.hidden) return;                 // drawn once; not redrawn on every status check
  rcBox.innerHTML = `<b>You changed the roads after this plan was made.</b> The plots and land use do not show the new roads yet.
    <div class="mini">Updating re-runs roads, plots, land use${$('#chamfer')?.checked ? ', corner chamfers' : ''} and the audit from the roads as they are now. Manual edits to plots or land use are replaced.</div>
    <div class="row"><button id="rcGo">Update the plan</button><button id="rcLater" class="ghost">Later</button></div>`;
  rcBox.hidden = false;
  $('#rcGo').onclick = async () => { try { await post(`/api/projects/${P.id}/run`, { workflow: 'design', from: 'roads', chamfer: !!$('#chamfer')?.checked, steep: +$('#steep').value, stream_buffer: +$('#streamBuf').value }); rcBox.hidden = true; $$('.tabs button')[1].click(); refreshStatus(); alert('Updating the plan from the new roads: the map refreshes when the run finishes.'); } catch (e) { alert(e.message); } };
  $('#rcLater').onclick = () => { rcLater = P.id; rcBox.hidden = true; };
}
// ---- a road drawn or edited in a planned design: its surface goes in and the blocks it crosses are re-plotted (~1 s) ----
let luT = null, luBusy = false;
function queueLocalUpdate() {
  if (!P || P.workflow !== 'design' || !LAYER_INDEX.some(l => l.kind === 'plots_design')) { setTimeout(refreshStatus, 600); return; }
  clearTimeout(luT); luT = setTimeout(() => { luT = null; localUpdate(); }, 1200);              // after the edit settles (several quick edits: one update)
}
async function localUpdate() {
  if (luBusy) { queueLocalUpdate(); return; } luBusy = true;
  try {
    const r = await post(`/api/projects/${P.id}/design/local_update`);
    if (r.ok && (r.plots || r.added || r.removed)) { await reloadKinds(['plots_design', 'reserves', 'roads', 'blocks']); alert('Plan updated: ' + r.msg); }
    else if (!r.ok && r.msg) alert(r.msg);
  } catch (e) { alert(e.message); }
  luBusy = false; luT = null; refreshStatus();
}
async function reloadKinds(kinds) {
  for (const L_ of LAYER_INDEX.filter(l => kinds.includes(l.kind))) {
    const was = results[L_.path] && resGroup.hasLayer(results[L_.path]);
    if (results[L_.path]) { resGroup.removeLayer(results[L_.path]); delete results[L_.path]; }
    if (was) await toggleLayer(L_, true);
  }
}
$('#delProj').onclick = async () => {
  if (!P) return;
  if (!confirm(`Delete the project "${P.name}"?\n\nIts folder is moved to LP_Projects\\_deleted (you can recover it from there).`)) return;
  try {
    const r = await api(`/api/projects/${encodeURIComponent(P.id)}`, { method: 'DELETE' });
    clearInterval(poll); stopTool(); P = null; Object.values(inputs).forEach(g => g.clearLayers()); angleLayer.clearLayers(); clearResults();
    $('#proj').hidden = true; $('#noProj').hidden = false; await loadProjects();
    alert(`Project deleted (moved to ${r.moved_to}).`);
  } catch (e) { alert(e.message); }
};
$$('.tabs button').forEach(b => b.onclick = () => { $$('.tabs button').forEach(x => x.classList.toggle('on', x === b)); ['inputs', 'run', 'results'].forEach(t => $(`#tab-${t}`).hidden = t !== b.dataset.tab); if (b.dataset.tab === 'results') loadResults(); });

// ------------------------------------------------------------------ site analysis, road design, redesign
const designParams = () => ({ pattern: $('#dPattern').value, band: +$('#dBand').value, block_len: +$('#dLen').value, local_width: +$('#dLocal').value, collector_width: +$('#dColl').value,
  max_parcel_ac: +$('#dParcel').value, steep: +$('#steep').value, stream_buffer: +$('#streamBuf').value });
async function runOnly(stage, extra = {}) {
  try { await post(`/api/projects/${P.id}/run`, { workflow: P.workflow, only: stage, steep: +$('#steep').value, stream_buffer: +$('#streamBuf').value, roads_mode: 'file', ...extra }); refreshStatus(); } catch (e) { alert(e.message); }
}
// plot size for the whole planning area (saved with the project; roads and plots follow it)
function pickOpt(sel, v, label) { const s = $(sel); if (!s) return; let o = [...s.options].find(x => +x.value === v); if (!o) { o = new Option(label, v); s.add(o); } s.value = String(v); }
function plotSizeChanged(save = true) {
  const w = +$('#dPW').value || 0, l = +$('#dPL').value || 0;
  if (l > 0) pickOpt('#dBand', 2 * l, `${2 * l} ft (2 x ${l} ft plots)`);
  if (w > 0) { const n = Math.max(4, Math.round(490 / w)); pickOpt('#dLen', n * w, `${n * w} ft (${n} x ${w})`); }
  if (save && P) { P.plot_w = w || null; P.plot_l = l || null; const pid = P.id; clearTimeout(window._pszT); window._pszT = setTimeout(() => post(`/api/projects/${pid}/meta`, { plot_w: +$('#dPW').value || null, plot_l: +$('#dPL').value || null }).catch(e => alert(e.message)), 400); }
}
['#dPW', '#dPL'].forEach(id => { if ($(id)) $(id).onchange = () => plotSizeChanged(true); });
$('#siteBtn').onclick = () => { $('#terrState').textContent = 'running...'; runOnly('site'); };
$('#designBtn').onclick = async () => {
  if (inputs.roads.getLayers().length && !confirm('Replace the current roads with a new design?')) return;
  try { await post(`/api/projects/${P.id}/design_roads`, designParams()); $('#toolHint').textContent = 'Designing the roads... (1 to 3 minutes; see 2. Run for progress)'; refreshStatus(); } catch (e) { alert(e.message); }
};
$('#redesignBtn').onclick = async () => {
  if (!inputs.zones.getLayers().length) return alert('Draw the area to redesign first.');
  inputs.zones.eachLayer(l => l.feature.properties.pattern = $('#dPattern').value); await post(`/api/projects/${P.id}/layer/zones`, fcOf('zones'));
  try { await post(`/api/projects/${P.id}/redesign`, designParams()); $('#toolHint').textContent = 'Redesigning the area... (see 2. Run for progress)'; refreshStatus(); } catch (e) { alert(e.message); }
};
const SLOPE_COL = { 'Flat': '#1a9850', 'Gentle': '#91cf60', 'Moderate': '#fee08b', 'Steep': '#fc8d59', 'Very steep': '#d73027' };
const slopeCol = c => SLOPE_COL[Object.keys(SLOPE_COL).find(k => (c || '').startsWith(k))] || '#ccc';
async function loadTerrain() {
  if (!P || P.workflow !== 'design') return;
  const t = await api(`/api/projects/${P.id}/terrain`);
  if (!t.relief) { $('#terrSum').innerHTML = ''; $('#terrState').textContent = 'not done yet'; $('#terrLayers').innerHTML = ''; return; }
  $('#terrState').textContent = 'done';
  $('#terrSum').innerHTML = `<table class="mini"><tr><th colspan="2">Elevation ${t.elev_min}-${t.elev_max} m (relief ${t.relief} m), contours every ${t.contour_interval} m, mean slope ${t.mean_slope_pct}%</th></tr>` +
    t.classes.map(c => `<tr><td><span class="swatch" style="background:${slopeCol(c.cls)}"></span>${c.cls}</td><td>${c.area_ac} ac (${c.share}%)</td></tr>`).join('') +
    (t.steep_pct > 0 ? `<tr><td><b>Kept green (slopes >= ${t.steep_pct}%)</b></td><td><b>${t.steep_reserve_ac} ac</b></td></tr>` : '') + '</table>';
  const r = await api(`/api/projects/${P.id}/layers`); $('#terrLayers').innerHTML = '';
  for (const L_ of r.layers.filter(l => ['raster', 'slope', 'contours', 'steep'].includes(l.kind))) {
    const lab = document.createElement('label'); const cb = document.createElement('input'); cb.type = 'checkbox';
    cb.checked = !!(results[L_.path] && resGroup.hasLayer(results[L_.path])) || L_.label === 'Contours';
    cb.onchange = () => toggleLayer(L_, cb.checked); $('#terrLayers').append(layerRow(L_, lab, cb)); if (cb.checked) toggleLayer(L_, true);
  }
}

// ------------------------------------------------------------------ run
$('#runBtn').onclick = async () => {
  const mode = $('#runMode').value, st = $('input[name=stage]:checked')?.value;
  const body = { chamfer: P.workflow === 'design' && $('#chamfer').checked, workflow: P.workflow, profile: $('#profile').value, roads_mode: 'file', stream_buffer: +$('#streamBuf').value, steep: +$('#steep').value, buildings: P.buildings || 'fast' };
  if (mode === 'from') body.from = st; if (mode === 'only') body.only = st;
  const w = []; if ($('#xFoot').checked) w.push('footpaths'); if ($('#xProp').checked) w.push('proposals'); if (w.length) body.with = w.join(',');
  try { await post(`/api/projects/${P.id}/run`, body); $$('.tabs button')[1].click(); refreshStatus(); } catch (e) { alert(e.message); }
};
$('#stopBtn').onclick = async () => { if (!P) return; try { const s = await api(`/api/projects/${P.id}/status`); if (!s.running) return alert('Nothing is running.'); await post(`/api/projects/${P.id}/stop`); alert('Stopping the run.'); refreshStatus(); } catch (e) { alert(e.message); } };
let wasRunning = false;
async function refreshStatus() {
  if (!P) return; let s; try { s = await api(`/api/projects/${P.id}/status`); } catch { return; }
  const log = $('#log'), atEnd = log.scrollTop + log.clientHeight >= log.scrollHeight - 30; log.textContent = s.log || 'No run yet.'; if (atEnd) log.scrollTop = log.scrollHeight;
  showRoadsChanged(!!s.roads_changed); if (s.edits && window.markSaved) markSaved(s.edits.dirty, s.edits.saved_at);
  const fe = $('#runFail'); if (fe) { fe.hidden = !s.failure; if (s.failure) fe.innerHTML = `<b>The run stopped${s.failure.stage ? ' at ' + s.failure.stage : ''}.</b> ${s.failure.what}<br><b>What to do:</b> ${s.failure.todo}<div class="mini">Details: ${s.failure.detail.replace(/</g, '&lt;')}</div>`; }
  const doneSet = new Set(s.stages.slice(0, s.finished));
  const cur = s.running ? s.stages[s.stages.length - 1] : null;
  $$('#stageList label').forEach(l => {
    const v = l.dataset.s, done = doneSet.has(v), now = v === cur && !done, pct = (s.progress || {})[v];
    l.classList.toggle('done', done); l.classList.toggle('now', now);
    const pb = l.querySelector('.pb'), bar = pb.firstElementChild, ran = s.stages.includes(v);
    pb.classList.toggle('ind', now && !(pct > 0)); bar.style.width = done ? '100%' : now ? `${pct || 0}%` : (ran && !done && s.failed ? `${pct || 0}%` : '0');
    l.querySelector('.pct').textContent = done ? '100%' : now ? (pct > 0 ? `${pct}%` : '') : '';
    l.querySelector('.nt').textContent = now ? ((s.notes || {})[v] || '') : '';
  });
  const pct = s.stages.length ? Math.round(100 * s.finished / Math.max(s.stages.length, 1)) : 0; $('#barIn').style.width = (s.running ? pct : (s.stages.length ? 100 : 0)) + '%';
  const b = $('#pState');
  if (s.running) { b.textContent = 'running: ' + (s.stages[s.stages.length - 1] || 'starting'); b.className = 'badge run'; $('#runMsg').textContent = `${s.finished} stage(s) done`; }
  else if (s.failed) { b.textContent = 'stopped with an error'; b.className = 'badge bad'; $('#runMsg').textContent = 'See the log for the error.'; }
  else if (s.paused) { b.textContent = 'paused: facilities to decide'; b.className = 'badge run'; $('#runMsg').textContent = 'Some facilities did not fit: choose for each below, then continue.'; }
  else if (s.stages.length) { b.textContent = 'finished'; b.className = 'badge ok'; $('#runMsg').textContent = 'Done.'; }
  if (window.FAC) FAC.status(s);
  else { b.textContent = 'ready'; b.className = 'badge'; }
  if (!s.running && s.pending_load && !s.failed) {                // a road design / redesign finished: load it for editing
    try { const fc = await post(`/api/projects/${P.id}/load_draft`); loadInput('roads', fc); inputs.zones.clearLayers(); saveInput('zones'); refreshInputState(); $('#toolHint').textContent = 'Design loaded: edit it with the tools, or draw an area and Redesign.'; } catch (e) { console.warn(e); }
  }
  if (wasRunning && !s.running) { await loadResults(true); loadTerrain(); if (typeof FE !== 'undefined') FE.refreshLayers(); } wasRunning = s.running;
}

// ------------------------------------------------------------------ results
// LUSPA colour codes (Revised Zoning Guidelines and Planning Standards 2025, Tables 1 and 2): code -> [name, fill, pattern colour, edge]
const LUSPA = { 'Re': ['Residential', '#DC7C24'], 'Re A': ['Residential Zone A', '#CC7722'], 'Re B': ['Residential Zone B', '#E5AA70'], 'Re C': ['Residential Zone C', '#BB8855'],
  'Re D': ['Residential Zone D', '#98623C'], 'Com': ['Commercial', '#73B2FF'], 'CBD': ['Central Business District', '#2E4DA7'], 'BM': ['Mixed Business / Residential', '#73B2FF', '#FFAA57'],
  'BI': ['Informal Business', '#73B2FF', '#000000'], 'TL': ['Transportation and Logistics', '#D6D6D6', '#000000'], 'CC': ['Civic and Culture', '#FF7F7F'],
  'PW': ['Place of Worship', '#FF7F7F', '#000000'], 'H': ['Health', '#FF0000'], 'BG': ['Government Business', '#FF7F7F', '#000000'], 'T': ['Tourist / Heritage', '#FF0080'],
  'SU': ['Special / Utility', '#FF7F7F', '#000000'], 'InD': ['Industrial', '#F4AFF4'], 'LI': ['Light Industrial', '#E8BEFF'], 'IS': ['Service Industry', '#EE82EE'],
  'Ed': ['Educational', '#FFFF00', null, '#C00000'], 'Ed P': ['Education Zone A: Pre-school and Basic', '#FFFF00', '#000000', '#C00000'], 'Ed S': ['Education Zone B: Senior High and TVET', '#FFFF00', '#000000', '#C00000'], 'Ed T': ['Education Zone C: Tertiary', '#FFFF00', '#000000', '#C00000'], 'SZ': ['Security', '#FF7F7F', '#000000'], 'PS': ['Public Space', '#00FF00'],
  'CA': ['Conservation', '#32CD32'], 'Ag': ['Agriculture', '#ADFF2F'], 'VAC': ['Open / yard, no building', '#FFFFFF', null, '#9E9E9E'], 'UNC': ['Use NOT confirmed: please verify', '#FFFFFF', '#FF6D00', '#FF6D00'] };
const EXIST_LUSPA = { 'Residential': 'Re', 'Mixed use (shop + residence)': 'BM', 'Commercial / mixed use': 'BM', 'Commercial': 'Com', 'Commercial (hotel)': 'Com', 'Commercial (fuel)': 'Com',
  'Commercial (entertainment)': 'Com', 'Commercial (wholesale / storage)': 'Com', 'Commercial (parking)': 'TL', 'Office': 'Com', 'Market': 'Com', 'Transport terminal': 'TL',
  'Health': 'H', 'Education': 'Ed', 'Religious': 'PW', 'Religious / assembly': 'PW', 'Civic': 'CC', 'Institutional / large commercial (verify)': 'CC', 'Recreation': 'PS',
  'Industrial': 'InD', 'Mixed use (industrial + commercial)': 'IS', 'Mixed use (commercial + industrial)': 'IS', 'Agricultural': 'Ag', 'Open / yard (no building)': 'VAC', 'Unconfirmed (verify)': 'UNC', 'Utility': 'SU' };
const DESIGN_LUSPA = { RE: 'Re B', RA: 'Re A', MU: 'BM', BM: 'BM', 'Com A': 'Com', CIV: 'CC', TR: 'TL', PW: 'PW', 'H Po': 'H', 'Ed P': 'Ed P', 'Ed S': 'Ed S', 'Ed T': 'Ed T', HD: 'H', HR: 'H', HT: 'H', POS: 'PS', GRN: 'CA', SU: 'SU', '': 'VAC' };
const luspaStyle = (code, base = {}) => { const c = LUSPA[code] || LUSPA.VAC; return { color: c[3] || c[2] || '#222', weight: code === 'UNC' ? 2.5 : c[3] ? 2 : c[2] ? 1.6 : .8, dashArray: code === 'UNC' ? '6 4' : c[2] && !c[3] ? '4 3' : null, fillColor: c[1], fillOpacity: .85, ...base }; };
const luspaLegend = codes => codes.map(k => { const c = LUSPA[k]; return `<span${k === 'VAC' || k === 'UNC' ? '' : ` class="lstd" title="Open the planning standard for ${k}" onclick="Standards.open('${k}')"`}><i style="background:${c[1]};border-color:${c[3] || c[2] || '#555'};${c[2] ? 'border-style:dashed;border-width:2px' : ''}"></i>${k === 'VAC' ? '' : '<b>' + k + '</b> '}${c[0]}</span>`; }).join('');
// kept for the attribute autocomplete
const USE_COL = Object.fromEntries(Object.keys(EXIST_LUSPA).map(k => [k, LUSPA[EXIST_LUSPA[k]][1]]));
const DES_COL = Object.fromEntries(Object.keys(DESIGN_LUSPA).filter(k => k).map(k => [k, LUSPA[DESIGN_LUSPA[k]][1]]));
const results = {}; const resGroup = L.layerGroup().addTo(map);
function clearResults() { resGroup.clearLayers(); for (const k in results) delete results[k]; $('#layerList').innerHTML = ''; $('#fileList').innerHTML = ''; $('#legend').innerHTML = ''; }
function popupHtml(p) { return '<table>' + Object.entries(p).filter(([k, v]) => v !== null && v !== '' && v !== 'None' && v !== 'nan').slice(0, 14).map(([k, v]) => `<tr><td><b>${k}</b></td><td>${v}</td></tr>`).join('') + '</table>'; }
function styleFor(kind) {
  return f => {
    const p = f.properties || {};
    switch (kind) {
      case 'plots': return luspaStyle(EXIST_LUSPA[p.ex_use] || 'VAC', (p.access || '').startsWith('Interior') ? { dashArray: '2 4' } : {});
      case 'plots_design': case 'reserves': return luspaStyle(DESIGN_LUSPA[p.use] || (p.use ? 'CC' : 'Re B'));
      case 'buildings': return { color: '#1f5fd1', weight: 1, fillOpacity: 0 };
      case 'blocks': return { color: '#000', weight: 1.5, fillOpacity: 0 };
      case 'roads': return { color: '#666', weight: .5, fillColor: '#c8c8c8', fillOpacity: .85 };
      case 'walls': return { color: '#e91e63', weight: 2 };
      case 'green': return { color: '#1b5e20', weight: 1, fillColor: LUSPA.CA[1], fillOpacity: .7 };
      case 'slope': return { color: '#555', weight: .3, fillColor: slopeCol(p.cls), fillOpacity: .55 };
      case 'contours': return { color: '#6d4c41', weight: (p.major === true || p.major === 1 || p.major === 'True') ? 1.6 : .6, opacity: .9 };
      case 'steep': return { color: '#b71c1c', weight: 1, fillColor: '#2e7d32', fillOpacity: .45, dashArray: '4 3' };
      case 'draft': return { color: p.kind === 'existing' ? '#111' : p.kind === 'collector' ? '#f5a142' : '#1f5fd1', weight: p.kind === 'local' ? 2 : 4 };
      default: return { color: '#333', weight: 1 };
    }
  };
}
const SEV = { high: '#b42318', medium: '#f59e0b', low: '#9ca3af' };
async function toggleLayer(L_, on) {
  if (!on) { if (results[L_.path]) resGroup.removeLayer(results[L_.path]); rebuildLegend(); return; }
  if (!results[L_.path] && L_.kind === 'raster') results[L_.path] = L.imageOverlay(`/api/projects/${P.id}/file?f=${encodeURIComponent(L_.path)}`, L_.bounds, { opacity: .75 });
  if (!results[L_.path]) {
    const fc = await api(`/api/projects/${P.id}/geojson?f=${encodeURIComponent(L_.path)}`);
    const top_ = TOP_KINDS.has(L_.kind);
    results[L_.path] = L.geoJSON(fc, { ...(top_ ? { pane: 'topLines', renderer: TOP_R } : {}), style: styleFor(L_.kind), interactive: !['contours', 'slope', 'steep'].includes(L_.kind), onEachFeature: (f, l) => { l.bindPopup(popupHtml(f.properties || {})); l.on('click', e => { if ((typeof FE !== 'undefined' && FE.capture(L_, f, l, e)) || (typeof Editor !== 'undefined' && Editor.captureResultClick(L_.kind, f, l, e))) { L.DomEvent.stop(e); setTimeout(() => l.closePopup(), 0); } }); },
      pointToLayer: (f, ll) => L.circleMarker(ll, { ...(top_ ? { pane: 'topLines', renderer: TOP_R } : {}), radius: L_.kind === 'audit' ? 7 : 5, color: '#fff', weight: 1.5, fillColor: L_.kind === 'audit' ? (SEV[f.properties.sev] || '#666') : '#ff6d00', fillOpacity: .95 }) });
  }
  results[L_.path]._kind = L_.kind; resGroup.addLayer(results[L_.path]); if (opOf(L_.path) < 0.999) applyOp(L_.path);
  if (['raster', 'slope', 'steep'].includes(L_.kind)) results[L_.path].bringToBack?.();
  rebuildLegend();
}
async function loadResults(fresh) {
  if (!P) return; if (fresh) clearResults();
  let r; try { r = await api(`/api/projects/${P.id}/layers`); } catch { return; }
  LAYER_INDEX = r.layers;
  const DEFAULT_ON = new Set(['plots', 'plots_design', 'reserves', 'roads', 'lines']);
  const GROUPS = [['Land use and plots', ['plots', 'plots_design', 'blocks', 'reserves']], ['Roads', ['roads', 'lines', 'points']], ['Buildings', ['buildings', 'walls']],
                  ['Terrain and environment', ['raster', 'slope', 'contours', 'steep', 'green']], ['Checks', ['audit']]];
  const grpOf = k => (GROUPS.find(([, ks]) => ks.includes(k)) || ['Other'])[0];
  const order = [...GROUPS.map(g => g[0]), 'Other'];
  const list = r.layers.filter(l => l.kind !== 'draft').map((l, i) => ({ l, i })).sort((a, b) => order.indexOf(grpOf(a.l.kind)) - order.indexOf(grpOf(b.l.kind)) || a.i - b.i).map(x => x.l);
  $('#layerList').innerHTML = list.length ? '' : '<p class="hint">No results yet: run the toolkit first.</p>';
  let lastG = null;
  for (const L_ of list) {
    const gname = grpOf(L_.kind); if (gname !== lastG) { const h = document.createElement('div'); h.className = 'lgh'; h.textContent = gname; $('#layerList').append(h); lastG = gname; }
    const lab = document.createElement('label'); const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = DEFAULT_ON.has(L_.kind) || !!(results[L_.path] && resGroup.hasLayer(results[L_.path]));
    cb.onchange = () => toggleLayer(L_, cb.checked); $('#layerList').append(layerRow(L_, lab, cb)); if (cb.checked) toggleLayer(L_, true);
  }
  const drawn = [['site', 'Site boundary'], ['roads', 'Roads you drew'], ['reserves', 'Road reserves (drawn roads)'], ['existing', 'Existing roads to keep'], ['stream', 'Streams / water'], ['zones', 'Redesign areas']]
    .filter(([k]) => k === 'reserves' ? inputs.roads.getLayers().length || inputs.existing.getLayers().length : inputs[k].getLayers().length);
  if (drawn.length) { const h = document.createElement('div'); h.className = 'lgh'; h.textContent = 'Drawn on the map'; $('#layerList').append(h);
    for (const [k, lab_] of drawn) { const row = document.createElement('div'); row.className = 'lrow'; row.dataset.input = k; const s_ = document.createElement('span'); s_.className = 'lname'; s_.textContent = lab_; row.append(s_, zoomBtn({ input: k }), opSlider('in:' + k, () => applyInputOp(k))); $('#layerList').append(row); }
  }
  applyInputOp('reserves');
  const kinds = new Set(list.map(l => l.kind));
  const leg = {};
  const legS = kinds.has('slope') ? Object.entries(SLOPE_COL).map(([k, c]) => `<span><i style="background:${c}"></i>${k}</span>`).join('') : '';
  const legHtml = legS + (kinds.has('plots_design') ? luspaLegend(['Re A', 'Re B', 'BM', 'Com', 'Ed P', 'H', 'CC', 'PW', 'TL', 'PS', 'CA', 'SU']) : kinds.has('plots') ? luspaLegend(Object.keys(LUSPA)) : '');
  rebuildLegend();
  $('#chamferCard').hidden = !(P.workflow === 'design' && kinds.has('plots_design'));
  renderDownloads(r);
  setTimeout(checkUnconfirmed, 1500);
  $('#legend').innerHTML = legHtml + (kinds.has('audit') ? `<div class="hint">Audit dots: <b style="color:${SEV.high}">high</b>, <b style="color:${SEV.medium}">medium</b>, <b style="color:#888">low</b>. Click a dot for the fix.</div>` : '');
  $('#fileList').innerHTML = r.files.filter(f => !f.endsWith('.json')).map(f => `<a data-f="${f}">${f.split('/').pop()}</a>`).join('') || '<p class="hint">No files yet.</p>';
  $$('#fileList a').forEach(a => a.onclick = () => { const f = a.dataset.f, u = `/api/projects/${P.id}/file?f=${encodeURIComponent(f)}`;
    if (f.endsWith('.png')) { $('#mBody').innerHTML = `<h3>${f.split('/').pop()}</h3><img src="${u}">`; $('#modal').hidden = false; } else window.open(u); });
  $('#zipBtn').href = `/api/projects/${P.id}/zip`;
}
$('#mClose').onclick = () => $('#modal').hidden = true;
$('#modal').addEventListener('click', e => { if (e.target.id === 'modal') $('#modal').hidden = true; });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { if (!$('#modal').hidden) $('#modal').hidden = true; if (!$('#newDlg').hidden) $('#newDlg').hidden = true; } });
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
}
let LAYER_INDEX = [];
// outlines, lines and points are drawn on their own canvas above the filled layers (plots, road surface), so fills never hide them
map.createPane('topLines'); map.getPane('topLines').style.zIndex = 450;
const TOP_R = L.canvas({ pane: 'topLines', tolerance: 7 });
const TOP_KINDS = new Set(['blocks', 'lines', 'walls', 'points', 'audit', 'contours']);
// hover over a design audit point: the finding and its fix in a tooltip (several findings at one spot are listed together)
const auditTip = L.tooltip({ direction: 'top', offset: [0, -8], className: 'audittip', opacity: 1 }); let auditT = 0;
let auditE = null;
map.on('mousemove', e => { auditE = e; if (!auditT) auditT = setTimeout(() => { auditT = 0; auditHover(auditE); }, 50); });   // the latest position, 50 ms after the move
function auditHover(e) {
  const L_ = LAYER_INDEX.find(l => l.kind === 'audit'), g = L_ && results[L_.path];
  if (!g || !resGroup.hasLayer(g)) { if (map.hasLayer(auditTip)) map.closeTooltip(auditTip); return; }
  const p0 = map.latLngToContainerPoint(e.latlng), hits = [];
  g.eachLayer(l => { const d = map.latLngToContainerPoint(l.getLatLng()).distanceTo(p0); if (d < 12) hits.push([d, l]); });
  if (!hits.length) { if (map.hasLayer(auditTip)) map.closeTooltip(auditTip); map.getContainer().classList.remove('overaudit'); return; }
  hits.sort((a, b) => a[0] - b[0]); map.getContainer().classList.add('overaudit');
  const esc = t => String(t ?? '').replace(/</g, '&lt;');
  const html = hits.slice(0, 4).map(([, l]) => { const p = l.feature.properties;
    return `<div class="ai"><b style="color:${SEV[p.sev] || '#666'}">${esc(p.sev).toUpperCase()}</b> <span class="mini">#${esc(p.n)} &middot; ${esc(p.cat)}</span><div>${esc(p.what)}</div><div class="mini"><b>Fix:</b> ${esc(p.fix)}</div></div>`; }).join('') + (hits.length > 4 ? `<div class="mini">+${hits.length - 4} more here</div>` : '');
  auditTip.setLatLng(hits[0][1].getLatLng()).setContent(html); if (!map.hasLayer(auditTip)) map.openTooltip(auditTip);
}
// no tool open: a click near a line or point of the top layers opens its pop-up (the top canvas itself takes no clicks)
map.on('click', e => {
  if ((typeof Editor !== 'undefined' && Editor.tool) || (typeof FE !== 'undefined' && FE.active)) return;
  const pt = turf.point([e.latlng.lng, e.latlng.lat]), tol = 8 * 40075016.7 * Math.cos(e.latlng.lat * Math.PI / 180) / Math.pow(2, map.getZoom() + 8);
  let best = null, bd = tol;
  for (const L_ of LAYER_INDEX) { if (!TOP_KINDS.has(L_.kind) || L_.kind === 'blocks' || !results[L_.path] || !resGroup.hasLayer(results[L_.path])) continue;
    results[L_.path].eachLayer(l => { let d = Infinity; try { const g = l.toGeoJSON(); const t = g.geometry.type;
      d = t === 'Point' ? turf.distance(pt, g, { units: 'meters' }) : t.includes('LineString') ? turf.pointToLineDistance(pt, t === 'LineString' ? g : turf.lineString(g.geometry.coordinates.flat()), { units: 'meters' }) : Infinity; } catch (er) {}
      if (d < bd) { bd = d; best = l; } }); }
  if (best && best.getPopup()) best.openPopup(e.latlng);
});
async function reloadPlots() { for (const L_ of LAYER_INDEX.filter(l => l.kind === 'plots')) { if (results[L_.path]) { resGroup.removeLayer(results[L_.path]); delete results[L_.path]; } await toggleLayer(L_, true); } }
// ---- legend on the map (hideable) ----
const legendCtl = L.control({ position: 'bottomright' });
legendCtl.onAdd = () => { const d = L.DomUtil.create('div', 'maplegend'); d.innerHTML = '<div class="lh"><b>Legend</b><button title="Hide / show the legend">&minus;</button></div><div class="lb"></div>';
  L.DomEvent.disableClickPropagation(d); L.DomEvent.disableScrollPropagation(d);
  d.querySelector('button').onclick = () => { d.classList.toggle('shut'); d.querySelector('button').innerHTML = d.classList.contains('shut') ? '+' : '&minus;'; try { localStorage.setItem('lp_leg', d.classList.contains('shut') ? '0' : '1'); } catch (e) {} };
  try { if (localStorage.getItem('lp_leg') === '0') { d.classList.add('shut'); d.querySelector('button').innerHTML = '+'; } } catch (e) {}
  return d; };
legendCtl.addTo(map);
// ---- grouped legend: what is on the map, by feature group and sub-group ----
const LEG_GROUPS = [['Residential', ['Re', 'Re A', 'Re B', 'Re C', 'Re D']], ['Commercial and mixed use', ['Com', 'CBD', 'BM', 'BI']],
  ['Community facilities', ['Ed', 'Ed P', 'Ed S', 'Ed T', 'H', 'CC', 'PW', 'BG', 'T']], ['Open space and environment', ['PS', 'CA', 'CZ', 'Ag']],
  ['Transport and utilities', ['TL', 'SU', 'SZ']], ['Industrial', ['InD', 'LI', 'IS']], ['Not a zoning class', ['VAC', 'UNC']]];
const legItem = (style, label) => `<span><i style="${style}"></i>${label}</span>`;
function rebuildLegend() {
  if (typeof resGroup === 'undefined') return;
  const on = LAYER_INDEX.filter(l => results[l.path] && resGroup.hasLayer(results[l.path])), kinds = new Set(on.map(l => l.kind)), parts = [];
  const sec = (title, body, open = true) => body ? `<details class="lg" ${open ? 'open' : ''}><summary>${title}</summary>${body}</details>` : '';
  // land use (existing plots, design plots, facility / green sites)
  const used = new Set();
  for (const l of on) { if (!['plots', 'plots_design', 'reserves'].includes(l.kind)) continue;
    results[l.path].eachLayer(x => { const p = x.feature?.properties || {}; used.add(l.kind === 'plots' ? (EXIST_LUSPA[p.ex_use] || 'VAC') : (DESIGN_LUSPA[p.use] || (p.use ? 'CC' : 'Re B'))); }); }
  if (used.size) parts.push(sec('Land use <span class="mini">(LUSPA 2025)</span>', LEG_GROUPS.map(([g, codes]) => { const c = codes.filter(k => used.has(k)); return c.length ? `<div class="lsub">${g}</div>` + luspaLegend(c) : ''; }).join('')));
  // terrain
  let ter = '';
  if (kinds.has('slope')) ter += `<div class="lsub">Slope</div>` + Object.entries(SLOPE_COL).map(([k, c]) => legItem(`background:${c}`, k)).join('');
  if (kinds.has('steep')) ter += legItem('background:#d73027;opacity:.5', 'Steep-slope reserve (kept green)');
  if (kinds.has('contours')) ter += legItem('border:0;border-top:2px solid #8d6e63;height:0;margin-top:6px', 'Contours');
  parts.push(sec('Terrain', ter, false));
  // roads
  let rd = '';
  if (kinds.has('roads')) rd += legItem('background:#c8c8c8;border-color:#666', 'Road surface / reserve');
  if (kinds.has('lines')) rd += legItem('border:0;border-top:2px solid #444;height:0;margin-top:6px', 'Road centrelines');
  const ws = [...new Set([...inputs.roads.getLayers(), ...inputs.existing.getLayers()].map(x => +(x.feature?.properties?.width_ft || 0)).filter(Boolean))].sort((a, b) => b - a);
  if (ws.length) rd += `<div class="lsub">Road hierarchy (reserve width)</div>` + ws.map(w => legItem(`border:0;border-top:${Math.max(2, Math.min(8, w / 15))}px solid ${w >= 60 ? '#333' : w >= 40 ? '#f5a623' : '#9e9e9e'};height:0;margin-top:6px`, `${w} ft${w === ws[0] ? ' (highest)' : ''}`)).join('');
  if (kinds.has('points')) rd += legItem('background:#ff6d00;border-radius:50%;border-color:#fff', 'Road pinch points');
  parts.push(sec('Roads', rd));
  // other features
  let ft = '';
  if (inputs.site.getLayers().length) ft += legItem('border:2px solid #ff3b30;background:none', 'Site boundary');
  if (kinds.has('blocks')) ft += legItem('border:1.5px solid #000;background:none', 'Blocks');
  if (kinds.has('buildings')) ft += legItem('border:1px solid #1f5fd1;background:none', 'Buildings');
  if (kinds.has('walls')) ft += legItem('border:0;border-top:2px solid #e91e63;height:0;margin-top:6px', 'Walls / fences');
  if (kinds.has('green')) ft += legItem(`background:${LUSPA.CA[1]}`, 'Tree belt / vacant land');
  if (inputs.stream.getLayers().length) ft += legItem('background:#2e8b57;opacity:.6', 'Streams / water');
  if (kinds.has('audit')) ft += `<div class="lsub">Design audit findings</div>` + Object.entries(SEV).map(([k, c]) => legItem(`background:${c};border-radius:50%`, k)).join('');
  parts.push(sec('Other features', ft));
  setMapLegend(parts.join(''));
}
function setMapLegend(html) { const d = legendCtl.getContainer(); d.querySelector('.lb').innerHTML = html; d.style.display = html ? '' : 'none'; }
setMapLegend('');
// ---- downloads: tick what you need, get one zip (vector layers as shapefiles) ----
function renderDownloads(r) {
  const box = $('#dlList'); if (!box) return;
  const items = r.downloads || [];
  box.innerHTML = items.length ? items.map(it => `<label class="tl"><input type="checkbox" value="${it.id}" ${it.default ? 'checked' : ''}> ${it.label} <span class="mini">${it.kind}</span></label>`).join('') : '<p class="hint">Nothing to download yet.</p>';
}
$('#dlAll').onclick = () => $$('#dlList input').forEach(c => c.checked = true);
$('#dlNone').onclick = () => $$('#dlList input').forEach(c => c.checked = false);
$('#dlBtn').onclick = () => { const ids = $$('#dlList input:checked').map(c => c.value); if (!ids.length) return alert('Tick what you want to download.');
  window.location = `/api/projects/${P.id}/download?items=${encodeURIComponent(ids.join('|'))}`; };
$('#panelBtn').onclick = () => { document.body.classList.toggle('nopanel'); setTimeout(() => map.invalidateSize(), 50); try { localStorage.setItem('lp_panel', document.body.classList.contains('nopanel') ? '0' : '1'); } catch (e) {} };
try { if (localStorage.getItem('lp_panel') === '0') { document.body.classList.add('nopanel'); setTimeout(() => map.invalidateSize(), 50); } } catch (e) {}
$('#guideBtn').onclick = async () => { const md = await api('/api/guide'); $('#mBody').innerHTML = marked.parse(md); $('#modal').hidden = false; };
const QP = new URLSearchParams(location.search);
loadProjects(QP.get('p')).then(() => { const t = QP.get('tab'); if (t && P) setTimeout(() => $(`.tabs button[data-tab=${t}]`)?.click(), 800); const tl = QP.get('tool'); if (tl && P) setTimeout(() => Editor.open(tl), 900); });
