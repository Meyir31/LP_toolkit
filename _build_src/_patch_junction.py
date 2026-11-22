p = 'ml4/road_surface.py'; s = open(p, encoding='utf-8').read()
a0 = s.index("            M = unary_union([lines[j].buffer(half[j]) for j in through]); hmax = max(half[j] for j in through)")
a1 = s.index("    S = unary_union(pieces)")
new = '''            M = unary_union([lines[j].buffer(half[j]) for j in through]); hmax = max(half[j] for j in through)
            L = g.length
            if p.within(M):                                             # where the branch centreline enters the through road
                s_exit = None
                for s in np.arange(0, min(L, hmax + 2 * tol), 0.25):
                    q = g.interpolate(s if at_start else L - s)
                    if not q.within(M): s_exit = s; break
                if s_exit is None: continue                             # runs along the other road: leave it
                g = substring(g, s_exit, L) if at_start else substring(g, 0, L - s_exit)
            elif p.distance(M) > tol: continue
            # carry the branch right across the through road (full overlap, no unpaved wedge at oblique junctions) ...
            d = _out_dir(g, at_start); c = list(g.coords); e = np.array(c[0 if at_start else -1])[:2]
            reach = 2 * hmax + 2 * half[i] + p.distance(M) + 1
            q = tuple(e + d * reach)
            g = LineString([q] + c) if at_start else LineString(c + [q])
            # ... then cut away whatever would stick out beyond the FAR edge of the through road
            LT = unary_union([lines[j] for j in through]).intersection(p.buffer(reach * 3 + 50))
            ref = Point(e - d * min(2 * hmax, max(L - 1, 1)))           # a point on the branch's own side
            near_pt = LT.interpolate(LT.project(ref)) if LT.geom_type in ('LineString', 'MultiLineString') else None
            far = None
            if near_pt is not None and LT.geom_type == 'LineString':
                sN = LT.project(ref); t = np.array(LT.interpolate(min(LT.length, sN + 2)).coords[0])[:2] - np.array(LT.interpolate(max(0, sN - 2)).coords[0])[:2]
                side = np.sign(t[0] * (ref.y - near_pt.y) - t[1] * (ref.x - near_pt.x)) or 1.0      # +1 = branch on the left of LT
                big = 4 * (hmax + half[i]) + 10
                far = LT.buffer(-side * big, single_sided=True)        # the far side of the through road
            else:
                parts = [x for x in shapely.get_parts(LT) if x.geom_type == 'LineString']
                zones = []
                for x in parts:
                    sN = x.project(ref); np_ = x.interpolate(sN)
                    t = np.array(x.interpolate(min(x.length, sN + 2)).coords[0])[:2] - np.array(x.interpolate(max(0, sN - 2)).coords[0])[:2]
                    side = np.sign(t[0] * (ref.y - np_.y) - t[1] * (ref.x - np_.x)) or 1.0
                    zones.append(x.buffer(-side * (4 * (hmax + half[i]) + 10), single_sided=True))
                far = unary_union(zones) if zones else None
            if far is not None: cutaway.setdefault(i, []).append(far.difference(M))
            flat[at_start] = True; log.append((i, at_start))
        if g.length < 1e-6: continue
        if not flat: pieces.append(g.buffer(half[i]))
        else:
            body = g.buffer(half[i], cap_style=2)
            for at_start in (True, False):                              # round the ends that were not trimmed
                if not flat.get(at_start): body = body.union(Point(g.coords[0] if at_start else g.coords[-1]).buffer(half[i]))
            for z in cutaway.get(i, []): body = body.difference(z)
            pieces.append(body)
'''
s = s[:a0] + new + s[a1:]
s = s.replace("    pieces, log = [], []", "    pieces, log, cutaway = [], [], {}")
s = s.replace("def road_surface(lines, half, tol=3.0, clip=None, return_ends=False):", "def road_surface(lines, half, tol=3.0, clip=None, return_ends=False, fillet=0.0):")
s = s.replace("    S = unary_union(pieces)\n", "    S = unary_union(pieces)\n    if fillet > 0: S = S.buffer(fillet, join_style=1).buffer(-fillet, join_style=1)      # rounded kerb returns at junction corners\n")
s = s.replace('  - if it ends against a through road (T-branch) -> trimmed / extended exactly to the edge of the through road and given a flat end.\n    The cut is limited to the through road\'s half-width + tolerance, so roads running alongside each other are not eaten;',
              '  - if it ends against a through road (T-branch) -> carried right across the through road (full overlap, no gaps at oblique junctions)\n    and only the part beyond the FAR edge of the through road is cut away, so nothing protrudes;\n  - fillet > 0: junction corners get rounded kerb returns of that radius;')
open(p, 'w', encoding='utf-8').write(s)
# call sites: existing-situation blocks (feet) and design roads (feet)
for f, a, b in (('ml5/blocks_plots.py', "ROAD = road_surface(LN, HW, tol=3 / FT, clip=site)", "ROAD = road_surface(LN, HW, tol=3 / FT, clip=site, fillet=4 / FT)"),
                ('ml4/blocks_plots.py', "ROAD = road_surface(LN, HW, tol=3 / FT, clip=site)", "ROAD = road_surface(LN, HW, tol=3 / FT, clip=site, fillet=4 / FT)"),
                ('toolkit_src/new_stages.py', "SURF = road_surface(list(noded), [wft / 2 for wft in seg_w], tol=3.0, clip=None)", "SURF = road_surface(list(noded), [wft / 2 for wft in seg_w], tol=3.0, clip=None, fillet=15.0)")):
    t = open(f, encoding='utf-8').read(); assert a in t, f; open(f, 'w', encoding='utf-8').write(t.replace(a, b))
print('ok')
