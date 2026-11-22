p = 'toolkit_src/autoroads.py'; s = open(p, encoding='utf-8').read()
helpers = '''
PATTERNS = {'grid': 'Grid iron', 'curvilinear': 'Curvilinear (follows the contours)', 'ringband': 'Ring and band (perimeter loop + inner grid)'}
def _chaikin(coords, it=2):
    c = np.asarray(coords, float)[:, :2]
    for _ in range(it):
        if len(c) < 3: break
        q = 0.75 * c[:-1] + 0.25 * c[1:]; r = 0.25 * c[:-1] + 0.75 * c[1:]
        c = np.vstack([c[:1], np.column_stack([q, r]).reshape(-1, 2), c[-1:]])
    return [tuple(x) for x in c]
def _extend(l, L=3000):
    from shapely.geometry import LineString
    c = np.array(l.coords)[:, :2]; d0 = _u(c[0] - c[1]); d1 = _u(c[-1] - c[-2])
    return LineString([tuple(c[0] + d0 * L)] + [tuple(x) for x in c] + [tuple(c[-1] + d1 * L)])
def _curvi_lines(sec, base, phase):
    """nested parallel curves of `base` (rows) + normals to it (cross roads): normals of a curve stay square to all its parallels"""
    import shapely
    from shapely.geometry import LineString
    B, Lr, BL = AUTO['band'], AUTO['local'], AUTO['block_len']
    step_rows, step_cross = B + Lr, BL + Lr
    b = LineString(_chaikin(base.simplify(30).coords, 3)); b = _extend(b, 2500)
    P = np.array(sec.exterior.coords)[:, :2]; span = max(np.ptp(P[:, 0]), np.ptp(P[:, 1])) + 500
    rows = []; k0 = int(span / step_rows) + 1
    for k in range(-k0, k0 + 1):
        d = phase + k * step_rows
        try: o = b.offset_curve(d, join_style=1) if abs(d) > 1 else b
        except Exception: continue
        for q in shapely.get_parts(o.intersection(sec)):
            if q.geom_type == 'LineString' and q.length > AUTO['min_seg']: rows.append(LineString(_chaikin(q.simplify(10).coords, 1)))
    crosses = []; bc = b.intersection(sec.buffer(400)); parts = [x for x in shapely.get_parts(bc) if x.geom_type == 'LineString']
    if parts:
        bc = max(parts, key=lambda x: x.length); s0 = (phase * 2.3) % step_cross
        for s_ in np.arange(s0, bc.length, step_cross):
            if s_ < 150 or bc.length - s_ < 150: continue
            p = np.array(bc.interpolate(s_).coords[0])[:2]; t = _tangent(bc, s_, 40); n = np.array([-t[1], t[0]])
            for q in shapely.get_parts(_long_line(p, n, span).intersection(sec)):
                if q.geom_type == 'LineString' and q.length > AUTO['min_seg']: crosses.append(q)
    return rows, crosses
def _ringband_lines(sec, S, R, u, ref, phase):
    """ring road 200 ft + half a road inside the road edges (100 ft inside the site boundary), rounded corners; inner grid; cross roads run through the band to the outer roads"""
    import shapely
    from shapely.ops import unary_union
    from shapely.geometry import LineString
    B, Lr = AUTO['band'], AUTO['local']
    ed = _road_edges(sec, R); redges = unary_union([e for e, w in ed]) if ed else None
    bnd = sec.exterior.intersection(S.exterior.buffer(3))
    core = sec
    if redges is not None and not redges.is_empty: core = core.difference(redges.buffer(B + Lr / 2))
    if not bnd.is_empty: core = core.difference(bnd.buffer(100 + Lr / 2))
    core = core.buffer(-80).buffer(80)                                    # rounded ring corners
    parts = [c for c in shapely.get_parts(core) if c.geom_type == 'Polygon' and c.area > 2 * 43560]
    if not parts: return None
    rings = [LineString(c.exterior.simplify(5).coords) for c in parts]
    rows, crosses = _grid_lines(sec, u, ref, phase, far_is_road=False)
    inner = unary_union([c.buffer(-(B / 2)) for c in parts])
    rows = [q for r_ in rows for q in shapely.get_parts(r_.intersection(inner)) if q.geom_type == 'LineString' and q.length > AUTO['min_seg']]
    open_ = sec.difference(bnd.buffer(100 + Lr)) if not bnd.is_empty else sec      # cross roads stop at the ring on the site-boundary side
    U = unary_union(parts)
    crosses = [q for c_ in crosses for q in shapely.get_parts(c_.intersection(open_)) if q.geom_type == 'LineString' and q.length > AUTO['min_seg'] and q.intersects(U)]
    return rings + rows, crosses
'''
a = "def auto_roads(S, existing, stream_poly=None, buildings=None, log=print, terrain=None):"
assert a in s
s = s.replace(a, helpers + "\ndef auto_roads(S, existing, stream_poly=None, buildings=None, log=print, terrain=None, pattern='grid'):")
a = "    def contour_dir(self, poly):"
assert a in s
s = s.replace(a, '''    def contour_through(self, poly):
        """longest contour piece inside the parcel at its median elevation"""
        from rasterio import features as rfeat
        from skimage.measure import find_contours
        from shapely.geometry import LineString
        import shapely
        m = rfeat.rasterize([poly], out_shape=self.z.shape, transform=self.T).astype(bool); zz = self.z[m]
        if zz.size < 10 or np.nanmax(zz) - np.nanmin(zz) < 2: return None
        best = None
        for c in find_contours(np.nan_to_num(self.z, nan=-9999), float(np.nanmedian(zz))):
            if len(c) < 3: continue
            l = LineString([self.T * (cc[1] + .5, cc[0] + .5) for cc in c]).intersection(poly)
            for q in shapely.get_parts(l):
                if q.geom_type == 'LineString' and (best is None or q.length > best.length): best = q
        return best if best is not None and best.length > 300 else None
    def contour_dir(self, poly):''')
