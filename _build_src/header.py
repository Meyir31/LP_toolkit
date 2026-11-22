#!/usr/bin/env python
"""LP Toolkit: one script for local plan preparation (existing-situation mapping of built-up areas and new layouts).

Usage (from the LP_Toolkit folder, with its own Python: run.bat ... or env\\Scripts\\python.exe lp_toolkit.py ...):

  python lp_toolkit.py existing --site "D:/.../Test 6.kml" --name "Test 6" [--title "Test 6 (Teshie)"] [--out DIR]
                                [--profile auto|planned|compact] [--from STAGE] [--only STAGE[,STAGE]] [--with footpaths,proposals]
  python lp_toolkit.py design   --site SITE.kml --name NAME --roads ROADS.shp|auto|draft [--existing ROADS.shp] [--stream STREAM.shp --stream-buffer 100]
                                [--out DIR] [--from STAGE] [--only STAGE[,STAGE]]
  python lp_toolkit.py db       --site SITE.kml [--out FILE.gpkg]        export the building database for a site
  python lp_toolkit.py guide                                              print the guide and write LP_Toolkit_Guide.md
  python lp_toolkit.py stages                                             list the stages

Existing stages: fetch, sam, digitize, compare, clean, database, roads, landuse, reserves, trees, blocks, plots, map
                 (+ optional footpaths, proposals with --with)
Design stages:   site, roads, subdivide, landuse, audit

Outputs go to <site folder>/<name> outputs/ (working files in its _work/ sub-folder). Stages already done can be re-run alone.
The full guide (processes, rules, standards, data sources, lessons) is in GUIDE below.
"""
import os, sys, re, json, math, glob, time, pickle, shutil, argparse, warnings
import numpy as np
warnings.filterwarnings('ignore')
TOOLKIT = os.path.dirname(os.path.abspath(__file__))
SAM_CKPT_DEFAULT = os.path.join(TOOLKIT, 'models', 'sam_vit_b_01ec64.pth').replace('\\', '/')
MS_CACHE = os.path.join(TOOLKIT, 'cache', 'ms').replace('\\', '/')
OBM_ROOT = 'D:/Work/2026/Data'                       # building database (see guide section 2)
USER_AGENT = 'gis-planning-client'                   # never send personal details to outside services
FT = 0.3048
# plot subdivision profiles for existing areas (guide section 4)
PROFILES = {
    'planned': dict(wmin=12, wmax=25, single_row=45, halve_depth=65, recut_area=1000, recut_depth=50),
    'compact': dict(wmin=9, wmax=18, single_row=30, halve_depth=40, recut_area=500, recut_depth=36),
}

# =====================================================================================================================
# LUSPA colour codes: Revised Zoning Guidelines and Planning Standards (2025), Table 1 (broad uses) and Table 2 (specific uses)
# code: (name, fill, pattern colour, matplotlib hatch, edge colour)  - pattern / hatch only where the Guidelines specify one
# =====================================================================================================================
LUSPA = {
    'Re':   ('Residential', '#DC7C24', None, None, None),
    'Re A': ('Residential Zone A', '#CC7722', None, None, None),
    'Re B': ('Residential Zone B', '#E5AA70', None, None, None),
    'Re C': ('Residential Zone C', '#BB8855', None, None, None),
    'Re D': ('Residential Zone D', '#98623C', None, None, None),
    'Com':  ('Commercial', '#73B2FF', None, None, None),
    'CBD':  ('Central Business District', '#2E4DA7', None, None, None),
    'BM':   ('Mixed Business / Residential', '#73B2FF', '#FFAA57', '//', None),
    'BI':   ('Informal Business', '#73B2FF', '#000000', '..', None),
    'TL':   ('Transportation and Logistics', '#D6D6D6', '#000000', '++', None),
    'CC':   ('Civic and Culture', '#FF7F7F', None, None, None),
    'PW':   ('Place of Worship', '#FF7F7F', '#000000', '^^', None),
    'H':    ('Health', '#FF0000', None, None, None),
    'BG':   ('Government Business', '#FF7F7F', '#000000', '..', None),
    'T':    ('Tourist / Heritage', '#FF0080', None, None, None),
    'SU':   ('Special / Utility', '#FF7F7F', '#000000', '//', None),
    'SZ':   ('Security', '#FF7F7F', '#000000', '--', None),
    'InD':  ('Industrial', '#F4AFF4', None, None, None),
    'LI':   ('Light Industrial', '#E8BEFF', None, None, None),
    'IS':   ('Service Industry', '#EE82EE', None, None, None),
    'Ed':   ('Educational', '#FFFF00', None, None, '#C00000'),
    'Ed P': ('Education Zone A: Pre-school and Basic School', '#FFFF00', '#000000', '..', '#C00000'),
    'Ed S': ('Education Zone B: Senior High and TVET', '#FFFF00', '#000000', '||', '#C00000'),
    'Ed T': ('Education Zone C: Tertiary', '#FFFF00', '#000000', '--', '#C00000'),
    'PS':   ('Public Space', '#00FF00', None, None, None),
    'CA':   ('Conservation', '#32CD32', None, None, None),
    'CZ':   ('Protected Coastal / Waterfront', '#20B2AA', None, None, None),
    'Ag':   ('Agriculture', '#ADFF2F', None, None, None),
    'VAC':  ('Open / yard, no building (not a zoning class)', '#FFFFFF', '#9E9E9E', None, '#9E9E9E'),
    'UNC':  ('Use NOT CONFIRMED: please verify', '#FFFFFF', '#FF6D00', None, '#FF6D00'),
}
EXIST_LUSPA = {'Residential': 'Re', 'Mixed use (shop + residence)': 'BM', 'Commercial / mixed use': 'BM', 'Commercial': 'Com', 'Commercial (hotel)': 'Com',
               'Commercial (fuel)': 'Com', 'Commercial (entertainment)': 'Com', 'Commercial (wholesale / storage)': 'Com', 'Commercial (parking)': 'TL', 'Office': 'Com',
               'Market': 'Com', 'Transport terminal': 'TL', 'Health': 'H', 'Education': 'Ed', 'Religious': 'PW', 'Religious / assembly': 'PW', 'Civic': 'CC',
               'Institutional / large commercial (verify)': 'CC', 'Recreation': 'PS', 'Industrial': 'InD', 'Mixed use (industrial + commercial)': 'IS',
               'Mixed use (commercial + industrial)': 'IS', 'Agricultural': 'Ag', 'Open / yard (no building)': 'VAC', 'Unconfirmed (verify)': 'UNC', 'Utility': 'SU'}
