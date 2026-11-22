import os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'webapp', 'static'))
def patch(p, a, b):
    s = open(p, encoding='utf-8').read(); assert s.count(a) == 1, (p, s.count(a), a[:90]); open(p, 'w', encoding='utf-8').write(s.replace(a, b))
patch('features.js', """<button data-a="snappane" title="Snapping: endpoint, vertex, edge, intersection, midpoint; tolerance">${IC.snap}<span>Snapping</span></button>""",
      """<button data-a="snappane" title="Snapping: endpoint, vertex, edge, intersection, midpoint; tolerance">${IC.snap}<span>Snapping</span></button><button data-a="modpane" title="Modify Features: Move, Rotate, Scale, Copy / Paste, Continue, Planarize and every editing tool">${IC.edit}<span>Modify</span></button><button data-a="attrpane" title="Attributes pane: edit the selection in place">${IC.attr}<span>Attributes</span></button><button data-a="histpane" title="Edit history since the last save">${IC.undo}<span>History</span></button>""")
patch('features.js', "  sgrp.querySelector('[data-a=snappane]').onclick = () => Sketch.snapPane();",
      "  sgrp.querySelector('[data-a=snappane]').onclick = () => Sketch.snapPane();\n  sgrp.querySelector('[data-a=modpane]').onclick = () => ModifyPane.toggle(); sgrp.querySelector('[data-a=attrpane]').onclick = () => AttrPane.toggle(); sgrp.querySelector('[data-a=histpane]').onclick = () => EditLog.pane();")
patch('features.js', "alert(`Edits saved (${r.saved_at}).`); markSaved(false, r.saved_at); }", "alert(`Edits saved (${r.saved_at}).`); markSaved(false, r.saved_at); if (window.EditLog) EditLog.clear(); }")
patch('index.html', '<script src="/static/features.js"></script>', '<script src="/static/features.js"></script>\n<script src="/static/pro_panes.js"></script>')
open('app.css', 'a', encoding='utf-8').write("""
.pane.dock { right: 12px; top: 220px; width: 300px; } .pane.modpane { right: 330px; top: 220px; width: 230px; }
.pane .mg { font-size: 10.5px; text-transform: uppercase; letter-spacing: .04em; color: #6b7480; margin: 8px 0 3px; }
.pane .mt { display: block; width: 100%; text-align: left; margin: 2px 0; padding: 4px 8px; background: #fff; color: #1f2328; border: 1px solid #e2e6ea; font-size: 12px; font-weight: 400; }
.pane .mt:hover { background: #eef4fa; border-color: #c7d9ea; } .pane .mt[hidden] { display: none; }
table.attr { width: 100%; border-collapse: collapse; font-size: 12px; margin: 6px 0; } table.attr th { text-align: left; color: #555; font-weight: 600; padding: 2px 6px 2px 0; width: 40%; word-break: break-all; }
table.attr td input { width: 100%; padding: 3px 5px; font-size: 12px; } ol.hist { margin: 0 0 8px; padding-left: 20px; font-size: 12px; } ol.hist li { margin: 3px 0; } ol.hist li.top { font-weight: 600; }
""")
print('ok')
