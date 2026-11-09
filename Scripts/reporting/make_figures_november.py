#!/usr/bin/env python3
"""
make_figures_november.py
========================
ComputerVision_Sentinel | Figures for the November 2026 midpoint update

Every number is read from Data/; nothing is typed in by hand. Same palette, fonts and base map as the
October figures (make_figures.py).

  fig09_crime_hotspots.png       recorded crime per street segment, property and street-based personal; hot spots
  fig10_crime_by_category.png    the same, one small map per study category
  fig11_image_set.png            which points have a 2020 or 2023 image, which are excluded, which have none
  fig12_segmentation_examples.png four side views with what the segmentation model found
  fig13_indicator_maps.png       building share, vegetation share and street lights per segment (not validated)
  fig14_workflow_status.png      the October workflow figure brought up to the November status (main README)

USAGE (repository root):  .venv/bin/python Scripts/reporting/make_figures_november.py [--out <folder>] [--only fig09,...]
"""
# Command-line options, file paths and the run record
import argparse
import json
import sys
from pathlib import Path

# Plotting without a screen, tables, numbers and images
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import patheffects  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from PIL import Image  # noqa: E402

# The October figure module (palette, base map) and the hot-spot script (segment lines)
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "Scripts" / "crime_data"))
sys.path.insert(0, str(REPO / "Scripts" / "cv_study"))
import make_figures as F  # noqa: E402
import hotspots as H  # noqa: E402

# Data folders and the default output folder
CRIME = REPO / "Data" / "sps_crime_2026-06-01_2026-08-31" / "03_segments"
STUDY = REPO / "Data" / "cv_study_2026-11"
OUT = REPO / "Docs" / "figures" / "mid_point_november"

# Map extent tight around the CBD (lon/lat), the count classes with their colours, and the hot-spot outline
EXTENT = (-106.6725, 52.1210, -106.6480, 52.1352)
BINS = [(0, 0, F.GREY, "none"), (0.01, 1, F.SEQ[0], "up to 1"), (1.01, 3, F.SEQ[1], "1–3"),
        (3.01, 6, F.SEQ[2], "3–6"), (6.01, 1e9, F.SEQ[3], "over 6")]
HOT_OUTLINE = [patheffects.withStroke(linewidth=4.6, foreground=F.INK)]
CREDIT = "Map data © OpenStreetMap contributors (ODbL); crime: Saskatoon Police Service extract, Jun–Aug 2026"


