p = 'toolkit_src/new_stages.py'; s = open(p, encoding='utf-8').read()
helper = '''
GOOGLE_SAT = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
def robust_tiles(w, s, e, n, zoom, path=None, ll=True):
    """satellite tiles with retries: Esri (8 retries per tile, 4 connections) -> Esri slowly (1 connection) -> Google satellite.
    path given: writes a GeoTIFF (EPSG:3857) and returns None; otherwise returns (image, extent) like contextily.bounds2img"""
    import contextily as cx
    tries = [('Esri World Imagery', cx.providers.Esri.WorldImagery, 4), ('Esri World Imagery (slow, 1 connection)', cx.providers.Esri.WorldImagery, 1),
             ('Google satellite (fallback)', GOOGLE_SAT, 2)]
    last = None
    for k, (name, src, nc) in enumerate(tries):
        try:
            if path: cx.bounds2raster(w, s, e, n, path, zoom=zoom, source=src, ll=ll, max_retries=8, wait=2, n_connections=nc, timeout=60); out = None
            else: out = cx.bounds2img(w, s, e, n, zoom=zoom, source=src, ll=ll, max_retries=8, wait=2, n_connections=nc, timeout=60)
            print(f'   imagery source: {name}', flush=True); return out
        except Exception as ex:
            last = ex; print(f'   imagery download failed ({name}): {str(ex)[:120]}; trying again in 20 s', flush=True); time.sleep(20)
    raise RuntimeError(f'satellite imagery could not be downloaded (Esri and Google both failed): {last}')
'''
a = "def st_fetch(ctx):"
assert a in s
s = s.replace(a, helper + a, 1)
a = "        cx.bounds2raster(w - b, s - b, e + b, n + b, WORK + 'img_z19_3857.tif', zoom=19, source=cx.providers.Esri.WorldImagery, ll=True)"
assert a in s
s = s.replace(a, "        robust_tiles(w - b, s - b, e + b, n + b, 19, path=WORK + 'img_z19_3857.tif')")
open(p, 'w', encoding='utf-8').write(s)
p = 'toolkit_src/build.py'; s = open(p, encoding='utf-8').read()
a = "def site_fix(s):\n"
assert a in s
s = s.replace(a, a + "    s = must(s, \"img, ext = cx.bounds2img(w, s, e, n, zoom=18, source=cx.providers.Esri.WorldImagery)\", \"img, ext = robust_tiles(w, s, e, n, 18, ll=False)\", 1, 'site')\n", 1)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
