
# =====================================================================================================================
# Automatic road layout (design --roads auto | draft). Applies the planner's rules (guide section 6) to any site.
# =====================================================================================================================
GRADE_MAX = {'local': 0.10, 'collector': 0.08}                         # LUSPA Table 26: max incline, local roads 10 %, collectors 8 %
AUTO = dict(band=200.0, local=30.0, collector=40.0, block_len=490.0, max_sector_ac=35.0, min_seg=120.0, arrive_back=140.0, min_angle=70.0,
            entry_gap=1000.0, entry_cost=60000.0)   # fewest junctions on the highest-order road: >= 1,000 ft apart (user rule: blocks parallel to the highest road)
HIGHWAY_WIDTH = {'motorway': 100, 'trunk': 100, 'primary': 100, 'secondary': 80, 'tertiary': 60, 'unclassified': 40, 'residential': 40, 'track': 40, 'service': 30}
def _u(v): v = np.asarray(v, float); return v / (np.linalg.norm(v) + 1e-12)
def _tangent(l, s, h=8.0):
    return _u(np.array(l.interpolate(min(l.length, s + h)).coords[0])[:2] - np.array(l.interpolate(max(0, s - h)).coords[0])[:2])
def _cubic(p0, d0, p3, d3, k=16):
    L = np.linalg.norm(p3 - p0) / 3; p1, p2 = p0 + d0 * L, p3 - d3 * L; t = np.linspace(0, 1, k)[:, None]
    return [tuple(x) for x in (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3]
def _long_line(c, d, L=1e5):
    from shapely.geometry import LineString
    return LineString([tuple(c - d * L), tuple(c + d * L)])
def _road_edges(sector, reserves):
    """pieces of the sector outline that face a road reserve, with the width of that road: [(LineString, width)]"""
    import shapely
    from shapely.ops import linemerge
    out = []
    ring = sector.exterior
    for poly, w in reserves:
        near = ring.intersection(poly.buffer(2.0))
        for g in shapely.get_parts(near):
            if g.geom_type == 'LineString' and g.length > 60: out.append((g, w))
            elif g.geom_type == 'MultiLineString':
                for q in shapely.get_parts(linemerge(g)):
                    if q.length > 60: out.append((q, w))
    return out
def _edge_direction(edge):
    """dominant direction of an edge (length-weighted, ignoring sign)"""
    c = np.array(edge.coords)[:, :2]; v = np.diff(c, axis=0); L = np.linalg.norm(v, axis=1)
    if L.sum() == 0: return np.array([1.0, 0.0])
    ang = np.arctan2(v[:, 1], v[:, 0]) * 2                       # doubled angles: direction without sign
    a = math.atan2((np.sin(ang) * L).sum(), (np.cos(ang) * L).sum()) / 2
    return np.array([math.cos(a), math.sin(a)])
def _grid_lines(sector, u, ref_pt, phase, far_is_road):
    """rows parallel to u (from the reference edge, 200 ft bands) and cross roads along n (block_len apart, shifted by phase)"""
    import shapely
    from shapely.geometry import LineString
    n = np.array([-u[1], u[0]]); P = np.array(sector.exterior.coords)[:, :2]
    pn = (P - ref_pt) @ n
    if abs(pn.min()) > abs(pn.max()): n = -n; pn = -pn                  # n points into the sector
    pu = (P - ref_pt) @ u; ext = pn.max()
    B, Lr, BL = AUTO['band'], AUTO['local'], AUTO['block_len']
    rows, offs = [], []
    o = B + Lr / 2
    while o + Lr / 2 + 100 <= ext: offs.append(o); o += B + Lr
    if offs:
        left = ext - offs[-1] - Lr / 2
        if left < 100 or (far_is_road and left < 180): offs = offs[:-1]
    for o in offs:
        g = _long_line(ref_pt + n * o, u).intersection(sector)
        rows += [q for q in shapely.get_parts(g) if q.geom_type == 'LineString' and q.length > AUTO['min_seg']]
    crosses = []
    s = pu.min() + phase
    while s < pu.max():
        if s - pu.min() > 150 and pu.max() - s > 150:
            g = _long_line(ref_pt + u * s, n).intersection(sector)
            crosses += [q for q in shapely.get_parts(g) if q.geom_type == 'LineString' and q.length > AUTO['min_seg']]
        s += BL + Lr
    return rows, crosses
def _score(sector, lines, bld, reserves_poly):
    """usable standard blocks minus building conflicts minus sharp arrivals"""
    import shapely
    from shapely.ops import unary_union
    if not lines: return -1e9, []
    surf = unary_union([l.buffer(AUTO['local'] / 2, cap_style=2) for l in lines])
    blocks = [b for b in shapely.get_parts(sector.difference(surf)) if b.area > 2000]
    good = 0.0
    for b in blocks:
        q = np.array(b.minimum_rotated_rectangle.exterior.coords); a, c = sorted([np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[1])])
        fill = b.area / max(b.minimum_rotated_rectangle.area, 1)
        w = 1.0 if (170 <= a <= 240 and fill > 0.85) else (0.7 if (90 <= a <= 120 and fill > 0.85) else 0.35)
        good += b.area * w
    conflict, n_cut = 0.0, 0
    if bld is not None:
        conflict = surf.intersection(bld).area
        n_cut = sum(1 for b in shapely.get_parts(bld) if b.area > 200 and surf.intersection(b).area > 0.15 * b.area)   # buildings the road reserve would cut into
    return good - 40 * conflict - 20000 * n_cut, blocks
