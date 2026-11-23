// About LP Toolkit / Urban GeoPlan (2026-11-23): what the toolkit does and who develops it. The Urban GeoPlan company logo is
// /static/brand/logo.png (put the logo file there); until it is there the Urban GeoPlan mark (brand/ugp-mark.svg) stands in.
(() => {
  const html = `
  <div class="about">
    <div class="ab-head">
      <img class="ab-logo" src="/static/brand/logo.png" alt="Urban GeoPlan" onerror="this.onerror=null;this.src='/static/brand/ugp-mark.svg'">
      <div><h2>LP Toolkit</h2><div class="ab-sub">Local plan preparation &middot; developed by <b>Urban GeoPlan</b></div></div>
    </div>
    <h3>What it does</h3>
    <p>LP Toolkit prepares local plans from a site boundary, following the LUSPA Zoning Guidelines and Planning Standards (2025)
    and the lessons of approved Ghanaian local plans.</p>
    <ul>
      <li><b>Site analysis:</b> terrain, contours, slope classes, streams, steep-slope reserve, existing roads and buildings.</li>
      <li><b>Road layout:</b> the planner's roads, or a designed layout to the road hierarchy and junction rules, ready to edit.</li>
      <li><b>Plot subdivision:</b> standard plots in two-row blocks, on straight and curved roads.</li>
      <li><b>Facilities and land use:</b> the facility programme for the population, suitability analysis for siting, and every
      facility fitted into the road blocks and spread out to serve the whole neighbourhood.</li>
      <li><b>Checks and outputs:</b> a design audit, maps, GIS layers in any Ghana coordinate system, and tables.</li>
      <li><b>Existing areas:</b> buildings, roads, plots and land use mapped from imagery for upgrading plans.</li>
    </ul>
    <h3>About Urban GeoPlan</h3>
    <p><b>Urban GeoPlan</b> is a geospatial and urban planning initiative in Ghana focused on spatial analytics, urban planning
    and digital mapping solutions. It brings planning practice and geospatial technology together so that the places people
    live in are planned with good data, clear standards and modern tools.</p>
    <ul>
      <li><b>Spatial analytics:</b> site and land suitability, terrain and environmental analysis, and evidence for planning decisions.</li>
      <li><b>Urban planning:</b> local plans, structure plans and layouts prepared to the LUSPA standards, from greenfield
      extensions to the upgrading of existing settlements.</li>
      <li><b>Digital mapping:</b> base maps, building and road mapping from imagery, and GIS data ready for planning authorities.</li>
    </ul>
    <p>LP Toolkit is developed and maintained by Urban GeoPlan to make local plan preparation faster, consistent and
    standards-based.</p>
    <div class="ab-foot">&copy; ${new Date().getFullYear()} Urban GeoPlan. All rights reserved.</div>
  </div>`;
  const open = () => { const b = document.getElementById('mBody'), m = document.getElementById('modal'); if (!b || !m) return; b.innerHTML = html; m.hidden = false; };
  const btn = document.getElementById('aboutBtn'); if (btn) btn.onclick = open;
  window.LP_ABOUT = open;
})();
