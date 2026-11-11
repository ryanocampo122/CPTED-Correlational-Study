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

USAGE (repository root):  .venv/bin/python Scripts/reporting/embed_boundary_maps.py
"""
# Lets type hints name classes before they are defined
from __future__ import annotations

# Reading the GeoJSON files and finding the repository root
import json
from pathlib import Path

# The repository root, the README it edits and the folder holding the three files
REPO = Path(__file__).resolve().parents[2]
README = REPO / "README.md"
BND = REPO / "Data" / "boundaries"

# The README text between these two markers is rewritten on every run
START = "<!-- boundary maps: start (written by Scripts/reporting/embed_boundary_maps.py) -->"
END = "<!-- boundary maps: end -->"

# Each file and the caption above its map, in the order they appear
MAPS = [
    ("central_business_district_osm.geojson", "Study area: the Central Business District"),
    ("osm_roads_downtown_context.geojson", "Road centrelines around Downtown"),
    ("osm_water_downtown_context.geojson", "South Saskatchewan River"),
]


def block(name: str, caption: str) -> str:
    """
    One caption line and one ```geojson block holding the whole file.

    :param name: file name inside Data/boundaries/
    :param caption: short title shown above the map
    :return: the Markdown for this map
    """
    # The file's features, written without spaces so the README stays as small as it can
    data = json.loads((BND / name).read_text())
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return f"**{caption}** ([`{name}`](Data/boundaries/{name}))\n\n```geojson\n{text}\n```\n"


def main() -> None:
    """Rewrite the part of README.md between START and END with the three maps."""
    # The README split into the part before the maps, the maps and the part after
    readme = README.read_text()
    before, rest = readme.split(START, 1)
    _, after = rest.split(END, 1)

    # The new maps, separated by blank lines
    maps = "\n".join(block(name, caption) for name, caption in MAPS)
    README.write_text(f"{before}{START}\n\n{maps}\n{END}{after}")
    print("wrote", len(MAPS), "maps into", README)


# Write the maps only when the file is run, not when it is imported
if __name__ == "__main__":
    main()