def _arrive_square(line, target_union, min_angle):
    import shapely
    """bend the last stretch of a line so it meets the road it runs into at ~90 deg (if it would meet below min_angle)"""
    from shapely.geometry import LineString, Point
    out = line
    for at_end in (True, False):
        l = out if at_end else LineString(list(out.coords)[::-1])
        p = Point(l.coords[-1]); near = target_union if target_union.geom_type in ('LineString', 'MultiLineString') else shapely.line_merge(target_union.boundary)
        if near.distance(p) > 25: out = l if at_end else LineString(list(l.coords)[::-1]); continue
        s_t = near.project(p); tg = _tangent(near, s_t); d = _u(np.array(l.coords[-1])[:2] - np.array(l.coords[-2])[:2])
        ang = math.degrees(math.acos(min(1, abs(float(d @ tg)))))
        if ang < min_angle and l.length > AUTO['arrive_back'] + 40:
            sA = l.length - AUTO['arrive_back']; A = np.array(l.interpolate(sA).coords[0])[:2]
            T = np.array(near.interpolate(near.project(Point(A))).coords[0])[:2]; d3 = _u(T - A)
            from shapely.ops import substring
            l = LineString(list(substring(l, 0, sA).coords) + _cubic(A, d, T, d3)[1:])
        out = l if at_end else LineString(list(l.coords)[::-1])
    return out
class _Terrain:
    """DEM sampler on EPSG:2136 ft: elevation, steep road length, contour direction of a parcel"""
    def __init__(self, path):
        import rasterio
        r = rasterio.open(path); self.z = r.read(1).astype(float); self.T = r.transform; self.Ti = ~r.transform
        self.px_m = abs(r.transform.a) * FT; gy, gx = np.gradient(self.z, self.px_m); self.gx, self.gy = gx, -gy     # map y up
    def at(self, x, y):
        c, r_ = self.Ti * (x, y); r_, c = int(r_), int(c)
        return self.z[r_, c] if 0 <= r_ < self.z.shape[0] and 0 <= c < self.z.shape[1] else np.nan
    def steep_len(self, lines, limit=0.18, step=30.0):
        L = 0.0
        for l in lines:
            n = max(2, int(l.length / step)); pts = [l.interpolate(t) for t in np.linspace(0, l.length, n)]
            zs = np.array([self.at(p.x, p.y) for p in pts]); ds = l.length / (n - 1) * FT
            g = np.abs(np.diff(zs)) / ds; L += float(np.nansum((g > limit) * l.length / (n - 1)))
        return L
    def contour_through(self, poly):
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
    def contour_dir(self, poly):
        from rasterio import features as rfeat
        m = rfeat.rasterize([poly], out_shape=self.z.shape, transform=self.T).astype(bool)
        gx, gy = self.gx[m], self.gy[m]; mag = np.hypot(gx, gy); ok = ~np.isnan(mag) & (mag > 0)
        if ok.sum() < 10: return None, 0.0
        ang = np.arctan2(gy[ok], gx[ok]) * 2; a = math.atan2((np.sin(ang) * mag[ok]).sum(), (np.cos(ang) * mag[ok]).sum()) / 2
        g = np.array([math.cos(a), math.sin(a)]); return np.array([-g[1], g[0]]), float(np.nanmean(mag[ok]))

