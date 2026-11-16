#!/usr/bin/env python3
"""
november_numbers.py
===================
CPTED Vision | Every number quoted in the November 2026 midpoint update

Reads Data/ and writes Docs/verification/november_2026_numbers.json, which the Markdown update and
build_november_report.js read. Nothing in either is typed by hand.

USAGE (repository root):  .venv/bin/python Scripts/reporting/november_numbers.py [--out <json>]
"""
# Command-line options, file paths and the numbers file
import argparse
import json
import sys
from pathlib import Path

# Tables, arrays and the side-view size
import numpy as np
import pandas as pd
from PIL import Image

# The CLIP check: how well a score separates views (AUC), F1, and the folds for testing a fitted cut-off
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

# Data folders, the CLIP prompts and the default output file
REPO = Path(__file__).resolve().parents[2]
STUDY = REPO / "Data" / "cv_study_2026-11"
PILOT = REPO / "Data" / "cv_pilot_2026-10" / "cbd"
CRIME = REPO / "Data" / "sps_crime_2026-06-01_2026-08-31" / "03_segments"
PROMPTS = REPO / "Scripts" / "cv_pilot" / "clip_prompts.json"
OUT = REPO / "Docs" / "verification" / "november_2026_numbers.json"

# How CLIP sees a side view (Scripts/cv_pilot/pilot_lib.py): three square crops, each shrunk to 224 x 224 pixels
# (CLIP ViT-B/32's input size), and a cue score made from the two prompt matches times CLIP's scale of 100
CLIP_CROPS = 3
CLIP_INPUT_PX = 224
CLIP_SCALE = 100

# The CLIP cues: the words in the report, the labelling-sheet column and the CLIP score column
CLIP_CUES = [("graffiti", "human_graffiti_0_1", "cue_graffiti_mean"),
             ("litter", "human_litter_0_1", "cue_litter_mean"),
             ("boarded windows", "human_boarded_windows_0_1", "cue_boarded_windows_mean"),
             ("vacant lot", "human_vacant_lot_0_1", "cue_vacant_lot_mean"),
             ("active storefront", "human_active_storefront_0_1", "cue_active_storefront_mean"),
             ("windows overlook", "human_windows_overlook_0_1", "cue_windows_overlook_street_mean"),
             ("people present", "human_people_present_0_1", "cue_people_present_mean"),
             ("fences", "human_fences_0_1", "cue_fences_barriers_mean"),
             ("seating", "human_seating_0_1", "cue_seating_mean")]

# The segmentation measure that covers the same thing as a CLIP cue: its words and the columns added together
STAND_INS = {"windows overlook": ("building share", ["share_building"]),
             "people present": ("person count", ["count_person"]),
             "fences": ("fence and wall share", ["share_fence", "share_wall"]),
             "seating": ("bench count", ["count_bench"])}

# Fewest labelled views with a cue before its AUC is reported, and before a fitted cut-off is tested;
# the folds and repeats for testing a cut-off on views it was not fitted on
MIN_FOR_AUC = 5
MIN_FOR_CUTOFF = 10
FOLDS, REPEATS = 5, 20


def read_json(path: Path) -> dict:
    """A JSON file as a dict.

    :param path: the file
    :return: its contents
    """
    return json.loads(path.read_text())


def image_numbers() -> dict:
    """The image set: how many points and segments got an image, and why the rest did not.

    :return: numbers for the update
    """
    # The run record of images.py and the per-point outcomes
    meta = read_json(STUDY / "run_meta.json")
    pts = pd.read_csv(STUDY / "points.csv")
    st = meta["status_counts"]
    return {"points": meta["points"], "points_with_image": meta["points_with_image"],
            "segments": int(pts.segment_id.nunique()), "segments_with_image": meta["segments_with_image"],
            "years": meta["capture_years"], "dates_local": meta["capture_dates_local"],
            "panoramas": meta["panoramas"], "side_views": 2 * meta["points_with_image"],
            "no_image_in_search": st.get("no_images_in_search_box", 0), "lost_to_heading_rule": meta["points_lost_to_heading_rule"],
            "excluded_bridge": st.get("excluded_bridge", 0), "excluded_freeway": st.get("excluded_freeway", 0)}


