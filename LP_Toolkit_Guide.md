# LP Toolkit: local plan preparation guide

LP Toolkit is developed and maintained by **Urban GeoPlan**, a geospatial and urban planning initiative in Ghana focused on spatial analytics, urban planning and digital mapping solutions.

Everything learned while preparing the test local plans (test.kml, Tests 2 to 5, Obusomase, Phase One, STMA scheme study) in one place.
This guide is printed by `python lp_toolkit.py guide` and is also written next to the script as `LP_Toolkit_Guide.md`.

## 1. What the toolkit does

Two workflows, each a chain of stages that read and write files in one output folder.

**A. Existing situation (upgrading areas, built-up land).** Run with `existing`.

| Stage | What it does | Main outputs |
|---|---|---|
| fetch | Esri World Imagery z19 (0.3 m), OSM buildings / roads / POIs, Microsoft footprints, building database | `_work/img_z19_3857.tif`, `_work/osm_*.gpkg`, `_work/ms_buildings.gpkg` |
| sam | Segment Anything (vit_b) masks over the image in 1024 px tiles, 160 px overlap | `_work/tiles/*.pkl` |
| digitize | Mask classification (roof, tree, vehicle, road, bare ground, foundation), duplicate and container removal, orthogonal outlines, wall lines | `<P>Buildings.shp`, `<P>Walls.shp` |
| compare | Check against OSM + Microsoft: shift the reference onto the image, merge split roofs, keep the outline that fits roof edges, add missed roofs | `<P>Buildings_corrected.shp`, `<P>comparison_report.json` |
| clean | Drop vehicles, vegetation, bare ground, blobs; flag foundations; final walls | `<P>Buildings_final.shp`, `<P>Walls_final.shp`, `<P>digitizing_summary.xlsx` |
| database | Check against the building database (Google / OSM / Microsoft with occupancy): split our blobs, swap better outlines, add missing buildings, attach occupancy and height | `<P>Buildings_final.shp` (backup `_pre_obm`), `<P>database_check_report.json` |
| roads | Carriageway width per road measured on the image; walls on the carriageway removed | `<P>Carriageways.shp` |
| landuse | Road reserves (building line to building line), existing use per building (OSM tag, then database occupancy, then rules), vacant land | `<P>Roads_existing.shp`, `<P>Existing_land_use_buildings.shp`, `<P>Vacant_open_land.shp` |
| reserves | Road centrelines realigned to the image; reserves re-measured; pinch points | `<P>Road_pinch_points.shp` |
| trees | Continuous tree belt / drain corridor from the image (its own land use) | `<P>Tree_belt_raw.shp` |
| blocks | Road surface (carriageway + 2 m footways) and blocks | `<P>Blocks_existing.shp`, `<P>Road_surface.shp` |
| plots | Existing plot subdivision by the halving rule (section 4) | `<P>Plots_existing.shp`, `<P>Tree_belt_existing.shp` |
| map | Existing land use map and tables | `<P>Existing_land_use_map.png`, `<P>Existing_land_use_tables.xlsx` |
| footpaths | OPTIONAL TRIAL: footpaths from open space between buildings (not reliable in dense cores) | `<P>Footpaths_TRIAL.shp` |
| proposals | OPTIONAL: upgrading proposals (mixed-use corridor, greenway, pocket parks, refuse points, facility gaps). Only when the user asks for proposals | `<P>Upgrading_plan_*.{png,xlsx}` |

**B. New layout (greenfield local plan).** Run with `design`.

| Stage | What it does |
|---|---|
| site | Imagery and Copernicus 30 m DEM warped to EPSG:2136, buildings from the database, site analysis map |
| roads | Road layout, three options: (1) `--roads file`: the planner's centrelines (with `width_ft`); (2) `--roads auto`: the toolkit designs the roads from the rules in section 6; (3) `--roads draft`: the toolkit drafts `<P>Roads_draft.shp`, the planner edits it and reruns with `--roads <edited> --from roads`. Then reserves (T-branch ends trimmed), blocks and the concept file |
| subdivide | Plots by the Phase One rule (section 5) |
| landuse | Facility programme (LUSPA + STMA rates and site shapes, section 7) |
| audit | Design audit: every flaw with location and suggested fix (section 8). Run after every design |

