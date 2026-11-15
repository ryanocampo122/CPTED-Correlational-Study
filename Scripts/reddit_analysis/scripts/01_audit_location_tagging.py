"""
01_audit_location_tagging.py
=============================
CPTED Vision | Audit of the neighbourhood tagger

PURPOSE
-------
Compares three versions of every neighbourhood tag, for posts and comments:

  raw            the scraper's original substring match ("river" in "driver")
  word_boundary  the same patterns matched as whole words (August 2026 fix)
  final          word boundary, minus reviewed references to other
                 cities' downtowns/rivers (October 2026, see
                 manual_review/location_other_city_review.csv)

Sutherland was not tracked in the June collection; it appears with
raw = word_boundary computed here for comparison.

OUTPUT
------
  05_audits/neighbourhood_tagging_audit.csv

USAGE
-----
  python 01_audit_location_tagging.py
"""

import pandas as pd

import common as c


def main() -> None:
    posts, comments = c.load_raw()
    c.neighbourhood_tags(posts, "full_text", "id", "post")
    c.neighbourhood_tags(comments, "body", "comment_id", "comment")

    rows = []
    for name, patterns in c.NEIGHBOURHOODS.items():
        col = c.slug(name, "vloc_")
        row = {"neighbourhood": name,
               "tracked_in_june_collection": name in c.NEIGHBOURHOODS_ORIGINAL}
        for kind, df, text_col in [("posts", posts, "full_text"), ("comments", comments, "body")]:
            raw = df[text_col].apply(lambda t: c.substring_match(t, patterns))
            wb = df[text_col].apply(lambda t: c.bounded_match(t, patterns))
            row[f"{kind}_raw"] = int(raw.sum())
            row[f"{kind}_word_boundary"] = int(wb.sum())
            row[f"{kind}_final"] = int(df[col].sum())
        for stage in ["raw", "word_boundary", "final"]:
            row[f"total_{stage}"] = row[f"posts_{stage}"] + row[f"comments_{stage}"]
        row["removed_by_word_boundary"] = row["total_raw"] - row["total_word_boundary"]
        row["removed_as_other_city"] = row["total_word_boundary"] - row["total_final"]
        row["pct_of_raw_removed"] = (
            round((1 - row["total_final"] / row["total_raw"]) * 100, 1) if row["total_raw"] else None
        )
        rows.append(row)

    audit = pd.DataFrame(rows).sort_values("total_raw", ascending=False)
    path = c.out_dir("05_audits") / "neighbourhood_tagging_audit.csv"
    audit.to_csv(path, index=False)
    print(f"Wrote {path}\n")
    print(audit[["neighbourhood", "total_raw", "total_word_boundary", "total_final",
                 "removed_by_word_boundary", "removed_as_other_city",
                 "pct_of_raw_removed"]].to_string(index=False))


if __name__ == "__main__":
    main()
