// Suitability: where could a facility go? (user 2026-11-22) Heat map (0-100) from the site analysis + planning standards, and the best
// candidate sites of the required size with their reasons. The planner accepts (becomes a located facility; on a plan, optionally applied
// to the plots now) or rejects (not suggested again) each one.
const SUIT = (() => {
  const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const pane = document.createElement('div'); pane.className = 'pane suitpane'; pane.hidden = true; map.getContainer().appendChild(pane);
  L.DomEvent.disableClickPropagation(pane); L.DomEvent.disableScrollPropagation(pane);
  let CAT = null, R = null, heat = null, drag = null, reloc = null; const candL = L.featureGroup().addTo(map); const SVGR = L.svg({ padding: 0.5 });
  const CSTYLE = { color: '#6a1b9a', weight: 3, dashArray: '6 4', fillColor: '#ce93d8', fillOpacity: .25 };
  // ---- relocate: drag a suggested site, or Relocate then click where it should go; the site is scored again where it is dropped ----
  const shift = (ll, dLat, dLng) => Array.isArray(ll) ? ll.map(x => shift(x, dLat, dLng)) : L.latLng(ll.lat + dLat, ll.lng + dLng);
  function drawCand(c) {
    if (c._lay) candL.removeLayer(c._lay);
    const lay = L.geoJSON(c.geometry, { style: c._done === 'accepted' ? { color: '#2e7d32', weight: 3, fillColor: '#a5d6a7', fillOpacity: .35 } : CSTYLE, renderer: SVGR }).addTo(candL);
    lay.bindTooltip(`#${c.rank}  ${c.score}`, { permanent: true, direction: 'center', className: 'suittip' }); c._lay = lay;
    const poly = lay.getLayers()[0];
    if (poly && !c._done) {
      poly.on('mouseover', () => { if (!drag) poly.getElement && poly.getElement() && (poly.getElement().style.cursor = 'grab'); });
      poly.on('mousedown', e => { if (c._done || reloc || e.originalEvent.button !== 0) return; L.DomEvent.stop(e); map.dragging.disable(); drag = { c, poly, start: e.latlng, orig: poly.getLatLngs(), moved: false }; map.getContainer().style.cursor = 'grabbing'; });
    }
  }
  map.on('mousemove', e => { if (!drag) return; drag.poly.setLatLngs(shift(drag.orig, e.latlng.lat - drag.start.lat, e.latlng.lng - drag.start.lng)); drag.moved = true; });
  let swallow = false;
  map.on('mouseup', async () => { if (!drag) return; const d = drag; drag = null; map.dragging.enable(); map.getContainer().style.cursor = ''; if (d.moved) { swallow = true; setTimeout(() => swallow = false, 400); await rescore(d.c, d.poly.toGeoJSON().geometry); } });
  map.getContainer().addEventListener('click', async ev => {               // capture phase: plots and other layers must not swallow the click
    if (swallow) { swallow = false; ev.preventDefault(); ev.stopPropagation(); return; }      // the click at the end of a drag: no popup from the layer underneath
    if (!reloc || ev.target.closest('.leaflet-control, .pane, .suitpane')) return; ev.preventDefault(); ev.stopPropagation();
    const e = { latlng: map.mouseEventToLatLng(ev) };
    const c = reloc; reloc = null; map.getContainer().style.cursor = '';
    const b = c._lay.getBounds().getCenter(); const poly = c._lay.getLayers()[0];
    poly.setLatLngs(shift(poly.getLatLngs(), e.latlng.lat - b.lat, e.latlng.lng - b.lng)); await rescore(c, poly.toGeoJSON().geometry);
  }, true);
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && reloc) { reloc = null; map.getContainer().style.cursor = ''; render(); } });
  async function rescore(c, geom) {
    $p('.smsg').textContent = `Scoring #${c.rank} where it was placed...`;
    try {
      const r = await post(`/api/projects/${P.id}/suitability/score`, { fid: R.facility, size_ac: R.size_ac, geometry: geom });
      Object.assign(c, { score: r.score, area_ac: r.area_ac, plots: r.plots || [], reasons: r.reasons || [], geometry: r.geometry || geom, _relocated: true });
      $p('.smsg').textContent = `#${c.rank} relocated: score ${r.score}` + (R.stage === 'plan' ? ` (${(r.plots || []).length} plots, ${r.area_ac} ac)` : '') + '.';
    } catch (er) { $p('.smsg').textContent = er.message; }
    drawCand(c); render();
  }
  pane.innerHTML = `<div class="ph"><b>Suitability: where could it go?</b><button class="ghost sclose" title="Close">&times;</button></div>
    <p class="hint">Scores the site for the chosen facility from the site analysis (slope, high / low ground, streams, steep land) and the planning standards (road access by class, distances from schools, clinics, fuel, homes, water). Before the roads it suggests areas on the bare site; on a plan it suggests groups of plots. Accept a site to make it a located facility, or reject it.</p>
    <label class="lbl">Facility</label><select class="sfac"></select>
    <div class="row"><span class="mini">Site size</span><input class="ssize" type="number" min="0.02" step="0.05" style="width:80px"><span class="mini">ac</span>
      <span class="mini">Suggestions</span><input class="sn" type="number" min="1" max="30" step="1" value="5" style="width:60px" title="How many sites to suggest (1-30)"></div>
    <div class="mini sstd"></div>
    <div class="row"><button class="sgo">Find sites</button><button class="ghost sclr" title="Forget the sites you rejected for this facility">Clear rejected</button></div>
    <div class="row"><label class="tl"><input type="checkbox" class="sheat" checked> Heat map</label><input class="sop" type="range" min="0.1" max="1" step="0.05" value="0.7" title="Heat map opacity" style="width:110px">
      <label class="tl splanrow" hidden><input type="checkbox" class="sapply" checked> Apply accepted sites to the plan now</label></div>
    <div class="slegend mini"><span class="sbar"></span> 0 unsuitable &nbsp; 100 best &nbsp; (blank = excluded: stream, steep, roads, required distances)</div>
    <div class="smsg mini"></div><div class="slist"></div>
    <div class="row sfitrow"><button class="ghost sfit" title="Design the roads again around every located facility (exact outlines), keep your own roads, then remake the plan">Fit roads to facilities</button></div>`;
  const $p = s => pane.querySelector(s);
  async function open() {
    if (!P) return alert('Choose a project first.');
    pane.hidden = false; if (window.Shell && Shell.showPane) try { Shell.showPane(true); Shell.rd && Shell.rd('tools'); } catch (e) {}
    if (!CAT) {
      try { CAT = await api('/api/facility_catalog?pop=0'); } catch (e) { $p('.smsg').textContent = e.message; return; }
      $p('.sfac').innerHTML = CAT.groups.map(g => `<optgroup label="${esc(g)}">${CAT.items.filter(f => f.group === g && f.id !== 'mixed_use').map(f => `<option value="${f.id}">${esc(f.name)}</option>`).join('')}</optgroup>`).join('');
      $p('.sfac').value = 'clinic'; pick();
    }
  }
  function pick() { const f = CAT.items.find(x => x.id === $p('.sfac').value); if (!f) return; $p('.ssize').value = f.size; $p('.sstd').textContent = 'Standard: ' + f.std; }
  function clear() { candL.clearLayers(); if (heat) { map.removeLayer(heat); heat = null; } $p('.slist').innerHTML = ''; R = null; }
  async function find() {
    clear(); const fid = $p('.sfac').value; $p('.smsg').textContent = 'Scoring the site...'; $p('.sgo').disabled = true;
    try { R = await post(`/api/projects/${P.id}/suitability`, { fid, size_ac: +$p('.ssize').value || null, n: Math.max(1, Math.min(30, Math.round(+$p('.sn').value || 5))) }); }
    catch (e) { $p('.smsg').textContent = e.message; $p('.sgo').disabled = false; return; }
    $p('.sgo').disabled = false;
    const st = R.stage === 'plan' ? 'on the plan (groups of plots)' : 'on the bare site (before the roads)';
    $p('.smsg').innerHTML = `${esc(R.name)}, ${R.size_ac} ac, ${st}. Weights: ${Object.entries(R.weights).map(([k, v]) => `${k} ${v} %`).join(', ')}${R.terrain ? '' : '. No elevation model yet: run the site analysis for slope and high / low ground.'}`;
    $p('.splanrow').hidden = R.stage !== 'plan';
    heat = L.imageOverlay(`/api/projects/${P.id}/file?f=${encodeURIComponent(R.heat.png)}&t=${Date.now()}`, R.heat.bounds, { opacity: +$p('.sop').value, interactive: false });
    if ($p('.sheat').checked) heat.addTo(map);
    if (!R.candidates.length) { $p('.slist').innerHTML = '<p class="mini">No site of this size passes the rules here. Try a smaller size, or clear the rejected sites.</p>'; return; }
    R.candidates.forEach(drawCand);
    try { map.fitBounds(candL.getBounds(), { padding: [40, 40] }); } catch (e) {}
    render();
  }
  function render() {
    $p('.slist').innerHTML = R.candidates.map(c => `<div class="scard${c._done ? ' done' : ''}" data-r="${c.rank}"><div class="sh"><b>#${c.rank}</b> <span class="sscore" style="background:${col(c.score)}">${c.score}</span> <span class="mini">${c.area_ac} ac${c.plots.length ? ` · ${c.plots.length} plots` : ''}</span>${c._relocated ? ' <span class="badge">relocated</span>' : ''}${c._done ? ` <span class="badge ${c._done === 'accepted' ? 'ok' : 'bad'}">${c._done}</span>` : ''}</div>
      <ul>${c.reasons.map(x => `<li class="${x.ok ? 'ok' : 'warn'}">${x.ok ? '✓' : '⚠'} ${esc(x.text)}</li>`).join('')}</ul>
      ${c._done ? '' : `<div class="row"><button class="ghost szoom">Zoom</button><button class="sacc">Accept</button><button class="ghost srel${reloc === c ? ' on' : ''}" title="Move the site: click where it should go (or drag it on the map)">Relocate</button><button class="ghost srej">Reject</button></div>`}</div>`).join('') +
      '<p class="mini">Tip: drag any suggested site on the map to move it; it is scored again where you drop it.</p>';
  }
  const col = v => v >= 80 ? '#1a9850' : v >= 65 ? '#91cf60' : v >= 50 ? '#fee08b' : v >= 35 ? '#fc8d59' : '#d73027';
  pane.addEventListener('click', async e => {
    if (e.target.classList.contains('sclose')) { pane.hidden = true; clear(); return; }
    if (e.target.classList.contains('sgo')) return find();
    if (e.target.classList.contains('sfit')) { window.fitRoadsToFacilities && fitRoadsToFacilities(); return; }
    if (e.target.classList.contains('sclr')) { await post(`/api/projects/${P.id}/suitability/clear_rejected`, { fid: $p('.sfac').value }); alert('Rejected sites for this facility forgotten.'); return; }
    const card = e.target.closest('.scard'); if (!card || !R) return; const c = R.candidates.find(x => x.rank === +card.dataset.r); if (!c) return;
    if (e.target.classList.contains('szoom')) { map.fitBounds(c._lay.getBounds(), { padding: [60, 60] }); return; }
    if (e.target.classList.contains('sacc')) {
      const apply = R.stage === 'plan' && $p('.sapply').checked;
      try { const r = await post(`/api/projects/${P.id}/suitability/accept`, { fid: R.facility, size_ac: R.size_ac, geometry: c.geometry, plots: c.plots, apply_now: apply });
        c._done = 'accepted'; drawCand(c);
        alert(`${R.name} #${c.rank} accepted: added to the located facilities` + (apply ? (r.applied_plots ? ` and ${r.applied_plots} plots now have this use (Undo on the plots layer reverses it).` : ' (no residential plots under it to change).') : '. It is reserved when the roads are designed, or given this use on the next run.'));
        if (window.FAC) FAC.load(); if (apply && typeof reloadKinds === 'function') reloadKinds(['plots_design']);
      } catch (er) { alert(er.message); }
      render(); return;
    }
    if (e.target.classList.contains('srel')) {
      reloc = reloc === c ? null : c; map.getContainer().style.cursor = reloc ? 'crosshair' : ''; render();
      if (reloc) alert(`Relocate #${c.rank}: click on the map where it should go, or drag the site (Esc cancels).`); return;
    }
    if (e.target.classList.contains('srej')) {
      try { await post(`/api/projects/${P.id}/suitability/reject`, { fid: R.facility, geometry: c.geometry }); } catch (er) { return alert(er.message); }
      c._done = 'rejected'; candL.removeLayer(c._lay); render();
    }
  });
  pane.addEventListener('change', e => {
    if (e.target.classList.contains('sfac')) { pick(); clear(); $p('.smsg').textContent = ''; }
    if (e.target.classList.contains('sheat') && heat) { e.target.checked ? heat.addTo(map) : map.removeLayer(heat); }
  });
  pane.addEventListener('input', e => { if (e.target.classList.contains('sop') && heat) heat.setOpacity(+e.target.value); });
  // ribbon: Analysis > Siting > Suitability
  const rib = document.querySelector('.ribbon');
  if (rib) {
    const g = document.createElement('div'); g.className = 'grp'; g.dataset.rt = 'analysis';
    g.innerHTML = `<div class="gb"><button data-x="suit" title="Where could a facility go? Suitability map and suggested sites"><svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" fill="#E8F5E9" stroke="#43A047"/><rect x="5" y="5" width="6" height="6" fill="#d73027" stroke="none" opacity=".7"/><rect x="11" y="11" width="8" height="8" fill="#1a9850" stroke="none" opacity=".8"/><path d="M15 6.5a2.5 2.5 0 1 1 0 .01M15 9v3" stroke="#6a1b9a" stroke-width="1.8"/></svg><span>Suitability</span></button></div><span class="gl">Siting</span>`;
    L.DomEvent.disableClickPropagation(g); rib.insertBefore(g, rib.querySelector('.rhide'));
    const cur = document.querySelector('#rtabs button.on'); if (cur && cur.dataset.rt !== 'analysis') g.classList.add('rt-off');
    g.querySelector('[data-x=suit]').onclick = e => { e.stopPropagation(); open(); };
  }
  return { open, state: () => R };
})();
window.SUIT = SUIT;
