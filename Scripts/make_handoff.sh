#!/usr/bin/env bash
# make_handoff.sh: build a shareable copy of the research folder for supervisors.
#
#   bash Scripts/make_handoff.sh            -> ~/Desktop/ComputerVision_Sentinel_research_<date>.zip
#
# Leaves out: .env (credentials), .venv, .git, node_modules, OS/editor clutter, caches,
# scratch pipeline output, flight runs (RESULTS_FINAL/), and every _local_audit_do_not_share/ folder
# (Reddit user text).
# Aborts if any credential value from .env is found inside the zip.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
NAME="ComputerVision_Sentinel_research_$(date +%Y-%m-%d)"
OUT="$HOME/Desktop/$NAME.zip"
PY="$ROOT/.venv/bin/python"; [[ -x "$PY" ]] || PY=python3

# 1. sanity: the pieces the October deliverable needs
[[ -f Scripts/reddit_analysis/scripts/common.py ]] || { echo "Missing Scripts/reddit_analysis (the Reddit scraper needs it)."; exit 1; }
[[ -f Deliverables/2026-10_october_update/CPTED_ComputerVis_2026.docx ]] \
  || { echo "October report (CPTED_ComputerVis_2026.docx, as sent) missing from Deliverables/2026-10_october_update/."; exit 1; }

# 2. zip into a temp folder named after the project
TMP="$(mktemp -d)"
ln -s "$ROOT" "$TMP/$NAME"
rm -f "$OUT"
( cd "$TMP" && zip -qr "$OUT" "$NAME/" \
    -x "$NAME/.env*" "$NAME/.venv/*" "$NAME/.git/*" "$NAME/.vscode/*" "*/node_modules/*" \
       "*/.DS_Store" "*.sw?" "*/__pycache__/*" "*.pyc" "*/~\$*" "*/.Rhistory" \
       "*/_local_audit_do_not_share/*" \
       "$NAME/Scripts/reddit_analysis/output/*" "$NAME/Scripts/reddit_analysis/scripts/output/*" \
       "$NAME/RESULTS_FINAL/*" "$NAME/Notebooks/_out/*" "*/.ipynb_checkpoints/*" )
rm -rf "$TMP"

# 3. refuse to hand over a zip that contains any credential
"$PY" - "$OUT" "$ROOT/.env" <<'EOF'
import sys, zipfile, pathlib
zpath, envpath = sys.argv[1], pathlib.Path(sys.argv[2])
secrets = []
if envpath.exists():
    for line in envpath.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if any(t in k.upper() for t in ("SECRET", "TOKEN", "SALT", "CLIENT_ID", "PASSWORD", "KEY")) and len(v) >= 8:
                secrets.append(v)
bad = []
with zipfile.ZipFile(zpath) as z:
    names = z.namelist()
    for n in names:
        if n.endswith("/.env") or "/.env" in n or "_local_audit_do_not_share" in n:
            bad.append(n)
            continue
        data = z.read(n)
        if any(s.encode() in data for s in secrets):
            bad.append(n)
if bad:
    pathlib.Path(zpath).unlink()
    sys.exit("STOPPED: credentials or private files found in: " + ", ".join(bad) + "  (zip deleted)")
print(f"OK: {len(names)} files, no credentials or private Reddit audit files inside.")
EOF
echo "Handoff zip: $OUT ($(du -h "$OUT" | cut -f1))"
