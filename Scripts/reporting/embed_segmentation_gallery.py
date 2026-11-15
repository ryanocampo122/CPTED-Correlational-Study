#!/usr/bin/env python3
"""
embed_segmentation_gallery.py
=============================
CPTED Vision | Every segmented side view as a gallery in Docs/cv_pipeline.md

Runs the segmentation model on all 492 side views again, the same way models.py does for the shares (the typical roof
where the model missed the camera car, then the tree crowns re-checked), and saves a small picture of each: the photo
on the left, the model's classes laid over it on the right, in the colours of fig12. Then it writes a gallery into
Docs/cv_pipeline.md, with the three biggest shares from segmentation_shares.csv under each picture, and stops if the
pictures and the published shares disagree. Only the text between the two markers below is replaced.

About 15 minutes on the Mac's GPU (the model runs once per view). With --text-only it rewrites only the gallery
text from the small pictures already saved, in a few seconds.

USAGE (repository root):  .venv/bin/python Scripts/reporting/embed_segmentation_gallery.py [--text-only]
"""
# Command-line paths
import sys
from pathlib import Path

# Pictures, tables and the legend
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from PIL import Image  # noqa: E402

# The study's models and the shared class colours
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "Scripts" / "cv_study"))
from make_figures_november import MAIN_COLOURS, class_palette  # noqa: E402
from models import (CAMERA_CAR_YEARS, CAMERA_VEHICLE_CLASSES, PanopticModel, class_map, fill_roof,  # noqa: E402
                    pick_device, refine_crowns, slug, typical_roofs)

# The study folder, the doc it edits and the folder for the small pictures
STUDY = REPO / "Data" / "cv_study_2026-11"
DOC = REPO / "Docs" / "cv_pipeline.md"
OUT = REPO / "Docs" / "figures" / "segmentation_all"

# The doc text between these two markers is rewritten on every run
START = "<!-- segmentation gallery: start (written by Scripts/reporting/embed_segmentation_gallery.py) -->"
END = "<!-- segmentation gallery: end -->"

# Size of each half of a small picture, the gap between the halves, JPEG quality, and pictures per table row
HALF = (240, 180)
GAP = 6
QUALITY = 78
PER_ROW = 3

# How far a share worked out from a picture may be from the published one (shares are rounded to 4 places)
TOLERANCE = 0.0006


def views() -> pd.DataFrame:
    """One row per side view: point, segment, side, year and picture path.

    :return: the side views, by point then side
    """
    man = pd.read_csv(STUDY / "image_manifest.csv")
    out = pd.concat([man.assign(side=s, view_file=man[f"view_{s}"]) for s in ("left", "right")])
    return out.sort_values(["point_id", "side"]).reset_index(drop=True)


def legend(labels: list[str], palette: np.ndarray) -> Path:
    """Save one legend picture naming the fixed colours.

    :param labels: the model's class names by id
    :param palette: colour per class (class_palette)
    :return: the legend picture
    """
    handles = [Patch(facecolor=palette[labels.index(name)] / 255, edgecolor="none",
                     label="camera's own car" if name == "Ego Vehicle" else name)
               for name in MAIN_COLOURS if name in labels]
    handles.append(Patch(facecolor="#bcbcbc", edgecolor="none", label="other classes (muted colours)"))
    fig = plt.figure(figsize=(7.2, 0.75))
    fig.legend(handles=handles, loc="center", ncol=6, fontsize=8, frameon=False, handlelength=1.2,
               columnspacing=1.0)
    path = OUT / "legend.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", pad_inches=0.04, metadata={"Software": None})
    plt.close(fig)
    return path


def small_picture(im: Image.Image, overlay: np.ndarray, path: Path) -> None:
    """Save the photo and its overlay side by side, small.

    :param im: the side view
    :param overlay: the side view with the class colours laid over it
    :param path: where to save
    """
    pair = Image.new("RGB", (2 * HALF[0] + GAP, HALF[1]), "white")
    pair.paste(im.resize(HALF, Image.LANCZOS), (0, 0))
    pair.paste(Image.fromarray(overlay).resize(HALF, Image.LANCZOS), (HALF[0] + GAP, 0))
    pair.save(path, "JPEG", quality=QUALITY, optimize=True)


def check_shares(label_map: np.ndarray, labels: list[str], published: pd.Series) -> float:
    """The largest gap between the shares in this picture and the published shares for the same view.

    :param label_map: class id per pixel, -1 where no class was given
    :param labels: the model's class names by id
    :param published: this view's row of segmentation_shares.csv
    :return: the largest absolute difference over all classes
    """
    # Shares of the street scene: the camera's own car comes off the total, as in models.describe
    per_class = np.bincount(label_map[label_map >= 0], minlength=len(labels))
    camera = sum(per_class[labels.index(name)] for name in CAMERA_VEHICLE_CLASSES)
    scene = label_map.size - camera
    gaps = [abs(per_class[i] / scene - published[f"share_{slug(name)}"])
            for i, name in enumerate(labels) if name not in CAMERA_VEHICLE_CLASSES]
    return max(gaps)


