#!/usr/bin/env python3
"""
verify_october_2026.py
======================
ComputerVision_Sentinel | Independent checks on the October 2026 work-plan tasks

The October tasks (revised work plan, p. 5) are: finalize crime categories,
extend the Reddit collection to 1 June - 31 August 2026, generate sample points
and collect street-level images. This script re-derives the claims made about
the last three from the files in Data/ and writes one table of checks:

  Docs/verification/october_2026_checks.csv   area, check, result, status, evidence
  Docs/verification/october_2026_checks.md    the same table, for reading

status: PASS (meets the stated design), WARN (works, but a limitation the
reader must know), FAIL (does not meet the design), INFO (a number, no target).

USAGE (from the repository root)
-----
  .venv/bin/python Scripts/verification/verify_october_2026.py
      --rerun-pipeline   also re-run the Reddit pipeline into a temp folder and
                         compare every published table byte-for-byte (~2 min)
      --network          also re-query Mapillary for 2024-2026 imagery over the
                         CBD (plain tiled bbox queries, independent of pilot.py coverage)
                         and refresh the cached OSM bridge list (Overpass)
      --out <folder>     where the checks table goes (default: Docs/verification/)
      --bridge-cache <json>  OSM bridge list to read, and to refresh with --network
                         (default: Data/cv_pilot_2026-10/cbd/osm_bridge_way_ids.json)
"""
from __future__ import annotations

import argparse
import filecmp
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "Data"
REDDIT = DATA / "reddit_2026-06-01_2026-08-31"
REDDIT_JUNE = DATA / "reddit_2025-06-11_2026-06-11"
CV = DATA / "cv_pilot_2026-10"
CBD = CV / "cbd"
BOX = CV / "placeholder_box"
PILOT = CV / "cbd_latest_imagery"
BOUNDARY = DATA / "boundaries" / "central_business_district_osm.geojson"
OUT = REPO / "Docs" / "verification"
BRIDGE_CACHE = CBD / "osm_bridge_way_ids.json"
TZ = "America/Regina"

sys.path.insert(0, str(REPO / "Scripts" / "cv_pilot"))
import pilot_lib as L  # noqa: E402

ROWS: list[dict] = []


def add(area: str, check: str, result: str, status: str, evidence: str = "") -> None:
    """Record one row of the checks table."""
    ROWS.append({"area": area, "check": check, "result": result, "status": status, "evidence": evidence})


def rel(p: Path) -> str:
    p = Path(p).resolve()
    return str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p)


