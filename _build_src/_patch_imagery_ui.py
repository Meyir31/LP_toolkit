p = 'webapp/app.py'; s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:70]; s = s.replace(a, b, 1)
rep("    return [PY, '-u', '-W', 'ignore', SCRIPT, wf, '--site', site, '--name', m['name'], '--title', m.get('title') or m['name']]",
    "    return [PY, '-u', '-W', 'ignore', SCRIPT, wf, '--site', site, '--name', m['name'], '--title', m.get('title') or m['name'], '--imagery', m.get('imagery', 'google')]")
rep("    cmd = [PY, '-u', '-W', 'ignore', SCRIPT, wf, '--site', site, '--name', m['name'], '--title', m.get('title') or m['name']]",
    "    cmd = [PY, '-u', '-W', 'ignore', SCRIPT, wf, '--site', site, '--name', m['name'], '--title', m.get('title') or m['name'], '--imagery', m.get('imagery', 'google')]")
rep("if k in ('title', 'workflow', 'profile', 'stream_buffer')}", "if k in ('title', 'workflow', 'profile', 'stream_buffer', 'imagery')}")
open(p, 'w', encoding='utf-8').write(s)
p = 'webapp/static/index.html'; s = open(p, encoding='utf-8').read()
a = '<div class="row"><button class="draw" data-kind="site" data-shape="polygon">Draw boundary</button><label class="file">Upload KML / GeoJSON / zipped SHP<input type="file" data-kind="site"></label></div>'
assert a in s
s = s.replace(a, a + '''
          <div class="row"><span class="mini">Satellite imagery for the analysis</span><select id="imagery"><option value="google">Google satellite (Esri as fallback)</option><option value="esri">Esri World Imagery (Google as fallback)</option></select></div>''')
open(p, 'w', encoding='utf-8').write(s)
p = 'webapp/static/app.js'; s = open(p, encoding='utf-8').read()
a = "  P = await api(`/api/projects/${id}`); $('#noProj').hidden = true;"
assert a in s
s = s.replace(a, "  P = await api(`/api/projects/${id}`); $('#imagery').value = P.imagery || 'google'; $('#noProj').hidden = true;")
a = "$('#pTitle').onchange = () => post(`/api/projects/${P.id}/meta`, { title: $('#pTitle').value });"
assert a in s
s = s.replace(a, a + "\n$('#imagery').onchange = () => post(`/api/projects/${P.id}/meta`, { imagery: $('#imagery').value });")
open(p, 'w', encoding='utf-8').write(s)
print('ok')
