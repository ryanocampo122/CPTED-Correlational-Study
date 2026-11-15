# Computer-vision pipeline (built environment, X)

The study correlates three measures on Downtown's street segments: **X**, the CPTED features of each street, measured
from street images; **Y1**, recorded crime (Saskatoon Police Service); and **Y2**, perceived safety (Reddit). This
pipeline produces X. It follows the eight steps of the revised work plan (p. 5): each step's output is the next
step's input, and no model output reaches the correlations until it has passed the label check (step 7).

Code: `Scripts/cv_pilot/` (steps 1–2 and the October pilot) and `Scripts/cv_study/` (steps 2–7); how to run: their
READMEs. Data: `Data/cv_pilot_2026-10/` and `Data/cv_study_2026-11/`.

## The pipeline at a glance

| Step | In | Does | Out | Status |
|---|---|---|---|---|
| 1 Sample points | OSM roads, CBD polygon | a point about every 50 m along each street segment | 423 points on 218 segments | done |
| 2 Image collection | sample points | newest Mapillary image from 2020 on, within 30 m, facing along the point's road; two side views per image | 246 points on 121 segments; 492 side views | done |
| 3 Segmentation | side views | share of each view in each of 63 classes (building, vegetation, sky, sidewalk, fence…) | `segmentation_shares.csv` | done; shares not yet checked |
| 4 Object detection | side views | counts street lights, benches, trash cans, people, cars… | `object_counts.csv` | done; street lights and seating pass |
| 5 CLIP scoring | side views | land-use type and nine CPTED cues that are hard to segment | `clip_scores.csv` | done; no cue passes |
| 6 CPTED indicators | steps 3–5 | averages the two sides of each point, then the points of each segment | `segment_indicators.csv` (121 segments) | first pass |
| 7 Validation | 150 labelled side views | precision, recall and F1 per cue against the labels | `validation/validation_results.csv` | scored; second coder next |
| 8 Integration | X per segment, Y1, Y2 | joins the three measures on the street segment | input to the correlations | crime join done; Reddit waits for D2 |

## Step 1: sample points

**In:** OpenStreetMap roads and the CBD polygon. **Out:** 423 points on 218 segments
(`Data/cv_pilot_2026-10/cbd/sample_points.csv`). **Status:** done.

The street segment is the unit of analysis, so points are laid out per segment, evenly enough that long and short
streets are measured alike.

- **Roads:** OpenStreetMap via Overpass; 9 classes (motorway to pedestrian). Service lanes, alleys and parking
  aisles are excluded for now; they matter for CPTED and can be added at full scale.
- **Segments:** each OSM way is split wherever it shares a vertex with another way, giving block-length segments
  (`split_at_intersections`).
- **Points:** evenly spaced along each segment (n = round(length / 50 m); one midpoint if shorter than 75 m,
  `resample_polyline`), kept only inside the study-area polygon, with near-duplicates under 10 m dropped (e.g. at
  junctions).
- **Boundary:** the CBD neighbourhood polygon, `Data/boundaries/central_business_district_osm.geojson`
  (OSM relation 13754152), until the City's own file arrives.

**Checks:** median spacing 45.6 m (90% between 42 and 59 m); minimum separation 10.1 m; all inside the polygon;
107 segments carry a single point. 11 points are on bridges or freeways and have no building frontage.

**Fixed:** the first run (`placeholder_box/`) used a hand-drawn box from the August prototype. Only 212 of its 595
points (36%) were in the CBD, and it missed 208 of the 423 CBD points (49%). The tool now defaults to the polygon.

![Sample points](figures/mid_point_october/fig05_sample_points_map.png)

## Step 2: image collection

**In:** the 423 sample points. **Out:** one image at 246 points on 121 segments, cut into 492 side views
(`Data/cv_study_2026-11/image_manifest.csv`, made by `Scripts/cv_study/images.py`). **Status:** done.

### What imagery exists

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

**Google Street View is not an option.** Google Maps Platform Terms of Service 3.2.3(a) forbid bulk download of
Street View images, and 3.2.3(c) forbid using Google Maps content to train, test, validate or fine-tune models
(read 16 Oct 2026). The work plan allowed Street View only "after confirming its terms of use allow this kind of
analysis"; they do not.

### The October pilot set the selection rules

The October task was to show that street-level images can be sourced as secondary data at the sample points and that
the downloaded model (CLIP ViT-B/32) can read them, not to deliver the full set. The method follows the street-view
crime studies in `Reference/Literature/Computer_Vision/` (He, Páez & Liu 2017; Hipp et al. 2022; Zhou et al. 2021;
Yue et al. 2022; Su, Li & Qiu 2023); see Section 4 of the October report for the model choice.

10 points in a deterministic farthest-point spread (fixed before any image was seen), newest image within 30 m
each (`Data/cv_pilot_2026-10/cbd_latest_imagery/`): 10 of 10 found (2014: 1, 2019: 1, 2020: 6, 2023: 2); 8 were 360°
images cut into two side-facing views. CLIP (`openai/clip-vit-base-patch32`, 3 square views per image) scored 8
land-use types and 9 CPTED cues from `clip_prompts.json`. The Reddit link reproduces the Downtown summary (238
records). `validation_template_blind.csv` is the blank labelling sheet (no model scores shown).

