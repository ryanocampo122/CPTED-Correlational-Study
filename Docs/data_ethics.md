# Data ethics and handling

## Reddit

- Authors are replaced by salted HMAC-SHA-256 hashes (`CPTED_VISION_HASH_SALT`, kept private and reused so hashes
  stay comparable across collections). Deleted and removed content is excluded. Emails, phone numbers and street
  addresses are scrubbed from `cleaned_text`.
- Raw text (`body`, `full_text`) is still verbatim and searchable, so a comment can be traced to its author.
  **Do not quote Reddit text in anything that leaves the team.** Paraphrase, and confirm the approach with the REB.
  `03_extracted_comment_samples/` and `_local_audit_do_not_share/` exist for internal checking only;
  the latter is git-ignored and excluded from handoff zips.
- Verbatim Reddit text is in the git repository: the raw and cleaned files, `03_extracted_comment_samples/`, and
  the excerpts in `Scripts/reddit_analysis/manual_review/`. They are committed so the pipeline can be rebuilt from
  them, and the GitHub repository is private, open only to the research team. Handoff zips include them too.
- Reddit users are not the population of Saskatoon; describe results as "how safety is discussed on r/saskatoon".

## Describing places, not labelling people

The work plan commits to describing places rather than predicting crime or labelling communities (territorial
stigmatization: Wacquant 2007; Meade 2021; Schwarze 2023, in `Reference/Literature/`). In practice:

- Report recorded crime as recorded crime (reporting and enforcement shape it; Buil-Gil et al. 2022).
- Keep cues about **physical features** (lighting, maintenance, vacancy, frontage) apart from mentions of **groups of
  people**. The current `people` cue mixes them and must be split before H4 (`reddit_pipeline.md`, Limitations).
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

- **Since November 2026 credentials live outside the repository**, in
  `~/.config/cpted_vision/secrets.env` (`PRAW_CLIENT_ID`, `PRAW_CLIENT_SECRET`, `PRAW_USER_AGENT`,
  `CPTED_VISION_HASH_SALT`, `MAPILLARY_TOKEN`; `KEY=VALUE` lines). The folder is `chmod 700` and the file
  `chmod 600`, so only your user account can read it. Every script reads, in order: variables already set in the shell,
  the file named by `CPTED_VISION_ENV_FILE` (if set), that file, and, as a legacy fallback, a `.env`
  at the repository root (git-ignored; the flight marks it WARN). `.venv/keys.txt` is no longer read; delete it.
  `.env`, `*.env`, `secrets.*` and `keys.txt` are git-ignored. New team members get the keys through a password
  manager share, never by chat or email.
- Setting up on a machine:
  ```bash
  mkdir -p ~/.config/cpted_vision && chmod 700 ~/.config/cpted_vision
  $EDITOR ~/.config/cpted_vision/secrets.env && chmod 600 ~/.config/cpted_vision/secrets.env
  ```
- **History.** From October 2026 until the November move, `.env` was committed to the private GitHub repository.
  Removing it from the current files does not remove it from git history, so everyone with access to the repository
  can still read those values. The history is not rewritten (that would change every commit ID again). The keys were
  moved in November 2026, not replaced: the values in the private file are the same ones that are in git history.
  Never paste keys into code, notebooks or messages.
- **Replacing the keys (recommended, not yet done).** Making the copies in git history useless needs a new Reddit app
  secret (reddit.com/prefs/apps) and a new Mapillary token (mapillary.com/dashboard/developers), pasted into the
  private file by the key owner. The hash salt is kept: changing it changes every `author_hash`, so new collections
  could no longer be compared with June–August 2026, and its protection is limited anyway because the repository
  holds verbatim Reddit text.
- `Scripts/make_handoff.sh` builds a shareable zip without `.env`, `.git`, `.venv` and the private audit folders,
  and refuses to finish if any credential value appears inside the zip (or if it cannot find the keys to check).
