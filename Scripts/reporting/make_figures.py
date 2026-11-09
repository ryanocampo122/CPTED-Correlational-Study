#!/usr/bin/env python3
"""
make_figures.py
===============
ComputerVision_Sentinel | Figures for the October 2026 update and the Docs/ pages

Every number is read from Data/ (or Docs/verification/); nothing is typed in by
hand except the workflow statuses in WORKFLOW, which mirror
Docs/verification/october_2026_checks.md and the work plan.

  fig01_workflow_status.png     the research workflow, coloured by status (16 Oct 2026)
  fig02_timeline.png            work-plan timeline with October status
  fig03_reddit_by_area.png      Jun-Aug 2026: share of negative mentions by area, 95% CI
  fig04_reddit_weekly.png       Jun-Aug 2026: posts per week (collection coverage)
  fig05_sample_points_map.png   placeholder box vs CBD; newest imagery year at each point
  fig06_imagery_by_year.png     CBD points by year of their newest street-level image
  fig07_pilot_images.png        four pilot images: what works and what needs fixing
  fig08_reddit_place_anchors.png  how finely Reddit can be placed inside Downtown

USAGE (repository root):  .venv/bin/python Scripts/reporting/make_figures.py [--out <folder>]
  --out defaults to Docs/figures/mid_point_october/ (the published figures)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from PIL import Image  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "Data"
REDDIT = DATA / "reddit_2026-06-01_2026-08-31"
CV = DATA / "cv_pilot_2026-10"
BND = DATA / "boundaries"
OUT = REPO / "Docs" / "figures" / "mid_point_october"      # --out overrides

# Reference palette (validated: Scripts/reporting/README.md)
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SEQ = ["#86b6ef", "#5598e7", "#256abf", "#104281"]          # ordinal blue, light -> dark
GREY, GREY_L = "#b9b8b3", "#e4e3df"
INK, INK_2 = "#0b0b0b", "#52514e"
SURFACE = "#ffffff"
STATUS = {  # status colours always travel with an icon and a word
    "done": ("#0ca30c", "\u2713", "Done"),
    "partial": ("#fab219", "\u25D0", "Started (pilot)"),
    "blocked": ("#d03b3b", "\u2715", "Decision needed"),
    "planned": (GREY, "\u25CB", "Planned"),
}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5,
    "axes.edgecolor": INK_2, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK_2, "ytick.color": INK_2,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.grid": True, "grid.color": GREY_L, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False,
})
DPI = 220


def save(fig, name: str) -> None:
    """Save to OUT/name at DPI and close the figure."""
    fig.savefig(OUT / name, dpi=DPI, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT / name)


def tint(hex_: str, a: float = 0.13) -> tuple:
    """Pale RGB tint of a hex colour: share a of the colour, the rest white."""
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return (1 - a + a * r, 1 - a + a * g, 1 - a + a * b)


# --------------------------------------------------------------------------- #
# 1. Workflow
# --------------------------------------------------------------------------- #
ROWS = [
    ("Reddit posts", "how safe people feel"),
    ("Street images", "what streets look like"),
    ("Police crime data", "recorded crime"),
    ("Background data", "light, noise, census"),
]
COLS = ["1. Collect  (Oct)", "2. Analyse  (Nov \u2013 Jan)", "3. Check accuracy  (Nov \u2013 Jan)"]
WORKFLOW = [
    [("done", "195 posts, 6,452 comments\nJune\u2013August 2026"),
     ("done", "Places and tone tagged;\nresults reproduce exactly"),
     ("partial", "Tags checked: first pass\n(30 examples per topic);\nby hand next")],
    [("done", "Collection method validated:\n10 Mapillary images sourced"),
     ("done", "CLIP ViT-B/32 model\nvalidated to analyse in the\npipeline on a small sample"),
     ("done", "Scoring validated on a\nsmall sample (10 images);\n~150-image check next")],
    [("done", "Crime types chosen;\ndata obtained"),
     ("planned", "Count crimes per street;\nmap hot spots"),
     ("planned", "Check crime locations\nare precise enough")],
    [("planned", "Road, bus and census\ndata to gather"),
     ("planned", "Estimate noise; count\nstreetlights in images"),
     ("planned", "Spot-check against\nthe images")],
]


def box(ax, x, y, w, h, status, text, fs=7.0):
    """Workflow-figure box: status icon and label on a tint of the status colour."""
    col, icon, _ = STATUS[status]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.8",
                                fc=tint(col), ec=col, lw=1.1))
    ax.text(x + 1.3, y + h / 2, icon, ha="left", va="center", fontsize=9.5, color=col, weight="bold")
    ax.text(x + 5.2, y + h / 2, text, ha="left", va="center", fontsize=fs, color=INK, linespacing=1.3)


def draw_workflow(workflow: list, decide_note: str | None = None, partial_label: str = "Started (pilot)"):
    """Draw the workflow figure: one row per data source and one column per stage, then the compare and share rows.

    :param workflow: status and text of every box, laid out like WORKFLOW
    :param decide_note: a "to decide" line for the compare row, or None for no such line
    :param partial_label: the legend word for the half-done status
    :return: the figure
    """
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    fig.subplots_adjust(left=0.005, right=0.995, top=0.995, bottom=0.08)
    ax.set_xlim(0, 100), ax.set_ylim(0, 76), ax.axis("off")
    x0, gap = 17.0, 0.8
    cw = (100 - x0 - 2 * gap) / 3
    rh, rgap, ytop = 9.6, 1.4, 70.5
    for j, c in enumerate(COLS):
        ax.text(x0 + j * (cw + gap) + cw / 2, ytop + 1.4, c, ha="center", va="bottom", fontsize=7.4,
                weight="bold", color=INK)
    for i, (name, sub) in enumerate(ROWS):
        y = ytop - (i + 1) * rh - i * rgap
        ax.text(0.3, y + rh / 2 + 1.5, name, ha="left", va="center", fontsize=7.6, weight="bold")
        ax.text(0.3, y + rh / 2 - 1.9, sub, ha="left", va="center", fontsize=6.7, color=INK_2)
        for j, (st, txt) in enumerate(workflow[i]):
            box(ax, x0 + j * (cw + gap), y, cw, rh, st, txt)
    ygrid = ytop - 4 * rh - 3 * rgap
    ax.annotate("", xy=(x0 + (100 - x0) / 2, ygrid - 3.2), xytext=(x0 + (100 - x0) / 2, ygrid - 0.3),
                arrowprops=dict(arrowstyle="-|>", color=INK_2, lw=0.9, mutation_scale=8))
    # integration row
    yi, hi = ygrid - 14.6, 11.2
    # Compare row text, with the "to decide" line only when one is given
    compare = ("Put all the data on the same streets and test three questions:  (1) do street features match where\n"
               "crime happens?  (2) do they match how safe people feel?  (3) does how safe people feel match crime?")
    if decide_note:
        compare += "\n\u2715 " + decide_note
    box(ax, x0, yi, 100 - x0, hi, "planned", compare, fs=6.9)
    ax.text(0.3, yi + hi / 2 + 1.5, "4. Compare", ha="left", va="center", fontsize=7.6, weight="bold")
    ax.text(0.3, yi + hi / 2 - 1.9, "Feb \u2013 Mar 2027", ha="left", va="center", fontsize=6.7, color=INK_2)
    yo, ho = yi - 8.4, 6.6
    box(ax, x0, yo, 100 - x0, ho, "planned",
        "Summary for the City's CPTED team  \u00b7  research paper  \u00b7  code and data handed over", fs=6.9)
    ax.text(0.3, yo + ho / 2 + 1.5, "5. Share", ha="left", va="center", fontsize=7.6, weight="bold")
    ax.text(0.3, yo + ho / 2 - 1.9, "Apr \u2013 May 2027", ha="left", va="center", fontsize=6.7, color=INK_2)
    # Legend: the statuses in the boxes, "planned" for the compare and share rows, and "decision needed" only with
    # a "to decide" line; the half-done status can carry its own word
    used = {st for row in workflow for st, _ in row} | {"planned"} | ({"blocked"} if decide_note else set())
    words = {**{k: lab for k, (_, _, lab) in STATUS.items()}, "partial": partial_label}
    handles = [Patch(fc=tint(c), ec=c, label=f"{i}  {words[k]}") for k, (c, i, _) in STATUS.items() if k in used]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 0.0), ncol=4, frameon=False,
              fontsize=6.6, handlelength=1.2, columnspacing=0.9)
    return fig


def fig_workflow():
    """fig01: the October workflow figure, with the open Reddit decision as it was sent."""
    save(draw_workflow(WORKFLOW, "To decide: Reddit can only be placed by neighbourhood, not street by street."),
         "fig01_workflow_status.png")


# --------------------------------------------------------------------------- #
# 2. Timeline
# --------------------------------------------------------------------------- #
TIMELINE = [
    ("Choose crime types, get data", "2026-10-01", "2026-10-31", "done"),
    ("Collect Reddit, Jun\u2013Aug 2026", "2026-10-01", "2026-10-31", "done"),
    ("Collect crime statistics", "2026-10-01", "2026-10-31", "done"),
    ("Collect street images", "2026-10-01", "2026-10-31", "done"),
    ("Analyse images with CLIP ViT-B/32", "2026-11-01", "2026-11-30", "partial"),
    ("Check CLIP ViT-B/32 on 150 labelled images", "2026-11-01", "2026-11-30", "partial"),
    ("Map crime hot spots", "2026-11-01", "2026-11-30", "planned"),
    ("Code Reddit posts by hand", "2026-12-01", "2027-01-31", "planned"),
    ("Build lighting and noise maps", "2026-12-01", "2027-01-31", "planned"),
    ("Test how the data relate", "2027-02-01", "2027-03-31", "planned"),
    ("Find where fear and crime differ", "2027-02-01", "2027-03-31", "planned"),
    ("Summary, paper, hand-over", "2027-04-01", "2027-05-31", "planned"),
]


# Short notes drawn to the right of a bar (the row is empty after October).
TIMELINE_NOTES = {
    "Collect street images": "Collection method validated: 10 Mapillary images sourced and\n"
                             "read by CLIP ViT-B/32 (the full study set is sourced next)",
}


def fig_timeline():
    fig, ax = plt.subplots(figsize=(6.6, 3.5))
    t0 = pd.Timestamp("2026-10-01")

    for i, (lab, s, e, st) in enumerate(TIMELINE):
        col, icon, _ = STATUS[st]
        a, b = (pd.Timestamp(s) - t0).days, (pd.Timestamp(e) - t0).days + 1
        ax.barh(i, b - a, left=a, height=0.62, color=tint(col, 0.35), edgecolor=col, lw=1)
        ax.text(a + 2, i, icon, va="center", ha="left", fontsize=8, color=INK, weight="bold")
        if lab in TIMELINE_NOTES:
            ax.text(b + 3, i, TIMELINE_NOTES[lab], va="center", ha="left", fontsize=6.6, color=INK, linespacing=1.15)

    ax.set_yticks(range(len(TIMELINE)), [t[0] for t in TIMELINE], fontsize=7.6)
    ax.invert_yaxis()
    months = pd.date_range("2026-10-01", "2027-06-01", freq="MS")
    ax.set_xticks([(m - t0).days for m in months], [m.strftime("%b\n%Y") if m.month in (10, 1) else m.strftime("%b") for m in months], fontsize=7.4)
    ax.set_xlim(0, (pd.Timestamp("2027-06-01") - t0).days)
    today = (pd.Timestamp("2026-10-17") - t0).days
    ax.axvline(today, color=INK, lw=1, ls="--")
    ax.text(today + 2, -0.9, "17 Oct 2026", fontsize=7, color=INK, va="bottom")
    ax.grid(axis="y", visible=False)
    used = {t[3] for t in TIMELINE}
    handles = [Patch(fc=tint(c, 0.35), ec=c, label=f"{i}  {lab}") for k, (c, i, lab) in STATUS.items() if k in used]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.42, -0.13), ncol=4, frameon=False, fontsize=6.6, handlelength=1.2, columnspacing=0.9)
    save(fig, "fig02_timeline.png")


# --------------------------------------------------------------------------- #
# 3-4. Reddit
# --------------------------------------------------------------------------- #
def fig_reddit_by_area():
    nb = pd.read_csv(REDDIT / "02_derived_analysis" / "neighbourhood_summary.csv")
    sens = pd.read_csv(REDDIT / "05_audits" / "sentiment_sensitivity.csv").set_index("spec")
    city = sens.loc["B_adjusted", "comments_pct_negative"]
    top = nb[nb.total_mentions >= 15].sort_values("pct_negative")
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    y = np.arange(len(top))
    colors = [BLUE if n == "Downtown / CBD" else INK_2 for n in top.neighbourhood]
    for i, r in enumerate(top.itertuples()):
        ax.plot([r.pct_neg_ci95_low, r.pct_neg_ci95_high], [i, i], color=colors[i], lw=2.2, solid_capstyle="round")
        ax.plot(r.pct_negative, i, "o", color=colors[i], ms=7.5, mec=SURFACE, mew=1.5, zorder=3)
        ax.text(max(r.pct_neg_ci95_high, r.pct_negative) + 1.5, i,
                f"{r.pct_negative:.0f}%   n = {int(r.total_mentions)} ({int(r.n_threads)} threads)",
                va="center", fontsize=7.4, color=INK)
    ax.axvline(city, color=INK_2, lw=0.9, ls="--")
    ax.text(city + 0.8, len(top) - 0.35, f"all comments {city:.0f}%", fontsize=7, color=INK_2, va="bottom")
    ax.set_yticks(y, top.neighbourhood, fontsize=8)
    ax.set_xlim(0, 90)
    ax.set_xlabel("% of mentions scored negative (adjusted VADER), with 95% CI (whole-thread bootstrap)")
    ax.grid(axis="y", visible=False)
    save(fig, "fig03_reddit_by_area.png")


def fig_reddit_weekly():
    raw = REDDIT / "01_raw_collection"
    p = pd.read_csv(next(raw.glob("saskatoon_safety_posts_*.csv")))
    c = pd.read_csv(next(raw.glob("saskatoon_safety_comments_*.csv")))
    c = c[c.comment_in_window.astype(bool)]
    tz = "America/Regina"
    pl = pd.to_datetime(p.created_utc, unit="s", utc=True).dt.tz_convert(tz).dt.tz_localize(None)
    weeks = pd.date_range("2026-06-01", "2026-08-31", freq="7D")
    pw = pd.cut(pl, list(weeks) + [pd.Timestamp("2026-09-01")], right=False, labels=weeks).value_counts().sort_index()
    seed = (p.text_has_safety_term | p.text_has_crime_term)
    pws = pd.cut(pl[seed], list(weeks) + [pd.Timestamp("2026-09-01")], right=False,
                 labels=weeks).value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(6.4, 2.4))
    x = np.arange(len(pw))
    ax.bar(x, pw.values, width=0.72, color=tint(BLUE, 0.45), edgecolor=BLUE, lw=0.8, label="all posts collected")
    ax.bar(x, pws.values, width=0.72, color=BLUE, label="post text contains a seed term")
    for i, v in enumerate(pw.values):
        ax.text(i, v + 0.4, str(int(v)), ha="center", fontsize=7, color=INK)
    labels = [f"{w.day} {w:%b}" for w in pw.index]
    labels[-1] += "\n(1 day)"
    ax.set_xticks(x, labels, fontsize=6.6, rotation=45, ha="right", rotation_mode="anchor")
    ax.set_ylabel("Posts per week")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=7.2, loc="upper left")
    ax.text(1.0, 1.02, f"{len(p)} posts · {len(c):,} in-window comments · posts on {pl.dt.date.nunique()} of 92 days",
            transform=ax.transAxes, ha="right", fontsize=7, color=INK_2)
    save(fig, "fig04_reddit_weekly.png")


def fig_place_anchors():
    a = pd.read_csv(CV / "cbd_latest_imagery" / "reddit_place_anchors.csv")
    a = a.sort_values("records_in_downtown_tagged")
    a["anchor"] = a.anchor.str.replace(" (ambiguous: avenue or neighbourhood)", " (ambiguous)", regex=False)
    n_dt = pd.read_csv(CV / "cbd_latest_imagery" / "reddit_downtown_summary.csv").iloc[0].n_records
    fig, ax = plt.subplots(figsize=(6.2, 2.9))
    ax.barh(a.anchor, a.records_in_downtown_tagged, color=BLUE, height=0.66)
    for i, v in enumerate(a.records_in_downtown_tagged):
        ax.text(v + 0.12, i, str(int(v)), va="center", fontsize=7.2)
    ax.set_xlabel(f"Downtown-tagged Reddit records naming the street or landmark (of {int(n_dt)})")
    ax.tick_params(axis="y", labelsize=7.4)
    ax.grid(axis="y", visible=False)
    save(fig, "fig08_reddit_place_anchors.png")


# --------------------------------------------------------------------------- #
# 5-6. Sample points and imagery
# --------------------------------------------------------------------------- #
def _geo():
    """(roads, water, CBD boundary) geometries from Data/boundaries/ for the map figures."""
    roads = json.loads((BND / "osm_roads_downtown_context.geojson").read_text())["features"]
    water = json.loads((BND / "osm_water_downtown_context.geojson").read_text())["features"][0]["geometry"]
    cbd = json.loads((BND / "central_business_district_osm.geojson").read_text())["features"][0]["geometry"]
    return roads, water, cbd


def _draw_base(ax, roads, water, cbd, extent):
    """Base map: river, roads and the CBD outline within extent."""
    from shapely.geometry import shape
    w = shape(water)

    for poly in getattr(w, "geoms", [w]):
        xs, ys = poly.exterior.xy
        ax.fill(xs, ys, color="#dbe9f6", lw=0, zorder=0)

    for f in roads:
        xs, ys = zip(*f["geometry"]["coordinates"])
        major = f["properties"]["highway"] in ("motorway", "trunk", "primary", "secondary")
        ax.plot(xs, ys, color="#cfcdc6" if major else GREY_L, lw=1.0 if major else 0.6, zorder=1)

    xs, ys = zip(*cbd["coordinates"][0])
    ax.plot(xs, ys, color=INK, lw=1.3, zorder=4)
    ax.set_xlim(extent[0], extent[2]), ax.set_ylim(extent[1], extent[3])
    ax.set_aspect(1 / np.cos(np.radians(52.13)))
    ax.set_xticks([]), ax.set_yticks([]), ax.grid(False)

    for s in ax.spines.values():
        s.set_visible(True), s.set_color(GREY)

    # 500 m scale bar
    x0, y0 = extent[0] + 0.0012, extent[1] + 0.0010
    dx = 500 / (111320 * np.cos(np.radians(52.13)))
    ax.plot([x0, x0 + dx], [y0, y0], color=INK, lw=2, solid_capstyle="butt", zorder=6)
    ax.text(x0 + dx / 2, y0 + 0.0004, "500 m", ha="center", va="bottom", fontsize=6.8, zorder=6)


def newest_year(cp: pd.DataFrame) -> pd.Series:
    """Year of each point's newest image (flat or 360), or 'none'."""
    return cp[["latest_flat", "latest_pano"]].fillna("").max(axis=1).str[:4].replace("", "none")


