"""
03_generate_charts.py
======================
CPTED Vision | Report charts from the corrected tables

PURPOSE
-------
Renders the corrected figures from the CSVs written by scripts 01-02b.
Changes from the August charts:
  - uncertainty is shown (95% thread-bootstrap CIs) wherever a site is compared
  - the seasonal chart no longer uses two y-axes (two panels instead)
  - titles describe the chart instead of asserting a conclusion
  - one validated palette (blue / orange / aqua, CVD-checked); grey = "before"
  - value labels are drawn in ink colours, never in the series colour

  chart1_location_tagging.png   raw vs final mention counts, areas changed by cleaning
  chart2_mention_volume.png     final mentions per area (>= 15)
  chart3_pct_negative_by_site.png  % negative with 95% CI, areas with >= 15 mentions
  chart4_env_cues.png           % of negative comments with each corrected cue
  chart5_time_of_day.png        mean sentiment by posting time, Downtown vs Riverbank
  chart6_seasonal.png           posts and mean sentiment by local season (by month
                                when the collection covers a single season)
  chart7_env_cue_audit.png      original vs corrected cue tag counts (comments)

INPUT
-----
  02_derived_analysis/*.csv, 05_audits/*.csv

OUTPUT
------
  charts/*.png

USAGE
-----
  python 03_generate_charts.py
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import common as c

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GREY = "#b9b8b3"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.edgecolor": INK_2, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK_2, "ytick.color": INK_2,
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True,
})

D = c.out_dir("02_derived_analysis")
A = c.out_dir("05_audits")
OUT = c.out_dir("charts")


def finish(fig, ax, name, title, subtitle=None):
    """Title, subtitle and house style; save to OUT/name at 200 dpi and close."""
    ax.set_title(title, loc="left", fontsize=12, weight="bold", pad=22 if subtitle else 8)
    if subtitle:
        ax.text(0, 1.015, subtitle, transform=ax.transAxes, fontsize=9, color=INK_2, va="bottom")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=200)
    plt.close(fig)


def chart1_location_tagging():
    audit = pd.read_csv(A / "neighbourhood_tagging_audit.csv")
    audit = audit[audit["total_raw"] != audit["total_final"]].sort_values("total_raw")
    fig, ax = plt.subplots(figsize=(9, 3.6))
    y = np.arange(len(audit))
    h = 0.38
    ax.barh(y + h / 2, audit["total_raw"], height=h - 0.04, color=GREY, label="Original tag (substring match)")
    ax.barh(y - h / 2, audit["total_final"], height=h - 0.04, color=BLUE, label="Final tag (whole word, other cities removed)")
    for i, (r, f) in enumerate(zip(audit["total_raw"], audit["total_final"])):
        ax.text(r + 6, y[i] + h / 2, f"{r}", va="center", fontsize=8.5, color=INK_2)
        ax.text(f + 6, y[i] - h / 2, f"{f}", va="center", fontsize=8.5, color=INK, weight="bold")
    ax.set_yticks(y, audit["neighbourhood"])
    ax.set_xlabel("Mentions (posts + comments)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    a = pd.read_csv(A / "neighbourhood_tagging_audit.csv").set_index("neighbourhood")
    notes = []
    if a.loc["Riverbank / Meewasin", "removed_by_word_boundary"] > 0:
        notes.append("Riverbank: 'river' matched 'driver'.")
    n_dt = int(a.loc["Downtown / CBD", "removed_as_other_city"])
    if n_dt:
        notes.append(f"Downtown: {n_dt} were other cities' downtowns.")
    finish(fig, ax, "chart1_location_tagging.png", "Location tags before and after cleaning",
           " ".join(["Areas whose count changed."] + notes))


def chart2_mention_volume():
    nb = pd.read_csv(D / "neighbourhood_summary.csv")
    top = nb[nb["total_mentions"] >= c.MIN_MENTIONS_FOCUS].sort_values("total_mentions")
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.barh(top["neighbourhood"], top["total_mentions"], color=BLUE, height=0.7)
    for i, v in enumerate(top["total_mentions"]):
        ax.text(v + 3, i, str(int(v)), va="center", fontsize=9, color=INK)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Mentions (posts + comments), final tags")
    finish(fig, ax, "chart2_mention_volume.png", "Mention volume by area",
           f"Areas with at least {c.MIN_MENTIONS_FOCUS} mentions. r/saskatoon safety threads, "
           f"{c.collection_window_label()}.")


def chart3_pct_negative():
    nb = pd.read_csv(D / "neighbourhood_summary.csv")
    top = nb[nb["total_mentions"] >= c.MIN_MENTIONS_FOCUS].sort_values("pct_negative")
    sens = pd.read_csv(A / "sentiment_sensitivity.csv").set_index("spec")
    city = sens.loc["B_adjusted", "comments_pct_negative"]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    y = np.arange(len(top))
    lo = top["pct_negative"] - top["pct_neg_ci95_low"]
    hi = top["pct_neg_ci95_high"] - top["pct_negative"]
    ax.errorbar(top["pct_negative"], y, xerr=[lo, hi], fmt="o", color=BLUE, ecolor=BLUE,
                elinewidth=2, capsize=0, markersize=8)
    ax.axvline(city, color=INK_2, lw=1, ls="--", label=f"All comments citywide ({city:.0f}%)")
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    for i, (p, n) in enumerate(zip(top["pct_negative"], top["total_mentions"])):
        ax.text(top["pct_neg_ci95_high"].iloc[i] + 1, i, f"{p:.0f}%  (n={n})", va="center", fontsize=8.5, color=INK)
    ax.set_yticks(y, top["neighbourhood"])
    ax.set_xlim(0, 75)
    ax.set_xlabel("% of mentions scored negative (adjusted VADER), with 95% CI")
    ax.grid(axis="y", visible=False)
    finish(fig, ax, "chart3_pct_negative_by_site.png", "Share of negative mentions by area",
           "Whiskers: 95% CI, resampling whole threads. Overlapping whiskers = no clear difference.")


def chart4_env_cues():
    cue = pd.read_csv(D / "env_cues_by_site.csv").set_index("neighbourhood")
    cues = c.ENV_CUE_NAMES
    labels = ["Lighting", "Noise", "Weather", "Night / evening", "People / isolation"]
    groups = [("Citywide (all comments)", GREY, "All negative comments"),
              ("Downtown / CBD", BLUE, "Downtown / CBD"),
              ("Riverbank / Meewasin", ORANGE, "Riverbank / Meewasin")]
    x = np.arange(len(cues))
    w = 0.26
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for k, (row, color, lab) in enumerate(groups):
        vals = cue.loc[row, cues].astype(float).values
        n = int(cue.loc[row, "n_negative_comments"])
        bars = ax.bar(x + (k - 1) * w, vals, width=w - 0.03, color=color, label=f"{lab} (n={n})")
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.4, f"{v:.0f}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(x, labels)
    ax.set_ylabel("% of negative comments mentioning cue")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    finish(fig, ax, "chart4_env_cues.png", "Environmental cues in negative comments (corrected tagging)",
           "Lighting tags were ~50% precise in a first-pass check; read lighting counts as an upper bound.")


def chart5_time_of_day():
    tod = pd.read_csv(D / "time_of_day_by_site.csv")
    order = c.TIME_OF_DAY_ORDER
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    ns = {}
    for k, (name, color, marker) in enumerate([("Downtown / CBD", BLUE, "o"), ("Riverbank / Meewasin", ORANGE, "s")]):
        sub = tod[tod["neighbourhood"] == name].set_index("time_of_day").reindex(order)
        ns[name] = sub["n"].astype(int).tolist()
        xs = np.arange(len(order)) + (k - 0.5) * 0.12
        ax.errorbar(xs, sub["mean_sentiment"],
                    yerr=[sub["mean_sentiment"] - sub["mean_ci95_low"], sub["mean_ci95_high"] - sub["mean_sentiment"]],
                    fmt=marker + "-", color=color, ecolor=color, elinewidth=1.5, lw=2, markersize=8,
                    capsize=0, label=name)
    ax.axhline(0, color=INK_2, lw=0.8, ls="--")
    ticks = [f"{o.capitalize()}\nn = {a} / {b}" for o, a, b in
             zip(order, ns["Downtown / CBD"], ns["Riverbank / Meewasin"])]
    ax.set_xticks(range(len(order)), ticks)
    ax.set_ylabel("Mean sentiment (adjusted VADER)")
    ax.set_xlabel("Local time the comment was posted  (n = Downtown / Riverbank comments)")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=9)
    con = pd.read_csv(D / "time_of_day_contrasts.csv")
    sig = con.loc[con["ci_excludes_zero"].astype(str) == "True", "neighbourhood"].tolist()
    sig = [n for n in sig if not n.startswith("Citywide")]
    note = (f"Night differs from other hours (95% CI excludes 0) at: {', '.join(sig)}." if sig
            else "No site's night-vs-other difference is distinguishable from zero.")
    finish(fig, ax, "chart5_time_of_day.png", "Tone of comments by posting time", "95% CI whiskers. " + note)


def chart6_seasonal():
    s = pd.read_csv(D / "seasonal_trend.csv").set_index("season").reindex(c.SEASON_ORDER)
    if (s["post_count"] > 0).sum() > 1:
        unit, title = "season", "Seasonal pattern (local time, all posts)"
        labels = s.index.str.capitalize()
    else:   # a single-season collection (e.g. the Jun-Aug 2026 study period): show months
        s = pd.read_csv(D / "monthly_trend.csv")
        unit, title = "month", "Monthly pattern (local time, all posts)"
        labels = [pd.Timestamp(year=int(y), month=int(m), day=1).strftime("%b %Y")
                  for y, m in zip(s["year"], s["month"])]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.5, 3.8))
    a1.bar(labels, s["post_count"], color=BLUE, width=0.6)
    for i, v in enumerate(s["post_count"]):
        a1.text(i, v + 2, str(int(v)), ha="center", fontsize=9, color=INK)
    a1.set_ylabel("Posts")
    a1.grid(axis="x", visible=False)
    a1.set_title(f"Posts per {unit}", loc="left", fontsize=11, weight="bold")
    a1.spines[["top", "right"]].set_visible(False)
    x = np.arange(len(s))
    a2.errorbar(x, s["mean_sentiment"],
                yerr=[s["mean_sentiment"] - s["mean_ci95_low"], s["mean_ci95_high"] - s["mean_sentiment"]],
                fmt="o", color=BLUE, elinewidth=2, markersize=8, capsize=0)
    a2.set_xticks(x, labels)
    a2.axhline(0, color=INK_2, lw=0.8, ls="--")
    a2.set_ylabel("Mean post sentiment (adjusted)")
    a2.grid(axis="x", visible=False)
    a2.set_title("Mean sentiment, 95% CI", loc="left", fontsize=11, weight="bold")
    a2.spines[["top", "right"]].set_visible(False)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, weight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "chart6_seasonal.png", dpi=200)
    plt.close(fig)


def chart7_env_cue_audit():
    audit = pd.read_csv(A / "env_cue_tagging_audit.csv")
    audit = audit[audit["record_type"] == "comments"].set_index("cue").reindex(c.ENV_CUE_NAMES)
    labels = ["Lighting", "Noise", "Weather", "Night / evening", "People / isolation"]
    x = np.arange(len(audit))
    w = 0.38
    fig, ax = plt.subplots(figsize=(9, 4))
    b1 = ax.bar(x - w / 2, audit["original"], width=w - 0.03, color=GREY, label="Original (substring)")
    b2 = ax.bar(x + w / 2, audit["corrected"], width=w - 0.03, color=BLUE, label="Corrected")
    for b, v in list(zip(b1, audit["original"])) + list(zip(b2, audit["corrected"])):
        ax.text(b.get_x() + b.get_width() / 2, v + 25, f"{int(v):,}", ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Comments tagged")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=9)
    finish(fig, ax, "chart7_env_cue_audit.png", "Environmental-cue tags: original vs corrected (comments)",
           "Original tags matched inside words: 'ice' in 'police', 'lit' in 'little', 'late' in 'plate'.")


def main() -> None:
    chart1_location_tagging()
    chart2_mention_volume()
    chart3_pct_negative()
    chart4_env_cues()
    chart5_time_of_day()
    chart6_seasonal()
    chart7_env_cue_audit()
    print(f"Wrote 7 charts to {OUT}")


if __name__ == "__main__":
    main()
