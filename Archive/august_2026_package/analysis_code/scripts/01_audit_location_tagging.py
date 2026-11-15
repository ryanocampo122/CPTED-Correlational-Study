"""
01_audit_location_tagging.py
=============================
CPTED Vision | Data quality audit of the neighbourhood tagger

PURPOSE
-------
The original scraper (initial_sraper.py) tags each post/comment with the
neighbourhoods it mentions using plain Python substring containment:

    if any(pattern in text.lower() for pattern in patterns):
        hits.append(neighbourhood_name)

This has no word-boundary check, so a short pattern can match *inside*
an unrelated word. The clearest case in this dataset: the "Riverbank /
Meewasin" category uses the bare pattern "river", which also matches
inside "driver" and "drivers" — both extremely common words in a
subreddit that discusses road/traffic safety.

This script:
  1. Re-implements both the ORIGINAL (raw substring) matcher and a
     CORRECTED (word-boundary regex) matcher for all 20 neighbourhood
     categories defined in the scraper.
  2. Runs both against every post and comment.
  3. Reports the false-positive rate per category, so we can see
     whether the issue is isolated to one category or systemic.

INPUT
-----
  data_pkg_august/01_raw_collection/saskatoon_safety_posts_20260611.csv
  data_pkg_august/01_raw_collection/saskatoon_safety_comments_20260611.csv

OUTPUT
------
  output/neighbourhood_tagging_audit.csv
      One row per neighbourhood category, with raw vs. corrected counts
      (posts and comments) and the implied false-positive rate.

FINDING (as of this run)
-------------------------
  Only "Riverbank / Meewasin" shows a material false-positive rate
  (~83% of both post and comment matches are false positives, driven
  almost entirely by "driver"/"drivers"). All other categories are
  clean (0-2% false-positive rate, mostly negligible rounding from
  overlapping substrings like "caswell" inside "caswell hill").

USAGE
-----
  python 01_audit_location_tagging.py
"""

import pandas as pd

from neighbourhoods import COMMENTS_PATH, NEIGHBOURHOODS, POSTS_PATH, bounded_match, raw_match

OUTPUT_PATH = "output/neighbourhood_tagging_audit.csv"


def main() -> None:
    posts = pd.read_csv(POSTS_PATH)
    comments = pd.read_csv(COMMENTS_PATH)

    rows = []
    for name, patterns in NEIGHBOURHOODS.items():
        posts_raw = posts["full_text"].apply(lambda t: raw_match(t, patterns))
        posts_corrected = posts["full_text"].apply(lambda t: bounded_match(t, patterns))
        comments_raw = comments["body"].apply(lambda t: raw_match(t, patterns))
        comments_corrected = comments["body"].apply(lambda t: bounded_match(t, patterns))

        rows.append({
            "neighbourhood": name,
            "posts_raw": int(posts_raw.sum()),
            "posts_corrected": int(posts_corrected.sum()),
            "comments_raw": int(comments_raw.sum()),
            "comments_corrected": int(comments_corrected.sum()),
        })

    audit = pd.DataFrame(rows)
    # False-positive rate = share of raw matches that disappear once we
    # require a word boundary. NaN where there were zero raw matches.
    audit["posts_fp_rate_pct"] = (
        1 - audit["posts_corrected"] / audit["posts_raw"].replace(0, pd.NA)
    ) * 100
    audit["comments_fp_rate_pct"] = (
        1 - audit["comments_corrected"] / audit["comments_raw"].replace(0, pd.NA)
    ) * 100
    audit = audit.sort_values("comments_raw", ascending=False).reset_index(drop=True)

    audit.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {OUTPUT_PATH}\n")
    print(audit.to_string(index=False))


if __name__ == "__main__":
    main()
