
# =====================================================================================================================
# Stage: fetch (existing workflow) - imagery, OSM (Overpass with fallbacks, then the OSM API), Microsoft footprints, database
# =====================================================================================================================
OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter',
            'https://overpass.private.coffee/api/interpreter', 'https://maps.mail.ru/osm/tools/overpass/api/interpreter']
def _http(url, data=None, timeout=180):
    import urllib.request, urllib.parse
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()
def overpass(query, timeout=60):
    for u in OVERPASS:
        try:
            txt = _http(u, {'data': query}, timeout=timeout).decode('utf-8')
            if '"elements"' in txt: return json.loads(txt)
            print('   overpass busy:', u, flush=True)
        except Exception as e: print('   overpass failed:', u, str(e)[:80], flush=True)
        time.sleep(3)
    return None
def osm_api_map(w, s, e, n, _depth=0):
    """main OSM API: returns nodes {id: (lon, lat, tags)} and ways [(id, tags, coords)].
    The API refuses areas with more than 50,000 nodes (HTTP 400): the box is then cut into 4 tiles (recursively) and merged."""
    import xml.etree.ElementTree as ET, urllib.error
    try: raw = _http(f'https://api.openstreetmap.org/api/0.6/map?bbox={w},{s},{e},{n}')
    except urllib.error.HTTPError as ex:
        if ex.code in (429, 509) and _depth < 8: time.sleep(20); return osm_api_map(w, s, e, n, _depth + 1)        # rate limited: wait and retry
        if ex.code != 400 or _depth >= 6: raise
        if _depth == 0: print('   OSM API: area too dense for one call, fetching it in tiles', flush=True)
        mx, my = (w + e) / 2, (s + n) / 2; nodes, seen, ways = {}, set(), []
        for bb in ((w, s, mx, my), (mx, s, e, my), (w, my, mx, n), (mx, my, e, n)):
            nd, wy = osm_api_map(*bb, _depth=_depth + 1); nodes.update(nd)
            for it in wy:
                if it[0] not in seen: seen.add(it[0]); ways.append(it)
        return nodes, ways
    root = ET.fromstring(raw)
    nodes = {}; ways = []
    for nd in root.iter('node'): nodes[nd.get('id')] = (float(nd.get('lon')), float(nd.get('lat')), {t.get('k'): t.get('v') for t in nd.iter('tag')})
    for wy in root.iter('way'):
        ref = [nodes[x.get('ref')][:2] for x in wy.iter('nd') if x.get('ref') in nodes]
        ways.append((int(wy.get('id')), {t.get('k'): t.get('v') for t in wy.iter('tag')}, ref))
    return nodes, ways
POI_KEYS = ('amenity', 'shop', 'office', 'healthcare', 'tourism', 'leisure', 'landuse', 'building')
def quadkey(lat, lon, z):
    x = (lon + 180) / 360; s = math.sin(math.radians(lat)); y = 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)
    tx, ty = int(x * 2 ** z), int(y * 2 ** z); q = ''
    for i in range(z, 0, -1):
        d = 0; m = 1 << (i - 1)
        if tx & m: d += 1
        if ty & m: d += 2
        q += str(d)
    return q

GOOGLE_SAT = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
IMAGERY_PREF = 'google'                                 # set by --imagery google | esri
def robust_tiles(w, s, e, n, zoom, path=None, ll=True):
    """satellite tiles with retries (8 per tile): preferred source (Google by default), then slowly on 1 connection, then the other source.
    path given: writes a GeoTIFF (EPSG:3857) and returns None; otherwise returns (image, extent) like contextily.bounds2img"""
    import contextily as cx
    G = [('Google satellite', GOOGLE_SAT, 4), ('Google satellite (slow, 1 connection)', GOOGLE_SAT, 1)]
    E = [('Esri World Imagery', cx.providers.Esri.WorldImagery, 4), ('Esri World Imagery (slow, 1 connection)', cx.providers.Esri.WorldImagery, 1)]
    tries = (E + G) if IMAGERY_PREF == 'esri' else (G + E)
    last = None
    for k, (name, src, nc) in enumerate(tries):
        try:
            if path: cx.bounds2raster(w, s, e, n, path, zoom=zoom, source=src, ll=ll, max_retries=8, wait=2, n_connections=nc, timeout=60); out = None
            else: out = cx.bounds2img(w, s, e, n, zoom=zoom, source=src, ll=ll, max_retries=8, wait=2, n_connections=nc, timeout=60)
            print(f'   imagery source: {name}', flush=True)
            if path: open(path + '.source.txt', 'w').write(name + (' (fallback)' if not name.lower().startswith(IMAGERY_PREF) else ''))
            return out
        except Exception as ex:
            last = ex; print(f'   imagery download failed ({name}): {str(ex)[:120]}; trying again in 20 s', flush=True); time.sleep(20)
    raise RuntimeError(f'satellite imagery could not be downloaded (Google and Esri both failed): {last}')
