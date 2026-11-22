# LP Toolkit: local plan preparation guide

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

**Web app.** `run_webapp.bat` opens the same workflows in the browser (http://localhost:5050; `run_webapp.bat --lan` lets other computers on the office network open it). Projects are kept in `D:/Work/2026/Machine Learning/LP_Projects/`. Draw or upload the site, roads (with widths), existing roads and streams on the satellite map; choose the road option; run with a live log; view the results as map layers (plots by use, audit findings) and download everything as a zip.

**Site analysis comes first.** The `site` stage prepares the terrain before any road is drawn: Copernicus 30 m DEM, contours at an interval adapted to the relief (1, 2, 5, 10 m...), slope in percent, slope classes (flat 0-5%, gentle 5-10%, moderate 10-18%, steep 18-30%: no roads straight downhill, very steep > 30%: keep green) and the steep-slope reserve (slopes >= `--steep` %, default 30, pieces >= 0.5 ac kept green and excluded from blocks). Outputs: `<P>Contours.shp`, `<P>Slope_classes.shp`, `<P>Slope_percent.tif`, `<P>Steep_slope_reserve.shp`, `<P>Terrain_summary.json`, `<P>Site_analysis.png`, map overlays. In the web app: "Prepare site analysis", then review the terrain layers before planning roads.

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

## 8. Checks to run before presenting anything (self-audit)

The user reviews like a planning officer. Catch the flaws before they do.

Layout (`design` audit):
- Junction angles (80 to 90; flag under 70), staggered T, Y junctions, dead ends over 200 m, block length over 600 ft, blocks over two lines of 8 plots without a break, double frontage, landlocked plots, plots below the standard, uneven splits, facility shapes (compact, near-square), harmony distances, riparian buffers.

Existing situation:
- Footprints: compare counts and roof-area IoU with the building database; look at a crop in the dense core and a crop in a planned area before accepting.
- Plots: buildings cut by plot lines, plots deeper than 60 m, open / yard plots, interior plots, overlap = 0, coverage about 100%. Look at curved blocks and block ends on the image before presenting.
- Maps: legend outside the map frame (never covering the site); building outlines in a colour distinct from plot lines; no empty legend entries; title with the place name.

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
