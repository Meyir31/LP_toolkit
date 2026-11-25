// LP Toolkit: ArcGIS Pro style editing of every output layer (plots / land use, buildings, blocks, roads, walls, ...)
// Select, Create (sketch with snapping + Trace), Edit vertices, Reshape (with Trace), Split, Merge, Attributes, Delete, Undo.
const FE = (() => {
  const mm = { units: 'meters' };
  const SV = d => `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const IC = {
    fselect: SV('<path d="M5 3l12 8-5.5 1.2L9 18z" fill="currentColor" fill-opacity=".15"/><path d="M12 12.5l4 6"/>'),
    fcreate: SV('<path d="M4 18l5-12 6 4 5-6"/><circle cx="4" cy="18" r="1.5" fill="currentColor"/><path d="M16 19h6M19 16v6"/>'),
    fvertices: SV('<path d="M4 18L9 5l7 4 4 10z"/><rect x="2.5" y="16.5" width="3" height="3" fill="currentColor"/><rect x="7.5" y="3.5" width="3" height="3" fill="currentColor"/><rect x="14.5" y="7.5" width="3" height="3" fill="currentColor"/><rect x="18.5" y="17.5" width="3" height="3" fill="currentColor"/>'),
    freshape: SV('<path d="M3 19V9l6-5 6 5v10z"/><path d="M15 9c4 1 6 4 6 10h-6" stroke-dasharray="3 2"/>'),
    fsplit: SV('<path d="M4 6l8-3 8 3v12l-8 3-8-3z"/><path d="M3 21L21 3" stroke-dasharray="3 2"/>'),
    fmerge: SV('<rect x="3" y="5" width="8" height="14"/><rect x="13" y="5" width="8" height="14"/><path d="M9 12h6M13 10l2 2-2 2"/>'),
    fattr: SV('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11"/>'),
    fdelete: SV('<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>'),
    fundo: SV('<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-3"/>'),
  };
  if (typeof LPI !== 'undefined') Object.assign(IC, LPI);   // colourful icons
  const B = (t, label, tip) => `<button data-f="${t}" title="${tip}">${IC[t]}<span>${label}</span></button>`;
  const rib = document.querySelector('.ribbon');
  const grp = document.createElement('div'); grp.className = 'grp g-feat';
  grp.innerHTML = `<div class="gb"><div class="fl"><span class="mini">Layer</span><select id="feLayer" title="Layer to edit"></select></div>
    ${B('fselect', 'Select', 'Select features of the editing layer: click; Shift+click adds; Esc clears')}${B('fcreate', 'Create', 'Create (digitize) a feature, with snapping and Trace')}
    ${B('fvertices', 'Vertices', 'Edit vertices: drag, add (midpoints), delete (click a vertex)')}${B('freshape', 'Reshape', 'Reshape with a sketch line (Trace available)')}
    ${B('fsplit', 'Split', 'Split features with a sketch line')}${B('fmerge', 'Merge', 'Merge the selected features')}${B('fattr', 'Attributes', 'Edit the attributes of the selected features')}${B('fuse', 'Change use', 'Change the land use of the selected plots / parcels')}
    ${B('fdelete', 'Delete', 'Delete the selected features')}${B('fundo', 'Undo', 'Undo the last edit on this layer')}</div><span class="gl">Features (edit any output)</span>`;
  rib.insertBefore(grp, rib.querySelector('.rhide'));
  grp.querySelector('[data-f=fselect]').style.display = 'none';
  const sgrp = document.createElement('div'); sgrp.className = 'grp g-save';
  sgrp.innerHTML = `<div class="gb"><button data-a="save" title="Save edits (Ctrl+S): a save point of every editable layer">${IC.save}<span>Save</span></button><button data-a="discard" title="Discard edits: every editable layer back to the last save point">${IC.discard}<span>Discard</span></button><button data-a="snappane" title="Snapping: endpoint, vertex, edge, intersection, midpoint; tolerance">${IC.snap}<span>Snapping</span></button><button data-a="modpane" title="Modify Features: Move, Rotate, Scale, Copy / Paste, Continue, Planarize and every editing tool">${IC.edit}<span>Modify</span></button><button data-a="attrpane" title="Attributes pane: edit the selection in place">${IC.attr}<span>Attributes</span></button><button data-a="histpane" title="Edit history since the last save">${IC.undo}<span>History</span></button></div><span class="gl">Edits</span>`;
  rib.insertBefore(sgrp, grp); L.DomEvent.disableClickPropagation(sgrp);
  async function saveEdits() { if (!P) return; try { const r = await post(`/api/projects/${P.id}/edits/save`); alert(`Edits saved (${r.saved_at}).`); markSaved(false, r.saved_at); if (typeof EditLog !== 'undefined') EditLog.clear(); } catch (e) { alert(e.message); } }
  async function discardEdits() { if (!P) return;
    if (!confirm('Discard all edits made since the last save point? Every editable layer returns to how it was then.')) return;
    try { const r = await post(`/api/projects/${P.id}/edits/discard`); alert(`Edits discarded: back to the save point of ${r.saved_at}.`); markSaved(false, r.saved_at); close(); await openProject(P.id); } catch (e) { alert(e.message); } }
  function markSaved(dirty, at) { window._dirty = !!dirty; const b = sgrp.querySelector('[data-a=save]'); b.classList.toggle('dirty', !!dirty);
    b.title = (dirty ? 'Unsaved edits. ' : '') + 'Save edits (Ctrl+S)' + (at ? ` - last save point ${at}` : ''); }
  window.markSaved = markSaved;
  sgrp.querySelector('[data-a=snappane]').onclick = () => Sketch.snapPane();
  sgrp.querySelector('[data-a=modpane]').onclick = () => ModifyPane.toggle(); sgrp.querySelector('[data-a=attrpane]').onclick = () => AttrPane.toggle(); sgrp.querySelector('[data-a=histpane]').onclick = () => EditLog.pane();
  sgrp.querySelector('[data-a=save]').onclick = saveEdits; sgrp.querySelector('[data-a=discard]').onclick = discardEdits;
  document.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveEdits(); } });
  ['psplit', 'pmerge'].forEach(t => rib.querySelector(`[data-t=${t}]`)?.remove()); rib.querySelector('[data-a=pundo]')?.remove();
  L.DomEvent.disableClickPropagation(grp);
  const wid = L.DomUtil.create('div', 'widget', map.getContainer()); wid.hidden = true; L.DomEvent.disableClickPropagation(wid); L.DomEvent.disableScrollPropagation(wid);
  let drag = null;
  wid.addEventListener('mousedown', e => { if (!e.target.closest('.wh') || e.target.closest('button')) return; drag = { x: e.clientX - wid.offsetLeft, y: e.clientY - wid.offsetTop }; wid.dataset.moved = 1; e.preventDefault(); });
  document.addEventListener('mousemove', e => { if (drag) { wid.style.left = (e.clientX - drag.x) + 'px'; wid.style.top = (e.clientY - drag.y) + 'px'; } });
  document.addEventListener('mouseup', () => drag = null);
  let layers = [], act = null, tool = null, sel = new Map(), temp = null;
  const q = s => wid.querySelector(s);
  const INPUT = { 'roads.geojson': 'roads', 'existing.geojson': 'existing', 'stream.geojson': 'stream', 'site.geojson': 'site', 'zones.geojson': 'zones' };
  const inputKind = () => act && INPUT[act.path];
  // ------------------------------------------------------------------ layers
  async function refreshLayers() {
    if (!P) return; try { layers = await api(`/api/projects/${P.id}/edit/layers`); } catch (e) { layers = []; }
    const s = $('#feLayer'), prev = act?.path;
    s.innerHTML = layers.length ? layers.map(l => `<option value="${l.path}">${l.label}</option>`).join('') : '<option value="">(run the toolkit first)</option>';
    act = layers.find(l => l.path === prev) || layers[0] || null; if (act) s.value = act.path;
  }
  $('#feLayer').onchange = () => { clearSel(); act = layers.find(l => l.path === $('#feLayer').value) || null; showActive(); if (tool) open(tool); };
  $('#feLayer').onfocus = () => refreshLayers();
  async function showActive() { if (!act || inputKind()) return; const L_ = LAYER_INDEX.find(l => l.path === act.path); if (L_) { await toggleLayer(L_, true); results[L_.path]?.bringToFront?.(); } }
  function featLayers() { if (!act) return []; const k = inputKind(); if (k) return inputs[k].getLayers(); return results[act.path]?.getLayers?.() || []; }
  function fidOf(l) { const k = inputKind(); return k ? inputs[k].getLayers().indexOf(l) : l.feature?.properties?._fid; }
  function paint(l, on) { const k = inputKind(); if (on) { l.setStyle?.({ color: '#00e5ff', weight: k ? 6 : 3, opacity: 1 }); return; } if (k) styleInput(k, l); else results[act.path]?.resetStyle?.(l); }
  function clearSel() { for (const l of sel.values()) try { paint(l, false); } catch (e) {} sel.clear(); info(); }
  function toggleSel(l, add) { const id = fidOf(l); if (id === undefined || id < 0) return; if (!add) clearSel(); if (sel.has(id)) { paint(l, false); sel.delete(id); } else { sel.set(id, l); paint(l, true); } info(); }
  // ------------------------------------------------------------------ server operations
  async function op(name, extra = {}) {
    if (typeof EditLog !== 'undefined' && name !== 'undo') EditLog.add(`${name.replace('_', ' ')} (${sel.size || ''})`, act);
    const k = inputKind(); if (k) await post(`/api/projects/${P.id}/layer/${k}`, fcOf(k));
    const r = await post(`/api/projects/${P.id}/edit/op`, { path: act.path, op: name, fids: [...sel.keys()], ...extra });
    sel.clear(); await reload(); info(); if (k === 'site' || k === 'zones') { refreshInputState?.(); if (k === 'site' && !inputs.site.getLayers().length) alert('Site boundary deleted: draw or upload a new one (1. Site and inputs).'); } return r;
  }
  async function reload() {
    const k = inputKind(); if (k) { loadInput(k, await api(`/api/projects/${P.id}/input/${k}`)); return; }
    const L_ = LAYER_INDEX.find(l => l.path === act.path); if (!L_) return;
    if (results[L_.path]) { resGroup.removeLayer(results[L_.path]); delete results[L_.path]; } await toggleLayer(L_, true);
  }
  // ------------------------------------------------------------------ widgets
  const TITLE = { fselect: 'Select', fcreate: 'Create feature', fvertices: 'Edit vertices', freshape: 'Reshape', fsplit: 'Split', fmerge: 'Merge', fattr: 'Attributes', fdelete: 'Delete', fuse: 'Change use' };
  const traceBox = '';
  const keysHint = '<p class="hint">Click to add vertices (snapping and Trace as set); F2 / Enter / double-click finishes, Backspace removes the last vertex, Esc cancels; D length, A direction, P parallel, E perpendicular, R right angle; right-click for the menu.</p>';
  function fieldsForm(vals) {
    if (!act?.fields?.length) return '<p class="hint">This layer has no attributes.</p>';
    const uses = act.fields.some(f => ['ex_use', 'use'].includes(f.name)) ? `<datalist id="useList">${Object.keys(USE_COL).concat(Object.keys(DES_COL)).map(u => `<option value="${u}">`).join('')}</datalist>` : '';
    return '<div class="g2 af">' + act.fields.filter(f => f.name !== '_fid').map(f => {
      const v = vals ? vals[f.name] : ''; const ph = v === undefined ? '(varies)' : '';
      return `<span title="${f.name}">${f.name}</span><input data-k="${f.name}" type="${f.type === 'number' ? 'number' : 'text'}" ${f.readonly ? 'disabled' : ''} ${['ex_use', 'use'].includes(f.name) ? 'list="useList"' : ''} value="${v === undefined || v === null || v === 'None' || v === 'nan' ? '' : String(v).replace(/"/g, '&quot;')}" placeholder="${ph}">`;
    }).join('') + '</div>' + uses;
  }
  function formValues(onlyChanged) { const o = {}; wid.querySelectorAll('.af input[data-k]').forEach(i => { if (!i.disabled && (!onlyChanged || i.dataset.ch)) o[i.dataset.k] = i.value; }); return o; }
  function watchForm() { wid.querySelectorAll('.af input[data-k]').forEach(i => i.oninput = () => i.dataset.ch = 1); }
  function selValues() { const ls = [...sel.values()]; if (!ls.length) return null; const o = {};
    for (const f of act.fields) { const vs = [...new Set(ls.map(l => l.feature?.properties?.[f.name]))]; o[f.name] = vs.length === 1 ? vs[0] : undefined; } return o; }
  const W = {
    fselect: () => `<div class="fsel"></div><p class="hint">Click any feature (road, plot, building, block, wall, water...): the layer follows what you click. Shift+click adds; drag a box to select many on this layer (Space+drag pans). Then pick any tool: road tools, plot tools and feature tools all use this selection. <b>Boundaries:</b> click on the site boundary line or a redesign area outline to select it; the Delete key (or Delete) removes it.</p>`,
    fcreate: () => `<p class="hint">New feature on <b>${act.label}</b>.</p>${act.geom === 'any' ? '<div class="row"><span class="mini">Shape</span><select id="fshape"><option value="line">Line (stream, drain, river centreline)</option><option value="polygon">Area (river banks, pond, wetland, reserve)</option></select></div>' : `<p class="hint">Shape: <b>${act.geom}</b></p>`}${traceBox}${keysHint}<div class="sk"></div><div class="lbl2" style="margin-top:6px">Attributes of the new feature</div>${fieldsForm(defaults())}<div class="wf"><button id="fgo">Start sketch</button></div>`,
    fvertices: () => `<div class="fsel"></div><p class="hint">Select ONE feature, then Start. Drag vertices to move them, drag a midpoint to add a vertex, click a vertex to delete it.</p><div class="wf"><button id="fvs">Start</button><button id="fvok" hidden>Save</button><button class="ghost" id="fvx" hidden>Cancel</button></div>`,
    freshape: () => `<div class="fsel"></div><p class="hint">Select ONE feature, then sketch the new outline. Polygons: a line that goes out and comes back in adds area; a line across removes the smaller part. Lines: the sketch replaces the stretch between its two ends.</p>${traceBox}${keysHint}<div class="sk"></div><div class="wf"><button id="fgo">Start sketch</button></div>`,
    fsplit: () => `<div class="fsel"></div><p class="hint">Optional: select the feature(s) to split. Sketch a line across them (it must cross from edge to edge). Without a selection, every feature the line crosses is split.</p>${traceBox}${keysHint}<div class="sk"></div><div class="wf"><button id="fgo">Start sketch</button></div>`,
    fmerge: () => act && /block/i.test(act.label) ? `<div class="fsel"></div><p class="hint"><b>Remove block boundary:</b> select two or more blocks that touch (no road between them), then Remove boundary: they become one block. Then re-plot it: <b>Plot size</b> (new layout) or <b>Re-demarcate</b> (existing situation).</p><div class="wf"><button id="fmg">Remove boundary</button></div>`
      : `<div class="fsel"></div><p class="hint">Select two or more touching features, then Merge. The merged feature keeps the attributes of the largest one.</p><div class="wf"><button id="fmg">Merge</button></div>`,
    fattr: () => `<div class="fsel"></div>${sel.size ? fieldsForm(selValues()) + '<div class="wf"><button id="fap">Apply</button></div>' : '<p class="hint">Select one or more features to see and edit their attributes.</p>'}`,
    fuse: () => { const fld = useField(); if (!fld) return '<p class="hint">This layer has no land use. Choose <b>Plots / land use</b> in the Layer list.</p>';
      const list = fld === 'ex_use' ? Object.keys(EXIST_LUSPA).filter(u => !u.startsWith('Unconfirmed')) : Object.keys(DESIGN_LUSPA).filter(Boolean);
      return `<div class="fsel"></div><p class="hint">Select plots (click, Shift+click, or drag a box), then click the new use.</p>
        <input id="fuq" type="search" placeholder="Filter uses" style="width:100%;margin-bottom:4px"><div class="uses">${list.map(u => { const c = LUSPA[(fld === 'ex_use' ? EXIST_LUSPA : DESIGN_LUSPA)[u]] || LUSPA.VAC;
        return `<button class="ub" data-u="${u}"><i style="background:${c[1]};border-color:${c[3] || c[2] || '#555'}"></i>${fld === 'use' ? `<b>${u}</b> ${c[0]}` : u}</button>`; }).join('')}</div>`; },
    fdelete: () => `<div class="fsel"></div><div class="wf"><button id="fdl" class="danger2">Delete selected</button></div>`,
  };
  function defaults() { const o = {}; for (const f of act.fields || []) { if (f.name === 'width_ft') o[f.name] = width; else if (f.name === 'ex_use') o[f.name] = 'Residential'; else if (f.name === 'type' && act.geom === 'any') o[f.name] = 'stream'; else if (f.name === 'buffer_ft') o[f.name] = 100; else o[f.name] = ''; } return o; }
  function open(t) {
    if (!P) return alert('Create or choose a project first');
    if (!act) { refreshLayers().then(() => act ? open(t) : alert('There is nothing to edit yet: run the toolkit first.')); return; }
    if (typeof Editor !== 'undefined') Editor.close();
    if (t === 'fuse' && !useField()) { const pl = layers.find(x => (x.fields || []).some(f => ['ex_use', 'use'].includes(f.name))); if (pl) { clearSel(); act = pl; $('#feLayer').value = pl.path; } }
    endSketch(); endVertices(); tool = t; showActive();
    grp.querySelectorAll('button[data-f]').forEach(b => b.classList.toggle('on', b.dataset.f === t));
    wid.innerHTML = `<div class="wh"><span class="wt">${IC[t] || ''}<b>${TITLE[t]}</b> <span class="mini">&middot; ${act.label}</span></span><span><button class="x" data-close title="Close (Esc)">&times;</button></span></div><div class="wb">${W[t]()}</div>`;
    wid.hidden = false; if (!wid.dataset.moved) { wid.style.top = (rib.offsetTop + rib.offsetHeight + 8) + 'px'; wid.style.left = (rib.offsetLeft + 340) + 'px'; }
    wid.querySelector('[data-close]').onclick = close; wire(t); info();
  }
  function close() { endSketch(); endVertices(); tool = null; wid.hidden = true; grp.querySelectorAll('button[data-f]').forEach(b => b.classList.remove('on')); }
  function info() { if (window.onSel) setTimeout(window.onSel, 0); wid.querySelectorAll('.fsel').forEach(e => e.innerHTML = sel.size ? `<b>${sel.size}</b> feature(s) selected <button class="ghost small" data-cs>clear</button>` : '<span class="mini">Nothing selected</span>'); wid.querySelectorAll('[data-cs]').forEach(b => b.onclick = clearSel); if (tool === 'fattr' && !wid.hidden) { const body = wid.querySelector('.wb'); body.innerHTML = W.fattr(); wireAttr(); info0(); } }
  function info0() { wid.querySelectorAll('.fsel').forEach(e => e.innerHTML = sel.size ? `<b>${sel.size}</b> feature(s) selected <button class="ghost small" data-cs>clear</button>` : '<span class="mini">Nothing selected</span>'); wid.querySelectorAll('[data-cs]').forEach(b => b.onclick = clearSel); }
  function wireAttr() { watchForm(); const b = q('#fap'); if (b) b.onclick = async () => { try { await op('update_attrs', { properties: formValues(true) }); } catch (e) { alert(e.message); } }; }
  grp.querySelectorAll('button[data-f]').forEach(b => b.onclick = () => {
    if (b.dataset.f === 'fundo') { if (!act) return; op('undo').catch(e => alert(e.message)); return; }
    tool === b.dataset.f ? close() : open(b.dataset.f);
  });
  function wire(t) {
    if (t === 'fcreate') { watchForm(); q('#fgo').onclick = () => startSketch(act.geom === 'any' ? q('#fshape').value : act.geom === 'polygon' ? 'polygon' : 'line', async geom => { try { await op('add', { geometry: geom, properties: formValues(false) }); flash('Feature added. Start sketch to add another.'); } catch (e) { alert(e.message); } }); }
    if (t === 'freshape') q('#fgo').onclick = () => { if (sel.size !== 1) return alert('Select ONE feature to reshape.'); startSketch('line', async geom => { try { await op('reshape', { geometry: geom }); flash('Reshaped.'); } catch (e) { alert(e.message); } }); };
    if (t === 'fsplit') q('#fgo').onclick = () => startSketch('line', async geom => { try { const r = await op('split', { geometry: geom }); flash('Split done.'); } catch (e) { alert(e.message); } });
    if (t === 'fmerge') q('#fmg').onclick = async () => { try { await op('merge'); } catch (e) { alert(e.message); } };
    if (t === 'fdelete') q('#fdl').onclick = async () => { if (!sel.size) return alert('Select features first.'); if (!confirm(`Delete ${sel.size} feature(s)?`)) return; try { await op('delete'); } catch (e) { alert(e.message); } };
    if (t === 'fattr') wireAttr();
    if (t === 'fuse' && q('.uses')) { q('#fuq').oninput = e => wid.querySelectorAll('.ub').forEach(b => b.hidden = !b.dataset.u.toLowerCase().includes(e.target.value.toLowerCase()));
      wid.querySelectorAll('.ub').forEach(b => b.onclick = async () => { if (!sel.size) return alert('Select plots first.'); const n = sel.size, u = b.dataset.u;
        const props = useField() === 'ex_use' ? { ex_use: u, use_conf: 'confirmed (planner)' } : { use: u };
        try { await op('update_attrs', { properties: props }); flash(`${n} plot(s) set to ${u}`); if (typeof checkUnconfirmed === 'function') setTimeout(checkUnconfirmed, 800); } catch (e) { alert(e.message); } }); }
    if (t === 'fvertices') { q('#fvs').onclick = startVertices; q('#fvok').onclick = saveVertices; q('#fvx').onclick = () => { endVertices(); open('fvertices'); }; }
  }
  // ------------------------------------------------------------------ edit vertices (Leaflet.draw vertex editing on a working copy)
  async function startVertices() {
    if (sel.size !== 1) return alert('Select ONE feature first.');
    const [fid, l] = [...sel.entries()][0]; let gj;
    if (inputKind()) gj = l.toGeoJSON(); else { const fc = await api(`/api/projects/${P.id}/edit/feature?path=${encodeURIComponent(act.path)}&fid=${fid}`); gj = fc.features[0]; }
    let g = gj.geometry;
    if (g.type === 'MultiPolygon') { g = { type: 'Polygon', coordinates: g.coordinates.reduce((a, b) => turf.area(turf.polygon(b)) > turf.area(turf.polygon(a)) ? b : a) }; alert('Multi-part feature: the largest part is edited.'); }
    if (g.type === 'MultiLineString') g = { type: 'LineString', coordinates: g.coordinates.reduce((a, b) => b.length > a.length ? b : a) };
    const ll = g.type === 'Polygon' ? g.coordinates.map(r => r.slice(0, -1).map(c => [c[1], c[0]])) : g.coordinates.map(c => [c[1], c[0]]);
    temp = (g.type === 'Polygon' ? L.polygon(ll, { color: '#ff1744', weight: 2, fillOpacity: .1, renderer: L.svg() }) : L.polyline(ll, { color: '#ff1744', weight: 3, renderer: L.svg() })).addTo(map);
    temp.editing.enable(); temp._fid = fid; paint(l, false);
    const snapMarkers = () => (temp?.editing?._markers || []).forEach(m => { if (m._snapHooked) return; m._snapHooked = true;
      m.on('dragend', () => { const s_ = Sketch.snapPoint(m.getLatLng()); if (!s_) return;                        // a dropped vertex snaps (endpoint / vertex / edge / intersection / midpoint)
        const o = m._origLatLng || m.getLatLng(); o.lat = s_.c[1]; o.lng = s_.c[0]; m.setLatLng([s_.c[1], s_.c[0]]); temp.redraw(); try { temp.editing.updateMarkers(); } catch (er) {} snapMarkers(); }); });
    snapMarkers(); temp.on('edit', snapMarkers);
    q('#fvs').hidden = true; q('#fvok').hidden = false; q('#fvx').hidden = false;
  }
  async function saveVertices() { if (!temp) return; const geom = temp.toGeoJSON().geometry, fid = temp._fid; endVertices(); sel.clear(); sel.set(fid, null);
    try { await op('update_geom', { geometry: geom }); } catch (e) { alert(e.message); } if (tool) open(tool); }
  function endVertices() { if (temp) { try { temp.editing.disable(); } catch (e) {} map.removeLayer(temp); temp = null; } }
  // ------------------------------------------------------------------ sketching: the shared ArcGIS-style Sketch (pro.js)
  const ROADS_ = ['roads', 'existing'];
  function startSketch(kind, onDone) {
    const k = inputKind();
    Sketch.start({ shape: kind === 'polygon' ? 'polygon' : 'line', title: `${TITLE[tool] || 'Sketch'} &middot; ${act ? act.label : ''}`, roads: ROADS_.includes(k) && kind !== 'polygon',
      onCancel: () => { if (tool) open(tool); },
      onDone: geom => {
        if (geom.type === 'LineString' && ROADS_.includes(k)) {                   // a road that runs a little past a crossing road (not a cross road): trimmed there
          const others = roadLayers().map(lineOf); geom = { type: 'LineString', coordinates: trimRoadOvershoot(geom.coordinates, others) };
        }
        onDone(geom);
      } });
  }
  function endSketch() { if (Sketch.active) Sketch.cancel(true); }
  function polyHitOther(ll, terrain = false) {                         // an area of a click-through layer (blocks, plots before land use, terrain): the smallest one under the click
    const pt = turf.point([ll.lng, ll.lat]); let best = null, ba = Infinity;
    for (const x of layers) {
      const g = results[x.path]; if (!g || !resGroup.hasLayer(g)) continue;
      if (TERRAIN.has(kindOf(x.path)) !== terrain) continue;
      g.eachLayer(l => { const o = l.options || {}; if (o.interactive !== false && o.pane !== 'topLines') return;
        try { const gj = l.toGeoJSON(); if ((gj.geometry?.type || '').includes('Polygon') && turf.booleanPointInPolygon(pt, gj)) { const a = turf.area(gj); if (a < ba) { ba = a; best = { path: x.path, l }; } } } catch (er) {} });
    }
    return best;
  }
  map.on('click', e => {                                                // what Select picks (user 2026-11-23: every layer): outline > line / point > click-through area > editing layer > terrain
    if (Sketch.active || Date.now() - (window.LPBOX_T || 0) < 400) return;
    if (pickBoundary(e)) return;
    const pick = o => { if (o && switchTo(o.path)) { toggleSel(o.l, e.originalEvent.shiftKey); if (tool === 'fattr') info(); return true; } return false; };
    if (tool === 'fselect' && !temp && (pick(lineHitOther(e.latlng)) || pick(polyHitOther(e.latlng)))) return;
    if (tool && !temp && act && !inputKind() && (tool !== 'fselect' || !TERRAIN.has(kindOf(act.path)))) {          // the editing layer: picked by position
      const hit = hitTest(e.latlng); if (hit) { toggleSel(hit, e.originalEvent.shiftKey); if (tool === 'fattr') info(); return; } }
    if (tool === 'fselect' && !temp && (pick(lineHitOther(e.latlng, true)) || pick(polyHitOther(e.latlng, true)))) return;
  });
  document.addEventListener('keydown', e => {
    if (e.target.matches('input, select, textarea') || Sketch.active) return;
    if (e.key === 'Escape' && tool) { clearSel(); }
    if (e.key === 'Delete' && sel.size && !['roads', 'existing'].includes(inputKind())) deleteSelected();      // any layer (roads: the road editor's Delete)
  });
  // ------------------------------------------------------------------ clicks on features
  // Select picks from any editable layer: the layer of the clicked feature becomes the editing layer
  const INPUT_PATH = { roads: 'roads.geojson', existing: 'existing.geojson', stream: 'stream.geojson', site: 'site.geojson', zones: 'zones.geojson' };
  function boundaryAt(ll) {                                             // the site boundary / a redesign area whose outline is under the click (8 px)
    const pt = turf.point([ll.lng, ll.lat]), tol = 8 * 40075016.7 * Math.cos(ll.lat * Math.PI / 180) / Math.pow(2, map.getZoom() + 8);
    for (const k of ['zones', 'site']) {
      if (!layers.some(x => x.path === INPUT_PATH[k]) || !map.hasLayer(inputs[k])) continue; let hit = null;      // a switched-off layer is not picked
      inputs[k].eachLayer(l => { if (hit) return; try { const ln = turf.polygonToLine(l.toGeoJSON()); const ls = ln.type === 'FeatureCollection' ? ln.features : [ln];
        if (ls.some(x => turf.pointToLineDistance(pt, x, { units: 'meters' }) < tol)) hit = l; } catch (er) {} });
      if (hit) return { k, l: hit };
    }
    return null;
  }
  const pickBoundary = e => { if (tool !== 'fselect' || temp) return false; const b = boundaryAt(e.latlng); if (!b || !switchTo(INPUT_PATH[b.k])) return false; toggleSel(b.l, e.originalEvent.shiftKey); return true; };
  function switchTo(path, add) {
    const L2 = layers.find(x => x.path === path); if (!L2) return false;
    if (act && act.path === path) return true;
    clearSel(); act = L2; $('#feLayer').value = path; info(); return true;
  }
  function capture(L_, f, l, e) {
    if (Date.now() - (window.LPBOX_T || 0) < 400) return true;
    if (Sketch.active) { Sketch.click(e.latlng); return true; }
    if (!tool || temp || !act) return false;
    if (pickBoundary(e)) return true;                                  // the site boundary / a redesign area outline wins over what lies under it
    if (tool === 'fselect') { const o = lineHitOther(e.latlng); if (o && switchTo(o.path)) { toggleSel(o.l, e.originalEvent.shiftKey); return true; } }   // a line / point under the click wins over a polygon
    if (tool === 'fselect' && L_.path !== act.path && switchTo(L_.path)) { toggleSel(l, e.originalEvent.shiftKey); return true; }
    if (tool === 'fselect' && L_.path !== act.path && !layers.some(x => x.path === L_.path)) {        // a layer that is not editable (e.g. road reserves) is on top: the nearest drawn road under the click
      const pt = turf.point([e.latlng.lng, e.latlng.lat]), tol = 10 * 40075016.7 * Math.cos(e.latlng.lat * Math.PI / 180) / Math.pow(2, map.getZoom() + 8);
      let best = null, bd = tol, bk = null;
      for (const k of ['roads', 'existing']) inputs[k].eachLayer(r => { try { const d = turf.pointToLineDistance(pt, lineOf(r), { units: 'meters' }); if (d < bd) { bd = d; best = r; bk = k; } } catch (er) {} });
      if (best && switchTo(INPUT_PATH[bk])) { toggleSel(best, e.originalEvent.shiftKey); return true; }
    }
    if (L_.path !== act.path) {                                       // another layer is on top: find the editing layer's feature under the click
      const hit = hitTest(e.latlng); if (hit) { toggleSel(hit, e.originalEvent.shiftKey); if (tool === 'fattr') info(); } return true; }
    toggleSel(l, e.originalEvent.shiftKey); if (tool === 'fattr') info(); return true;
  }
  function captureInput(kind, l, e) {
    if (Date.now() - (window.LPBOX_T || 0) < 400) { L.DomEvent.stop(e); return true; }
    if (Sketch.active) { L.DomEvent.stop(e); Sketch.click(e.latlng); return true; }
    if (tool === 'fselect' && !temp && inputKind() !== kind && INPUT_PATH[kind] && switchTo(INPUT_PATH[kind])) { L.DomEvent.stop(e); toggleSel(l, e.originalEvent.shiftKey); return true; }
    if (!tool || temp || inputKind() !== kind) return false;
    L.DomEvent.stop(e); toggleSel(l, e.originalEvent.shiftKey); if (tool === 'fattr') info(); return true;
  }
  // ------------------------------------------------------------------ hit test on the editing layer (whatever is drawn above it)
  const TERRAIN = new Set(['contours', 'slope', 'steep', 'water']);
  const kindOf = path => (LAYER_INDEX.find(l => l.path === path) || {}).kind;
  function lineHitOther(ll, terrain = false) {                         // a line / point of any visible editable layer under the click (they are click-through, picked by position)
    const pt = turf.point([ll.lng, ll.lat]), tol = 8 * 40075016.7 * Math.cos(ll.lat * Math.PI / 180) / Math.pow(2, map.getZoom() + 8);
    let best = null, bd = tol;
    for (const x of layers) {
      const g = results[x.path]; if (!g || !resGroup.hasLayer(g)) continue;
      if (TERRAIN.has(kindOf(x.path)) !== terrain) continue;            // terrain layers (contours ...) only when nothing else is under the click
      g.eachLayer(l => { let gj; try { gj = l.toGeoJSON(); } catch (er) { return; } const t = gj.geometry?.type || ''; let d = Infinity;
        try { if (t.includes('LineString')) d = turf.pointToLineDistance(pt, t === 'LineString' ? gj : turf.lineString(gj.geometry.coordinates.flat()), { units: 'meters' });
              else if (t === 'Point') d = turf.distance(pt, gj, { units: 'meters' }); } catch (er) {}
        if (d < bd) { bd = d; best = { path: x.path, l }; } });
    }
    return best;
  }
  function actVisible() { if (!act) return false; const k = inputKind(); return k ? map.hasLayer(inputs[k]) : !!(results[act.path] && resGroup.hasLayer(results[act.path])); }
  function hitTest(ll) {
    if (!actVisible()) return null;                                     // a switched-off layer is never picked
    const pt = turf.point([ll.lng, ll.lat]), tol = 8 * 40075016.7 * Math.cos(ll.lat * Math.PI / 180) / Math.pow(2, map.getZoom() + 8);   // 8 px in metres
    let best = null, bestA = Infinity;
    for (const l of featLayers()) {
      let gj; try { gj = l.toGeoJSON(); } catch (er) { continue; } const t = gj.geometry?.type || '';
      if (t.includes('Polygon')) { if (turf.booleanPointInPolygon(pt, gj)) { const a = turf.area(gj); if (a < bestA) { bestA = a; best = l; } } }
      else if (t.includes('LineString')) { const d = turf.pointToLineDistance(pt, t === 'LineString' ? gj : turf.lineString(gj.geometry.coordinates.flat()), { units: 'meters' }); if (d < tol && d - 1e9 < bestA) { bestA = d - 1e9; best = l; } }
    }
    return best;
  }
  // ------------------------------------------------------------------ rectangle selection and land use
  const useField = () => (act?.fields || []).map(f => f.name).find(n => n === 'ex_use' || n === 'use');
  function boxSelect(b, add) {
    if (!add) clearSel(); const poly = turf.bboxPolygon([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]); let n = 0;
    for (const l of featLayers()) { try { if (turf.booleanIntersects(poly, l.toGeoJSON())) { const id = fidOf(l); if (id === undefined || id < 0) continue; sel.set(id, l); paint(l, true); n++; } } catch (er) {} }
    if (tool === 'fattr') open('fattr'); else info();
  }
  function flash(t) { const d = document.createElement('div'); d.className = 'flash'; d.textContent = t; wid.querySelector('.wb')?.prepend(d); setTimeout(() => d.remove(), 4000); }
  async function openUse(ls) {
    if (!layers.length) await refreshLayers();
    if (!useField()) { const pl = layers.find(x => (x.fields || []).some(f => ['ex_use', 'use'].includes(f.name))); if (!pl) return alert('There are no plots to change yet: run the toolkit first.'); act = pl; $('#feLayer').value = pl.path; }
    open('fuse'); for (const l of ls || []) { const id = l.feature?.properties?._fid; if (id !== undefined) { sel.set(id, l); paint(l, true); } } info();
  }
  // ---- helpers for the Modify / Attributes / History panes (pro.js) ----
  const toLL = g => g.type === 'Polygon' ? [g.coordinates[0].slice(0, -1).map(p => [p[1], p[0]])] : g.coordinates.map(p => [p[1], p[0]]);
  async function reselect(ids) { const k = inputKind(); const src = k ? inputs[k].getLayers() : (results[act.path]?.getLayers() || []);
    src.forEach((l, i) => { const id = k ? i : l.feature?.properties?._fid; if (ids.includes(id)) { sel.set(id, l); paint(l, true); } }); info(); }
  async function applyGeoms(items) {                                    // [{ l, geometry }] -> moved / rotated / scaled features
    const k = inputKind(); if (!items.length) return;
    if (typeof EditLog !== 'undefined') EditLog.add(`${items.length} feature(s) changed`, act);
    if (k) { if (k === 'roads' && typeof Editor !== 'undefined') Editor.push(); items.forEach(({ l, geometry }) => { l.setLatLngs(toLL(geometry)); if (k === 'roads') markMine(l); styleInput(k, l); }); saveInput(k); info(); return; }
    const ids = items.map(({ l }) => fidOf(l));
    await post(`/api/projects/${P.id}/edit/op`, { path: act.path, op: 'update_geoms', items: items.map(({ l, geometry }) => ({ fid: fidOf(l), geometry })) });
    sel.clear(); await reload(); await reselect(ids);
  }
  async function addFeatures(items) {                                  // [{ geometry, properties }] -> pasted copies
    const k = inputKind(); if (!items.length) return;
    if (typeof EditLog !== 'undefined') EditLog.add(`paste ${items.length} feature(s)`, act);
    if (k) { if (k === 'roads' && typeof Editor !== 'undefined') Editor.push(); items.forEach(it => L.geoJSON({ type: 'Feature', properties: { ...(it.properties || {}) }, geometry: it.geometry }, { onEachFeature: (ff, l) => { l.feature = ff; addInputLayer(k, l); } })); saveInput(k); return; }
    await post(`/api/projects/${P.id}/edit/op`, { path: act.path, op: 'add_many', items: items.map(it => ({ geometry: it.geometry, properties: Object.fromEntries(Object.entries(it.properties || {}).filter(([kk]) => !kk.startsWith('_'))) })) });
    await reload();
  }
  async function updateAttrs(props) { const ids = [...sel.keys()]; await op('update_attrs', { properties: props }); await reselect(ids); }
  function sketchFrom(start, onDone) { startSketch('line', onDone); setTimeout(() => Sketch.click(L.latLng(start[1], start[0])), 0); }
  function selection() { return act ? { path: act.path, kind: inputKind() || (LAYER_INDEX.find(l => l.path === act.path) || {}).kind, layers: [...sel.values()] } : null; }
  function clearAll() { clearSel(); }
  async function deleteSelected() {                                       // the one Delete for every layer (user 2026-11-23)
    if (!sel.size) { alert('Select features first (Select on the Edit tab).'); return false; }
    const nm = act?.label || act?.path || 'this layer';
    if (!confirm(`Delete ${sel.size} feature(s) from ${nm}?`)) return false;
    try { await op('delete'); if (typeof flash === 'function') flash(`${nm}: deleted`); return true; } catch (e) { alert(e.message); return false; }
  }
  return { deleteSelected, refreshLayers, capture, captureInput, close, boxSelect, openUse, selection, clearAll, open: t => open(t), applyGeoms, addFeatures, updateAttrs, sketchFrom,
    fields: () => (act?.fields || []).filter(f => f.name !== '_fid'), values: () => selValues(), layerLabel: () => act?.label || '', undoLayer: () => op('undo'), isInput: () => !!inputKind(), get canBox() { return !!tool && !Sketch.active && !temp && tool !== 'fcreate'; }, get active() { return !!tool || Sketch.active; } };
})();
