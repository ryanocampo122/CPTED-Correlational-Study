#!/usr/bin/env python3
"""
make_study_area_map.py
======================
ComputerVision_Sentinel | Study-area map for the main README

Draws the three files in Data/boundaries/ on one map: the Central Business District
polygon (the study area), the Downtown road centrelines and the South Saskatchewan River.
It reuses the base map from make_figures.py, so it matches the other map figures.

  Docs/figures/study_area_map.png

USAGE (repository root):  .venv/bin/python Scripts/reporting/make_study_area_map.py
"""
# Lets type hints name classes before they are defined
from __future__ import annotations

# Shape tools for the polygon area and the map extent
from pyproj import Geod
from shapely.geometry import shape

# Plotting, legend pieces, and the shared base map, palette and folders from make_figures.py
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from make_figures import DPI, INK, INK_2, REPO, _draw_base, _geo

# Where the map is saved
OUT = REPO / "Docs" / "figures" / "study_area_map.png"


def main() -> None:
    """Draw the three boundary layers on one map and save it to OUT."""
    # Road centrelines, the river and the CBD polygon, read from Data/boundaries/
    roads, water, cbd = _geo()

    # The river was clipped to the Downtown map extent, so its bounds are the map's bounds
    extent = shape(water).bounds

    # CBD area in km², measured on the ellipsoid so it is in true square metres
    area_km2 = abs(Geod(ellps="WGS84").geometry_area_perimeter(shape(cbd))[0]) / 1e6

    # River, roads, CBD outline and a 500 m scale bar
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    _draw_base(ax, roads, water, cbd, extent)

    # One legend entry per layer, named after its file
    handles = [
        Line2D([], [], color=INK, lw=1.3,
               label=f"Central Business District, the study area ({area_km2:.2f} km²)\n"
                     "central_business_district_osm.geojson"),
        Line2D([], [], color="#cfcdc6", lw=1.0,
               label=f"Roads, {len(roads)} centrelines (thicker: main roads)\n"
                     "osm_roads_downtown_context.geojson"),
        Patch(facecolor="#dbe9f6", edgecolor="none",
              label="South Saskatchewan River\nosm_water_downtown_context.geojson"),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.01), fontsize=6.6,
              frameon=False, labelspacing=0.9)

    # OpenStreetMap data must carry its licence notice
    ax.text(0.995, 0.005, "Map data © OpenStreetMap contributors (ODbL)", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=6, color=INK_2)

    fig.savefig(OUT, dpi=DPI, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT)


# Draw the map only when the file is run, not when it is imported
if __name__ == "__main__":
    main()
