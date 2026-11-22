def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
patch('webapp/static/editor.js', [
 # box select: blocks when re-demarcating
 ("  map.on('mouseup', e => {\n    if (!box) return; const b = box.getBounds(); map.removeLayer(box); box = null; map.dragging.enable();",
  "  map.on('mouseup', e => {\n    if (!box) return; const b = box.getBounds(); map.removeLayer(box); box = null; map.dragging.enable();\n    if (tool === 'redemarcate') { boxBlocks(b); return; }"),
 # widget: block numbers box + chips
 ("    redemarcate: () => `<div class=\"bsel\"></div>",
  "    redemarcate: () => `<div class=\"bsel\"></div><div class=\"row\"><input id=\"rnum\" placeholder=\"or type block numbers: 12, 15-18\" style=\"flex:1\"><button class=\"ghost small\" id=\"rnumok\">Add</button><button class=\"ghost small\" id=\"rclr\">Clear</button></div>"),
 ("      <p class=\"hint\">Click a plot to select its whole block (Shift+click adds blocks). Plot lines are placed where the image shows boundaries: walls and gaps between buildings.</p>",
  "      <p class=\"hint\">Click anywhere inside a block to add it (click again to remove); Ctrl+drag a box to take several. Block outlines and numbers are shown while this tool is open.</p>"),
 ("    if (t === 'redemarcate') q('#rap').onclick = async () => {",
  """    if (t === 'redemarcate') { showBlocks(); q('#rnumok').onclick = () => { parseBlocks(q('#rnum').value).forEach(b => pBlocks.add(b)); q('#rnum').value = ''; paintBlocks(); refresh(); };
      q('#rnum').onkeydown = e => { if (e.key === 'Enter') q('#rnumok').click(); }; q('#rclr').onclick = () => { pBlocks.clear(); paintBlocks(); refresh(); }; }
    if (t === 'redemarcate') q('#rap').onclick = async () => {"""),
 # clicking a plot toggles its block without Shift
 ("    if (tool === 'redemarcate') { if (!add) pBlocks.clear(); pBlocks.has(p.block_id) ? pBlocks.delete(p.block_id) : pBlocks.add(p.block_id); }",
  "    if (tool === 'redemarcate') { toggleBlock(p.block_id); return true; }"),
 # tidy up the block overlay when the tool closes
 ("  function close() { prev.clearLayers(); mg.clearLayers();", "  function close() { prev.clearLayers(); mg.clearLayers(); hideBlocks();"),
 # map click inside a block (gaps, roads edges etc.)
 ("  map.on('click', e => { if (tool === 'measure') measureClick(e.latlng); });",
  "  map.on('click', e => { if (tool === 'measure') measureClick(e.latlng); if (tool === 'redemarcate') { const b = blockAt(e.latlng); if (b != null) toggleBlock(b); } });"),
 # helpers
 ("  // ------------------------------------------------------------------ plots (existing situation): select plots / blocks",
  r"""  // ------------------------------------------------------------------ blocks overlay for re-demarcation (click inside, box, numbers)
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
  // ------------------------------------------------------------------ plots (existing situation): select plots / blocks"""),
 # selected-block chips with remove buttons
 ("    wid.querySelectorAll('.bsel').forEach(e => e.innerHTML = pBlocks.size ? `Blocks selected: <b>${[...pBlocks].join(', ')}</b>` : '<span class=\"mini\">No blocks selected: click a plot in each block</span>'); };",
  "    wid.querySelectorAll('.bsel').forEach(e => { e.innerHTML = pBlocks.size ? `<span class=\"mini\">${pBlocks.size} block(s):</span> ` + [...pBlocks].sort((a, b) => a - b).map(b => `<span class=\"chip\">${b}<button data-rb=\"${b}\" title=\"Remove\">&times;</button></span>`).join('') : '<span class=\"mini\">No blocks selected: click inside a block, Ctrl+drag a box, or type numbers</span>';\n      e.querySelectorAll('[data-rb]').forEach(x => x.onclick = () => toggleBlock(+x.dataset.rb)); }); };"),
])
# box selection must start for the re-demarcate tool too (Ctrl+drag)
s = open('webapp/static/editor.js', encoding='utf-8').read()
a = "    if (!tool || !e.originalEvent.ctrlKey || ['create', 'snap', 'extend', 'trim'].includes(tool) && picking !== 'targets') return;"
assert a in s
s = s.replace(a, "    if (!tool || !e.originalEvent.ctrlKey || ['create', 'snap', 'extend', 'trim', 'measure'].includes(tool) && picking !== 'targets') return;")
open('webapp/static/editor.js', 'w', encoding='utf-8').write(s)
c = 'webapp/static/app.css'; t = open(c, encoding='utf-8').read()
t += """
.blk { font: 700 11px/1 "Segoe UI", sans-serif; color: #0b3d5e; background: rgba(255,255,255,.85); border: 1px solid #0b3d5e; border-radius: 9px; padding: 2px 6px; white-space: nowrap; }
.blk.on { background: #00b8d4; color: #fff; border-color: #00838f; }
.chip { display: inline-flex; align-items: center; gap: 2px; background: #e0f7fa; border: 1px solid #80deea; border-radius: 10px; padding: 0 2px 0 7px; margin: 2px; font-size: 12px; }
.chip button { background: none; border: none; color: #00838f; padding: 0 4px; font-size: 14px; line-height: 1; }
"""
open(c, 'w', encoding='utf-8').write(t)
print('ok')
