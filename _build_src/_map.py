import geopandas as gpd, numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Patch
D = 'D:/Work/2026/Machine Learning/Test 5 outputs/'; FT = 0.3048
PL = gpd.read_file(D + 'Test5_Plots_existing.shp').to_crs(3857); BL = gpd.read_file(D + 'Test5_Blocks_existing.shp').to_crs(3857); RS = gpd.read_file(D + 'Test5_Road_surface.shp').to_crs(3857)
B = gpd.read_file(D + 'Test5_Existing_land_use_buildings.shp').to_crs(3857); TB = gpd.read_file(D + 'Test5_Tree_belt_existing.shp').to_crs(3857); site = gpd.read_file('D:/Work/2026/Machine Learning/Test 5.kml').to_crs(3857)
COL = {'Residential': '#f6e27f', 'Mixed use (shop + residence)': '#f4a259', 'Commercial / mixed use': '#e86a5a', 'Commercial': '#d62828', 'Commercial (hotel)': '#a23b72', 'Commercial (fuel)': '#6c757d',
       'Office': '#7b2cbf', 'Health': '#ff70a6', 'Education': '#1e88e5', 'Religious': '#8d6e63', 'Civic': '#00acc1', 'Market': '#ff8f00', 'Transport terminal': '#455a64', 'Institutional / large commercial (verify)': '#43a047', 'Open / yard (no building)': '#e8f5e9'}
fig, ax = plt.subplots(figsize=(19, 19)); ax.set_facecolor('white')
COUNTS = luspa_draw(ax, PL, 'ex_use', EXIST_LUSPA, lw=.7)
INT = PL[PL.access.str.startswith('Interior')]; INT.plot(ax=ax, color='none', ec='#555', lw=0, hatch='///')
TB.plot(ax=ax, color=LUSPA['CA'][1]); RS.plot(ax=ax, color='#c8c8c8'); B.plot(ax=ax, color='none', ec='#1f5fd1', lw=.45); BL.boundary.plot(ax=ax, color='black', lw=1.1); site.boundary.plot(ax=ax, color='red', lw=2.2)
for g, i in zip(BL.geometry, BL.block_id): c = g.representative_point(); ax.text(c.x, c.y, str(i), fontsize=8, ha='center', weight='bold', color='navy', bbox=dict(fc='white', ec='none', alpha=.6, pad=.5))
x0, y0, x1, y1 = site.total_bounds; ax.set_xlim(x0 - 20, x1 + 20); ax.set_ylim(y0 - 20, y1 + 20); ax.set_xticks([]); ax.set_yticks([])
tb_ac = TB.to_crs(2136).area.sum() / 43560
ax.legend(handles=luspa_handles(COUNTS, lambda code, n: f' ({n} plots)') +
          ([Patch(color=LUSPA['CA'][1], label=f'CA  Conservation: tree belt / drain corridor ({tb_ac:.1f} ac)')] if tb_ac > 0.05 else []) + [Patch(color='#c8c8c8', label='Roads'),
           Patch(fc='white', ec='#555', hatch='///', label=f'Interior plot: access lane not mapped, verify ({len(INT)})'),
           Patch(fc='none', ec='black', label='Block (number)'), Patch(fc='none', ec='#1f5fd1', lw=1.5, label='Building footprint'), Patch(fc='none', ec='#222', label='Plot boundary')], loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=11, framealpha=.95, borderaxespad=0)
ax.set_title(TITLE + f' - existing land use (LUSPA colour codes): {len(BL)} blocks, {len(PL)} plots', fontsize=16)
try: plt.savefig(D + 'Test5_Existing_land_use_map.png', bbox_inches='tight', dpi=70)
except OSError: plt.savefig(D + 'Test5_Existing_land_use_map.png'.replace('.png', '_v2.png'), bbox_inches='tight', dpi=70); print('map file open elsewhere - saved as _v2')
P2 = gpd.read_file(D + 'Test5_Plots_existing.shp'); site2 = gpd.read_file('D:/Work/2026/Machine Learning/Test 5.kml').to_crs(2136).geometry.iloc[0]
t = P2.groupby('ex_use').agg(plots=('plot_id', 'size'), area_m2=('area_m2', 'sum')).sort_values('area_m2', ascending=False)
t.loc['Tree belt / drain corridor'] = [0, round(TB.to_crs(2136).area.sum() * FT * FT)]; t.loc['Roads'] = [0, round(gpd.read_file(D + 'Test5_Road_surface.shp').area.sum() * FT * FT)]
t['area_ha'] = (t.area_m2 / 1e4).round(2); t['share_%'] = (t.area_m2 / (site2.area * FT * FT) * 100).round(1)
with pd.ExcelWriter(D + 'Test5_Existing_land_use_tables.xlsx') as xw:
    t.reset_index().rename(columns={'ex_use': 'land use'}).to_excel(xw, sheet_name='land use areas', index=False)
    gpd.read_file(D + 'Test5_Blocks_existing.shp').drop(columns='geometry').to_excel(xw, sheet_name='blocks', index=False)
    P2.drop(columns='geometry').to_excel(xw, sheet_name='plots', index=False)
print(t.to_string())
