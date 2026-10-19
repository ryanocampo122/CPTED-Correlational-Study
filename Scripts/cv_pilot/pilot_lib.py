"""
pilot_lib.py
============
Shared helpers for the October 2026 computer-vision pilot
(ComputerVision_Sentinel: street-level imagery -> CPTED cues -> Reddit).

Design choices
--------------
* Dependency-light on purpose. Geometry uses plain Python + numpy, so the
  sampling step needs no shapely/geopandas. Pillow is needed for image checks.
  torch + transformers are imported lazily and ONLY by ClipEncoder.
* Every network call goes through a small function so it can be mocked in
  tests/test_pilot.py (the test-suite never touches the internet).
* Secrets are read from the .env at the repo root and are never
  written to logs, CSVs or exception messages.
"""
from __future__ import annotations

import json
import math
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]                      # <repo>/Scripts/cv_pilot/pilot_lib.py
DEFAULT_OUT = REPO_ROOT / "Data" / "cv_pilot_2026-10" / "cbd"

# Study area (work plan step 1: the City's neighbourhood boundary). Until the City's
# own file is in hand this is the OSM copy of the Central Business District
# neighbourhood (relation 13754152, admin_level 10), saved by hand in Data/boundaries/.
DEFAULT_BOUNDARY = REPO_ROOT / "Data" / "boundaries" / "central_business_district_osm.geojson"
DEFAULT_BOUNDARY_NAME = "central business"

# Box inherited from the August 2026 prototype (removed; in git history at 060db4f).
# (min_lon, min_lat, max_lon, max_lat). A hand-drawn PLACEHOLDER: only 36% of the
# points it produced fall inside the CBD (Docs/verification/october_2026_checks.md).
# Used only when no boundary file is given (--boundary-geojson "").
DEFAULT_BBOX = (-106.6650, 52.1240, -106.6350, 52.1360)

# Work plan: "about every 50 m along OpenStreetMap roads".
DEFAULT_STEP_M = 50.0
# Drivable + pedestrian-priority streets. Alleys/driveways/parking aisles
# (highway=service) are excluded for the pilot; they matter for CPTED and are
# added back at full scale.
DEFAULT_HIGHWAYS = "motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|pedestrian"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
MAPILLARY_IMAGES_URL = "https://graph.mapillary.com/images"
# Fields confirmed in Mapillary's API v4 docs/SDK. Kept deliberately short:
# an unknown field makes the whole request fail.
MAPILLARY_FIELDS = ("id,captured_at,compass_angle,computed_compass_angle,computed_geometry,geometry,"
                    "is_pano,camera_type,thumb_1024_url,thumb_2048_url")
MAPILLARY_FIELDS_MINIMAL = "id,captured_at,compass_angle,geometry,is_pano,thumb_1024_url,thumb_2048_url"
MAPILLARY_MAX_LIMIT = 2000                      # API maximum per request
LOCAL_TZ = "America/Regina"

SUMMER_MONTHS = (6, 7, 8)                       # study period is June-August
USER_AGENT = "ComputerVision_Sentinel research pilot (University of Saskatchewan)"

# The CLIP model is a pinned requirement (see requirements.txt): this exact revision of the Hugging Face
# repository, never "latest", because a re-uploaded model would change every score. ./flight's install stage
# downloads and checks it; otherwise it downloads on first use (~600 MB, into ~/.cache/huggingface/).
CLIP_MODEL = "openai/clip-vit-base-patch32"
CLIP_REVISION = "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"


