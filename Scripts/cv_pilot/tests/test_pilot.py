"""Offline tests for the CV pilot: no network, no torch (fakes stand in for Mapillary and CLIP).
Run from the repo root:  .venv/bin/python Scripts/cv_pilot/tests/test_pilot.py   (or pytest)"""
from __future__ import annotations

import json
import sys
import tempfile
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import pilot  # noqa: E402
import pilot_lib as L  # noqa: E402


# ---------------- geometry ----------------
def test_haversine_and_bearing():
    d = L.haversine_m(-106.66, 52.13, -106.66, 52.1309)        # ~100 m north
    assert abs(d - 100.1) < 1
    assert abs(L.bearing_deg(-106.66, 52.13, -106.66, 52.14) - 0) < 0.5
    assert abs(L.bearing_deg(-106.66, 52.13, -106.65, 52.13) - 90) < 0.5
    assert L.angle_diff(350, 10) == 20


def test_resample_spacing():
    pts = L.resample_polyline([(0, 0), (500, 0)], 50)
    assert len(pts) == 10
    gaps = np.diff([p[2] for p in pts])
    assert np.allclose(gaps, 50)
    assert len(L.resample_polyline([(0, 0), (30, 0)], 50)) == 1     # short line -> midpoint


def test_point_in_polygon_with_hole():
    outer = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    hole = [(4, 4), (6, 4), (6, 6), (4, 6), (4, 4)]
    assert L.point_in_polygons(2, 2, [[outer, hole]])
    assert not L.point_in_polygons(5, 5, [[outer, hole]])
    assert not L.point_in_polygons(11, 5, [[outer, hole]])


def grid_ways():
    """Two crossing streets in Downtown Saskatoon coordinates."""
    return [{"way_id": "1", "name": "A St", "highway": "residential",
             "coords": [(-106.665, 52.130), (-106.660, 52.130), (-106.655, 52.130)]},
            {"way_id": "2", "name": "B Ave", "highway": "residential",
             "coords": [(-106.660, 52.127), (-106.660, 52.130), (-106.660, 52.133)]}]


def test_split_and_points():
    segs = L.split_at_intersections(grid_ways())
    assert len(segs) == 4                                  # each street split at the shared vertex
    polys = L.bbox_polygon(L.DEFAULT_BBOX)
    pts = L.generate_points(segs, polys, 50)
    assert 25 < len(pts) < 40                             # ~1.4 km of road / 50 m
    ids = [p["point_id"] for p in pts]
    assert len(set(ids)) == len(ids)
    # no two points closer than 10 m
    for i, a in enumerate(pts):
        for b in pts[i + 1:]:
            assert L.haversine_m(a["lon"], a["lat"], b["lon"], b["lat"]) >= 9.9


def test_spread_order_is_deterministic_and_spread():
    segs = L.split_at_intersections(grid_ways())
    pts = L.generate_points(segs, L.bbox_polygon(L.DEFAULT_BBOX), 50)
    o1, o2 = L.spread_order(pts), L.spread_order(pts)
    assert o1 == o2 and sorted(o1) == list(range(len(pts)))
    first5 = [pts[i] for i in o1[:5]]
    dmin = min(L.haversine_m(a["lon"], a["lat"], b["lon"], b["lat"])
               for i, a in enumerate(first5) for b in first5[i + 1:])
    assert dmin > 150                                      # early picks are far apart


def test_boundary_geojson_and_name_match(tmp=None):
    tmp = Path(tempfile.mkdtemp())
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"NAME": "Central Business District"},
         "geometry": {"type": "Polygon", "coordinates": [[[-106.67, 52.12], [-106.63, 52.12], [-106.63, 52.14], [-106.67, 52.14], [-106.67, 52.12]]]}},
        {"type": "Feature", "properties": {"NAME": "Nutana"},
         "geometry": {"type": "Polygon", "coordinates": [[[-106.65, 52.10], [-106.62, 52.10], [-106.62, 52.12], [-106.65, 52.10]]]}}]}
    f = tmp / "b.geojson"
    f.write_text(json.dumps(fc))
    polys, bb, src = L.load_boundary(str(f), "central business")
    assert len(polys) == 1 and bb[1] == 52.12
    try:
        L.load_boundary(str(f), "nope")
        assert False
    except ValueError as e:
        assert "Nutana" in str(e)


# ---------------- image choice ----------------
def cand(i, lon, lat, iso, pano=False, url=True):
    """Synthetic Mapillary search result."""
    return {"id": str(i), "captured_at": iso, "is_pano": pano, "compass_angle": 90.0,
            "computed_geometry": {"type": "Point", "coordinates": [lon, lat]},
            "thumb_1024_url": f"https://x/{i}.jpg" if url else None,
            "thumb_2048_url": f"https://x/{i}_2048.jpg" if url else None}


