"""
02_corrected_analysis.py
=========================
ComputerVision_Sentinel | Corrected neighbourhood-level analysis

PURPOSE
-------
Re-tags every post and comment using the word-boundary-corrected matcher
(see 01_audit_location_tagging.py for why this is necessary), then
computes the analysis tables that feed the August report:

  1. neighbourhood_summary_corrected.csv
       Per-neighbourhood mention counts, mean sentiment, % negative.
  2. env_cues_by_site.csv
       For a set of "focus" sites, the rate at which each environmental
       cue (lighting/noise/weather/time_of_day/people) co-occurs with
       NEGATIVE comments.
  3. time_of_day_by_site.csv
       Mean sentiment by time-of-day bucket, for the same focus sites.
  4. seasonal_trend.csv
       Citywide post volume and mean sentiment by season.

INPUT
-----
  /mnt/user-data/uploads/saskatoon_safety_posts_20260611.csv
  /mnt/user-data/uploads/saskatoon_safety_comments_20260611.csv

OUTPUT
------
  output/neighbourhood_summary_corrected.csv
  output/env_cues_by_site.csv
  output/time_of_day_by_site.csv
  output/seasonal_trend.csv

USAGE
-----
  python 02_corrected_analysis.py
"""

import re
import pandas as pd

POSTS_PATH = "/mnt/user-data/uploads/saskatoon_safety_posts_20260611.csv"
COMMENTS_PATH = "/mnt/user-data/uploads/saskatoon_safety_comments_20260611.csv"

# Same pattern list as 01_audit_location_tagging.py — kept in sync manually.
# If you change one, change the other (or refactor both to import from a
# shared constants module).
NEIGHBOURHOODS: dict[str, list[str]] = {
    "Pleasant Hill":       ["pleasant hill"],
    "Riversdale":          ["riversdale"],
    "Meadowgreen":         ["meadowgreen"],
    "Westmount":           ["westmount"],
    "Mount Royal":         ["mount royal"],
    "King George":         ["king george"],
    "Caswell Hill":        ["caswell hill", "caswell"],
    "Mayfair":             ["mayfair"],
    "Downtown / CBD":      ["downtown", "cbd", "central business district",
                            "20th street", "20th st", "23rd street", "23rd st"],
    "Broadway":            ["broadway"],
    "Nutana":              ["nutana"],
    "Downtown Terminal":   ["downtown terminal", "bus terminal", "bus depot",
                            "transit terminal"],
    "Confederation Mall":  ["confederation mall", "confed mall"],
    "Market Mall":         ["market mall"],
    "Place Riel / USask":  ["place riel", "usask", "u of s", "university of saskatchewan"],
    "Riverbank / Meewasin": ["river", "meewasin", "riverbank", "river trail"],
    "Stonebridge":         ["stonebridge"],
    "Lakeridge":           ["lakeridge"],
    "Briarwood":           ["briarwood"],
    "Arbor Creek":         ["arbor creek"],
    "Silverspring":        ["silverspring", "silver spring"],
}

# Sites with enough corrected volume (>=15 mentions) to be worth a
# deeper cue / time-of-day breakdown, plus the two sites the August
# report focuses on (Downtown/CBD, Riverbank/Meewasin).
FOCUS_SITES = [
    "Downtown / CBD", "Riverbank / Meewasin", "Caswell Hill",
    "Stonebridge", "Riversdale", "Pleasant Hill",
]

ENV_CUE_COLUMNS = ["env_lighting", "env_noise", "env_weather",
                    "env_time_of_day", "env_people"]


def bounded_match(text: str, patterns: list[str]) -> bool:
    if not isinstance(text, str):
        return False
    t = text.lower()
    return any(re.search(r"\b" + re.escape(p) + r"\b", t) for p in patterns)


