#!/usr/bin/env python3
"""
embed_model_details.py
======================
CPTED Vision | Detailed numbers and example pictures for steps 4 and 5 in Docs/cv_pipeline.md

Step 4 (object detection): a table of every object class the model counts (views with at least one, by photo year,
objects counted, most in one view, and the label check where there is one), and four example views with each counted
object boxed. Step 5 (CLIP): a land-use table and a cue table (all 492 views, and agreement with the 150 labelled
views), and four labelled example views with CLIP's answers next to the labels. Each step ends with a drop-down
gallery of all 492 side views: every counted object boxed (step 4, checked against object_counts.csv), and CLIP's land
use and cues under each photo, grouped by CLIP's land use (step 5). Every number is read from Data/cv_study_2026-11/;
the example views are picked by fixed rules, written below. Only the text between each pair of markers is replaced.

The model runs once over all 492 views (about 15 minutes on the Mac's GPU). With --text-only it rewrites only the doc
text from the pictures already saved, in a few seconds.

USAGE (repository root):  .venv/bin/python Scripts/reporting/embed_model_details.py [--text-only]
"""
# Command-line paths and wrapping long captions
import sys
import textwrap
from pathlib import Path

# Pictures and tables
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

# The study's models and the shared class colours
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "Scripts" / "cv_study"))
from make_figures_november import class_palette  # noqa: E402
from models import (CAMERA_CAR_YEARS, OBJECT_CLASSES, PanopticModel, class_map, fill_roof,  # noqa: E402
                    pick_device, slug, typical_roofs)

# Inputs, the doc it edits, the folder for the two figures and the folders for the two galleries' small pictures
STUDY = REPO / "Data" / "cv_study_2026-11"
DOC = REPO / "Docs" / "cv_pipeline.md"
OUT = REPO / "Docs" / "figures" / "model_details"
DET_ALL = REPO / "Docs" / "figures" / "detection_all"
CLIP_ALL = REPO / "Docs" / "figures" / "clip_all"

# Small-picture sizes (the boxes need the larger one to be seen), JPEG quality, and pictures per gallery row
DET_SIZE = (360, 270)
CLIP_SIZE = (240, 180)
QUALITY = 78
PER_ROW = 3

# The doc text between each pair of markers is rewritten on every run
MARKS = {"detection": ("<!-- detection details: start (written by Scripts/reporting/embed_model_details.py) -->",
                       "<!-- detection details: end -->"),
         "clip": ("<!-- clip details: start (written by Scripts/reporting/embed_model_details.py) -->",
                  "<!-- clip details: end -->")}

# The label-check cue names as plain words
CHECK_WORDS = {"streetlight_visible": "street lights", "seating": "seating", "people_present": "people"}

# The fixed rules from step 7: a CLIP cue counts as present at a score of 0.5 or more, an object at a count of 1
CLIP_PRESENT = 0.5

# The detection examples: the view with the most objects of each of these classes (ties: first by point and side),
# and the plural used in each panel title
EXAMPLE_OBJECTS = {"Street Light": "street lights", "Bench": "benches", "Person": "people", "Trash Can": "trash cans"}

# The cue columns of the labelling sheet and of the CLIP table, and the words shown for each cue
CUES = [("graffiti", "human_graffiti_0_1", "cue_graffiti_mean"),
        ("litter", "human_litter_0_1", "cue_litter_mean"),
        ("boarded windows", "human_boarded_windows_0_1", "cue_boarded_windows_mean"),
        ("vacant lot", "human_vacant_lot_0_1", "cue_vacant_lot_mean"),
        ("active storefront", "human_active_storefront_0_1", "cue_active_storefront_mean"),
        ("windows overlook the street", "human_windows_overlook_0_1", "cue_windows_overlook_street_mean"),
        ("people present", "human_people_present_0_1", "cue_people_present_mean"),
        ("fences or barriers", "human_fences_0_1", "cue_fences_barriers_mean"),
        ("seating", "human_seating_0_1", "cue_seating_mean")]