def test_choose_image_prefers_summer_then_recent_then_near():
    lon, lat = -106.66, 52.13
    near_winter = cand(1, lon, lat, "2025-01-10T12:00:00Z")
    far_summer_old = cand(2, lon + 0.0002, lat, "2019-07-01T12:00:00Z")      # ~14 m
    mid_summer_new = cand(3, lon + 0.0001, lat, "2023-08-01T12:00:00Z")
    pano = cand(4, lon, lat, "2025-07-01T12:00:00Z", pano=True)
    toofar = cand(5, lon + 0.002, lat, "2025-07-01T12:00:00Z")               # ~137 m
    allc = [near_winter, far_summer_old, mid_summer_new, pano, toofar]
    c, why = L.choose_image(allc, lon, lat, 30, prefer="summer")
    assert why == "ok" and c["id"] == "3"
    c, _ = L.choose_image(allc, lon, lat, 30)                                  # default: most recent year
    assert c["id"] == "1"
    c, _ = L.choose_image(allc, lon, lat, 30, allow_pano=True)                # same year: Jul pano beats Jan flat
    assert c["id"] == "4"                                                     # (Jun-Aug ranks before flat)
    w = L.local_window("2026-06-01", "2026-08-31")
    s26 = cand(6, lon, lat, "2026-07-02T18:00:00Z", pano=True)
    c, _ = L.choose_image(allc + [s26], lon, lat, 30, window=w, allow_pano=True)
    assert c["id"] == "6"
    c, why = L.choose_image(allc, lon, lat, 30, window=w, allow_pano=True)
    assert c is None and "outside_capture_window" in why
    c, why = L.choose_image([pano, toofar], lon, lat, 30)
    assert c is None and "panorama=1" in why and "too_far=1" in why
    assert L.parse_captured_at(1690000000000).year == 2023              # epoch ms


def test_choose_image_heading_rule():
    """With the November rule on, a camera facing across the point's road is not used."""
    # A point on an east-west road (bearing 90), and a 2023 panorama 10 m along it facing east
    lon, lat = -106.66, 52.13
    along = cand(1, lon + 0.00015, lat, "2023-05-13T12:00:00Z", pano=True)
    # A 2023 panorama right at the point whose camera faces north: it stands on the cross street
    across = {**cand(2, lon, lat, "2023-05-14T12:00:00Z", pano=True), "compass_angle": 0.0}
    # Without the rule the nearer cross-street image wins; with it the along-road image is chosen
    c, _ = L.choose_image([along, across], lon, lat, 30, allow_pano=True)
    assert c["id"] == "2"
    c, why = L.choose_image([along, across], lon, lat, 30, allow_pano=True, road_bearing=90.0, max_off_road_deg=30)
    assert why == "ok" and c["id"] == "1"
    # Facing west (270) is still along the road, since up- and down-road count the same
    west = {**cand(3, lon, lat, "2023-05-13T12:00:00Z", pano=True), "compass_angle": 265.0}
    c, _ = L.choose_image([west], lon, lat, 30, allow_pano=True, road_bearing=90.0, max_off_road_deg=30)
    assert c["id"] == "3"
    # When only the cross-street image exists, the point gets no image and the reason says why
    c, why = L.choose_image([across], lon, lat, 30, allow_pano=True, road_bearing=90.0, max_off_road_deg=30)
    assert c is None and "off_road_heading=1" in why


def test_bridge_or_freeway():
    """Points on bridges or freeway-type roads are flagged; ordinary streets are not."""
    # Way 111 is on a bridge in this made-up bridge list
    bridges = {"111"}
    assert L.bridge_or_freeway({"osm_way_id": 111, "highway": "primary"}, bridges) == "bridge"
    assert L.bridge_or_freeway({"osm_way_id": 222, "highway": "trunk"}, bridges) == "freeway"
    assert L.bridge_or_freeway({"osm_way_id": 333, "highway": "residential"}, bridges) == ""


def test_bridge_or_freeway_flags_the_11_published_points():
    """On the published CBD points the flag reproduces the 11 bridge and freeway points of the October checks."""
    # The published sample points and the cached OSM bridge list
    cbd = L.REPO_ROOT / "Data" / "cv_pilot_2026-10" / "cbd"
    bridges = L.load_bridge_way_ids(cbd / "osm_bridge_way_ids.json")
    points = json.loads((cbd / "sample_points.geojson").read_text())["features"]
    import pandas as pd
    rows = pd.read_csv(cbd / "sample_points.csv").to_dict("records")
    flagged = [r["point_id"] for r in rows if L.bridge_or_freeway(r, bridges)]
    assert len(points) == 423 and len(flagged) == 11