def slug(name: str) -> str:
    """Column-name-safe version of a neighbourhood name, matching the
    convention used by the original scraper's loc_* columns."""
    return "c_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def tag_neighbourhoods(df: pd.DataFrame, text_col: str) -> pd.DataFrame:
    """Adds one boolean column per neighbourhood (corrected matcher)."""
    for name, patterns in NEIGHBOURHOODS.items():
        df[slug(name)] = df[text_col].apply(lambda t: bounded_match(t, patterns))
    return df


def build_neighbourhood_summary(posts: pd.DataFrame, comments: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in NEIGHBOURHOODS:
        col = slug(name)
        p_sub = posts[posts[col]]
        c_sub = comments[comments[col]]
        all_sent = pd.concat([p_sub["sentiment_compound"], c_sub["sentiment_compound"]])
        all_cat = pd.concat([p_sub["sentiment_category"], c_sub["sentiment_category"]])
        rows.append({
            "neighbourhood": name,
            "posts": len(p_sub),
            "comments": len(c_sub),
            "total_mentions": len(p_sub) + len(c_sub),
            "mean_sentiment": round(all_sent.mean(), 3) if len(all_sent) else None,
            "pct_negative": round((all_cat == "negative").mean() * 100, 1) if len(all_cat) else None,
            "n_negative": int((all_cat == "negative").sum()),
        })
    return pd.DataFrame(rows).sort_values("total_mentions", ascending=False).reset_index(drop=True)


def build_env_cues_by_site(comments: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in FOCUS_SITES:
        col = slug(name)
        sub = comments[(comments[col]) & (comments["sentiment_category"] == "negative")]
        n = len(sub)
        row = {"neighbourhood": name, "n_negative_comments": n}
        for cue in ENV_CUE_COLUMNS:
            row[cue] = round(sub[cue].mean() * 100, 1) if n else None
        rows.append(row)
    return pd.DataFrame(rows)


def build_time_of_day_by_site(comments: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in FOCUS_SITES:
        col = slug(name)
        sub = comments[comments[col]]
        g = sub.groupby("time_of_day")["sentiment_compound"].agg(["mean", "count"])
        for tod in ["morning", "afternoon", "evening", "night"]:
            if tod in g.index:
                rows.append({
                    "neighbourhood": name, "time_of_day": tod,
                    "mean_sentiment": round(g.loc[tod, "mean"], 3),
                    "n": int(g.loc[tod, "count"]),
                })
            else:
                rows.append({"neighbourhood": name, "time_of_day": tod,
                              "mean_sentiment": None, "n": 0})
    return pd.DataFrame(rows)


def build_seasonal_trend(posts: pd.DataFrame) -> pd.DataFrame:
    g = posts.groupby("season")["sentiment_compound"].agg(["mean", "count"])
    g = g.reindex(["spring", "summer", "fall", "winter"])
    g.columns = ["mean_sentiment", "post_count"]
    return g.reset_index()


def main() -> None:
    posts = pd.read_csv(POSTS_PATH)
    comments = pd.read_csv(COMMENTS_PATH)

    posts = tag_neighbourhoods(posts, "full_text")
    comments = tag_neighbourhoods(comments, "body")

    nb_summary = build_neighbourhood_summary(posts, comments)
    nb_summary.to_csv("output/neighbourhood_summary_corrected.csv", index=False)
    print("=== Corrected neighbourhood summary ===")
    print(nb_summary.to_string(index=False), "\n")

    cue_df = build_env_cues_by_site(comments)
    cue_df.to_csv("output/env_cues_by_site.csv", index=False)
    print("=== Environmental cue rate in negative comments, by site ===")
    print(cue_df.to_string(index=False), "\n")

    tod_df = build_time_of_day_by_site(comments)
    tod_df.to_csv("output/time_of_day_by_site.csv", index=False)
    print("=== Mean sentiment by time of day, by site ===")
    print(tod_df.to_string(index=False), "\n")

    season_df = build_seasonal_trend(posts)
    season_df.to_csv("output/seasonal_trend.csv", index=False)
    print("=== Seasonal trend (all posts) ===")
    print(season_df.to_string(index=False))


if __name__ == "__main__":
    main()
