// Facilities and services (after the site analysis): the toolkit decides, or the planner ticks each facility, its number, size and location.
// Catalogue: LUSPA Revised Zoning Guidelines 2025 + the study of the planner's local plans (lp_toolkit.py FACILITY_CATALOG).
const FAC = (() => {
  let S = null, saveT = null, draw = null, curPid = null;
  const layer = L.featureGroup().addTo(map);
  const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const card = document.getElementById('facCard');
  const item = id => S.catalog.items.find(x => x.id === id);
  const cur = id => S.items[id] || { on: false, n: 0, size_ac: item(id).size };
  const nOn = id => S.sites.features.filter(f => f.properties.fac_id === id).length;

  async function load() {
    if (!P || P.workflow !== 'design') { card.hidden = true; layer.clearLayers(); return; }
    card.hidden = false; curPid = P.id; $('#facList').innerHTML = '<p class="mini">Loading the facility list...</p>';
    try { S = await api(`/api/projects/${P.id}/facilities`); } catch (e) {
      S = null; const old = /not found/i.test(e.message);
      $('#facList').innerHTML = `<p class="mini"><b>The facility list could not be loaded.</b> ${old ? 'The app server is an older version: close it and start <b>run_webapp.bat</b> again, then reload this page.' : esc(String(e.message).replace(/<[^>]+>/g, ' ').slice(0, 300))}</p>`; return; }
    if (S.mode !== 'custom' || !Object.keys(S.items).length) S.items = recItems();
    render(); drawSites();
  }
  function recItems() { const o = {}; S.catalog.items.forEach(f => o[f.id] = { on: f.rec > 0, n: f.rec, size_ac: f.size }); return o; }
  async function recatalog() {
    try { S.catalog = await api(`/api/facility_catalog?pop=${+$('#facPop').value || 0}`); } catch (e) { return alert(e.message); }
    if (S.mode === 'auto') S.items = recItems(); render(); save();
  }
  function render() {
    const auto = S.mode === 'auto';
    $$('#facMode button').forEach(b => b.classList.toggle('on', b.dataset.m === S.mode));
    $('#facPop').value = S.population || ''; $('#facPopHint').textContent = S.estimate ? `estimate from the site: ~${S.estimate.toLocaleString()} people` : 'draw the site to get an estimate';
    $('#facRec').hidden = auto;
    const q = ($('#facSearch').value || '').toLowerCase(), onlyOn = $('#facOnly').checked;
    let h = '';
    for (const g of S.catalog.groups) {
      const rows = S.catalog.items.filter(f => f.group === g).filter(f => !q || (f.name + ' ' + f.std + ' ' + f.luspa).toLowerCase().includes(q)).filter(f => !onlyOn || (auto ? f.rec > 0 : cur(f.id).on) || nOn(f.id));
      if (!rows.length) continue;
      const k = S.catalog.items.filter(f => f.group === g && (auto ? f.rec > 0 : cur(f.id).on)).length;
      h += `<details class="facg" open><summary>${esc(g)} <span class="mini">${k} ticked</span></summary><table class="factbl"><tbody>`;
      for (const f of rows) {
        const c = auto ? { on: f.rec > 0, n: f.rec, size_ac: f.size } : cur(f.id), here = nOn(f.id), dis = auto ? 'disabled' : '';
        const nTxt = f.id === 'sa' ? 'title="S.A: at least this many; more are added until every home is within 500 m"' : f.id === 'pos' ? 'title="P.O.S sites; total open space = number x size (LUSPA 1.2 ac per 1,000 people)"' : '';
        h += `<tr data-id="${f.id}" class="${c.on ? 'on' : ''}"><td class="fcell">
          <div class="fl1"><label><input type="checkbox" class="fon" ${c.on ? 'checked' : ''} ${dis}> <b>${esc(f.name)}</b></label> <span class="lus">${esc(f.luspa)}</span></div>
          <div class="fl2"><span class="mini">No.</span><input type="number" class="fn" min="0" max="99" step="1" value="${c.n}" ${dis} ${nTxt} aria-label="Number">
            ${f.id === 'mixed_use' ? '<span class="mini">(on / off)</span>' : `<span class="mini">Size</span><input type="number" class="fs" min="0.01" max="500" step="0.05" value="${c.size_ac}" ${dis} aria-label="Site size in acres"><span class="mini">ac</span>
            <button class="ghost fpt" title="Click on the map where it should go (a site of this size is shaped there)">Point</button><button class="ghost fpg" title="Draw the exact site outline">Outline</button>`}
            ${here ? `<span class="badge ok fhere" title="Located on the map (click to remove)">${here} on map &times;</span>` : ''}</div>
          <div class="mini fstd">${esc(f.std)}</div></td></tr>`;
      }
      h += '</tbody></table></details>';
    }
    $('#facList').innerHTML = h || '<p class="mini">Nothing matches.</p>';
    summary();
  }
  function summary() {
    let n = 0, ac = 0;
    for (const f of S.catalog.items) { const c = S.mode === 'auto' ? { on: f.rec > 0, n: f.rec, size_ac: f.size } : cur(f.id); if (c.on && c.n > 0 && f.id !== 'mixed_use') { n += c.n; ac += c.n * (+c.size_ac || 0); } }
    $('#facSum').textContent = `${n} facility sites, about ${ac.toFixed(1)} ac` + (S.estimate ? ` for ~${(+$('#facPop').value || S.estimate).toLocaleString()} people` : '') + (S.sites.features.length ? ` | ${S.sites.features.length} located on the map` : '') + (S.mode === 'auto' ? ' | the toolkit decides (recommended for the population)' : '');
  }
  function save(keep) {
    clearTimeout(saveT); const pid = P.id;
    saveT = setTimeout(() => post(`/api/projects/${pid}/facilities`, { mode: S.mode, population: +$('#facPop').value || null, items: S.mode === 'custom' ? S.items : {}, keep_decisions: !!keep })
      .then(() => { $('#facState').textContent = S.mode === 'custom' ? 'your list (saved)' : 'toolkit decides (saved)'; }).catch(e => alert(e.message)), 500);
  }
  // ---------- events
  const ready = () => { if (S) return true; alert('The facility list is not loaded (see the message in the card).'); return false; };
  $$('#facMode button').forEach(b => b.onclick = () => {
    if (!ready()) return;
    if (S.mode === b.dataset.m) return; S.mode = b.dataset.m;
    if (S.mode === 'custom' && !Object.values(S.items).some(x => x.on)) S.items = recItems();
    render(); save();
  });
  $('#facPop').onchange = () => { if (!ready()) return; S.population = +$('#facPop').value || null; recatalog(); };
  $('#facRec').onclick = () => { if (!ready()) return; S.items = recItems(); render(); save(); };
  $('#facSearch').oninput = () => S && render(); $('#facOnly').onchange = () => S && render();
  $('#facList').addEventListener('change', e => {
    const tr = e.target.closest('tr[data-id]'); if (!tr || S.mode !== 'custom') return; const id = tr.dataset.id, c = { ...cur(id) };
    if (e.target.classList.contains('fon')) { c.on = e.target.checked; if (c.on && !(c.n > 0)) { c.n = Math.max(1, item(id).rec); tr.querySelector('.fn').value = c.n; } }
    if (e.target.classList.contains('fn')) { c.n = Math.max(0, Math.round(+e.target.value || 0)); c.on = c.n > 0; tr.querySelector('.fon').checked = c.on; }
    if (e.target.classList.contains('fs')) c.size_ac = Math.max(0.01, +e.target.value || item(id).size);
    S.items[id] = c; tr.classList.toggle('on', c.on); summary(); save();
  });
  $('#facList').addEventListener('click', e => {
    const tr = e.target.closest('tr[data-id]'); if (!tr) return; const id = tr.dataset.id;
    if (e.target.classList.contains('fpt') || e.target.classList.contains('fpg')) startDraw(id, e.target.classList.contains('fpt') ? 'point' : 'polygon');
    if (e.target.classList.contains('fhere')) { S.sites.features = S.sites.features.filter(f => f.properties.fac_id !== id); saveSites(); }
  });
  // ---------- located sites on the map
  const siteStyle = { color: '#7b1fa2', weight: 2.5, dashArray: '6 4', fillColor: '#ce93d8', fillOpacity: .35 };
  function drawSites() {
    layer.clearLayers(); if (!S) return;
    L.geoJSON(S.sites, {
      style: () => siteStyle,
      pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 9, color: '#7b1fa2', weight: 3, fillColor: '#ce93d8', fillOpacity: .9 }),
      onEachFeature: (f, l) => {
        const it = item(f.properties.fac_id), nm = it ? it.name : f.properties.fac_id;
        l.bindTooltip(`${esc(nm)}${f.geometry.type === 'Point' ? ` (${f.properties.size_ac || cur(f.properties.fac_id).size_ac} ac site shaped here)` : ''}`, { direction: 'top' });
        l.on('click', ev => { L.DomEvent.stop(ev); const b = document.createElement('div'); b.innerHTML = `<b>${esc(nm)}</b><br><button class="ghost danger">Remove from the map</button>`;
          b.querySelector('button').onclick = () => { S.sites.features = S.sites.features.filter(x => x !== f); map.closePopup(); saveSites(); }; L.popup().setLatLng(ev.latlng).setContent(b).openOn(map); });
      }
    }).eachLayer(l => layer.addLayer(l));
  }
  function startDraw(id, kind) {
    if (draw) draw.h.disable();
    const h = kind === 'point' ? new L.Draw.Marker(map, { icon: L.divIcon({ className: 'facpin', html: '', iconSize: [16, 16] }) }) : new L.Draw.Polygon(map, { shapeOptions: siteStyle, showArea: true });
    draw = { id, kind, h }; h.enable(); alert(`${item(id).name}: ${kind === 'point' ? 'click on the map where it should go' : 'draw its outline (double-click to finish)'} (Esc cancels)`);
  }
  map.on(L.Draw.Event.CREATED, e => {
    if (!draw) return; const it = item(draw.id), gj = e.layer.toGeoJSON();
    gj.properties = { fac_id: draw.id, name: it.name, size_ac: +(cur(draw.id).size_ac || it.size) };
    S.sites.features.push(gj);
    if (S.mode === 'custom') { const c = { ...cur(draw.id) }; if (!c.on || c.n < nOn(draw.id)) { c.on = true; c.n = Math.max(c.n || 0, nOn(draw.id)); S.items[draw.id] = c; save(); } }
    draw = null; saveSites();
  });
  map.on('draw:drawstop', () => { setTimeout(() => { draw = null; }, 0); });
  async function saveSites() { try { await post(`/api/projects/${P.id}/facility_sites`, S.sites); } catch (e) { alert(e.message); } drawSites(); render(); }

  // ---------- facilities that did not fit: the run pauses after land use, the planner chooses per item
  let shownFor = '', sawRun = false;
  async function status(s) {
    const box = document.getElementById('facShort'); if (!box) return;
    if (s.running) { sawRun = true; }
    const justPaused = sawRun && !s.running; if (!s.running) sawRun = false;
    if (!s.paused) { box.hidden = true; shownFor = ''; return; }
    const key = P.id + '|' + (s.log || '').length; if (shownFor === key) return; shownFor = key;
    let sf; try { sf = await api(`/api/projects/${P.id}/shortfall`); } catch (e) { return; }
    if (!sf.items?.length) { box.hidden = true; return; }
    box.hidden = false;
    if (justPaused) { document.querySelector('.tabs button[data-tab="run"]')?.click(); if (window.Shell && Shell.showProject) Shell.showProject(); }
    if (justPaused) alert(`The run paused: ${sf.items.length} facilit${sf.items.length > 1 ? 'ies' : 'y'} did not fit. Choose for each in 2. Run, then continue.`);
    box.innerHTML =`<b>The run paused: ${sf.items.length} facilit${sf.items.length > 1 ? 'ies' : 'y'} did not fit on the land left over after subdivision.</b>
      <p class="mini">Choose for each, then continue (the plan is re-run from land use). Tip for large sites: locate them on the map in <b>Facilities and services</b> and re-run from the roads, so the roads go around them.</p>
      <table class="factbl short"><thead><tr><th>Facility</th><th>Size</th><th>Would take</th><th>Choice</th></tr></thead><tbody>` +
      sf.items.map(x => `<tr data-k="${esc(x.id)}#${x.k}"><td><b>${esc(x.name)}</b><div class="mini">${esc(x.why)}</div></td><td>${x.size_ac} ac</td><td>${x.plots} residential plot${x.plots === 1 ? '' : 's'}${x.plots_ac ? ` (${x.plots_ac} ac)` : ''}</td>
        <td><select class="sdec"><option value="take">Take the plots</option><option value="skip">Skip it</option><option value="reduce">Reduce the size to</option></select> <input class="sred" type="number" step="0.05" min="0.05" value="${Math.max(0.05, +(x.size_ac * 0.6).toFixed(2))}" style="width:70px" hidden> <span class="mini sredu" hidden>ac</span></td></tr>`).join('') +
      `</tbody></table><div class="row"><button id="facGo">Continue from land use</button></div>`;
    box.querySelectorAll('.sdec').forEach(sel => sel.onchange = () => { const r = sel.value === 'reduce'; sel.parentElement.querySelector('.sred').hidden = !r; sel.parentElement.querySelector('.sredu').hidden = !r; });
    box.querySelector('#facGo').onclick = async () => {
      const decisions = {};
      box.querySelectorAll('tr[data-k]').forEach(tr => { const v = tr.querySelector('.sdec').value; decisions[tr.dataset.k] = v === 'reduce' ? `reduce:${+tr.querySelector('.sred').value || 0.1}` : v; });
      try { await post(`/api/projects/${P.id}/shortfall`, { decisions, steep: +$('#steep').value, chamfer: !!$('#chamfer')?.checked }); box.hidden = true; refreshStatus(); } catch (e) { alert(e.message); }
    };
  }
  // reload when another project is opened
  setInterval(() => { if (P && (P.id !== curPid || (P.workflow === 'design') === card.hidden)) load(); }, 800);
  return { load, status };
})();
window.FAC = FAC;
