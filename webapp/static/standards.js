// ---- Planning standards repository (LUSPA Revised Zoning Guidelines and Planning Standards, 2025) ----
// Opens from the header "Standards" button, or from a map legend entry (opens that use's standard).
const Standards = (() => {
  let DATA = null, cur = null;
  const ALIAS = { Re: 'neigh', Com: 'mkt', H: 'h_tab', Ed: 'ed_tab', CC: 'bg', InD: 'li', CZ: 'cz', 'H Po': 'h_po', UNC: null, VAC: null };
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  function swatch(it, big) {
    const pc = it.pc || '#000', h = it.hatch;
    const pat = h === 'diag' ? `repeating-linear-gradient(45deg, ${pc} 0 2px, transparent 2px 6px)`
      : h === 'vert' ? `repeating-linear-gradient(90deg, ${pc} 0 2px, transparent 2px 6px)`
      : h === 'horiz' ? `repeating-linear-gradient(0deg, ${pc} 0 2px, transparent 2px 6px)`
      : h === 'cross' ? `repeating-linear-gradient(0deg, ${pc} 0 1px, transparent 1px 5px), repeating-linear-gradient(90deg, ${pc} 0 1px, transparent 1px 5px)`
      : h === 'dots' ? `radial-gradient(${pc} 1px, transparent 1.6px) 0 0 / 5px 5px` : '';
    const tri = h === 'tri' ? `<b style="font-size:${big ? 11 : 7}px;line-height:1;color:${pc}">&#9650;</b>` : '';
    return `<i class="sw${big ? ' big' : ''}" style="background:${pat ? pat + ',' : ''}${it.fill};border:${it.edge ? 2 : 1}px ${it.dash ? 'dashed' : 'solid'} ${it.edge || '#555'}">${tri}</i>`;
  }
  // ---------- residential drawings: plot plan, height, all zones to scale ----------
  const FTM = 0.3048, shade = (hex, f) => { const n = parseInt(hex.slice(1), 16), c = [n >> 16, n >> 8 & 255, n & 255].map(x => Math.round(x + (255 - x) * f)); return `rgb(${c})`; };
  function geom(v) {
    const W = v.w * FTM, D = v.d * FTM, A = W * D, eW = W - 2 * v.side, eD = D - v.front - v.rear, eA = eW * eD;
    const F = Math.min(v.cov / 100 * A, eA), k = Math.sqrt(F / eA);
    return { W, D, A, eW, eD, eA, F, fw: eW * k, fd: eD * k, limited: v.cov / 100 * A > eA };
  }
  function plotSvg(v, g, fill, s, x0, y0) {   // front (road) at the bottom
    const w = g.W * s, h = g.D * s, ex = x0 + v.side * s, ey = y0 + v.rear * s;
    const fx = x0 + (w - g.fw * s) / 2, fy = y0 + h - v.front * s - g.fd * s;
    return `<rect x="${x0}" y="${y0}" width="${w}" height="${h}" fill="${shade(fill, .78)}" stroke="#333" stroke-width="1.5"/>
      <rect x="${ex}" y="${ey}" width="${g.eW * s}" height="${g.eD * s}" fill="none" stroke="#c62828" stroke-width="1.2" stroke-dasharray="5 3"/>
      <rect x="${fx}" y="${fy}" width="${g.fw * s}" height="${g.fd * s}" fill="${fill}" stroke="#333" stroke-width="1"/>`;
  }
  function planViz(v, fill) {
    const g = geom(v), s = Math.min(230 / g.W, 250 / g.D), x0 = 62, y0 = 34, w = g.W * s, h = g.D * s, W = x0 + w + 70, H = y0 + h + 58;
    const lab = (x, y, t, a = 'middle', r = 0) => `<text x="${x}" y="${y}" text-anchor="${a}" ${r ? `transform="rotate(${r} ${x} ${y})"` : ''}>${t}</text>`;
    const dimW = v.nodim ? '1 acre (no set dimensions; drawn square)' : `${v.w} ft (${g.W.toFixed(1)} m)`;
    return `<svg viewBox="0 0 ${W} ${H}" class="vz" style="max-width:${W}px">
      ${lab(x0 + w / 2, 18, dimW)}<line x1="${x0}" y1="24" x2="${x0 + w}" y2="24" class="dim"/>
      ${v.nodim ? '' : lab(x0 - 30, y0 + h / 2, `${v.d} ft (${g.D.toFixed(1)} m)`, 'middle', -90)}<line x1="${x0 - 22}" y1="${y0}" x2="${x0 - 22}" y2="${y0 + h}" class="dim"/>
      ${plotSvg(v, g, fill, s, x0, y0)}
      ${lab(x0 + w / 2, y0 + v.rear * s / 2 + 4, `rear ${v.rear} m`)}
      ${lab(x0 + w / 2, y0 + h - v.front * s / 2 + 4, `front ${v.front} m`)}
      ${lab(x0 + w + 6, y0 + h / 2 + 4, `side ${v.side} m`, 'start')}
      <rect x="${x0 - 10}" y="${y0 + h + 6}" width="${w + 20}" height="20" fill="#9e9e9e"/>${lab(x0 + w / 2, y0 + h + 20, 'ROAD (front)')}
      ${lab(x0 + w / 2, y0 + h + 44, `largest footprint ${Math.round(g.F)} m2`)}</svg>`;
  }
  function elevViz(v, fill) {
    const g = geom(v), sw = Math.min(150 / g.fw, 2.6), bw = Math.max(40, g.fw * sw), sh = 22, n = v.mode === 'min' ? v.st + 2 : v.st, H = 30 + n * sh + 40, x0 = 40, gy = 20 + n * sh + 10;
    let b = '';
    for (let i = 0; i < n; i++) {
      const extra = v.mode === 'min' ? i >= v.st : v.mode === 'range' && i >= v.st0;
      b += `<rect x="${x0}" y="${gy - (i + 1) * sh}" width="${bw}" height="${sh}" fill="${extra ? shade(fill, .7) : fill}" stroke="#333" ${extra ? 'stroke-dasharray="4 3"' : ''}/>`;
    }
    const t = v.mode === 'min' ? `min ${v.st} storeys, may go higher` : v.mode === 'range' ? `${v.st0} to ${v.st} storeys` : `up to ${v.st} storeys`;
    return `<svg viewBox="0 0 ${x0 + bw + 210} ${H}" class="vz" style="max-width:${x0 + bw + 210}px">${b}
      <line x1="10" y1="${gy}" x2="${x0 + bw + 30}" y2="${gy}" stroke="#333" stroke-width="2"/>
      ${v.mode === 'min' ? `<text x="${x0 + bw / 2}" y="${gy - n * sh - 4}" text-anchor="middle">&#9650;</text>` : ''}
      <text x="${x0 + bw + 10}" y="${gy - v.st * sh / 2}">${t}</text><text x="${x0 + bw + 10}" y="${gy - v.st * sh / 2 + 15}" class="mini">about ${v.st * 3} m at 3 m a storey</text></svg>`;
  }
  function facts(v) {
    const g = geom(v), ac = g.A / 4046.86, eff = g.F / g.A * 100;
    return `<table class="stab kv vzf"><tr><th>Plot area</th><td>${Math.round(g.A)} m2 (${ac.toFixed(3)} acre)</td></tr>
      <tr><th>Plots per acre</th><td>${(1 / ac).toFixed(1)} (plots only, before roads)</td></tr>
      <tr><th>Buildable area inside setbacks</th><td>${Math.round(g.eA)} m2 (${Math.round(g.eA / g.A * 100)}% of the plot)</td></tr>
      <tr><th>Coverage allowed</th><td>${v.cov}% = ${Math.round(v.cov / 100 * g.A)} m2</td></tr>
      <tr><th>Largest ground floor</th><td><b>${Math.round(g.F)} m2 (${Math.round(eff)}%)</b></td></tr>
      <tr><th>Max floor area (all storeys)</th><td>${Math.round(g.F * v.st)} m2${v.mode === 'min' ? ' at the minimum height' : ''}</td></tr></table>
      ${g.limited ? `<div class="vznote">Setbacks govern here: ${v.cov}% coverage is allowed, but the setbacks leave room for only ${Math.round(eff)}% of the plot.</div>` : ''}`;
  }
  function cmpViz(curId) {
    const its = DATA.items.filter(x => x.viz), gs = its.map(x => geom(x.viz)), gap = 26, s = Math.min(3.4, (900 - gap * its.length) / gs.reduce((a, g) => a + g.W, 0));
    const maxD = Math.max(...gs.map(g => g.D)) * s, base = 14 + maxD; let x = 14, out = '';
    its.forEach((it, i) => { const g = gs[i], on = it.id === curId;
      out += plotSvg(it.viz, g, it.viz.fill || it.fill, s, x, base - g.D * s) + (on ? `<rect x="${x - 4}" y="${base - g.D * s - 4}" width="${g.W * s + 8}" height="${g.D * s + 8}" fill="none" stroke="#1f5f8b" stroke-width="3"/>` : '') +
        `<text x="${x + g.W * s / 2}" y="${base + 36}" text-anchor="middle" font-weight="700">${it.code}</text><text x="${x + g.W * s / 2}" y="${base + 51}" text-anchor="middle" class="mini">${it.viz.nodim ? '1 acre' : it.viz.w + ' x ' + it.viz.d + ' ft'}</text>`;
      x += g.W * s + gap; });
    return `<svg viewBox="0 0 ${x} ${base + 60}" class="vz" style="max-width:${x}px"><rect x="0" y="${base + 4}" width="${x}" height="16" fill="#9e9e9e"/><text x="${x / 2}" y="${base + 16}" text-anchor="middle">ROAD</text>${out}</svg>`;
  }
  const VZLEG = `<div class="vzleg"><span><i style="background:#eee;border:1.5px solid #333"></i>plot</span><span><i style="border:1.2px dashed #c62828"></i>setback line (buildable area)</span><span><i style="background:#888;border:1px solid #333"></i>largest footprint allowed</span></div>`;
  function vizHtml(it) {
    if (it.viz) return `<h4>The standard on one plot</h4>${VZLEG}<div class="vzrow"><div>${planViz(it.viz, it.viz.fill || it.fill)}</div><div>${elevViz(it.viz, it.viz.fill || it.fill)}${facts(it.viz)}</div></div>
      <h4>All residential plots to the same scale</h4>${cmpViz(it.id)}`;
    if (it.vizcmp) return `<h4>Residential plots to the same scale</h4>${VZLEG}${cmpViz()}`;
    return '';
  }
  async function load() { if (!DATA) DATA = await (await fetch('/static/standards/standards.json')).json(); return DATA; }
  function list(q) {
    q = (q || '').toLowerCase().trim();
    const hit = it => !q || [it.code, it.name, it.group, it.intent, ...(it.permitted || []), ...(it.std || []).flat(), ...(it.tables || []).flatMap(t => t.rows.flat())].join(' ').toLowerCase().includes(q);
    $('#stdList').innerHTML = DATA.groups.map(g => {
      const its = DATA.items.filter(it => it.group === g && hit(it)); if (!its.length) return '';
      return `<div class="sg">${esc(g)}</div>` + its.map(it => `<a data-id="${it.id}" class="${cur === it.id ? 'on' : ''}">${swatch(it)}<b>${esc(it.code)}</b> ${esc(it.name)}</a>`).join('');
    }).join('') || '<div class="mini" style="padding:10px">Nothing matches.</div>';
    $('#stdList').querySelectorAll('a').forEach(a => a.onclick = () => show(a.dataset.id));
  }
  const ul = (t, a, cls) => a?.length ? `<div class="sbox ${cls}"><h4>${t}</h4><ul>${a.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>` : '';
  function show(id) {
    const it = DATA.items.find(x => x.id === id); if (!it) return; cur = id;
    $('#stdList').querySelectorAll('a').forEach(a => a.classList.toggle('on', a.dataset.id === id));
    const tab = t => `<h4>${esc(t.title)}</h4><table class="stab"><tr>${t.head.map(h => `<th>${esc(h)}</th>`).join('')}</tr>${t.rows.map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</table>`;
    $('#stdBody').innerHTML = `<div class="shead">${swatch(it, true)}<div><h3>${it.code ? esc(it.code) + ': ' : ''}${esc(it.name)}</h3>
        <div class="mini">${esc(it.group)}${it.page ? ' &middot; Guidelines p. ' + it.page : ''}</div></div></div>
      ${it.intent ? `<p class="sint">${esc(it.intent)}</p>` : ''}
      ${vizHtml(it)}
      ${it.std ? `<h4>Key standards</h4><table class="stab kv">${it.std.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('')}</table>` : ''}
      ${(it.tables || []).map(tab).join('')}
      ${it.permitted || it.prohibited ? `<div class="scols">${ul('Permitted uses', it.permitted, 'ok')}${ul('Prohibited uses', it.prohibited, 'no')}</div>` : ''}
      ${(it.img || []).map(f => `<figure><img loading="lazy" src="/static/standards/img/${f}"><figcaption>${esc(it.cap || '')}</figcaption></figure>`).join('')}`;
    $('#stdBody').scrollTop = 0;
  }
  async function open(code) {
    $('#stdDlg').hidden = false; if (code) $('#stdQ').value = '';
    if (!DATA) $('#stdBody').innerHTML = '<p class="mini">Loading the standards...</p>';
    await load(); list($('#stdQ').value);
    let id = code && (code in ALIAS ? ALIAS[code] : (DATA.items.find(x => x.code === code) || {}).id);
    show(id || cur || DATA.items[0].id);
  }
  const wire = () => {
    $('#stdBtn').onclick = () => open();
    $('#stdX').onclick = () => $('#stdDlg').hidden = true;
    $('#stdDlg').onclick = e => { if (e.target.id === 'stdDlg') $('#stdDlg').hidden = true; };
    $('#stdQ').oninput = e => list(e.target.value);
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('#stdDlg').hidden) $('#stdDlg').hidden = true; });
    // legend entries open the standard for that use
    document.addEventListener('click', e => { const s = e.target.closest('[data-luspa]'); if (s) open(s.dataset.luspa); });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire); else wire();
  return { open };
})();
