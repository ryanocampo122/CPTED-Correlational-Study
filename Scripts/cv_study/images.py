#!/usr/bin/env python3
"""
images.py
=========
CPTED Vision | November 2026: the full street-image set (work plan step 2)

Applies Decision D1 (Docs/cv_pipeline.md) to every CBD sample point:
  * points on bridges or freeway-type roads are flagged and get no image (no frontage to measure);
  * every other point gets its newest Mapillary image captured from 2020 onward, within 30 m,
    whose camera faces along the point's own road (within 30 degrees), so a camera standing on the
    cross street is never used;
  * each 360-degree panorama is cut into two side views, one facing each side of the street.

Writes to Data/cv_study_2026-11/ (everything is committed):
  points.csv           the 423 points with their bridge/freeway flag and what happened at each
  image_manifest.csv   one row per point with an image: image ID, capture date, distance, heading, files
  images/              the side views (<point>_<image>_right.jpg and _left.jpg)
  images/pano_raw/     the downloaded panoramas, so the side views can be cut again offline
  run_meta.json        the rule, the counts and the software versions

USAGE (repository root)
  .venv/bin/python Scripts/cv_study/images.py                       # search and download (Mapillary API)
  .venv/bin/python Scripts/cv_study/images.py --recrop-to <folder>  # offline: cut the side views again
                                                                    # from the committed panoramas
"""
# Command-line options, file paths, the run record and the clock
import argparse
import json
import sys
from pathlib import Path

# Tables and image files
import pandas as pd
from PIL import Image

# The pilot's tools (Mapillary search, image choice, panorama cropping), shared so both use one rule
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "cv_pilot"))
import pilot_lib as L  # noqa: E402

# Where the points come from, where everything is written, and the cached OSM bridge list
REPO = HERE.parents[1]
POINTS_CSV = REPO / "Data" / "cv_pilot_2026-10" / "cbd" / "sample_points.csv"
BRIDGES_JSON = REPO / "Data" / "cv_pilot_2026-10" / "cbd" / "osm_bridge_way_ids.json"
DEFAULT_OUT = REPO / "Data" / "cv_study_2026-11"

# The Decision D1 rule: images from 2020 on, within 30 m, camera within 30 degrees of the road, newest first
CAPTURE_START = "2020-01-01"
RADIUS_M = 30.0
MAX_OFF_ROAD_DEG = 30.0

# Each side view is a 90-degree-wide normal camera picture, 1024 x 768 pixels
VIEW_FOV_DEG = 90.0
JPEG_QUALITY = 90


def side_view_yaws(road_bearing: float, heading: float) -> dict:
    """Where to turn inside a panorama to face each side of the street.

    :param road_bearing: compass direction of the point's road, in degrees
    :param heading: compass direction the panorama's centre faces, in degrees
    :return: {"right": yaw, "left": yaw}, in degrees from the panorama's centre
    """
    return {"right": (road_bearing + 90 - heading) % 360, "left": (road_bearing - 90 - heading) % 360}


def cut_side_views(raw: Path, road_bearing: float, heading: float, out_dir: Path, stem: str) -> dict:
    """Cut the two side views out of one panorama and save them.

    :param raw: the downloaded panorama
    :param road_bearing: compass direction of the point's road
    :param heading: compass direction the panorama's centre faces
    :param out_dir: folder for the side views
    :param stem: file name start, <point>_<image>
    :return: {"right": relative file name, "left": relative file name}
    """
    # Open the panorama once and cut both sides from it
    pano = Image.open(raw)
    files = {}
    # One view per side of the street
    for side, yaw in side_view_yaws(road_bearing, heading).items():
        # Save under images/, named after the point, the image and the side
        name = f"{stem}_{side}.jpg"
        L.equirect_to_perspective(pano, yaw, fov_deg=VIEW_FOV_DEG).save(out_dir / name, quality=JPEG_QUALITY)
        files[side] = f"images/{name}"
    return files


