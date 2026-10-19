# Computer-vision pipeline (built environment, X)

Work-plan steps 1–8 (p. 5). Code: `Scripts/cv_pilot/` (how to run: its README). Data: `Data/cv_pilot_2026-10/`.

## Step 1: sample points (done)

- **Roads:** OpenStreetMap via Overpass; 9 classes (motorway to pedestrian). Service lanes, alleys and parking
  aisles are excluded for now; they matter for CPTED and can be added at full scale.
- **Segments:** each OSM way is split wherever it shares a vertex with another way, giving block-length segments.
- **Points:** evenly spaced along each segment (n = round(length / 50 m); one midpoint if shorter than 75 m),
  kept only inside the study-area polygon, with near-duplicates under 10 m dropped (e.g. at junctions).
- **Boundary:** the CBD neighbourhood polygon, `Data/boundaries/central_business_district_osm.geojson`
  (OSM relation 13754152), until the City's own file arrives.

Result: **423 points on 218 segments**. Checks: median spacing 45.6 m (90% between 42 and 59 m); minimum separation
10.1 m; all inside the polygon; 107 segments carry a single point. 11 points are on bridges or freeways and have no
building frontage.

**Fixed:** the first run (`placeholder_box/`) used a hand-drawn box from the August prototype. Only 212 of its 595
points (36%) were in the CBD, and it missed 208 of the 423 CBD points (49%). The tool now defaults to the polygon.

![Sample points](figures/mid_point_october/fig05_sample_points_map.png)

## Step 2: image collection

**October goal: validate the method.** The halfway-point task was to show that the project can source street-level
images as secondary data at its sample points and that the downloaded model (CLIP ViT-B/32) can read them, not to
deliver the full study-period set. Both were shown on 10 images (`cbd_latest_imagery/`). The method follows the
street-view crime studies in `Reference/Literature/Computer_Vision/` (He, Páez & Liu 2017; Hipp et al. 2022;
Zhou et al. 2021; Yue et al. 2022; Su, Li & Qiu 2023); see Section 4 of the October report for the model choice.

**Coverage audit** (`pilot.py coverage`): every Mapillary image within 30 m of every point, by year, flat and 360°.

| Newest image at the point | Points |
|---|---|
| June–August 2026 (study period) | **0** |
| 2023 (360°) | 27 |
| 2020 (360°) | 261 |
| 2017–2019 | 21 |
| 2014 | 88 |
| none within 30 m | 26 |

An independent tiled query found no Mapillary images over the CBD captured from 2024 to 16 Oct 2026. A study-period
download over 60 spread points found 0 images (all logged in `cbd/pilot_attempts.csv`).

![Imagery by year](figures/mid_point_october/fig06_imagery_by_year.png)

**Why it matters and what others do.** Imagery 3–6 years older than the outcomes describes the typical built form,
not the street in summer 2026. Published street-view crime studies keep imagery within 1–3 years of the crime data
(Hipp et al. 2022, *J. Quant. Criminology*: limited to 2017–2020 images for 2018 crime; Zhou et al. 2021; Yue et
al. 2022) or justify a longer gap by showing the environment was stable (He, Páez & Liu 2017). Papers in
`Reference/Literature/Computer_Vision/`.

**Google Street View is not an option.** Google Maps Platform Terms of Service 3.2.3(a) forbid bulk download of
Street View images, and 3.2.3(c) forbid using Google Maps content to train, test, validate or fine-tune models
(read 16 Oct 2026). The work plan allowed Street View only "after confirming its terms of use allow this kind of
analysis"; they do not.

Options are in Decision 1 (`decisions_and_issues.md`).

## Pilot on the newest imagery (`cbd_latest_imagery/`)

10 points in a deterministic farthest-point spread (fixed before any image was seen), newest image within 30 m
each: 10 of 10 found (2014: 1, 2019: 1, 2020: 6, 2023: 2); 8 were 360° images cut into two side-facing views.
CLIP (`openai/clip-vit-base-patch32`, 3 square views per image) scored 8 land-use types and 9 CPTED cues from
`clip_prompts.json`. The Reddit link reproduces the Downtown summary (238 records). `validation_template_blind.csv`
is the blank hand-labelling sheet (no model scores shown).

![Pilot images](figures/mid_point_october/fig07_pilot_images.png)

What the pilot showed:

- Side views from 360° images show frontages, which natural-surveillance cues need.
- **2 of 10 images were captured on the cross street** (camera ~89° off the point's road), so their "side" views
  look down the road. Fix for November: in `choose_image()`, require the camera heading within ~30° of the road
  bearing (mod 180°) before distance ranking.
- Points on bridges (University Bridge) and freeways (Idylwyld) have no frontage: drop or flag them.
- Some CLIP land-use labels are visibly wrong (a building frontage labelled `transit_node`); 1 of 10 is
  low-confidence. Nothing from CLIP is used until it is checked against hand labels.
- The 2014 frames carry a road-survey overlay (distance-measuring instrument, street names), so they came from a
  survey vehicle: worth asking the City whether newer survey imagery exists.

## Steps 3–8 (November onward)

- **3 Segmentation:** a model trained on Mapillary Vistas; share of building, greenery, sky, road, sidewalk,
  fence/wall per image.
- **4 Detection:** streetlights (lighting infrastructure, H3), people, cars, benches, transit stops. Streetlights are
  deliberately not scored by CLIP (thin objects are a CLIP weakness).
- **5 CLIP:** cues that are hard to segment (graffiti, litter, boarded windows, active storefronts).
- **6 Indicators:** combine per CPTED principle; average per segment.
- **7 Validation:** ~150 hand-labelled images (`validation_plan.md`).
- **8 Integration:** join with crime counts and Reddit (see Decision 2 on the Reddit unit).

Images: © Mapillary contributors, CC BY-SA 4.0. Map data © OpenStreetMap contributors (ODbL).