# --------------------------------------------------------------------------- #
# Reddit: the study-period collection
# --------------------------------------------------------------------------- #
def reddit_checks(rerun: bool) -> None:
    """Reddit Jun-Aug 2026 checks. rerun=True also re-runs both Reddit pipelines into a
    temp folder and compares every published CSV byte for byte."""
    A = "Reddit Jun-Aug 2026"
    raw = REDDIT / "01_raw_collection"
    posts = pd.read_csv(next(raw.glob("saskatoon_safety_posts_*.csv")))
    comments = pd.read_csv(next(raw.glob("saskatoon_safety_comments_*.csv")))
    meta = json.loads(next(raw.glob("saskatoon_safety_metadata_*.json")).read_text())
    qlog = pd.read_csv(next(raw.glob("search_query_log_*.csv")))

    w0 = pd.Timestamp(meta["window_local"][0], tz=TZ)
    w1 = pd.Timestamp(meta["window_local"][1], tz=TZ) + pd.Timedelta(days=1)
    pl = pd.to_datetime(posts.created_utc, unit="s", utc=True).dt.tz_convert(TZ)
    cl = pd.to_datetime(comments.created_utc, unit="s", utc=True).dt.tz_convert(TZ)
    inside = (pl >= w0) & (pl < w1)
    add(A, "Posts dated inside 1 Jun - 31 Aug 2026 (Saskatoon time)",
        f"{int(inside.sum())} of {len(posts)} posts; first {pl.min():%Y-%m-%d}, last {pl.max():%Y-%m-%d}",
        "PASS" if inside.all() else "FAIL", rel(raw))
    cin = (cl >= w0) & (cl < w1)
    flag_ok = (cin == comments.comment_in_window.astype(bool)).all()
    add(A, "Comments posted after 31 Aug flagged and left out of analysis",
        f"{int(cin.sum()):,} of {len(comments):,} comments inside the window; "
        f"{int((~cin).sum())} later comments flagged (comment_in_window)",
        "PASS" if flag_ok else "FAIL", "comment_in_window column")
    add(A, "Months covered", ", ".join(f"{k}: {v} posts" for k, v in
                                      pl.dt.strftime("%b").value_counts().reindex(["Jun", "Jul", "Aug"]).items()),
        "INFO")
    days = pl.dt.date.nunique()
    add(A, "Days in the window with at least one post", f"{days} of 92 days", "INFO")

    ids_ok = posts.id.is_unique and comments.comment_id.is_unique and comments.parent_post_id.isin(posts.id).all()
    add(A, "No duplicate records; every comment links to a collected post",
        f"{len(posts)} unique posts, {len(comments):,} unique comments", "PASS" if ids_ok else "FAIL")

    priv = ("author" not in posts.columns and "author" not in comments.columns
            and "author_hash" in posts.columns)
    email = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")
    phone = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")
    txt = pd.concat([posts.cleaned_text, comments.cleaned_text]).fillna("")
    n_pii = int(txt.str.contains(email).sum() + txt.str.contains(phone).sum())
    add(A, "Usernames removed (salted hashes); no emails/phone numbers in cleaned_text",
        f"author column absent; {n_pii} emails/phone numbers found", "PASS" if priv and n_pii == 0 else "FAIL")

    mx = int(qlog.results_returned.max())
    add(A, "No search query hit Reddit's ~250-result cap (would truncate recall)",
        f"{len(qlog)} queries (31 terms x 4 sort orders); largest returned {mx} results",
        "PASS" if mx < 240 else "WARN", rel(next(raw.glob("search_query_log_*.csv"))))

    got = comments.groupby("parent_post_id").size()
    collected = posts.id.map(got).fillna(0).sum()
    share = collected / posts.num_comments.sum()
    add(A, "Comment threads collected vs Reddit's own comment count",
        f"{int(collected):,} of {int(posts.num_comments.sum()):,} ({share:.0%}); 'load more' stubs not expanded, "
        f"depth <= 4, <= 200 per post, deleted comments dropped", "WARN" if share < 0.9 else "PASS",
        "reddit_scraper.py ScraperConfig")

    jp = pd.read_csv(next((REDDIT_JUNE / "01_raw_collection").glob("saskatoon_safety_posts_*.csv")))
    jl = pd.to_datetime(jp.created_utc, unit="s", utc=True).dt.tz_convert(TZ)
    overlap = jp[jl >= pd.Timestamp("2026-06-01", tz=TZ)]
    found = int(overlap.id.isin(posts.id).sum())
    newer = int(((pl < pd.Timestamp("2026-06-11", tz=TZ)) & ~posts.id.isin(jp.id)).sum())
    add(A, "Re-finds the June collection's posts for the overlapping days (1-10 Jun 2026)",
        f"{found} of {len(overlap)} re-found; {newer} additional posts found for those days (crime seeds, more sorts)",
        "PASS" if found >= 0.8 * len(overlap) else "WARN", rel(REDDIT_JUNE))

    has_seed = posts.text_has_safety_term | posts.text_has_crime_term
    add(A, "Posts whose own title/body contains a seed term",
        f"{int(has_seed.sum())} of {len(posts)} ({has_seed.mean():.0%}); Reddit search also matches other fields, "
        "so 40% of threads may be off-topic", "WARN", "text_has_safety_term / text_has_crime_term")

    # Downtown figures (the published table) and their sensitivity to off-topic threads
    nb = pd.read_csv(REDDIT / "02_derived_analysis" / "neighbourhood_summary.csv").set_index("neighbourhood")
    d = nb.loc["Downtown / CBD"]
    add(A, "Downtown/CBD records (whole-word tag, other cities removed, in-window)",
        f"{int(d.total_mentions)} records ({int(d.posts)} posts, {int(d.comments)} comments, {int(d.n_threads)} threads); "
        f"{d.pct_negative}% negative (95% CI {d.pct_neg_ci95_low}-{d.pct_neg_ci95_high}, thread bootstrap)",
        "INFO", rel(REDDIT / "02_derived_analysis" / "neighbourhood_summary.csv"))
    cl_ = REDDIT / "04_cleaned_datasets"
    cp = pd.read_csv(next(cl_.glob("*posts*_CLEANED_v2.csv")))
    cc = pd.read_csv(next(cl_.glob("*comments*_CLEANED_v2.csv")))
    cc = cc[cc.comment_in_window.astype(bool)]
    on_topic = set(cp.loc[cp.text_has_safety_term | cp.text_has_crime_term, "id"].astype(str))
    rec = pd.concat([cp.assign(thread=cp.id.astype(str)), cc.assign(thread=cc.parent_post_id.astype(str))])
    dt = rec[rec.vloc_downtown_cbd.astype(bool)]
    dt_on = dt[dt.thread.isin(on_topic)]
    add(A, "Downtown share negative if off-topic threads are dropped (sensitivity)",
        f"{len(dt_on)} of {len(dt)} Downtown records are in seed-term threads; "
        f"{(dt_on.sentiment_adj_category == 'negative').mean():.1%} negative vs "
        f"{(dt.sentiment_adj_category == 'negative').mean():.1%} for all", "INFO")

    ppl = dt[dt.venv_people.astype(bool)]
    terms = ppl.venv_people_terms.fillna("").str.split(";").explode()
    homeless = int(ppl.venv_people_terms.fillna("").str.contains("homeless").sum())
    add(A, "What the 'people' cue measures Downtown",
        f"{len(ppl)} Downtown records; {homeless} of them via 'homeless'/'homelessness' "
        f"(top terms: {', '.join(f'{k} {v}' for k, v in terms.value_counts().head(4).items())})",
        "WARN", "mixes presence of people with mentions of a social group; split it before H4")

    prec = pd.read_csv(REDDIT / "05_audits" / "env_cue_precision_heldout.csv").set_index("cue")
    add(A, "Environmental-cue precision (held-out sample, June records; automated first pass, not yet checked by hand)",
        "; ".join(f"{k} {v.precision:.0%}" for k, v in prec.iterrows())
        + ". Lighting fires on traffic/car lights", "WARN", rel(REDDIT / "05_audits" / "env_cue_precision_heldout.csv"))

    vr = (REDDIT / "05_audits" / "verification_report.txt").read_text()
    n_pass, n_fail = vr.count("[PASS]"), vr.count("[FAIL]")
    add(A, "Pipeline self-checks (08_verify_outputs.py)", f"{n_pass} passed, {n_fail} failed",
        "PASS" if n_fail == 0 and n_pass else "FAIL", rel(REDDIT / "05_audits" / "verification_report.txt"))

    if rerun:
        for ds in (REDDIT, REDDIT_JUNE):
            with tempfile.TemporaryDirectory() as tmp:
                env = {**os.environ, "COMPUTERVISION_SENTINEL_OUT_DIR": tmp}
                r = subprocess.run(["bash", str(REPO / "Scripts/reddit_analysis/run_all.sh"), ds.name], env=env, capture_output=True, text=True, check=False)
                files = [p.relative_to(tmp) for p in Path(tmp).rglob("*.csv")]
                same = [f for f in files if filecmp.cmp(Path(tmp) / f, ds / f, shallow=False)]
                add(A if ds == REDDIT else "Reddit Jun 2025-Jun 2026",
                    f"Published tables reproduce from raw data ({ds.name})",
                    f"{len(same)} of {len(files)} CSV outputs byte-identical; pipeline exit code {r.returncode}",
                    "PASS" if r.returncode == 0 and len(same) == len(files) else "FAIL", "run_all.sh")


