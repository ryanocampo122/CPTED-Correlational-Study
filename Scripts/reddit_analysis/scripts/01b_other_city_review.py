"""
01b_other_city_review.py
========================
UrbanSentinel-Prairie | Keep the other-city location review in sync

PURPOSE
-------
Word-boundary matching fixed "river" inside "driver", but it cannot tell
Saskatoon's downtown from Regina's. The August report quoted a comment that
begins "I operate buildings in downtown Regina" as evidence about Downtown/CBD.

This script lists every post/comment whose location match co-occurs with the
name of another city, and merges that list with the hand-made decisions in

    manual_review/location_other_city_review.csv

  - existing decisions are preserved exactly;
  - new candidates are appended with decision = "pending";
  - candidates that no longer match are reported, not deleted.

Only rows with decision = "exclude" remove a tag (see common.neighbourhood_tags).
"pending" rows are treated as "keep" but the script exits non-zero so they get
reviewed before results are reported.

OUTPUT
------
  manual_review/location_other_city_review.csv   (updated in place)

USAGE
-----
  python 01b_other_city_review.py
"""

import sys

import pandas as pd

import common as c

REVIEW_PATH = c.MANUAL_REVIEW_DIR / "location_other_city_review.csv"
COLUMNS = ["record_type", "record_id", "neighbourhood", "other_cities_mentioned",
           "decision", "reason", "reviewer", "review_date", "location_excerpt"]


def excerpt(text: str, patterns: list[str], width: int = 110) -> str:
    t = text.lower()
    m = c._bounded_re(tuple(patterns)).search(t)
    if not m:
        return ""
    s = text[max(0, m.start() - width): m.end() + width]
    return " ".join(s.split())


def candidates() -> pd.DataFrame:
    posts, comments = c.load_raw()
    rows = []
    for record_type, df, text_col, id_col in [("post", posts, "full_text", "id"),
                                              ("comment", comments, "body", "comment_id")]:
        for _, r in df.iterrows():
            text = r[text_col]
            cities = c.other_cities_mentioned(text)
            if not cities:
                continue
            for name, patterns in c.NEIGHBOURHOODS.items():
                if c.bounded_match(text, patterns):
                    rows.append({
                        "record_type": record_type, "record_id": str(r[id_col]),
                        "neighbourhood": name, "other_cities_mentioned": cities,
                        "location_excerpt": excerpt(text, patterns),
                    })
    return pd.DataFrame(rows)


def main() -> int:
    cand = candidates()
    key = ["record_type", "record_id", "neighbourhood"]
    if REVIEW_PATH.exists():
        review = pd.read_csv(REVIEW_PATH, dtype=str).fillna("")
    else:
        review = pd.DataFrame(columns=COLUMNS)

    merged = cand.merge(review[key + ["decision", "reason", "reviewer", "review_date"]],
                        on=key, how="left")
    merged["decision"] = merged["decision"].fillna("").replace("", "pending")
    merged = merged.fillna("")
    stale = review.merge(cand[key], on=key, how="left", indicator=True)
    stale = stale[stale["_merge"] == "left_only"]

    out = pd.concat([merged[COLUMNS], stale[COLUMNS]], ignore_index=True)
    out = out.sort_values(["neighbourhood", "decision", "record_type", "record_id"])
    out.to_csv(REVIEW_PATH, index=False)

    print(f"Candidates (location match + another city named): {len(cand)}")
    print(out.groupby(["neighbourhood", "decision"]).size().to_string())
    if len(stale):
        print(f"\n{len(stale)} reviewed rows no longer match any candidate (kept in file).")
    pending = (out["decision"] == "pending").sum()
    if pending:
        print(f"\n{pending} candidate(s) still pending review in {REVIEW_PATH}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
