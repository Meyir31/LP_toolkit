def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
ICONS = r'''  const SV = d => `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const IC = {
    select: SV('<path d="M5 3l12 8-5.5 1.2L9 18z" fill="currentColor" fill-opacity=".15"/><path d="M12 12.5l4 6"/>'),
    clear: SV('<rect x="3" y="3" width="18" height="18" rx="2" stroke-dasharray="3 2"/><path d="M9 9l6 6M15 9l-6 6"/>'),
    create: SV('<path d="M3 20l6-6 5 2 7-11"/><circle cx="3" cy="20" r="1.4" fill="currentColor"/><circle cx="21" cy="5" r="1.4" fill="currentColor"/><path d="M15 19h6M18 16v6"/>'),
    offset: SV('<path d="M3 8c5-4 13-4 18 0"/><path d="M3 16c5-4 13-4 18 0" stroke-dasharray="3 2"/><path d="M12 7.5v5M10 10.5l2 2 2-2"/>'),
    extend: SV('<path d="M3 12h10" /><path d="M13 12h5" stroke-dasharray="2 2"/><path d="M21 5v14"/><path d="M15 9l3 3-3 3"/>'),
    trim: SV('<circle cx="6" cy="7" r="2.5"/><circle cx="6" cy="17" r="2.5"/><path d="M8 8.5L20 17M8 15.5L20 7"/>'),
    split: SV('<path d="M3 12h7M14 12h7"/><path d="M12 5v14" stroke-dasharray="2 2"/><circle cx="10" cy="12" r="1.3" fill="currentColor"/><circle cx="14" cy="12" r="1.3" fill="currentColor"/>'),
    square: SV('<path d="M4 20V4"/><path d="M4 20h16"/><path d="M4 14h6v6"/>'),
    attr: SV('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11"/>'),
    delete: SV('<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>'),
    undo: SV('<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-3"/>'),
    redo: SV('<path d="M15 14l5-5-5-5"/><path d="M20 9H10a6 6 0 000 12h3"/>'),
    snap: SV('<path d="M6 3v8a6 6 0 0012 0V3"/><path d="M6 7h4M14 7h4"/><path d="M10 3v8a2 2 0 004 0V3"/>'),
    hide: SV('<path d="M18 15l-6-6-6 6"/>'), edit: SV('<path d="M4 20h4l11-11-4-4L4 16z"/><path d="M13 7l4 4"/>'),
    min: SV('<path d="M5 12h14"/>'), max: SV('<rect x="5" y="5" width="14" height="14" rx="1"/>'),
  };
  const B = (attr, ic, label, tip) => `<button ${attr} title="${tip}">${IC[ic]}<span>${label}</span></button>`;
'''
patch('webapp/static/editor.js', [
 ("  // ------------------------------------------------------------------ ribbon\n  const rib = L.DomUtil.create('div', 'ribbon', map.getContainer());",
  "  // ------------------------------------------------------------------ ribbon (icons, ArcGIS Pro style; collapsible)\n" + ICONS + "  const rib = L.DomUtil.create('div', 'ribbon', map.getContainer());"),
 ("""  rib.innerHTML = `
    <div class="grp"><span class="gl">Selection</span><button data-t="select" title="Click a road; Shift+click adds; Ctrl+drag draws a box">Select</button><button data-a="clear" title="Clear the selection">Clear</button></div>
    <div class="grp"><span class="gl">Create</span><button data-t="create">Create road</button></div>
    <div class="grp"><span class="gl">Modify</span><button data-t="offset">Offset</button><button data-t="extend">Extend</button><button data-t="trim">Trim</button><button data-t="split">Split</button><button data-t="square">Square ends</button><button data-t="attr">Attributes</button><button data-t="delete">Delete</button></div>
    <div class="grp"><span class="gl">Edit</span><button data-a="undo" title="Ctrl+Z">Undo</button><button data-a="redo" title="Ctrl+Y">Redo</button><button data-t="snap">Snapping</button></div>`;""",
  """  rib.innerHTML = `
    <div class="grp"><div class="gb">${B('data-t="select"', 'select', 'Select', 'Select: click a road; Shift+click adds; Ctrl+drag draws a box')}${B('data-a="clear"', 'clear', 'Clear', 'Clear the selection')}</div><span class="gl">Selection</span></div>
    <div class="grp"><div class="gb">${B('data-t="create"', 'create', 'Create', 'Create road (width templates)')}</div><span class="gl">Create</span></div>
    <div class="grp"><div class="gb">${B('data-t="offset"', 'offset', 'Offset', 'Offset: parallel copy / move of selected roads')}${B('data-t="extend"', 'extend', 'Extend', 'Extend a road end to the next road')}${B('data-t="trim"', 'trim', 'Trim', 'Trim a road back to the crossing roads')}${B('data-t="split"', 'split', 'Split', 'Split roads')}${B('data-t="square"', 'square', 'Square', 'Square ends: make roads meet at 90 degrees')}${B('data-t="attr"', 'attr', 'Attributes', 'Attributes: width, class, keep on redesign')}${B('data-t="delete"', 'delete', 'Delete', 'Delete selected roads')}</div><span class="gl">Modify</span></div>
    <div class="grp"><div class="gb">${B('data-a="undo"', 'undo', 'Undo', 'Undo (Ctrl+Z)')}${B('data-a="redo"', 'redo', 'Redo', 'Redo (Ctrl+Y)')}${B('data-t="snap"', 'snap', 'Snapping', 'Snapping on / off and tolerance')}</div><span class="gl">Edit</span></div>
    <button class="rhide" data-a="hide" title="Hide the editing ribbon">${IC.hide}</button>`;
  const ribTab = L.DomUtil.create('button', 'ribtab', map.getContainer()); ribTab.innerHTML = `${IC.edit}<span>Edit roads</span>`; ribTab.title = 'Show the editing ribbon'; ribTab.hidden = true;
  L.DomEvent.disableClickPropagation(ribTab);
  const setRib = on => { rib.classList.toggle('gone', !on); ribTab.hidden = on; try { localStorage.setItem('lp_rib', on ? '1' : '0'); } catch (e) {} };
  rib.querySelector('[data-a=hide]').onclick = () => setRib(false); ribTab.onclick = () => setRib(true);
  try { if (localStorage.getItem('lp_rib') === '0') setTimeout(() => setRib(false), 0); } catch (e) {}"""),
 ("  function show(on) { rib.style.display = on ? '' : 'none'; if (!on) close(); }",
  "  function show(on) { rib.style.display = on ? '' : 'none'; ribTab.style.display = on ? '' : 'none'; if (!on) close(); }"),
 ("""    wid.innerHTML = `<div class="wh"><b>${TITLE[t]}</b><button class="x" title="Close (Esc)">&times;</button></div><div class="wb">${W[t]()}</div>`; wid.hidden = false;
    wid.querySelector('.x').onclick = close;""",
  """    wid.innerHTML = `<div class="wh"><span class="wt">${IC[t === 'attr' ? 'attr' : t] || ''}<b>${TITLE[t]}</b></span><span><button class="x mn" title="Minimise / restore the panel">${IC.min}</button><button class="x" data-close title="Close (Esc)">&times;</button></span></div><div class="wb">${W[t]()}</div>`; wid.hidden = false;
    wid.classList.remove('mini'); wid.querySelector('[data-close]').onclick = close;
    wid.querySelector('.mn').onclick = () => { wid.classList.toggle('mini'); wid.querySelector('.mn').innerHTML = wid.classList.contains('mini') ? IC.max : IC.min; };"""),
])
patch('webapp/static/app.css', [(".ribbon { position: absolute;", """.ribbon .gb { display: flex; gap: 1px; }
.ribbon .grp { flex-direction: column; align-items: center; }
.ribbon .grp .gl { margin: 1px 0 0; }
.ribbon button { display: flex; flex-direction: column; align-items: center; gap: 1px; min-width: 46px; padding: 3px 4px; font-size: 11px; line-height: 1.1; }
.ribbon button svg { color: #1f5f8b; }
.ribbon button.on svg { color: #0b3d5e; }
.ribbon .rhide { min-width: 0; align-self: flex-start; padding: 2px; border: 1px solid #e3e1dc; margin-left: auto; }
.ribbon.gone { display: none !important; }
.ribtab { position: absolute; top: 10px; left: 56px; z-index: 1000; display: flex; align-items: center; gap: 6px; background: #fff; color: #1f5f8b; border: 1px solid #c9ced6; border-radius: 6px; padding: 5px 10px; box-shadow: 0 2px 8px rgba(0,0,0,.18); font-size: 12px; }
.widget .wt { display: flex; align-items: center; gap: 6px; } .widget .wt svg { color: #1f5f8b; }
.widget .wh .x svg { width: 14px; height: 14px; }
.widget.mini .wb { display: none; } .widget.mini { width: 220px; }
body.nopanel #panel { display: none; }
.panelbtn { background: transparent; color: #fff; border: 1px solid rgba(255,255,255,.35); padding: 4px 8px; margin-right: 10px; }
.ribbon { position: absolute;""")])
patch('webapp/static/index.html', [('<div class="brand">LP Toolkit', '<div class="brand"><button id="panelBtn" class="panelbtn" title="Show / hide the side panel">&#9776;</button>LP Toolkit')])
patch('webapp/static/app.js', [("$('#mClose').onclick = () => $('#modal').hidden = true;",
  "$('#mClose').onclick = () => $('#modal').hidden = true;\n$('#panelBtn').onclick = () => { document.body.classList.toggle('nopanel'); setTimeout(() => map.invalidateSize(), 50); try { localStorage.setItem('lp_panel', document.body.classList.contains('nopanel') ? '0' : '1'); } catch (e) {} };\ntry { if (localStorage.getItem('lp_panel') === '0') { document.body.classList.add('nopanel'); setTimeout(() => map.invalidateSize(), 50); } } catch (e) {}")])
print('ok')
