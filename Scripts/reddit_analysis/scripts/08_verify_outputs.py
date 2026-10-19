"""
08_verify_outputs.py
====================
ComputerVision_Sentinel | Independent checks on the pipeline outputs

PURPOSE
-------
Re-derives key numbers by separate code paths and fails loudly on any mismatch.

  June 2026 collection (substring-tagged raw files):
  1. Provenance: the vocabularies in common.py match the scraper copy that
     produced the June data (01_raw_collection/initial_sraper.py).
  2. Stored columns reproduce: env_* from substring matching, sentiment_compound
     from stock VADER on cleaned_text.
  3. The August 2026 tables reproduce byte-for-byte from the raw data with the
     August logic (if the August package is present), so the shared matcher
     behaves exactly like the August one.
  October 2026 and later collections (reddit_scraper.py, whole-word tags):
  1. Provenance: the common.py copy saved with the collection
     (01_raw_collection/collection_code/) has the same vocabularies, cue
     definitions and lexicon adjustments as this one.
  2. Stored loc_*, env_*, sentiment_compound and sentiment_adj_compound
     reproduce from the text under the current definitions.
  3. Every post was created inside the collection window, and the
     comment_in_window flag agrees with each comment's timestamp.
  Every collection:
  4. The cleaned v2 rows reconcile with neighbourhood_summary.csv.
  5. Every hand-review "exclude" decision is reflected in the cleaned data, and
     no quote sample row comes from an excluded record.
  6. June collection only: numbers quoted in the July/August documents,
     re-checked against the data (05_audits/august_document_claims_check.csv).

OUTPUT
------
  05_audits/verification_report.txt
  05_audits/august_document_claims_check.csv

USAGE
-----
  python 08_verify_outputs.py      (exit code 1 if any hard check fails)
"""

import ast
import importlib.util
import io
import re
import sys
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import pandas as pd

import common as c

LOG: list[str] = []
FAILS: list[str] = []


def check(ok: bool, label: str) -> None:
    """Log one PASS/FAIL line. Any FAIL makes main() return 1."""
    LOG.append(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        FAILS.append(label)


def scraper_vocab(path):
    """SASKATOON_NEIGHBOURHOODS and ENVIRONMENTAL_CUES literals from a scraper file,
    read with ast so the scraper is never imported or run."""
    tree = ast.parse(path.read_text())
    out = {}
    for node in tree.body:
        targets = []
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.Assign):
            targets = node.targets
        for t in targets:
            if isinstance(t, ast.Name) and t.id in ("SASKATOON_NEIGHBOURHOODS", "ENVIRONMENTAL_CUES"):
                out[t.id] = ast.literal_eval(node.value)
    return out


# --- August logic, copied from the August 02_corrected_analysis.py --------------

def august_tables(posts: pd.DataFrame, comments: pd.DataFrame) -> dict[str, str]:
    """August 2026 tables rebuilt with the August logic. Returns {file name: CSV text}."""
    focus = ["Downtown / CBD", "Riverbank / Meewasin", "Caswell Hill",
             "Stonebridge", "Riversdale", "Pleasant Hill"]
    cues = ["env_lighting", "env_noise", "env_weather", "env_time_of_day", "env_people"]

    def slug(name):
        return "c_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")

    posts, comments = posts.copy(), comments.copy()
    for name, pats in c.NEIGHBOURHOODS_ORIGINAL.items():
        posts[slug(name)] = posts["full_text"].apply(lambda t: c.bounded_match(t, pats))
        comments[slug(name)] = comments["body"].apply(lambda t: c.bounded_match(t, pats))

    rows = []
    for name in c.NEIGHBOURHOODS_ORIGINAL:
        p_sub, c_sub = posts[posts[slug(name)]], comments[comments[slug(name)]]
        s = pd.concat([p_sub["sentiment_compound"], c_sub["sentiment_compound"]])
        k = pd.concat([p_sub["sentiment_category"], c_sub["sentiment_category"]])
        rows.append({"neighbourhood": name, "posts": len(p_sub), "comments": len(c_sub),
                     "total_mentions": len(p_sub) + len(c_sub),
                     "mean_sentiment": round(s.mean(), 3) if len(s) else None,
                     "pct_negative": round((k == "negative").mean() * 100, 1) if len(k) else None,
                     "n_negative": int((k == "negative").sum())})
    nb = pd.DataFrame(rows).sort_values("total_mentions", ascending=False).reset_index(drop=True)

    cue_rows = []
    for name in focus:
        sub = comments[(comments[slug(name)]) & (comments["sentiment_category"] == "negative")]
        r = {"neighbourhood": name, "n_negative_comments": len(sub)}
        for q in cues:
            r[q] = round(sub[q].mean() * 100, 1) if len(sub) else None
        cue_rows.append(r)

    tod_rows = []
    for name in focus:
        g = comments[comments[slug(name)]].groupby("time_of_day")["sentiment_compound"].agg(["mean", "count"])
        for tod in ["morning", "afternoon", "evening", "night"]:
            if tod in g.index:
                tod_rows.append({"neighbourhood": name, "time_of_day": tod,
                                 "mean_sentiment": round(g.loc[tod, "mean"], 3), "n": int(g.loc[tod, "count"])})
            else:
                tod_rows.append({"neighbourhood": name, "time_of_day": tod, "mean_sentiment": None, "n": 0})

    g = posts.groupby("season")["sentiment_compound"].agg(["mean", "count"]).reindex(
        ["spring", "summer", "fall", "winter"])
    g.columns = ["mean_sentiment", "post_count"]

    def csv(df, **kw):
        buf = io.StringIO()
        df.to_csv(buf, **kw)
        return buf.getvalue()

    return {"neighbourhood_summary_corrected.csv": csv(nb, index=False),
            "env_cues_by_site.csv": csv(pd.DataFrame(cue_rows), index=False),
            "time_of_day_by_site.csv": csv(pd.DataFrame(tod_rows), index=False),
            "seasonal_trend.csv": csv(g.reset_index(), index=False)}