def st_fetch(ctx):
    import geopandas as gpd, pandas as pd, contextily as cx, rasterio, gzip, urllib.request
    from shapely.geometry import Polygon, LineString, Point, shape
    WORK, SITE_KML = ctx['WORK'], ctx['SITE_KML']
    site = gpd.read_file(SITE_KML); site['geometry'] = site.geometry.force_2d(); S = site.to_crs(2136).geometry.iloc[0]
    w, s, e, n = site.total_bounds; b = 0.0006
    # ---- imagery ----
    sf = WORK + 'img_z19_3857.tif.source.txt'
    src_now = open(sf).read() if os.path.exists(sf) else ''
    if os.path.exists(WORK + 'img_z19_3857.tif') and '(fallback)' in src_now:
        print(f'   keeping the imagery from the last download ({src_now}); the preferred source was unavailable then. To try {IMAGERY_PREF} again, delete _work/img_z19_3857.tif', flush=True)
    elif os.path.exists(WORK + 'img_z19_3857.tif') and src_now and not src_now.lower().startswith(IMAGERY_PREF):
        print(f'   imagery source changed to {IMAGERY_PREF}: downloading again (detection tiles from the old imagery are cleared)', flush=True)
        os.remove(WORK + 'img_z19_3857.tif'); [os.remove(f) for f in glob.glob(WORK + 'tiles/*.pkl')]
    if not os.path.exists(WORK + 'img_z19_3857.tif'):
        robust_tiles(w - b, s - b, e + b, n + b, 19, path=WORK + 'img_z19_3857.tif')
    r = rasterio.open(WORK + 'img_z19_3857.tif'); print('   imagery', r.shape, 'px at', round(r.res[0], 3), 'm', flush=True); progress(55, 'imagery')
    # ---- OSM ----
    BB = f'{s - b},{w - b},{n + b},{e + b}'
    small = (e - w + 2 * b) * (n - s + 2 * b) < 0.04
    dB = None if small else overpass(f'[out:json][timeout:50];(way["building"]({BB});relation["building"]({BB}););out geom;')
    dR = overpass(f'[out:json][timeout:50];way["highway"]({BB});out geom;') if dB is not None else None      # all servers busy: go straight to the OSM API
    dP = None if dR is None else overpass('[out:json][timeout:120];(' + ''.join(f'nwr["{k}"]({BB});' for k in POI_KEYS[:-1]) + f'nwr["building"]["building"!="yes"]({BB}););out center tags;'.replace('timeout:120', 'timeout:50'))
    brows, rrows, prows = [], [], []
    if dB is not None and dR is not None and dP is not None:
        for el in dB['elements']:
            if el['type'] == 'way' and len(el.get('geometry', [])) >= 4: brows.append(dict(osm_id=el['id'], building=el['tags'].get('building'), geometry=Polygon([(p['lon'], p['lat']) for p in el['geometry']])))
        for el in dR['elements']:
            if len(el.get('geometry', [])) >= 2: t = el['tags']; rrows.append(dict(osm_id=el['id'], highway=t.get('highway'), name=t.get('name'), lanes=t.get('lanes'), width=t.get('width'), geometry=LineString([(p['lon'], p['lat']) for p in el['geometry']])))
        for el in dP['elements']:
            c = (el.get('lon'), el.get('lat')) if el['type'] == 'node' else (el.get('center', {}).get('lon'), el.get('center', {}).get('lat'))
            if c[0] is None: continue
            t = el.get('tags', {}); key = next((k for k in POI_KEYS if k in t), None)
            prows.append(dict(osm=f"{el['type']}/{el['id']}", key=key, val=t.get(key), name=t.get('name'), geometry=Point(c)))
    else:
        print('   OSM API map call' + ('' if small else ' (Overpass unavailable)'), flush=True); nodes, ways = osm_api_map(w - b, s - b, e + b, n + b)
        for nid, (lo, la, t) in nodes.items():
            key = next((k for k in POI_KEYS[:-1] if k in t), None)
            if key: prows.append(dict(osm=f'node/{nid}', key=key, val=t[key], name=t.get('name'), geometry=Point(lo, la)))
        for wid, t, ref in ways:
            if 'highway' in t and len(ref) >= 2: rrows.append(dict(osm_id=wid, highway=t['highway'], name=t.get('name'), lanes=t.get('lanes'), width=t.get('width'), geometry=LineString(ref)))
            if len(ref) >= 4 and ref[0] == ref[-1]:
                if 'building' in t: brows.append(dict(osm_id=wid, building=t['building'], geometry=Polygon(ref)))
                key = next((k for k in POI_KEYS if k in t and not (k == 'building' and t[k] == 'yes')), None)
                if key: prows.append(dict(osm=f'way/{wid}', key=key, val=t[key], name=t.get('name'), geometry=Polygon(ref).centroid))
    O = gpd.GeoDataFrame(brows, geometry='geometry', crs=4326) if brows else gpd.GeoDataFrame(columns=['osm_id', 'building', 'geometry'], geometry='geometry', crs=4326)
    O = O.to_crs(2136); O = O[O.intersects(S.buffer(30))]; O.to_file(WORK + 'osm_buildings.gpkg')
    Rd = gpd.GeoDataFrame(rrows, geometry='geometry', crs=4326).to_crs(2136); Rd = Rd[Rd.intersects(S.buffer(100))]; Rd.to_file(WORK + 'osm_roads.gpkg')
    Pp = gpd.GeoDataFrame(prows, geometry='geometry', crs=4326) if prows else gpd.GeoDataFrame(columns=['osm', 'key', 'val', 'name', 'geometry'], geometry='geometry', crs=4326)
    Pp = Pp.to_crs(2136); Pp = Pp[Pp.within(S.buffer(50))]; Pp.to_file(WORK + 'osm_poi.gpkg')
    print(f'   OSM: {len(O)} buildings, {len(Rd)} road segments {Rd.highway.value_counts().to_dict()}, {len(Pp)} POIs'); progress(70, 'OpenStreetMap')
    try: fetch_osm_sites(w - b, s - b, e + b, n + b, S, WORK)
    except Exception as ex: print('   OSM site outlines not available:', str(ex)[:100], flush=True)
    # ---- Microsoft footprints (level-9 quadkey tile, cached) ----
    os.makedirs(MS_CACHE, exist_ok=True); links_f = MS_CACHE + '/dataset-links.csv'
    if not os.path.exists(links_f): open(links_f, 'wb').write(_http('https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv'))
    links = pd.read_csv(links_f); geoms = []
    for qk in {quadkey(la, lo, 9) for la in (s, n) for lo in (w, e)}:
        for url in links[links.QuadKey.astype(str).str.zfill(9) == qk].Url:
            fn = MS_CACHE + '/' + url.split('/')[-1]
            if not os.path.exists(fn): urllib.request.urlretrieve(url, fn)
            with gzip.open(fn, 'rt') as f:
                for line in f:
                    g = shape(json.loads(line)['geometry']); c = g.centroid
                    if w - 0.001 < c.x < e + 0.001 and s - 0.001 < c.y < n + 0.001: geoms.append(g)
    M = gpd.GeoDataFrame(geometry=geoms, crs=4326).to_crs(2136); M = M[M.intersects(S.buffer(30))]; M.to_file(WORK + 'ms_buildings.gpkg'); print('   Microsoft footprints', len(M)); progress(85, 'Microsoft')
    # ---- building database ----
    G = obm_load(site); G.to_file(WORK + 'obm_buildings.gpkg'); print('   building database', len(G), G.source.value_counts().to_dict() if len(G) else '')

