p = 'toolkit_src/new_stages.py'; s = open(p, encoding='utf-8').read()
a = """    tries = [('Esri World Imagery', cx.providers.Esri.WorldImagery, 4), ('Esri World Imagery (slow, 1 connection)', cx.providers.Esri.WorldImagery, 1),
             ('Google satellite (fallback)', GOOGLE_SAT, 2)]"""
assert a in s
s = s.replace(a, """    G = [('Google satellite', GOOGLE_SAT, 4), ('Google satellite (slow, 1 connection)', GOOGLE_SAT, 1)]
    E = [('Esri World Imagery', cx.providers.Esri.WorldImagery, 4), ('Esri World Imagery (slow, 1 connection)', cx.providers.Esri.WorldImagery, 1)]
    tries = (E + G) if IMAGERY_PREF == 'esri' else (G + E)""")
s = s.replace("GOOGLE_SAT = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'", "GOOGLE_SAT = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'\nIMAGERY_PREF = 'google'                                 # set by --imagery google | esri")
s = s.replace('"""satellite tiles with retries: Esri (8 retries per tile, 4 connections) -> Esri slowly (1 connection) -> Google satellite.', '"""satellite tiles with retries (8 per tile): preferred source (Google by default), then slowly on 1 connection, then the other source.')
s = s.replace("raise RuntimeError(f'satellite imagery could not be downloaded (Esri and Google both failed): {last}')", "raise RuntimeError(f'satellite imagery could not be downloaded (Google and Esri both failed): {last}')")
open(p, 'w', encoding='utf-8').write(s)
p = 'toolkit_src/cli.py'; s = open(p, encoding='utf-8').read()
a = "        p.add_argument('--from', dest='from_'); p.add_argument('--only')"
assert a in s
s = s.replace(a, a + "\n        p.add_argument('--imagery', choices=['google', 'esri'], default='google', help='satellite imagery source (the other one is the fallback)')")
a = "    ctx = make_ctx(a, a.cmd); run("
assert a in s
s = s.replace(a, "    global IMAGERY_PREF\n    IMAGERY_PREF = getattr(a, 'imagery', 'google') or 'google'; print('imagery preference:', IMAGERY_PREF)\n" + a)
open(p, 'w', encoding='utf-8').write(s)
g = 'toolkit_src/guide.md'; t = open(g, encoding='utf-8').read()
t = t.replace("| Esri World Imagery (contextily, zoom 19) | Digitizing, checks, map backgrounds | 0.299 m/px at 5.5 N. EPSG:3857 metres are close to ground metres near the equator |",
 "| Satellite imagery (contextily, zoom 19): Google satellite by default (user choice 2026-11-17, Esri kept dropping connections), Esri World Imagery as the fallback (`--imagery esri` to prefer Esri) | Digitizing, checks, map backgrounds | 0.3 m/px at 5.5 N; 8 retries per tile, then a slow single-connection pass, then the other source. Google's terms allow its imagery only through official Google tools: fine for internal planning, use Esri or licensed imagery for published maps. The digitizing colour rules were calibrated on Esri (green cast): check the first Google runs against the building database |")
open(g, 'w', encoding='utf-8').write(t); print('ok')
