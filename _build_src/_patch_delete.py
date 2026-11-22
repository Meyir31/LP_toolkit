p = 'webapp/app.py'; s = open(p, encoding='utf-8').read()
a = "@app.get('/api/projects/<pid>')\ndef project(pid):"
assert a in s
if 'def delete_project' not in s:
    s = s.replace(a, '''@app.delete('/api/projects/<pid>')
def delete_project(pid):
    """move the project to LP_Projects/_deleted/<name>_<date-time> (recoverable: move the folder back)"""
    d = pdir(pid)
    if pid in RUNS and RUNS[pid].poll() is None: return jsonify(error='the project is running: stop it first'), 400
    trash = os.path.join(ROOT, '_deleted'); os.makedirs(trash, exist_ok=True)
    dest = os.path.join(trash, f"{pid}_{time.strftime('%Y%m%d-%H%M%S')}")
    try: shutil.move(d, dest)
    except Exception as e: return jsonify(error=f'could not move the project folder (is a file open in ArcGIS or a viewer?): {e}'), 400
    RUNS.pop(pid, None); return jsonify(ok=True, moved_to=dest)
''' + a)
open(p, 'w', encoding='utf-8').write(s)
p = 'webapp/static/index.html'; s = open(p, encoding='utf-8').read()
a = '<div class="ptitle"><h2 id="pName"></h2><span id="pState" class="badge"></span></div>'
assert a in s
s = s.replace(a, '<div class="ptitle"><h2 id="pName"></h2><span><span id="pState" class="badge"></span> <button id="delProj" class="ghost danger" title="Delete this project">Delete</button></span></div>')
open(p, 'w', encoding='utf-8').write(s); print('ok')