# --------------------------------------------------------------------------- #
# Environment / secrets
# --------------------------------------------------------------------------- #
def load_env(path: Path | None = None) -> None:
    """Minimal .env reader (KEY=VALUE). Existing environment variables win."""
    path = path or (REPO_ROOT / ".env")
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get_mapillary_token() -> str:
    """MAPILLARY_TOKEN from the environment or .env. Exits with setup steps if unset.
    A value starting with PASTE is the August prototype's placeholder and is rejected."""
    load_env()
    tok = os.environ.get("MAPILLARY_TOKEN", "").strip()
    if not tok or tok.upper().startswith("PASTE"):
        raise SystemExit(
            "MAPILLARY_TOKEN is empty or still a placeholder.\n"
            f"  The keys live in {REPO_ROOT / '.env'} (copy: {REPO_ROOT / '.venv' / 'keys.txt'}).\n"
            "  Set the line  MAPILLARY_TOKEN=MLY|...  there. To get a token:\n"
            "  1. Sign in at https://www.mapillary.com/dashboard/developers\n"
            "  2. Register an application and copy its Client Token (starts with 'MLY|')\n"
        )
    return tok


def scrub(text: str, secret: str) -> str:
    """Remove a secret from any string before it is logged or raised."""
    return text.replace(secret, "***") if secret else text


