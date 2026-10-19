# Reporting: figures, numbers and the October report

| Script | Reads | Writes |
|---|---|---|
| `make_figures.py` | `Data/`, `Docs/verification/` | `Docs/figures/mid_point_october/fig01`–`fig08` (PNG, 220 dpi); `--out` for another folder |
| `report_numbers.py` | `Data/`, `Docs/verification/october_2026_checks.csv` | `Docs/verification/october_2026_numbers.json`: every number the report quotes |
| `build_october_report.js` | the JSON above and `Docs/figures/mid_point_october/` (`--numbers`, `--figures`, `--out` redirect each) | `Deliverables/2026-10_october_update/ComputerVision_Sentinel_October2026_Progress_Report.docx` |

```bash
.venv/bin/python Scripts/verification/verify_october_2026.py
.venv/bin/python Scripts/reporting/make_figures.py
.venv/bin/python Scripts/reporting/report_numbers.py
(cd Scripts/reporting && npm install && node build_october_report.js)
```

The report is Times New Roman 11 pt (captions 10 pt), US Letter, 1-inch margins, with a running header from page 2
and black table header rows. Every main section (and each 3.x subsection) starts at the top of a new page; within a
page, paragraphs never break across pages, headings, captions and figures stay with what follows, and table rows
never split. After any content change, check that each page's content still fits: if a block grows, shrink a
figure (the width argument of `figure()`) or tighten the text rather than letting it spill. To check the layout, convert to PDF with LibreOffice
(`soffice --headless --convert-to pdf <file>.docx`) and look at the pages.

Figure colours use one validated palette: blue / orange / aqua for categories (CVD-safe, checked with a palette
validator), an ordinal blue ramp for imagery years, and status colours (done, partial, limitation, blocked, planned)
that always appear with a symbol and a word, never colour alone.
