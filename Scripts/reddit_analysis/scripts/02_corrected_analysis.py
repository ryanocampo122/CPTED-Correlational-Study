"""
02_corrected_analysis.py
=========================
CPTED Vision | Neighbourhood, cue, time-of-day and seasonal analysis

PURPOSE
-------
Builds the analysis tables from the cleaned row-level data written by
01d_build_cleaned_datasets.py. Compared with the August version:

  - locations: word boundary + other-city exclusions; Sutherland added
  - environmental cues: corrected venv_* tags instead of the substring env_*
  - sentiment: adjusted VADER (sentiment_adj_*) is primary; the original VADER
    figures are kept alongside in *_vader_original columns
  - seasons use local (Saskatoon) time, not UTC
  - every mean / percentage carries a 95% CI from a thread-clustered bootstrap
    (comments in the same thread are not independent)
  - "focus sites" = every area with >= common.MIN_MENTIONS_FOCUS mentions

A note on time of day: time_of_day is when a comment was POSTED, not when the
experience it describes happened. Read the time-of-day tables as "tone of
discussion by posting hour", not "how safe a place feels at night".

INPUT
-----
  04_cleaned_datasets/saskatoon_safety_{posts,comments}_<stamp>_CLEANED_v2.csv

OUTPUT (02_derived_analysis/)
------
  neighbourhood_summary.csv                 per area: volume, sentiment, % negative, CIs
  neighbourhood_summary_thread_inherited.csv sensitivity: comments inherit their thread's location
  env_cues_by_site.csv                      % of NEGATIVE comments mentioning each cue (wide)
  env_cues_by_site_detail.csv               cue rate in negative vs all comments, with CIs (long)
  time_of_day_by_site.csv                   mean sentiment by posting-time bucket, with CIs
  time_of_day_contrasts.csv                 night minus other buckets, per site, with CI
  seasonal_trend.csv                        posts by local season, sentiment with CI
  monthly_trend.csv                         posts by local month, sentiment with CI

Comments posted after the collection window closed (October collections flag
them with comment_in_window) are left out of every table; see
common.analysis_comments().

USAGE
-----
  python 02_corrected_analysis.py
"""

import numpy as np
import pandas as pd

import common as c

NEG = "negative"


