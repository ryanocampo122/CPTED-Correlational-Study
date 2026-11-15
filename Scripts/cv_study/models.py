#!/usr/bin/env python3
"""
models.py
=========
CPTED Vision | November 2026: segmentation, detection and CLIP on every side view
(work plan steps 3-5, Docs/cv_pipeline.md)

One panoptic model does both segmentation and detection: Mask2Former (Swin-L) trained on Mapillary
Vistas, pinned to one revision like CLIP. For each side view it gives
  * segmentation: the share of the picture that is each of the 65 Vistas classes (building, vegetation,
    sky, road, sidewalk, fence, wall, terrain, ...);
  * detection: how many separate objects of each street-furniture class it found (street lights, poles,
    people, cars, benches, trash cans, CCTV cameras, bike racks, ...).
CLIP (the pilot's ClipScorer and clip_prompts.json) scores the cues that are hard to segment: graffiti,
litter, boarded windows, active storefronts, and the land-use type.

Tree crowns are checked pixel by pixel before the shares are counted (refine_crowns). The model outlines each
crown as one solid shape, so in the May images, when most trees are bare, the sky and walls seen between the
branches came out as Vegetation. Inside a crown a pixel now stays Vegetation only if it looks like part of the tree.

In the 2023 car-roof images the roof's mirror-like paint reflects the scene above it, and in some right-side views
the model labelled those reflections (trees, sky, a car) instead of the camera car. The roof is in nearly the same
place in every view of one side, so where the model missed it, the typical roof for that side stands in
(typical_roofs, fill_roof), and objects found on it are not counted.

Reads Data/cv_study_2026-11/image_manifest.csv and images/. Writes there:
  segmentation_shares.csv   one row per side view: share of each class (adds up to 1 with share_unlabelled)
  object_counts.csv         one row per side view: objects found per street-furniture class
  clip_scores.csv           one row per side view: land-use type and cue probabilities
  segment_indicators.csv    one row per street segment: the side views averaged per point, then per segment
  models_meta.json          models, revisions, settings, device and counts

Nothing here is a measurement until it passes the label check (Docs/validation_plan.md). In 2020
images, people and cars describe one day during COVID-19 restrictions (Decision D1): they are flagged.

USAGE (repository root)
  .venv/bin/python Scripts/cv_study/models.py                   # all side views (~30 min on Apple GPU)
  .venv/bin/python Scripts/cv_study/models.py --limit 4 --out <scratch folder>   # quick trial
"""
# Command-line options, file paths, the run record and timing
import argparse
import json
import sys
import time
from pathlib import Path

# Numbers, tables and image files
import numpy as np
import pandas as pd
from PIL import Image

# Shape tools for the tree-crown check (opening, nearest-pixel search)
from scipy import ndimage

# The pilot's CLIP scorer and helpers
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "cv_pilot"))
import pilot_lib as L  # noqa: E402

# Default input and output folder
REPO = HERE.parents[1]
STUDY = REPO / "Data" / "cv_study_2026-11"

# The panoptic model, pinned like CLIP: this exact revision, never "latest"
SEG_MODEL = "facebook/mask2former-swin-large-mapillary-vistas-panoptic"
SEG_REVISION = "b9a3e9eb06a6477a741c98cf91cfca11e620e59d"

# Street-furniture classes counted as objects, and the ones that only describe the day the image was taken
OBJECT_CLASSES = ["Street Light", "Pole", "Utility Pole", "Traffic Light", "CCTV Camera", "Bench", "Trash Can",
                  "Bike Rack", "Fire Hydrant", "Mailbox", "Phone Booth", "Billboard", "Person", "Bicyclist", "Car"]
TRANSIENT_CLASSES = ["Person", "Bicyclist", "Car"]

# The segmentation shares carried up to the street segments (the rest stay in segmentation_shares.csv)
INDICATOR_SHARES = ["Building", "Vegetation", "Sky", "Road", "Sidewalk", "Fence", "Wall", "Terrain", "Car"]

# The camera's own car (the 2023 panoramas were taken from a car roof): left out of every share, so a street
# filmed from a roof is not made to look emptier than one filmed without
CAMERA_VEHICLE_CLASSES = ["Ego Vehicle", "Car Mount"]

