# Street images for the study (November 2026)

The full image set under Decision D1 (`Docs/cv_pipeline.md`): at each CBD sample point, the newest Mapillary image
captured from 2020 on, within 30 m, whose camera faces along the point's own road (within 30°). Points on bridges or
freeway-type roads are excluded. Made by `Scripts/cv_study/images.py`; the model outputs are added by
`Scripts/cv_study/models.py`.

| | |
|---|---|
| Points | 423 published CBD points (`Data/cv_pilot_2026-10/cbd/sample_points.csv`) |
| With an image | 246 points on 121 of the 218 street segments: 225 from 21 May 2020, 21 from 13–14 May 2023 (Saskatoon time) |
| No image | 100 points with no 2020+ image within the search box; 66 whose only 2020+ images face across the road (camera on the cross street); 11 excluded (9 bridge, 2 freeway) |
| Images | 238 panoramas (`images/pano_raw/`), each cut into two 90° side views, one per side of the street (`images/<point>_<image>_right.jpg`, `_left.jpg`, 1024 × 768) |
| Licence | Mapillary images are CC BY-SA 4.0: credit "Mapillary and contributors"; derivatives are share-alike |

| File | Contents |
|---|---|
| `points.csv` | the 423 points with `flag` (bridge / freeway) and `status` (`ok`, or why there is no image) |
| `image_manifest.csv` | one row per point with an image: image ID, capture time (UTC), distance to the point, road bearing, camera heading and the angle between them, the panorama and the two side views, brightness/sharpness flags, Mapillary link |
| `run_meta.json` | the rule, the counts and the capture dates in local time |
| `segmentation_shares.csv` | one row per side view (492): share of the street scene in each of the 63 Mapillary Vistas classes, `share_unlabelled`, and `camera_vehicle_share_of_picture` (the camera's car, left out of every share) |
| `object_counts.csv` | one row per side view: street-furniture objects found (street lights, poles, people, cars, benches, trash cans, CCTV cameras, ...) |
| `clip_scores.csv` | one row per side view: CLIP land-use type (top two, probabilities, low-confidence flag) and the nine cue probabilities |
| `segment_indicators.csv` | one row per street segment with an image (121): shares and cue probabilities averaged over both sides and then the points, objects per point, image years, a COVID-2020 flag for people and cars, the most common land-use type |
| `models_meta.json` | models and pinned revisions, settings, device and run time |
| `validation/` | the blind hand-labelling sheets (150 views; 30 for a second coder) and, once filled in, the accuracy results |

The model outputs come from `Scripts/cv_study/models.py`: Mask2Former (Swin-L, Mapillary Vistas, panoptic) at
revision `b9a3e9e` for segmentation and detection, and CLIP ViT-B/32 at revision `3d74acf` for the cues. A repeat run
on the same machine writes identical files. **None of it is validated yet**: no indicator is used until it passes the
hand-label check (`Docs/validation_plan.md`).

The 2023 panoramas were taken from a car-roof camera, so the car's roof shows at the bottom of their side views. The
side views are cut again, byte for byte, from the committed panoramas with
`.venv/bin/python Scripts/cv_study/images.py --recrop-to <folder>`.
