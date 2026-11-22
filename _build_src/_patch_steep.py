import sys
def patch(p, a, b):
    s = open(p, encoding='utf-8').read(); assert s.count(a) == 1, (p, s.count(a), a[:80]); open(p, 'w', encoding='utf-8').write(s.replace(a, b))
for p in sys.argv[1:]:
    patch(p, "CT = CT[~CT.is_empty]; CT.to_file(D + PFX + 'Contours.shp')",
             "CT['geometry'] = [shapely.line_merge(shapely.union_all([q for q in shapely.get_parts(x) if q.geom_type in ('LineString', 'MultiLineString')])) for x in CT.geometry]   # lines only: a clip can leave points\n"
             "    CT = CT[~CT.is_empty & CT.geom_type.isin(['LineString', 'MultiLineString'])]; CT.to_file(D + PFX + 'Contours.shp')")
    patch(p, "        GS = gpd.GeoDataFrame(dict(reserve=",
             "        g = shapely.union_all([q for q in shapely.get_parts(g) if q.geom_type in ('Polygon', 'MultiPolygon') and q.area > 0]) if not g.is_empty else g   # areas only: the clip can leave slivers of line / point\n"
             "        g = g if (not g.is_empty and g.geom_type in ('Polygon', 'MultiPolygon')) else Polygon()\n"
             "        GS = gpd.GeoDataFrame(dict(reserve=")
    print('patched', p)
