"""
05_extract_example_quotes.py
==============================
ComputerVision_Sentinel | Candidate example comments for report quote blocks

PURPOSE
-------
Pulls the highest-scored negative / positive comments for the two report sites
using the FINAL location tags (word boundary + other-city exclusions) and the
adjusted sentiment. The August version used the raw loc_downtown_cbd column,
which is how a comment about downtown Regina ended up quoted as evidence about
Saskatoon.

Every row carries `other_cities_mentioned` so a quote can be checked before use.
Comments that mention another city at all are kept out of the samples unless
their review decision was "keep".

ETHICS NOTE
-----------
These are verbatim public comments with their comment_id, which makes them
searchable and re-identifiable. The collection protocol in initial_sraper.py
says there is no direct quotation of users in any publication without a
separate consent process. Paraphrase in anything that leaves the team, and
confirm the approach with the REB.

INPUT
-----
  04_cleaned_datasets/saskatoon_safety_comments_<stamp>_CLEANED_v2.csv
  (comments posted after the collection window are left out)

OUTPUT
------
  03_extracted_comment_samples/riverbank_negative_comments.csv   (all)
  03_extracted_comment_samples/riverbank_positive_comments_top10.csv
  03_extracted_comment_samples/downtown_negative_comments_top15.csv
  03_extracted_comment_samples/sutherland_negative_comments.csv  (all)

USAGE
-----
  python 05_extract_example_quotes.py
"""

import pandas as pd

import common as c

COLS = ["comment_id", "parent_post_id", "score", "local_time_of_day", "local_date",
        "sentiment_adj_compound", "sentiment_compound", "venv_names",
        "other_cities_mentioned", "body"]


def main() -> None:
    comments = c.analysis_comments(pd.read_csv(c.cleaned_file("comments"), low_memory=False)).copy()
    comments["other_cities_mentioned"] = comments["body"].apply(c.other_cities_mentioned)
    comments["venv_names"] = comments[[f"venv_{q}" for q in c.ENV_CUE_NAMES]].apply(
        lambda r: ";".join(q for q in c.ENV_CUE_NAMES if r[f"venv_{q}"]), axis=1)

    out = c.out_dir("03_extracted_comment_samples")

    def pick(site: str, category: str, top: int | None, fname: str) -> int:
        """Write one site x sentiment sample, highest score first. Returns the row count."""
        sub = comments[comments[c.slug(site, "vloc_")] & (comments["sentiment_adj_category"] == category)]
        sub = sub.sort_values("score", ascending=False)
        if top:
            sub = sub.head(top)
        sub[COLS].to_csv(out / fname, index=False)
        return len(sub)

    n1 = pick("Riverbank / Meewasin", "negative", None, "riverbank_negative_comments.csv")
    n2 = pick("Riverbank / Meewasin", "positive", 10, "riverbank_positive_comments_top10.csv")
    n3 = pick("Downtown / CBD", "negative", 15, "downtown_negative_comments_top15.csv")
    n4 = pick("Sutherland", "negative", None, "sutherland_negative_comments.csv")
    print(f"Riverbank negative: {n1}, Riverbank positive (top): {n2}, "
          f"Downtown negative (top): {n3}, Sutherland negative: {n4}")
    print("Reminder: paraphrase rather than quote verbatim outside the team (see ETHICS NOTE).")


if __name__ == "__main__":
    main()
