"""features.js + app.js + editor.js: every digitising tool uses the shared ArcGIS-style Sketch (pro.js)."""
import os, re
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'webapp', 'static'))
def patch(p, a, b, n=1):
    s = open(p, encoding='utf-8').read(); assert s.count(a) == n, (p, s.count(a), a[:90]); open(p, 'w', encoding='utf-8').write(s.replace(a, b))

# ---------------- features.js ----------------
s = open('features.js', encoding='utf-8').read()
i = s.index("  // ------------------------------------------------------------------ sketch with snapping and Trace")
j = s.index("  // ------------------------------------------------------------------ clicks on features")
s = s[:i] + '''  // ------------------------------------------------------------------ sketching: the shared ArcGIS-style Sketch (pro.js)
  const ROADS_ = ['roads', 'existing'];
  function startSketch(kind, onDone) {
    const k = inputKind();
    Sketch.start({ shape: kind === 'polygon' ? 'polygon' : 'line', title: `${TITLE[tool] || 'Sketch'} &middot; ${act ? act.label : ''}`,
      onCancel: () => { if (tool) open(tool); },
      onDone: geom => {
        if (geom.type === 'LineString' && ROADS_.includes(k)) {                   // a road that runs a little past a crossing road (not a cross road): trimmed there
          const others = roadLayers().map(lineOf); geom = { type: 'LineString', coordinates: trimRoadOvershoot(geom.coordinates, others) };
        }
        onDone(geom);
      } });
  }
  function endSketch() { if (Sketch.active) Sketch.cancel(true); }
  map.on('click', e => {
    if (Sketch.active) return;
    if (tool && !temp && act && !inputKind() && Date.now() - (window.LPBOX_T || 0) > 400) {          // lines / points of the editing layer: picked by position
      const hit = hitTest(e.latlng); if (hit) { toggleSel(hit, e.originalEvent.shiftKey); if (tool === 'fattr') info(); } }
  });
  document.addEventListener('keydown', e => {
    if (e.target.matches('input, select, textarea') || Sketch.active) return;
    if (e.key === 'Escape' && tool) { clearSel(); }
    if (e.key === 'Delete' && tool && sel.size && !inputKind()) { if (confirm(`Delete ${sel.size} feature(s)?`)) op('delete').catch(er => alert(er.message)); }
  });
''' + s[j:]
s = s.replace("    if (sketch) { sketchClick(e.latlng); return true; }", "    if (Sketch.active) { Sketch.click(e.latlng); return true; }")
s = s.replace("    if (sketch) { L.DomEvent.stop(e); sketchClick(e.latlng); return true; }", "    if (Sketch.active) { L.DomEvent.stop(e); Sketch.click(e.latlng); return true; }")
s = s.replace("get canBox() { return !!tool && !sketch && !temp && tool !== 'fcreate'; }, get active() { return !!tool || !!sketch; }",
              "get canBox() { return !!tool && !Sketch.active && !temp && tool !== 'fcreate'; }, get active() { return !!tool || Sketch.active; }")
s = s.replace("let layers = [], act = null, tool = null, sel = new Map(), sketch = null, temp = null;", "let layers = [], act = null, tool = null, sel = new Map(), temp = null;")
# trace / snapping checkboxes now live on the sketch bar and the Snapping pane
s = re.sub(r"  const traceBox = `[^`]*`;", "  const traceBox = '';", s)
s = re.sub(r"  const keysHint = '[^']*';", "  const keysHint = '<p class=\"hint\">Click to add vertices (snapping and Trace as set); F2 / Enter / double-click finishes, Backspace removes the last vertex, Esc cancels; D length, A direction, P parallel, E perpendicular, R right angle; right-click for the menu.</p>';", s)
assert 'sketch.' not in s and 'sketchClick' not in s, [m.start() for m in re.finditer(r'sketch\.|sketchClick', s)][:5]
open('features.js', 'w', encoding='utf-8').write(s)

# ---------------- app.js: the input drawing tools (site, roads, existing, stream, zones) use the Sketch too ----------------
patch('app.js', """map.on(L.Draw.Event.CREATED, e => {
  const kind = activeDraw; if (!kind) return; const l = e.layer;""", """map.on(L.Draw.Event.CREATED, e => { if (activeDraw) onDrawn(activeDraw, e.layer); });
function onDrawn(kind, l) {""")
patch('app.js', """  if (kind === 'site') map.fitBounds(l.getBounds());
  if (kind === 'roads' || kind === 'existing') startDraw(kind, 'polyline'); else stopDraw();
});""", """  if (kind === 'site') map.fitBounds(l.getBounds());
  if (kind === 'roads' || kind === 'existing') startDraw(kind, 'polyline'); else stopDraw();
}""")
patch('app.js', """  drawer = shape === 'polygon' ? new L.Draw.Polygon(map, { shapeOptions: st, allowIntersection: false }) : new L.Draw.Polyline(map, { shapeOptions: st });
  drawer.enable(); $$('button.draw').forEach(b => b.classList.toggle('on', b.dataset.kind === kind && b.dataset.shape === shape));""",
"""  $$('button.draw').forEach(b => b.classList.toggle('on', b.dataset.kind === kind && b.dataset.shape === shape));
  const NAMES = { roads: `Road ${width} ft`, existing: 'Existing road', stream: 'Stream / water', site: 'Site boundary', zones: 'Redesign area' };
  Sketch.start({ shape: shape === 'polygon' ? 'polygon' : 'line', title: NAMES[kind] || kind, onCancel: () => stopDraw(),
    onDone: geom => {
      let c = geom.type === 'Polygon' ? geom.coordinates[0].slice(0, -1) : geom.coordinates;
      if ((kind === 'roads' || kind === 'existing') && geom.type === 'LineString') c = trimRoadOvershoot(c, roadLayers().map(lineOf));   // not a cross road: trimmed at the crossing
      const ll = c.map(p => [p[1], p[0]]); onDrawn(kind, shape === 'polygon' ? L.polygon(ll, st) : L.polyline(ll, st));
    } });""")