# --------------------------------------------------------------------------- #
# Geometry (no shapely)
# --------------------------------------------------------------------------- #
EARTH_R = 6371008.8


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def bearing_deg(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Compass bearing from point 1 to point 2, 0-360 degrees, 0 = north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def angle_diff(a: float, b: float) -> float:
    """Smallest absolute difference between two compass angles, 0..180."""
    d = abs((a - b) % 360)
    return min(d, 360 - d)


class LocalProjection:
    """Equirectangular projection about a reference point (error << 1 m over ~3 km)."""

    def __init__(self, lon0: float, lat0: float):
        self.lon0, self.lat0 = lon0, lat0
        self.ky = math.pi / 180 * EARTH_R
        self.kx = self.ky * math.cos(math.radians(lat0))

    def to_xy(self, lon: float, lat: float) -> tuple[float, float]:
        return ((lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky)

    def to_lonlat(self, x: float, y: float) -> tuple[float, float]:
        return (self.lon0 + x / self.kx, self.lat0 + y / self.ky)


def point_in_ring(x: float, y: float, ring: list) -> bool:
    """Ray-casting test against one closed ring of (x, y) vertices."""
    inside, n, j = False, len(ring), len(ring) - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def point_in_polygons(lon: float, lat: float, polys: list) -> bool:
    """polys = list of polygons; each polygon = [outer_ring, hole, hole, ...] in lon/lat."""
    for rings in polys:
        if point_in_ring(lon, lat, rings[0]) and not any(point_in_ring(lon, lat, h) for h in rings[1:]):
            return True
    return False


def bbox_polygon(bbox: tuple) -> list:
    """(w, s, e, n) box in the polygon-list format used by point_in_polygons."""
    w, s, e, n = bbox
    return [[[(w, s), (e, s), (e, n), (w, n), (w, s)]]]


def _geojson_geometries(obj: dict, name_match: str | None):
    """Yield (properties, geometry) from FeatureCollection / Feature / bare geometry."""
    t = obj.get("type")
    if t == "FeatureCollection":
        for f in obj.get("features", []):
            yield from _geojson_geometries(f, name_match)
    elif t == "Feature":
        props = obj.get("properties") or {}
        if name_match:
            hay = " ".join(str(v) for v in props.values()).lower()
            if name_match.lower() not in hay:
                return
        yield props, obj.get("geometry")
    elif t in ("Polygon", "MultiPolygon", "LineString", "MultiLineString"):
        yield {}, obj


def load_boundary(geojson_path: str | None = None, name_match: str | None = None,
                  bbox: tuple = DEFAULT_BBOX) -> tuple[list, tuple, str]:
    """Return (polygons, bbox, human-readable source)."""
    if not geojson_path:
        return bbox_polygon(bbox), bbox, (
            f"PLACEHOLDER bounding box {bbox} inherited from the earlier prototype "
            "(replace with the City neighbourhood polygon via --boundary-geojson)")
    obj = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    polys = []
    for props, geom in _geojson_geometries(obj, name_match):
        if not geom:
            continue
        if geom["type"] == "Polygon":
            polys.append([[tuple(c[:2]) for c in ring] for ring in geom["coordinates"]])
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                polys.append([[tuple(c[:2]) for c in ring] for ring in poly])
    if not polys:
        seen = set()
        for props, _ in _geojson_geometries(obj, None):
            for v in props.values():
                if isinstance(v, str) and len(v) < 60:
                    seen.add(v)
        raise ValueError(
            f"No polygon in {geojson_path} matched --boundary-name {name_match!r}. "
            f"Some values present in the file: {sorted(seen)[:40]}")
    xs = [c[0] for p in polys for ring in p for c in ring]
    ys = [c[1] for p in polys for ring in p for c in ring]
    if max(abs(v) for v in xs) > 180 or max(abs(v) for v in ys) > 90:
        raise ValueError("Boundary coordinates are not lon/lat (WGS84). Re-export the GeoJSON in EPSG:4326.")
    bb = (min(xs), min(ys), max(xs), max(ys))
    return polys, bb, f"{geojson_path} (match={name_match!r}, {len(polys)} polygon(s))"


# --------------------------------------------------------------------------- #
# Roads -> street segments -> sample points
# --------------------------------------------------------------------------- #
def overpass_query(bbox: tuple, highway_regex: str = DEFAULT_HIGHWAYS) -> str:
    """Overpass QL for every way in bbox whose highway tag matches highway_regex."""
    w, s, e, n = bbox
    return (f'[out:json][timeout:90];\n'
            f'way["highway"~"^({highway_regex})$"]({s},{w},{n},{e});\n'
            f'out geom;')


def parse_overpass(js: dict) -> list[dict]:
    """Overpass JSON -> [{way_id, name, highway, coords}]. Ways with < 2 vertices are dropped."""
    ways = []
    for el in js.get("elements", []):
        if el.get("type") != "way" or not el.get("geometry"):
            continue
        coords = [(g["lon"], g["lat"]) for g in el["geometry"]]
        if len(coords) < 2:
            continue
        tags = el.get("tags", {})
        ways.append({"way_id": str(el["id"]), "name": tags.get("name", ""),
                     "highway": tags.get("highway", ""), "coords": coords})
    return ways


def fetch_roads_overpass(bbox: tuple, highway_regex: str = DEFAULT_HIGHWAYS, session=None,
                         endpoints=None) -> tuple[list[dict], str]:
    """Road ways from the first Overpass endpoint that returns any. Returns (ways, endpoint)."""
    import requests
    session = session or requests.Session()
    last = None
    for url in (endpoints or OVERPASS_ENDPOINTS):
        try:
            r = session.post(url, data={"data": overpass_query(bbox, highway_regex)},
                             headers={"User-Agent": USER_AGENT}, timeout=120)
            r.raise_for_status()
            ways = parse_overpass(r.json())
            if ways:
                return ways, url
            last = f"{url}: returned no ways"
        except Exception as exc:                          # noqa: BLE001
            last = f"{url}: {exc}"
    raise RuntimeError(f"Overpass failed on every endpoint (last: {last}). "
                       "Use --roads-geojson with a local export of the road network instead.")


def load_roads_geojson(path: str) -> list[dict]:
    """Local (Multi)LineString GeoJSON -> way dicts in the same shape as parse_overpass."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    ways = []
    for i, (props, geom) in enumerate(_geojson_geometries(obj, None)):
        if not geom:
            continue
        lines = ([geom["coordinates"]] if geom["type"] == "LineString"
                 else geom["coordinates"] if geom["type"] == "MultiLineString" else [])
        for k, line in enumerate(lines):
            coords = [tuple(c[:2]) for c in line]
            if len(coords) >= 2:
                wid = str(props.get("id") or props.get("OBJECTID") or props.get("@id") or f"local{i}")
                ways.append({"way_id": wid if k == 0 else f"{wid}.{k}",
                             "name": props.get("name") or props.get("STREET") or "",
                             "highway": props.get("highway", ""), "coords": coords})
    return ways


def _ckey(c) -> tuple:
    """Vertex key rounded to ~1 cm so shared vertices compare equal."""
    return (round(c[0], 7), round(c[1], 7))


def split_at_intersections(ways: list[dict]) -> list[dict]:
    """Split each way wherever it shares a vertex with another way, giving block-face
    street segments (the unit of analysis in the work plan). Works from coordinates,
    so it does not depend on OSM node ids being present."""
    count = Counter()
    for w in ways:
        for k in {_ckey(c) for c in w["coords"]}:
            count[k] += 1
    segs = []
    for w in ways:
        coords, start, part = w["coords"], 0, 0
        for i in range(1, len(coords)):
            if i == len(coords) - 1 or count[_ckey(coords[i])] > 1:
                piece = coords[start:i + 1]
                if len(piece) >= 2:
                    segs.append({"segment_id": f"{w['way_id']}_{part}", "way_id": w["way_id"],
                                 "name": w["name"], "highway": w["highway"], "coords": piece})
                    part += 1
                start = i
    return segs


def resample_polyline(xy: list, step: float) -> list[tuple]:
    """Evenly spaced points (spacing ~= step) along a polyline in metres.
    Returns [(x, y, along_m, bearing_deg_of_local_segment)]. A line shorter than
    1.5*step gets one midpoint sample."""
    seg = [math.hypot(xy[i + 1][0] - xy[i][0], xy[i + 1][1] - xy[i][1]) for i in range(len(xy) - 1)]
    total = sum(seg)
    if total <= 0:
        return []
    n = max(1, round(total / step))
    targets = [(i + 0.5) * total / n for i in range(n)]
    out, acc, si = [], 0.0, 0
    for t in targets:
        while si < len(seg) - 1 and acc + seg[si] < t:
            acc += seg[si]
            si += 1
        f = 0.0 if seg[si] == 0 else (t - acc) / seg[si]
        x = xy[si][0] + f * (xy[si + 1][0] - xy[si][0])
        y = xy[si][1] + f * (xy[si + 1][1] - xy[si][1])
        brg = (math.degrees(math.atan2(xy[si + 1][0] - xy[si][0], xy[si + 1][1] - xy[si][1])) + 360) % 360
        out.append((x, y, t, brg))
    return out


def generate_points(segments: list[dict], polys: list, step: float = DEFAULT_STEP_M,
                    min_sep_m: float = 10.0) -> list[dict]:
    """Sample points every ~step m along each segment, kept only inside the boundary.
    Near-duplicates (< min_sep_m, e.g. at junctions) are dropped."""
    if not segments:
        return []
    allc = [c for s in segments for c in s["coords"]]
    proj = LocalProjection(sum(c[0] for c in allc) / len(allc), sum(c[1] for c in allc) / len(allc))
    taken: dict[tuple, list] = {}
    pts = []
    for s in segments:
        xy = [proj.to_xy(*c) for c in s["coords"]]
        seg_len = sum(math.hypot(xy[i + 1][0] - xy[i][0], xy[i + 1][1] - xy[i][1]) for i in range(len(xy) - 1))
        for x, y, along, brg in resample_polyline(xy, step):
            lon, lat = proj.to_lonlat(x, y)
            if not point_in_polygons(lon, lat, polys):
                continue
            cell = (int(x // min_sep_m), int(y // min_sep_m))
            near = [q for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                    for q in taken.get((cell[0] + dx, cell[1] + dy), [])]
            if any(math.hypot(x - qx, y - qy) < min_sep_m for qx, qy in near):
                continue
            taken.setdefault(cell, []).append((x, y))
            pts.append({"lon": round(lon, 7), "lat": round(lat, 7), "segment_id": s["segment_id"],
                        "osm_way_id": s["way_id"], "road_name": s["name"], "highway": s["highway"],
                        "along_m": round(along, 1), "segment_len_m": round(seg_len, 1),
                        "road_bearing_deg": round(brg, 1)})
    pts.sort(key=lambda p: (p["segment_id"], p["along_m"]))
    for i, p in enumerate(pts, 1):
        p["point_id"] = f"P{i:04d}"
    return pts


def spread_order(points: list[dict]) -> list[int]:
    """Deterministic farthest-point ordering: start at the point nearest the centroid,
    then repeatedly add the point farthest from everything chosen so far. Any prefix of
    this list is a spatially spread sample, chosen WITHOUT looking at imagery or any
    outcome variable (so the pilot cannot be cherry-picked)."""
    if not points:
        return []
    proj = LocalProjection(np.mean([p["lon"] for p in points]), np.mean([p["lat"] for p in points]))
    xy = np.array([proj.to_xy(p["lon"], p["lat"]) for p in points])
    first = int(np.argmin(((xy - xy.mean(axis=0)) ** 2).sum(axis=1)))
    order, mind = [first], ((xy - xy[first]) ** 2).sum(axis=1)
    while len(order) < len(points):
        nxt = int(np.argmax(mind))
        order.append(nxt)
        mind = np.minimum(mind, ((xy - xy[nxt]) ** 2).sum(axis=1))
    return order


# --------------------------------------------------------------------------- #
# Mapillary
# --------------------------------------------------------------------------- #
def local_window(start: str | None, end: str | None) -> tuple[datetime, datetime] | None:
    """('2026-06-01', '2026-08-31') in Saskatoon local time -> (start, end) as aware
    UTC datetimes, end inclusive to 23:59:59. None if neither is given."""
    if not start and not end:
        return None
    from datetime import date, time as dtime
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(LOCAL_TZ)
    s = datetime.combine(date.fromisoformat(start or "2000-01-01"), dtime.min, tz)
    e = datetime.combine(date.fromisoformat(end or "2100-01-01"), dtime(23, 59, 59), tz)
    return s.astimezone(timezone.utc), e.astimezone(timezone.utc)


def iso_z(d: datetime) -> str:
    """UTC timestamp in the format Mapillary's capture-date filters accept."""
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_captured_at(v) -> datetime | None:
    """Mapillary capture time (epoch ms, epoch s or ISO string) -> aware UTC datetime, or None."""
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)) or str(v).isdigit():
            v = float(v)
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc)
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:                                      # noqa: BLE001
        return None


