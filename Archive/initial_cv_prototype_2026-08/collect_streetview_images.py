"""
08_collect_streetview_images.py

Pulls street-level imagery for the case-study sites (Downtown/CBD,
Riverbank/Meewasin) from Mapillary, so the CV pillar has something to
score. Mapillary (not Google Street View) because: (1) free API,
(2) CC-BY-SA so images can actually appear in the report/paper without
a licensing question, (3) faces/plates are auto-blurred, which sidesteps
a hunk of the "is this human-subjects data" question in the ethics
application.

Requires a free Mapillary access token: https://www.mapillary.com/dashboard/developers
Run locally, not in a sandboxed environment - needs open internet access
to graph.mapillary.com.

Output:
    ../data_pkg_august/05_cv_streetscape/streetview_points.csv
    ../data_pkg_august/05_cv_streetscape/images/<site_slug>/<image_id>.jpg
"""

import csv
import os
import time
import requests

MAPILLARY_TOKEN = "PASTE_YOUR_TOKEN_HERE"

# Approximate bounding boxes (min_lon, min_lat, max_lon, max_lat).
# PLACEHOLDER - refine these against the actual site boundaries you use
# for the Reddit neighbourhood tagging (City of Saskatoon Open Data has
# neighbourhood polygon GeoJSON if you want exact boundaries instead of
# a hand-drawn bbox like the one in your screenshot).
SITES = {
    "downtown_cbd": (-106.6650, 52.1240, -106.6350, 52.1360),
    "riverbank_meewasin": (-106.6500, 52.1150, -106.6250, 52.1400),
}

GRID_STEP_DEG = 0.0015  # ~150m at this latitude; tighten if you want denser sampling
SEARCH_RADIUS_M = 75
OUT_DIR = "../data_pkg_august/05_cv_streetscape"


def grid_points(bbox, step):
    min_lon, min_lat, max_lon, max_lat = bbox
    lon = min_lon
    while lon <= max_lon:
        lat = min_lat
        while lat <= max_lat:
            yield lon, lat
            lat += step
        lon += step


def nearest_image(lon, lat, radius_m):
    resp = requests.get(
        "https://graph.mapillary.com/images",
        params={
            "access_token": MAPILLARY_TOKEN,
            "fields": "id,thumb_1024_url,captured_at,compass_angle",
            "closeto": f"{lon},{lat}",
            "radius": radius_m,
            "limit": 1,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return data[0] if data else None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []

    for site_slug, bbox in SITES.items():
        img_dir = os.path.join(OUT_DIR, "images", site_slug)
        os.makedirs(img_dir, exist_ok=True)

        for lon, lat in grid_points(bbox, GRID_STEP_DEG):
            try:
                img = nearest_image(lon, lat, SEARCH_RADIUS_M)
            except requests.RequestException as e:
                print(f"  request failed at {lon:.5f},{lat:.5f}: {e}")
                continue

            if img is None:
                continue

            img_path = os.path.join(img_dir, f"{img['id']}.jpg")
            if not os.path.exists(img_path):
                jpg = requests.get(img["thumb_1024_url"], timeout=15).content
                with open(img_path, "wb") as f:
                    f.write(jpg)

            rows.append({
                "site": site_slug,
                "image_id": img["id"],
                "sample_lon": lon,
                "sample_lat": lat,
                "captured_at": img.get("captured_at"),
                "image_path": img_path,
            })
            time.sleep(0.1)  # be polite to the API

        print(f"{site_slug}: {sum(r['site'] == site_slug for r in rows)} images collected")

    out_csv = os.path.join(OUT_DIR, "streetview_points.csv")
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out_csv}")


if __name__ == "__main__":
    main()
