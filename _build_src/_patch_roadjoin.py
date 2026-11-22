def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
# ---------- reserves stage: segments shifted onto the image are joined up again; one width per named road ----------
patch('ml5/pinch_v2.py', [
 ("new = []\nfor g in R3.geometry:", "new = []; orig = list(R3.geometry)\nfor g in R3.geometry:"),
 ("R3['geometry'] = new; R = R3.to_crs(2136)", '''# segments are nudged one by one: ends that met before the nudge meet again (average position); ends that stopped on another road go back onto it
ends = [(i, k, Point(g.coords[0 if k == 0 else -1])) for i, g in enumerate(orig) for k in (0, 1)]
newc = [list(g.coords) for g in new]
from collections import defaultdict
groups, seen = [], set()
for a, (i, k, p) in enumerate(ends):
    if a in seen: continue
    grp = [b for b, (j, kk, q) in enumerate(ends) if b not in seen and p.distance(q) < 1.0]
    seen.update(grp); groups.append(grp)
for grp in groups:
    if len(grp) < 2: continue
    pts = np.array([newc[ends[b][0]][0 if ends[b][1] == 0 else -1][:2] for b in grp]); m = tuple(pts.mean(0))
    for b in grp: newc[ends[b][0]][0 if ends[b][1] == 0 else -1] = m
for grp in groups:
    if len(grp) != 1: continue
    i, k, p = ends[grp[0]]
    hits = [j for j, g in enumerate(orig) if j != i and g.distance(p) < 1.0]
    if hits:
        j = hits[0]; gj = LineString(newc[j]); q = gj.interpolate(gj.project(Point(newc[i][0 if k == 0 else -1])))
        newc[i][0 if k == 0 else -1] = q.coords[0]
new = [LineString(c) for c in newc]
R3['geometry'] = new; R = R3.to_crs(2136)
# one carriageway width per named road (single segments can measure the median or a lay-by as road)
nm = R.name.fillna('').astype(str)
R['carriage_w'] = np.where(nm != '', R.groupby([nm, R.highway]).carriage_w.transform('median'), R.carriage_w)'''),
])
# ---------- blocks stage: the median between the two carriageways of a dual road is road reserve, not a block ----------
patch('ml5/blocks_plots.py', [("ROAD = road_surface(LN, HW, tol=3 / FT, clip=site, fillet=4 / FT)", '''ROAD = road_surface(LN, HW, tol=3 / FT, clip=site, fillet=4 / FT)
# dual carriageways: two parallel ways with the same name, 6-45 m apart -> fill the median between them
fills = []
named = R[R.name.notna() & (R.name.astype(str) != '')].reset_index(drop=True)
for a in range(len(named)):
    for b in range(a + 1, len(named)):
        if named.name[a] != named.name[b]: continue
        la, lb = named.geometry[a], named.geometry[b]
        if la.distance(lb) * FT > 45: continue
        smp = [la.interpolate(t, normalized=True) for t in np.linspace(.1, .9, 9)]
        d = np.array([lb.distance(q) * FT for q in smp]); ok = (d > 6) & (d < 45)
        if ok.mean() < .5: continue
        sep = float(np.median(d[ok])) / FT; wa, wb = named.carriage_w[a] / 2 / FT, named.carriage_w[b] / 2 / FT
        both = unary_union([la.buffer(wa, cap_style=2), lb.buffer(wb, cap_style=2)])
        fills.append(both.buffer(sep * .6, cap_style=2, join_style=2).buffer(-sep * .6, cap_style=2, join_style=2).intersection(la.buffer(sep + wa, cap_style=2)).intersection(lb.buffer(sep + wb, cap_style=2)))
if fills: ROAD = unary_union([ROAD] + fills).intersection(site); print('dual carriageway medians filled:', len(fills))''')])
print('ok')
