#!/usr/bin/env bash
# run_all.sh: rebuild the August 2026 analysis from ../data_pkg_august/01_raw_collection/.
#
#   bash run_all.sh              -> analysis_code/output/
#   bash run_all.sh <folder>     -> <folder>/output/   (./flight uses this)
#
# Python steps 01-05 and the cleaned row-level datasets always run; every script reads the
# neighbourhood list from scripts/neighbourhoods.py. The .docx builders (06, 07) run only if
# the docx package is installed in this folder (npm install). The delivered files are never
# overwritten: everything goes to output/.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
WORK="${1:-$HERE}"
PY="${PYTHON:-$REPO/.venv/bin/python}"
[[ -x "$PY" ]] || PY=python3

mkdir -p "$WORK/output"
cd "$WORK"
echo "Writing outputs to: $WORK/output"

run() { echo; echo "== $(basename "$1") =="; MPLBACKEND=Agg "$PY" "$1"; }
run "$HERE/scripts/01_audit_location_tagging.py"
run "$HERE/scripts/02_corrected_analysis.py"
run "$HERE/scripts/03_generate_charts.py"
run "$HERE/scripts/04_build_excel_workbook.py"
run "$HERE/scripts/05_extract_example_quotes.py"
run "$HERE/../data_pkg_august/04_cleaned_datasets/produce_cleaned_datasets.py"

if (cd "$HERE" && node -e "require.resolve('docx')" >/dev/null 2>&1); then
  cp output/chart*.png "$HERE/scripts/"            # the builders read the charts from their own folder
  (cd "$HERE/scripts" && node 06_build_meewasin_memo_docx.js && node 07_build_august_report_docx.js \
     && mv memo.docx august_report.docx "$WORK/output/")
  (cd "$HERE/scripts" && rm -f chart1_raw_vs_corrected.png chart2_corrected_volume.png chart3_sentiment_by_site.png \
     chart4_env_cues.png chart5_time_of_day.png chart6_seasonal.png)
else
  echo; echo "Skipping the .docx builders (06, 07): run 'npm install' in $HERE first."
fi
echo; echo "Done. Outputs are in $WORK/output"
