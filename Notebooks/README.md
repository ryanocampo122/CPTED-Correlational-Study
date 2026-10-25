# Notebooks

Notebooks sit on top of the scripts in `Scripts/`. They show what the pipeline produced, walk through
how it runs, and are where new methods are tried before they become scripts. The scripts stay the
record: every published number comes from them, and `./flight --execute_flight` checks them.

| Notebook | What it does | Reads | Run by the flight |
|---|---|---|---|
| `00_replicate_system.ipynb` | Runs the whole pipeline once (`./flight --execute_flight --offline`) into `Notebooks/_out/`, then walks through each stage's results | everything | no (it runs the flight itself) |
| `01_reddit.ipynb` | Reddit, June–August 2026: collection, areas with % negative and 95% CIs, cue precision, sentiment sensitivity, self-checks | `Data/reddit_2026-06-01_2026-08-31/` | yes |
| `02_crime.ipynb` | SPS recorded crime, June–August 2026: study categories, city vs CBD, by month, data checks | `Data/sps_crime_2026-06-01_2026-08-31/` | yes |
| `03_cv_pilot.ipynb` | Street images: the 423 sample points, imagery by year, and the 10-image CLIP pilot | `Data/cv_pilot_2026-10/` | yes |

## Rules

- **Never write to `Data/`, `Docs/` or `Deliverables/`.** Anything a notebook makes goes in
  `Notebooks/_out/` (git-ignored), through `out_dir()` in `_setup.py`.
- **Outputs are never committed.** `nbstripout` is installed as a git filter (`.gitattributes`), so
  `git add` stores each notebook without its outputs. Outputs can hold Reddit text, images and model
  scores; the executed copies the flight makes stay in `RESULTS_FINAL/EXECUTION-<n>/notebooks/`.
  After cloning, run `.venv/bin/nbstripout --install` once to turn the filter on.
- **No Reddit text in a notebook.** Show counts, rates and tables, never posts or comments
  (`Docs/data_ethics.md`).
- **Start every notebook with `from _setup import *`**: the same folders and project modules
  (`pilot_lib`, `common`) as the scripts.
- **A method that works moves into `Scripts/`**, with a test and a flight step; the notebook then
  imports it from there.

## Running

In VS Code, open a notebook and pick the `.venv` Python as the kernel. From the command line, to run
one notebook top to bottom the way the flight does (output copy in `Notebooks/_out/`):

```bash
.venv/bin/python Scripts/flight/run_notebook.py Notebooks/01_reddit.ipynb Notebooks/_out/01_reddit.ipynb
```
