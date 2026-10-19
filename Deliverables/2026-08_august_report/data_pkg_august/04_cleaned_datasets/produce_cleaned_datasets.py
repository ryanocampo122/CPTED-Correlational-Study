"""
Produces cleaned, row-level versions of the posts and comments datasets with
verified (word-boundary) neighbourhood location tags.

WHY THIS EXISTS
---------------
The original analysis applied word-boundary location matching in memory and
wrote out only aggregate summary tables. This script materialises the cleaned
row-level data itself, so the corrected tags are inspectable per-row rather than
only visible in aggregate.

WHAT IT DOES
------------
For each of the 21 tracked neighbourhood categories, adds a verified boolean
column (`vloc_*`) computed with word-boundary matching, alongside the original
`loc_*` columns where they exist. Also adds:

  - `vloc_any`            : True if any neighbourhood matched (verified)
  - `vloc_names`          : semicolon-joined list of verified matches
  - `vloc_n`              : count of verified matches
  - `tag_changed`         : True if verified tags differ from the original
                            `loc_*` columns for this row (only meaningful for
                            the six categories that had original loc_ columns)

The original columns are preserved untouched so the before/after is auditable.

OUTPUT
------
  output/saskatoon_safety_posts_20260611_CLEANED.csv
  output/saskatoon_safety_comments_20260611_CLEANED.csv
  output/cleaning_changelog.csv   (row-level record of what changed)
"""

import os
import sys
from pathlib import Path

import pandas as pd

# The vocabulary, matcher and raw-data folder are shared with the analysis scripts.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "analysis_code" / "scripts"))
from neighbourhoods import NEIGHBOURHOODS, RAW_DIR, bounded_match  # noqa: E402
from neighbourhoods import slug as column_name  # noqa: E402

OUT_DIR = "output"   # relative to the working folder, so the delivered files here are never overwritten


# Categories that have an original loc_* column in the raw files, so we can
# compare before/after. Others had no dedicated column.
ORIGINAL_LOC_COLUMNS = {
    "Pleasant Hill": "loc_pleasant_hill",
    "Riversdale": "loc_riversdale",
    "Downtown / CBD": "loc_downtown_cbd",
    "Downtown Terminal": "loc_downtown_terminal",
    "Confederation Mall": "loc_confederation_mall",
    "Riverbank / Meewasin": "loc_riverbank_meewasin",
}


def slug(name: str) -> str:
    return column_name(name, "vloc_")


def clean(df: pd.DataFrame, text_col: str, id_col: str, kind: str):
    """Adds verified location columns and returns (cleaned_df, changelog_df)."""
    changes = []

    for name, patterns in NEIGHBOURHOODS.items():
        df[slug(name)] = df[text_col].apply(lambda t: bounded_match(t, patterns))

    vcols = [slug(n) for n in NEIGHBOURHOODS]
    df["vloc_any"] = df[vcols].any(axis=1)
    df["vloc_n"] = df[vcols].sum(axis=1)
    df["vloc_names"] = df.apply(
        lambda r: ";".join(n for n in NEIGHBOURHOODS if r[slug(n)]), axis=1
    )

    # Compare against original columns where they exist
    changed_mask = pd.Series(False, index=df.index)
    for name, orig_col in ORIGINAL_LOC_COLUMNS.items():
        if orig_col not in df.columns:
            continue
        orig = df[orig_col].fillna(False).astype(bool)
        new = df[slug(name)]
        diff = orig != new
        changed_mask |= diff
        for idx in df.index[diff]:
            changes.append({
                "record_type": kind,
                "record_id": df.at[idx, id_col],
                "neighbourhood": name,
                "original_tag": bool(orig.at[idx]),
                "verified_tag": bool(new.at[idx]),
                "change": "removed (unrelated match)" if orig.at[idx] and not new.at[idx]
                          else "added",
                "text_excerpt": str(df.at[idx, text_col])[:180].replace("\n", " "),
            })

    df["tag_changed"] = changed_mask
    return df, pd.DataFrame(changes)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    posts = pd.read_csv(f"{RAW_DIR}/saskatoon_safety_posts_20260611.csv", low_memory=False)
    comments = pd.read_csv(f"{RAW_DIR}/saskatoon_safety_comments_20260611.csv", low_memory=False)

    posts_clean, posts_log = clean(posts, "full_text", "id", "post")
    comments_clean, comments_log = clean(comments, "body", "comment_id", "comment")

    posts_clean.to_csv(f"{OUT_DIR}/saskatoon_safety_posts_20260611_CLEANED.csv", index=False)
    comments_clean.to_csv(f"{OUT_DIR}/saskatoon_safety_comments_20260611_CLEANED.csv", index=False)

    changelog = pd.concat([posts_log, comments_log], ignore_index=True)
    changelog.to_csv(f"{OUT_DIR}/cleaning_changelog.csv", index=False)

    print(f"Posts cleaned:    {len(posts_clean):,} rows, "
          f"{posts_clean['tag_changed'].sum()} rows with tag changes")
    print(f"Comments cleaned: {len(comments_clean):,} rows, "
          f"{comments_clean['tag_changed'].sum()} rows with tag changes")
    print(f"Changelog:        {len(changelog):,} individual tag changes")
    print()
    print("Changes by neighbourhood:")
    print(changelog.groupby(["neighbourhood", "change"]).size().to_string())


if __name__ == "__main__":
    main()