def test_local_window_is_saskatoon_time():
    s, e = L.local_window("2026-06-01", "2026-08-31")
    assert L.iso_z(s) == "2026-06-01T06:00:00Z" and L.iso_z(e) == "2026-09-01T05:59:59Z"


def test_equirect_crop_points_the_right_way():
    from PIL import Image
    W, H = 720, 360
    col = np.tile(np.linspace(0, 255, W, dtype=np.uint8), (H, 1))       # red encodes longitude
    pano = Image.fromarray(np.stack([col, col * 0, col * 0], axis=-1))
    for yaw, frac in [(0, 0.5), (90, 0.75), (-90, 0.25)]:
        v = np.asarray(L.equirect_to_perspective(pano, yaw, out_w=64, out_h=48))
        centre = v[24, 32, 0] / 255.0
        assert abs(centre - frac) < 0.02, (yaw, centre)
    v = np.asarray(L.equirect_to_perspective(pano, 0, fov_deg=90, out_w=64, out_h=48))
    edge = v[24, 0, 0] / 255.0                                          # left edge = 45 deg left of centre
    assert abs(edge - 0.375) < 0.03


def test_wilson():
    lo, hi = L.wilson(0, 10)
    assert lo == 0 and 0.25 < hi < 0.35
    lo, hi = L.wilson(76, 238)
    assert 0.26 < lo < 0.27 and 0.37 < hi < 0.39


# ---------------- end-to-end with fakes ----------------
class FakeClient:
    """Serves 1 synthetic image per point for 2 of every 3 points."""

    def __init__(self, img_dir: Path):
        self.n = 0
        self.img_dir = img_dir

    def search(self, lon, lat, radius, window=None):
        self.n += 1
        if self.n % 3 == 0:
            return []
        out = [cand(1000 + self.n, lon + 0.00005, lat, "2014-07-15T15:00:00Z")]
        if self.n % 2 == 0:                                   # some points also have a 2026 panorama
            out.append(cand(5000 + self.n, lon, lat + 0.00005, "2026-07-20T17:00:00Z", pano=True))
        if window:
            out = [c for c in out if window[0] <= L.parse_captured_at(c["captured_at"]) <= window[1]]
        return out

    def search_bbox(self, bbox, window=None, limit=2000):
        w, s, e, n = bbox
        lon, lat = (w + e) / 2, (s + n) / 2
        out = [cand(f"b{lon:.4f}{lat:.4f}", lon, lat, "2014-07-15T15:00:00Z"),
               cand(f"p{lon:.4f}{lat:.4f}", lon, lat, "2026-07-20T17:00:00Z", pano=True)]
        return [c for c in out if not window or window[0] <= L.parse_captured_at(c["captured_at"]) <= window[1]]

    def download(self, url, dest):
        from PIL import Image
        dest.parent.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(len(url))
        shape = (512, 1024, 3) if "_2048" in url else (576, 1024, 3)
        Image.fromarray(rng.integers(0, 255, shape, dtype=np.uint8)).save(dest)
        return 1


class FakeEncoder:
    """Deterministic pseudo-embeddings so the scoring maths can run without torch."""
    model_name, device, logit_scale = "fake-clip", "cpu", 100.0

    def _v(self, key):
        rng = np.random.default_rng(zlib.crc32(key.encode()))       # stable across runs (hash() is not)
        v = rng.normal(size=16)
        return v / np.linalg.norm(v)

    def encode_texts(self, texts):
        return np.stack([self._v(t) for t in texts])

    def encode_images(self, images):
        return np.stack([self._v(str(np.asarray(im).sum())) for im in images])


