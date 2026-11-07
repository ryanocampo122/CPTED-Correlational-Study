# Flight: the whole pipeline in one command

```bash
./flight --execute_flight             # from the repository root
./flight --help                       # options
```

| File | Does |
|---|---|
| `../../flight` | launcher: uses `.venv/bin/python` if it exists, else `python3`, and runs `execute_flight.py` |
| `execute_flight.py` | the stages, the step log, the comparisons and the summary (standard library only, so it can build `.venv` itself) |
| `load_models.py` | stage 1 (`--fetch-only`): the pinned CLIP model in the Hugging Face cache; stage 3: loads CLIP and VADER, smoke-tests both, writes `models/models.json` |
| `run_notebook.py` | stage 4: runs one notebook from `Notebooks/` top to bottom and saves the copy with outputs in the execution's `notebooks/` |

Stages: **1 install** (packages and the pinned CLIP model) → **2 collect** (Reddit and Mapillary APIs) → **3 load models** (CLIP, VADER) → **4 results**
(reproduction from the committed raw data, and the same analysis on the fresh collection) → **5 checks**
(file-by-file comparison with the published outputs, repository unchanged, no credential in the output).
`Docs/workflow.md` ("One command") describes each stage and what it writes.

Each run creates `RESULTS_FINAL/EXECUTION-<n>/` (next free number) and appends a row to
`RESULTS_FINAL/executions.csv`. Start with `FLIGHT_SUMMARY.md` in the run's folder.

What the flight never does:

- write into `Data/`, `Docs/` or `Deliverables/` (every script gets an `--out`/environment override; step 5 checks
  the repository's files are unchanged);
- regenerate the sample points (`pilot.py points` is never called; the 423 points are copied and read);
- change `Scripts/reddit_analysis/manual_review/` (each analysis runs on a copy, so new other-city candidates stop at
  `pending` in the execution folder);
- print a credential (keys come from the shell, then `~/.config/computervision_sentinel/secrets.env`, with a legacy
  repository `.env` read only as a WARN fallback; only key names are logged, and step 5 scans every output file for
  the values).

Adding a step: give the script an option to write elsewhere, then call it from `stage_results()` with `F.run(...)`;
its status, time, log and note appear in the summary automatically. A new Reddit analysis step only needs adding to
`run_all.sh`: the flight reads its step list from there.