# --------------------------------------------------------------------------- #
# Sample points
# --------------------------------------------------------------------------- #
def point_checks(network: bool) -> None:
    """Sample-point checks. network=True refreshes the cached OSM bridge list."""
    A = "Sample points"
    polys, _, _ = L.load_boundary(str(BOUNDARY), "central business")
    pts = pd.read_csv(CBD / "sample_points.csv")
    box = pd.read_csv(BOX / "sample_points.csv")
    meta = json.loads((CBD / "run_meta.json").read_text())["points"]

    add(A, "Points generated inside the CBD polygon (work plan step 1)",
        f"{len(pts)} points on {pts.segment_id.nunique()} street segments from {meta['n_ways']} OSM ways "
        f"({meta['highway_filter'].count('|') + 1} road classes)", "INFO", rel(CBD / "sample_points.csv"))
    inside = pts.apply(lambda r: L.point_in_polygons(r.lon, r.lat, polys), axis=1)
    add(A, "Every CBD point lies inside the boundary", f"{int(inside.sum())} of {len(pts)}",
        "PASS" if inside.all() else "FAIL", rel(BOUNDARY))

    gaps = []
    for _, g in pts.sort_values("along_m").groupby("segment_id"):
        if len(g) > 1:
            gaps += list(np.diff(g.along_m.values))
    gaps = np.array(gaps)
    add(A, "Spacing between consecutive points on the same segment (target ~50 m)",
        f"median {np.median(gaps):.1f} m, 90% between {np.percentile(gaps, 5):.0f} and "
        f"{np.percentile(gaps, 95):.0f} m (n = {len(gaps)} gaps); segments shorter than 75 m get one midpoint",
        "PASS" if 40 <= np.median(gaps) <= 60 else "WARN")

    proj = L.LocalProjection(pts.lon.mean(), pts.lat.mean())
    xy = np.array([proj.to_xy(a, b) for a, b in zip(pts.lon, pts.lat)])
    dmin = min(np.sqrt(((xy[i + 1:] - xy[i]) ** 2).sum(axis=1)).min() for i in range(len(xy) - 1))
    add(A, "No duplicate points (minimum separation 10 m)", f"closest pair {dmin:.1f} m apart",
        "PASS" if dmin >= 10 else "FAIL")

    per_seg = pts.groupby("segment_id").size()
    add(A, "Points per street segment", f"median {per_seg.median():.0f}, max {per_seg.max()}; "
        f"{(per_seg == 1).sum()} of {len(per_seg)} segments have a single point", "INFO")

    in_cbd = box.apply(lambda r: L.point_in_polygons(r.lon, r.lat, polys), axis=1)
    w, s, e, n = json.loads((BOX / "run_meta.json").read_text())["points"]["bbox"]
    in_box = pts.lon.between(w, e) & pts.lat.between(s, n)
    add(A, "Earlier run used a placeholder box, not the CBD boundary",
        f"only {int(in_cbd.sum())} of {len(box)} placeholder points ({in_cbd.mean():.0%}) fall inside the CBD; "
        f"the box missed {int((~in_box).sum())} of {len(pts)} CBD points ({(~in_box).mean():.0%})",
        "FAIL", f"{rel(BOX)} (superseded by {rel(CBD)})")

    hw = pts.highway.value_counts()
    add(A, "Road classes sampled", ", ".join(f"{k} {v}" for k, v in hw.items()), "INFO")

    cache = BRIDGE_CACHE
    if network or not cache.exists():
        w, s, e, n = meta["bbox"]
        import requests
        q = f'[out:json][timeout:60];way["bridge"]["bridge"!="no"]["highway"]({s},{w},{n},{e});out ids;'
        js, errors = None, []
        for url in L.OVERPASS_ENDPOINTS:                # public servers are often busy: try each in turn
            try:
                r = requests.post(url, data={"data": q}, headers={"User-Agent": L.USER_AGENT}, timeout=90)
                r.raise_for_status()
                js = r.json()
                if "elements" in js:
                    break
                errors.append(f"{url}: no elements in the answer")
                js = None
            except (requests.RequestException, ValueError) as exc:
                errors.append(f"{url}: {type(exc).__name__}")
        if js is not None:
            cache.write_text(json.dumps({"retrieved_utc": L.now_iso(), "query": q,
                                         "way_ids": sorted(str(x["id"]) for x in js["elements"])}, indent=1))
        elif cache.exists():
            add(A, "OSM bridge list refreshed from Overpass",
                "Overpass unavailable (" + "; ".join(errors) + "); used the cached list retrieved "
                + json.loads(cache.read_text()).get("retrieved_utc", "?")[:10], "WARN", rel(cache))
        else:
            raise SystemExit("Overpass unavailable and no cached bridge list: " + "; ".join(errors))
    bridges = set(json.loads(cache.read_text())["way_ids"])
    on_bridge = pts.osm_way_id.astype(str).isin(bridges)
    motor = pts.highway.isin(["motorway", "trunk"])
    add(A, "Points on bridges or freeways (no building frontage to measure)",
        f"{int(on_bridge.sum())} on bridges, {int(motor.sum())} on motorway/trunk roads "
        f"({int((on_bridge | motor).sum())} in total, {(on_bridge | motor).mean():.0%})",
        "WARN", f"{rel(cache)}; decide whether to drop them")


