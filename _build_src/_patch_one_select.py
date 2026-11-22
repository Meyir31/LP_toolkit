"""One Select for everything: click any feature (road, plot, building, block, wall, water...) and the layer follows;
road tools, plot tools and feature tools all use that selection."""
import os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'webapp'))
def patch(p, a, b):
    s = open(p, encoding='utf-8').read(); assert s.count(a) == 1, (p, s.count(a), a[:90]); open(p, 'w', encoding='utf-8').write(s.replace(a, b))

# ---------------- features.js: the one selection ----------------
patch('static/features.js', "  function capture(L_, f, l, e) {\n    if (Date.now() - (window.LPBOX_T || 0) < 400) return true;\n    if (sketch) { sketchClick(e.latlng); return true; }\n    if (!tool || temp || !act) return false;\n",
      """  // Select picks from any editable layer: the layer of the clicked feature becomes the editing layer
  const INPUT_PATH = { roads: 'roads.geojson', existing: 'existing.geojson', stream: 'stream.geojson' };
  function switchTo(path, add) {
    const L2 = layers.find(x => x.path === path); if (!L2) return false;
    if (act && act.path === path) return true;
    clearSel(); act = L2; $('#feLayer').value = path; info(); return true;
  }
  function capture(L_, f, l, e) {
    if (Date.now() - (window.LPBOX_T || 0) < 400) return true;
    if (sketch) { sketchClick(e.latlng); return true; }
    if (!tool || temp || !act) return false;
    if (tool === 'fselect' && L_.path !== act.path && switchTo(L_.path)) { toggleSel(l, e.originalEvent.shiftKey); return true; }
""")
patch('static/features.js', "  function captureInput(kind, l, e) {\n    if (Date.now() - (window.LPBOX_T || 0) < 400) { L.DomEvent.stop(e); return true; }\n    if (sketch) { L.DomEvent.stop(e); sketchClick(e.latlng); return true; }\n",
      """  function captureInput(kind, l, e) {
    if (Date.now() - (window.LPBOX_T || 0) < 400) { L.DomEvent.stop(e); return true; }
    if (sketch) { L.DomEvent.stop(e); sketchClick(e.latlng); return true; }
    if (tool === 'fselect' && !temp && inputKind() !== kind && INPUT_PATH[kind] && switchTo(INPUT_PATH[kind])) { L.DomEvent.stop(e); toggleSel(l, e.originalEvent.shiftKey); return true; }
""")
patch('static/features.js', "  return { refreshLayers, capture, captureInput, close, boxSelect, openUse,",
      "  function selection() { return act ? { path: act.path, kind: inputKind() || (LAYER_INDEX.find(l => l.path === act.path) || {}).kind, layers: [...sel.values()] } : null; }\n"
      "  function clearAll() { clearSel(); }\n"
      "  return { refreshLayers, capture, captureInput, close, boxSelect, openUse, selection, clearAll, open: t => open(t),")
patch('static/features.js', "    fselect: () => `<div class=\"fsel\"></div><p class=\"hint\">Click features of the editing layer; Shift+click adds or removes; drag a box to select many (Space+drag pans).</p>`,",
      "    fselect: () => `<div class=\"fsel\"></div><p class=\"hint\">Click any feature (road, plot, building, block, wall, water...): the layer follows what you click. Shift+click adds; drag a box to select many on this layer (Space+drag pans). Then pick any tool: road tools, plot tools and feature tools all use this selection.</p>`,")
patch('static/features.js', "fselect: 'Select features',", "fselect: 'Select',")
# the Features group's own Select button is the same tool now: hidden
patch('static/features.js', "  rib.insertBefore(grp, rib.querySelector('.rhide'));\n", "  rib.insertBefore(grp, rib.querySelector('.rhide'));\n  grp.querySelector('[data-f=fselect]').style.display = 'none';\n")

# ---------------- editor.js: the Select button opens the one Select; tools take its selection ----------------
patch('static/editor.js', "  rib.querySelectorAll('.grp').forEach((g, i) => { if (i < 4) g.classList.add('g-roads'); });",
      "  rib.querySelectorAll('.grp').forEach((g, i) => { if (i > 0 && i < 4) g.classList.add('g-roads'); });      // the Selection group serves both workflows\n"
      "  rib.querySelector('[data-t=pselect]').style.display = 'none';                                           // one Select for everything")
patch('static/editor.js', "  rib.querySelectorAll('button[data-t]').forEach(b => b.onclick = () => (tool === b.dataset.t ? close() : open(b.dataset.t)));",
      "  rib.querySelectorAll('button[data-t]').forEach(b => b.onclick = () => {\n"
      "    if (['select', 'pselect'].includes(b.dataset.t)) { close(); rib.querySelectorAll('button[data-t]').forEach(x => x.classList.remove('on')); if (typeof FE !== 'undefined') FE.open('fselect'); b.classList.add('on'); return; }\n"
      "    tool === b.dataset.t ? close() : open(b.dataset.t); });")
patch('static/editor.js', "  rib.querySelector('[data-a=clear]').onclick = () => clearSel();",
      "  rib.querySelector('[data-a=clear]').onclick = () => { clearSel(); pSel.clear(); pBlocks.clear(); paintPlots(); if (typeof FE !== 'undefined') FE.clearAll(); refresh(); };")
patch('static/editor.js', "    close(); tool = t; picking = 'select'; sidePick = null;",
      "    close(); tool = t; picking = 'select'; sidePick = null;\n"
      "    const fs = typeof FE !== 'undefined' && FE.selection();                    // the one Select's selection carries into the road / plot tools\n"
      "    if (fs && fs.layers.length && ['roads', 'existing'].includes(fs.kind) && !['redemarcate', 'measure'].includes(t)) { sel.clear(); fs.layers.forEach(l => { sel.add(l); restyle(l); }); }\n"
      "    if (fs && fs.layers.length && fs.kind === 'plots' && t === 'redemarcate') fs.layers.forEach(l => { const b_ = l.feature?.properties?.block_id; if (b_ != null) pBlocks.add(b_); });")
patch('static/editor.js', "  rib.querySelector('[data-a=puse]').onclick = () => { const ls = [...pSel.values()]; if (typeof FE !== 'undefined') FE.openUse(ls); };",
      "  rib.querySelector('[data-a=puse]').onclick = () => { if (typeof FE === 'undefined') return; const fs = FE.selection(); const ls = fs && ['plots', 'plots_design'].includes(fs.kind) ? fs.layers : [...pSel.values()]; FE.openUse(ls); };")
print('ok')
