#!/usr/bin/env bash
# run_all.sh: runs the ComputerVision_Sentinel Reddit analysis pipeline on one dataset.
# See README.md for what each step does.
#
#   bash run_all.sh                                         June 2025-26 collection -> output/<dataset>/
#   bash run_all.sh reddit_2026-06-01_2026-08-31            study-period collection -> output/<dataset>/
#   bash run_all.sh reddit_2026-06-01_2026-08-31 --publish  -> Data/<dataset>/ (tracked outputs)
#
# A dataset is a folder Data/<dataset>/ whose 01_raw_collection/ holds one
# saskatoon_safety_posts_*.csv and one ..._comments_*.csv from the scraper.
# output/ is scratch and git-ignored; --publish overwrites the tracked tables,
# so compare a scratch run with the published one first (git diff shows changes).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DATASET="reddit_2025-06-11_2026-06-11"
PUBLISH=0
for arg in "$@"; do
  case "$arg" in
    --publish) PUBLISH=1 ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *) DATASET="$arg" ;;
  esac
done

export COMPUTERVISION_SENTINEL_RAW_DIR="$REPO/Data/$DATASET/01_raw_collection"
[[ -d "$COMPUTERVISION_SENTINEL_RAW_DIR" ]] || { echo "No such dataset: $COMPUTERVISION_SENTINEL_RAW_DIR" >&2; exit 1; }
if [[ $PUBLISH == 1 ]]; then
  export COMPUTERVISION_SENTINEL_OUT_DIR="$REPO/Data/$DATASET"
else
  export COMPUTERVISION_SENTINEL_OUT_DIR="${COMPUTERVISION_SENTINEL_OUT_DIR:-$HERE/output/$DATASET}"
fi
PY="$REPO/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3
echo "Dataset: $DATASET"
echo "Writing outputs to: $COMPUTERVISION_SENTINEL_OUT_DIR"

cd "$HERE/scripts"
run() { echo; echo "== $1 =="; "$PY" "$1"; }

run 01_audit_location_tagging.py
run 01b_other_city_review.py        # exits non-zero if any candidate is still "pending"
run 01c_audit_env_cues.py
run 01d_build_cleaned_datasets.py
run 02_corrected_analysis.py
run 02b_sentiment_sensitivity.py
run 03_generate_charts.py
run 04_build_excel_workbook.py
run 05_extract_example_quotes.py
run 08_verify_outputs.py            # exits non-zero if any check fails

echo
echo "Done. Outputs are in $COMPUTERVISION_SENTINEL_OUT_DIR"
