"""
neighbourhoods.py
=================
ComputerVision_Sentinel | Shared neighbourhood vocabulary, matchers and inputs for the August 2026 analysis code

Scripts 01, 02, 03 and 05 in this folder, and data_pkg_august/04_cleaned_datasets/produce_cleaned_datasets.py,
import from here, so each of these is defined once:

  NEIGHBOURHOODS   the 21 location categories and their patterns, read from the scraper that produced the data
                   (data_pkg_august/01_raw_collection/initial_sraper.py, SASKATOON_NEIGHBOURHOODS). The scraper's
                   source is parsed, never run, so the list cannot drift from the collection it is applied to.
  raw_match        the scraper's original matching: bare substring containment ("river" inside "driver")
  bounded_match    the corrected matching: the same patterns on word boundaries
  slug             a column-name-safe neighbourhood name ("c_downtown_cbd", "vloc_downtown_cbd")
  POSTS_PATH, COMMENTS_PATH   the raw collection in data_pkg_august/01_raw_collection/
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2]          # Deliverables/2026-08_august_report/
RAW_DIR = PACKAGE / "data_pkg_august" / "01_raw_collection"
SCRAPER = RAW_DIR / "initial_sraper.py"
POSTS_PATH = RAW_DIR / "saskatoon_safety_posts_20260611.csv"
COMMENTS_PATH = RAW_DIR / "saskatoon_safety_comments_20260611.csv"


def scraper_constant(name: str):
    """A module-level literal from the scraper's source (ast.literal_eval: nothing is executed)."""
    for node in ast.parse(SCRAPER.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.AnnAssign):
            target = node.target
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        else:
            continue
        if isinstance(target, ast.Name) and target.id == name:
            return ast.literal_eval(node.value)
    raise LookupError(f"{name} is not defined in {SCRAPER}")


NEIGHBOURHOODS: dict[str, list[str]] = scraper_constant("SASKATOON_NEIGHBOURHOODS")


def raw_match(text, patterns: list[str]) -> bool:
    """The ORIGINAL scraper logic: bare substring containment."""
    if not isinstance(text, str):
        return False
    t = text.lower()
    return any(p in t for p in patterns)


def bounded_match(text, patterns: list[str]) -> bool:
    """The CORRECTED logic: the same patterns, matched on word boundaries, so 'river' no longer
    matches inside 'driver'."""
    if not isinstance(text, str):
        return False
    t = text.lower()
    return any(re.search(r"\b" + re.escape(p) + r"\b", t) for p in patterns)


def slug(name: str, prefix: str = "c_") -> str:
    """Column-name-safe neighbourhood name: slug("Downtown / CBD") -> "c_downtown_cbd"."""
    return prefix + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
