#!/usr/bin/env python3
"""
hotspots.py
===========
CPTED Vision | November 2026: recorded crime (Y1) on the CBD street segments

Places every study-category SPS record inside the CBD on the street segments the sample points sit on,
then counts records per segment, by study category and by group (property; street-based personal,
Docs/crime_data.md). Hot spots are the segments that together hold half of a group's records, the usual
crime-concentration measure; a formal hot-spot statistic comes later.

Placement rule (by street name first, because SPS places a hundred-block record at a general point
30-85 m from the road centreline, so plain distance would put it on the wrong street or nowhere):
  * the 218 study segments are rebuilt from Data/boundaries/osm_roads_downtown_context.geojson with the
    same road classes, box and splitting code as the sample points, and checked against each point's
    published segment length;
  * a hundred-block record goes to the nearest segment of the street it names (SPS "21ST ST E" =
    OSM "21st Street East") within 100 m;
  * an intersection record is split equally between the segments of its two named streets within 30 m;
  * a record whose street has no study segment close enough goes to the nearest study segment within
    30 m, and otherwise is kept and counted as unplaced (lanes, parking lots, roads with no sample point).

Reads Data/sps_crime_2026-06-01_2026-08-31/02_cleaned/ and Data/cv_pilot_2026-10/cbd/sample_points.csv.
Writes Data/sps_crime_2026-06-01_2026-08-31/03_segments/:
  segment_crime_counts.csv   one row per study segment: length, counts by category and group, per 100 m, hot-spot flags
  record_links.csv           which segment(s) each record went to, with its share and distance
  hotspot_summary.json       totals, unplaced records and the concentration figures

USAGE (repository root):  .venv/bin/python Scripts/crime_data/hotspots.py [--out <folder>]
"""
# Command-line options, file paths and the summary file
import argparse
import json
import sys
from pathlib import Path

# Tables, numbers and line geometry
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

# The sample-point tools, so the segments are cut exactly as the points were
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Scripts" / "cv_pilot"))
import pilot_lib as L  # noqa: E402

# Inputs: the cleaned crime file, the published sample points and the road centrelines
DATASET = REPO / "Data" / "sps_crime_2026-06-01_2026-08-31"
CLEAN = DATASET / "02_cleaned" / "sps_offences_2026-06-01_2026-08-31_clean.csv"
POINTS = REPO / "Data" / "cv_pilot_2026-10" / "cbd" / "sample_points.csv"
ROADS = REPO / "Data" / "boundaries" / "osm_roads_downtown_context.geojson"
DEFAULT_OUT = DATASET / "03_segments"

# Placement distances (metres): to a segment of the named street, to the named streets at an intersection,
# and to any segment when the name finds nothing; then the share of records that defines a hot spot
NAMED_MAX_M = 100.0
INTERSECTION_MAX_M = 30.0
FALLBACK_MAX_M = 30.0
HOTSPOT_SHARE = 0.5

# SPS street abbreviations written out the way OpenStreetMap names streets
ABBREVIATIONS = {"ST": "STREET", "AVE": "AVENUE", "DR": "DRIVE", "CRES": "CRESCENT", "PL": "PLACE",
                 "RD": "ROAD", "BLVD": "BOULEVARD", "E": "EAST", "W": "WEST", "N": "NORTH", "S": "SOUTH"}

# Study categories and the two groups, in report order
CATEGORIES = ["break_and_enter", "theft_from_vehicle", "auto_theft", "mischief_vandalism", "street_robbery", "assault"]
GROUPS = ["property", "street_personal"]


