p = 'toolkit_src/autoroads.py'; s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:70]; s = s.replace(a, b, 1)
# rings: at least two links to the outer roads
rep("    return rings + rows, crosses\n", """    links = []
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
""")
# kept roads cut at a redesign-area edge: extend into the area to the first new road
rep("    # ---- 5. connect: extend local ends to the road centreline / boundary they face; bend sharp arrivals square ----",
"""    # ---- 4b. kept roads cut at a redesign-area edge: carry them into the area to the first new road ----
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
    # ---- 5. connect: extend local ends to the road centreline / boundary they face; bend sharp arrivals square ----""")
open(p, 'w', encoding='utf-8').write(s); print('ok')