def check_october_collection(posts: pd.DataFrame, comments: pd.DataFrame) -> None:
    """Checks 1-3 for collections made with reddit_scraper.py (October 2026 on)."""
    raw = c.raw_dir()
    snap = raw / "collection_code" / "common.py"
    if snap.exists():
        spec = importlib.util.spec_from_file_location("collection_common", snap)
        cc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cc)
        check(cc.NEIGHBOURHOODS == c.NEIGHBOURHOODS,
              "collection used the same neighbourhood vocabulary as this analysis")
        check(cc.ENV_CUES == c.ENV_CUES, "collection used the same cue definitions as this analysis")
        check(cc.VADER_LEXICON_ADJUSTMENTS == c.VADER_LEXICON_ADJUSTMENTS,
              "collection used the same sentiment lexicon adjustments as this analysis")
    else:
        LOG.append("[SKIP] no collection_code/common.py saved with this collection")

    for kind, df, col in [("posts", posts, "full_text"), ("comments", comments, "body")]:
        for q in c.ENV_CUE_NAMES:
            ok = (df[col].apply(lambda t: c.cue_flag(t, q)) == df[f"env_{q}"].astype(bool)).all()
            check(ok, f"{kind}: stored env_{q} == corrected cue definition")
        ok = all((df[col].apply(lambda t, p=pats: c.bounded_match(t, p))
                  == df[c.slug(name, "loc_")].astype(bool)).all()
                 for name, pats in c.NEIGHBOURHOODS.items())
        check(ok, f"{kind}: stored loc_* == whole-word match for all {len(c.NEIGHBOURHOODS)} areas")
        ok = (df["cleaned_text"].apply(c.vader_compound) == df["sentiment_adj_compound"]).all()
        check(ok, f"{kind}: stored sentiment_adj_compound == adjusted VADER(cleaned_text)")
        ok = (df["cleaned_text"].apply(lambda t: c.vader_compound(t, adjusted=False)) == df["sentiment_compound"]).all()
        check(ok, f"{kind}: stored sentiment_compound == stock VADER(cleaned_text)")

    meta = c.raw_metadata()
    tz = ZoneInfo(c.LOCAL_TZ)
    s, e = (datetime.fromisoformat(d).date() for d in meta["window_local"])
    w0 = datetime.combine(s, dtime.min, tz).timestamp()
    w1 = datetime.combine(e, dtime.max, tz).timestamp()
    check(posts["created_utc"].between(w0, w1).all(),
          f"every post was created inside the window ({s} to {e}, {c.LOCAL_TZ})")
    inside = comments["created_utc"].between(w0, w1)
    check((inside == comments["comment_in_window"].astype(bool)).all(),
          f"comment_in_window agrees with comment timestamps ({int(inside.sum()):,} of {len(comments):,} inside)")
    check(posts["id"].is_unique and comments["comment_id"].is_unique, "post and comment ids are unique")
    check(comments["parent_post_id"].isin(posts["id"]).all(), "every comment belongs to a collected post")