def words(name: str) -> str:
    """A class or land-use name as plain words: "surface_parking" -> "surface parking".

    :param name: the name
    :return: the words
    """
    return name.replace("_", " ").lower().replace("cctv", "CCTV")


def num(x: float, places: int = 2) -> str:
    """A score for a table, or a dash when it cannot be worked out.

    :param x: the score
    :param places: decimal places
    :return: the text
    """
    return "–" if pd.isna(x) else f"{x:.{places}f}"


def load() -> dict:
    """Every table this script reads.

    :return: the tables by name
    """
    keys = ["point_id", "side"]
    labels = pd.read_csv(STUDY / "validation" / "validation_blind.csv")
    return {"objects": pd.read_csv(STUDY / "object_counts.csv"), "clip": pd.read_csv(STUDY / "clip_scores.csv"),
            "manifest": pd.read_csv(STUDY / "image_manifest.csv"), "labels": labels,
            "results": pd.read_csv(STUDY / "validation" / "validation_results.csv"),
            "labelled_clip": labels.merge(pd.read_csv(STUDY / "clip_scores.csv"), on=keys, validate="one_to_one")}


def view_file(manifest: pd.DataFrame, point_id: str, side: str) -> Path:
    """The side view picture of one point and side.

    :param manifest: image_manifest.csv
    :param point_id: the point
    :param side: "left" or "right"
    :return: the picture's path
    """
    return STUDY / manifest.set_index("point_id").loc[point_id, f"view_{side}"]


def detection_section(t: dict, fig: Path) -> str:
    """The step 4 table, its explanation, the example figure and the gallery.

    :param t: the tables (load)
    :param fig: the example figure
    :return: the section's Markdown
    """
    oc, res = t["objects"], t["results"]
    n, n20, n23 = len(oc), int((oc.capture_year == 2020).sum()), int((oc.capture_year == 2023).sum())
    # The label check for the object classes that have one, by count column
    checks = {r.prediction: r for r in res[res.model == "object"].itertuples()}
    rows = []
    # One row per object class, the most common first
    for name in sorted(OBJECT_CLASSES, key=lambda c: -int((oc[f"count_{slug(c)}"] > 0).sum())):
        col = f"count_{slug(name)}"
        has = oc[col] > 0
        check = checks.get(col)
        verdict = f"{num(check.f1)} for {CHECK_WORDS[check.cue]} ({'passes' if check.passes_f1_0_7 else 'fails'})" \
            if check is not None else "not checked"
        rows.append(f"| {words(name)} | {int(has.sum())} ({round(100 * has.mean())}%) | "
                    f"{int(has[oc.capture_year == 2020].sum())} | {int(has[oc.capture_year == 2023].sum())} | "
                    f"{int(oc[col].sum())} | {int(oc[col].max())} | {verdict} |")
    light, bench, person = (checks[f"count_{slug(c)}"] for c in ("Street Light", "Bench", "Person"))
    return (f"The table gives the full counts. A view counts once for a class if the model found at least one object "
            f"of that class in it. The last column is the label check from step 7, which exists for street lights, "
            f"benches (as seating) and people; a check passes at an F1 of 0.7 or more.\n\n"
            f"| Object | Views with at least one (of {n}) | 2020 views (of {n20}) | 2023 views (of {n23}) | "
            f"Objects counted | Most in one view | Label check (F1) |\n|---|---|---|---|---|---|---|\n"
            + "\n".join(rows) +
            f"\n\nStreet lights pass with an F1 of {light.f1:.2f}: of the views where the model found a street light, "
            f"{round(100 * light.precision)}% had one in the labels, and it found {round(100 * light.recall)}% of the "
            f"views that had one. Benches pass as a measure of seating ({bench.f1:.2f}, precision "
            f"{bench.precision:.2f}, recall {bench.recall:.2f}). People do not pass ({person.f1:.2f}): the model finds "
            f"{round(100 * person.recall)}% of the views with people, but only {round(100 * person.precision)}% of "
            f"the views where it finds a person have one in the labels.\n\n"
            f"![Four views with each counted object boxed]({fig.relative_to(DOC.parent)})\n\n"
            f"*The views with the most street lights, benches, people and trash cans, picked by that rule; each box "
            f"is one object the model counted, and the box counts match `object_counts.csv`.*\n\n"
            f"Every side view is in the drop-down below, with each counted object boxed in the colour of its class; "
            f"the script checks that every view's boxes match `object_counts.csv`.\n\n" + detection_gallery(t))


