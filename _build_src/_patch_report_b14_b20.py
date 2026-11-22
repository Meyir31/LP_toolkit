"""Test report fixes B14-B20: base-map switcher, Standards, Guide close, plot profile, project names, project switch, plain errors."""
import os, re
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'webapp'))
def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert s.count(a) == 1, (p, s.count(a), a[:90]); s = s.replace(a, b)
    open(p, 'w', encoding='utf-8').write(s)

# ---------------- server ----------------
patch('app.py', [
 # B18: blank names refused, duplicate names explained
 ("    j = request.get_json(force=True); name = slug(j.get('name', 'project')); pid = name",
  "    j = request.get_json(force=True)\n    if not str(j.get('name') or '').strip(): return jsonify(error='Give the project a name.'), 400\n    name = slug(j.get('name')); pid = name"),
 ("    if os.path.exists(d): return jsonify(error=f'project \"{name}\" already exists'), 400",
  "    if os.path.exists(d): return jsonify(error=f'A project called \"{name}\" already exists. Choose another name (or open it from the project list).'), 400"),
 # B17: the profile used by the last run is remembered and shown
 ("    m['running'] = is_running(pid)\n    return jsonify(m)",
  """    m['running'] = is_running(pid)
    if not m.get('profile'):                                           # older projects: read it from the last run's command line
        f = os.path.join(d, 'run.log')
        if os.path.exists(f):
            mt = re.search(r'--profile (\\w+)', open(f, encoding='utf-8', errors='replace').readline())
            if mt: m['profile'] = mt.group(1)
    return jsonify(m)"""),
 ("        cmd += ['--profile', j.get('profile', 'auto'), '--buildings', j.get('buildings', m.get('buildings', 'fast'))]",
  "        prof_ = j.get('profile') or m.get('profile') or 'auto'; m['profile'] = prof_\n        cmd += ['--profile', prof_, '--buildings', j.get('buildings', m.get('buildings', 'fast'))]"),
 # B20: an unreadable upload gets a plain message, no GDAL text or temp paths
 ("    except Exception as e: return jsonify(error=str(e)), 400\n    return jsonify(ok=True, features=n)",
  "    except Exception as e:\n        print('upload failed:', e, flush=True)\n        return jsonify(error='This file could not be read as map data. Upload a KML / KMZ, a GeoJSON, or a zipped shapefile (.zip with the .shp, .shx, .dbf and .prj).'), 400\n    return jsonify(ok=True, features=n)"),
 ("if __name__ == '__main__':", """# B20: an unexpected server error is answered in plain words (the details go to the server console only)
from werkzeug.exceptions import HTTPException
@app.errorhandler(Exception)
def _plain_error(ex):
    if isinstance(ex, HTTPException): return ex
    import traceback; traceback.print_exc()
    return jsonify(error=f'Something went wrong on the server ({type(ex).__name__}). The action was not completed; nothing was changed. Details are in the app console.'), 500

if __name__ == '__main__':"""),
])

# ---------------- page ----------------
patch('static/app.js', [
 # B19: nothing carries over from the previous project
 ("async function openProject(id) {\n  stopTool();",
  "async function openProject(id) {\n  stopTool(); if (typeof Editor !== 'undefined') Editor.close();\n  $('#confirmAlert') && ($('#confirmAlert').hidden = true); document.querySelector('.confirmbox') && (document.querySelector('.confirmbox').hidden = true); map.closePopup();\n  $$('.tabs button')[0]?.click();"),
 # B17: the panel shows the project's profile
 ("$('#imagery').value = P.imagery || 'google';", "$('#imagery').value = P.imagery || 'google'; if ($('#profile')) $('#profile').value = P.profile || 'auto';"),
 # B18: messages in the dialog itself; blank name caught before sending
 ("$('#nCreate').onclick = async () => { try { const p = await post('/api/projects', { name: $('#nName').value, title: $('#nTitle').value, workflow: newWf }); $('#newDlg').hidden = true; loadProjects(p.id); } catch (e) { alert(e.message); } };",
  "$('#nCreate').onclick = async () => { const msg = $('#nMsg'); msg.textContent = '';\n  if (!$('#nName').value.trim()) { msg.textContent = 'Give the project a name.'; $('#nName').focus(); return; }\n  try { const p = await post('/api/projects', { name: $('#nName').value, title: $('#nTitle').value, workflow: newWf }); $('#newDlg').hidden = true; $('#nName').value = ''; $('#nTitle').value = ''; loadProjects(p.id); } catch (e) { msg.textContent = e.message; } };"),
 ("$('#newProj').onclick = () => { $('#newDlg').hidden = false; $('#nName').focus(); };", "$('#newProj').onclick = () => { $('#nMsg').textContent = ''; $('#newDlg').hidden = false; $('#nName').focus(); };"),
 # B16: Guide (and other pop-ups in #modal) close with Escape or a click outside
 ("$('#mClose').onclick = () => $('#modal').hidden = true;",
  "$('#mClose').onclick = () => $('#modal').hidden = true;\n$('#modal').addEventListener('click', e => { if (e.target.id === 'modal') $('#modal').hidden = true; });\ndocument.addEventListener('keydown', e => { if (e.key === 'Escape') { if (!$('#modal').hidden) $('#modal').hidden = true; if (!$('#newDlg').hidden) $('#newDlg').hidden = true; } });"),
])
patch('static/index.html', [
 ('  <div class="row right"><button class="ghost" id="nCancel">Cancel</button><button id="nCreate">Create</button></div>',
  '  <div id="nMsg" class="errmsg"></div>\n  <div class="row right"><button class="ghost" id="nCancel">Cancel</button><button id="nCreate">Create</button></div>'),
])
# B17: Update map re-runs with the project's own profile
patch('static/editor.js', [("{ workflow: 'existing', only: 'map', buildings: P.buildings || 'fast' }", "{ workflow: 'existing', only: 'map', buildings: P.buildings || 'fast', profile: P.profile || $('#profile')?.value || 'auto' }")])
# B15: Standards opens on the first click (wired at once, dialog shown before the data loads); a legend click clears the search
s = open('static/standards.js', encoding='utf-8').read()
a = "  async function open(code) {\n    await load(); $('#stdDlg').hidden = false; list($('#stdQ').value);"
assert s.count(a) == 1
s = s.replace(a, "  async function open(code) {\n    $('#stdDlg').hidden = false; if (code) $('#stdQ').value = '';\n    if (!DATA) $('#stdBody').innerHTML = '<p class=\"mini\">Loading the standards...</p>';\n    await load(); list($('#stdQ').value);")
a = "  document.addEventListener('DOMContentLoaded', () => {\n    $('#stdBtn').onclick = () => open();"
assert s.count(a) == 1
s = s.replace(a, "  const wire = () => {\n    $('#stdBtn').onclick = () => open();")
a = "    document.addEventListener('click', e => { const s = e.target.closest('[data-luspa]'); if (s) open(s.dataset.luspa); });\n  });"
assert s.count(a) == 1
s = s.replace(a, "    document.addEventListener('click', e => { const s = e.target.closest('[data-luspa]'); if (s) open(s.dataset.luspa); });\n  };\n  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire); else wire();")
open('static/standards.js', 'w', encoding='utf-8').write(s)
# B14: the base-map switcher opens above the tools bar
open('static/app.css', 'a', encoding='utf-8').write("""
/* B14: map controls on the right (base-map switcher) above the tools bar */
.leaflet-top.leaflet-right { z-index: 1101; }
.errmsg { color: #c62828; font-size: 13px; min-height: 18px; margin-top: 6px; }
""")
print('ok')
