// LP Toolkit: ArcGIS Pro style panes - Modify Features, Attributes (docked), Edit history, map right-click menu, Ctrl+C / Ctrl+V.

// ---- edit history (since the last save) ----
const EditLog = (() => {
  const items = [];
  function add(text, act) { items.unshift({ t: new Date().toTimeString().slice(0, 5), text, layer: act ? act.label : '' }); if (items.length > 60) items.pop(); render(); }
  function render() {
    const p = document.getElementById('histPane'); if (!p) return;
    p.querySelector('.pb').innerHTML = items.length ? `<ol class="hist">${items.map((it, i) => `<li class="${i ? '' : 'top'}"><span class="mini">${it.t}</span> ${it.text} <span class="mini">${it.layer}</span></li>`).join('')}</ol>
      <div class="row"><button class="small" id="hUndo">Undo last edit</button></div>` : '<p class="mini">No edits since the last save.</p>';
    const u = p.querySelector('#hUndo'); if (u) u.onclick = undoLast;
  }
  async function undoLast() {
    if (FE.isInput()) Editor.undo(); else { try { await FE.undoLayer(); } catch (e) { alert(e.message); return; } }
    items.shift(); render();
  }
  function pane() {
    let p = document.getElementById('histPane'); if (p) { p.remove(); return; }
    p = L.DomUtil.create('div', 'pane', map.getContainer()); p.id = 'histPane'; p.style.top = '330px'; L.DomEvent.disableClickPropagation(p);
    p.innerHTML = '<div class="ph"><b>Edit history</b><button class="x">&times;</button></div><div class="pb"></div>'; p.querySelector('.x').onclick = () => p.remove(); render();
  }
  const clear = () => { items.length = 0; render(); };
  return { add, pane, clear, undoLast };
})();

