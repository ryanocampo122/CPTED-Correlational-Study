#!/usr/bin/env python3
"""
validation.py
=============
CPTED Vision | November 2026: the label check of the image models (Docs/validation_plan.md)

sample   Draws 150 side views for blind labelling and writes the sheets. Fixed before anyone labels:
         * strata are land-use type (CLIP's top label) x image year, each getting a share of the 150 in
           proportion to its size (at least 2 where it has 2 views);
         * inside a stratum, points are taken in the deterministic farthest-point spread order, one side per
           point first, so the sample covers the whole CBD;
         * 30 of the 150, spread the same way, also go to a second coder for the agreement check.
         The sheets show no model output.
score    Once the sheets are filled in: per cue precision, recall and F1 of each model against the first
         coder, land-use accuracy, and Cohen's kappa between the two coders on the 30 shared views.
         Reports "pending" while the sheets are empty.

Files in Data/cv_study_2026-11/validation/:
  validation_blind.csv          the 150 views for the first coder (fill in the human_* columns)
  validation_blind_coder2.csv   the 30 shared views for the second coder (filled in separately)
  validation_results.csv/.json  written by `score`

Model predictions compared with the labels (thresholds fixed in advance, provisional):
  a CLIP cue counts as present at a mean probability of 0.5 or more; a detected object counts as present
  at one or more in the view; the land-use type is CLIP's top label.

USAGE (repository root)
  .venv/bin/python Scripts/cv_study/validation.py sample
  .venv/bin/python Scripts/cv_study/validation.py score
"""
# Command-line options, file paths and the results file
import argparse
import json
import sys
from pathlib import Path

# Tables and numbers
import numpy as np
import pandas as pd

# The pilot's deterministic spread order
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "cv_pilot"))
import pilot_lib as L  # noqa: E402

# Folders: the study data and the validation sheets inside it
REPO = HERE.parents[1]
STUDY = REPO / "Data" / "cv_study_2026-11"
POINTS = REPO / "Data" / "cv_pilot_2026-10" / "cbd" / "sample_points.csv"

# Sample sizes: views for the first coder, views shared with the second coder, smallest stratum share
N_SAMPLE = 150
N_SECOND = 30
MIN_PER_STRATUM = 2

# Cue present when CLIP's mean probability reaches this, or when at least one object is detected
CLIP_PRESENT = 0.5
OBJECT_PRESENT = 1

# Label columns (same as the October pilot sheet) and the model prediction(s) each is checked against
HUMAN_COLUMNS = ["human_typology", "human_graffiti_0_1", "human_litter_0_1", "human_boarded_windows_0_1",
                 "human_vacant_lot_0_1", "human_active_storefront_0_1", "human_windows_overlook_0_1",
                 "human_people_present_0_1", "human_fences_0_1", "human_seating_0_1",
                 "human_streetlight_visible_0_1", "human_notes"]
CHECKS = {
    "human_graffiti_0_1": [("clip", "cue_graffiti_mean")],
    "human_litter_0_1": [("clip", "cue_litter_mean")],
    "human_boarded_windows_0_1": [("clip", "cue_boarded_windows_mean")],
    "human_vacant_lot_0_1": [("clip", "cue_vacant_lot_mean")],
    "human_active_storefront_0_1": [("clip", "cue_active_storefront_mean")],
    "human_windows_overlook_0_1": [("clip", "cue_windows_overlook_street_mean")],
    "human_people_present_0_1": [("clip", "cue_people_present_mean"), ("object", "count_person")],
    "human_fences_0_1": [("clip", "cue_fences_barriers_mean")],
    "human_seating_0_1": [("clip", "cue_seating_mean"), ("object", "count_bench")],
    "human_streetlight_visible_0_1": [("object", "count_street_light")],
}