def image_year_numbers() -> dict:
    """Why 2023 images alone were not used: points and segments with a 2020 or 2023 panorama, before any image rule.

    :return: numbers for the update
    """
    # The October coverage check, one row per point, with each point's segment
    cov = pd.read_csv(PILOT / "coverage_points.csv")
    seg = pd.read_csv(PILOT / "sample_points.csv", usecols=["point_id", "segment_id"])
    cov = cov.merge(seg, on="point_id", validate="one_to_one")
    years = cov.years_pano.fillna("").astype(str).str.split(";")
    out = {}
    for year in ("2020", "2023"):
        has = years.apply(lambda found, y=year: y in found)
        out[year] = {"points": int(has.sum()), "segments": int(cov[has].segment_id.nunique())}
    out["points_with_both"] = int(years.apply(lambda found: "2020" in found and "2023" in found).sum())
    # The count-only Reddit search for 2023 (7 Nov 2026) kept no output file; its result is recorded in
    # Decision D1 of Docs/cv_pipeline.md and copied here
    out["reddit_posts_2023"], out["reddit_posts_2026"] = 122, 168
    return out


def model_numbers() -> dict:
    """What the models found across all side views (not yet validated).

    :return: numbers for the update
    """
    # The run record and the per-view tables
    meta = read_json(STUDY / "models_meta.json")
    shares = pd.read_csv(STUDY / "segmentation_shares.csv")
    counts = pd.read_csv(STUDY / "object_counts.csv")
    clip = pd.read_csv(STUDY / "clip_scores.csv")
    # Mean share of the street scene for the main surface classes, in percent
    surfaces = {c: round(100 * float(shares[f"share_{c}"].mean()), 1)
                for c in ("building", "vegetation", "sky", "road", "sidewalk", "fence", "wall")}
    # Views with at least one of each street-furniture object, and the total found
    objects = {c.removeprefix("count_"): {"views_with_any": int((counts[c] > 0).sum()), "total": int(counts[c].sum())}
               for c in counts.columns if c.startswith("count_")}
    # The camera car's part of the picture in the 2023 views, and the views where its typical roof stood in
    car_2023 = shares[shares.capture_year == 2023].camera_vehicle_share_of_picture
    roof_filled = int(shares.camera_roof_filled_in.sum()) if "camera_roof_filled_in" in shares else None
    typology = clip.typology_top1.value_counts()
    return {"views": meta["views"], "points": meta["points"], "segments": meta["segments"], "device": meta["device"],
            "minutes": round(meta["seconds"] / 60, 1), "segmentation_model": meta["segmentation_model"],
            "segmentation_revision": meta["segmentation_revision"][:7], "clip_model": meta["clip_model"],
            "clip_revision": meta["clip_revision"][:7], "surface_share_pct": surfaces, "objects": objects,
            "camera_car_pct_2023_views": round(100 * float(car_2023.mean()), 1) if len(car_2023) else None,
            "camera_roof_filled_in": roof_filled, "views_2023": int(len(car_2023)),
            "typology_counts": {k: int(v) for k, v in typology.items()},
            "typology_low_confidence": int(clip.typology_low_confidence.sum())}