a = """        best = None
        for u, ref, w in cands:
            for phase in np.linspace(0, AUTO['block_len'] + AUTO['local'], 7)[:-1]:
                rows, crosses = _grid_lines(sec, u, ref, phase, far_is_road=False)
                sc, _ = _score(sec, rows + crosses, bld, None)
                sc += w * 50                                             # prefer running along the highest-order road
                if terrain is not None: sc -= (400 if hilly else 150) * terrain.steep_len(rows + crosses)      # road length steeper than 18%
                if best is None or sc > best[0]: best = (sc, rows, crosses)"""
assert a in s
s = s.replace(a, """        best = None
        def options():
            if pattern == 'curvilinear':
                from shapely.geometry import LineString
                bases = []
                if terrain is not None:
                    cl = terrain.contour_through(sec)
                    if cl is not None: bases.append((cl, 0))
                bases += [(e, w) for e, w in sorted(edges, key=lambda t: -t[0].length * t[1])[:2]]
                if not bases: bases.append((LineString([tuple(q[0]), tuple(q[1])]), 0))
                for b, w in bases:
                    for phase in np.linspace(0, AUTO['band'] + AUTO['local'], 5)[:-1]:
                        yield (w,) + _curvi_lines(sec, b, phase)
            else:
                for u, ref, w in cands:
                    for phase in np.linspace(0, AUTO['block_len'] + AUTO['local'], 7)[:-1]:
                        if pattern == 'ringband':
                            rb = _ringband_lines(sec, S, R, u, ref, phase)
                            if rb is not None: yield (w,) + rb; continue
                        yield (w,) + _grid_lines(sec, u, ref, phase, far_is_road=False)
        for w, rows, crosses in options():
            sc, _ = _score(sec, rows + crosses, bld, None)
            sc += w * 50                                                 # prefer running along the highest-order road
            if terrain is not None: sc -= (400 if hilly else 150) * terrain.steep_len(rows + crosses)      # road length steeper than 18%
            if best is None or sc > best[0]: best = (sc, rows, crosses)""")
