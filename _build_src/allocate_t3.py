"""Test 2 land use. Program: LUSPA Manual 4.6.3 + Guidelines mandatory list. Rates, site sizes and shapes: learned from the STMA schemes.
Order: community uses go first onto compact leftover sites (as in the schemes); residential plots are taken only where no suitable site exists."""
import geopandas as gpd, pandas as pd, numpy as np, rasterio, math, json, warnings, shapely
from rasterio.mask import mask
from shapely.ops import unary_union
from shapely.geometry import LineString, Point
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Patch
warnings.filterwarnings('ignore')
OUT = 'ml3/'; AC = 43560
unit = lambda v: np.asarray(v, float) / np.linalg.norm(v)
P = gpd.read_file(OUT + 'plots_final.gpkg'); R = gpd.read_file(OUT + 'reserves_final.gpkg')
C = gpd.read_file(OUT + 'concept.gpkg').set_index('Part').geometry; RD = gpd.read_file(OUT + 'layout_roads.gpkg').set_index('Class').geometry
SITE, MAIN = C['Site'], C['60 ft existing road']; CORR = shapely.Point(-1e7, -1e7).buffer(1); WZ = C['West zone']; SR = C['Stream reserve']; COLLR = RD['40 ft collector']; ROADS = RD.union_all()
dem = rasterio.open(OUT + 'dem_2136.tif')
def elev(g):
    try: a, _ = mask(dem, [g], crop=True, filled=False, all_touched=True); return float(a.compressed().mean())
    except Exception: return np.nan
def mrr(g):
    if g is None or g.is_empty or g.area <= 0: return [1.0, 1.0]                # nothing there (small site)
    c = list(g.minimum_rotated_rectangle.exterior.coords); return sorted([math.dist(c[0], c[1]), math.dist(c[1], c[2])])
P['use'], P['label'] = 'RE', ''
R['use'], R['label'] = '', ''
log = []
# ---------- 0. plot-sized leftover pieces (80-125 ft deep, regular) are cut into plots along their road side ----------
def split_into_plots(g, n):
    c = list(g.minimum_rotated_rectangle.exterior.coords); e = [np.array(c[1]) - np.array(c[0]), np.array(c[2]) - np.array(c[1])]
    ax_ = e[0] if np.linalg.norm(e[0]) > np.linalg.norm(e[1]) else e[1]; L = np.linalg.norm(ax_); u = ax_ / L; nrm = np.array([-u[1], u[0]])
    o = np.array(g.minimum_rotated_rectangle.centroid.coords[0]) - u * L / 2
    cuts = [LineString([tuple(o + u * L * k / n - nrm * 500), tuple(o + u * L * k / n + nrm * 500)]) for k in range(1, n)]
    parts = shapely.get_parts(shapely.ops.split(g, unary_union(cuts))) if cuts else [g]
    return [q for q in parts if q.area > 100]
newp = []
for i in list(R.index):
    g = R.geometry[i]; w_, l_ = mrr(g); fill = g.area / (w_ * l_)
    if 80 <= w_ <= 125 and fill >= 0.78 and g.boundary.intersection(ROADS.buffer(2)).length > 60:
        n = max(1, round(l_ / 75))
        for q in split_into_plots(g, n): newp.append(dict(geometry=q, block=-1000 - i))
        R.drop(index=i, inplace=True)
if newp: P = pd.concat([P, gpd.GeoDataFrame(newp, crs=P.crs).assign(use='RE', label='')], ignore_index=True); P = gpd.GeoDataFrame(P, geometry='geometry', crs=R.crs)
log.append(('Leftover pieces cut into plots', f'{len(newp)} plots', 'pieces 80-125 ft deep with road frontage'))
P['elev'] = [elev(g) for g in P.geometry]; R['elev'] = [elev(g) for g in R.geometry]; R['ac'] = R.area / AC
P['main'] = [g.distance(MAIN) < 3 for g in P.geometry]; P['kor'] = [g.distance(CORR) < 3 for g in P.geometry]
# ---------- repair: plots with no road access, or small double-frontage plots, merge into the neighbour they share most boundary with ----------
def frontage_dirs(g):
    g = max(shapely.get_parts(g), key=lambda q: q.area); c = np.array(g.exterior.simplify(1.5).coords); ns = []
    for a_, b_ in zip(c[:-1], c[1:]):
        L = np.linalg.norm(b_ - a_)
        if L < 25: continue
        m = (a_ + b_) / 2; t = (b_ - a_) / L; n = np.array([t[1], -t[0]])
        if g.contains(shapely.Point(m + n * 3)): n = -n
        if ROADS.contains(shapely.Point(m + n * 6)): ns.append(n)
    return ns
fixed = 0
for i in list(P.index):
    if i not in P.index: continue
    g = P.geometry[i]; ns = frontage_dirs(g)
    dbl = any(float(ns[a] @ ns[b]) < -0.8 for a in range(len(ns)) for b in range(a + 1, len(ns)))
    if ns and not (dbl and g.area < 9000) and g.area >= 6970 * 0.98: continue
    nb = P[(P.index != i) & (P.geometry.buffer(1).intersection(g).area > 30)]
    if nb.empty: continue
    j = max(nb.index, key=lambda j: P.geometry[j].buffer(1).intersection(g).area)
    ug = unary_union([P.geometry[j], g]).buffer(0.3).buffer(-0.3)
    if ug.geom_type != 'Polygon': continue
    P.at[j, 'geometry'] = ug; P.drop(index=i, inplace=True); fixed += 1