def side_views(manifest: pd.DataFrame) -> pd.DataFrame:
    """One row per side view (point, side, year, picture path), by point then side.

    :param manifest: image_manifest.csv
    :return: the side views
    """
    out = pd.concat([manifest.assign(side=s, view_file=manifest[f"view_{s}"]) for s in ("left", "right")])
    return out.sort_values(["point_id", "side"]).reset_index(drop=True)


def object_boxes(seg_map: np.ndarray, segments: list[dict], labels: list[str], roof: np.ndarray | None) -> list:
    """A box around every object the model counted in one view, the way models.describe counts them.

    :param seg_map: segment id per pixel
    :param segments: {id, label_id, score} for each segment
    :param labels: the model's class names by id
    :param roof: in a car-roof image, the typical roof for this side (typical_roofs), else None
    :return: (class name, class id, x0, y0, x1, y1) per counted object
    """
    # Objects lying mostly on a filled-in camera roof are reflections and are not counted
    _, filled = fill_roof(class_map(seg_map, segments), roof, labels)
    boxes = []
    for s in segments:
        label = labels[s["label_id"]]
        mask = seg_map == s["id"]
        if label not in OBJECT_CLASSES or (filled and roof[mask].mean() > 0.5):
            continue
        ys, xs = np.nonzero(mask)
        boxes.append((label, s["label_id"], xs.min(), ys.min(), xs.max(), ys.max()))
    return boxes


def check_boxes(view: str, published: pd.Series, boxes: list) -> None:
    """Stop if the boxes in a view do not match its published counts.

    :param view: the view's point and side, for the message
    :param published: the view's row of object_counts.csv
    :param boxes: object_boxes for the view
    """
    for label in OBJECT_CLASSES:
        found = sum(b[0] == label for b in boxes)
        if found != int(published[f"count_{slug(label)}"]):
            sys.exit(f"{view}: {label} boxes {found} != published {int(published[f'count_{slug(label)}'])}")


def detection_pass(t: dict) -> dict:
    """Run the model once over every side view, save each view's boxed small picture and the legend, and check every
    view's boxes against object_counts.csv.

    :param t: the tables (load)
    :return: {(point_id, side): (boxes, palette)} for every view
    """
    DET_ALL.mkdir(parents=True, exist_ok=True)
    views = side_views(t["manifest"])
    counts = t["objects"].set_index(["point_id", "side"])
    model = PanopticModel(pick_device())
    palette = class_palette(model.labels)
    roofs, cache = typical_roofs(model, views, STUDY)
    out = {}
    # Each side view: find its objects, check them, and draw them on a small copy of the photo
    for k, v in enumerate(views.itertuples(), 1):
        im = Image.open(STUDY / v.view_file).convert("RGB")
        seg = cache.get((v.point_id, v.side)) or model.run(im)
        roof = roofs.get(v.side) if v.capture_year in CAMERA_CAR_YEARS else None
        boxes = object_boxes(*seg, model.labels, roof)
        check_boxes(f"{v.point_id} {v.side}", counts.loc[(v.point_id, v.side)], boxes)
        small = im.resize(DET_SIZE, Image.LANCZOS)
        draw = ImageDraw.Draw(small)
        sx, sy = DET_SIZE[0] / im.width, DET_SIZE[1] / im.height
        for label, lid, x0, y0, x1, y1 in boxes:
            draw.rectangle([x0 * sx, y0 * sy, x1 * sx, y1 * sy], outline=tuple(int(c) for c in palette[lid]), width=2)
        small.save(DET_ALL / f"{v.point_id}_{v.side}.jpg", "JPEG", quality=QUALITY, optimize=True)
        out[(v.point_id, v.side)] = boxes
        if k % 50 == 0:
            print(f"[detection gallery] {k}/{len(views)} views")
    # One legend for the object colours
    present = [c for c in OBJECT_CLASSES if any(b[0] == c for bs in out.values() for b in bs)]
    handles = [Rectangle((0, 0), 1, 1, fill=False, lw=2, edgecolor=palette[model.labels.index(c)] / 255,
                         label=words(c)) for c in present]
    fig = plt.figure(figsize=(8.6, 0.9))
    fig.legend(handles=handles, loc="center", ncol=6, fontsize=8, frameon=False, handlelength=1.2)
    fig.savefig(DET_ALL / "legend.png", dpi=150, bbox_inches="tight", pad_inches=0.04, metadata={"Software": None})
    plt.close(fig)
    return {"boxes": out, "palette": palette, "labels": model.labels}


