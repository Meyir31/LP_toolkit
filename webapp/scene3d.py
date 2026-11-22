"""3D view support: terrain tiles (Terrarium PNG) from the project DEM, and buildings with heights."""
import os, io, math, glob, threading
import numpy as np

_DEM = {}            # project dir -> (path, fill value)
_LOCK = threading.Lock()
_TILES = {}          # (path, z, x, y) -> png bytes (small cache)
COP = 'https://copernicus-dem-30m.s3.amazonaws.com/{t}/{t}.tif'


def _cop_tile(lat, lon):
    return f"Copernicus_DSM_COG_10_{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00_{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00_DEM"


def dem_for(project_dir, out_dir, site_geojson):
    """the project's DEM: the toolkit's _work/dem.tif, else a cached cut of the Copernicus 30 m DEM around the site"""
    with _LOCK:
        import rasterio, geopandas as gpd
        from rasterio.warp import transform_bounds
        sb = tuple(round(v, 5) for v in gpd.read_file(site_geojson).to_crs(4326).total_bounds)   # the site as it is now (it may have been redrawn)
        def covers(fn):
            try:
                with rasterio.open(fn) as r: L, B, R, T = transform_bounds(r.crs, 'EPSG:4326', *r.bounds)
                return L <= sb[0] and B <= sb[1] and R >= sb[2] and T >= sb[3]
            except Exception: return False
        if project_dir in _DEM and _DEM[project_dir][2] == sb and os.path.exists(_DEM[project_dir][0]): return _DEM[project_dir][:2]
        f = os.path.join(project_dir, '_dem3d.tif')                      # a cut with a margin round the site (the toolkit's DEM covers the site only)
        if os.path.exists(f) and not covers(f): os.remove(f)             # cut for an older boundary: cut again
        if not os.path.exists(f):
            try:
                import geopandas as gpd
                from rasterio.merge import merge
                w, s, e, n = gpd.read_file(site_geojson).to_crs(4326).total_bounds
                m = 0.03; w, s, e, n = w - m, s - m, e + m, n + m
                srcs = [rasterio.open('/vsicurl/' + COP.format(t=_cop_tile(la, lo)))
                        for la in range(math.floor(s), math.floor(n) + 1) for lo in range(math.floor(w), math.floor(e) + 1)]
                arr, tr = merge(srcs, bounds=(w, s, e, n))
                prof = srcs[0].profile.copy(); prof.update(driver='GTiff', height=arr.shape[1], width=arr.shape[2], transform=tr, count=1, compress='deflate', tiled=False)
                prof.pop('blockxsize', None); prof.pop('blockysize', None)
                with rasterio.open(f, 'w', **prof) as o: o.write(arr[0], 1)
            except Exception:
                f = os.path.join(out_dir, '_work', 'dem.tif')             # offline: the toolkit's own DEM
                if not os.path.exists(f): raise
        with rasterio.open(f) as r:
            a = r.read(1, masked=True).astype(float); fill = float(a.mean()) if a.count() else 0.0
        _DEM[project_dir] = (f, fill, sb)
        return _DEM[project_dir][:2]


def terrarium_png(dem_path, fill, z, x, y):
    """one 256 px Web Mercator tile, Terrarium encoded (v = elevation + 32768)"""
    key = (dem_path, z, x, y)
    if key in _TILES: return _TILES[key]
    try: return _terrarium(dem_path, fill, z, x, y, key)
    except Exception: return flat_png(fill)                             # never fail a tile: a flat one keeps the terrain alive


