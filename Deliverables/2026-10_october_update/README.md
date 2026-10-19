# October 2026 update (for Dr. Jayasooriya and Dr. Kang)

| File | What it is |
|---|---|
| `CPTED_ComputerVis_2026.docx` | **The report, as sent.** 8 pages: where the project stands, three of the four October work-plan tasks (sample points are still being refined and are not reported yet), and the image model (CLIP ViT-B/32), why it was chosen and how it can change. Edited by hand after it was generated |
| `CPTED_ComputerVis_2026.pdf` | The same report as a PDF |

The report's base is generated, not hand-typed: every number comes from `Data/` through
`Scripts/reporting/report_numbers.py`, and the figures come from `Scripts/reporting/make_figures.py`.
A rebuild writes `ComputerVision_Sentinel_October2026_Progress_Report.docx` (the generated base); it neither
reproduces nor overwrites the hand-edited `CPTED_ComputerVis_2026.docx`.

To rebuild everything, including this report, into a fresh `RESULTS_FINAL/EXECUTION-<n>/` folder without touching
the published files: `./flight --execute_flight` (repository root). To rebuild only the report in place:

```bash
.venv/bin/python Scripts/verification/verify_october_2026.py   # checks  -> Docs/verification/
.venv/bin/python Scripts/reporting/make_figures.py             # figures -> Docs/figures/mid_point_october/
.venv/bin/python Scripts/reporting/report_numbers.py           # numbers -> Docs/verification/october_2026_numbers.json
(cd Scripts/reporting && npm install && node build_october_report.js)
```

The detailed documentation behind the report is in `Docs/` (start at `Docs/README.md`).

**Edited after sending (19 Oct 2026).** In `CPTED_ComputerVis_2026.docx` the project name in the running header, one sentence in section 3.3 and the document properties was changed to ComputerVision_Sentinel; nothing else was changed. `CPTED_ComputerVis_2026.pdf` was re-exported from it (same 8 pages). The earlier generated PDF, superseded by these, was removed.