def detection_figure(t: dict, found: dict) -> Path:
    """Four views with every counted object boxed and named.

    :param t: the tables (load)
    :param found: detection_pass
    :return: the figure's path
    """
    oc = t["objects"].sort_values(["point_id", "side"])
    fig, axes = plt.subplots(2, 2, figsize=(9.6, 7.6))
    # One panel per example class: the view with the most objects of that class
    for ax, (name, plural) in zip(axes.flat, EXAMPLE_OBJECTS.items()):
        v = oc.loc[oc[f"count_{slug(name)}"].idxmax()]
        ax.imshow(Image.open(view_file(t["manifest"], v.point_id, v.side)).convert("RGB"))
        boxes = found["boxes"][(v.point_id, v.side)]
        # A named box around each counted object
        for label, lid, x0, y0, x1, y1 in boxes:
            colour = found["palette"][lid] / 255
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, lw=1.6, edgecolor=colour))
            # Dark text on light colours, white text on dark ones
            ink = "black" if colour @ [0.299, 0.587, 0.114] > 0.6 else "white"
            ax.text(x0, y0 - 4, words(label), fontsize=6.5, color=ink,
                    bbox={"facecolor": colour, "edgecolor": "none", "pad": 1})
        tally = pd.Series([b[0] for b in boxes]).value_counts()
        listed = ", ".join(f"{k} {words(c)}" for c, k in tally.items())
        ax.set_title(f"Most {plural}: {v.point_id} {v.side}, {v.capture_year}\n{listed}", loc="left",
                     fontsize=7.5)
        ax.set_xticks([]), ax.set_yticks([])
    fig.text(0.995, 0.005, "Images: Mapillary contributors (CC BY-SA 4.0). Objects: Mask2Former (Mapillary Vistas)",
             ha="right", fontsize=6, color="#555")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.03, hspace=0.18, wspace=0.03)
    path = OUT / "detection_examples.png"
    fig.savefig(path, dpi=130, metadata={"Software": None})
    plt.close(fig)
    return path


def table_rows(cells: list[str]) -> str:
    """Gallery cells as an HTML table, PER_ROW to a row.

    :param cells: one <td> per picture
    :return: the table
    """
    rows = ["<tr>" + "".join(cells[i:i + PER_ROW]) + "</tr>" for i in range(0, len(cells), PER_ROW)]
    return "<table>\n" + "\n".join(rows) + "\n</table>\n"


def cell(v, small: Path, width: int, text: str) -> str:
    """One gallery picture and its caption, kept short: GitHub shows only the first ~500 KB of a page.

    :param v: the side view (point_id, side)
    :param small: the small picture
    :param width: display width in pixels
    :param text: the caption (HTML)
    :return: the <td>
    """
    return f'<td valign="top"><img src="{small.relative_to(DOC.parent)}" width="{width}"><br><sub>{text}</sub></td>'