# The car-roof image years, and the least share of a picture the model must call the camera car for its own
# outline to be used (below it, the typical roof for that side stands in; see typical_roofs)
CAMERA_CAR_YEARS = [2023]
ROOF_MIN_SHARE = 0.02

# Post-processing settings: the library's defaults, written down so they are part of the record
PANOPTIC_SETTINGS = {"threshold": 0.5, "mask_threshold": 0.5, "overlap_mask_area_threshold": 0.8}

# Tree-crown check settings, in CIE Lab colour (L = lightness 0-100, a = green (-) to red (+), b = blue (-) to
# yellow (+)): the width below which a part of a crown counts as a trunk or limb, and the leaf, shaded-branch and
# sky colours. Set by eye on five views (P0054, P0055, P0146, P0261, P0375); not part of the label check
CROWN = {"thin_px": 21, "leaf_max_a": -4, "leaf_min_b": -10, "leaf_max_l": 92, "wood_max_l": 38,
         "blue_sky_max_b": -8, "blue_sky_min_l": 50, "white_sky_min_l": 82, "white_sky_max_b": 4, "white_sky_max_a": 6}

# The classes a gap in a crown can show behind the tree (thin things such as poles are left out on purpose)
CROWN_BACKGROUND_CLASSES = ["Building", "Wall", "Fence", "Sky", "Terrain", "Water", "Mountain", "Bridge", "Tunnel",
                            "Snow", "Sand"]


def slug(label: str) -> str:
    """Column-name form of a class name: "Street Light" -> "street_light".

    :param label: a Vistas class name
    :return: lower case, words joined by underscores, brackets and dashes dropped
    """
    return "_".join(label.lower().replace("(", "").replace(")", "").replace("-", " ").split())


