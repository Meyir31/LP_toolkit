"""Design audit: run after every design. Lists each flaw with its location and a suggested fix, and draws them on a map.
Usage: python design_audit.py <out_dir> [stage]   stage = roads | plots | landuse (default: whatever files exist)"""
import sys, os, math, json, warnings, numpy as np, geopandas as gpd, pandas as pd, shapely, rasterio
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
from collections import defaultdict
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
warnings.filterwarnings('ignore')
OUT = sys.argv[1]; FT2M = 0.3048; AC = 43560
RD = gpd.read_file(OUT + 'layout_roads.gpkg').set_index('Class').geometry
CL = gpd.read_file(OUT + 'layout_centrelines.gpkg').geometry
CONC = gpd.read_file(OUT + 'concept.gpkg').set_index('Part').geometry; S = CONC['Site']; S = max(shapely.get_parts(S), key=lambda g: g.area)
WIDTH = {'100 ft road reserve': 100, '60 ft main road': 60, '40 ft collector': 40, '30 ft local road': 30}
ROADS = RD.union_all()
flaws = []
def flaw(cat, sev, where, what, fix):
    p = where if isinstance(where, Point) else Point(where); flaws.append(dict(n=len(flaws) + 1, cat=cat, sev=sev, x=p.x, y=p.y, what=what, fix=fix))
def mrr(g):
    c = list(g.minimum_rotated_rectangle.exterior.coords); return sorted([math.dist(c[0], c[1]), math.dist(c[1], c[2])])
def road_class(pt):
    for c in ('100 ft road reserve', '60 ft main road', '60 ft existing road', '40 ft collector', '30 ft local road'):
        if c in RD.index and RD[c].buffer(0.5).contains(pt): return c
    return None
# ================= ROADS =================
segs = [x for x in shapely.get_parts(shapely.node(unary_union(list(CL)))) if x.length > 3]
J = defaultdict(list)
for x in segs:
    c = np.array(x.coords)
    for e, s_ in ((c[0], min(25, x.length / 2)), (c[-1], max(0, x.length - min(25, x.length / 2)))):
        nb = np.array(x.interpolate(s_).coords[0]); J[(round(e[0], 1), round(e[1], 1))].append((math.degrees(math.atan2(nb[1] - e[1], nb[0] - e[0])), x))
nodes = {k: v for k, v in J.items()}
for k, legs in nodes.items():
    if len(legs) < 3: continue
    a = sorted(l[0] % 360 for l in legs); g = min((a[(i + 1) % len(a)] - a[i]) % 360 for i in range(len(a)))
    if g < 80: flaw('Roads', 'high', k, f'junction angle {g:.0f} deg (< 80)', 'bend the approaching road in its last 100-150 ft so it meets square')
    if len(legs) > 4: flaw('Roads', 'high', k, f'{len(legs)}-way junction', 'separate the roads so no more than 4 legs meet')
    cls = set()
    for ang, x in legs:
        p = np.array(k) + np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))]) * 40; cls.add(road_class(Point(p)))
    cls.discard(None)
    if '30 ft local road' in cls and ({'60 ft main road', '60 ft existing road', '100 ft road reserve'} & cls):
        flaw('Roads', 'medium', k, 'hierarchy skip: 30 ft local road joins ' + ' / '.join(sorted({'60 ft main road', '60 ft existing road', '100 ft road reserve'} & cls)), 'route the local road to a 40 ft collector instead, or upgrade it to 40 ft')
for k, legs in nodes.items():
    if len(legs) == 1 and Point(k).distance(S.exterior) > 10 and S.contains(Point(k)):
        L = legs[0][1].length * FT2M
        flaw('Roads', 'high' if L > 200 else 'low', k, f'dead end ({L:.0f} m)', 'connect it to the nearest road' if L > 200 else 'acceptable cul-de-sac (<= 200 m); give it a turning head')
