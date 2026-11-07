"""Offline tests for hotspots.py: street-name matching and the hot-spot rule.
Run from the repo root:  .venv/bin/python Scripts/crime_data/tests/test_hotspots.py   (or pytest)"""
# Test helpers, file paths and tables
import sys
from pathlib import Path

import pandas as pd

# The script under test
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hotspots as H  # noqa: E402


def test_street_key_matches_sps_and_osm_spellings():
    """SPS abbreviations and OSM full names end up the same; different streets stay different."""
    assert H.street_key("21ST ST E") == H.street_key("21st Street East") == "21 STREET EAST"
    assert H.street_key("1ST AVE N") == H.street_key("1 Avenue North") == H.street_key("1st Avenue North")
    assert H.street_key("SPADINA CRES E") == H.street_key("Spadina Crescent East")
    assert H.street_key("2ND AVE S") != H.street_key("2nd Avenue North")
    assert H.street_key(float("nan")) == ""


def test_concentration_marks_the_segments_holding_half():
    """With counts 6, 3, 1, 0 the first segment alone holds 60%, so it is the only hot spot."""
    counts = pd.Series({"a": 6.0, "b": 3.0, "c": 1.0, "d": 0.0})
    hot, share = H.concentration(counts)
    assert hot.tolist() == [True, False, False, False] and share == 0.25


if __name__ == "__main__":
    # Run every test in this file and report each one
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:  # noqa: BLE001
                fails += 1
                print("FAIL", name, repr(exc))
    sys.exit(1 if fails else 0)