def image_lonlat(c: dict) -> tuple[float, float] | None:
    """Image position, preferring Mapillary's corrected computed_geometry."""
    g = c.get("computed_geometry") or c.get("geometry")
    if g and g.get("coordinates"):
        return g["coordinates"][0], g["coordinates"][1]
    return None


def heading_of(c: dict):
    """Camera heading in degrees, preferring computed_compass_angle. None if absent."""
    h = c.get("computed_compass_angle")
    if h is None:
        h = c.get("compass_angle")
    return None if h is None else float(h)


def choose_image(cands: list[dict], lon: float, lat: float, max_dist_m: float,
                 summer_months=SUMMER_MONTHS, window: tuple | None = None,
                 allow_pano: bool = False, prefer: str = "recent") -> tuple[dict | None, str]:
    """Pick one image for a sample point. Rule (fixed in advance, see README):
    drop images farther than max_dist_m, without a thumbnail, outside the capture
    window (if one is set), and panoramas unless allow_pano (a panorama also needs a
    heading so it can be cropped). Then rank:
      prefer="recent": most recent year > Jun-Aug capture > flat over panorama > nearest
      prefer="summer": Jun-Aug capture > most recent year > flat over panorama > nearest
    Returns (candidate_or_None, reason)."""
    if not cands:
        return None, "no_images_in_search_box"
    usable, dropped = [], Counter()
    for c in cands:
        pano = bool(c.get("is_pano"))
        if pano and not allow_pano:
            dropped["panorama"] += 1
            continue
        url = (c.get("thumb_2048_url") or c.get("thumb_1024_url")) if pano else c.get("thumb_1024_url")
        if not url:
            dropped["no_thumbnail"] += 1
            continue
        if pano and heading_of(c) is None:
            dropped["panorama_no_heading"] += 1
            continue
        ll, dt = image_lonlat(c), parse_captured_at(c.get("captured_at"))
        if ll is None or dt is None:
            dropped["no_geometry_or_date"] += 1
            continue
        if window and not (window[0] <= dt <= window[1]):
            dropped["outside_capture_window"] += 1
            continue
        d = haversine_m(lon, lat, ll[0], ll[1])
        if d > max_dist_m:
            dropped["too_far"] += 1
            continue
        usable.append({**c, "_dist_m": d, "_dt": dt, "_summer": dt.month in summer_months,
                       "_pano": pano, "_url": url})
    if not usable:
        return None, "none_usable(" + ",".join(f"{k}={v}" for k, v in dropped.items()) + ")"
    if prefer == "summer":
        key = lambda c: (not c["_summer"], -c["_dt"].year, c["_pano"], c["_dist_m"])  # noqa: E731
    else:
        key = lambda c: (-c["_dt"].year, not c["_summer"], c["_pano"], c["_dist_m"])  # noqa: E731
    usable.sort(key=key)
    return usable[0], "ok"


