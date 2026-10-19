#!/usr/bin/env python3
"""
pilot.py  -  ComputerVisionSentinel-Prairie | October 2026 computer-vision pilot
======================================================================
A deliberately small end-to-end run of the work-plan pipeline on <= 10 Downtown images:

  points   1. sample points every ~50 m along OSM streets, clipped to the Downtown boundary
  images   2. pick a spatially spread set of points, pull ONE Mapillary image for each
  score    3. CLIP zero-shot: land-use typology + CPTED cue scores for each image
  reddit   4. link to Reddit (r/saskatoon, 1 Jun - 31 Aug 2026) and compare cue by cue
  report   5. write pilot_report.md, contact_sheet.jpg and a blind validation sheet

  python pilot.py check        # 1-minute pre-flight: token, Overpass, libraries, Reddit files
  python pilot.py coverage     # after `points`: which years of imagery exist at each point
  By default only images captured in the study period (1 Jun - 31 Aug 2026) are used, including
  360-degree panoramas cropped to side-on views. --any-date / --no-pano change that.
  python pilot.py all          # run everything
  python pilot.py <step>       # or one step at a time

This is a feasibility pilot, NOT a result: n <= 10 images cannot support any inference
about CPTED and crime/perception. It shows that every stage runs and joins.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_lib as L  # noqa: E402

DOWNTOWN = "Downtown / CBD"
STUDY_START, STUDY_END = "2026-06-01", "2026-08-31"          # work plan study period (local time)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def out_dir(a) -> Path:
    p = Path(a.out)
    p.mkdir(parents=True, exist_ok=True)
    return p


def update_meta(out: Path, key: str, value: dict) -> None:
    f = out / "run_meta.json"
    meta = json.loads(f.read_text()) if f.exists() else {}
    meta[key] = value
    meta["last_updated_utc"] = L.now_iso()
    meta["git_commit"] = L.git_commit()
    f.write_text(json.dumps(meta, indent=2, default=str))


def read_meta(out: Path) -> dict:
    f = out / "run_meta.json"
    return json.loads(f.read_text()) if f.exists() else {}


def lib_versions() -> dict:
    v = {"python": sys.version.split()[0]}
    for m in ("numpy", "pandas", "PIL", "requests", "torch", "transformers"):
        try:
            mod = __import__(m)
            v[m] = getattr(mod, "__version__", "?")
        except Exception:                                  # noqa: BLE001
            v[m] = "not installed"
    return v


def as_bool(s: pd.Series) -> pd.Series:
    return s.map(lambda v: str(v).strip().lower() in ("true", "1", "1.0", "yes"))


# --------------------------------------------------------------------------- #
# 1. points
# --------------------------------------------------------------------------- #
def cmd_points(a, session=None) -> pd.DataFrame:
    out = out_dir(a)
    polys, bbox, bsrc = L.load_boundary(a.boundary_geojson, a.boundary_name)
    if a.roads_geojson:
        ways, rsrc = L.load_roads_geojson(a.roads_geojson), a.roads_geojson
    else:
        ways, rsrc = L.fetch_roads_overpass(bbox, a.highways, session=session)
    segs = L.split_at_intersections(ways)
    pts = L.generate_points(segs, polys, a.step)
    if not pts:
        raise SystemExit("No sample points fell inside the boundary. Check --boundary-geojson / --boundary-name.")
    df = pd.DataFrame(pts)[["point_id", "lon", "lat", "segment_id", "osm_way_id", "road_name", "highway",
                            "along_m", "segment_len_m", "road_bearing_deg"]]
    df.to_csv(out / "sample_points.csv", index=False)
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
         "properties": {"point_id": r.point_id, "segment_id": r.segment_id, "road_name": r.road_name}}
        for r in df.itertuples()]}
    (out / "sample_points.geojson").write_text(json.dumps(gj))
    update_meta(out, "points", {
        "boundary_source": bsrc, "roads_source": rsrc, "highway_filter": a.highways, "step_m": a.step,
        "n_ways": len(ways), "n_street_segments": len(segs), "n_points": len(df),
        "n_segments_with_points": int(df.segment_id.nunique()), "bbox": bbox})
    print(f"[points] {len(df)} points on {df.segment_id.nunique()} street segments "
          f"(from {len(ways)} OSM ways). Boundary: {bsrc}")
    if not a.boundary_geojson:
        print("[points] WARNING: using the placeholder bounding box. Open sample_points.geojson in "
              "geojson.io / QGIS and confirm it covers Downtown before relying on it.")
    return df


# --------------------------------------------------------------------------- #
# 2. images
# --------------------------------------------------------------------------- #
def view_type(compass, road_bearing: float) -> tuple[float | None, str]:
    if compass is None or (isinstance(compass, float) and np.isnan(compass)):
        return None, "unknown"
    d = L.angle_diff(float(compass), float(road_bearing))
    d = min(d, 180 - d)                       # looking up- or down-road are equivalent
    return round(d, 1), ("along_road" if d < 30 else "side_on" if d > 60 else "oblique")


def cmd_images(a, client=None) -> pd.DataFrame:
    out = out_dir(a)
    pts = pd.read_csv(out / "sample_points.csv")
    client = client or L.MapillaryClient(L.get_mapillary_token())
    window = L.local_window(a.capture_start, a.capture_end)
    study = L.local_window(STUDY_START, STUDY_END)
    order = L.spread_order(pts.to_dict("records"))
    attempts, chosen = [], []
    for rank, idx in enumerate(order[: a.max_attempts], 1):
        p = pts.iloc[idx]
        row = {"rank": rank, "point_id": p.point_id, "lon": p.lon, "lat": p.lat}
        cands = client.search(p.lon, p.lat, a.radius, window)
        row["n_candidates"] = len(cands)
        c, reason = L.choose_image(cands, p.lon, p.lat, a.radius, window=window,
                                   allow_pano=a.allow_pano, prefer=a.prefer)
        row["status"] = reason
        if c is None:
            attempts.append(row)
            print(f"[images] #{rank:02d} {p.point_id}: no usable image ({reason})")
            continue
        fname = Path("images") / f"{p.point_id}_{c['id']}.jpg"
        alt = ""
        if c["_pano"]:
            # 360-degree image: cut two normal camera views facing each side of the street
            from PIL import Image
            raw = out / "images" / "pano_raw" / f"{c['id']}.jpg"
            if not raw.exists():
                client.download(c["_url"], raw)
            pano = Image.open(raw)
            heading = L.heading_of(c)
            right = (p.road_bearing_deg + 90 - heading) % 360
            left = (p.road_bearing_deg - 90 - heading) % 360
            L.equirect_to_perspective(pano, right, fov_deg=90).save(out / fname, quality=90)
            alt = str(Path("images") / f"{p.point_id}_{c['id']}_left.jpg")
            L.equirect_to_perspective(pano, left, fov_deg=90).save(out / alt, quality=90)
            vt_deg, vt = 90.0, "side_on_from_360"
        else:
            if not (out / fname).exists():
                client.download(c["_url"], out / fname)
            vt_deg, vt = view_type(L.heading_of(c), p.road_bearing_deg)
        q = L.image_quality(out / fname)
        rec = {"point_id": p.point_id, "segment_id": p.segment_id, "road_name": p.road_name,
               "image_id": c["id"], "image_file": str(fname), "captured_at": c["_dt"].isoformat(),
               "capture_year": c["_dt"].year, "summer_capture": bool(c["_summer"]),
               "in_study_period": bool(study[0] <= c["_dt"] <= study[1]), "is_pano": bool(c["_pano"]),
               "image_file_other_side": alt,
               "dist_to_point_m": round(c["_dist_m"], 1), "compass_angle": L.heading_of(c),
               "heading_vs_road_deg": vt_deg, "view_type": vt,
               "mapillary_url": f"https://www.mapillary.com/app/?pKey={c['id']}", **q}
        chosen.append(rec)
        row.update({"image_id": c["id"], "captured_at": rec["captured_at"], "dist_m": rec["dist_to_point_m"]})
        attempts.append(row)
        print(f"[images] #{rank:02d} {p.point_id}: {c['id']} ({rec['captured_at'][:10]}, "
              f"{rec['dist_to_point_m']} m, {vt}) {q['flags'] or 'ok'}")
        if len(chosen) >= a.n:
            break
    pd.DataFrame(attempts).to_csv(out / "pilot_attempts.csv", index=False)
    if not chosen:
        raise SystemExit("No usable Mapillary images at any attempted point"
                         + (f" captured {a.capture_start or '...'} to {a.capture_end or '...'}" if window else "")
                         + ". Run `pilot.py coverage` to see which years exist, try --allow-pano or a larger --radius.")
    man = pd.DataFrame(chosen)
    man.to_csv(out / "image_manifest.csv", index=False)
    n_ok = sum(1 for r in attempts if r["status"] == "ok")
    update_meta(out, "images", {
        "selection_rule": ("points ordered by deterministic farthest-point spread (start nearest centroid); "
                           "first N with a usable image kept; per point: within radius"
                           + (f", captured {a.capture_start or '...'} to {a.capture_end or '...'}" if window else "")
                           + ("; 360-degree panoramas allowed and cropped to two side-on views" if a.allow_pano else "; no panoramas")
                           + ("; ranked most recent year > Jun-Aug > flat > nearest" if a.prefer == "recent"
                              else "; ranked Jun-Aug > most recent year > flat > nearest")),
        "capture_window": [a.capture_start, a.capture_end] if window else None,
        "in_study_period": int(man.in_study_period.sum()), "panoramas_used": int(man.is_pano.sum()),
        "radius_m": a.radius, "target_n": a.n, "points_attempted": len(attempts), "points_with_image": n_ok,
        "hit_rate": round(n_ok / len(attempts), 3), "n_images": len(man),
        "summer_captures": int(man.summer_capture.sum()),
        "capture_years": {int(k): int(v) for k, v in man.capture_year.value_counts().sort_index().items()},
        "mapillary_license": "CC BY-SA 4.0 (attribute Mapillary and contributors; share-alike on derivatives)"})
    print(f"[images] kept {len(man)} images from {len(attempts)} attempted points "
          f"(hit rate {n_ok}/{len(attempts)})")
    return man


# --------------------------------------------------------------------------- #
# 2b. coverage: what imagery exists, by year, at every sample point
# --------------------------------------------------------------------------- #
def _tiles(bbox, step):
    w, s_, e, n = bbox
    x = w
    while x < e:
        y = s_
        while y < n:
            yield (x, y, min(x + step, e), min(y + step, n))
            y += step
        x += step


def _fetch_all(client, box, window, depth=0) -> list[dict]:
    res = client.search_bbox(box, window, limit=L.MAPILLARY_MAX_LIMIT)
    if len(res) >= L.MAPILLARY_MAX_LIMIT and depth < 6:      # capped: split into quarters
        w, s_, e, n = box
        mx, my = (w + e) / 2, (s_ + n) / 2
        res = []
        for q in ((w, s_, mx, my), (mx, s_, e, my), (w, my, mx, n), (mx, my, e, n)):
            res += _fetch_all(client, q, window, depth + 1)
    return res


def cmd_coverage(a, client=None) -> pd.DataFrame:
    """For every sample point: which capture years (flat / 360-degree) exist within --radius.
    Answers 'is there summer-2026 imagery?' for the whole study area, not just 10 points."""
    out = out_dir(a)
    pts = pd.read_csv(out / "sample_points.csv")
    client = client or L.MapillaryClient(L.get_mapillary_token())
    pad = a.radius / 111320.0 * 2
    bbox = (pts.lon.min() - pad, pts.lat.min() - pad, pts.lon.max() + pad, pts.lat.max() + pad)
    years = list(range(a.coverage_from_year, 2027))
    windows = [("before", L.local_window("2000-01-01", f"{years[0] - 1}-12-31"))] + \
              [(str(y), L.local_window(f"{y}-01-01", f"{y}-12-31")) for y in years]
    imgs, n_req = {}, 0
    for label, win in windows:
        before = len(imgs)
        for t in _tiles(bbox, 0.004):
            for c in _fetch_all(client, t, win):
                n_req += 1
                ll, dt = L.image_lonlat(c), L.parse_captured_at(c.get("captured_at"))
                if ll and dt:
                    imgs[c["id"]] = {"image_id": c["id"], "lon": ll[0], "lat": ll[1], "captured_at": dt,
                                     "is_pano": bool(c.get("is_pano"))}
        print(f"[coverage] {label}: {len(imgs) - before} images")
    study = L.local_window(STUDY_START, STUDY_END)
    im = pd.DataFrame(imgs.values())
    if im.empty:
        raise SystemExit("[coverage] No Mapillary images at all in the study area.")
    loc = im.captured_at.map(lambda d: d.astimezone(__import__("zoneinfo").ZoneInfo(L.LOCAL_TZ)))
    im["year"], im["month"] = loc.map(lambda d: d.year), loc.map(lambda d: d.month)
    im["capture_date"] = loc.map(lambda d: d.date().isoformat())
    im["in_study_period"] = im.captured_at.map(lambda d: study[0] <= d <= study[1])
    # nearest-point assignment within radius
    proj = L.LocalProjection(pts.lon.mean(), pts.lat.mean())
    pxy = np.array([proj.to_xy(x, y) for x, y in zip(pts.lon, pts.lat)])
    ixy = np.array([proj.to_xy(x, y) for x, y in zip(im.lon, im.lat)])
    rows = []
    for k, r in enumerate(pts.itertuples()):
        near = im[np.hypot(*(ixy - pxy[k]).T) <= a.radius]
        flat, pano = near[~near.is_pano], near[near.is_pano]
        rows.append({"point_id": r.point_id, "n_images": len(near),
                     "latest_flat": flat.capture_date.max() if len(flat) else "",
                     "latest_pano": pano.capture_date.max() if len(pano) else "",
                     "study_period_flat": int(flat.in_study_period.sum()),
                     "study_period_pano": int(pano.in_study_period.sum()),
                     "years_flat": ";".join(map(str, sorted(flat.year.unique()))),
                     "years_pano": ";".join(map(str, sorted(pano.year.unique())))})
    cp = pd.DataFrame(rows)
    cp.to_csv(out / "coverage_points.csv", index=False)
    im.drop(columns=["captured_at"]).to_csv(out / "coverage_images.csv", index=False)
    by = []
    for y in sorted(im.year.unique()):
        yi = im[im.year == y]
        by.append({"year": int(y), "images_flat": int((~yi.is_pano).sum()), "images_360": int(yi.is_pano.sum()),
                   "points_with_flat": int(cp.years_flat.str.split(";").map(lambda v: str(y) in v).sum()),
                   "points_with_360": int(cp.years_pano.str.split(";").map(lambda v: str(y) in v).sum())})
    byy = pd.DataFrame(by)
    byy.to_csv(out / "coverage_by_year.csv", index=False)
    n = len(cp)
    sp_any = int(((cp.study_period_flat + cp.study_period_pano) > 0).sum())
    sp_flat = int((cp.study_period_flat > 0).sum())
    any_img = int((cp.n_images > 0).sum())
    update_meta(out, "coverage", {"radius_m": a.radius, "points": n, "points_with_any_image": any_img,
                                  "points_with_study_period_image": sp_any, "points_with_study_period_flat": sp_flat,
                                  "images_found": len(im), "years_checked": f"<= {years[-1]}",
                                  "by_year": by})
    print(byy.to_string(index=False))
    print(f"[coverage] {any_img} of {n} points have any image within {a.radius:g} m; "
          f"{sp_any} have a Jun-Aug 2026 image ({sp_flat} flat, the rest 360-degree only).")
    return cp


# --------------------------------------------------------------------------- #
# 3. score (CLIP)
# --------------------------------------------------------------------------- #
def cmd_score(a, encoder=None) -> pd.DataFrame:
    from PIL import Image
    out = out_dir(a)
    man = pd.read_csv(out / "image_manifest.csv")
    prompts = L.load_prompts()
    encoder = encoder or L.ClipEncoder(a.clip_model)
    scorer = L.ClipScorer(encoder, prompts, views=a.views)
    scorer.prepare()
    rows = []
    for r in man.itertuples():
        im = Image.open(out / r.image_file).convert("RGB")
        rows.append({"point_id": r.point_id, "image_id": r.image_id, **scorer.score(im)})
        print(f"[score] {r.point_id}: {rows[-1]['typology_top1']} ({rows[-1]['typology_top1_prob']:.2f})"
              + ("  [low confidence]" if rows[-1]["typology_low_confidence"] else ""))
    df = pd.DataFrame(rows)
    df.to_csv(out / "clip_scores.csv", index=False)
    update_meta(out, "score", {"model": getattr(encoder, "model_name", "injected"),
                               "device": getattr(encoder, "device", "n/a"), "views_per_image": a.views,
                               "prompts_file": "Scripts/cv_pilot/clip_prompts.json",
                               "libs": lib_versions(),
                               "caveat": "uncalibrated zero-shot probabilities; not validated; n<=10"})
    return df


# --------------------------------------------------------------------------- #
# 4. reddit
# --------------------------------------------------------------------------- #
def find_reddit_dir(given: str | None) -> Path:
    if given:
        return Path(given)
    d = L.REPO_ROOT / "Data" / "reddit_2026-06-01_2026-08-31"
    if not d.exists():
        raise SystemExit("Could not find Data/reddit_2026-06-01_2026-08-31. Pass --reddit-dir.")
    return d


def load_reddit(reddit_dir: Path) -> tuple[pd.DataFrame, dict]:
    """One row per record (posts + comments POSTED INSIDE the study window), validated tags."""
    d = reddit_dir / "04_cleaned_datasets"
    pf, cf = sorted(d.glob("*posts*CLEANED_v2.csv")), sorted(d.glob("*comments*CLEANED_v2.csv"))
    if not pf or not cf:
        raise SystemExit(f"Cleaned v2 posts/comments CSVs not found in {d}")
    posts, comments = pd.read_csv(pf[-1]), pd.read_csv(cf[-1])
    n_comments_all = len(comments)
    comments = comments[as_bool(comments["comment_in_window"])]
    keep = ["cleaned_text", "sentiment_adj_compound", "sentiment_adj_category", "vloc_downtown_cbd",
            "venv_lighting", "venv_people", "thread_id", "local_date"]
    p = posts[keep].assign(record_type="post", record_id=posts["id"])
    c = comments[keep].assign(record_type="comment", record_id=comments["comment_id"])
    recs = pd.concat([p, c], ignore_index=True)
    recs["cleaned_text"] = recs["cleaned_text"].fillna("").astype(str)
    for col in ("vloc_downtown_cbd", "venv_lighting", "venv_people"):
        recs[col] = as_bool(recs[col])
    info = {"posts_file": pf[-1].name, "comments_file": cf[-1].name, "n_posts": len(posts),
            "n_comments_total": n_comments_all, "n_comments_in_window": len(comments)}
    return recs, info


def rate_row(k: int, n: int) -> dict:
    lo, hi = L.wilson(k, n)
    return {"k": k, "n": n, "per_100": round(100 * k / n, 1) if n else np.nan,
            "ci95_low": round(100 * lo, 1), "ci95_high": round(100 * hi, 1)}


def downtown_summary(recs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, df in (("Downtown / CBD (validated tag)", recs[recs.vloc_downtown_cbd]),
                     ("Rest of study corpus", recs[~recs.vloc_downtown_cbd]),
                     ("All records", recs)):
        s = df.sentiment_adj_compound
        m, se = s.mean(), (s.std(ddof=1) / np.sqrt(len(s)) if len(s) > 1 else np.nan)
        neg = int((df.sentiment_adj_category == "negative").sum())
        lo, hi = L.wilson(neg, len(df))
        rows.append({"group": name, "n_posts": int((df.record_type == "post").sum()),
                     "n_comments": int((df.record_type == "comment").sum()), "n_records": len(df),
                     "n_threads": int(df.thread_id.nunique()), "mean_sentiment_adj": round(m, 3),
                     "mean_ci95_low": round(m - 1.96 * se, 3), "mean_ci95_high": round(m + 1.96 * se, 3),
                     "n_negative": neg, "pct_negative": round(100 * neg / len(df), 1),
                     "pct_neg_ci95_low": round(100 * lo, 1), "pct_neg_ci95_high": round(100 * hi, 1)})
    return pd.DataFrame(rows)


def cue_flags(recs: pd.DataFrame, lex: dict) -> tuple[pd.DataFrame, dict]:
    flags, rx = pd.DataFrame(index=recs.index), {}
    for k, v in lex["audited_cues"].items():
        flags[k] = recs[v["column"]]
    for k, v in lex["physical_cues"].items():
        rx[k] = re.compile(r"\b(?:" + v["pattern"] + r")\b", re.I)
        flags[k] = recs.cleaned_text.map(lambda t, r=rx[k]: bool(r.search(t)))
    return flags, rx


def audited_precision(reddit_dir: Path) -> dict:
    f = reddit_dir / "05_audits" / "env_cue_precision_heldout.csv"
    if not f.exists():
        return {}
    d = pd.read_csv(f)
    return {r.cue: (round(r.precision, 2), int(r.n_correct), int(r.n_judged)) for r in d.itertuples()}


def anchors_table(recs: pd.DataFrame, lex: dict) -> pd.DataFrame:
    rows = []
    for name, pat in lex["place_anchors"].items():
        r = re.compile(pat, re.I)
        hit = recs.cleaned_text.map(lambda t: bool(r.search(t)))
        rows.append({"anchor": name, "records_all": int(hit.sum()),
                     "records_in_downtown_tagged": int((hit & recs.vloc_downtown_cbd).sum())})
    return pd.DataFrame(rows).sort_values("records_all", ascending=False)


def cue_samples(recs, flags, rx, n=8) -> pd.DataFrame:
    """A few matched snippets per EXPLORATORY cue so precision can be hand-checked quickly.
    Local audit file only: do not quote these in any report/paper (ethics note in the scraper)."""
    rows = []
    for k, r in rx.items():
        idx = list(flags.index[flags[k] & recs.vloc_downtown_cbd])
        if len(idx) > n:
            idx = list(pd.Series(idx).sample(n, random_state=0))
        for i in idx:
            t = recs.at[i, "cleaned_text"]
            m = r.search(t)
            s = max(0, m.start() - 90) if m else 0
            rows.append({"cue": k, "record_id": recs.at[i, "record_id"], "snippet": t[s:s + 220],
                         "judge_is_true_cue_0_or_1": ""})
    return pd.DataFrame(rows, columns=["cue", "record_id", "snippet", "judge_is_true_cue_0_or_1"])


def clip_side(clip: pd.DataFrame | None, targets: list[str]) -> tuple[str, float]:
    if not targets:
        return "n/a (lighting comes from the detector step, Nov)", np.nan
    parts, vals = [], []
    for t in targets:
        if t.startswith("typ_"):
            lab = t[4:]
            parts.append(f"share of images typed '{lab}'")
            if clip is not None:
                vals.append(float((clip.typology_top1 == lab).mean()))
        else:
            parts.append(f"mean {t}_mean")
            if clip is not None:
                vals.append(float(clip[f"{t}_mean"].mean()))
    return " & ".join(parts), (round(float(np.mean(vals)), 3) if vals else np.nan)


def cmd_reddit(a) -> dict:
    out = out_dir(a)
    rd = find_reddit_dir(a.reddit_dir)
    recs, info = load_reddit(rd)
    lex = json.loads((Path(__file__).resolve().parent / "reddit_lexicon.json").read_text())
    clip = pd.read_csv(out / "clip_scores.csv") if (out / "clip_scores.csv").exists() else None

    summ = downtown_summary(recs)
    summ.to_csv(out / "reddit_downtown_summary.csv", index=False)

    flags, rx = cue_flags(recs, lex)
    prec = audited_precision(rd)
    dt = recs.vloc_downtown_cbd
    rows = []
    for k in flags.columns:
        spec = lex["physical_cues"].get(k) or lex["audited_cues"].get(k)
        a1 = rate_row(int(flags.loc[dt, k].sum()), int(dt.sum()))
        a0 = rate_row(int(flags.loc[~dt, k].sum()), int((~dt).sum()))
        measure, val = clip_side(clip, spec["compare_with"])
        p = prec.get(k)
        rows.append({"reddit_cue": k,
                     "cue_status": "audited" if k in lex["audited_cues"] else "exploratory (precision unchecked)",
                     "heldout_precision": f"{p[0]} ({p[1]}/{p[2]})" if p else "",
                     "downtown_k": a1["k"], "downtown_n": a1["n"], "downtown_per_100": a1["per_100"],
                     "downtown_ci95": f"{a1['ci95_low']}-{a1['ci95_high']}", "rest_per_100": a0["per_100"],
                     "rest_ci95": f"{a0['ci95_low']}-{a0['ci95_high']}",
                     "clip_measure_on_pilot_images": measure, "clip_value": val})
    cmp_df = pd.DataFrame(rows)
    cmp_df.to_csv(out / "reddit_cue_comparison.csv", index=False)
    anchors = anchors_table(recs, lex)
    anchors.to_csv(out / "reddit_place_anchors.csv", index=False)
    audit_dir = out / "_local_audit_do_not_share"
    audit_dir.mkdir(exist_ok=True)
    cue_samples(recs, flags, rx).to_csv(audit_dir / "reddit_cue_samples_for_precision_check.csv", index=False)

    # per-point join table. Reddit only resolves to the neighbourhood, so every pilot
    # point inherits the same Downtown values (this IS the finding, see anchors table).
    jn = None
    man_f = out / "image_manifest.csv"
    if man_f.exists():
        man = pd.read_csv(man_f)
        d0 = summ.iloc[0]
        jn = man[["point_id", "segment_id", "image_id"]].copy()
        jn["reddit_join_level"] = f"neighbourhood: {DOWNTOWN}"
        jn["reddit_n_records"] = int(d0.n_records)
        jn["reddit_mean_sentiment_adj"] = d0.mean_sentiment_adj
        jn["reddit_pct_negative"] = d0.pct_negative
        if clip is not None:
            jn = jn.merge(clip[["point_id", "typology_top1", "typology_top1_prob"]], on="point_id", how="left")
        jn.to_csv(out / "reddit_join.csv", index=False)
    update_meta(out, "reddit", {**info, "reddit_dir": str(rd.relative_to(L.REPO_ROOT)) if rd.is_relative_to(L.REPO_ROOT) else str(rd),
                                "window": "2026-06-01..2026-08-31 (America/Regina)",
                                "downtown_definition": "vloc_downtown_cbd (hand-validated tag; other-city mentions removed)",
                                "n_downtown_records": int(dt.sum())})
    print(f"[reddit] Downtown/CBD: {int(dt.sum())} records ({int((recs[dt].record_type == 'post').sum())} posts); "
          f"mean sentiment {summ.iloc[0].mean_sentiment_adj}, {summ.iloc[0].pct_negative}% negative")
    return {"summary": summ, "cues": cmp_df, "anchors": anchors, "join": jn}


# --------------------------------------------------------------------------- #
# 5. report
# --------------------------------------------------------------------------- #
def contact_sheet(out: Path, man: pd.DataFrame, clip: pd.DataFrame | None, cols: int = 5, w: int = 384) -> Path:
    from PIL import Image, ImageDraw
    tiles = []
    for r in man.itertuples():
        im = Image.open(out / r.image_file).convert("RGB")
        im = im.resize((w, int(w * im.height / im.width)))
        cap_h = 34
        t = Image.new("RGB", (w, im.height + cap_h), "white")
        t.paste(im, (0, 0))
        typ = ""
        if clip is not None and (clip.point_id == r.point_id).any():
            typ = clip[clip.point_id == r.point_id].typology_top1.iloc[0]
        d = ImageDraw.Draw(t)
        d.text((4, im.height + 3), f"{r.point_id} | {str(r.captured_at)[:10]} | {typ}", fill="black")
        d.text((4, im.height + 18), "Imagery: Mapillary, CC BY-SA 4.0", fill="gray")
        tiles.append(t)
    cols = min(cols, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    th = max(t.height for t in tiles)
    sheet = Image.new("RGB", (cols * w, rows * th), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * w, (i // cols) * th))
    p = out / "contact_sheet.jpg"
    sheet.save(p, quality=88)
    return p


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else str(v) for v in r) + " |")
    return "\n".join(lines)


def cmd_report(a) -> Path:
    out = out_dir(a)
    meta = read_meta(out)
    man = pd.read_csv(out / "image_manifest.csv")
    clip = pd.read_csv(out / "clip_scores.csv") if (out / "clip_scores.csv").exists() else None
    sheet = contact_sheet(out, man, clip)
    att = pd.read_csv(out / "pilot_attempts.csv")
    pm, im_ = meta.get("points", {}), meta.get("images", {})
    rd = lambda f: pd.read_csv(out / f) if (out / f).exists() else None  # noqa: E731
    summ, cues, anchors = rd("reddit_downtown_summary.csv"), rd("reddit_cue_comparison.csv"), rd("reddit_place_anchors.csv")

    # blind validation sheet (no CLIP columns, so the labeller is not anchored)
    val = man[["image_id", "point_id", "image_file"]].copy()
    for c in ["human_typology", "human_graffiti_0_1", "human_litter_0_1", "human_boarded_windows_0_1",
              "human_vacant_lot_0_1", "human_active_storefront_0_1", "human_windows_overlook_0_1",
              "human_people_present_0_1", "human_fences_0_1", "human_seating_0_1",
              "human_streetlight_visible_0_1", "human_notes"]:
        val[c] = ""
    val.to_csv(out / "validation_template_blind.csv", index=False)

    R = []
    A = R.append
    A("# October 2026 pilot: street-level imagery -> CPTED cues -> Reddit\n")
    A(f"*Generated {L.now_iso()} (git `{meta.get('git_commit', 'n/a')}`). Every number is read from the pilot's output files.*\n")
    A(f"> **Status: feasibility pilot, not a result.** With {len(man)} images no association between built environment, "
      "crime or perception can be estimated. The pilot shows that each stage of the work-plan pipeline runs and joins.\n")
    A("## 1. What was run\n")
    A(f"* **Sample points:** {pm.get('n_points', '?')} points about {pm.get('step_m', 50):g} m apart on "
      f"{pm.get('n_segments_with_points', '?')} street segments (OSM ways split at intersections).")
    A(f"* **Boundary:** {pm.get('boundary_source', '?')}.")
    A(f"* **Pilot sample:** {im_.get('selection_rule', '')}.")
    A(f"* **Imagery:** Mapillary, CC BY-SA 4.0; max {im_.get('radius_m', '?')} m from the point.")
    s = meta.get("score", {})
    if s:
        A(f"* **CLIP:** `{s.get('model')}` on {s.get('device')}, {s.get('views_per_image')} square views per image; "
          "prompts in `Scripts/cv_pilot/clip_prompts.json`.")
    A("")
    A("## 2. Coverage and image dates\n")
    n_ok = int((att.status == "ok").sum())
    years = {int(k): int(v) for k, v in man.capture_year.value_counts().sort_index().items()}
    A(f"Of {len(att)} points attempted (in spread order), **{n_ok} had a usable image** ({100 * n_ok / len(att):.0f}%). "
      f"Capture years of the {len(man)} kept images: {years}; **{int(man.summer_capture.sum())} of {len(man)} are Jun-Aug captures.**\n")
    A(f"**Temporal mismatch to disclose:** crime and Reddit cover Jun-Aug 2026; the imagery was captured on the dates above "
      f"({int((man.capture_year < 2024).sum())} of {len(man)} before 2024). It describes the *typical built form*, not the street in summer 2026.\n")
    A("View direction relative to the street: " + ", ".join(f"{k}={v}" for k, v in man.view_type.value_counts().items()) +
      ". Side-on views show frontages (better for natural surveillance); along-road views mostly show carriageway. "
      "Quality flags (provisional thresholds): " +
      ", ".join(f"{k}={v}" for k, v in man["flags"].fillna("").replace("", "ok").value_counts().items()) + ".\n")
    cov = meta.get("coverage")
    if cov:
        A("### What imagery exists across all sample points\n")
        A(md_table(pd.DataFrame(cov["by_year"])))
        A(f"\n{cov['points_with_any_image']} of {cov['points']} points have any image within {cov['radius_m']:g} m; "
          f"**{cov['points_with_study_period_image']} have an image from the study period (Jun-Aug 2026)**, "
          f"{cov['points_with_study_period_flat']} of them a flat (non-360) image.\n")
    if "in_study_period" in man.columns:
        A(f"Pilot images captured inside the study period (Jun-Aug 2026): **{int(man.in_study_period.sum())} of {len(man)}**"
          + (f"; {int(man.is_pano.sum())} cut from 360-degree panoramas (side-on views)." if "is_pano" in man.columns else ".") + "\n")
    A(f"![contact sheet]({sheet.name})\n")
    if clip is not None:
        A("## 3. What CLIP says about the images\n")
        t = man[["point_id", "road_name", "captured_at"]].assign(captured_at=man.captured_at.astype(str).str[:10]).merge(
            clip[["point_id", "typology_top1", "typology_top1_prob", "typology_margin", "typology_low_confidence"]], on="point_id")
        A(md_table(t))
        cuecols = [c for c in clip.columns if c.startswith("cue_") and c.endswith("_mean")]
        A("\nCPTED cue scores (mean P(cue present) across the image's views; uncalibrated):\n")
        c = clip[["point_id"] + cuecols].copy()
        c.columns = ["point_id"] + [x[4:-5] for x in cuecols]
        A(md_table(c.round(2)))
        A(f"\nLow-confidence typology calls: {int(clip.typology_low_confidence.sum())} of {len(clip)}. "
          "Nothing here is validated until compared with hand labels (`validation_template_blind.csv` is the blank sheet for these images).\n")
    if summ is not None:
        A("## 4. The Reddit side (r/saskatoon, 1 Jun - 31 Aug 2026)\n")
        A(md_table(summ))
        A("\nDowntown / CBD = hand-validated location tag (other-city mentions such as \"downtown Regina\" removed); adjusted VADER sentiment. "
          "These figures reproduce the Downtown row of the existing `neighbourhood_summary.csv`.\n")
    if cues is not None:
        A("### Cue by cue: what the images show vs what Reddit says\n")
        A(md_table(cues[["reddit_cue", "cue_status", "heldout_precision", "downtown_k", "downtown_n", "downtown_per_100",
                         "downtown_ci95", "rest_per_100", "clip_measure_on_pilot_images", "clip_value"]]))
        A("\nA **template for the full comparison, not evidence**: images <= 10, Reddit cue counts are small, exploratory cues are unchecked, "
          "and the audited `lighting` cue has about 50% precision (it fires on traffic lights), so it cannot yet support H3.\n")
    if anchors is not None:
        A("### How finely can Reddit be located?\n")
        A(md_table(anchors.head(8)))
        A("\nStreet and landmark mentions number in the single digits to low tens. Reddit joins to **neighbourhood or zone**, "
          "not to individual 50 m segments; this needs a decision (see README).\n")
    A("## 5. Limitations\n")
    for t in ["n <= 10 images: no inference. Hit rate and image dates are the useful pilot outputs.",
              "Daytime imagery shows lighting infrastructure, not how well lit a place is at night.",
              "CLIP cues are uncalibrated zero-shot scores, not yet validated; CLIP is not used for streetlights (detector step).",
              "Image capture dates differ from the study period (section 2).",
              "Reddit users are not the population of Saskatoon, and the corpus is built from seed-term searches: it describes how safety is talked about, not how safe places are.",
              "The study describes places; it does not predict crime or label communities."]:
        A(f"* {t}")
    A("\n## 6. Attribution\n")
    A("Street-level imagery: Mapillary contributors, CC BY-SA 4.0 (https://www.mapillary.com). Figures that reproduce these images "
      "must credit Mapillary and keep the licence. No Reddit text is quoted in this report.\n")
    rp = out / "pilot_report.md"
    rp.write_text("\n".join(R))
    update_meta(out, "report", {"file": rp.name})
    print(f"[report] wrote {rp}")
    return rp


# --------------------------------------------------------------------------- #
# check / CLI
# --------------------------------------------------------------------------- #
def cmd_check(a) -> int:
    ok = True

    def line(name, passed, msg=""):
        nonlocal ok
        ok &= bool(passed)
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f": {msg}" if msg else ""))

    print("Pre-flight check")
    for m in ("numpy", "pandas", "PIL", "requests", "torch", "transformers"):
        try:
            __import__(m)
            line(f"import {m}", True)
        except Exception as e:                              # noqa: BLE001
            line(f"import {m}", False, str(e) + (" (CLIP step only)" if m in ("torch", "transformers") else ""))
    try:
        recs, _ = load_reddit(find_reddit_dir(a.reddit_dir))
        line("Reddit cleaned files", True, f"{len(recs)} records in window, {int(recs.vloc_downtown_cbd.sum())} Downtown")
    except SystemExit as e:
        line("Reddit cleaned files", False, str(e))
    try:
        n = len(L.MapillaryClient(L.get_mapillary_token()).search(-106.6600, 52.1290, 60))
        line("Mapillary token + search", True, f"{n} image records within ~60 m of a Downtown test point")
    except SystemExit as e:
        line("Mapillary token", False, str(e).splitlines()[0])
    except Exception as e:                                  # noqa: BLE001
        line("Mapillary search", False, str(e)[:160])
    try:
        ways, url = L.fetch_roads_overpass((-106.662, 52.128, -106.658, 52.130))
        line("Overpass (OSM roads)", True, f"{len(ways)} ways via {url}")
    except Exception as e:                                  # noqa: BLE001
        line("Overpass (OSM roads)", False, str(e)[:160])
    print("All checks passed." if ok else "Some checks failed: fix them before `pilot.py all`.")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("step", choices=["check", "points", "coverage", "images", "score", "reddit", "report", "all"])
    p.add_argument("--out", default=str(L.DEFAULT_OUT), help="output folder")
    p.add_argument("--boundary-geojson",
                   default=str(L.DEFAULT_BOUNDARY) if L.DEFAULT_BOUNDARY.exists() else None,
                   help="neighbourhood polygon(s), WGS84 GeoJSON (default: the CBD in Data/boundaries/; "
                        "'' = the old placeholder box)")
    p.add_argument("--boundary-name", default=L.DEFAULT_BOUNDARY_NAME,
                   help="text matching the polygon's properties (default: 'central business')")
    p.add_argument("--roads-geojson", help="local road centrelines instead of Overpass")
    p.add_argument("--highways", default=L.DEFAULT_HIGHWAYS, help="OSM highway regex")
    p.add_argument("--step", dest="step_m", type=float, default=L.DEFAULT_STEP_M, help="point spacing in metres")
    p.add_argument("--n", type=int, default=10, help="images wanted (pilot cap: 10)")
    p.add_argument("--max-attempts", type=int, default=60, help="max points to try")
    p.add_argument("--radius", type=float, default=30.0, help="max distance (m) from point to image")
    p.add_argument("--capture-start", default=STUDY_START,
                   help="only images captured on/after this local date (default: study period start, 2026-06-01)")
    p.add_argument("--capture-end", default=STUDY_END,
                   help="only images captured on/before this local date (default: study period end, 2026-08-31)")
    p.add_argument("--any-date", action="store_true",
                   help="drop the capture-date filter (images from any year; NOT the study design)")
    p.add_argument("--study-period", action="store_true", help="(default behaviour; kept for compatibility)")
    p.add_argument("--no-pano", dest="allow_pano", action="store_false",
                   help="skip 360-degree images (by default they are used, cropped to side-on views)")
    p.add_argument("--prefer", choices=["recent", "summer"], default="recent",
                   help="ranking when several images qualify (default: most recent year first)")
    p.add_argument("--coverage-from-year", type=int, default=2013)
    p.add_argument("--clip-model", default="openai/clip-vit-base-patch32")
    p.add_argument("--views", type=int, default=3, help="square crops per image for CLIP")
    p.add_argument("--reddit-dir", help="Data/reddit_2026-06-01_2026-08-31 (auto-detected)")
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    a.step_name, a.step = a.step, a.step_m          # positional step name vs spacing in metres
    if a.any_date:
        a.capture_start = a.capture_end = None
    if a.step_name == "check":
        return cmd_check(a)
    steps = {"points": cmd_points, "coverage": cmd_coverage, "images": cmd_images, "score": cmd_score, "reddit": cmd_reddit, "report": cmd_report}
    for name in (["points", "coverage", "images", "score", "reddit", "report"] if a.step_name == "all" else [a.step_name]):
        steps[name](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
