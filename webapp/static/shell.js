// LP Toolkit: ArcGIS Pro style shell (loaded last). Tabbed ribbon (Project, Map, Edit, Design, Analysis, View) built around the
// existing tool groups; Contents pane with the layers (visibility, transparency) and the legend; tool panes docked on the right
// next to the Project pane; status bar (scale, pointer position, selected features, edits, run); dark / light theme.
(() => {
  const $1 = s => document.querySelector(s), $all = s => [...document.querySelectorAll(s)];
  const store = { get: (k, d) => { try { const v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} } };
  const fix = () => setTimeout(() => map.invalidateSize(), 80);
  // ---------------------------------------------------------------- icons (24 px, colour coded like the tool icons)
  const S = d => `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#37474F" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const I = {
    newp: S('<path d="M3 7h6l2 2h10v10H3z" fill="#FFCC80"/><circle cx="17" cy="16" r="4.2" fill="#43A047" stroke="#fff"/><path d="M17 13.8v4.4M14.8 16h4.4" stroke="#fff" stroke-width="1.6"/>'),
    open: S('<path d="M3 6h6l2 2h10v11H3z" fill="#FFCC80"/><path d="M3 11h18" stroke="#FB8C00"/>'),
    del: S('<path d="M6 7l1 13h10l1-13z" fill="#E53935" stroke="#B71C1C"/><path d="M4 7h16M9 7V4h6v3" stroke="#B71C1C"/>'),
    save: S('<path d="M4 4h13l3 3v13H4z" fill="#1E88E5" stroke="#0D47A1"/><rect x="7" y="4" width="8" height="5" fill="#fff" stroke="#0D47A1"/><rect x="7" y="13" width="10" height="6" fill="#E3F2FD" stroke="#0D47A1"/>'),
    discard: S('<path d="M4 4h13l3 3v13H4z" fill="#fff"/><path d="M8 9l8 8M16 9l-8 8" stroke="#E53935" stroke-width="2.2"/>'),
    run: S('<circle cx="12" cy="12" r="9" fill="#43A047" stroke="#1B5E20"/><path d="M10 8l6 4-6 4z" fill="#fff" stroke="#fff"/>'),
    stop: S('<circle cx="12" cy="12" r="9" fill="#E53935" stroke="#B71C1C"/><rect x="8.5" y="8.5" width="7" height="7" fill="#fff" stroke="#fff"/>'),
    results: S('<rect x="3" y="4" width="18" height="16" rx="2" fill="#fff"/><rect x="3" y="4" width="18" height="5" rx="2" fill="#8E24AA" stroke="#8E24AA"/><path d="M9 9v11M3 14.5h18" stroke="#90A4AE"/>'),
    download: S('<path d="M12 3v11M7.5 9.5L12 14l4.5-4.5" stroke="#1E88E5" stroke-width="2"/><path d="M4 15v5h16v-5" fill="#E3F2FD"/>'),
    guide: S('<path d="M4 5c3-1 6-1 8 1 2-2 5-2 8-1v14c-3-1-6-1-8 1-2-2-5-2-8-1z" fill="#FFF8E1"/><path d="M12 6v14" stroke="#FB8C00"/>'),
    std: S('<rect x="4" y="3" width="16" height="18" rx="2" fill="#E8F5E9"/><path d="M8 8h8M8 12h8M8 16h5" stroke="#43A047" stroke-width="1.8"/>'),
    zin: S('<circle cx="10.5" cy="10.5" r="6.5" fill="#E3F2FD" stroke="#1E88E5"/><path d="M15.5 15.5L21 21" stroke="#1E88E5" stroke-width="2.4"/><path d="M8 10.5h5M10.5 8v5" stroke="#0D47A1" stroke-width="1.8"/>'),
    zout: S('<circle cx="10.5" cy="10.5" r="6.5" fill="#E3F2FD" stroke="#1E88E5"/><path d="M15.5 15.5L21 21" stroke="#1E88E5" stroke-width="2.4"/><path d="M8 10.5h5" stroke="#0D47A1" stroke-width="1.8"/>'),
    full: S('<circle cx="12" cy="12" r="8.5" fill="#E3F2FD" stroke="#1E88E5"/><path d="M3.5 12h17M12 3.5c3 3 3 14 0 17M12 3.5c-3 3-3 14 0 17" stroke="#1E88E5"/>'),
    prev: S('<path d="M15 5l-7 7 7 7" stroke="#1E88E5" stroke-width="2.4"/>'),
    nextx: S('<path d="M9 5l7 7-7 7" stroke="#1E88E5" stroke-width="2.4"/>'),
    contents: S('<rect x="3" y="4" width="18" height="16" rx="1.5" fill="#fff"/><rect x="3" y="4" width="6" height="16" fill="#1E88E5" stroke="#1E88E5"/><path d="M11.5 8h7M11.5 12h7M11.5 16h5" stroke="#90A4AE"/>'),
    pane: S('<rect x="3" y="4" width="18" height="16" rx="1.5" fill="#fff"/><rect x="15" y="4" width="6" height="16" fill="#FB8C00" stroke="#FB8C00"/>'),
    tools: S('<rect x="3" y="4" width="18" height="16" rx="1.5" fill="#fff"/><rect x="15" y="4" width="6" height="16" fill="#8E24AA" stroke="#8E24AA"/><path d="M6 9l3 3-3 3" stroke="#8E24AA"/>'),
    legend: S('<rect x="3" y="4" width="18" height="16" rx="1.5" fill="#fff"/><rect x="6" y="7" width="4" height="3" fill="#FB8C00" stroke="none"/><rect x="6" y="11" width="4" height="3" fill="#43A047" stroke="none"/><rect x="6" y="15" width="4" height="3" fill="#1E88E5" stroke="none"/><path d="M12 8.5h6M12 12.5h6M12 16.5h6" stroke="#90A4AE"/>'),
    v3d: S('<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" fill="#E3F2FD" stroke="#1E88E5"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" stroke="#1E88E5"/>'),
    sun: S('<circle cx="12" cy="12" r="4.5" fill="#FDD835" stroke="#F9A825"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" stroke="#F9A825"/>'),
    moon: S('<path d="M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z" fill="#5C6BC0" stroke="#283593"/>'),
    reset: S('<path d="M4 12a8 8 0 108-8" stroke="#1E88E5" stroke-width="2"/><path d="M4 4v5h5" stroke="#1E88E5" stroke-width="2"/>'),
    terrain: S('<path d="M2 19l6-9 4 5 3-4 7 8z" fill="#A5D6A7" stroke="#2E7D32"/><circle cx="17" cy="6" r="2" fill="#FDD835" stroke="#F9A825"/>'),
    roads: S('<path d="M8 21L11 3M16 21L13 3" stroke="#37474F" stroke-width="1.6"/><path d="M12 5v2M12 10v2M12 15v2" stroke="#FDD835" stroke-width="1.8"/>'),
    area: S('<path d="M4 6l7-3 9 5-2 11-11 2z" fill="#FFE0B2" stroke="#FB8C00" stroke-dasharray="3 2"/>'),
    redesign: S('<path d="M4 6l7-3 9 5-2 11-11 2z" fill="#E1F5FE" stroke="#039BE5"/><path d="M9 9l6 6M15 9l-6 6" stroke="#039BE5"/>'),
    chamfer: S('<path d="M4 20V9l5-5h11v16z" fill="#FFCC80"/><path d="M4 9l5-5" stroke="#E53935" stroke-width="2.2"/>'),
    update: S('<path d="M20 12a8 8 0 01-14 5.3M4 12A8 8 0 0118 6.7" stroke="#43A047" stroke-width="2"/><path d="M18 3v4h-4M6 21v-4h4" stroke="#43A047" stroke-width="2"/>'),
    audit: S('<circle cx="12" cy="12" r="9" fill="#FFF3E0" stroke="#FB8C00"/><path d="M12 7v6" stroke="#E53935" stroke-width="2.4"/><circle cx="12" cy="16.5" r="1.3" fill="#E53935" stroke="none"/>'),
    stages: S('<path d="M4 6h10M4 12h14M4 18h8" stroke="#1E88E5" stroke-width="2"/><circle cx="18" cy="6" r="2" fill="#43A047" stroke="none"/><circle cx="16" cy="18" r="2" fill="#FB8C00" stroke="none"/>'),
    ribbon: S('<rect x="3" y="4" width="18" height="6" rx="1" fill="#E3F2FD" stroke="#1E88E5"/><path d="M8 15l4 4 4-4" stroke="#1E88E5" stroke-width="2"/>')
  };
  // ---------------------------------------------------------------- theme
  const themeBtn = $1('#themeBtn');
  function setTheme(t) {
    document.documentElement.dataset.theme = t; store.set('lp_theme', t);
    themeBtn.innerHTML = t === 'dark' ? '&#9728;' : '&#9790;'; themeBtn.title = t === 'dark' ? 'Light mode' : 'Dark mode';
    $all('[data-theme-set]').forEach(b => b.classList.toggle('on', b.dataset.themeSet === t));
  }
  themeBtn.onclick = () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  // ---------------------------------------------------------------- right dock: Project / Tools
  const dock = $1('#toolDock'), panel = $1('#panel');
  function rd(which) { panel.hidden = which !== 'project'; dock.hidden = which !== 'tools'; $all('#rdock .dtabs [data-rd]').forEach(b => b.classList.toggle('on', b.dataset.rd === which)); }
  $all('#rdock .dtabs [data-rd]').forEach(b => b.onclick = () => rd(b.dataset.rd));
  function showPane(on) { document.body.classList.toggle('nopanel', !on); store.set('lp_panel', on ? '1' : '0'); fix(); }
  function showContents(on) { document.body.classList.toggle('nocontents', !on); store.set('lp_contents', on ? '1' : '0'); fix(); }
  $all('[data-close]').forEach(b => b.onclick = () => b.dataset.close === 'contents' ? showContents(false) : showPane(false));
  function showProject(tab) { showPane(true); rd('project'); if (tab) $all('#proj .tabs button').find(b => b.dataset.tab === tab)?.click(); }
  function flash(el) { if (!el) return; el.scrollIntoView({ block: 'center', behavior: 'smooth' }); el.style.outline = '2px solid var(--accent)'; el.style.outlineOffset = '3px'; setTimeout(() => { el.style.outline = ''; }, 1800); }
  // tool panes (editor / features widgets, Snapping, Modify, Attributes, History, Plot size...) dock on the right
  const isTool = n => n && n.nodeType === 1 && (n.classList.contains('widget') || (n.classList.contains('pane') && !n.classList.contains('ctxmenu')));
  const shown = () => [...dock.children].filter(n => isTool(n) && !n.hidden && getComputedStyle(n).display !== 'none');
  let lastN = 0, before = 'project';
  function updTools() {
    const n = shown().length; $1('#toolEmpty').hidden = n > 0; $1('#toolCount').textContent = n || '';
    if (n > lastN) { if (!dock.hidden) before = before; else before = 'project'; showPane(true); rd('tools'); }
    if (n === 0 && lastN > 0 && !dock.hidden) rd(before);
    lastN = n;
  }
  function adopt(n) { if (!isTool(n) || n.parentElement === dock) return; dock.append(n); updTools(); }
  [...map.getContainer().children].forEach(adopt);
  new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(adopt))).observe(map.getContainer(), { childList: true });
  let updT = null; new MutationObserver(() => { clearTimeout(updT); updT = setTimeout(updTools, 30); }).observe(dock, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'style'] });
  // ---------------------------------------------------------------- Contents pane: layers (visibility, transparency) + legend
  const ctL = $1('#ctLayers'); ctL.innerHTML = ''; ctL.append($1('#layerList'));
  window.setMapLegend = html => { $1('#ctLegend').innerHTML = html || '<p class="hint">Nothing on the map yet.</p>'; };
  if (typeof rebuildLegend === 'function') try { rebuildLegend(); } catch (e) {}
  $1('#ctSearch').oninput = e => { const q = e.target.value.trim().toLowerCase(); ctL.querySelectorAll('.lrow, .lgh').forEach(r => { r.style.display = !q || r.textContent.toLowerCase().includes(q) ? '' : 'none'; }); };
  // ---------------------------------------------------------------- ribbon: tabs over the existing groups + new groups
  const host = $1('#ribbonHost'), rib = document.querySelector('.ribbon'); host.append(rib);
  rib.querySelectorAll(':scope > .grp').forEach(g => { g.dataset.rt = g.querySelector('[data-t=measure]') ? 'map' : g.classList.contains('g-psize') ? 'design' : 'edit'; });
  const btn = (id, icon, label, tip) => `<button data-s="${id}" title="${tip}">${I[icon]}<span>${label}</span></button>`;
  function group(rt, label, html, where = 'end') {
    const g = document.createElement('div'); g.className = 'grp'; g.dataset.rt = rt; g.innerHTML = `<div class="gb">${html}</div><span class="gl">${label}</span>`;
    L.DomEvent.disableClickPropagation(g); if (where === 'start') rib.prepend(g); else rib.insertBefore(g, rib.querySelector('.rhide')); return g;
  }
  // PROJECT
  group('project', 'Project', btn('newp', 'newp', 'New', 'New project') + btn('open', 'open', 'Open', 'Open a project (list at the top)') + btn('delp', 'del', 'Delete', 'Delete this project (moved to _deleted)'));
  group('project', 'Edits', btn('psave', 'save', 'Save', 'Save edits (Ctrl+S)') + btn('pdiscard', 'discard', 'Discard', 'Discard the edits since the last save'));
  group('project', 'Toolkit', btn('prun', 'run', 'Run', 'Run the toolkit stages (2. Run)') + btn('pstop', 'stop', 'Stop', 'Stop the run') + btn('pres', 'results', 'Results', 'Maps, tables and reports (3. Results)') + btn('pdl', 'download', 'Download', 'Download the outputs (shapefiles, maps, tables)'));
  group('project', 'Help', btn('guide', 'guide', 'Guide', 'User guide') + btn('std', 'std', 'Standards', 'LUSPA planning standards'));
  // MAP
  const navG = group('map', 'Navigate', btn('zin', 'zin', 'Zoom in', 'Zoom in') + btn('zout', 'zout', 'Zoom out', 'Zoom out') + btn('full', 'full', 'Full extent', 'Zoom to the site') + btn('prev', 'prev', 'Previous', 'Previous extent') + btn('next', 'nextx', 'Next', 'Next extent'), 'start');
  const BASES = [['Esri satellite', esri], ['Google satellite', gsat], ['Google hybrid', ghyb], ['OpenStreetMap', osm]];
  const baseG = group('map', 'Basemap', `<div class="stack">${BASES.map(([n], i) => `<label><input type="radio" name="shBase" value="${i}"> ${n}</label>`).join('')}</div>`);
  navG.after(baseG);
  const layG = group('map', 'Layer', btn('contents', 'contents', 'Contents', 'Show / hide the Contents pane') + btn('legend', 'legend', 'Legend', 'Jump to the legend in Contents')); baseG.after(layG);
  group('map', 'Views', btn('v3d', 'v3d', '3D view', 'Terrain, land use and buildings by height'));
  // DESIGN (new layout)
  group('design', 'Site', btn('site', 'terrain', 'Site analysis', 'Elevation, contours, slope classes and the steep-slope reserve'));
  group('design', 'Roads', btn('droads', 'roads', 'Design roads', 'Design the roads for me (pattern, block size, plot size)') + btn('zone', 'area', 'Redesign area', 'Draw an area to redesign') + btn('redesign', 'redesign', 'Redesign', 'Lay out the drawn areas again'));
  const plotG = rib.querySelector('.grp.g-psize');
  const planG = group('design', 'Plan', btn('chamfer', 'chamfer', 'Chamfer', 'LUSPA corner truncations on every corner plot') + btn('update', 'update', 'Update plan', 'Re-make plots, land use and audit from the roads as they are now') + btn('drun', 'stages', 'Stages', 'Run single stages (2. Run)'));
  if (plotG) planG.before(plotG);
  // ANALYSIS
  group('analysis', 'Toolkit', btn('arun', 'run', 'Run', 'Run the toolkit (2. Run)') + btn('astop', 'stop', 'Stop', 'Stop the run') + btn('astages', 'stages', 'Log', 'Progress and log'));
  group('analysis', 'Review', btn('audit', 'audit', 'Audit', 'Show / hide the design audit findings') + btn('astd', 'std', 'Standards', 'LUSPA planning standards') + btn('av3d', 'v3d', '3D view', '3D view'));
  // VIEW
  group('view', 'Theme', btn('light', 'sun', 'Light', 'Light mode') + btn('dark', 'moon', 'Dark', 'Dark mode'));
  group('view', 'Panes', btn('vcont', 'contents', 'Contents', 'Show / hide Contents') + btn('vproj', 'pane', 'Project', 'Show the Project pane') + btn('vtools', 'tools', 'Tools', 'Show the Tools pane') + btn('vrib', 'ribbon', 'Ribbon', 'Collapse / expand the ribbon (or double-click a tab)'));
  group('view', 'Layout', btn('reset', 'reset', 'Reset', 'Reset the pane sizes'));
  rib.querySelector('[data-s=light]').dataset.themeSet = 'light'; rib.querySelector('[data-s=dark]').dataset.themeSet = 'dark';
  const click = sel => { const el = $1(sel); if (el) el.click(); return !!el; };
  const needP = () => { if (!P) { alert('Open or create a project first.'); return false; } return true; };
  const ACT = {
    newp: () => click('#newProj'), open: () => { const s = $1('#projSel'); s.focus(); try { s.showPicker(); } catch (e) {} }, delp: () => needP() && click('#delProj'),
    psave: () => click('.g-save [data-a=save]'), pdiscard: () => click('.g-save [data-a=discard]'),
    prun: () => needP() && showProject('run'), pstop: () => click('#stopBtn'), pres: () => needP() && showProject('results'), pdl: () => { if (!needP()) return; showProject('results'); setTimeout(() => flash($1('#dlBtn')), 150); },
    guide: () => click('#guideBtn'), std: () => click('#stdBtn'), astd: () => click('#stdBtn'),
    zin: () => map.zoomIn(), zout: () => map.zoomOut(),
    full: () => { const s = inputs.site.getLayers(); if (s.length) map.fitBounds(inputs.site.getBounds()); else if (resGroup.getLayers().length) try { map.fitBounds(L.featureGroup(resGroup.getLayers()).getBounds()); } catch (e) {} },
    prev: () => hist(-1), next: () => hist(1),
    contents: () => showContents(document.body.classList.contains('nocontents')), legend: () => { showContents(true); flash($1('#ctLegH')); },
    v3d: () => click('#v3dBtn'), av3d: () => click('#v3dBtn'),
    site: () => { if (!needP()) return; showProject('inputs'); setTimeout(() => { flash($1('#siteBtn').closest('.card')); $1('#siteBtn').click(); }, 100); },
    droads: () => { if (!needP()) return; showProject('inputs'); setTimeout(() => flash($1('#designBtn').closest('.sub')), 100); },
    zone: () => { if (!needP()) return; click('button.draw[data-kind=zones]'); }, redesign: () => needP() && click('#redesignBtn'),
    chamfer: () => { if (!needP()) return; if (!click('#chamferNow')) alert('Run the design first.'); },
    update: async () => { if (!needP()) return; try { await post(`/api/projects/${P.id}/run`, { workflow: 'design', from: 'roads', chamfer: !!$1('#chamfer')?.checked, steep: +$1('#steep').value, stream_buffer: +$1('#streamBuf').value }); showProject('run'); refreshStatus(); alert('Updating the plan from the roads (2. Run shows the progress).'); } catch (e) { alert(e.message); } },
    drun: () => needP() && showProject('run'), arun: () => needP() && showProject('run'), astop: () => click('#stopBtn'), astages: () => needP() && showProject('run'),
    audit: async () => { const L_ = (typeof LAYER_INDEX !== 'undefined' ? LAYER_INDEX : []).find(l => l.kind === 'audit'); if (!L_) return alert('No audit yet: run the design (or the audit stage).'); const on = !(results[L_.path] && resGroup.hasLayer(results[L_.path])); await toggleLayer(L_, on); $all('#layerList input[type=checkbox]').forEach(cb => { if (cb.parentElement.textContent.trim() === L_.label) cb.checked = on; }); },
    light: () => setTheme('light'), dark: () => setTheme('dark'),
    vcont: () => showContents(document.body.classList.contains('nocontents')), vproj: () => showProject(), vtools: () => { showPane(true); rd('tools'); }, vrib: () => toggleRibbon(),
    reset: () => { ['--lw', '--rw'].forEach(v => document.documentElement.style.removeProperty(v)); store.set('lp_lw', ''); store.set('lp_rw', ''); showContents(true); showPane(true); fix(); }
  };
  rib.querySelectorAll('[data-s]').forEach(b => b.onclick = () => ACT[b.dataset.s]?.());
  // basemap radios follow the map
  const syncBase = () => BASES.forEach(([, l], i) => { const r = baseG.querySelector(`input[value="${i}"]`); if (r) r.checked = map.hasLayer(l); });
  baseG.querySelectorAll('input').forEach(r => r.onchange = () => { BASES.forEach(([, l]) => map.removeLayer(l)); BASES[+r.value][1].addTo(map); BASES[+r.value][1].bringToBack(); syncBase(); });
  map.on('baselayerchange', syncBase); syncBase();
  // previous / next extent
  const ext = []; let ei = -1, jumping = false;
  map.on('moveend', () => { if (jumping) { jumping = false; return; } ext.splice(ei + 1); ext.push([map.getCenter(), map.getZoom()]); if (ext.length > 50) ext.shift(); ei = ext.length - 1; });
  function hist(d) { const j = ei + d; if (j < 0 || j >= ext.length) { alert(d < 0 ? 'No earlier map view.' : 'No later map view.'); return; } ei = j; jumping = true; map.setView(ext[j][0], ext[j][1]); }
  // tabs
  const TABS = [['project', 'Project'], ['map', 'Map'], ['edit', 'Edit'], ['design', 'Design'], ['analysis', 'Analysis'], ['view', 'View']];
  const tabsEl = $1('#rtabs'); tabsEl.innerHTML = TABS.map(([k, n]) => `<button data-rt="${k}">${n}</button>`).join('');
  function tab(k) { store.set('lp_rtab', k); tabsEl.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.rt === k)); rib.querySelectorAll(':scope > .grp').forEach(g => g.classList.toggle('rt-off', g.dataset.rt !== k)); if (host.classList.contains('collapsed')) toggleRibbon(); }
  function toggleRibbon() { host.classList.toggle('collapsed'); store.set('lp_rib2', host.classList.contains('collapsed') ? '0' : '1'); fix(); }
  tabsEl.querySelectorAll('button').forEach(b => { b.onclick = () => tab(b.dataset.rt); b.ondblclick = () => toggleRibbon(); });
  const col = document.createElement('button'); col.className = 'rcollapse'; col.title = 'Collapse the ribbon'; col.innerHTML = '&#8963;'; col.onclick = toggleRibbon; rib.append(col);
  // the Design tab is for new layouts; the existing-situation plot tools sit on Edit
  const syncWf = () => { const des = !P || P.workflow !== 'existing'; tabsEl.querySelector('[data-rt=design]').hidden = !des; if (!des && store.get('lp_rtab', 'edit') === 'design') tab('edit'); };
  const _sw = window.setWorkflow; window.setWorkflow = function (wf, save) { const r = _sw(wf, save); syncWf(); return r; };
  // ---------------------------------------------------------------- view tabs over the map
  $1('#vt3d').onclick = () => click('#v3dBtn');
  // ---------------------------------------------------------------- splitters
  $all('.split').forEach(sp => sp.onmousedown = e => {
    const which = sp.dataset.split, pane = which === 'contents' ? $1('#contents') : $1('#rdock'), v = which === 'contents' ? '--lw' : '--rw';
    const x0 = e.clientX, w0 = pane.offsetWidth; let w = w0; sp.classList.add('drag'); document.body.classList.add('noselect'); e.preventDefault();
    const mv = ev => { w = Math.max(200, Math.min(760, which === 'contents' ? w0 + ev.clientX - x0 : w0 - (ev.clientX - x0))); document.documentElement.style.setProperty(v, w + 'px'); };
    const up = () => { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); sp.classList.remove('drag'); document.body.classList.remove('noselect'); store.set(v === '--lw' ? 'lp_lw' : 'lp_rw', String(w)); fix(); };
    document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
  });
  // ---------------------------------------------------------------- status bar
  const sc = $1('#sbScale'), PRE = [500, 1000, 2500, 5000, 10000, 25000, 50000, 100000];
  const mpp = () => 40075016.686 * Math.cos(map.getCenter().lat * Math.PI / 180) / (256 * 2 ** map.getZoom());
  function fillScale() { const s = Math.round(mpp() / 0.00028); sc.innerHTML = `<option value="">1:${s.toLocaleString()}</option>` + PRE.map(v => `<option value="${v}">1:${v.toLocaleString()}</option>`).join(''); sc.value = ''; }
  sc.onchange = () => { const v = +sc.value; if (!v) return; map.setZoom(Math.round(Math.log2(40075016.686 * Math.cos(map.getCenter().lat * Math.PI / 180) / (256 * v * 0.00028)))); };
  map.on('zoomend moveend', fillScale); fillScale();
  const xy = $1('#sbXY'); map.on('mousemove', e => { const { lat, lng } = e.latlng; xy.textContent = `${Math.abs(lat).toFixed(6)}° ${lat >= 0 ? 'N' : 'S'}  ${Math.abs(lng).toFixed(6)}° ${lng >= 0 ? 'E' : 'W'}`; });
  setInterval(() => {
    let n = 0; try { const s = typeof FE !== 'undefined' && FE.selection(); n = s ? s.layers.length : 0; } catch (e) {}
    $1('#sbSel').textContent = `Selected features: ${n}`;
    const ed = $1('#sbEdit'); ed.textContent = P ? (window._dirty ? '● Unsaved edits' : 'Edits saved') : ''; ed.classList.toggle('warn', !!window._dirty);
    const st = $1('#pState'), rn = $1('#sbRun'); rn.textContent = P && st ? (st.textContent || '') : ''; rn.classList.toggle('run', !!st && st.classList.contains('run'));
    $1('#vtTitle').textContent = P ? `${P.title || P.name} · ${P.workflow === 'existing' ? 'Existing situation' : 'New layout'}` : '';
    $1('#projSel').title = P ? `Project: ${P.name}` : 'Project';
  }, 600);
  // ---------------------------------------------------------------- restore the layout
  const lw = store.get('lp_lw', ''), rw = store.get('lp_rw', '');
  if (lw) document.documentElement.style.setProperty('--lw', lw + 'px'); if (rw) document.documentElement.style.setProperty('--rw', rw + 'px');
  if (store.get('lp_contents', '1') === '0') document.body.classList.add('nocontents');
  if (store.get('lp_rib2', '1') === '0') host.classList.add('collapsed');
  setTheme(document.documentElement.dataset.theme || 'light'); rd('project'); tab(store.get('lp_rtab', 'edit')); syncWf(); updTools(); fix();
  window.Shell = { tab, rd, showProject, setTheme, showContents, showPane };
})();
