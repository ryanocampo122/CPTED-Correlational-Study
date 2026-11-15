#!/usr/bin/env python3
"""
embed_model_details.py
======================
CPTED Vision | Detailed numbers and example pictures for steps 4 and 5 in Docs/cv_pipeline.md

Step 4 (object detection): a table of every object class the model counts (views with at least one, by photo year,
objects counted, most in one view, and the label check where there is one), and four example views with each counted
object boxed. Step 5 (CLIP): a land-use table and a cue table (all 492 views, and agreement with the 150 labelled
views), and four labelled example views with CLIP's answers next to the labels. Every number is read from
Data/cv_study_2026-11/; the example views are picked by fixed rules, written below. Only the text between each pair
of markers is replaced.

USAGE (repository root):  .venv/bin/python Scripts/reporting/embed_model_details.py
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
from PIL import Image  # noqa: E402

# The study's models and the shared class colours
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "Scripts" / "cv_study"))
from make_figures_november import class_palette  # noqa: E402
from models import OBJECT_CLASSES, PanopticModel, pick_device, slug  # noqa: E402

# Inputs, the doc it edits and the folder for the two figures
STUDY = REPO / "Data" / "cv_study_2026-11"
DOC = REPO / "Docs" / "cv_pipeline.md"
OUT = REPO / "Docs" / "figures" / "model_details"

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


def detection_section(t: dict) -> str:
    """The step 4 table, its explanation and the example figure.

    :param t: the tables (load)
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
    fig = detection_figure(t)
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
            f"is one object the model counted, and the box counts match `object_counts.csv`.*\n")


def detection_figure(t: dict) -> Path:
    """Four views with every counted object boxed and named, checked against object_counts.csv.

    :param t: the tables (load)
    :return: the figure's path
    """
    oc = t["objects"].sort_values(["point_id", "side"])
    model = PanopticModel(pick_device())
    palette = class_palette(model.labels)
    fig, axes = plt.subplots(2, 2, figsize=(9.6, 7.6))
    # One panel per example class: the view with the most objects of that class
    for ax, (name, plural) in zip(axes.flat, EXAMPLE_OBJECTS.items()):
        v = oc.loc[oc[f"count_{slug(name)}"].idxmax()]
        im = Image.open(view_file(t["manifest"], v.point_id, v.side)).convert("RGB")
        seg_map, segments = model.run(im)
        ax.imshow(im)
        found = {}
        # A box around each object of a counted class (all four examples are 2020 photos, so no camera roof)
        for s in segments:
            label = model.labels[s["label_id"]]
            if label not in OBJECT_CLASSES:
                continue
            ys, xs = np.nonzero(seg_map == s["id"])
            colour = palette[s["label_id"]] / 255
            ax.add_patch(Rectangle((xs.min(), ys.min()), xs.max() - xs.min(), ys.max() - ys.min(), fill=False,
                                   lw=1.6, edgecolor=colour))
            # Dark text on light colours, white text on dark ones
            ink = "black" if colour @ [0.299, 0.587, 0.114] > 0.6 else "white"
            ax.text(xs.min(), ys.min() - 4, words(label), fontsize=6.5, color=ink,
                    bbox={"facecolor": colour, "edgecolor": "none", "pad": 1})
            found[label] = found.get(label, 0) + 1
        # The boxes must match the published counts for this view
        for label in OBJECT_CLASSES:
            if found.get(label, 0) != int(v[f"count_{slug(label)}"]):
                sys.exit(f"{v.point_id} {v.side}: {label} boxes {found.get(label, 0)} != published "
                         f"{int(v[f'count_{slug(label)}'])}")
        listed = ", ".join(f"{k} {words(c)}" for c, k in sorted(found.items(), key=lambda kv: -kv[1]))
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


def clip_section(t: dict) -> str:
    """The step 5 tables, their explanation and the example figure.

    :param t: the tables (load)
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
    fig = clip_figure(t)
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
            f"windows that the label does not show.*\n")


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


def main() -> None:
    """Draw the two figures and rewrite both marked parts of the doc."""
    OUT.mkdir(parents=True, exist_ok=True)
    t = load()
    doc = DOC.read_text()
    # Each section between its markers
    for key, text in (("detection", detection_section(t)), ("clip", clip_section(t))):
        start, end = MARKS[key]
        before, rest = doc.split(start, 1)
        _, after = rest.split(end, 1)
        doc = f"{before}{start}\n\n{text}\n{end}{after}"
    DOC.write_text(doc)
    print("wrote steps 4 and 5 details into", DOC)


# Write the details only when the file is run, not when it is imported
if __name__ == "__main__":
    main()
