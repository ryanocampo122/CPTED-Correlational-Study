#!/usr/bin/env python3
"""
make_pipeline_diagram.py
========================
ComputerVision_Sentinel | The research workflow and data pipeline, for the main README

Three lanes (X built environment, Y1 recorded crime, Y2 perceived safety), each from its source through
collection, model or cleaning, to its measure; the lanes meet in the three research questions. Solid boxes run
in ./flight --execute_flight today; dashed boxes are planned. Counts are read from Data/, never typed in.
Colours and type come from make_figures.py, so this figure matches the report's.

USAGE (repository root):  .venv/bin/python Scripts/reporting/make_pipeline_diagram.py [--out <png>]
  --out defaults to Docs/figures/pipeline_overview.png (the image in README.md)
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

from make_figures import AQUA, BLUE, DPI, GREY, GREY_L, INK, INK_2, ORANGE, SURFACE, tint

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "Data"
OUT = REPO / "Docs" / "figures" / "pipeline_overview.png"

W, H = 12.2, 11.5                       # figure size, inches; drawing units are inches too
LEFT = 2.0                              # lanes start here; stage names sit to the left
LANE_W, LANE_GAP = 3.15, 0.25
BOX_H, ROW_GAP = 1.1, 0.36


def counts() -> dict:
    """The numbers shown in the boxes, from the published data."""
    with open(DATA / "cv_pilot_2026-10" / "cbd" / "sample_points.csv", newline="", encoding="utf-8") as f:
        pts = list(csv.DictReader(f))
    prompts = json.loads((REPO / "Scripts" / "cv_pilot" / "clip_prompts.json").read_text(encoding="utf-8"))
    meta = json.loads(next((DATA / "reddit_2026-06-01_2026-08-31" / "01_raw_collection")
                           .glob("saskatoon_safety_metadata_*.json")).read_text(encoding="utf-8"))
    reddit_checks = (DATA / "reddit_2026-06-01_2026-08-31" / "05_audits" / "verification_report.txt").read_text(
        encoding="utf-8").count("[PASS]")
    with open(DATA / "cv_pilot_2026-10" / "cbd_latest_imagery" / "image_manifest.csv", newline="",
              encoding="utf-8") as f:
        pilot_images = sum(1 for _ in csv.DictReader(f))
    sps = DATA / "sps_crime_2026-06-01_2026-08-31" / "02_cleaned"
    report = json.loads((sps / "cleaning_report.json").read_text(encoding="utf-8"))
    with open(sps / "category_counts.csv", newline="", encoding="utf-8") as f:
        cats = [r for r in csv.DictReader(f) if r["category_decision"] in ("included", "conditional")]
    return {"points": len(pts), "segments": len({p["segment_id"] for p in pts}), "cues": len(prompts["cues"]),
            "posts": meta["posts_collected"], "comments": meta["comments_collected"],
            "sps_rows": report["raw_rows"], "categories": len(cats), "reddit_checks": reddit_checks,
            "pilot_images": pilot_images}


def lane_x(i: int) -> float:
    return LEFT + i * (LANE_W + LANE_GAP)


def row_y(j: int) -> float:
    """Bottom edge of stage row j (0 = Source, at the top)."""
    return 8.05 - j * (BOX_H + ROW_GAP)


def box(ax, x, y, w, h, colour, title, lines, planned=False):
    """One step: lane-tinted with a solid border if built, white with a dashed grey border if planned."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.09",
                                facecolor=SURFACE if planned else tint(colour, 0.10),
                                edgecolor=GREY if planned else colour, linewidth=1.5,
                                linestyle=(0, (4, 3)) if planned else "-"))
    ink = INK_2 if planned else INK
    ax.text(x + 0.16, y + h - 0.2, title, fontsize=11, weight="bold", color=ink, va="top")
    ax.text(x + 0.16, y + h - 0.47, "\n".join(lines), fontsize=9.8, color=ink, va="top", linespacing=1.35)


def arrow(ax, x, y0, y1, planned=False):
    ax.annotate("", xy=(x, y1), xytext=(x, y0),
                arrowprops={"arrowstyle": "-|>", "color": INK_2, "lw": 1.2, "mutation_scale": 13,
                            "linestyle": (0, (3, 2)) if planned else "-", "shrinkA": 0, "shrinkB": 0})


