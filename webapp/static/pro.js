// LP Toolkit: ArcGIS Pro style sketching and snapping, shared by every digitising tool (features, roads, site, streams, zones).
// Snapping: endpoint / vertex / edge / intersection / midpoint toggles + tolerance, snap tip at the cursor.
// Sketch: F2 / Enter finish, Esc cancel, Backspace delete last vertex, T trace, D distance, A direction, P parallel,
// E perpendicular, R right angle to the last segment, right-click menu with all of them.
const Sketch = (() => {
  const FTM = 0.3048, M = { units: 'meters' };
  const SNAP = Object.assign({ on: true, end: true, vertex: true, edge: true, inter: true, mid: false, tol: 12, roadAll: false }, (() => { try { return JSON.parse(localStorage.getItem('lp_snap') || '{}'); } catch (e) { return {}; } })());
  const saveSnap = () => { try { localStorage.setItem('lp_snap', JSON.stringify(SNAP)); } catch (e) {} };
  map.createPane('proSketch'); map.getPane('proSketch').style.zIndex = 665; map.getPane('proSketch').style.pointerEvents = 'none';
  const R_ = L.svg({ pane: 'proSketch' }), g = L.layerGroup().addTo(map);
  const opt = o => Object.assign({ interactive: false, renderer: R_, pane: 'proSketch' }, o);
  let S = null;                                                           // the active sketch
  // ---------------------------------------------------------------- geometry to snap to (what is drawn in view)
  const NOSNAP = ['contours', 'slope', 'steep', 'water', 'audit', 'raster', 'hillshade'];
  function collect(roadsOnly) {                                          // roadsOnly: a road sketch snaps to roads, the site and streams (not plot corners)
    const out = [], vb = map.getBounds().pad(0.3), add = (lyr, closed) => {
      if (!lyr.getLatLngs || (lyr.getBounds && !vb.intersects(lyr.getBounds()))) return;
      const walk = a => { if (!a.length) return; if (a[0] instanceof L.LatLng) { const c = a.map(p => [p.lng, p.lat]); if (closed && c.length > 2) c.push(c[0]); if (c.length > 1) { const ln = turf.lineString(c); out.push({ ln, bb: turf.bbox(ln), closed }); } } else a.forEach(walk); };
      walk(lyr.getLatLngs());
    };
    if (typeof resGroup !== 'undefined') resGroup.eachLayer(gr => { const k = gr._kind || ''; if (NOSNAP.includes(k) || (roadsOnly && !/centre|draft/.test(k))) return; gr.eachLayer?.(l => add(l, l instanceof L.Polygon)); });
    Object.entries(inputs).forEach(([k, gr]) => { if (roadsOnly && k === 'zones') return; gr.eachLayer(l => add(l, l instanceof L.Polygon)); });
    return out;
  }
  function intersections(rings) {                                         // lazily, for the geometry in view (lines first; at most ~400 shapes)
    const pts = [], rs = rings.slice(0, 400);
    for (let i = 0; i < rs.length; i++) for (let j = i + 1; j < rs.length; j++) {
      const a = rs[i].bb, b = rs[j].bb; if (a[2] < b[0] || b[2] < a[0] || a[3] < b[1] || b[3] < a[1]) continue;
      try { turf.lineIntersect(rs[i].ln, rs[j].ln).features.forEach(f => pts.push(f.geometry.coordinates)); } catch (e) {}
    }
    return pts;
  }
  const mpp = () => 40075016.686 * Math.cos(map.getCenter().lat * Math.PI / 180) / (256 * 2 ** map.getZoom());
  function snapAt(ll) {
    if (!SNAP.on || !S) return null;
    const tol = SNAP.tol * mpp(), td = tol / 111000 * 1.5, pt = turf.point([ll.lng, ll.lat]); let best = null;
    const take = (d, c, type, ri, rank) => { if (d < tol && (!best || rank < best.rank || (rank === best.rank && d < best.d))) best = { d, c, type, ri, rank }; };
    S.rings.forEach((r, ri) => {
      if (ll.lng < r.bb[0] - td || ll.lng > r.bb[2] + td || ll.lat < r.bb[1] - td || ll.lat > r.bb[3] + td) return;
      const cs = r.ln.geometry.coordinates;
      if (SNAP.end && !r.closed) { take(turf.distance(pt, cs[0], M), cs[0], 'Endpoint', ri, 0); take(turf.distance(pt, cs[cs.length - 1], M), cs[cs.length - 1], 'Endpoint', ri, 0); }
      if (SNAP.vertex) cs.forEach(c => take(turf.distance(pt, c, M), c, 'Vertex', ri, 2));
      if (SNAP.mid) for (let k = 0; k < cs.length - 1; k++) { const m = [(cs[k][0] + cs[k + 1][0]) / 2, (cs[k][1] + cs[k + 1][1]) / 2]; take(turf.distance(pt, m, M), m, 'Midpoint', ri, 3); }
      if (SNAP.edge) { const np = turf.nearestPointOnLine(r.ln, pt, M); take(np.properties.dist, np.geometry.coordinates, 'Edge', ri, 4); }
    });
    if (SNAP.inter) { if (!S.inter) S.inter = intersections(S.rings); S.inter.forEach(c => take(turf.distance(pt, c, M), c, 'Intersection', -1, 1)); }
    if (best && best.ri >= 0) best.loc = turf.nearestPointOnLine(S.rings[best.ri].ln, turf.point(best.c), M).properties.location;
    return best;
  }
  function edgeBearingAt(ll) {                                           // direction of the edge under the cursor (parallel / perpendicular)
    const pt = turf.point([ll.lng, ll.lat]); let best = null;
    S.rings.forEach(r => { const np = turf.nearestPointOnLine(r.ln, pt, M); if (!best || np.properties.dist < best.d) best = { d: np.properties.dist, r, np }; });
    if (!best || best.d > 30 * mpp()) return null;
    const cs = best.r.ln.geometry.coordinates, i = Math.min(best.np.properties.index, cs.length - 2); return turf.bearing(cs[i], cs[i + 1]);
  }
  function tracePath(r, a, b) {
    try {
      const ln = r.ln, Lm = turf.length(ln, M), sl = (x, y) => (Math.min(Lm, y) - Math.max(0, x) < 0.01 ? [] : turf.lineSliceAlong(ln, Math.max(0, x), Math.min(Lm, y), M).geometry.coordinates);
      const direct = a <= b ? sl(a, b) : sl(b, a).reverse();
      if (!r.closed) return direct.slice(1, -1);
      const other = a <= b ? sl(0, a).reverse().concat(sl(b, Lm).reverse()) : sl(a, Lm).concat(sl(0, b));
      const len = c => c.length > 1 ? turf.length(turf.lineString(c), M) : 0;
      return (len(other) < len(direct) ? other : direct).slice(1, -1);
    } catch (e) { return []; }
  }
  // ---------------------------------------------------------------- sketch
  const pts = () => S.groups.flat();
  const last = () => { const p = pts(); return p[p.length - 1]; };
  function constrain(c) {                                                // apply the active constraint to a candidate point
    const lp = S && pts().length ? last() : null; if (!lp) return c;
    let br = S.lock != null ? S.lock : turf.bearing(lp, c);
    if (S.lock != null) {                                                 // keep the direction: project the cursor onto the ray
      const d = turf.distance(lp, c, M), diff = (turf.bearing(lp, c) - br) * Math.PI / 180; const along = Math.max(0.01, d * Math.cos(diff));
      c = turf.destination(lp, S.dist != null ? S.dist : along, br, M).geometry.coordinates;
    } else if (S.dist != null) c = turf.destination(lp, S.dist, br, M).geometry.coordinates;
    return c;
  }
  function start(o) {                                                    // o: { shape: 'line' | 'polygon', onDone(geom), onCancel?, title? }
    cancel(true);
    S = Object.assign({ groups: [], snaps: [], hover: null, lock: null, dist: null, lockName: '', trace: false, inter: null }, o); S.rings = collect(o.roads && !SNAP.roadAll);
    map.doubleClickZoom.disable(); map.getContainer().style.cursor = 'crosshair'; document.activeElement?.blur?.(); bar(); draw();
  }
  function cancel(silent) { if (!S) return; const c = S.onCancel; S = null; g.clearLayers(); hideMenu(); barEl.hidden = true; tipEl.hidden = true; map.doubleClickZoom.enable(); map.getContainer().style.cursor = ''; if (!silent && c) c(); }
  function click(ll) {
    if (!S) return;
    const s = S.lock == null && S.dist == null ? snapAt(ll) : null; let c = s ? s.c : [ll.lng, ll.lat]; c = constrain(c);
    const lastSnap = S.snaps[S.snaps.length - 1], grp = [];
    if (s && lastSnap && s.ri >= 0 && lastSnap.ri === s.ri && S.trace) grp.push(...tracePath(S.rings[s.ri], lastSnap.loc, s.loc));
    grp.push(c); S.groups.push(grp); S.snaps.push(s); S.lock = null; S.dist = null; S.lockName = ''; bar(); draw();
  }
  function finish() {
    if (!S) return; const p = pts();
    for (let i = p.length - 1; i > 0; i--) if (turf.distance(p[i], p[i - 1], M) < 0.05) p.splice(i, 1);
    if ((S.shape === 'polygon' && p.length < 3) || p.length < 2) { alert('Not enough vertices: keep clicking, or press Esc to cancel.'); return; }
    const geom = S.shape === 'polygon' ? { type: 'Polygon', coordinates: [[...p, p[0]]] } : { type: 'LineString', coordinates: p };
    const done = S.onDone; cancel(true); done(geom);
  }
  function undoVertex() { if (!S || !S.groups.length) return; S.groups.pop(); S.snaps.pop(); bar(); draw(); }
  function draw() {
    g.clearLayers(); if (!S) return; const p = pts().map(c => [c[1], c[0]]), h = S.hover; const all = h ? [...p, ...(h.tr || []).map(c => [c[1], c[0]]), [h.c[1], h.c[0]]] : p;
    if (all.length > 1) (S.shape === 'polygon' && all.length > 2 ? L.polygon(all, opt({ color: '#ff1744', weight: 2, dashArray: '6 4', fillOpacity: .1 })) : L.polyline(all, opt({ color: '#ff1744', weight: 2.5, dashArray: '6 4' }))).addTo(g);
    p.forEach(x => L.circleMarker(x, opt({ radius: 3.5, color: '#fff', weight: 1, fillColor: '#ff1744', fillOpacity: 1 })).addTo(g));
    if (h && h.snap) L.circleMarker([h.c[1], h.c[0]], opt({ radius: 7, color: { Endpoint: '#d50000', Vertex: '#ff9100', Intersection: '#aa00ff', Midpoint: '#2962ff', Edge: '#00b8d4' }[h.snap] || '#00e5ff', weight: 2.5, fill: false })).addTo(g);
    if (S.lock != null && pts().length) { const lp = last(); const far = turf.destination(lp, 2000, S.lock, M).geometry.coordinates; L.polyline([[lp[1], lp[0]], [far[1], far[0]]], opt({ color: '#7c4dff', weight: 1, dashArray: '2 6' })).addTo(g); }
  }
  // ---------------------------------------------------------------- the sketch bar and the cursor tip
  const barEl = L.DomUtil.create('div', 'skbar', map.getContainer()); barEl.hidden = true; L.DomEvent.disableClickPropagation(barEl);
  const tipEl = L.DomUtil.create('div', 'sktip', map.getContainer()); tipEl.hidden = true;
  function bar() {
    if (!S) { barEl.hidden = true; return; } const p = pts(); let t = `<b>${S.title || 'Sketch'}</b> &middot; ${p.length} vertices`;
    if (p.length > 1) t += ` &middot; ${(turf.length(turf.lineString(p), M) / FTM).toFixed(0)} ft (${turf.length(turf.lineString(p), M).toFixed(1)} m)`;
    if (S.shape === 'polygon' && p.length > 2) t += ` &middot; ${(turf.area(turf.polygon([[...p, p[0]]])) / 4046.86).toFixed(3)} ac`;
    barEl.innerHTML = `${t}${S.lockName ? ` &middot; <span class="lk">${S.lockName}</span>` : ''}
      <span class="sp"></span><label title="T"><input type="checkbox" id="skTr" ${S.trace ? 'checked' : ''}> Trace</label>
      <button class="ghost small" data-k="D" title="D: type a length">Distance</button><button class="ghost small" data-k="A" title="A: type a direction">Direction</button>
      <button class="ghost small" data-k="P" title="P: parallel to the edge under the cursor">Parallel</button><button class="ghost small" data-k="E" title="E: perpendicular to the edge under the cursor">Perpendicular</button>
      <button class="ghost small" data-k="R" title="R: at right angles to the last segment">Right angle</button>
      <button class="small" data-k="F2" title="F2 / Enter / double-click">Finish</button><button class="ghost small" data-k="Escape" title="Esc">Cancel</button>`;
    barEl.hidden = false; barEl.querySelector('#skTr').onchange = e => { S.trace = e.target.checked; };
    barEl.querySelectorAll('[data-k]').forEach(b => b.onclick = () => key(b.dataset.k, lastMouse));
  }
  let lastMouse = null;
  function tip(e, s, c) {
    if (!S) { tipEl.hidden = true; return; } const p = pts(); let t = s ? `<b>${s.type}</b>` : '';
    if (p.length) { const lp = last(); const d = turf.distance(lp, c, M); t += `${t ? '<br>' : ''}${(d / FTM).toFixed(0)} ft &middot; ${((turf.bearing(lp, c) + 360) % 360).toFixed(0)}&deg;`; }
    if (!t) { tipEl.hidden = true; return; }
    const pnt = map.latLngToContainerPoint(e.latlng); tipEl.style.left = (pnt.x + 16) + 'px'; tipEl.style.top = (pnt.y + 14) + 'px'; tipEl.innerHTML = t; tipEl.hidden = false;
  }
  // ---------------------------------------------------------------- constraints and keys
  function ask(label, unit, cb) {                                          // inline number entry on the sketch bar
    const f = L.DomUtil.create('div', 'skask', map.getContainer()); L.DomEvent.disableClickPropagation(f);
    f.innerHTML = `${label} <input type="number" step="any" style="width:90px"> ${unit} <button class="small">OK</button>`;
    const i = f.querySelector('input'); i.focus(); const ok = () => { const v = parseFloat(i.value); f.remove(); if (!isNaN(v)) cb(v); };
    f.querySelector('button').onclick = ok; i.onkeydown = e => { e.stopPropagation(); if (e.key === 'Enter') ok(); if (e.key === 'Escape') f.remove(); };
  }
  function key(k, ll) {
    if (!S) return;
    if (k === 'F2' || k === 'Enter') return finish();
    if (k === 'Escape') return cancel();
    if (k === 'Backspace' || k === 'Delete') return undoVertex();
    if (k === 't' || k === 'T') { S.trace = !S.trace; bar(); return; }
    if (!pts().length) return alert('Click the first vertex first.');
    const lp = last();
    if (k === 'd' || k === 'D') ask('Length', 'ft', v => { S.dist = v * FTM; S.lockName = `length ${v} ft`; bar(); });
    if (k === 'a' || k === 'A') ask('Direction (bearing from north)', '&deg;', v => { S.lock = v; S.lockName = `direction ${v}&deg;`; bar(); draw(); });
    if ((k === 'p' || k === 'P' || k === 'e' || k === 'E') && ll) { const b = edgeBearingAt(ll); if (b == null) return alert('Hover over an edge first, then press P or E.');
      const cur = turf.bearing(lp, [ll.lng, ll.lat]); let br = /e/i.test(k) ? b + 90 : b; if (Math.abs(((cur - br + 540) % 360) - 180) > 90) br += 180;
      S.lock = br; S.lockName = /e/i.test(k) ? 'perpendicular' : 'parallel'; bar(); draw(); }
    if (k === 'r' || k === 'R') { const p = pts(); if (p.length < 2) return alert('Right angle needs one segment first.');
      const b = turf.bearing(p[p.length - 2], lp), cur = ll ? turf.bearing(lp, [ll.lng, ll.lat]) : b + 90; let br = b + 90; if (Math.abs(((cur - br + 540) % 360) - 180) > 90) br -= 180;
      S.lock = br; S.lockName = 'right angle'; bar(); draw(); }
  }
  // ---------------------------------------------------------------- right-click menu while sketching
  const menuEl = L.DomUtil.create('div', 'ctxmenu', map.getContainer()); menuEl.hidden = true; L.DomEvent.disableClickPropagation(menuEl);
  function hideMenu() { menuEl.hidden = true; }
  function showMenu(e, items) {
    const p = map.latLngToContainerPoint(e.latlng); menuEl.style.left = p.x + 'px'; menuEl.style.top = p.y + 'px';
    menuEl.innerHTML = items.map((it, i) => it === '-' ? '<hr>' : `<div class="mi" data-i="${i}">${it[0]}<span>${it[1] || ''}</span></div>`).join(''); menuEl.hidden = false;
    menuEl.querySelectorAll('.mi').forEach(d => d.onclick = () => { hideMenu(); items[+d.dataset.i][2](); });
  }
  map.on('contextmenu', e => {
    if (S) { L.DomEvent.stop(e); const ll = e.latlng; showMenu(e, [['Finish', 'F2', () => finish()], ['Delete last vertex', 'Backspace', undoVertex], '-', ['Distance...', 'D', () => key('D', ll)], ['Direction...', 'A', () => key('A', ll)],
      ['Parallel', 'P', () => key('P', ll)], ['Perpendicular', 'E', () => key('E', ll)], ['Right angle', 'R', () => key('R', ll)], '-', [`Trace ${S.trace ? 'off' : 'on'}`, 'T', () => key('T')], ['Cancel sketch', 'Esc', () => cancel()]]); return; }
    if (window.ProMenu) { L.DomEvent.stop(e); window.ProMenu(e, showMenu); }
  });
  map.on('click', () => hideMenu());
  // ---------------------------------------------------------------- mouse and keyboard
  map.on('mousemove', e => {
    lastMouse = e.latlng; if (!S) return;
    const s = S.lock == null && S.dist == null ? snapAt(e.latlng) : null; let c = s ? s.c : [e.latlng.lng, e.latlng.lat]; c = constrain(c);
    const ls = S.snaps[S.snaps.length - 1], tr = s && ls && S.trace && s.ri >= 0 && ls.ri === s.ri ? tracePath(S.rings[s.ri], ls.loc, s.loc) : [];
    S.hover = { c, snap: s && s.type, tr }; draw(); tip(e, s, c);
  });
  map.on('click', e => { if (S && Date.now() - (window.LPBOX_T || 0) > 400) click(e.latlng); });
  map.on('dblclick', e => { if (S) { L.DomEvent.stop(e); finish(); } });
  document.addEventListener('keydown', e => {
    if (!S || e.target.matches('input, select, textarea')) return;
    if (['F2', 'Enter', 'Escape', 'Backspace', 'Delete'].includes(e.key) || /^[tdaperTDAPER]$/.test(e.key)) { e.preventDefault(); e.stopPropagation(); key(e.key, lastMouse); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); e.stopPropagation(); undoVertex(); }
  }, true);
  // ---------------------------------------------------------------- the Snapping pane
  function snapPane(anchor) {
    let p = document.getElementById('snapPane'); if (p) { p.remove(); return; }
    p = L.DomUtil.create('div', 'pane', map.getContainer()); p.id = 'snapPane'; L.DomEvent.disableClickPropagation(p);
    const row = (k, lab, col) => `<label><input type="checkbox" data-s="${k}" ${SNAP[k] ? 'checked' : ''}> <i style="border-color:${col}"></i>${lab}</label>`;
    p.innerHTML = `<div class="ph"><b>Snapping</b><button class="x">&times;</button></div><div class="pb">
      <label class="big"><input type="checkbox" data-s="on" ${SNAP.on ? 'checked' : ''}> Snapping on</label>
      ${row('end', 'Endpoint', '#d50000')}${row('inter', 'Intersection', '#aa00ff')}${row('vertex', 'Vertex', '#ff9100')}${row('mid', 'Midpoint', '#2962ff')}${row('edge', 'Edge', '#00b8d4')}
      <label title="Off: a road snaps only to roads, the site and streams, so plot corners do not pull it off its line"><input type="checkbox" data-s="roadAll" ${SNAP.roadAll ? 'checked' : ''}> Roads also snap to plots and outlines</label>
      <div class="row"><span class="mini">Tolerance</span><input type="number" id="snTol" value="${SNAP.tol}" min="3" max="40" style="width:60px"><span class="mini">pixels</span></div></div>`;
    p.querySelector('.x').onclick = () => p.remove();
    p.querySelectorAll('[data-s]').forEach(c => c.onchange = () => { SNAP[c.dataset.s] = c.checked; saveSnap(); if (S) { S.rings = collect(S.roads && !SNAP.roadAll); S.inter = null; } });
    p.querySelector('#snTol').onchange = e => { SNAP.tol = Math.max(3, +e.target.value || 12); saveSnap(); };
  }
  function snapPoint(ll) {                                              // snapping outside a sketch (moving vertices): same settings
    if (S) return snapAt(ll); const keep = S; S = { rings: collect(false), inter: null }; const r = snapAt(ll); S = keep; return r; }
  return { start, cancel, finish, click, snapPane, snapPoint, SNAP, get active() { return !!S; } };
})();

