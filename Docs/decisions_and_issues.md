# Decisions and issues

## Decisions needed (raised 17 Oct 2026)

### D1. Image source for the study period
No Mapillary imagery from June–August 2026, or from any date after 2023, exists over the CBD
(`Docs/cv_pipeline.md`). Google Street View's terms forbid bulk download and model use.

| Option | For | Against |
|---|---|---|
| (a) Newest Mapillary imagery, date stated | available now; 288 of 423 points have 2020 or 2023 imagery | 3–6 year gap (12 for 2014-only points); 26 points have none |
| (b) Ask the City for recent street-level imagery (e.g. road-survey imagery; the 2014 Mapillary frames came from a survey vehicle) | could be recent and complete | depends on the City; data-sharing terms |
| (c) Capture new imagery | current, complete | primary data collection (the plan is secondary-only); cannot cover summer 2026 |

**Recommended:** (b) now through Elisabeth Miller; (a) as fallback, describing imagery as typical built form and
testing stability where 2020 and 2023 images both exist.

### D2. Spatial unit for Reddit
Reddit places records in neighbourhoods, not on 50 m segments: the most-named Downtown street (2nd Avenue) appears in
8 of 238 Downtown records; 9 of 14 streets/landmarks appear fewer than 5 times. With Downtown alone, Reddit is one
value and cannot be correlated with anything.
**Recommended:** RQ1 (X ↔ Y1) at segment level; RQ2 and RQ3 across several neighbourhoods, adding comparison
areas with enough Reddit records (Riverbank/Meewasin 155, Broadway 39; others are small).

### D3. SPS crime data (settled 17 Oct 2026)
Crime data obtained and added (17 Oct 2026): `Data/sps_crime_2026-06-01_2026-08-31/`, cleaned by
`Scripts/crime_data/clean_sps_crime.py` (9,650 records, 2,982 in the study categories). Checked against the checklist in
`Docs/crime_data.md`: locations are hundred-blocks or intersections, and the extract has no premise type, occurrence
time or violation code, so street robbery includes commercial robbery and assault stays conditional. Not raised in
the October report.

## Decisions made

| Date | Decision | Where |
|---|---|---|
| 2026-10 | Revised plan: secondary data only; Reddit replaces surveys; imagery replaces sensors; study period Jun–Aug 2026 | `Plan/workplan_revised_2026-10.pdf` |
| 2026-10 | Crime categories: five included, assault conditional, four excluded | work plan p. 4; `crime_data.md` |
| 2026-10-16 | Whole-word tagging, hand-reviewed other-city exclusions, adjusted VADER, local time, thread-bootstrap CIs | `Scripts/reddit_analysis/README.md` |
| 2026-10-16 | Crime seed terms added to the Reddit collection; comments after the window excluded from analysis | `reddit_pipeline.md` |
| 2026-10-16 | Study area = CBD polygon (OSM copy) until the City's file arrives; placeholder box retired | `cv_pipeline.md` |
| 2026-10-16 | Streetlights from detection, not CLIP | `Scripts/cv_pilot/clip_prompts.json` |

## Issue log

Status: **open**, **fixed**, **mitigated** (limitation kept and disclosed).

| # | Found | Issue | Effect | Status / fix |
|---|---|---|---|---|
| 1 | 2026-10-16 | The analysis code that produced the Jun–Aug tables was missing from the folder and never committed; the scraper could not import `common.py` | results not reproducible; collector broken | **fixed** 16 Oct 2026: rebuilt; both collections reproduce byte-for-byte |
| 2 | 2026-10-16 | Sample points generated in a hand-drawn placeholder box | 64% of points outside the CBD; 49% of the CBD missed | **fixed** 16 Oct 2026: regenerated in the CBD polygon; polygon is the default |
| 3 | 2026-10-16 | No study-period street imagery | imagery and outcomes years apart | **open**: D1 |
| 4 | 2026-10-16 | Pilot images matched across intersections (2 of 10) | side views of the wrong street | **open**: heading rule in `choose_image()` (Nov) |
| 5 | 2026-10-16 | 11 points on bridges/freeways | no frontage to measure | **open**: drop or flag (Nov) |
| 6 | 2026-10-16 | 78 of 195 posts contain no seed term in their text | off-topic threads | **mitigated**: flags kept; Downtown 31.2% vs 31.9%; relevance coding Dec–Jan |
| 7 | 2026-10-16 | `people` cue mostly "homeless"/"homelessness" (16 of 26 Downtown hits) | conflates natural surveillance with a group label; stigma risk | **open**: split before H4 |
| 8 | 2026-10 (earlier) | `lighting` cue ~50% precise | cannot support H3 | **mitigated**: not used for H3; hand-code; detection for streetlights |
| 9 | 2026-10-16 | Comment threads 84% complete (collapsed replies not expanded) | some discussion missed | **mitigated**: disclosed; could raise `replace_more_limit` in a re-collection |
| 10 | 2026-10-16 | SPS map locations approximate | segment counts uncertain | **open**: data added 17 Oct; locations are hundred-blocks or intersections (9,650 records on 2,625 points), so crime is counted per segment, not per point (`crime_data.md`); premise type still to request from SPS |
| 11 | 2026-10-16 | Jun–Aug other-city review decisions lost with the code | cannot show who decided | **mitigated**: 68 rows reconstructed from the changelog (17 exclude, 51 keep), marked **to be confirmed by hand** |
| 12 | 2026-10-16 | The October README from the update zip said the pilot "ran end to end" before any image existed, and quoted naive CIs (26.3–38.1) instead of thread-bootstrap CIs (24.9–39.7) | overstated progress | **fixed**: replaced; numbers now come from `report_numbers.py` |
| 13 | 2026-10-16 | Chart subtitles hard-coded from the June data (e.g. "14 other-city downtowns" on Jun–Aug chart 1; it is 16) | wrong captions | **fixed** 16 Oct 2026: computed from data |
| 14 | 2026-10-16 | Google Street View terms forbid bulk download and model use | the plan's gap-filler is unavailable | **closed**: not used |
| 15 | 2026-08 | Reddit API secret was hard-coded in the scraper shared in the August package | credential exposure | **open until confirmed**: removed from all files and never in git history; **confirm the key was rotated** at reddit.com/prefs/apps |
| 16 | 2026-10-16 | Precision samples judged on June records only | Jun–Aug precision assumed equal | **open**: add a Jun–Aug sample in coding |

Earlier corrections to the July/August analysis (substring tags, other-city quotes, VADER seed bias, UTC dates,
missing CIs) are documented in `Scripts/reddit_analysis/README.md` ("What changed since August").

Fixes are dated rather than linked to commits: this repository's history starts on 17 Oct 2026 (commit 22eb390).
