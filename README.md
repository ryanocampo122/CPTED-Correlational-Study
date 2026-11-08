# CPTED Computer Vision and Correlational Sentiment analysis of Public Safety - A Study on Crime Patterns - Saskatoon

USask AIRI 2026 project on CPTED, crime and perceived safety in Saskatoon.
Co-leads Dr. Varuni Jayasooriya (SENS) and Dr. Timothy Kang (Sociology); collaborators Dr. Khan Wahid (ECE) and
Elisabeth Miller (City of Saskatoon, Neighbourhood Safety and CPTED); RA Ryan Ocampo.

The study follows the **revised work plan** (`Plan/workplan_revised_2026-10.pdf`): a cross-sectional, correlational
study on open secondary data for **1 June – 31 August 2026**. CPTED features measured from street-level imagery (X) are
correlated with recorded crime (Y1, Saskatoon Police Service) and with perceived safety on Reddit (Y2), on street
segments in Downtown/CBD.

## Start here

| You want | Open |
|---|---|
| The latest update for supervisors | `Deliverables/2026-10_october_update/` |
| The literature review (CPTED evidence, crime and perception, pilot sites) | [`Docs/literature review/Master_lit_review.docx`](Docs/literature%20review/Master_lit_review.docx) |
| How the whole study fits together, and how to run it | `Docs/workflow.md` |
| The results, step by step, in notebooks | `Notebooks/` (start with `00_replicate_system.ipynb`) |
| What has been checked, and how | `Docs/verification/october_2026_checks.md` |
| Decisions and known problems | Decision D1 (image source: newest image at each point, decided November 2026) in `Docs/cv_pipeline.md`; Decision D2 (Reddit spatial unit) and the Reddit limitations in `Docs/reddit_pipeline.md`; gaps in the crime data in `Docs/crime_data.md` |
| Any other documentation | `Docs/README.md` |

## Status

| November task (work plan p. 5) | Status (7 Nov 2026) |
|---|---|
| Run segmentation, detection and CLIP | **Done, not yet validated**: 492 side views from 246 points on 121 of the 218 segments (newest 2020/2023 image per point, Decision D1); Mask2Former (Mapillary Vistas) for segmentation and objects, CLIP for cues (`Docs/cv_pipeline.md`) |
| Check accuracy against hand-labelled images | **Sheet ready**: 150 side views drawn blind, 30 for a second coder; labelling next (`Docs/validation_plan.md`) |
| Map crime hot spots by category | **Done**: 255 of 257 CBD study-category records placed on street segments; half of all study crime on 11 of 218 segments (`Docs/crime_data.md`) |