def load_clean() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cleaned posts, and the comments used in analysis (in-window only, when recorded)."""
    posts = pd.read_csv(c.cleaned_file("posts"), low_memory=False)
    comments = pd.read_csv(c.cleaned_file("comments"), low_memory=False)
    return posts, c.analysis_comments(comments)


def r3(x):
    """Round to 3 dp; None/NaN -> None."""
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 3)


def summarise(values: pd.Series, cats: pd.Series, clusters: pd.Series) -> dict:
    """Mean sentiment and % negative, each with a thread-bootstrap 95% CI."""
    n = len(values)
    if n == 0:
        return {"mean_sentiment": None, "mean_ci95_low": None, "mean_ci95_high": None,
                "pct_negative": None, "pct_neg_ci95_low": None, "pct_neg_ci95_high": None,
                "n_negative": 0}
    neg = (cats == NEG).astype(float).values
    m_lo, m_hi = c.cluster_bootstrap_ci(values.values, clusters.values)
    p_lo, p_hi = c.cluster_bootstrap_ci(neg, clusters.values)
    return {
        "mean_sentiment": r3(values.mean()),
        "mean_ci95_low": r3(m_lo), "mean_ci95_high": r3(m_hi),
        "pct_negative": round(neg.mean() * 100, 1),
        "pct_neg_ci95_low": None if np.isnan(p_lo) else round(p_lo * 100, 1),
        "pct_neg_ci95_high": None if np.isnan(p_hi) else round(p_hi * 100, 1),
        "n_negative": int(neg.sum()),
    }


def neighbourhood_summary(posts, comments, comment_prefix: str = "vloc_") -> pd.DataFrame:
    """comment_prefix="thread_vloc_" counts a comment if it OR its thread's
    post mentions the area (sensitivity analysis)."""
    rows = []
    for name in c.NEIGHBOURHOODS:
        p = posts[posts[c.slug(name, "vloc_")]]
        cm = comments[comments[c.slug(name, comment_prefix)]]
        both = pd.concat([p, cm])
        row = {"neighbourhood": name, "posts": len(p), "comments": len(cm),
               "total_mentions": len(both), "n_threads": both["thread_id"].nunique()}
        row.update(summarise(both["sentiment_adj_compound"], both["sentiment_adj_category"], both["thread_id"]))
        row["mean_sentiment_vader_original"] = r3(both["sentiment_compound"].mean()) if len(both) else None
        row["pct_negative_vader_original"] = (round((both["sentiment_category"] == NEG).mean() * 100, 1)
                                              if len(both) else None)
        row["small_sample"] = len(both) < 30
        rows.append(row)
    return pd.DataFrame(rows).sort_values("total_mentions", ascending=False).reset_index(drop=True)


def focus_sites(summary: pd.DataFrame) -> list[str]:
    """Areas with at least MIN_MENTIONS_FOCUS verified mentions."""
    return summary.loc[summary["total_mentions"] >= c.MIN_MENTIONS_FOCUS, "neighbourhood"].tolist()


def env_cues(comments, sites) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cue rates among negative comments, citywide and per site. Returns (wide, long)."""
    wide, long = [], []
    groups = [("Citywide (all comments)", pd.Series(True, index=comments.index))]
    groups += [(s, comments[c.slug(s, "vloc_")]) for s in sites]
    for name, mask in groups:
        site = comments[mask]
        negs = site[site["sentiment_adj_category"] == NEG]
        w = {"neighbourhood": name, "n_negative_comments": len(negs)}
        for cue in c.ENV_CUE_NAMES:
            col = f"venv_{cue}"
            k_neg, k_all = int(negs[col].sum()), int(site[col].sum())
            w[cue] = round(k_neg / len(negs) * 100, 1) if len(negs) else None
            lo, hi = (c.cluster_bootstrap_ci(negs[col].astype(float).values, negs["thread_id"].values)
                      if len(negs) else (np.nan, np.nan))
            long.append({
                "neighbourhood": name, "cue": cue,
                "n_negative_comments": len(negs), "k_negative_with_cue": k_neg,
                "pct_of_negative": w[cue],
                "pct_of_negative_ci95_low": None if np.isnan(lo) else round(lo * 100, 1),
                "pct_of_negative_ci95_high": None if np.isnan(hi) else round(hi * 100, 1),
                "n_all_comments": len(site), "k_all_with_cue": k_all,
                "pct_of_all": round(k_all / len(site) * 100, 1) if len(site) else None,
                "pct_negative_given_cue": round((negs[col].sum() / k_all) * 100, 1) if k_all else None,
                "pct_negative_without_cue": (round(((site["sentiment_adj_category"] == NEG) & ~site[col]).sum()
                                                   / (~site[col]).sum() * 100, 1) if (~site[col]).sum() else None),
            })
        wide.append(w)
    return pd.DataFrame(wide), pd.DataFrame(long)