log.append(('Plot repair', f'{fixed} plots merged into neighbours', 'no road access, or small plots with roads front and back'))
# deep plots (> 150 ft): roads front and back -> two plots back to back; one frontage -> rear given to the plot behind if it stays <= 150 ft
nsplit = ngive = 0; NEWH = []
for i in list(P.index):
    g = P.geometry[i]; w_, d_ = mrr(g)
    if d_ <= 150: continue
    q = list(g.minimum_rotated_rectangle.exterior.coords); e1, e2 = np.array(q[1]) - np.array(q[0]), np.array(q[2]) - np.array(q[1])
    dv = unit(e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2); cm = np.array(g.minimum_rotated_rectangle.centroid.coords[0])
    ns = frontage_dirs(g); dbl = any(float(ns[a] @ ns[b]) < -0.8 for a in range(len(ns)) for b in range(a + 1, len(ns)))
    cut = LineString([tuple(cm - np.array([-dv[1], dv[0]]) * 400), tuple(cm + np.array([-dv[1], dv[0]]) * 400)])
    halves = [h for h in shapely.get_parts(shapely.ops.split(g, cut)) if h.area > 100]
    if dbl and len(halves) == 2 and min(h.area for h in halves) >= 6970 * 0.98:
        P.at[i, 'geometry'] = halves[0]; NEWH.append(P.loc[[i]].assign(geometry=[halves[1]])); nsplit += 1; continue
    if not dbl and ns:
        front = ns[0]; off = d_ - 120                                           # keep 120 ft from the front
        if off < 20: continue
        rear_cut = LineString([tuple(cm - front * (d_ / 2 - off) - np.array([-front[1], front[0]]) * 400), tuple(cm - front * (d_ / 2 - off) + np.array([-front[1], front[0]]) * 400)])
        parts = sorted([h for h in shapely.get_parts(shapely.ops.split(g, rear_cut)) if h.area > 50], key=lambda h: -h.area)
        if len(parts) < 2: continue
        keep, rear = parts[0], unary_union(parts[1:])
        nb = P[(P.index != i) & (P.geometry.buffer(1).intersection(rear).area > 30)]
        if nb.empty: continue
        j = max(nb.index, key=lambda j: P.geometry[j].buffer(1).intersection(rear).area); ug = unary_union([P.geometry[j], rear]).buffer(0.3).buffer(-0.3)
        if ug.geom_type == 'Polygon' and mrr(ug)[1] <= 150 and keep.area >= 6970 * 0.98:
            P.at[i, 'geometry'] = keep; P.at[j, 'geometry'] = ug; ngive += 1
if NEWH: P = gpd.GeoDataFrame(pd.concat([P] + NEWH, ignore_index=True), geometry='geometry', crs=R.crs)
P = P.reset_index(drop=True)
log.append(('Deep plots', f'{nsplit} split back to back, {ngive} rear strips given to the plot behind', 'plots kept within ~150 ft depth'))
BLK = gpd.read_file(OUT + 'layout_blocks.gpkg').geometry
moved_ = 0
for b in BLK:
    w_, l_ = mrr(b)
    if w_ < 170 and b.exterior.intersection(ROADS.buffer(2)).length / b.exterior.length > 0.8 and b.buffer(3).intersection(SR).area < 100:
        idx = P.index[P.geometry.representative_point().within(b.buffer(1))]
        if len(idx):
            R = pd.concat([R, gpd.GeoDataFrame(dict(use=[''], label=['']), geometry=[unary_union(list(P.loc[idx].geometry)).buffer(0.5).buffer(-0.5)], crs=P.crs)], ignore_index=True)
            P = P.drop(index=idx); moved_ += len(idx)
R = gpd.GeoDataFrame(R, geometry='geometry', crs=P.crs); R['ac'] = R.area / AC; R['elev'] = [elev(g) for g in R.geometry]
log.append(('Single-row blocks (roads all round)', f'{moved_} plots returned to the site pool', 'become facility sites (local-plan pattern), no double-frontage plots'))
R['fill'] = [g.area / np.prod(mrr(g)) for g in R.geometry]; R['front'] = [g.boundary.intersection(ROADS.buffer(2)).length for g in R.geometry]
gross = SITE.area / AC; deduct = (MAIN.area + SR.area) / AC; net = gross - deduct
program = dict(gross_ac=round(gross, 1), existing_road_and_stream_reserve_ac=round(deduct, 1), net_ac=round(net, 1), housing_ac_at_65pct=round(net * 0.65, 1), plots_target=round(net * 0.65 * 6.2), population=round(net * 0.65 * 6.2 * 7.2, -1))
centre = unary_union(list(P.geometry)).centroid; JPT = COLLR.intersection(MAIN.buffer(2)).centroid
nres0 = len(P)
SMALL = nres0 < 60                                # well below a neighbourhood (Guidelines: < 5,000 people): served by the surrounding neighbourhood's facilities
NEIGH_USES = {'Ed P', 'H Po', 'Com A', 'PW', 'CIV'}
def _skip_small(use, label):
    if SMALL and (use in NEIGH_USES or str(label).startswith('UT')):
        log.append((label, 'not placed', f'small site ({nres0} plots, well below a 5,000-person neighbourhood): served by the surrounding neighbourhood')); print(f'   {label}: not placed (small site, {nres0} plots: served by the surrounding neighbourhood)', flush=True); return True
    return False
if SMALL: print(f'   small site: {nres0} plots - neighbourhood facilities (school, health, market, worship, civic, water tank) are not carved out; open space and sanitary sites are', flush=True)
def compact(lo, hi, extra=None):
    asp = np.array([mrr(g)[1] / max(mrr(g)[0], 1) for g in R.geometry])
    c = R[(R.use == '') & R.ac.between(lo, hi) & (R.fill >= 0.8) & (R.front >= 100) & (asp <= 2.0)]
    return c if extra is None else c[extra(c)]
def take(i, use, label, why):
    if _skip_small(use, label): return shapely.Polygon()
    R.at[i, 'use'] = use; R.at[i, 'label'] = label; log.append((label, f'{R.ac[i]:.2f} ac leftover site', why)); return R.geometry[i]
def assign_plots(idx, use, label, why):
    if _skip_small(use, label): return shapely.Polygon()
    idx = [i for i in idx if i in P.index]
    if not idx:                                   # small site: nothing left to give this facility
        log.append((label, 'not placed', 'no residential plots left on this small site: served from outside the site')); print(f'   {label}: not placed (no plots left on this small site)', flush=True)
        return shapely.Polygon()
    g = unary_union(list(P.loc[idx].geometry)).buffer(0.5).buffer(-0.5); keep = idx[0]
    P.at[keep, 'geometry'] = g; P.at[keep, 'use'] = use; P.at[keep, 'label'] = label; P.drop(index=list(idx[1:]), inplace=True)
    log.append((label, f'{g.area / AC:.2f} ac ({len(idx)} plots)', why)); return g
