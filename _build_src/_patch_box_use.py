"""Box (rectangle) select for roads, plots and any Features layer; existing roads selectable; Change use tool."""
import os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'webapp', 'static'))
def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)

# ---------------- icons ----------------
patch('icons.js', [("    edit: S(", """    box: S(`<rect x="2.5" y="3.5" width="15" height="12" fill="#E3F2FD" stroke="${BL}" stroke-width="1.6" stroke-dasharray="3 2"/><path d="M12 10l9 6-4 1-2 4z" fill="${BL}" stroke="${BD}"/>`),
    fuse: S(`<rect x="3" y="3" width="8" height="8" fill="#DC7C24"/><rect x="13" y="3" width="8" height="8" fill="#73B2FF"/><rect x="3" y="13" width="8" height="8" fill="#FFFF00" stroke="#C00000"/><rect x="13" y="13" width="8" height="8" fill="#00FF00"/>`),
    edit: S(""")])

# ---------------- editor.js: Box mode, existing roads, plots box, Change use ----------------
patch('editor.js', [
 # buttons
 ("${B('data-a=\"clear\"', 'clear', 'Clear', 'Clear the selection')}",
  "${B('data-a=\"box\"', 'box', 'Box', 'Rectangle select: when on, drag on the map to draw a box (Ctrl+drag also works). Turn off to pan the map.')}${B('data-a=\"clear\"', 'clear', 'Clear', 'Clear the selection')}"),
 ("${B('data-t=\"pselect\"', 'select', 'Select', 'Select plots: click; Shift+click adds')}",
  "${B('data-t=\"pselect\"', 'select', 'Select', 'Select plots: click; Shift+click adds')}${B('data-a=\"box\"', 'box', 'Box', 'Rectangle select: drag a box over plots (Shift adds). Turn off to pan the map.')}${B('data-a=\"puse\"', 'fuse', 'Change use', 'Change the land use of the selected plots')}"),
 # Ctrl+drag / Box mode
 ("""  map.on('mousedown', e => {
    if (!tool || !e.originalEvent.ctrlKey || ['create', 'snap', 'extend', 'trim', 'measure'].includes(tool) && picking !== 'targets') return;
    map.dragging.disable(); boxStart = e.latlng;""",
  """  let boxFE = false;
  const BOXROAD = ['select', 'attr', 'delete', 'offset'];
  map.on('mousedown', e => {
    if (!(e.originalEvent.ctrlKey || window.LPBOX) || e.originalEvent.button !== 0) return;
    boxFE = typeof FE !== 'undefined' && FE.canBox;
    if (!boxFE && (!tool || ['create', 'snap', 'extend', 'trim', 'measure'].includes(tool) && picking !== 'targets')) return;
    map.dragging.disable(); boxStart = e.latlng;"""),
 ("""    if (!box) return; const b = box.getBounds(); map.removeLayer(box); box = null; map.dragging.enable();
    if (tool === 'redemarcate') { boxBlocks(b); return; }
    const set = picking === 'targets' ? targets : sel, poly = turf.bboxPolygon([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]), edge = turf.polygonToLine(poly);
    roadLayers(picking === 'targets').forEach(l => {""",
  """    if (!box) return; const b = box.getBounds(); map.removeLayer(box); box = null; map.dragging.enable();
    const p1 = map.latLngToContainerPoint(boxStart), p2 = map.latLngToContainerPoint(e.latlng); if (p1.distanceTo(p2) < 5) return;   // a click, not a box
    window.LPBOX_T = Date.now(); const add = e.originalEvent.shiftKey;
    if (boxFE) { FE.boxSelect(b, add); return; }
    if (tool === 'redemarcate') { boxBlocks(b); return; }
    const poly = turf.bboxPolygon([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
    if (['pselect', 'psplit', 'pmerge'].includes(tool)) { if (!add) pSel.clear(); plotLayers().forEach(l => { try { if (turf.booleanIntersects(poly, l.toGeoJSON())) pSel.set(l.feature.properties.plot_id, l); } catch (er) {} }); paintPlots(); refresh(); return; }
    const set = picking === 'targets' ? targets : sel, edge = turf.polygonToLine(poly);
    roadLayers(picking === 'targets' || BOXROAD.includes(tool)).forEach(l => {"""),
 # clicks: ignore the click that ends a box; existing roads selectable for select / attributes / delete / offset
 ("""  function onClick(kind, l, e) {
    if (typeof FE !== 'undefined' && FE.captureInput(kind, l, e)) return;""",
  """  function onClick(kind, l, e) {
    if (Date.now() - (window.LPBOX_T || 0) < 400) { L.DomEvent.stop(e); return; }
    if (typeof FE !== 'undefined' && FE.captureInput(kind, l, e)) return;"""),
 ("    if (kind !== 'roads') return;\n    const pt = turf.point([e.latlng.lng, e.latlng.lat]);",
  "    if (kind !== 'roads' && !BOXROAD.includes(tool)) return;\n    const pt = turf.point([e.latlng.lng, e.latlng.lat]);"),
 ("  function captureResultClick(kind, f, l, e) {\n", "  function captureResultClick(kind, f, l, e) {\n    if (Date.now() - (window.LPBOX_T || 0) < 400) return true;\n"),
 # delete / attributes / offset also write the existing roads layer
 ("ls.forEach(l => inputs.roads.removeLayer(l)); sel.clear(); saveInput('roads'); refresh(); }",
  "ls.forEach(l => { inputs.roads.removeLayer(l); inputs.existing.removeLayer(l); }); sel.clear(); saveInput('roads'); saveInput('existing'); refresh(); }"),
 ("restyle(l); }); saveInput('roads'); refresh(); }; }", "restyle(l); }); saveInput('roads'); saveInput('existing'); refresh(); }; }"),
 ("    prev.clearLayers(); sidePick = null; saveInput('roads'); clearSel(); hintOffset();", "    prev.clearLayers(); sidePick = null; saveInput('roads'); saveInput('existing'); clearSel(); hintOffset();"),
])
s = open('editor.js', encoding='utf-8').read()
# Box toggle (all Box buttons, also the one in the Features group) + Change use from the Plots group
s = s.replace("  rib.querySelector('[data-a=clear]').onclick = () => clearSel();", """  rib.querySelector('[data-a=clear]').onclick = () => clearSel();
  window.LPBOX = false;
  window.setBox = on => { window.LPBOX = on; document.querySelectorAll('.ribbon [data-a=box]').forEach(b => b.classList.toggle('on', on)); map.getContainer().classList.toggle('boxmode', on);
    if (on && !tool && !(typeof FE !== 'undefined' && FE.canBox)) open(WF === 'design' ? 'select' : 'pselect'); };
  rib.addEventListener('click', e => { if (e.target.closest('[data-a=box]')) window.setBox(!window.LPBOX); });
  rib.querySelector('[data-a=puse]').onclick = () => { const ls = [...pSel.values()]; if (typeof FE !== 'undefined') FE.openUse(ls); };""", 1)