def fig_points_map():
    roads, water, cbd = _geo()
    box_pts = pd.read_csv(CV / "placeholder_box" / "sample_points.csv")
    pts = pd.read_csv(CV / "cbd" / "sample_points.csv")
    cp = pd.read_csv(CV / "cbd" / "coverage_points.csv").set_index("point_id")
    pts["newest"] = pts.point_id.map(newest_year(cp.reset_index()).set_axis(cp.index))
    bb = json.loads((CV / "placeholder_box" / "run_meta.json").read_text())["points"]["bbox"]
    extent = (-106.6745, 52.1195, -106.6325, 52.1385)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.7, 3.25))
    for ax in (a1, a2):
        _draw_base(ax, roads, water, cbd, extent)

    from shapely.geometry import Point, shape
    poly = shape(cbd)
    inside = box_pts.apply(lambda r: poly.contains(Point(r.lon, r.lat)), axis=1)
    a1.add_patch(Rectangle((bb[0], bb[1]), bb[2] - bb[0], bb[3] - bb[1], fill=False, ec=ORANGE, lw=1.3, ls="--", zorder=5))
    a1.scatter(box_pts.lon[~inside], box_pts.lat[~inside], s=4.5, color=ORANGE, lw=0, zorder=3)
    a1.scatter(pts.lon, pts.lat, s=4.5, color=BLUE, lw=0, zorder=3)
    a1.set_title("a. Study-area boundary", loc="left", fontsize=8.5, weight="bold")

    h1 = [Line2D([], [], color=INK, lw=1.3, label="CBD neighbourhood boundary"),
          Line2D([], [], marker="o", ls="", color=BLUE, ms=3.5, label=f"CBD points ({len(pts)})"),
          Line2D([], [], color=ORANGE, lw=1.3, ls="--", marker="o", ms=3.5, label=f"old placeholder box: {int((~inside).sum())} of\n{len(box_pts)} points outside the CBD")]

    a1.legend(handles=h1, loc="upper left", bbox_to_anchor=(0, -0.01), frameon=False, fontsize=6.6, handlelength=1.6)
    order = [("2023", SEQ[3]), ("2020", SEQ[2]), ("2017–19", SEQ[1]), ("2014", SEQ[0])]
    grp = pts.newest.replace({"2017": "2017–19", "2018": "2017–19", "2019": "2017–19"})
    hand = []
    for lab, col in order[::-1]:
        m = grp == lab
        a2.scatter(pts.lon[m], pts.lat[m], s=6, color=col, lw=0, zorder=3)
        hand.append(Line2D([], [], marker="o", ls="", color=col, ms=3.8, label=f"{lab}  ({int(m.sum())} points)"))

    m = grp == "none"
    a2.scatter(pts.lon[m], pts.lat[m], s=7, facecolor="none", edgecolor=INK_2, lw=0.6, zorder=3)
    hand.append(Line2D([], [], marker="o", ls="", mfc="none", mec=INK_2, ms=3.8, label=f"no image  ({int(m.sum())})"))
    hand.append(Line2D([], [], ls="", label="Jun–Aug 2026:  0 points"))
    a2.set_title("b. Newest street-level image within 30 m", loc="left", fontsize=8.5, weight="bold")
    # read order: study period first (empty), then newest -> oldest, then no image
    a2.legend(handles=[hand[5], hand[3], hand[2], hand[1], hand[0], hand[4]], loc="upper left",
              bbox_to_anchor=(0, -0.01), frameon=False, fontsize=6.6, ncol=2, handlelength=1.0, columnspacing=0.8)

    fig.text(0.995, 0.005, "Map data © OpenStreetMap contributors (ODbL); image dates from Mapillary", ha="right", fontsize=5.8, color=INK_2)
    fig.subplots_adjust(wspace=0.04)
    save(fig, "fig05_sample_points_map.png")


