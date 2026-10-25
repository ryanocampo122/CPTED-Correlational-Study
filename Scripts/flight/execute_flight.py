#!/usr/bin/env python3
"""
execute_flight.py
=================
ComputerVision_Sentinel | The whole pipeline in one command:  ./flight --execute_flight

  1 install       .venv (created if missing), pip install -r requirements.txt, npm install for the report builder,
                  and the CLIP model at its pinned revision (downloaded once, ~600 MB)
  2 collect       through the APIs: Reddit (r/saskatoon, 1 Jun - 31 Aug 2026) and Mapillary (imagery coverage and
                  the 10 newest images at the 423 published sample points, which are read and never regenerated)
  3 load models   CLIP ViT-B/32 and VADER (stock and adjusted), each smoke-tested (load_models.py)
  4 results       reproduction: every published output rebuilt from the committed raw data; live: the same
                  analysis on the fresh collection; CV tests; verification checks; figures; report numbers;
                  the October report (.docx); notebooks 01-09 in Notebooks/, run top to bottom
  5 checks        reproduction compared with Data/ and Docs/ file by file; fresh collection compared with the
                  published numbers; Data/, Docs/, Deliverables/, Scripts/ and Notebooks/ unchanged; no
                  credential in the output

Each run gets a new folder RESULTS_FINAL/EXECUTION-<n>/ (n = last + 1) and writes nowhere else.
Read its FLIGHT_SUMMARY.md first; flight_status.json holds the same in machine-readable form, logs/ every
step's full output, and comparisons/ the file-by-file results. RESULTS_FINAL/executions.csv lists every run.

Standard library only, so it runs before the environment exists; every step runs in .venv's Python.

USAGE (repository root)
-----
  ./flight --execute_flight                      everything (~20 min once installed; the Reddit collection is ~10)
  ./flight --execute_flight --offline            no API calls: install, models, reproduction, checks
  ./flight --execute_flight --skip-install --skip-reddit-collection --skip-coverage
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VENV = REPO / ".venv"
VPY = VENV / "bin" / "python"
DATA = REPO / "Data"
REDDIT_DS = "reddit_2026-06-01_2026-08-31"         # study period
REDDIT_JUNE_DS = "reddit_2025-06-11_2026-06-11"    # earlier 12-month collection
SPS = DATA / "sps_crime_2026-06-01_2026-08-31"
CV = DATA / "cv_pilot_2026-10"
CBD, PILOT = CV / "cbd", CV / "cbd_latest_imagery"
VERIF = REPO / "Docs" / "verification"
FIGS = REPO / "Docs" / "figures" / "mid_point_october"
ANALYSIS = REPO / "Scripts" / "reddit_analysis"
AUGUST = REPO / "Deliverables" / "2026-08_august_report"      # rebuilt with its own analysis_code/
REVIEW = ANALYSIS / "manual_review"
REPORTING = REPO / "Scripts" / "reporting"
PILOT_PY = REPO / "Scripts" / "cv_pilot" / "pilot.py"
SCRAPER = REPO / "Scripts" / "reddit_collection" / "reddit_scraper.py"
STUDY = ("2026-06-01", "2026-08-31")

KEY_FILES = (REPO / ".env", VENV / "keys.txt")      # read in this order; the first holding a key wins
NEEDS = {"reddit": ("PRAW_CLIENT_ID", "PRAW_CLIENT_SECRET", "COMPUTERVISION_SENTINEL_HASH_SALT"),
         "mapillary": ("MAPILLARY_TOKEN",)}
SECRET_HINTS = ("SECRET", "TOKEN", "SALT", "CLIENT_ID", "PASSWORD", "KEY")
# Never part of the repository snapshot: build artefacts, environments, OS clutter
SNAPSHOT_SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "_out"}   # _out: Notebooks/_out (scratch)
SNAPSHOT_SKIP_FILES = {".DS_Store", "package-lock.json", ".Rhistory", ".RData"}   # plus Word lock files (~$...)
STATUSES = ("PASS", "WARN", "FAIL", "SKIP")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def hms(s: float) -> str:
    s = int(round(s))
    return f"{s // 3600}h{s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m{s % 60:02d}s"


def secret_values() -> list[str]:
    """Values of secret-looking keys in either key file, to scan the output for (never printed)."""
    keys = {}
    for p in KEY_FILES:
        keys.update({k: v for k, v in read_keyfile(p).items() if k not in keys})
    return [v for k, v in keys.items() if any(h in k.upper() for h in SECRET_HINTS) and len(v) >= 8]


def read_keyfile(path: Path) -> dict:
    """KEY=VALUE lines (quotes stripped, comments skipped), as the collector and pilot read .env."""
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


# --------------------------------------------------------------------------- #
# Step bookkeeping
# --------------------------------------------------------------------------- #
class Flight:
    def __init__(self, root: Path, args: argparse.Namespace):
        self.args, self.root = args, root
        self.started, self.t0 = now(), time.time()
        root.mkdir(parents=True, exist_ok=True)
        self.exec_dir = self._new_execution_dir(root)
        self.name = self.exec_dir.name
        self.logs = self.exec_dir / "logs"
        self.logs.mkdir()
        self.steps: list[dict] = []
        self.facts: dict = {}                       # numbers gathered along the way, for the summary
        self.secrets: list[str] = []                # credential values, only to scan the output for them
        self.env = dict(os.environ, MPLBACKEND="Agg", PYTHONUNBUFFERED="1")
        if args.offline:
            self.env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")

    @staticmethod
    def _new_execution_dir(root: Path) -> Path:
        n = max([int(m.group(1)) for p in root.glob("EXECUTION-*")
                 if (m := re.fullmatch(r"EXECUTION-(\d+)", p.name))] + [0]) + 1
        while True:
            d = root / f"EXECUTION-{n}"
            try:
                d.mkdir()
                return d
            except FileExistsError:
                n += 1

    def d(self, *parts: str) -> Path:
        """A folder inside this execution, created on demand."""
        p = self.exec_dir.joinpath(*parts)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def rel(self, p: Path) -> str:
        p = Path(p)
        return str(p.relative_to(self.exec_dir)) if p.is_relative_to(self.exec_dir) else str(p)

    def say(self, msg: str) -> None:
        line = f"{now()}  {msg}"
        print(msg, flush=True)
        with open(self.logs / "flight.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _add(self, sid, stage, title, status, note="", seconds=0.0, log=None, exit_code=None, details=None) -> dict:
        step = {"n": len(self.steps) + 1, "id": sid, "stage": stage, "title": title, "status": status,
                "note": note, "seconds": round(seconds, 1), "exit_code": exit_code,
                "log": self.rel(log) if log else None, "details": details or {}}
        self.steps.append(step)
        self.say(f"[{step['n']:2d}] {status:4s}  {sid:28s} {hms(seconds):>7s}  {note}")
        return step

    def skip(self, sid, stage, title, why) -> dict:
        return self._add(sid, stage, title, "SKIP", why)

    def record(self, sid, stage, title, status, note="", seconds=0.0, details=None, log=None) -> dict:
        return self._add(sid, stage, title, status, note, seconds, log=log, details=details)

    def status_of(self, sid: str) -> str | None:
        return next((s["status"] for s in self.steps if s["id"] == sid), None)

    def ok(self, sid: str) -> bool:
        return self.status_of(sid) in ("PASS", "WARN")

    def run(self, sid, stage, title, cmds, cwd=REPO, env=None, warn=None, note_fn=None) -> dict:
        """Run one or more commands in sequence, all output to one log. cmds = [(label, argv)].
        warn = {label: (exit_code, note)}: that exit code is a known limitation (WARN) and the sequence goes on.
        Any other non-zero exit stops the sequence and fails the step."""
        n = len(self.steps) + 1
        log = self.logs / f"{n:02d}_{sid}.log"
        self.say(f"[{n:2d}] ....  {sid:28s} running  (log: {self.rel(log)})")
        t0, status, codes, notes = time.time(), "PASS", {}, []
        with open(log, "w", encoding="utf-8") as f:
            for label, argv in cmds:
                f.write(f"\n===== {label}\n$ {' '.join(map(str, argv))}\n(cwd {cwd})  started {now()}\n\n")
                f.flush()
                rc = subprocess.run([str(a) for a in argv], cwd=cwd, env=env or self.env, check=False,
                                    stdout=f, stderr=subprocess.STDOUT).returncode
                codes[label] = rc
                f.write(f"\n===== {label}: exit {rc}\n")
                f.flush()
                if rc == 0:
                    continue
                if warn and label in warn and rc == warn[label][0]:
                    status = "WARN"
                    notes.append(warn[label][1])
                    continue
                status = "FAIL"
                notes.append(f"{label} exited {rc}")
                break
        note = "; ".join(notes)
        if note_fn and status != "FAIL":
            try:
                extra = note_fn()
            except Exception as e:                          # noqa: BLE001
                extra = f"(could not summarise: {type(e).__name__}: {e})"
            note = "; ".join(x for x in (note, extra) if x)
        last = list(codes.values())[-1] if codes else None
        step = self._add(sid, stage, title, status, note, time.time() - t0, log=log,
                         exit_code=last if len(codes) == 1 else None,
                         details={"exit_codes": codes} if len(codes) > 1 else {})
        return step


# --------------------------------------------------------------------------- #
# Small file helpers (stdlib only)
# --------------------------------------------------------------------------- #
def csv_rows(path: Path) -> list[dict]:
    csv.field_size_limit(sys.maxsize)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def one(folder: Path, pattern: str) -> Path | None:
    hits = sorted(folder.glob(pattern))
    return hits[-1] if hits else None


def copy_inputs(src: Path, dst: Path, names: list[str]) -> None:
    """Copy named files/folders from a published folder into this execution (the originals are only read)."""
    dst.mkdir(parents=True, exist_ok=True)
    for n in names:
        s = src / n
        if s.is_dir():
            shutil.copytree(s, dst / n, dirs_exist_ok=True)
        elif s.exists():
            shutil.copy2(s, dst / n)


def analysis_steps() -> list[str]:
    """The Reddit analysis steps, in run_all.sh's order (run_all.sh stays the single definition)."""
    return re.findall(r"^run (\S+\.py)", (ANALYSIS / "run_all.sh").read_text(), re.M)


