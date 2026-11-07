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

**Decision D1 (decided November 2026): image source for the study period.** No open source has street-level
imagery of the CBD from June–August 2026 (searched 30 Oct 2026):

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

**Decision: (a).** Each point uses its newest Mapillary image within 30 m: 2023 at 27 points and 2020 at 261, so
288 points on 163 of the 218 segments (75%). The outcomes stay June–August 2026 (the SPS extract and the Reddit
collection). The other 135 points (newest image 2014–2019, or none) get no image score, so 55 segments have no X
value and are left out of the correlations; every result says it describes the 163 covered segments. The capture
year is kept with every image score.

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
4. **Coverage:** a quarter of the segments (55 of 218) have no 2020 or 2023 image.
5. **Mixed years:** 27 points use 2023 images and 261 use 2020 images; the capture year is recorded so results can be
   checked by year.

**How the assumption is tested** (validation plan, "Image currency"): the same points are labelled and scored on
their 2014 and 2020 images, which exist together at 243 points on 144 segments. If the measured features were stable
over those six years, stability over the six years to 2026 is plausible; features that change are reported and
treated with caution. A 2020-against-2023 comparison is not possible: only 3 points have both.

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
- **8 Integration:** join with crime counts and Reddit (see Decision D2 in `reddit_pipeline.md` on the Reddit unit).

Images: © Mapillary contributors, CC BY-SA 4.0. Map data © OpenStreetMap contributors (ODbL).
