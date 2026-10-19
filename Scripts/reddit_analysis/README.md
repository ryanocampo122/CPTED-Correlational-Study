# ComputerVision_Sentinel: Reddit analysis pipeline

Turns a raw r/saskatoon collection into cleaned row-level data, analysis tables,
charts, audits and a verification report. It runs on either collection:

| Dataset (`Data/<dataset>/`) | Window | Scraper | Status |
|---|---|---|---|
| `reddit_2026-06-01_2026-08-31` | 1 Jun – 31 Aug 2026 (study period) | `reddit_scraper.py` (Oct 2026) | **current** |
| `reddit_2025-06-11_2026-06-11` | 11 Jun 2025 – 11 Jun 2026 | `initial_sraper.py` (Jun 2026) | earlier; behind the August report |

Both published output sets reproduce byte-for-byte from the raw files (checked
16 Oct 2026; `./flight --execute_flight` re-checks it on every run).

## What changed since August

| Problem | Fix | Where |
|---|---|---|
| Location tags matched inside words (`river` in `driver`) | Whole-word matching (August fix, kept) | `common.bounded_match` |
| "Downtown" sometimes meant Regina's, Calgary's… downtown; a Regina comment was quoted in the August report | 76 candidate records read by hand; 15 excluded | `manual_review/location_other_city_review.csv`, `01b` |
| Sutherland never tracked, although the survey draft cites it | Added as a 22nd area (53 mentions, all checked) | `common.NEIGHBOURHOODS_ADDED` |
| Environmental cues matched inside words (`ice` in `police`, `lit` in `little`, `late` in `plate`); never corrected in August | Whole words + inflections − explicit non-environmental senses; accuracy hand-checked | `common.ENV_CUES`, `01c`, `manual_review/env_cue_validation_heldout.csv` |
| VADER scores the seed words `safe`/`safety` as positive and has no entry for `unsafe`, `sketchy`, `afraid` | Adjusted lexicon is primary; original kept alongside; 4-way sensitivity analysis | `common.VADER_LEXICON_ADJUSTMENTS`, `02b` |
| Month, season and weekday taken from UTC | Local `America/Regina` time fields | `common.add_local_time` |
| No uncertainty; "Downtown negative only at night" read off a −0.004 mean (n=40) | 95% CIs from a bootstrap that resamples whole threads; explicit night-vs-other contrasts | `02` |
| `02_corrected_analysis.py` corrupted by stray vim keystrokes | Restored, then rewritten | `02_corrected_analysis.py` |
| Absolute sandbox paths (`/mnt/user-data/…`, `/home/…`) | Paths discovered automatically or set by environment variable | `common.raw_dir` |
| Pattern list copied by hand into 4 scripts | One definition in `common.py`; `08` checks it against the scraper that produced the data | `common.py`, `08` |

## Pipeline

| # | Script | Writes |
|---|---|---|
| — | `common.py` | shared vocabularies, matchers, paths, sentiment, time, statistics |
| 01 | `01_audit_location_tagging.py` | `05_audits/neighbourhood_tagging_audit.csv` (raw → word boundary → final) |
| 01b | `01b_other_city_review.py` | updates `manual_review/location_other_city_review.csv`; exits 1 if any candidate is `pending` |
| 01c | `01c_audit_env_cues.py` | `05_audits/env_cue_tagging_audit.csv`, `env_cue_false_trigger_words.csv`, `env_cue_precision_heldout.csv` |
| 01d | `01d_build_cleaned_datasets.py` | `04_cleaned_datasets/*_CLEANED_v2.csv`, `location_changelog.csv`, `env_cue_changelog.csv` |
| 02 | `02_corrected_analysis.py` | `02_derived_analysis/*.csv` (incl. `monthly_trend.csv`) |
| 02b | `02b_sentiment_sensitivity.py` | `05_audits/sentiment_sensitivity*.csv` |
| 03 | `03_generate_charts.py` | `charts/chart1…7.png` |
| 04 | `04_build_excel_workbook.py` | `ComputerVision_Sentinel_DataTables_corrected.xlsx` |
| 05 | `05_extract_example_quotes.py` | `03_extracted_comment_samples/*.csv` |
| 08 | `08_verify_outputs.py` | `05_audits/verification_report.txt`, `august_document_claims_check.csv`; exits 1 on any failed check |
| 06, 07 | `*.js` | **archival**: rebuild the August memo/report exactly as sent (old numbers). Not run. |

## Running

From the repository root, with the project environment (`requirements.txt`;
vaderSentiment 3.3.2 reproduces the stored scores exactly):

```bash
bash Scripts/reddit_analysis/run_all.sh reddit_2026-06-01_2026-08-31            # scratch → output/<dataset>/
bash Scripts/reddit_analysis/run_all.sh reddit_2026-06-01_2026-08-31 --publish  # → Data/<dataset>/ (tracked)
bash Scripts/reddit_analysis/run_all.sh                                         # the June 2025-26 collection
```

Run a scratch copy first and compare it with the published folder; `--publish`
overwrites the tracked tables. The bootstrap uses a fixed seed (`common.SEED`),
so two runs give identical files.

**The two collections differ in one way the scripts handle automatically**
(`common.is_substring_collection()`): the June files store the original
substring tags in `loc_*`/`env_*`, while October-and-later files already store
the whole-word tags and flag comments posted after the window closed
(`comment_in_window`). Those late comments stay in the cleaned files but are left
out of every analysis table (`common.analysis_comments()`).

## Hand-made inputs (`manual_review/`)

- **`location_other_city_review.csv`**: one row per location match that co-occurs
  with another city's name, for every collection (keyed by record id).
  `decision` = `keep` / `exclude` / `pending`. Only `exclude` removes a tag. A new
  collection's candidates appear as `pending` and the pipeline stops until someone
  decides them. The 68 Jun–Aug 2026 rows were reconstructed on 16 Oct 2026 from that
  collection's `location_changelog.csv` (17 exclude, 51 keep) after the original
  review file was lost; they are marked to be confirmed by hand.
- **`env_cue_validation_heldout.csv`**: 30 random corrected matches per cue,
  judged before the final exclusions were tuned (so the precision estimate is
  conservative). Fill `ra_judgement` (1/0) for a second-coder check; `01c`
  reports agreement automatically.

## Known limits (not fixable with keyword rules)

- **Lighting** tags are about 50% precise (95% CI 33–67%): "lights" is mostly traffic
  signals and car lights in this subreddit. Treat lighting counts as an upper bound,
  and hand-code lighting before making any lighting claim.
- **Time of day** means when a comment was posted, not when the experience happened.
- Comments are tagged by their own text only. `thread_vloc_*` and
  `neighbourhood_summary_thread_inherited.csv` show the alternative where a comment
  inherits its thread's location.
- VADER is a general-purpose lexicon. The workplan's hand-coding step (Dec–Jan)
  should include a sentiment validation sample.
