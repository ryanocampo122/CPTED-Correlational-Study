# Validation plan

**Why this matters.** The AIRI seed grant promised a proof-of-concept framework and pilot data for larger
applications (NSERC Alliance, NFRF Exploration/Transformation, SSHRC–NSERC programs; grant application p. 3).
Reviewers of those programs will ask one question first: does each automated measure agree with careful human
judgement? No correlation (RQ1–RQ3) should be reported for a measure that has not passed its check. The work plan
names two checks (p. 3): about 150 hand-labelled images, and a consistency check of Reddit coding. This page makes
them concrete and adds the checks the October work showed are needed.

## Component checks

| Component | What has to be shown | Method | Proposed target | Status (17 Oct 2026) |
|---|---|---|---|---|
| CV cues and typology (X) | Model outputs agree with people | ~150 images, labelled blind (no model scores shown) on `validation_template_blind.csv`; per-cue precision, recall, F1; typology accuracy | report per cue; use a cue only if F1 ≥ 0.7 (to agree) | blind sheet for 10 pilot images; prompts fixed in `clip_prompts.json` before labelling |
| Labeller agreement | The hand labels themselves are reliable | second coder on ≥ 30 of the 150; Cohen's kappa per cue | κ ≥ 0.6 | not started |
| Image sample | The 150 are not cherry-picked | stratify by land-use type and imagery year; draw by the same deterministic spread order | fixed before labelling | spread order implemented |
| Image currency | Older imagery still describes summer-2026 streets | compare labels on 2020 vs 2023 images where both exist; spot-check a sample against newer sources | stable labels on ≥ 80% | not started (Decision D1, `cv_pipeline.md`) |
| Streetlights (H3) | Detector finds poles in daytime images | count streetlights by hand on a subset; compare with detector | report recall and spacing error | November |
| Reddit place tags | A tagged place is the place meant | other-city review (automated first pass done; 68 Jun–Aug rows still to be confirmed by hand); hand-check a random sample of tags | precision ≥ 0.9 | partly done |
| Reddit cue tags | Cue words mean the environmental cue | held-out sample, 30 per cue (June records): lighting 50%, noise 93%, people 87%, time 90%, weather 90%; add a Jun–Aug sample; split `people` | precision ≥ 0.8; lighting hand-coded | partly done |
| Reddit coding (Dec–Jan) | Location, crime type, cue codes are consistent | codebook; second coder on a random 10–20%; kappa | κ ≥ 0.6 | planned |
| Sentiment | Scores follow human judgement of tone | hand-rate ~200 records (negative / neutral / positive); compare with adjusted VADER | report agreement; keep the 4-scorer sensitivity | sensitivity done; hand-rating planned |
| Recorded crime (Y1) | Locations precise enough for the unit | compare location generalization with segment length; test sensitivity to a coarser unit | — | data added and cleaned (`Data/sps_crime_2026-06-01_2026-08-31/`): locations are hundred-blocks or intersections, 9,650 records on 2,625 points; sensitivity test not started |
| Pipeline | Same inputs give the same outputs | automated checks; byte-for-byte reproduction | all pass | done: 30 checks; 22/22 and 23/23 tables |

Targets are proposals for the co-leads to confirm. Report every result, including cues that fail and are dropped.

## Order of work

1. Fix image matching (heading rule; drop bridges/freeways) **before** drawing the 150, so labels describe the images
   that will be scored.
2. Label blind, then score; never show labellers model output.
3. Second coder on a subset in parallel.
4. Only cues that pass enter the segment indicators (step 6) and the correlations.