DESIGN_LUSPA = {'RE': 'Re B', 'RA': 'Re A', 'MU': 'BM', 'BM': 'BM', 'Com A': 'Com', 'CIV': 'CC', 'TR': 'TL', 'PW': 'PW', 'H Po': 'H', 'Ed P': 'Ed P',
                'POS': 'PS', 'GRN': 'CA', 'SU': 'SU', '': 'VAC'}
def luspa_draw(ax, gdf, col, mapping, lw=.5, ec='#222'):
    """fill each feature with its LUSPA colour and pattern; returns {code: count}"""
    import matplotlib as mpl
    counts = {}
    codes = gdf[col].map(lambda u: mapping.get(u, 'VAC'))
    for code in codes.unique():
        sub = gdf[codes == code]; name, fill, pc, hatch, edge = LUSPA[code]; counts[code] = len(sub)
        sub.plot(ax=ax, color=fill, ec=edge or ec, lw=lw if not edge else max(lw, 1.2), linestyle='--' if code == 'UNC' else '-')
        if hatch == '^^':                                          # 'black triangular pattern fill' (no triangle hatch in matplotlib): small triangles on a grid
            import shapely
            from shapely.geometry import Point as _Pt
            for g in sub.geometry:
                x0, y0, x1, y1 = g.bounds; st = 22.0
                pts = [(x, y + (st / 2 if int((x - x0) / st) % 2 else 0)) for x in np.arange(x0 + st / 2, x1, st) for y in np.arange(y0 + st / 2, y1, st)]
                pts = [q for q in pts if g.contains(_Pt(q))]
                if pts: ax.scatter([q[0] for q in pts], [q[1] for q in pts], marker='^', s=9, c=pc, linewidths=0, zorder=3)
        elif hatch:
            with mpl.rc_context({'hatch.color': pc, 'hatch.linewidth': 1.4 if pc not in (None, '#000000') else .8}): sub.plot(ax=ax, facecolor='none', ec=pc, lw=0, hatch=hatch * 2)
    return counts
def luspa_handles(counts, suffix=lambda code, n: f' ({n})'):
    from matplotlib.patches import Patch
    import matplotlib as mpl
    hs = []
    for code in [c for c in LUSPA if c in counts]:
        name, fill, pc, hatch, edge = LUSPA[code]
        with mpl.rc_context({'hatch.color': pc or '#000000', 'hatch.linewidth': 1.4 if pc not in (None, '#000000') else .8}): hs.append(Patch(facecolor=fill, edgecolor=edge or pc or '#555555', hatch=('**' if hatch == '^^' else hatch * 2 if hatch else None), lw=1.2 if edge else .8, label=f'{code if code not in ("VAC", "UNC") else ""}  {name}{suffix(code, counts[code])}'.strip()))
    return hs

PROFILE_THRESHOLD_M2 = 70                            # median image-digitized building below this -> compact
PROFILE_THRESHOLD_DB_M2 = 56                         # same test on database / OSM footprints (they are drawn tighter: Osu 61, La 51)
CUR_STAGE = {'name': None}
def progress(pct, note=''):
    """progress line for the web app: '@@progress <stage> <percent> <note>'"""
    print(f"@@progress {CUR_STAGE['name']} {max(0, min(100, pct)):.0f} {note}", flush=True)

# =====================================================================================================================
# Shared helpers: mask features / classification / outlines (digitizing), walls, building database, road surface
# =====================================================================================================================
