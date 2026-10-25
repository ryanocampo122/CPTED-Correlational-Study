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
| What has been checked, and how | `Docs/verification/october_2026_checks.md` |
| Open decisions and known problems | Decision D1 (image source) in `Docs/cv_pipeline.md`; Decision D2 (Reddit spatial unit) and the Reddit limitations in `Docs/reddit_pipeline.md`; gaps in the crime data in `Docs/crime_data.md` |
| Any other documentation | `Docs/README.md` |

## Status

| October task (work plan p. 5) | Status |
|---|---|
| Finalize crime categories | **Done**: 5 included, assault conditional, 4 excluded; SPS June–August 2026 extract added and cleaned: 9,650 records, 2,982 in the study categories (`Docs/crime_data.md`) |
| Extend Reddit to June–August 2026 | **Done, verified**: 195 posts, 6,452 comments; every table reproduces byte-for-byte; 30 checks pass |
| Generate sample points | **In progress**: 423 points on 218 street segments generated and checked; being refined (about two more weeks), not yet reported |
| Collect street-level images | **Done: method validated**: 10 Mapillary images sourced and read by CLIP ViT-B/32 in the pipeline; no June–August 2026 imagery exists yet (newest 2020/2023), so the full set is sourced next |

![Workflow](Docs/figures/mid_point_october/fig01_workflow_status.png)

## Folder map

```
Plan/            governing documents: revised work plan, grant application
Docs/            detailed documentation, verification checks, figures, history, the literature review
Data/
  reddit_2026-06-01_2026-08-31/   CURRENT  study-period Reddit: raw, cleaned, tables, audits, charts
  reddit_2025-06-11_2026-06-11/   earlier  12-month collection behind the July/August reports (corrected)
  sps_crime_2026-06-01_2026-08-31/ CURRENT  SPS recorded crime (Y1): raw extract, cleaned rows, category counts
  cv_pilot_2026-10/               CURRENT  CBD sample points, imagery coverage audit, 10-image pilot
  boundaries/                              CBD polygon (interim, from OSM) and map context
  climate_2010_2025/                       ECCC climate 2010–2025, four prairie cities; kept for possible use
flight           ./flight --execute_flight: the whole pipeline in one command (Scripts/flight/)
Scripts/
  flight/              the flight: execute_flight.py (stages, comparisons, summary), load_models.py
  reddit_collection/   Reddit collector (reddit_scraper.py)
  reddit_analysis/     cleaning, tagging, analysis and self-checks (run_all.sh <dataset>)
  crime_data/          cleans the SPS extract into study categories (clean_sps_crime.py)
  climate_data/        ECCC download scripts behind Data/climate_2010_2025/
  cv_pilot/            sample points, Mapillary imagery, CLIP scoring, Reddit link (pilot.py)
  verification/        independent checks of every October claim
  reporting/           figures, report numbers, the October .docx builder
  make_handoff.sh      builds a shareable zip without credentials or private text
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
```

Each run writes everything it produces (results, JSON, status logs, figures, the report, file-by-file comparisons
with the published outputs) into a new `RESULTS_FINAL/EXECUTION-<n>/` and nothing anywhere else. Open its
`FLIGHT_SUMMARY.md` first. Details and options: `Docs/workflow.md` ("One command") and `./flight --help`.

Environment: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (Python 3.14; the flight does
this itself). Credentials are in `.env` at the root (committed to the private repository; a copy is in
`.venv/keys.txt`): `PRAW_CLIENT_ID`, `PRAW_CLIENT_SECRET`, `PRAW_USER_AGENT`, `COMPUTERVISION_SENTINEL_HASH_SALT`,
`MAPILLARY_TOKEN`. Single steps, to run one on its own, are listed in `Docs/workflow.md`; the most used:

```bash
bash Scripts/reddit_analysis/run_all.sh reddit_2026-06-01_2026-08-31            # Reddit analysis (scratch)
.venv/bin/python Scripts/crime_data/clean_sps_crime.py                            # clean the SPS crime extract
.venv/bin/python Scripts/cv_pilot/pilot.py coverage --out Data/cv_pilot_2026-10/cbd
.venv/bin/python Scripts/verification/verify_october_2026.py                      # re-check October claims
.venv/bin/python Scripts/reporting/make_figures.py                                # rebuild figures
```

## Ground rules

- Raw data in `Data/*/01_raw_collection/` is never edited; everything else is regenerated by code.
- Numbers in deliverables come from scripts (`Scripts/reporting/report_numbers.py`).
- Reddit text is not quoted outside the team; images credit Mapillary (CC BY-SA 4.0); maps credit OpenStreetMap.
  See `Docs/data_ethics.md`.