def best_group(cands, n, k=12):
    best = None
    for sd in list(cands)[:k]:
        g = chain(sd, n); u = unary_union(list(P.loc[g].geometry)); w_, l_ = mrr(u); sc = (w_ * l_) / u.area + 0.3 * l_ / w_ + (5 if u.area / (w_ * l_) < 0.82 else 0)
        if len(g) == n and (best is None or sc < best[0]): best = (sc, g)
    if best: return best[1]
    return chain(list(cands)[0], n) if len(list(cands)) else []
def plots_along_frontage(poly, depth=105.0, fw=70.0):
    edges = poly.exterior.intersection(ROADS.buffer(3)); edges = shapely.line_merge(unary_union([e for e in shapely.get_parts(edges) if e.geom_type == 'LineString']))
    out, used = [], Point(0, 0).buffer(0.01)
    for e in sorted([x for x in shapely.get_parts(edges) if x.length >= 140], key=lambda x: -x.length):
        e = e.simplify(2); strip = poly.intersection(e.buffer(depth, cap_style=2)).difference(used)
        if strip.is_empty or strip.area < 6970: continue
        n = max(1, int((e.length + 3) // fw)); cuts = []
        for k in range(1, n):
            p_ = np.array(e.interpolate(e.length * k / n).coords[0]); a1 = np.array(e.interpolate(max(0, e.length * k / n - 5)).coords[0]); b1 = np.array(e.interpolate(min(e.length, e.length * k / n + 5)).coords[0]); t_ = unit(b1 - a1); nn = np.array([-t_[1], t_[0]])
            cuts.append(LineString([tuple(p_ - nn * 400), tuple(p_ + nn * 400)]))
        parts = shapely.get_parts(shapely.ops.split(strip, unary_union(cuts))) if cuts else [strip]
        for q in parts:
            if q.area >= 6970 * 0.98 and q.area <= 16000 and q.area / np.prod(mrr(q)) >= 0.65: out.append(q)
        used = used.union(strip)
    return out, poly.difference(unary_union(out)) if out else poly
def chain_area(seed, target_ac):
    grp = chain(seed, 1)
    for k in range(2, 6):
        if unary_union(list(P.loc[grp].geometry)).area / AC >= target_ac * 0.9: break
        grp = chain(seed, k)
    return grp
def chain(seed, n):
    pool = P[(P.use == 'RE') & (P.block == P.at[seed, 'block'])]; grp = [seed]
    while len(grp) < n:
        cur = unary_union(list(P.loc[grp].geometry)); c = pool[(~pool.index.isin(grp)) & (pool.geometry.distance(cur) < 2)]
        if c.empty: break
        def loose(i):
            u = unary_union(list(P.loc[grp + [i]].geometry)); a, b = mrr(u); return u.minimum_rotated_rectangle.area / u.area + 0.5 * b / max(a, 1)
        grp.append(min(c.index, key=loose))
    return grp
# ---------- 1. school: whole residential block on the collector, central (learned 0.9-3.0 ac, median 1.8) ----------
B = P[P.use == 'RE'].groupby('block').agg(n=('use', 'size'), main=('main', 'any'), kor=('kor', 'any')).reset_index()
B['geometry'] = [unary_union(list(P[P.block == k].geometry)) for k in B.block]; B = gpd.GeoDataFrame(B, geometry='geometry', crs=P.crs); B['ac'] = B.area / AC
B['on_coll'] = B.geometry.distance(COLLR) < 3; B['d'] = B.geometry.centroid.distance(centre); B['fill'] = [g.area / np.prod(mrr(g.convex_hull)) for g in B.geometry]
cand = B[(~B.main) & (~B.kor) & B.ac.between(1.4, 2.6) & (B.fill >= 0.85)].sort_values('d')
cand = cand[cand.d <= cand.d.min() + 400].sort_values(['on_coll', 'd'], ascending=[False, True])     # central first, then on a collector
if cand.empty:                                    # no ideal block: any compact residential block of school size
    cand = B[(~B.kor) & B.ac.between(0.9, 3.0) & (B.fill >= 0.7)].sort_values(['on_coll', 'd'], ascending=[False, True])
if len(cand):
    SCH = assign_plots(list(P.index[P.block == cand.block.iloc[0]]), 'Ed P', 'Basic School (Primary + JHS) and Nursery', 'Guidelines: nursery + primary per neighbourhood; learned school site 0.9-3.0 ac; central, on the collector')
else:                                             # small site: no block of school size -> a group of plots near the centre
    re_ = P[P.use == 'RE']; tgt_ = min(1.8, 0.2 * re_.area.sum() / AC)
    seed_ = re_.geometry.centroid.distance(centre).idxmin(); grp_ = chain_area(seed_, tgt_)
    SCH = assign_plots(grp_, 'Ed P', 'Basic School (Primary + JHS) and Nursery', f'no residential block of school size on this site: {len(grp_)} central plots grouped; below the 3 ac primary standard - check the population needs a school here')
    if not SMALL: print(f'   school: no block of school size; {len(grp_)} central plots grouped ({SCH.area / AC:.2f} ac) - check the population needs a school here', flush=True)
si = P.index[P.label.str.startswith('Basic School')][0] if P.label.str.startswith('Basic School').any() else None
for i in list(R.index):                       # no open space inside school land: a leftover piece inside the school block joins the school
    if R.geometry[i].buffer(1).intersection(SCH).area > 30:
        SCH = unary_union([SCH, R.geometry[i]]).buffer(0.5).buffer(-0.5); P.at[si, 'geometry'] = SCH; R.drop(index=i, inplace=True)
# ---------- 2. P.O.S + children's play area: compact leftover site nearest the school ----------
c = compact(0.4, 1.4)
if len(c) and c.geometry.distance(SCH).min() < 300: take(c.geometry.distance(SCH).idxmin(), 'POS', "P.O.S and Children's Play Area", 'next to the school (learned pairing); learned open space 0.5-2.7 ac')
else:
    nb_ = P[(P.use == 'RE') & (P.geometry.distance(SCH) > 20) & (P.geometry.distance(SCH) < 80)]                  # across a road from the school
    if len(nb_): assign_plots(best_group(nb_.geometry.distance(SCH).sort_values().index, 4), 'POS', "P.O.S and Children's Play Area", 'across the road from the school (local-plan pattern: school + playground)')
# ---------- 3. gateway: market on a corner where the collector meets the main road (4 plots); health post on a compact leftover site on a major road near the gateway, else 4 plots ----------
mp = P[(P.use == 'RE') & P.main].copy()
if mp.empty: mp = P[P.use == 'RE'].copy()                  # small site: no residential plot on a main road -> nearest plots to the gateway
mp['d'] = mp.geometry.distance(JPT); mp = mp.sort_values('d')
MK = assign_plots(best_group(mp.index, 4, k=8), 'Com A', 'Neighbourhood Shopping Centre / Market', 'Guidelines mandatory; learned market site 0.6 ac; gateway corner (collector x main road)')
c = compact(0.5, 1.0, lambda c: (c.geometry.distance(MAIN.union(CORR)) < 3) & (c.geometry.distance(JPT) < 700))
if len(c): HP = take(c.geometry.distance(JPT).idxmin(), 'H Po', 'Health Post', 'Guidelines min. 0.5 ac on a main road; learned health site 0.88 ac; near the gateway')
else:
    o = mp[mp.index.isin(P.index)]; o = o[(P.loc[o.index, 'use'] == 'RE')]
    if o.empty: o = P[P.use == 'RE'].assign(d=lambda x: x.geometry.distance(JPT)).sort_values('d')
    HP = assign_plots(chain_area(o.index[0], 0.75), 'H Po', 'Health Post', 'Guidelines min. 0.5 ac on a main road; ~0.75 ac at the gateway')
po = P[(P.use == 'RE') & P.main]
if po.empty: po = P[P.use == 'RE']
po = po.assign(d=po.geometry.distance(MK)).sort_values('d')
if len(po) and not SMALL: P.at[po.index[0], 'use'] = 'BM'; P.at[po.index[0], 'label'] = 'Postal Agency (mixed use)'; log.append(('Postal Agency', '1 plot', 'Guidelines mandatory; beside the market'))
# ---------- 4. places of worship (1 per ~160 plots): compact leftover sites, one each side of the main road; else 4 plots ----------
n_pw = max(1, round(nres0 / 160))
west_of_stream = lambda c: c.geometry.centroid.within(WZ.buffer(5))
for side in ([lambda c: ~west_of_stream(c), west_of_stream, lambda c: ~west_of_stream(c), lambda c: ~west_of_stream(c)])[:n_pw]:
    c = compact(0.55, 1.3, side)
    c = c[[R.geometry[i].area / np.prod(mrr(R.geometry[i])) >= 0.8 for i in c.index]] if len(c) else c
    if len(c): take(c.ac.idxmax(), 'PW', 'Place of Worship', 'learned 1 per ~160 plots; site 0.68-1.21 ac, near-square')
    else:
        z = P[(P.use == 'RE') & side(P) & ~P.main & ~P.kor]; order = z.geometry.centroid.distance(z.geometry.union_all().centroid).sort_values().index
        cands_ = []
        for n_ in (4, 3, 5, 6):
            g_ = best_group(order, n_, k=40); u_ = unary_union(list(P.loc[g_].geometry)); w_, l_ = mrr(u_)
            if 0.55 <= u_.area / AC <= 1.3: cands_.append((u_.area / (w_ * l_) < 0.8, l_ / w_, g_))
        g_ = min(cands_, key=lambda t: t[:2])[2] if cands_ else best_group(order, 4)
        assign_plots(g_, 'PW', 'Place of Worship', 'learned 1 per ~160 plots; most compact plot group')
# ---------- 5. community centre (Guidelines recommended; learned civic 0.65-1.13 ac): largest compact site left nearest the centre ----------
c = compact(0.55, 1.3)
if len(c): take(c.geometry.distance(centre).idxmin(), 'CIV', 'Community Centre', 'Guidelines recommended; learned civic site 0.82 ac')
# ---------- 6. open space east of the 100 ft road, so children need not cross it ----------
east = lambda c: c.geometry.centroid.within(WZ.buffer(5))
if not ((R.use == 'POS') & east(R)).any():
    c = R[(R.use == '') & (R.ac >= 0.4) & east(R)]
    if len(c): take(c.ac.idxmax(), 'POS', 'P.O.S', 'west of the stream (children need not cross it)')
# ---------- 6b. deep irregular residential plots (> 150 ft, not on a major road, e.g. where curved roads meet) -> one defined open space if together >= 0.3 ac ----------
deep = P[(P.use == 'RE') & ~P.main & ~P.kor & np.array([mrr(g)[1] > 150 for g in P.geometry])]
if False and len(deep):
    groups = shapely.get_parts(unary_union(list(deep.geometry.buffer(1))))
    for gg in groups:
        idx = list(deep.index[deep.geometry.intersects(gg)])
        if 0.4 <= unary_union(list(P.loc[idx].geometry)).area / AC <= 1.5: assign_plots(idx, 'POS', 'P.O.S', 'irregular land where curved roads meet (as in the schemes, open space takes the irregular land)')
sa_sites = []
# ---------- 7b. open space within reach (500 m), but no more sites than the scheme rate allows (1 per ~271 plots) ----------
POS_CAP = max(1, round((P.use == 'RE').sum() / 271))
for _ in range(4):
    homes = P[P.use == 'RE']; pts = list(homes.geometry.centroid); os_ = unary_union(list(R.geometry[R.use == 'POS']) + list(P.geometry[P.use == 'POS']))
    dmax = np.array([os_.distance(p) if not os_.is_empty else 1e9 for p in pts]) * 0.3048
    if (dmax <= 500).all() or (R.use == 'POS').sum() + (P.use == 'POS').sum() >= POS_CAP + 1: break
    unc = homes[dmax > 500]; zone = unc.geometry.union_all().convex_hull.buffer(300)
    SAU = unary_union(sa_sites) if sa_sites else shapely.Point(0, 0)
    c = R[(R.use == '') & (R.ac >= 0.4) & R.geometry.intersects(zone) & (R.geometry.distance(SAU) > 197)]
    if len(c): take(c.geometry.distance(unc.geometry.union_all().centroid).idxmin(), 'POS', 'P.O.S', 'homes more than 500 m from open space')
    else:
        unc = unc[unc.geometry.distance(SAU) > 197]
        s_ = unc.geometry.centroid.distance(unc.geometry.union_all().centroid).idxmin()
        g_ = assign_plots(chain_area(s_, 0.45), 'POS', 'P.O.S', 'homes more than 500 m from open space; compact plot group >= 0.45 ac')
c = R[(R.use == '') & R.ac.between(0.12, 0.45)].sort_values('elev', ascending=False)
if len(c) and c.elev.iloc[0] >= P[P.use == 'RE'].elev.max() - 1.0: take(c.index[0], 'SU', 'UT (water tank)', 'highest ground; learned utility 0.2 ac')
elif (P.use == 'RE').any(): assign_plots(chain_area(P[P.use == 'RE'].elev.idxmax(), 0.18), 'SU', 'UT (water tank)', 'highest ground (gravity supply); learned utility site 0.2 ac')
else: assign_plots([], 'SU', 'UT (water tank)', '')
# ---------- 8. remaining leftover sites: facility programme first (local-plan pattern: wedges hold facilities), then open space, then merge ----------
nres_now = (P.use == 'RE').sum()
PROG = [('Basic School (second)', 'Ed P', 1.2, 3.0, 0, 'learned 1 school site per ~144 plots; Guidelines: basic school within walking distance'),
        ('Day Care / Nursery', 'Ed P', 0.5, 1.0, max(1, round(nres_now / 300)), 'Guidelines mandatory nursery; learned 0.65-0.97 ac'),
        ('Clinic', 'H Po', 0.5, 1.3, 1, 'second health site for ~2,700 people; learned health 0.63-1.05 ac'),
        ('Community Centre', 'CIV', 0.5, 1.3, 1 - int((R.use == 'CIV').any()), 'Guidelines recommended; learned civic 0.65-1.13 ac'),
        ('Police Post', 'CIV', 0.4, 1.1, 1, 'learned police/fire 0.58-1.09 ac'),
        ('Sub-Market / Commercial', 'Com A', 0.3, 1.6, 1, 'learned market/commercial 0.23-1.58 ac'),
        ('Lorry / Taxi Station', 'TR', 0.4, 1.4, 1 - int((R.use == 'TR').any()), 'learned transport 0.41-1.41 ac; on a collector or the main road'),
        ("Children's Playground", 'POS', 0.2, 0.6, min(2, max(1, round(nres_now / 300))), 'small play area (Tokunaso/Wassa pattern); about 1 per 300 plots'),
        ('Utility (U.T)', 'SU', 0.1, 0.35, 2, 'learned utility 0.13-0.36 ac')]
quota = {p_[0]: p_[4] for p_ in PROG}
homes_ = list(P[P.use == 'RE'].geometry.centroid); sch_now = P.geometry[P.use == 'Ed P'].union_all()
pop_ = nres_now * 7.2                                                       # ~7.2 people per plot (as the population estimate below)
far_ = max((sch_now.distance(h) for h in homes_), default=0) * 0.3048 if not sch_now.is_empty else 1e9
NEED2 = pop_ > 5000 or far_ > 800                                          # Guidelines: 1 primary per neighbourhood of <= 5,000 people; learned: homes within ~800 m
print(f'   second basic school: {"needed" if NEED2 else "not needed"} (population ~{pop_:.0f}, furthest home {far_:.0f} m from the school)', flush=True)
if NEED2:                                                                   # the leftover site that brings the furthest home closest to a school, at least 400 m from the first
    away_ = lambda g: sch_now.is_empty or g.distance(sch_now) * 0.3048 >= 400
    best_s = None
    for i in R[(R.use == '') & R.ac.between(1.2, 3.0)].index:
        g = R.geometry[i]; w2, l2_ = mrr(g)
        if not away_(g): continue
        if g.area / (w2 * l2_) < 0.7 or l2_ / w2 > 2.5: continue
        u_ = sch_now.union(g); m_ = max(u_.distance(h) for h in homes_)
        if best_s is None or m_ < best_s[0]: best_s = (m_, i)
    if not best_s:                                                           # no leftover site fits: a regular residential block that best covers the furthest homes
        B2 = P[P.use == 'RE'].groupby('block').agg(n=('use', 'size'), main=('main', 'any')).reset_index()
        B2['geometry'] = [unary_union(list(P[(P.block == k) & (P.use == 'RE')].geometry)) for k in B2.block]; B2 = gpd.GeoDataFrame(B2, geometry='geometry', crs=P.crs); B2['ac'] = B2.area / AC
        B2['fill'] = [g.area / np.prod(mrr(g.convex_hull)) for g in B2.geometry]; B2 = B2[(~B2.main) & B2.ac.between(1.2, 2.6) & (B2.fill >= 0.85)]; B2 = B2[[away_(g) for g in B2.geometry]]
        if len(B2):
            sc_ = [max(sch_now.union(g).distance(h) for h in homes_) for g in B2.geometry]; kb = B2.block.iloc[int(np.argmin(sc_))]
            assign_plots(list(P.index[(P.block == kb) & (P.use == 'RE')]), 'Ed P', 'Basic School (second)', f'learned 1 school per ~144 plots; regular block placed so every home is within {min(sc_) * 0.3048:.0f} m of a school')
        else: quota['Basic School (second)'] = 1
    if best_s: take(best_s[1], 'Ed P', 'Basic School (second)', f'Guidelines: >5,000 people or homes > 800 m away; placed >= 400 m from the first, every home within {best_s[0] * 0.3048:.0f} m of a school')
for i in R[(R.use == '')].sort_values('ac', ascending=False).index.tolist():
    g = R.geometry[i]; a_ = R.ac[i]; done = False
    near_sa = len(sa_sites) and min(g.distance(x) for x in sa_sites) < 197
    for name, use, lo, hi, _, why in PROG:
        if quota[name] <= 0 or not (lo <= a_ <= hi): continue
        if name == 'Basic School (second)' and not sch_now.is_empty and g.distance(sch_now) * 0.3048 < 400: continue      # never next to the first school
        if near_sa and use in ('POS', 'Ed P', 'H Po', 'Com A'): continue
        w2, l2_ = mrr(g)
        if use in ('Ed P', 'H Po', 'CIV', 'Com A', 'PW') and (g.area / (w2 * l2_) < 0.78 or l2_ / w2 > 2.2): continue      # buildings need compact sites
        if name == 'Lorry / Taxi Station' and g.distance(MAIN) > 3 and g.distance(COLLR) > 3: continue
        take(i, use, name, why); quota[name] -= 1; done = True; break
    if done: continue
    pos = R[R.use == 'POS']
    if a_ >= 0.6 and (len(pos) >= POS_CAP or near_sa or a_ > 2.7):      # open spaces are scheme-sized (0.5-2.7 ac): a bigger piece gets plots on its road edges first
        newp, rest_ = plots_along_frontage(g)
        if newp:
            P = gpd.GeoDataFrame(pd.concat([P, gpd.GeoDataFrame(dict(use=['RE'] * len(newp), label=[''] * len(newp), block=[-3000 - i] * len(newp), main=[q.distance(MAIN) < 3 for q in newp], kor=[False] * len(newp), elev=[elev(q) for q in newp]), geometry=newp, crs=P.crs)], ignore_index=True), geometry='geometry', crs=P.crs)
            R.at[i, 'geometry'] = rest_; R.at[i, 'ac'] = rest_.area / AC; g = rest_; a_ = R.ac[i]
            log.append(('Leftover land cut into plots', f'{len(newp)} plots', 'standard plots along the road edges of a large leftover piece'))
            if a_ < 0.05: R.at[i, 'use'] = 'DROP'; continue
    if not near_sa and len(pos) < POS_CAP and a_ >= 0.4: take(i, 'POS', 'P.O.S', 'defined open space (leftover land >= 0.4 ac, or none within 200 m)'); continue
    nb = P[(P.use == 'RE') & (P.geometry.buffer(1).intersection(g).area > 20)]          # small piece: join the neighbouring plot if it stays a sensible size
    j = max(nb.index, key=lambda j: P.geometry[j].buffer(1).intersection(g).area) if len(nb) else None
    if j is not None and (P.geometry[j].area + g.area) < 18000 and mrr(unary_union([P.geometry[j], g]))[1] < 180:
        P.at[j, 'geometry'] = unary_union([P.geometry[j], g]).buffer(0.3).buffer(-0.3); R.at[i, 'use'] = 'DROP'
    else: R.at[i, 'use'] = 'GRN'; R.at[i, 'label'] = 'Landscaped green'
R = R[R.use != 'DROP']
# ---------- landlocked pockets (>= 0.6 ac, little road frontage): a cul-de-sac (<= 200 m) square from the nearest road, plots along both sides ----------
LANES = []
ROAD_LINES = gpd.read_file(OUT + 'layout_centrelines.gpkg').geometry.union_all()
for i in []:   # cul-de-sac step tested: few plots, created double frontage -> off
    g = R.geometry[i]; q = list(g.minimum_rotated_rectangle.exterior.coords); e1, e2 = np.array(q[1]) - np.array(q[0]), np.array(q[2]) - np.array(q[1])
    Lv = e1 if np.linalg.norm(e1) > np.linalg.norm(e2) else e2; u_ = unit(Lv); cm = np.array(g.minimum_rotated_rectangle.centroid.coords[0])
    best_l = None
    for sgn in (1, -1):                                                         # enter along the pocket's long axis from whichever end is nearer a road
        far = cm + sgn * u_ * np.linalg.norm(Lv) / 2; ray = LineString([tuple(cm), tuple(far + sgn * u_ * 900)])
        h = ray.intersection(ROAD_LINES)
        hs = [x for x in shapely.get_parts(h) if x.geom_type == 'Point']
        if not hs: continue
        hp = min(hs, key=lambda x: x.distance(Point(cm))); L_ = Point(cm).distance(hp) + np.linalg.norm(Lv) / 2 - 60
        if L_ * 0.3048 <= 200 and (best_l is None or L_ < best_l[0]): best_l = (L_, np.array(hp.coords[0]), -sgn * u_)
    if best_l is None: continue
    L_, start, dirn = best_l; end = start + dirn * L_
    lane = LineString([tuple(start), tuple(end)]); lane_poly = lane.buffer(15, cap_style=2).union(Point(end).buffer(40))     # turning head
    # plots crossed by the lane are trimmed (or merged if too small)
    hitp = P[P.geometry.intersects(lane_poly)]
    for j in hitp.index:
        ng = P.geometry[j].difference(lane_poly); ng = max(shapely.get_parts(ng), key=lambda x: x.area) if not ng.is_empty else ng
        if ng.is_empty or ng.area < 6970 * 0.98: P.at[j, 'use'] = 'DROPP'
        else: P.at[j, 'geometry'] = ng
    P = P[P.use != 'DROPP']
    ROADS = ROADS.union(lane_poly); pocket = g.difference(lane_poly)
    newp = []
    for part in shapely.get_parts(pocket):
        np_, rest_ = plots_along_frontage(part); newp += np_
    if newp:
        P = gpd.GeoDataFrame(pd.concat([P, gpd.GeoDataFrame(dict(use=['RE'] * len(newp), label=[''] * len(newp), block=[-4000 - i] * len(newp), main=[False] * len(newp), kor=[False] * len(newp), elev=[elev(q) for q in newp]), geometry=newp, crs=P.crs)], ignore_index=True), geometry='geometry', crs=P.crs)
        rem = pocket.difference(unary_union(newp)); R.at[i, 'geometry'] = rem if not rem.is_empty else Point(0, 0).buffer(0.01)
        LANES.append(lane_poly); log.append(('Cul-de-sac into a landlocked pocket', f'{L_ * 0.3048:.0f} m lane, {len(newp)} plots', 'local-plan pattern; cul-de-sac <= 200 m with turning head'))
R = R[R.area > 200]
if LANES: gpd.GeoDataFrame(geometry=LANES, crs=P.crs).to_file(OUT + 'lanes.gpkg')
if quota.get('Day Care / Nursery', 0) > 0:
    big_ = R[(R.use == 'POS') & (R.area / AC > 1.6)]
    if len(big_):
        i = big_.area.idxmax(); g = R.geometry[i]; q = list(g.minimum_rotated_rectangle.exterior.coords)
        e1, e2 = np.array(q[1]) - np.array(q[0]), np.array(q[2]) - np.array(q[1]); Lv = e1 if np.linalg.norm(e1) > np.linalg.norm(e2) else e2; u_ = unit(Lv)
        o_ = np.array(g.minimum_rotated_rectangle.centroid.coords[0]) - u_ * np.linalg.norm(Lv) / 2; nn_ = np.array([-u_[1], u_[0]])
        for t_ in np.linspace(40, np.linalg.norm(Lv) - 40, 60):
            cut = LineString([tuple(o_ + u_ * t_ - nn_ * 800), tuple(o_ + u_ * t_ + nn_ * 800)]); parts = sorted(shapely.get_parts(shapely.ops.split(g, cut)), key=lambda h: h.centroid.distance(Point(o_)))
            if len(parts) == 2 and 0.6 <= parts[0].area / AC <= 1.0:
                R.at[i, 'geometry'] = parts[1]
                R = pd.concat([R, gpd.GeoDataFrame(dict(use=['Ed P'], label=['Day Care / Nursery']), geometry=[parts[0]], crs=R.crs)], ignore_index=True)
                log.append(('Day Care / Nursery', f'{parts[0].area / AC:.2f} ac carved from a large open space', 'Guidelines mandatory nursery')); break
        R = gpd.GeoDataFrame(R, geometry='geometry', crs=P.crs)
# ---------- 7. S.A: every home within 500 m (Guidelines); each site on the lowest ground of the uncovered area, >= 60 m from school/health ----------
sens = unary_union([SCH, HP, MK] + list(R.geometry[R.use.isin(['POS', 'Ed P', 'H Po'])]) + list(P.geometry[P.use.isin(['Ed P', 'H Po', 'POS'])])); sa_sites = []
for _ in range(4):
    homes = P[P.use == 'RE']; pts = list(homes.geometry.centroid)
    dmax = np.array([min([g.distance(p) for g in sa_sites]) if sa_sites else 1e9 for p in pts]) * 0.3048
    if (dmax <= 500).all(): break
    unc = homes[dmax > 500]; zone = unc.geometry.union_all().convex_hull.buffer(300)
    c = R[(R.use.isin(['', 'GRN'])) & R.ac.between(0.12, 0.45) & (R.geometry.distance(sens) > 197) & R.geometry.intersects(zone) & (R.geometry.distance(MAIN) > 3) & (R.geometry.distance(CORR) > 3)].sort_values('elev')
    if len(c) and c.elev.iloc[0] <= unc.elev.quantile(0.25): sa_sites.append(take(c.index[0], 'SU', 'S.A', 'lowest ground of its area; every home within 500 m (Guidelines); learned S.A 0.28 ac'))
    else:
        cand = unc[(unc.geometry.distance(sens) > 197) & ~unc.main & ~unc.kor]
        if cand.empty: break
        cen = unc.geometry.union_all().centroid; cand = cand[cand.elev <= cand.elev.quantile(0.4)]
        grp = None
        for s_ in cand.geometry.distance(cen).sort_values().index:               # low ground, as central to the uncovered homes as possible
            g_ = chain_area(s_, 0.25)
            if unary_union(list(P.loc[g_].geometry)).distance(sens) > 197: grp = g_; break
        if grp is None: break
        sa_sites.append(assign_plots(grp, 'SU', 'S.A', 'low ground, central to the homes it serves, >= 60 m from school, health, market and play areas; every home within 500 m (Guidelines)'))
# ---------- 9. corner shops on collector corners (1 per ~230 plots) ----------
n_sh = max(1, round(nres0 / 230))
cand = P[(P.use == 'RE') & (P.geometry.distance(COLLR) < 3) & ~P.main].copy()
cand['corner'] = [g.buffer(3).intersection(RD['30 ft local road']).area for g in cand.geometry]
for s in cand.sort_values('corner', ascending=False).index[:n_sh]: P.at[s, 'use'] = 'Com A'; P.at[s, 'label'] = 'Corner Shop'
log.append(('Corner Shop', f'{n_sh} corner plot(s) on the collector', 'learned 1 per ~230 plots'))
# ---------- 10. deep frontage plots on the 60 ft main road / 100 ft corridor (> 140 ft deep) -> mixed use (commercial below, residential above) ----------
mu = [i for i in P.index[P.use == 'RE'] if mrr(P.geometry[i])[1] > 140 and (P.geometry[i].distance(MAIN) < 3 or P.geometry[i].distance(CORR) < 3)]
P.loc[mu, 'use'] = 'MU'; P.loc[mu, 'label'] = ''
log.append(('Mixed use frontage plots', f'{len(mu)} plots', 'deep plots on the major roads; Guidelines: mixed use / commercial along major roads'))
# ---------- larger plots with roads front and back -> commercial (local plans put shops/commercial where plots face two roads) ----------
nc = 0
for i in P.index[P.use == 'RE']:
    ns = frontage_dirs(P.geometry[i])
    if any(float(ns[a] @ ns[b]) < -0.8 for a in range(len(ns)) for b in range(a + 1, len(ns))): P.at[i, 'use'] = 'Com A'; P.at[i, 'label'] = 'Commercial'; nc += 1
log.append(('Commercial (plots with two road frontages)', f'{nc} plots', 'no residential double frontage'))
# ---------- final check: residential plots with no road access join a neighbour ----------
for i in list(P.index[P.use == 'RE']):
    if i not in P.index or frontage_dirs(P.geometry[i]): continue
    nb = P[(P.index != i) & (P.use == 'RE') & (P.geometry.buffer(1).intersection(P.geometry[i]).area > 20)]
    if nb.empty: continue
    j = max(nb.index, key=lambda j: P.geometry[j].buffer(1).intersection(P.geometry[i]).area); ug = unary_union([P.geometry[j], P.geometry[i]]).buffer(0.3).buffer(-0.3)
    if ug.geom_type == 'Polygon': P.at[j, 'geometry'] = ug; P.drop(index=i, inplace=True)
# ---------- open spaces are scheme-sized (median 1.4 ac, at most 2.7 ac): a bigger one gets standard plots along its road edges ----------
for i in list(R.index[R.use == 'POS']):
    g = R.geometry[i]
    if g.area / AC <= 2.7: continue
    newp, rest_ = plots_along_frontage(g)
    if not newp: continue
    P = gpd.GeoDataFrame(pd.concat([P, gpd.GeoDataFrame(dict(use=['RE'] * len(newp), label=[''] * len(newp), block=[-4000 - i] * len(newp), main=[q.distance(MAIN) < 3 for q in newp], kor=[False] * len(newp), elev=[elev(q) for q in newp]), geometry=newp, crs=P.crs)], ignore_index=True), geometry='geometry', crs=P.crs)
    R.at[i, 'geometry'] = rest_; R.at[i, 'ac'] = rest_.area / AC
    log.append(('Open space reduced to scheme size', f'{len(newp)} plots', f'{g.area / AC:.1f} ac open space: standard plots cut along its road edges, {rest_.area / AC:.1f} ac kept as P.O.S'))
# ---------- no plot far below the Residential B minimum: a small one joins the neighbour it shares the longest edge with ----------
for i in list(P.index[(P.use == 'RE') & (P.area < 0.6 * 6970)]):
    if i not in P.index: continue
    g = P.geometry[i]; nb = P[(P.index != i) & (P.use == 'RE') & (P.geometry.buffer(1).intersection(g).area > 20)]
    if nb.empty: P.at[i, 'use'] = 'GRN'; P.at[i, 'label'] = 'Landscaped green (island too small for a plot)'; continue
    j = max(nb.index, key=lambda j: P.geometry[j].buffer(1).intersection(g).area); ug = unary_union([P.geometry[j], g]).buffer(0.3).buffer(-0.3)
    if ug.geom_type == 'Polygon': P.at[j, 'geometry'] = ug; P.drop(index=i, inplace=True)
# ---------- deep plots at sector edges (150-230 ft, one frontage) -> Residential A (larger lots, LUSPA zone) ----------
ra = []                                              # Residential A as a ZONE: whole blocks whose plots are mostly deep, never single scattered plots
for b_, grp_ in P[P.use == 'RE'].groupby('block'):
    deep_ = [i for i in grp_.index if 150 < mrr(P.geometry[i])[1] <= 235]
    if len(grp_) >= 3 and len(deep_) >= 0.6 * len(grp_): ra += list(grp_.index)
P.loc[ra, 'use'] = 'RA'; P.loc[ra, 'label'] = ''
log.append(('Residential A (larger lots at sector edges)', f'{len(ra)} plots', 'whole blocks of deep plots (150-230 ft) where grids meet curved tracks / the boundary'))
# ---------- outputs ----------
res = P[P.use.isin(['RE', 'RA'])]
print('program (Manual 4.6.3):', program)
print(f'plots {len(P)} | residential {len(res)} | population ~{len(res) * 7.2:.0f}')
for l in log: print('  ', l)
P.to_file(OUT + 'plots_landuse.gpkg'); R.to_file(OUT + 'reserves_landuse.gpkg')
json.dump(dict(program=program, res_plots=len(res), log=log), open(OUT + 'allocate.json', 'w'), indent=1)
COL = {'RA': '#c96a1a', 'MU': '#b5651d', 'CIV': '#c19bd8', 'TR': '#9a9a9a', 'RE': '#DC7C24', 'BM': '#73B2FF', 'Com A': '#73B2FF', 'PW': '#FF7F7F', 'H Po': '#FF0000', 'Ed P': '#FFFF00', 'POS': '#00FF00', 'SU': '#a0522d', 'GRN': '#b8f0b8'}
r = rasterio.open(OUT + 'imagery_2136.tif'); a = np.moveaxis(r.read(), 0, -1); bb = r.bounds
fig, ax = plt.subplots(figsize=(15, 14)); ax.imshow(a, extent=(bb.left, bb.right, bb.bottom, bb.top), alpha=.35)
gpd.GeoSeries([SR]).plot(ax=ax, color='#2e8b57', alpha=.8)
for cls, c_ in (('30 ft local road', '#e6e6e6'), ('40 ft collector', '#f5c242'), ('60 ft existing road', '#8c8c8c')): gpd.GeoSeries([RD[cls]]).plot(ax=ax, color=c_)
CNT = luspa_draw(ax, R, 'use', DESIGN_LUSPA, lw=.5, ec='k'); C2 = luspa_draw(ax, P, 'use', DESIGN_LUSPA, lw=.4, ec='k')
for k_, v_ in C2.items(): CNT[k_] = CNT.get(k_, 0) + v_
for g, l in list(zip(P.geometry, P.label)) + list(zip(R.geometry, R.label)):
    if l and l != 'Landscaped green':
        c_ = g.representative_point(); ax.text(c_.x, c_.y, l.replace('Neighbourhood Shopping Centre / Market', 'Market').replace(' (mixed use)', '').replace(' (Primary + JHS) and Nursery', '\n(Primary, JHS, Nursery)'), fontsize=7.5, ha='center', weight='bold')
gpd.GeoSeries([SITE]).boundary.plot(ax=ax, color='yellow', lw=2)
ax.legend(handles=luspa_handles(CNT) + [Patch(color='#2e8b57', label='Stream reserve (wooded)'), Patch(color='#8c8c8c', label='Main / existing roads'), Patch(color='#f5c242', label='40 ft collector'), Patch(color='#e6e6e6', label='30 ft local road')], loc='lower left', fontsize=9, title='LUSPA colour codes (Zoning Guidelines 2025)')
x0, y0, x1, y1 = SITE.buffer(80).bounds; ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_xticks([]); ax.set_yticks([])
ax.set_title(f'Test 3: {len(res)} residential plots, about {round(len(res) * 7.2, -1):,.0f} people', fontsize=14)
plt.savefig(OUT + 'landuse_preview.png', bbox_inches='tight', dpi=80)
