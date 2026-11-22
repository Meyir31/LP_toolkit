// LP Toolkit: colourful tool icons (shared by the ribbon in editor.js and the Features group in features.js).
// Colour coding: blue = select / navigate, green = create / add, orange = modify, red = delete / cut, purple = attributes, yellow = measure / map.
const LPI = (() => {
  const K = '#37474F', BL = '#1E88E5', BD = '#0D47A1', GR = '#43A047', GD = '#1B5E20', OR = '#FB8C00', RD = '#E53935', PU = '#8E24AA', YE = '#FDD835', TN = '#FFCC80', RG = '#90A4AE';
  const S = d => `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="${K}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const plus = (x, y, c = GR) => `<circle cx="${x}" cy="${y}" r="4.2" fill="${c}" stroke="#fff" stroke-width="1"/><path d="M${x - 2.2} ${y}h4.4M${x} ${y - 2.2}v4.4" stroke="#fff" stroke-width="1.6"/>`;
  const arrow = `<path d="M5 3l12 8-5.5 1.2L9 18z" fill="${BL}" stroke="${BD}"/><path d="M12 12.5l4 6" stroke="${BD}" stroke-width="2"/>`;
  const bin = `<path d="M6 7l1 13h10l1-13z" fill="${RD}" stroke="#B71C1C"/><path d="M4 7h16" stroke="#B71C1C" stroke-width="2"/><path d="M9 7V4h6v3" stroke="#B71C1C"/><path d="M10 11v6M14 11v6" stroke="#fff"/>`;
  const table = `<rect x="3" y="4" width="18" height="16" rx="2" fill="#fff"/><rect x="3" y="4" width="18" height="5" rx="2" fill="${PU}" stroke="${PU}"/><path d="M9 9v11M3 14.5h18" stroke="${RG}"/><rect x="3" y="4" width="18" height="16" rx="2"/>`;
  const undo = `<path d="M4 9h10a6 6 0 010 12h-3" stroke="${BL}" stroke-width="2.2"/><path d="M9 14L4 9l5-5" stroke="${BL}" stroke-width="2.2"/>`;
  const plotSplit = `<path d="M4 6l8-3 8 3v12l-8 3-8-3z" fill="${TN}"/><path d="M3 21L21 3" stroke="${RD}" stroke-width="2" stroke-dasharray="3 2"/>`;
  const plotMerge = `<rect x="3" y="5" width="8" height="14" fill="${TN}"/><rect x="13" y="5" width="8" height="14" fill="${TN}"/><path d="M8 12h7" stroke="${GR}" stroke-width="2.2"/><path d="M13 9.5l2.5 2.5-2.5 2.5" stroke="${GR}" stroke-width="2.2"/>`;
  return {
    select: S(arrow), fselect: S(arrow),
    clear: S(`<rect x="3" y="3" width="18" height="18" rx="2" stroke="${BL}" stroke-dasharray="3 2" fill="#E3F2FD"/><path d="M9 9l6 6M15 9l-6 6" stroke="${RD}" stroke-width="2.2"/>`),
    create: S(`<path d="M3 20l6-6 5 2 6-10" stroke="${RG}" stroke-width="4"/><path d="M3 20l6-6 5 2 6-10" stroke="#fff" stroke-width="1" stroke-dasharray="2 2"/>${plus(18, 18)}`),
    offset: S(`<path d="M3 8c5-4 13-4 18 0" stroke="${K}" stroke-width="2.2"/><path d="M3 17c5-4 13-4 18 0" stroke="${OR}" stroke-width="2.2" stroke-dasharray="3 2"/><path d="M12 7v5.5M9.8 10.5l2.2 2.2 2.2-2.2" stroke="${BL}" stroke-width="2"/>`),
    extend: S(`<path d="M3 12h9" stroke="${K}" stroke-width="2.4"/><path d="M12 12h6" stroke="${GR}" stroke-width="2.4" stroke-dasharray="2 2"/><path d="M21 4v16" stroke="${RD}" stroke-width="2.6"/><path d="M15 9l3 3-3 3" stroke="${GR}" stroke-width="2"/>`),
    trim: S(`<circle cx="6" cy="7" r="2.7" fill="${RD}" stroke="#B71C1C"/><circle cx="6" cy="17" r="2.7" fill="${RD}" stroke="#B71C1C"/><path d="M8 8.5L20 17M8 15.5L20 7" stroke="${K}" stroke-width="2"/>`),
    split: S(`<path d="M3 12h7" stroke="${BL}" stroke-width="2.6"/><path d="M14 12h7" stroke="${OR}" stroke-width="2.6"/><path d="M12 4v16" stroke="${RD}" stroke-width="1.6" stroke-dasharray="2 2"/>`),
    square: S(`<rect x="4" y="14" width="6" height="6" fill="${YE}" stroke="${OR}"/><path d="M4 20V4" stroke="${PU}" stroke-width="2.4"/><path d="M4 20h16" stroke="${PU}" stroke-width="2.4"/>`),
    attr: S(table), fattr: S(table),
    delete: S(bin), fdelete: S(bin),
    undo: S(undo), fundo: S(undo),
    redo: S(`<path d="M20 9H10a6 6 0 000 12h3" stroke="${BL}" stroke-width="2.2"/><path d="M15 14l5-5-5-5" stroke="${BL}" stroke-width="2.2"/>`),
    snap: S(`<path d="M5 3v8a7 7 0 0014 0V3h-4v8a3 3 0 01-6 0V3z" fill="${RD}" stroke="#B71C1C"/><path d="M5 3h4v3H5zM15 3h4v3h-4z" fill="${RG}" stroke="${K}"/>`),
    measure: S(`<path d="M3 17L17 3l4 4L7 21z" fill="${YE}" stroke="#F57F17"/><path d="M7 13l2 2M10 10l2 2M13 7l2 2" stroke="${K}"/>`),
    redemarcate: S(`<rect x="3" y="4" width="18" height="16" rx="1" fill="#fff"/><path d="M3 4h6v8H3zM9 4h12v8H9z" fill="${TN}"/><path d="M3 12h12v8H3z" fill="#FFE0B2"/><path d="M15 12h6v8h-6z" fill="${TN}"/><path d="M3 12h18M9 4v8M15 12v8" stroke="${OR}" stroke-width="1.8"/><rect x="3" y="4" width="18" height="16" rx="1"/>`),
    psplit: S(plotSplit), fsplit: S(plotSplit),
    pmerge: S(plotMerge), fmerge: S(plotMerge),
    pmap: S(`<path d="M3 6l6-3v15l-6 3z" fill="${GR}" stroke="${GD}"/><path d="M9 3l6 3v15l-6-3z" fill="${YE}" stroke="#F57F17"/><path d="M15 6l6-3v15l-6 3z" fill="${BL}" stroke="${BD}"/>`),
    fcreate: S(`<path d="M3 18l5-12 6 4 5-6" stroke="${GD}" stroke-width="1.8" fill="#C8E6C9"/>${plus(18, 18)}`),
    fvertices: S(`<path d="M4 18L9 5l7 4 4 10z" fill="#BBDEFB" stroke="${BD}"/><rect x="2.5" y="16.5" width="3.2" height="3.2" fill="${RD}" stroke="none"/><rect x="7.5" y="3.5" width="3.2" height="3.2" fill="${RD}" stroke="none"/><rect x="14.5" y="7.5" width="3.2" height="3.2" fill="${RD}" stroke="none"/><rect x="18.5" y="17.5" width="3.2" height="3.2" fill="${RD}" stroke="none"/>`),
    freshape: S(`<path d="M3 19V9l6-5 6 5v10z" fill="#BBDEFB" stroke="${BD}"/><path d="M15 9c4 1 6 4 6 10h-6" stroke="${OR}" stroke-width="2" stroke-dasharray="3 2"/>`),
    box: S(`<rect x="2.5" y="3.5" width="15" height="12" fill="#E3F2FD" stroke="${BL}" stroke-width="1.6" stroke-dasharray="3 2"/><path d="M12 10l9 6-4 1-2 4z" fill="${BL}" stroke="${BD}"/>`),
    fuse: S(`<rect x="3" y="3" width="8" height="8" fill="#DC7C24"/><rect x="13" y="3" width="8" height="8" fill="#73B2FF"/><rect x="3" y="13" width="8" height="8" fill="#FFFF00" stroke="#C00000"/><rect x="13" y="13" width="8" height="8" fill="#00FF00"/>`),
    save: S(`<path d="M4 4h12l4 4v12H4z" fill="${BL}" stroke="${BD}"/><rect x="7" y="4" width="8" height="5" fill="#fff" stroke="${BD}"/><rect x="7" y="13" width="10" height="7" fill="#E3F2FD" stroke="${BD}"/>`),
    discard: S(`<path d="M4 4h12l4 4v12H4z" fill="#ECEFF1" stroke="${K}"/><path d="M8 10l8 8M16 10l-8 8" stroke="${RD}" stroke-width="2.2"/>`),
    edit: S(`<path d="M4 20h4l11-11-4-4L4 16z" fill="${YE}" stroke="#F57F17"/><path d="M15 5l4 4" stroke="${RD}" stroke-width="2.4"/><path d="M4 20l1.2-4 2.8 2.8z" fill="${K}"/>`),
  };
})();
