# Recorded crime (Y1)

## Final categories (October task: done)

From the revised work plan, p. 4, with the matching Saskatoon Police Service (SPS) offence type as it is named in the
June–August 2026 extract, and the number of offence records (city-wide / inside the CBD polygon).

| Category | Decision | SPS type in the extract | Records (city / CBD) | Rationale (work plan) | Note for the data |
|---|---|---|---|---|---|
| Break and enter | Included | Break and Enter - Residential; Break and Enter - Non Residential | 521 / 10 | access control, target hardening, visibility of entry points | — |
| Theft from vehicle | Included | Theft From Vehicle | 635 / 72 | sightlines, lighting, parking layout | — |
| Auto theft | Included | Theft of Motor Vehicle | 215 / 5 | where cars are parked and how watched | — |
| Mischief / vandalism | Included | Mischief/Willful Damage; Graffiti | 774 / 76 | maintenance and territoriality; visible in imagery | Graffiti is its own SPS type (44) and is counted here |
| Street robbery | Included | Robbery | 105 / 16 | natural surveillance | includes commercial robbery; the extract has no premise type to separate it |
| Assault | Conditional | Assault | 732 / 78 | only if outdoor incidents can be separated | the extract has no premise type, so outdoor assaults cannot be separated yet |
| Fraud | Excluded | Fraud | 523 | no link to physical design | — |
| Homicide | Excluded | Homicide | 2 | too rare over three months; mostly interpersonal | — |
| Sexual assault | Excluded | Sexual Violation | 75 | mostly indoors, by someone known | — |
| Drug offences | Excluded | Controlled Drug and Substance Act | 86 | reflects enforcement, not environment | — |

The other 16 SPS types in the extract (5,982 records, for example "Other Provincial", "Other Criminal Code",
"Other Theft Under $5000", "Weapons Possession", "Uttering Threats", "Arson") are not among the work plan's categories;
they stay in the cleaned file, labelled `not_selected`. Full list with counts:
`Data/sps_crime_2026-06-01_2026-08-31/02_cleaned/type_counts.csv`.

**If counts are low:** group into *property crime* (break and enter, theft from vehicle, auto theft, mischief) and
*street-based personal crime* (robbery, outdoor assault).

These categories match the Hypotheses: H1 (opportunistic crime), H2 (mischief and property crime), H3
(vehicle-related crime and street robbery). The Reddit crime seed terms were aligned with them in October.

## What SPS data are available

- The **public crime map** (map.saskatoonpolice.ca) shows "mapped locations of reported crimes from selected
  violation types". Its disclaimer: *"The locations identified on the map are intended to indicate the general
  area in which the incident occurred and are not intended to identify the exact incident location"*; the data
  "should not [be relied on] for comparison purposes over time"; commercial use is prohibited (read 16 Oct 2026).
- The category names in the table above are the type names in the SPS extract (they replace the crimemaps.ca names
  used before the data arrived).
- SPS also publishes monthly and annual statistics as PDFs by patrol division (Central, East, North, West): far too
  coarse for street segments.

## `Data/crime/` is not the SPS data

`Data/crime/` holds Statistics Canada police-reported crime collected for the related Sentinel climate–crime research,
not the SPS extract for this study, which is in `Data/sps_crime_2026-06-01_2026-08-31/` (checked 17 Oct 2026):

- `<city>/Actual_Incidents_*.csv`: "Actual incidents" for 314 detailed violations, one count per year, 2010–2024, for
  Saskatoon, Regina, Edmonton and Winnipeg (Statistics Canada geography codes 47725, 47705, 48835, 46602). 539 of the
  4,668 values per city are not available (status "..").
- `crime_metrics/`: each city's yearly "Total, all violations" and its year-on-year change; both match the source
  files exactly.
- The same four incident files are copied, unchanged, in `Data/reddit_2009_2025/`.

There are no dates within the year, no locations and no premise type, so these files cannot give counts per street
segment or for June–August 2026. They do include the matching violation types (breaking and entering, theft of and
from motor vehicles, mischief, robbery, assault levels 1–3), so at most they give city-wide context, such as
Saskatoon's yearly trend for the selected categories.

## The SPS extract, June–August 2026

Obtained 17 Oct 2026 and kept unchanged in `Data/sps_crime_2026-06-01_2026-08-31/01_raw_collection/`;
`Scripts/crime_data/clean_sps_crime.py` writes the cleaned files to `02_cleaned/` (dataset README there).

- **9,650 offence records**, reported 1 June 00:00 to 31 August 23:59 2026 (Saskatoon time), none outside the window;
  7,701 distinct incidents (same reported time and location). Six fields: reported date, type, location,
  neighbourhood, latitude, longitude.
- **Study categories:** 2,982 records, 2,250 included and 732 conditional (assault): 1,010 in June, 1,020 in July,
  952 in August.
- **CBD:** 1,848 records fall in the CBD polygon. Of the study categories, 163 are property crime and 94 street-based
  personal crime (robbery 16, assault 78) over the three months, so the grouping rule above is likely to be needed.

What the extract has, against the checklist set before it arrived:

| Needed | In the extract? | Consequence |
|---|---|---|
| 1. Occurrence date and time | **No**: only the reported date and time | time-of-day and day-of-week describe when crime was reported, not when it happened |
| 2. Violation / UCR code | **No**: SPS type names only | robbery types and assault levels cannot be separated |
| 3. Premise or location type | **No** | street robbery includes commercial robbery; assault stays *conditional* (outdoor incidents cannot be separated). Ask SPS for premise type, or report robbery and assault with this caveat |
| 4. Block-level location | **Yes**: hundred-block (8,738) or intersection (912), with a point for each; 2,625 distinct points | precision is the block or intersection, not the address (see Validation) |
| 5. Founded / unfounded status | **No** | treat every record as reported, not confirmed |

Two patterns are flagged in the cleaned file, not removed:

- **Fixed-address midnight records** (`fixed_address_midnight`, 938 records): every one is "Other Criminal Code",
  reported at exactly 00:00 at one of three addresses (200 block 19th St E: 673; 10 block 25th St E: 136; 100 block
  3rd Ave N: 129), 802 of them inside the CBD. They look like records filed at a fixed address rather than street
  incidents (to confirm with SPS). None are in the study categories, but they would inflate any "all crime" count for
  the CBD, so leave them out of such counts.
- **Identical rows** (`identical_rows`, `identical_rank`): 1,075 records repeat another record exactly (same time,
  type and location), 138 of them in the study categories. An incident can carry several counts of the same offence,
  so they are kept; `category_counts.csv` gives both offence records and distinct incidents.

39 records have no neighbourhood (`neighbourhood_missing`); every record has coordinates, and `in_cbd` comes from the
CBD polygon, which agrees with SPS's own neighbourhood for 9,614 of 9,650 records.

Record any data-sharing terms in `Docs/data_ethics.md`.

## Validation for crime data

- Locations are generalized to the hundred-block or intersection: 9,650 records sit on 2,625 points, and 199
  location names map to more than one point. Points 50 m apart are finer than this, so crime must be counted per block
  face or street segment (or a grid), not per sample point; say so in the methods.
- Recorded crime is shaped by reporting and enforcement (Buil-Gil et al. 2022): describe it as recorded crime, not
  crime.
