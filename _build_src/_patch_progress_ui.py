def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
# ---------------- server ----------------
patch('webapp/app.py', [
 ("        cmd += ['--profile', j.get('profile', 'auto')]", "        cmd += ['--profile', j.get('profile', 'auto'), '--buildings', j.get('buildings', m.get('buildings', 'fast'))]"),
 ("if k in ('title', 'workflow', 'profile', 'stream_buffer', 'imagery')}", "if k in ('title', 'workflow', 'profile', 'stream_buffer', 'imagery', 'buildings')}"),
 ("    pend = meta(pid).get('pending_load') if not running else None",
  """    pend = meta(pid).get('pending_load') if not running else None
    prog, note = {}, {}
    for mm in re.finditer(r'^@@progress (\\w+) (\\d+) ?(.*)$', txt, flags=re.M): prog[mm.group(1)] = int(mm.group(2)); note[mm.group(1)] = mm.group(3).strip()
    txt = re.sub(r'^@@progress .*\\n?', '', txt, flags=re.M)"""),
 ("returncode=rc, pending_load=pend)", "returncode=rc, pending_load=pend, progress=prog, notes=note)"),
])
# ---------------- page ----------------
patch('webapp/static/index.html', [
 ('          <div class="card"><div class="cardh">Plot profile</div>',
  '''          <div class="card"><div class="cardh">Buildings</div>
            <label class="tl"><input type="radio" name="bmode" value="fast" checked> OpenStreetMap + building database (fast: about 15 to 25 minutes)</label>
            <label class="tl"><input type="radio" name="bmode" value="full"> Also detect buildings on the image with SAM (slow: about 3 minutes per image tile, hours for a large site; use where footprints are missing)</label>
            <p class="hint">Fast route: OSM outlines where they exist, database outlines (Google, Microsoft) where OSM has none, occupancy and height for every building, walls and fences from the image.</p></div>
          <div class="card"><div class="cardh">Plot profile</div>'''),
])
patch('webapp/static/app.css', [("[hidden] { display: none !important; }", """[hidden] { display: none !important; }
.stages label { display: block; position: relative; }
.stages .pb { height: 5px; background: #e6e8eb; border-radius: 3px; margin-top: 5px; overflow: hidden; }
.stages .pb i { display: block; height: 100%; width: 0; background: #1f5f8b; transition: width .6s; }
.stages label.done .pb i { background: #2f7d32; width: 100% !important; }
.stages .pb.ind i { width: 35% !important; animation: pbmove 1.3s ease-in-out infinite; }
@keyframes pbmove { 0% { margin-left: -35%; } 100% { margin-left: 100%; } }
.stages .pct { float: right; font-size: 11px; color: #6b7280; }
.stages .nt { display: block; font-size: 11px; color: #6b7280; min-height: 0; }""")])
# ---------------- script ----------------
patch('webapp/static/app.js', [
 ("const STAGES = { existing: ['fetch', 'sam', 'digitize', 'compare', 'clean', 'database', 'roads', 'landuse', 'reserves', 'trees', 'blocks', 'plots', 'map'], design: ['site', 'roads', 'subdivide', 'landuse', 'audit'] };",
  "const STAGES = { existing: ['fetch', 'footprints', 'roads', 'landuse', 'reserves', 'trees', 'blocks', 'plots', 'map'], existing_full: ['fetch', 'sam', 'digitize', 'compare', 'clean', 'database', 'roads', 'landuse', 'reserves', 'trees', 'blocks', 'plots', 'map'], design: ['site', 'roads', 'subdivide', 'landuse', 'audit'] };\nconst stagesOf = wf => wf === 'existing' && (P?.buildings === 'full') ? STAGES.existing_full : STAGES[wf];"),
 ("database: 'check vs building database',", "database: 'check vs building database', footprints: 'OSM + building database, walls',"),
 ("  $('#stageList').innerHTML = STAGES[wf].map((s, i) => `<label title=\"${STAGE_HELP[s] || ''}\"><input type=\"radio\" name=\"stage\" value=\"${s}\" ${i === 0 ? 'checked' : ''}> ${i + 1}. ${s}</label>`).join('');",
  "  $('#stageList').innerHTML = stagesOf(wf).map((s, i) => `<label title=\"${STAGE_HELP[s] || ''}\" data-s=\"${s}\"><input type=\"radio\" name=\"stage\" value=\"${s}\" ${i === 0 ? 'checked' : ''}> ${i + 1}. ${s}<span class=\"pct\"></span><div class=\"pb\"><i></i></div><span class=\"nt\"></span></label>`).join('');"),
 ("  P = await api(`/api/projects/${id}`);", "  P = await api(`/api/projects/${id}`); P.buildings = P.buildings || 'fast'; $$('input[name=bmode]').forEach(r => r.checked = r.value === P.buildings);"),
 ("$('#pTitle').onchange = () => post(`/api/projects/${P.id}/meta`, { title: $('#pTitle').value });",
  "$('#pTitle').onchange = () => post(`/api/projects/${P.id}/meta`, { title: $('#pTitle').value });\n$$('input[name=bmode]').forEach(r => r.onchange = () => { P.buildings = r.value; post(`/api/projects/${P.id}/meta`, { buildings: r.value }); setWorkflow(P.workflow, false); });"),
 ("  const body = { workflow: P.workflow, profile: $('#profile').value, roads_mode: 'file', stream_buffer: +$('#streamBuf').value, steep: +$('#steep').value };",
  "  const body = { workflow: P.workflow, profile: $('#profile').value, roads_mode: 'file', stream_buffer: +$('#streamBuf').value, steep: +$('#steep').value, buildings: P.buildings || 'fast' };"),
 ("""  $$('#stageList label').forEach(l => { const v = l.querySelector('input').value; l.classList.toggle('done', doneSet.has(v)); l.classList.toggle('now', s.running && s.stages[s.stages.length - 1] === v && !doneSet.has(v)); });""",
  """  const cur = s.running ? s.stages[s.stages.length - 1] : null;
  $$('#stageList label').forEach(l => {
    const v = l.dataset.s, done = doneSet.has(v), now = v === cur && !done, pct = (s.progress || {})[v];
    l.classList.toggle('done', done); l.classList.toggle('now', now);
    const pb = l.querySelector('.pb'), bar = pb.firstElementChild, ran = s.stages.includes(v);
    pb.classList.toggle('ind', now && !(pct > 0)); bar.style.width = done ? '100%' : now ? `${pct || 0}%` : (ran && !done && s.failed ? `${pct || 0}%` : '0');
    l.querySelector('.pct').textContent = done ? '100%' : now ? (pct > 0 ? `${pct}%` : '') : '';
    l.querySelector('.nt').textContent = now ? ((s.notes || {})[v] || '') : '';
  });"""),
])
print('ok')
