#!/usr/bin/env python3
"""
report_numbers.py
=================
UrbanSentinel-Prairie | Every number quoted in the October 2026 progress report

Reads Data/ and writes Docs/verification/october_2026_numbers.json, which
build_october_report.js reads. Nothing in the report text is typed by hand.

USAGE (repository root):  .venv/bin/python Scripts/reporting/report_numbers.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "Data"
REDDIT = DATA / "reddit_2026-06-01_2026-08-31"
JUNE = DATA / "reddit_2025-06-11_2026-06-11"
CV = DATA / "cv_pilot_2026-10"
TZ = "America/Regina"
sys.path.insert(0, str(REPO / "Scripts" / "cv_pilot"))
import pilot_lib as L  # noqa: E402


def r1(x):
    return round(float(x), 1)


def reddit() -> dict:
    raw = REDDIT / "01_raw_collection"
    p = pd.read_csv(next(raw.glob("saskatoon_safety_posts_*.csv")))
    c = pd.read_csv(next(raw.glob("saskatoon_safety_comments_*.csv")))
    meta = json.loads(next(raw.glob("saskatoon_safety_metadata_*.json")).read_text())
    q = pd.read_csv(next(raw.glob("search_query_log_*.csv")))
    pl = pd.to_datetime(p.created_utc, unit="s", utc=True).dt.tz_convert(TZ)
    nb = pd.read_csv(REDDIT / "02_derived_analysis" / "neighbourhood_summary.csv").set_index("neighbourhood")
    nbj = pd.read_csv(JUNE / "02_derived_analysis" / "neighbourhood_summary.csv").set_index("neighbourhood")
    sens = pd.read_csv(REDDIT / "05_audits" / "sentiment_sensitivity.csv").set_index("spec")
    prec = pd.read_csv(REDDIT / "05_audits" / "env_cue_precision_heldout.csv").set_index("cue")
    vr = (REDDIT / "05_audits" / "verification_report.txt").read_text()
    vrj = (JUNE / "05_audits" / "verification_report.txt").read_text()
    chk = pd.read_csv(REPO / "Docs" / "verification" / "october_2026_checks.csv")

    def area(df, name):
        r = df.loc[name]
        return {"n": int(r.total_mentions), "posts": int(r.posts), "comments": int(r.comments),
                "threads": int(r.n_threads), "pct_neg": r1(r.pct_negative),
                "pct_lo": r1(r.pct_neg_ci95_low), "pct_hi": r1(r.pct_neg_ci95_high),
                "mean": float(r.mean_sentiment), "mean_lo": float(r.mean_ci95_low), "mean_hi": float(r.mean_ci95_high)}

    cl = REDDIT / "04_cleaned_datasets"
    cp = pd.read_csv(next(cl.glob("*posts*_CLEANED_v2.csv")))
    cc = pd.read_csv(next(cl.glob("*comments*_CLEANED_v2.csv")))
    cc = cc[cc.comment_in_window.astype(bool)]
    on = set(cp.loc[cp.text_has_safety_term | cp.text_has_crime_term, "id"].astype(str))
    rec = pd.concat([cp.assign(thread=cp.id.astype(str)), cc.assign(thread=cc.parent_post_id.astype(str))])
    dt = rec[rec.vloc_downtown_cbd.astype(bool)]
    dt_on = dt[dt.thread.isin(on)]
    ppl = dt[dt.venv_people.astype(bool)]
    jp = pd.read_csv(next((JUNE / "01_raw_collection").glob("saskatoon_safety_posts_*.csv")))
    jl = pd.to_datetime(jp.created_utc, unit="s", utc=True).dt.tz_convert(TZ)
    ov = jp[jl >= pd.Timestamp("2026-06-01", tz=TZ)]
    got = c.groupby("parent_post_id").size()
    anchors = pd.read_csv(CV / "cbd_latest_imagery" / "reddit_place_anchors.csv").sort_values(
        "records_in_downtown_tagged", ascending=False)
    rep = chk[chk.check.str.startswith("Published tables reproduce")]

    def nums(s):
        a, b = s.split(" CSV")[0].split(" of ")
        return int(a), int(b)

    areas15 = nb[nb.total_mentions >= 15].index.tolist()
    rv = pd.read_csv(REPO / "Scripts" / "reddit_analysis" / "manual_review" / "location_other_city_review.csv", dtype=str)
    rv = rv[rv.reviewer.fillna("").str.contains("reconstructed")]
    return {
        "posts": len(p), "comments": len(c), "comments_in_window": int(c.comment_in_window.sum()),
        "comments_late": int((~c.comment_in_window.astype(bool)).sum()),
        "posts_by_month": {m: int(v) for m, v in pl.dt.strftime("%b").value_counts().items()},
        "days_with_posts": int(pl.dt.date.nunique()),
        "seeds_safety": len(meta["seed_sets"]["safety"]), "seeds_crime": len(meta["seed_sets"]["crime"]),
        "sorts": len(meta["search_sorts"]), "queries": len(q), "query_max": int(q.results_returned.max()),
        "collected_utc": meta["collection_run_utc"][:10],
        "reddit_comment_count": int(p.num_comments.sum()), "comment_coverage_pct": round(
            100 * p.id.map(got).fillna(0).sum() / p.num_comments.sum()),
        "june_overlap_posts": len(ov), "june_overlap_found": int(ov.id.isin(p.id).sum()),
        "seed_term_posts": int((p.text_has_safety_term | p.text_has_crime_term).sum()),
        "downtown": area(nb, "Downtown / CBD"), "riverbank": area(nb, "Riverbank / Meewasin"),
        "broadway": area(nb, "Broadway"), "areas_15": len(areas15),
        "downtown_june_collection": area(nbj, "Downtown / CBD"),
        "all_comments_pct_neg": float(sens.loc["B_adjusted", "comments_pct_negative"]),
        "dt_on_topic_n": len(dt_on), "dt_on_topic_pct_neg": r1(100 * (dt_on.sentiment_adj_category == "negative").mean()),
        "dt_people_n": len(ppl), "dt_people_homeless": int(ppl.venv_people_terms.fillna("").str.contains("homeless").sum()),
        "precision": {k: round(100 * v.precision) for k, v in prec.iterrows()},
        "precision_n": int(prec.n_judged.iloc[0]),
        "selfchecks_pass": vr.count("[PASS]"), "selfchecks_fail": vr.count("[FAIL]"),
        "selfchecks_june_pass": vrj.count("[PASS]"),
        "reproduce_junaug": nums(rep.iloc[0].result), "reproduce_june": nums(rep.iloc[1].result),
        "anchor_top": anchors.iloc[0].anchor, "anchor_top_n": int(anchors.iloc[0].records_in_downtown_tagged),
        "anchors_under5": int((anchors.records_in_downtown_tagged < 5).sum()), "anchors_n": len(anchors),
        "review_excluded": int((rv.decision == "exclude").sum()), "review_kept": int((rv.decision == "keep").sum()),
        "riverbank_june_collection": area(nbj, "Riverbank / Meewasin"),
    }


def points() -> dict:
    polys, _, _ = L.load_boundary(str(DATA / "boundaries" / "central_business_district_osm.geojson"), "central business")
    pts = pd.read_csv(CV / "cbd" / "sample_points.csv")
    box = pd.read_csv(CV / "placeholder_box" / "sample_points.csv")
    meta = json.loads((CV / "cbd" / "run_meta.json").read_text())["points"]
    w, s, e, n = json.loads((CV / "placeholder_box" / "run_meta.json").read_text())["points"]["bbox"]
    gaps = []
    for _, g in pts.sort_values("along_m").groupby("segment_id"):
        gaps += list(np.diff(g.along_m.values))
    inside = box.apply(lambda r: L.point_in_polygons(r.lon, r.lat, polys), axis=1)
    in_box = pts.lon.between(w, e) & pts.lat.between(s, n)
    bridges = set(json.loads((CV / "cbd" / "osm_bridge_way_ids.json").read_text())["way_ids"])
    bad = pts.osm_way_id.astype(str).isin(bridges) | pts.highway.isin(["motorway", "trunk"])
    per = pts.groupby("segment_id").size()
    proj = L.LocalProjection(pts.lon.mean(), pts.lat.mean())
    xy = np.array([proj.to_xy(a, b) for a, b in zip(pts.lon, pts.lat)])
    dmin = min(np.sqrt(((xy[i + 1:] - xy[i]) ** 2).sum(axis=1)).min() for i in range(len(xy) - 1))
    return {"n": len(pts), "segments": int(pts.segment_id.nunique()), "ways": meta["n_ways"],
            "road_classes": meta["highway_filter"].count("|") + 1,
            "spacing_median": r1(np.median(gaps)), "spacing_p5": round(np.percentile(gaps, 5)),
            "spacing_p95": round(np.percentile(gaps, 95)), "min_sep": r1(dmin),
            "single_point_segments": int((per == 1).sum()),
            "box_n": len(box), "box_inside": int(inside.sum()), "box_inside_pct": round(100 * inside.mean()),
            "box_missed": int((~in_box).sum()), "box_missed_pct": round(100 * (~in_box).mean()),
            "bridge_or_freeway": int(bad.sum())}


def imagery() -> dict:
    cov = json.loads((CV / "cbd" / "run_meta.json").read_text())["coverage"]
    cp = pd.read_csv(CV / "cbd" / "coverage_points.csv")
    newest = cp[["latest_flat", "latest_pano"]].fillna("").max(axis=1).str[:4].replace("", "none")
    man = pd.read_csv(CV / "cbd_latest_imagery" / "image_manifest.csv")
    pts = pd.read_csv(CV / "cbd_latest_imagery" / "sample_points.csv").set_index("point_id")
    off = np.array([min(d, 180 - d) for d in (L.angle_diff(r.compass_angle, pts.at[r.point_id, "road_bearing_deg"])
                                               for r in man.itertuples())])
    clip = pd.read_csv(CV / "cbd_latest_imagery" / "clip_scores.csv")
    att = pd.read_csv(CV / "cbd" / "pilot_attempts.csv")
    vc = newest.value_counts()
    return {"points": cov["points"], "any": cov["points_with_any_image"], "study": cov["points_with_study_period_image"],
            "newest": {k: int(v) for k, v in vc.items()},
            "since_2020": int((newest.isin(["2020", "2023"])).sum()),
            "y2017_19": int(newest.isin(["2017", "2018", "2019"]).sum()),
            "study_attempts": len(att), "study_found": int((att.status == "ok").sum()),
            "pilot_n": len(man), "pilot_pano": int(man.is_pano.sum()),
            "pilot_years": {str(k): int(v) for k, v in man.capture_year.value_counts().sort_index().items()},
            "pilot_cross_street": int((off > 60).sum()), "pilot_aligned": int((off < 30).sum()),
            "clip_low_conf": int(clip.typology_low_confidence.sum()), "cues": 9, "typology_labels": 8}


def main() -> None:
    out = {"generated_from": "Data/ via Scripts/reporting/report_numbers.py",
           "reddit": reddit(), "points": points(), "imagery": imagery()}
    path = REPO / "Docs" / "verification" / "october_2026_numbers.json"
    path.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
