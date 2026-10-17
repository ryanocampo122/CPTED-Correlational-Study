"""
05_extract_example_quotes.py
==============================
UrbanSentinel-Prairie | Pull representative example comments for the report

PURPOSE
-------
Grabs a handful of real, anonymized example comments for the two focus
sites (Downtown/CBD and Riverbank/Meewasin, corrected), used as
illustrative quotes in Sections 4-5 of the August report. Comments are
selected by Reddit score (proxy for community agreement/visibility) and
capped in length; no usernames are included (author identity was already
SHA-256 hashed by the original scraper, see initial_sraper.py).

INPUT
-----
  /mnt/user-data/uploads/saskatoon_safety_comments_20260611.csv

OUTPUT
------
  output/genuine_negative_river_comments.csv       (Meewasin, negative, corrected)
  output/genuine_positive_river_comments_sample.csv (Meewasin, positive, corrected)
  output/downtown_negative_comments_sample.csv      (Downtown/CBD, negative)

NOTE
----
The Meewasin extraction uses the CORRECTED word-boundary matcher (see
01_audit_location_tagging.py) — NOT the original loc_riverbank_meewasin
column, which needs correcting for false positives. The Downtown/CBD extraction uses the original
loc_downtown_cbd column directly, since script 01 confirmed that
category's false-positive rate is negligible (0-1%).

USAGE
-----
  python 05_extract_example_quotes.py
"""

import re
import pandas as pd

COMMENTS_PATH = "/mnt/user-data/uploads/saskatoon_safety_comments_20260611.csv"

MEEWASIN_PATTERNS = ["river", "meewasin", "riverbank", "river trail"]


def bounded_match(text: str, patterns: list[str]) -> bool:
    if not isinstance(text, str):
        return False
    t = text.lower()
    return any(re.search(r"\b" + re.escape(p) + r"\b", t) for p in patterns)


def main() -> None:
    comments = pd.read_csv(COMMENTS_PATH)
    comments["river_real"] = comments["body"].apply(lambda t: bounded_match(t, MEEWASIN_PATTERNS))

    # --- Riverbank / Meewasin, corrected ---
    real_comm = comments[comments["river_real"]]

    neg = real_comm[real_comm["sentiment_category"] == "negative"].sort_values("score", ascending=False)
    neg[["comment_id", "score", "time_of_day", "created_date", "env_lighting", "body"]].to_csv(
        "output/genuine_negative_river_comments.csv", index=False)

    pos = real_comm[real_comm["sentiment_category"] == "positive"].sort_values("score", ascending=False)
    pos[["comment_id", "score", "time_of_day", "created_date", "body"]].head(10).to_csv(
        "output/genuine_positive_river_comments_sample.csv", index=False)

    print(f"Meewasin (corrected): {len(neg)} negative, {len(pos)} positive genuine comments")

    # --- Downtown / CBD (original column is reliable, see script 01) ---
    downtown_neg = comments[
        (comments["loc_downtown_cbd"]) & (comments["sentiment_category"] == "negative")
    ].sort_values("score", ascending=False)
    downtown_neg[["comment_id", "score", "time_of_day", "created_date", "body"]].head(15).to_csv(
        "output/downtown_negative_comments_sample.csv", index=False)

    print(f"Downtown/CBD: {len(downtown_neg)} negative comments (top 15 saved)")
    print("\nReminder: 'downtown' is a generic term. Before quoting any Downtown/CBD")
    print("comment, spot-check that it's actually about Saskatoon and not another city")
    print("mentioned in the same thread (see Section 2 caveat in the August report).")


if __name__ == "__main__":
    main()
