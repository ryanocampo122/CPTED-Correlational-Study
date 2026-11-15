# CPTED Vision — Analysis Code (August 2026 deliverable)

Code used to produce the August progress report, its companion data
workbook, and the earlier Meewasin data-quality memo, from the raw
Reddit collection in `../data_pkg_august/01_raw_collection/`.

## Background

The original scraper's neighbourhood tagger (`initial_sraper.py`, kept in
`../data_pkg_august/01_raw_collection/`) matches location keywords with plain
text containment, with no word-boundary check. This inflated the
"Riverbank / Meewasin" tag, since its keyword list includes the bare word
"river", which also matched unrelated mentions of "driver" / "drivers".
Scripts 01–02 clean and verify this; scripts 03–07 build the report
deliverables from the verified data.

## Pipeline (run in order)

| # | Script | Language | What it does |
|---|--------|----------|---------------|
| — | `neighbourhoods.py` | Python | Shared by every script below: the neighbourhood patterns (read from `initial_sraper.py`), the original and corrected matchers, column names, and the raw-data paths |
| 01 | `01_audit_location_tagging.py` | Python | Compares raw vs. word-boundary-corrected tagging for all 20 neighbourhood categories; confirms the issue is isolated to Riverbank/Meewasin |
| 02 | `02_corrected_analysis.py` | Python | Re-tags posts/comments with the verified matcher; computes neighbourhood summary, environmental-cue rates, time-of-day sentiment, and seasonal trend |
| 03 | `03_generate_charts.py` | Python | Renders the 6 report figures (PNG) from the outputs of 01 and 02 |
| 04 | `04_build_excel_workbook.py` | Python | Assembles the verified data tables into a workbook (delivered as `CPTED_Vision_August_DataTables.numbers`) |
| 05 | `05_extract_example_quotes.py` | Python | Pulls representative, anonymized example comments for the report's quote blocks |
| 06 | `06_build_meewasin_memo_docx.js` | Node.js (docx) | Builds the earlier, narrower Meewasin-only memo |
| 07 | `07_build_august_report_docx.js` | Node.js (docx) | Builds the full August report, with embedded charts and quotes |
| — | `../data_pkg_august/04_cleaned_datasets/produce_cleaned_datasets.py` | Python | Writes the cleaned row-level datasets and `cleaning_changelog.csv` |

Run `run_all.sh` to execute the whole pipeline in order (see below).

## Running everything

```bash
bash run_all.sh            # -> analysis_code/output/
bash run_all.sh <folder>   # -> <folder>/output/
```

`run_all.sh` runs scripts 01–05 and `produce_cleaned_datasets.py` with the project environment (`.venv` at the
repository root, or `python3`), writing everything to a fresh `output/` folder; the delivered files are never
overwritten. The `.docx` builders (06, 07) run too once their Node package is installed (`npm install` in this
folder); otherwise they are skipped with a message. `./flight --execute_flight` runs this on every flight and
compares every output with the delivered copy.

## Inputs

Every script reads the raw collection through `scripts/neighbourhoods.py`:

```
../data_pkg_august/01_raw_collection/saskatoon_safety_posts_20260611.csv
../data_pkg_august/01_raw_collection/saskatoon_safety_comments_20260611.csv
```

## Where the outputs already live

This folder contains code only; no generated files are duplicated here.
The outputs of a verified run are already in the package:

- Analysis tables → `../data_pkg_august/02_derived_analysis/`
- Comment samples → `../data_pkg_august/03_extracted_comment_samples/`
- Charts → `../charts/`
- Reports → `../Master_Report.docx`, `../CPTED_Vision_Meewasin_DataQuality_Memo.docx`

Re-running `run_all.sh` regenerates all of these into a local `output/`
directory rather than overwriting the delivered copies.

## One neighbourhood pattern list

The pattern dictionary used to be copied by hand into `01_audit_location_tagging.py`, `02_corrected_analysis.py`,
`produce_cleaned_datasets.py` and (for Riverbank/Meewasin) `05_extract_example_quotes.py`, with the matchers
and column-name helper copied alongside. Since 19 Oct 2026 they all import `scripts/neighbourhoods.py`, which
reads `SASKATOON_NEIGHBOURHOODS` straight from the scraper that produced the data
(`../data_pkg_august/01_raw_collection/initial_sraper.py`; the file is parsed, never run). There is one list,
and it is the scraper's: a change to the scraper is picked up everywhere, and nothing can drift.

The refactor changes no output: the scripts before and after it give byte-identical files. Compared with the
files delivered in August, 6 are byte-identical, the 6 charts have identical pixels (only their PNG metadata
names a newer matplotlib), and 5 tables and samples hold the same rows, with rows tied on the sort key in a
different order (pandas' default sort is not stable; for the Downtown quote sample, a different one of two
comments tied at the cut-off score is kept).
