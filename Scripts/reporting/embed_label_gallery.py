#!/usr/bin/env python3
"""
embed_label_gallery.py
======================
CPTED Vision | The 150 labelled side views as a gallery in Docs/cv_pipeline.md

Reads the labelling sheet (Data/cv_study_2026-11/validation/validation_blind.csv), makes a small copy of each
labelled side view in Docs/figures/label_check/, and writes a gallery into Docs/cv_pipeline.md: one table per
land-use label, each picture linked to the full side view, with the cues marked present under it. Only the text
between the two markers below is replaced, so re-running it after the labels change keeps the doc in step.

USAGE (repository root):  .venv/bin/python Scripts/reporting/embed_label_gallery.py
"""
# Paths and tables
from pathlib import Path

import pandas as pd

# Making the small copies of the pictures
from PIL import Image

# The repository root, the labelling sheet, the doc it edits and the folder for the small copies
REPO = Path(__file__).resolve().parents[2]
VALIDATION = REPO / "Data" / "cv_study_2026-11" / "validation"
SHEET = VALIDATION / "validation_blind.csv"
DOC = REPO / "Docs" / "cv_pipeline.md"
THUMBS = REPO / "Docs" / "figures" / "label_check"

# The doc text between these two markers is rewritten on every run
START = "<!-- label gallery: start (written by Scripts/reporting/embed_label_gallery.py) -->"
END = "<!-- label gallery: end -->"

# Small-copy width in pixels, JPEG quality, and pictures per table row
THUMB_W = 360
QUALITY = 80
PER_ROW = 5

# The cue columns of the sheet and the words shown for them under each picture
CUES = {"human_graffiti_0_1": "graffiti", "human_litter_0_1": "litter", "human_boarded_windows_0_1": "boarded windows",
        "human_vacant_lot_0_1": "vacant lot", "human_active_storefront_0_1": "active storefront",
        "human_windows_overlook_0_1": "windows overlook", "human_people_present_0_1": "people",
        "human_fences_0_1": "fences", "human_seating_0_1": "seating",
        "human_streetlight_visible_0_1": "street light"}


def thumbnail(src: Path) -> Path:
    """Save a small copy of one side view in THUMBS, under the same file name.

    :param src: the full side view
    :return: the small copy
    """
    out = THUMBS / src.name
    with Image.open(src) as im:
        h = round(im.height * THUMB_W / im.width)
        im.convert("RGB").resize((THUMB_W, h), Image.LANCZOS).save(out, "JPEG", quality=QUALITY, optimize=True)
    return out


def caption(row: pd.Series) -> str:
    """The text under one picture: its point and side, the cues marked present, and the labeller's note if any.

    :param row: one row of the labelling sheet
    :return: the caption as HTML
    """
    present = [word for col, word in CUES.items() if row[col] == 1]
    text = f"{row.point_id} {row.side}<br>{', '.join(present) if present else 'no cues marked'}"
    return f"{text}<br><i>{row.human_notes}</i>" if pd.notna(row.human_notes) else text


def gallery(sheet: pd.DataFrame) -> str:
    """One table per land-use label, largest group first, inside a section the reader opens.

    :param sheet: the labelling sheet
    :return: the gallery's Markdown
    """
    parts = []
    # Largest land-use group first; inside a group, by point and side
    for label, group in sorted(sheet.groupby("human_typology"), key=lambda g: (-len(g[1]), g[0])):
        group = group.sort_values(["point_id", "side"])
        cells = []
        for _, r in group.iterrows():
            # The small copy links to the full side view; both paths are relative to Docs/
            full = (VALIDATION / r.image_file).resolve().relative_to(REPO)
            small = thumbnail(REPO / full).relative_to(REPO / "Docs")
            cells.append(f'<td width="20%" valign="top"><a href="../{full}"><img src="{small}" width="160" '
                         f'alt="{r.point_id} {r.side}"></a><br><sub>{caption(r)}</sub></td>')
        rows = ["<tr>" + "".join(cells[i:i + PER_ROW]) + "</tr>" for i in range(0, len(cells), PER_ROW)]
        name = label.replace("_", " ").capitalize()
        parts.append(f"**{name}** ({len(group)} view{'' if len(group) == 1 else 's'})\n\n<table>\n" + "\n".join(rows) + "\n</table>\n")
    summary = (f"<summary><b>Show all {len(sheet)} labelled views</b> (grouped by land-use label; click a picture "
               f"for the full view)</summary>")
    return f"<details>\n{summary}\n\n" + "\n".join(parts) + "\n</details>\n"


def main() -> None:
    """Make the small copies and rewrite the part of the doc between START and END."""
    THUMBS.mkdir(parents=True, exist_ok=True)
    sheet = pd.read_csv(SHEET)

    # A view left without a land-use label gets its own group, so every labelled view is shown
    sheet["human_typology"] = sheet.human_typology.fillna("no_land-use_label")

    # The doc split into the part before the gallery, the gallery and the part after
    doc = DOC.read_text()
    before, rest = doc.split(START, 1)
    _, after = rest.split(END, 1)
    DOC.write_text(f"{before}{START}\n\n{gallery(sheet)}\n{END}{after}")
    print("wrote", len(sheet), "labelled views into", DOC)


# Write the gallery only when the file is run, not when it is imported
if __name__ == "__main__":
    main()
