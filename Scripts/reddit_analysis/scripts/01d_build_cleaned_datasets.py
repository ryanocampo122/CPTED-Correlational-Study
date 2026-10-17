"""
01d_build_cleaned_datasets.py
=============================
UrbanSentinel-Prairie | Row-level cleaned datasets (October 2026 corrections)

PURPOSE
-------
Writes the posts and comments with every correction applied as NEW columns.
Original columns are never modified, so every before/after stays auditable.
Supersedes the August produce_cleaned_datasets.py, which corrected location
tags only.

COLUMNS ADDED
-------------
  vloc_<area>            final location tag: word-boundary match minus
                         hand-reviewed other-city references (22 areas,
                         Sutherland included)
  vloc_any / vloc_n / vloc_names
  thread_vloc_<area>     comments only: True if the comment OR its parent post
                         is tagged (thread-context sensitivity analysis)
  venv_<cue>             corrected environmental cue (whole words, minus
                         non-environmental senses)
  venv_<cue>_terms       the words that triggered it
  venv_n
  sentiment_adj_compound / sentiment_adj_category
                         VADER with the seed-term lexicon fix (see common.py);
                         scored on the same cleaned_text as the original
  local_*                local (America/Regina) date, month, weekday, hour,
                         season, time of day
  thread_id              post id (posts) / parent post id (comments)
  loc_tag_changed        any of the six original loc_* tags differs from vloc_*
  env_tag_changed        any original env_* tag differs from venv_*

OUTPUT
------
  04_cleaned_datasets/saskatoon_safety_posts_<stamp>_CLEANED_v2.csv
  04_cleaned_datasets/saskatoon_safety_comments_<stamp>_CLEANED_v2.csv
  (<stamp> = the raw collection's date stamp, e.g. 20260611 or 20261016)
  04_cleaned_datasets/location_changelog.csv   one row per location tag change
  04_cleaned_datasets/env_cue_changelog.csv    one row per cue tag change

USAGE
-----
  python 01d_build_cleaned_datasets.py
"""

import pandas as pd

import common as c


LOC_LOG_COLS = ["record_type", "record_id", "neighbourhood", "original_tag", "word_boundary_tag",
                "final_tag", "stage", "had_loc_column", "text_excerpt"]
ENV_LOG_COLS = ["record_type", "record_id", "cue", "original_tag", "corrected_tag", "change",
                "original_trigger_patterns", "corrected_terms", "text_excerpt"]


def excerpt(text, n: int = 180) -> str:
    return " ".join(str(text)[:n].split()) if isinstance(text, str) else ""