# ---------- st_design_autoroads: one or all patterns, metrics, comparison ----------
a = "    L = auto_roads(S, existing, stream, bld, log=print, terrain=terrain)"
assert a in s
i0 = s.index(a); i1 = s.index("    ctx['roads'] = WORK + 'auto_roads.gpkg'", i0)
s = s[:i0] + '''    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    pat = (ctx.get('pattern') or ('all' if (ctx.get('roads') or '').lower() == 'draft' else 'grid')).lower()
    pats = list(PATTERNS) if pat == 'all' else [pat]
    res = {}
    for pt in pats:
        print(f'   -- pattern: {PATTERNS[pt]}', flush=True)
        L = auto_roads(S, existing, stream, bld, log=print, terrain=terrain, pattern=pt)
        new = [l for l, w, k in L if k != 'existing']
        surf = road_surface([l for l, *_ in L], [w / 2 for _, w, _ in L], tol=3.0, clip=S)
        blocked = surf.union(stream.intersection(S)) if stream is not None else surf
        blocks = [b for b in shapely.get_parts(S.difference(blocked)) if b.area > 2000]
        met = dict(pattern=pt, name=PATTERNS[pt], new_road_km=round(sum(l.length for l in new) * FT / 1000, 2),
                   road_share_pct=round(surf.area / S.area * 100, 1),
                   steep_road_m=round(terrain.steep_len(new) * FT) if terrain is not None else None,
                   developable_ac=round(sum(b.area for b in blocks) / 43560, 1), approx_plots=int(sum(b.area for b in blocks) * 0.85 / 7000),
                   blocks=len(blocks))
        G = gpd.GeoDataFrame(dict(width_ft=[w for _, w, _ in L], kind=[k for *_, k in L]), geometry=[l for l, *_ in L], crs=2136)
        suffix = '' if len(pats) == 1 else '_' + pt
        G.to_file(WORK + f'auto_roads{suffix}.gpkg'); G.to_file(D + PFX + f'Roads_draft{suffix}.shp')
        res[pt] = (G, met); print('      ' + ', '.join(f'{k} {v}' for k, v in met.items() if k not in ('pattern', 'name')), flush=True)
    json.dump([m for _, m in res.values()], open(D + PFX + 'Roads_patterns.json', 'w'), indent=1)
    if stream is not None and not ctx.get('stream'):
        gpd.GeoDataFrame(geometry=[stream], crs=2136).to_file(WORK + 'auto_stream.gpkg'); ctx['stream'] = WORK + 'auto_stream.gpkg'; ctx['stream_buffer'] = 0
    img = None
    if os.path.exists(WORK + 'imagery_2136.tif'):
        import rasterio
        r = rasterio.open(WORK + 'imagery_2136.tif'); img = (np.moveaxis(r.read(), 0, -1)[:, :, :3], r.bounds)
    fig, axs = plt.subplots(1, len(res), figsize=(9 * len(res), 9)); axs = np.atleast_1d(axs)
    for ax, (pt, (G, met)) in zip(axs, res.items()):
        if img is not None: b = img[1]; ax.imshow(img[0], extent=(b.left, b.right, b.bottom, b.top), alpha=.55)
        if os.path.exists(D + PFX + 'Contours.shp'):
            C = gpd.read_file(D + PFX + 'Contours.shp'); C[C.major].plot(ax=ax, color='#8d6e63', lw=.6); C[~C.major].plot(ax=ax, color='#bcaaa4', lw=.25)
        gpd.GeoSeries([S]).boundary.plot(ax=ax, color='red', lw=2)
        if stream is not None: gpd.GeoSeries([stream.intersection(S)]).plot(ax=ax, color='#2e8b57', alpha=.45)
        for k, c_, lw in (('existing', 'black', 3.5), ('collector', '#f5a142', 2.6), ('local', '#1f5fd1', 1.3)):
            s_ = G[G.kind == k]
            if len(s_): s_.plot(ax=ax, color=c_, lw=lw)
        x0, y0, x1, y1 = S.bounds; ax.set_xlim(x0 - 100, x1 + 100); ax.set_ylim(y0 - 100, y1 + 100); ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"{met['name']}\\n{met['new_road_km']} km new road | steep road {met['steep_road_m']} m | ~{met['approx_plots']} plots | {met['developable_ac']} ac developable", fontsize=11)
    fig.suptitle(f"{ctx['NAME']}: road layout patterns (green = stream / steep-slope reserve)", fontsize=14)
    plt.savefig(D + PFX + ('Roads_patterns.png' if len(res) > 1 else 'Roads_draft.png'), bbox_inches='tight', dpi=60)
    if len(pats) == 1: ctx['roads'] = WORK + 'auto_roads.gpkg'
    else:
        bestp = max(res, key=lambda k: res[k][1]['approx_plots'] - (res[k][1]['steep_road_m'] or 0) / 10)
        shutil.copy(WORK + f'auto_roads_{bestp}.gpkg', WORK + 'auto_roads.gpkg'); ctx['roads'] = WORK + 'auto_roads.gpkg'
        print(f'   suggested pattern: {PATTERNS[bestp]} (most plots for the least steep road)')
''' + s[i1 + len("    ctx['roads'] = WORK + 'auto_roads.gpkg'"):]
open(p, 'w', encoding='utf-8').write(s)
# CLI --pattern
p = 'toolkit_src/cli.py'; s = open(p, encoding='utf-8').read()
a = "p.add_argument('--steep', dest='steep_pct', type=float, default=30, help='keep slopes >= this %% as green (0 = off)')"
assert a in s
s = s.replace(a, a + "; p.add_argument('--pattern', choices=['grid', 'curvilinear', 'ringband', 'all'], help='road pattern for auto / draft (draft default: all three)')")
s = s.replace("steep_pct=getattr(a, 'steep_pct', 30),", "steep_pct=getattr(a, 'steep_pct', 30), pattern=getattr(a, 'pattern', None),")
open(p, 'w', encoding='utf-8').write(s)
print('patched')
