import os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'webapp', 'static'))
def patch(p, a, b):
    s = open(p, encoding='utf-8').read(); assert s.count(a) == 1, (p, s.count(a), a[:90]); open(p, 'w', encoding='utf-8').write(s.replace(a, b))
# 1. snap targets: no contours / slope / audit ever; road sketches snap to roads, site and streams only (unless the planner asks for everything)
patch('pro.js', "const SNAP = Object.assign({ on: true, end: true, vertex: true, edge: true, inter: true, mid: false, tol: 12 }",
                "const SNAP = Object.assign({ on: true, end: true, vertex: true, edge: true, inter: true, mid: false, tol: 12, roadAll: false }")
patch('pro.js', """  function collect() {
    const out = [], vb""", """  const NOSNAP = ['contours', 'slope', 'steep', 'audit', 'raster', 'hillshade'];
  function collect(roadsOnly) {                                          // roadsOnly: a road sketch snaps to roads, the site and streams (not plot corners)
    const out = [], vb""")
patch('pro.js', """    if (typeof resGroup !== 'undefined') resGroup.eachLayer(gr => gr.eachLayer?.(l => add(l, l instanceof L.Polygon)));
    Object.values(inputs).forEach(gr => gr.eachLayer(l => add(l, l instanceof L.Polygon)));""",
"""    if (typeof resGroup !== 'undefined') resGroup.eachLayer(gr => { const k = gr._kind || ''; if (NOSNAP.includes(k) || (roadsOnly && !/centre|draft/.test(k))) return; gr.eachLayer?.(l => add(l, l instanceof L.Polygon)); });
    Object.entries(inputs).forEach(([k, gr]) => { if (roadsOnly && k === 'zones') return; gr.eachLayer(l => add(l, l instanceof L.Polygon)); });""")
# 2. trace is off until asked for (T), as in ArcGIS Pro; the hover line shows the traced path when it is on
patch('pro.js', "S = Object.assign({ groups: [], snaps: [], hover: null, lock: null, dist: null, lockName: '', trace: true, rings: collect(), inter: null }, o);",
                "S = Object.assign({ groups: [], snaps: [], hover: null, lock: null, dist: null, lockName: '', trace: false, inter: null }, o); S.rings = collect(o.roads && !SNAP.roadAll);")
patch('pro.js', """    S.hover = { c, snap: s && s.type }; draw(); tip(e, s, c);""",
"""    const ls = S.snaps[S.snaps.length - 1], tr = s && ls && S.trace && s.ri >= 0 && ls.ri === s.ri ? tracePath(S.rings[s.ri], ls.loc, s.loc) : [];
    S.hover = { c, snap: s && s.type, tr }; draw(); tip(e, s, c);""")
patch('pro.js', "const p = pts().map(c => [c[1], c[0]]), h = S.hover; const all = h ? [...p, [h.c[1], h.c[0]]] : p;",
                "const p = pts().map(c => [c[1], c[0]]), h = S.hover; const all = h ? [...p, ...(h.tr || []).map(c => [c[1], c[0]]), [h.c[1], h.c[0]]] : p;")
# snapping pane: the road option
patch('pro.js', """${row('end', 'Endpoint', '#d50000')}""", """${row('end', 'Endpoint', '#d50000')}""")
patch('pro.js', """      <div class="row"><span class="mini">Tolerance</span>""", """      <label title="Off: a road snaps only to roads, the site and streams, so plot corners do not pull it off its line"><input type="checkbox" data-s="roadAll" ${SNAP.roadAll ? 'checked' : ''}> Roads also snap to plots and outlines</label>
      <div class="row"><span class="mini">Tolerance</span>""")
patch('pro.js', "SNAP[c.dataset.s] = c.checked; saveSnap(); if (S) S.inter = null; });", "SNAP[c.dataset.s] = c.checked; saveSnap(); if (S) { S.rings = collect(S.roads && !SNAP.roadAll); S.inter = null; } });")
patch('pro.js', "const keep = S; S = { rings: collect(), inter: null };", "const keep = S; S = { rings: collect(false), inter: null };")
# road sketches say so
patch('app.js', "Sketch.start({ shape: shape === 'polygon' ? 'polygon' : 'line', title: NAMES[kind] || kind, onCancel: () => stopDraw(),",
                "Sketch.start({ shape: shape === 'polygon' ? 'polygon' : 'line', title: NAMES[kind] || kind, roads: kind === 'roads' || kind === 'existing', onCancel: () => stopDraw(),")
patch('features.js', "Sketch.start({ shape: kind === 'polygon' ? 'polygon' : 'line', title: `${TITLE[tool] || 'Sketch'} &middot; ${act ? act.label : ''}`,",
                     "Sketch.start({ shape: kind === 'polygon' ? 'polygon' : 'line', title: `${TITLE[tool] || 'Sketch'} &middot; ${act ? act.label : ''}`, roads: ROADS_.includes(k) && kind !== 'polygon',")
# 3. square ends: a short square stub at the junction; the planner's own vertices stay where they were clicked
patch('editor.js', """      if (!tgt) continue; const i = atEnd ? c.length - 2 : 1, nb = c[i], len = turf.distance(end, nb, mm); if (len < 3) continue;
      const bRoad = bearingAt(tgt.t, tgt), away = turf.bearing(end, nb), perp = [bRoad + 90, bRoad - 90].reduce((a, b) => turn360(a, away) < turn360(b, away) ? a : b);
      c[i] = turf.destination(end, len, perp, mm).geometry.coordinates;""",
"""      if (!tgt) continue; const i = atEnd ? c.length - 2 : 1, nb = c[i], len = turf.distance(end, nb, mm); if (len < 3) continue;
      const bRoad = bearingAt(tgt.t, tgt), away = turf.bearing(end, nb), perp = [bRoad + 90, bRoad - 90].reduce((a, b) => turn360(a, away) < turn360(b, away) ? a : b);
      if (turn360(perp, away) < 3) continue;                                               // already square
      const stub = Math.min(len * 0.5, 30), p = turf.destination(end, stub, perp, mm).geometry.coordinates;   // about 100 ft square to the road, then on to the planner's next vertex
      if (len <= 12) c[i] = turf.destination(end, len, perp, mm).geometry.coordinates;   // a short first segment: just turn it
      else if (atEnd) c.splice(c.length - 1, 0, p); else c.splice(1, 0, p);""")
print('ok')
