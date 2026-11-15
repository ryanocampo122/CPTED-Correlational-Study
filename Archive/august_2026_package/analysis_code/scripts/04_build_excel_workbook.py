"""
04_build_excel_workbook.py
============================
CPTED Vision | Build the companion Excel workbook

PURPOSE
-------
Assembles the CSV outputs from 01_audit_location_tagging.py and
02_corrected_analysis.py into a single formatted workbook for the
supervisors to browse directly: CPTED_Vision_August_DataTables.xlsx

Sheets:
  0. README                 - what's in this file, how it was produced
  1. Neighbourhood Summary  - corrected mention counts + sentiment, all 20 sites
  2. Raw vs Corrected       - before/after impact of the tagging fix, 6 priority sites
  3. Env Cues by Site       - environmental-cue rates within negative comments
  4. Time of Day by Site    - mean sentiment by time-of-day bucket
  5. Seasonal Trend         - citywide post volume & sentiment by season

INPUT
-----
  output/neighbourhood_tagging_audit.csv      (script 01)
  output/neighbourhood_summary_corrected.csv  (script 02)
  output/env_cues_by_site.csv                 (script 02)
  output/time_of_day_by_site.csv              (script 02)
  output/seasonal_trend.csv                   (script 02)

OUTPUT
------
  output/CPTED_Vision_August_DataTables.xlsx

NOTE ON FORMULAS
-----------------
This workbook is a static reference/summary export, not a financial
model — all values are written directly rather than as formulas, since
every number here is the *output* of the Python analysis above (there's
nothing left for Excel to calculate). If you extend this workbook with
your own calculations, prefer real formulas (e.g. SUMIFS) over hardcoded
results so the sheet stays live if the underlying numbers change.

USAGE
-----
  python 04_build_excel_workbook.py
  (run AFTER 01_audit_location_tagging.py and 02_corrected_analysis.py)
"""

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
import pandas as pd

NAVY = "1F3B5C"
FONT = "Arial"

PRIORITY_SITES = [
    "Pleasant Hill", "Riversdale", "Downtown / CBD",
    "Downtown Terminal", "Confederation Mall", "Riverbank / Meewasin",
]


def style_header(ws, row: int, ncols: int) -> None:
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def autosize(ws, ncols: int, width: int = 16) -> None:
    for c in range(1, ncols + 1):
        ws.column_dimensions[get_column_letter(c)].width = width


def write_df(ws, df: pd.DataFrame, start_row: int = 1, start_col: int = 1,
             pct_cols=None, float_cols=None) -> None:
    """Writes a DataFrame as a formatted table with a navy header row and
    alternating row shading. pct_cols/float_cols control number formats."""
    pct_cols = pct_cols or []
    float_cols = float_cols or []
    for j, col in enumerate(df.columns):
        ws.cell(row=start_row, column=start_col + j, value=col)
    style_header(ws, start_row, len(df.columns))
    for i, (_, r) in enumerate(df.iterrows()):
        for j, col in enumerate(df.columns):
            cell = ws.cell(row=start_row + 1 + i, column=start_col + j, value=r[col])
            cell.font = Font(name=FONT, size=10)
            if col in pct_cols:
                cell.number_format = '0.0"%"'
            if col in float_cols:
                cell.number_format = "0.000"
            if i % 2 == 1:
                cell.fill = PatternFill("solid", fgColor="F2F5F8")


def build_readme_sheet(wb) -> None:
    ws = wb.active
    ws.title = "README"
    ws.column_dimensions["A"].width = 100
    lines = [
        ("CPTED Vision \u2014 Corrected Reddit Analysis (August 2026)", 14, True),
        ("", 10, False),
        ("This workbook accompanies the August progress report. It contains the neighbourhood-level", 10, False),
        ("mention, sentiment, and environmental-cue data after refining the location-tagging in", 10, False),
        ("initial_sraper.py, where bare substring matching on \"river\" was also matching \"driver\"/\"drivers\".", 10, False),
        ("", 10, False),
        ("Produced by the scripts in this code package, in order: 01, 02, then this script (04).", 10, False),
        ("", 10, False),
        ("Sheets:", 11, True),
        ("  1. Neighbourhood Summary \u2014 corrected mention counts and sentiment, all 20 tracked areas", 10, False),
        ("  2. Raw vs Corrected \u2014 before/after impact of the tagging fix, 6 priority sites", 10, False),
        ("  3. Env Cues by Site \u2014 environmental-cue co-occurrence rates within negative comments, focus sites", 10, False),
        ("  4. Time of Day by Site \u2014 mean sentiment by time-of-day bucket, focus sites", 10, False),
        ("  5. Seasonal Trend \u2014 post volume and mean sentiment by season, citywide", 10, False),
        ("", 10, False),
        ("Source data: saskatoon_safety_posts/comments_20260611.csv (r/saskatoon, 2025-06-11 to 2026-06-11)", 10, False),
        ("Prepared by: Ryan Ocampo, CPTED Vision", 10, False),
    ]
    for i, (text, size, bold) in enumerate(lines, start=1):
        c = ws.cell(row=i, column=1, value=text)
        c.font = Font(name=FONT, size=size, bold=bold, color=NAVY if bold and size >= 14 else "000000")