![Pilot images](figures/mid_point_october/fig07_pilot_images.png)

What the pilot showed, and the rule each finding became:

- Side views from 360° images show frontages, which natural-surveillance cues need. **Rule:** each panorama is cut
  into two side views, one facing each side of the street.
- **2 of 10 images were captured on the cross street** (camera ~89° off the point's road), so their "side" views
  look down the road. **Rule:** `choose_image()` takes `road_bearing` and `max_off_road_deg`; the camera heading must
  be within 30° of the road bearing (mod 180°).
- Points on bridges (University Bridge) and freeways (Idylwyld) have no frontage. **Rule:** `bridge_or_freeway()`
  flags the 11 points (9 bridge, 2 freeway); they stay in the point list and get no image.
- Some CLIP land-use labels are visibly wrong (a building frontage labelled `transit_node`); 1 of 10 is
  low-confidence. **Rule:** nothing from CLIP is used until it is checked against the labels (step 7).
- The 2014 frames carry a road-survey overlay (distance-measuring instrument, street names), so they came from a
  survey vehicle: worth asking the City whether newer survey imagery exists.

### Decision D1 (decided November 2026): image dates

Imagery 3–6 years older than the outcomes describes the typical built form, not the street in summer 2026. Published
street-view crime studies keep imagery within 1–3 years of the crime data (Hipp et al. 2022, *J. Quant.
Criminology*: limited to 2017–2020 images for 2018 crime; Zhou et al. 2021; Yue et al. 2022) or justify a longer gap
by showing the environment was stable (He, Páez & Liu 2017).

No open source has street-level imagery of the CBD from June–August 2026 (searched 30 Oct 2026):

- **Mapillary:** none of the 423 points has a study-period image; the newest CBD image is from May 2023. Across
  Saskatoon the only newer images are 181 from May 2024, the closest about 5 km from Downtown.
- **Panoramax:** no Downtown images. **KartaView:** newest image 2019.
- **Google Street View:** terms forbid bulk download and model use (above).

| Option | For | Against |
|---|---|---|
| (a) Newest Mapillary image at each point, with the 2026 crime and Reddit data | available now; 288 of 423 points (163 of 218 segments) have 2020 or 2023 imagery | 3–6 year gap; May, not summer; 55 segments without a 2020/2023 image |
| (b) Ask the City for recent street-level imagery (e.g. road-survey imagery; the 2014 Mapillary frames came from a survey vehicle) | could be recent and complete | depends on the City; data-sharing terms |
| (c) Capture new imagery | current, complete | primary data collection (the plan is secondary-only); cannot cover summer 2026 |
| (d) Match the outcomes to the images: 2023 images with 2023 crime and Reddit | no date gap | 2023 imagery covers only 27 points on 19 of 218 segments; needs a new SPS extract (the SPS crime map warns against comparing its data over time) and a new Reddit collection, which reaches fewer older posts (122 for June–August 2023 against 168 for 2026, same terms and settings, 7 Nov 2026) |

**Decision: (a).** Each point uses its newest Mapillary image from 2020 on within 30 m whose camera faces along the
point's own road (within 30°, the pilot's rule above). The outcomes stay June–August 2026 (the SPS extract and the
Reddit collection).

### What step 2 produced

Before the camera-direction rule, 288 points on 163 of the 218 segments had a 2020 or 2023 image; with it,
**246 points on 121 segments (56%)** have one: 225 from 21 May 2020 and 21 from 13–14 May 2023. The rule removed 66
points whose only images were taken from the cross street; most are on the east–west streets (19th to 25th Street),
because the 2020 survey drove the avenues. The other points get no image score, so 97 segments have no X value and
are left out of the correlations; every result says it describes the 121 covered segments. The capture year is kept
with every image score.

![Image set](figures/mid_point_november/fig11_image_set.png)

**Assumption, stated with every result that uses X:** the street features measured (building frontage, greenery,
lighting infrastructure, fences and walls, sidewalks, signs of disorder) did not change substantially between the
image year (2020 or 2023) and summer 2026. X therefore describes the typical built form of each segment, not its
state in summer 2026.

**Limitations:**

1. **Date gap:** the images are 3 years (2023) or 6 years (2020) older than the crime and Reddit data. Changes in
   between (new buildings, closures, removed or added lighting) are not seen.
2. **Season:** every 2020 and 2023 image was taken in May (21 May 2020; 13–14 May 2023), not June–August, so trees
   have less foliage and greenery shares are likely lower than in summer.
3. **COVID-19:** the 2020 images were captured in a single day during COVID-19 restrictions. Cues that depend on
   activity (people present, open storefronts, parked cars) describe that day, not a normal summer; they are flagged
   in the results and not read as fixed features of the street.
