def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
# ---------------- app.js ----------------
patch('webapp/static/app.js', [
 ("  if (typeof Editor !== 'undefined') Editor.show(wf === 'design');", "  if (typeof Editor !== 'undefined') Editor.mode(wf);"),
 ("    results[L_.path] = L.geoJSON(fc, { style: styleFor(L_.kind), interactive: !['contours', 'slope', 'steep'].includes(L_.kind), onEachFeature: (f, l) => l.bindPopup(popupHtml(f.properties || {})),",
  "    results[L_.path] = L.geoJSON(fc, { style: styleFor(L_.kind), interactive: !['contours', 'slope', 'steep'].includes(L_.kind), onEachFeature: (f, l) => { l.bindPopup(popupHtml(f.properties || {})); l.on('click', e => { if (typeof Editor !== 'undefined' && Editor.captureResultClick(L_.kind, f, l, e)) { L.DomEvent.stop(e); setTimeout(() => l.closePopup(), 0); } }); },"),
 ("  resGroup.addLayer(results[L_.path]);", "  results[L_.path]._kind = L_.kind; resGroup.addLayer(results[L_.path]);"),
 ("  const DEFAULT_ON = new Set(['plots', 'plots_design', 'reserves', 'roads']);", "  LAYER_INDEX = r.layers;\n  const DEFAULT_ON = new Set(['plots', 'plots_design', 'reserves', 'roads']);"),
 ("  $('#legend').innerHTML = legS + Object.entries(leg)", "  const legHtml = legS + Object.entries(leg).map(([k, c]) => `<span><i style=\"background:${c}\"></i>${k}</span>`).join('');\n  setMapLegend(legHtml);\n  renderDownloads(r);\n  $('#legend').innerHTML = legS + Object.entries(leg)"),
 ("$('#mClose').onclick = () => $('#modal').hidden = true;", r"""$('#mClose').onclick = () => $('#modal').hidden = true;
let LAYER_INDEX = [];
async function reloadPlots() { for (const L_ of LAYER_INDEX.filter(l => l.kind === 'plots')) { if (results[L_.path]) { resGroup.removeLayer(results[L_.path]); delete results[L_.path]; } await toggleLayer(L_, true); } }
// ---- legend on the map (hideable) ----
const legendCtl = L.control({ position: 'bottomright' });
legendCtl.onAdd = () => { const d = L.DomUtil.create('div', 'maplegend'); d.innerHTML = '<div class="lh"><b>Legend</b><button title="Hide / show the legend">&minus;</button></div><div class="lb"></div>';
  L.DomEvent.disableClickPropagation(d); L.DomEvent.disableScrollPropagation(d);
  d.querySelector('button').onclick = () => { d.classList.toggle('shut'); d.querySelector('button').innerHTML = d.classList.contains('shut') ? '+' : '&minus;'; try { localStorage.setItem('lp_leg', d.classList.contains('shut') ? '0' : '1'); } catch (e) {} };
  try { if (localStorage.getItem('lp_leg') === '0') { d.classList.add('shut'); d.querySelector('button').innerHTML = '+'; } } catch (e) {}
  return d; };
legendCtl.addTo(map);
function setMapLegend(html) { const d = legendCtl.getContainer(); d.querySelector('.lb').innerHTML = html; d.style.display = html ? '' : 'none'; }
setMapLegend('');
// ---- downloads: tick what you need, get one zip (vector layers as shapefiles) ----
function renderDownloads(r) {
  const box = $('#dlList'); if (!box) return;
  const items = r.downloads || [];
  box.innerHTML = items.length ? items.map(it => `<label class="tl"><input type="checkbox" value="${it.id}" ${it.default ? 'checked' : ''}> ${it.label} <span class="mini">${it.kind}</span></label>`).join('') : '<p class="hint">Nothing to download yet.</p>';
}
$('#dlAll').onclick = () => $$('#dlList input').forEach(c => c.checked = true);
$('#dlNone').onclick = () => $$('#dlList input').forEach(c => c.checked = false);
$('#dlBtn').onclick = () => { const ids = $$('#dlList input:checked').map(c => c.value); if (!ids.length) return alert('Tick what you want to download.');
  window.location = `/api/projects/${P.id}/download?items=${encodeURIComponent(ids.join('|'))}`; };"""),
])
# ---------------- index.html: download card replaces the single zip button ----------------
patch('webapp/static/index.html', [
 ('''        <div class="card"><div class="cardh">Maps, tables and reports</div><div id="fileList"></div>
          <a id="zipBtn" class="btn">Download all outputs (zip)</a></div>''',
  '''        <div class="card"><div class="cardh">Maps, tables and reports</div><div id="fileList"></div></div>
        <div class="card"><div class="cardh">Download</div>
          <p class="hint">Tick the outputs you need. Map layers come as shapefiles (EPSG:2136, Ghana National Grid, with .prj), maps as PNG, tables as Excel. One zip.</p>
          <div class="row"><button class="ghost small" id="dlAll">All</button><button class="ghost small" id="dlNone">None</button></div>
          <div id="dlList"></div>
          <div class="row"><button id="dlBtn">Download selected</button> <a id="zipBtn" class="mini" href="#">or everything</a></div></div>'''),
])
patch('webapp/static/app.css', [("[hidden] { display: none !important; }", """[hidden] { display: none !important; }
.maplegend { background: rgba(255,255,255,.96); border: 1px solid #c9ced6; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,.2); font-size: 12px; max-width: 260px; max-height: 45vh; overflow: auto; }
.maplegend .lh { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 4px 8px; border-bottom: 1px solid #e3e1dc; }
.maplegend .lh button { padding: 0 7px; font-size: 13px; background: #fff; color: #333; border-color: #ccc; }
.maplegend .lb { padding: 6px 8px; } .maplegend .lb span { display: flex; align-items: center; gap: 6px; margin: 2px 0; }
.maplegend .lb i { width: 14px; height: 11px; border: 1px solid #555; display: inline-block; flex: none; }
.maplegend.shut .lb { display: none; }
#dlList { max-height: 260px; overflow: auto; margin: 6px 0; }
button.small { padding: 2px 8px; font-size: 12px; }
.widget .mres { background: #fff8e1; border: 1px solid #ffe0a3; border-radius: 4px; padding: 6px 8px; margin: 6px 0; }
.widget .seg2 { display: flex; gap: 14px; }""")])
# ---------------- app.py: download list + zip with shapefiles ----------------
patch('webapp/app.py', [
 ("    return jsonify(layers=out, files=files)", '''    downloads = []
    for L_ in out:
        if L_['kind'] == 'raster': continue
        downloads.append(dict(id='L:' + L_['path'], label=L_['label'], kind='shapefile' if not L_['path'].endswith('.csv') else 'table (csv) + points shapefile', default=L_['kind'] in ('plots', 'plots_design', 'buildings', 'blocks', 'roads', 'reserves')))
    for f in files:
        nm = f.split('/')[-1]
        if nm.endswith('.json') and 'overlay' in nm: continue
        downloads.append(dict(id='F:' + f, label=nm, kind={'png': 'map / image', 'xlsx': 'Excel table', 'json': 'summary', 'csv': 'table'}.get(nm.rsplit('.', 1)[-1], 'file'), default=nm.endswith(('.png', '.xlsx')) and '_work/' not in f))
    return jsonify(layers=out, files=files, downloads=downloads)'''),
 ("@app.get('/api/projects/<pid>/zip')", '''@app.get('/api/projects/<pid>/download')
def download(pid):
    """the ticked outputs as one zip: map layers as shapefiles (EPSG:2136), maps / tables as they are"""
    import geopandas as gpd, tempfile, pandas as pd
    items = [x for x in request.args.get('items', '').split('|') if x]; d = pdir(pid); tmp = tempfile.mkdtemp(); buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for it in items:
            kind, rel = it[:2], it[2:]
            try: f = safe(pid, rel)
            except Exception: continue
            base = os.path.splitext(os.path.basename(f))[0]
            if kind == 'L:':
                if f.endswith('.csv'):
                    t = pd.read_csv(f); g = gpd.GeoDataFrame(t.drop(columns=['x', 'y']), geometry=gpd.points_from_xy(t.x, t.y), crs=2136)
                    z.write(f, f'tables/{os.path.basename(f)}')
                else:
                    g = gpd.read_file(f)
                    if g.crs is None: g = g.set_crs(2136)
                    g = g.to_crs(2136)
                for c in list(g.columns):
                    if c != 'geometry' and str(g[c].dtype) == 'object': g[c] = g[c].astype(str).str.slice(0, 250)
                for gt in sorted(set(g.geom_type.dropna())):              # a shapefile holds one geometry type
                    sub = g[g.geom_type == gt]; nm = base if len(set(g.geom_type.dropna())) == 1 else f'{base}_{gt}'
                    out = os.path.join(tmp, nm + '.shp'); sub.to_file(out)
                    for ext in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
                        if os.path.exists(out[:-4] + ext): z.write(out[:-4] + ext, f'shapefiles/{nm}{ext}')
            else:
                z.write(f, ('maps/' if f.endswith('.png') else 'tables/' if f.endswith(('.xlsx', '.csv')) else '') + os.path.basename(f))
    shutil.rmtree(tmp, ignore_errors=True); buf.seek(0)
    return send_file(buf, mimetype='application/zip', as_attachment=True, download_name=f'{meta(pid)["name"]}_outputs.zip')
@app.get('/api/projects/<pid>/zip')'''),
])
print('ok')