def validation_numbers() -> dict:
    """The blind labelling sample and, once labelled, the accuracy results.

    :return: numbers for the update
    """
    # How the sample was drawn, and the scoring status
    strata = read_json(STUDY / "validation" / "sample_strata.json")
    res_file = STUDY / "validation" / "validation_results.json"
    res = read_json(res_file) if res_file.exists() else {"status": "pending"}
    # Views with at least one label filled in on the first sheet
    sheet = pd.read_csv(STUDY / "validation" / "validation_blind.csv", dtype=str)
    labels = [c for c in sheet.columns if c.startswith("human_") and c != "human_notes"]
    # Each model check against the labels, once scored (cue, model, precision, recall, F1, whether it passes)
    res_csv = STUDY / "validation" / "validation_results.csv"
    checks = []
    if res["status"] != "pending" and res_csv.exists():
        for r in pd.read_csv(res_csv).itertuples():
            checks.append({"cue": r.cue, "model": r.model, "n": int(r.n), "present": int(r.present_in_labels),
                           "precision": None if pd.isna(r.precision) else round(float(r.precision), 2),
                           "recall": None if pd.isna(r.recall) else round(float(r.recall), 2),
                           "f1": None if pd.isna(r.f1) else round(float(r.f1), 2), "passes": bool(r.passes_f1_0_7)})
    return {"n_sample": strata["n_sample"], "n_second_coder": strata["n_second_coder"],
            "n_labelled": int(sheet[labels].notna().any(axis=1).sum()),
            "strata": len(strata["strata"]), "population_views": strata["views_in_population"], "status": res["status"],
            "typology_accuracy": res.get("typology_accuracy"), "checks": checks,
            "checks_passing": sum(c["passes"] for c in checks)}


def fitted_cutoff_f1(y: np.ndarray, s: np.ndarray) -> float:
    """F1 of a cut-off chosen on four-fifths of the labelled views and applied to the other fifth, averaged over
    REPEATS different splits, so the cut-off is always tested on views it was not chosen on.

    :param y: 1 where the labels show the cue, else 0
    :param s: the score for each view
    :return: the average F1
    """
    out = []
    for r in range(REPEATS):
        pred = np.zeros_like(y)
        for train, test in StratifiedKFold(FOLDS, shuffle=True, random_state=r).split(s, y):
            # The cut-off with the best F1 on the training views, used on the test views
            cut = max(np.unique(s[train]), key=lambda c, tr=train: f1_score(y[tr], s[tr] >= c))
            pred[test] = s[test] >= cut
        out.append(f1_score(y, pred))
    return round(float(np.mean(out)), 2)


def clip_check_numbers() -> dict:
    """Why the CLIP cues fail the label check: how well each score separates the labelled views with and without the
    cue (AUC), what a fitted cut-off would give, the segmentation measures for the same cues, and the land-use bias.

    :return: numbers for the update
    """
    # The labelled views with their CLIP scores, segmentation shares and object counts (score columns only, so the
    # merge has no duplicate columns)
    k = ["point_id", "side"]
    clip = pd.read_csv(STUDY / "clip_scores.csv")
    shares = pd.read_csv(STUDY / "segmentation_shares.csv")
    counts = pd.read_csv(STUDY / "object_counts.csv")
    pick = lambda df, start: df[k + [c for c in df.columns if c.startswith(start)]]  # noqa: E731
    lab = (pd.read_csv(STUDY / "validation" / "validation_blind.csv")
           .merge(pick(clip, ("cue_", "typ_")), on=k).merge(pick(shares, "share_"), on=k).merge(pick(counts, "count_"), on=k))
    # The F1 at the fixed cut-off of 0.5, as scored by validation.py
    res = pd.read_csv(STUDY / "validation" / "validation_results.csv").set_index("prediction")

    # Each cue: views with it in the labels, CLIP's AUC and F1s, and the segmentation measure's AUC
    cues = []
    for word, label, score in CLIP_CUES:
        d = lab.dropna(subset=[label])
        y, s = d[label].astype(int).to_numpy(), d[score].to_numpy()
        present = int(y.sum())
        row = {"cue": word, "present": present, "n": int(len(y)),
               "auc": round(float(roc_auc_score(y, s)), 2) if present >= MIN_FOR_AUC else None,
               "f1_at_half": round(float(res.loc[score, "f1"]), 2) if pd.notna(res.loc[score, "f1"]) else None,
               "f1_fitted": fitted_cutoff_f1(y, s) if present >= MIN_FOR_CUTOFF else None,
               "stand_in": None, "stand_in_auc": None}
        if word in STAND_INS:
            name, cols = STAND_INS[word]
            row["stand_in"] = name
            row["stand_in_auc"] = round(float(roc_auc_score(y, d[cols].sum(axis=1).to_numpy())), 2)
        cues.append(row)

    # Across all side views: the vacant-lot score against the building share, and the average land-use probabilities
    views = clip.merge(pick(shares, "share_"), on=k)
    types = [c for c in clip.columns if c.startswith("typ_")]
    # The prompt wording: how many "absent" prompts say "no", and the side-view size that the crops are cut from
    prompts = json.loads(PROMPTS.read_text())["cues"]
    negatives = [p for v in prompts.values() for p in v["negative"]]
    first = pd.read_csv(STUDY / "image_manifest.csv").view_left.iloc[0]
    with Image.open(STUDY / first) as im:
        width, height = im.size
    return {"cues": cues, "min_for_auc": MIN_FOR_AUC, "min_for_cutoff": MIN_FOR_CUTOFF,
            "vacant_vs_building": round(float(views.cue_vacant_lot_mean.corr(views.share_building, method="spearman")), 2),
            "land_use_types": len(types),
            "parking_mean_prob": round(float(clip.typ_surface_parking.mean()), 3),
            "commercial_mean_prob": round(float(clip.typ_commercial_street.mean()), 3),
            "negatives": len(negatives), "negatives_with_no": sum(" no " in f" {p} " for p in negatives),
            "vacant_prompts": [prompts["vacant_lot"]["positive"][0], prompts["vacant_lot"]["negative"][0]],
            "graffiti_negative": prompts["graffiti"]["negative"][0],
            "view_px": [width, height], "crops": CLIP_CROPS, "crop_px": height, "clip_px": CLIP_INPUT_PX,
            "score_at_gap_0_01": round(1 / (1 + np.exp(-CLIP_SCALE * 0.01)), 2)}


