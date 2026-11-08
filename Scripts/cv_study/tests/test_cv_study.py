"""Offline tests for Scripts/cv_study: no network and no model (small made-up inputs stand in).
Run from the repo root:  .venv/bin/python Scripts/cv_study/tests/test_cv_study.py   (or pytest)"""
# Test helpers, file paths, numbers and tables
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# The study scripts under test
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import images  # noqa: E402
import models  # noqa: E402
import validation  # noqa: E402


def test_side_views_face_across_the_road():
    """On a north-south road with the camera facing north, the side views turn 90 degrees right and left."""
    yaws = images.side_view_yaws(road_bearing=0.0, heading=0.0)
    assert yaws == {"right": 90.0, "left": 270.0}
    # Camera facing south on the same road: the views still face east and west
    yaws = images.side_view_yaws(road_bearing=0.0, heading=180.0)
    assert yaws == {"right": 270.0, "left": 90.0}


def test_describe_leaves_out_the_camera_car():
    """Shares are of the street scene only; the camera's car is reported on its own; objects are counted."""
    # A 10 x 10 picture: bottom 2 rows are the camera's car, top 4 rows building, the rest two street lights
    labels = ["Building", "Ego Vehicle", "Street Light", "Car Mount"]
    seg_map = np.zeros((10, 10), dtype=int)
    seg_map[:4] = 1
    seg_map[4:6] = 2
    seg_map[6:8] = 3
    seg_map[8:] = 4
    segments = [{"id": 1, "label_id": 0}, {"id": 2, "label_id": 2}, {"id": 3, "label_id": 2}, {"id": 4, "label_id": 1}]
    shares, counts = models.describe(seg_map, segments, labels)
    # 40 building pixels of an 80-pixel scene; 20 car pixels of the 100-pixel picture
    assert shares["share_building"] == 0.5
    assert shares["share_street_light"] == 0.5
    assert shares["camera_vehicle_share_of_picture"] == 0.2
    assert "share_ego_vehicle" not in shares and abs(shares["share_unlabelled"]) < 1e-9
    assert counts["count_street_light"] == 2 and counts["count_person"] == 0


def test_segment_indicators_average_sides_then_points():
    """Shares are averaged over the two sides and then the points; objects are added across the two sides."""
    # Two points on one segment, two sides each
    keys = pd.DataFrame({"point_id": ["P1", "P1", "P2", "P2"], "segment_id": ["S"] * 4, "image_id": [1, 1, 2, 2],
                         "side": ["left", "right"] * 2, "capture_year": [2020] * 4})
    shares = keys.assign(**{f"share_{models.slug(c)}": 0.0 for c in models.INDICATOR_SHARES})
    shares["share_building"] = [0.2, 0.4, 0.6, 0.8]
    counts = keys.assign(**{f"count_{models.slug(c)}": 0 for c in models.OBJECT_CLASSES})
    counts["count_street_light"] = [1, 0, 2, 1]
    clip = keys.assign(cue_graffiti_mean=[0.1, 0.3, 0.5, 0.7], typology_top1=["a", "a", "b", "a"])
    seg = models.segment_indicators(shares, counts, clip).set_index("segment_id")
    # Building: (0.3 + 0.7) / 2; street lights per point: (1 + 3) / 2
    assert seg.loc["S", "share_building"] == 0.5
    assert seg.loc["S", "count_street_light"] == 2.0
    assert seg.loc["S", "n_points_with_image"] == 2 and bool(seg.loc["S", "transient_cues_covid_2020"])
    assert seg.loc["S", "typology_most_common"] == "a"


def test_kappa():
    """Perfect agreement gives 1; agreement no better than chance gives 0."""
    a = pd.Series([1, 0, 1, 0])
    assert validation.kappa(a, a) == 1.0
    assert abs(validation.kappa(a, pd.Series([1, 1, 0, 0]))) < 1e-9
    assert np.isnan(validation.kappa(pd.Series([np.nan]), pd.Series([np.nan])))


if __name__ == "__main__":
    # Run every test in this file and report each one
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:  # noqa: BLE001
                fails += 1
                print("FAIL", name, repr(exc))
    sys.exit(1 if fails else 0)
