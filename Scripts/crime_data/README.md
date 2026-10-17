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