def detection_gallery(t: dict) -> str:
    """Every side view with its counted objects boxed, by photo year, in a drop-down.

    :param t: the tables (load)
    :return: the gallery's Markdown
    """
    views = side_views(t["manifest"])
    counts = t["objects"].set_index(["point_id", "side"])
    cols = [f"count_{slug(c)}" for c in OBJECT_CLASSES]
    parts = [f"![Box colours]({(DET_ALL / 'legend.png').relative_to(DOC.parent)})\n"]
    # One table per photo year
    for year in sorted(views.capture_year.unique()):
        cells = []
        for v in views[views.capture_year == year].itertuples():
            small = DET_ALL / f"{v.point_id}_{v.side}.jpg"
            if not small.exists():
                sys.exit(f"no small picture for {v.point_id} {v.side}; run without --text-only")
            c = counts.loc[(v.point_id, v.side), cols].astype(int)
            c = c[c > 0].sort_values(ascending=False, kind="stable")
            listed = ", ".join(f"{k} {words(col[6:])}" for col, k in c.items()) or "no objects"
            cells.append(cell(v, small, 250, f"{v.point_id} {v.side}, {v.capture_year}<br>{listed}"))
        parts.append(f"**{year} photos** ({len(cells)} side views)\n\n" + table_rows(cells))
    return ("<details>\n<summary><h3>Drop down for all photos</h3></summary>\n\n" + "\n".join(parts)
            + "\n</details>\n")


def clip_section(t: dict, fig: Path) -> str:
    """The step 5 tables, their explanation, the example figure and the gallery.

    :param t: the tables (load)
    :param fig: the example figure
    :return: the section's Markdown
    """
    cl, lc, res = t["clip"], t["labelled_clip"], t["results"]
    n, n_lab = len(cl), len(lc)
    # Land use: CLIP's label on every view, and on the labelled views how often it agrees with the label
    land = []
    for typ in cl.typology_top1.value_counts().index.union(lc.human_typology.dropna().unique(), sort=False):
        mine = cl.typology_top1 == typ
        said = lc.human_typology == typ
        agree = int((said & (lc.typology_top1 == typ)).sum())
        land.append((int(mine.sum()), f"| {words(typ)} | {int(mine.sum())} | {int(cl.typology_low_confidence[mine].sum())} "
                                      f"| {int(said.sum())} | {agree} |"))
    land = [row for _, row in sorted(land, key=lambda r: -r[0])]
    labelled = lc.dropna(subset=["human_typology"])
    accuracy = (labelled.human_typology == labelled.typology_top1).mean()
    commercial = labelled[labelled.human_typology == "commercial_street"].typology_top1.value_counts()
    n_wrong = int((labelled.human_typology != labelled.typology_top1).sum())
    # Cues: how often CLIP marks each present, and the label check
    checks = {r.prediction: r for r in res[res.model == "clip"].itertuples()}
    cue_rows = []
    for word, human, col in CUES:
        c = checks[col]
        cue_rows.append(f"| {word} | {int((cl[col] >= CLIP_PRESENT).sum())} | {cl[col].median():.2f} | "
                        f"{int(c.present_in_labels)} | {num(c.precision)} | {num(c.recall)} | {num(c.f1)} |")
    present = {word: int((cl[col] >= CLIP_PRESENT).sum()) for word, _, col in CUES}
    in_labels = {word: int(checks[col].present_in_labels) for word, _, col in CUES}
    return (f"CLIP gives each view a probability for each of the eight land-use types, and a score from 0 to 1 for "
            f"each cue. The tables give its results on all {n} views and, for the {n_lab} labelled views, how often it "
            f"agrees with the labels. A land-use label is low-confidence when CLIP's top probability is under 0.40 or "
            f"less than 0.10 ahead of the second.\n\n"
            f"| Land-use type | CLIP's label (of {n}) | Of those, low-confidence | Labels say (of {n_lab}) | "
            f"CLIP agrees |\n|---|---|---|---|---|\n" + "\n".join(land) +
            f"\n\nOn the labelled views CLIP's land-use label matches {round(100 * accuracy)}% of the time. Of its "
            f"{n_wrong} mistakes, {int(commercial.sum() - commercial.get('commercial_street', 0))} are on the "
            f"{int(commercial.sum())} views labelled commercial street: it calls "
            f"{int(commercial.get('surface_parking', 0))} of them surface parking and "
            f"{int(commercial.get('transit_node', 0))} transit node, and gets "
            f"{int(commercial.get('commercial_street', 0))} right.\n\n"
            f"A cue counts as present when its score is {CLIP_PRESENT} or more, the rule fixed before the label check."
            f"\n\n| Cue | CLIP marks present (of {n}) | Median score | Present in labels (of {n_lab}) | Precision | "
            f"Recall | F1 |\n|---|---|---|---|---|---|---|\n" + "\n".join(cue_rows) +
            f"\n\nBy that rule CLIP marks boarded windows in {present['boarded windows']} of the {n} views and a "
            f"vacant lot in {present['vacant lot']}, far more than the labels show ({in_labels['boarded windows']} and "
            f"{in_labels['vacant lot']} of {n_lab}). It almost never marks active storefronts ("
            f"{present['active storefront']} views) or windows overlooking the street ("
            f"{present['windows overlook the street']}), which the labels find in {in_labels['active storefront']} "
            f"and {in_labels['windows overlook the street']} of {n_lab}. Its scores do not follow these cues on "
            f"Downtown's streets, so no cue passes the check and none is used.\n\n"
            f"![Four labelled views with CLIP's answers]({fig.relative_to(DOC.parent)})\n\n"
            f"*Four labelled views picked by fixed rules: where CLIP is most sure and right about land use, the two "
            f"most common land-use mistakes (each where CLIP is most sure), and where CLIP is most sure of boarded "
            f"windows that the label does not show.*\n\n"
            f"Every side view is in the drop-down below, grouped by CLIP's land-use label, with its probability and "
            f"the cues it scores at {CLIP_PRESENT} or more; views in the labelled sample also show their label.\n\n"
            + clip_gallery(t))