def collect(out: Path) -> None:
    """Search Mapillary at every point, choose one image by the Decision D1 rule, download it and cut it.

    :param out: output folder (Data/cv_study_2026-11)
    """
    # Folders for the side views and the raw panoramas
    (out / "images" / "pano_raw").mkdir(parents=True, exist_ok=True)
    # The 423 published points, the bridge list, the Mapillary client and the capture window (2020 onward)
    points = pd.read_csv(POINTS_CSV)
    bridges = L.load_bridge_way_ids(BRIDGES_JSON)
    client = L.MapillaryClient(L.get_mapillary_token())
    window = L.local_window(CAPTURE_START, None)
    # What happened at each point, and one manifest row for each point that got an image
    point_rows = []
    manifest = []
    # Go through the points in their published order
    for p in points.to_dict("records"):
        # Points with no frontage are flagged and skipped
        flag = L.bridge_or_freeway(p, bridges)
        if flag:
            point_rows.append({**p, "flag": flag, "status": f"excluded_{flag}", "image_id": ""})
            continue
        # Images near the point from 2020 on, then the one image the rule picks
        cands = client.search(p["lon"], p["lat"], RADIUS_M, window)
        c, reason = L.choose_image(cands, p["lon"], p["lat"], RADIUS_M, window=window, allow_pano=True,
                                   prefer="recent", road_bearing=p["road_bearing_deg"],
                                   max_off_road_deg=MAX_OFF_ROAD_DEG)
        # No usable image: record why and move on
        if c is None:
            point_rows.append({**p, "flag": "", "status": reason, "image_id": ""})
            print(f"[images] {p['point_id']}: no image ({reason})")
            continue
        # Download the panorama once (neighbouring points can share one) and remember its heading
        raw = out / "images" / "pano_raw" / f"{c['id']}.jpg"
        if not raw.exists():
            client.download(c["_url"], raw)
        heading = L.heading_of(c)
        # Angle between the camera and the road, folded so up- and down-road both count as 0
        off_road = L.angle_diff(heading, p["road_bearing_deg"])
        off_road = min(off_road, 180 - off_road)
        # Cut the two side views and check their brightness and sharpness
        files = cut_side_views(raw, p["road_bearing_deg"], heading, out / "images", f"{p['point_id']}_{c['id']}")
        quality = {side: L.image_quality(out / f) for side, f in files.items()}
        manifest.append({
            "point_id": p["point_id"], "segment_id": p["segment_id"], "road_name": p["road_name"],
            "image_id": c["id"], "captured_at": c["_dt"].isoformat(), "capture_year": c["_dt"].year,
            "capture_month": c["_dt"].month, "is_pano": bool(c["_pano"]), "dist_to_point_m": round(c["_dist_m"], 1),
            "road_bearing_deg": p["road_bearing_deg"], "compass_angle": heading, "off_road_deg": round(off_road, 1),
            "pano_file": f"images/pano_raw/{c['id']}.jpg", "view_right": files["right"], "view_left": files["left"],
            "flags_right": quality["right"]["flags"], "flags_left": quality["left"]["flags"],
            "mapillary_url": f"https://www.mapillary.com/app/?pKey={c['id']}"})
        point_rows.append({**p, "flag": "", "status": "ok", "image_id": c["id"]})
        print(f"[images] {p['point_id']}: {c['id']} ({c['_dt'].date()}, {c['_dist_m']:.0f} m, {off_road:.0f} deg off road)")
    # Save the point list, the manifest and the run record
    pd.DataFrame(point_rows).to_csv(out / "points.csv", index=False)
    man = pd.DataFrame(manifest)
    man.to_csv(out / "image_manifest.csv", index=False)
    write_meta(out, pd.DataFrame(point_rows), man)
    print(f"[images] {len(man)} of {len(points)} points have an image on "
          f"{man.segment_id.nunique()} segments; years {man.capture_year.value_counts().sort_index().to_dict()}")


def write_meta(out: Path, points: pd.DataFrame, man: pd.DataFrame) -> None:
    """Save the rule and the counts to run_meta.json.

    :param out: output folder
    :param points: what happened at each point
    :param man: the image manifest
    """
    # Why points got no image, counted
    statuses = points.status.str.replace(r"\(.*", "", regex=True).value_counts().to_dict()
    # Capture dates in Saskatoon local time (the manifest keeps UTC times)
    local_dates = pd.to_datetime(man.captured_at, utc=True, format="ISO8601").dt.tz_convert(L.LOCAL_TZ).dt.date.astype(str)
    # How many points lost their only 2020+ images to the camera-direction rule
    heading_lost = int(points.status.str.contains("off_road_heading", regex=False).sum())
    meta = {
        "rule": (f"Decision D1: newest Mapillary image captured from {CAPTURE_START} on, within {RADIUS_M:.0f} m, "
                 f"camera heading within {MAX_OFF_ROAD_DEG:.0f} degrees of the point's road (up- or down-road); "
                 "points on bridges or freeway-type roads excluded; panoramas cut into two 90-degree side views"),
        "points": len(points), "points_with_image": len(man), "segments_with_image": int(man.segment_id.nunique()),
        "status_counts": {k: int(v) for k, v in statuses.items()},
        "points_lost_to_heading_rule": heading_lost,
        "capture_years": {int(k): int(v) for k, v in man.capture_year.value_counts().sort_index().items()},
        "capture_dates_local": sorted(local_dates.unique().tolist()),
        "panoramas": int(man.image_id.nunique()),
        "mapillary_license": "CC BY-SA 4.0 (attribute Mapillary and contributors; share-alike on derivatives)",
        "git_commit": L.git_commit(), "created_utc": L.now_iso()}
    (out / "run_meta.json").write_text(json.dumps(meta, indent=2))


def recrop(src: Path, dest: Path) -> None:
    """Offline: cut every side view again from the committed panoramas, into another folder.

    :param src: the folder holding image_manifest.csv and images/pano_raw/
    :param dest: where to write the new side views (dest/images/)
    """
    # Folder for the new side views, and the manifest that says how each was cut
    (dest / "images").mkdir(parents=True, exist_ok=True)
    man = pd.read_csv(src / "image_manifest.csv")
    # Cut each point's two views again from its panorama
    for r in man.itertuples():
        cut_side_views(src / r.pano_file, r.road_bearing_deg, r.compass_angle, dest / "images",
                       f"{r.point_id}_{r.image_id}")
    print(f"[images] cut {2 * len(man)} side views again into {dest / 'images'}")


def main() -> int:
    """Run the collection, or the offline re-cut.

    :return: exit code
    """
    # Output folder, and the optional offline re-cut target
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output folder (default Data/cv_study_2026-11)")
    ap.add_argument("--recrop-to", help="offline: cut the side views again from --out's panoramas into this folder")
    a = ap.parse_args()
    # Offline re-cut when asked, otherwise the full collection
    if a.recrop_to:
        recrop(Path(a.out), Path(a.recrop_to))
    else:
        collect(Path(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