// ---- roads: an end that runs a little past the road it crosses (not a cross road) is trimmed at the crossing ----
function trimRoadOvershoot(coords, others, maxFt = 100) {
  const M = { units: 'meters' }; let ln = turf.lineString(coords); const limit = maxFt * 0.3048;
  const U = others.filter(o => o && o.geometry && o.geometry.coordinates.length > 1);
  if (!U.length) return coords;
  for (const atEnd of [true, false]) {
    const Lm = turf.length(ln, M); let best = null;
    for (const o of U) for (const h of turf.lineIntersect(ln, o).features) {
      const s = turf.nearestPointOnLine(ln, h, M).properties.location; const beyond = atEnd ? Lm - s : s;
      if (beyond > 0.5 && beyond < limit && (!best || beyond < best.beyond)) best = { s, beyond };
    }
    if (!best) continue;
    const end = turf.point(atEnd ? ln.geometry.coordinates.at(-1) : ln.geometry.coordinates[0]);
    if (U.some(o => turf.pointToLineDistance(end, o, M) < 1.5)) continue;        // the end reaches another road: a real link, keep it
    const piece = atEnd ? turf.lineSliceAlong(ln, 0, best.s, M) : turf.lineSliceAlong(ln, best.s, Lm, M);
    if (turf.length(piece, M) > 3) ln = piece;
  }
  return ln.geometry.coordinates;
}

