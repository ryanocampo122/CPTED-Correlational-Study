# Label check of the image models (blind)

`validation_blind.csv` lists 150 side views for the first coder; `validation_blind_coder2.csv` lists 30 of the same
views for a second coder, who labels them **without seeing the first coder's sheet**. Neither sheet shows any model
output. The views were drawn by `Scripts/cv_study/validation.py sample` before anyone labelled, by a rule fixed in
advance (`sample_strata.json`): land-use type × image year strata, proportional, in the deterministic spread order.

**Status (8 Nov 2026):** all 150 views in `validation_blind.csv` are labelled; the `labelled_by` column records who
labelled each row. The 30 views in `validation_blind_coder2.csv` are not labelled yet, and nothing has been scored.

## How to label

Open each `image_file` (the path is relative to this folder) and fill in its row. Judge only what is visible in
the picture. Leave a cell blank if you cannot tell (it then counts as not labelled, not as 0).

| Column | What to enter |
|---|---|
| `human_typology` | the one land-use type that best describes the view: `commercial_street` (storefronts and shops), `institutional` (a large public building: city hall, library, school), `residential` (houses or apartment buildings), `surface_parking` (a parking lot with parked cars), `transit_node` (a bus stop or transit terminal), `road_corridor` (a wide road or intersection dominated by traffic), `park_open_space` (a park with grass and trees), `riverfront_walkway` (a paved path beside the river) |
| `human_graffiti_0_1` | 1 if there is graffiti or tagging on a wall or object, else 0 |
| `human_litter_0_1` | 1 if litter or garbage is visible on the ground, else 0 |
| `human_boarded_windows_0_1` | 1 if a building has boarded-up or broken windows, else 0 |
| `human_vacant_lot_0_1` | 1 if there is an empty vacant lot or an abandoned building, else 0 |
| `human_active_storefront_0_1` | 1 if there is an open storefront with shop windows and signs, else 0 |
| `human_windows_overlook_0_1` | 1 if a building has many windows facing the street, else 0 |
| `human_people_present_0_1` | 1 if at least one person is visible, else 0 |
| `human_fences_0_1` | 1 if a fence, gate or barrier runs along a property edge, else 0 |
| `human_seating_0_1` | 1 if a bench or other outdoor seating is visible, else 0 |
| `human_streetlight_visible_0_1` | 1 if at least one street light (the lamp, not just a bare pole) is visible, else 0 |
| `human_notes` | anything unusual (e.g. the view is blocked by a truck, or shows mostly the camera car) |

The 2023 views (taken from a car roof) show the camera car at the bottom; ignore it. The 2020 views were taken on
21 May 2020 during COVID-19 restrictions, so few people may be out: label what is there.

## Scoring

When the sheets are filled in, run `.venv/bin/python Scripts/cv_study/validation.py score`. It writes
`validation_results.csv` (per cue and model: precision, recall, F1, and Cohen's kappa between the coders) and
`validation_results.json`. A cue is used only if F1 ≥ 0.7 and kappa ≥ 0.6 (proposed targets,
`Docs/validation_plan.md`). Until then `validation_results.json` says `pending`.