| October task (work plan p. 5) | Status |
|---|---|
| Finalize crime categories | **Done**: 5 included, assault conditional, 4 excluded; SPS June–August 2026 extract added and cleaned: 9,650 records, 2,982 in the study categories (`Docs/crime_data.md`) |
| Extend Reddit to June–August 2026 | **Done, verified**: 195 posts, 6,452 comments; every table reproduces byte-for-byte; 30 checks pass |
| Generate sample points | **Done**: 423 points on 218 street segments; refined in November (11 bridge/freeway points flagged; images must face along the point's road) |
| Collect street-level images | **Done: method validated**: 10 Mapillary images sourced and read by CLIP ViT-B/32 in the pipeline; no June–August 2026 imagery exists yet (newest 2020/2023), so the full set is sourced next |

![Workflow](Docs/figures/mid_point_october/fig01_workflow_status.png)

## Folder map

```
Plan/            governing documents: revised work plan, grant application
Docs/            detailed documentation, verification checks, figures, the literature review
Data/
  reddit_2026-06-01_2026-08-31/   CURRENT  study-period Reddit: raw, cleaned, tables, audits, charts
  reddit_2025-06-11_2026-06-11/   earlier  12-month collection behind the July/August reports (corrected)
  sps_crime_2026-06-01_2026-08-31/ CURRENT  SPS recorded crime (Y1): raw extract, cleaned rows, category counts, per segment
  cv_pilot_2026-10/               CURRENT  CBD sample points, imagery coverage audit, 10-image pilot
  cv_study_2026-11/               CURRENT  study image set (246 points), segmentation/detection/CLIP outputs, labelling sheet
  boundaries/                              CBD polygon (interim, from OSM) and map context
  climate_2010_2025/                       ECCC climate 2010–2025, four prairie cities; kept for possible use
flight           ./flight --execute_flight: the whole pipeline in one command (Scripts/flight/)
Scripts/
  flight/              the flight: execute_flight.py (stages, comparisons, summary), load_models.py, run_notebook.py
  reddit_collection/   Reddit collector (reddit_scraper.py)
  reddit_analysis/     cleaning, tagging, analysis and self-checks (run_all.sh <dataset>)
  crime_data/          cleans the SPS extract into study categories (clean_sps_crime.py); crime per segment (hotspots.py)
  climate_data/        ECCC download scripts behind Data/climate_2010_2025/
  cv_pilot/            sample points, Mapillary imagery, CLIP scoring, Reddit link (pilot.py)
  cv_study/            November: full image set (images.py), segmentation/detection/CLIP (models.py), labelling (validation.py)
  verification/        independent checks of every October claim
  reporting/           figures, report numbers, the October and November .docx builders
  make_handoff.sh      builds a shareable zip without credentials or private text
Notebooks/       notebooks on top of the scripts: replicate the system, Reddit, crime, street images (outputs never committed)
Deliverables/    dated copies of what was sent (2026-08, 2026-10); later edits noted in each README
Reference/       literature (incl. computer-vision papers), presentations, maps
Archive/         surveys dropped in the revised plan (the August CV prototype is in git history)
RESULTS_FINAL/   one EXECUTION-<n>/ folder per flight run, plus executions.csv (git-ignored)
```

## Running

**One command runs the whole pipeline** (repository root):

```bash
./flight --execute_flight             # install -> collect (Reddit, Mapillary APIs) -> load CLIP + VADER -> results
./flight --execute_flight --offline   # the same without API calls
./flight --execute_flight --offline --skip-models   # quick check: all but re-running the image models (~11 min)
```

Each run writes everything it produces (results, JSON, status logs, figures, the report, file-by-file comparisons
with the published outputs) into a new `RESULTS_FINAL/EXECUTION-<n>/` and nothing anywhere else. Open its
`FLIGHT_SUMMARY.md` first. Details and options: `Docs/workflow.md` ("One command") and `./flight --help`.

Environment: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (Python 3.14; the flight does
this itself). Credentials live outside the repository, in `~/.config/computervision_sentinel/secrets.env`
(setup in `Docs/data_ethics.md`): `PRAW_CLIENT_ID`, `PRAW_CLIENT_SECRET`, `PRAW_USER_AGENT`,
`COMPUTERVISION_SENTINEL_HASH_SALT`, `MAPILLARY_TOKEN`. Single steps, to run one on its own, are listed in `Docs/workflow.md`; the most used:

```bash
bash Scripts/reddit_analysis/run_all.sh reddit_2026-06-01_2026-08-31            # Reddit analysis (scratch)
.venv/bin/python Scripts/crime_data/clean_sps_crime.py                            # clean the SPS crime extract
.venv/bin/python Scripts/cv_pilot/pilot.py coverage --out Data/cv_pilot_2026-10/cbd
.venv/bin/python Scripts/verification/verify_october_2026.py                      # re-check October claims
.venv/bin/python Scripts/reporting/make_figures.py                                # rebuild figures
.venv/bin/python Scripts/crime_data/hotspots.py                                   # crime per street segment
.venv/bin/python Scripts/cv_study/models.py                                       # image models (~11 min)
```

**Notebooks** (`Notebooks/`, see its README): open them in VS Code with the `.venv` kernel. They read `Data/` and
never write there, the flight runs 01–03 on every run, and a git filter keeps their outputs out of commits
(after cloning, run `.venv/bin/nbstripout --install` once).

## Ground rules

- Raw data in `Data/*/01_raw_collection/` is never edited; everything else is regenerated by code.
- Numbers in deliverables come from scripts (`Scripts/reporting/report_numbers.py`).
- Reddit text is not quoted outside the team; images credit Mapillary (CC BY-SA 4.0); maps credit OpenStreetMap.
  See `Docs/data_ethics.md`.