def fig_imagery_by_year():
    cp = pd.read_csv(CV / "cbd" / "coverage_points.csv")
    ny = newest_year(cp)
    cats = ["none", "2014", "2017", "2018", "2019", "2020", "2023", "2024", "2025", "2026"]
    vc = ny.value_counts().reindex(cats, fill_value=0)
    fig, ax = plt.subplots(figsize=(6.2, 2.3))
    x = np.arange(len(cats))
    cols = [GREY] + [BLUE] * 6 + [GREY_L] * 3
    ax.bar(x, vc.values, color=cols, width=0.7)

    for i, v in enumerate(vc.values):
        ax.text(i, v + 4, str(int(v)), ha="center", fontsize=7.4, weight="bold" if cats[i] == "2026" else None)
    ax.set_xticks(x, ["no\nimage"] + cats[1:], fontsize=7.6)
    ax.annotate("study period\n(Jun–Aug 2026): 0", xy=(9, 4), xytext=(8.0, 120), fontsize=7.2, ha="center",
                arrowprops=dict(arrowstyle="-|>", color=INK_2, lw=0.8, mutation_scale=7))
    ax.set_ylabel(f"CBD sample points (of {len(cp)})")
    ax.set_xlabel("Year of the newest Mapillary image within 30 m of the point")
    ax.grid(axis="x", visible=False)
    save(fig, "fig06_imagery_by_year.png")