# staggered T junctions
Ts = []
for k, legs in nodes.items():
    if len(legs) != 3: continue
    v = [np.array([math.cos(math.radians(l[0])), math.sin(math.radians(l[0]))]) for l in legs]
    pr = min([(0, 1), (0, 2), (1, 2)], key=lambda ij: float(v[ij[0]] @ v[ij[1]])); br = [q for q in range(3) if q not in pr][0]
    Ts.append((np.array(k), v[pr[0]], np.sign(v[pr[0]][0] * v[br][1] - v[pr[0]][1] * v[br][0])))
for i in range(len(Ts)):
    for j in range(i + 1, len(Ts)):
        pa, ta, sa = Ts[i]; pb, tb, sb = Ts[j]; d = pb - pa; dd = np.linalg.norm(d)
        if 10 < dd < 131 and abs(ta @ tb) > 0.95 and abs((d / dd) @ ta) > 0.95 and sa != sb:
            flaw('Roads', 'high', (pa + pb) / 2, f'staggered T junctions {dd * FT2M:.0f} m apart', 'align them into one 4-way junction or move them >= 40 m apart')
# junction spacing on major roads
import re as _re
_wd = {c: float(_re.search(r'(\d+(?:\.\d+)?)\s*ft', c).group(1)) for c in RD.index if _re.search(r'(\d+(?:\.\d+)?)\s*ft', c)}
_top = max(_wd.values()) if _wd else 0
_checks = [(c, 305 if w == _top else 90) for c, w in sorted(_wd.items(), key=lambda t: -t[1]) if w == _top or w >= 60]   # the highest road (any width): entries >= 1,000 ft apart
for cls_, min_m in _checks:
    if cls_ not in RD.index: continue
    zone = RD[cls_].buffer(3)
    js = [Point(k) for k, legs in nodes.items() if len(legs) >= 3 and zone.contains(Point(k))]
    axis = max(shapely.get_parts(shapely.line_merge(unary_union([x for x in segs if x.within(RD[cls_].buffer(1))]))), key=lambda g: g.length, default=None)
    if axis is None or len(js) < 2: continue
    ss = sorted(((axis.project(p), p) for p in js), key=lambda t: t[0])           # by position only (two junctions can share one)
    for (a, pa), (b, pb) in zip(ss, ss[1:]):
        if (b - a) * FT2M < 20: continue                                    # the two sides of one crossroads
        if (b - a) * FT2M < min_m: flaw('Roads', 'medium', Point((pa.x + pb.x) / 2, (pa.y + pb.y) / 2), f'entries onto the {cls_} only {(b - a) * FT2M:.0f} m apart (< {min_m} m)', 'run blocks parallel to this road and close one entry')
