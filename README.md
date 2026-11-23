<img src="webapp/static/brand/logo.png" alt="Urban GeoPlan" width="72" align="right">

# LP Toolkit

**Developed by [Urban GeoPlan](https://www.linkedin.com/company/107451042/).**

Local plan preparation for Ghana: existing-situation surveys and new layouts (roads, plot subdivision, facility programme and land use), following the LUSPA Revised Zoning Guidelines and Planning Standards (2025) and rules learned from approved local plans.

## What is here

| Path | What it is |
|---|---|
| `lp_toolkit.py` | The planning engine (one script). Commands: `existing`, `design`, `facilities`, `db`, `guide`, `stages`. |
| `LP_Toolkit_Guide.md` | The method guide (written by `python lp_toolkit.py guide`). |
| `webapp/` | Browser app (Flask + Leaflet): draw the site and roads, run the toolkit, edit results, facility checklist, 3D view, standards. |
| `run_webapp.bat` | Starts the web app at http://localhost:5050 (add `--lan` for the office network). |
| `run.bat` | Runs the toolkit from the command line. |
| `_build_src/` | Scripts used to build and patch the toolkit and web app. |

## Setup (Windows)

```bat
python -m venv env
env\Scripts\pip install -r requirements.txt
run_webapp.bat
```

Not included in the repository (too large or downloaded data):

- `models/sam_vit_b_01ec64.pth`: the Segment Anything ViT-B checkpoint, needed only for image detection of buildings (`existing --buildings full`). Download it from the Segment Anything release and place it in `models/`.
- `cache/`: imagery and footprint tiles, downloaded again on first use.
- The building footprint database (`D:/Work/2026/Data`) used by the existing-situation workflow.

Projects are stored outside the repository, in `LP_Projects/<project>/` (set another folder with the `LP_PROJECTS` environment variable).

## Command line examples

```bat
env\Scripts\python lp_toolkit.py design --site site.geojson --name MyPlan --roads draft --pattern mixed
env\Scripts\python lp_toolkit.py design --site site.geojson --name MyPlan --roads roads.geojson --facilities facilities.json
env\Scripts\python lp_toolkit.py existing --site site.geojson --name MyArea --buildings fast
env\Scripts\python lp_toolkit.py facilities --pop 5000
```


## About

LP Toolkit is developed and maintained by **Urban GeoPlan**, a geospatial and urban planning initiative in Ghana focused on spatial analytics, urban planning and digital mapping solutions ([LinkedIn](https://www.linkedin.com/company/107451042/)). Copyright (c) 2026 Urban GeoPlan. All rights reserved.

The Urban GeoPlan logo is `webapp/static/brand/logo.png` (header, About box, favicon); replace that file to update it everywhere.
