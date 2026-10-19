#!/usr/bin/env python3
"""
clean_sps_crime.py
==================
ComputerVision_Sentinel | Clean the Saskatoon Police Service (SPS) criminal-offence extract (Y1)

Reads the raw extract in Data/sps_crime_2026-06-01_2026-08-31/01_raw_collection/ (never edited; its SHA-256 is
checked first) and writes 02_cleaned/:

  sps_offences_2026-06-01_2026-08-31_clean.csv   one row per raw row: original fields kept, study columns added
  type_counts.csv                                every SPS offence type, its study category and its counts
  category_counts.csv                            offence rows and distinct incidents per study category
  cleaning_report.json                           input hash, row counts and every flag count

Nothing is dropped. Rows outside the study categories, and rows that look administrative, are kept and labelled,
so every count traces back to a raw row. The category decisions follow Docs/crime_data.md (work plan p. 4).
An SPS type the script does not know stops the run, so a new type is reviewed before it is counted.

USAGE (repository root):  .venv/bin/python Scripts/crime_data/clean_sps_crime.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape
from shapely.prepared import prep

REPO = Path(__file__).resolve().parents[2]
DATASET = REPO / "Data" / "sps_crime_2026-06-01_2026-08-31"
RAW = DATASET / "01_raw_collection" / "sps_criminal_offences_june_1_2026_to_august_31_2026.csv"
RAW_SHA256 = "912c3b25bee66d40e5a0cb18c31b7c5d07a61cb2c4100ef7893ce1c743f21df1"
CBD = REPO / "Data" / "boundaries" / "central_business_district_osm.geojson"
OUT = DATASET / "02_cleaned"
CLEAN_NAME = "sps_offences_2026-06-01_2026-08-31_clean.csv"

LOCAL_TZ = "America/Regina"                      # Saskatoon: UTC-6 all year
WINDOW = ("2026-06-01", "2026-08-31")            # study period, local dates, inclusive
MIDNIGHT_CLUSTER_MIN = 20                        # an address with this many 00:00 records is a fixed-address cluster

# SPS "Type" -> (study category, decision, group). Decisions and groups: Docs/crime_data.md.
STUDY_TYPES = {
    "Break and Enter - Residential":     ("break_and_enter", "included", "property"),
    "Break and Enter - Non Residential": ("break_and_enter", "included", "property"),
    "Theft From Vehicle":                ("theft_from_vehicle", "included", "property"),
    "Theft of Motor Vehicle":            ("auto_theft", "included", "property"),
    "Mischief/Willful Damage":           ("mischief_vandalism", "included", "property"),
    "Graffiti":                          ("mischief_vandalism", "included", "property"),
    "Robbery":                           ("street_robbery", "included", "street_personal"),
    "Assault":                           ("assault", "conditional", "street_personal"),
    "Fraud":                             ("fraud", "excluded", ""),
    "Homicide":                          ("homicide", "excluded", ""),
    "Sexual Violation":                  ("sexual_assault", "excluded", ""),
    "Controlled Drug and Substance Act": ("drug_offences", "excluded", ""),
}
OTHER_TYPES = {                                  # in the extract, not among the work plan's categories
    "Other Provincial", "Other Criminal Code", "Other Theft Under $5000", "Provincial Traffic Safety Act",
    "Weapons Possession Cont to Order/Conceal", "Criminal Code Traffic Violation", "Uttering Threats",
    "Possession of Stolen Property", "Theft Over $5000", "Criminal Harassment (Stalking)", "Arson",
    "Other Crimes Against the Person", "Kidnapping/Hostage Taking/Abduction", "Firearms Related",
    "Alcohol Gaming Regulations Act", "Commodification of Sex Activity",
}
CATEGORY_ORDER = ["break_and_enter", "theft_from_vehicle", "auto_theft", "mischief_vandalism",
                  "street_robbery", "assault"]

BLOCK_RE = re.compile(r"^(\d+) BLOCK (.+)$")


def sha256(path: Path) -> str:
    """Hex SHA-256 of a file, read in 1 MB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_location(loc: str) -> tuple[str, object, str, str]:
    """'200 BLOCK 23RD ST E' -> ('block', 200, '23RD ST E', ''); 'A & B' -> ('intersection', None, 'A', 'B')."""
    m = BLOCK_RE.match(loc)
    if m:
        return "block", int(m.group(1)), m.group(2), ""
    if " & " in loc:
        a, b = loc.split(" & ", 1)
        return "intersection", None, a, b
    return "other", None, loc, ""


