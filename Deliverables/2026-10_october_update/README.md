# October 2026 update (for Dr. Jayasooriya and Dr. Kang)

| File | What it is |
|---|---|
| `UrbanSentinel_October2026_Progress_Report.docx` | **The report.** 9 pages: where the project stands, three of the four October work-plan tasks (sample points are still being refined and are not reported yet), and the image model (CLIP ViT-B/32), why it was chosen and how it can change |
| `UrbanSentinel_October2026_Progress_Report.pdf` | The same report as a PDF (rendered with LibreOffice; Word's page breaks may differ slightly) |

The report is generated, not hand-typed: every number comes from `Data/` through
`Scripts/reporting/report_numbers.py`, and the figures come from `Scripts/reporting/make_figures.py`.
To rebuild it after the data change:

```bash
.venv/bin/python Scripts/verification/verify_october_2026.py   # checks -> Docs/verification/
.venv/bin/python Scripts/reporting/make_figures.py             # figures -> Docs/figures/
.venv/bin/python Scripts/reporting/report_numbers.py           # numbers -> Docs/verification/october_2026_numbers.json
(cd Scripts/reporting && npm install && node build_october_report.js)
```

The detailed documentation behind the report is in `Docs/` (start at `Docs/README.md`).