// ---- Attributes pane (docked, follows the selection) ----
const AttrPane = (() => {
  let el = null;
  const esc = v => String(v).replace(/"/g, '&quot;');
  function render() {
    if (!el) return; const s = FE.selection(), n = s ? s.layers.length : 0, b = el.querySelector('.pb');
    if (!n) { b.innerHTML = '<p class="mini">Select features (Select tool) to see and edit their attributes here.</p>'; return; }
    const vals = FE.values() || {}, fs = FE.fields();
    b.innerHTML = `<div class="mini">${n} feature(s) &middot; ${FE.layerLabel()}</div><table class="attr">${fs.map(f => { const v = vals[f.name];
        return `<tr><th title="${f.name}">${f.name}</th><td><input data-k="${f.name}" ${f.readonly ? 'disabled' : ''} value="${v === undefined || v === null || v === 'None' || v === 'nan' ? '' : esc(v)}" placeholder="${v === undefined ? '(varies)' : ''}"></td></tr>`; }).join('')}</table>
      <div class="row"><button class="small" id="apApply">Apply</button><span class="mini" id="apMsg"></span></div>`;
    b.querySelectorAll('input[data-k]').forEach(i => i.oninput = () => { i.dataset.ch = 1; });
    b.querySelector('#apApply').onclick = async () => {
      const props = {}; b.querySelectorAll('input[data-k]').forEach(i => { if (i.dataset.ch && !i.disabled) props[i.dataset.k] = i.value; });
      if (!Object.keys(props).length) return;
      try { await FE.updateAttrs(props); const m = el && el.querySelector('#apMsg'); if (m) m.textContent = 'Saved to the layer.'; } catch (e) { alert(e.message); }
    };
  }
  function toggle() {
    if (el) { el.remove(); el = null; window.onSel = null; return; }
    el = L.DomUtil.create('div', 'pane dock', map.getContainer()); L.DomEvent.disableClickPropagation(el); L.DomEvent.disableScrollPropagation(el);
    el.innerHTML = '<div class="ph"><b>Attributes</b><button class="x">&times;</button></div><div class="pb"></div>'; el.querySelector('.x').onclick = toggle; window.onSel = render; render();
  }
  return { toggle, render, get open() { return !!el; } };
})();

// ---- Modify Features pane ----
const ModifyPane = (() => {
  let el = null, clip = [], lastMouse = null;
  const FTM = 0.3048, M = { units: 'meters' };
  map.on('mousemove', e => { lastMouse = e.latlng; });
  const sel = () => { const s = FE.selection(); return s && s.layers.length ? s : null; };
  const need = () => { const s = sel(); if (!s) alert('Select features first (Select tool).'); return s; };
  const centre = s => turf.center(turf.featureCollection(s.layers.map(l => l.toGeoJSON()))).geometry.coordinates;
  async function move(dxFt, dyFt) {
    const s = need(); if (!s) return;
    await FE.applyGeoms(s.layers.map(l => { let f = l.toGeoJSON();
      if (dxFt) f = turf.transformTranslate(f, Math.abs(dxFt) * FTM, dxFt > 0 ? 90 : 270, M);
      if (dyFt) f = turf.transformTranslate(f, Math.abs(dyFt) * FTM, dyFt > 0 ? 0 : 180, M);
      return { l, geometry: f.geometry }; }));
  }
  function moveByPoints() {
    const s = need(); if (!s) return;
    Sketch.start({ shape: 'line', title: 'Move: click the base point, then the destination (F2)', onDone: async geom => {
      const a = geom.coordinates[0], b = geom.coordinates[geom.coordinates.length - 1];
      await FE.applyGeoms(s.layers.map(l => ({ l, geometry: turf.transformTranslate(l.toGeoJSON(), turf.distance(a, b, M), turf.bearing(a, b), M).geometry }))); } });
  }
  async function rotate(deg) { const s = need(); if (!s) return; const c = centre(s); await FE.applyGeoms(s.layers.map(l => ({ l, geometry: turf.transformRotate(l.toGeoJSON(), -deg, { pivot: c }).geometry }))); }
  async function scale(f) { const s = need(); if (!s) return; const c = centre(s); await FE.applyGeoms(s.layers.map(l => ({ l, geometry: turf.transformScale(l.toGeoJSON(), f, { origin: c }).geometry }))); }
  function copy() { const s = need(); if (!s) return; clip = s.layers.map(l => ({ geometry: l.toGeoJSON().geometry, properties: Object.assign({}, l.feature && l.feature.properties) })); alert(`${clip.length} feature(s) copied. Ctrl+V pastes them into the editing layer.`); }
  async function paste() { if (!clip.length) return alert('Nothing copied yet (Ctrl+C).'); await FE.addFeatures(clip); alert(`${clip.length} feature(s) pasted in place: use Move to place them.`); }
  function cont() {
    const s = need(); if (!s) return; if (s.layers.length !== 1) return alert('Select ONE line to continue.');
    const l = s.layers[0], g = l.toGeoJSON().geometry; if (g.type !== 'LineString') return alert('Continue works on lines.');
    const c = g.coordinates, m = lastMouse ? [lastMouse.lng, lastMouse.lat] : c[c.length - 1];
    const atStart = turf.distance(m, c[0], M) < turf.distance(m, c[c.length - 1], M), from = atStart ? c[0] : c[c.length - 1];
    FE.sketchFrom(from, async geom => { const add = geom.coordinates.slice(1); const nc = atStart ? [...add.reverse(), ...c] : [...c, ...add]; await FE.applyGeoms([{ l, geometry: { type: 'LineString', coordinates: nc } }]); });
  }
  function askNum(label, unit, cb, def) { const v = prompt(`${label} (${unit})`, def === undefined ? '' : def); if (v === null) return; const n = parseFloat(v); if (!isNaN(n)) cb(n); }
  function run(k) {
    if (k === 'move') return moveByPoints();
    if (k === 'movexy') return askNum('Move east (+) / west (-)', 'ft', dx => askNum('Move north (+) / south (-)', 'ft', dy => move(dx, dy), '0'), '0');
    if (k === 'rotate') return askNum('Rotate anticlockwise', 'degrees', rotate, '90');
    if (k === 'scale') return askNum('Scale factor', 'for example 1.1', scale, '1.1');
    if (k === 'copy') return copy(); if (k === 'paste') return paste(); if (k === 'continue') return cont();
    if (k === 'planarize') { const s = FE.selection(); return Editor.planarize(s && s.kind === 'roads' ? s.layers : []); }
    if (k === 'attrs') return AttrPane.toggle();
    if (['extend', 'trim', 'offset'].includes(k)) { const b = document.querySelector(`.ribbon [data-t=${k}]`); if (b && b.offsetParent) return b.click(); return alert('This road tool is in the New layout workflow.'); }
    FE.open(k);
  }
  function toggle() {
    if (el) { el.remove(); el = null; return; }
    el = L.DomUtil.create('div', 'pane modpane', map.getContainer()); L.DomEvent.disableClickPropagation(el); L.DomEvent.disableScrollPropagation(el);
    const T = (k, label, tip) => `<button class="mt" data-m="${k}" title="${tip}">${label}</button>`;
    el.innerHTML = `<div class="ph"><b>Modify Features</b><button class="x">&times;</button></div><div class="pb">
      <input id="mfq" type="search" placeholder="Find a tool" style="width:100%;margin-bottom:6px">
      <div class="mg">Alignment</div>${T('move', 'Move', 'Click a base point, then the destination (snapping on)')}${T('movexy', 'Move by distance', 'Move by a typed offset in feet')}${T('rotate', 'Rotate', 'Rotate about the centre of the selection')}${T('scale', 'Scale', 'Scale about the centre of the selection')}
      <div class="mg">Copy</div>${T('copy', 'Copy (Ctrl+C)', 'Copy the selected features')}${T('paste', 'Paste (Ctrl+V)', 'Paste into the editing layer, in place')}
      <div class="mg">Reshape</div>${T('fvertices', 'Edit vertices', 'Drag, add and delete vertices')}${T('freshape', 'Reshape', 'Reshape with a sketch line')}${T('continue', 'Continue feature', 'Extend the selected line from its nearer end')}${T('extend', 'Extend (roads)', 'Extend road ends to the next road')}${T('trim', 'Trim (roads)', 'Trim roads back to crossing roads')}
      <div class="mg">Divide</div>${T('fsplit', 'Split', 'Split features with a sketch line')}${T('planarize', 'Planarize (roads)', 'Split roads where they cross')}
      <div class="mg">Combine</div>${T('fmerge', 'Merge', 'Merge the selected touching features')}
      <div class="mg">Construct</div>${T('fcreate', 'Create', 'Create features with the sketch tools')}${T('offset', 'Offset (roads)', 'Parallel copy / move of roads')}
      <div class="mg">Attributes</div>${T('attrs', 'Attributes pane', 'Edit the attributes of the selection')}${T('fdelete', 'Delete', 'Delete the selected features')}</div>`;
    el.querySelector('.x').onclick = toggle;
    el.querySelector('#mfq').oninput = e => el.querySelectorAll('.mt').forEach(b => { b.hidden = !b.textContent.toLowerCase().includes(e.target.value.toLowerCase()); });
    el.querySelectorAll('.mt').forEach(b => { b.onclick = () => run(b.dataset.m); });
  }
  document.addEventListener('keydown', e => {
    if (e.target.matches('input, select, textarea') || Sketch.active) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c' && sel()) { e.preventDefault(); copy(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') { e.preventDefault(); paste(); }
  });
  return { toggle, run, copy, paste, move, rotate, scale };
})();

// ---- right-click menu on the map (when not sketching) ----
window.ProMenu = (e, show) => {
  const s = FE.selection(), n = s ? s.layers.length : 0;
  show(e, [['Select', '', () => document.querySelector('.ribbon [data-t=select]').click()], ['Attributes pane', '', AttrPane.toggle], ['Modify Features', '', ModifyPane.toggle], '-',
    ['Copy', 'Ctrl+C', ModifyPane.copy], ['Paste', 'Ctrl+V', ModifyPane.paste], ['Delete selected', 'Del', () => { if (n) FE.open('fdelete'); else alert('Nothing selected.'); }],
    ['Zoom to selection', '', () => { if (n) map.fitBounds(L.featureGroup(s.layers).getBounds(), { maxZoom: 20, padding: [60, 60] }); }],
    ['Clear selection', 'Esc', () => document.querySelector('.ribbon [data-a=clear]').click()], '-',
    ['Undo', 'Ctrl+Z', EditLog.undoLast], ['Edit history', '', EditLog.pane], ['Save edits', 'Ctrl+S', () => document.querySelector('.ribbon [data-a=save]').click()], ['Snapping', '', () => Sketch.snapPane()]]);
};
