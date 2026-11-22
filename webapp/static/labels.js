// Map labels for the plan: off, or the attribute the planner picks (name / LUSPA code / use / area / size / plot number), for facilities only or every plot.
const LBL = (() => {
  map.createPane('labelPane'); map.getPane('labelPane').style.zIndex = 640; map.getPane('labelPane').style.pointerEvents = 'none';
  const layer = L.layerGroup().addTo(map);
  let cfg = { attr: 'name', which: 'fac' };
  try { Object.assign(cfg, JSON.parse(localStorage.getItem('lp_labels') || '{}')); } catch (e) {}
  const ATTRS = [['off', 'Off'], ['name', 'Name / use'], ['code', 'LUSPA code'], ['use', 'Use code'], ['ac', 'Area (acres)'], ['m2', 'Area (m²)'], ['dims', 'Size (frontage x depth, ft)'], ['id', 'Plot number']];
  const ctl = L.control({ position: 'topright' });
  ctl.onAdd = () => {
    const d = L.DomUtil.create('div', 'lblctl leaflet-bar');
    d.innerHTML = `<b>Labels</b> <select class="la" title="What the labels show">${ATTRS.map(([v, t]) => `<option value="${v}">${t}</option>`).join('')}</select>
      <select class="lw" title="Which features are labelled"><option value="fac">Facilities only</option><option value="all">All plots</option></select>`;
    L.DomEvent.disableClickPropagation(d); L.DomEvent.disableScrollPropagation(d);
    d.querySelector('.la').value = cfg.attr; d.querySelector('.lw').value = cfg.which;
    d.querySelector('.la').onchange = e => { cfg.attr = e.target.value; keep(); draw(true); };
    d.querySelector('.lw').onchange = e => { cfg.which = e.target.value; keep(); draw(true); };
    return d;
  };
  ctl.addTo(map);
  const keep = () => { try { localStorage.setItem('lp_labels', JSON.stringify(cfg)); } catch (e) {} };
  const KINDS = new Set(['plots_design', 'reserves', 'plots']);
  const RESID = new Set(['RE', 'RA', '', 'Residential', 'Re', 'Re A', 'Re B']);
  const isRes = p => RESID.has(p.use ?? '') && !p.label || (p.ex_use || '') === 'Residential';
  const codeOf = p => (typeof DESIGN_LUSPA !== 'undefined' && p.use != null && DESIGN_LUSPA[p.use]) || p.luspa || p.code || p.use || p.ex_use || '';
  const nameOf = p => p.label || (typeof LUSPA !== 'undefined' && LUSPA[codeOf(p)] ? LUSPA[codeOf(p)][0] : '') || p.ex_use || p.use || '';
  const SHORT = { 'Neighbourhood Shopping Centre / Market': 'Market', 'Basic School (Primary + JHS) and Nursery': 'Basic School & JHS', 'Clinic (Health Post)': 'Clinic', 'Sports Field / Football Park': 'Sports Field',
    'Sub-Market / Commercial': 'Sub-Market', 'Lorry / Taxi Station': 'Lorry Park', 'P.O.S (park / open space)': 'P.O.S', 'Postal Agency (mixed use)': 'Postal Agency', 'Landscaped green (island too small for a plot)': 'Green', 'Residential Zone B: medium density': 'Re B' };
  const esc = t => String(t ?? '').replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  function text(p, l) {
    const a = () => l._lblArea ?? (l._lblArea = turf.area(l.feature));
    switch (cfg.attr) {
      case 'name': return nameOf(p);
      case 'code': return codeOf(p);
      case 'use': return p.use ?? p.ex_use ?? '';
      case 'ac': return (a() / 4046.86).toFixed(2) + ' ac';
      case 'm2': return Math.round(a()).toLocaleString() + ' m²';
      case 'dims': return p.w && p.d ? `${Math.round(p.w)} x ${Math.round(p.d)} ft` : (p.frontage_m && p.depth_m ? `${Math.round(p.frontage_m / 0.3048)} x ${Math.round(p.depth_m / 0.3048)} ft` : '');
      case 'id': return p.plot_id ?? p.id ?? (p._fid != null ? p._fid + 1 : '');
    }
    return '';
  }
  let sig = '';
  function draw(force) {
    const z = map.getZoom(), off = cfg.attr === 'off';
    const vis = (typeof LAYER_INDEX !== 'undefined' ? LAYER_INDEX : []).filter(x => KINDS.has(x.kind) && results[x.path] && resGroup.hasLayer(results[x.path]));
    const nf = vis.reduce((s, x) => s + results[x.path].getLayers().length, 0);
    const b = map.getBounds().pad(0.2), bk = cfg.which === 'all' ? [b.getWest(), b.getSouth()].map(v => v.toFixed(3)).join() : '';
    const s = [cfg.attr, cfg.which, z, nf, vis.map(x => x.path).join('|'), bk].join('#');
    if (!force && s === sig) return; sig = s; layer.clearLayers();
    if (off || (cfg.which === 'all' && z < 17) || z < 15) return;
    const fs = Math.max(9, Math.min(13, 9 + (z - 15) * 1.5));
    const cands = [];
    for (const x of vis) results[x.path].eachLayer(l => {
      const p = l.feature?.properties; if (!p || !l.getBounds) return;
      if (cfg.which === 'fac' && (isRes(p) || /^(Commercial|Landscaped green)/.test(p.label || '') || (!p.label && (p.use === 'GRN' || p.kind === 'reserve' || p.use === 'MU' || p.use === 'Com A')))) return;
      if (!b.intersects(l.getBounds())) return;
      let t = text(p, l); if (t === '' || t == null) return;
      if (cfg.attr === 'name') t = SHORT[t] || t;
      if (!l._lblPt) { try { const c = turf.pointOnFeature(l.feature).geometry.coordinates; l._lblPt = L.latLng(c[1], c[0]); } catch (e) { l._lblPt = l.getBounds().getCenter(); } }
      if (l._lblArea == null) { try { l._lblArea = turf.area(l.feature); } catch (e) { l._lblArea = 0; } }
      cands.push([l._lblArea, l._lblPt, String(t)]);
    });
    cands.sort((a, b2) => b2[0] - a[0]);                                    // bigger sites first; a label that would overlap one already shown is left out
    const boxes = [];
    for (const [, pt, t] of cands) {
      const c = map.latLngToContainerPoint(pt), w = t.length * fs * 0.56 + 4, h = fs + 4, bx = [c.x - w / 2, c.y - h / 2, c.x + w / 2, c.y + h / 2];
      if (boxes.some(o => bx[0] < o[2] && bx[2] > o[0] && bx[1] < o[3] && bx[3] > o[1])) continue;
      boxes.push(bx);
      layer.addLayer(L.marker(pt, { pane: 'labelPane', interactive: false, keyboard: false, icon: L.divIcon({ className: 'maplbl', html: `<span style="font-size:${fs}px">${esc(t)}</span>`, iconSize: null }) }));
    }
  }
  map.on('zoomend moveend', () => draw());
  setInterval(() => draw(), 1500);
  return { draw, cfg };
})();
window.LBL = LBL;
