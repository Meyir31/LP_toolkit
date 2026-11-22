import re
p = 'webapp/static/app.js'; s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:80]; s = s.replace(a, b, 1)
rep("const FT = 0.3048, SNAP_M = 12;", "const FT = 0.3048; let SNAP_M = 12, snapOn = true;")
rep("let P = null, poll = null, activeDraw = null, drawer = null, tool = null, width = 30, offsetPick = null;", "let P = null, poll = null, activeDraw = null, drawer = null, width = 30;")
# snapping respects the on / off switch
rep("function snapEnds(l) {\n", "function snapEnds(l) {\n  if (!snapOn) return false;\n")
# remove the old simple road tools (now in editor.js)
a0 = s.index("// ------------------------------------------------------------------ road tools")
a1 = s.index("// ------------------------------------------------------------------ drawing")
s = s[:a0] + """// ------------------------------------------------------------------ road tools: see editor.js (ArcGIS Pro style ribbon and widgets)
function markMine(l) { l.feature.properties.locked = true; l.feature.properties.kind = l.feature.properties.kind === 'existing' ? 'existing' : 'planner'; }
function onFeatureClick(kind, l, e) { if (typeof Editor !== 'undefined') Editor.onClick(kind, l, e); }
function stopTool() { if (typeof Editor !== 'undefined') Editor.close(); }
""" + s[a1:]
# drawing: history before a new road, square ends after
rep("  const kind = activeDraw; if (!kind) return; const l = e.layer;", "  const kind = activeDraw; if (!kind) return; const l = e.layer;\n  if (kind === 'roads' && typeof Editor !== 'undefined') Editor.push();")
rep("  addInputLayer(kind, l); if (kind === 'roads') snapEnds(l); saveInput(kind); liveAngle.clearLayers();",
    "  addInputLayer(kind, l); if (kind === 'roads') { snapEnds(l); if (typeof Editor !== 'undefined') Editor.afterCreate(l); } saveInput(kind); liveAngle.clearLayers();")
rep("$$('button.draw').forEach(b => b.onclick = () => { if (!P) return alert('Create or choose a project first'); if (b.classList.contains('on')) return stopDraw(); stopTool(); startDraw(b.dataset.kind, b.dataset.shape); });",
    "$$('button.draw').forEach(b => b.onclick = () => { if (!P) return alert('Create or choose a project first'); if (b.classList.contains('on')) return stopDraw(); stopTool(); startDraw(b.dataset.kind, b.dataset.shape); });")
rep("document.addEventListener('keydown', e => { if (e.key === 'Escape') stopTool(); });\n", "")
# the ribbon only for new layouts
rep("  $('#designInputs').hidden = wf !== 'design'; $('#existingInputs').hidden = wf !== 'existing'; $('#extras').hidden = wf !== 'existing';",
    "  $('#designInputs').hidden = wf !== 'design'; $('#existingInputs').hidden = wf !== 'existing'; $('#extras').hidden = wf !== 'existing';\n  if (typeof Editor !== 'undefined') Editor.show(wf === 'design');")
open(p, 'w', encoding='utf-8').write(s)
# ---- index.html: roads card without the old tool buttons; load editor.js ----
p = 'webapp/static/index.html'; s = open(p, encoding='utf-8').read()
a0 = s.index('            <div class="mini">Road width (ft)</div>'); a1 = s.index('            <div class="row"><label class="tl"><input type="checkbox" id="showAngles" checked>')
s = s[:a0] + '''            <p class="hint">Edit the roads with the <b>editing ribbon</b> at the top of the map, as in ArcGIS Pro: <b>Select</b>, <b>Create road</b> (width templates), <b>Offset</b>, <b>Extend</b>, <b>Trim</b>, <b>Split</b>, <b>Square ends</b>, <b>Attributes</b>, <b>Delete</b>, <b>Undo / Redo</b> (Ctrl+Z / Ctrl+Y) and <b>Snapping</b>. Each tool opens a panel: select roads, set the options, check the preview, Apply.</p>
            <p class="hint" id="toolHint"></p>
''' + s[a1:]
s = s.replace('<script src="/static/app.js"></script>', '<script src="/static/app.js"></script>\n<script src="/static/editor.js"></script>')
open(p, 'w', encoding='utf-8').write(s)
# ---- css for the ribbon and widgets ----
c = 'webapp/static/app.css'; t = open(c, encoding='utf-8').read()
t += '''
/* ArcGIS Pro style editing ribbon and tool panes */
.ribbon { position: absolute; top: 10px; left: 56px; right: 70px; z-index: 1000; display: flex; flex-wrap: wrap; gap: 6px; background: rgba(255,255,255,.97); border: 1px solid #c9ced6; border-radius: 6px; padding: 4px 6px; box-shadow: 0 2px 8px rgba(0,0,0,.18); font-size: 12px; }
.ribbon .grp { display: flex; align-items: center; gap: 2px; padding-right: 6px; border-right: 1px solid #e3e1dc; }
.ribbon .grp:last-child { border-right: none; }
.ribbon .gl { font-size: 10px; color: #6b7280; text-transform: uppercase; letter-spacing: .04em; margin-right: 4px; }
.ribbon button { background: #fff; color: #1f2328; border: 1px solid transparent; padding: 4px 8px; font-size: 12px; border-radius: 4px; }
.ribbon button:hover { background: #eef4fa; border-color: #c7d9ea; }
.ribbon button.on { background: #d6e8f7; border-color: #1f5f8b; color: #0b3d5e; font-weight: 600; }
.widget { position: absolute; top: 64px; left: 56px; z-index: 1001; width: 330px; max-height: calc(100% - 90px); overflow: auto; background: #fff; border: 1px solid #b9c1cb; border-radius: 6px; box-shadow: 0 6px 18px rgba(0,0,0,.25); font-size: 13px; }
.widget .wh { display: flex; justify-content: space-between; align-items: center; padding: 7px 10px; background: #f1f4f7; border-bottom: 1px solid #dde2e8; cursor: move; border-radius: 6px 6px 0 0; }
.widget .wh .x { background: none; border: none; color: #444; font-size: 18px; line-height: 1; padding: 0 4px; cursor: pointer; }
.widget .wb { padding: 10px 12px; }
.widget .g2 { display: grid; grid-template-columns: 96px 1fr; gap: 6px 8px; align-items: center; margin: 6px 0; }
.widget .g2 > span:nth-child(odd) { color: #555; }
.widget select, .widget input[type=number] { padding: 3px 6px; }
.widget .chk { display: flex; gap: 6px; align-items: center; margin: 6px 0; }
.widget .tmpl label { display: block; margin: 3px 0; }
.widget .lbl2 { font-size: 11px; color: #6b7280; text-transform: uppercase; margin-bottom: 4px; }
.widget .wf { display: flex; gap: 6px; justify-content: flex-end; margin-top: 8px; }
.widget .selinfo { background: #f6f9fc; border: 1px solid #e1e8f0; border-radius: 4px; padding: 5px 8px; margin-bottom: 6px; }
.widget button.small { padding: 1px 6px; font-size: 11px; }
.widget .sep { border-top: 1px dashed #ddd; margin: 10px 0 4px; }
.widget button.on { background: #f5a142; border-color: #f5a142; color: #fff; }
.danger2 { background: #b42318 !important; border-color: #b42318 !important; }
.leaflet-top.leaflet-left { top: 52px; }
'''
open(c, 'w', encoding='utf-8').write(t)
print('ok')