def fig_pilot_images():
    d = CV / "cbd_latest_imagery"
    man = pd.read_csv(d / "image_manifest.csv").set_index("point_id")
    panels = [
        ("P0198", "a", "Side view works: frontage, windows and entrance are visible.",
         "CLIP land-use label: 'transit node' (wrong)."),
        ("P0060", "b", "Park edge on Spadina Crescent.",
         "CLIP land-use label: 'park / open space' (plausible)."),
        ("P0123", "c", "Camera was on the cross street (89° off the road),",
         "so the 'side' view looks down the road."),
        ("P0168", "d", "Point on a bridge: no frontage to measure.",
         "2014 frame from a road-survey vehicle (text overlay)."),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(6.6, 5.75))
    for ax, (pid, letter, l1, l2) in zip(axes.ravel(), panels):
        r = man.loc[pid]
        im = Image.open(d / r.image_file).convert("RGB")
        w, h = im.size
        tw = int(h * 4 / 3)
        if w > tw:
            im = im.crop(((w - tw) // 2, 0, (w - tw) // 2 + tw, h))
        ax.imshow(im)
        ax.set_xticks([]), ax.set_yticks([]), ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
        when = pd.Timestamp(r.captured_at).strftime("%b %Y")
        kind = "360° crop" if r.is_pano else "flat photo"
        road = r.road_name.replace(" Street ", " St ").replace("Crescent", "Cres.")
        ax.set_title(f"{letter}. {pid} · {road} · {when} · {kind}", loc="left", fontsize=7.4,
                     weight="bold", pad=3)
        ax.text(0, -0.035, l1, transform=ax.transAxes, fontsize=7.1, va="top")
        ax.text(0, -0.11, l2, transform=ax.transAxes, fontsize=7.1, va="top")
    fig.text(0.99, 0.004, "Imagery © Mapillary contributors, CC BY-SA 4.0", ha="right", fontsize=6, color=INK_2)
    fig.subplots_adjust(hspace=0.30, wspace=0.04, left=0.01, right=0.99, top=0.965, bottom=0.085)
    save(fig, "fig07_pilot_images.png")


def main() -> None:
    global OUT
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUT, help="output folder (default: %(default)s)")
    OUT = ap.parse_args().out
    OUT.mkdir(parents=True, exist_ok=True)
    fig_workflow()
    fig_timeline()
    fig_reddit_by_area()
    fig_reddit_weekly()
    fig_points_map()
    fig_imagery_by_year()
    fig_pilot_images()
    fig_place_anchors()


if __name__ == "__main__":
    main()
