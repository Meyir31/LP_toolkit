p = 'webapp/static/app.js'; s = open(p, encoding='utf-8').read()
i0 = s.index("const USE_COL = {"); i1 = s.index("const results = {};")
s = s[:i0] + r"""// LUSPA colour codes (Revised Zoning Guidelines and Planning Standards 2025, Tables 1 and 2): code -> [name, fill, pattern colour, edge]
const LUSPA = { 'Re': ['Residential', '#DC7C24'], 'Re A': ['Residential Zone A', '#CC7722'], 'Re B': ['Residential Zone B', '#E5AA70'], 'Re C': ['Residential Zone C', '#BB8855'],
  'Re D': ['Residential Zone D', '#98623C'], 'Com': ['Commercial', '#73B2FF'], 'CBD': ['Central Business District', '#2E4DA7'], 'BM': ['Mixed Business / Residential', '#73B2FF', '#FFAA57'],
  'BI': ['Informal Business', '#73B2FF', '#000000'], 'TL': ['Transportation and Logistics', '#D6D6D6', '#000000'], 'CC': ['Civic and Culture', '#FF7F7F'],
  'PW': ['Place of Worship', '#FF7F7F', '#000000'], 'H': ['Health', '#FF0000'], 'BG': ['Government Business', '#FF7F7F', '#000000'], 'T': ['Tourist / Heritage', '#FF0080'],
  'SU': ['Special / Utility', '#FF7F7F', '#000000'], 'InD': ['Industrial', '#F4AFF4'], 'LI': ['Light Industrial', '#E8BEFF'], 'IS': ['Service Industry', '#EE82EE'],
  'Ed': ['Educational', '#FFFF00', null, '#C00000'], 'Ed P': ['Education Zone A: Pre-school and Basic', '#FFFF00', '#000000', '#C00000'], 'PS': ['Public Space', '#00FF00'],
  'CA': ['Conservation', '#32CD32'], 'Ag': ['Agriculture', '#ADFF2F'], 'VAC': ['Open / yard, no building', '#FFFFFF', null, '#9E9E9E'] };
const EXIST_LUSPA = { 'Residential': 'Re', 'Mixed use (shop + residence)': 'BM', 'Commercial / mixed use': 'BM', 'Commercial': 'Com', 'Commercial (hotel)': 'Com', 'Commercial (fuel)': 'Com',
  'Commercial (entertainment)': 'Com', 'Commercial (wholesale / storage)': 'Com', 'Commercial (parking)': 'TL', 'Office': 'Com', 'Market': 'Com', 'Transport terminal': 'TL',
  'Health': 'H', 'Education': 'Ed', 'Religious': 'PW', 'Religious / assembly': 'PW', 'Civic': 'CC', 'Institutional / large commercial (verify)': 'CC', 'Recreation': 'PS',
  'Industrial': 'InD', 'Mixed use (industrial + commercial)': 'IS', 'Mixed use (commercial + industrial)': 'IS', 'Agricultural': 'Ag', 'Open / yard (no building)': 'VAC' };
const DESIGN_LUSPA = { RE: 'Re B', RA: 'Re A', MU: 'BM', BM: 'BM', 'Com A': 'Com', CIV: 'CC', TR: 'TL', PW: 'PW', 'H Po': 'H', 'Ed P': 'Ed P', POS: 'PS', GRN: 'CA', SU: 'SU', '': 'VAC' };
const luspaStyle = (code, base = {}) => { const c = LUSPA[code] || LUSPA.VAC; return { color: c[3] || c[2] || '#222', weight: c[3] ? 2 : c[2] ? 1.6 : .8, dashArray: c[2] && !c[3] ? '4 3' : null, fillColor: c[1], fillOpacity: .85, ...base }; };
const luspaLegend = codes => codes.map(k => { const c = LUSPA[k]; return `<span><i style="background:${c[1]};border-color:${c[3] || c[2] || '#555'};${c[2] ? 'border-style:dashed;border-width:2px' : ''}"></i>${k === 'VAC' ? '' : '<b>' + k + '</b> '}${c[0]}</span>`; }).join('');
// kept for the attribute autocomplete
const USE_COL = Object.fromEntries(Object.keys(EXIST_LUSPA).map(k => [k, LUSPA[EXIST_LUSPA[k]][1]]));
const DES_COL = Object.fromEntries(Object.keys(DESIGN_LUSPA).filter(k => k).map(k => [k, LUSPA[DESIGN_LUSPA[k]][1]]));
""" + s[i1:]
def rep(a, b):
    global s
    assert a in s, a[:80]; s = s.replace(a, b, 1)
rep("      case 'plots': return { color: '#222', weight: .8, fillColor: USE_COL[p.ex_use] || '#ccc', fillOpacity: .75, dashArray: (p.access || '').startsWith('Interior') ? '4 3' : null };",
    "      case 'plots': return luspaStyle(EXIST_LUSPA[p.ex_use] || 'VAC', (p.access || '').startsWith('Interior') ? { dashArray: '2 4' } : {});")
rep("      case 'plots_design': case 'reserves': return { color: '#222', weight: .7, fillColor: DES_COL[p.use] || (p.use ? '#b0bec5' : '#f6e27f'), fillOpacity: .8 };",
    "      case 'plots_design': case 'reserves': return luspaStyle(DESIGN_LUSPA[p.use] || (p.use ? 'CC' : 'Re B'));")
rep("      case 'green': return { color: '#1b5e20', weight: 1, fillColor: '#2e7d32', fillOpacity: .7 };", "      case 'green': return { color: '#1b5e20', weight: 1, fillColor: LUSPA.CA[1], fillOpacity: .7 };")
rep("""    const used = new Set(results[L_.path].getLayers().map(l => l.feature?.properties?.ex_use));
    setMapLegend(Object.entries(USE_COL).filter(([k]) => used.has(k)).map(([k, c]) => `<span><i style="background:${c}"></i>${k}</span>`).join(''));""",
    """    const used = new Set(results[L_.path].getLayers().map(l => EXIST_LUSPA[l.feature?.properties?.ex_use] || 'VAC'));
    setMapLegend('<div class="mini" style="margin-bottom:3px">LUSPA colour codes (2025)</div>' + luspaLegend(Object.keys(LUSPA).filter(k => used.has(k))));""")
rep("  const leg = kinds.has('plots') ? USE_COL : kinds.has('plots_design') ? { 'Residential B (RE)': DES_COL.RE, 'Residential A (RA)': DES_COL.RA, 'School': DES_COL['Ed P'], 'Health': DES_COL['H Po'], 'Worship': DES_COL.PW, 'Civic': DES_COL.CIV, 'Open space': DES_COL.POS, 'Commercial': DES_COL['Com A'], 'Sanitary': DES_COL.SA, 'Utility': DES_COL.UT } : {};",
    "  const leg = {};")
rep("  const legHtml = legS + Object.entries(leg).map(([k, c]) => `<span><i style=\"background:${c}\"></i>${k}</span>`).join('');",
    "  const legHtml = legS + (kinds.has('plots_design') ? luspaLegend(['Re A', 'Re B', 'BM', 'Com', 'Ed P', 'H', 'CC', 'PW', 'TL', 'PS', 'CA', 'SU']) : kinds.has('plots') ? luspaLegend(Object.keys(LUSPA)) : '');")
open(p, 'w', encoding='utf-8').write(s); print('ok')
