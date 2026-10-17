"""
10_merge_cv_reddit.py

Joins the new CV streetscape scores (script 09) against the verified
Reddit neighbourhood sentiment table (script 02's output), so you can
answer the actual research question: does the physical condition of a
place match what people say about it online?

Output:
    ../data_pkg_august/05_cv_streetscape/cv_vs_reddit_comparison.csv
    ../charts/chart7_cv_vs_reddit_sentiment.png
"""

import pandas as pd
import matplotlib.pyplot as plt

CV_CSV = "../data_pkg_august/05_cv_streetscape/cv_streetscape_by_site.csv"
REDDIT_CSV = "../data_pkg_august/02_derived_analysis/neighbourhood_summary_corrected.csv"

# Map your CV site slugs to the exact neighbourhood strings used in the
# Reddit tables, since the two pipelines name sites differently.
SITE_TO_NEIGHBOURHOOD = {
    "downtown_cbd": "Downtown / CBD",
    "riverbank_meewasin": "Riverbank / Meewasin",
}


def main():
    cv = pd.read_csv(CV_CSV)
    reddit = pd.read_csv(REDDIT_CSV)

    cv["neighbourhood"] = cv["site"].map(SITE_TO_NEIGHBOURHOOD)
    merged = cv.merge(reddit, on="neighbourhood", how="left")

    out_csv = "../data_pkg_august/05_cv_streetscape/cv_vs_reddit_comparison.csv"
    merged.to_csv(out_csv, index=False)
    print(f"wrote comparison table -> {out_csv}")
    print(merged[["neighbourhood", "mean_cv_safety_score", "mean_sentiment", "pct_negative"]])

    if len(merged) >= 2:
        corr = merged["mean_cv_safety_score"].corr(merged["mean_sentiment"])
        print(f"\nPearson correlation (CV score vs Reddit sentiment): {corr:.3f}")
    else:
        print("\nNeed at least 2 sites with both CV and Reddit data to compute a correlation.")

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(merged["mean_cv_safety_score"], merged["mean_sentiment"], s=80)
    for _, row in merged.iterrows():
        ax.annotate(row["neighbourhood"], (row["mean_cv_safety_score"], row["mean_sentiment"]),
                    textcoords="offset points", xytext=(6, 6))
    ax.set_xlabel("CV streetscape safety score (image-based)")
    ax.set_ylabel("Reddit mean sentiment (text-based)")
    ax.set_title("Physical streetscape vs. online perceived safety")
    ax.axhline(0, color="grey", linewidth=0.5)
    ax.axvline(0, color="grey", linewidth=0.5)
    fig.tight_layout()
    fig.savefig("../charts/chart7_cv_vs_reddit_sentiment.png", dpi=150)
    print("wrote chart -> ../charts/chart7_cv_vs_reddit_sentiment.png")


if __name__ == "__main__":
    main()
