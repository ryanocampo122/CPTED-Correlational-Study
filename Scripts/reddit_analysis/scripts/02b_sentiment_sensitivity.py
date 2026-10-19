"""
02b_sentiment_sensitivity.py
============================
ComputerVision_Sentinel | How much do the conclusions depend on the sentiment scorer?

PURPOSE
-------
Stock VADER rates the seed terms "safe" (+1.9) and "safety" (+1.8) as positive
and has no entry for "unsafe", "sketchy" or "afraid", so the very words used to
select the data push its sentiment upward. This script scores every post and
comment four ways and reports the headline figures under each:

  A  original     stock VADER on cleaned_text (reproduces the stored scores)
  B  adjusted     VADER with the common.VADER_LEXICON_ADJUSTMENTS (PRIMARY)
  C  adjusted+case  as B, on a PII-scrubbed copy that keeps capitalisation
                  (cleaned_text is lower-cased, which removes VADER's
                  ALL-CAPS emphasis signal)
  D  masked       stock VADER with every safe/safer/safest/safely/safety
                  token replaced by a neutral placeholder (upper bound on
                  the seed-term effect; also discards "not safe" negativity)

A conclusion that holds under all four is robust to the scorer choice.

INPUT
-----
  04_cleaned_datasets/saskatoon_safety_{posts,comments}_<stamp>_CLEANED_v2.csv
  (comments posted after the collection window are left out)

OUTPUT
------
  05_audits/sentiment_sensitivity.csv          headline figures per spec
  05_audits/sentiment_sensitivity_ranking.csv  % negative rank of focus sites per spec

USAGE
-----
  python 02b_sentiment_sensitivity.py
"""

import re

import pandas as pd

import common as c

SAFE_RE = re.compile(r"\b(safe|safer|safest|safely|safety)\b", re.I)

SPECS = {
    "A_original": lambda r: c.vader_compound(r["cleaned_text"], adjusted=False),
    "B_adjusted": lambda r: c.vader_compound(r["cleaned_text"], adjusted=True),
    "C_adjusted_case": lambda r: c.vader_compound(c.scrub_pii_keep_case(r["text"]), adjusted=True),
    "D_masked": lambda r: c.vader_compound(SAFE_RE.sub("xxx", r["cleaned_text"])
                                            if isinstance(r["cleaned_text"], str) else "", adjusted=False),
}


def main() -> None:
    posts = pd.read_csv(c.cleaned_file("posts"), low_memory=False)
    comments = c.analysis_comments(pd.read_csv(c.cleaned_file("comments"), low_memory=False)).copy()
    posts["text"], comments["text"] = posts["full_text"], comments["body"]

    for df in (posts, comments):
        for spec, fn in SPECS.items():
            df[spec] = df.apply(fn, axis=1)
            df[spec + "_cat"] = df[spec].apply(c.sentiment_category)
    assert (posts["A_original"] == posts["sentiment_compound"]).all()
    assert (comments["A_original"] == comments["sentiment_compound"]).all()
    assert (posts["B_adjusted"] == posts["sentiment_adj_compound"]).all()

    nb_sizes = {n: int(posts[c.slug(n, "vloc_")].sum() + comments[c.slug(n, "vloc_")].sum())
                for n in c.NEIGHBOURHOODS}
    sites = [n for n, k in sorted(nb_sizes.items(), key=lambda x: -x[1]) if k >= c.MIN_MENTIONS_FOCUS]

    rows, ranks = [], []
    for spec in SPECS:
        cat = spec + "_cat"
        row = {"spec": spec,
               "posts_mean": round(posts[spec].mean(), 3),
               "posts_pct_negative": round((posts[cat] == "negative").mean() * 100, 1),
               "posts_pct_positive": round((posts[cat] == "positive").mean() * 100, 1),
               "comments_mean": round(comments[spec].mean(), 3),
               "comments_pct_negative": round((comments[cat] == "negative").mean() * 100, 1)}
        site_neg = {}
        for s in sites:
            col = c.slug(s, "vloc_")
            both = pd.concat([posts.loc[posts[col], [spec, cat]], comments.loc[comments[col], [spec, cat]]])
            site_neg[s] = (both[cat] == "negative").mean() * 100
            if s in c.REPORT_SITES + ["Sutherland"]:
                key = c.slug(s)
                row[f"{key}_mean"] = round(both[spec].mean(), 3)
                row[f"{key}_pct_negative"] = round(site_neg[s], 1)
        order = sorted(site_neg, key=lambda s: -site_neg[s])
        for rank, s in enumerate(order, 1):
            ranks.append({"spec": spec, "rank_by_pct_negative": rank, "neighbourhood": s,
                          "pct_negative": round(site_neg[s], 1), "mentions": nb_sizes[s]})
        rows.append(row)

    out = pd.DataFrame(rows)
    rk = pd.DataFrame(ranks)
    a = c.out_dir("05_audits")
    out.to_csv(a / "sentiment_sensitivity.csv", index=False)
    rk.to_csv(a / "sentiment_sensitivity_ranking.csv", index=False)
    print(out.T.to_string(header=False))
    print("\nTop 3 focus sites by % negative under each spec:")
    for spec, g in rk.groupby("spec"):
        print(f"  {spec:16s} " + "; ".join(f"{r.neighbourhood} {r.pct_negative}%" for r in g.head(3).itertuples()))


if __name__ == "__main__":
    main()
