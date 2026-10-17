# UrbanSentinel-Prairie — Analysis Code (August 2026 deliverable)

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
| 01 | `01_audit_location_tagging.py` | Python | Compares raw vs. word-boundary-corrected tagging for all 20 neighbourhood categories; confirms the issue is isolated to Riverbank/Meewasin |
| 02 | `02_corrected_analysis.py` | Python | Re-tags posts/comments with the verified matcher; computes neighbourhood summary, environmental-cue rates, time-of-day sentiment, and seasonal trend |
| 03 | `03_generate_charts.py` | Python | Renders the 6 report figures (PNG) from the outputs of 01 and 02 |
| 04 | `04_build_excel_workbook.py` | Python | Assembles the verified data tables into a workbook (delivered as `UrbanSentinel_August_DataTables.numbers`) |
| 05 | `05_extract_example_quotes.py` | Python | Pulls representative, anonymized example comments for the report's quote blocks |
| 06 | `06_build_meewasin_memo_docx.js` | Node.js (docx) | Builds the earlier, narrower Meewasin-only memo |
| 07 | `07_build_august_report_docx.js` | Node.js (docx) | Builds the full August report, with embedded charts and quotes |

Run `run_all.sh` to execute the whole pipeline in order (see below).

## Setup

```bash
# Python side
pip install pandas matplotlib openpyxl --break-system-packages

# Node side (for the .docx builders)
npm install docx
```

## Running everything

```bash
bash run_all.sh
```

This runs scripts 01–05, copies the resulting charts into this
directory (the .js builders expect them alongside themselves), then
runs 06 and 07. Generated files land in a fresh `output/` directory.

## Inputs expected

The Python scripts read the raw collection CSVs. In this package those live at:

```
../data_pkg_august/01_raw_collection/saskatoon_safety_posts_20260611.csv
../data_pkg_august/01_raw_collection/saskatoon_safety_comments_20260611.csv
```

The scripts have absolute paths hardcoded in the `POSTS_PATH` /
`COMMENTS_PATH` constants at the top of scripts 01, 02, and 05 — point
these at the paths above before running.

## Where the outputs already live

This folder contains code only; no generated files are duplicated here.
The outputs of a verified run are already in the package:

- Analysis tables → `../data_pkg_august/02_derived_analysis/`
- Comment samples → `../data_pkg_august/03_extracted_comment_samples/`
- Charts → `../charts/`
- Reports → `../Master_Report.docx`, `../UrbanSentinel_Meewasin_DataQuality_Memo.docx`

Re-running `run_all.sh` regenerates all of these into a local `output/`
directory rather than overwriting the delivered copies.

## A note on keeping the neighbourhood pattern list in sync

The `NEIGHBOURHOOD` / `SASKATOON_NEIGHBOURHOODS` pattern dictionary is
currently duplicated across `01_audit_location_tagging.py` and
`02_corrected_analysis.py` (copied verbatim from `initial_sraper.py`).
If the source scraper's pattern list ever changes, update all three
places, or better, refactor into a shared `neighbourhoods.py` module
that all scripts import from.
