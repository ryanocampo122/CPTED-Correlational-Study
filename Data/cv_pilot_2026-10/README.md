# Computer-vision pilot, October 2026

Outputs of `Scripts/cv_pilot/pilot.py` (see its README for commands). Three runs:

| Folder | What it is | Status |
|---|---|---|
| `cbd/` | **Sample points** for the study area: 423 points about 50 m apart on 218 street segments inside the CBD boundary (`Data/boundaries/`); Mapillary **coverage audit** by year for every point; the study-period download attempt (60 points tried, 0 images) | current |
| `cbd_latest_imagery/` | **Feasibility pilot** on the newest image at each point (any date): 10 images (2014–2023), CLIP typology and cue scores, Reddit link tables, `pilot_report.md`, `contact_sheet.jpg`, and `validation_template_blind.csv` for hand labelling | current; not study-period imagery |
| `placeholder_box/` | The first run, made with a hand-drawn box from the August prototype: 595 points, only 36% inside the CBD | superseded; kept for the record |

Key files in each run: `sample_points.csv/.geojson` (point id, segment id, OSM way, road name and class,
bearing), `coverage_points.csv` (per point: images within 30 m, newest flat and 360° capture, study-period
counts), `coverage_by_year.csv`, `coverage_images.csv` (every image found), `pilot_attempts.csv` (every
point tried, including misses), `image_manifest.csv`, `clip_scores.csv`, `run_meta.json` (parameters, counts,
git commit).

Headline: **0 of 423 CBD points have an image from 1 June – 31 August 2026**; the newest imagery is 2023
(27 points) or 2020 (261). See `Docs/cv_pipeline.md` and Decision 1 in `Docs/decisions_and_issues.md`.

`_local_audit_do_not_share/` folders (git-ignored) contain Reddit text snippets for precision checks. Do not
share or quote them. Images: © Mapillary contributors, CC BY-SA 4.0; credit Mapillary on any figure that shows them.