4. **Coverage:** 97 of the 218 segments (44%) have no usable 2020 or 2023 image, and they are not spread evenly:
   the avenues are covered and most east–west streets are not, so X describes mainly the avenues.
5. **Mixed years:** 21 points use 2023 images and 225 use 2020 images; the capture year is recorded so results can be
   checked by year. The 2023 panoramas were taken from a car roof; the camera car is left out of every share.

**How the assumption is tested** (validation plan, "Image currency"): the same points are labelled and scored on
their 2014 and 2020 images, which exist together at 243 points on 144 segments. If the measured features were stable
over those six years, stability over the six years to 2026 is plausible; features that change are reported and
treated with caution. A 2020-against-2023 comparison is not possible: only 3 points have both.

## Steps 3–5: the image models

**In:** the 492 side views. **Out:** `segmentation_shares.csv`, `object_counts.csv` and `clip_scores.csv` in
`Data/cv_study_2026-11/`, made by `Scripts/cv_study/models.py` (about 13 minutes on the Mac's GPU; a repeat run writes
identical files). **Status:** done; only street lights and seating have passed the label check so far (step 7).

Segmentation and detection come from one model, so every share and count describes the same reading of each view.
CLIP covers what a segmentation model has no class for.

- **3 Segmentation:** one panoptic model, Mask2Former (Swin-L) trained on Mapillary Vistas, pinned to revision
  `b9a3e9e`, run at the side views' full 1024 × 768 size. It gives the share of each view's street scene in each of
  63 classes; across the 492 side views: building 25%, sky 24%, road 21%, sidewalk 7%, vegetation 7%, fence 1.3%.
  - **Tree crowns** (`refine_crowns`): the model outlines each crown as one solid shape, and in May most trees are
    bare, so the sky and walls seen between the branches came out as vegetation. Inside each crown a pixel now stays
    vegetation only if it looks like part of the tree (a trunk or limb, leaf-green, or a dark, shaded branch);
    sky-coloured gaps become sky, and the rest take the class beside the tree, usually the building behind it. The
    colour rules were set by eye on five views and are not part of the label check.
  - **Camera car:** the 2023 panoramas were taken from a car roof, which fills about 26% of each of their side views
    and is left out of every share. Its mirror-like paint reflects the scene above it, and in 11 of the 42 views from
    2023 the model labelled the reflections instead of the car; there the typical roof for that side of the car stands
    in (`typical_roofs`, `fill_roof`).
- **4 Detection:** the same model counts street-furniture objects: street lights in 274 of 492 views, poles in 466,
  benches in 92, trash cans in 182, people in 57, cars in 261. Objects found on the camera roof are not counted.
  Street lights are deliberately not scored by CLIP (thin objects are a CLIP weakness). People and cars in 2020
  images are flagged (COVID-19 day).
- **5 CLIP:** land-use type and the nine cues on every side view. The land-use label looks unreliable: it calls 230
  of 492 views `surface_parking` and only 8 `commercial_street`, and 109 are low-confidence.

![Segmentation examples](figures/mid_point_november/fig12_segmentation_examples.png)

## Step 6: CPTED indicators per segment

**In:** the step 3–5 tables. **Out:** `segment_indicators.csv` (121 segments). **Status:** first pass.

The correlations are per segment, so each measure is averaged first over the two sides of a point, then over the
points of a segment; a segment with more points does not count more. Combining the measures into one indicator per
CPTED principle waits for the validation results, so only measures that pass step 7 go in.

![Indicator maps](figures/mid_point_november/fig13_indicator_maps.png)

## Step 7: validation (the label check)

**In:** 150 side views, labelled blind (no model scores shown). **Out:**
`Data/cv_study_2026-11/validation/validation_results.csv`, made by `Scripts/cv_study/validation.py score`.
**Status:** scored; the second coder's 30 views are not labelled yet.

The 150 views are drawn by a fixed rule from 12 land-use × image-year groups, in proportion to each group's size, so
they are not hand-picked. A cue is used only if its F1 is at least 0.7; the second coder's agreement target is a
kappa of at least 0.6 (`validation_plan.md`).

**Result:** 2 of the 12 checks pass, both from the object counts: street lights (F1 0.92) and seating from bench
counts (0.72). People from person counts do not pass (0.46). No CLIP cue passes, and CLIP's land-use label matches the
labels for 39% of views. Nothing else is used yet.

## Step 8: integration

**In:** X per segment (step 6), crime per segment (Y1) and Reddit (Y2). **Out:** one table per segment for the
correlations. **Status:** crime join done; Reddit waits for Decision D2.

- **Crime (Y1):** records are placed on the same 218 segments (`crime_data.md`). The 121 segments with an image hold
  164 of the 255 placed records (64%) and 6 of the 11 hot spots.
- **Reddit (Y2):** posts rarely name a street, so the unit for Reddit is still open (Decision D2 in
  `reddit_pipeline.md`).

Images: © Mapillary contributors, CC BY-SA 4.0. Map data © OpenStreetMap contributors (ODbL).
