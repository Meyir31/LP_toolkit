"""Uncertain uses: white + 'Unconfirmed (verify)' (guess kept); sites: no double counting; multipart blocks."""
def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
# ---- land use per building: database residential is evidence too; every building gets use_conf ----
patch('ml5/plan_existing.py', [
 ("    if isinstance(udb, str) and udb != 'Residential': use.append(udb); how.append('building database occupancy'); continue",
  "    if isinstance(udb, str): use.append(udb); how.append('building database occupancy'); continue"),
 ("B['ex_use'] = use; B['use_source'] = how",
  "B['ex_use'] = use; B['use_source'] = how\nB['use_conf'] = ['confirmed' if str(h).startswith(('OSM tag', 'building database')) else 'unconfirmed' for h in how]       # rule-based guesses must be confirmed by the planner\nprint('uses confirmed by OSM / database:', int((B.use_conf == 'confirmed').sum()), 'of', len(B), '| to confirm:', int((B.use_conf != 'confirmed').sum()))"),
])
# ---- plots: unconfirmed main building -> plot left 'Unconfirmed (verify)', guess kept ----
patch('ml5/plots_v6.py', [
 ("""uses, mbs, nbs = [], [], []
for g in PL.geometry:
    inb = B[B.representative_point().within(g)]
    if len(inb):
        tg = inb[inb.use_source.astype(str).str.startswith('OSM tag') & (inb.ex_use != 'Residential')]
        j = tg.area.idxmax() if len(tg) else inb.area.idxmax(); uses.append(B.ex_use[j]); mbs.append(int(B.bld_id[j])); nbs.append(len(inb))
    else: uses.append('Open / yard (no building)'); mbs.append(None); nbs.append(0)
PL['ex_use'], PL['main_bld'], PL['n_bld'] = uses, mbs, nbs""",
 """uses, mbs, nbs, guess, conf = [], [], [], [], []
UC = B.use_conf if 'use_conf' in B else pd.Series('confirmed', index=B.index)
for g in PL.geometry:
    inb = B[B.representative_point().within(g)]
    if len(inb):
        tg = inb[inb.use_source.astype(str).str.startswith(('OSM tag', 'building database')) & (inb.ex_use != 'Residential')]
        j = tg.area.idxmax() if len(tg) else inb.area.idxmax(); mbs.append(int(B.bld_id[j])); nbs.append(len(inb)); guess.append(B.ex_use[j])
        if UC[j] == 'confirmed': uses.append(B.ex_use[j]); conf.append('confirmed')
        else: uses.append('Unconfirmed (verify)'); conf.append('to confirm')
    else: uses.append('Open / yard (no building)'); mbs.append(None); nbs.append(0); guess.append(''); conf.append('confirmed')
PL['ex_use'], PL['main_bld'], PL['n_bld'], PL['use_guess'], PL['use_conf'] = uses, mbs, nbs, guess, conf"""),
 ("print('block widths m', {int(i): round(bwidth(shapely.force_2d(g)) * FT) for i, g in zip(BLK.block_id, BLK.geometry)});",
  "print('block widths m', {int(i): round(bwidth(max(shapely.get_parts(shapely.force_2d(g)), key=lambda x: x.area)) * FT) for i, g in zip(BLK.block_id, BLK.geometry) if not g.is_empty});"),
 ("PL = PL[['plot_id', 'block_id', 'access', 'ex_use', 'n_bld', 'main_bld', 'area_m2', 'frontage_m', 'depth_m', 'coverage', 'geometry']];",
  "PL = PL[['plot_id', 'block_id', 'access', 'ex_use', 'use_conf', 'use_guess', 'n_bld', 'main_bld', 'area_m2', 'frontage_m', 'depth_m', 'coverage', 'geometry']];"),
])
# ---- build.py: site pieces taken once (overlapping OSM outlines), use + confirmation from the site ----
patch('toolkit_src/build.py', [
 ("""        for _, srow in SITES.iterrows():
            part = g_.intersection(srow.geometry.buffer(0))""",
  """        taken_ = None
        for _, srow in SITES.assign(_a=SITES.area).sort_values('_a', ascending=False).iterrows():     # larger sites first; overlaps counted once
            sg_ = srow.geometry.buffer(0) if taken_ is None else srow.geometry.buffer(0).difference(taken_)
            part = g_.intersection(sg_); taken_ = sg_ if taken_ is None else taken_.union(sg_)"""),
 ("    for i_ in hit: PL.at[i_, 'ex_use'] = sp[2]", "    for i_ in hit: PL.at[i_, 'ex_use'] = sp[2]; PL.at[i_, 'use_conf'] = 'confirmed'; PL.at[i_, 'use_guess'] = sp[2]"),
])
# ---- LUSPA palette: the 'unconfirmed' class ----
patch('toolkit_src/header.py', [
 ("    'VAC':  ('Open / yard, no building (not a zoning class)', '#FFFFFF', '#9E9E9E', None, '#9E9E9E'),",
  "    'VAC':  ('Open / yard, no building (not a zoning class)', '#FFFFFF', '#9E9E9E', None, '#9E9E9E'),\n    'UNC':  ('Use NOT CONFIRMED: please verify', '#FFFFFF', '#FF6D00', None, '#FF6D00'),"),
 ("'Agricultural': 'Ag', 'Open / yard (no building)': 'VAC'}", "'Agricultural': 'Ag', 'Open / yard (no building)': 'VAC', 'Unconfirmed (verify)': 'UNC', 'Utility': 'SU'}"),
 ("    for code in codes.unique():\n        sub = gdf[codes == code]; name, fill, pc, hatch, edge = LUSPA[code]; counts[code] = len(sub)\n        sub.plot(ax=ax, color=fill, ec=edge or ec, lw=lw if not edge else max(lw, 1.2))",
  "    for code in codes.unique():\n        sub = gdf[codes == code]; name, fill, pc, hatch, edge = LUSPA[code]; counts[code] = len(sub)\n        sub.plot(ax=ax, color=fill, ec=edge or ec, lw=lw if not edge else max(lw, 1.2), linestyle='--' if code == 'UNC' else '-')"),
 ("label=f'{code if code != \"VAC\" else \"\"}  {name}{suffix(code, counts[code])}'.strip()))",
  "label=f'{code if code not in (\"VAC\", \"UNC\") else \"\"}  {name}{suffix(code, counts[code])}'.strip()))"),
])
print('ok')