def clip_figure(t: dict) -> Path:
    """Four labelled views with CLIP's land use and cues next to the labels.

    :param t: the tables (load)
    :return: the figure's path
    """
    lc = t["labelled_clip"].dropna(subset=["human_typology"]).sort_values(["point_id", "side"])
    agree = lc[lc.human_typology == lc.typology_top1]
    wrong = lc[lc.human_typology != lc.typology_top1]
    # The two most common mistakes (label, CLIP's label), most common first
    pairs = wrong.groupby(["human_typology", "typology_top1"]).size().sort_values(ascending=False, kind="stable")
    picks = [("Right about land use", agree.loc[agree.typology_top1_prob.idxmax()])]
    for (said, clip_said), _ in pairs.head(2).items():
        rows = wrong[(wrong.human_typology == said) & (wrong.typology_top1 == clip_said)]
        picks.append((f"Common mistake: {words(said)} called {words(clip_said)}",
                      rows.loc[rows.typology_top1_prob.idxmax()]))
    no_boards = lc[lc.human_boarded_windows_0_1 == 0]
    picks.append(("Boarded windows that are not there", no_boards.loc[no_boards.cue_boarded_windows_mean.idxmax()]))
    fig, axes = plt.subplots(2, 2, figsize=(9.6, 8.6))
    # One panel per pick: the photo, then CLIP's answers and the labels under it
    for ax, (title, r) in zip(axes.flat, picks):
        ax.imshow(Image.open(view_file(t["manifest"], r.point_id, r.side)).convert("RGB"))
        ax.set_xticks([]), ax.set_yticks([])
        clip_cues = [f"{word} {r[col]:.2f}" for word, _, col in CUES if r[col] >= CLIP_PRESENT]
        label_cues = [word for word, human, _ in CUES if r[human] == 1]
        ax.set_title(f"{title}\n{r.point_id} {r.side}, {r.capture_year}", loc="left", fontsize=8)
        lines = [f"Label: {words(r.human_typology)}; cues: {', '.join(label_cues) or 'none'}",
                 f"CLIP: {words(r.typology_top1)} ({r.typology_top1_prob:.2f}); cues at 0.5 or more: "
                 f"{', '.join(clip_cues) or 'none'}"]
        ax.text(0, -0.03, "\n".join(textwrap.fill(line, 92) for line in lines), transform=ax.transAxes, va="top",
                fontsize=6.8)
    fig.text(0.995, 0.005, "Images: Mapillary contributors (CC BY-SA 4.0). Scores: CLIP ViT-B/32", ha="right",
             fontsize=6, color="#555")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.07, hspace=0.38, wspace=0.03)
    path = OUT / "clip_examples.png"
    fig.savefig(path, dpi=130, metadata={"Software": None})
    plt.close(fig)
    return path