def time_of_day(comments, sites) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sentiment per time-of-day bucket and site, plus night-vs-other contrasts with CIs.
    Returns (table, contrasts)."""
    rows, contrasts = [], []
    groups = [("Citywide (all comments)", comments)] + [(s, comments[comments[c.slug(s, "vloc_")]]) for s in sites]
    for name, sub in groups:
        for tod in c.TIME_OF_DAY_ORDER:
            b = sub[sub["local_time_of_day"] == tod]
            lo, hi = c.cluster_bootstrap_ci(b["sentiment_adj_compound"].values, b["thread_id"].values)
            rows.append({
                "neighbourhood": name, "time_of_day": tod, "n": len(b),
                "n_threads": b["thread_id"].nunique(),
                "mean_sentiment": r3(b["sentiment_adj_compound"].mean()) if len(b) else None,
                "mean_ci95_low": r3(lo), "mean_ci95_high": r3(hi),
                "pct_negative": round((b["sentiment_adj_category"] == NEG).mean() * 100, 1) if len(b) else None,
                "mean_sentiment_vader_original": r3(b["sentiment_compound"].mean()) if len(b) else None,
            })
        night = sub[sub["local_time_of_day"] == "night"]
        other = sub[sub["local_time_of_day"] != "night"]
        if len(night) and len(other):
            lo, hi = c.cluster_bootstrap_diff_ci(night["sentiment_adj_compound"].values, night["thread_id"].values,
                                                 other["sentiment_adj_compound"].values, other["thread_id"].values)
            diff = night["sentiment_adj_compound"].mean() - other["sentiment_adj_compound"].mean()
            contrasts.append({
                "neighbourhood": name, "n_night": len(night), "n_other": len(other),
                "mean_night": r3(night["sentiment_adj_compound"].mean()),
                "mean_other": r3(other["sentiment_adj_compound"].mean()),
                "night_minus_other": r3(diff), "ci95_low": r3(lo), "ci95_high": r3(hi),
                "ci_excludes_zero": bool(lo > 0 or hi < 0) if not np.isnan(lo) else None,
            })
    return pd.DataFrame(rows), pd.DataFrame(contrasts)


def seasonal(posts) -> pd.DataFrame:
    """Posts and sentiment per local season; the UTC-season count is kept for comparison."""
    rows = []
    for s in c.SEASON_ORDER:
        b = posts[posts["local_season"] == s]
        lo, hi = c.cluster_bootstrap_ci(b["sentiment_adj_compound"].values, b["thread_id"].values)
        rows.append({
            "season": s, "post_count": len(b),
            "post_count_utc_season": int((posts["season"] == s).sum()),
            "mean_sentiment": r3(b["sentiment_adj_compound"].mean()),
            "mean_ci95_low": r3(lo), "mean_ci95_high": r3(hi),
            "pct_negative": round((b["sentiment_adj_category"] == NEG).mean() * 100, 1),
            "mean_sentiment_vader_original": r3(b["sentiment_compound"].mean()),
        })
    return pd.DataFrame(rows)


def monthly(posts) -> pd.DataFrame:
    """Posts and sentiment per local calendar month."""
    rows = []
    year = posts["local_date"].str[:4].astype(int)
    for (y, m), b in posts.groupby([year, posts["local_month"]]):
        lo, hi = c.cluster_bootstrap_ci(b["sentiment_adj_compound"].values, b["thread_id"].values)
        rows.append({
            "year": int(y), "month": int(m), "post_count": len(b),
            "mean_sentiment": r3(b["sentiment_adj_compound"].mean()),
            "mean_ci95_low": r3(lo), "mean_ci95_high": r3(hi),
            "pct_negative": round((b["sentiment_adj_category"] == NEG).mean() * 100, 1),
            "mean_sentiment_vader_original": r3(b["sentiment_compound"].mean()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    posts, comments = load_clean()
    d = c.out_dir("02_derived_analysis")

    nb = neighbourhood_summary(posts, comments)
    nb.to_csv(d / "neighbourhood_summary.csv", index=False)
    print("=== Neighbourhood summary (adjusted sentiment, thread-bootstrap 95% CI) ===")
    print(nb[["neighbourhood", "posts", "comments", "total_mentions", "mean_sentiment",
              "mean_ci95_low", "mean_ci95_high", "pct_negative", "pct_neg_ci95_low",
              "pct_neg_ci95_high", "mean_sentiment_vader_original",
              "pct_negative_vader_original"]].to_string(index=False), "\n")

    inh = neighbourhood_summary(posts, comments, comment_prefix="thread_vloc_")
    inh.to_csv(d / "neighbourhood_summary_thread_inherited.csv", index=False)

    sites = focus_sites(nb)
    print(f"Focus sites (>= {c.MIN_MENTIONS_FOCUS} mentions): {sites}\n")

    wide, long = env_cues(comments, sites)
    wide.to_csv(d / "env_cues_by_site.csv", index=False)
    long.to_csv(d / "env_cues_by_site_detail.csv", index=False)
    print("=== % of negative comments mentioning each cue (corrected cues) ===")
    print(wide.to_string(index=False), "\n")

    tod, contrasts = time_of_day(comments, sites)
    tod.to_csv(d / "time_of_day_by_site.csv", index=False)
    contrasts.to_csv(d / "time_of_day_contrasts.csv", index=False)
    print("=== Night vs other posting times (comments) ===")
    print(contrasts.to_string(index=False), "\n")

    season = seasonal(posts)
    season.to_csv(d / "seasonal_trend.csv", index=False)
    print("=== Seasonal trend (posts, local time) ===")
    print(season.to_string(index=False), "\n")

    month = monthly(posts)
    month.to_csv(d / "monthly_trend.csv", index=False)
    print("=== Monthly trend (posts, local time) ===")
    print(month.to_string(index=False))


if __name__ == "__main__":
    main()
