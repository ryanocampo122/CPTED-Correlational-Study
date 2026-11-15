"""
01c_audit_env_cues.py
=====================
CPTED Vision | Audit of the environmental-cue tagger

PURPOSE
-------
The scraper's env_* columns were produced with substring matching, the same
bug as "river" in "driver", and were never corrected in the August package.
This script measures the damage and documents the corrected tags:

  original        the env_* column as stored (substring match)
  word_boundary   the original terms matched as whole words, nothing else
  corrected       common.ENV_CUES: whole words + inflections - non-
                  environmental senses (the definition used from October 2026)

It also lists the words that triggered the original substring match without
being a cue word ("police" -> "ice"), and summarises the judged precision
of the corrected tags from manual_review/env_cue_validation_heldout.csv.

OUTPUT
------
  05_audits/env_cue_tagging_audit.csv
  05_audits/env_cue_false_trigger_words.csv
  05_audits/env_cue_precision_heldout.csv

USAGE
-----
  python 01c_audit_env_cues.py
"""

import re
from collections import Counter

import pandas as pd

import common as c


def false_triggers(texts: pd.Series, cue: str, corrected: pd.Series) -> Counter:
    """Whole words containing an original pattern, in texts that the
    original tagger flagged but the corrected tagger does not."""
    pats = c.ENV_CUES_ORIGINAL[cue]
    word_re = re.compile(r"[a-z0-9']+")
    cnt = Counter()
    for t in texts[~corrected]:
        if not isinstance(t, str):
            continue
        for w in word_re.findall(t.lower()):
            if any(p in w for p in pats if " " not in p):
                cnt[w] += 1
    return cnt


def main() -> None:
    posts, comments = c.load_raw()
    audit_rows, trigger_rows = [], []

    for kind, df, text_col in [("posts", posts, "full_text"), ("comments", comments, "body")]:
        for cue in c.ENV_CUE_NAMES:
            stored = df[f"env_{cue}"].astype(bool)
            recomputed = df[text_col].apply(lambda t: c.original_cue_flag(t, cue))
            wb = df[text_col].apply(lambda t: c.bounded_match(t, c.ENV_CUES_ORIGINAL[cue]))
            corrected = df[text_col].apply(lambda t: c.cue_flag(t, cue))
            if c.is_substring_collection():
                assert (stored == recomputed).all(), f"stored env_{cue} does not reproduce"
            else:
                # October scraper already stores the corrected tags; "original" is
                # what the June substring tagger would have produced on this text.
                assert (stored == corrected).all(), f"stored env_{cue} != corrected definition"
                stored = recomputed
            audit_rows.append({
                "record_type": kind, "cue": cue,
                "original": int(stored.sum()),
                "word_boundary_only": int(wb.sum()),
                "corrected": int(corrected.sum()),
                "pct_of_original_not_confirmed": round((1 - (stored & corrected).sum() / stored.sum()) * 100, 1),
                "added_by_inflections": int((corrected & ~stored).sum()),
            })
            for w, n in false_triggers(df[text_col], cue, corrected & stored).most_common(25):
                trigger_rows.append({"record_type": kind, "cue": cue, "word": w, "count": n})

    audit = pd.DataFrame(audit_rows)
    triggers = pd.DataFrame(trigger_rows)
    triggers = triggers[~triggers.apply(
        lambda r: bool(c.cue_hits(r["word"], r["cue"])), axis=1)]

    val = pd.read_csv(c.MANUAL_REVIEW_DIR / "env_cue_validation_heldout.csv")
    prec = []
    for cue, g in val.groupby("cue"):
        k, n = int(g["judged_correct"].sum()), len(g)
        lo, hi = c.wilson_ci(k, n)
        ra = pd.to_numeric(g["ra_judgement"], errors="coerce")
        prec.append({"cue": cue, "n_judged": n, "n_correct": k,
                     "precision": round(k / n, 3), "ci95_low": round(lo, 3), "ci95_high": round(hi, 3),
                     "n_ra_judged": int(ra.notna().sum()),
                     "agreement_with_ra": round((ra == g["judged_correct"])[ra.notna()].mean(), 3)
                     if ra.notna().any() else None,
                     "note": "Held-out sample judged before final exclusions were added; "
                             "true precision of the shipped definition is at least this."})
    prec = pd.DataFrame(prec)

    d = c.out_dir("05_audits")
    audit.to_csv(d / "env_cue_tagging_audit.csv", index=False)
    triggers.to_csv(d / "env_cue_false_trigger_words.csv", index=False)
    prec.to_csv(d / "env_cue_precision_heldout.csv", index=False)
    print(audit.to_string(index=False))
    print()
    print(prec[["cue", "n_correct", "n_judged", "precision", "ci95_low", "ci95_high"]].to_string(index=False))
    print("\nTop false triggers (comments):")
    t = triggers[triggers["record_type"] == "comments"]
    for cue, g in t.groupby("cue"):
        print(f"  {cue:12s} " + ", ".join(f"{w} ({n})" for w, n in zip(g["word"].head(6), g["count"].head(6))))


if __name__ == "__main__":
    main()