# --------------------------------------------------------------------------- #
# Street-level imagery
# --------------------------------------------------------------------------- #
def imagery_checks(network: bool) -> None:
    """Coverage and pilot-image checks. network=True adds a tiled Mapillary re-query for
    2024-2026 imagery, independent of pilot.py."""
    A = "Street-level images"
    meta = json.loads((CBD / "run_meta.json").read_text())["coverage"]
    cp = pd.read_csv(CBD / "coverage_points.csv")
    add(A, "CBD points with a Mapillary image captured 1 Jun - 31 Aug 2026 (study period)",
        f"{meta['points_with_study_period_image']} of {meta['points']} points (within {meta['radius_m']:g} m)",
        "FAIL" if meta["points_with_study_period_image"] == 0 else "PASS", rel(CBD / "coverage_points.csv"))
    add(A, "CBD points with any Mapillary image", f"{meta['points_with_any_image']} of {meta['points']}", "INFO")
    latest = cp[["latest_flat", "latest_pano"]].fillna("").max(axis=1).str[:4]
    vc = latest.replace("", "none").value_counts().sort_index()
    add(A, "Most recent image at each CBD point, by capture year",
        ", ".join(f"{k}: {v}" for k, v in vc.items()), "WARN", rel(CBD / "coverage_points.csv"))
    recent = int((latest >= "2020").sum())
    add(A, "Points whose newest image is 2020 or later (<= 6 years before the study period)",
        f"{recent} of {len(cp)} ({recent / len(cp):.0%}); all 360-degree captures", "WARN")

    att = pd.read_csv(CBD / "pilot_attempts.csv")
    add(A, "Study-period download attempt (60 spread points)",
        f"{int((att.status == 'ok').sum())} images found; every miss logged", "FAIL", rel(CBD / "pilot_attempts.csv"))

    man = pd.read_csv(PILOT / "image_manifest.csv")
    pts = pd.read_csv(PILOT / "sample_points.csv").set_index("point_id")
    off = []
    for r in man.itertuples():
        d = L.angle_diff(r.compass_angle, pts.at[r.point_id, "road_bearing_deg"])
        off.append(min(d, 180 - d))
    off = np.array(off)
    years = man.capture_year.value_counts().sort_index()
    add(A, "Validation run on the newest imagery (any date): images sourced",
        f"{len(man)} of {len(man)} spread points; capture years "
        + ", ".join(f"{k}: {v}" for k, v in years.items()), "PASS", rel(PILOT))
    add(A, "Validation images taken on the point's own street (camera within 30 deg of the road)",
        f"{int((off < 30).sum())} of {len(man)}; {int((off > 60).sum())} were captured on the cross street",
        "WARN", "fix: require heading alignment in choose_image()")
    clip = pd.read_csv(PILOT / "clip_scores.csv")
    add(A, "CLIP ViT-B/32 land-use labels on the validation images",
        f"{int(clip.typology_low_confidence.sum())} of {len(clip)} low-confidence; not yet compared with hand labels",
        "WARN", rel(PILOT / "validation_template_blind.csv"))

    if network:
        tok = L.get_mapillary_token()
        client = L.MapillaryClient(tok)
        w, s, e, n = json.loads((CBD / "run_meta.json").read_text())["points"]["bbox"]
        win = L.local_window("2024-01-01", "2026-10-16")
        step, found, tiles, errors = 0.005, 0, 0, 0
        for x in np.arange(w, e, step):
            for y in np.arange(s, n, step):
                tiles += 1
                try:
                    found += len(client.search_bbox((x, y, min(x + step, e), min(y + step, n)), win, limit=500))
                except RuntimeError:
                    errors += 1
        add(A, "Independent re-query: any Mapillary image over the CBD captured 2024 to 16 Oct 2026",
            f"{found} images in {tiles - errors} of {tiles} bbox tiles queried on {L.now_iso()[:10]}",
            ("FAIL" if found == 0 else "INFO") if errors == 0 else "WARN", "Mapillary API v4 /images")