**Web app.** `run_webapp.bat` opens the same workflows in the browser (http://localhost:5050; `run_webapp.bat --lan` lets other computers on the office network open it). Projects are kept in `D:/Work/2026/Machine Learning/LP_Projects/`. Draw or upload the site, roads (with widths), existing roads and streams on the satellite map; choose the road option; run with a live log; view the results as map layers (plots by use, audit findings) and download everything as a zip. The header buttons open this Guide, the About box (what the toolkit does, Urban GeoPlan), the 3D view and the LUSPA standards.

Web app tools (ribbon tabs Project, Map, Edit, Design, Analysis, View):

| Tool | What it does |
|---|---|
| Contents | Every layer grouped (Land use and plots, Roads, Buildings, Terrain and environment, Checks) with a tick box to show / hide it, including the roads you drew; drag to change the drawing order. Right-click a layer (or its zoom button) for Zoom to layer; Zoom to selection on the Map tab |
| Navigation | Mouse wheel zooms in half steps; hold **Shift** and scroll to zoom in fine steps |
| Labels | Map tab: labels on / off and the attribute to show (use, name, area ...), with overlap avoidance |
| Angles | Map tab: show / hide the junction angle marks on the roads |
| Select | Works on every layer: a click picks the line or point under it first, then the smallest area (plot, facility, block, road reserve), terrain layers last. Hidden layers are never picked: untick a layer to reach what is under it. Shift + click adds to the selection |
| Delete | Deletes the selection on any editable layer (ribbon Delete or the Delete key); one undo step per edit |
| Change use | Gives selected plots a new use; your changes are kept when the plan is updated (use_overrides.geojson) |
| Coordinate system | Project tab: any coordinate system that covers Ghana (Ghana National Grid ft, Ghana Metre Grid, UTM 30N / 31N, WGS 84 ...). Changes the coordinates shown and the exported files; the work itself stays in EPSG:2136 |
| Facilities and services | The facility checklist (section 7) |
| Suitability | Where a facility could go (section 7): heat map and the best sites; Accept, Reject or Relocate each one |
| Fit roads | After accepting a suitability site on a designed plan: the roads are adjusted slightly around it (section 7) |
| 3D view | Terrain, land use (open spaces included) and buildings by height |

**Site analysis comes first.** The `site` stage prepares the terrain before any road is drawn: Copernicus 30 m DEM, contours at an interval adapted to the relief (1, 2, 5, 10 m...), slope in percent, slope classes (flat 0-5%, gentle 5-10%, moderate 10-18%, steep 18-30%: no roads straight downhill, very steep > 30%: keep green) and the steep-slope reserve (slopes >= `--steep` %, default 30, pieces >= 0.5 ac kept green and excluded from blocks). **Rivers check (2026-11-25):** after the satellite image is downloaded, the site is checked against the rivers database (all of Africa, OpenStreetMap waterways): every river, stream, canal, drain or ditch within 500 m is listed (how many cross the site, metres inside, names, nearest distance), drawn in blue with a white edge on both panels of `<P>Site_analysis.png` and saved as the map layer "Rivers and streams (database)" (dashed = seasonal / intermittent). Look at them on the image: the database can miss a small stream or carry an old channel. The ones the live OpenStreetMap download did not return are added to `_work/osm_water.gpkg`, so "Design the roads for me" keeps them in a green reserve: each side 165 ft (50 m) for a river, 110 ft for a stream or canal, 30 ft for a drain, 15 ft for a ditch, unless the planner sets the buffer. Outputs: `<P>Contours.shp`, `<P>Slope_classes.shp`, `<P>Slope_percent.tif`, `<P>Steep_slope_reserve.shp`, `<P>Rivers_database.shp`, `<P>Rivers_check.json`, `<P>Terrain_summary.json`, `<P>Site_analysis.png`, map overlays. In the web app: "Prepare site analysis", then review the terrain layers before planning roads.

**Three road patterns** (`--pattern grid | curvilinear | ringband`; `--roads draft` drafts all three and compares them in `<P>Roads_patterns.png/.json`):
- Grid iron: straight two-row blocks along the parcel's main road edge.
- Curvilinear: rows are nested parallel curves of the parcel's contour line, 230 ft apart; cross roads are normals to that curve (square to every parallel). Follows the user's nested-curve rule and the Tokunaso / Beposo curved distributors. On steep sites the parallels drift off the true contour away from the centre line, so check the steep-road figure.
- Ring and band: the user's N1 method: a 200 ft band of plots along the parcel edges behind a 30 ft ring road with rounded corners, an inner grid in the core, cross roads continued through the ring to the outer roads (4-way).
All patterns keep the stream and steep-slope reserves green and are scored for road length steeper than 18%. Obusomase (hilly, 161 m relief): grid 1,382 plots / 4.9 km steep road; curvilinear 1,361 / 5.2 km; ring and band 1,411 / 4.8 km (suggested).

The automatic road layout (option 2) keeps existing roads on their alignment and carries them into the site, splits parcels over 35 ac with 40 ft collectors, lays a grid in each parcel along its highest-order road edge (30 ft roads 230 ft apart for two 100 ft plot rows, cross roads 520 ft apart for seven 70 ft plots), tries several grid offsets and orientations and keeps the one with the most standard blocks and fewest building conflicts, and bends sharp arrivals square. It is a draft: on Test 3 it gave 437 residential plots (80% standard) but 10 high audit findings (junction angles, staggered T junctions) against 0 for the hand-tuned layout. Always review the audit, and prefer option 3 (draft and edit) for real plans.

`<P>` is the file prefix (the site name without spaces, for example `Test5_`). Every stage can be re-run alone (`--only`) or from a point onwards (`--from`).

## 2. Data sources and how to get them

| Source | Use | Notes |
|---|---|---|
| Satellite imagery (contextily, zoom 19): Google satellite by default (user choice 2026-11-17, Esri kept dropping connections), Esri World Imagery as the fallback (`--imagery esri` to prefer Esri) | Digitizing, checks, map backgrounds | 0.3 m/px at 5.5 N; 8 retries per tile, then a slow single-connection pass, then the other source. Google's terms allow its imagery only through official Google tools: fine for internal planning, use Esri or licensed imagery for published maps. The digitizing colour rules were calibrated on Esri (green cast): check the first Google runs against the building database |
| **Building database** `D:/Work/2026/Data` | Footprints, occupancy, storey height | One GeoPackage per level-6 quadkey tile, layer `building`, EPSG:4326, ODbL. Tiles on disk: 033331, 033333 (Accra / south-east, 4.1 M buildings), 122220. Fields: id, occupancy (GEM taxonomy), height (`HBET:1-5` = 1 to 5 storeys), floorspace (rare), source_id (0 OSM, 1 Google Open Buildings, 2 Microsoft). Occupancy is good where OSM is rich (Osu 78% known), almost all UNK in indigenous cores (La). The `Ghana buildings.gdb` beside it is an empty ArcGIS project geodatabase |
| OSM via Overpass | Roads (with names and class), POI tags, buildings | Overpass servers are often overloaded (502/504). The toolkit tries overpass-api.de, kumi, private.coffee, mail.ru, then falls back to the main OSM API `/api/0.6/map?bbox=` (works for sites up to about 0.25 sq deg / 50,000 nodes) |
| **Cadastral plots database** `D:/Work/2026/Data/cadastre_accra.gpkg` | Surveyed plot boundaries for existing-area demarcation (section 4, step 8) | From `D:/Work/2026/Data/COLLESUA NEW 1/COLLESUA NEW 1.dwg` (AutoCAD 2007, no CRS stored; Ghana National Grid ft, EPSG:2136), exported with ArcGIS Pro; plot layers 0LOT, 0LOT1, 0DIST01-04, 0FOB, 0FOBIL, 0SEC204, 0CHRIS noded and polygonised, duplicates between layers dropped. Layers `parcels` (181,934: parcel_id, layer, area_ac, front_ft, depth_ft; median 0.19 ac), `lines` (651,316), `labels` (sections, place names, survey numbers). Greater Accra only. Loader `cadastre_load()` |
| **Rivers database** `D:/Work/2026/Data/rivers_africa.gpkg` | Rivers, streams, canals, drains and ditches in and near the site (site analysis, green reserve in the road design) | OpenStreetMap waterways for Africa, 1,329,371 lines, from `D:/Work/2026/Data/Rivers_ Africa/Rivers.shp` (1.1 GB, converted once to an R-tree indexed GeoPackage, layer `rivers`, EPSG:4326, about 0.02 s per site). Fields: osm_id, name, waterway, intermittent, seasonal, tunnel, width. Loader `rivers_load()`, check `river_check()` |
| Microsoft Global ML Building Footprints | Reference footprints | `dataset-links.csv` + level-9 quadkey tile (Accra = 033333111); cached in `LP_Toolkit/cache/ms` |
| Copernicus DEM 30 m (AWS) | Terrain, slope, drainage, facility siting | `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N05_00_W001_00_DEM/...` (tile by integer lat/lon) |
| STMA scheme study | Learned plot / block / road / facility statistics | `D:/Work/2026/Machine Learning/Results_STMA_Schemes/STMA_Scheme_Design_Rules.md` (section 7) |
| User's local plans | Layout patterns | `All Scaned Maps Arranged` root: Tokunaso (sections A/B/C), Beposo extension, Prestea-Brumasi industrial park, Wassa Mampong (Fig. 10), Cosmax/Hemax LP1 |
| LUSPA training deck | Design principles and flaws | "LOCAL PLAN PREPARATION II.pptx" slides 40 to 55 (section 8) |
| Zoning Guidelines and Planning Standards (LUSPA 2025) | Governing standards | Govern wherever the past schemes differ (for example 30 ft minimum access road) |

Coordinate system for all planning work: **EPSG:2136 (Ghana National Grid, Gold Coast feet)**. 1 ft = 0.3048 m; 1 acre = 43,560 sq ft.

Privacy: never send the user's name, e-mail or project names to outside services. Use the generic user agent `gis-planning-client`.

## 3. Digitizing from imagery: settings that worked

- SAM vit_b checkpoint `models/sam_vit_b_01ec64.pth`, `points_per_side=48`, `pred_iou_thresh=0.82`, `stability_score_thresh=0.88`, `min_mask_region_area=50`. About 3 minutes per 1024 px tile on CPU (16 threads); a 55 ac site is 12 tiles, 163 ac is 25 tiles. The computer must not sleep during the run (tiles already done are skipped on restart).
- Classification rules (per mask, cropped to its bounding box for speed): drop under 9 m2; vehicle = small and elongated; over 2,500 m2 = yard / block; tree if (green > 18 and bright < 115) or (green > 14 and sat > 0.33 and bright < 110), calibrated for the green cast of Esri imagery; foundation = grey (sat < 0.10), many internal edges (edge > 0.22), bright 105 to 185, area > 40, texture > 25.
- Duplicate removal only between masks of similar size (ratio > 0.5), otherwise roofs inside compounds disappear. Compound outlines (containers) are removed.
- Outlines: rectangle if fill >= 0.85, else orthogonalized.
- Walls: Sato ridge filter, skeleton, probabilistic Hough, segments off roofs and off road surface, collinear pieces joined. Interior compound walls are incomplete.
- Foundations cannot be told apart from flat grey roofs reliably: they are flagged "possible uncompleted / foundation - verify", not dropped.
- Comparison: shift the reference onto the image first (Osu OSM was about 0.6 m off; database about 0.5 to 0.9 m). Merge only when two or more of our pieces sit inside one reference building. On a 1:1 match keep the outline with the higher mean image gradient along it (fits the roof edge).
- **Always check footprints against the building database.** In dense indigenous cores (La) SAM misses many small roofs and Microsoft draws one blob over several houses; Google footprints in the database are far better there. Expected after the database step: Osu 2,223 -> 2,908 buildings; La 1,006 -> 1,785.
- Footpaths in dense cores cannot be mapped reliably from 0.3 m imagery: houses touch and roofs overhang the alleys. Use field GPS, midday drone imagery or local knowledge. The `footpaths` stage is a trial only.

## 4. Existing plot subdivision (upgrading areas)

The user's rule (2026-11-16): **subdivision follows the same principle everywhere. A block 200 ft or 240 ft wide is divided by 2, whether it is straight or curved. Try this before any other method.**

How the toolkit applies it:
1. Blocks = site minus road surface (carriageway buffers + 2 m footways). The tree belt is removed first as its own use.
2. Straight blocks (fill of the minimum rotated rectangle >= 0.72): split along the long axis at the line that cuts the least building (within +-25% of the middle, mild preference for the middle). Blocks narrower than the single-row depth stay one row.
3. Curved or irregular blocks: every point goes to the nearer of the two long opposite frontages (distance field at 0.15 m), so the row line is the curve halfway between them.
4. Plot lines square to the frontage (normal to the curve on curved roads), placed by dynamic programming to cut as little building as possible, with a bonus where a detected wall runs; frontage within the profile range.
5. Block ends: oversized end wedges are re-cut square to the side street they run along (plots facing the side street).
6. Any plot still deeper than the profile maximum is halved again at the line of least building cut, never through a large (> 500 m2, image-confirmed) building. Back plots with no road are flagged `Interior (access lane not mapped - verify)`; plots on the site boundary are `Site edge (road outside site)`.
7. Plot use = the plot's most specific tagged building (OSM tag / database occupancy), else its largest building.
8. **Cadastral drawing (2026-11-25, existing areas only).** Where the site lies in the cadastral plots database (`D:/Work/2026/Data/cadastre_accra.gpkg`, 181,934 surveyed plots of Greater Accra from `COLLESUA NEW 1.dwg`), the drawing is combined with steps 2-6 (user's choice: guide the cuts and compare, not replace):
   - Registration: the drawing is moved by at most 20 ft when that clearly takes its plots off the road surface traced from the image (on-road share down by a third); the shift is reported. Measured: within about 10 ft of the image everywhere tested (Ben 1 none, baku test +5 E / -13 N).
   - Pull: every candidate line (row line, plot cut, halving line) running along a parallel drawing line within 4 ft gets a bonus of 3 per foot followed, larger than the building cut cost, so the surveyed line wins even where it crosses a building (user: flag, keep the drawing).
   - Whole blocks: where at least half of a block's plots already overlap a drawing plot (IoU >= 0.6) and the drawing covers 90% of the block, the block takes the drawing's exact plot lines; slivers under 1,500 sq ft join the neighbour.
   - Compare: every plot gets `cad_match` (matches drawing: IoU >= 0.75 / differs from drawing / not in drawing), `cad_iou`, `cad_id` (parcel_id in the database) and `cad_flag` ("drawing line crosses a building - check"). Outputs `<P>Cadastre_plots.shp` (reference layer), `<P>Cadastre_conflicts.shp` (buildings crossed), `<P>Cadastre_check.json`; web app: Results > "Cadastral drawing" card and two map layers.
   - Test: Ben 1 matches 43 -> 125 of 258 plots; baku test 13 -> 33 of 163 (there the ground plots are mostly half drawing plots, 15 m frontage, so they rightly stay "differs"). `--no-cadastre` switches it off.

Profiles (chosen automatically from the median size of image-digitized buildings, threshold 70 m2, or set with `--profile`):

| Profile | For | Frontage | Single row if block narrower than | Halve plots deeper than | End-wedge re-cut |
|---|---|---|---|---|---|
| planned | Planned / estate areas (Osu) | 12 to 25 m | 45 m | 65 m | area > 1,000 m2 and depth > 50 m |
| compact | Indigenous / compound cores (La) | 9 to 18 m | 30 m | 40 m | area > 500 m2 and depth > 36 m |

Methods that failed and must not be used again: Voronoi partition between buildings (spikes, 115% coverage); piece-level Voronoi rows (diagonal bisectors); band buffers with leftover attachment (spikes); frontage rows plus interior core for superblocks (blobs). The width test for curved blocks uses the equal area and perimeter rectangle on a 6 m simplified outline, never 2A/(P/2).

## 5. New plot subdivision (Phase One rule)

1. Offset the front road line by 100 ft (offset the curve on curved blocks): a 200 ft block becomes two 100 ft halves. Extend the mid line to touch the road lines at both block ends.
2. Cut at the chosen frontage, perpendicular to the mid line, each cut road edge to road edge. On curves size each plot to at least frontage x 100 sq ft, close to the standard dimensions.
3. Measure the whole block length first. **Only the first and last plots absorb the leftover** (510 ft gives 80, 70, 70, 70, 70, 70, 80). Middle plots stay exactly the standard. Never below 65 ft frontage.
4. Size options 65, 70, 75, 80 ft, always 100 ft deep, one size per block: pick the size where each end plot takes at most +10 ft, smallest leftover; ties go to 70, then 75, 65, 80. If none fits, mix sizes symmetrically with the larger at the ends.
5. Front row always 100 ft deep; in deeper blocks the back row takes the extra depth. 80 ft frontage on major roads. Residential B minimum 0.16 ac (6,970 sq ft).
6. Act 925 s72(3)(a): a local plan needs at least 20 plots, each at least 110 m2.
7. Do not put an access road through the middle of a block that already lies between two roads.
8. **Straight and curved blocks (study of your local plans, 2026-11-21).** Straight blocks: one mid line, cuts square to the long side and carried straight through both rows (72-96 % of mid-line junctions in Tokunaso, Beposo and Prestea-Brumasi are crossings); end plots keep fronting the long side and take the rounded or oblique corner, never turned to the short cross road; cuts never skewed to follow an oblique road. Curved blocks (cut direction turns more than 14 degrees along the block): mid line parallel to the curve, cuts radial (square to the road). The cut is carried through both rows while the two rows' fronts stay within about 12 % of each other (Tokunaso, 63 % crossings on curves); otherwise each row is cut to its own frontage (Beposo, 48 %) so every plot keeps the standard size. Each sector has its own grid turned to its main road; triangles where sectors meet go to facilities or open space. The subdivide stage writes subdivision.json (straight / curved blocks and the cut method used).
9. **No double frontage (user, 2026-11-21).** A road behind the block (even part of the way) means two rows back to back from 160 ft block depth (equal rows; shallow rows get wider frontages to keep the plot area). Wedge blocks between converging roads: split halfway between the two roads, each row cut square to its own road, the narrow tip a reserve (facility / green). Blocks under 170 ft deep with roads on both sides go to the facility / open-space pool. A plot still facing two roads is split back to back (halves >= 6,400 sq ft), else joins the green / facility site beside it, else stays residential and the audit flags it. Never turned into commercial the planner did not ask for. No 'landscaped green' (user, 2026-11-21): a leftover piece joins the facility / open space beside it, else the plot beside it; a lone piece of 0.4 ac or more with frontage is a P.O.S, a smaller island between roads becomes road reserve. Facility sites are clean blocks: plot groups that are not compact or that box a residential plot into a notch are rejected, plots are carved from a leftover piece only when the rest stays one compact site, and a plot left sharing two sides with a facility joins it. Plots are kept at the planner's size: only plots under 85 % of it (65 x 100 ft when none is set) are merged into a neighbour. Roads enclose all land uses (user, 2026-11-21, Wassa Mampong): the road designer adds a road just inside the site boundary (after the collectors, smoothed where the boundary is jagged), so no plot backs onto the boundary; stretches along a stream reserve keep the green buffer edge. The grid direction still follows the real roads. Road designer: where both sides of a parcel are roads the bands are spread evenly (170-250 ft), and blocks too shallow for two rows with roads all round score almost nothing.

## 6. Road layout: how the user designs (the planner draws, the tool assists)

The road layout is the planner's decision. The user stopped automatic designs and asked the tool to learn from how they draw in Line.shp (watch edits read-only; never write to Line.shp while they edit). Rules learned:

- **Junctions 80 to 90 degrees** (never below 70). Bend road ends to arrive square. No Y or knife-edge junctions, no wedge blocks.
- **No staggered T junctions.** Every road reaching a road from one side lines up with a road on the other side (4-way) or has nothing opposite. Existing roads arriving at the site are carried straight in first; the grid is built off them.
- **No double frontage**: no single-row blocks between two parallel roads.
- **Blocks run parallel to the highest-order road beside them**, so few roads enter it. Hierarchy: 100 ft > 60 ft > 40 ft collector > 30 ft local; only 40 ft collectors join the 60 / 100 ft roads.
- Grid direction per parcel follows the edge facing the main connecting road, not simply the straightest edge.
- Bands: a 200 ft band along edges behind a 30 ft road; inner 30 ft grid roads square to the main edge, 200 ft apart (two rows of 100 ft plots); blocks about 400 to 520 ft long, never over 600 to 700 ft; break blocks where cross roads arrive.
- Large faces (60 to 70 ac) are first split by curved 30 ft connectors into 25 to 40 ac parcels. Strongly curved edges get nested curved inner roads offset 200 ft + road, not a straight grid.
- Every road end trimmed to the crossing road edge; edge lines join at corners with no overshoots, no lines across road mouths, no hairline gaps; never delete the back line of plots where a road dead-ends against a block.
- Cul-de-sacs no longer than 200 m (656 ft). Short corner blocks about 200 x 200 to 250 ft are fine.
- Blend patterns (grid + curved / crescent + cul-de-sac), not one pattern only.
- Patterns from the user's local plans: (1) streams as a continuous green buffer with blocks backing onto it and roads crossing only where needed; (2) existing roads kept on alignment and existing built-up areas retained as blocks; (3) a straight grid of two-row blocks per sector, orientation following each sector's main road; (4) triangular wedges where grids meet become worship / open space / S.A / clinic / corner shop, not odd plots; (5) curved distributors with fanned blocks; (6) mixed commercial-residential frontage on main roads; (7) neighbourhood clusters: basic school + playground, S.A + U.T pairs, corner shops, day care.
- Terrain: schools, health and football parks on the flattest well-drained blocks; S.A on low ground by the green, at least 300 ft from schools and clinics; UT (water tanks and masts) on high ground, at least 300 ft from schools, day cares and clinics; flag roads steeper than about 18% running straight downhill.
- Learned road widths (STMA): 20-25 ft lanes (49%), 30-35 ft (18%), 40-45 ft (19%), 50 ft and over (6%). The 2025 Guidelines require 30 ft minimum access roads.

Input for `design --roads`: a line file (shp / gpkg / kml) of road centrelines with a `width_ft` field (or a `class` text containing the width, for example "40 ft collector"). Optional `--stream` polygon or line file with `--stream-buffer` (ft).

## 7. Land use programme and facility rules

Programme: LUSPA Manual 4.6.3 + the 2025 Guidelines mandatory list. Rates, site sizes and shapes learned from 65 approved STMA schemes (39,846 plots); the Guidelines govern where they differ.

| Facility | Learned rate | Learned site | Shape |
|---|---|---|---|
| School | 1 per 144 plots | 1.82 ac (0.92 to 3.02), about 265 x 380 ft | full small block, 79% near-square |
| Place of worship | 1 per 159 plots | 0.90 ac (0.68 to 1.21) | compact, 2 rows deep, 2 to 3 plots long |
| Market / commercial | 1 per 229 plots | 0.59 ac (0.23 to 1.58) | elongated along the road, often a corner |
| Open space | 1 per 271 plots | 1.37 ac (0.49 to 2.70) | defined scheme-sized P.O.S only |
| Sanitary area | 1 per 356 plots | 0.28 ac, about 100 x 155 ft | 1 to 2 plots |
| Health | 1 per 653 plots | 0.88 ac (Guidelines minimum 0.5 ac for a health post) | compact |
| Civic / community, police, nursery, lorry park | 1 per 600 to 1,700 plots | 0.8 to 0.9 ac | compact near-square |
| Utility | 1 per 613 plots | 0.20 ac, about one plot | |
| Cemetery | 1 per 1,475 plots | 2.6 ac | |

- Community uses take a whole block depth as compact 2 x 2 or 2 x 3 plot squares across both rows, never single plots or strips along one row.
- No open space inside school land; no undefined football / sports field (none appears in any scheme).
- Market and health post on the gateway corners (collector x main road); school as a clean whole block on the collector; worship one each side of the main road.
- Access: every home within 800 m of a basic school (stricter than the Guidelines' 2.5 km); open space within about 400 m; S.A within 500 m (2025 standard).
- LUSPA standards: primary school per neighbourhood of 5,000; JHS per 10,000; SHS per 20,000; worship catchment up to 15,000; local shop up to 500 persons; local market up to 30,000 (+20 to 50% parking); police and fire up to 35,000; hydrants every 120 m on major roads.
- Population for checks: 7.2 persons per plot (Obusomase assumption) for new layouts. For existing areas: 1.5 storeys average, 60 m2 per household, 3.4 persons per household (provisional, Osu).
- Harmony: no S.A beside a playground, school or clinic.

**Facility rules from the study of your local plans (2026-11-21)** (Tokunaso A/B/C, Beposo, Prestea-Brumasi, Wassa Mampong, Cosmax/Hemax, STMA):

| Facility | Site | Placement |
|---|---|---|
| Basic School & JHS | whole block ringed by roads, 2.0-4.1 ac (LUSPA KG-JHS 6 ac, flagged as a gap) | central, on the collector, not on the main road |
| Playground (school) | 1-1.5 ac, pitch-shaped, across the road from the school, not counted in the school | one per school |
| Day care | 0.6-0.7 ac square across both rows | neighbourhood cluster by the market; 60 m from a fuel station |
| Clinic | about 1 ac (200 x 240 ft) across both rows | near the school, as far as the site allows (LUSPA 500 m) from market, lorry park, S.A, fuel; second clinic only above 5,000 people |
| Market | about 1 ac per section; main market with lorry park 5 ac for 20,000 | gateway corner; lorry park on the main road side |
| Corner shop | at least 0.25 ac (two plots where one is smaller) | corner plots at junctions (collector corners when the toolkit places them) |
| Fuel station | 0.5-1 ac junction corner | main road only; 60 m from schools / day care, 500 m from clinics, 30 m from streams, 300 m from the next station |
| Place of worship | 0.5-0.8 ac (aim 0.75) corner parcel across both rows | 1 per ~1,500 people; away from fuel and S.A |
| P.O.S | 1-1.5 ac within about 400 m of every home; total about 1.2 ac per 1,000 people | spread over the plan (farthest homes first); wedges, corners, low ground; every open space with road frontage; never landscaped green or residential plots notched into it |
| Children's playground | 0.5-1 ac | in the neighbourhood cluster, within about 400 m of every home |
| S.A | 0.2-0.45 ac on a corner plot, on a road a refuse truck can use | every home within 500 m; 60 m from schools, day care, playgrounds, clinics; off the main road |
| Police / fire | police 2.5-3 ac (LUSPA) | on the main road at the edge of the housing |

**Second study: Shama District, Ahanta West and Prestea-Huni Valley plans (2026-11-25).** 64 plans in `All Scaned Maps Arranged/New LPs`: 10 recent Shama District local plans in colour (2022-2025: East Inchaban, Lower Inchaban 1 and 2, South Inchaban, Aboadze-Abuesi, Nyankrom-Aboadze-Abuesi, Shama Extension Three, West Essaman, Ohiamadwen, Nkyirkyir; plus Bedukrom and West Assorko as images), 40 Ahanta West planning schemes and 14 Prestea-Huni Valley schemes (scanned, black and white). About 50,000 plots measured: the vector plans shape by shape (scale checked on the 1,000 ft grid), the scans from the closed shapes between the drawn lines (scale from the sheet at 1:2,500, checked on the grid; sizes measured inside the lines, so a few feet under the true plot).

| Group | Plots | Typical plot | Under 0.16 ac | Blocks |
|---|---|---|---|---|
| Ahanta West schemes (older) | 29,050 | 77 x 93 ft (6,600 sq ft); 70-85 x 85-95 | 62 % | two rows, rounded corners |
| Prestea-Huni Valley schemes | 10,022 | 74 x 94 ft (6,500 sq ft) | 69 % | two rows, grid per sector |
| Shama: Inchaban, Aboadze, Nyankrom (large) | 8,416 | 90-100 x 100-115 ft (10,000 sq ft) | 3-5 % | 205-230 ft deep, 300-410 ft long |
| Shama: Extension Three, Ohiamadwen, Nkyirkyir, South Inchaban (medium) | 1,829 | 80-90 x 100-105 ft (8,000-8,700 sq ft) | 3-24 % | 200-210 ft deep, about 400 ft long |
| Shama: West Essaman (compact, 2025) | 618 | 70-80 x 90 ft (6,600 sq ft) | 65 % | 180 ft deep, 345-475 ft long |

What the new plans add:
- **Plot size is a local choice.** Older schemes and the compact 2025 plan use about 70-80 x 90 ft; the peri-urban Shama plans use about 100 x 100-110 ft; most use one size per plan. The web app offers these as presets (Design the roads for me > Plot size from your plans), and the block depth follows (two plot depths) with a block length of whole plots (about 400-500 ft). The LUSPA Re B minimum (0.16 ac) still governs: the audit flags smaller plots.
- **Blocks are short**: median 300-410 ft (4-6 plots a row), two rows deep; corners cut off (chamfered or rounded) in almost every plan.
- **Roads**: two widths between blocks recur, about 20-30 ft (access) and 40-60 ft (local / distributor), with 75-100 ft main roads; West Essaman uses 30 and 40 ft roads with 20 ft lanes. Curvilinear networks follow the contours in the hilly plans (Lower Inchaban, Aboadze: 26-50 % irregular blocks); straight grids in the flat ones (West Essaman, Shama Extension Three: under 20 %).
- **Mixed commercial-residential along the highway**: the single row of plots facing the main road is mixed use (West Essaman about 60 plots, Shama Extension Three). The toolkit now does the same when mixed use is in the programme.
- **Kept as they are**: existing built-up villages (one "built-up area" parcel), cemeteries, poultry farms, wetlands and stream buffers, quarry buffers; high-tension lines run through a clear corridor without plots.
- **Land-use budget (Shama plans)**: residential 61-78 % of the planned land (46-49 % where large parks or farms are kept), open space 3-14 % (24-41 % with a golf course or stream valley), commercial 3-6 % (11 % with mixed-use frontage), civic 2-6 %, education 1-6 %, utility and sanitary 0.2-1.3 %.
- **Facilities (Shama plans)**: civic and worship sites about 1 ac (0.7-1.2), 1 per 60-120 plots, often on corners; commercial 0.7-1.8 ac, 1 per 40-190 plots (shopping centre, sub-market, hotel, bank, filling station, LPG station on the main roads); schools 1.0-1.5 ac, 1 per 140-410 plots, with central school blocks of 3-11 ac; utility and sanitary sites (S.A, refuse container R.D, U.T) 0.25-0.6 ac, 1 per 120-270 plots; many small children's playgrounds (C.P.G, 0.3-0.5 ac) and open spaces in leftover strips and along streams.
- **Clusters**: school + market + S.A (West Essaman), worship + school (Shama Extension Three), police + fire + clinic and lorry park + market + playing ground in the centre (Nyankrom), school + church + bank + post office + fire station at the gateway (Aboadze-Abuesi). Light-industrial zones of large plots (0.6-1 ac) sit at the edge on the main road (Nyankrom, Shama Extension Three, Tai Oil village).
- New optional catalogue items: Refuse Container Site (R.D) and Light Industrial Area.

**Facility programme (web app "Facilities and services", after the site analysis).** Either the toolkit decides (the counts the population needs: `python lp_toolkit.py facilities --pop N` prints the catalogue of about 60 services, all levels, from LUSPA 2025 and the study) or the planner ticks each facility with its number, site size and, optionally, its location (a point or an outline). Saved as facilities.json (mode auto | custom, items {id: on, n, size_ac}, decisions) and facility_sites.geojson (fac_id); passed with `--facilities` / `--facility-sites`. Located sites are taken out of the blocks before subdivision. Learned facilities (school, playground, market, fuel, clinic, worship, day care, P.O.S, S.A, U.T, shops, police post, lorry park) keep their own placement rules with the planner's numbers and sizes; the others (SHS, hospitals, police station, cemetery, hotels, utilities ...) go to a leftover site of the right size by their siting preference. When a requested facility does not fit, the land-use stage writes shortfall.json and the run pauses: for each item the planner chooses Take the plots / Skip / Reduce the size, and the run continues from land use. In the toolkit's own programme it takes the plots by itself.

**Located facilities fit into the designed roads (user, 2026-11-23).** The road designer lays the grid as usual (no ring roads around the sites, no site at an angle to the grid); then each located facility takes the block where the planner put it:
- the whole block when it is about the right size;
- a stretch of the block across its full depth (frontage on both roads) when the block is much bigger; a leftover too small for a plot joins the site;
- neighbouring blocks joined into one site when one block is too small (the local road between them is dropped; never across a collector, main, existing or planner's road).
Sizes therefore follow the blocks (two whole blocks for a 3 ac school, for example); the run log notes any site smaller than asked. The fitted outlines are saved back to facility_sites.geojson (backup `.before_fit`), so the map, the land use and Fit roads use the same outline. A planner's outline that crosses a road is fitted the same way at the land-use stage.

**Corner shops and S.A on corner plots (user, 2026-11-23).** A located corner shop or S.A takes the corner of the block nearest where it was put: one plot row deep, fronting both roads at the junction. S.A sites the toolkit places itself start from a corner plot. Neither grows by taking in the plots or leftover pieces beside it.

**Facilities spread out (neighbourhood distribution, user 2026-11-23).** The homes are grouped into neighbourhood units of about 5,000 people; core facilities (basic school, clinic, market, day care, community centre) go one per unit, to the unit furthest from the ones already placed. Walking-catchment uses go farthest-first: P.O.S until every home is within 400 m (each at least 100 ft wide, length up to 3 x width), S.A within 500 m, worship within 500 m. The same kind is kept apart (playgrounds and day cares about 240 m, clinics 720 m, markets and community centres 600 m, second schools 480 m).

**Suitability (web app, Design > Suitability).** For any facility in the catalogue: a heat map of every 25 ft cell scored from the site analysis (slope, high / low ground, streams, steep reserve) and the standards (distance rules, catchments, road access where the facility needs an existing main road; elsewhere the road design provides access), and the best sites of the required size, spread over the whole planning area so that each serves the most homes. Type how many suggestions you want. Before the roads the sites are squares running with the road grid; on a designed plan they are compact plot groups. For each: **Accept** (it becomes a located facility; Apply to the plan now), **Reject** (never suggested again), or **Relocate** (drag it, or click Relocate then the new place: it snaps to the plots there and is scored again).

**Fit roads (after accepting a suitability site on a designed plan).** Slight changes only: designed roads through the site are trimmed to its edge, a short road just beside it is shifted onto its edge, sides without frontage get an edge road, cut road ends are reconnected; your own roads and the existing roads never move (reported instead). Only the blocks touched are re-plotted.

## 8. Checks to run before presenting anything (self-audit)

The user reviews like a planning officer. Catch the flaws before they do.

Layout (`design` audit):
- Junction angles (80 to 90; flag under 70), staggered T, Y junctions, dead ends over 200 m, block length over 600 ft, blocks over two lines of 8 plots without a break, double frontage, landlocked plots, plots below the standard, uneven splits, facility shapes (compact, near-square), harmony distances, riparian buffers.

Existing situation:
- Footprints: compare counts and roof-area IoU with the building database; look at a crop in the dense core and a crop in a planned area before accepting.
- Plots: buildings cut by plot lines, plots deeper than 60 m, open / yard plots, interior plots, overlap = 0, coverage about 100%. Look at curved blocks and block ends on the image before presenting.
- Maps: legend outside the map frame (never covering the site); building outlines in a colour distinct from plot lines; no empty legend entries; title with the place name. Map sheets carry the credit "Prepared with LP Toolkit · Urban GeoPlan".

Reporting rules: say what failed and what is uncertain; give numbers; no proposals unless asked; no em dashes in documents (use colons, commas or parentheses).

## 9. Operational lessons

- Close output files in ArcGIS / image viewers before a run: Windows locks open files. The map stage saves `_v2.png` when the map is open elsewhere. ArcGIS Pro also locks file geodatabases ("permission denied").
- Shapefile field names are cut to 10 characters (carriage_w_m -> carriage_w); the toolkit reads the short names.
- KML polygons carry Z: always force 2D.
- Filter degenerate geometries (non-polygons, under 10 sq ft) before rectangle metrics.
- Keep working files out of temporary folders. The toolkit keeps them in `<output>/_work/`.
- The Python environment is `LP_Toolkit/env` (copied from the working environment; packages: geopandas, shapely 2, rasterio, opencv, scikit-image, scipy, networkx, contextily, pyogrio, torch CPU, segment_anything, matplotlib, openpyxl). Run with `LP_Toolkit\run.bat ...` or `env\Scripts\python.exe lp_toolkit.py ...`.

## 10. Reference runs

| Site | Area | Buildings (final) | Blocks | Plots | Notes |
|---|---|---|---|---|---|
| Test 4, Osu (planned) | 163.7 ac | 2,908 | 58 | 788 | profile planned; 335 buildings cut; commercial strip along Oxford St from database occupancy |
| Test 5, La (compact core) | 55.2 ac | 1,785 | 18 | 441 | profile compact; 131 interior plots (unmapped footpaths); occupancy unknown in database |
| Test 3 (greenfield, stream) | 142 ac | | 49 | 389 residential | design workflow; open issue: NE sector landlocked pockets |