def equirect_to_perspective(pano, yaw_deg: float, fov_deg: float = 90.0,
                            out_w: int = 1024, out_h: int = 768, pitch_deg: float = 0.0):
    """Cut a normal (rectilinear) camera view out of a 360-degree equirectangular image.
    yaw_deg is measured from the panorama's centre column (0 = the direction the centre
    of the panorama faces). Bilinear sampling with numpy; returns a PIL image."""
    from PIL import Image
    src = np.asarray(pano.convert("RGB"), dtype=np.float32)
    H, W = src.shape[:2]
    f = (out_w / 2) / math.tan(math.radians(fov_deg) / 2)
    xs = np.arange(out_w) - (out_w - 1) / 2
    ys = np.arange(out_h) - (out_h - 1) / 2
    x, y = np.meshgrid(xs, ys)
    z = np.full_like(x, f)
    # pitch (rotate about x), then yaw (rotate about y)
    p = math.radians(pitch_deg)
    y2 = y * math.cos(p) - z * math.sin(p)
    z2 = y * math.sin(p) + z * math.cos(p)
    lon = np.arctan2(x, z2) + math.radians(yaw_deg)
    lat = -np.arctan2(y2, np.hypot(x, z2))
    u = ((lon / (2 * math.pi) + 0.5) % 1.0) * W - 0.5
    v = (0.5 - lat / math.pi) * H - 0.5
    v = np.clip(v, 0, H - 1)
    u0 = np.floor(u).astype(int)
    v0 = np.floor(v).astype(int)
    du, dv = (u - u0)[..., None], (v - v0)[..., None]
    u1, v1 = (u0 + 1) % W, np.minimum(v0 + 1, H - 1)
    u0 %= W
    out = (src[v0, u0] * (1 - du) * (1 - dv) + src[v0, u1] * du * (1 - dv)
           + src[v1, u0] * (1 - du) * dv + src[v1, u1] * du * dv)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