def build(df: pd.DataFrame, record_type: str, text_col: str, id_col: str):
    df = df.copy()
    c.neighbourhood_tags(df, text_col, id_col, record_type)
    vcols = [c.slug(n, "vloc_") for n in c.NEIGHBOURHOODS]
    df["vloc_any"] = df[vcols].any(axis=1)
    df["vloc_n"] = df[vcols].sum(axis=1)
    df["vloc_names"] = df[vcols].apply(
        lambda r: ";".join(n for n, col in zip(c.NEIGHBOURHOODS, vcols) if r[col]), axis=1)

    for cue in c.ENV_CUE_NAMES:
        hits = df[text_col].apply(lambda t, q=cue: c.cue_hits(t, q))
        df[f"venv_{cue}"] = hits.apply(bool)
        df[f"venv_{cue}_terms"] = hits.apply(lambda h: ";".join(sorted(set(h))))
    df["venv_n"] = df[[f"venv_{q}" for q in c.ENV_CUE_NAMES]].sum(axis=1)

    df["sentiment_adj_compound"] = df["cleaned_text"].apply(c.vader_compound)
    df["sentiment_adj_category"] = df["sentiment_adj_compound"].apply(c.sentiment_category)

    c.add_local_time(df)
    df["thread_id"] = c.thread_id(df, record_type)

    loc_changes, env_changes = [], []
    changed = pd.Series(False, index=df.index)
    # June files store substring loc_* tags for 6 of the 21 original areas; October
    # files store whole-word loc_* tags for all 22 (Sutherland included).
    vocab = c.NEIGHBOURHOODS_ORIGINAL if c.is_substring_collection() else c.NEIGHBOURHOODS
    for name, patterns in vocab.items():
        orig_col = c.slug(name, "loc_") if c.slug(name, "loc_") in df.columns else None
        orig = (df[orig_col].astype(bool) if orig_col
                else df[text_col].apply(lambda t, p=patterns: c.substring_match(t, p)))
        wb = df[text_col].apply(lambda t, p=patterns: c.bounded_match(t, p))
        final = df[c.slug(name, "vloc_")]
        if orig_col:
            changed |= orig != final
        for idx in df.index[(orig != final)]:
            stage = ("word boundary (August 2026)" if orig[idx] != wb[idx]
                     else "other-city exclusion (October 2026)")
            loc_changes.append({
                "record_type": record_type, "record_id": df.at[idx, id_col],
                "neighbourhood": name, "original_tag": bool(orig[idx]),
                "word_boundary_tag": bool(wb[idx]), "final_tag": bool(final[idx]),
                "stage": stage, "had_loc_column": bool(orig_col),
                "text_excerpt": excerpt(df.at[idx, text_col]),
            })
    df["loc_tag_changed"] = changed

    env_changed = pd.Series(False, index=df.index)
    for cue in c.ENV_CUE_NAMES:
        orig = df[f"env_{cue}"].astype(bool)
        new = df[f"venv_{cue}"]
        diff = orig != new
        env_changed |= diff
        for idx in df.index[diff]:
            t = df.at[idx, text_col]
            low = t.lower() if isinstance(t, str) else ""
            trig = sorted({p for p in c.ENV_CUES_ORIGINAL[cue] if p in low})
            env_changes.append({
                "record_type": record_type, "record_id": df.at[idx, id_col], "cue": cue,
                "original_tag": bool(orig[idx]), "corrected_tag": bool(new[idx]),
                "change": "removed" if orig[idx] else "added",
                "original_trigger_patterns": ";".join(trig),
                "corrected_terms": df.at[idx, f"venv_{cue}_terms"],
                "text_excerpt": excerpt(t),
            })
    df["env_tag_changed"] = env_changed
    return df, pd.DataFrame(loc_changes, columns=LOC_LOG_COLS), pd.DataFrame(env_changes, columns=ENV_LOG_COLS)


def add_thread_tags(comments: pd.DataFrame, posts: pd.DataFrame) -> None:
    for name in c.NEIGHBOURHOODS:
        col = c.slug(name, "vloc_")
        tagged_posts = set(posts.loc[posts[col], "id"].astype(str))
        comments[f"thread_{col}"] = comments[col] | comments["parent_post_id"].astype(str).isin(tagged_posts)


def main() -> None:
    posts, comments = c.load_raw()
    posts2, p_loc, p_env = build(posts, "post", "full_text", "id")
    comments2, c_loc, c_env = build(comments, "comment", "body", "comment_id")
    add_thread_tags(comments2, posts2)

    d = c.out_dir("04_cleaned_datasets")
    posts2.to_csv(c.cleaned_file("posts"), index=False)
    comments2.to_csv(c.cleaned_file("comments"), index=False)
    loc_log = pd.concat([p_loc, c_loc], ignore_index=True)
    env_log = pd.concat([p_env, c_env], ignore_index=True)
    loc_log.to_csv(d / "location_changelog.csv", index=False)
    env_log.to_csv(d / "env_cue_changelog.csv", index=False)

    print(f"Posts:    {len(posts2):,} rows ({posts2['loc_tag_changed'].sum()} location-changed, "
          f"{posts2['env_tag_changed'].sum()} cue-changed)")
    print(f"Comments: {len(comments2):,} rows ({comments2['loc_tag_changed'].sum()} location-changed, "
          f"{comments2['env_tag_changed'].sum()} cue-changed)")
    print(f"\nLocation changelog: {len(loc_log):,} tag changes")
    if len(loc_log):
        print(loc_log.groupby(["neighbourhood", "stage"]).size().to_string())
    print(f"\nCue changelog: {len(env_log):,} tag changes")
    if len(env_log):
        print(env_log.groupby(["cue", "change"]).size().to_string())


if __name__ == "__main__":
    main()