# ================= BLOCKS =================
if os.path.exists(OUT + 'layout_blocks.gpkg'):
    for b in gpd.read_file(OUT + 'layout_blocks.gpkg').geometry:
        w, l = mrr(b); c = b.representative_point()
        on_buffer = 'Stream reserve' in CONC.index and b.buffer(3).intersection(CONC['Stream reserve']).area > 0.25 * l * 3
        if l > 600 and on_buffer and w < 200: flaw('Blocks', 'low', c, f'plot row {l:.0f} ft long backing onto the stream buffer (local-plan pattern)', 'accepted; add footpath links to the buffer every ~8 plots')
        elif l > 600 and int(l // 70) > 8:
            LU2 = gpd.read_file(OUT + 'plots_landuse.gpkg') if os.path.exists(OUT + 'plots_landuse.gpkg') else None
            nonres = 0.0
            if LU2 is not None:
                RS2 = gpd.read_file(OUT + 'reserves_landuse.gpkg')
                nonres = (LU2[~LU2.use.isin(['RE', 'RA'])].intersection(b).area.sum() + RS2.intersection(b).area.sum()) / b.area
            if nonres < 0.15: flaw('Blocks', 'medium', c, f'block {l:.0f} ft long ({int(l // 70)} plots a row > 8)', 'add a cross road or footpath to break it')
        sides_on_road = b.exterior.intersection(ROADS.buffer(2)).length / b.exterior.length
        LU_ = gpd.read_file(OUT + 'plots_landuse.gpkg') if os.path.exists(OUT + 'plots_landuse.gpkg') else None
        res_in = LU_ is None or ((LU_.use == 'RE') & LU_.geometry.representative_point().within(b.buffer(1))).any()
        if w < 170 and sides_on_road > 0.85 and b.area > 8000 and not on_buffer and res_in: flaw('Blocks', 'high', c, f'single-row block {w:.0f} ft deep with roads all round', 'double-frontage risk: remove or move one of the roads so the block is 2 rows deep')
# ================= PLOTS =================
pf = OUT + 'plots_landuse.gpkg' if os.path.exists(OUT + 'plots_landuse.gpkg') else OUT + 'plots_final.gpkg'
if os.path.exists(pf):
    PL = gpd.read_file(pf); res = PL[PL['use'].isin(['RE', 'RA'])] if 'use' in PL else PL.assign(use='RE')
    for g, u_ in zip(res.geometry, res['use']):
        c = g.representative_point(); w, d = mrr(g); a = g.area
        segs_ = np.array(g.exterior.simplify(1.5).coords); ns = []
        for p0, p1 in zip(segs_[:-1], segs_[1:]):
            L = np.linalg.norm(p1 - p0)
            if L < 25: continue
            m = (p0 + p1) / 2; t = (p1 - p0) / L; n = np.array([t[1], -t[0]])
            if g.contains(Point(m + n * 3)): n = -n
            if ROADS.contains(Point(m + n * 6)): ns.append(n)
        if any(float(ns[i] @ ns[j]) < -0.8 for i in range(len(ns)) for j in range(i + 1, len(ns))): flaw('Plots', 'high', c, 'double frontage (roads front and back)', 'change the road so the plot backs onto another plot')
        if not ns: flaw('Plots', 'high', c, 'no road access', 'give it frontage or merge it with a neighbour')
        if a < 6970 * 0.98: flaw('Plots', 'high', c, f'plot {a:,.0f} sq ft below the Residential B minimum (0.16 ac = 6,970 sq ft)', 'widen the frontage or merge with a neighbour')
        if a > (20000 if u_ == 'RA' else 12000): flaw('Plots', 'low', c, f'large residential plot {a:,.0f} sq ft', 'split if it has enough frontage')
        if w > 95: flaw('Plots', 'low', c, f'wide frontage ({w:.0f} ft) - standard is 70 ft', 'add a plot to the row')
        if d > (235 if u_ == 'RA' else 150): flaw('Plots', 'medium', c, f'deep plot ({d:.0f} ft)', 'block too deep: tighten the road spacing')
        if w < 55: flaw('Plots', 'medium', c, f'narrow frontage ({w:.0f} ft)', 'merge with a neighbour')
        if a / (w * d) < 0.7: flaw('Plots', 'low', c, f'irregular shape (fill {a / (w * d):.2f})', 'acceptable at bends/boundaries if >= 7,000 sq ft')
    rb = res[res['use'] == 'RE']; W_ = np.array([mrr(g)[0] for g in rb.geometry]); D_ = np.array([mrr(g)[1] for g in rb.geometry]); A_ = rb.area.values
    print(f'PLOT SIZES (Residential B {len(rb)}, plus {len(res) - len(rb)} Residential A): frontage median {np.median(W_):.0f} ft ({(abs(W_ - 70) <= 5).mean() * 100:.0f}% at 70 +/- 5), depth median {np.median(D_):.0f} ft ({((D_ >= 95) & (D_ <= 115)).mean() * 100:.0f}% 95-115), area median {np.median(A_):,.0f} sq ft, below 0.16 ac: {(A_ < 6970 * 0.98).sum()}')
# ================= LAND USE =================
if os.path.exists(OUT + 'plots_landuse.gpkg'):
    R = gpd.read_file(OUT + 'reserves_landuse.gpkg'); F = pd.concat([PL[PL.use != 'RE'][['label', 'geometry']], R[['label', 'geometry']]]); F = gpd.GeoDataFrame(F, geometry='geometry', crs=PL.crs)
    rng = {'School': (0.9, 3.0, 'learned school sites 0.9-3.0 ac'), 'Health': (0.5, 1.2, 'Guidelines min 0.5 ac; learned 0.63-1.05'), 'Worship': (0.55, 1.3, 'learned 0.68-1.21 ac'),
           'Market': (0.25, 1.6, 'learned 0.23-1.58 ac'), 'P.O.S': (0.4, 2.7, 'learned open space 0.5-2.7 ac'), 'S.A': (0.15, 0.6, 'learned 0.18-0.39 ac'), 'UT': (0.1, 0.4, 'learned 0.13-0.36 ac'),
           'Community': (0.5, 1.2, 'learned civic 0.65-1.13 ac'), 'Nursery': (0.5, 1.0, 'learned 0.65-0.97 ac'), 'Lorry': (0.4, 1.4, 'learned transport 0.41-1.41 ac')}
    for g, l in zip(F.geometry, F.label):
        for key, (lo, hi, why) in rng.items():
            if key in str(l):
                if not (lo <= g.area / AC <= hi): flaw('Land use', 'medium', g.representative_point(), f'{l}: {g.area / AC:.2f} ac outside {lo}-{hi} ac', f'resize ({why})')
                break
    sch = F[F.label.str.contains('School', na=False)].geometry.union_all()
    for g, l in zip(F.geometry, F.label):
        if ('P.O.S' in str(l) or 'green' in str(l).lower()) and g.buffer(1).intersection(sch).area > 30 and g.intersection(sch.buffer(1)).length >= 0:
            if g.distance(sch) < 1 and not g.buffer(2).intersection(sch).difference(ROADS).is_empty: flaw('Land use', 'high', g.representative_point(), f'{l} shares a boundary with the school (open space in school land)', 'separate by a road or merge into the school site')
    if not sch.is_empty and sch.distance(RD.get('100 ft road reserve', Point(0, 0))) < 3: flaw('Land use', 'medium', sch.representative_point(), 'school fronts the 100 ft road (pupil safety)', 'give the school its gate on a collector or local road')
    green = R[R.label.str.contains('green', case=False, na=False)]
    for g in green.geometry:
        if g.area / AC > 0.25: flaw('Land use', 'medium', g.representative_point(), f'undefined leftover land {g.area / AC:.2f} ac (landscaped green)', 'reshape roads/blocks so it becomes plots, or give it a defined use')
    if len(green): print(f'landscaped green total {green.area.sum() / AC:.2f} ac in {len(green)} pieces')
    pts = list(PL[PL.use.isin(['RE', 'RA'])].geometry.centroid)
    for key, lim, why in (('School', 800, 'learned: 90% of homes within ~720 m'), ('S\\.A', 500, 'Guidelines: within 500 m'), ('P\\.O\\.S', 400, 'within 400 m'), ('Health', 1200, 'learned p90 1.1 km')):
        f = F[F.label.str.contains(key, na=False)]
        if not len(pts): continue                                   # no homes on the site
        if f.empty and len(pts) < 60 and key in ('School', 'Health'): flaw('Land use', 'low', S.centroid, f'no {key} site: small site ({len(pts)} homes), served by the surrounding neighbourhood', 'confirm a school / health facility is within reach outside the site'); continue
        if f.empty: flaw('Land use', 'high', S.centroid, f'no {key.replace(chr(92), "")} site', 'add one'); continue
        d = np.array([f.geometry.distance(p).min() for p in pts]) * FT2M
        if d.max() > lim: far = pts[int(d.argmax())]; flaw('Land use', 'medium', far, f'{int((d > lim).sum())} homes more than {lim} m from a {key.replace(chr(92), "")} site (max {d.max():.0f} m)', why)
    sa = F[F.label.str.contains('S\\.A', na=False)].geometry
    sens = F[F.label.str.contains('School|Health|Nursery|Market|Play|P.O.S', na=False)]
    for g in sa:
        near = sens[sens.geometry.distance(g) * FT2M < 60]
        if len(near): flaw('Land use', 'high', g.representative_point(), 'S.A within 60 m of ' + ', '.join(sorted(set(near.label))), 'move the S.A away from schools, health, food and play areas')
        if g.distance(RD.get('60 ft main road', Point(0, 0))) < 3 or g.distance(RD.get('100 ft road reserve', Point(0, 0))) < 3: flaw('Land use', 'medium', g.representative_point(), 'S.A fronts a major road', 'place it on a local road')
    for g, l in zip(F.geometry, F.label):
        if any(k in str(l) for k in ('School', 'Worship', 'Health', 'Market', 'Community')):
            w_, l_ = mrr(g); fill = g.area / (w_ * l_)
            if fill < 0.8 or l_ / w_ > (3.2 if 'Market' in str(l) else 2.2): flaw('Land use', 'medium', g.representative_point(), f'{l}: irregular site (fill {fill:.2f}, {w_:.0f} x {l_:.0f} ft)', 'use a compact near-square parcel (learned: community sites are near-square, full block depth)')
# ================= REPORT =================
D = pd.DataFrame(flaws)
order = {'high': 0, 'medium': 1, 'low': 2}
print(f'\nDESIGN AUDIT: {len(D)} findings' + ('' if D.empty else ' | ' + ', '.join(f'{k} {v}' for k, v in D.sev.value_counts().items())))
if not D.empty:
    D = D.sort_values(['sev', 'cat'], key=lambda c: c.map(order) if c.name == 'sev' else c).reset_index(drop=True); D['n'] = range(1, len(D) + 1)
    for r in D.itertuples(): print(f'  {r.n:>2}. [{r.sev:6s}] {r.cat:8s} {r.what}  ->  {r.fix}')
    D.to_csv(OUT + 'design_audit.csv', index=False)
img = rasterio.open(OUT + 'imagery_2136.tif'); a = np.moveaxis(img.read(), 0, -1); bb = img.bounds
fig, ax = plt.subplots(figsize=(15, 14)); ax.imshow(a, extent=(bb.left, bb.right, bb.bottom, bb.top), alpha=.35)
colr = {'100 ft road reserve': '#5a5a5a', '60 ft main road': '#8c8c8c', '40 ft collector': '#f5c242', '30 ft local road': '#d9d9d9'}
for c_, g in RD.items(): gpd.GeoSeries([g]).plot(ax=ax, color=colr.get(c_, '#ccc'))
if os.path.exists(pf): gpd.read_file(pf).plot(ax=ax, color='#f3c99a', ec='k', lw=.3)
elif os.path.exists(OUT + 'layout_blocks.gpkg'): gpd.read_file(OUT + 'layout_blocks.gpkg').plot(ax=ax, color='#f3c99a', ec='k', lw=.5)
sc = {'high': 'red', 'medium': 'darkorange', 'low': 'royalblue'}
if not D.empty:
    for r in D.itertuples():
        ax.plot(r.x, r.y, 'o', mfc='none', mec=sc[r.sev], ms=18, mew=2.5); ax.text(r.x + 25, r.y + 25, str(r.n), color=sc[r.sev], fontsize=10, weight='bold')
gpd.GeoSeries([S]).boundary.plot(ax=ax, color='yellow', lw=2)
x0, y0, x1, y1 = S.buffer(80).bounds; ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_xticks([]); ax.set_yticks([])
ax.set_title(f'Design audit: {len(D)} findings (red high, orange medium, blue low)', fontsize=15)
plt.savefig(OUT + 'design_audit.png', bbox_inches='tight', dpi=75)
