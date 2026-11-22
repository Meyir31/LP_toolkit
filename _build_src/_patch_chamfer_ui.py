"""Web app: 'Chamfer corner plots' option for design runs + a button to chamfer an existing design."""
import os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'webapp'))
def patch(p, a, b):
    s = open(p, encoding='utf-8').read(); assert s.count(a) == 1, (p, s.count(a), a[:70]); open(p, 'w', encoding='utf-8').write(s.replace(a, b))
patch('static/index.html', '          <div class="row"><button id="runBtn">Run</button><button id="stopBtn" class="ghost">Stop</button></div>',
  '          <label class="chk" id="chamferRow" title="LUSPA corner truncations (Guidelines 10.1.1): 3.5 m on local roads, 5 m on collectors, 10 m on arterials; never more than a quarter of the plot side. The cut corner is added to the road reserve."><input type="checkbox" id="chamfer"> Chamfer corner plots after the design (LUSPA 3.5 / 5 / 10 m)</label>\n'
  '          <div class="row"><button id="runBtn">Run</button><button id="stopBtn" class="ghost">Stop</button></div>')
patch('static/index.html', '        <div class="card"><div class="cardh">Map layers</div><div id="layerList"></div><div id="legend"></div></div>',
  '        <div class="card"><div class="cardh">Map layers</div><div id="layerList"></div><div id="legend"></div></div>\n'
  '        <div class="card" id="chamferCard" hidden><div class="cardh">Corner plots</div><p class="hint">Cut LUSPA corner truncations on every corner plot of this design '
  '(3.5 m local, 5 m collector, 10 m arterial; at most a quarter of the plot side). Plots and road reserves change together; plots already chamfered are left as they are.</p>'
  '<button id="chamferNow">Chamfer corner plots now</button></div>')
patch('static/app.js', "  const body = { workflow: P.workflow, profile: $('#profile').value,",
      "  const body = { chamfer: P.workflow === 'design' && $('#chamfer').checked, workflow: P.workflow, profile: $('#profile').value,")
patch('static/app.js', "  rebuildLegend();\n  renderDownloads(r);",
      "  rebuildLegend();\n  $('#chamferCard').hidden = !(P.workflow === 'design' && kinds.has('plots_design'));\n  renderDownloads(r);")
patch('static/app.js', "$('#delProj').onclick = async () => {",
      "$('#chamferNow').onclick = async () => { if (!P) return;\n"
      "  try { await post(`/api/projects/${P.id}/run`, { workflow: 'design', only: 'chamfer,audit', chamfer: true }); $$('.tabs button')[1].click(); refreshStatus();"
      " alert('Chamfering the corner plots: the map updates when the run finishes.'); } catch (e) { alert(e.message); } };\n"
      "$('#delProj').onclick = async () => {")
patch('static/app.js', "  $('#designInputs').hidden = wf !== 'design';",
      "  $('#designInputs').hidden = wf !== 'design'; if ($('#chamferRow')) $('#chamferRow').hidden = wf !== 'design';")
patch('app.py', "    if j.get('only'): cmd += ['--only', j['only']]",
      "    if j.get('only'): cmd += ['--only', j['only']]\n    if wf == 'design' and j.get('chamfer'): cmd += ['--chamfer']")
print('ok')
