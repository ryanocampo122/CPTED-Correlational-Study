#!/usr/bin/env python3
"""
embed_boundary_maps.py
======================
ComputerVision_Sentinel | Interactive boundary maps in the main README

Copies the three files in Data/boundaries/ into README.md as ```geojson blocks. GitHub draws
each block as the same interactive map it shows when the file itself is opened (drag to pan,
scroll to zoom, click a feature for its properties). The script replaces only the text
between the two markers below, so re-running it after a boundary file changes keeps the
README in step.

GitHub's maps ignore colours set in the file, so the river is also drawn in red as a
picture (Docs/figures/downtown_river_red.png) and placed under its map.

USAGE (repository root):  .venv/bin/python Scripts/reporting/embed_boundary_maps.py
"""
# Lets type hints name classes before they are defined
from __future__ import annotations

# Reading the GeoJSON files and finding the repository root
import json
from pathlib import Path

# Plotting, the river's shape, and the shared base map and palette from make_figures.py
import matplotlib.pyplot as plt
from shapely.geometry import shape
from make_figures import DPI, INK_2, _draw_base, _geo

# The repository root, the README it edits and the folder holding the three files
REPO = Path(__file__).resolve().parents[2]
README = REPO / "README.md"
BND = REPO / "Data" / "boundaries"

# The red river picture, its path inside the README, and the red (the palette's "decision needed" red)
RIVER_PNG = REPO / "Docs" / "figures" / "downtown_river_red.png"
RIVER_LINK = "Docs/figures/downtown_river_red.png"
RED = "#d03b3b"

# The README text between these two markers is rewritten on every run
START = "<!-- boundary maps: start (written by Scripts/reporting/embed_boundary_maps.py) -->"
END = "<!-- boundary maps: end -->"

# Each file, the caption above its map, and the picture under it (None for no picture)
MAPS = [
    ("central_business_district_osm.geojson", "Study area: the Central Business District", None),
    ("osm_roads_downtown_context.geojson", "Road centrelines around Downtown", None),
    ("osm_water_downtown_context.geojson", "South Saskatchewan River", RIVER_LINK),
]


def draw_red_river() -> None:
    """Draw the river in red over the Downtown roads and the CBD outline, and save it to RIVER_PNG."""
    # Road centrelines, the river and the CBD polygon, read from Data/boundaries/
    roads, water, cbd = _geo()

    # The river was clipped to the Downtown map extent, so its bounds are the map's bounds
    river = shape(water)
    extent = river.bounds

    # Roads, CBD outline and a 500 m scale bar, with the river first drawn in the usual pale blue
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    _draw_base(ax, roads, water, cbd, extent)

    # Each piece of the river filled red on top of the blue, but under the roads
    for part in getattr(river, "geoms", [river]):
        # The outline of this piece, as x (longitude) and y (latitude) lists
        xs, ys = part.exterior.xy
        ax.fill(xs, ys, color=RED, lw=0, zorder=0.5)

    # OpenStreetMap data must carry its licence notice
    ax.text(0.995, 0.005, "Map data © OpenStreetMap contributors (ODbL)", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=6, color=INK_2)

    fig.savefig(RIVER_PNG, dpi=DPI, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", RIVER_PNG)


def block(name: str, caption: str, picture: str | None) -> str:
    """
    One caption line, one ```geojson block holding the whole file, and an optional picture.

    :param name: file name inside Data/boundaries/
    :param caption: short title shown above the map
    :param picture: README path of a picture shown under the map, or None
    :return: the Markdown for this map
    """
    # The file's features, written without spaces so the README stays as small as it can
    data = json.loads((BND / name).read_text())
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    md = f"**{caption}** ([`{name}`](Data/boundaries/{name}))\n\n```geojson\n{text}\n```\n"

    # The picture goes under the map, with a line saying why it is there
    if picture:
        # A short line and the picture itself
        md += (f"\nThe same river in red, with the Downtown roads and the CBD outline:\n\n"
               f"![{caption} in red]({picture})\n")
    return md


def main() -> None:
    """Draw the red river picture, then rewrite the part of README.md between START and END."""
    draw_red_river()

    # The README split into the part before the maps, the maps and the part after
    readme = README.read_text()
    before, rest = readme.split(START, 1)
    _, after = rest.split(END, 1)

    # The new maps, separated by blank lines
    maps = "\n".join(block(name, caption, picture) for name, caption, picture in MAPS)
    README.write_text(f"{before}{START}\n\n{maps}\n{END}{after}")
    print("wrote", len(MAPS), "maps into", README)


# Write the maps only when the file is run, not when it is imported
if __name__ == "__main__":
    main()