def save(fig, name: str, out: Path) -> None:
    """Save a figure at the October resolution and close it.

    :param fig: the figure
    :param name: file name
    :param out: folder
    """
    fig.savefig(out / name, dpi=F.DPI, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", out / name)


def segment_lonlat() -> dict:
    """The 218 study segments as lon/lat lines, rebuilt exactly as the hot-spot script does.

    :return: {segment_id: (lons, lats)}
    """
    # Lines in metres from the hot-spot script, turned back into lon/lat for the map
    lines, proj = H.study_segments(pd.read_csv(H.POINTS))
    out = {}
    for k, line in lines.items():
        lonlat = [proj.to_lonlat(x, y) for x, y in line.coords]
        out[k] = ([p[0] for p in lonlat], [p[1] for p in lonlat])
    return out


def draw_counts(ax, geo, counts: pd.Series, hot: pd.Series | None, title: str) -> None:
    """One map: each study segment coloured by its record count, hot spots drawn thicker.

    :param ax: the axes to draw on
    :param geo: segment_id -> (lons, lats)
    :param counts: records per segment
    :param hot: True for hot-spot segments, or None for no hot-spot marking
    :param title: panel title
    """
    # Base map, then every segment in the colour of its count class
    F._draw_base(ax, *F._geo(), EXTENT)
    for seg_id, (xs, ys) in geo.items():
        n = counts.get(seg_id, 0.0)
        colour = next(c for lo, hi, c, _ in BINS if lo <= n <= hi)
        is_hot = hot is not None and bool(hot.get(seg_id, False))
        # Hot spots are drawn thicker, with a black outline
        ax.plot(xs, ys, color=colour, lw=2.8 if is_hot else 1.6, solid_capstyle="round", zorder=6 if is_hot else 5,
                path_effects=HOT_OUTLINE if is_hot else None)
    ax.set_title(title, loc="left", fontsize=8.5, weight="bold")


def legend_handles(with_hot: bool) -> list:
    """Legend entries for the count classes, and the hot-spot outline if shown.

    :param with_hot: whether to include the hot-spot entry
    :return: list of legend handles
    """
    hands = [Line2D([], [], color=c, lw=2.2, label=lab) for _, _, c, lab in BINS]
    # The hot-spot entry, only on maps that mark them
    if with_hot:
        hands.append(Line2D([], [], color=F.SEQ[2], lw=2.8, path_effects=HOT_OUTLINE,
                            label="hot spot (segments holding half the records)"))
    return hands


def fig_hotspots(out: Path) -> None:
    """fig09: property and street-based personal crime per segment, with hot spots."""
    # Counts per segment and the summary of the placement
    seg = pd.read_csv(CRIME / "segment_crime_counts.csv").set_index("segment_id")
    summ = json.loads((CRIME / "hotspot_summary.json").read_text())
    geo = segment_lonlat()
    fig, axes = plt.subplots(1, 2, figsize=(6.7, 3.4))
    # One panel per crime group
    for ax, group, label in zip(axes, ["property", "street_personal"], ["a. Property crime", "b. Street-based personal crime"]):
        n = summ["records_by_group"][group]
        k = summ["hotspot_segments"][group]
        draw_counts(ax, geo, seg[group], seg[f"hotspot_{group}"],
                    f"{label} ({n:.0f} records)\nhalf of them on {k} of {summ['segments']} segments")
    axes[0].legend(handles=legend_handles(True), title="records per segment", title_fontsize=6.6, loc="upper left",
                   bbox_to_anchor=(0, -0.01), frameon=False, fontsize=6.6, ncol=3, handlelength=1.6)
    fig.text(0.995, -0.035, CREDIT, ha="right", fontsize=5.8, color=F.INK_2)
    fig.subplots_adjust(wspace=0.04)
    save(fig, "fig09_crime_hotspots.png", out)


def fig_categories(out: Path) -> None:
    """fig10: one small map per study category."""
    # Counts per segment and the readable category names
    seg = pd.read_csv(CRIME / "segment_crime_counts.csv").set_index("segment_id")
    names = {"break_and_enter": "Break and enter", "theft_from_vehicle": "Theft from vehicle",
             "auto_theft": "Auto theft", "mischief_vandalism": "Mischief / vandalism",
             "street_robbery": "Robbery", "assault": "Assault (conditional)"}
    geo = segment_lonlat()
    fig, axes = plt.subplots(2, 3, figsize=(6.7, 4.9))
    # One map per category, in report order
    for ax, cat in zip(axes.ravel(), H.CATEGORIES):
        draw_counts(ax, geo, seg[cat], None, f"{names[cat]} ({seg[cat].sum():.0f})")
    axes[1, 0].legend(handles=legend_handles(False), title="records per segment", title_fontsize=6.6,
                      loc="upper left", bbox_to_anchor=(0, -0.01), frameon=False, fontsize=6.6, ncol=5, handlelength=1.4)
    fig.text(0.995, -0.035, CREDIT, ha="right", fontsize=5.8, color=F.INK_2)
    fig.subplots_adjust(wspace=0.04, hspace=0.22)
    save(fig, "fig10_crime_by_category.png", out)


def fig_image_set(out: Path) -> None:
    """fig11: what each sample point got under the image decision."""
    # The points with their outcome and, where they got one, the image year
    pts = pd.read_csv(STUDY / "points.csv")
    man = pd.read_csv(STUDY / "image_manifest.csv")[["point_id", "capture_year"]]
    pts = pts.merge(man, on="point_id", how="left")
    fig, ax = plt.subplots(figsize=(4.2, 3.6))
    F._draw_base(ax, *F._geo(), EXTENT)
    # Each outcome in its own colour, with its count in the legend
    groups = [(pts.capture_year == 2023, F.SEQ[3], "o", "2023 image"), (pts.capture_year == 2020, F.SEQ[1], "o", "2020 image"),
              (pts.flag.fillna("") != "", F.ORANGE, "x", "bridge or freeway (excluded)"),
              (pts.capture_year.isna() & (pts.flag.fillna("") == ""), F.INK_2, "o", "no usable image")]
    hands = []
    for mask, colour, marker, label in groups:
        hollow = label == "no usable image"
        ax.scatter(pts.lon[mask], pts.lat[mask], s=8, marker=marker, lw=0.7 if marker == "x" or hollow else 0,
                   facecolor="none" if hollow else colour, edgecolor=colour, zorder=6)
        hands.append(Line2D([], [], ls="", marker=marker, ms=4, mfc="none" if hollow else colour, mec=colour,
                            label=f"{label} ({int(mask.sum())})"))
    ax.set_title(f"Image set: {int(pts.capture_year.notna().sum())} of {len(pts)} points", loc="left", fontsize=8.5,
                 weight="bold")
    ax.legend(handles=hands, loc="upper left", bbox_to_anchor=(0, -0.01), frameon=False, fontsize=6.6, ncol=2)
    fig.text(0.995, -0.06, "Map data © OpenStreetMap contributors (ODbL); images: Mapillary (CC BY-SA 4.0)",
             ha="right", fontsize=5.8, color=F.INK_2)
    save(fig, "fig11_image_set.png", out)


def fig_segmentation_examples(out: Path) -> None:
    """fig12: four side views next to what the segmentation model labelled in them."""
    from models import CAMERA_VEHICLE_CLASSES, PanopticModel, pick_device
    # Four views spread through the sample: the 1st, 4th, 7th and 10th point in the manifest's spread
    man = pd.read_csv(STUDY / "image_manifest.csv")
    picks = man.iloc[np.linspace(0, len(man) - 1, 4).round().astype(int)]
    model = PanopticModel(pick_device())
    # A fixed colour per class, so the same class looks the same in every panel
    rng = np.random.default_rng(7)
    palette = rng.integers(40, 230, size=(len(model.labels) + 1, 3))
    # Capture dates in Saskatoon local time, the way the docs give them
    local = pd.to_datetime(picks.captured_at, utc=True, format="ISO8601").dt.tz_convert("America/Regina").dt.date
    picks = picks.assign(local_date=local.astype(str))
    fig, axes = plt.subplots(4, 2, figsize=(6.7, 10.3))
    # Each picked view: the photo on the left, the labelled classes on the right
    for row, r in zip(axes, picks.itertuples()):
        im = Image.open(STUDY / r.view_right).convert("RGB")
        seg_map, segments = model.run(im)
        label_map = np.full(seg_map.shape, len(model.labels))
        for s in segments:
            label_map[seg_map == s["id"]] = s["label_id"]
        overlay = (0.45 * np.asarray(im) + 0.55 * palette[label_map]).astype(np.uint8)
        row[0].imshow(im)
        row[1].imshow(overlay)
        # Name the three biggest classes in the panel title, leaving out the camera's own car
        ids, n = np.unique(label_map[label_map < len(model.labels)], return_counts=True)
        named = [model.labels[i] for i in ids[np.argsort(-n)] if model.labels[i] not in CAMERA_VEHICLE_CLASSES]
        top = ", ".join(named[:3])
        row[0].set_title(f"{r.point_id}, {r.road_name}, {r.local_date}", loc="left", fontsize=7)
        row[1].set_title(f"model: mostly {top}", loc="left", fontsize=7)
        for a in row:
            a.set_xticks([]), a.set_yticks([]), a.grid(False)
    fig.text(0.995, 0.06, "Images: Mapillary contributors (CC BY-SA 4.0). Segmentation: Mask2Former (Mapillary Vistas)",
             ha="right", fontsize=5.8, color=F.INK_2)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.97, bottom=0.07, hspace=0.12, wspace=0.03)
    save(fig, "fig12_segmentation_examples.png", out)


