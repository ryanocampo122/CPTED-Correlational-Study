# Project history

| When | What | Where |
|---|---|---|
| Jan 2026 | AIRI Research Capacity Building Grant application: *A Privacy-Preserving GeoAI Framework for Urban CPTED Decision Support Using Environmental Sensing and Community Narratives* (co-leads Dr. Varuni Jayasooriya, SENS, and Dr. Timothy Kang, Sociology; collaborators Dr. Khan Wahid, ECE, and Elisabeth Miller, City of Saskatoon). $15,000, 1 Apr 2026 – 1 Apr 2027 | `Plan/AIRI_2026_grant_application.pdf` |
| Jun 2026 | Phase 1: literature review and pilot-site selection for sensor deployment; first Reddit collection (11 Jun 2025 – 11 Jun 2026: 426 posts, 14,889 comments) | `Docs/literature review/`, `Reference/Presentations/ComputerVision_Sentinel_Phase1_Briefing.pdf`, `Data/reddit_2025-06-11_2026-06-11/` |
| Jul 2026 | Initial findings summary (site identification, perception scan; counted posts only, before the "river"/"driver" fix) | removed 19 Oct 2026; its data were copies of `Data/reddit_2025-06-11_2026-06-11/01_raw_collection/`, and its literature-review draft was superseded by the August version, now `Docs/literature review/Master_lit_review.docx` |
| Jul–Aug 2026 | Meewasin data-quality memo ("river" matched "driver", 21 Jul); August report with verified location tags (Downtown the strongest signal); survey drafts for Downtown, Meewasin and Sutherland | `Deliverables/2026-08_august_report/`, `Archive/surveys_dropped_2026-10/` |
| Aug 2026 | First Mapillary + CLIP prototype (hand-drawn site boxes) | removed Oct 2026; git history at 00a9ab7 (`Archive/initial_cv_prototype_2026-08/`) |
| Oct 2026 | Re-audit of the June collection: cue tags, other-city quotes, sentiment bias, local time, CIs corrected | `Scripts/reddit_analysis/README.md` ("What changed since August") |
| Oct 2026 | Revised work plan: cross-sectional correlational study on open secondary data, 1 Jun – 31 Aug 2026; surveys and sensors dropped | `Plan/workplan_revised_2026-10.pdf` |
| 16–17 Oct 2026 | October tasks: crime categories; Reddit for the study period; CBD sample points; imagery coverage audit and 10-image pilot; folder put under version control and reorganized; analysis pipeline rebuilt and verified | `Deliverables/2026-10_october_update/`, `Docs/verification/` |
| 17 Oct 2026 | This repository's history starts (first commit 22eb390); fixes before then are dated in `decisions_and_issues.md`, not linked to commits | `git log` |
| 18 Oct 2026 | One-command pipeline: `./flight --execute_flight` installs, collects (Reddit, Mapillary), loads CLIP and VADER, and rebuilds and compares every result in `RESULTS_FINAL/EXECUTION-<n>/` | `Scripts/flight/`, `Docs/workflow.md` |
| 18 Oct 2026 | 2010–2025 climate–crime study cleared: its Reddit (2009–2025) and Statistics Canada crime data and scripts removed; the ECCC climate data kept for possible use | `Data/climate_2010_2025/`, `Scripts/climate_data/` |
| 19 Oct 2026 | Former project name replaced by ComputerVision_Sentinel across the repository: Word files, archival August scripts, scraper copies, run summaries and logs (renamed), the October report PDF (re-exported), `.env` | `Deliverables/` and `Data/reddit_*/` READMEs |