PATTERNS = {'mixed': 'Blended (best pattern per parcel)', 'grid': 'Grid iron', 'curvilinear': 'Curvilinear (follows the contours)'}     # ring and band removed (user: 'horrible')
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
    core = core.buffer(-150).buffer(150)                                  # rounded ring corners, small notches ignored
    parts = [c for c in shapely.get_parts(core) if c.geom_type == 'Polygon' and c.area > 2 * 43560]
    if not parts: return None
    rings = [LineString(_chaikin(c.exterior.simplify(60).coords, 3)) for c in parts]                    # smooth loop, not every bend of a reserve edge
    rows, crosses = _grid_lines(sec, u, ref, phase, far_is_road=False)
    inner = unary_union([c.buffer(-(B / 2)) for c in parts])
    rows = [q for r_ in rows for q in shapely.get_parts(r_.intersection(inner)) if q.geom_type == 'LineString' and q.length > AUTO['min_seg']]
    open_ = sec.difference(bnd.buffer(100 + Lr)) if not bnd.is_empty else sec      # cross roads stop at the ring on the site-boundary side
    U = unary_union(parts)
    crosses = [q for c_ in crosses for q in shapely.get_parts(c_.intersection(open_)) if q.geom_type == 'LineString' and q.length > AUTO['min_seg'] and q.intersects(U)]
    links = []
    if redges is not None and not redges.is_empty:
        for rg in rings:
            n_conn = sum(1 for c_ in crosses if c_.intersects(rg.buffer(3)))
            if n_conn >= 2: continue
            cand = []
            for t in np.linspace(0, rg.length, 24, endpoint=False):
                pt = rg.interpolate(t); q = redges.interpolate(redges.project(pt)); d = pt.distance(q)
                if d < 400: cand.append((d, pt, q))
            cand.sort(key=lambda x: x[0]); used = []
            for d, pt, q in cand:
                if len(used) >= 2 - n_conn: break
                if all(pt.distance(u) > rg.length / 4 for u in used):
                    links.append(LineString([pt.coords[0], q.coords[0]])); used.append(pt)
    return rings + rows, crosses + links

