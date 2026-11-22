import math, numpy as np, pandas as pd, geopandas as gpd, rasterio, cv2, shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union, transform as shp_transform, linemerge
K = ctx['_K']
site = gpd.read_file('D:/Work/2026/Machine Learning/Test 5.kml').to_crs(2136).geometry.iloc[0]
# ---------- 3. walls: stronger detection, joined, off roofs and roads ----------
r = rasterio.open('ml5/img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); T = r.transform; Ti = ~r.transform
K3 = K.to_crs(3857); bpx = [shp_transform(lambda x, y, z=None: Ti * (x, y), g) for g in K3.geometry]
from skimage.filters import sato
from skimage.morphology import skeletonize, remove_small_objects
from skimage.transform import probabilistic_hough_line
g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(float) / 255
rid = sato(g, sigmas=[1.0, 1.5], black_ridges=False)
m = remove_small_objects(rid > np.percentile(rid, 90), 20); sk = skeletonize(m)
segs = probabilistic_hough_line(sk, threshold=7, line_length=int(4.0 / 0.299), line_gap=4, rng=0)
BU = unary_union([p.buffer(2.5) for p in bpx])
hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV); gr = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(float)
mu = cv2.blur(gr, (21, 21)); sd = np.sqrt(np.maximum(cv2.blur(gr * gr, (21, 21)) - mu * mu, 0))
road = (sd < 11) & (hsv[:, :, 1] < 45) & (gr > 60) & (gr < 160); road = cv2.morphologyEx(road.astype(np.uint8), cv2.MORPH_OPEN, np.ones((13, 13), np.uint8)).astype(bool)
keep_s = []
for (x0, y0), (x1, y1) in segs:
    s = LineString([(x0, y0), (x1, y1)])
    if s.intersection(BU).length > 0.4 * s.length: continue
    n = max(2, int(s.length)); xs = np.clip(np.linspace(x0, x1, n).astype(int), 0, road.shape[1] - 1); ys = np.clip(np.linspace(y0, y1, n).astype(int), 0, road.shape[0] - 1)
    if road[ys, xs].mean() > 0.4: continue
    keep_s.append(s)
# join: snap near-collinear segments that touch / overlap (buffer-dissolve then centrelines via skeleton of the dissolved strip)
strip = unary_union([s.buffer(0.9, cap_style=2) for s in keep_s])
joined = []
for part in shapely.get_parts(strip):
    q = list(part.minimum_rotated_rectangle.exterior.coords); e1 = np.array(q[1]) - np.array(q[0]); e2 = np.array(q[2]) - np.array(q[1])
    L, Wd = (e1, e2) if np.linalg.norm(e1) >= np.linalg.norm(e2) else (e2, e1)
    if np.linalg.norm(Wd) < 4:                                               # straight strip -> one wall line
        c = np.array(part.minimum_rotated_rectangle.centroid.coords[0]); u = L / np.linalg.norm(L)
        joined.append(LineString([tuple(c - u * np.linalg.norm(L) / 2), tuple(c + u * np.linalg.norm(L) / 2)]))
    else:                                                                    # corner / L-shaped: keep its member segments
        joined += [s for s in keep_s if s.within(part.buffer(0.1))]
joined = [s for s in joined if s.length * 0.299 >= 4]
WL = gpd.GeoDataFrame(geometry=[shp_transform(lambda x, y, z=None: T * (x, y), s) for s in joined], crs=3857).to_crs(2136)
WL = WL[WL.intersects(site)].reset_index(drop=True); WL['length_m'] = (WL.length * 0.3048).round(1)
# wall type: along a road edge (street frontage) or between plots
RDm = gpd.GeoSeries([shp_transform(lambda x, y, z=None: T * (x, y), p) for p in shapely.get_parts(shapely.geometry.MultiPolygon([shapely.geometry.Polygon(c[:, 0, :]) for c in cv2.findContours(road.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0] if len(c) >= 4]).buffer(0))], crs=3857).to_crs(2136).union_all()
WL['wall_type'] = ['Street frontage wall' if g.distance(RDm) < 8 else 'Plot boundary wall' for g in WL.geometry]
WL['wall_id'] = range(1, len(WL) + 1); WL = WL[['wall_id', 'wall_type', 'length_m', 'geometry']]
WL.to_file(D + 'Test5_Walls_final.shp')
print('walls', len(WL), WL['wall_type'].value_counts().to_dict(), 'total m', round(WL.length_m.sum()))
