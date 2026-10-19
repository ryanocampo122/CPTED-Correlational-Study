# Reddit collection, 1 June – 31 August 2026 (study period)

r/saskatoon posts and their comment threads for the revised work plan's study period, collected
16 October 2026 with `Scripts/reddit_collection/reddit_scraper.py` (version 2026-10). This is the
**current** Reddit dataset (perceived safety, Y2).

| | |
|---|---|
| Posts | 195 (June 51, July 65, August 79), all created inside the window (Saskatoon time) |
| Comments | 6,452, of which 6,403 were written inside the window; the 49 later ones are flagged (`comment_in_window`) and left out of every analysis table |
| Search | 12 safety terms (as in June) + 19 crime terms, each under 4 sort orders (124 queries); largest query returned 184 results, below Reddit's ~250 cap |
| Downtown/CBD | 238 records (18 posts, 220 comments, 51 threads); 31.9% negative (95% CI 24.9–39.7) |
| Checks | 30 automated checks pass (`05_audits/verification_report.txt`); every table reproduces byte-for-byte from `01_raw_collection/` |

Full verification: `Docs/verification/october_2026_checks.md`. Method and limitations: `Docs/reddit_pipeline.md`.

## Folders

| Folder | Contents | Made by |
|---|---|---|
| `01_raw_collection/` | posts, comments, GIS export, metadata, summary, search-query log, scraper log, and `collection_code/` (the exact scraper and `common.py` that ran) | the scraper; **never edit** (one exception: on 18 Oct 2026 three folder-path strings in the metadata JSON and `collection_code/reddit_scraper.py` were updated to the current folder layout; no data values changed) |
| `02_derived_analysis/` | per-area summary, thread-inherited sensitivity, environmental cues by area, time of day, night contrasts, season and month tables | `run_all.sh` step 02 |
| `03_extracted_comment_samples/` | candidate example comments (verbatim, re-identifiable: **do not quote outside the team**) | step 05 |
| `04_cleaned_datasets/` | row-level posts and comments with every correction added as new columns; location and cue changelogs | step 01d |
| `05_audits/` | tagging audits, cue precision, sentiment sensitivity, verification report | steps 01, 01c, 02b, 08 |
| `charts/`, `ComputerVision_Sentinel_DataTables_corrected.xlsx` | report charts and a workbook of every table | steps 03, 04 |

Regenerate with `bash Scripts/reddit_analysis/run_all.sh reddit_2026-06-01_2026-08-31 --publish`.
Column definitions for the cleaned files are in `Data/reddit_2025-06-11_2026-06-11/README.md` (same pipeline);
this collection adds `found_by`, `found_by_seed_sets`, `text_has_safety_term`, `text_has_crime_term`
(posts) and `comment_in_window` (comments).

## Read these numbers with care

- 78 of 195 posts contain no seed term in their own title or body (Reddit search matches other fields).
  Dropping those threads leaves Downtown almost unchanged (31.2% vs 31.9% negative).
- The `people` cue counts "homeless"/"homelessness" (16 of 26 Downtown hits). It mixes presence of people
  with mentions of a social group; split it before using it for H4.
- The `lighting` cue is about 50% precise (traffic and car lights). Do not use it for H3.
- `time_of_day` is when a comment was posted, not when the experience happened.
- Comment threads are 84% of Reddit's own count: collapsed replies are not expanded, depth ≤ 4, ≤ 200 per post.
