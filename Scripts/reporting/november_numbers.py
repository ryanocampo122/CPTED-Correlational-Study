#!/usr/bin/env python3
"""
november_numbers.py
===================
ComputerVision_Sentinel | Every number quoted in the November 2026 midpoint update

Reads Data/ and writes Docs/verification/november_2026_numbers.json, which the Markdown update and
build_november_report.js read. Nothing in either is typed by hand.

USAGE (repository root):  .venv/bin/python Scripts/reporting/november_numbers.py [--out <json>]
"""
# Command-line options, file paths and the numbers file
import argparse
import json
import sys
from pathlib import Path

# Tables
import pandas as pd

# Data folders and the default output file
REPO = Path(__file__).resolve().parents[2]
STUDY = REPO / "Data" / "cv_study_2026-11"
CRIME = REPO / "Data" / "sps_crime_2026-06-01_2026-08-31" / "03_segments"
OUT = REPO / "Docs" / "verification" / "november_2026_numbers.json"


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
    # The camera car's part of the picture in the 2023 views
    car_2023 = shares[shares.capture_year == 2023].camera_vehicle_share_of_picture
    typology = clip.typology_top1.value_counts()
    return {"views": meta["views"], "points": meta["points"], "segments": meta["segments"], "device": meta["device"],
            "minutes": round(meta["seconds"] / 60, 1), "segmentation_model": meta["segmentation_model"],
            "segmentation_revision": meta["segmentation_revision"][:7], "clip_model": meta["clip_model"],
            "clip_revision": meta["clip_revision"][:7], "surface_share_pct": surfaces, "objects": objects,
            "camera_car_pct_2023_views": round(100 * float(car_2023.mean()), 1) if len(car_2023) else None,
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
    numbers = {"images": image_numbers(), "models": model_numbers(), "validation": validation_numbers(),
               "crime": crime_numbers(), "join": join_numbers()}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(numbers, indent=2, ensure_ascii=False))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
