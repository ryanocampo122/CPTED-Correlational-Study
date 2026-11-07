# Crime data: clean the SPS extract

| Script | Reads | Writes |
|---|---|---|
| `clean_sps_crime.py` | `Data/sps_crime_2026-06-01_2026-08-31/01_raw_collection/` (raw SPS extract, never edited), `Data/boundaries/central_business_district_osm.geojson` | `Data/sps_crime_2026-06-01_2026-08-31/02_cleaned/`: cleaned rows, `category_counts.csv`, `type_counts.csv`, `cleaning_report.json` |

```bash
.venv/bin/python Scripts/crime_data/clean_sps_crime.py
```

What it does, in order:

1. Checks the raw file's SHA-256 and columns; stops if either has changed.

2. Stops if the extract has an SPS type it does not know, so a new type is mapped (here and in `Docs/crime_data.md`)
   before it is counted.

3. Maps each SPS type to a study category and decision (`STUDY_TYPES`, from `Docs/crime_data.md`); the rest are
   `not_selected`.

4. Adds time parts (Saskatoon time), parses block and intersection locations, flags missing neighbourhoods, and
   marks points inside the CBD polygon.

5. Flags fixed-address midnight clusters and identical rows, and gives each reported time and location an
   incident ID. Nothing is dropped.

Output columns are documented in `Data/sps_crime_2026-06-01_2026-08-31/README.md`. Re-running reproduces every output
byte for byte. For a later extract, give it its own dataset folder and pass `--raw`, `--out` and `--no-hash-check`
(then record its hash in the script).

## Crime per street segment and hot spots (November 2026)

| Script | Reads | Writes |
|---|---|---|
| `hotspots.py` | `02_cleaned/` (CBD study-category records), `Data/cv_pilot_2026-10/cbd/sample_points.csv` and `run_meta.json`, `Data/boundaries/osm_roads_downtown_context.geojson` | `Data/sps_crime_2026-06-01_2026-08-31/03_segments/` |

```bash
.venv/bin/python Scripts/crime_data/hotspots.py
.venv/bin/python Scripts/crime_data/tests/test_hotspots.py      # offline tests
```

1. Rebuilds the 218 study segments with the same road classes, box and splitting code as the sample points, and
   stops if any segment's length differs from the published one by more than 1 m.

2. Places each record by street name first, because SPS puts a hundred-block record 30–85 m from the road centreline:
   a block record goes to the nearest segment of the street it names within 100 m; an intersection record is split
   equally between the segments of its two streets within 30 m; otherwise the nearest segment within 30 m, else the
   record is counted as unplaced (2 records, on a stretch of Spadina Crescent East with no sample point).

3. Counts records per segment by category and group, and per 100 m. Hot spots are the segments that together hold
   half of a group's records (largest counts first). Maps: `Scripts/reporting/make_figures_november.py` (fig09, fig10).