def crime_numbers() -> dict:
    """Recorded crime on the street segments: placement, totals and hot spots.

    :return: numbers for the update
    """
    # The hot-spot summary and the per-segment counts
    summ = read_json(CRIME / "hotspot_summary.json")
    seg = pd.read_csv(CRIME / "segment_crime_counts.csv")
    top = seg.sort_values("all_study_crime", ascending=False, kind="mergesort").head(5)
    return {**{k: summ[k] for k in ("records", "placed", "unplaced", "segments", "segments_with_any_record",
                                    "records_by_group", "records_by_category", "hotspot_segments",
                                    "hotspot_share_of_segments", "placed_by_rule")},
            "top_segments": [{"road": r.road_name, "length_m": round(r.length_m), "records": round(r.all_study_crime, 1),
                              "property": round(r.property, 1), "street_personal": round(r.street_personal, 1)}
                             for r in top.itertuples()]}


def join_numbers() -> dict:
    """How far the street images and the crime records already overlap, for the X-to-crime analysis.

    :return: numbers for the update
    """
    # Segments with an image, and the crime counted on them
    ind = pd.read_csv(STUDY / "segment_indicators.csv")
    seg = pd.read_csv(CRIME / "segment_crime_counts.csv")
    both = seg[seg.segment_id.isin(ind.segment_id)]
    return {"segments_with_image": int(len(ind)), "records_on_imaged_segments": round(float(both.all_study_crime.sum()), 1),
            "imaged_segments_with_any_record": int((both.all_study_crime > 0).sum()),
            "hotspots_with_image": int(both.hotspot_all_study_crime.sum())}


def main() -> int:
    """Collect every number and write the JSON file.

    :return: exit code
    """
    # Output file option
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT), help="output JSON (default Docs/verification/november_2026_numbers.json)")
    out = Path(ap.parse_args().out)
    numbers = {"images": image_numbers(), "image_years": image_year_numbers(), "models": model_numbers(),
               "validation": validation_numbers(), "clip_check": clip_check_numbers(),
               "crime": crime_numbers(), "join": join_numbers()}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(numbers, indent=2, ensure_ascii=False))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
