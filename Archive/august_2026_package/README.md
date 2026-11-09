# ComputerVision_Sentinel — August 2026 package (archive)

Everything sent with the August 2026 report except the report itself, which is in
`Deliverables/2026-08_august_report/` (`Master_Report.docx` and a PDF). Moved here from that folder on
8 November 2026; nothing inside the package was changed. `./flight` rebuilds it from `data_pkg_august/` and
compares every table and chart with these copies.

Reddit safety-perception analysis prepared for the August 2026 project meeting.
Source: r/saskatoon, 11 Jun 2025 – 11 Jun 2026 (426 posts, 14,889 comments).

---

## Start here

| If you want to… | Open |
|---|---|
| Read the findings | `Deliverables/2026-08_august_report/Master_Report.docx` (or the PDF beside it) |
| Read the literature review | `Docs/literature review/Master_lit_review.docx` (moved there; see below) |
| See the slides from the meeting | `Presentation_Slides.pdf` |
| Look up a specific number | `data_pkg_august/02_derived_analysis/` |
| See the evidence behind the data cleaning | `data_pkg_august/04_cleaned_datasets/cleaning_changelog.csv` |
| Find a quote to cite or read aloud | `data_pkg_august/03_extracted_comment_samples/` |
| Reuse a chart in slides | `charts/` |
| Reproduce the analysis | `analysis_code/README.md` |
| See a map of this package | `august_2026_folder_structure.docx` |

---

## Contents

### Reports

- **`Master_Report.docx`** (in `Deliverables/2026-08_august_report/`) — the main deliverable. Verified analysis, six
  figures, site deep dives on Downtown/CBD and Riverbank/Meewasin, direct
  answers to the questions raised in July, limitations, and recommendations.
- **`ComputerVision_Sentinel_Meewasin_DataQuality_Memo.docx`** — an earlier, narrower memo
  covering only the Riverbank/Meewasin location verification. Superseded in
  scope by the main report; kept because the report's appendix references it.

- **The literature review** — sent with this package as `Master_lit_review.docx`; the one copy now kept is
  `Docs/literature review/Master_lit_review.docx`. *A Privacy-Preserving GeoAI Framework for Urban
  CPTED Decision Support Using Environmental Sensing and Community Narratives: Site Identification for
  Saskatoon Pilot Deployment* (about 5,700 words): CPTED theory and evidence, crime and perception, and the
  candidate pilot sites.
- **`Presentation_Slides.pdf`** — the nine slides for the August meeting, including why the numbers changed.
- **`august_2026_folder_structure.docx`** — a one-page map of this package with
  a navigation table; useful for orienting anyone new to the folder.

### `charts/`

The six report figures as standalone PNGs, for reuse in slides or the paper
draft. Numbering matches the figure numbers in the report.

### `analysis_code/`

Code only — no generated files are duplicated here. Seven scripts, numbered in
run order, plus `run_all.sh` to execute the full pipeline. See
`analysis_code/README.md` for what each script does and how to point them at the
data.

### `data_pkg_august/`

All data, organised by provenance. See `data_pkg_august/README.md` for the full
data dictionary.

- **`01_raw_collection/`** — exactly as scraped, unmodified. Posts, comments, GIS
  export, run metadata, scraper log, and `initial_sraper.py` itself.

- **`02_derived_analysis/`** — the five verified aggregate tables (tagging audit,
  neighbourhood summary, environmental cues, time-of-day, seasonal trend).

- **`03_extracted_comment_samples/`** — the specific comments quoted in the
  report, so each quote traces to a source row.

- **`04_cleaned_datasets/`** — cleaned row-level data with verified `vloc_*`
  location tags alongside the originals, plus `cleaning_changelog.csv` recording
  all 607 individual tag changes with text excerpts.

---

## Headline finding

After cleaning and verifying the location tagging, **Downtown/CBD — not the
Meewasin Trail — is the strongest safety-perception signal** in the Reddit data:
320 mentions, 40.3% negative, concentrated at night (the only negative
time-of-day bucket in the dataset). Riverbank/Meewasin came back net-positive at
+0.33.

This differs from what was reported in the July 20 email. The location keyword
"river" had been matching unrelated mentions of "driver" and "drivers"; once
cleaned, Meewasin's mention count went from 725 to 122 and its sentiment
resolved positive. All 20 tracked neighbourhood categories were checked and
Riverbank/Meewasin was the only one materially affected.

---

## Verification status

All figures in the report were cross-checked against the source data, and the
analysis reproduces byte-for-byte from the raw collection. The cleaned row-level
datasets reconcile exactly with the published aggregates across all 21
neighbourhood categories.

Two open items flagged for discussion rather than resolved here:

1. **"Downtown" is a generic term.** Three matched comments referred to another
   city's downtown or were URL-string artifacts; these are documented in the
   changelog. A rounding-level effect (3 of 306), but worth a manual pass before
   anything enters the paper draft.

2. **The social-versus-environmental characterisation of Downtown/CBD** is a
   qualitative reading of the highest-scored comments, not a conclusion the cue
   percentages establish on their own (lighting appears in 17.8% of its negative
   comments). Worth reading those comments directly before defending the claim.

---