def study_segments(points: pd.DataFrame) -> tuple[dict, L.LocalProjection]:
    """Rebuild the study segments as lines in metres, and check them against the published lengths.

    :param points: the published sample points
    :return: ({segment_id: LineString in metres}, the projection used)
    """
    # A flat x/y projection in metres centred on the points, so distances are plain metres
    proj = L.LocalProjection(points.lon.mean(), points.lat.mean())
    # The road classes and the box the sample points were made from (their run record)
    meta = json.loads((POINTS.parent / "run_meta.json").read_text())["points"]
    classes = set(meta["highway_filter"].split("|"))
    west, south, east, north = meta["bbox"]
    # Keep the same roads the points step fetched: those classes, touching that box
    ways = [w for w in L.load_roads_geojson(str(ROADS)) if w["highway"] in classes
            and any(west <= lon <= east and south <= lat <= north for lon, lat in w["coords"])]
    # Split them exactly as the sample points were split
    segs = L.split_at_intersections(ways)
    wanted = set(points.segment_id)
    lines = {s["segment_id"]: LineString([proj.to_xy(lon, lat) for lon, lat in s["coords"]])
             for s in segs if s["segment_id"] in wanted}
    # Every study segment must be found, with the same length the points were published with
    missing = wanted - set(lines)
    if missing:
        raise SystemExit(f"{len(missing)} study segments not rebuilt from {ROADS.name}: {sorted(missing)[:5]}")
    published = points.groupby("segment_id").segment_len_m.first()
    worst = max(abs(lines[k].length - v) for k, v in published.items())
    if worst > 1.0:
        raise SystemExit(f"rebuilt segment lengths differ from the published ones by up to {worst:.1f} m")
    return lines, proj


def street_key(name) -> str:
    """One spelling for a street name from either source, so SPS and OSM names can be compared.

    "21ST ST E" and "21st Street East" both become "21 STREET EAST"; "1 Avenue North" and
    "1st Avenue North" both become "1 AVENUE NORTH".

    :param name: a street name, or a missing value
    :return: the name in capitals, abbreviations written out and ordinal endings dropped ("" if missing)
    """
    # A missing name matches nothing
    if not isinstance(name, str):
        return ""
    # Each word: drop "ST/ND/RD/TH" after a number, then write out abbreviations
    words = []
    for w in name.upper().split():
        w = w[:-2] if w[:-2].isdigit() and w[-2:] in ("ST", "ND", "RD", "TH") else w
        words.append(ABBREVIATIONS.get(w, w))
    return " ".join(words)


def place(records: pd.DataFrame, lines: dict, names: dict, proj: L.LocalProjection) -> pd.DataFrame:
    """Link each record to its segment(s) by the placement rule.

    :param records: CBD study-category records
    :param lines: study segments as lines in metres
    :param names: study segment id -> street_key of its road name
    :param proj: the projection the lines use
    :return: one row per (record, segment) link, with the record's share; unplaced records get segment_id ""
    """
    # Segment ids, lines and street keys in a fixed order, so ties always break the same way
    ids = sorted(lines)
    geoms = [lines[k] for k in ids]
    keys = np.array([names[k] for k in ids])
    links = []
    # Each record in turn
    for r in records.itertuples():
        # Distance from the record's point to every study segment, and which segments are on its named street(s)
        pt = Point(proj.to_xy(r.longitude, r.latitude))
        dist = np.array([g.distance(pt) for g in geoms])
        on_street = keys == street_key(r.street)
        on_cross = keys == street_key(r.cross_street) if r.location_type == "intersection" else np.zeros_like(on_street)
        # Intersection: shared by the segments of both named streets that meet there
        meet = np.flatnonzero((on_street | on_cross) & (dist <= INTERSECTION_MAX_M))
        if r.location_type == "intersection" and len(meet) > 0:
            chosen, rule = list(meet), "intersection_split"
        # Hundred block: the nearest segment of the named street
        elif r.location_type != "intersection" and on_street.any() and dist[on_street].min() <= NAMED_MAX_M:
            named = np.flatnonzero(on_street)
            chosen, rule = [int(named[dist[named].argmin()])], "named_street"
        # Name found nothing close: the nearest segment, if it is close enough
        elif dist.min() <= FALLBACK_MAX_M:
            chosen, rule = [int(dist.argmin())], "nearest"
        # Too far from every study segment: kept, but unplaced
        else:
            links.append({"record_id": r.record_id, "segment_id": "", "share": 1.0,
                          "distance_m": round(float(dist.min()), 1), "rule": "unplaced"})
            continue
        # One link per chosen segment, sharing the record equally
        for i in chosen:
            links.append({"record_id": r.record_id, "segment_id": ids[i], "share": 1 / len(chosen),
                          "distance_m": round(float(dist[i]), 1), "rule": rule})
    return pd.DataFrame(links)