def draw_sample(study: Path, out: Path) -> None:
    """Draw the 150 views and the 30 shared ones, and write the blank sheets.

    :param study: folder holding image_manifest.csv and clip_scores.csv
    :param out: where to write the sheets
    """
    # Every side view with its land-use type, image year and position
    clip = pd.read_csv(study / "clip_scores.csv")
    pts = pd.read_csv(POINTS)[["point_id", "lon", "lat"]]
    man = pd.read_csv(study / "image_manifest.csv")[["point_id", "view_right", "view_left"]]
    views = clip[["point_id", "image_id", "side", "capture_year", "typology_top1"]].merge(pts, on="point_id")
    views["stratum"] = views.typology_top1 + " | " + views.capture_year.astype(str)
    # Each point's place in the farthest-point spread order (the same order the pilot used)
    pt_rows = pts[pts.point_id.isin(views.point_id)].reset_index(drop=True)
    rank = {pt_rows.point_id[i]: r for r, i in enumerate(L.spread_order(pt_rows.to_dict("records")))}
    views["spread_rank"] = views.point_id.map(rank)
    # Which side of a point is tried first alternates along the spread order, so left and right come out even
    views["side_first"] = (views.side == "left") != (views.spread_rank % 2 == 1)
    # Views per stratum in proportion to its size, at least MIN_PER_STRATUM, then trimmed to exactly N_SAMPLE
    size = views.stratum.value_counts()
    want = (size / size.sum() * N_SAMPLE).round().astype(int).clip(lower=np.minimum(MIN_PER_STRATUM, size))
    # Trim or top up the largest strata until the total is exactly N_SAMPLE
    while want.sum() != N_SAMPLE:
        step = 1 if want.sum() < N_SAMPLE else -1
        room = (want < size) if step == 1 else (want > MIN_PER_STRATUM)
        want[(size * room).idxmax()] += step
    picked = []
    # Inside each stratum: spread order, one side per point first, then the other sides
    for stratum, k in want.sort_index().items():
        s = views[views.stratum == stratum].sort_values(["spread_rank", "side_first"], ascending=[True, False])
        first_side = s.drop_duplicates("point_id")
        rest = s.drop(first_side.index)
        picked.append(pd.concat([first_side, rest]).head(k))
    sample = pd.concat(picked).sort_values(["spread_rank", "side"]).reset_index(drop=True)
    # The shared 30: every fifth view in spread order, so they spread over the whole sample
    sample["second_coder"] = False
    sample.loc[sample.index[:: len(sample) // N_SECOND][:N_SECOND], "second_coder"] = True
    # Each view's image file, then the blank sheets (no model output on them)
    files = man.melt(id_vars="point_id", var_name="side", value_name="image_file")
    files["side"] = files.side.str.replace("view_", "")
    sample = sample.merge(files, on=["point_id", "side"])
    out.mkdir(parents=True, exist_ok=True)
    blank = sample[["image_id", "point_id", "side", "image_file", "second_coder"]].assign(
        image_file=lambda d: "../" + d.image_file, **{c: "" for c in HUMAN_COLUMNS})
    blank.to_csv(out / "validation_blind.csv", index=False)
    blank[blank.second_coder].drop(columns="second_coder").to_csv(out / "validation_blind_coder2.csv", index=False)
    (out / "sample_strata.json").write_text(json.dumps(
        {"rule": __doc__.split("sample   ")[1].split("score    ")[0].strip(), "views_in_population": len(views),
         "strata": {k: {"population": int(size[k]), "sampled": int(want[k])} for k in want.sort_index().index},
         "n_sample": len(sample), "n_second_coder": int(sample.second_coder.sum())}, indent=2))
    print(f"[validation] {len(sample)} views from {sample.point_id.nunique()} points in {len(want)} strata; "
          f"{int(sample.second_coder.sum())} shared with the second coder")


def as_flag(s: pd.Series) -> pd.Series:
    """Labels as 0/1 numbers, blanks as missing.

    :param s: a human_*_0_1 column
    :return: 1.0, 0.0 or NaN
    """
    return pd.to_numeric(s, errors="coerce")


def kappa(a: pd.Series, b: pd.Series) -> float:
    """Cohen's kappa: agreement between two coders beyond what chance would give.

    :param a: first coder's labels
    :param b: second coder's labels, same rows
    :return: kappa, or NaN when it cannot be computed
    """
    # Only rows both coders filled in
    both = a.notna() & b.notna()
    a, b = a[both].astype(str), b[both].astype(str)
    # No rows, or both coders always gave one and the same answer: kappa is undefined
    if len(a) == 0:
        return float("nan")
    observed = float((a == b).mean())
    chance = sum(float((a == v).mean()) * float((b == v).mean()) for v in set(a) | set(b))
    return float("nan") if chance == 1 else (observed - chance) / (1 - chance)


def score(study: Path, out: Path) -> None:
    """Compare the models with the labels, and the two coders with each other.

    :param study: folder holding the model outputs
    :param out: folder holding the filled sheets, where the results are written
    """
    # The filled sheets and the model outputs for the same views
    first = pd.read_csv(out / "validation_blind.csv", dtype=str)
    second = pd.read_csv(out / "validation_blind_coder2.csv", dtype=str)
    keys = ["point_id", "side"]
    models = pd.read_csv(study / "clip_scores.csv").merge(pd.read_csv(study / "object_counts.csv"), on=keys + [
        "segment_id", "image_id", "capture_year"])
    labelled = first.dropna(subset=[c for c in HUMAN_COLUMNS if c != "human_notes"], how="all")
    # Nothing labelled yet: say so and stop
    if labelled.empty:
        status = {"status": "pending", "labelled_views": 0, "note": "fill in validation_blind.csv, then run score"}
        (out / "validation_results.json").write_text(json.dumps(status, indent=2))
        print("[validation] pending: no labels yet")
        return
    data = labelled.merge(models, on=keys)
    rows = []
    # Each labelled cue against each model prediction for it
    for human, preds in CHECKS.items():
        truth = as_flag(data[human])
        for kind, col in preds:
            # A prediction counts as present at the fixed threshold for its kind
            pred = (data[col] >= (CLIP_PRESENT if kind == "clip" else OBJECT_PRESENT)).astype(float)
            ok = truth.notna()
            tp = int(((pred == 1) & (truth == 1) & ok).sum())
            fp = int(((pred == 1) & (truth == 0) & ok).sum())
            fn = int(((pred == 0) & (truth == 1) & ok).sum())
            precision = tp / (tp + fp) if tp + fp else float("nan")
            recall = tp / (tp + fn) if tp + fn else float("nan")
            f1 = 2 * precision * recall / (precision + recall) if tp else float("nan")
            # Agreement between the coders on the shared views, for this cue
            shared = second.merge(first, on=keys, suffixes=("_2", "_1"))
            k = kappa(as_flag(shared[f"{human}_1"]), as_flag(shared[f"{human}_2"]))
            rows.append({"cue": human.replace("human_", "").replace("_0_1", ""), "model": kind, "prediction": col,
                         "n": int(ok.sum()), "present_in_labels": int((truth == 1).sum()), "tp": tp, "fp": fp, "fn": fn,
                         "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
                         "passes_f1_0_7": bool(f1 >= 0.7), "kappa_coders": round(k, 3),
                         "passes_kappa_0_6": bool(k >= 0.6)})
    res = pd.DataFrame(rows)
    res.to_csv(out / "validation_results.csv", index=False)
    # Land-use accuracy against the first coder
    typ = data.dropna(subset=["human_typology"])
    summary = {"status": "scored", "labelled_views": len(labelled),
               "typology_accuracy": round(float((typ.human_typology == typ.typology_top1).mean()), 3) if len(typ) else None,
               "cues_passing_f1": res[res.passes_f1_0_7].cue.unique().tolist()}
    (out / "validation_results.json").write_text(json.dumps(summary, indent=2))
    print(f"[validation] {len(labelled)} labelled views; cues passing F1 >= 0.7: {summary['cues_passing_f1']}")


def main() -> int:
    """Draw the sample or score the filled sheets.

    :return: exit code
    """
    # Which step to run, where the model outputs are, and where the sheets go
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["sample", "score"])
    ap.add_argument("--study", default=str(STUDY), help="folder with the model outputs (default Data/cv_study_2026-11)")
    ap.add_argument("--out", help="folder for the sheets (default: <study>/validation)")
    a = ap.parse_args()
    study = Path(a.study)
    out = Path(a.out) if a.out else study / "validation"
    if a.step == "sample":
        draw_sample(study, out)
    else:
        score(study, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