def fig_indicator_maps(out: Path) -> None:
    """fig13: three model indicators per segment (not yet validated)."""
    # Indicators per segment and the segment lines
    ind = pd.read_csv(STUDY / "segment_indicators.csv").set_index("segment_id")
    geo = segment_lonlat()
    panels = [("share_building", "a. Building share", F.SEQ),
              ("share_vegetation", "b. Vegetation share", F.SEQ),
              ("count_street_light", "c. Street lights per point", F.SEQ)]
    fig, axes = plt.subplots(1, 3, figsize=(6.7, 2.6))
    # One map per indicator, coloured by quartile of its value
    for ax, (col, title, colours) in zip(axes, panels):
        F._draw_base(ax, *F._geo(), EXTENT)
        vals = ind[col]
        cuts = vals.quantile([0.25, 0.5, 0.75]).to_numpy()
        for seg_id, (xs, ys) in geo.items():
            # Segments with no image stay grey
            if seg_id not in vals.index:
                ax.plot(xs, ys, color=F.GREY, lw=1.4, zorder=4)
                continue
            q = int(np.searchsorted(cuts, vals[seg_id], side="right"))
            ax.plot(xs, ys, color=colours[q], lw=1.8, solid_capstyle="round", zorder=5)
        ax.set_title(title, loc="left", fontsize=7.6, weight="bold")
    hands = [Line2D([], [], color=c, lw=2.2, label=lab) for c, lab in zip(F.SEQ, ["lowest quarter", "2nd", "3rd", "highest quarter"])]
    hands.append(Line2D([], [], color=F.GREY, lw=2.2, label="no image"))
    axes[0].legend(handles=hands, loc="upper left", bbox_to_anchor=(0, -0.01), frameon=False, fontsize=6.4, ncol=5,
                   handlelength=1.4)
    fig.text(0.995, -0.04, "Not yet validated against hand labels. Images: Mapillary (CC BY-SA 4.0); map: OpenStreetMap",
             ha="right", fontsize=5.8, color=F.INK_2)
    fig.subplots_adjust(wspace=0.04)
    save(fig, "fig13_indicator_maps.png", out)