// ---- edit session, ArcGIS Pro style: unsaved edits are asked about before a run, a project switch or closing the page ----
const EditSession = (() => {
  function dialog(title, text, buttons) {                                  // buttons: [[label, value, primary?]] -> Promise(value)
    return new Promise(res => {
      const d = document.createElement('div'); d.className = 'esdlg';
      d.innerHTML = `<div class="esbox"><b>${title}</b><p>${text}</p><div class="row right">${buttons.map(([l, v, pr], i) => `<button data-i="${i}" class="${pr ? '' : 'ghost'}">${l}</button>`).join('')}</div></div>`;
      document.body.appendChild(d); d.querySelectorAll('button').forEach(b => b.onclick = () => { d.remove(); res(buttons[+b.dataset.i][1]); });
    });
  }
  const dirty = () => !!window._dirty;
  const save = async () => { const r = await fetch(`/api/projects/${P.id}/edits/save`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); if (window.markSaved) markSaved(false); window._dirty = false; return r.ok; };
  const discard = async () => { await fetch(`/api/projects/${P.id}/edits/discard`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); window._dirty = false; };
  // a run on edited data: save first?
  const RUNS = /\/api\/projects\/[^/]+\/(run|redemarcate|design_roads|redesign)$/;
  const _fetch = window.fetch.bind(window);
  window.fetch = async (url, o = {}) => {
    if (typeof url === 'string' && (o.method || 'GET') === 'POST' && RUNS.test(url) && dirty() && typeof P !== 'undefined' && P) {
      const v = await dialog('Unsaved edits', 'This project has edits that are not saved. The run uses the project files as they are now.', [['Save and run', 'save', true], ['Run without saving', 'run'], ['Cancel', 'cancel']]);
      if (v === 'cancel') throw new Error('Run cancelled.');
      if (v === 'save') await save();
    }
    return _fetch(url, o);
  };
  // switching project with unsaved edits
  const sel = document.getElementById('projSel'); let cur = sel.value;
  sel.addEventListener('focus', () => { cur = sel.value; });
  const orig = sel.onchange;
  sel.onchange = async e => {
    if (dirty() && P && cur && cur !== sel.value) {
      const target = sel.value; sel.value = cur;
      const v = await dialog('Unsaved edits', `Save the edits to "${P.name}" before opening another project?`, [['Save', 'save', true], ['Discard', 'discard'], ['Cancel', 'cancel']]);
      if (v === 'cancel') return;
      if (v === 'save') await save(); else await discard();
      sel.value = target;
    }
    cur = sel.value; orig && orig(e);
  };
  window.addEventListener('beforeunload', e => { if (dirty()) { e.preventDefault(); e.returnValue = ''; } });
  return { dialog, save, discard };
})();