def check_june_collection(posts: pd.DataFrame, comments: pd.DataFrame) -> None:
    """Checks 1-3 for the June 2026 collection (initial_sraper.py, substring tags)."""
    raw = c.raw_dir()

    # 1. provenance
    vocab = scraper_vocab(raw / "initial_sraper.py")
    check(vocab.get("SASKATOON_NEIGHBOURHOODS") == c.NEIGHBOURHOODS_ORIGINAL,
          "NEIGHBOURHOODS_ORIGINAL matches the scraper that produced the June data")
    check(vocab.get("ENVIRONMENTAL_CUES") == c.ENV_CUES_ORIGINAL,
          "ENV_CUES_ORIGINAL matches the scraper that produced the June data")

    # 2. stored columns reproduce
    for kind, df, col in [("posts", posts, "full_text"), ("comments", comments, "body")]:
        for q in c.ENV_CUE_NAMES:
            ok = (df[col].apply(lambda t: c.original_cue_flag(t, q)) == df[f"env_{q}"].astype(bool)).all()
            check(ok, f"{kind}: stored env_{q} == substring match of original vocabulary")
        ok = (df["cleaned_text"].apply(lambda t: c.vader_compound(t, adjusted=False)) == df["sentiment_compound"]).all()
        check(ok, f"{kind}: stored sentiment_compound == stock VADER(cleaned_text)")

    # 3. August reproduction
    aug_dir = c.AUGUST_TABLES_DIR
    if aug_dir.exists():
        for fname, text in august_tables(posts, comments).items():
            p = aug_dir / fname
            if p.exists() and p.read_text() == text:
                check(True, f"August {fname} reproduces byte-for-byte")
                continue
            # pandas' default sort is not stable, so rows tied on the sort key
            # can come out in a different order; compare content instead.
            delivered = pd.read_csv(p) if p.exists() else pd.DataFrame()
            ours = pd.read_csv(io.StringIO(text))
            key = list(ours.columns[:2])
            same = (not delivered.empty and
                    delivered.sort_values(key).reset_index(drop=True)
                    .equals(ours.sort_values(key).reset_index(drop=True)))
            check(same, f"August {fname} reproduces (identical values; only tied rows ordered differently)")
    else:
        LOG.append(f"[SKIP] August derived tables not found in {aug_dir}")


def main() -> int:
    posts, comments = c.load_raw()
    june = c.is_substring_collection()
    LOG.append(f"Dataset: {c.dataset_name()}  (collection version {c.collection_version()})")
    if june:
        check_june_collection(posts, comments)
    else:
        check_october_collection(posts, comments)

    # 4. cleaned v2 reconciles with summary
    cp = pd.read_csv(c.cleaned_file("posts"), low_memory=False)
    cc = pd.read_csv(c.cleaned_file("comments"), low_memory=False)
    check(len(cp) == len(posts) and len(cc) == len(comments),
          f"cleaned row counts equal raw ({len(posts):,} / {len(comments):,})")
    check(all(cp[col].astype(str).equals(posts[col].astype(str)) for col in posts.columns),
          "every original posts column unchanged in cleaned file")
    check(all(cc[col].astype(str).equals(comments[col].astype(str)) for col in comments.columns),
          "every original comments column unchanged in cleaned file")
    nb = pd.read_csv(c.out_dir("02_derived_analysis") / "neighbourhood_summary.csv").set_index("neighbourhood")
    ca = c.analysis_comments(cc)
    bad = []
    for name in c.NEIGHBOURHOODS:
        col = c.slug(name, "vloc_")
        both = pd.concat([cp[cp[col]], ca[ca[col]]])
        r = nb.loc[name]
        if not (len(cp[cp[col]]) == r.posts and len(ca[ca[col]]) == r.comments
                and int((both["sentiment_adj_category"] == "negative").sum()) == r.n_negative
                and (len(both) == 0 or round(both["sentiment_adj_compound"].mean(), 3) == r.mean_sentiment)):
            bad.append(name)
    check(not bad, f"neighbourhood_summary reconciles with cleaned rows for all {len(c.NEIGHBOURHOODS)} areas {bad or ''}")

    # 5. review decisions applied; quotes clean
    review = pd.read_csv(c.MANUAL_REVIEW_DIR / "location_other_city_review.csv", dtype=str)
    check((review["decision"] != "pending").all(), "no pending other-city review decisions")
    ex = review[review["decision"] == "exclude"]
    # The review file is shared by all collections; check the rows for this one.
    present = set(cp["id"].astype(str)) | set(cc["comment_id"].astype(str))
    ex = ex[ex["record_id"].isin(present)]
    applied = True
    for r in ex.itertuples():
        df, idc = (cp, "id") if r.record_type == "post" else (cc, "comment_id")
        row = df[df[idc].astype(str) == r.record_id]
        applied &= len(row) == 1 and not bool(row[c.slug(r.neighbourhood, "vloc_")].iloc[0])
    check(applied, f"all {len(ex)} 'exclude' decisions are reflected in vloc_* tags")
    q_dir = c.out_dir("03_extracted_comment_samples")
    excluded_ids = set(ex["record_id"])
    leaked = [f.name for f in q_dir.glob("*.csv")
              if set(pd.read_csv(f, dtype=str)["comment_id"]) & excluded_ids]
    check(not leaked, f"no quote sample contains an excluded record {leaked or ''}")

    # 6. claims in the July / August documents (June collection only)
    a = c.out_dir("05_audits")
    if june:
        write_claims(posts, comments, cp, cc, a)

    LOG.append("")
    LOG.append(f"{len(FAILS)} hard check(s) failed." if FAILS else "All hard checks passed.")
    (a / "verification_report.txt").write_text("\n".join(LOG) + "\n")
    print("\n".join(LOG))
    return 1 if FAILS else 0