# =====================================================================================================================
# Design workflow: site (imagery + DEM + database buildings), roads (planner's centrelines -> reserves, blocks, concept)
# =====================================================================================================================
def fetch_dem(site4326, out_tif, buf=0.004):
    import rasterio
    from rasterio.windows import from_bounds
    w, s, e, n = site4326.total_bounds; w, s, e, n = w - buf, s - buf, e + buf, n + buf
    lat, lon = math.floor((s + n) / 2), math.floor((w + e) / 2)
    tile = f"Copernicus_DSM_COG_10_{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00_{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00_DEM"
    url = f'https://copernicus-dem-30m.s3.amazonaws.com/{tile}/{tile}.tif'
    with rasterio.open(url) as r:
        win = from_bounds(w, s, e, n, r.transform); a = r.read(1, window=win); t = r.window_transform(win)
        prof = {k: v for k, v in r.profile.items() if k not in ('blockxsize', 'blockysize', 'tiled', 'compress', 'interleave')}
        prof.update(height=a.shape[0], width=a.shape[1], transform=t, driver='GTiff')
        with rasterio.open(out_tif, 'w', **prof) as d: d.write(a, 1)
    print('   DEM', a.shape, 'elevation', float(np.nanmin(a)), '-', float(np.nanmax(a)), 'm')
def st_design_site(ctx):
    import geopandas as gpd
    WORK, SITE_KML = ctx['WORK'], ctx['SITE_KML']
    site = gpd.read_file(SITE_KML)
    if not os.path.exists(WORK + 'dem.tif'): fetch_dem(site, WORK + 'dem.tif')
    G = obm_load(site); G.to_file(WORK + 'buildings.gpkg'); print('   existing buildings (database)', len(G))
    fetch_osm_roads_water(site, WORK)
    _design_site_analysis(ctx)
    terrain_products(ctx)
def _width_of(row):
    for k in ('width_ft', 'WIDTH_FT', 'width', 'Width', 'reserve_ft'):
        if k in row and row[k] is not None and str(row[k]) not in ('', 'nan', 'None'):
            try: return float(row[k])
            except Exception: pass
    for k in ('class', 'Class', 'CLASS', 'name', 'Name', 'type'):
        if k in row and isinstance(row[k], str):
            m = re.search(r'(\d+(?:\.\d+)?)\s*(ft|feet|\')', row[k])
            if m: return float(m.group(1))
    return 30.0
