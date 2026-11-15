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


def test_crown_check_gives_gaps_back_to_sky_and_building():
    """A filled crown over a wall and the sky keeps its leaves and trunk; the gaps become Building and Sky."""
    # Class names, and a 60 x 80 picture: a light brick wall on the left half, blue sky on the right half
    labels = ["Vegetation", "Sky", "Building", "Ego Vehicle", "Car Mount"]
    rgb = np.zeros((60, 80, 3))
    rgb[:, :40] = [0.75, 0.45, 0.35]
    rgb[:, 40:] = [0.45, 0.65, 0.95]
    # A green leaf patch inside the crown, and a grey trunk under it
    rgb[20:28, 30:38] = [0.2, 0.6, 0.2]
    rgb[45:, 39:41] = [0.5, 0.5, 0.5]
    # What the model said: building and sky, with one solid crown and its trunk on top
    pixel_class = np.where(np.arange(80) < 40, 2, 1)[None, :].repeat(60, 0)
    pixel_class[5:45, 10:70] = 0
    pixel_class[45:, 39:41] = 0
    refined = models.refine_crowns(rgb, pixel_class, labels)
    # Leaves and trunk stay Vegetation; a gap over the wall becomes Building and a gap over the sky becomes Sky
    assert (refined[20:28, 30:38] == 0).all() and (refined[45:, 39:41] == 0).all()
    assert refined[10, 20] == 2 and refined[10, 60] == 1
    # Through describe, only the leaf patch and the trunk are counted as vegetation
    seg_map = pixel_class + 1
    segments = [{"id": i + 1, "label_id": i} for i in range(3)]
    shares, _ = models.describe(seg_map, segments, labels, rgb)
    assert shares["share_vegetation"] == round((8 * 8 + 15 * 2) / (60 * 80), 4)


def test_missed_camera_roof_is_filled_in_and_its_reflections_not_counted():
    """When the model calls the camera car's roof a Car, the typical roof replaces it and no car is counted."""
    # A 10 x 10 picture: building on the top 6 rows, the roof (labelled Car by the model) on the bottom 4
    labels = ["Building", "Ego Vehicle", "Car", "Car Mount"]
    seg_map = np.ones((10, 10), dtype=int)
    seg_map[6:] = 2
    segments = [{"id": 1, "label_id": 0}, {"id": 2, "label_id": 2}]
    roof = np.zeros((10, 10), dtype=bool)
    roof[6:] = True
    shares, counts = models.describe(seg_map, segments, labels, roof=roof)
    # The street scene is all building, the roof is 40% of the picture, and the reflected car is not counted
    assert shares["share_building"] == 1.0 and shares["camera_vehicle_share_of_picture"] == 0.4
    assert shares["camera_roof_filled_in"] == 1 and counts["count_car"] == 0
    # Without a roof (an image not taken from a car) nothing changes: the car is counted
    shares, counts = models.describe(seg_map, segments, labels)
    assert shares["camera_roof_filled_in"] == 0 and counts["count_car"] == 1


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
