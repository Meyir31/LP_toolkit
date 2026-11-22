import geopandas as gpd, rasterio, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
D = 'D:/Work/2026/Machine Learning/Test 5 outputs/'
r = rasterio.open('ml5/img_z19_3857.tif'); img = np.moveaxis(r.read(), 0, -1)[:, :, :3]; b = r.bounds
P = gpd.read_file(D + 'Test5_Footpaths_TRIAL_not_reliable.shp').to_crs(3857); C = gpd.read_file(D + 'Test5_footpath_candidates.shp').to_crs(3857)
RS = gpd.read_file(D + 'Test5_Road_surface.shp').to_crs(3857); S = gpd.read_file('D:/Work/2026/Machine Learning/Test 5.kml').to_crs(3857); c = S.geometry.iloc[0].centroid
fig, axs = plt.subplots(1, 3, figsize=(33, 11))
for k, ax in enumerate(axs):
    ax.imshow(img, extent=(b.left, b.right, b.bottom, b.top)); RS.boundary.plot(ax=ax, color='white', lw=1)
    if k == 0:
        C.plot(ax=ax, column='score', cmap='RdYlGn', vmin=0.1, vmax=0.7, lw=2, legend=True); ax.set_title('candidate segments by score (green = strong path evidence)', fontsize=14)
    else:
        P.plot(ax=ax, column='class', lw=3, legend=True, cmap='cool'); ax.set_title('kept footpaths', fontsize=14)
    if k < 2: ax.set_xlim(c.x - 80, c.x + 80); ax.set_ylim(c.y - 80, c.y + 80)
    else: x0, y0, x1, y1 = S.total_bounds; ax.set_xlim(x0 - 10, x1 + 10); ax.set_ylim(y0 - 10, y1 + 10); S.boundary.plot(ax=ax, color='orange', lw=2)
    ax.set_xticks([]); ax.set_yticks([])
plt.savefig(D + 'Test5_footpaths_preview.png', bbox_inches='tight', dpi=50)