def tree_snapshot(skip_root: Path) -> dict:
    """{relative path: (size, mtime_ns)} for every repository file the flight must not change."""
    snap = {}
    for top in ("Data", "Docs", "Deliverables", "Scripts", "Notebooks", "Plan", "Reference", "Archive"):
        base = REPO / top
        if not base.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if x not in SNAPSHOT_SKIP_DIRS
                           and not Path(dirpath, x).resolve().is_relative_to(skip_root)]
            for fn in filenames:
                if fn in SNAPSHOT_SKIP_FILES or fn.endswith(".pyc") or fn.startswith("~$"):
                    continue
                p = Path(dirpath, fn)
                st = p.stat()
                snap[str(p.relative_to(REPO))] = (st.st_size, st.st_mtime_ns)
    for fn in (".env", ".gitignore", "README.md", "requirements.txt", "flight"):
        p = REPO / fn
        if p.exists():
            st = p.stat()
            snap[fn] = (st.st_size, st.st_mtime_ns)
    return snap


# --------------------------------------------------------------------------- #
# Comparing a rebuilt file with its published copy
# --------------------------------------------------------------------------- #
VOLATILE_JSON_KEYS = re.compile(r"(_utc|^git_commit|^libs|^device)$")


def _strip_volatile(obj):
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if not VOLATILE_JSON_KEYS.search(k)}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def _flatten(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def _png_image(data: bytes):
    """(header, decompressed image data) of a PNG, ignoring its metadata chunks; None if not a PNG."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    i, header, chunks = 8, None, []
    while i + 8 <= len(data):
        n, kind = int.from_bytes(data[i:i + 4], "big"), data[i + 4:i + 8]
        if kind == b"IHDR":
            header = data[i + 8:i + 8 + n]
        elif kind == b"IDAT":
            chunks.append(data[i + 8:i + 8 + n])
        i += 12 + n
    try:
        return header, zlib.decompress(b"".join(chunks))
    except zlib.error:
        return None


def _tied_rows(a: bytes, b: bytes) -> str | None:
    """Why two CSVs with the same header differ only through ties, or None. pandas' default sort is not
    stable, so rows tied on the sort key can come out in another order, and a top-n cut can keep a
    different one of the rows tied at the cut-off (the August code sorts quotes by score)."""
    ra = list(csv.reader(io.StringIO(a.decode("utf-8", "replace"))))
    rb = list(csv.reader(io.StringIO(b.decode("utf-8", "replace"))))
    if not ra or not rb or ra[0] != rb[0] or len(ra) != len(rb):
        return None
    if sorted(ra[1:]) == sorted(rb[1:]):
        return "same rows; rows tied on the sort key are in a different order"
    if "score" in ra[0]:
        k = ra[0].index("score")
        try:
            sa, sb = sorted(float(r[k]) for r in ra[1:]), sorted(float(r[k]) for r in rb[1:])
        except ValueError:
            return None
        cut = sa[0] if sa else 0
        if sa == sb and sorted(r for r in ra[1:] if float(r[k]) > cut) == sorted(r for r in rb[1:] if float(r[k]) > cut):
            return f"same rows, except which of the rows tied at the cut-off score ({cut:g}) was kept"
    return None


def compare_file(new: Path, pub: Path, tolerate_ties: bool = False) -> tuple[str, str]:
    """(status, note): identical | equivalent (differs only where a run stamps its own time or metadata, or,
    with tolerate_ties, only in how tied rows were ordered) | differs."""
    a, b = new.read_bytes(), pub.read_bytes()
    if a == b:
        return "identical", ""
    suf = new.suffix.lower()
    if suf == ".png":
        ia, ib = _png_image(a), _png_image(b)
        if ia is not None and ia == ib:
            return "equivalent", "identical pixels; only the PNG metadata (e.g. the matplotlib version) differs"
        return "differs", "the images differ"
    if suf == ".csv" and tolerate_ties:
        why = _tied_rows(a, b)
        if why:
            return "equivalent", why
    if suf == ".xlsx":
        try:
            with zipfile.ZipFile(new) as za, zipfile.ZipFile(pub) as zb:
                names = sorted(set(za.namelist()) | set(zb.namelist()))
                diff = [n for n in names if n != "docProps/core.xml"
                        and (n not in za.namelist() or n not in zb.namelist() or za.read(n) != zb.read(n))]
            return ("equivalent", "only the workbook's embedded creation time differs") if not diff \
                else ("differs", f"workbook parts differ: {', '.join(diff[:5])}")
        except zipfile.BadZipFile:
            return "differs", "not a valid workbook"
    if suf == ".json":
        try:
            ja, jb = json.loads(a), json.loads(b)
        except ValueError:
            return "differs", "not valid JSON"
        sa, sb = _strip_volatile(ja), _strip_volatile(jb)
        if sa == sb:
            return "equivalent", "only run timestamps / git commit / library versions differ"
        fa, fb = dict(_flatten(sa)), dict(_flatten(sb))
        keys = [k for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k)]
        return "differs", f"{len(keys)} value(s) differ, e.g. " + "; ".join(
            f"{k}: {fb.get(k)!r} -> {fa.get(k)!r}" for k in keys[:4])
    if suf in (".md", ".txt", ".csv"):
        ta, tb = a.decode("utf-8", "replace").splitlines(), b.decode("utf-8", "replace").splitlines()
        stamp = re.compile(r"^\*?Generated \d{4}-\d{2}-\d{2}T")
        na, nb = [x for x in ta if not stamp.match(x)], [x for x in tb if not stamp.match(x)]
        if na == nb:
            return "equivalent", "only the 'Generated <time> (git <commit>)' line differs"
        first = next((i for i, (x, y) in enumerate(zip(na, nb)) if x != y), min(len(na), len(nb)))
        return "differs", f"{len(na)} vs {len(nb)} lines (published second); first difference at line {first + 1}"
    return "differs", f"{len(a):,} vs {len(b):,} bytes (published second)"


def compare_tree(area: str, new_root: Path, pub_root: Path, exclude: tuple[str, ...] = ()) -> list[dict]:
    """Every file the run produced under new_root against pub_root, plus published files the run did not produce."""
    def files(root: Path) -> set[str]:
        out = set()
        for p in root.rglob("*"):
            r = str(p.relative_to(root))
            if p.is_file() and p.name != ".DS_Store" and "_local_audit_do_not_share" not in r \
                    and "__pycache__" not in r and not any(r == e or r.startswith(e.rstrip("/") + "/") for e in exclude):
                out.add(r)
        return out
    new, pub = files(new_root), files(pub_root) if pub_root.exists() else set()
    rows = []
    for r in sorted(new | pub):
        if r not in pub:
            rows.append({"area": area, "file": r, "status": "new", "note": "not in the published folder"})
        elif r not in new:
            rows.append({"area": area, "file": r, "status": "missing", "note": "published, but this run did not produce it"})
        else:
            st, note = compare_file(new_root / r, pub_root / r)
            rows.append({"area": area, "file": r, "status": st, "note": note})
    return rows


NETWORK_CHECKS = ("Independent re-query", "Points on bridges or freeways",   # depend on today's API answers
                  "OSM bridge list refreshed")


def compare_checks(new: Path, pub: Path, offline: bool = False) -> list[dict]:
    """Verification table row by row, keyed on (area, check). offline: the network-only rows were not run."""
    a = {(r["area"], r["check"]): r for r in csv_rows(new)}
    b = {(r["area"], r["check"]): r for r in csv_rows(pub)}
    undated = lambda r: (r["status"], re.sub(r"\d{4}-\d{2}-\d{2}", "<date>", r["result"]))  # noqa: E731
    rows = []
    for k in list(b) + [k for k in a if k not in b]:
        ra, rb = a.get(k), b.get(k)
        if ra and rb and undated(ra) == undated(rb):      # same answer; at most the query date moved
            continue
        net = any(k[1].startswith(x) for x in NETWORK_CHECKS)
        if offline and net and ra is None:
            continue
        rows.append({"area": k[0], "check": k[1],
                     "published": f"{rb['status']}: {rb['result']}" if rb else "(no row)",
                     "this_run": f"{ra['status']}: {ra['result']}" if ra else "(no row)",
                     "why": "re-queried live, so the answer can change" if net else "check this"})
    return rows


# --------------------------------------------------------------------------- #
# Numbers for the summary
# --------------------------------------------------------------------------- #
def reddit_numbers(ds_dir: Path) -> dict:
    """Collection size and the Downtown figures from one Reddit dataset folder."""
    raw = ds_dir / "01_raw_collection"
    out = {}
    p, c = one(raw, "saskatoon_safety_posts_*.csv"), one(raw, "saskatoon_safety_comments_*.csv")
    if p and c:
        posts, comments = csv_rows(p), csv_rows(c)
        out.update(posts=len(posts), comments=len(comments),
                   comments_in_window=sum(r.get("comment_in_window") == "True" for r in comments),
                   post_ids=sorted(r["id"] for r in posts))
    nb = ds_dir / "02_derived_analysis" / "neighbourhood_summary.csv"
    if nb.exists():
        d = next((r for r in csv_rows(nb) if r["neighbourhood"] == "Downtown / CBD"), None)
        if d:
            out["downtown"] = {"records": int(float(d["total_mentions"])), "threads": int(float(d["n_threads"])),
                               "pct_negative": float(d["pct_negative"]),
                               "ci95": [float(d["pct_neg_ci95_low"]), float(d["pct_neg_ci95_high"])]}
    vr = ds_dir / "05_audits" / "verification_report.txt"
    if vr.exists():
        t = vr.read_text()
        out["self_checks"] = {"pass": t.count("[PASS]"), "fail": t.count("[FAIL]")}
    return out


def coverage_numbers(folder: Path) -> dict:
    meta_f = folder / "run_meta.json"
    if not meta_f.exists() or "coverage" not in json.loads(meta_f.read_text()):
        return {}
    cov = json.loads(meta_f.read_text())["coverage"]
    newest = {}
    if (folder / "coverage_points.csv").exists():
        for r in csv_rows(folder / "coverage_points.csv"):
            y = max(r.get("latest_flat") or "", r.get("latest_pano") or "")[:4] or "none"
            newest[y] = newest.get(y, 0) + 1
    return {"points": cov.get("points"), "with_any_image": cov.get("points_with_any_image"),
            "with_study_period_image": cov.get("points_with_study_period_image"),
            "newest_year": dict(sorted(newest.items()))}


def pilot_numbers(folder: Path) -> dict:
    out = {}
    if (folder / "image_manifest.csv").exists():
        man = csv_rows(folder / "image_manifest.csv")
        years = {}
        for r in man:
            years[r["capture_year"]] = years.get(r["capture_year"], 0) + 1
        out.update(images=len(man), capture_years=dict(sorted(years.items())))
    if (folder / "clip_scores.csv").exists():
        clip = csv_rows(folder / "clip_scores.csv")
        out["clip_low_confidence"] = sum(r["typology_low_confidence"] == "True" for r in clip)
        out["clip_top1"] = {r["point_id"]: r["typology_top1"] for r in clip}
    return out


# --------------------------------------------------------------------------- #
# The flight
# --------------------------------------------------------------------------- #
def stage_install(F: Flight) -> bool:
    S = "1 install"
    t0 = time.time()
    if not VPY.exists():
        rc = subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=False).returncode
        F.record("venv", S, "Create the project virtual environment",
                 "PASS" if rc == 0 else "FAIL", f"created .venv with {sys.executable}", time.time() - t0)
        if rc:
            return False
    else:
        F.record("venv", S, "Project virtual environment", "PASS", f"using {VPY.relative_to(REPO)}")
    v = subprocess.run([VPY, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
                       capture_output=True, text=True, check=False).stdout.strip()
    F.facts["python"] = v
    if not v.startswith("3.14"):
        F.say(f"      note: .venv runs Python {v}; requirements.txt is pinned for 3.14")

    if F.args.skip_install:
        F.skip("pip_install", S, "Install requirements.txt", "--skip-install")
        F.skip("npm_install", S, "Install the report builder's Node packages", "--skip-install")
    else:
        F.run("pip_install", S, "Install requirements.txt",
              [("pip", [VPY, "-m", "pip", "install", "--disable-pip-version-check", "-r", REPO / "requirements.txt"])],
              note_fn=lambda: "requirements.txt satisfied")
        if shutil.which("npm"):
            F.run("npm_install", S, "Install the report builder's Node packages",
                  [("npm", ["npm", "install", "--no-audit", "--no-fund"])], cwd=REPORTING)
        else:
            F.skip("npm_install", S, "Install the report builder's Node packages", "npm not found; report build skipped")

    env_dir = F.d("environment")
    clip_json = env_dir / "clip_model.json"

    def clip_note():
        c = json.loads(clip_json.read_text())["clip"]
        return f"{c['model']} @ {c['revision'][:7]} ({c['megabytes']} MB) in {c['cache_folder']}"
    F.run("clip_model", S, "CLIP model at its pinned revision (download if missing)",
          [("fetch", [VPY, REPO / "Scripts" / "flight" / "load_models.py", "--fetch-only", "--out", clip_json])],
          note_fn=clip_note)
    t0 = time.time()
    freeze = subprocess.run([VPY, "-m", "pip", "freeze", "--disable-pip-version-check"],
                            capture_output=True, text=True, check=False).stdout
    (env_dir / "pip_freeze.txt").write_text(freeze)
    shutil.copy2(REPO / "requirements.txt", env_dir / "requirements.txt")

    def git(*a: str) -> str:
        return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, check=False).stdout.strip()

    dirty = [x for x in git("status", "--porcelain").splitlines() if x.strip()]
    (env_dir / "git_status.txt").write_text("\n".join(dirty) + "\n")
    node = shutil.which("node")
    info = {"started_utc": F.started, "python": v, "platform": platform.platform(),
            "node": subprocess.run([node, "--version"], capture_output=True, text=True,
                                   check=False).stdout.strip() if node else None,
            "git_branch": git("rev-parse", "--abbrev-ref", "HEAD"), "git_commit": git("rev-parse", "--short", "HEAD"),
            "uncommitted_changes": len(dirty),
            "requirements_sha256": hashlib.sha256((REPO / "requirements.txt").read_bytes()).hexdigest(),
            "packages": len([x for x in freeze.splitlines() if "==" in x]), "options": vars(F.args)}
    (env_dir / "versions.json").write_text(json.dumps(info, indent=2, default=str) + "\n")
    F.facts["git"] = {k: info[k] for k in ("git_branch", "git_commit", "uncommitted_changes")}
    F.record("environment", S, "Record the environment", "PASS",
             f"Python {v}, {info['packages']} packages, git {info['git_commit']} on {info['git_branch']}"
             f" (+{len(dirty)} uncommitted)", time.time() - t0)
    return F.ok("pip_install") or F.args.skip_install


def stage_keys(F: Flight) -> dict:
    """Credentials from .env, falling back to .venv/keys.txt. Names only are ever printed."""
    S = "2 collect"
    primary, backup = (read_keyfile(p) for p in KEY_FILES)
    merged = {**backup, **primary}
    for k, v in merged.items():
        F.env.setdefault(k, v)                    # values already in the shell win, as in the scripts
    have = lambda k: bool(os.environ.get(k) or merged.get(k))  # noqa: E731
    ready = {use: all(have(k) for k in keys) for use, keys in NEEDS.items()}
    notes, status = [], "PASS"
    if not KEY_FILES[0].exists():
        notes.append(".env not found")
    from_backup = sorted(k for k in backup if k not in primary)
    if from_backup:
        status = "WARN"
        notes.append(f"taken from .venv/keys.txt because .env lacks them: {', '.join(from_backup)}")
    differ = sorted(k for k in set(primary) & set(backup) if primary[k] != backup[k])
    if differ:
        status = "WARN"
        notes.append(f".env and .venv/keys.txt disagree on {', '.join(differ)} (.env used)")
    for use, keys in NEEDS.items():
        if not ready[use]:
            status = "FAIL"
            notes.append(f"{use} collection skipped, missing: {', '.join(k for k in keys if not have(k))}")
    F.record("keys", S, "Credentials present (.env, fallback .venv/keys.txt)", status,
             "; ".join(notes) or f"all {sum(map(len, NEEDS.values()))} needed keys present in .env; "
                                 ".venv/keys.txt matches")
    F.secrets = secret_values()
    return ready


def stage_collect(F: Flight) -> None:
    S = "2 collect"
    if F.args.offline:
        F.secrets = secret_values()
        for sid, t in (("reddit_collect", "Collect Reddit through the API"),
                       ("mapillary_coverage", "Mapillary coverage at the sample points"),
                       ("mapillary_images", "Download the 10 newest images")):
            F.skip(sid, S, t, "--offline")
        return
    ready = stage_keys(F)
    py = VPY

    # Reddit -------------------------------------------------------------
    raw = F.d("live", REDDIT_DS, "01_raw_collection")
    if not ready["reddit"]:
        F.skip("reddit_collect", S, "Collect Reddit through the API", "keys missing (see the keys step)")
    elif F.args.skip_reddit_collection:
        F.skip("reddit_collect", S, "Collect Reddit through the API", "--skip-reddit-collection")
    else:
        def reddit_note():
            n = reddit_numbers(raw.parent)
            return (f"{n['posts']} posts, {n['comments']:,} comments ({n['comments_in_window']:,} in window)"
                    if "posts" in n else "no collection files written")
        F.run("reddit_collect", S, f"Collect r/saskatoon {STUDY[0]} .. {STUDY[1]} through the Reddit API",
              [("probe", [py, SCRAPER, "--probe"]),
               ("collect", [py, SCRAPER, "--start", STUDY[0], "--end", STUDY[1], "--out", raw])],
              note_fn=reddit_note)

    # Mapillary ----------------------------------------------------------
    if not ready["mapillary"]:
        F.skip("mapillary_coverage", S, "Mapillary coverage at the sample points", "keys missing")
        F.skip("mapillary_images", S, "Download the 10 newest images", "keys missing")
        return
    pts = ["sample_points.csv", "sample_points.geojson", "run_meta.json"]   # published points, copied, never regenerated
    cov = F.d("live", "cv_coverage")
    if F.args.skip_coverage:
        F.skip("mapillary_coverage", S, "Mapillary coverage at the sample points", "--skip-coverage")
    else:
        copy_inputs(CBD, cov, pts)

        def cov_note():
            c = coverage_numbers(cov)
            return (f"{c['with_study_period_image']} of {c['points']} points have a Jun-Aug 2026 image; "
                    f"{c['with_any_image']} have any (newest by year: {c['newest_year']})")
        F.run("mapillary_coverage", S, "Mapillary coverage (every image within 30 m of each of the 423 points)",
              [("coverage", [py, PILOT_PY, "coverage", "--out", cov])], note_fn=cov_note)
    live_cv = F.d("live", "cv_pilot")
    copy_inputs(CBD, live_cv, pts)
    F.run("mapillary_images", S, "Download the newest image at 10 spread points (any date)",
          [("images", [py, PILOT_PY, "images", "--any-date", "--out", live_cv])],
          note_fn=lambda: (lambda n: f"{n.get('images')} images, capture years {n.get('capture_years')}")(
              pilot_numbers(live_cv)))


def stage_models(F: Flight) -> None:
    out = F.d("models") / "models.json"

    def note():
        m = json.loads(out.read_text())
        c, v = m["clip"], m["vader"]
        return (f"CLIP {c.get('model')} rev {str(c.get('revision'))[:7]} on {c.get('device')} "
                f"({c.get('status')}); VADER {v.get('version')} stock+adjusted ({v.get('status')})")
    F.run("load_models", "3 load models", "Load CLIP and VADER and smoke-test them",
          [("models", [VPY, REPO / "Scripts" / "flight" / "load_models.py", "--out", out])], note_fn=note)


def reddit_analysis(F: Flight, sid: str, title: str, raw: Path, out: Path, review: Path) -> None:
    """The run_all.sh steps on one collection, writing to out/ and using a copy of the review files."""
    shutil.copytree(REVIEW, review, dirs_exist_ok=True)
    env = dict(F.env, COMPUTERVISION_SENTINEL_RAW_DIR=str(raw), COMPUTERVISION_SENTINEL_OUT_DIR=str(out),
               COMPUTERVISION_SENTINEL_REVIEW_DIR=str(review))
    cmds = [(s, [VPY, s]) for s in analysis_steps()]
    pending = {"01b_other_city_review.py": (
        1, "new other-city candidates are 'pending' hand review (treated as keep; decide them in the manual_review/ copy)")}

    def note():
        n = reddit_numbers(out)
        d, sc = n.get("downtown", {}), n.get("self_checks", {})
        return (f"self-checks {sc.get('pass')} pass / {sc.get('fail')} fail; Downtown {d.get('records')} records, "
                f"{d.get('pct_negative')}% negative (95% CI {d.get('ci95')})") if d else ""
    F.run(sid, "4 results", title, cmds, cwd=ANALYSIS / "scripts", env=env, warn=pending, note_fn=note)


def stage_results(F: Flight) -> None:
    S = "4 results"
    py = VPY
    rep, live = F.d("reproduction"), F.exec_dir / "live"

    # Reddit: both published collections, then the fresh one ------------
    for ds, sid in ((REDDIT_DS, "reddit_reproduce_jun_aug"), (REDDIT_JUNE_DS, "reddit_reproduce_jun_2025")):
        reddit_analysis(F, sid, f"Rebuild {ds} from its committed raw files",
                        DATA / ds / "01_raw_collection", rep / ds, rep / "manual_review" / ds)
    if F.ok("reddit_collect"):
        reddit_analysis(F, "reddit_live", f"Analyse the fresh collection ({REDDIT_DS})",
                        live / REDDIT_DS / "01_raw_collection", live / REDDIT_DS, live / "manual_review")
    else:
        F.skip("reddit_live", S, "Analyse the fresh Reddit collection", "no fresh collection in this run")

    # The August 2026 package, rebuilt with its own code (one shared neighbourhoods.py) -------------
    aug_out = rep / "august_2026_package"
    F.run("august_reproduce", S, "Rebuild the August 2026 package with its own analysis code",
          [("run_all", ["bash", AUGUST / "analysis_code" / "run_all.sh", aug_out])],
          env=dict(F.env, PYTHON=str(VPY)),
          note_fn=lambda: f"{len(list((aug_out / 'output').glob('*')))} files rebuilt")

    # Crime ---------------------------------------------------------------
    crime_out = rep / SPS.name / "02_cleaned"
    F.run("crime_clean", S, "Clean the SPS extract (raw file hash-checked)",
          [("clean", [py, REPO / "Scripts" / "crime_data" / "clean_sps_crime.py", "--out", crime_out])],
          note_fn=lambda: (lambda r: f"{r['raw_rows']:,} records; by decision {r['rows_by_decision']}")(
              json.loads((crime_out / "cleaning_report.json").read_text())))

    # CV: the published 10-image pilot, then the fresh images -------------
    rep_cv = rep / "cv_pilot_cbd_latest_imagery"
    copy_inputs(PILOT, rep_cv, ["sample_points.csv", "sample_points.geojson", "run_meta.json", "image_manifest.csv",
                                "pilot_attempts.csv", "images"])
    F.run("cv_reproduce", S, "Re-score the 10 published pilot images with CLIP; Reddit link; pilot report",
          [(s, [py, PILOT_PY, s, "--out", rep_cv]) for s in ("score", "reddit", "report")],
          note_fn=lambda: (lambda n: f"{n.get('images')} images, {n.get('clip_low_confidence')} low-confidence")(
              pilot_numbers(rep_cv)))
    live_cv = live / "cv_pilot"
    if F.ok("mapillary_images"):
        rd = live / REDDIT_DS if F.ok("reddit_live") else DATA / REDDIT_DS
        F.run("cv_live", S, "CLIP-score the fresh images; Reddit link; pilot report",
              [("score", [py, PILOT_PY, "score", "--out", live_cv]),
               ("reddit", [py, PILOT_PY, "reddit", "--out", live_cv, "--reddit-dir", rd]),
               ("report", [py, PILOT_PY, "report", "--out", live_cv])],
              note_fn=lambda: (lambda n: f"{n.get('images')} images scored, {n.get('clip_low_confidence')} "
                                         f"low-confidence; Reddit from "
                                         f"{'this run' if rd != DATA / REDDIT_DS else 'Data/ (published)'}")(
                  pilot_numbers(live_cv)))
    else:
        F.skip("cv_live", S, "CLIP-score the fresh images", "no fresh images in this run")

    # Tests, verification, figures, numbers, report -----------------------
    F.run("cv_tests", S, "CV pilot tests (offline)",
          [("tests", [py, REPO / "Scripts" / "cv_pilot" / "tests" / "test_pilot.py"])],
          note_fn=lambda: (lambda t: f"{t.count('PASS test_')} passed, {t.count('FAIL test_')} failed")(
              (F.logs / f"{len(F.steps) + 1:02d}_cv_tests.log").read_text()))
    ver = F.d("verification")
    shutil.copy2(CBD / "osm_bridge_way_ids.json", ver / "osm_bridge_way_ids.json")
    review = rep / "manual_review" / "verification"
    shutil.copytree(REVIEW, review, dirs_exist_ok=True)
    cmd = [py, REPO / "Scripts" / "verification" / "verify_october_2026.py", "--rerun-pipeline",
           "--out", ver, "--bridge-cache", ver / "osm_bridge_way_ids.json"]
    if not F.args.offline:
        cmd.append("--network")

    def ver_note():
        rows = csv_rows(ver / "october_2026_checks.csv")
        tot = {s: sum(r["status"] == s for r in rows) for s in ("PASS", "WARN", "FAIL", "INFO")}
        return ", ".join(f"{k} {v}" for k, v in tot.items()) + " (imagery/placeholder FAILs are findings, not code errors)"
    F.run("verification", S, "Verification checks on every October claim (+ Reddit re-run, byte compare)",
          [("verify", cmd)], env=dict(F.env, COMPUTERVISION_SENTINEL_REVIEW_DIR=str(review)), note_fn=ver_note)
    figs = F.d("figures")
    F.run("figures", S, "Figures fig01-fig08",
          [("figures", [py, REPORTING / "make_figures.py", "--out", figs])],
          note_fn=lambda: f"{len(list(figs.glob('fig*.png')))} figures")
    report = F.d("report")
    numbers = report / "october_2026_numbers.json"
    checks = ver / "october_2026_checks.csv"
    if checks.exists():
        F.run("report_numbers", S, "Every number quoted in the report",
              [("numbers", [py, REPORTING / "report_numbers.py", "--checks", checks, "--out", numbers])])
    else:
        F.skip("report_numbers", S, "Every number quoted in the report", "no verification table")
    docx = report / "ComputerVision_Sentinel_October2026_Progress_Report.docx"
    if F.args.skip_report:
        F.skip("report_docx", S, "October report (.docx)", "--skip-report")
    elif not (shutil.which("node") and (REPORTING / "node_modules" / "docx").exists()):
        F.skip("report_docx", S, "October report (.docx)", "node or the docx package is missing (npm install)")
    elif not numbers.exists() or len(list(figs.glob("fig*.png"))) < 8:
        F.skip("report_docx", S, "October report (.docx)", "numbers or figures missing")
    else:
        F.run("report_docx", S, "October report (.docx), generated base",
              [("docx", ["node", REPORTING / "build_october_report.js", "--numbers", numbers,
                         "--figures", figs, "--out", docx])],
              note_fn=lambda: f"{docx.stat().st_size / 1e6:.1f} MB; the hand-edited CPTED_ComputerVis_2026.docx "
                              "is the version sent")

    # Notebooks 01-09: each one run top to bottom; the copies with outputs stay in this execution --------
    # (00_replicate_system runs the flight itself, so the flight never runs it)
    notebooks = sorted((REPO / "Notebooks").glob("0[1-9]_*.ipynb"))
    if notebooks:
        nb_out = F.d("notebooks")
        F.run("notebooks", S, f"Notebooks run top to bottom ({len(notebooks)})",
              [(nb.stem, [py, REPO / "Scripts" / "flight" / "run_notebook.py", nb, nb_out / nb.name])
               for nb in notebooks],
              note_fn=lambda: f"{len(list(nb_out.glob('*.ipynb')))} run; copies with outputs in notebooks/")
    else:
        F.skip("notebooks", S, "Notebooks run top to bottom", "no notebooks in Notebooks/")


def stage_checks(F: Flight, snapshot: dict) -> None:
    S = "5 checks"
    cmp_dir = F.d("comparisons")
    rep, live = F.exec_dir / "reproduction", F.exec_dir / "live"

    # 1. reproduction vs published, file by file --------------------------
    t0 = time.time()
    rows = []
    for ds in (REDDIT_DS, REDDIT_JUNE_DS):
        if (rep / ds).exists():
            rows += compare_tree(f"Reddit {ds}", rep / ds, DATA / ds, exclude=("01_raw_collection", "README.md"))
    aug_out = rep / "august_2026_package" / "output"
    if aug_out.exists():
        delivered = [AUGUST / "data_pkg_august" / d for d in
                     ("02_derived_analysis", "03_extracted_comment_samples", "04_cleaned_datasets")] + [AUGUST / "charts"]
        for d in delivered:
            for pub in sorted(list(d.glob("*.csv")) + list(d.glob("*.png"))):
                new = aug_out / pub.name
                st, note = compare_file(new, pub, tolerate_ties=True) if new.exists() else \
                    ("missing", "delivered, but this run did not produce it")
                rows.append({"area": "August 2026 package", "file": str(pub.relative_to(AUGUST)),
                             "status": st, "note": note})
    if (rep / SPS.name / "02_cleaned").exists():
        rows += compare_tree("SPS crime", rep / SPS.name / "02_cleaned", SPS / "02_cleaned")
    if (rep / "cv_pilot_cbd_latest_imagery").exists():
        rows += compare_tree("CV pilot (10 images)", rep / "cv_pilot_cbd_latest_imagery", PILOT,
                             exclude=("sample_points.csv", "sample_points.geojson", "image_manifest.csv",
                                      "pilot_attempts.csv", "images"))
    for name, new, pub in (("Review files", rep / "manual_review" / REDDIT_DS / "location_other_city_review.csv",
                            REVIEW / "location_other_city_review.csv"),):
        if new.exists():
            st, note = compare_file(new, pub)
            rows.append({"area": name, "file": "location_other_city_review.csv (after step 01b)", "status": st,
                         "note": note or "no new candidates"})
    if (F.exec_dir / "figures").exists():
        rows += compare_tree("Figures", F.exec_dir / "figures", FIGS)
    num = F.exec_dir / "report" / "october_2026_numbers.json"
    if num.exists():
        st, note = compare_file(num, VERIF / "october_2026_numbers.json")
        rows.append({"area": "Report numbers", "file": "october_2026_numbers.json", "status": st, "note": note})
    with open(cmp_dir / "reproduction_vs_published.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["area", "file", "status", "note"])
        w.writeheader()
        w.writerows(rows)
    chk_new = F.exec_dir / "verification" / "october_2026_checks.csv"
    chk_rows = compare_checks(chk_new, VERIF / "october_2026_checks.csv", F.args.offline) if chk_new.exists() else []
    with open(cmp_dir / "verification_checks_vs_published.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["area", "check", "published", "this_run", "why"])
        w.writeheader()
        w.writerows(chk_rows)
    by_area: dict = {}
    for r in rows:
        by_area.setdefault(r["area"], {k: 0 for k in ("identical", "equivalent", "differs", "missing", "new")})
        by_area[r["area"]][r["status"]] += 1
    F.facts["reproduction"] = {"by_area": by_area, "problems": [r for r in rows if r["status"] in ("differs", "missing")],
                               "checks_changed": chk_rows}
    bad = [r for r in rows if r["status"] in ("differs", "missing")]
    real_chk = [r for r in chk_rows if r["why"] == "check this"]
    status = "FAIL" if bad or real_chk else "WARN" if chk_rows else "PASS"
    same = sum(r["status"] in ("identical", "equivalent") for r in rows)
    F.record("compare_reproduction", S, "Rebuilt outputs vs the published files", status,
             f"{same} of {len(rows)} files match the published copy"
             + (f"; {len(bad)} differ or are missing" if bad else "")
             + (f"; {len(chk_rows)} verification row(s) changed ({len(chk_rows) - len(real_chk)} re-queried live)"
                if chk_rows else ""), time.time() - t0, log=cmp_dir / "reproduction_vs_published.csv")

    # 2. fresh collection vs published --------------------------------------
    t0 = time.time()
    lv = {}
    if (live / REDDIT_DS / "01_raw_collection").exists():
        pub, new = reddit_numbers(DATA / REDDIT_DS), reddit_numbers(live / REDDIT_DS)
        if new.get("post_ids"):
            ids_p, ids_n = set(pub.get("post_ids", [])), set(new["post_ids"])
            lv["reddit"] = {"published": {k: v for k, v in pub.items() if k != "post_ids"},
                            "this_run": {k: v for k, v in new.items() if k != "post_ids"},
                            "posts_in_both": len(ids_p & ids_n), "posts_only_published": len(ids_p - ids_n),
                            "posts_only_this_run": len(ids_n - ids_p)}
        pend = live / "manual_review" / "location_other_city_review.csv"
        if pend.exists():
            lv.setdefault("reddit", {})["review_pending"] = sum(r["decision"] == "pending" for r in csv_rows(pend))
    if (live / "cv_coverage" / "coverage_points.csv").exists():
        lv["coverage"] = {"published": coverage_numbers(CBD), "this_run": coverage_numbers(live / "cv_coverage")}
    if (live / "cv_pilot" / "image_manifest.csv").exists():
        lv["pilot"] = {"published": pilot_numbers(PILOT), "this_run": pilot_numbers(live / "cv_pilot")}
    (cmp_dir / "live_vs_published.json").write_text(json.dumps(lv, indent=2) + "\n")
    F.facts["live"] = lv
    if lv:
        F.record("compare_live", S, "Fresh collection vs the published numbers", "PASS",
                 "see FLIGHT_SUMMARY.md (differences are expected: Reddit changes over time)",
                 time.time() - t0, log=cmp_dir / "live_vs_published.json")
    else:
        F.skip("compare_live", S, "Fresh collection vs the published numbers", "nothing collected in this run")

    # 3. the repository was not written to ----------------------------------
    t0 = time.time()
    after = tree_snapshot(F.root.resolve())
    changed = sorted(k for k in set(snapshot) | set(after) if snapshot.get(k) != after.get(k))
    (cmp_dir / "repository_files_changed.txt").write_text("\n".join(changed) + ("\n" if changed else ""))
    F.facts["repo_changed"] = changed
    F.record("repo_untouched", S, "Data/, Docs/, Deliverables/, Scripts/, Notebooks/ unchanged by the flight",
             "FAIL" if changed else "PASS",
             f"{len(changed)} file(s) changed: {', '.join(changed[:5])}" if changed else
             f"{len(snapshot):,} files checked, none changed", time.time() - t0)

    # 4. no credential value anywhere in this execution ---------------------
    t0 = time.time()
    secrets = [s.encode() for s in getattr(F, "secrets", [])]
    hits, n = [], 0
    for p in F.exec_dir.rglob("*"):
        if p.is_file() and p != F.logs / "flight.log":
            n += 1
            data = p.read_bytes()
            if any(s in data for s in secrets):
                hits.append(F.rel(p))
    data = (F.logs / "flight.log").read_bytes()
    if any(s in data for s in secrets):
        hits.append("logs/flight.log")
    F.record("secret_scan", S, "No credential value in any file of this execution",
             "FAIL" if hits else "PASS" if secrets else "WARN",
             f"credential values found in: {', '.join(hits)}" if hits else
             f"{n:,} files scanned for {len(secrets)} credential values: none found" if secrets else
             "no credentials loaded, nothing to scan for", time.time() - t0)


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #
def overall(F: Flight) -> str:
    st = [s["status"] for s in F.steps]
    return "FAIL" if "FAIL" in st else "WARN" if "WARN" in st else "PASS"


def write_summary(F: Flight, interrupted: bool = False) -> None:
    fin, secs = now(), time.time() - F.t0
    status = "INTERRUPTED" if interrupted else overall(F)
    counts = {s: sum(x["status"] == s for x in F.steps) for s in STATUSES}
    js = {"execution": F.name, "status": status, "started_utc": F.started, "finished_utc": fin,
          "seconds": round(secs), "counts": counts,
          "options": {k: str(v) if isinstance(v, Path) else v for k, v in vars(F.args).items()},
          "facts": F.facts, "steps": F.steps}
    (F.exec_dir / "flight_status.json").write_text(json.dumps(js, indent=2, default=str) + "\n")

    g = F.facts.get("git", {})
    L = [f"# Flight {F.name}: {status}", "",
         f"Started {F.started}, finished {fin} ({hms(secs)}). Git `{g.get('git_commit', '?')}` on "
         f"`{g.get('git_branch', '?')}` with {g.get('uncommitted_changes', '?')} uncommitted changes. "
         f"Command: `./flight {' '.join(sys.argv[1:])}`.", "",
         "PASS = worked as designed; WARN = worked, with a known limitation (see the note); "
         "FAIL = did not work, read its log; SKIP = not run (reason given).", "",
         "## Stages", "", "| Stage | PASS | WARN | FAIL | SKIP |", "|---|---|---|---|---|"]
    for stage in dict.fromkeys(s["stage"] for s in F.steps):
        c = {k: sum(1 for s in F.steps if s["stage"] == stage and s["status"] == k) for k in STATUSES}
        L.append(f"| {stage} | {c['PASS']} | {c['WARN']} | {c['FAIL']} | {c['SKIP']} |")
    L += ["", "## Steps", "", "| # | Step | Status | Time | Result | Log |", "|---|---|---|---|---|---|"]
    for s in F.steps:
        note = str(s["note"]).replace("|", "/").replace("\n", " ")
        L.append(f"| {s['n']} | {s['title']} (`{s['id']}`) | **{s['status']}** | {hms(s['seconds'])} | {note} | "
                 + (f"[{s['log']}]({s['log']})" if s["log"] else "") + " |")

    r = F.facts.get("reproduction")
    if r:
        L += ["", "## Reproduction: rebuilt from the committed raw data, compared with the published files", "",
              "identical = same bytes; equivalent = differs only where a run stamps its own time "
              "(workbook creation time, report header, run_meta timestamps).", "",
              "| Area | identical | equivalent | differs | missing | new |", "|---|---|---|---|---|---|"]
        for a, c in r["by_area"].items():
            L.append(f"| {a} | {c['identical']} | {c['equivalent']} | {c['differs']} | {c['missing']} | {c['new']} |")
        if r["problems"]:
            L += ["", "Files that differ or are missing:", ""]
            L += [f"- {p['area']}: `{p['file']}` ({p['status']}): {p['note']}" for p in r["problems"]]
        if r["checks_changed"]:
            L += ["", "Verification rows that changed from `Docs/verification/october_2026_checks.csv`:", ""]
            L += [f"- {c['area']} / {c['check']}: published *{c['published']}*; this run *{c['this_run']}* "
                  f"({c['why']})" for c in r["checks_changed"]]
        L += ["", "Full list: `comparisons/reproduction_vs_published.csv`, `comparisons/verification_checks_vs_published.csv`."]

    lv = F.facts.get("live")
    if lv:
        L += ["", "## Fresh collection (this run) vs the published data", "",
              "| Measure | Published | This run |", "|---|---|---|"]
        rd = lv.get("reddit", {})
        p, n = rd.get("published", {}), rd.get("this_run", {})
        if n:
            for k, label in (("posts", "Posts, 1 Jun - 31 Aug 2026"), ("comments", "Comments"),
                             ("comments_in_window", "Comments posted inside the window")):
                L.append(f"| {label} | {p.get(k, '')} | {n.get(k, '')} |")
            L.append(f"| Posts found by both / only published / only this run | | {rd.get('posts_in_both')} / "
                     f"{rd.get('posts_only_published')} / {rd.get('posts_only_this_run')} |")
            pd_, nd = p.get("downtown", {}), n.get("downtown", {})
            L.append(f"| Downtown records | {pd_.get('records', '')} | {nd.get('records', '')} |")
            L.append(f"| Downtown % negative (95% CI) | {pd_.get('pct_negative', '')} ({pd_.get('ci95', '')}) | "
                     f"{nd.get('pct_negative', '')} ({nd.get('ci95', '')}) |")
            L.append(f"| Pipeline self-checks pass / fail | {p.get('self_checks', {}).get('pass', '')} / "
                     f"{p.get('self_checks', {}).get('fail', '')} | {n.get('self_checks', {}).get('pass', '')} / "
                     f"{n.get('self_checks', {}).get('fail', '')} |")
        if "review_pending" in rd:
            L.append(f"| Other-city candidates pending hand review | 0 | {rd['review_pending']} |")
        cv = lv.get("coverage")
        if cv:
            cp, cn = cv["published"], cv["this_run"]
            L.append(f"| Points with a Jun-Aug 2026 Mapillary image (Decision D1) | {cp.get('with_study_period_image')} "
                     f"of {cp.get('points')} | {cn.get('with_study_period_image')} of {cn.get('points')} |")
            L.append(f"| Points with any image | {cp.get('with_any_image')} | {cn.get('with_any_image')} |")
            L.append(f"| Newest image at each point, by year | {cp.get('newest_year')} | {cn.get('newest_year')} |")
        pl = lv.get("pilot")
        if pl:
            pp, pn = pl["published"], pl["this_run"]
            L.append(f"| Pilot images (capture years) | {pp.get('images')} ({pp.get('capture_years')}) | "
                     f"{pn.get('images')} ({pn.get('capture_years')}) |")
            L.append(f"| CLIP low-confidence labels | {pp.get('clip_low_confidence')} | {pn.get('clip_low_confidence')} |")
        L += ["", "Reddit changes after collection (edits, deletions, new comments), so these numbers are expected to "
                  "drift; they are not the published results. Full numbers: `comparisons/live_vs_published.json`."]

    L += ["", "## Where everything is", "", "```",
          f"{F.name}/",
          "  FLIGHT_SUMMARY.md        this page",
          "  flight_status.json       every step, status, time, note, log (machine-readable)",
          "  logs/                    flight.log (the run) and one log per step",
          "  environment/             versions.json, pip_freeze.txt, requirements.txt, git_status.txt",
          "  models/models.json       what CLIP and VADER were loaded, and their smoke tests",
          "  live/                    fresh API data and its analysis (Reddit dataset, Mapillary coverage, pilot)",
          "  reproduction/            published outputs rebuilt from the committed raw data (incl. the August package)",
          "  verification/            october_2026_checks.csv/.md",
          "  figures/                 fig01-fig08",
          "  report/                  october_2026_numbers.json, the October report .docx",
          "  comparisons/             reproduction_vs_published.csv, verification_checks_vs_published.csv,",
          "                           live_vs_published.json, repository_files_changed.txt",
          "```", "",
          "`live/` and `reproduction/` hold Reddit text (and `_local_audit_do_not_share/` snippets): internal only "
          "(Docs/data_ethics.md)."]
    if interrupted:
        L += ["", "**Interrupted** before every step ran; the table above lists the steps that did."]
    (F.exec_dir / "FLIGHT_SUMMARY.md").write_text("\n".join(L) + "\n")

    idx = F.root / "executions.csv"
    new = not idx.exists()
    with open(idx, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["execution", "status", "started_utc", "finished_utc", "minutes", "pass", "warn", "fail", "skip",
                        "git_commit", "uncommitted_changes", "options"])
        w.writerow([F.name, status, F.started, fin, round(secs / 60, 1), counts["PASS"], counts["WARN"],
                    counts["FAIL"], counts["SKIP"], g.get("git_commit"), g.get("uncommitted_changes"),
                    " ".join(sys.argv[1:])])


def guarded(F: Flight, name: str, stage):
    """Run one stage; an unexpected error in the flight itself becomes a FAIL step and the flight goes on."""
    try:
        return stage(F)
    except Exception as e:                                  # noqa: BLE001
        import traceback
        log = F.logs / f"flight_error_{name}.log"
        log.write_text(traceback.format_exc())
        F.record(f"flight_error_{name}", "flight", f"Unexpected error in the {name} stage", "FAIL",
                 f"{type(e).__name__}: {e}", log=log)
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="./flight", description=__doc__.split("\n\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("USAGE")[1])
    ap.add_argument("--execute_flight", action="store_true", help="run the flight (required)")
    ap.add_argument("--offline", action="store_true", help="no API calls: skip stage 2 and the live analysis")
    ap.add_argument("--skip-install", action="store_true", help="skip pip/npm installs (environment still recorded)")
    ap.add_argument("--skip-reddit-collection", action="store_true", help="skip the Reddit API collection (~10 min)")
    ap.add_argument("--skip-coverage", action="store_true", help="skip the Mapillary coverage audit (slowest API step)")
    ap.add_argument("--skip-report", action="store_true", help="skip building the .docx")
    ap.add_argument("--results-root", type=Path, default=REPO / "RESULTS_FINAL",
                    help="where EXECUTION-<n>/ folders go (default: RESULTS_FINAL/ at the repository root)")
    a = ap.parse_args(argv)
    if not a.execute_flight:
        ap.print_help()
        print("\nNothing run: add --execute_flight.")
        return 2

    F = Flight(a.results_root.resolve(), a)
    F.say(f"ComputerVision_Sentinel flight {F.name} -> {F.exec_dir}")
    snapshot = tree_snapshot(F.root)
    try:
        if guarded(F, "install", stage_install):
            for stage in (stage_collect, stage_models, stage_results):
                guarded(F, stage.__name__.removeprefix("stage_"), stage)
        else:
            F.say("Install failed: nothing else can run. See the pip_install log.")
        guarded(F, "checks", lambda f: stage_checks(f, snapshot))
    except KeyboardInterrupt:
        F.say("Interrupted.")
        write_summary(F, interrupted=True)
        return 130
    write_summary(F)
    st = overall(F)
    F.say(f"\nFlight {F.name}: {st}  ({hms(time.time() - F.t0)})\nSummary: {F.exec_dir / 'FLIGHT_SUMMARY.md'}")
    return 1 if st == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