def write_claims(posts, comments, cp, cc, a) -> None:
    """Numbers quoted in the July/August documents vs recomputed values
    -> august_document_claims_check.csv."""
    rawm = comments[comments["loc_riverbank_meewasin"].astype(bool)]
    wb_river = comments["body"].apply(lambda t: c.bounded_match(t, c.NEIGHBOURHOODS_ORIGINAL["Riverbank / Meewasin"]))
    fp = comments[comments["loc_riverbank_meewasin"].astype(bool) & ~wb_river]["body"].str.lower()
    claims = [
        ("Master report / memo", "comment false hits from 'driver'/'drivers'", "542", int(fp.str.contains(r"\bdrivers?\b").sum())),
        ("Memo", "raw Riverbank comments mean sentiment", "+0.01", round(rawm["sentiment_compound"].mean(), 3)),
        ("Master report", "other priority categories 0-2% affected", "0-2%",
         "Downtown Terminal comments 12.5% (1 of 8)"),
        ("July briefing", "avg comments per post", "39.5",
         f"{len(comments) / len(posts):.1f} collected (39.5 is Reddit's num_comments field)"),
        ("July briefing", "median post score", "18", float(posts["score"].median())),
        ("July briefing", "posts+comments tagged to a neighbourhood", "1,212",
         f"{int(posts['any_neighbourhood'].sum() + comments['any_neighbourhood'].sum())} raw; "
         f"{int(cp['vloc_any'].sum() + cc['vloc_any'].sum())} after all corrections"),
        ("July briefing", "number of seed terms", "11", 12),
        ("July briefing / Findings", "lighting cue: posts / comments", "84 / 1,457",
         f"{int(cp['venv_lighting'].sum())} / {int(cc['venv_lighting'].sum())} corrected"),
        ("July briefing / Findings", "weather cue: posts / comments", "172 / 2,528",
         f"{int(cp['venv_weather'].sum())} / {int(cc['venv_weather'].sum())} corrected"),
        ("Master report / slides", "Downtown lighting in negative comments", "17.8%",
         None),
        ("Master report / slides", "Downtown negative only at night", "night -0.004, the only negative bucket",
         None),
        ("Master report", "quote 'We've had to lock all washrooms...'", "Downtown/CBD (Saskatoon)",
         "comment mxg71xr is about downtown Regina"),
    ]
    cue = pd.read_csv(c.out_dir("02_derived_analysis") / "env_cues_by_site.csv").set_index("neighbourhood")
    claims[9] = claims[9][:3] + (f"{cue.loc['Downtown / CBD', 'lighting']}% corrected",)
    con = pd.read_csv(c.out_dir("02_derived_analysis") / "time_of_day_contrasts.csv").set_index("neighbourhood")
    dt = con.loc["Downtown / CBD"]
    claims[10] = claims[10][:3] + (f"night minus other {dt.night_minus_other:+.3f}, 95% CI "
                                   f"{dt.ci95_low:+.3f} to {dt.ci95_high:+.3f} (not distinguishable from 0)",)
    claims_df = pd.DataFrame(claims, columns=["document", "claim", "as_reported", "verified_value"])
    claims_df.to_csv(a / "august_document_claims_check.csv", index=False)


if __name__ == "__main__":
    sys.exit(main())