def fig_workflow(out: Path) -> None:
    """fig14: the October workflow figure with the street-image and crime rows moved on to November.

    :param out: folder
    """
    # What the image, model, labelling and crime scripts recorded about their runs
    meta = json.loads((STUDY / "run_meta.json").read_text())
    models = json.loads((STUDY / "models_meta.json").read_text())
    strata = json.loads((STUDY / "validation" / "sample_strata.json").read_text())
    crime = json.loads((CRIME / "hotspot_summary.json").read_text())
    n_segments = pd.read_csv(STUDY / "points.csv").segment_id.nunique()
    # The October boxes, with the street-image row and the crime row's middle box updated
    rows = [list(r) for r in F.WORKFLOW]
    rows[1] = [("done", f"{meta['points_with_image']} of {meta['points']} points imaged\n"
                        f"on {meta['segments_with_image']} of {n_segments} segments;\nnewest 2020/2023 image"),
               ("done", f"Segmentation, objects and\nCLIP run on all {models['views']}\nside views"),
               ("partial", f"{strata['n_sample']} views drawn for hand\nlabels, {strata['n_second_coder']} for a second\n"
                           f"coder; labelling next")]
    rows[2][1] = ("done", f"{crime['placed']} of {crime['records']} records placed\non streets; half of them on\n"
                          f"{crime['hotspot_segments']['all_study_crime']} segments")
    save(F.draw_workflow(rows, partial_label="Started"), "fig14_workflow_status.png", out)


# Figure names and the functions that draw them
FIGURES = {"fig09": fig_hotspots, "fig10": fig_categories, "fig11": fig_image_set,
           "fig12": fig_segmentation_examples, "fig13": fig_indicator_maps, "fig14": fig_workflow}


def main() -> int:
    """Draw every November figure, or just the ones asked for.

    :return: exit code
    """
    # Output folder and an optional subset of figures
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT), help="output folder (default Docs/figures/mid_point_november)")
    ap.add_argument("--only", help="comma-separated figure names, e.g. fig09,fig10")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    wanted = a.only.split(",") if a.only else list(FIGURES)
    # Draw each requested figure
    for name in wanted:
        FIGURES[name](out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