def clean(raw: Path, out: Path, check_hash: bool = True) -> dict:
    """Write the 02_cleaned/ outputs and return the cleaning report. Exits if the raw
    file's hash changed (check_hash), its columns differ, or an SPS type is unmapped."""
    digest = sha256(raw)
    if check_hash and digest != RAW_SHA256:
        raise SystemExit(f"{raw.name} has changed (SHA-256 {digest}); raw files are never edited. "
                         "If SPS sent a new extract, give it its own dataset folder.")
    d = pd.read_csv(raw, dtype=str, keep_default_na=False)
    expected = ["Reported Date", "Type", "Location", "Neighbourhood", "Latitude", "Longitude"]
    if list(d.columns) != expected:
        raise SystemExit(f"Unexpected columns {list(d.columns)}; expected {expected}")

    unknown = sorted(set(d.Type) - set(STUDY_TYPES) - OTHER_TYPES)
    if unknown:
        raise SystemExit(f"Unmapped SPS types {unknown}: add them to STUDY_TYPES or OTHER_TYPES "
                         "and to Docs/crime_data.md before counting.")

    c = pd.DataFrame({"record_id": range(1, len(d) + 1)})
    when = pd.to_datetime(d["Reported Date"], format="%Y-%m-%d %H:%M:%S").dt.tz_localize(LOCAL_TZ)
    c["reported_at"] = when.map(lambda t: t.isoformat())
    c["reported_date"] = when.dt.strftime("%Y-%m-%d")
    c["reported_time"] = when.dt.strftime("%H:%M")
    c["month"] = when.dt.strftime("%Y-%m")
    c["weekday"] = when.dt.day_name()
    c["hour"] = when.dt.hour
    c["in_window"] = c.reported_date.between(*WINDOW)

    c["sps_type"] = d["Type"]
    mapped = d["Type"].map(lambda t: STUDY_TYPES.get(t, ("", "not_selected", "")))
    c["study_category"] = mapped.str[0]
    c["category_decision"] = mapped.str[1]
    c["crime_group"] = mapped.str[2]

    c["location"] = d["Location"]
    parts = d["Location"].map(parse_location)
    c["location_type"] = parts.str[0]
    c["block_start"] = parts.str[1].astype("Int64")
    c["street"] = parts.str[2]
    c["cross_street"] = parts.str[3]
    c["neighbourhood"] = d["Neighbourhood"].str.strip()
    c["neighbourhood_missing"] = c.neighbourhood.eq("")
    c["latitude"] = pd.to_numeric(d["Latitude"])
    c["longitude"] = pd.to_numeric(d["Longitude"])

    cbd = prep(shape(json.loads(CBD.read_text())["features"][0]["geometry"]))
    c["in_cbd"] = [cbd.contains(Point(x, y)) for x, y in zip(c.longitude, c.latitude)]

    # Fixed-address midnight clusters: many records at exactly 00:00 at one address.
    midnight = c.reported_time.eq("00:00")
    per_address = c[midnight].location.value_counts()
    cluster_addresses = sorted(per_address[per_address >= MIDNIGHT_CLUSTER_MIN].index)
    c["fixed_address_midnight"] = midnight & c.location.isin(cluster_addresses)

    # Identical raw rows (same time, type and location): kept, since one incident can hold several counts.
    raw_key = d[expected].astype(str).agg("|".join, axis=1)
    c["identical_rows"] = raw_key.map(raw_key.value_counts())
    c["identical_rank"] = raw_key.groupby(raw_key).cumcount() + 1

    # Incident: every offence SPS reported at the same time and location.
    inc = c[["reported_at", "location"]].drop_duplicates().sort_values(["reported_at", "location"])
    inc["incident_id"] = [f"I{i:05d}" for i in range(1, len(inc) + 1)]
    c = c.merge(inc, on=["reported_at", "location"], how="left").sort_values("record_id")

    out.mkdir(parents=True, exist_ok=True)
    c.to_csv(out / CLEAN_NAME, index=False)

    types = (c.groupby("sps_type").agg(offence_rows=("record_id", "size"), incidents=("incident_id", "nunique"),
                                        offence_rows_cbd=("in_cbd", "sum"),
                                        fixed_address_midnight=("fixed_address_midnight", "sum"))
             .reset_index())
    types["study_category"] = types.sps_type.map(lambda t: STUDY_TYPES.get(t, ("",))[0])
    types["category_decision"] = types.sps_type.map(lambda t: STUDY_TYPES.get(t, ("", "not_selected"))[1])
    types = types[["sps_type", "study_category", "category_decision", "offence_rows", "incidents",
                   "offence_rows_cbd", "fixed_address_midnight"]].sort_values(
        ["category_decision", "offence_rows"], ascending=[True, False])
    types.to_csv(out / "type_counts.csv", index=False)

    rows = []
    for cat in CATEGORY_ORDER:
        s = c[c.study_category == cat]
        rows.append({"study_category": cat, "category_decision": s.category_decision.iat[0],
                     "crime_group": s.crime_group.iat[0], "sps_types": "; ".join(sorted(s.sps_type.unique())),
                     "offence_rows": len(s), "incidents": s.incident_id.nunique(),
                     "offence_rows_cbd": int(s.in_cbd.sum()), "incidents_cbd": s[s.in_cbd].incident_id.nunique()})
    pd.DataFrame(rows).to_csv(out / "category_counts.csv", index=False)

    sps_cbd = c.neighbourhood.eq("Central Business District")
    report = {
        "script": "Scripts/crime_data/clean_sps_crime.py",
        "raw_file": str(raw.relative_to(REPO)),
        "raw_sha256": digest,
        "raw_rows": len(d),
        "reported_at_min": c.reported_at.min(), "reported_at_max": c.reported_at.max(),
        "rows_outside_window": int((~c.in_window).sum()),
        "rows_by_decision": c.category_decision.value_counts().to_dict(),
        "rows_by_study_category": {k: int((c.study_category == k).sum()) for k in CATEGORY_ORDER},
        "incidents": int(c.incident_id.nunique()),
        "location_type": c.location_type.value_counts().to_dict(),
        "neighbourhood_missing": int(c.neighbourhood_missing.sum()),
        "in_cbd_polygon": int(c.in_cbd.sum()),
        "sps_neighbourhood_cbd": int(sps_cbd.sum()),
        "cbd_polygon_vs_sps_neighbourhood_disagree": int((sps_cbd != c.in_cbd).sum()),
        "rows_in_identical_groups": int((c.identical_rows > 1).sum()),
        "identical_extra_rows": int((c.identical_rank > 1).sum()),
        "midnight_rows": int(midnight.sum()),
        "fixed_address_midnight_rows": int(c.fixed_address_midnight.sum()),
        "fixed_address_midnight_addresses": {a: int(per_address[a]) for a in cluster_addresses},
        "fixed_address_midnight_by_type": c[c.fixed_address_midnight].sps_type.value_counts().to_dict(),
        "fixed_address_midnight_in_cbd": int((c.fixed_address_midnight & c.in_cbd).sum()),
        "fields_absent_from_extract": ["occurrence date/time (only Reported Date)", "UCR / violation code",
                                       "premise or location type", "founded/unfounded status",
                                       "incident or file number"],
    }
    (out / "cleaning_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--raw", type=Path, default=RAW, help="raw SPS extract (default: the study-period file)")
    ap.add_argument("--out", type=Path, default=OUT, help="output folder (default: the dataset's 02_cleaned/)")
    ap.add_argument("--no-hash-check", action="store_true", help="skip the SHA-256 check (for a different extract)")
    a = ap.parse_args()
    r = clean(a.raw, a.out, check_hash=not a.no_hash_check)
    print(f"{r['raw_rows']} rows, {r['incidents']} incidents; by decision {r['rows_by_decision']}")
    print(f"study categories {r['rows_by_study_category']}")
    print(f"flags: {r['fixed_address_midnight_rows']} fixed-address midnight rows, "
          f"{r['identical_extra_rows']} extra identical rows, {r['neighbourhood_missing']} missing neighbourhoods")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