s = s.replace("Click roads to select. Shift+click adds. Ctrl+drag draws a box.", "Click roads to select (existing roads too). Shift+click adds. Box button or Ctrl+drag: draw a box.")
open('editor.js', 'w', encoding='utf-8').write(s)

# ---------------- features.js: Box button, boxSelect, Change use tool ----------------
patch('features.js', [
 ("${B('fattr', 'Attributes', 'Edit the attributes of the selected features')}",
  "${B('fattr', 'Attributes', 'Edit the attributes of the selected features')}${B('fuse', 'Change use', 'Change the land use of the selected plots / parcels')}"),
 ("    ${B('fselect', 'Select', 'Select features of the editing layer: click; Shift+click adds; Esc clears')}",
  "    ${B('fselect', 'Select', 'Select features of the editing layer: click; Shift+click adds; Esc clears')}<button data-a=\"box\" title=\"Rectangle select: drag a box (Shift adds). Turn off to pan the map.\">${IC.box}<span>Box</span></button>"),
 ("fattr: 'Attributes', fdelete: 'Delete' };", "fattr: 'Attributes', fdelete: 'Delete', fuse: 'Change use' };"),
 ("    fdelete: () => `<div class=\"fsel\"></div>",
  """    fuse: () => { const fld = useField(); if (!fld) return '<p class="hint">This layer has no land use. Choose <b>Plots / land use</b> in the Layer list.</p>';
      const list = fld === 'ex_use' ? Object.keys(EXIST_LUSPA).filter(u => !u.startsWith('Unconfirmed')) : Object.keys(DESIGN_LUSPA).filter(Boolean);
      return `<div class="fsel"></div><p class="hint">Select plots (click, Shift+click or the Box button), then click the new use.</p>
        <input id="fuq" type="search" placeholder="Filter uses" style="width:100%;margin-bottom:4px"><div class="uses">${list.map(u => { const c = LUSPA[(fld === 'ex_use' ? EXIST_LUSPA : DESIGN_LUSPA)[u]] || LUSPA.VAC;
        return `<button class="ub" data-u="${u}"><i style="background:${c[1]};border-color:${c[3] || c[2] || '#555'}"></i>${fld === 'use' ? `<b>${u}</b> ${c[0]}` : u}</button>`; }).join('')}</div>`; },
    fdelete: () => `<div class="fsel"></div>"""),
 ("    if (t === 'fattr') wireAttr();", """    if (t === 'fattr') wireAttr();
    if (t === 'fuse' && q('.uses')) { q('#fuq').oninput = e => wid.querySelectorAll('.ub').forEach(b => b.hidden = !b.dataset.u.toLowerCase().includes(e.target.value.toLowerCase()));
      wid.querySelectorAll('.ub').forEach(b => b.onclick = async () => { if (!sel.size) return alert('Select plots first.'); const n = sel.size, u = b.dataset.u;
        const props = useField() === 'ex_use' ? { ex_use: u, use_conf: 'confirmed (planner)' } : { use: u };
        try { await op('update_attrs', { properties: props }); flash(`${n} plot(s) set to ${u}`); if (typeof checkUnconfirmed === 'function') setTimeout(checkUnconfirmed, 800); } catch (e) { alert(e.message); } }); }"""),
 ("  function capture(L_, f, l, e) {\n", "  function capture(L_, f, l, e) {\n    if (Date.now() - (window.LPBOX_T || 0) < 400) return true;\n"),
 ("  function captureInput(kind, l, e) {\n", "  function captureInput(kind, l, e) {\n    if (Date.now() - (window.LPBOX_T || 0) < 400) { L.DomEvent.stop(e); return true; }\n"),
 ("  return { refreshLayers, capture, captureInput, close, get active() { return !!tool || !!sketch; } };",
  """  // ------------------------------------------------------------------ rectangle selection and land use
  const useField = () => (act?.fields || []).map(f => f.name).find(n => n === 'ex_use' || n === 'use');
  function boxSelect(b, add) {
    if (!add) clearSel(); const poly = turf.bboxPolygon([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]); let n = 0;
    for (const l of featLayers()) { try { if (turf.booleanIntersects(poly, l.toGeoJSON())) { const id = fidOf(l); if (id === undefined || id < 0) continue; sel.set(id, l); paint(l, true); n++; } } catch (er) {} }
    if (tool === 'fattr') open('fattr'); else info();
  }
  function flash(t) { const d = document.createElement('div'); d.className = 'flash'; d.textContent = t; wid.querySelector('.wb')?.prepend(d); setTimeout(() => d.remove(), 2500); }
  async function openUse(ls) {
    if (!layers.length) await refreshLayers();
    if (!useField()) { const pl = layers.find(x => (x.fields || []).some(f => ['ex_use', 'use'].includes(f.name))); if (!pl) return alert('There are no plots to change yet: run the toolkit first.'); act = pl; $('#feLayer').value = pl.path; }
    open('fuse'); for (const l of ls || []) { const id = l.feature?.properties?._fid; if (id !== undefined) { sel.set(id, l); paint(l, true); } } info();
  }
  return { refreshLayers, capture, captureInput, close, boxSelect, openUse, get canBox() { return !!tool && !sketch && !temp && tool !== 'fcreate'; }, get active() { return !!tool || !!sketch; } };"""),
])
s = open('features.js', encoding='utf-8').read()
# Change use opened from the Features group on a layer without a use: switch to the plots layer first
s = s.replace("    endSketch(); endVertices(); tool = t; showActive();",
 "    if (t === 'fuse' && !useField()) { const pl = layers.find(x => (x.fields || []).some(f => ['ex_use', 'use'].includes(f.name))); if (pl) { clearSel(); act = pl; $('#feLayer').value = pl.path; } }\n    endSketch(); endVertices(); tool = t; showActive();", 1)
open('features.js', 'w', encoding='utf-8').write(s)

open('app.css', 'a', encoding='utf-8').write("""
/* box select + change use */
.leaflet-container.boxmode { cursor: crosshair; }
.widget .uses { max-height: 300px; overflow: auto; display: flex; flex-direction: column; gap: 2px; }
.widget .ub { display: flex; align-items: center; gap: 7px; text-align: left; background: #fff; color: #1f2328; border: 1px solid #e2e6ea; padding: 4px 8px; font-size: 12px; font-weight: 400; }
.widget .ub:hover { background: #eef4fa; border-color: #c7d9ea; }
.widget .ub i { width: 16px; height: 12px; border: 1.5px solid #555; flex: none; }
.widget .flash { background: #e8f5e9; border-left: 4px solid #43A047; padding: 5px 8px; margin-bottom: 6px; border-radius: 4px; font-size: 12px; }
""")
print('ok')
