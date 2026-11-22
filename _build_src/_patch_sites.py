"""Large service / utility sites (schools, hospitals, police, ...) are one plot, never subdivided."""
def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
# ---------------- fetch: OSM site outlines (school grounds, hospital grounds, police, utilities ...) ----------------
patch('toolkit_src/new_stages.py', [
 ("    print(f'   OSM: {len(O)} buildings, {len(Rd)} road segments {Rd.highway.value_counts().to_dict()}, {len(Pp)} POIs'); progress(70, 'OpenStreetMap')",
  """    print(f'   OSM: {len(O)} buildings, {len(Rd)} road segments {Rd.highway.value_counts().to_dict()}, {len(Pp)} POIs'); progress(70, 'OpenStreetMap')
    try: fetch_osm_sites(w - b, s - b, e + b, n + b, S, WORK)
    except Exception as ex: print('   OSM site outlines not available:', str(ex)[:100], flush=True)"""),
])
s = open('toolkit_src/new_stages.py', encoding='utf-8').read()
s += r'''
# OSM tags of service / utility sites that are kept as ONE plot (never subdivided), with their land use
SITE_TAGS = {('amenity', 'school'): 'Education', ('amenity', 'kindergarten'): 'Education', ('amenity', 'college'): 'Education', ('amenity', 'university'): 'Education',
             ('amenity', 'hospital'): 'Health', ('amenity', 'clinic'): 'Health', ('healthcare', 'hospital'): 'Health', ('healthcare', 'clinic'): 'Health',
             ('amenity', 'police'): 'Civic', ('amenity', 'fire_station'): 'Civic', ('amenity', 'prison'): 'Civic', ('amenity', 'townhall'): 'Civic',
             ('amenity', 'courthouse'): 'Civic', ('amenity', 'post_office'): 'Civic', ('amenity', 'community_centre'): 'Civic', ('office', 'government'): 'Civic',
             ('landuse', 'military'): 'Civic', ('military', 'barracks'): 'Civic', ('amenity', 'place_of_worship'): 'Religious', ('landuse', 'religious'): 'Religious',
             ('amenity', 'marketplace'): 'Market', ('amenity', 'bus_station'): 'Transport terminal', ('amenity', 'fuel'): 'Commercial (fuel)',
             ('power', 'substation'): 'Utility', ('power', 'plant'): 'Utility', ('man_made', 'water_works'): 'Utility', ('man_made', 'wastewater_plant'): 'Utility',
             ('landuse', 'cemetery'): 'Civic', ('amenity', 'grave_yard'): 'Civic', ('leisure', 'stadium'): 'Recreation', ('leisure', 'sports_centre'): 'Recreation'}
def fetch_osm_sites(w, s, e, n, S, WORK):
    """outlines of service / utility sites (closed ways with the tags above) -> osm_sites.gpkg (EPSG:2136)"""
    import geopandas as gpd
    from shapely.geometry import Polygon
    small = (e - w) * (n - s) < 0.04; rows = []
    if small: nodes, ways = osm_api_map(w, s, e, n); items = [(t, ref) for _, t, ref in ways]
    else:
        BB = f'{s},{w},{n},{e}'; q = ''.join(f'way["{k}"="{v}"]({BB});' for k, v in SITE_TAGS)
        d = overpass(f'[out:json][timeout:60];({q});out geom;'); items = [(el.get('tags', {}), [(p['lon'], p['lat']) for p in el.get('geometry', [])]) for el in (d or {}).get('elements', [])]
    for t, ref in items:
        if len(ref) < 4 or ref[0] != ref[-1]: continue
        hit = next(((k, v) for (k, v) in SITE_TAGS if t.get(k) == v), None)
        if hit and 'building' not in t: rows.append(dict(tag=f'{hit[0]}={hit[1]}', use=SITE_TAGS[hit], name=t.get('name'), geometry=Polygon(ref)))
    G = gpd.GeoDataFrame(rows, geometry='geometry', crs=4326) if rows else gpd.GeoDataFrame(columns=['tag', 'use', 'name', 'geometry'], geometry='geometry', crs=4326)
    G = G.to_crs(2136); G = G[G.intersects(S)]; G.to_file(WORK + 'osm_sites.gpkg'); print(f'   OSM site outlines (schools, hospitals, police, utilities ...): {len(G)}', flush=True)
'''
open('toolkit_src/new_stages.py', 'w', encoding='utf-8').write(s)
# ---------------- plots stage: sites carved out whole; touching service plots of one use merged ----------------
patch('toolkit_src/build.py', [("    s = must(s, \"PL.to_file(D + PFX + 'Plots_existing.shp');\", \"save_plots(PL);\", 1, 'plots')",
'''    s = must(s, "PL.to_file(D + PFX + 'Plots_existing.shp');", "save_plots(PL);", 1, 'plots')
    # service / utility sites (OSM outlines) are taken out of the blocks whole, before the subdivision
    s = must(s, "for bid, blk0 in zip(BLK.block_id, BLK.geometry):", """SITES = gpd.read_file(WORK + 'osm_sites.gpkg') if os.path.exists(WORK + 'osm_sites.gpkg') else None
SITE_PIECES = []                                                            # (block id, geometry, use, name)
if SITES is not None and len(SITES):
    SU_ = unary_union([g.buffer(0) for g in SITES.geometry])
    newb = []
    for bid_, g_ in zip(BLK.block_id, BLK.geometry):
        g_ = shapely.force_2d(g_).buffer(0)
        for _, srow in SITES.iterrows():
            part = g_.intersection(srow.geometry.buffer(0))
            for q_ in shapely.get_parts(part):
                if q_.geom_type == 'Polygon' and q_.area * FT * FT > 300: SITE_PIECES.append((bid_, q_, srow['use'], srow.get('name')))
        newb.append(g_.difference(SU_) if any(sp[0] == bid_ for sp in SITE_PIECES) else g_)
    BLK = BLK.copy(); BLK['geometry'] = newb
    print(f'   service / utility sites kept whole: {len(SITE_PIECES)}', flush=True)
for bid, blk0 in zip(BLK.block_id, BLK.geometry):""", 1, 'plots')
    s = must(s, "PL = gpd.GeoDataFrame(dict(block_id=[p[0] for p in pieces]), geometry=[p[1] for p in pieces], crs=2136)",
             "pieces += [(sp[0], sp[1]) for sp in SITE_PIECES]\\nPL = gpd.GeoDataFrame(dict(block_id=[p[0] for p in pieces]), geometry=[p[1] for p in pieces], crs=2136)", 1, 'plots')
    s = must(s, "PL['ex_use'], PL['main_bld'], PL['n_bld'] = uses, mbs, nbs", """PL['ex_use'], PL['main_bld'], PL['n_bld'] = uses, mbs, nbs
# a site carved from OSM keeps its own use (school, hospital, police ...)
for sp in SITE_PIECES:
    hit = PL.index[[g.representative_point().within(sp[1].buffer(1)) and g.intersection(sp[1]).area > 0.8 * g.area for g in PL.geometry]]
    for i_ in hit: PL.at[i_, 'ex_use'] = sp[2]
# services and utilities are ONE plot: touching plots of the same service use in a block are merged
SERVICE = {'Education', 'Health', 'Civic', 'Religious', 'Religious / assembly', 'Transport terminal', 'Market', 'Utility', 'Recreation', 'Institutional / large commercial (verify)'}
rows_ = []; drop_ = set()
for (bid_, use_), grp_ in PL[PL.ex_use.isin(SERVICE)].groupby(['block_id', 'ex_use']):
    if len(grp_) < 2: continue
    comps = shapely.get_parts(unary_union([g.buffer(0.5) for g in grp_.geometry]))
    for c_ in comps:
        mem = [i_ for i_ in grp_.index if grp_.geometry[i_].intersects(c_)]
        if len(mem) < 2: continue
        g_ = unary_union([PL.geometry[i_] for i_ in mem]).buffer(0.3).buffer(-0.3)
        keep_ = max(mem, key=lambda i_: PL.geometry[i_].area); PL.at[keep_, 'geometry'] = max(shapely.get_parts(g_), key=lambda x: x.area) if g_.geom_type != 'Polygon' else g_
        PL.at[keep_, 'n_bld'] = int(sum(PL.n_bld[i_] for i_ in mem)); drop_.update(i_ for i_ in mem if i_ != keep_)
if drop_: PL = PL.drop(index=list(drop_)).reset_index(drop=True); print(f'   service plots merged into whole sites: {len(drop_)} plot lines removed', flush=True)""", 1, 'plots')''')])
print('ok')
