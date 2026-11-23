// LP Toolkit road editor: ArcGIS Pro style editing ribbon + tool widgets (select, create, offset, extend, trim, split, square ends, attributes, delete, undo / redo, snapping)
const Editor = (() => {
  const mm = { units: 'meters' };
  let tool = null, sel = new Set(), targets = new Set(), undo = [], redo = [], picking = 'select', sidePick = null, box = null, boxStart = null;
  const prev = L.layerGroup().addTo(map);
  const TEMPLATES = [['Local road 24 ft', 24], ['Local road 30 ft', 30], ['Collector 40 ft', 40], ['Main road 60 ft', 60], ['Arterial 80 ft', 80], ['Arterial 100 ft', 100], ['Arterial 120 ft', 120], ['Arterial 150 ft', 150], ['Regional road 200 ft (60 m)', 200], ['National road 300 ft (90 m)', 300]];
  const CLASS_OF = w => w >= 80 ? 'Arterial' : w >= 60 ? 'Main road' : w >= 40 ? 'Collector' : 'Local road';
  // ------------------------------------------------------------------ ribbon (icons, ArcGIS Pro style; collapsible)
  const SV = d => `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const IC = {
    select: SV('<path d="M5 3l12 8-5.5 1.2L9 18z" fill="currentColor" fill-opacity=".15"/><path d="M12 12.5l4 6"/>'),
    clear: SV('<rect x="3" y="3" width="18" height="18" rx="2" stroke-dasharray="3 2"/><path d="M9 9l6 6M15 9l-6 6"/>'),
    create: SV('<path d="M3 20l6-6 5 2 7-11"/><circle cx="3" cy="20" r="1.4" fill="currentColor"/><circle cx="21" cy="5" r="1.4" fill="currentColor"/><path d="M15 19h6M18 16v6"/>'),
    offset: SV('<path d="M3 8c5-4 13-4 18 0"/><path d="M3 16c5-4 13-4 18 0" stroke-dasharray="3 2"/><path d="M12 7.5v5M10 10.5l2 2 2-2"/>'),
    extend: SV('<path d="M3 12h10" /><path d="M13 12h5" stroke-dasharray="2 2"/><path d="M21 5v14"/><path d="M15 9l3 3-3 3"/>'),
    trim: SV('<circle cx="6" cy="7" r="2.5"/><circle cx="6" cy="17" r="2.5"/><path d="M8 8.5L20 17M8 15.5L20 7"/>'),
    split: SV('<path d="M3 12h7M14 12h7"/><path d="M12 5v14" stroke-dasharray="2 2"/><circle cx="10" cy="12" r="1.3" fill="currentColor"/><circle cx="14" cy="12" r="1.3" fill="currentColor"/>'),
    square: SV('<path d="M4 20V4"/><path d="M4 20h16"/><path d="M4 14h6v6"/>'),
    attr: SV('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11"/>'),
    delete: SV('<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>'),
    undo: SV('<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-3"/>'),
    redo: SV('<path d="M15 14l5-5-5-5"/><path d="M20 9H10a6 6 0 000 12h3"/>'),
    snap: SV('<path d="M6 3v8a6 6 0 0012 0V3"/><path d="M6 7h4M14 7h4"/><path d="M10 3v8a2 2 0 004 0V3"/>'),
    measure: SV('<path d="M3 17L17 3l4 4L7 21z"/><path d="M7 13l2 2M10 10l2 2M13 7l2 2"/>'),
    redemarcate: SV('<rect x="3" y="4" width="18" height="16" rx="1"/><path d="M3 12h18M9 4v8M15 12v8"/><path d="M19 2l2 2-2 2" />'),
    psplit: SV('<path d="M4 6l8-3 8 3v12l-8 3-8-3z"/><path d="M3 21L21 3" stroke-dasharray="3 2"/>'),
    pmerge: SV('<rect x="3" y="5" width="8" height="14"/><rect x="13" y="5" width="8" height="14"/><path d="M9 12h6M13 10l2 2-2 2"/>'),
    pmap: SV('<path d="M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/>'),
    hide: SV('<path d="M18 15l-6-6-6 6"/>'), edit: SV('<path d="M4 20h4l11-11-4-4L4 16z"/><path d="M13 7l4 4"/>'),
    min: SV('<path d="M5 12h14"/>'), max: SV('<rect x="5" y="5" width="14" height="14" rx="1"/>'),
  };
  if (typeof LPI !== 'undefined') Object.assign(IC, LPI);   // colourful icons
  const B = (attr, ic, label, tip) => `<button ${attr} title="${tip}">${IC[ic]}<span>${label}</span></button>`;
  const rib = L.DomUtil.create('div', 'ribbon', map.getContainer());
  rib.innerHTML = `
    <div class="grp"><div class="gb">${B('data-t="select"', 'select', 'Select', 'Select: click a road (existing roads too); Shift+click adds; drag a box to select many')}${B('data-a="clear"', 'clear', 'Clear', 'Clear the selection')}</div><span class="gl">Selection</span></div>
    <div class="grp"><div class="gb">${B('data-t="create"', 'create', 'Create', 'Create road (width templates)')}</div><span class="gl">Create</span></div>
    <div class="grp"><div class="gb">${B('data-t="offset"', 'offset', 'Offset', 'Offset: parallel copy / move of selected roads')}${B('data-t="extend"', 'extend', 'Extend', 'Extend a road end to the next road')}${B('data-t="trim"', 'trim', 'Trim', 'Trim a road back to the crossing roads')}${B('data-t="split"', 'split', 'Split', 'Split roads')}${B('data-t="square"', 'square', 'Square', 'Square ends: make roads meet at 90 degrees')}${B('data-t="attr"', 'attr', 'Attributes', 'Attributes: width, class, keep on redesign')}${B('data-t="delete"', 'delete', 'Delete', 'Delete selected roads')}</div><span class="gl">Modify</span></div>
    <div class="grp"><div class="gb">${B('data-a="undo"', 'undo', 'Undo', 'Undo (Ctrl+Z)')}${B('data-a="redo"', 'redo', 'Redo', 'Redo (Ctrl+Y)')}${B('data-t="snap"', 'snap', 'Snapping', 'Snapping on / off and tolerance')}</div><span class="gl">Edit</span></div>
    <div class="grp g-plots"><div class="gb">${B('data-t="pselect"', 'select', 'Select', 'Select plots: click; Shift+click adds; drag a box to select many')}${B('data-a="puse"', 'fuse', 'Change use', 'Change the land use of the selected plots')}${B('data-t="redemarcate"', 'redemarcate', 'Re-demarcate', 'Re-demarcate the selected blocks')}${B('data-t="psplit"', 'psplit', 'Split plot', 'Split plots with a line')}${B('data-t="pmerge"', 'pmerge', 'Merge', 'Merge selected plots')}${B('data-a="pundo"', 'undo', 'Undo', 'Undo the last plot edit')}${B('data-a="pmap"', 'pmap', 'Update map', 'Update the land use map and tables')}</div><span class="gl">Plots</span></div>
    <div class="grp"><div class="gb">${B('data-t="measure"', 'measure', 'Measure', 'Measure distance or area')}</div><span class="gl">Measure</span></div>
    <button class="rhide" data-a="hide" title="Hide the tools">${IC.hide}</button>`;
  rib.querySelectorAll('.grp').forEach((g, i) => { if (i > 0 && i < 4) g.classList.add('g-roads'); });      // the Selection group serves both workflows
  rib.querySelector('[data-t=pselect]').style.display = 'none';                                           // one Select for everything
  const ribTab = L.DomUtil.create('button', 'ribtab', map.getContainer()); ribTab.innerHTML = `${IC.edit}<span>Tools</span>`; ribTab.title = 'Show the tools'; ribTab.hidden = true;
  L.DomEvent.disableClickPropagation(ribTab);
  const setRib = on => { rib.classList.toggle('gone', !on); ribTab.hidden = on; try { localStorage.setItem('lp_rib', on ? '1' : '0'); } catch (e) {} };
  rib.querySelector('[data-a=hide]').onclick = () => setRib(false); ribTab.onclick = () => setRib(true);
  try { if (localStorage.getItem('lp_rib') === '0') setTimeout(() => setRib(false), 0); } catch (e) {}
  L.DomEvent.disableClickPropagation(rib); L.DomEvent.disableScrollPropagation(rib);
  const wid = L.DomUtil.create('div', 'widget', map.getContainer()); wid.hidden = true;
  L.DomEvent.disableClickPropagation(wid); L.DomEvent.disableScrollPropagation(wid);
  rib.querySelectorAll('button[data-t]').forEach(b => b.onclick = () => {
    if (b.dataset.t === 'snap') { Sketch.snapPane(); return; }
    if (['select', 'pselect'].includes(b.dataset.t)) { close(); rib.querySelectorAll('button[data-t]').forEach(x => x.classList.remove('on')); if (typeof FE !== 'undefined') FE.open('fselect'); b.classList.add('on'); return; }
    tool === b.dataset.t ? close() : open(b.dataset.t); });
  rib.querySelector('[data-a=clear]').onclick = () => { clearSel(); pSel.clear(); pBlocks.clear(); paintPlots(); if (typeof FE !== 'undefined') FE.clearAll(); refresh(); };
  // drag = rectangle select whenever a selecting tool is open (ArcGIS Pro style); Space+drag or the middle mouse button pans
  const BOXTOOLS = ['select', 'attr', 'delete', 'offset', 'square', 'split', 'pselect', 'psplit', 'pmerge', 'redemarcate'];
  let spaceDown = false;
  window.boxAuto = () => !spaceDown && (BOXTOOLS.includes(tool) || (typeof FE !== 'undefined' && FE.canBox));
  const syncCursor = () => map.getContainer().classList.toggle('boxmode', window.boxAuto());
  setInterval(syncCursor, 400);
  document.addEventListener('keydown', e => { if (e.code === 'Space' && !e.target.matches('input, select, textarea')) { if (!spaceDown) { spaceDown = true; syncCursor(); } e.preventDefault(); } }, true);
  document.addEventListener('keyup', e => { if (e.code === 'Space') { spaceDown = false; syncCursor(); if (!e.target.matches('input, select, textarea')) e.preventDefault(); } }, true);
  let mpan = null;                                     // middle-button pan, always available
  map.getContainer().addEventListener('mousedown', e => { if (e.button === 1) { mpan = { x: e.clientX, y: e.clientY }; e.preventDefault(); } });
  document.addEventListener('mousemove', e => { if (mpan) { map.panBy([mpan.x - e.clientX, mpan.y - e.clientY], { animate: false }); mpan = { x: e.clientX, y: e.clientY }; } });
  document.addEventListener('mouseup', e => { if (e.button === 1) mpan = null; });
  rib.querySelector('[data-a=puse]').onclick = () => { if (typeof FE === 'undefined') return; const fs = FE.selection(); const ls = fs && ['plots', 'plots_design'].includes(fs.kind) ? fs.layers : [...pSel.values()]; FE.openUse(ls); };
  rib.querySelector('[data-a=undo]').onclick = () => undo.length ? doUndo() : alert('Nothing to undo on the roads. (Other layers: Features > Undo, or the History pane.)');
  rib.querySelector('[data-a=redo]').onclick = () => redo.length ? doRedo() : alert('Nothing to redo on the roads.');
  let WF = 'design';
  function show(on) { mode(on ? 'design' : 'existing'); }
  function mode(wf) { WF = wf; close(); rib.querySelectorAll('.g-roads').forEach(g => g.style.display = wf === 'design' ? '' : 'none'); rib.querySelectorAll('.g-plots').forEach(g => g.style.display = wf === 'existing' ? '' : 'none'); }
  // drag the widget by its title bar
  let drag = null;
  wid.addEventListener('mousedown', e => { if (!e.target.closest('.wh') || e.target.closest('button')) return; drag = { x: e.clientX - wid.offsetLeft, y: e.clientY - wid.offsetTop }; wid.dataset.moved = 1; e.preventDefault(); });
  document.addEventListener('mousemove', e => { if (drag) { wid.style.left = (e.clientX - drag.x) + 'px'; wid.style.top = (e.clientY - drag.y) + 'px'; } });
  document.addEventListener('mouseup', () => drag = null);
  // ------------------------------------------------------------------ history
  function push() { if (!P) return; undo.push(JSON.stringify(fcOf('roads'))); if (undo.length > 60) undo.shift(); redo = []; }
  function restore(js) { clearSel(); loadInput('roads', JSON.parse(js)); saveInput('roads'); preview(); }
  function doUndo() { if (!undo.length) return; redo.push(JSON.stringify(fcOf('roads'))); restore(undo.pop()); }
  function doRedo() { if (!redo.length) return; undo.push(JSON.stringify(fcOf('roads'))); restore(redo.pop()); }
  map.on('draw:editstart draw:deletestart', push);
  // ------------------------------------------------------------------ selection
  const hi = l => l.setStyle?.({ color: '#00e5ff', weight: Math.max(5, (+(l.feature.properties.width_ft || 30)) / 7), opacity: 1 });
  const tgtStyle = l => l.setStyle?.({ color: '#ff1744', weight: 6, opacity: 1 });
  function restyle(l) { if (sel.has(l)) hi(l); else if (targets.has(l)) tgtStyle(l); else styleInput(inputs.existing.hasLayer(l) ? 'existing' : 'roads', l); }
  function clearSel() { const a = [...sel, ...targets]; sel.clear(); targets.clear(); a.forEach(restyle); refresh(); }
  function toggle(set, l, add) { if (!add) { const old = [...set]; set.clear(); old.forEach(restyle); } set.has(l) ? set.delete(l) : set.add(l); restyle(l); refresh(); }
  function alive(set) { for (const l of [...set]) if (!inputs.roads.hasLayer(l) && !inputs.existing.hasLayer(l)) set.delete(l); return [...set]; }
  // Ctrl+drag box selection
  let boxFE = false;
  const BOXROAD = ['select', 'attr', 'delete', 'offset'];
  map.on('mousedown', e => {
    if (e.originalEvent.button !== 0 || !(e.originalEvent.ctrlKey || window.boxAuto())) return;
    boxFE = typeof FE !== 'undefined' && FE.canBox;
    if (!boxFE && (!tool || ['create', 'snap', 'extend', 'trim', 'measure'].includes(tool) && picking !== 'targets')) return;
    e.originalEvent.preventDefault(); document.body.classList.add('noselect'); window.getSelection()?.removeAllRanges();
    map.dragging.disable(); boxStart = e.latlng; box = L.rectangle([e.latlng, e.latlng], { color: '#00e5ff', weight: 1, dashArray: '4 3', fillOpacity: .08, interactive: false }).addTo(map);
  });
  map.on('mousemove', e => { if (box) box.setBounds([boxStart, e.latlng]); });
  map.on('mouseup', e => {
    document.body.classList.remove('noselect');
    if (!box) return; const b = box.getBounds(); map.removeLayer(box); box = null; map.dragging.enable();
    const p1 = map.latLngToContainerPoint(boxStart), p2 = map.latLngToContainerPoint(e.latlng); if (p1.distanceTo(p2) < 5) return;   // a click, not a box
    window.LPBOX_T = Date.now(); const add = e.originalEvent.shiftKey;
    if (boxFE) { FE.boxSelect(b, add); return; }
    if (tool === 'redemarcate') { boxBlocks(b); return; }
    const poly = turf.bboxPolygon([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
    if (['pselect', 'psplit', 'pmerge'].includes(tool)) { if (!add) pSel.clear(); plotLayers().forEach(l => { try { if (turf.booleanIntersects(poly, l.toGeoJSON())) pSel.set(l.feature.properties.plot_id, l); } catch (er) {} }); paintPlots(); refresh(); return; }
    const set = picking === 'targets' ? targets : sel, edge = turf.polygonToLine(poly);
    roadLayers(picking === 'targets' || BOXROAD.includes(tool)).forEach(l => { const ln = lineOf(l);
      if (ln.geometry.coordinates.some(c => turf.booleanPointInPolygon(c, poly)) || turf.lineIntersect(ln, edge).features.length) { set.add(l); restyle(l); } });
    refresh();
  });
  // ------------------------------------------------------------------ geometry helpers
  const ftm = ft => ft * FT;
  function sideOf(line, pt) { const np = turf.nearestPointOnLine(line, pt, mm); const r = ((turf.bearing(np, pt) - bearingAt(line, np) + 540) % 360) - 180; return r > 0 ? 'right' : 'left'; }
  function offsetTo(line, d, side) {                           // offset distance d (m) to the named side, whichever sign turf needs
    const o = turf.lineOffset(line, d, mm), c = o.geometry.coordinates, mid = c[Math.floor(c.length / 2)];
    return sideOf(line, turf.point(mid)) === side ? o : turf.lineOffset(line, -d, mm);
  }
  function chaikin(c, it = 2) { for (let k = 0; k < it; k++) { if (c.length < 3) break; const o = [c[0]]; for (let i = 0; i < c.length - 1; i++) { const a = c[i], b = c[i + 1]; o.push([.75 * a[0] + .25 * b[0], .75 * a[1] + .25 * b[1]], [.25 * a[0] + .75 * b[0], .25 * a[1] + .75 * b[1]]); } o.push(c[c.length - 1]); c = o; } return c; }
  function targetLines(except, onlySel) { const src = onlySel && alive(targets).length ? alive(targets) : roadLayers(); const t = src.filter(l => l !== except).map(lineOf); if (!onlySel) { const s = siteLine(); if (s) t.push(s); } return t; }
  function extendEnd(c, atEnd, tl, maxM) {                      // run an end straight on to the first target line
    const end = atEnd ? c[c.length - 1] : c[0], pv = atEnd ? c[c.length - 2] : c[1];
    const ray = turf.lineString([end, turf.destination(end, maxM, turf.bearing(pv, end), mm).geometry.coordinates]); let best = null;
    for (const t of tl) for (const h of turf.lineIntersect(ray, t).features) { const d = turf.distance(end, h, mm); if (d > .3 && (!best || d < best.d)) best = { d, c: h.geometry.coordinates }; }
    if (!best) return false; if (atEnd) c.push(best.c); else c.unshift(best.c); return true;
  }
  function trimOvershoot(c, tl, maxM) {                         // cut a dangling end that runs past its last crossing by less than maxM
    let ln = turf.lineString(c), Lm = turf.length(ln, mm); const cuts = [];
    for (const t of tl) for (const h of turf.lineIntersect(ln, t).features) cuts.push(turf.nearestPointOnLine(ln, h, mm).properties.location);
    if (!cuts.length) return c; const a = Math.min(...cuts), b = Math.max(...cuts); let s = 0, e = Lm;
    if (a > .3 && a < maxM) s = a; if (Lm - b > .3 && Lm - b < maxM) e = b;
    return e - s > 1 ? turf.lineSliceAlong(ln, s, e, mm).geometry.coordinates : c;
  }
  function newRoad(coords, props) { const nl = L.polyline([]); nl.feature = { type: 'Feature', properties: props, geometry: null }; setLine(nl, coords); addInputLayer('roads', nl); return nl; }
  // ------------------------------------------------------------------ widgets
  const W = {
    select: () => `<p>Click roads to select (existing roads too). <b>Shift</b>+click adds. <b>Drag</b> a box to select many. To pan: hold <b>Space</b> and drag, or use the middle mouse button. <b>Esc</b> closes the tool.</p><div class="selinfo"></div>`,
    create: () => `<div class="lbl2">Template</div><div class="tmpl">${TEMPLATES.map(([n, w]) => `<label><input type="radio" name="tp" value="${w}" ${w == width ? 'checked' : ''}> ${n}</label>`).join('')}
      <label><input type="radio" name="tp" value="custom"> Custom <input id="ewc" type="number" min="6" value="${width}" style="width:60px"> ft</label></div>
      <label class="chk"><input type="checkbox" id="esq" checked> Start and end square to the road they join (90&deg;)</label>
      <p class="hint">Click on the map to add points; double-click to finish. Ends snap onto roads within the snapping tolerance.</p>
      <div class="wf"><button id="ego">Start drawing</button></div>`,
    offset: () => `<div class="selinfo"></div>
      <div class="g2"><span>Method</span><select id="om"><option value="copy">Copy</option><option value="move">Move</option></select>
      <span>Distance</span><span><input id="od" type="number" min="1" value="230" style="width:80px"> ft</span>
      <span>Count</span><input id="oc" type="number" min="1" max="20" value="1" style="width:60px">
      <span>Side</span><select id="os"><option value="pick">Pick on the map</option><option value="left">Left</option><option value="right">Right</option><option value="both">Both</option></select>
      <span>Corners</span><select id="oco"><option value="mitered">Mitered</option><option value="smooth">Smooth (rounded)</option></select>
      <span>New width</span><select id="ow"><option value="same">Same as the original</option>${TEMPLATES.map(([n, w]) => `<option value="${w}">${n}</option>`).join('')}</select></div>
      <label class="chk"><input type="checkbox" id="ofit" checked> Fit the new road ends to the roads they meet (extend / trim)</label>
      <p class="hint" id="ohint">Select the road(s) to offset, then set the side. 230 ft = a 200 ft block + a 30 ft road.</p>
      <div class="wf"><button id="oap">Apply</button><button class="ghost" id="oca">Cancel</button></div>`,
    extend: () => `<div class="g2"><span>Extend to</span><select id="xt"><option value="nearest">Nearest road or the site boundary</option><option value="sel">Selected target roads</option></select>
      <span>Max distance</span><span><input id="xm" type="number" min="1" value="1500" style="width:80px"> ft</span></div>
      <div id="xtgt" hidden><button class="ghost" id="xpick">Pick target roads</button> <span class="mini" id="xtn"></span></div>
      <p class="hint">Click near the END of a road to extend it.</p>`,
    trim: () => `<div class="g2"><span>Trim to</span><select id="tt"><option value="nearest">Nearest crossing roads</option><option value="sel">Selected cutting roads</option></select></div>
      <div id="ttgt" hidden><button class="ghost" id="tpick">Pick cutting roads</button> <span class="mini" id="ttn"></span></div>
      <p class="hint">Click the piece of road to remove.</p>
      <div class="sep"></div><div class="g2"><span>Overshoots</span><span>shorter than <input id="tov" type="number" min="1" value="60" style="width:60px"> ft</span></div>
      <div class="wf"><button class="ghost" id="tall">Trim overshoots on all roads</button></div>`,
    split: () => `<div class="g2"><span>Method</span><select id="sm"><option value="point">At the clicked point</option><option value="parts">Into equal parts</option><option value="dist">Every set distance</option><option value="x">At all crossings</option></select>
      <span id="spl">Parts</span><input id="sv" type="number" min="2" value="2" style="width:80px"></div>
      <div class="selinfo"></div><p class="hint" id="shint">Click a road where it should be split.</p>
      <div class="wf" id="sapw" hidden><button id="sap">Apply</button></div>`,
    square: () => `<div class="selinfo"></div><div class="g2"><span>Bend length</span><span><input id="ql" type="number" min="20" value="120" style="width:70px"> ft</span>
      <span>Fix angles below</span><span><input id="qa" type="number" min="1" max="89" value="85" style="width:60px"> &deg;</span></div>
      <p class="hint">Select roads (or Ctrl+drag a box over an area), then Apply: road ends that meet another road at a sharp angle are bent to arrive at 90&deg;.</p>
      <div class="wf"><button id="qap">Apply</button></div>`,
    attr: () => `<div class="selinfo"></div><div class="g2"><span>Width</span><span><select id="aw">${[20, 24, 30, 40, 50, 60, 80, 100, 120].map(w => `<option>${w}</option>`).join('')}<option value="c">custom</option></select> <input id="awc" type="number" min="6" style="width:60px" hidden> ft</span>
      <span>Class</span><span id="acls" class="mini"></span></div>
      <label class="chk"><input type="checkbox" id="alk"> Mine: keep on redesign</label>
      <div class="wf"><button id="aap">Apply</button></div>`,
    delete: () => `<div class="selinfo"></div><p class="hint">Select roads (click, Shift+click, Ctrl+drag), then Delete. The Delete key works too.</p><div class="wf"><button id="dap" class="danger2">Delete selected</button></div>`,
    measure: () => `<div class="seg2"><label><input type="radio" name="mm" value="dist" checked> Distance</label><label><input type="radio" name="mm" value="area"> Area</label></div>
      <div id="mres" class="mres"><span class="mini">Click on the map to start.</span></div><p class="hint">Click to add points, double-click to finish (the next click starts a new measurement).</p><div class="wf"><button class="ghost" id="mclr">Clear</button></div>`,
    pselect: () => `<div class="psel"></div><p class="hint">Click plots to select them; Shift+click adds; drag a box to select many (Space+drag pans). Then choose a plot tool.</p>`,
    redemarcate: () => `<div class="bsel"></div><div class="row"><input id="rnum" placeholder="or type block numbers: 12, 15-18" style="flex:1"><button class="ghost small" id="rnumok">Add</button><button class="ghost small" id="rclr">Clear</button></div><div class="g2"><span>Rows</span><select id="rr"><option value="auto">Automatic (halve if deep enough)</option><option value="2">Two rows (back to back)</option><option value="1">One row</option></select>
      <span>Min frontage</span><span><input id="rwmin" type="number" min="5" step="1" placeholder="auto" style="width:70px"> m</span>
      <span>Max frontage</span><span><input id="rwmax" type="number" min="6" step="1" placeholder="auto" style="width:70px"> m</span>
      <span>Rear line</span><select id="rsp"><option value="evidence">Follow the image (walls, gaps between buildings)</option><option value="middle">Exact middle of the block</option></select></div>
      <p class="hint">Click anywhere inside a block to add it (click again to remove); Ctrl+drag a box to take several. Block outlines and numbers are shown while this tool is open.</p>
      <div class="wf"><button id="rap">Re-demarcate</button></div>`,
    psplit: () => `<div class="psel"></div><p class="hint">Optional: select the plot(s) to split. Then draw a line across them (double-click to finish). Without a selection, every plot the line crosses is split.</p><div class="wf"><button id="psd">Draw split line</button></div>`,
    pmerge: () => `<div class="psel"></div><p class="hint">Select two or more touching plots in the same block, then Merge.</p><div class="wf"><button id="pmg">Merge</button></div>`,
    snap: () => `<label class="chk"><input type="checkbox" id="sn" ${snapOn ? 'checked' : ''}> Snapping on</label><div class="g2"><span>Tolerance</span><span><input id="st" type="number" min="1" value="${SNAP_M}" style="width:60px"> m</span></div>
      <p class="hint">New and edited road ends snap onto the nearest road within the tolerance.</p><div class="wf"><button class="ghost" id="sall">Snap all road ends now</button></div>`,
  };
  const TITLE = { measure: 'Measure', pselect: 'Select plots', redemarcate: 'Re-demarcate blocks', psplit: 'Split plot', pmerge: 'Merge plots', select: 'Select', create: 'Create road', offset: 'Offset', extend: 'Extend', trim: 'Trim', split: 'Split', square: 'Square ends', attr: 'Attributes', delete: 'Delete', snap: 'Snapping' };
  let nextTool = null;
  function open(t) {
    if (t === 'delete' && typeof FE !== 'undefined' && FE.deleteSelected) {       // Delete works on every layer: features other than roads go to the feature editor's delete
      const fs0 = FE.selection();
      if (fs0 && fs0.layers.length && !['roads', 'existing'].includes(fs0.kind)) { FE.deleteSelected(); return; }
    }
    nextTool = t; if (typeof FE !== 'undefined') FE.close();
    if (!P) return alert('Create or choose a project first');
    close(); tool = t; picking = 'select'; sidePick = null;
    const fs = typeof FE !== 'undefined' && FE.selection();                    // the one Select's selection carries into the road / plot tools
    if (fs && fs.layers.length && ['roads', 'existing'].includes(fs.kind) && !['redemarcate', 'measure'].includes(t)) { sel.clear(); fs.layers.forEach(l => { sel.add(l); restyle(l); }); }
    if (fs && fs.layers.length && fs.kind === 'plots' && t === 'redemarcate') fs.layers.forEach(l => { const b_ = l.feature?.properties?.block_id; if (b_ != null) pBlocks.add(b_); });
    rib.querySelectorAll('button[data-t]').forEach(b => b.classList.toggle('on', b.dataset.t === t));
    wid.innerHTML = `<div class="wh"><span class="wt">${IC[t === 'attr' ? 'attr' : t] || ''}<b>${TITLE[t]}</b></span><span><button class="x mn" title="Minimise / restore the panel">${IC.min}</button><button class="x" data-close title="Close (Esc)">&times;</button></span></div><div class="wb">${W[t]()}</div>`; wid.hidden = false;
    wid.classList.remove('mini'); wid.querySelector('[data-close]').onclick = close;
    wid.querySelector('.mn').onclick = () => { wid.classList.toggle('mini'); wid.querySelector('.mn').innerHTML = wid.classList.contains('mini') ? IC.max : IC.min; };
    if (!wid.dataset.moved) { wid.style.top = (rib.offsetTop + rib.offsetHeight + 8) + 'px'; wid.style.left = rib.offsetLeft + 'px'; }
    map.getContainer().style.cursor = t === 'create' || t === 'snap' ? '' : 'crosshair';
    wire(t); refresh();
  }
  function close() { prev.clearLayers(); mg.clearLayers(); hideBlocks(); mPts = []; mDone = false; map.doubleClickZoom.enable(); if (['pselect', 'redemarcate', 'psplit', 'pmerge'].includes(tool) && !['pselect', 'redemarcate', 'psplit', 'pmerge'].includes(nextTool)) clearPlots(); if (tool === 'create') stopDraw(); tool = null; wid.hidden = true; rib.querySelectorAll('button[data-t]').forEach(b => b.classList.remove('on')); map.getContainer().style.cursor = ''; }
  const q = s => wid.querySelector(s);
  let refresh = function () {
    const n = alive(sel).length; wid.querySelectorAll('.selinfo').forEach(e => e.innerHTML = n ? `<b>${n}</b> road(s) selected <button class="ghost small" data-cs>clear</button>` : '<span class="mini">No roads selected</span>');
    wid.querySelectorAll('[data-cs]').forEach(b => b.onclick = () => clearSel());
    if (tool === 'attr' && n) { const ws = [...new Set(alive(sel).map(l => +(l.feature.properties.width_ft || 30)))]; q('#acls').textContent = ws.map(w => `${CLASS_OF(w)} (${w} ft)`).join(', ');
      if (ws.length === 1 && [...q('#aw').options].some(o => o.value == ws[0])) q('#aw').value = ws[0]; q('#alk').checked = alive(sel).every(l => l.feature.properties.locked); }
    if (tool === 'offset') preview();
    const tn = alive(targets).length; if (q('#xtn')) q('#xtn').textContent = tn ? `${tn} target(s)` : ''; if (q('#ttn')) q('#ttn').textContent = tn ? `${tn} cutting road(s)` : '';
  };
  // ------------------------------------------------------------------ wiring of each widget
  function wire(t) {
    if (t === 'create') {
      const cur = () => { const r = wid.querySelector('input[name=tp]:checked'); return r.value === 'custom' ? +q('#ewc').value : +r.value; };
      q('#ego').onclick = () => { width = cur(); startDraw('roads', 'polyline'); q('#ego').textContent = 'Drawing... (F2 / double-click finishes each road, Esc stops)'; };
      wid.querySelectorAll('input[name=tp]').forEach(r => r.onchange = () => { width = cur(); if (activeDraw === 'roads') startDraw('roads', 'polyline'); });
    }
    if (t === 'offset') {
      ['#om', '#od', '#oc', '#os', '#oco', '#ow', '#ofit'].forEach(s => q(s).onchange = q(s).oninput = () => { if (s === '#os') sidePick = null; preview(); hintOffset(); });
      q('#oap').onclick = applyOffset; q('#oca').onclick = () => { clearSel(); close(); }; hintOffset();
    }
    if (t === 'extend') { q('#xt').onchange = () => { q('#xtgt').hidden = q('#xt').value !== 'sel'; }; q('#xpick').onclick = () => { picking = picking === 'targets' ? 'select' : 'targets'; q('#xpick').classList.toggle('on', picking === 'targets'); q('#xpick').textContent = picking === 'targets' ? 'Done picking targets' : 'Pick target roads'; }; }
    if (t === 'trim') { q('#tt').onchange = () => { q('#ttgt').hidden = q('#tt').value !== 'sel'; }; q('#tpick').onclick = () => { picking = picking === 'targets' ? 'select' : 'targets'; q('#tpick').classList.toggle('on', picking === 'targets'); q('#tpick').textContent = picking === 'targets' ? 'Done picking' : 'Pick cutting roads'; };
      q('#tall').onclick = () => { push(); const m = ftm(+q('#tov').value || 60); let n = 0; inputs.roads.eachLayer(l => { const c = lineOf(l).geometry.coordinates, nc = trimOvershoot(c, targetLines(l, false), m); if (nc !== c) { setLine(l, nc); n++; } }); saveInput('roads'); alert(`${n} road(s) trimmed.`); }; }
    if (t === 'split') { const upd = () => { const m = q('#sm').value; q('#spl').textContent = m === 'dist' ? 'Distance (ft)' : 'Parts'; q('#sv').style.visibility = ['parts', 'dist'].includes(m) ? '' : 'hidden'; q('#spl').style.visibility = q('#sv').style.visibility;
        q('#sapw').hidden = m === 'point'; q('#shint').textContent = m === 'point' ? 'Click a road where it should be split.' : 'Select roads, then Apply.'; if (m === 'dist') q('#sv').value = 490; else if (m === 'parts') q('#sv').value = 2; };
      q('#sm').onchange = upd; upd(); q('#sap').onclick = applySplit; }
    if (t === 'square') q('#qap').onclick = applySquare;
    if (t === 'attr') { q('#aw').onchange = () => q('#awc').hidden = q('#aw').value !== 'c'; q('#aap').onclick = () => { const ls = alive(sel); if (!ls.length) return alert('Select roads first.'); push();
        const w = q('#aw').value === 'c' ? +q('#awc').value : +q('#aw').value; ls.forEach(l => { l.feature.properties.width_ft = w; l.feature.properties.locked = q('#alk').checked; if (q('#alk').checked) l.feature.properties.kind = 'planner'; restyle(l); }); saveInput('roads'); saveInput('existing'); refresh(); }; }
    if (t === 'delete') q('#dap').onclick = deleteSel;
    if (t === 'measure') { map.doubleClickZoom.disable(); wid.querySelectorAll('input[name=mm]').forEach(r => r.onchange = () => { mPts = []; mDone = false; drawMeasure(); }); q('#mclr').onclick = () => { mPts = []; mDone = false; drawMeasure(); }; drawMeasure(); }
    if (t === 'redemarcate') { showBlocks(); q('#rnumok').onclick = () => { parseBlocks(q('#rnum').value).forEach(b => pBlocks.add(b)); q('#rnum').value = ''; paintBlocks(); refresh(); };
      q('#rnum').onkeydown = e => { if (e.key === 'Enter') q('#rnumok').click(); }; q('#rclr').onclick = () => { pBlocks.clear(); paintBlocks(); refresh(); }; }
    if (t === 'redemarcate') q('#rap').onclick = async () => {
      if (!pBlocks.size) return alert('Click a plot in each block to re-demarcate.');
      try { await post(`/api/projects/${P.id}/redemarcate`, { blocks: [...pBlocks], rows: q('#rr').value, wmin: +q('#rwmin').value || null, wmax: +q('#rwmax').value || null, split: q('#rsp').value });
        q('.hint').textContent = 'Re-demarcating... the plots reload when it is done (see 2. Run).'; refreshStatus(); } catch (e) { alert(e.message); } };
    if (t === 'psplit') q('#psd').onclick = () => { const d = new L.Draw.Polyline(map, { shapeOptions: { color: '#ff1744', weight: 3, dashArray: '6 4' } }); d.enable();
      map.once(L.Draw.Event.CREATED, async ev => { const ll = ev.layer.getLatLngs(); try { const r = await post(`/api/projects/${P.id}/plots/split`, { line: { type: 'LineString', coordinates: ll.map(p => [p.lng, p.lat]) }, plot_ids: [...pSel.keys()] });
        clearPlots(); await reloadPlots(); refresh(); } catch (e) { alert(e.message); } }); };
    if (t === 'pmerge') q('#pmg').onclick = async () => { try { await post(`/api/projects/${P.id}/plots/merge`, { plot_ids: [...pSel.keys()] }); clearPlots(); await reloadPlots(); refresh(); } catch (e) { alert(e.message); } };
    if (t === 'snap') { q('#sn').onchange = () => snapOn = q('#sn').checked; q('#st').onchange = () => SNAP_M = +q('#st').value || 12; q('#sall').onclick = () => { push(); let n = 0; inputs.roads.eachLayer(l => { if (snapEnds(l)) n++; }); saveInput('roads'); alert(`${n} road(s) snapped.`); }; }
  }
  function deleteSel() { const ls = alive(sel); if (!ls.length) { const fs0 = typeof FE !== 'undefined' && FE.selection(); if (fs0 && fs0.layers.length) return FE.deleteSelected(); return alert('Select the features to delete first (Select on the Edit tab).'); } push(); ls.forEach(l => { inputs.roads.removeLayer(l); inputs.existing.removeLayer(l); }); sel.clear(); saveInput('roads'); saveInput('existing'); refresh(); }
  // ------------------------------------------------------------------ offset
  function hintOffset() { if (!q('#ohint')) return; const s = q('#os').value; q('#ohint').textContent = !alive(sel).length ? 'Select the road(s) to offset (click, Shift+click, Ctrl+drag).' : s === 'pick' && !sidePick ? 'Now click on the map on the side where the new road should go.' : 'Check the dashed preview, then Apply.'; }
  function offsetResults() {
    const ls = alive(sel); if (!ls.length || !q('#od')) return [];
    const d = ftm(+q('#od').value || 230), n = Math.max(1, +q('#oc').value || 1), s = q('#os').value, out = [];
    if (s === 'pick' && !sidePick) return [];
    for (const l of ls) {
      const ln = lineOf(l), sides = s === 'both' ? ['left', 'right'] : s === 'pick' ? [sideOf(ln, sidePick)] : [s];
      for (const sd of sides) for (let k = 1; k <= (q('#om').value === 'move' ? 1 : n); k++) {
        let c = offsetTo(ln, d * k, sd).geometry.coordinates; if (q('#oco').value === 'smooth') c = chaikin(c, 2);
        if (q('#ofit').checked) { const tl = targetLines(l, false); extendEnd(c, true, tl, ftm(600)); extendEnd(c, false, tl, ftm(600)); c = trimOvershoot(c, tl, ftm(120)); }
        out.push({ src: l, c });
      }
    }
    return out;
  }
  function preview() { prev.clearLayers(); if (tool !== 'offset') return; for (const r of offsetResults()) L.polyline(r.c.map(x => [x[1], x[0]]), { color: '#ff4081', weight: 3, dashArray: '8 6', interactive: false }).addTo(prev); }
  function applyOffset() {
    const res = offsetResults(); if (!res.length) return alert(alive(sel).length ? 'Pick the side on the map first.' : 'Select the road(s) to offset first.');
    push(); const mv = q('#om').value === 'move', w = q('#ow').value;
    for (const r of res) { const props = { ...r.src.feature.properties, locked: true, kind: 'planner' }; if (w !== 'same') props.width_ft = +w;
      if (mv) { setLine(r.src, r.c); r.src.feature.properties = props; } else newRoad(r.c, props); }
    prev.clearLayers(); sidePick = null; saveInput('roads'); saveInput('existing'); clearSel(); hintOffset();
  }
  // ------------------------------------------------------------------ split
  function splitAt(l, locs) {
    const ln = lineOf(l), Lm = turf.length(ln, mm); locs = [...new Set(locs.filter(s => s > 1 && s < Lm - 1).map(s => +s.toFixed(2)))].sort((a, b) => a - b); if (!locs.length) return 0;
    const cuts = [0, ...locs, Lm], props = { ...l.feature.properties };
    setLine(l, turf.lineSliceAlong(ln, cuts[0], cuts[1], mm).geometry.coordinates);
    for (let i = 1; i < cuts.length - 1; i++) newRoad(turf.lineSliceAlong(ln, cuts[i], cuts[i + 1], mm).geometry.coordinates, { ...props });
    return locs.length;
  }
  function applySplit() {
    const ls = alive(sel); if (!ls.length) return alert('Select roads first.'); push(); const m = q('#sm').value, v = +q('#sv').value; let n = 0;
    for (const l of ls) { const ln = lineOf(l), Lm = turf.length(ln, mm); let locs = [];
      if (m === 'parts') for (let i = 1; i < Math.max(2, v); i++) locs.push(Lm * i / Math.max(2, v));
      if (m === 'dist') for (let s = ftm(v || 490); s < Lm; s += ftm(v || 490)) locs.push(s);
      if (m === 'x') for (const t of targetLines(l, false)) for (const h of turf.lineIntersect(ln, t).features) locs.push(turf.nearestPointOnLine(ln, h, mm).properties.location);
      n += splitAt(l, locs); }
    saveInput('roads'); clearSel(); alert(`${n} split point(s) added.`);
  }
  function planarize(ls) {                                             // ArcGIS Planarize: every given road (or all) split where it crosses another
    ls = (ls || []).filter(l => inputs.roads.hasLayer(l)); if (!ls.length) return alert('Planarize: select the roads to split where they cross (Select tool, Shift+click or drag a box).');
    push(); let n = 0;
    for (const l of ls) { const ln = lineOf(l); const locs = [];
      for (const t of targetLines(l, false)) for (const h of turf.lineIntersect(ln, t).features) locs.push(turf.nearestPointOnLine(ln, h, mm).properties.location);
      n += splitAt(l, locs); }
    saveInput('roads'); clearSel(); alert(`Planarize: ${n} split point(s) added.`);
  }
  // ------------------------------------------------------------------ square ends
  function applySquare() {
    const ls = alive(sel); if (!ls.length) return alert('Select roads first (Ctrl+drag a box to take a whole area).'); push();
    const bend = ftm(+q('#ql').value || 120), lim = +q('#qa').value || 85; let n = 0;
    for (const l of ls) {
      let c = lineOf(l).geometry.coordinates;
      for (const atEnd of [true, false]) {
        const ln = turf.lineString(c), Lm = turf.length(ln, mm); if (Lm < bend * 1.3) continue;
        const end = atEnd ? c[c.length - 1] : c[0]; let tgt = null;
        for (const t of targetLines(l, false)) { const np = turf.nearestPointOnLine(t, end, mm); if (np.properties.dist < 2 && (!tgt || np.properties.dist < tgt.np.properties.dist)) tgt = { t, np }; }
        if (!tgt) continue;
        const bRoad = bearingAt(tgt.t, tgt.np), bMe = turf.bearing(atEnd ? c[c.length - 2] : c[1], end); if (acute(bRoad, bMe) >= lim) continue;
        const A = turf.along(ln, atEnd ? Lm - bend : bend, mm).geometry.coordinates, T = turf.nearestPointOnLine(tgt.t, A, mm);
        const away = turf.bearing(T, A), perp = [bRoad + 90, bRoad - 90].reduce((a, b) => turn360(a, away) < turn360(b, away) ? a : b);
        const C = turf.destination(T, turf.distance(T, A, mm) * .55, perp, mm).geometry.coordinates, Tc = T.geometry.coordinates;
        const curve = []; for (let i = 0; i <= 12; i++) { const s = i / 12; curve.push([(1 - s) ** 2 * A[0] + 2 * (1 - s) * s * C[0] + s * s * Tc[0], (1 - s) ** 2 * A[1] + 2 * (1 - s) * s * C[1] + s * s * Tc[1]]); }
        const keep = atEnd ? turf.lineSliceAlong(ln, 0, Lm - bend, mm).geometry.coordinates : turf.lineSliceAlong(ln, bend, Lm, mm).geometry.coordinates;
        c = atEnd ? [...keep, ...curve.slice(1)] : [...curve.reverse(), ...keep.slice(1)]; n++;
      }
      setLine(l, c); l.feature.properties.locked = true;
    }
    saveInput('roads'); clearSel(); alert(`${n} road end(s) squared.`);
  }
  // ------------------------------------------------------------------ clicks on roads and on the map
  function onClick(kind, l, e) {
    if (Date.now() - (window.LPBOX_T || 0) < 400) { L.DomEvent.stop(e); return; }
    if (typeof FE !== 'undefined' && FE.captureInput(kind, l, e)) return;
    if (tool === 'measure') { L.DomEvent.stop(e); measureClick(e.latlng); return; }
    if (!tool || tool === 'create' || tool === 'snap') return;
    if (tool === 'offset' && q('#os')?.value === 'pick' && alive(sel).length && !sel.has(l)) {            // picking the offset side: the click is a location, whatever lies under it
      L.DomEvent.stop(e); sidePick = turf.point([e.latlng.lng, e.latlng.lat]); preview(); hintOffset(); return; }
    if (kind !== 'roads' && kind !== 'existing') return;                                                     // road tools act on roads only (not the site boundary, streams, zones)
    L.DomEvent.stop(e); const add = e.originalEvent.shiftKey;
    if (picking === 'targets') { toggle(targets, l, true); return; }
    if (kind !== 'roads' && !BOXROAD.includes(tool)) return;
    const pt = turf.point([e.latlng.lng, e.latlng.lat]);
    if (tool === 'extend') { push(); const c = lineOf(l).geometry.coordinates, atEnd = turf.distance(pt, c[c.length - 1], mm) < turf.distance(pt, c[0], mm);
      if (!extendEnd(c, atEnd, targetLines(l, q('#xt').value === 'sel'), ftm(+q('#xm').value || 1500))) { undo.pop(); return alert('Nothing to extend to within the maximum distance.'); }
      setLine(l, c); markMine(l); saveInput('roads'); return; }
    if (tool === 'trim') { const ln = lineOf(l), Lm = turf.length(ln, mm), loc = turf.nearestPointOnLine(ln, pt, mm).properties.location, cuts = [];
      for (const t of targetLines(l, q('#tt').value === 'sel')) for (const h of turf.lineIntersect(ln, t).features) { const s = turf.nearestPointOnLine(ln, h, mm).properties.location; if (s > .5 && s < Lm - .5) cuts.push(s); }
      if (!cuts.length) return alert('This road does not cross a cutting road: use Delete instead.'); push();
      const a = Math.max(0, ...cuts.filter(s => s <= loc)), b = Math.min(Lm, ...cuts.filter(s => s >= loc)), keep = [];
      if (a > 1) keep.push(turf.lineSliceAlong(ln, 0, a, mm)); if (Lm - b > 1) keep.push(turf.lineSliceAlong(ln, b, Lm, mm));
      if (!keep.length) inputs.roads.removeLayer(l); else { setLine(l, keep[0].geometry.coordinates); markMine(l); if (keep[1]) newRoad(keep[1].geometry.coordinates, { ...l.feature.properties }); }
      saveInput('roads'); return; }
    if (tool === 'split' && q('#sm').value === 'point') { push(); const ln = lineOf(l); if (!splitAt(l, [turf.nearestPointOnLine(ln, pt, mm).properties.location])) undo.pop(); saveInput('roads'); return; }
    toggle(sel, l, add); if (tool === 'offset') hintOffset();
  }
  map.on('click', e => { if (tool === 'measure') measureClick(e.latlng); if (tool === 'redemarcate') { const b = blockAt(e.latlng); if (b != null) toggleBlock(b); } });
  map.on('dblclick', e => { if (tool === 'measure') { mDone = true; drawMeasure(); } });
  map.on('mousemove', e => { if (tool === 'measure' && mPts.length && !mDone) drawMeasure(e.latlng); });
  map.on('click', e => { if (tool === 'offset' && q('#os')?.value === 'pick' && alive(sel).length) { sidePick = turf.point([e.latlng.lng, e.latlng.lat]); preview(); hintOffset(); } });
  document.addEventListener('keydown', e => {
    if (e.target.matches('input, select, textarea')) return;
    if (e.key === 'Escape') { if (box) { map.removeLayer(box); box = null; map.dragging.enable(); } close(); stopDraw(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); doUndo(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); doRedo(); }
    if (e.key === 'Delete' && alive(sel).length) deleteSel();
    if (e.key === 'Enter' && tool === 'offset') applyOffset();
  });
  // ------------------------------------------------------------------ after a road is drawn: square its ends to the roads it joins (Create option)
  const turn360 = (b1, b2) => Math.abs(((b1 - b2) % 360 + 540) % 360 - 180);   // true angle between two bearings (0-180), keeps the side
  function afterCreate(l) {
    if (!q('#esq')?.checked) return; const c = lineOf(l).geometry.coordinates; if (c.length < 2) return;
    for (const atEnd of [true, false]) {
      const end = atEnd ? c[c.length - 1] : c[0]; let tgt = null;
      for (const t of targetLines(l, false)) { const np = turf.nearestPointOnLine(t, end, mm); if (np.properties.dist < 1 && (!tgt || np.properties.dist < tgt.properties.dist)) tgt = Object.assign(np, { t }); }
      if (!tgt) continue; const i = atEnd ? c.length - 2 : 1, nb = c[i], len = turf.distance(end, nb, mm); if (len < 3) continue;
      const bRoad = bearingAt(tgt.t, tgt), away = turf.bearing(end, nb), perp = [bRoad + 90, bRoad - 90].reduce((a, b) => turn360(a, away) < turn360(b, away) ? a : b);
      if (turn360(perp, away) < 3) continue;                                               // already square
      const stub = Math.min(len * 0.4, 15), p = turf.destination(end, stub, perp, mm).geometry.coordinates;   // about 50 ft square to the road (kerb return), then on to the planner's next vertex
      if (len <= 12) c[i] = turf.destination(end, len, perp, mm).geometry.coordinates;   // a short first segment: just turn it
      else if (atEnd) c.splice(c.length - 1, 0, p); else c.splice(1, 0, p);
    }
    setLine(l, c);
  }
  // ------------------------------------------------------------------ measure
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
  // ------------------------------------------------------------------ blocks overlay for re-demarcation (click inside, box, numbers)
  let blocksFC = null, blocksFor = null; const bo = L.layerGroup();
  async function showBlocks() {
    const L_ = LAYER_INDEX.find(l => l.kind === 'blocks'); if (!L_) return;
    if (blocksFor !== P.id + L_.path) { blocksFC = await api(`/api/projects/${P.id}/geojson?f=${encodeURIComponent(L_.path)}`); blocksFor = P.id + L_.path; }
    bo.addTo(map); paintBlocks();
  }
  function hideBlocks() { bo.clearLayers(); map.removeLayer(bo); }
  function paintBlocks() {
    if (!blocksFC) return; bo.clearLayers();
    L.geoJSON(blocksFC, { interactive: false, style: f => pBlocks.has(f.properties.block_id) ? { color: '#00b8d4', weight: 3, fillColor: '#00e5ff', fillOpacity: .35 } : { color: '#ffffff', weight: 1.5, dashArray: '5 4', fill: false },
      onEachFeature: (f, l) => { const c = l.getBounds().getCenter(); if (map.getZoom() >= 16 || pBlocks.has(f.properties.block_id))
        L.marker(c, { interactive: false, icon: L.divIcon({ className: '', html: `<span class="blk${pBlocks.has(f.properties.block_id) ? ' on' : ''}">${f.properties.block_id}</span>`, iconSize: null }) }).addTo(bo); } }).addTo(bo);
  }
  map.on('zoomend', () => { if (tool === 'redemarcate') paintBlocks(); });
  function blockAt(ll) { if (!blocksFC) return null; const pt = turf.point([ll.lng, ll.lat]); const f = blocksFC.features.find(f => f.geometry && turf.booleanPointInPolygon(pt, f)); return f ? f.properties.block_id : null; }
  function boxBlocks(b) { if (!blocksFC) return; const bx = turf.bboxPolygon([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
    blocksFC.features.forEach(f => { if (f.geometry && !turf.booleanDisjoint(f, bx)) pBlocks.add(f.properties.block_id); }); paintBlocks(); paintPlots(); refresh(); }
  function toggleBlock(id) { pBlocks.has(id) ? pBlocks.delete(id) : pBlocks.add(id); paintBlocks(); paintPlots(); refresh(); }
  function parseBlocks(t) { const out = []; (t || '').split(/[,\s]+/).forEach(x => { const m = x.match(/^(\d+)(?:-(\d+))?$/); if (!m) return; const a = +m[1], b = +(m[2] || m[1]); for (let i = Math.min(a, b); i <= Math.max(a, b); i++) out.push(i); });
    const ids = new Set((blocksFC?.features || []).map(f => f.properties.block_id)); return out.filter(i => !ids.size || ids.has(i)); }
  // ------------------------------------------------------------------ plots (existing situation): select plots / blocks
  const pSel = new Map(), pBlocks = new Set();
  const PHI = { color: '#00e5ff', weight: 3 };
  function plotLayers() { const g = Object.values(results).find(x => x._kind === 'plots'); return g ? g.getLayers() : []; }
  function paintPlots() { const g = Object.values(results).find(x => x._kind === 'plots'); if (!g) return; g.eachLayer(l => { const p = l.feature.properties; if (pSel.has(p.plot_id) || pBlocks.has(p.block_id)) l.setStyle(PHI); else g.resetStyle(l); }); }
  function clearPlots() { pSel.clear(); pBlocks.clear(); paintPlots(); refresh(); }
  function captureResultClick(kind, f, l, e) {
    if (Date.now() - (window.LPBOX_T || 0) < 400) return true;
    if (tool && !['measure', 'pselect', 'redemarcate', 'psplit', 'pmerge', 'create'].includes(tool)) {   // a road tool: a result layer (e.g. road reserves) is on top -> the nearest road under the click
      const pt = turf.point([e.latlng.lng, e.latlng.lat]), tol = 10 * 40075016.7 * Math.cos(e.latlng.lat * Math.PI / 180) / Math.pow(2, map.getZoom() + 8);
      let best = null, bd = tol; for (const r of roadLayers(true)) { const d = turf.pointToLineDistance(pt, lineOf(r), { units: 'meters' }); if (d < bd) { bd = d; best = r; } }
      if (best) { onClick(inputs.existing.hasLayer(best) ? 'existing' : 'roads', best, e); return true; }
      if (tool === 'offset' && q('#os')?.value === 'pick' && alive(sel).length) { sidePick = pt; preview(); hintOffset(); return true; }
      return true;
    }
    if (tool === 'measure') { measureClick(e.latlng); return true; }
    if (kind !== 'plots' || !['pselect', 'redemarcate', 'psplit', 'pmerge'].includes(tool)) return false;
    const p = f.properties, add = e.originalEvent.shiftKey;
    if (tool === 'redemarcate') { toggleBlock(p.block_id); return true; }
    else { if (!add) pSel.clear(); pSel.has(p.plot_id) ? pSel.delete(p.plot_id) : pSel.set(p.plot_id, l); }
    paintPlots(); refresh(); return true;
  }
  const _refresh = refresh;
  refresh = function () { _refresh();
    wid.querySelectorAll('.psel').forEach(e => e.innerHTML = pSel.size ? `<b>${pSel.size}</b> plot(s) selected: ${[...pSel.keys()].slice(0, 6).join(', ')}${pSel.size > 6 ? '...' : ''}` : '<span class="mini">No plots selected</span>');
    wid.querySelectorAll('.bsel').forEach(e => { e.innerHTML = pBlocks.size ? `<span class="mini">${pBlocks.size} block(s):</span> ` + [...pBlocks].sort((a, b) => a - b).map(b => `<span class="chip">${b}<button data-rb="${b}" title="Remove">&times;</button></span>`).join('') : '<span class="mini">No blocks selected: click inside a block, Ctrl+drag a box, or type numbers</span>';
      e.querySelectorAll('[data-rb]').forEach(x => x.onclick = () => toggleBlock(+x.dataset.rb)); }); };
  rib.querySelector('[data-a=pundo]').onclick = async () => { try { await post(`/api/projects/${P.id}/plots/undo`); clearPlots(); await reloadPlots(); } catch (e) { alert(e.message); } };
  rib.querySelector('[data-a=pmap]').onclick = async () => { try { await post(`/api/projects/${P.id}/run`, { workflow: 'existing', only: 'map', buildings: P.buildings || 'fast', profile: P.profile || $('#profile')?.value || 'auto' }); alert('Updating the land use map and tables (about a minute).'); refreshStatus(); } catch (e) { alert(e.message); } };
  return { open, close, onClick, push, afterCreate, show, mode, clearSel, captureResultClick, planarize, undo: () => doUndo(), redo: () => doRedo(), get tool() { return tool; } };
})();