def pick_device() -> str:
    """The fastest device available: Apple GPU, NVIDIA GPU, or the CPU.

    :return: "mps", "cuda" or "cpu"
    """
    import torch
    # Apple GPU first (this Mac), then NVIDIA, else the processor
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class PanopticModel:
    """Mask2Former on one side view at its full 1024 x 768 size (no shrinking, so thin poles survive)."""

    def __init__(self, device: str):
        """Load the pinned model and its image processor.

        :param device: "mps", "cuda" or "cpu"
        """
        from transformers import AutoImageProcessor, Mask2FormerForUniversalSegmentation
        # The processor normalises colours but keeps the picture's own size (the slow, original processor,
        # pinned so a library update cannot change results); the model goes to the device
        self.processor = AutoImageProcessor.from_pretrained(SEG_MODEL, revision=SEG_REVISION, do_resize=False,
                                                            use_fast=False)
        self.model = Mask2FormerForUniversalSegmentation.from_pretrained(SEG_MODEL, revision=SEG_REVISION)
        self.model.to(device).eval()
        self.device = device
        # Class names by id, in the model's own order
        self.labels = [self.model.config.id2label[i] for i in range(len(self.model.config.id2label))]

    def run(self, im: Image.Image) -> tuple[np.ndarray, list[dict]]:
        """Segment one picture.

        :param im: an RGB side view
        :return: (segment id per pixel, list of {id, label_id, score} for each segment)
        """
        import torch
        # Prepare the picture, run the model without training bookkeeping, then turn its masks into segments
        inputs = self.processor(images=im, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
        result = self.processor.post_process_panoptic_segmentation(
            outputs, target_sizes=[im.size[::-1]], label_ids_to_fuse=set(), **PANOPTIC_SETTINGS)[0]
        return result["segmentation"].cpu().numpy(), result["segments_info"]


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Picture colours to CIE Lab (lightness, green-red, blue-yellow), which match how colours look to people.

    :param rgb: the picture as numbers from 0 to 1, height x width x 3
    :return: L, a and b for every pixel, height x width x 3
    """
    # Undo the screen brightness curve, then mix the three channels into X, Y, Z relative to daylight white
    linear = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    xyz = linear @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    # The cube-root step, then lightness and the two colour axes
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def row_neighbour(label_map: np.ndarray, wanted: np.ndarray) -> np.ndarray:
    """For every pixel, the class of the nearest wanted pixel in the same row, to its left or right.

    :param label_map: class id of every pixel
    :param wanted: True where a pixel may be used
    :return: a class map, -1 where the row has no wanted pixel
    """
    # Picture size, and the column number of every pixel
    height, width = label_map.shape
    cols = np.broadcast_to(np.arange(width), (height, width))
    # Column of the nearest wanted pixel to the left (-1 if none) and to the right (the width if none)
    left = np.maximum.accumulate(np.where(wanted, cols, -1), axis=1)
    right = np.minimum.accumulate(np.where(wanted, cols, width)[:, ::-1], axis=1)[:, ::-1]
    # The closer side wins; a side with no wanted pixel counts as very far away
    far = 2 * width
    pick = np.where(np.where(left >= 0, cols - left, far) <= np.where(right < width, right - cols, far), left, right)
    # The class at the picked column, or -1 where the row had none
    found = (pick >= 0) & (pick < width)
    out = np.full(label_map.shape, -1)
    out[found] = np.take_along_axis(label_map, np.clip(pick, 0, width - 1), axis=1)[found]
    return out


def refine_crowns(rgb: np.ndarray, label_map: np.ndarray, labels: list[str]) -> np.ndarray:
    """Re-check every pixel the model put inside a tree crown.

    The model outlines each crown as one solid shape, so a bare tree hides the sky and walls behind it. A crown pixel
    stays Vegetation if it is part of a trunk or thin limb, leaf-green, or dark like a shaded branch. A bright neutral
    or blue pixel becomes Sky. Anything else takes the background class beside the tree in the same row (usually the
    building behind it), or the nearest background pixel if the row has none.

    :param rgb: the picture as numbers from 0 to 1, height x width x 3
    :param label_map: class id of every pixel (-1 where no segment covers it)
    :param labels: class names by id
    :return: a new class map with the crowns re-checked
    """
    # Class ids of vegetation and sky, and of the background classes a gap can show
    veg, sky = labels.index("Vegetation"), labels.index("Sky")
    background = [labels.index(name) for name in CROWN_BACKGROUND_CLASSES if name in labels]
    # Lightness and the two colour axes of every pixel
    light, green_red, blue_yellow = np.moveaxis(srgb_to_lab(rgb), -1, 0)
    # The model's crowns, and their thin parts (what an opening with a thin_px square removes: trunks and limbs)
    crown = label_map == veg
    thin = crown & ~ndimage.binary_opening(crown, structure=np.ones((CROWN["thin_px"], CROWN["thin_px"])))
    # Leaf-green, shaded-branch and sky colours (blue sky, or the white of an overexposed sky)
    leaf = (green_red < CROWN["leaf_max_a"]) & (blue_yellow > CROWN["leaf_min_b"]) & (light < CROWN["leaf_max_l"])
    wood = light < CROWN["wood_max_l"]
    skyish = ((blue_yellow < CROWN["blue_sky_max_b"]) & (light > CROWN["blue_sky_min_l"])) | (
        (light > CROWN["white_sky_min_l"]) & (blue_yellow < CROWN["white_sky_max_b"])
        & (np.abs(green_red) < CROWN["white_sky_max_a"]))
    # Crown pixels that are part of the tree, sky seen through it, and anything else seen through it
    plant = crown & (thin | leaf | wood)
    to_sky = crown & ~plant & skyish
    other = crown & ~plant & ~skyish
    # The new map, with the sky gaps made Sky
    refined = label_map.copy()
    refined[to_sky] = sky
    # The other gaps take the background class beside them in the same row
    is_background = np.isin(label_map, background)
    beside = row_neighbour(label_map, is_background)
    use_row = other & (beside >= 0)
    refined[use_row] = beside[use_row]
    # Gaps with no background anywhere in their row
    rest = other & (beside < 0)
    # They take the nearest background pixel in any direction, if the picture has one
    if rest.any() and is_background.any():
        # Row and column of the nearest background pixel for every pixel, then its class for those gaps
        _, (rows, cols) = ndimage.distance_transform_edt(~is_background, return_indices=True)
        refined[rest] = label_map[rows[rest], cols[rest]]
    return refined


def class_map(seg_map: np.ndarray, segments: list[dict]) -> np.ndarray:
    """The class of every pixel, from the segment it belongs to.

    :param seg_map: segment id per pixel (pixels in no segment hold 0 or -1)
    :param segments: {id, label_id, score} for each segment
    :return: class id per pixel, -1 where no segment covers it
    """
    # Start with no class anywhere
    out = np.full(seg_map.shape, -1)
    # Go through the segments one at a time
    for s in segments:
        # This segment's pixels take its class
        out[seg_map == s["id"]] = s["label_id"]
    return out


def typical_roofs(model: "PanopticModel", views: pd.DataFrame, study: Path) -> tuple[dict, dict]:
    """Where the camera car's roof sits in each side view of the car-roof images.

    The roof is in nearly the same place in every car-roof view of one side, but its mirror-like paint reflects the
    trees, buildings and sky above it, so in some views the model labels those reflections instead of the car.

    :param model: the panoptic model
    :param views: one row per side view (point_id, side, capture_year, view_file)
    :param study: folder holding the images
    :return: ({side: True where the roof is}, {(point_id, side): (seg_map, segments)} for the views already run)
    """
    # Model results of the car-roof views (kept so they are not run twice), the roof found in each by side, and
    # the class ids of the camera car
    cache, found = {}, {"right": [], "left": []}
    camera_ids = [model.labels.index(name) for name in CAMERA_VEHICLE_CLASSES]
    # Each side view from a car-roof year
    for v in views[views.capture_year.isin(CAMERA_CAR_YEARS)].itertuples():
        # Run the model once and keep the result, then find the camera car in it
        cache[(v.point_id, v.side)] = model.run(Image.open(study / v.view_file).convert("RGB"))
        roof = np.isin(class_map(*cache[(v.point_id, v.side)]), camera_ids)
        # Only views where the model found the roof describe its shape
        if roof.mean() >= ROOF_MIN_SHARE:
            # Add this view's roof to its side
            found[v.side].append(roof)
    # The typical roof: pixels that are roof in at least half of the views that found one
    roofs = {side: np.mean(masks, axis=0) >= 0.5 for side, masks in found.items() if masks}
    return roofs, cache


def fill_roof(pixel_class: np.ndarray, roof: np.ndarray | None, labels: list[str]) -> tuple[np.ndarray, bool]:
    """In a car-roof image where the model missed the camera car, make the typical roof the camera car.

    :param pixel_class: class id of every pixel
    :param roof: the typical roof for this side (typical_roofs), or None for images not taken from a car roof
    :param labels: class names by id
    :return: (the class map, True if the roof was filled in)
    """
    # The roof is filled in only for car-roof images where the model found (almost) none of the camera car
    camera_ids = [labels.index(name) for name in CAMERA_VEHICLE_CLASSES]
    filled = roof is not None and np.isin(pixel_class, camera_ids).mean() < ROOF_MIN_SHARE
    # The roof's pixels become the camera car (what it reflects is not part of the street)
    if filled:
        # A copy, so the model's own map is left as it was
        pixel_class = pixel_class.copy()
        pixel_class[roof] = labels.index("Ego Vehicle")
    return pixel_class, filled


def describe(seg_map: np.ndarray, segments: list[dict], labels: list[str],
             rgb: np.ndarray | None = None, roof: np.ndarray | None = None) -> tuple[dict, dict]:
    """Turn one segmentation into class shares and object counts.

    Shares are of the street scene only: pixels of the camera's own car are left out of the total, and
    reported separately as camera_vehicle_share_of_picture.

    :param seg_map: segment id per pixel (pixels in no segment hold 0 or -1)
    :param segments: {id, label_id, score} for each segment
    :param labels: class names by id
    :param rgb: the picture as numbers from 0 to 1; when given, tree crowns are re-checked first (refine_crowns)
    :param roof: in a car-roof image, the typical roof for this side (typical_roofs); it stands in for the camera
        car when the model did not find the car in this view
    :return: ({share_<class>: share of the street scene}, {count_<class>: objects found})
    """
    # The class of every pixel, from its segment, with the typical roof standing in where the camera car was missed
    pixel_class, filled = fill_roof(class_map(seg_map, segments), roof, labels)
    # When the picture is given, re-check the tree crowns against its colours
    if rgb is not None:
        # The class map with the gaps in the crowns given back to the sky and walls behind them
        pixel_class = refine_crowns(rgb, pixel_class, labels)
    # Pixels per class (uncovered pixels left out), and an empty count for each street-furniture class
    per_class = np.bincount(pixel_class[pixel_class >= 0], minlength=len(labels))
    class_pixels = {name: int(n) for name, n in zip(labels, per_class)}
    counts = {f"count_{slug(name)}": 0 for name in OBJECT_CLASSES}
    # Count each segment that is a street-furniture object (the crown check changes pixels, not objects)
    for s in segments:
        # This segment's class name, and whether it lies mostly on a filled-in roof (a reflection, not an object)
        name = labels[s["label_id"]]
        on_roof = filled and roof[seg_map == s["id"]].mean() > 0.5
        # Only street-furniture classes off the roof are counted
        if name in OBJECT_CLASSES and not on_roof:
            # One more object of this class
            counts[f"count_{slug(name)}"] += 1
    # The camera's car comes off the total; what is left is the street scene
    camera = sum(class_pixels.pop(name) for name in CAMERA_VEHICLE_CLASSES)
    scene = seg_map.size - camera
    shares = {f"share_{slug(name)}": n / scene for name, n in class_pixels.items()}
    # Whatever no segment covered, the camera car's part of the whole picture, and rounding so repeated runs match
    shares["share_unlabelled"] = 1.0 - sum(shares.values())
    shares["camera_vehicle_share_of_picture"] = camera / seg_map.size
    shares = {k: round(v, 4) for k, v in shares.items()}
    # Whether the typical roof stood in for the camera car in this view (1) or not (0)
    shares["camera_roof_filled_in"] = int(filled)
    return shares, counts


def run_models(study: Path, out: Path, limit: int | None) -> None:
    """Run both models on every side view and write the per-view tables and the segment indicators.

    :param study: folder holding image_manifest.csv and images/
    :param out: where to write the tables
    :param limit: only the first N points (for a quick trial), or None for all
    """
    # The manifest, cut short for a trial; one row per side view (right and left)
    man = pd.read_csv(study / "image_manifest.csv")
    man = man.head(limit) if limit else man
    views = pd.concat([man.assign(side=s, view_file=man[f"view_{s}"]) for s in ("right", "left")])
    views = views.sort_values(["point_id", "side"]).reset_index(drop=True)
    # Load both models once on the fastest device
    device = pick_device()
    seg = PanopticModel(device)
    clip = L.ClipScorer(L.ClipEncoder(L.CLIP_MODEL, device=device, revision=L.CLIP_REVISION), L.load_prompts())
    clip.prepare()
    # One row per side view for each table, and the timer
    share_rows, count_rows, clip_rows = [], [], []
    start = time.time()
    # The camera car's typical roof on each side of the car-roof images, and those views' model results
    roofs, cached = typical_roofs(seg, views, study)
    # Each side view in turn
    for i, v in enumerate(views.itertuples(), 1):
        # The view's identity, shared by all three tables
        key = {"point_id": v.point_id, "segment_id": v.segment_id, "image_id": v.image_id, "side": v.side,
               "capture_year": v.capture_year}
        im = Image.open(study / v.view_file).convert("RGB")
        # Segmentation and detection from one model pass (already run for the car-roof views)
        seg_map, segments = cached.pop((v.point_id, v.side), None) or seg.run(im)
        # Shares and counts, with the tree crowns re-checked and, in car-roof views, the typical roof on hand
        roof = roofs.get(v.side) if v.capture_year in CAMERA_CAR_YEARS else None
        shares, counts = describe(seg_map, segments, seg.labels, np.asarray(im, dtype=float) / 255, roof)
        share_rows.append({**key, **shares})
        count_rows.append({**key, **counts})
        # CLIP land-use type and cue probabilities
        clip_rows.append({**key, **clip.score(im)})
        # Progress every 25 views
        if i % 25 == 0 or i == len(views):
            print(f"[models] {i}/{len(views)} views, {time.time() - start:.0f} s")
    # Save the three per-view tables, then the per-segment indicators
    out.mkdir(parents=True, exist_ok=True)
    shares_df, counts_df, clip_df = pd.DataFrame(share_rows), pd.DataFrame(count_rows), pd.DataFrame(clip_rows)
    shares_df.to_csv(out / "segmentation_shares.csv", index=False)
    counts_df.to_csv(out / "object_counts.csv", index=False)
    clip_df.to_csv(out / "clip_scores.csv", index=False)
    segment_indicators(shares_df, counts_df, clip_df).to_csv(out / "segment_indicators.csv", index=False)
    meta = {"segmentation_model": SEG_MODEL, "segmentation_revision": SEG_REVISION,
            "input_size": "native 1024 x 768 (no resize)", "panoptic_settings": PANOPTIC_SETTINGS,
            "shares_exclude_camera_vehicle": CAMERA_VEHICLE_CLASSES,
            "tree_crown_check": {"settings": CROWN, "background_classes": CROWN_BACKGROUND_CLASSES,
                                 "note": "set by eye on 5 views; not part of the label check"},
            "camera_roof_fill": {"years": CAMERA_CAR_YEARS, "min_own_roof_share": ROOF_MIN_SHARE,
                                 "typical_roof_share": {s: round(float(r.mean()), 3) for s, r in roofs.items()},
                                 "views_filled_in": int(shares_df.camera_roof_filled_in.sum())},
            "object_classes": OBJECT_CLASSES, "transient_classes_flagged_in_2020": TRANSIENT_CLASSES,
            "clip_model": L.CLIP_MODEL, "clip_revision": L.CLIP_REVISION, "clip_prompts": "Scripts/cv_pilot/clip_prompts.json",
            "device": device, "views": len(views), "points": int(man.point_id.nunique()),
            "segments": int(man.segment_id.nunique()), "seconds": round(time.time() - start),
            "caveat": "not validated; no indicator is used until it passes the label check",
            "git_commit": L.git_commit(), "created_utc": L.now_iso()}
    (out / "models_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"[models] {len(views)} side views from {meta['points']} points on {meta['segments']} segments "
          f"in {meta['seconds']} s on {device}")


def segment_indicators(shares: pd.DataFrame, counts: pd.DataFrame, clip: pd.DataFrame) -> pd.DataFrame:
    """Average the side views per point (both sides of the street), then the points per segment.

    :param shares: per-view class shares
    :param counts: per-view object counts
    :param clip: per-view CLIP scores
    :return: one row per street segment
    """
    # The columns carried up: chosen class shares, all object counts, and the CLIP cue means
    share_cols = [f"share_{slug(c)}" for c in INDICATOR_SHARES]
    count_cols = [f"count_{slug(c)}" for c in OBJECT_CLASSES]
    cue_cols = [c for c in clip.columns if c.startswith("cue_") and c.endswith("_mean")]
    keys = ["point_id", "segment_id", "image_id", "side", "capture_year"]
    views = shares[keys + share_cols].merge(counts[keys + count_cols], on=keys).merge(clip[keys + cue_cols], on=keys)
    # Per point: shares and cue probabilities averaged over the two sides, objects added up across both sides
    point = views.groupby(["point_id", "segment_id", "capture_year"]).agg(
        {**{c: "mean" for c in share_cols + cue_cols}, **{c: "sum" for c in count_cols}}).reset_index()
    # Per segment: the mean over its points, how many points it has, and its image years
    seg = point.groupby("segment_id").agg({**{c: "mean" for c in share_cols + count_cols + cue_cols},
                                           "point_id": "count", "capture_year": lambda y: ";".join(map(str, sorted(set(y))))})
    seg = seg.rename(columns={"point_id": "n_points_with_image", "capture_year": "capture_years"})
    # People and cars from 2020 images describe one COVID-19 day, so the segment is flagged
    seg["transient_cues_covid_2020"] = seg.capture_years.str.contains("2020")
    # Land-use type most often given to the segment's side views
    typ = clip.groupby("segment_id").typology_top1.agg(lambda t: t.value_counts().index[0])
    seg["typology_most_common"] = typ
    return seg.round(4).reset_index()


def main() -> int:
    """Run the models on the full image set, or on a few points for a trial.

    :return: exit code
    """
    # Input folder, output folder and an optional trial size
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--study", default=str(STUDY), help="folder with image_manifest.csv (default Data/cv_study_2026-11)")
    ap.add_argument("--out", help="where to write the tables (default: the --study folder)")
    ap.add_argument("--limit", type=int, help="only the first N points (trial run)")
    a = ap.parse_args()
    run_models(Path(a.study), Path(a.out or a.study), a.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
