def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:90]); s = s.replace(a, b, 1)
    open(p, 'w', encoding='utf-8').write(s)
patch('toolkit_src/build.py', [("    s = re.sub(r\"^n0 = len\\(pieces\\)\", \"n0 = len(pieces)\", s, flags=re.M)\n    return s",
'''    s = re.sub(r"^n0 = len\\(pieces\\)", "n0 = len(pieces)", s, flags=re.M)
    # ---- re-demarcation of selected blocks, row / frontage options, rear line from image evidence ----
    s = must(s, "WMIN, WMAX, STEP = PROF['wmin'] / FT, PROF['wmax'] / FT, 1 / FT", """WMIN, WMAX, STEP = float(ctx.get('wmin_m') or PROF['wmin']) / FT, float(ctx.get('wmax_m') or PROF['wmax']) / FT, 1 / FT
REDO = [int(x) for x in (ctx.get('redo_blocks') or [])]
if REDO: BLK = BLK[BLK.block_id.isin(REDO)].reset_index(drop=True); print(f'   re-demarcating blocks {REDO}', flush=True)
WT = shapely.STRtree(list(W.geometry)) if len(W) else None
def split_cost(ln, BUb, off):
    \\"\\"\\"cost of a rear (row) line: building length it cuts, minus walls / fences running along it (seen on the image), mild pull to the middle\\"\\"\\"
    if ctx.get('split') == 'middle': return abs(off)
    c = (ln.intersection(BUb).length if BUb is not None else 0) + abs(off) * 0.05
    if WT is not None and not ln.is_empty:
        z = ln.buffer(1.5 / FT); parts = [g for g in shapely.get_parts(ln) if g.geom_type == 'LineString']
        if parts:
            d = unit(np.subtract(parts[0].coords[-1], parts[0].coords[0])[:2])
            for k in WT.query(z):
                w = W.geometry.iloc[k]; dw = unit(np.subtract(w.coords[-1], w.coords[0])[:2])
                if abs(float(d @ dw)) > 0.9: c -= 1.0 * w.intersection(z).length
    return c
def save_plots(PL):
    if REDO and os.path.exists(D + PFX + 'Plots_existing.shp'):
        old = gpd.read_file(D + PFX + 'Plots_existing.shp'); old = old[~old.block_id.isin(REDO)]
        PL = gpd.GeoDataFrame(pd.concat([old, PL], ignore_index=True), geometry='geometry', crs=2136)
    PL.to_file(D + PFX + 'Plots_existing.shp')""", 1, 'plots')
    s = must(s, "if depth < PROF['single_row'] / FT: rows = [blk]", "if ctx.get('rows') == '1' or (ctx.get('rows') != '2' and depth < PROF['single_row'] / FT): rows = [blk]", None, 'plots')
    s = must(s, "            cst = (ln.intersection(BUb).length if BUb is not None else 0) + abs(off) * 0.05", "            cst = split_cost(ln, BUb, off)", None, 'plots')
    s = must(s, "    rows = two_side_rows(blk) if width >= 40 / FT else None", "    rows = None if ctx.get('rows') == '1' else (two_side_rows(blk) if (width >= 40 / FT or ctx.get('rows') == '2') else None)", 1, 'plots')
    s = must(s, "    if not rows: rows = [[blk, max(frontage_pieces(blk), key=lambda f: f.length)]] if width < 40 / FT else rows_by_frontage(blk)", "    if not rows: rows = [[blk, max(frontage_pieces(blk), key=lambda f: f.length)]] if (width < 40 / FT or ctx.get('rows') == '1') else rows_by_frontage(blk)", 1, 'plots')
    s = must(s, "PL.to_file(D + PFX + 'Plots_existing.shp');", "save_plots(PL);", 1, 'plots')
    return s''')])
patch('toolkit_src/cli.py', [
 ("            p.add_argument('--buildings', choices=['fast', 'full'], default='fast', help='fast: OSM + building database (minutes); full: + image detection with SAM (hours)')",
  """            p.add_argument('--buildings', choices=['fast', 'full'], default='fast', help='fast: OSM + building database (minutes); full: + image detection with SAM (hours)')
            p.add_argument('--blocks', help='re-demarcate only these block ids (comma list) with --only plots,map')
            p.add_argument('--rows', choices=['auto', '1', '2'], default='auto'); p.add_argument('--wmin', type=float, help='min plot frontage m'); p.add_argument('--wmax', type=float, help='max plot frontage m')
            p.add_argument('--split', choices=['evidence', 'middle'], default='evidence', help='rear line: follow walls / gaps between buildings on the image, or the exact middle')"""),
 ("TITLE=a.title or name, buildings=getattr(a, 'buildings', 'fast'),",
  "TITLE=a.title or name, buildings=getattr(a, 'buildings', 'fast'), redo_blocks=[x for x in (getattr(a, 'blocks', None) or '').split(',') if x.strip()], rows=getattr(a, 'rows', 'auto'), wmin_m=getattr(a, 'wmin', None), wmax_m=getattr(a, 'wmax', None), split=getattr(a, 'split', 'evidence'),"),
])
print('ok')