def draw(out: Path) -> None:
    n = counts()
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    ax.text(0.25, H - 0.35, "How the study works: from open data to the research questions",
            fontsize=15, weight="bold", color=INK, va="top")
    ax.text(0.25, H - 0.82, "Saskatoon Downtown (CBD) street segments, 1 June – 31 August 2026",
            fontsize=10.5, color=INK_2, va="top")
    # legend: what solid and dashed mean (never colour alone)
    lx = W - 4.35
    for k, (label, planned) in enumerate((("built: runs in ./flight today", False), ("planned", True))):
        x = lx + k * 2.75
        ax.add_patch(FancyBboxPatch((x, H - 0.78), 0.34, 0.22, boxstyle="round,pad=0,rounding_size=0.04",
                                    facecolor=SURFACE if planned else tint(INK_2, 0.08),
                                    edgecolor=GREY if planned else INK_2, linewidth=1.3,
                                    linestyle=(0, (3, 2)) if planned else "-"))
        ax.text(x + 0.45, H - 0.67, label, fontsize=9.8, color=INK, va="center")

    lanes = [(BLUE, "X", "Built environment", "street-level imagery"),
             (ORANGE, "Y1", "Recorded crime", "Saskatoon Police Service"),
             (AQUA, "Y2", "Perceived safety", "Reddit, r/saskatoon")]
    for i, (colour, var, name, sub) in enumerate(lanes):
        x = lane_x(i)
        ax.add_patch(Rectangle((x, 9.98), LANE_W, 0.09, facecolor=colour, edgecolor="none"))
        ax.text(x, 9.84, f"{var}  {name}", fontsize=12.5, weight="bold", color=INK, va="top")
        ax.text(x, 9.52, sub, fontsize=9.8, color=INK_2, va="top")

    stages = ["Source", "Collect", "Model / clean", "Measure"]
    for j, s in enumerate(stages):
        ax.text(0.25, row_y(j) + BOX_H / 2, s, fontsize=11.5, weight="bold", color=INK, va="center")

    steps = [  # lane -> per stage: (title, detail lines, planned)
        [("OpenStreetMap + Mapillary", ["streets and the CBD boundary;", "street-level photos (API)"], False),
         ("Sample points + photos", [f"{n['points']} points ~50 m apart on", f"{n['segments']} street segments;",
                                     "newest photo at each point"], False),
         ("CLIP ViT-B/32 (zero-shot)", [f"land use and {n['cues']} CPTED cues", "per photo; run on the",
                                        f"{n['pilot_images']}-image pilot so far"], False),
         ("CPTED indicators", ["combined per CPTED principle,", "averaged per street segment"], True)],
        [("SPS offence extract", [f"{n['sps_rows']:,} records, Jun – Aug 2026", "(file from the police service)"],
          False),
         ("Raw file kept unchanged", ["SHA-256 checked on every run"], False),
         ("clean_sps_crime.py", [f"{n['categories']} study categories, CBD flag;", "nothing dropped, all labelled"],
          False),
         ("Crime counts", ["per street segment;", "hot spots"], True)],
        [("Reddit API", [f"{n['posts']} posts, {n['comments']:,} comments", "(r/saskatoon, Jun – Aug 2026)"], False),
         ("reddit_scraper.py", ["safety and crime search terms;", "authors replaced by salted hashes"], False),
         ("VADER sentiment (adjusted)", ["places and cues tagged", f"(run_all.sh, {n['reddit_checks']} self-checks)"],
          False),
         ("Share negative", ["per neighbourhood,", "95% CI (thread bootstrap)"], False)],
    ]
    for i, (colour, *_) in enumerate(lanes):
        x = lane_x(i)
        for j, (title, lines, planned) in enumerate(steps[i]):
            box(ax, x, row_y(j), LANE_W, BOX_H, colour, title, lines, planned)
            if j:
                arrow(ax, x + LANE_W / 2, row_y(j - 1), row_y(j) + BOX_H, planned)

    # integration: where the three measures meet (planned)
    iy, ih = 1.62, 1.55
    ix0, ix1 = lane_x(0), lane_x(2) + LANE_W
    for i in range(3):
        arrow(ax, lane_x(i) + LANE_W / 2, row_y(3), iy + ih, planned=True)
    box(ax, ix0, iy, ix1 - ix0, ih, INK_2, "Integration: the three research questions (Feb – Mar 2027)", [], True)
    rqs = [("RQ1   X ↔ Y1", "on street segments"), ("RQ2   X ↔ Y2", "by neighbourhood"),
           ("RQ3   Y1 ↔ Y2", "by neighbourhood")]
    for i, (rq, unit) in enumerate(rqs):
        ax.text(lane_x(i) + 0.16, iy + ih - 0.58, rq, fontsize=11, weight="bold", color=INK_2, va="top")
        ax.text(lane_x(i) + 0.16, iy + ih - 0.86, unit, fontsize=9.8, color=INK_2, va="top")
    ax.text(ix0 + 0.16, iy + 0.2, "Spearman correlation · bivariate Moran's I · LISA. "
            "Reddit places posts by neighbourhood, not street (Decision D2).",
            fontsize=9.8, color=INK_2, va="bottom")

    # the one command that runs the built boxes
    fy = 0.25
    ax.add_patch(FancyBboxPatch((0.25, fy), W - 0.5, 1.05, boxstyle="round,pad=0,rounding_size=0.09",
                                facecolor=GREY_L, edgecolor="none"))
    ax.text(0.45, fy + 0.8, "./flight --execute_flight", fontsize=11.5, weight="bold", color=INK, va="center",
            family="DejaVu Sans Mono")
    ax.text(0.45, fy + 0.32, "1 Install  →  2 Collect (APIs)  →  3 Load models  →  4 Results  →  5 Checks"
            "   ⇒   RESULTS_FINAL/EXECUTION-<n>/", fontsize=10.2, color=INK, va="center")
    ax.text(W - 0.45, fy + 0.8, "every published output rebuilt from raw data and compared file by file",
            fontsize=9.8, color=INK_2, va="center", ha="right")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUT, help="PNG to write (default: %(default)s)")
    draw(ap.parse_args().out)


if __name__ == "__main__":
    main()
