"""Split a merged road surface into one polygon per road centreline (EPSG:2136, feet).
Junctions go to the higher road (trunk > primary > secondary > ...); left-over slivers join the piece they touch most."""
RANK = {'motorway': 0, 'trunk': 1, 'primary': 2, 'secondary': 3, 'tertiary': 4, 'unclassified': 5, 'residential': 6, 'living_street': 6,
        'service': 7, 'track': 8, 'pedestrian': 8, 'footway': 9, 'path': 9}


def _poly(g):
    """valid, polygon-only version of g"""
    import shapely
    from shapely.geometry import MultiPolygon
    g = shapely.make_valid(g)
    ps = [p for p in shapely.get_parts(g) if p.geom_type == 'Polygon' and not p.is_empty]
    ps += [q for p in shapely.get_parts(g) if p.geom_type == 'MultiPolygon' for q in p.geoms]
    return ps[0] if len(ps) == 1 else MultiPolygon(ps) if ps else shapely.Polygon()


def split_surface_per_road(surface, R, FT=0.3048):
    """surface: shapely (Multi)Polygon; R: GeoDataFrame of centrelines (same CRS) with optional name / highway / carriage_w.
    returns a GeoDataFrame: one row per road, with the road's attributes, area_m2 and geometry"""
    import geopandas as gpd, shapely
    from shapely.strtree import STRtree
    from shapely.ops import unary_union
    S = shapely.make_valid(surface).buffer(0)
    R = R[R.geometry.notna() & ~R.geometry.is_empty].copy().reset_index(drop=True)
    if not len(R) or S.is_empty: return None
    hw = R['highway'] if 'highway' in R else None
    R['_r'] = hw.map(RANK).fillna(6) if hw is not None else 6
    cw = R['carriage_w'].fillna(7.0) if 'carriage_w' in R else 7.0
    R['_w'] = (cw / 2 + 2.5) / FT                                  # half carriageway + footway, in feet
    R['_len'] = R.length
    order = R.sort_values(['_r', '_len'], ascending=[True, False]).index
    pieces, taken = {}, []
    tree_taken = None
    for i in order:
        buf = R.geometry[i].buffer(R._w[i] * 1.15, cap_style='flat')
        part = S.intersection(buf)
        if part.is_empty: continue
        if taken:
            near = [taken[k] for k in STRtree(taken).query(part)] if len(taken) > 1 else taken
            if near: part = part.difference(unary_union(near))
        part = _poly(part)
        if part.is_empty or part.area * FT * FT < 1: continue
        pieces[i] = part; taken.append(part)
    if not pieces: return None
    # left-overs (junction corners, kerb returns): join the piece they share the longest edge with
    rest = _poly(S.difference(unary_union(list(pieces.values()))))
    keys = list(pieces); tree = STRtree([pieces[k] for k in keys])
    for q in shapely.get_parts(rest):
        if q.area * FT * FT < 0.5: continue
        cand = [keys[j] for j in tree.query(q.buffer(1))]
        if not cand:
            cand = [min(keys, key=lambda k: pieces[k].distance(q))]
        best = max(cand, key=lambda k: pieces[k].buffer(0.5).intersection(q.boundary).length)
        pieces[best] = _poly(pieces[best].union(q))
    rows = []
    keep = [c for c in ('osm_id', 'name', 'highway', 'carriage_w', 'reserve_m') if c in R.columns]
    for i, g in pieces.items():
        g2 = _poly(g.buffer(0.2).buffer(-0.2))
        g = g2 if not g2.is_empty and g2.area > 0.995 * g.area else g
        if g.is_empty: continue
        r = {c: R.at[i, c] for c in keep}; r['area_m2'] = round(g.area * FT * FT, 1); r['geometry'] = g; rows.append(r)
    return gpd.GeoDataFrame(rows, geometry='geometry', crs=R.crs)


def split_file(surface_shp, centrelines_shp, backup=True):
    """convert an existing merged Road_surface.shp in place (the merged original is kept as *_merged.shp)"""
    import geopandas as gpd, os, shutil, glob
    S = gpd.read_file(surface_shp)
    if 'highway' in S.columns or 'name' in S.columns or not os.path.exists(centrelines_shp): return False
    R = gpd.read_file(centrelines_shp)
    if S.crs is None: S = S.set_crs(2136)
    R = R.to_crs(S.crs) if R.crs else R.set_crs(S.crs)
    out = split_surface_per_road(S.union_all(), R)
    if out is None or len(out) < 2: return False
    if backup:
        base = surface_shp[:-4]
        for x in glob.glob(base + '.*'): shutil.copy(x, base + '_merged' + os.path.splitext(x)[1])
    out.to_file(surface_shp)
    return True