patch('app.js', "function stopDraw() { drawer?.disable(); drawer = null;", "function stopDraw() { drawer?.disable(); drawer = null; if (typeof Sketch !== 'undefined' && Sketch.active) Sketch.cancel(true);")

# ---------------- editor.js: Snapping opens the Snapping pane; Create road uses the Sketch ----------------
patch('editor.js', "  rib.querySelectorAll('button[data-t]').forEach(b => b.onclick = () => {\n",
      "  rib.querySelectorAll('button[data-t]').forEach(b => b.onclick = () => {\n    if (b.dataset.t === 'snap') { Sketch.snapPane(); return; }\n")
patch('editor.js', "      q('#ego').onclick = () => { width = cur(); startDraw('roads', 'polyline'); q('#ego').textContent = 'Drawing... (double-click to finish)'; };",
      "      q('#ego').onclick = () => { width = cur(); startDraw('roads', 'polyline'); q('#ego').textContent = 'Drawing... (F2 / double-click finishes each road, Esc stops)'; };")

# ---------------- index.html: load pro.js ----------------
patch('index.html', '<script src="/static/icons.js"></script>', '<script src="/static/pro.js"></script>\n<script src="/static/icons.js"></script>')
open('app.css', 'a', encoding='utf-8').write("""
/* ArcGIS-style sketch bar, cursor tip, context menu, panes */
.skbar { position: absolute; left: 50%; transform: translateX(-50%); bottom: 14px; z-index: 1105; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; max-width: 94%;
  background: #fff; border: 1px solid #b9c1cb; border-radius: 6px; box-shadow: 0 4px 14px rgba(0,0,0,.25); padding: 6px 10px; font-size: 12px; }
.skbar[hidden] { display: none; } .skbar .sp { flex: 1; } .skbar .lk { color: #6200ea; font-weight: 600; } .skbar label { display: inline-flex; gap: 4px; align-items: center; }
.skbar button { padding: 3px 8px; font-size: 12px; }
.sktip { position: absolute; z-index: 1106; pointer-events: none; background: rgba(33,33,33,.85); color: #fff; font-size: 11px; line-height: 1.3; padding: 3px 6px; border-radius: 4px; white-space: nowrap; }
.sktip[hidden] { display: none; }
.skask { position: absolute; left: 50%; transform: translateX(-50%); bottom: 64px; z-index: 1107; background: #fff; border: 1px solid #7c4dff; border-radius: 6px; padding: 6px 10px; font-size: 12px; box-shadow: 0 4px 14px rgba(0,0,0,.25); }
.ctxmenu { position: absolute; z-index: 1110; min-width: 200px; background: #fff; border: 1px solid #b9c1cb; border-radius: 6px; box-shadow: 0 6px 18px rgba(0,0,0,.25); padding: 4px 0; font-size: 12.5px; }
.ctxmenu[hidden] { display: none; } .ctxmenu .mi { display: flex; justify-content: space-between; gap: 18px; padding: 5px 12px; cursor: pointer; } .ctxmenu .mi:hover { background: #e8f0fe; }
.ctxmenu .mi span { color: #8a929c; font-size: 11px; } .ctxmenu hr { border: 0; border-top: 1px solid #e3e6ea; margin: 3px 0; }
.pane { position: absolute; right: 64px; top: 120px; z-index: 1104; width: 250px; background: #fff; border: 1px solid #b9c1cb; border-radius: 6px; box-shadow: 0 6px 18px rgba(0,0,0,.25); font-size: 12.5px; }
.pane .ph { display: flex; justify-content: space-between; align-items: center; padding: 7px 10px; border-bottom: 1px solid #e3e6ea; background: #f6f8fa; border-radius: 6px 6px 0 0; }
.pane .ph .x { background: none; border: 0; font-size: 18px; color: #444; padding: 0 4px; } .pane .pb { padding: 8px 10px; max-height: 60vh; overflow: auto; }
.pane label { display: flex; align-items: center; gap: 6px; margin: 4px 0; } .pane label.big { font-weight: 600; } .pane label i { width: 10px; height: 10px; border: 2.5px solid; border-radius: 50%; }
""")
print('ok')