def auto_roads(S, existing, stream_poly=None, buildings=None, log=print, terrain=None, pattern='mixed', zones=None, only_zones=False):
    """S: site polygon (EPSG:2136 ft); existing: [(LineString, width_ft[, kind])] (kind 'locked' = planner's roads, kept exactly);
    zones: [(Polygon, pattern)] redesign areas; only_zones: new roads only inside the zones. Returns [(LineString, width_ft, kind)]"""
    zones = zones or []
    from shapely.ops import substring
    ZU = None
    if zones:
        from shapely.ops import unary_union as _uu
        ZU = _uu([z for z, _ in zones])
    def zone_of(sec):
        best = None
        for z, pt in zones:
            a = z.intersection(sec).area
            if a > 0.4 * sec.area and (best is None or a > best[0]): best = (a, pt or 'mixed')
        return None if best is None else best[1]
    import shapely
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union, nearest_points
    out = []
    # ---- 1. existing roads: kept on alignment, carried straight in to the boundary or the next road ----
    ex = []
    for it in existing:
        l, w = it[0], it[1]; kind = it[2] if len(it) > 2 else 'existing'
        if kind == 'locked':                                              # planner's roads: kept exactly as drawn
            ex.append((l, w)); out.append((l, w, 'locked')); continue
        g = l.intersection(S.buffer(w))
        for q in shapely.get_parts(g):
            if q.geom_type != 'LineString' or q.length < 50: continue
            c = list(q.coords)
            for at_end in (True, False):
                p = np.array(c[-1] if at_end else c[0])[:2]
                if Point(p).distance(S.exterior) < 10: continue
                d = _u(np.array(c[-1])[:2] - np.array(c[-2])[:2]) if at_end else _u(np.array(c[0])[:2] - np.array(c[1])[:2])
                ray = LineString([tuple(p), tuple(p + d * 3000)]); others = unary_union([o[0] for o in existing if o[0] is not l] + [S.exterior])
                h = ray.intersection(others)
                if not h.is_empty:
                    hp = min([pp for pp in shapely.get_parts(h) if pp.geom_type == 'Point'] or [Point(ray.coords[-1])], key=lambda pp: pp.distance(Point(p)))
                    if hp.distance(Point(p)) < 2000: c = c + [tuple(np.array(hp.coords[0]))] if at_end else [tuple(np.array(hp.coords[0]))] + c
            ex.append((LineString(c), w)); out.append((LineString(c), w, kind))
    SR = stream_poly.intersection(S) if stream_poly is not None and not stream_poly.is_empty else None
    def reserves_of(lines):
        return [(l.buffer(w / 2, cap_style=2).intersection(S.buffer(1)), w) for l, w, *_ in lines]
    # ---- 2. access: a site with no road gets a collector from its longest edge through the centre ----
    if not ex:
        q = np.array(S.minimum_rotated_rectangle.exterior.coords)[:, :2]; e1, e2 = q[1] - q[0], q[2] - q[1]
        d = _u(e2 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e1); c = np.array(S.centroid.coords[0])
        g = _long_line(c, d).intersection(S); g = max(shapely.get_parts(g), key=lambda x: x.length)
        out.append((g, AUTO['collector'], 'collector')); log('   no existing road: collector across the site through the centre')
    # ---- 3. collectors: split large parcels (> max_sector_ac) square to their main road edge, through the centre ----
    for level in range(3):
        R = reserves_of(out); blocked = unary_union([p for p, _ in R] + ([SR] if SR is not None else []))
        sectors = [g for g in shapely.get_parts(S.difference(blocked)) if g.area > 43560]
        added = False
        if only_zones and ZU is not None: sectors = [q for g in sectors for q in shapely.get_parts(g.intersection(ZU)) if q.geom_type == 'Polygon' and q.area > 43560]
        for sec in sectors:
            if sec.area / 43560 <= AUTO['max_sector_ac']: continue
            edges = _road_edges(sec, R)
            if edges:
                e, w = max(edges, key=lambda t: t[0].length * t[1]); d = _edge_direction(e); d = np.array([-d[1], d[0]])
            else:
                q = np.array(sec.minimum_rotated_rectangle.exterior.coords)[:, :2]; e1, e2 = q[1] - q[0], q[2] - q[1]
                d = _u(e2 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e1)
            c = np.array(sec.centroid.coords[0]); best = None
            d0 = d
            for shift, turn in [(sh, tn) for sh in np.linspace(-0.25, 0.25, 11) for tn in ((0, -10, 10, -20, 20) if terrain is not None else (0,))]:   # fewest buildings, gentlest grade, near the middle
                q = np.array(sec.minimum_rotated_rectangle.exterior.coords)[:, :2]; span = max(np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[1]))
                ca, sa = math.cos(math.radians(turn)), math.sin(math.radians(turn)); d = np.array([d0[0] * ca - d0[1] * sa, d0[0] * sa + d0[1] * ca])
                cc = c + np.array([-d0[1], d0[0]]) * shift * span
                g = _long_line(cc, d).intersection(sec.buffer(AUTO['collector']))
                parts = [x for x in shapely.get_parts(g) if x.geom_type == 'LineString']
                if not parts: continue
                g = max(parts, key=lambda x: x.length)
                cost = (g.buffer(AUTO['collector'] / 2).intersection(buildings).area if buildings is not None else 0) + abs(shift) * 2000 + abs(turn) * 150
                if terrain is not None: cost += 250 * terrain.steep_len([g], GRADE_MAX['collector'])
                if best is None or cost < best[0]: best = (cost, g)
            if best is None: continue
            out.append((best[1], AUTO['collector'], 'collector')); added = True
            log(f'   collector splits a {sec.area / 43560:.0f} ac parcel')
        if not added: break
    # ---- 4. grid per parcel ----
    w_top = max([w for _, w, k in out if k in ('existing', 'locked', 'collector')] or [0])     # the highest road in the area, whatever its width
    TOP = unary_union([l for l, w, k in out if k in ('existing', 'locked', 'collector') and w == w_top]) if w_top > 0 else None
    TOPZ = TOP.buffer(w_top / 2 + 85) if TOP is not None else None          # a new road ending here would be joined to the top road (step 5 reaches 80 ft)
    def entries(lines):
        if TOPZ is None: return 0
        return sum(1 for l in lines for e in (l.coords[0], l.coords[-1]) if TOPZ.contains(Point(e)))
    R = reserves_of(out); blocked = unary_union([p for p, _ in R] + ([SR] if SR is not None else []))
    sectors = [g for g in shapely.get_parts(S.difference(blocked)) if g.area > 30000]
    if only_zones and ZU is not None: sectors = [q for g in sectors for q in shapely.get_parts(g.intersection(ZU)) if q.geom_type == 'Polygon' and q.area > 30000]
    bld = unary_union(list(buildings.geoms)) if buildings is not None and hasattr(buildings, 'geoms') else buildings
    RES_U = unary_union([p_ for p_, _ in R])
    def staggered(lines):
        n_ = 0
        for l in lines:
            c_ = np.array(l.coords)[:, :2]
            for e_, d_ in ((c_[-1], _u(c_[-1] - c_[-2])), (c_[0], _u(c_[0] - c_[1]))):
                for p_ in prev_ends:
                    pv = np.array(p_.coords[0]) - e_
                    if np.linalg.norm(pv) > 260: continue
                    if not LineString([tuple(e_), p_.coords[0]]).intersects(RES_U): continue     # only across a road
                    off = abs(d_[0] * pv[1] - d_[1] * pv[0])
                    if 3 < off < 131: n_ += 1
        return n_
    for sec in sectors:
        prev_ends = [Point(e) for l, w, k in out if k == 'local' for e in (l.coords[0], l.coords[-1]) if sec.distance(Point(e)) < 120]
        edges = _road_edges(sec, R)
        cands = []
        if edges:
            for e, w in sorted(edges, key=lambda t: -t[0].length * t[1])[:2]:
                cands.append((_edge_direction(e), np.array(e.interpolate(0.5, normalized=True).coords[0])[:2], w))
        q = np.array(sec.minimum_rotated_rectangle.exterior.coords)[:, :2]; e1, e2 = q[1] - q[0], q[2] - q[1]
        cands.append((_u(e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2), q[0], 0))
        hilly = False
        if terrain is not None:                                          # rows along the contours (cross roads take the slope over short lengths)
            cd, mg = terrain.contour_dir(sec)
            if cd is not None:
                hilly = mg > 0.08; cands.append((cd, q[0], 0))
                if edges: cands.append((cd, np.array(edges[0][0].interpolate(0.5, normalized=True).coords[0])[:2], 0))
        best = None
        pat = zone_of(sec) or pattern
        def options(pattern):
            if pattern == 'ringband': pattern = 'mixed'                 # removed pattern (older redesign areas may still name it)
            if pattern == 'mixed':
                for pt in ('grid', 'curvilinear'): yield from options(pt)
                return
            if pattern == 'curvilinear':
                from shapely.geometry import LineString
                bases = []
                if terrain is not None:
                    cl = terrain.contour_through(sec)
                    if cl is not None: bases.append((cl, 0))
                if not bases: bases += [(e, w) for e, w in sorted(edges, key=lambda t: -t[0].length * t[1])[:2]]      # contour first: the pattern follows the terrain
                if not bases: bases.append((LineString([tuple(q[0]), tuple(q[1])]), 0))
                for b, w in bases:
                    for phase in np.linspace(0, AUTO['band'] + AUTO['local'], 5)[:-1]:
                        yield (w,) + _curvi_lines(sec, b, phase)
            else:
                for u, ref, w in cands:
                    Pp = np.array(sec.exterior.coords)[:, :2]; pu0 = ((Pp - ref) @ u).min(); per = AUTO['block_len'] + AUTO['local']
                    al = [((np.array(p_.coords[0]) - ref) @ u - pu0) % per for p_ in prev_ends]      # positions that line cross roads up with roads across the street
                    for phase in list(np.linspace(0, per, 7)[:-1]) + al[:12]:
                        if pattern == 'ringband':
                            rb = _ringband_lines(sec, S, R, u, ref, phase)
                            if rb is not None: yield (w,) + rb; continue
                        yield (w,) + _grid_lines(sec, u, ref, phase, far_is_road=False)
        for w, rows, crosses in options(pat):
            sc, _ = _score(sec, rows + crosses, bld, None)
            sc -= 30000 * staggered(rows + crosses)                      # T junctions 1-40 m off a road end across the street
            sc += w * 50                                                 # prefer running along the highest-order road
            sc -= AUTO['entry_cost'] * entries(rows + crosses)            # every junction on the highest-order road costs (blocks run parallel to it)
            if terrain is not None:                                      # hills: road length over the LUSPA max grade (10 %) and over 18 % both cost
                sc -= (1500 if hilly else 400) * terrain.steep_len(rows + crosses, 0.18) + (500 if hilly else 120) * terrain.steep_len(rows + crosses, GRADE_MAX['local'])
            if best is None or sc > best[0]: best = (sc, rows, crosses)
        if best is None: continue
        for l in best[1] + best[2]: out.append((l, AUTO['local'], 'local'))
    # ---- 4b. kept roads cut at a redesign-area edge: carry them into the area to the first new road ----
    if only_zones and ZU is not None:
        newl = unary_union([l for l, w, k in out if k in ('local', 'collector')]); fixed = []
        for l, w, k in out:
            if k == 'locked' and not newl.is_empty:
                c = list(l.coords)
                for at_end in (True, False):
                    p = Point(c[-1] if at_end else c[0])
                    if p.distance(ZU.boundary) > 5: continue
                    d = _u(np.array(c[-1])[:2] - np.array(c[-2])[:2]) if at_end else _u(np.array(c[0])[:2] - np.array(c[1])[:2])
                    h = LineString([p.coords[0], tuple(np.array(p.coords[0]) + d * 600)]).intersection(newl)
                    pts = [q for q in shapely.get_parts(h) if q.geom_type == 'Point' and q.distance(p) > 1]
                    if pts:
                        hp = min(pts, key=lambda q: q.distance(p)).coords[0]
                        c = c + [hp] if at_end else [hp] + c
                l = LineString(c)
            fixed.append((l, w, k))
        out = fixed
    # ---- 5. connect: extend local ends to the road centreline / boundary they face; bend sharp arrivals square ----
    allc = unary_union([l for l, *_ in out]); fin = []
    for l, w, k in out:
        if k == 'local':
            c = list(l.coords)
            for at_end in (True, False):
                p = np.array(c[-1] if at_end else c[0])[:2]; d = _u(np.array(c[-1])[:2] - np.array(c[-2])[:2]) if at_end else _u(np.array(c[0])[:2] - np.array(c[1])[:2])
                ray = LineString([tuple(p + d * 0.5), tuple(p + d * 80)])
                tgt = unary_union([x for x, *_ in out if x is not l] + [S.exterior]); h = ray.intersection(tgt)
                if not h.is_empty:
                    hp = min([pp for pp in shapely.get_parts(h) if pp.geom_type == 'Point'] or [Point(ray.coords[-1])], key=lambda pp: pp.distance(Point(p)))
                    c = c + [tuple(np.array(hp.coords[0]))] if at_end else [tuple(np.array(hp.coords[0]))] + c
            l = LineString(c)
            others = unary_union([x for x, ww, kk in out if kk != 'local'])
            if not others.is_empty: l = _arrive_square(l, others, AUTO['min_angle'])
        fin.append((l, w, k))
    # ---- 6. junctions on the highest-order road: >= entry_gap apart, as crossroads (both sides aligned); other local roads stop at the first parallel road ----
    if TOP is not None:
        topl = shapely.line_merge(TOP) if TOP.geom_type == 'MultiLineString' else TOP
        topl = max(shapely.get_parts(topl), key=lambda x: x.length) if topl.geom_type != 'LineString' else topl
        ent = []                                                           # (index in fin, end, position along the top road, side, fixed)
        for i, (l, w, k) in enumerate(fin):
            if k not in ('local', 'collector') or (k == 'collector' and w == w_top): continue      # a collector that IS the highest road is not an entry into it
            for at_end in (True, False):
                e = Point(l.coords[-1] if at_end else l.coords[0])
                if e.distance(TOP) <= w_top / 2 + 6:
                    sp = topl.project(e); tg = _tangent(topl, sp); v = np.array(e.coords[0])[:2] - np.array(topl.interpolate(sp).coords[0])[:2]
                    inner = Point(l.interpolate(min(40, l.length / 2)) if not at_end else l.interpolate(max(0, l.length - 40)))
                    vi = np.array(inner.coords[0])[:2] - np.array(topl.interpolate(sp).coords[0])[:2]
                    ent.append((i, at_end, sp, 1 if (tg[0] * vi[1] - tg[1] * vi[0]) > 0 else -1, k == 'collector'))
        kept = sorted(sp for i, a, sp, sd, fx in ent if fx)
        for i, a, sp, sd, fx in sorted(ent, key=lambda t: t[2]):
            if fx: continue
            if all(abs(sp - k_) >= AUTO['entry_gap'] for k_ in kept) or any(abs(sp - k_) <= 60 for k_ in kept): kept.append(sp)   # spaced, or opposite an entry already kept (crossroads)
        cut = 0
        for i, a, sp, sd, fx in ent:
            if fx or any(abs(sp - k_) <= 60 for k_ in kept): continue
            l, w, k = fin[i]; others = unary_union([x for j, (x, *_r) in enumerate(fin) if j != i and _r[1] != 'existing'])
            end = Point(l.coords[-1] if a else l.coords[0]); hits = [q for q in shapely.get_parts(l.intersection(others)) if q.geom_type == 'Point' and q.distance(end) > 30]
            if not hits: continue                                          # no parallel road to stop at: keep the access
            h = min(hits, key=lambda q: q.distance(end)); s_h = l.project(h)
            nl = substring(l, 0, s_h) if a else substring(l, s_h, l.length)
            if nl.length > AUTO['min_seg'] / 2: fin[i] = (nl, w, k); cut += 1
        n_top = sum(1 for i, a, sp, sd, fx in ent if fx or any(abs(sp - k_) <= 60 for k_ in kept))
        log(f'   junctions on the {w_top:.0f} ft road: {n_top} kept (>= {AUTO["entry_gap"]:.0f} ft apart, as crossroads); {cut} local roads now end at the parallel road')
    if terrain is not None:
        for kk in ('collector', 'local'):
            ls_ = [l for l, w, k in fin if k == kk]
            if ls_:
                over = terrain.steep_len(ls_, GRADE_MAX[kk]) * FT; tot = sum(l.length for l in ls_) * FT
                log(f"   {kk} roads steeper than the LUSPA {GRADE_MAX[kk] * 100:.0f} % maximum: {over:.0f} m of {tot:.0f} m" + ('  -> check these on the slope layer' if over > 0 else ''))
    # ---- 7. no staggered T junctions: two local roads meeting a road from opposite sides within 40 m become one crossroads ----
    from shapely import affinity as _aff
    def _tan_at(m, sp):
        a_ = np.array(m.interpolate(max(0, sp - 5)).coords[0])[:2]; b_ = np.array(m.interpolate(min(m.length, sp + 5)).coords[0])[:2]; return _u(b_ - a_)
    fixed_n = 0
    for _round in range(60):
        moved = False
        roads_ = [l for l, *_ in fin]
        ends_ = []                                                          # (line idx, at_end, road idx, position on road, side)
        for i, (l, w, k) in enumerate(fin):
            if k != 'local': continue
            for at_end in (True, False):
                e = Point(l.coords[-1] if at_end else l.coords[0])
                for j, m in enumerate(roads_):
                    if j == i or m.distance(e) > 3: continue
                    sp = m.project(e)
                    if sp < 1 or sp > m.length - 1: continue
                    t = _tan_at(m, sp); inner = np.array(l.interpolate(max(0, l.length - 30) if at_end else min(l.length, 30)).coords[0])[:2] - np.array(e.coords[0])[:2]
                    ends_.append((i, at_end, j, sp, 1 if (t[0] * inner[1] - t[1] * inner[0]) > 0 else -1))
        for x in ends_:
            for y in ends_:
                if moved or x[2] != y[2] or x[0] >= y[0] or x[4] == y[4]: continue
                gap = abs(x[3] - y[3])
                if not (3 < gap < 131): continue                            # 1-40 m apart on opposite sides: staggered
                mv, st = (x, y) if fin[x[0]][0].length <= fin[y[0]][0].length else (y, x)
                road = roads_[mv[2]]; t = _tan_at(road, mv[3]) * (st[3] - mv[3])
                l, w, k = fin[mv[0]]; nl = _aff.translate(l, xoff=t[0], yoff=t[1]).intersection(S.buffer(1))
                if nl.geom_type != 'LineString' or nl.length < 0.8 * l.length: continue
                far = Point(nl.coords[0] if mv[1] else nl.coords[-1])          # the other end must still reach a road or the boundary
                if min([r.distance(far) for jj, r in enumerate(roads_) if jj != mv[0]] + [S.exterior.distance(far)]) > 5: continue
                fin[mv[0]] = (nl, w, k); fixed_n += 1; moved = True
        if not moved: break
    if fixed_n: log(f'   staggered T junctions aligned into crossroads: {fixed_n}')
    log(f"   auto layout: {sum(1 for *_, k in fin if k == 'existing')} existing, {sum(1 for *_, k in fin if k == 'collector')} collectors, {sum(1 for *_, k in fin if k == 'local')} local roads")
    return fin
