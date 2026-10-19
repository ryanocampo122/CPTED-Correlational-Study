# Data ethics and handling

## Reddit

- Authors are replaced by salted HMAC-SHA-256 hashes (`COMPUTERVISION_SENTINEL_HASH_SALT`, kept private and reused so hashes
  stay comparable across collections). Deleted and removed content is excluded. Emails, phone numbers and street
  addresses are scrubbed from `cleaned_text`.
- Raw text (`body`, `full_text`) is still verbatim and searchable, so a comment can be traced to its author.
  **Do not quote Reddit text in anything that leaves the team.** Paraphrase, and confirm the approach with the REB.
  `03_extracted_comment_samples/` and `_local_audit_do_not_share/` exist for internal checking only;
  the latter is git-ignored and excluded from handoff zips.
- Reddit users are not the population of Saskatoon; describe results as "how safety is discussed on r/saskatoon".

## Describing places, not labelling people

The work plan commits to describing places rather than predicting crime or labelling communities (territorial
stigmatization: Wacquant 2007; Meade 2021; Schwarze 2023, in `Reference/Literature/`). In practice:

- Report recorded crime as recorded crime (reporting and enforcement shape it; Buil-Gil et al. 2022).
- Keep cues about **physical features** (lighting, maintenance, vacancy, frontage) apart from mentions of **groups of
  people**. The current `people` cue mixes them (issue 7) and must be split before H4.
- Maps of perceived danger and crime go out with their uncertainty and without ranking neighbourhoods by "danger".

## Imagery and map data

- Mapillary images: CC BY-SA 4.0. Credit "Mapillary contributors" on every figure that shows images; derived image
  products are share-alike. Faces and plates are blurred by Mapillary.
- OpenStreetMap data: ODbL. Credit "© OpenStreetMap contributors" on maps.
- Google Street View: not used. Its terms forbid bulk download and model use (Maps Platform ToS 3.2.3).

## Police data

- The SPS public map prohibits commercial use and disclaims accuracy and comparison over time.
- The June–August 2026 extract (`Data/sps_crime_2026-06-01_2026-08-31/`, received 17 Oct 2026) holds no names or
  exact addresses: locations are hundred-blocks or intersections. No terms of use are recorded yet; record SPS's terms
  here, and until then share only aggregated counts outside the team.

## Credentials and sharing

- All credentials live in `.env` at the repository root (`PRAW_CLIENT_ID`, `PRAW_CLIENT_SECRET`,
  `PRAW_USER_AGENT`, `COMPUTERVISION_SENTINEL_HASH_SALT`, `MAPILLARY_TOKEN`), with a copy in `.venv/keys.txt`.
  Since October 2026 `.env` is committed to the private GitHub repository, so everyone with access to
  the repository can read the keys and the hash salt. Never paste them into code, notebooks or messages.
- `Scripts/make_handoff.sh` builds a shareable zip without `.env`, `.git`, `.venv` and the private audit folders,
  and refuses to finish if any credential value appears inside the zip.
- The Reddit secret that was hard-coded in the August package must be rotated (issue 15).
