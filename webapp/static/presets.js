// Plot size presets measured on the local plans studied (2026-11-25): sets plot size, block depth (two rows) and block length (whole plots, about 400-500 ft).
(() => {
  const sel = document.getElementById('dPreset'); if (!sel) return;
  const $ = id => document.getElementById(id);
  const setLen = (w) => {
    const L = $('dLen'); if (!L) return;
    const n = Math.max(4, Math.round(480 / w)), v = n * w;
    if (![...L.options].some(o => +o.value === v)) L.add(new Option(`${v} ft (${n} x ${w})`, v));
    L.value = String(v);
  };
  sel.addEventListener('change', () => {
    const v = sel.value;
    if (!v) { $('dPW').value = ''; $('dPL').value = ''; $('dBand').value = '200'; $('dLen').value = '490'; return; }
    const [w, l] = v.split('x').map(Number);
    $('dPW').value = w; $('dPL').value = l; $('dBand').value = String(2 * l); setLen(w);
    ['dPW', 'dPL', 'dBand', 'dLen'].forEach(id => $(id).dispatchEvent(new Event('change', { bubbles: true })));
  });
})();
