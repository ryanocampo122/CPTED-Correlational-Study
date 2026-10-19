"""
03_generate_charts.py
======================
ComputerVision_Sentinel | Chart generation for the August report

PURPOSE
-------
Builds the six PNG charts used in ComputerVision_Sentinel_August_Report.docx, from
the CSVs produced by 01_audit_location_tagging.py and
02_corrected_analysis.py.

  Figure 1  chart1_raw_vs_corrected.png
      Raw vs. corrected mention counts for the six priority sites
      (illustrates the scale of the tagging correction).
  Figure 2  chart2_corrected_volume.png
      Corrected total mentions by neighbourhood (sites with >=15).
  Figure 3  chart3_sentiment_by_site.png
      Mean sentiment and % negative by site (corrected).
  Figure 4  chart5_time_of_day.png
      Mean sentiment by time of day, Downtown/CBD vs. Riverbank/Meewasin.
  Figure 5  chart4_env_cues.png
      Environmental-cue co-occurrence in negative comments: citywide vs.
      Downtown/CBD vs. Riverbank/Meewasin.
  Figure 6  chart6_seasonal.png
      Citywide post volume and mean sentiment by season.

INPUT (produced by earlier scripts in this package)
-----------------------------------------------------
  output/neighbourhood_tagging_audit.csv     (from script 01)
  output/neighbourhood_summary_corrected.csv (from script 02)
  output/env_cues_by_site.csv                (from script 02)
  output/time_of_day_by_site.csv             (from script 02)
  output/seasonal_trend.csv                  (from script 02)

OUTPUT
------
  output/chart1_raw_vs_corrected.png
  output/chart2_corrected_volume.png
  output/chart3_sentiment_by_site.png
  output/chart4_env_cues.png
  output/chart5_time_of_day.png
  output/chart6_seasonal.png

USAGE
-----
  python 03_generate_charts.py
  (run AFTER 01_audit_location_tagging.py and 02_corrected_analysis.py)
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.edgecolor": "#444444",
    "axes.labelcolor": "#222222",
    "text.color": "#222222",
    "xtick.color": "#333333",
    "ytick.color": "#333333",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})

NAVY, BLUE, RED, ORANGE, GREEN, GREY = (
    "#1F3B5C", "#3F7CAC", "#C0504D", "#E08E45", "#4C9A6A", "#B0B0B0",
)

# Six sites that have an explicit loc_* boolean column in the original
# scraper output, so we can compare "raw" (as originally tagged) against
# "corrected" (from 01_audit_location_tagging.py) directly.
PRIORITY_SITES = [
    "Pleasant Hill", "Riversdale", "Downtown / CBD",
    "Downtown Terminal", "Confederation Mall", "Riverbank / Meewasin",
]


def chart1_raw_vs_corrected():
    """Impact chart: raw substring-match counts vs. corrected
    word-boundary counts, for the six priority sites."""
    audit = pd.read_csv("output/neighbourhood_tagging_audit.csv")
    audit = audit[audit["neighbourhood"].isin(PRIORITY_SITES)].copy()
    audit["total_raw"] = audit["posts_raw"] + audit["comments_raw"]
    audit["total_corrected"] = audit["posts_corrected"] + audit["comments_corrected"]
    audit = audit.sort_values("total_raw", ascending=True).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(9, 4.2))
    y = np.arange(len(audit))
    h = 0.36
    ax.barh(y + h / 2, audit["total_raw"], height=h, color=GREY, label="Raw tag (before fix)")
    ax.barh(y - h / 2, audit["total_corrected"], height=h, color=NAVY, label="Corrected (word-boundary)")
    ax.set_yticks(y)
    ax.set_yticklabels(audit["neighbourhood"])
    ax.set_xlabel("Total mentions (posts + comments)")
    ax.set_title("Location matching refinement: mention counts before vs. after correction",
                  fontsize=12, weight="bold", loc="left")
    for i in range(len(audit)):
        ax.text(audit["total_raw"][i] + 8, y[i] + h / 2, f"{int(audit['total_raw'][i])}",
                 va="center", fontsize=9, color="#555555")
        ax.text(audit["total_corrected"][i] + 8, y[i] - h / 2, f"{int(audit['total_corrected'][i])}",
                 va="center", fontsize=9, color=NAVY, weight="bold")
    ax.legend(loc="lower right", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig("output/chart1_raw_vs_corrected.png", dpi=200)
    plt.close()


def chart2_corrected_volume():
    """Corrected total mention volume, sites with >=15 mentions."""
    nb = pd.read_csv("output/neighbourhood_summary_corrected.csv")
    top = nb[nb["total_mentions"] >= 15].sort_values("total_mentions", ascending=True)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors = [NAVY if n == "Downtown / CBD" else (BLUE if n == "Riverbank / Meewasin" else "#7C97AE")
              for n in top["neighbourhood"]]
    ax.barh(top["neighbourhood"], top["total_mentions"], color=colors)
    ax.set_xlabel("Total mentions (posts + comments), corrected")
    ax.set_title("Corrected neighbourhood mention volume (sites with \u226515 mentions)",
                  fontsize=12, weight="bold", loc="left")
    for i, (n, v) in enumerate(zip(top["neighbourhood"], top["total_mentions"])):
        ax.text(v + 4, i, str(int(v)), va="center", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig("output/chart2_corrected_volume.png", dpi=200)
    plt.close()


def chart3_sentiment_by_site():
    """Mean sentiment (colour-coded) and % negative, sites with >=15 mentions."""
    nb = pd.read_csv("output/neighbourhood_summary_corrected.csv")
    top = nb[nb["total_mentions"] >= 15].sort_values("mean_sentiment")

    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors = [RED if v < 0.15 else (ORANGE if v < 0.3 else GREEN) for v in top["mean_sentiment"]]
    ax.barh(top["neighbourhood"], top["mean_sentiment"], color=colors)
    ax.axvline(0, color="#888888", lw=0.8)
    ax.set_xlabel("Mean sentiment (VADER compound, corrected)")
    ax.set_title("Mean sentiment by site \u2014 Downtown/CBD is the most negative high-volume site",
                  fontsize=12, weight="bold", loc="left")
    for i, (n, v, pn) in enumerate(zip(top["neighbourhood"], top["mean_sentiment"], top["pct_negative"])):
        ax.text(v + (0.01 if v >= 0 else -0.01), i, f"{v:.2f}  ({pn:.0f}% neg)",
                 va="center", ha="left" if v >= 0 else "right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig("output/chart3_sentiment_by_site.png", dpi=200)
    plt.close()


def chart4_env_cues():
    """Env-cue co-occurrence in negative comments: citywide vs. two focus sites.
    Citywide % is computed here directly from the raw comments file since
    02_corrected_analysis.py only stores per-site breakdowns."""
    comments = pd.read_csv("/mnt/user-data/uploads/saskatoon_safety_comments_20260611.csv")
    neg_all = comments[comments["sentiment_category"] == "negative"]
    cues = ["env_lighting", "env_noise", "env_weather", "env_time_of_day", "env_people"]
    citywide = {c: round(neg_all[c].mean() * 100, 1) for c in cues}

    cue_site = pd.read_csv("output/env_cues_by_site.csv")
    dtn = cue_site[cue_site["neighbourhood"] == "Downtown / CBD"].iloc[0]
    mee = cue_site[cue_site["neighbourhood"] == "Riverbank / Meewasin"].iloc[0]

    labels = ["Lighting", "Noise", "Weather", "Time of day\nlanguage", "People /\nisolation"]
    x = np.arange(len(cues))
    w = 0.26
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(x - w, [citywide[c] for c in cues], width=w, color=GREY, label="Citywide (all negative comments)")
    ax.bar(x, [dtn[c] for c in cues], width=w, color=NAVY, label="Downtown / CBD (negative comments)")
    ax.bar(x + w, [mee[c] for c in cues], width=w, color=BLUE, label="Riverbank / Meewasin (negative comments, corrected)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("% of negative comments mentioning cue")
    ax.set_title("Environmental cues co-occurring with negative sentiment", fontsize=12, weight="bold", loc="left")
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig("output/chart4_env_cues.png", dpi=200)
    plt.close()


def chart5_time_of_day():
    """Mean sentiment by time-of-day bucket, Downtown/CBD vs. Meewasin."""
    tod = pd.read_csv("output/time_of_day_by_site.csv")
    order = ["morning", "afternoon", "evening", "night"]

    fig, ax = plt.subplots(figsize=(8, 4.3))
    for name, color, marker in [("Downtown / CBD", NAVY, "o"), ("Riverbank / Meewasin", BLUE, "s")]:
        sub = tod[tod["neighbourhood"] == name].set_index("time_of_day").reindex(order)
        ax.plot(order, sub["mean_sentiment"], marker=marker, color=color, label=name,
                 linewidth=2.2, markersize=7)
        for i, (t, v, n) in enumerate(zip(order, sub["mean_sentiment"], sub["n"])):
            ax.annotate(f"n={int(n)}", (i, v), textcoords="offset points", xytext=(0, 8),
                        fontsize=8, color=color, ha="center")
    ax.axhline(0, color="#999999", lw=0.8, ls="--")
    ax.set_ylabel("Mean sentiment (VADER compound)")
    ax.set_title("Sentiment by time of day: Downtown/CBD vs. Riverbank/Meewasin",
                  fontsize=12, weight="bold", loc="left")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig("output/chart5_time_of_day.png", dpi=200)
    plt.close()


def chart6_seasonal():
    """Citywide post volume (bars) and mean sentiment (line) by season."""
    season = pd.read_csv("output/seasonal_trend.csv")
    order = ["spring", "summer", "fall", "winter"]
    season = season.set_index("season").reindex(order)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax2 = ax.twinx()
    ax.bar(order, season["post_count"], color="#D8E2EC", label="Post volume", zorder=1)
    ax2.plot(order, season["mean_sentiment"], color=RED, marker="o", linewidth=2.2,
              label="Mean sentiment", zorder=2)
    ax.set_ylabel("Post count")
    ax2.set_ylabel("Mean sentiment (VADER compound)")
    ax.set_title("Seasonal pattern: post volume and mean sentiment", fontsize=12, weight="bold", loc="left")
    lines, labels_ = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels_ + labels2, frameon=False, loc="upper right")
    ax.spines[["top"]].set_visible(False)
    plt.tight_layout()
    plt.savefig("output/chart6_seasonal.png", dpi=200)
    plt.close()


def main() -> None:
    chart1_raw_vs_corrected()
    chart2_corrected_volume()
    chart3_sentiment_by_site()
    chart4_env_cues()
    chart5_time_of_day()
    chart6_seasonal()
    print("Wrote 6 charts to output/")


if __name__ == "__main__":
    main()