def concentration(counts: pd.Series) -> tuple[pd.Series, float]:
    """Which segments hold HOTSPOT_SHARE of the records, and what share of all segments that is.

    :param counts: records per segment (all study segments, zeros included)
    :return: (True for hot-spot segments, share of segments that are hot spots)
    """
    # Largest counts first; a segment is a hot spot while the running total is still short of half
    ordered = counts.sort_values(ascending=False, kind="mergesort")
    running = ordered.cumsum().shift(fill_value=0)
    hot = (running < HOTSPOT_SHARE * counts.sum()) & (ordered > 0)
    return hot.reindex(counts.index), float(hot.mean())


def main() -> int:
    """Place the records, count them per segment and save the tables.

    :return: exit code
    """
    # Output folder option
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output folder (default 03_segments/)")
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    # The published points, the study segments and the CBD study-category records
    points = pd.read_csv(POINTS)
    lines, proj = study_segments(points)
    crime = pd.read_csv(CLEAN)
    records = crime[crime.in_cbd & crime.category_decision.isin(["included", "conditional"])]
    # Each segment's street name in the shared spelling
    names = {k: street_key(v) for k, v in points.groupby("segment_id").road_name.first().items()}
    # Link records to segments, then attach each record's category and group
    links = place(records, lines, names, proj)
    links = links.merge(records[["record_id", "study_category", "crime_group", "location_type"]], on="record_id")
    placed = links[links.segment_id != ""]
    # One row per study segment, with its name, length and number of sample points
    seg = points.groupby("segment_id").agg(road_name=("road_name", "first"), highway=("highway", "first"),
                                           length_m=("segment_len_m", "first"), n_points=("point_id", "size"))
    # Records per segment for each category and each group, zeros where none
    for col, values in (("study_category", CATEGORIES), ("crime_group", GROUPS)):
        table = placed.pivot_table(index="segment_id", columns=col, values="share", aggfunc="sum")
        for v in values:
            seg[v] = table[v].reindex(seg.index).fillna(0.0).round(3) if v in table else 0.0
    seg["all_study_crime"] = seg[GROUPS].sum(axis=1).round(3)
    # Rates per 100 m of street, and the hot-spot flags for each group and for all study crime
    shares = {}
    for col in GROUPS + ["all_study_crime"]:
        seg[f"{col}_per_100m"] = (100 * seg[col] / seg.length_m).round(2)
        seg[f"hotspot_{col}"], shares[col] = concentration(seg[col])
    seg.reset_index().to_csv(out / "segment_crime_counts.csv", index=False)
    links.sort_values(["record_id", "segment_id"]).to_csv(out / "record_links.csv", index=False)
    # Totals and concentration figures for the report
    unplaced = links[links.rule == "unplaced"]
    summary = {
        "records": int(len(records)), "placed": int(records.record_id.isin(placed.record_id).sum()),
        "unplaced": int(len(unplaced)), "intersection_records_split": int(placed[placed.rule == "intersection_split"]
                                                                          .record_id.nunique()),
        "segments": int(len(seg)), "segments_with_any_record": int((seg.all_study_crime > 0).sum()),
        "records_by_group": {g: round(float(seg[g].sum()), 1) for g in GROUPS},
        "records_by_category": {c: round(float(seg[c].sum()), 1) for c in CATEGORIES},
        "hotspot_rule": f"segments holding the first {HOTSPOT_SHARE:.0%} of records, largest counts first",
        "hotspot_segments": {k: int(seg[f"hotspot_{k}"].sum()) for k in shares},
        "hotspot_share_of_segments": {k: round(v, 3) for k, v in shares.items()},
        "placed_by_rule": {k: int(v) for k, v in placed.groupby("rule").record_id.nunique().items()},
        "rule": {"named_street_max_m": NAMED_MAX_M, "intersection_max_m": INTERSECTION_MAX_M,
                 "fallback_nearest_max_m": FALLBACK_MAX_M}}
    (out / "hotspot_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[hotspots] {summary['placed']} of {summary['records']} CBD study-category records placed on "
          f"{summary['segments_with_any_record']} of {summary['segments']} segments; {summary['unplaced']} unplaced")
    print(f"[hotspots] half of all study crime lies on {summary['hotspot_segments']['all_study_crime']} segments "
          f"({shares['all_study_crime']:.0%} of segments)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