def st_design_roads(ctx):
    """planner's road centrelines (width_ft or a class text with the width) -> layout_roads / layout_centrelines / layout_blocks / concept"""
    import geopandas as gpd, shapely
    from shapely.geometry import Polygon, Point, LineString, box
    from shapely.ops import unary_union
    WORK, SITE_KML = ctx['WORK'], ctx['SITE_KML']
    mode = (ctx.get('roads') or '').lower()
    if mode in ('auto', 'draft'):
        st_design_autoroads(ctx)
        if mode == 'draft':
            print(f"   DRAFT written: {ctx['D']}{ctx['PFX']}Roads_draft.shp (+ .png). Edit it, then run: design ... --roads <edited file> --from roads"); ctx['stop'] = True; return
    if not ctx.get('roads'): raise SystemExit('design roads: give the planner road centrelines with --roads (field width_ft, or a class text such as "40 ft collector")')
    site = gpd.read_file(SITE_KML).to_crs(2136); S = shapely.force_2d(site.geometry.iloc[0]); S = Polygon(S.exterior.coords)
    RL = gpd.read_file(ctx['roads']).to_crs(2136); RL['geometry'] = RL.geometry.force_2d(); RL = RL.explode(index_parts=False)
    RL = RL[RL.geom_type == 'LineString'].reset_index(drop=True); RL['w'] = [_width_of(r_) for _, r_ in RL.iterrows()]
    if RL.empty: raise SystemExit('NO ROADS: the roads file has no road lines. Draw roads (or use "Design the roads for me") before running the layout.')
    # node the network: split every line where it crosses another (keeps each piece's width)
    noded = shapely.get_parts(shapely.node(shapely.geometry.MultiLineString(list(RL.geometry))))
    seg_w = []
    for p in noded:
        mid = p.interpolate(0.5, normalized=True); k = int(np.argmin([g.distance(mid) for g in RL.geometry])); seg_w.append(RL.w.iloc[k])
    SURF = road_surface(list(noded), [wft / 2 for wft in seg_w], tol=3.0, clip=None, fillet=15.0)
    far = Point(-1e7, -1e7).buffer(1)
    name = lambda wft: {30: '30 ft local road', 40: '40 ft collector', 60: '60 ft main road', 100: '100 ft road reserve'}.get(int(round(wft)), f'{wft:.0f} ft road')
    classes = {}
    for p, wft in zip(noded, seg_w): classes.setdefault(name(wft), []).append(p.buffer(wft / 2 + 0.5, cap_style=2))
    rows = {k: unary_union(v).intersection(SURF) for k, v in classes.items()}
    for k in ('30 ft local road', '40 ft collector'): rows.setdefault(k, far)
    gpd.GeoDataFrame(dict(Class=list(rows)), geometry=list(rows.values()), crs=2136).to_file(WORK + 'layout_roads.gpkg')
    gpd.GeoDataFrame(dict(width_ft=seg_w), geometry=list(noded), crs=2136).to_file(WORK + 'layout_centrelines.gpkg')
    wmax = max(seg_w); MAIN = rows.get(name(wmax), far) if wmax >= 40 else far
    if ctx.get('stream'):
        st = gpd.read_file(ctx['stream']).to_crs(2136); st['geometry'] = st.geometry.force_2d()
        SR = st.union_all().buffer(float(ctx.get('stream_buffer') or 0) or 0.01).intersection(S)
    else: SR = far
    STP = steep_reserve(ctx)
    if STP is not None: SR = STP if SR.equals(far) else SR.union(STP); print(f'   steep-slope reserve kept green: {STP.area / 43560:.1f} ac')
    x0, y0, x1, y1 = S.bounds; WZ = S.intersection(box(x0 - 10, y0 - 10, S.centroid.x, y1 + 10))
    gpd.GeoDataFrame(dict(Part=['Site', '60 ft existing road', 'Stream reserve', 'West zone']), geometry=[S, MAIN.intersection(S) if not MAIN.equals(far) else far, SR, WZ], crs=2136).to_file(WORK + 'concept.gpkg')
    BL = [g for g in shapely.get_parts(S.difference(SURF).difference(SR if not SR.equals(far) else Point(0, 0).buffer(0.001))) if g.area > 2000]
    gpd.GeoDataFrame(geometry=BL, crs=2136).to_file(WORK + 'layout_blocks.gpkg')
    print(f'   roads {len(noded)} segments {pd_counts(seg_w)} | blocks {len(BL)} | stream reserve {"yes" if not SR.equals(far) else "no"}')
def pd_counts(v):
    from collections import Counter; return dict(Counter(int(round(x)) for x in v))

def fetch_osm_roads_water(site, WORK):
    """existing roads (highways) and streams (waterways) around a design site -> osm_roads.gpkg, osm_water.gpkg (EPSG:2136)"""
    import geopandas as gpd
    from shapely.geometry import LineString
    w, s, e, n = site.to_crs(4326).total_bounds; b = 0.003; BB = f'{s - b},{w - b},{n + b},{e + b}'
    rows = []; d = None
    small = (e - w + 2 * b) * (n - s + 2 * b) < 0.04                      # OSM API map call handles areas up to ~0.25 sq deg / 50,000 nodes
    if small:
        try: nodes, ways = osm_api_map(w - b, s - b, e + b, n + b)
        except Exception as ex: print('   OSM API failed, trying Overpass:', str(ex)[:80], flush=True); small = False
    if not small: d = overpass(f'[out:json][timeout:50];(way["highway"]({BB});way["waterway"]({BB}););out geom;')
    if d is not None:
        for el in d['elements']:
            t = el.get('tags', {})
            if len(el.get('geometry', [])) >= 2: rows.append(dict(highway=t.get('highway'), waterway=t.get('waterway'), name=t.get('name'), geometry=LineString([(p['lon'], p['lat']) for p in el['geometry']])))
    else:
        if not small: nodes, ways = osm_api_map(w - b, s - b, e + b, n + b)
        for wid, t, ref in ways:
            if len(ref) >= 2 and ('highway' in t or 'waterway' in t): rows.append(dict(highway=t.get('highway'), waterway=t.get('waterway'), name=t.get('name'), geometry=LineString(ref)))
    G = gpd.GeoDataFrame(rows, geometry='geometry', crs=4326) if rows else gpd.GeoDataFrame(columns=['highway', 'waterway', 'name', 'geometry'], geometry='geometry', crs=4326)
    G = G.to_crs(2136)
    G[G.highway.notna()].to_file(WORK + 'osm_roads.gpkg'); G[G.waterway.isin(['stream', 'river', 'canal', 'drain', 'ditch'])].to_file(WORK + 'osm_water.gpkg')
    print(f'   OSM: {int(G.highway.notna().sum())} roads, {int(G.waterway.notna().sum())} waterways')

