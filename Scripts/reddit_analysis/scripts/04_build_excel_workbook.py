"""
04_build_excel_workbook.py
============================
CPTED Vision | Companion workbook for the corrected tables

PURPOSE
-------
Collects the corrected analysis and audit tables into one .xlsx for browsing
(opens in Excel, Numbers or Google Sheets). Values are written directly, not as
formulas: every number is an output of the Python pipeline.

Sheets:
  README, Neighbourhood Summary, Location Tag Audit, Env Cue Audit,
  Env Cue Precision, Env Cues by Site, Time of Day by Site,
  Night vs Other, Seasonal Trend, Monthly Trend, Sentiment Sensitivity

INPUT
-----
  02_derived_analysis/*.csv, 05_audits/*.csv

OUTPUT
------
  CPTED_Vision_DataTables_corrected.xlsx  (in the output root)

USAGE
-----
  python 04_build_excel_workbook.py
"""

import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import common as c

NAVY = "1F3B5C"
FONT = "Arial"
D = c.out_dir("02_derived_analysis")
A = c.out_dir("05_audits")

SHEETS = [
    ("Neighbourhood Summary", D / "neighbourhood_summary.csv"),
    ("Location Tag Audit", A / "neighbourhood_tagging_audit.csv"),
    ("Env Cue Audit", A / "env_cue_tagging_audit.csv"),
    ("Env Cue Precision", A / "env_cue_precision_heldout.csv"),
    ("Env Cues by Site", D / "env_cues_by_site.csv"),
    ("Env Cues Detail", D / "env_cues_by_site_detail.csv"),
    ("Time of Day by Site", D / "time_of_day_by_site.csv"),
    ("Night vs Other", D / "time_of_day_contrasts.csv"),
    ("Seasonal Trend", D / "seasonal_trend.csv"),
    ("Monthly Trend", D / "monthly_trend.csv"),
    ("Sentiment Sensitivity", A / "sentiment_sensitivity.csv"),
]

README_LINES = [
    ("CPTED Vision - Corrected Reddit Analysis (October 2026)", 14, True),
    ("", 10, False),
    ("Supersedes the August 2026 data tables. Method (October 2026 corrections, same for every collection):", 10, False),
    ("  1. Location tags: whole-word matching plus reviewed references to other cities removed (Location Tag Audit;", 10, False),
    ("     the review is an automated first pass, to be confirmed by hand).", 10, False),
    ("  2. Sutherland tracked as a 22nd area.", 10, False),
    ("  3. Environmental cues: whole-word matching minus non-environmental senses; substring tags matched inside", 10, False),
    ("     words ('ice' in 'police', 'lit' in 'little'). See Env Cue Audit and Env Cue Precision.", 10, False),
    ("  4. Sentiment: adjusted VADER is primary ('safety' neutral; 'unsafe', 'afraid', 'sketchy' given negative values).", 10, False),
    ("     Original VADER figures are kept in *_vader_original columns. See Sentiment Sensitivity.", 10, False),
    ("  5. Seasons use local (Saskatoon) time, not UTC.", 10, False),
    ("  6. 95% CIs from a bootstrap that resamples whole threads (comments in one thread are not independent).", 10, False),
    ("", 10, False),
    ("Reading notes:", 11, True),
    ("  - time_of_day is when a comment was POSTED, not when the experience happened.", 10, False),
    ("  - Lighting cue precision in a first-pass check (not yet checked by hand) is ~50%; treat lighting counts as an", 10, False),
    ("    upper bound.", 10, False),
    ("  - small_sample = fewer than 30 mentions. Overlapping CIs mean no clear difference.", 10, False),
    ("", 10, False),
    ("Produced by Scripts/reddit_analysis (run_all.sh). Prepared by: Ryan Ocampo, CPTED Vision", 10, False),
]


def source_line() -> str:
    """Provenance line for each sheet: raw file stamp, window and dataset."""
    m = c.raw_metadata()
    win = m.get("window_local") or [m.get("window_start", "?")[:10], m.get("window_end", "?")[:10]]
    return (f"Source: saskatoon_safety_posts/comments_{c.raw_stamp()}.csv "
            f"(r/saskatoon, {win[0]} to {win[1]}; dataset {c.dataset_name()})")


def write_df(ws, df: pd.DataFrame) -> None:
    """df -> worksheet with a styled header row; NaN -> empty cell."""
    for j, col in enumerate(df.columns, start=1):
        cell = ws.cell(row=1, column=j, value=col)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(j)].width = max(12, min(40, len(str(col)) + 4))
    for i, row in enumerate(df.itertuples(index=False), start=2):
        for j, v in enumerate(row, start=1):
            v = None if (isinstance(v, float) and pd.isna(v)) else v
            cell = ws.cell(row=i, column=j, value=v)
            cell.font = Font(name=FONT, size=10)
            if i % 2 == 1:
                cell.fill = PatternFill("solid", fgColor="F2F5F8")
    ws.freeze_panes = "B2"


def main() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "README"
    ws.column_dimensions["A"].width = 120
    for i, (text, size, bold) in enumerate(README_LINES[:-1] + [(source_line(), 10, False)] + README_LINES[-1:],
                                           start=1):
        cell = ws.cell(row=i, column=1, value=text)
        cell.font = Font(name=FONT, size=size, bold=bold, color=NAVY if size >= 14 else "000000")
    for name, path in SHEETS:
        write_df(wb.create_sheet(name), pd.read_csv(path))
    out = c.out_dir() / "CPTED_Vision_DataTables_corrected.xlsx"
    wb.save(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
