# SPS criminal offences, 1 June – 31 August 2026 (study period)

Saskatoon Police Service (SPS) criminal-offence records for the revised work plan's study period. This is the **current** recorded-crime dataset (Y1). Category decisions, what the extract does and
does not contain, and its caveats: `Docs/crime_data.md`.

| | |
|---|---|
| Records | 9,650 offences, reported 1 Jun 00:00 – 31 Aug 23:59 2026 (Saskatoon time); 7,701 distinct incidents |
| Study categories | 2,982 records: break and enter 521, theft from vehicle 635, auto theft 215, mischief/vandalism 774, street robbery 105 (included); assault 732 (conditional) |
| CBD | 1,848 records inside the CBD polygon; 257 of them in the study categories |
| Location | hundred-block (8,738) or intersection (912), each with a point; not exact addresses |
| Not in the extract | occurrence date, UCR code, premise type, founded/unfounded status, file number |

## Folders

| Folder | Contents | Made by |
|---|---|---|
| `01_raw_collection/` | `sps_criminal_offences_june_1_2026_to_august_31_2026.csv`, exactly as received (read-only; SHA-256 `912c3b25bee66d40e5a0cb18c31b7c5d07a61cb2c4100ef7893ce1c743f21df1`) | SPS; **never edit** |
| `02_cleaned/` | the cleaned file, counts and a cleaning report (below) | `Scripts/crime_data/clean_sps_crime.py` |
| `03_segments/` | the 257 CBD study-category records placed on the 218 study street segments: counts per segment by category and group, per 100 m, hot-spot flags (`segment_crime_counts.csv`); which segment(s) each record went to (`record_links.csv`); totals (`hotspot_summary.json`) | `Scripts/crime_data/hotspots.py` (November 2026) |

Regenerate `02_cleaned/` with `.venv/bin/python Scripts/crime_data/clean_sps_crime.py`. The script checks the raw
file's SHA-256 first and stops if it has changed; a second run reproduces every output byte for byte.

## Raw file (`01_raw_collection/`)

| Column | Content |
|---|---|
| `Reported Date` | when the offence was reported, `YYYY-MM-DD HH:MM:SS`, Saskatoon local time |
| `Type` | SPS offence type (28 types) |
| `Location` | `<n> BLOCK <street>` or `<street> & <street>` |
| `Neighbourhood` | SPS neighbourhood name (blank for 39 records) |
| `Latitude`, `Longitude` | the point SPS gives for the block or intersection (WGS84) |

## Cleaned files (`02_cleaned/`)

`sps_offences_2026-06-01_2026-08-31_clean.csv`: one row per raw row, in the raw order. Nothing is dropped or
changed; these columns are added or derived:

| Column | Meaning |
|---|---|
| `record_id` | row number in the raw file (1–9,650) |
| `reported_at` | reported date-time with offset, e.g. `2026-08-31T23:59:00-06:00` |
| `reported_date`, `reported_time`, `month`, `weekday`, `hour` | parts of the reported time (local) |
| `in_window` | reported 1 June – 31 August 2026 (all rows are) |
| `sps_type` | the raw `Type` |
| `study_category` | `break_and_enter`, `theft_from_vehicle`, `auto_theft`, `mischief_vandalism`, `street_robbery`, `assault`; the excluded types are labelled `fraud`, `homicide`, `sexual_assault`, `drug_offences`; blank for the rest |
| `category_decision` | `included`, `conditional` (assault), `excluded`, or `not_selected` (types outside the work plan's list) |
| `crime_group` | `property` (break and enter, theft from vehicle, auto theft, mischief) or `street_personal` (robbery, assault), for the "if counts are low" grouping |
| `location`, `location_type` | the raw location; `block` or `intersection` |
| `block_start`, `street`, `cross_street` | for blocks: the hundred number and street; for intersections: the two streets |
| `neighbourhood`, `neighbourhood_missing` | SPS neighbourhood (blank kept) and a flag for the 39 blanks |
| `latitude`, `longitude` | as numbers |
| `in_cbd` | the point lies inside `Data/boundaries/central_business_district_osm.geojson` (interim OSM boundary) |
| `fixed_address_midnight` | reported at exactly 00:00 at an address with 20 or more such records (938 rows, all "Other Criminal Code", at 3 addresses); likely records filed at a fixed address, not street incidents |
| `identical_rows`, `identical_rank` | how many raw rows are exactly identical to this one, and this row's position among them (1,075 rows have rank > 1); kept, since one incident can carry several counts |
| `incident_id` | one ID per reported time and location (7,701) |

- `category_counts.csv`: for each study category, the SPS types it covers, offence records and distinct incidents,
  city-wide and inside the CBD.
- `type_counts.csv`: every SPS type with its category, decision, records, incidents, CBD records and
  fixed-address midnight records.
- `cleaning_report.json`: raw file, hash, date range and every count above.