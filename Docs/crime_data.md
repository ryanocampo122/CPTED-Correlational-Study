# Recorded crime (Y1)

## Final categories (October task: done)

From the revised work plan, p. 4, with the matching category on the Saskatoon Police Service (SPS) public crime map.

| Category | Decision | SPS map category | Rationale (work plan) | Note for the data |
|---|---|---|---|---|
| Break and enter | Included | Break & enter | access control, target hardening, visibility of entry points | — |
| Theft from vehicle | Included | Theft from vehicle | sightlines, lighting, parking layout | — |
| Auto theft | Included | Auto theft | where cars are parked and how watched | — |
| Mischief / vandalism | Included | Mischief | maintenance and territoriality; visible in imagery | — |
| Street robbery | Included | Robbery | natural surveillance | SPS "Robbery" includes commercial robbery; premise type needed |
| Assault | Conditional | Assault | only if outdoor incidents can be separated | the public map shows no premise type |
| Fraud | Excluded | Fraud | no link to physical design | — |
| Homicide | Excluded | Homicide | too rare over three months; mostly interpersonal | — |
| Sexual assault | Excluded | Sexual assault | mostly indoors, by someone known | — |
| Drug offences | Excluded | (in "Other") | reflects enforcement, not environment | — |

**If counts are low:** group into *property crime* (break and enter, theft from vehicle, auto theft, mischief) and
*street-based personal crime* (robbery, outdoor assault).

These categories match the Hypotheses: H1 (opportunistic crime), H2 (mischief and property crime), H3
(vehicle-related crime and street robbery). The Reddit crime seed terms were aligned with them in October.

## What SPS data are available

- The **public crime map** (map.saskatoonpolice.ca) shows "mapped locations of reported crimes from selected
  violation types". Its disclaimer: *"The locations identified on the map are intended to indicate the general
  area in which the incident occurred and are not intended to identify the exact incident location"*; the data
  "should not [be relied on] for comparison purposes over time"; commercial use is prohibited (read 16 Oct 2026).
- Category names above are as listed on crimemaps.ca, which republishes the SPS map; confirm them against the
  SPS extract.
- SPS also publishes monthly and annual statistics as PDFs by patrol division (Central, East, North, West): far too
  coarse for street segments.

## What to check in the data

The crime data were obtained on 17 Oct 2026 and will be added to `Data/`. Check that the extract (1 June – 31 August 2026, the categories above) has:

1. occurrence date and time (and reported date),
2. violation / UCR code (to separate robbery types and assault levels),
3. **premise or location type** (street, parking lot, residence, commercial), needed for street robbery and outdoor assault,
4. **block-level location** (e.g. hundred-block address or coordinates snapped to the block centre),
5. founded/unfounded status.

Record any data-sharing terms in `Docs/data_ethics.md`.

## Validation for crime data

- Check how locations are generalized (offset, block centroid) and whether 50 m segments are finer than the location
  precision; if so, aggregate to block faces or a grid and say so.
- Recorded crime is shaped by reporting and enforcement (Buil-Gil et al. 2022): describe it as recorded crime, not
  crime.
