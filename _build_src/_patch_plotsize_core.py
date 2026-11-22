"""plot size (breadth = frontage FIXW, length = depth DEPTH) and fit / exact modes in the Phase One subdivider (toolkit stage + localplots core)"""
import re, sys
def sub1(s, a, b, p):
    assert s.count(a) == 1, (p, s.count(a), a[:70]); return s.replace(a, b)
for p in sys.argv[1:]:
    s = open(p, encoding='utf-8').read()
    if 'FIXW' in s: print('already', p); continue
    s = sub1(s, "two_rows = depth >= 185 and bool(back)", "two_rows = depth >= 1.85 * DEPTH and bool(back)", p)
    s = sub1(s, "if depth > 260 and not back:", "if depth > 2.6 * DEPTH and not back:", p)
    s = sub1(s, "if depth > 330 and back:", "if depth > 3.3 * DEPTH and back:", p)
    s = sub1(s, "prefer = [80, 75, 70, 65] if on_main else SIZES", "prefer = SIZES if FIXW else ([80, 75, 70, 65] if on_main else SIZES)", p)
    s = sub1(s, "SIZES = [70, 75, 65, 80]", "SIZES = [FIXW] if FIXW else [70, 75, 65, 80]", p)
    s = sub1(s, "target = (65 if i in (0, len(w) - 1) else x) * 100 * 0.98", "target = (min(65, x) if i in (0, len(w) - 1) else x) * DEPTH * 0.98", p)
    s = sub1(s, "if between(front, a, cut_line(M, s_new)).area >= target or not split: break", "if MODE == 'exact' or between(front, a, cut_line(M, s_new)).area >= target or not split: break", p)
    s = sub1(s, "if M.length - pos[-1] < 60 and len(pos) > 2: pos.pop()", "if MODE != 'exact' and M.length - pos[-1] < 60 and len(pos) > 2: pos.pop()", p)
    s = sub1(s, "front = blk.intersection(ext(F).buffer(DEPTH + 1, cap_style=2)) if split else blk", "front = blk.intersection(ext(F).buffer(depth + 1, cap_style=2)) if split else blk", p)
    s = sub1(s, "subdivide_row(blk, F, bi, depth=DEPTH if two_rows else depth / 2, split=two_rows)", "subdivide_row(blk, F, bi, depth=(depth / 2 if MODE == 'fit' else DEPTH) if two_rows else depth / 2, split=two_rows)", p)
    # fixed frontage: plan_sizes
    m = re.search(r"\n( *)if L < 2 \* 65: return \[L\], 'single'\n", s); ind = m.group(1)
    s = s.replace(m.group(0), f"""
{ind}if FIXW:                                                           # the planner's plot breadth: fit = leftover to the two end plots, exact = leftover strip left open
{ind}    n = max(1, int(L // FIXW)); r = L - n * FIXW
{ind}    if MODE == 'exact': return [FIXW] * n + ([r] if r > 1 else []), f'{{FIXW:.0f}} ft exact (leftover {{r:.0f}} ft open)'
{ind}    if n == 1: return [L], 'single'
{ind}    w = [FIXW] * n; w[0] += r / 2; w[-1] += r / 2; return w, f'{{FIXW:.0f}} ft (ends +{{r / 2:.0f}})'
{ind}if L < 2 * 65: return [L], 'single'
""", 1)
    # exact mode: the leftover piece at the end of a row is left open
    m = re.search(r"\n( *)for q in parts: plots\.append\(dict\(geometry=q, block=bi, how=how, row=", s); ind = m.group(1)
    s = s.replace(m.group(0), f"""
{ind}if MODE == 'exact' and FIXW and len(w) > len(pos):                 # the last piece is the leftover (narrower than the breadth): open space
{ind}    lo = [q for q in parts if M.project(q.representative_point()) > pos[-1]]; parts = [q for q in parts if q not in lo]
{ind}    for q in lo: reserve(q, bi, 'leftover (exact plot size)')
{ind}for q in parts: plots.append(dict(geometry=q, block=bi, how=how, row=""", 1)
    # exact mode: rows exactly DEPTH deep; what is left between / behind them is open
    m = re.search(r"\n( *)subdivide_row\(blk, F, bi, depth=\(depth / 2 if MODE", s); ind = m.group(1)
    s = s.replace(m.group(0), f"""
{ind}if MODE == 'exact' and depth > (2 * DEPTH if two_rows else DEPTH) + 10:
{ind}    strip = blk.intersection(ext(F).buffer(DEPTH, cap_style=2)); strip = max(shapely.get_parts(strip), key=lambda g: g.area)
{ind}    subdivide_row(strip, F, bi, depth=DEPTH / 2); used = strip
{ind}    if two_rows:
{ind}        Bk = max(back, key=lambda x: x.length); sb = blk.difference(strip.buffer(0.05)).intersection(ext(Bk).buffer(DEPTH, cap_style=2))
{ind}        if not sb.is_empty:
{ind}            sb = max(shapely.get_parts(sb), key=lambda g: g.area); subdivide_row(sb, Bk, bi, depth=DEPTH / 2); used = used.union(sb)
{ind}    reserve(blk.difference(used.buffer(0.05)), bi, 'leftover (exact plot size)'); return
{ind}subdivide_row(blk, F, bi, depth=(depth / 2 if MODE""", 1)
    open(p, 'w', encoding='utf-8').write(s); print('patched', p)