SLOPE_CLASSES = [(0, 5, 'Flat (0-5%)', '#1a9850'), (5, 10, 'Gentle (5-10%)', '#91cf60'), (10, 18, 'Moderate (10-18%)', '#fee08b'),
                 (18, 30, 'Steep (18-30%): no roads straight downhill', '#fc8d59'), (30, 1e9, 'Very steep (> 30%): keep green', '#d73027')]
def contour_interval(relief_m):
    return next(c for c in (1, 2, 5, 10, 20, 50) if relief_m / c <= 40)
def terrain_products(ctx):
    """slope (%) raster, slope classes, contours (interval adapted to the relief), steep-slope reserve; summary in the log"""
    import geopandas as gpd, rasterio, shapely
    from rasterio import features as rfeat
    from shapely.geometry import Polygon, LineString, shape
    from shapely.ops import unary_union
    from skimage.measure import find_contours
    WORK, D, PFX = ctx['WORK'], ctx['D'], ctx['PFX']
    S = shapely.force_2d(gpd.read_file(ctx['SITE_KML']).to_crs(2136).geometry.iloc[0]); S = Polygon(S.exterior.coords)
    r = rasterio.open(WORK + 'dem_2136.tif'); dem = r.read(1).astype(float); T = r.transform; px_m = abs(T.a) * FT
    gy, gx = np.gradient(dem, px_m); slope = np.hypot(gx, gy) * 100
    prof = r.profile.copy(); prof.update(dtype='float32', nodata=-9999)
    with rasterio.open(D + PFX + 'Slope_percent.tif', 'w', **prof) as o: o.write(np.where(np.isnan(slope), -9999, slope).astype('float32'), 1)
    inside = rfeat.rasterize([S], out_shape=dem.shape, transform=T).astype(bool)
    cls = np.zeros(dem.shape, np.uint8)
    for k, (a, b, lab, col) in enumerate(SLOPE_CLASSES, 1): cls[(slope >= a) & (slope < b)] = k
    cls[~inside | np.isnan(slope)] = 0
    rows = []
    for k, (a, b, lab, col) in enumerate(SLOPE_CLASSES, 1):
        polys = [shape(g) for g, v in rfeat.shapes(cls, mask=cls == k, transform=T) if v == k]
        if not polys: continue
        g = unary_union(polys).buffer(10).buffer(-10).simplify(8).intersection(S)
        if g.is_empty: continue
        rows.append(dict(cls=lab, pct_from=a, pct_to=(b if b < 1e8 else 999), area_ac=round(g.area / 43560, 2), share=round(g.area / S.area * 100, 1), geometry=g))
    SC = gpd.GeoDataFrame(rows, geometry='geometry', crs=2136); SC.to_file(D + PFX + 'Slope_classes.shp')
    zin = dem[inside & ~np.isnan(dem)]; relief = float(zin.max() - zin.min()); CI = contour_interval(relief)
    lines = []
    for z in np.arange(np.floor(np.nanmin(dem) / CI) * CI, np.nanmax(dem) + CI, CI):
        for c in find_contours(np.nan_to_num(dem, nan=-9999), z):
            if len(c) < 3: continue
            xy = [T * (cc[1] + 0.5, cc[0] + 0.5) for cc in c]
            lines.append(dict(elev_m=float(z), major=int(round(z / CI)) % 5 == 0, geometry=LineString(xy).simplify(3)))
    CT = gpd.GeoDataFrame(lines, geometry='geometry', crs=2136); CT = CT[CT.intersects(S.buffer(300))]; CT['geometry'] = CT.intersection(S.buffer(300))
    CT = CT[~CT.is_empty]; CT.to_file(D + PFX + 'Contours.shp')
    steep = float(ctx.get('steep_pct', 30) or 0)
    if steep > 0:
        m = (slope >= steep) & inside
        polys = [shape(g) for g, v in rfeat.shapes(m.astype(np.uint8), mask=m, transform=T) if v == 1]
        g = unary_union(polys).buffer(-15).buffer(15) if polys else Polygon()
        g = unary_union([q for q in shapely.get_parts(g) if q.area >= 0.5 * 43560]).intersection(S) if not g.is_empty else g
        GS = gpd.GeoDataFrame(dict(reserve=[f'Steep slope (>= {steep:.0f}%): green / conservation'], area_ac=[round(g.area / 43560, 2)]), geometry=[g], crs=2136)
        GS.to_file(WORK + 'steep_reserve.gpkg'); GS.to_file(D + PFX + 'Steep_slope_reserve.shp')
    if os.path.exists(WORK + 'site_analysis.png'): shutil.copy(WORK + 'site_analysis.png', D + PFX + 'Site_analysis.png')
    terrain_overlays(ctx, S)
    summ = dict(elev_min=round(float(zin.min()), 1), elev_max=round(float(zin.max()), 1), relief=round(relief, 1), contour_interval=CI, mean_slope_pct=round(float(np.nanmean(slope[inside])), 1),
                classes=[dict(cls=rr.cls, area_ac=rr.area_ac, share=rr.share) for _, rr in SC.iterrows()], steep_pct=steep,
                steep_reserve_ac=(round(float(GS.area_ac.iloc[0]), 1) if steep > 0 else 0))
    json.dump(summ, open(D + PFX + 'Terrain_summary.json', 'w'), indent=1)
    print(f'   terrain: elevation {zin.min():.0f}-{zin.max():.0f} m (relief {relief:.0f} m), contours every {CI} m, mean slope {np.nanmean(slope[inside]):.1f}%')
    for _, rr in SC.iterrows(): print(f'     {rr.cls:45s} {rr.area_ac:7.1f} ac  {rr.share:5.1f}%')
    if steep > 0: print(f'   steep-slope reserve (>= {steep:.0f}%, pieces >= 0.5 ac): {GS.area_ac.iloc[0]:.1f} ac kept green')