def build_neighbourhood_summary_sheet(wb) -> None:
    ws = wb.create_sheet("Neighbourhood Summary")
    nb = pd.read_csv("output/neighbourhood_summary_corrected.csv")
    nb.columns = ["Neighbourhood", "Posts", "Comments", "Total Mentions",
                  "Mean Sentiment", "% Negative", "N Negative"]
    write_df(ws, nb, pct_cols=["% Negative"], float_cols=["Mean Sentiment"])
    autosize(ws, len(nb.columns), 16)
    ws.column_dimensions["A"].width = 22


def build_raw_vs_corrected_sheet(wb) -> None:
    ws = wb.create_sheet("Raw vs Corrected")
    audit = pd.read_csv("output/neighbourhood_tagging_audit.csv")
    comp = audit[audit["neighbourhood"].isin(PRIORITY_SITES)].copy()
    comp["posts_fp"] = comp["posts_raw"] - comp["posts_corrected"]
    comp["comments_fp"] = comp["comments_raw"] - comp["comments_corrected"]
    comp = comp.rename(columns={
        "neighbourhood": "Neighbourhood",
        "posts_raw": "Posts (raw)", "posts_corrected": "Posts (corrected)",
        "posts_fp": "Posts removed (false pos.)",
        "comments_raw": "Comments (raw)", "comments_corrected": "Comments (corrected)",
        "comments_fp": "Comments removed (false pos.)",
    })
    cols = ["Neighbourhood", "Posts (raw)", "Posts (corrected)", "Posts removed (false pos.)",
            "Comments (raw)", "Comments (corrected)", "Comments removed (false pos.)"]
    write_df(ws, comp[cols])
    autosize(ws, len(cols), 20)
    ws.column_dimensions["A"].width = 22


def build_env_cues_sheet(wb) -> None:
    ws = wb.create_sheet("Env Cues by Site")
    cue = pd.read_csv("output/env_cues_by_site.csv")
    cue.columns = ["Neighbourhood", "N Negative Comments", "Lighting %", "Noise %",
                   "Weather %", "Time-of-day language %", "People/Isolation %"]
    write_df(ws, cue, pct_cols=["Lighting %", "Noise %", "Weather %",
                                 "Time-of-day language %", "People/Isolation %"])
    autosize(ws, len(cue.columns), 18)
    ws.column_dimensions["A"].width = 22


def build_time_of_day_sheet(wb) -> None:
    ws = wb.create_sheet("Time of Day by Site")
    tod = pd.read_csv("output/time_of_day_by_site.csv")
    tod.columns = ["Neighbourhood", "Time of Day", "Mean Sentiment", "N Comments"]
    write_df(ws, tod, float_cols=["Mean Sentiment"])
    autosize(ws, 4, 18)
    ws.column_dimensions["A"].width = 22


def build_seasonal_sheet(wb) -> None:
    ws = wb.create_sheet("Seasonal Trend")
    season = pd.read_csv("output/seasonal_trend.csv")
    season.columns = ["Season", "Mean Sentiment", "Post Count"]
    write_df(ws, season, float_cols=["Mean Sentiment"])
    autosize(ws, 3, 18)


def main() -> None:
    wb = openpyxl.Workbook()
    build_readme_sheet(wb)
    build_neighbourhood_summary_sheet(wb)
    build_raw_vs_corrected_sheet(wb)
    build_env_cues_sheet(wb)
    build_time_of_day_sheet(wb)
    build_seasonal_sheet(wb)
    out_path = "output/CPTED_Vision_August_DataTables.xlsx"
    wb.save(out_path)
    print(f"Wrote {out_path}")
    print("Remember to run scripts/office/soffice.py recalc.py if you add any formulas.")


if __name__ == "__main__":
    main()
