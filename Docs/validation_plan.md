# Validation plan

## Component checks

| Component | What has to be shown | Method | Proposed target | Status (8 Nov 2026) |
|---|---|---|---|---|
| CV cues and typology (X) | Model outputs agree with people | ~150 images, labelled blind (no model scores shown) on `Data/cv_study_2026-11/validation/validation_blind.csv`; per-cue precision, recall, F1; typology accuracy (`Scripts/cv_study/validation.py score`) | report per cue; use a cue only if F1 ≥ 0.7 (to agree) | done: 150 side views labelled and scored (`validation_results.csv`); street lights (F1 0.92) and seating (0.72) pass from the object counts; no CLIP cue passes; CLIP land use 39% |
| Labeller agreement | The labels themselves are reliable | second coder on ≥ 30 of the 150; Cohen's kappa per cue | κ ≥ 0.6 | 30 views marked for the second coder (`validation_blind_coder2.csv`); not started |
| Image sample | The 150 are not cherry-picked | stratify by land-use type and imagery year; draw by the same deterministic spread order | fixed before labelling | done: 12 land-use × year strata, proportional, spread order (`sample_strata.json`) |
| Image currency | Older imagery still describes summer-2026 streets | compare labels on 2014 vs 2020 images at the 243 points that have both (2020 vs 2023: only 3 points); spot-check a sample against newer sources | stable labels on ≥ 80% | not started (Decision D1 decided: newest image at each point, `cv_pipeline.md`) |
| Streetlights (H3) | Detector finds poles in daytime images | count streetlights on the labelled views; compare with detector | report recall and spacing error | detector run (Mask2Former street-light class: 274 of 492 views); checked by the `human_streetlight_visible` column |
| Reddit place tags | A tagged place is the place meant | other-city review (automated first pass done for all 144 rows; to be confirmed by hand with `blind_review.py`); hand-check a random sample of tags | precision ≥ 0.9 | partly done |
| Reddit cue tags | Cue words mean the environmental cue | held-out sample, 30 per cue (June records), automated first pass: lighting 50%, noise 93%, people 87%, time 90%, weather 90%; to be judged by hand with `blind_review.py`; add a Jun–Aug sample; split `people` | precision ≥ 0.8; lighting hand-coded | partly done |
| Reddit coding (Dec–Jan) | Location, crime type, cue codes are consistent | codebook; second coder on a random 10–20%; kappa | κ ≥ 0.6 | planned |
| Sentiment | Scores follow human judgement of tone | hand-rate ~200 records (negative / neutral / positive); compare with adjusted VADER | report agreement; keep the 4-scorer sensitivity | sensitivity done; hand-rating planned |
| Recorded crime (Y1) | Locations precise enough for the unit | compare location generalization with segment length; test sensitivity to a coarser unit | — | data added and cleaned (`Data/sps_crime_2026-06-01_2026-08-31/`): locations are hundred-blocks or intersections, 9,650 records on 2,625 points; sensitivity test not started |
| Pipeline | Same inputs give the same outputs | automated checks; byte-for-byte reproduction | all pass | done: 30 checks; 22/22 and 23/23 tables |

Targets are proposals and may change. Report every result, including cues that fail and are dropped.

## Order of work

1. Fix image matching (heading rule; drop bridges/freeways) **before** drawing the 150, so labels describe the images
   that will be scored. **Done (November 2026).**
2. Label blind, then score; never show labellers model output.
3. Second coder on a subset in parallel.
4. Only cues that pass enter the segment indicators (step 6) and the correlations.