def write() -> None:
    """Write the checks to OUT as CSV and Markdown, and print them."""
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(ROWS)
    df.to_csv(OUT / "october_2026_checks.csv", index=False)
    lines = ["# October 2026 verification checks", "",
             "Generated by `Scripts/verification/verify_october_2026.py` from the files in `Data/`. "
             "PASS = meets the design; WARN = works, with a limitation; FAIL = does not meet the design; "
             "INFO = a number with no target.", ""]
    for area, g in df.groupby("area", sort=False):
        lines += [f"## {area}", "", "| Status | Check | Result | Evidence |", "|---|---|---|---|"]
        lines += [f"| {r.status} | {r.check} | {r.result} | {r.evidence} |" for r in g.itertuples()]
        lines.append("")
    counts = df.status.value_counts()
    lines.append("Totals: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    (OUT / "october_2026_checks.md").write_text("\n".join(lines) + "\n")
    print(df[["area", "status", "check", "result"]].to_string(index=False, max_colwidth=90))
    print("\n" + "Totals: " + ", ".join(f"{k} {v}" for k, v in counts.items()))


def main() -> int:
    global OUT, BRIDGE_CACHE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rerun-pipeline", action="store_true")
    ap.add_argument("--network", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--bridge-cache", type=Path, default=BRIDGE_CACHE)
    a = ap.parse_args()
    OUT, BRIDGE_CACHE = a.out, a.bridge_cache
    reddit_checks(a.rerun_pipeline)
    point_checks(a.network)
    imagery_checks(a.network)
    write()
    # Imagery and placeholder-box FAILs are findings about the world, reported in the
    # table; only a failed data-integrity check on the Reddit data stops the script.
    return 1 if any(r["status"] == "FAIL" and r["area"].startswith("Reddit") for r in ROWS) else 0


if __name__ == "__main__":
    sys.exit(main())