def steep_reserve(ctx):
    import geopandas as gpd
    f = ctx['WORK'] + 'steep_reserve.gpkg'
    if float(ctx.get('steep_pct', 30) or 0) <= 0 or not os.path.exists(f): return None
    g = gpd.read_file(f).union_all(); return None if g.is_empty else g

def terrain_overlays(ctx, S):
    """web-map overlays (EPSG:3857 PNG + lat/lon bounds): elevation with hillshade, slope classes"""
    import rasterio, matplotlib, geopandas as gpd
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from rasterio import features as rfeat
    from pyproj import Transformer
    WORK, D, PFX = ctx['WORK'], ctx['D'], ctx['PFX']
    with rasterio.open(WORK + 'dem_2136.tif') as r:
        t, w, h = calculate_default_transform(r.crs, 'EPSG:3857', r.width, r.height, *r.bounds, resolution=3)
        z = np.full((h, w), np.nan, 'float32'); reproject(rasterio.band(r, 1), z, src_transform=r.transform, src_crs=r.crs, dst_transform=t, dst_crs='EPSG:3857', resampling=Resampling.bilinear, dst_nodata=np.nan)
    S3 = gpd.GeoSeries([S], crs=2136).to_crs(3857).iloc[0]
    near = rfeat.rasterize([S3.buffer(90)], out_shape=z.shape, transform=t).astype(bool) & ~np.isnan(z)
    gy, gx = np.gradient(np.nan_to_num(z, nan=np.nanmean(z)), 3.0); slope = np.hypot(gx, gy) * 100
    az, alt = np.radians(315), np.radians(45); asp = np.arctan2(-gx, gy)
    hs = np.clip(np.sin(alt) * np.cos(np.arctan(np.hypot(gx, gy))) + np.cos(alt) * np.sin(np.arctan(np.hypot(gx, gy))) * np.cos(az - asp), 0, 1)
    zin = z[near]; zn = (z - zin.min()) / max(zin.max() - zin.min(), 1)
    rgb = matplotlib.colormaps['terrain'](np.clip(zn * 0.85 + 0.12, 0, 1))[:, :, :3] * (0.45 + 0.55 * hs[:, :, None])
    dem_png = np.dstack([rgb, near * 0.85]); dem_png[~near] = 0
    cols = np.zeros(z.shape + (4,))
    for a, b, lab, col in SLOPE_CLASSES:
        m = (slope >= a) & (slope < b) & near; c = matplotlib.colors.to_rgb(col); cols[m] = (*c, 0.75)
    tr = Transformer.from_crs(3857, 4326, always_xy=True); x0, y1 = t.c, t.f; x1, y0 = t.c + w * t.a, t.f + h * t.e
    (lo0, la0), (lo1, la1) = tr.transform(x0, y0), tr.transform(x1, y1)
    bounds = [[la0, lo0], [la1, lo1]]
    for name, arr in (('Elevation_overlay.png', dem_png), ('Slope_overlay.png', cols)):
        matplotlib.image.imsave(D + PFX + name, np.clip(arr, 0, 1)); json.dump(dict(bounds=bounds), open(D + PFX + name.replace('.png', '.json'), 'w'))

# =====================================================================================================================
# Stage: footprints (fast route) - OpenStreetMap + building database in one step, no image detection (SAM)
# =====================================================================================================================
def st_footprints(ctx):
    """OSM outlines where they exist, building-database outlines (Google / Microsoft / OSM) where OSM has none; occupancy and height
    attached to every building; walls / fences detected on the image. Replaces sam, digitize, compare, clean and database."""
    import geopandas as gpd, pandas as pd, shapely
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    D, PFX, WORK = ctx['D'], ctx['PFX'], ctx['WORK']
    S = shapely.force_2d(gpd.read_file(ctx['SITE_KML']).to_crs(2136).geometry.iloc[0]); S = Polygon(S.exterior.coords)
    O = gpd.read_file(WORK + 'osm_buildings.gpkg').to_crs(2136); O = O[O.intersects(S) & O.geometry.is_valid].reset_index(drop=True)
    G = gpd.read_file(WORK + 'obm_buildings.gpkg') if os.path.exists(WORK + 'obm_buildings.gpkg') else obm_load(gpd.read_file(ctx['SITE_KML']))
    G = G.to_crs(2136); G = G[G.intersects(S)].reset_index(drop=True); progress(10, 'inputs read')
    gt = shapely.STRtree(list(G.geometry)); rows = []
    for g in O.geometry:                                              # 1. OSM outlines, with database attributes by best overlap
        g = g.buffer(0)
        if g.is_empty or g.area * FT * FT < 6: continue
        c = [(G.geometry[j].intersection(g).area, j) for j in gt.query(g)]; c = [x for x in c if x[0] > 0.3 * min(g.area, G.geometry[x[1]].area)]
        j = max(c)[1] if c else None
        rows.append(dict(geometry=g, src='OSM', action='OSM footprint', j=j))
    progress(45, 'OSM footprints')
    U = unary_union([r_['geometry'] for r_ in rows]) if rows else None; added = 0
    for j, g in enumerate(G.geometry):                                # 2. database outlines where OSM has nothing
        if g.area * FT * FT < 9: continue
        if U is not None and g.intersection(U).area > 0.3 * g.area: continue
        rows.append(dict(geometry=g, src=f'database ({G.source[j]})', action=f'added from database ({G.source[j]})', j=j)); added += 1
    progress(70, 'database footprints')
    F = gpd.GeoDataFrame(rows, geometry='geometry', crs=2136)
    col = lambda k: [G[k][int(j)] if j is not None and not pd.isna(j) else None for j in F.j]
    F['db_id'], F['db_source'], F['occupancy'], F['use_db'], F['height'] = col('id'), col('source'), col('occupancy'), col('use_obm'), col('height')
    F['class'] = 'Building'; F['reason'] = 'OSM / building database'; F['area_m2'] = (F.area * FT * FT).round(1); F['bld_id'] = range(1, len(F) + 1)
    F = F[['bld_id', 'class', 'area_m2', 'src', 'action', 'reason', 'db_id', 'db_source', 'occupancy', 'use_db', 'height', 'geometry']]
    F.to_file(D + PFX + 'Buildings_final.shp'); F.to_file(D + PFX + 'Buildings.shp')
    print(f'   buildings: {len(F)} ({len(F) - added} OSM outlines, {added} from the database {G.source.value_counts().to_dict() if len(G) else ""}) | occupancy known for {int((F.occupancy.notna() & (F.occupancy != "UNK")).sum())}', flush=True)
    ctx['footprint_source'] = 'database'
    _walls_from_image(ctx, F); progress(100, 'walls')

