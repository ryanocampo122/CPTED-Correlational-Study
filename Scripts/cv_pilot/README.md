# CV pilot (October 2026): street images → CPTED cues → Reddit

A small end-to-end run of the revised work plan's computer-vision pipeline on **at most 10 Downtown images**.
It shows that each stage runs and joins. It is **not** a result: 10 images cannot support any claim about CPTED,
crime or perception.

| Step | Command | Work-plan step | Output (in `--out`) |
|---|---|---|---|
| Pre-flight | `python pilot.py check` | – | PASS/FAIL for libraries, Reddit files, Mapillary token, OSM |
| 1. Sample points | `python pilot.py points` | 1 | `sample_points.csv/.geojson` (~50 m apart on OSM streets, split into street segments) |
| 1b. Coverage | `python pilot.py coverage` | 2 | `coverage_by_year.csv`, `coverage_points.csv`, `coverage_images.csv` (every Mapillary image within 30 m of every point, by year) |
| 2. Images | `python pilot.py images` | 2 | `images/`, `image_manifest.csv`, `pilot_attempts.csv` (misses included) |
| 3. CLIP scoring | `python pilot.py score` | 5 | `clip_scores.csv` (land-use typology + 9 CPTED cues) |
| 4. Reddit link | `python pilot.py reddit` | 8 | `reddit_downtown_summary.csv`, `reddit_cue_comparison.csv`, `reddit_place_anchors.csv`, `reddit_join.csv` |
| 5. Report | `python pilot.py report` | – | `pilot_report.md`, `contact_sheet.jpg`, `validation_template_blind.csv` |

## What was run in October 2026 (`Data/cv_pilot_2026-10/`)

| Folder | Boundary | Images | Result |
|---|---|---|---|
| `placeholder_box/` | hand-drawn box from the August prototype | study period only | 595 points, but only 36% inside the CBD; 0 study-period images. **Superseded.** |
| `cbd/` | CBD neighbourhood polygon (`Data/boundaries/`) | study period only | 423 points on 218 segments; coverage audit; **0 of 423 points have a Jun–Aug 2026 image**, 60 attempts logged |
| `cbd_latest_imagery/` | same 423 points | most recent at each point (`--any-date`) | 10 of 10 images (2014–2023), CLIP scores, Reddit link, report, contact sheet, blind validation sheet |

Commands used:

```bash
.venv/bin/python Scripts/cv_pilot/pilot.py points   --out Data/cv_pilot_2026-10/cbd
.venv/bin/python Scripts/cv_pilot/pilot.py coverage --out Data/cv_pilot_2026-10/cbd
.venv/bin/python Scripts/cv_pilot/pilot.py images   --out Data/cv_pilot_2026-10/cbd          # study period: 0 found
# feasibility run on the newest imagery that exists (copy points + run_meta.json first):
for s in images score reddit report; do
  .venv/bin/python Scripts/cv_pilot/pilot.py $s --any-date --out Data/cv_pilot_2026-10/cbd_latest_imagery
done
```

By default the boundary is the CBD polygon in `Data/boundaries/` (the OSM copy of the City's neighbourhood
boundary; swap in the City's own file when it arrives) and the output folder is `Data/cv_pilot_2026-10/cbd/`.
`--boundary-geojson ""` falls back to the old placeholder box. Tests (offline, no token):
`.venv/bin/python Scripts/cv_pilot/tests/test_pilot.py`. The first CLIP run downloads the model once (~600 MB).
Credentials: `MAPILLARY_TOKEN=MLY|...` in the git-ignored `.env` at the repo root.

## Images and the study period

The pilot keeps only images captured 1 June to 31 August 2026 (Saskatoon time) unless `--any-date` is given, and
uses 360-degree panoramas as well as normal photos. Each panorama is cut into two normal camera views facing the
two sides of the street. **No Mapillary imagery from 2024, 2025 or 2026 exists over the CBD** (coverage audit,
and an independent tiled re-query on 17 Oct 2026); the newest is 2023 (27 points) and 2020 (261 points).
Google Street View is not an alternative: its terms (Maps Platform ToS 3.2.3) prohibit bulk download and using the
imagery to train, test or validate models. See `Docs/decisions_and_issues.md`.

## How the 10 pilot images are chosen (fixed before looking at any image)

1. Points are ordered by a deterministic *farthest-point* spread: start at the point nearest the centre, then
   repeatedly take the point farthest from those already chosen. Nothing about imagery, crime or Reddit influences
   the order, so the sample can't be cherry-picked.
2. Walk that order; at each point search Mapillary within 30 m. Drop images without a thumbnail or outside the
   capture window. Rank by the **most recent year**, then a **June–August** capture, then flat before 360-degree,
   then the **nearest**.
3. Keep the first 10 points that have a usable image. Every miss is logged in `pilot_attempts.csv`.

**Known fix for November:** 2 of the 10 pilot images were captured on the *cross street* at an intersection
(camera heading ~89° from the point's road), so their "side-on" crops look down the road. `choose_image()` should
require the camera heading to be within ~30° of the road bearing. Points on bridges and freeways (11 of 423) have no
frontage to measure and should be dropped or flagged.

## What each part measures, and what it can't

* **Typology** (8 labels: the 7 CPTED land-use types from the Phase 1 briefing + `road_corridor`) and **9 cues**
  (graffiti, litter, boarded windows, vacant lot, active storefront, windows overlooking the street, people
  present, fences, seating). Prompts live in `clip_prompts.json`, so they can be reviewed without reading code.
* Wide photos are scored as 3 square crops (left/centre/right), because CLIP's default centre-crop throws away the
  sides of the street.
* Scores are **uncalibrated zero-shot** probabilities. Rank and compare them; don't treat them as measurements until
  checked against hand labels. `validation_template_blind.csv` is the blank sheet (no model scores shown) for the
  first 10 of the ~150.
* **Streetlights are deliberately not scored by CLIP.** Thin objects like poles are a known CLIP weakness; lighting
  comes from object detection / segmentation in November (work-plan steps 3–4).

## Files

`pilot.py` (CLI), `pilot_lib.py` (geometry, Mapillary, CLIP; no shapely needed), `clip_prompts.json`,
`reddit_lexicon.json`, `tests/test_pilot.py`.
`_local_audit_do_not_share/` folders (git-ignored) hold Reddit snippets for checking cue precision. They contain
user text: **do not send or quote them**.

Imagery: © Mapillary contributors, CC BY-SA 4.0. Credit Mapillary on any figure that shows the images.
