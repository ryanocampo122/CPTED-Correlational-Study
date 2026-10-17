# UrbanSentinel-Prairie — Data Package

All data used in the August 2026 analysis, organised by provenance: what was
collected, what was derived from it, and which comment samples were pulled for
the report's quote blocks.

Source: r/saskatoon, collection window 11 Jun 2025 – 11 Jun 2026.
Collection run: 2026-06-11 21:02 UTC.

---

## 01_raw_collection/ — as collected, unmodified

The original scraper output. **Nothing in this folder has been altered.** The
data cleaning described in the report was applied downstream, in the derived
tables, not to these files.

| File | Contents |
|---|---|
| `saskatoon_safety_posts_20260611.csv` | 426 rows × 53 cols — one row per post, with VADER sentiment, time-of-day/season buckets, `loc_*` neighbourhood flags, `env_*` environmental cue flags |
| `saskatoon_safety_comments_20260611.csv` | 14,889 rows × 44 cols — one row per comment, same sentiment/cue structure, linked to posts via `parent_post_id` |
| `saskatoon_safety_gis_20260611.csv` | 90 rows × 12 cols — one row per neighbourhood-mention, formatted for GIS import |
| `saskatoon_safety_metadata_20260611.json` | Run parameters: seed terms, window, counts, categories tracked |
| `saskatoon_safety_summary_20260611.txt` | Human-readable summary produced at collection time |
| `urbansentinel_scraper.log` | Full run log (PRAW init, per-term searches, comment collection progress) |
| `initial_sraper.py` | The collection script itself, included so the tagging logic is inspectable |

**Note on the location flags in these files.** The `loc_riverbank_meewasin`
column in the posts and comments CSVs reflects the original text-containment
matching, which also captured unrelated words containing "river" (chiefly
"driver"/"drivers"). Do not cite Riverbank/Meewasin figures from this column —
use the cleaned datasets in `04_cleaned_datasets/` or the verified aggregates in
`02_derived_analysis/`. All other `loc_*` columns were checked and are accurate
(0–2% affected).

**Privacy note.** Author identities were hashed at collection time
(`author_hash`); no usernames appear in any file. Comment text is reproduced as
posted publicly on Reddit.

---

## 02_derived_analysis/ — verified analysis tables

Produced by scripts 01 and 02 of the analysis code. These reproduce
byte-for-byte from the raw files above.

| File | Contents |
|---|---|
| `neighbourhood_tagging_audit.csv` | 21 rows — per-category comparison of original vs. word-boundary matching, with the share affected. This is the evidence base for the cleaning step described in the report |
| `neighbourhood_summary_corrected.csv` | 21 rows — verified mention counts, mean sentiment, % negative, and negative count per neighbourhood |
| `env_cues_by_site.csv` | 6 rows — rate at which each environmental cue (lighting, noise, weather, time-of-day language, people/isolation) co-occurs with negative comments, for the six focus sites |
| `time_of_day_by_site.csv` | 24 rows — mean sentiment and sample size per time-of-day bucket, per focus site |
| `seasonal_trend.csv` | 4 rows — citywide post volume and mean sentiment by season |

Sentiment values are VADER compound scores, ranging −1 (most negative) to +1
(most positive). `n` columns are sample sizes — worth checking before reading
much into any single figure, since several sites have small bases.

---

## 03_extracted_comment_samples/ — quoted material

The specific comments drawn on for the report's illustrative quotes, so each
quote is traceable to its source row.

| File | Contents |
|---|---|
| `genuine_negative_river_comments.csv` | All 26 verified negative Riverbank/Meewasin comments, sorted by score |
| `genuine_positive_river_comments_sample.csv` | Top 10 verified positive Riverbank/Meewasin comments |
| `downtown_negative_comments_sample.csv` | Top 15 negative Downtown/CBD comments by score |

Each includes `comment_id`, `score`, `time_of_day`, `created_date`, and full
`body` text.

---

## 04_cleaned_datasets/ — cleaned row-level data

The row-level datasets with verified location tags. Produced by
`produce_cleaned_datasets.py` (included in this folder).

Worth knowing how this relates to the rest of the package: the original analysis
applied word-boundary matching **in memory** and saved only the aggregate tables
in `02_derived_analysis/`. The cleaned row-level data was never written out at
that time. This folder materialises it, so the verified tags can be inspected
per-row rather than only in aggregate.

| File | Contents |
|---|---|
| `saskatoon_safety_posts_20260611_CLEANED.csv` | 426 rows — all original columns preserved, plus verified `vloc_*` tags for all 21 categories |
| `saskatoon_safety_comments_20260611_CLEANED.csv` | 14,889 rows — same structure |
| `cleaning_changelog.csv` | 607 rows — one per individual tag change, with a text excerpt showing what triggered the original match |
| `produce_cleaned_datasets.py` | The script that generated the above |

### Columns added

| Column | Meaning |
|---|---|
| `vloc_<neighbourhood>` | Verified boolean tag, word-boundary matched (21 columns) |
| `vloc_any` | True if any neighbourhood matched |
| `vloc_n` | Count of verified matches for the row |
| `vloc_names` | Semicolon-joined names of verified matches |
| `tag_changed` | True if the verified tags differ from the original `loc_*` for this row |

**Original columns are left untouched**, so every before/after comparison stays
auditable. The `loc_*` and `vloc_*` columns sit side by side.

### What changed

607 individual tag changes across 38 posts and 569 comments, all removals of
unrelated matches:

| Category | Removals | Cause |
|---|---|---|
| Riverbank / Meewasin | 603 | "river" matching inside "driver" / "drivers" |
| Downtown / CBD | 3 | 2 from "cbd" appearing inside Reddit image-URL hash strings; 1 from "downtowns" in a comment about other cities' downtowns generally |
| Downtown Terminal | 1 | "bus terminal" in a comment about Vancouver transit, not Saskatoon |

The three Downtown/CBD removals are the concrete instances of the generic-term
caveat noted in the report. They are a rounding-level effect (3 of 306), but the
last two illustrate the pattern worth spot-checking by hand: a comment can
mention "downtown" while discussing a different city entirely.

### Verification

The cleaned datasets reconcile exactly against the published aggregates — all 21
neighbourhood totals match, and mean sentiment for both focus sites agrees to
three decimal places (Downtown/CBD +0.059, Riverbank/Meewasin +0.325).

---

## Reproducing the derived tables

From the `analysis_code/` folder in the deliverable package:

```bash
pip install -r requirements.txt
python3 scripts/01_audit_location_tagging.py
python3 scripts/02_corrected_analysis.py
```

Both scripts read from the raw CSV paths defined at the top of each file — point
those at `01_raw_collection/` if running outside the original environment.

To regenerate the cleaned row-level datasets:

```bash
python3 04_cleaned_datasets/produce_cleaned_datasets.py
```

This reads only from `01_raw_collection/` and rewrites everything in
`04_cleaned_datasets/`. It requires pandas and nothing else.
