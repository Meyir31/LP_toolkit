// Map navigation additions (user 2026-11-22): Zoom to layer (button on each Contents row + right-click menu), Zoom to selection (ribbon),
// and the Labels controls moved into a "Labels" group on the Map tab of the ribbon.
(() => {
  const pad = { padding: [30, 30] };
  function fit(b) { if (b && b.isValid && b.isValid()) { map.fitBounds(b, pad); return true; } return false; }
  async function zoomToLayer(ref) {
    try {
      if (ref.input) {
        const ks = ref.input === 'reserves' ? ['roads', 'existing'] : [ref.input];
        const ls = ks.flatMap(k => inputs[k] ? inputs[k].getLayers() : []);
        if (!ls.length || !fit(L.featureGroup(ls).getBounds())) alert('Nothing to zoom to in this layer.');
        return;
      }
      const g = results[ref.path];
      if (g && g.getBounds) {                                             // vector layers and image overlays (hillshade, slope) both have bounds
        let b_ = null; try { b_ = (!g.getLayers || g.getLayers().length) ? g.getBounds() : null; } catch (e) {}
        if (fit(b_)) return;
      }
      const fc = await api(`/api/projects/${P.id}/geojson?f=${encodeURIComponent(ref.path)}`);       // layer not loaded (switched off): read its extent
      if (!fc.features || !fc.features.length || !fit(L.geoJSON(fc).getBounds())) alert('This layer has no features.');
    } catch (e) { alert('Could not zoom to the layer: ' + e.message); }
  }
  window.zoomToLayer = zoomToLayer;
  function zoomToSelection() {
    let ls = [];
    try { const s = typeof FE !== 'undefined' && FE.selection ? FE.selection() : null; ls = (s && s.layers) || []; } catch (e) {}
    ls = ls.filter(l => l && (l.getBounds || l.getLatLng));
    if (!ls.length) return alert('Select features first (Select on the Edit tab), then Zoom to selection.');
    const b = L.latLngBounds([]); ls.forEach(l => l.getBounds ? b.extend(l.getBounds()) : b.extend(l.getLatLng()));
    if (b.isValid() && b.getNorthEast().equals(b.getSouthWest())) map.setView(b.getCenter(), Math.max(map.getZoom(), 19)); else fit(b);
  }
  window.zoomToSelection = zoomToSelection;
  // ---- right-click a Contents row: Zoom to layer ----
  const menu = document.createElement('div'); menu.className = 'lyrmenu'; menu.hidden = true; document.body.appendChild(menu);
  document.addEventListener('click', () => { menu.hidden = true; });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') menu.hidden = true; });
  document.addEventListener('contextmenu', e => {
    const row = e.target.closest && e.target.closest('#layerList .lrow'); if (!row) return;
    const ref = row.dataset.path ? { path: row.dataset.path } : row.dataset.input ? { input: row.dataset.input } : null; if (!ref) return;
    e.preventDefault(); menu.innerHTML = '<button data-a="zoom">Zoom to layer</button>' + (typeof FE !== 'undefined' ? '<button data-a="sel">Zoom to selection</button>' : '');
    menu.style.left = e.clientX + 'px'; menu.style.top = e.clientY + 'px'; menu.hidden = false;
    menu.querySelector('[data-a=zoom]').onclick = () => { menu.hidden = true; zoomToLayer(ref); };
    const sb = menu.querySelector('[data-a=sel]'); if (sb) sb.onclick = () => { menu.hidden = true; zoomToSelection(); };
  });
  // ---- ribbon: Zoom to selection (Map > Navigate) and the Labels group (Map tab) ----
  const rib = document.querySelector('.ribbon'); if (!rib) return;
  const ic = d => `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#37474F" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const nav = [...rib.querySelectorAll(':scope > .grp')].find(g => g.querySelector('[data-s=full]'));
  if (nav) {
    nav.querySelector('.gb').insertAdjacentHTML('beforeend', `<button data-x="zsel" title="Zoom to the selected features">${ic('<rect x="4" y="4" width="10" height="10" fill="#E3F2FD" stroke="#1E88E5" stroke-dasharray="2 2"/><circle cx="15.5" cy="15.5" r="4.5" stroke="#1E88E5"/><path d="M19 19l3 3" stroke="#1E88E5" stroke-width="2.2"/>')}<span>Selection</span></button>`);
    nav.querySelector('[data-x=zsel]').onclick = e => { e.stopPropagation(); zoomToSelection(); };
  }
  // junction angle labels on / off (Map > Layer), and Fit roads to facilities (Design > Roads)
  const layG = [...rib.querySelectorAll(':scope > .grp')].find(x => x.dataset.rt === 'map' && /Layer/.test(x.querySelector('.gl')?.textContent || ''));
  if (layG) {
    layG.querySelector('.gb').insertAdjacentHTML('beforeend', `<button data-x="angles" title="Show / hide the junction angles on the roads">${ic('<path d="M4 20h16M4 20L15 6" stroke="#37474F"/><path d="M10 20a6 6 0 0 0-2.2-4.6" stroke="#E53935" stroke-width="2"/><text x="12.5" y="17" font-size="7" fill="#E53935" stroke="none" font-family="sans-serif">90</text>')}<span>Angles</span></button>`);
    const ab = layG.querySelector('[data-x=angles]'); const cb = document.getElementById('showAngles');
    if (cb) { ab.classList.toggle('on', cb.checked); ab.onclick = e => { e.stopPropagation(); cb.checked = !cb.checked; cb.dispatchEvent(new Event('change')); }; }
  }
  const roadsG = [...rib.querySelectorAll(':scope > .grp')].find(x => x.dataset.rt === 'design' && /Roads/.test(x.querySelector('.gl')?.textContent || ''));
  if (roadsG) {
    roadsG.querySelector('.gb').insertAdjacentHTML('beforeend', `<button data-x="fitroads" title="Design the roads again around the located facilities (exact outlines), keep your own roads, then remake the plan">${ic('<rect x="8" y="8" width="8" height="8" fill="#F3E5F5" stroke="#6a1b9a" stroke-dasharray="2 1.5"/><path d="M3 5h18M3 19h18M5 3v18M19 3v18" stroke="#8d8d8d" stroke-width="1.8"/>')}<span>Fit roads</span></button>`);
    roadsG.querySelector('[data-x=fitroads]').onclick = e => { e.stopPropagation(); window.fitRoadsToFacilities && fitRoadsToFacilities(); };
  }
  const lc = document.querySelector('.lblctl');
  if (lc) {
    const g = document.createElement('div'); g.className = 'grp'; g.dataset.rt = 'map';
    g.innerHTML = '<div class="gb"><div class="stack lblrib"></div></div><span class="gl">Labels</span>'; L.DomEvent.disableClickPropagation(g);
    const box = g.querySelector('.lblrib');
    const la = lc.querySelector('.la'), lw = lc.querySelector('.lw');
    const r1 = document.createElement('label'); r1.innerHTML = '<span>Show</span>'; r1.append(la);
    const r2 = document.createElement('label'); r2.innerHTML = '<span>For</span>'; r2.append(lw);
    box.append(r1, r2);
    const after = [...rib.querySelectorAll(':scope > .grp')].find(x => x.dataset.rt === 'map' && /Layer/.test(x.querySelector('.gl')?.textContent || ''));
    if (after) after.after(g); else rib.insertBefore(g, rib.querySelector('.rhide'));
    const cur = document.querySelector('#rtabs button.on, .rtabs button.on, [data-rt].on:not(.grp)');
    if (cur && cur.dataset.rt && cur.dataset.rt !== 'map') g.classList.add('rt-off');
    lc.closest('.leaflet-control')?.remove(); lc.remove();
  }
})();