def caption(v: pd.Series, shares: pd.Series) -> str:
    """The text under one picture: point, side and year, then the three biggest shares of the street scene.

    :param v: the side view
    :param shares: this view's row of segmentation_shares.csv
    :return: the caption as HTML
    """
    cols = [c for c in shares.index if c.startswith("share_") and c != "share_unlabelled"]
    top = shares[cols].astype(float).nlargest(3)
    words = ", ".join(f"{c[6:].replace('_', ' ')} {round(100 * s)}%" for c, s in top.items())
    roof = "<br><i>camera roof filled in</i>" if shares.camera_roof_filled_in == 1 else ""
    return f"{v.point_id} {v.side}, {v.capture_year}<br>{words}{roof}"


def gallery(rows: list[tuple[pd.Series, str, str]], legend_path: Path) -> str:
    """One table per photo year, inside a section the reader opens.

    :param rows: (side view, small picture path from Docs/, caption) for every view
    :param legend_path: the legend picture
    :return: the gallery's Markdown
    """
    parts = [f"![Colours]({legend_path.relative_to(DOC.parent)})\n"]
    # One table per photo year, in year order; each small picture links to the full side view
    for year in sorted({v.capture_year for v, _, _ in rows}):
        cells = [f'<td width="33%" valign="top"><a href="../Data/cv_study_2026-11/{v.view_file}"><img src="{small}" '
                 f'width="250" alt="{v.point_id} {v.side}"></a><br><sub>{text}</sub></td>'
                 for v, small, text in rows if v.capture_year == year]
        lines = ["<tr>" + "".join(cells[i:i + PER_ROW]) + "</tr>" for i in range(0, len(cells), PER_ROW)]
        parts.append(f"**{year} photos** ({len(cells)} side views)\n\n<table>\n" + "\n".join(lines) + "\n</table>\n")
    # A coloured tip box above the section, and the section's title as a heading, so the closed gallery is easy to see
    tip = (f"> [!TIP]\n> **All {len(rows)} segmented side views are in the section below.** Click its heading to open "
           f"it. Each shows the photo on the left and the model's classes on the right, with the three biggest shares "
           f"underneath; click a picture for the full view.\n\n")
    summary = f"<summary><h3>Click to open: all {len(rows)} segmented side views</h3></summary>"
    return f"{tip}<details>\n{summary}\n\n" + "\n".join(parts) + "\n</details>\n"


def write_doc(rows: list[tuple[pd.Series, str, str]], legend_path: Path) -> None:
    """Rewrite the part of the doc between START and END.

    :param rows: (side view, small picture path from Docs/, caption) for every view
    :param legend_path: the legend picture
    """
    doc = DOC.read_text()
    before, rest = doc.split(START, 1)
    _, after = rest.split(END, 1)
    DOC.write_text(f"{before}{START}\n\n{gallery(rows, legend_path)}\n{END}{after}")
    print("wrote", len(rows), "segmented views into", DOC)


def text_only() -> None:
    """Rewrite only the gallery text from the small pictures already saved, without running the model."""
    shares = pd.read_csv(STUDY / "segmentation_shares.csv").set_index(["point_id", "side"])
    rows = []
    for v in views().itertuples():
        # Every small picture must already exist
        path = OUT / Path(v.view_file).name
        if not path.exists():
            sys.exit(f"no small picture for {v.point_id} {v.side}; run without --text-only")
        view = pd.Series(v._asdict())
        rows.append((view, str(path.relative_to(DOC.parent)), caption(view, shares.loc[(v.point_id, v.side)])))
    write_doc(rows, OUT / "legend.png")


def main() -> None:
    """Segment every side view, save the small pictures, check them against the shares, and write the gallery."""
    if "--text-only" in sys.argv:
        text_only()
        return
    OUT.mkdir(parents=True, exist_ok=True)
    allv = views()
    shares = pd.read_csv(STUDY / "segmentation_shares.csv").set_index(["point_id", "side"])
    model = PanopticModel(pick_device())
    palette = class_palette(model.labels)

    # The camera car's typical roof on each side, found the same way as for the shares (keeps the model results)
    roofs, cache = typical_roofs(model, allv, STUDY)

    # Each side view: segment it, save its small picture, and compare it with its published shares
    rows, worst = [], 0.0
    for k, v in enumerate(allv.itertuples(), 1):
        im = Image.open(STUDY / v.view_file).convert("RGB")
        seg = cache.get((v.point_id, v.side)) or model.run(im)
        roof = roofs.get(v.side) if v.capture_year in CAMERA_CAR_YEARS else None
        label_map, _ = fill_roof(class_map(*seg), roof, model.labels)
        label_map = refine_crowns(np.asarray(im, dtype=float) / 255, label_map, model.labels)
        published = shares.loc[(v.point_id, v.side)]
        worst = max(worst, check_shares(label_map, model.labels, published))
        # The photo with the class colours laid over it, as in fig12
        coloured = palette[np.where(label_map >= 0, label_map, len(model.labels))]
        overlay = (0.45 * np.asarray(im) + 0.55 * coloured).astype(np.uint8)
        path = OUT / Path(v.view_file).name
        small_picture(im, overlay, path)
        view = pd.Series(v._asdict())
        rows.append((view, str(path.relative_to(DOC.parent)), caption(view, published)))
        if k % 50 == 0:
            print(f"[segmentation gallery] {k}/{len(allv)} views")
    print(f"largest gap between a picture and its published shares: {worst:.5f}")
    if worst > TOLERANCE:
        sys.exit("the pictures do not match segmentation_shares.csv; re-run models.py first")

    # The gallery, with a fresh legend
    write_doc(rows, legend(model.labels, palette))


# Write the gallery only when the file is run, not when it is imported
if __name__ == "__main__":
    main()