def st_design_autoroads(ctx):
    """--roads auto | draft: design the roads from the rules; writes <P>Roads_draft.shp (editable) and a preview"""
    import geopandas as gpd, shapely
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    WORK, D, PFX = ctx['WORK'], ctx['D'], ctx['PFX']
    site = gpd.read_file(ctx['SITE_KML']).to_crs(2136); S = Polygon(shapely.force_2d(site.geometry.iloc[0]).exterior.coords)
    existing = []
    if ctx.get('existing'):                                             # the planner's existing roads (always used)
        E = gpd.read_file(ctx['existing']).to_crs(2136); E['geometry'] = E.geometry.force_2d()
        for _, r_ in E.explode(index_parts=False).iterrows():
            if r_.geometry.geom_type == 'LineString': existing.append((r_.geometry, _width_of(r_) if any(k in r_ for k in ('width_ft', 'class', 'Class')) else 40.0))
    if ctx.get('lock'):                                                   # roads the planner keeps (drawn / edited / outside a redesign area)
        Lk = gpd.read_file(ctx['lock']).to_crs(2136); Lk['geometry'] = Lk.geometry.force_2d()
        for _, r_ in Lk.explode(index_parts=False).iterrows():
            if r_.geometry.geom_type == 'LineString': existing.append((r_.geometry, _width_of(r_), 'locked'))
        print(f'   kept roads (locked): {len(Lk)}')
    if os.path.exists(WORK + 'osm_roads.gpkg'):                         # OpenStreetMap roads: always, unless the planner already gave that road
        O = gpd.read_file(WORK + 'osm_roads.gpkg'); given = unary_union([e[0] for e in existing]).buffer(25) if existing else None; n_osm = 0
        for g, h in zip(O.geometry, O.highway):
            if h in HIGHWAY_WIDTH and g.intersects(S.buffer(100)) and g.intersection(S).length > 100:
                if given is not None and g.intersection(given).length > 0.6 * g.length: continue
                existing.append((g, float(HIGHWAY_WIDTH[h]))); n_osm += 1
        print(f'   OpenStreetMap roads kept on their alignment: {n_osm}', flush=True)
    stream = None; stream_src = ''
    if ctx.get('stream'):
        st = gpd.read_file(ctx['stream']).to_crs(2136); st['geometry'] = st.geometry.force_2d()
        if len(st): stream = st.union_all().buffer(float(ctx.get('stream_buffer') or 0) or 0.01); stream_src = 'drawn by the planner'
    if stream is None and os.path.exists(WORK + 'osm_water.gpkg'):
        Wt = gpd.read_file(WORK + 'osm_water.gpkg')
        if len(Wt):
            st_ = Wt.union_all().buffer(float(ctx.get('stream_buffer') or 110))
            if st_.intersects(S): stream = st_; ctx['stream_poly'] = stream; stream_src = f'OpenStreetMap waterways ({len(Wt)})'
    STP = steep_reserve(ctx)
    if STP is not None: stream_src = (stream_src + ' + ' if stream is not None else '') + 'steep slopes'; stream = STP if stream is None else stream.union(STP); print(f'   steep-slope reserve kept green: {STP.area / 43560:.1f} ac')
    terrain = _Terrain(WORK + 'dem_2136.tif') if os.path.exists(WORK + 'dem_2136.tif') else None
    bld = None
    if os.path.exists(WORK + 'buildings.gpkg'):
        Bd = gpd.read_file(WORK + 'buildings.gpkg').to_crs(2136); Bd = Bd[Bd.intersects(S)]
        if len(Bd): bld = unary_union(list(Bd.geometry))
    print(f'   inputs: {len(existing)} existing roads, green reserve {("yes: " + stream_src) if stream is not None else "no"}, {0 if bld is None else len(shapely.get_parts(bld))} existing buildings')
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    pat = (ctx.get('pattern') or 'mixed').lower()
    zones = []
    if ctx.get('zones'):
        Zg = gpd.read_file(ctx['zones']).to_crs(2136)
        for _, z in Zg.iterrows():
            if z.geometry is not None and z.geometry.geom_type in ('Polygon', 'MultiPolygon'): zones.append((shapely.force_2d(z.geometry), (z.get('pattern') or pat)))
        print(f'   redesign areas: {len(zones)} ({", ".join(PATTERNS.get(p_, p_) for _, p_ in zones)})')
    saved = dict(AUTO)
    for k, ck in (('band', 'band'), ('block_len', 'block_len'), ('local', 'local_width'), ('collector', 'collector_width'), ('max_sector_ac', 'max_parcel_ac')):
        if ctx.get(ck): AUTO[k] = float(ctx[ck])
    print(f"   parameters: block depth {AUTO['band']:.0f} ft, block length {AUTO['block_len']:.0f} ft, local roads {AUTO['local']:.0f} ft, collectors {AUTO['collector']:.0f} ft, parcels up to {AUTO['max_sector_ac']:.0f} ac")
    pats = list(PATTERNS) if pat == 'all' else [pat]
    res = {}
    for pt in pats:
        print(f'   -- pattern: {PATTERNS[pt]}', flush=True)
        L = auto_roads(S, existing, stream, bld, log=print, terrain=terrain, pattern=pt, zones=zones, only_zones=bool(ctx.get('only_zones')))
        new = [l for l, w, k in L if k not in ('existing', 'locked')]
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
        for k, c_, lw in (('existing', 'black', 3.5), ('locked', '#7b1fa2', 2.2), ('collector', '#f5a142', 2.6), ('local', '#1f5fd1', 1.3)):
            s_ = G[G.kind == k]
            if len(s_): s_.plot(ax=ax, color=c_, lw=lw)
        x0, y0, x1, y1 = S.bounds; ax.set_xlim(x0 - 100, x1 + 100); ax.set_ylim(y0 - 100, y1 + 100); ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"{met['name']}\n{met['new_road_km']} km new road | steep road {met['steep_road_m']} m | ~{met['approx_plots']} plots | {met['developable_ac']} ac developable", fontsize=11)
    fig.suptitle(f"{ctx['NAME']}: road layout patterns (green = stream / steep-slope reserve)", fontsize=14)
    plt.savefig(D + PFX + ('Roads_patterns.png' if len(res) > 1 else 'Roads_draft.png'), bbox_inches='tight', dpi=60)
    AUTO.clear(); AUTO.update(saved)
    if len(pats) == 1: ctx['roads'] = WORK + 'auto_roads.gpkg'
    else:
        bestp = max(res, key=lambda k: res[k][1]['approx_plots'] - (res[k][1]['steep_road_m'] or 0) / 10)
        shutil.copy(WORK + f'auto_roads_{bestp}.gpkg', WORK + 'auto_roads.gpkg'); ctx['roads'] = WORK + 'auto_roads.gpkg'
        print(f'   suggested pattern: {PATTERNS[bestp]} (most plots for the least steep road)')

