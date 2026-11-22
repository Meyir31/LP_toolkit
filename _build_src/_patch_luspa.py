"""LUSPA colour codes (Revised Zoning Guidelines and Planning Standards 2025, Tables 1 and 2) for every land use map."""
def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
PALETTE = r'''
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
}
EXIST_LUSPA = {'Residential': 'Re', 'Mixed use (shop + residence)': 'BM', 'Commercial / mixed use': 'BM', 'Commercial': 'Com', 'Commercial (hotel)': 'Com',
               'Commercial (fuel)': 'Com', 'Commercial (entertainment)': 'Com', 'Commercial (wholesale / storage)': 'Com', 'Commercial (parking)': 'TL', 'Office': 'Com',
               'Market': 'Com', 'Transport terminal': 'TL', 'Health': 'H', 'Education': 'Ed', 'Religious': 'PW', 'Religious / assembly': 'PW', 'Civic': 'CC',
               'Institutional / large commercial (verify)': 'CC', 'Recreation': 'PS', 'Industrial': 'InD', 'Mixed use (industrial + commercial)': 'IS',
               'Mixed use (commercial + industrial)': 'IS', 'Agricultural': 'Ag', 'Open / yard (no building)': 'VAC'}
DESIGN_LUSPA = {'RE': 'Re B', 'RA': 'Re A', 'MU': 'BM', 'BM': 'BM', 'Com A': 'Com', 'CIV': 'CC', 'TR': 'TL', 'PW': 'PW', 'H Po': 'H', 'Ed P': 'Ed P',
                'POS': 'PS', 'GRN': 'CA', 'SU': 'SU', '': 'VAC'}
def luspa_draw(ax, gdf, col, mapping, lw=.5, ec='#222'):
    """fill each feature with its LUSPA colour and pattern; returns {code: count}"""
    import matplotlib as mpl
    counts = {}
    codes = gdf[col].map(lambda u: mapping.get(u, 'VAC'))
    for code in codes.unique():
        sub = gdf[codes == code]; name, fill, pc, hatch, edge = LUSPA[code]; counts[code] = len(sub)
        sub.plot(ax=ax, color=fill, ec=edge or ec, lw=lw if not edge else max(lw, 1.2))
        if hatch:
            with mpl.rc_context({'hatch.color': pc, 'hatch.linewidth': .8}): sub.plot(ax=ax, facecolor='none', ec=pc, lw=0, hatch=hatch * 2)
    return counts
def luspa_handles(counts, suffix=lambda code, n: f' ({n})'):
    from matplotlib.patches import Patch
    import matplotlib as mpl
    hs = []
    for code in [c for c in LUSPA if c in counts]:
        name, fill, pc, hatch, edge = LUSPA[code]
        with mpl.rc_context({'hatch.color': pc or '#000000'}): hs.append(Patch(facecolor=fill, edgecolor=edge or pc or '#555555', hatch=(hatch * 2 if hatch else None), lw=1.2 if edge else .8, label=f'{code if code != "VAC" else ""}  {name}{suffix(code, counts[code])}'.strip()))
    return hs
'''
patch('toolkit_src/header.py', [("PROFILE_THRESHOLD_M2 = 70 ", PALETTE + "\nPROFILE_THRESHOLD_M2 = 70 ")])
# existing-situation land use map
s = open('ml5/landuse_map.py', encoding='utf-8').read()
a0 = s.index("fig, ax = plt.subplots(figsize=(19, 19)); ax.set_facecolor('white')"); a1 = s.index("INT = PL[PL.access.str.startswith('Interior')]")
s = s[:a0] + "fig, ax = plt.subplots(figsize=(19, 19)); ax.set_facecolor('white')\nCOUNTS = luspa_draw(ax, PL, 'ex_use', EXIST_LUSPA, lw=.7)\n" + s[a1:]
s = s.replace("TB.plot(ax=ax, color='#2e7d32');", "TB.plot(ax=ax, color=LUSPA['CA'][1]);")
a0 = s.index("ax.legend(handles=[Patch(color=c, label=f'{k} ({(PL.ex_use == k).sum()} plots)') for k, c in COL.items() if (PL.ex_use == k).any()] +")
a1 = s.index("Patch(color='#c8c8c8', label='Roads'),", a0)
s = s[:a0] + "ax.legend(handles=luspa_handles(COUNTS, lambda code, n: f' ({n} plots)') +\n          ([Patch(color=LUSPA['CA'][1], label=f'CA  Conservation: tree belt / drain corridor ({tb_ac:.1f} ac)')] if tb_ac > 0.05 else []) + [" + s[a1:]
s = s.replace("ax.set_title(f'Test 5 (La) - existing land use:", "ax.set_title(f'Test 5 (La) - existing land use (LUSPA colour codes):")
open('ml5/landuse_map.py', 'w', encoding='utf-8').write(s)
# design land use map
s = open('ml3/allocate_t3.py', encoding='utf-8').read()
a = "R.plot(ax=ax, color=[COL[u] for u in R.use], ec='k', lw=.5); P.plot(ax=ax, color=[COL[u] for u in P.use], ec='k', lw=.4)"
assert a in s
s = s.replace(a, "CNT = luspa_draw(ax, R, 'use', DESIGN_LUSPA, lw=.5, ec='k'); C2 = luspa_draw(ax, P, 'use', DESIGN_LUSPA, lw=.4, ec='k')\nfor k_, v_ in C2.items(): CNT[k_] = CNT.get(k_, 0) + v_")
a0 = s.index("ax.legend(handles=[Patch(color=v, label=k) for k, v in [('Residential 70 x 100 (80 on major roads)', COL['RE'])")
a1 = s.index("loc='lower left', fontsize=9)", a0) + len("loc='lower left', fontsize=9)")
s = s[:a0] + "ax.legend(handles=luspa_handles(CNT) + [Patch(color='#2e8b57', label='Stream reserve (wooded)'), Patch(color='#8c8c8c', label='Main / existing roads'), Patch(color='#f5c242', label='40 ft collector'), Patch(color='#e6e6e6', label='30 ft local road')], loc='lower left', fontsize=9, title='LUSPA colour codes (Zoning Guidelines 2025)')" + s[a1:]
open('ml3/allocate_t3.py', 'w', encoding='utf-8').write(s)
print('ok')