class MapillaryClient:
    """Tiny client for the images search endpoint (token sent in a header, never logged)."""

    def __init__(self, token: str, session=None, pause_s: float = 0.3):
        import requests
        self.token, self.pause_s = token, pause_s
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _get(self, params: dict):
        """GET /images with the token as a header; retried as a query parameter on 401/403."""
        r = self.session.get(MAPILLARY_IMAGES_URL, params=params, timeout=30,
                             headers={"Authorization": f"OAuth {self.token}"})
        if r.status_code in (401, 403):               # some tokens only work as a query param
            r = self.session.get(MAPILLARY_IMAGES_URL, params={**params, "access_token": self.token}, timeout=30)
        return r

    def search(self, lon: float, lat: float, radius_m: float, window: tuple | None = None) -> list[dict]:
        """Images in a square of half-width radius_m around a point (distance is filtered later)."""
        dlat = radius_m / 111320.0
        dlon = radius_m / (111320.0 * math.cos(math.radians(lat)))
        return self.search_bbox((lon - dlon, lat - dlat, lon + dlon, lat + dlat), window, limit=500)

    def search_bbox(self, bbox: tuple, window: tuple | None = None, limit: int = MAPILLARY_MAX_LIMIT) -> list[dict]:
        """Images in a lon/lat box (must be < 0.01 square degrees), optionally only those
        captured inside window (aware datetimes), filtered server-side."""
        params = {"bbox": ",".join(f"{v:.7f}" for v in bbox), "fields": MAPILLARY_FIELDS, "limit": limit}
        if window:
            params["start_captured_at"], params["end_captured_at"] = iso_z(window[0]), iso_z(window[1])
        try:
            r = self._get(params)
            if r.status_code == 400:                  # field rejected -> retry with the minimal set
                r = self._get({**params, "fields": MAPILLARY_FIELDS_MINIMAL})
            if r.status_code in (401, 403):
                raise SystemExit("Mapillary rejected the token (HTTP %d). Check MAPILLARY_TOKEN in .env." % r.status_code)
            r.raise_for_status()
            time.sleep(self.pause_s)
            return r.json().get("data", [])
        except SystemExit:  # pylint: disable=try-except-raise  # let it past the broad handler below
            raise
        except Exception as exc:                          # noqa: BLE001
            raise RuntimeError(scrub(str(exc), self.token)) from None

    def download(self, url: str, dest: Path) -> int:
        """Save an image URL to dest. Returns bytes written."""
        r = self.session.get(url, timeout=60)             # CDN link, no token needed
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return len(r.content)


