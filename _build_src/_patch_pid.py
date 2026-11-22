def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
patch('webapp/app.py', [
 ("# ------------------------------------------------------------------ helpers\n",
  '''# ------------------------------------------------------------------ helpers
def pid_alive(pid):
    """True while a process with this id is running (Windows: exit code 259 = still active)"""
    if not pid: return False
    try:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not h: return False
        code = ctypes.c_ulong(); ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code)); ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259
    except Exception: return False
def is_running(pid_):
    """running = started by this server and not finished, or a run recorded in project.json whose process is still alive (survives app restarts)"""
    p = RUNS.get(pid_)
    if p is not None: return p.poll() is None
    try: return pid_alive(meta(pid_).get('pid'))
    except Exception: return False
'''),
 ("    RUNS[pid] = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=TOOLKIT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))\n    m = meta(pid); m['last_run'] = time.strftime('%Y-%m-%d %H:%M'); m['pending_load'] = pending; save_meta(pid, m)",
  "    RUNS[pid] = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=TOOLKIT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))\n    m = meta(pid); m['last_run'] = time.strftime('%Y-%m-%d %H:%M'); m['pending_load'] = pending; m['pid'] = RUNS[pid].pid; save_meta(pid, m)"),
])
s = open('webapp/app.py', encoding='utf-8').read()
# every "already running" guard and the project list use is_running
s = s.replace("if pid in RUNS and RUNS[pid].poll() is None:", "if is_running(pid):")
s = s.replace("m['running'] = d in RUNS and RUNS[d].poll() is None; out.append(m)", "m['running'] = is_running(d); out.append(m)")
s = s.replace("    m['running'] = pid in RUNS and RUNS[pid].poll() is None\n", "    m['running'] = is_running(pid)\n")
# the run endpoint starts its own Popen: route it through the same bookkeeping
a = "    RUNS[pid] = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=TOOLKIT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))\n    m['last_run'] = time.strftime('%Y-%m-%d %H:%M'); save_meta(pid, m)"
if a in s:
    s = s.replace(a, "    RUNS[pid] = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=TOOLKIT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))\n    m['last_run'] = time.strftime('%Y-%m-%d %H:%M'); m['pid'] = RUNS[pid].pid; save_meta(pid, m)")
# stop: kill the whole process tree, also for runs started before a restart
a = "    p = RUNS.get(pid)\n    if p and p.poll() is None: p.terminate(); return jsonify(ok=True)\n    return jsonify(ok=False)"
assert a in s
s = s.replace(a, "    p = RUNS.get(pid); target = p.pid if (p and p.poll() is None) else meta(pid).get('pid')\n    if target and pid_alive(target):\n        subprocess.run(['taskkill', '/PID', str(target), '/T', '/F'], capture_output=True); return jsonify(ok=True)\n    return jsonify(ok=False)")
# status
a = "    p = RUNS.get(pid); running = p is not None and p.poll() is None"
assert a in s
s = s.replace(a, "    p = RUNS.get(pid); running = is_running(pid)")
open('webapp/app.py', 'w', encoding='utf-8').write(s)
print('ok', s.count('is_running('))