def clip_pictures(t: dict) -> None:
    """Save a small copy of every side view for the CLIP gallery.

    :param t: the tables (load)
    """
    CLIP_ALL.mkdir(parents=True, exist_ok=True)
    for v in side_views(t["manifest"]).itertuples():
        with Image.open(STUDY / v.view_file) as im:
            im.convert("RGB").resize(CLIP_SIZE, Image.LANCZOS).save(CLIP_ALL / f"{v.point_id}_{v.side}.jpg", "JPEG",
                                                                   quality=QUALITY, optimize=True)


def clip_gallery(t: dict) -> str:
    """Every side view with CLIP's land use and cues, grouped by CLIP's land use, in a drop-down.

    :param t: the tables (load)
    :return: the gallery's Markdown
    """
    views = side_views(t["manifest"]).merge(t["clip"], on=["point_id", "side", "capture_year"], validate="one_to_one")
    labels = t["labels"].set_index(["point_id", "side"]).human_typology
    parts = []
    # One table per CLIP land-use label, the most common first
    for typ in views.typology_top1.value_counts().index:
        cells = []
        for v in views[views.typology_top1 == typ].itertuples():
            small = CLIP_ALL / f"{v.point_id}_{v.side}.jpg"
            if not small.exists():
                sys.exit(f"no small picture for {v.point_id} {v.side}; run without --text-only")
            low = " (low confidence)" if v.typology_low_confidence else ""
            cues = ", ".join(f"{word} {getattr(v, col):.2f}" for word, _, col in CUES
                             if getattr(v, col) >= CLIP_PRESENT) or "none"
            text = f"{v.point_id} {v.side}, {v.capture_year}<br>{words(typ)} {v.typology_top1_prob:.2f}{low}<br>cues: {cues}"
            if (v.point_id, v.side) in labels.index:
                said = labels.loc[(v.point_id, v.side)]
                text += f"<br><i>label: {words(said) if pd.notna(said) else 'no land-use label'}</i>"
            cells.append(cell(v, small, 200, text))
        parts.append(f"**CLIP says {words(typ)}** ({len(cells)} side views)\n\n" + table_rows(cells))
    return ("<details>\n<summary><h3>Drop down for all photos</h3></summary>\n\n" + "\n".join(parts)
            + "\n</details>\n")


def main() -> None:
    """Run the model and draw the pictures (unless --text-only), then rewrite both marked parts of the doc."""
    OUT.mkdir(parents=True, exist_ok=True)
    t = load()
    if "--text-only" in sys.argv:
        det_fig, clip_fig = OUT / "detection_examples.png", OUT / "clip_examples.png"
    else:
        found = detection_pass(t)
        det_fig = detection_figure(t, found)
        clip_pictures(t)
        clip_fig = clip_figure(t)
    doc = DOC.read_text()
    # Each section between its markers
    for key, text in (("detection", detection_section(t, det_fig)), ("clip", clip_section(t, clip_fig))):
        start, end = MARKS[key]
        before, rest = doc.split(start, 1)
        _, after = rest.split(end, 1)
        doc = f"{before}{start}\n\n{text}\n{end}{after}"
    DOC.write_text(doc)
    print("wrote steps 4 and 5 details into", DOC)


# Write the details only when the file is run, not when it is imported
if __name__ == "__main__":
    main()