def image_quality(path: Path) -> dict:
    """Cheap quality metrics on a 512-px-wide greyscale copy. Thresholds are PROVISIONAL
    and are to be calibrated against the ~150 hand-labelled images."""
    from PIL import Image
    im = Image.open(path)
    w, h = im.size
    g = im.convert("L").resize((512, max(8, int(512 * h / w))))
    a = np.asarray(g, dtype=np.float32)
    lap = a[1:-1, 1:-1] * 4 - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
    q = {"width": w, "height": h, "brightness": round(float(a.mean()), 1), "sharpness": round(float(lap.var()), 1)}
    q["flags"] = ";".join(f for f, bad in [("dark", q["brightness"] < 40), ("overexposed", q["brightness"] > 215),
                                           ("low_sharpness", q["sharpness"] < 30), ("low_res", w < 640)] if bad)
    return q


# --------------------------------------------------------------------------- #
# CLIP (zero-shot): the only part that needs torch / transformers
# --------------------------------------------------------------------------- #
class ClipEncoder:
    """Thin wrapper over Hugging Face CLIP. Returns L2-normalised embeddings."""

    def __init__(self, model_name: str = CLIP_MODEL, device: str | None = None, revision: str = CLIP_REVISION):
        import torch
        from transformers import CLIPModel, CLIPProcessor
        self.torch = torch
        if device is None:
            device = ("cuda" if torch.cuda.is_available()
                      else "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
                      else "cpu")
        self.device, self.model_name, self.revision = device, model_name, revision
        self.model = CLIPModel.from_pretrained(model_name, revision=revision).to(device).eval()
        self.proc = CLIPProcessor.from_pretrained(model_name, revision=revision)
        self.logit_scale = float(self.model.logit_scale.exp().item())     # = 100 for released CLIP

    def _norm(self, feats):
        """L2-normalise features to float64 numpy (dot product = cosine similarity)."""
        if not self.torch.is_tensor(feats):                # newer transformers return an output object
            feats = getattr(feats, "pooler_output", feats[0])
        feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.detach().cpu().numpy().astype(np.float64)

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        with self.torch.no_grad():
            inp = self.proc(text=texts, return_tensors="pt", padding=True, truncation=True).to(self.device)
            return self._norm(self.model.get_text_features(**inp))

    def encode_images(self, images: list) -> np.ndarray:
        with self.torch.no_grad():
            inp = self.proc(images=images, return_tensors="pt").to(self.device)
            return self._norm(self.model.get_image_features(**inp))


