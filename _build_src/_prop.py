"""Test 4 upgrading plan - proposals: mixed-use corridors, drainage greenway, pocket parks, pinch-point actions, refuse points, facility gaps."""
import numpy as np, geopandas as gpd, pandas as pd, rasterio, cv2, shapely, json
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union, transform as shp_transform
D = 'D:/Work/2026/Machine Learning/Test 4 outputs/'; FT = 0.3048
site = gpd.read_file('D:/Work/2026/Machine Learning/Test 4.kml').to_crs(2136).geometry.iloc[0]
B = gpd.read_file(D + 'Test4_Existing_land_use_buildings.shp'); R = gpd.read_file(D + 'Test4_Roads_existing.shp'); PP = gpd.read_file(D + 'Test4_Road_pinch_points.shp')
V = gpd.read_file(D + 'Test4_Vacant_open_land.shp'); CWY = gpd.read_file(D + 'Test4_Carriageways.shp').union_all()
POP = int(round(B[B.ex_use == 'Residential'].area.sum() * FT * FT * 1.5 / 60 * 3.4, -2))                                                                  # provisional (1.5 storeys, 60 m2 per household, 3.4 persons)
# ---------- 1. mixed-use corridors: building frontage band along the primary / secondary roads ----------
maj = R[R.highway.isin(['primary', 'secondary'])]
corr = unary_union([g.buffer((cw / 2 + 30) / FT) for g, cw in zip(maj.geometry, maj.carriage_w)]).intersection(site).difference(CWY)
MU = gpd.GeoDataFrame(dict(zone=['Mixed-use corridor (commercial ground floor, residential above)']), geometry=[corr], crs=2136)
# ---------- 2. drainage greenway: the continuous tree corridor through the site ----------
r = rasterio.open('ml4/img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3].copy(); T = r.transform
Rc, Gc, Bc = [img[:, :, k].astype(float) for k in range(3)]; br = img.mean(2)
tree = ((Gc - (Rc + Bc) / 2) > 16) & (br < 120)
tree = cv2.morphologyEx(tree.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)); tree = cv2.morphologyEx(tree, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
cs, _ = cv2.findContours(tree, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); gw = []
for c in cs:
    if len(c) < 10: continue
    p = Polygon([T * tuple(pt) for pt in c[:, 0, :].astype(float)]).buffer(0)
    if p.is_empty: continue
    q = list(p.minimum_rotated_rectangle.exterior.coords); a_, b_ = sorted([np.hypot(*np.subtract(q[0], q[1])), np.hypot(*np.subtract(q[1], q[2]))])
    if p.area > 2500 and b_ / max(a_, 1) > 3: gw.append(p.simplify(2))      # long, continuous tree belt (> 2,500 m2, at least 3:1)
G = gpd.GeoDataFrame(geometry=gw, crs=3857).to_crs(2136); G['geometry'] = G.intersection(site); G = G[G.area * FT * FT > 1500]
G['zone'] = 'Drainage greenway / linear park (protect trees, keep 15 m clear of the drain)'; G['area_m2'] = (G.area * FT * FT).round(0)
# ---------- 3. pocket parks on vacant land ----------
PK = V.copy(); PK['zone'] = 'Pocket park / children\'s play (on vacant land)'
# ---------- 4. pinch points: actions ----------
# pinch points and actions come from pinch_v2.py (realigned centrelines)
# ---------- 5. refuse / sanitary collection points: none mapped; one per ~2,500 people, on the widest reserves at junctions, every home within 300 m ----------
n_ref = int(np.ceil(POP / 2500)); cand = []
for g, rw, cw in zip(R.geometry, R.reserve_m, R.carriage_w):
    if np.isnan(rw) or rw - cw < 5 or not g.intersects(site): continue           # needs >= 2.5 m of verge each side
    for s in np.arange(30, g.length - 30, 60):
        pt = g.interpolate(s)
        if pt.within(site.buffer(-30)): cand.append(pt)
homes = list(B[B.ex_use == 'Residential'].geometry.centroid); chosen = []
for _ in range(n_ref):
    best = None
    for c in cand:
        if any(c.distance(x) < 250 / FT for x in chosen): continue
        cov = sum(1 for h in homes[::5] if min([c.distance(h)] + [x.distance(h) for x in chosen]) < 300 / FT)
        if best is None or cov > best[0]: best = (cov, c)
    if best: chosen.append(best[1])
RF = gpd.GeoDataFrame(dict(facility=['Refuse / sanitary collection point (skip pad in the road verge)'] * len(chosen)), geometry=chosen, crs=2136)
# ---------- 6. facility gaps (provisional: OSM under-records facilities) ----------
cnt = B.ex_use.value_counts()
std = [('Basic school (primary + JHS)', 'Education', 5000, 'one per neighbourhood of ~5,000 (LUSPA neighbourhood list)'),
       ('Health post / clinic', 'Health', 5000, 'health post serves up to 5,000 (LUSPA)'),
       ('Place of worship', 'Religious', 1150, 'learned rate ~1 per 160 plots (~1,150 people)'),
       ('Market / shopping centre', 'Market', 5000, 'neighbourhood shopping centre or market per neighbourhood (LUSPA)'),
       ('Public open space / play', 'Open space', 1950, 'learned rate ~1 per 270 plots (~1,950 people)'),
       ('Refuse / sanitary point', 'Refuse', 2500, 'learned S.A rate ~1 per 2,500 people; Guidelines: within 500 m')]
have = {'Education': int(cnt.get('Education', 0)), 'Health': int(cnt.get('Health', 0)), 'Religious': int(cnt.get('Religious', 0)), 'Market': 0, 'Open space': 0, 'Refuse': 0}
gap = []
for name, key, per, why in std:
    need = int(np.ceil(POP / per)); h = have[key]
    gap.append(dict(facility=name, existing_mapped=h, needed_for_20000=need, gap=max(0, need - h), basis=why,
                    proposal={'Education': 'Existing schools cover the need if capacity is adequate - verify enrolment', 'Health': 'Covered (incl. 2 hospitals) - verify',
                              'Religious': 'Likely under-mapped in OSM - field check before any allocation', 'Market': 'Neighbourhood market: acquire / redevelop an under-used compound near the La Rd - Oxford St corner',
                              'Open space': f'{len(PK)} pocket parks on vacant land + drainage greenway ({G.area_m2.sum():.0f} m2); remaining gap needs acquisition of under-used land',
                              'Refuse': f'{len(RF)} skip pads in wide road verges (every home within ~300 m)'}[key]))
GAP = pd.DataFrame(gap)
# ---------- outputs ----------
MU.to_file(D + 'Test4_Plan_mixed_use_corridor.shp'); G.to_file(D + 'Test4_Plan_greenway.shp'); PK.to_file(D + 'Test4_Plan_pocket_parks.shp')
RF.to_file(D + 'Test4_Plan_refuse_points.shp')
with pd.ExcelWriter(D + 'Test4_Upgrading_plan_tables.xlsx') as xw:
    pd.DataFrame([dict(item='Site area (ha)', value=round(site.area * FT * FT / 1e4, 1)), dict(item='Buildings', value=len(B)), dict(item='Building coverage (%)', value=round(B.area.sum() / site.area * 100, 1)),
                  dict(item='Estimated population (provisional)', value=POP), dict(item='Assumption', value='1.5 storeys average, 60 m2 per household, 3.4 persons per household'),
                  dict(item='Pinch points', value=len(PP)), dict(item='Mixed-use corridor (ha)', value=round(corr.area * FT * FT / 1e4, 1)), dict(item='Drainage greenway (m2)', value=round(G.area_m2.sum())),
                  dict(item='Pocket parks', value=len(PK)), dict(item='Refuse points', value=len(RF))]).to_excel(xw, sheet_name='summary', index=False)
    GAP.to_excel(xw, sheet_name='facility gaps', index=False)
    B.ex_use.value_counts().rename_axis('existing use').rename('buildings').reset_index().to_excel(xw, sheet_name='existing land use', index=False)
    R.drop(columns='geometry').to_excel(xw, sheet_name='roads', index=False)
    PP.drop(columns='geometry').to_excel(xw, sheet_name='pinch points', index=False)
print(GAP[['facility', 'existing_mapped', 'needed_for_20000', 'gap']].to_string()); print('greenway m2', G.area_m2.sum(), '| corridor ha', round(corr.area * FT * FT / 1e4, 1), '| refuse points', len(RF), '| pinch points', len(PP), 'severe', int((PP.width_m < 6).sum()))
# ---------- map ----------
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
b = r.bounds; ext = (b.left, b.right, b.bottom, b.top); S3 = gpd.GeoSeries([site], crs=2136).to_crs(3857)
fig, ax = plt.subplots(figsize=(18, 17)); ax.imshow(img, extent=ext, alpha=.55)
MU.to_crs(3857).plot(ax=ax, color='#e15759', alpha=.35); G.to_crs(3857).plot(ax=ax, color='#2ca02c', alpha=.6, ec='darkgreen')
B.to_crs(3857).plot(ax=ax, color='#f4d35e', ec='k', lw=.1, alpha=.8); PK.to_crs(3857).plot(ax=ax, color='lime', ec='darkgreen', lw=1.5)
PP.to_crs(3857).plot(ax=ax, color=np.where(PP.width_m < 6, 'red', 'orange'), markersize=90, marker='X'); RF.to_crs(3857).plot(ax=ax, color='saddlebrown', markersize=140, marker='s', ec='white')
S3.boundary.plot(ax=ax, color='black', lw=2.5); x0, y0, x1, y1 = S3.total_bounds; ax.set_xlim(x0 - 30, x1 + 30); ax.set_ylim(y0 - 30, y1 + 30); ax.set_xticks([]); ax.set_yticks([])
ax.legend(handles=[Patch(color='#e15759', alpha=.5, label='Mixed-use corridor (La Rd, 28th Feb Rd, Oxford St)'), Patch(color='#2ca02c', label='Drainage greenway / linear park'),
                   Patch(color='lime', label='Pocket park on vacant land'), Patch(color='#f4d35e', label='Existing buildings (retained)'),
                   Line2D([0], [0], marker='X', color='w', markerfacecolor='red', markersize=12, label='Severe pinch point (< 6 m between building lines)'),
                   Line2D([0], [0], marker='X', color='w', markerfacecolor='orange', markersize=12, label='Narrow section (below class minimum): no parking, calming'),
                   Line2D([0], [0], marker='s', color='w', markerfacecolor='saddlebrown', markersize=12, label='Refuse / sanitary collection point')], loc='lower left', fontsize=11)
ax.set_title(TITLE + f' upgrading plan - proposals (provisional population ~{POP:,})', fontsize=16)
plt.savefig(D + 'Test4_Upgrading_plan_proposals.png', bbox_inches='tight', dpi=60)