# OSM tags of service / utility sites that are kept as ONE plot (never subdivided), with their land use
SITE_TAGS = {('amenity', 'school'): 'Education', ('amenity', 'kindergarten'): 'Education', ('amenity', 'college'): 'Education', ('amenity', 'university'): 'Education',
             ('amenity', 'hospital'): 'Health', ('amenity', 'clinic'): 'Health', ('healthcare', 'hospital'): 'Health', ('healthcare', 'clinic'): 'Health',
             ('amenity', 'police'): 'Civic', ('amenity', 'fire_station'): 'Civic', ('amenity', 'prison'): 'Civic', ('amenity', 'townhall'): 'Civic',
             ('amenity', 'courthouse'): 'Civic', ('amenity', 'post_office'): 'Civic', ('amenity', 'community_centre'): 'Civic', ('office', 'government'): 'Civic',
             ('landuse', 'military'): 'Civic', ('military', 'barracks'): 'Civic', ('amenity', 'place_of_worship'): 'Religious', ('landuse', 'religious'): 'Religious',
             ('amenity', 'marketplace'): 'Market', ('amenity', 'bus_station'): 'Transport terminal', ('amenity', 'fuel'): 'Commercial (fuel)',
             ('power', 'substation'): 'Utility', ('power', 'plant'): 'Utility', ('man_made', 'water_works'): 'Utility', ('man_made', 'wastewater_plant'): 'Utility',
             ('landuse', 'cemetery'): 'Civic', ('amenity', 'grave_yard'): 'Civic', ('leisure', 'stadium'): 'Recreation', ('leisure', 'sports_centre'): 'Recreation'}
def fetch_osm_sites(w, s, e, n, S, WORK):
    """outlines of service / utility sites (closed ways with the tags above) -> osm_sites.gpkg (EPSG:2136)"""
    import geopandas as gpd
    from shapely.geometry import Polygon
    small = (e - w) * (n - s) < 0.04; rows = []
    if small: nodes, ways = osm_api_map(w, s, e, n); items = [(t, ref) for _, t, ref in ways]
    else:
        BB = f'{s},{w},{n},{e}'; q = ''.join(f'way["{k}"="{v}"]({BB});' for k, v in SITE_TAGS)
        d = overpass(f'[out:json][timeout:60];({q});out geom;'); items = [(el.get('tags', {}), [(p['lon'], p['lat']) for p in el.get('geometry', [])]) for el in (d or {}).get('elements', [])]
    for t, ref in items:
        if len(ref) < 4 or ref[0] != ref[-1]: continue
        hit = next(((k, v) for (k, v) in SITE_TAGS if t.get(k) == v), None)
        if hit and 'building' not in t: rows.append(dict(tag=f'{hit[0]}={hit[1]}', use=SITE_TAGS[hit], name=t.get('name'), geometry=Polygon(ref)))
    G = gpd.GeoDataFrame(rows, geometry='geometry', crs=4326) if rows else gpd.GeoDataFrame(columns=['tag', 'use', 'name', 'geometry'], geometry='geometry', crs=4326)
    G = G.to_crs(2136); G = G[G.intersects(S)]; G.to_file(WORK + 'osm_sites.gpkg'); print(f'   OSM site outlines (schools, hospitals, police, utilities ...): {len(G)}', flush=True)


