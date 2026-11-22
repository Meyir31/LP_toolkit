"""Plot size after the design: re-plot selected blocks (or the whole planning area) with the planner's plot breadth x length.
Two ways to handle what does not divide exactly, previewed side by side before the planner chooses:
  fit   - the breadth is kept; the row leftover goes to the two end plots and the block depth is shared between the rows
  exact - every plot is exactly breadth x length; leftover strips are left open (landscaped green)
Residential plots only (RE / RA / MU); facility sites in the blocks stay as they are."""
import os
import numpy as np

RESU = ['RE', 'RA', 'MU']
MIN_SQFT = 6970                                                         # LUSPA Residential B minimum (0.16 ac)
AC = 43560.0


def _region(work, fids, whole):
    import geopandas as gpd
    from shapely.ops import unary_union
    P = gpd.read_file(work + 'plots_landuse.gpkg')
    if whole: res = P[P.use.isin(RESU)]
    else:
        sel = P.iloc[[i for i in fids if 0 <= i < len(P)]]
        if not len(sel): raise ValueError('select plots in the blocks to re-plot first (or choose the whole planning area)')
        idx = set(sel[sel.use.isin(RESU)].index)
        bf = work + 'layout_blocks.gpkg'
        if os.path.exists(bf):                                          # the whole block of every selected plot
            B = gpd.read_file(bf); rp = sel.geometry.representative_point()
            hit = [b for b in B.geometry if any(b.buffer(3).contains(p) for p in rp)]
            if hit:
                BU = unary_union([b.buffer(3) for b in hit]); inb = P.geometry.representative_point().within(BU) & P.use.isin(RESU)
                idx |= set(P.index[inb])
        res = P.loc[sorted(idx)]
    if not len(res): raise ValueError('no residential plots in the selection: plot size applies to residential blocks')
    return P, res


def _roads(work):
    import geopandas as gpd
    return gpd.read_file(work + 'layout_roads.gpkg').union_all()


def compute(work, fids, whole, breadth, length, mode):
    """-> dict(P, res, plots [dict], open [polygon], stats)"""
    import shapely
    from shapely.ops import unary_union
    from localplots import subdivide_blocks_rows
    P, res = _region(work, fids, whole)
    RS = _roads(work)
    region = unary_union(list(res.geometry)).difference(RS.buffer(0.05))
    blocks = [q for q in shapely.get_parts(region) if q.geom_type == 'Polygon' and q.area > 2000]
    plots, reserves = subdivide_blocks_rows(blocks, RS, None, breadth, length, mode)
    opens = [r['geometry'] for r in reserves]
    def mrr(g):
        import math
        c = list(g.minimum_rotated_rectangle.exterior.coords); return sorted([math.dist(c[0], c[1]), math.dist(c[1], c[2])])
    for p in plots:
        w, d = mrr(p['geometry']); p['w'] = round(w, 1); p['d'] = round(d, 1); p['sqft'] = round(p['geometry'].area)
        p['ok'] = abs(w - breadth) <= 0.15 * breadth and abs(d - length) <= 0.15 * length if breadth and length else True
        p['small'] = p['sqft'] < MIN_SQFT
    n = len(plots)
    stats = dict(mode=mode, before=len(res), plots=n, blocks=len(blocks), size_ok=sum(p['ok'] for p in plots), below_min=sum(p['small'] for p in plots),
                 open_ac=round(sum(g.area for g in opens) / AC, 2), median_w=float(np.median([p['w'] for p in plots])) if n else 0, median_d=float(np.median([p['d'] for p in plots])) if n else 0)
    return dict(P=P, res=res, plots=plots, open=opens, stats=stats)


def to_fc(r):
    import geopandas as gpd
    feats = []
    if r['plots']:
        g = gpd.GeoDataFrame([dict(how=p.get('how', ''), row=p.get('row', ''), w=p['w'], d=p['d'], sqft=p['sqft'], ok=bool(p['ok']), small=bool(p['small'])) for p in r['plots']],
                             geometry=[p['geometry'] for p in r['plots']], crs=2136).to_crs(4326)
        import json; feats += json.loads(g.to_json(drop_id=True))['features']
    if r['open']:
        g = gpd.GeoDataFrame(dict(open=[1] * len(r['open'])), geometry=r['open'], crs=2136).to_crs(4326)
        import json; feats += json.loads(g.to_json(drop_id=True))['features']
    return dict(type='FeatureCollection', features=feats)


def apply(work, fids, whole, breadth, length, mode, history=None):
    """write the re-plotted blocks into plots_landuse (and the open pieces into reserves_landuse as landscaped green)"""
    import geopandas as gpd, pandas as pd, time
    r = compute(work, fids, whole, breadth, length, mode)
    P, res = r['P'], r['res']
    fp, fr = work + 'plots_landuse.gpkg', work + 'reserves_landuse.gpkg'
    if history:                                                         # one undo step per layer (the editor's Undo on that layer)
        for f, rel in ((fp, history[0]), (fr, history[1])):
            if os.path.exists(f):
                os.makedirs(rel, exist_ok=True); gpd.read_file(f).to_file(os.path.join(rel, time.strftime('%Y%m%d-%H%M%S-') + str(int(time.time() * 1000) % 1000) + '.gpkg'))
    def inherit(q):                                                     # use / block of the old plot it overlaps most
        cand = res[res.geometry.intersects(q.buffer(-1))]
        if not len(cand): return 'RE', None
        k = cand.geometry.intersection(q).area.idxmax(); return cand.use[k], (cand.block[k] if 'block' in cand.columns else None)
    rows = []
    for p in r['plots']:
        u, b = inherit(p['geometry'])
        rows.append(dict(block=b if b is not None else -1, how=p.get('how', ''), row=p.get('row', ''), w=p['w'], d=p['d'], kind='plot', use=u, label='', geometry=p['geometry']))
    newp = gpd.GeoDataFrame(rows, geometry='geometry', crs=P.crs) if rows else P.iloc[:0]
    P = P.drop(index=res.index)
    P = gpd.GeoDataFrame(pd.concat([P, newp], ignore_index=True), crs=P.crs)
    P = P[~P.geometry.is_empty & (P.area > 300)].reset_index(drop=True); P['area'] = P.area
    if 'chamfered' in P: P['chamfered'] = P['chamfered'].fillna(0)
    P.to_file(fp)
    if r['open'] and os.path.exists(fr):
        R = gpd.read_file(fr)
        S_ = gpd.GeoDataFrame(dict(use=['GRN'] * len(r['open']), label=['Landscaped green (plot size leftover)'] * len(r['open'])), geometry=r['open'], crs=R.crs)
        R = gpd.GeoDataFrame(pd.concat([R, S_], ignore_index=True), crs=R.crs); R.to_file(fr)
    return r['stats']
