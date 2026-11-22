"""Road centrelines realigned to the image; existing reserves re-measured; pinch points by class minimum and the road's own width."""
import numpy as np, cv2, rasterio, geopandas as gpd, pandas as pd, shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely import affinity
D = 'D:/Work/2026/Machine Learning/Test 5 outputs/'; FT = 0.3048
r = rasterio.open('ml5/img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); Ti = ~r.transform
hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV); gr = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(float)
mu = cv2.blur(gr, (7, 7)); sd = np.sqrt(np.maximum(cv2.blur(gr * gr, (7, 7)) - mu * mu, 0))
roadlike = ((hsv[:, :, 1] < 55) & (gr > 50) & (gr < 175) & (sd < 18)).astype(float); roadlike = cv2.blur(roadlike, (5, 5))
site = gpd.read_file('D:/Work/2026/Machine Learning/Test 5.kml').to_crs(2136).geometry.iloc[0]
R = gpd.read_file(D + 'Test5_Roads_existing.shp'); R3 = R.to_crs(3857)
B = gpd.read_file(D + 'Test5_Buildings_final.shp'); W = gpd.read_file(D + 'Test5_Walls_final.shp')
def score(line):
    pts = [line.interpolate(t) for t in np.linspace(0, line.length, max(4, int(line.length)))]; v = []
    for p in pts:
        x, y = Ti * (p.x, p.y); x, y = int(x), int(y)
        if 0 <= x < img.shape[1] and 0 <= y < img.shape[0]: v.append(roadlike[y, x])
    return np.mean(v) if v else 0
new = []; orig = list(R3.geometry)
for g in R3.geometry:
    best = (score(g), g)
    for off in np.arange(-6, 6.01, 0.5):
        if off == 0: continue
        try: o = g.offset_curve(off)
        except Exception: continue
        if o.is_empty or o.geom_type != 'LineString': continue
        sc = score(o)
        if sc > best[0] + 0.02: best = (sc, o)
    new.append(best[1])
# segments are nudged one by one: ends that met before the nudge meet again (average position); ends that stopped on another road go back onto it
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
R['carriage_w'] = np.where(nm != '', R.groupby([nm, R.highway]).carriage_w.transform('median'), R.carriage_w)
OBST = unary_union(list(B.geometry) + [w.buffer(0.3) for w in W.geometry])
MINW = {'service': 7.5, 'residential': 9.0, 'unclassified': 9.0, 'tertiary': 12.0, 'secondary': 15.0, 'primary': 20.0}
res, pins, onroad = [], [], []
for i, g in enumerate(R.geometry):
    ws = []
    for s in np.arange(20, g.length - 20, 30):
        p = np.array(g.interpolate(s).coords[0]); q = np.array(g.interpolate(min(g.length, s + 5)).coords[0]) - np.array(g.interpolate(max(0, s - 5)).coords[0])
        t = q / (np.linalg.norm(q) + 1e-9); n = np.array([-t[1], t[0]])
        if Point(p).within(OBST): onroad.append(dict(road=R.name.iloc[i] or R.highway.iloc[i], geometry=Point(p))); continue
        side = []
        for sg in (1, -1):
            h = LineString([tuple(p), tuple(p + sg * n * 130)]).intersection(OBST)
            side.append(min(Point(p).distance(x) for x in shapely.get_parts(h)) if not h.is_empty else np.nan)
        if not any(np.isnan(side)): ws.append((sum(side) * FT, Point(p)))
    if not ws: res.append(np.nan); continue
    arr = np.array([w for w, _ in ws]); med = float(np.median(arr)); res.append(round(med, 1))
    lim = min(0.8 * med, MINW.get(R.highway.iloc[i], 9.0))
    for w_, pt in ws:
        if 2.5 < w_ < lim: pins.append(dict(road=R.name.iloc[i] or R.highway.iloc[i], highway=R.highway.iloc[i], width_m=round(w_, 1), road_med_m=round(med, 1), class_min_m=MINW.get(R.highway.iloc[i], 9.0), geometry=pt))
R['reserve_m'] = res; R.to_file(D + 'Test5_Roads_existing.shp')
PP = gpd.GeoDataFrame(pins, crs=2136)
if len(PP):
    cl = unary_union([p.buffer(25 / FT) for p in PP.geometry]); keep = []
    for c in shapely.get_parts(cl):
        sub = PP[PP.within(c)]; keep.append(sub.loc[sub.width_m.idxmin()])
    PP = gpd.GeoDataFrame(keep, crs=2136).reset_index(drop=True)
PP = PP[PP.within(site)].reset_index(drop=True)
PP['action'] = np.where(PP.width_m < 6, 'Severe: set back encroaching wall / structure; building line on redevelopment', 'Narrow: no parking, traffic calming; building line on redevelopment')
PP.to_file(D + 'Test5_Plan_pinch_point_actions.shp'); PP.to_file(D + 'Test5_Road_pinch_points.shp')
OR = gpd.GeoDataFrame(onroad, crs=2136); OR = OR[OR.within(site)]
OR.to_file(D + 'Test5_Check_footprint_on_road.shp') if len(OR) else None
print('pinch points', len(PP), PP.width_m.describe().round(1).to_dict() if len(PP) else '', '| severe (<6 m)', int((PP.width_m < 6).sum()), '| centreline samples inside a footprint (check):', len(OR))
print(R.groupby('highway').reserve_m.median().round(1).to_dict())