def test_end_to_end_offline():
    """Whole CLI on a synthetic street grid. The reddit/report steps run only when the
    study-period Reddit data are present, and must reproduce its Downtown row."""
    tmp = Path(tempfile.mkdtemp())
    args = pilot.build_parser().parse_args(["all", "--out", str(tmp), "--any-date", "--no-pano"])
    args.step_name, args.step = args.step, args.step_m
    args.boundary_geojson = None                    # synthetic grid: placeholder box, no data files
    args.capture_start = args.capture_end = None

    import pandas as pd
    # points from a local roads file (no Overpass)
    roads = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"id": w["way_id"], "name": w["name"]},
         "geometry": {"type": "LineString", "coordinates": w["coords"]}} for w in grid_ways()]}
    (tmp / "roads.geojson").write_text(json.dumps(roads))
    args.roads_geojson = str(tmp / "roads.geojson")
    pts = pilot.cmd_points(args)
    assert len(pts) > 10

    man = pilot.cmd_images(args, client=FakeClient(tmp))
    assert len(man) == 10
    att = pd.read_csv(tmp / "pilot_attempts.csv")
    assert (att.status == "ok").sum() == 10 and len(att) > 10            # misses are logged, not hidden

    assert not man.in_study_period.any()                                  # default run: 2014 flats

    cov = pilot.cmd_coverage(args, client=FakeClient(tmp))
    assert len(cov) == len(pts) and (tmp / "coverage_by_year.csv").exists()

    a2 = pilot.build_parser().parse_args(["images", "--out", str(tmp / "s26")])     # defaults = study period
    a2.step_name, a2.step = a2.step, a2.step_m
    assert (a2.capture_start, a2.capture_end, a2.allow_pano) == (pilot.STUDY_START, pilot.STUDY_END, True)
    (tmp / "s26").mkdir()
    (tmp / "s26" / "sample_points.csv").write_text((tmp / "sample_points.csv").read_text())
    m26 = pilot.cmd_images(a2, client=FakeClient(tmp))
    assert m26.in_study_period.all() and m26.is_pano.all() and len(m26) > 0
    for r in m26.itertuples():                                            # both side views written
        assert (tmp / "s26" / r.image_file).exists() and (tmp / "s26" / r.image_file_other_side).exists()

    sc = pilot.cmd_score(args, encoder=FakeEncoder())
    assert len(sc) == 10 and sc.typology_top1.notna().all()
    typ = [c for c in sc.columns if c.startswith("typ_")]
    assert np.allclose(sc[typ].sum(axis=1), 1, atol=0.01)              # softmax over labels
    for c in [c for c in sc.columns if c.startswith("cue_")]:
        assert sc[c].between(0, 1).all()

    reddit_dir = L.REPO_ROOT / "Data" / "reddit_2026-06-01_2026-08-31"
    if reddit_dir.exists():
        res = pilot.cmd_reddit(args)
        d0 = res["summary"].iloc[0]
        # must reproduce the Downtown row of the existing neighbourhood_summary.csv
        ns = pd.read_csv(reddit_dir / "02_derived_analysis" / "neighbourhood_summary.csv")
        ref = ns[ns.neighbourhood == "Downtown / CBD"].iloc[0]
        assert d0.n_records == ref.total_mentions
        assert abs(d0.mean_sentiment_adj - ref.mean_sentiment) < 0.001
        assert abs(d0.pct_negative - ref.pct_negative) < 0.05
        assert (tmp / "reddit_join.csv").exists()
        rp = pilot.cmd_report(args)
        txt = rp.read_text()
        assert "feasibility pilot" in txt and "CC BY-SA" in txt
        assert (tmp / "contact_sheet.jpg").exists() and (tmp / "validation_template_blind.csv").exists()
        assert "cue_" not in (tmp / "validation_template_blind.csv").read_text()   # blind


def test_no_secret_in_error():
    assert L.scrub("bad token MLY|abc123 here", "MLY|abc123") == "bad token *** here"


def test_key_files_order_and_precedence():
    """Keys come from the shell first, then $CPTED_VISION_ENV_FILE, then
    ~/.config/cpted_vision/secrets.env, then the legacy repository .env. Uses a fake HOME and fake
    key names, so no real credential is read or changed."""
    import os
    tmp = Path(tempfile.mkdtemp())
    saved = {k: os.environ.get(k) for k in ("HOME", "CPTED_VISION_ENV_FILE", "CVS_TEST_A", "CVS_TEST_B")}
    try:
        os.environ["HOME"] = str(tmp)
        os.environ.pop("CPTED_VISION_ENV_FILE", None)
        home_file = tmp / ".config" / "cpted_vision" / "secrets.env"
        assert L.key_files() == [home_file, L.REPO_ROOT / ".env"]
        assert all(L.REPO_ROOT not in p.parents for p in L.key_files()[:-1])     # only the legacy file is in the repo
        override = tmp / "other.env"
        override.write_text("CVS_TEST_A=from_override\n")
        home_file.parent.mkdir(parents=True)
        home_file.write_text("# comment\nCVS_TEST_A=from_home\nCVS_TEST_B='from_home'\n")
        os.environ["CPTED_VISION_ENV_FILE"] = str(override)
        assert L.key_files()[:2] == [override, home_file]
        os.environ.pop("CVS_TEST_A", None)
        os.environ["CVS_TEST_B"] = "from_shell"
        L.load_env()
        assert os.environ["CVS_TEST_A"] == "from_override"       # first file holding the key wins
        assert os.environ["CVS_TEST_B"] == "from_shell"          # the shell wins over every file
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:                       # noqa: BLE001
                fails += 1
                import traceback
                traceback.print_exc()
                print("FAIL", name, e)
    sys.exit(1 if fails else 0)
