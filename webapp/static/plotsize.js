// LP Toolkit: Plot size after the design (new layout). The planner gives the plot breadth (frontage) x length (depth) for the
// selected blocks or the whole planning area; both ways of handling what does not divide exactly are previewed, the planner picks one:
//   Fit the block - breadth kept, row leftover to the two end plots, block depth shared between the rows
//   Exact size    - every plot exactly breadth x length, leftover strips left open (landscaped green)
const PlotSize = (() => {
  const ICON = `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="1" fill="#FFCC80" stroke="#37474F" stroke-width="1.5"/><path d="M9 5v14M15 5v14M3 12h18" stroke="#37474F" stroke-width="1.2"/><path d="M3 2.5h6M3 1.5v2M9 1.5v2" stroke="#1E88E5" stroke-width="1.4"/><path d="M22.5 12v7M21.5 12h2M21.5 19h2" stroke="#E53935" stroke-width="1.4"/></svg>`;
  const rib = document.querySelector('.ribbon'); if (!rib) return {};
  const grp = document.createElement('div'); grp.className = 'grp g-roads g-psize';
  grp.innerHTML = `<div class="gb"><button data-a="psize" title="Plot size: breadth x length for the selected blocks or the whole planning area (preview, then choose how leftovers are handled)">${ICON}<span>Plot size</span></button></div><span class="gl">Plots</span>`;
  const roadsG = [...rib.querySelectorAll('.grp.g-roads')].pop(); roadsG ? roadsG.after(grp) : rib.append(grp);
  L.DomEvent.disableClickPropagation(grp);
  map.createPane('psPrev'); map.getPane('psPrev').style.zIndex = 640; map.getPane('psPrev').style.pointerEvents = 'none';
  const PR = L.svg({ pane: 'psPrev' }); const prev = L.layerGroup().addTo(map);
  let pane = null, res = null, showing = null, timer = null;
  const q = s => pane.querySelector(s);
  function fids() { const s = FE.selection(); return s && s.kind === 'plots_design' ? s.layers.map(l => l.feature?.properties?._fid).filter(x => x != null) : []; }
  function where() { return q('input[name=psW]:checked').value; }
  function selInfo() { if (!pane) return; const n = fids().length; q('#psSel').textContent = n ? `(${n} plot${n > 1 ? 's' : ''} selected: their whole blocks)` : '(click a plot in each block; drag a box for many)'; }
  function draw(mode) {
    prev.clearLayers(); showing = mode; if (!res) return;
    L.geoJSON(res[mode].fc, { pane: 'psPrev', renderer: PR, interactive: false, style: f => f.properties.open ? { color: '#1b5e20', weight: 1, fillColor: '#66bb6a', fillOpacity: .55, dashArray: '3 3' }
      : f.properties.small ? { color: '#ff6d00', weight: 2, fillColor: '#ffab40', fillOpacity: .35 } : { color: '#00e5ff', weight: 1.6, fillColor: '#00e5ff', fillOpacity: f.properties.ok ? .12 : .3 } }).addTo(prev);
    pane.querySelectorAll('.psopt').forEach(c => c.classList.toggle('on', c.dataset.m === mode));
  }
  function card(mode, title, how) {
    const s = res[mode].stats, pct = s.plots ? Math.round(100 * s.size_ok / s.plots) : 0;
    return `<div class="psopt" data-m="${mode}"><div class="pst"><b>${title}</b><button class="ghost small" data-show="${mode}">Show</button></div><p class="mini">${how}</p>
      <table class="attr"><tr><th>Plots</th><td><b>${s.plots}</b> (now ${s.before})</td></tr><tr><th>At your size (+/-15%)</th><td>${s.size_ok} (${pct}%)</td></tr>
      <tr><th>Median plot</th><td>${s.median_w.toFixed(0)} x ${s.median_d.toFixed(0)} ft</td></tr><tr><th>Below 0.16 ac (Re B min.)</th><td>${s.below_min ? `<span style="color:#b42318">${s.below_min}</span>` : 0}</td></tr>
      <tr><th>Open / green left over</th><td>${s.open_ac} ac</td></tr></table><button data-apply="${mode}">Apply: ${title.toLowerCase()}</button></div>`;
  }
  async function preview() {
    const b = +q('#psB').value, l = +q('#psL').value; if (!(b > 0 && l > 0)) return alert('Give the plot breadth and length in feet.');
    const whole = where() === 'all', f = whole ? [] : fids(); if (!whole && !f.length) return alert('Select plots first: click a plot in each block to re-plot (Shift+click adds, drag a box for many), or choose the whole planning area.');
    q('#psRes').innerHTML = '<p class="hint">Working out both options...</p>';
    try { res = await post(`/api/projects/${P.id}/plotsize/preview`, { breadth: b, length: l, fids: f, whole }); } catch (e) { q('#psRes').innerHTML = ''; return alert(e.message); }
    res._req = { breadth: b, length: l, fids: f, whole };
    q('#psRes').innerHTML = `<p class="hint">${res.fit.stats.blocks} block(s). Choose how to handle what does not divide exactly (cyan = plots, orange = below 0.16 ac, green = left open):</p>` +
      card('fit', 'Fit the block', `Breadth ${b} ft kept; the leftover of each row goes to its two end plots; the block depth is shared between the rows.`) +
      card('exact', 'Exact size', `Every plot ${b} x ${l} ft; leftover strips are left open as landscaped green.`);
    pane.querySelectorAll('[data-show]').forEach(x => x.onclick = () => draw(x.dataset.show));
    pane.querySelectorAll('[data-apply]').forEach(x => x.onclick = () => apply(x.dataset.apply));
    draw('fit');
  }
  async function apply(mode) {
    if (!res) return; const r0 = res._req;
    try { const r = await post(`/api/projects/${P.id}/plotsize/apply`, { ...r0, mode });
      if (typeof EditLog !== 'undefined') EditLog.add(`plot size ${r0.breadth} x ${r0.length} ft (${mode})`, { label: 'Plots and land use' });
      prev.clearLayers(); res = null; q('#psRes').innerHTML = ''; FE.clearAll?.();
      await reloadKinds(['plots_design', 'reserves']); markSaved?.(true);
      alert(`Plot size applied (${mode === 'fit' ? 'fit the block' : 'exact size'}): ${r.stats.plots} plots in ${r.stats.blocks} block(s)${r.stats.below_min ? `, ${r.stats.below_min} below 0.16 ac` : ''}${r.stats.open_ac ? `, ${r.stats.open_ac} ac left open` : ''}. Undo: Features > Plots and land use > Undo. Run "Update the plan" from land use to refresh the tables and audit.`);
    } catch (e) { alert(e.message); }
  }
  function open() {
    if (pane) { close(); return; }
    if (!P || P.workflow !== 'design') return alert('Plot size after the design is for new layouts.');
    if (!LAYER_INDEX.some(l => l.kind === 'plots_design')) return alert('Run the design first. For the whole planning area before the design, set the plot size under "Design the roads for me".');
    pane = L.DomUtil.create('div', 'pane pspane', map.getContainer()); L.DomEvent.disableClickPropagation(pane); L.DomEvent.disableScrollPropagation(pane);
    pane.innerHTML = `<div class="ph"><b>Plot size</b><button class="x">&times;</button></div><div class="pb">
      <div class="g2"><span>Breadth (frontage)</span><span><input id="psB" type="number" min="30" max="400" value="${P.plot_w || 70}" style="width:70px"> ft</span>
      <span>Length (depth)</span><span><input id="psL" type="number" min="30" max="600" value="${P.plot_l || 100}" style="width:70px"> ft</span></div>
      <label class="tl"><input type="radio" name="psW" value="sel" checked> Selected blocks <span class="mini" id="psSel"></span></label>
      <label class="tl"><input type="radio" name="psW" value="all"> Whole planning area (every residential block)</label>
      <div class="row"><button id="psGo">Preview both options</button></div><div id="psRes"></div>
      <p class="hint">Residential plots only; facility sites stay. Roads are not moved: for road spacing that fits the plots, set the plot size under "Design the roads for me" before the design.</p></div>`;
    q('.x').onclick = close; q('#psGo').onclick = preview;
    pane.querySelectorAll('input').forEach(i => i.addEventListener('input', () => { if (res) { res = null; prev.clearLayers(); q('#psRes').innerHTML = ''; } }));
    FE.open?.('fselect'); const L_ = LAYER_INDEX.find(l => l.kind === 'plots_design'); if (L_) toggleLayer(L_, true);
    selInfo(); timer = setInterval(selInfo, 700);
  }
  function close() { if (pane) pane.remove(); pane = null; res = null; prev.clearLayers(); clearInterval(timer); }
  grp.querySelector('[data-a=psize]').onclick = open;
  return { open, close };
})();