def square_views(im, n: int = 3) -> list:
    """CLIP centre-crops to a square, which would discard the sides of a wide street
    photo. Score n square crops (left / centre / right) and aggregate instead."""
    w, h = im.size
    if w <= h * 1.15 or n == 1:
        s = min(w, h)
        l, t = (w - s) // 2, (h - s) // 2
        return [im.crop((l, t, l + s, t + s))]
    s = h
    xs = [round(i * (w - s) / (n - 1)) for i in range(n)]
    return [im.crop((x, 0, x + s, s)) for x in xs]


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


@dataclass
class ClipScorer:
    """Zero-shot scoring from prompt sets in clip_prompts.json.
    * typology: softmax over land-use labels (single-label)
    * cues: for each cue, softmax over [positive prompt, negative prompt] -> P(cue present)
    Probabilities are UNCALIBRATED (they depend on the contrast wording). They rank and
    compare images; they are not measurements until validated against hand labels."""
    encoder: Any            # ClipEncoder, or any object with encode_texts / encode_images
    prompts: dict
    views: int = 3
    _typ: dict = field(default_factory=dict, init=False)
    _cue: dict = field(default_factory=dict, init=False)

    def _embed_phrases(self, phrases: list[str]) -> np.ndarray:
        """Mean embedding over every phrase x template, re-normalised (prompt ensembling)."""
        texts = [t.format(p) for p in phrases for t in self.prompts["templates"]]
        e = self.encoder.encode_texts(texts).mean(axis=0)
        return e / np.linalg.norm(e)

    def prepare(self) -> None:
        """Embed all typology labels and cue prompt pairs once."""
        self._typ = {k: self._embed_phrases(v) for k, v in self.prompts["typology"].items()
                     if not k.startswith("_")}
        self._cue = {k: (self._embed_phrases(v["positive"]), self._embed_phrases(v["negative"]))
                     for k, v in self.prompts["cues"].items() if not k.startswith("_")}

    def score(self, im) -> dict:
        """One image -> typology top-2, per-label probabilities, and per-cue mean/max
        P(present) across square views."""
        if not self._typ:
            self.prepare()
        scale = getattr(self.encoder, "logit_scale", 100.0)
        views = square_views(im, self.views)
        img = self.encoder.encode_images(views)                         # (v, d)
        labels = list(self._typ)
        t_prob = _softmax(scale * img @ np.stack([self._typ[k] for k in labels]).T).mean(axis=0)
        order = np.argsort(-t_prob)
        out = {"typology_top1": labels[order[0]], "typology_top1_prob": round(float(t_prob[order[0]]), 3),
               "typology_top2": labels[order[1]], "typology_top2_prob": round(float(t_prob[order[1]]), 3),
               "typology_margin": round(float(t_prob[order[0]] - t_prob[order[1]]), 3),
               "n_views": len(views)}
        out["typology_low_confidence"] = bool(out["typology_top1_prob"] < 0.40 or out["typology_margin"] < 0.10)
        for k, p in zip(labels, t_prob):
            out[f"typ_{k}"] = round(float(p), 3)
        for k, (pos, neg) in self._cue.items():
            pr = _softmax(scale * np.stack([img @ pos, img @ neg], axis=1))[:, 0]     # per view
            out[f"cue_{k}_mean"] = round(float(pr.mean()), 3)
            out[f"cue_{k}_max"] = round(float(pr.max()), 3)
        return out


def load_prompts(path: Path | None = None) -> dict:
    return json.loads((path or (HERE / "clip_prompts.json")).read_text())


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a proportion (honest about small counts)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def git_commit() -> str:
    """Short hash of HEAD, or 'n/a' outside a git checkout."""
    import subprocess
    try:
        return subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"], check=False,
                              capture_output=True, text=True, timeout=5).stdout.strip() or "n/a"
    except Exception:                                      # noqa: BLE001
        return "n/a"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