def flat_png(fill=0.0):
    from PIL import Image
    v = fill + 32768; rgb = np.zeros((256, 256, 3), 'uint8'); rgb[..., 0] = int(v // 256); rgb[..., 1] = int(v) % 256
    b = io.BytesIO(); Image.fromarray(rgb, 'RGB').save(b, 'PNG'); return b.getvalue()


def _terrarium(dem_path, fill, z, x, y, key):
    import rasterio
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_bounds
    from PIL import Image
    R = 20037508.342789244; size = 2 * R / 2 ** z
    x0, y1 = -R + x * size, R - y * size; x1, y0 = x0 + size, y1 - size
    dst = np.full((256, 256), np.nan, dtype='float32')
    with rasterio.open(dem_path) as src:
        reproject(rasterio.band(src, 1), dst, src_nodata=src.nodata, dst_transform=from_bounds(x0, y0, x1, y1, 256, 256),
                  dst_crs='EPSG:3857', dst_nodata=np.nan, resampling=Resampling.bilinear)
    dst = np.where(np.isfinite(dst), dst, fill)
    v = dst.astype('float64') + 32768
    rgb = np.dstack([np.floor(v / 256), np.floor(v) % 256, np.floor((v - np.floor(v)) * 256)]).clip(0, 255).astype('uint8')
    b = io.BytesIO(); Image.fromarray(rgb, 'RGB').save(b, 'PNG')
    if len(_TILES) > 3000: _TILES.clear()
    _TILES[key] = b.getvalue(); return _TILES[key]


# ---------------- building heights ----------------
STOREY_M = 3.2
DEFAULT_STOREYS = {'Residential': 1, 'Mixed use (shop + residence)': 2, 'Commercial / mixed use': 2, 'Commercial': 2, 'Commercial (hotel)': 3,
                   'Office': 3, 'Health': 2, 'Education': 1, 'Civic': 2, 'Religious': 1, 'Market': 1, 'Industrial': 1}


def storeys_of(row):
    """(storeys, source): database height tag (H:n, HBET:a-b) first, otherwise an estimate from the use and footprint"""
    h = str(row.get('height') or '')
    if h.startswith('H:'):
        try: return max(1, int(float(h[2:]))), 'database'
        except ValueError: pass
    if h.startswith('HBET:'):
        try:
            a, b = [float(t) for t in h[5:].split('-')]
            est = 1 if (row.get('area_m2') or 0) < 200 else 2 if (row.get('area_m2') or 0) < 600 else 3
            return int(min(max(est, a), b)), 'database range + estimate'
        except ValueError: pass
    use = row.get('ex_use') or row.get('use') or 'Residential'
    n = DEFAULT_STOREYS.get(use, 1)
    a = row.get('area_m2') or 0
    if use == 'Residential' and a > 350: n = 2
    if a > 1500: n = max(n, 3)
    return n, 'estimate'


def buildings_fc(out_dir, pfx):
    """buildings (EPSG:4326 GeoJSON) with storeys, height_m and the source of the height"""
    import geopandas as gpd, json
    fs = [os.path.join(out_dir, pfx + 'Existing_land_use_buildings.shp')] + sorted(glob.glob(os.path.join(out_dir, '*uildings*.shp'))) + [os.path.join(out_dir, '_work', 'buildings.gpkg')]       # design projects: the existing buildings on the site
    f = next((x for x in fs if os.path.exists(x)), None)
    if not f: return {'type': 'FeatureCollection', 'features': []}
    g = gpd.read_file(f)
    if g.crs is None: g = g.set_crs(2136)
    if 'area_m2' not in g: g['area_m2'] = g.to_crs(2136).area * 0.0929
    st, src = zip(*[storeys_of(r) for r in g.to_dict('records')]) if len(g) else ((), ())
    keep = [c for c in ('bld_id', 'ex_use', 'use', 'occupancy', 'height', 'area_m2', 'src') if c in g.columns]
    out = g[keep + ['geometry']].copy(); out['storeys'] = st; out['height_m'] = [round(s * STOREY_M + 0.6, 1) for s in st]; out['h_source'] = src
    out = out.to_crs(4326); out['geometry'] = out.geometry.simplify(0.0000015)
    return json.loads(out.to_json(drop_id=True))
