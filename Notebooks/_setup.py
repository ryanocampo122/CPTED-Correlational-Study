"""
_setup.py
=========
CPTED Vision | Shared set-up for every notebook in Notebooks/

Each notebook starts with `from _setup import *`. That gives it the same folders and the same
project modules the scripts use, and one place to write anything it makes (Notebooks/_out/,
git-ignored). Notebooks read Data/ and Docs/; they never write there.
"""

# Folder paths and adding the project's own modules to the import path
import sys
from pathlib import Path

# Tables, numbers and plots
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# The repository and its main folders
REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "Data"
DOCS = REPO / "Docs"
SCRIPTS = REPO / "Scripts"

# The published datasets the notebooks read: Reddit (study period and the earlier 12 months),
# police crime, and the street-image pilot
REDDIT = DATA / "reddit_2026-06-01_2026-08-31"
REDDIT_JUNE = DATA / "reddit_2025-06-11_2026-06-11"
SPS = DATA / "sps_crime_2026-06-01_2026-08-31"
CV = DATA / "cv_pilot_2026-10"

# Where notebooks write anything they make (git-ignored)
OUT = REPO / "Notebooks" / "_out"

# Let notebooks import pilot_lib and common the same way the scripts do
for folder in (SCRIPTS / "cv_pilot", SCRIPTS / "reddit_analysis" / "scripts"):
    # Add each folder once, at the front, so the project's version is found first
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

# Plots: a white background and readable text in the notebook and in saved files
plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})

# Text added under every figure that shows street images (Mapillary's licence asks for it)
MAPILLARY_CREDIT = "Images: © Mapillary contributors, CC BY-SA 4.0"


def out_dir(name):
    """A folder inside Notebooks/_out/ for one notebook's files, created if needed.

    :param name: the folder name, usually the notebook's name
    :return: the folder's path
    """
    # Make the folder (and Notebooks/_out/) if they aren't there yet
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# What `from _setup import *` brings into a notebook
__all__ = ["Path", "plt", "np", "pd", "REPO", "DATA", "DOCS", "SCRIPTS", "REDDIT", "REDDIT_JUNE", "SPS", "CV",
           "OUT", "MAPILLARY_CREDIT", "out_dir"]