# =====================================================================================================================
# Stage: chamfer (design, optional) - corner truncations on corner plots (LUSPA Guidelines 2025, s.10.1.1): the triangle cut
# off a plot is added to the road reserve. Distance by the higher road at the corner: local / cul-de-sac 3.5 m, collector 5 m,
# major arterial 10 m; never more than 15 % of the plot's shorter side (small plots get smaller chamfers).
# =====================================================================================================================
CHAMFER_M = [(60, 10.0), (40, 5.0), (0, 3.5)]          # road reserve width ft >= key -> truncation in metres
def st_design_chamfer(ctx):
    """Corner truncations (chamfers) on corner plots; plots and road reserves updated together (guide section 6)."""
    if not ctx.get('chamfer'): print('   corner chamfers not requested (--chamfer)'); return
    import geopandas as gpd, numpy as np, re, math, shapely
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    W = ctx['WORK']; FTM = 0.3048
    RD = gpd.read_file(W + 'layout_roads.gpkg'); width = lambda c: float(re.search(r'(\d+(?:\.\d+)?)\s*ft', c).group(1)) if re.search(r'(\d+(?:\.\d+)?)\s*ft', str(c)) else 30.0
    RD['w'] = [width(c) for c in RD.Class]; ROAD = RD.union_all(); tree = shapely.STRtree(list(RD.geometry))
    def road_at(seg):
        """the reserve width of the road an edge fronts (None: not a road edge)"""
        b = seg.buffer(3); best = None
        for k in tree.query(b):
            a = RD.geometry.iloc[k].intersection(b).area
            if a > 0.4 * seg.length * 3 and (best is None or a > best[0]): best = (a, RD.w.iloc[k], k)
        return best
    gain, loss = {}, {}; n_cut = 0                                       # per road reserve: land it gains (chamfers) / gives back (rounded corners squared)
    def chamfer(g):
        """square the corner to the plot, then cut the straight chamfer at the LUSPA distance"""
        nonlocal n_cut
        if g.geom_type != 'Polygon': return g
        c = np.array(g.exterior.simplify(3.0).coords)[:-1]; n = len(c); new = g
        E = [(c[q], c[(q + 1) % n]) for q in range(n)]; L_ = [np.linalg.norm(b - a) for a, b in E]
        RF = [road_at(shapely.LineString([a, b])) if L_[q] >= 25 else None for q, (a, b) in enumerate(E)]
        for q in range(n):                                                 # a long road edge, short pieces (the kerb curve), then the next long road edge
            if not RF[q]: continue
            t = (q + 1) % n; short = 0.0
            while L_[t] < 25 and t != q: short += L_[t]; t = (t + 1) % n
            if t == q or short > 45 or not RF[t]: continue
            (a1, b1), (a2, b2) = E[q], E[t]; u1, u2 = (b1 - a1) / L_[q], (b2 - a2) / L_[t]
            den = u1[0] * u2[1] - u1[1] * u2[0]
            if abs(den) < 1e-6: continue
            tt = ((a2 - a1)[0] * u2[1] - (a2 - a1)[1] * u2[0]) / den; v = a1 + u1 * tt          # the corner the two edges would make
            e1, e2 = -u1 * L_[q], u2 * L_[t]; l1, l2 = L_[q], L_[t]
            ang = math.degrees(math.acos(max(-1, min(1, (e1 @ e2) / (l1 * l2)))))
            if not 45 <= ang <= 120: continue
            r1, r2 = RF[q], RF[t]
            k = r1[2] if r1[1] >= r2[1] else r2[2]; wmax = max(r1[1], r2[1])
            d = min(next(m for w0, m in CHAMFER_M if wmax >= w0) / FTM, 0.25 * min(l1, l2))      # LUSPA distance, at most a quarter of the plot side
            if d < 4: continue
            big = Polygon([tuple(v), tuple(v + e1 / l1 * min(l1, d + 25)), tuple(v + e2 / l2 * min(l2, d + 25))])
            sq = new.union(big.intersection(ROAD)).buffer(0.01).buffer(-0.01)  # the corner squared (the kerb curve's land back to the plot)
            tri = Polygon([tuple(v), tuple(v + e1 / l1 * d), tuple(v + e2 / l2 * d)])
            nn = sq.difference(tri.buffer(0.01))
            nn = max(shapely.get_parts(nn), key=lambda q: q.area) if nn.geom_type != 'Polygon' else nn
            back, taken = nn.difference(new), new.difference(nn)
            if taken.area < 2 and back.area < 2: continue
            gain.setdefault(k, []).append(taken); loss.setdefault(k, []).append(back); new = nn; n_cut += 1
        return new
    for f in ('plots_landuse.gpkg', 'reserves_landuse.gpkg'):
        if not os.path.exists(W + f): continue
        G = gpd.read_file(W + f)
        if 'chamfered' not in G: G['chamfered'] = 0
        n0 = n_cut; out_ = []
        for g, done_ in zip(G.geometry, G.chamfered):
            if done_: out_.append(g); continue                              # chamfered on an earlier run: left as it is
            k0 = n_cut; out_.append(chamfer(g))
        G['chamfered'] = [1 if (d_ or g2 is not g1) else 0 for d_, g1, g2 in zip(G.chamfered, G.geometry, out_)]; G['geometry'] = out_
        if 'area' in G: G['area'] = G.area
        G.to_file(W + f)
    back_all = unary_union([t for ts in loss.values() for t in ts]) if loss else None   # squared corners go back to the plots, whichever reserve held them
    for k in range(len(RD)):
        g_ = unary_union([RD.geometry.iloc[k]] + gain.get(k, []))
        if back_all is not None and not back_all.is_empty: g_ = g_.difference(back_all.buffer(0.01))
        RD.at[RD.index[k], 'geometry'] = g_.buffer(0.05).buffer(-0.05)
    RD.drop(columns='w').to_file(W + 'layout_roads.gpkg')
    tot = (sum(t.area for ts in gain.values() for t in ts) - sum(t.area for ts in loss.values() for t in ts)) * FTM * FTM
    print(f'   corner chamfers: {n_cut} plot corners truncated (local 3.5 m, collector 5 m, arterial 10 m; max 25 % of the plot side; rounded kerb corners squared to a straight chamfer), net {tot:+.0f} m2 to the road reserves', flush=True)
