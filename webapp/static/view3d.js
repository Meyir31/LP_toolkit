// LP Toolkit: 3D view of the planning area (MapLibre GL): terrain from the project DEM, satellite image,
// land use / plots draped on the terrain, roads, site boundary and buildings extruded to their height.
const View3D = (() => {
  const LIB = 'https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl';
  let m = null, pid = null, libP = null, nBld = { db: 0, est: 0 };
  const el = id => document.getElementById(id);
  function lib() {
    if (window.maplibregl) return Promise.resolve();
    if (!libP) libP = new Promise((ok, no) => {
      const c = document.createElement('link'); c.rel = 'stylesheet'; c.href = LIB + '.css'; document.head.appendChild(c);
      const s = document.createElement('script'); s.src = LIB + '.js'; s.onload = ok; s.onerror = () => no(new Error('could not load the 3D library (internet needed the first time)')); document.head.appendChild(s);
    });
    return libP;
  }
  const colOf = (use, design) => { const code = design ? DESIGN_LUSPA[use] : EXIST_LUSPA[use]; const c = LUSPA[code || (use ? 'CC' : 'VAC')] || LUSPA.VAC; return c[1]; };
  async function gj(path) { return api(`/api/projects/${P.id}/geojson?f=${encodeURIComponent(path)}`); }
  function siteFC() { const s = inputs.site.getLayers()[0]; return s ? { type: 'FeatureCollection', features: [s.toGeoJSON()] } : { type: 'FeatureCollection', features: [] }; }
  async function open() {
    if (!P) return alert('Choose a project first.');
    el('v3d').hidden = false; el('v3msg').textContent = 'Loading the 3D view...';
    try { await lib(); } catch (e) { el('v3msg').textContent = e.message; return; }
    if (m && pid !== P.id) { m.remove(); m = null; }
    if (!m) build(); else m.resize();
  }
  function build() {
    pid = P.id;
    const b = inputs.site.getLayers().length ? inputs.site.getBounds() : map.getBounds();
    m = new maplibregl.Map({
      container: 'v3map', maxPitch: 85, attributionControl: { compact: true },
      style: { version: 8,
        sources: {
          sat: { type: 'raster', tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'], tileSize: 256, maxzoom: 19, attribution: 'Esri World Imagery' },
          dem: { type: 'raster-dem', tiles: [location.origin + `/api/projects/${encodeURIComponent(P.id)}/dem/{z}/{x}/{y}.png`], tileSize: 256, encoding: 'terrarium', maxzoom: 14 },
        },
        layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#dfe6ec' } }, { id: 'sat', type: 'raster', source: 'sat' },
          { id: 'hill', type: 'hillshade', source: 'dem', layout: { visibility: 'none' }, paint: { 'hillshade-exaggeration': .6, 'hillshade-shadow-color': '#2b2b2b' } }],
        terrain: { source: 'dem', exaggeration: +el('v3ex').value },
        sky: { 'sky-color': '#9cc3e6', 'horizon-color': '#e8eef4', 'fog-color': '#e8eef4', 'sky-horizon-blend': .5, 'horizon-fog-blend': .6 } },
      bounds: [[b.getWest(), b.getSouth()], [b.getEast(), b.getNorth()]], fitBoundsOptions: { padding: 40 }, pitch: 60, bearing: -20,
    });
    m.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    m.boxZoom.disable();                                            // Shift+drag is used for tilting
    m.getCanvasContainer().addEventListener('contextmenu', e => e.preventDefault());
    m.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');
    m.on('load', loadData);
    // middle-button drag or Shift+left-drag: tilt + turn (right-drag does the same through MapLibre); left-drag pans
    const cv = m.getCanvasContainer(); let orb = null;
    cv.addEventListener('mousedown', e => { if (!(e.button === 1 || (e.button === 0 && e.shiftKey))) return; orb = { x: e.clientX, y: e.clientY }; e.preventDefault(); e.stopPropagation(); }, true);
    window.addEventListener('mousemove', e => { if (!orb) return; const dx = e.clientX - orb.x, dy = e.clientY - orb.y; orb = { x: e.clientX, y: e.clientY };
      m.jumpTo({ bearing: m.getBearing() + dx * 0.4, pitch: Math.max(0, Math.min(85, m.getPitch() - dy * 0.35)) }); });
    window.addEventListener('mouseup', () => orb = null);
    m.on('error', e => { const t = String(e.error?.message || e.error || ''); console.warn('3D:', t); if (/dem\//.test(e.sourceId === 'dem' || e.sourceId === 'hs' ? 'dem/' : t)) el('v3msg').textContent = 'Elevation tiles could not be loaded: the terrain is shown flat.'; else if (!m.loaded()) el('v3msg').textContent = '3D view problem: ' + t.slice(0, 160); });
  }
  async function loadData() {
    try {
      const L_ = k => LAYER_INDEX.find(l => l.kind === k);
      const plots = L_('plots') || L_('plots_design'), design = !L_('plots') && !!L_('plots_design'), roads = L_('roads');
      const sites = design ? L_('reserves') : null;                // facility / open-space sites (P.O.S, schools on leftover land ...) live in their own layer
      const [sc, pf, rf, sf] = await Promise.all([api(`/api/projects/${P.id}/scene3d`), plots ? gj(plots.path) : null, roads ? gj(roads.path) : null, sites ? gj(sites.path) : null]);
      if (pf && sf) pf.features.push(...sf.features.filter(f => f.properties && f.properties.use && f.properties.use !== 'DROP'));
      if (pf) { pf.features.forEach(f => f.properties._col = colOf(design ? f.properties.use : f.properties.ex_use, design));
        m.addSource('plots', { type: 'geojson', data: pf });
        m.addLayer({ id: 'plots', type: 'fill', source: 'plots', paint: { 'fill-color': ['get', '_col'], 'fill-opacity': .55 } });
        m.addLayer({ id: 'plots-l', type: 'line', source: 'plots', paint: { 'line-color': '#222', 'line-width': .6 } }); }
      if (rf) { m.addSource('roads', { type: 'geojson', data: rf }); m.addLayer({ id: 'roads', type: 'fill', source: 'roads', paint: { 'fill-color': '#8d8d8d', 'fill-opacity': .65 } }); }
      m.addSource('site', { type: 'geojson', data: siteFC() });
      m.addLayer({ id: 'site', type: 'line', source: 'site', paint: { 'line-color': '#ff1744', 'line-width': 3 } });
      const B = sc.buildings; nBld = { db: 0, est: 0 };
      B.features.forEach(f => { const p = f.properties; p._col = colOf(p.ex_use || p.use, false); p.h_source === 'estimate' ? nBld.est++ : nBld.db++; });
      m.addSource('bld', { type: 'geojson', data: B });
      m.addLayer({ id: 'bld', type: 'fill-extrusion', source: 'bld', paint: { 'fill-extrusion-color': ['get', '_col'], 'fill-extrusion-height': ['*', ['get', 'height_m'], +el('v3hx').value], 'fill-extrusion-base': 0, 'fill-extrusion-opacity': .92 } });
      m.on('click', 'bld', e => { const p = e.features[0].properties;
        new maplibregl.Popup({ maxWidth: '260px' }).setLngLat(e.lngLat).setHTML(`<b>${p.ex_use || p.use || 'Building'}</b><br>${p.storeys} storey(s), about ${p.height_m} m<br><span style="color:#667">height: ${p.h_source}${p.height && p.height !== 'null' ? ' (' + p.height + ')' : ''}<br>footprint ${Math.round(p.area_m2)} m2</span>`).addTo(m); });
      m.on('mouseenter', 'bld', () => m.getCanvas().style.cursor = 'pointer'); m.on('mouseleave', 'bld', () => m.getCanvas().style.cursor = '');
      el('v3msg').innerHTML = `Terrain: ${sc.dem || 'not available (flat)'}<br>Buildings: ${B.features.length} (${nBld.db} with height data, ${nBld.est} estimated at 3.2 m per storey)`;
      applyToggles(); colourMode();
    } catch (e) { el('v3msg').textContent = 'Could not load the layers: ' + e.message; }
  }
  function applyToggles() {
    if (!m || !m.isStyleLoaded()) return;
    const vis = (id, on) => m.getLayer(id) && m.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
    vis('sat', el('v3sat').checked); vis('hill', el('v3hs').checked); vis('plots', el('v3pl').checked); vis('plots-l', el('v3pl').checked);
    vis('roads', el('v3rd').checked); vis('bld', el('v3bd').checked); vis('site', el('v3st').checked);
  }
  function colourMode() {
    if (!m?.getLayer('bld')) return;
    m.setPaintProperty('bld', 'fill-extrusion-color', el('v3col').value === 'height'
      ? ['interpolate', ['linear'], ['get', 'storeys'], 1, '#ffffb2', 2, '#fecc5c', 3, '#fd8d3c', 5, '#f03b20', 8, '#bd0026']
      : el('v3col').value === 'white' ? '#f2f2f2' : ['get', '_col']);
    el('v3leg').innerHTML = el('v3col').value === 'height' ? [1, 2, 3, 5, 8].map((s, i) => `<span><i style="background:${['#ffffb2', '#fecc5c', '#fd8d3c', '#f03b20', '#bd0026'][i]}"></i>${s}${i === 4 ? '+' : ''}</span>`).join('') + ' <span class="mini">storeys</span>' : el('v3col').value === 'use' ? '<span class="mini">LUSPA colour of the building use</span>' : '';
  }
  document.addEventListener('DOMContentLoaded', () => {
    el('v3dBtn').onclick = open;
    el('v3x').onclick = () => el('v3d').hidden = true;
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !el('v3d').hidden) el('v3d').hidden = true; });
    ['v3sat', 'v3hs', 'v3pl', 'v3rd', 'v3bd', 'v3st'].forEach(id => el(id).onchange = applyToggles);
    el('v3ex').oninput = () => { el('v3exv').textContent = el('v3ex').value + 'x'; m?.setTerrain({ source: 'dem', exaggeration: +el('v3ex').value }); };
    el('v3hx').oninput = () => { el('v3hxv').textContent = el('v3hx').value + 'x'; m?.getLayer('bld') && m.setPaintProperty('bld', 'fill-extrusion-height', ['*', ['get', 'height_m'], +el('v3hx').value]); };
    el('v3col').onchange = colourMode;
    el('v3top').onclick = () => m?.easeTo({ pitch: 0, bearing: 0 });
    el('v3tilt').onclick = () => m?.easeTo({ pitch: 65, bearing: (m.getBearing() || 0) - 30 });
    el('v3fit').onclick = () => { if (!m) return; const b = inputs.site.getBounds(); m.fitBounds([[b.getWest(), b.getSouth()], [b.getEast(), b.getNorth()]], { padding: 40, pitch: 60, bearing: m.getBearing() }); };
  });
  return { open };
})();
