#!/usr/bin/env python3
"""
models.py
=========
ComputerVision_Sentinel | November 2026: segmentation, detection and CLIP on every side view
(work plan steps 3-5, Docs/cv_pipeline.md)

One panoptic model does both segmentation and detection: Mask2Former (Swin-L) trained on Mapillary
Vistas, pinned to one revision like CLIP. For each side view it gives
  * segmentation: the share of the picture that is each of the 65 Vistas classes (building, vegetation,
    sky, road, sidewalk, fence, wall, terrain, ...);
  * detection: how many separate objects of each street-furniture class it found (street lights, poles,
    people, cars, benches, trash cans, CCTV cameras, bike racks, ...).
CLIP (the pilot's ClipScorer and clip_prompts.json) scores the cues that are hard to segment: graffiti,
litter, boarded windows, active storefronts, and the land-use type.

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

# Post-processing settings: the library's defaults, written down so they are part of the record
PANOPTIC_SETTINGS = {"threshold": 0.5, "mask_threshold": 0.5, "overlap_mask_area_threshold": 0.8}


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


def describe(seg_map: np.ndarray, segments: list[dict], labels: list[str]) -> tuple[dict, dict]:
    """Turn one segmentation into class shares and object counts.

    Shares are of the street scene only: pixels of the camera's own car are left out of the total, and
    reported separately as camera_vehicle_share_of_picture.

    :param seg_map: segment id per pixel (pixels in no segment hold 0 or -1)
    :param segments: {id, label_id, score} for each segment
    :param labels: class names by id
    :return: ({share_<class>: share of the street scene}, {count_<class>: objects found})
    """
    # Pixels per segment id, then per class
    ids, pixels = np.unique(seg_map, return_counts=True)
    per_id = dict(zip(ids.tolist(), pixels.tolist()))
    class_pixels = {name: 0 for name in labels}
    counts = {f"count_{slug(name)}": 0 for name in OBJECT_CLASSES}
    # Add each segment's pixels to its class, and count it if it is a street-furniture object
    for s in segments:
        name = labels[s["label_id"]]
        class_pixels[name] += per_id.get(s["id"], 0)
        if name in OBJECT_CLASSES:
            counts[f"count_{slug(name)}"] += 1
    # The camera's car comes off the total; what is left is the street scene
    camera = sum(class_pixels.pop(name) for name in CAMERA_VEHICLE_CLASSES)
    scene = seg_map.size - camera
    shares = {f"share_{slug(name)}": n / scene for name, n in class_pixels.items()}
    # Whatever no segment covered, the camera car's part of the whole picture, and rounding so repeated runs match
    shares["share_unlabelled"] = 1.0 - sum(shares.values())
    shares["camera_vehicle_share_of_picture"] = camera / seg_map.size
    shares = {k: round(v, 4) for k, v in shares.items()}
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
    # One row per side view for each table
    share_rows, count_rows, clip_rows = [], [], []
    start = time.time()
    # Each side view in turn
    for i, v in enumerate(views.itertuples(), 1):
        # The view's identity, shared by all three tables
        key = {"point_id": v.point_id, "segment_id": v.segment_id, "image_id": v.image_id, "side": v.side,
               "capture_year": v.capture_year}
        im = Image.open(study / v.view_file).convert("RGB")
        # Segmentation and detection from one model pass
        seg_map, segments = seg.run(im)
        shares, counts = describe(seg_map, segments, seg.labels)
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
