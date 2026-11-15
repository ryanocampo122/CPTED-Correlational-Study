# Reporting: figures, numbers and the October and November reports

| Script | Reads | Writes |
|---|---|---|
| `make_figures.py` | `Data/`, `Docs/verification/` | `Docs/figures/mid_point_october/fig01`–`fig08` (PNG, 220 dpi); `--out` for another folder |
| `report_numbers.py` | `Data/`, `Docs/verification/october_2026_checks.csv` | `Docs/verification/october_2026_numbers.json`: every number the report quotes |
| `build_october_report.js` | the JSON above and `Docs/figures/mid_point_october/` (`--numbers`, `--figures`, `--out` redirect each) | `Deliverables/2026-10_october_update/CPTED_Vision_October2026_Progress_Report.docx` |
| `make_figures_november.py` | `Data/sps_crime_2026-06-01_2026-08-31/03_segments/`, `Data/cv_study_2026-11/` (fig12 re-runs the segmentation model on four views) | `Docs/figures/mid_point_november/fig09`–`fig14` (fig09: crime heat map with hot spots; fig14: the workflow figure in the main README); `--only fig09,...` for a subset |
| `november_numbers.py` | `Data/cv_study_2026-11/`, `Data/sps_crime_2026-06-01_2026-08-31/03_segments/` | `Docs/verification/november_2026_numbers.json`: every number the November update quotes |
| `embed_boundary_maps.py` | `Data/boundaries/` (the CBD polygon, roads and river) | the three interactive ```` ```geojson ```` maps in the main `README.md`, one under another (only the text between its two markers) |
| `build_november_report.js` | the November JSON and `Docs/figures/mid_point_november/` (`--numbers`, `--figures`, `--out`, `--md`) | `Deliverables/2026-11_midpoint/CPTED_Vision_November2026_Midpoint_Update.docx` and the same text as `Deliverables/2026-11_midpoint/README.md`; both kept local (git-ignored) until the update is sent |

```bash
.venv/bin/python Scripts/verification/verify_october_2026.py
.venv/bin/python Scripts/reporting/make_figures.py
.venv/bin/python Scripts/reporting/report_numbers.py
(cd Scripts/reporting && npm install && node build_october_report.js)
.venv/bin/python Scripts/reporting/make_figures_november.py
.venv/bin/python Scripts/reporting/november_numbers.py
node Scripts/reporting/build_november_report.js
.venv/bin/python Scripts/reporting/embed_boundary_maps.py
```

The November report follows the newer spec: Times New Roman; title 12 pt bold, headings 11.5 pt, body 11 pt,
captions 10 pt, table text 8 pt; the same running header on every page; every main section on a new page; tables
kept whole (rows never split, every row but the last keeps with the next) and figures kept with their captions.

The report is Times New Roman 11 pt (captions 10 pt), US Letter, 1-inch margins, with a running header from page 2
and black table header rows. Every main section (and each 3.x subsection) starts at the top of a new page; within a
page, paragraphs never break across pages, headings, captions and figures stay with what follows, and table rows
never split. After any content change, check that each page's content still fits: if a block grows, shrink a
figure (the width argument of `figure()`) or tighten the text rather than letting it spill. To check the layout, convert to PDF with LibreOffice
(`soffice --headless --convert-to pdf <file>.docx`) and look at the pages.

Figure colours use one validated palette: blue / orange / aqua for categories (CVD-safe, checked with a palette
validator), an ordinal blue ramp for imagery years, and status colours (done, partial, limitation, blocked, planned)
that always appear with a symbol and a word, never colour alone.
