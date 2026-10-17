"""
common.py
=========
UrbanSentinel-Prairie | Shared paths, vocabularies and matchers

Every analysis script (and, from October 2026, the collection scraper) imports
its tagging vocabulary and matching logic from here, so there is exactly one
definition of each. Before this module existed the neighbourhood pattern list
was copied by hand into four scripts.

CONTENTS
--------
  Paths            raw_dir(), out_dir(), MANUAL_REVIEW_DIR
  Neighbourhoods   NEIGHBOURHOODS_ORIGINAL (the 21 categories in the June
                   collection), NEIGHBOURHOODS (= original + Sutherland)
  Matchers         substring_match()   - reproduces the ORIGINAL scraper logic
                   bounded_match()     - word-boundary match (August fix)
                   neighbourhood_tags()- word-boundary + other-city exclusions
  Env cues         ENV_CUES_ORIGINAL   - the scraper's original vocabulary
                   ENV_CUES            - corrected (October 2026) definitions
                   cue_hits()          - corrected cue matcher
  Sentiment        vader_adjusted()    - VADER with the seed-term lexicon fix
  Time             add_local_time()    - Saskatoon local-time fields
  Statistics       cluster_bootstrap_ci(), wilson_ci()

WHY THE CUE DEFINITIONS CHANGED (October 2026)
----------------------------------------------
The scraper tagged environmental cues with plain substring containment, the same
bug that inflated "river" via "driver". Short patterns matched inside unrelated
words: "lit" in "little"/"literally", "ice" in "police"/"nice"/"price",
"rain" in "train", "late" in "plate"/"related". 05_audits/env_cue_tagging_audit.csv
documents the scale. The corrected definitions keep the original vocabulary,
match whole words only (with ordinary inflections such as "lights", "darker",
"homelessness"), and strip a short, explicit list of phrases where the word is
not used in its environmental sense ("red light", "headlights", "light rail",
"let alone", "ice cream", "too late"). Every exclusion is listed below so it can
be reviewed or reverted.

PATH RESOLUTION
---------------
Each Reddit dataset is a folder Data/<dataset>/ whose 01_raw_collection/ holds
one saskatoon_safety_posts_<stamp>.csv and one ..._comments_<stamp>.csv.
Raw data: $URBANSENTINEL_RAW_DIR, else Data/reddit_2025-06-11_2026-06-11/01_raw_collection.
Outputs: $URBANSENTINEL_OUT_DIR, else ../output. run_all.sh sets both.

TWO COLLECTION VERSIONS
-----------------------
  2026-06  June 2026 run (initial_sraper.py): raw loc_*/env_* columns are the
           original SUBSTRING tags; all comments are analysed.
  2026-10  October 2026 run (reddit_scraper.py): raw loc_*/env_* columns are
           already whole-word tags from this file; comments posted after the
           window closed are flagged (comment_in_window) and left out of the
           analysis tables (analysis_comments()).
is_substring_collection() tells the scripts which one they are reading.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = SCRIPTS_DIR.parent
REPO_DIR = ANALYSIS_DIR.parent.parent
DATA_DIR = REPO_DIR / "Data"
MANUAL_REVIEW_DIR = ANALYSIS_DIR / "manual_review"

# Each Reddit dataset lives in Data/<dataset>/, with the scraper output in
# 01_raw_collection/ and this pipeline's outputs beside it.
DEFAULT_DATASET = "reddit_2025-06-11_2026-06-11"
# The June 2026 collection's August-2026 tables, kept as sent, used by
# 08_verify_outputs.py to show the shared matcher reproduces them.
AUGUST_TABLES_DIR = (REPO_DIR / "Deliverables" / "2026-08_august_report" / "data_pkg_august"
                     / "02_derived_analysis")


def _raw_files(d: Path, kind: str) -> list[Path]:
    return sorted(Path(d).glob(f"saskatoon_safety_{kind}_*.csv"))


def raw_dir() -> Path:
    """Folder holding one saskatoon_safety_posts_*.csv and one ..._comments_*.csv:
    $URBANSENTINEL_RAW_DIR, else the default dataset's 01_raw_collection."""
    env = os.getenv("URBANSENTINEL_RAW_DIR")
    candidates = [Path(env)] if env else []
    candidates += [DATA_DIR / DEFAULT_DATASET / "01_raw_collection"]
    for c in candidates:
        if len(_raw_files(c, "posts")) == 1 and len(_raw_files(c, "comments")) == 1:
            return c.resolve()
    raise FileNotFoundError(
        "No raw collection found (need exactly one saskatoon_safety_posts_*.csv and one "
        "..._comments_*.csv). Set URBANSENTINEL_RAW_DIR. Looked in: "
        + ", ".join(str(c) for c in candidates)
    )


def raw_file(kind: str) -> Path:
    return _raw_files(raw_dir(), kind)[0]


def raw_stamp() -> str:
    """Date stamp of the collection files, e.g. '20260611'."""
    return raw_file("posts").stem.rsplit("_", 1)[-1]


def raw_metadata() -> dict:
    files = sorted(raw_dir().glob("saskatoon_safety_metadata_*.json"))
    return json.loads(files[0].read_text()) if files else {}


def collection_window_label() -> str:
    """'Jun 2025 - Jun 2026' style label for chart subtitles."""
    m = raw_metadata()
    if "window_local" in m:
        s, e = (pd.Timestamp(x) for x in m["window_local"])
    elif "window_start" in m:
        s, e = pd.Timestamp(m["window_start"]), pd.Timestamp(m["window_end"])
    else:
        return ""
    return f"{s:%b %Y} - {e:%b %Y}"


def collection_version() -> str:
    """'2026-06' for the June 2026 run (original substring tagging); later runs
    record scraper_version in their metadata (whole-word tagging)."""
    return raw_metadata().get("scraper_version", "2026-06")


def is_substring_collection() -> bool:
    """True for the June 2026 run, whose stored loc_*/env_* tags are substring matches."""
    return collection_version() == "2026-06"


def dataset_name() -> str:
    """'reddit_2026-06-01_2026-08-31' for Data/reddit_2026-06-01_2026-08-31/01_raw_collection."""
    return raw_dir().parent.name


def out_dir(*parts: str) -> Path:
    """Output folder (created on demand). out_dir("02_derived_analysis")."""
    base = Path(os.getenv("URBANSENTINEL_OUT_DIR", ANALYSIS_DIR / "output"))
    p = base.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def cleaned_file(kind: str) -> Path:
    return out_dir("04_cleaned_datasets") / f"saskatoon_safety_{kind}_{raw_stamp()}_CLEANED_v2.csv"


def load_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    posts = pd.read_csv(raw_file("posts"), low_memory=False)
    comments = pd.read_csv(raw_file("comments"), low_memory=False)
    return posts, comments


def analysis_comments(comments: pd.DataFrame) -> pd.DataFrame:
    """Comments used in analysis tables: all of them, or only those posted
    inside the collection window when the scraper recorded that."""
    if "comment_in_window" in comments.columns:
        return comments[comments["comment_in_window"].astype(bool)]
    return comments


# ---------------------------------------------------------------------------
# Neighbourhood vocabulary
# ---------------------------------------------------------------------------

# Verbatim from initial_sraper.py as run on 2026-06-11 (SASKATOON_NEIGHBOURHOODS).
NEIGHBOURHOODS_ORIGINAL: dict[str, list[str]] = {
    "Pleasant Hill":       ["pleasant hill"],
    "Riversdale":          ["riversdale"],
    "Meadowgreen":         ["meadowgreen"],
    "Westmount":           ["westmount"],
    "Mount Royal":         ["mount royal"],
    "King George":         ["king george"],
    "Caswell Hill":        ["caswell hill", "caswell"],
    "Mayfair":             ["mayfair"],
    "Downtown / CBD":      ["downtown", "cbd", "central business district",
                            "20th street", "20th st", "23rd street", "23rd st"],
    "Broadway":            ["broadway"],
    "Nutana":              ["nutana"],
    "Downtown Terminal":   ["downtown terminal", "bus terminal", "bus depot",
                            "transit terminal"],
    "Confederation Mall":  ["confederation mall", "confed mall"],
    "Market Mall":         ["market mall"],
    "Place Riel / USask":  ["place riel", "usask", "u of s", "university of saskatchewan"],
    "Riverbank / Meewasin": ["river", "meewasin", "riverbank", "river trail"],
    "Stonebridge":         ["stonebridge"],
    "Lakeridge":           ["lakeridge"],
    "Briarwood":           ["briarwood"],
    "Arbor Creek":         ["arbor creek"],
    "Silverspring":        ["silverspring", "silver spring"],
}

# Added October 2026: the safety-perception survey draft names Sutherland as a
# site the Reddit data pointed to, but it was never a tracked category. Every
# one of its 53 word-boundary matches was checked by hand and refers to the
# Saskatoon neighbourhood (or businesses / Sutherland Beach within it).
NEIGHBOURHOODS_ADDED: dict[str, list[str]] = {
    "Sutherland": ["sutherland"],
}

NEIGHBOURHOODS: dict[str, list[str]] = {**NEIGHBOURHOODS_ORIGINAL, **NEIGHBOURHOODS_ADDED}

# Six categories that have a loc_* column in the raw files.
ORIGINAL_LOC_COLUMNS = {
    "Pleasant Hill": "loc_pleasant_hill",
    "Riversdale": "loc_riversdale",
    "Downtown / CBD": "loc_downtown_cbd",
    "Downtown Terminal": "loc_downtown_terminal",
    "Confederation Mall": "loc_confederation_mall",
    "Riverbank / Meewasin": "loc_riverbank_meewasin",
}

# Sites broken down by cue / time of day = every category with at least this
# many verified mentions (posts + comments). The August list was hand-picked
# and omitted Broadway (51) and Place Riel (48) despite its stated >=15 rule.
MIN_MENTIONS_FOCUS = 15
# The two sites the August report compared directly.
REPORT_SITES = ["Downtown / CBD", "Riverbank / Meewasin"]

# Cities whose mention in the same text marks a location match for manual
# review (is "downtown" Saskatoon's downtown, or Regina's?).
OTHER_CITIES = [
    "regina", "calgary", "edmonton", "vancouver", "toronto", "winnipeg",
    "montreal", "ottawa", "victoria", "halifax", "kelowna", "prince albert",
    "moose jaw", "north battleford", "swift current", "yorkton", "lloydminster",
    "red deer", "lethbridge", "kamloops", "hamilton", "mississauga", "seattle",
    "portland", "minneapolis", "chicago", "new york", "nyc", "san francisco",
    "denver", "los angeles", "houston", "london", "kingston", "surrey",
    "burnaby", "windsor", "quebec",
]
OTHER_CITY_RE = re.compile(r"\b(" + "|".join(re.escape(c) for c in OTHER_CITIES) + r")\b")


def slug(name: str, prefix: str = "") -> str:
    return prefix + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def substring_match(text, patterns: list[str]) -> bool:
    """ORIGINAL scraper logic: bare substring containment ("river" in "driver")."""
    if not isinstance(text, str):
        return False
    t = text.lower()
    return any(p in t for p in patterns)


@lru_cache(maxsize=None)
def _bounded_re(patterns: tuple[str, ...]) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(re.escape(p) for p in patterns) + r")\b")


def bounded_match(text, patterns: list[str]) -> bool:
    """Word-boundary match on the same patterns (the August 2026 fix)."""
    if not isinstance(text, str):
        return False
    return bool(_bounded_re(tuple(patterns)).search(text.lower()))


def other_cities_mentioned(text) -> str:
    if not isinstance(text, str):
        return ""
    return ";".join(sorted(set(OTHER_CITY_RE.findall(text.lower()))))


@lru_cache(maxsize=1)
def other_city_exclusions() -> frozenset[tuple[str, str, str]]:
    """(record_type, record_id, neighbourhood) triples a reviewer marked
    'exclude' in manual_review/location_other_city_review.csv."""
    path = MANUAL_REVIEW_DIR / "location_other_city_review.csv"
    review = pd.read_csv(path, dtype=str)
    ex = review[review["decision"].str.strip().str.lower() == "exclude"]
    return frozenset(zip(ex["record_type"], ex["record_id"], ex["neighbourhood"]))


def neighbourhood_tags(df: pd.DataFrame, text_col: str, id_col: str, record_type: str,
                       vocab: dict[str, list[str]] | None = None,
                       prefix: str = "vloc_") -> pd.DataFrame:
    """Adds one boolean column per neighbourhood: word-boundary match, minus
    hand-reviewed other-city references. Returns df (modified in place)."""
    vocab = NEIGHBOURHOODS if vocab is None else vocab
    excl = other_city_exclusions()
    for name, patterns in vocab.items():
        col = slug(name, prefix)
        hit = df[text_col].apply(lambda t, p=patterns: bounded_match(t, p))
        drop = df[id_col].astype(str).apply(lambda i, n=name: (record_type, i, n) in excl)
        df[col] = hit & ~drop
    return df


# ---------------------------------------------------------------------------
# Environmental cues
# ---------------------------------------------------------------------------

# Verbatim from initial_sraper.py as run on 2026-06-11 (ENVIRONMENTAL_CUES).
ENV_CUES_ORIGINAL: dict[str, list[str]] = {
    "lighting":   ["light", "lit", "dark", "lighting", "streetlight", "unlit"],
    "noise":      ["loud", "noisy", "quiet", "noise", "screaming", "yelling"],
    "weather":    ["snow", "ice", "cold", "winter", "freezing", "rain", "slush"],
    "time_of_day": ["night", "evening", "late", "early morning", "midnight",
                    "2am", "3am", "afterhours", "after dark"],
    "people":     ["crowded", "empty", "deserted", "abandoned", "alone",
                   "stranger", "strangers", "homeless"],
}

# Corrected definitions. "include" entries are regex fragments matched as whole
# words (\b...\b) on lower-cased text. "exclude" phrases are blanked out before
# matching, so e.g. "red light" no longer counts as a lighting cue but
# "the street had no lights" still does.
ENV_CUES: dict[str, dict[str, list[str]]] = {
    "lighting": {
        "include": [
            r"lights?", r"lighting", r"lit", r"unlit", r"dark", r"darker",
            r"darkest", r"darkness", r"darkened", r"street[ -]?lights?",
            r"street[ -]?lamps?", r"lamp[ -]?posts?", r"flood[ -]?lights?",
            r"flashlights?", r"daylight", r"sunlight", r"moonlight",
        ],
        "exclude": [
            # traffic signals
            r"\b(red|green|yellow|amber|orange|traffic|stop|walk|signal|crosswalk|"
            r"crossing|pedestrian|turn|advance|flashing)[ -]lights?\b",
            r"\bthe lights? (turn|turns|turned|turning|change|changes|changed|changing)\b",
            r"\b(run|runs|ran|running) (a|the) (red )?lights?\b",
            r"\b(at|past|through) (a|the) lights?\b", r"\blight heads?\b",
            r"\bthe lights (at|on) \d+\w*\b", r"\b(make|made|making) the light\b",
            r"\b(flashy|flashing|crosswalk|crossing) lights?\b",
            # vehicle lights
            r"\b(head|tail|brake|hazard|dash|fog|parking|running|high[ -]?beam|"
            r"back[ -]?up|reverse|indicator|police|emergency|cop|siren)[ -]?lights?\b",
            r"\b(turn|turns|turned|turning|put|have|had|has) (on )?(his|her|their|your|its) lights\b",
            # decorative / indoor / figurative
            r"\b(grow|uv|black|christmas|xmas|holiday|fairy|string)[ -]lights?\b",
            r"\blight (humou?r|therapy|show|shows|tour|tours|display|displays|reading|hearted)\b",
            r"\blight beers?\b", r"\blight ?house\b", r"\blight[ -]sensitive\b",
            r"\b(ceiling|auto|back|interior|dome|bike|neon|uv) lights?\b",
            r"\b(white|red|blue|green) light and\b",
            r"\bcandles? to light\b", r"\blit (it|them) up\b",
            # non-illumination senses of "light"
            r"\blight (rail|years?|sleeper|weight|duty|blue|snow|rain|traffic|"
            r"jacket|packer|switch|bulb|fixture)\b",
            r"\b(in|by) (the )?light of\b", r"\bmake light of\b",
            r"\bsh[ea]d(s|ding)? (some )?light on\b", r"\b(come|came|bring|brought) to light\b",
            r"\bgas[ -]?lit\b", r"\bgaslight\w*\b",
            r"\b(fire|fires|cigarette|joint|smoke|candle)s? (was |were )?lit\b",
            r"\blit (a|the|his|her|their|up a) (fire|cigarette|joint|smoke|candle)s?\b",
            # non-illumination senses of "dark"
            r"\bdark (clothing|clothes|colou?red|colou?rs?|jackets?|hoodies?|coats?|"
            r"hair|greys?|grays?|green|blue|red|black|brown|pastels?|web|humou?r|money|"
            r"horse|side|skin|skinned|chocolate|mode|souls?|times|ages|place)\b",
            r"\b(in the dark about|kept in the dark|shot in the dark)\b",
        ],
    },
    "noise": {
        "include": [
            r"loud", r"louder", r"loudest", r"loudly", r"noisy", r"noise",
            r"noises", r"quiet", r"quieter", r"quietest", r"screaming", r"yelling",
        ],
        "exclude": [
            r"\bout loud\b", r"\bloud and clear\b", r"\bcrying out loud\b",
            r"\bquiet part\b", r"\b(keep|keeps|kept|keeping) (it |this |that )?quiet\b",
            r"\bquiet(ly)? quit\w*\b", r"\byell(ing)? at (the )?clouds?\b",
            r"\bcr(y|ies|ied|ying) the loudest\b",
            r"\bthe loudest (complain\w*|voices?|critics?|people|ones)\b", r"\bloud cups?\b",
        ],
    },
    "weather": {
        "include": [
            r"snow\w*", r"ice", r"icy", r"cold", r"colder", r"coldest", r"winter",
            r"winters", r"wintery", r"wintry", r"freezing", r"rain", r"rains",
            r"rained", r"raining", r"rainy", r"rainfall", r"rainstorms?", r"slush",
            r"slushy",
        ],
        "exclude": [
            r"\bsnowflakes?\b", r"\bsnowbirds?\b",
            r"\bice (cream|creams|cube|cubes|tea|coffee)\b", r"\bice cold\b",
            r"\bice road\b",
            r"\bcold (call|calls|calling|case|cases|hard|blood|blooded|feet|shoulder|"
            r"turkey|brew|brews|beer|beers|drink|drinks|sweat|sore|sores|laser|plunge|war)\b",
            r"\b(common|a bad|caught a|catch a|catching a|have a|had a|just a|got a) cold\b",
            r"\brain ?check\b", r"\bmake it rain\b",
        ],
        # Case-sensitive: "ICE" (US immigration enforcement) is not weather.
        "exclude_case_sensitive": [r"\bICE\b"],
    },
    "time_of_day": {
        # Deliberate narrowing: bare "late" ("too late", "the late 90s",
        # "running late") is replaced by explicitly nocturnal phrases.
        "include": [
            r"night", r"nights", r"night[ -]?time", r"tonight", r"overnight",
            r"nightly", r"nightlife", r"nightfall", r"midnight", r"evening",
            r"evenings", r"late (at )?nights?", r"late[ -]night", r"late evenings?",
            r"early mornings?", r"[23] ?am", r"after dark", r"after[ -]?hours",
        ],
        "exclude": [
            r"\b(like )?night (and|&) day\b", r"\bday (and|&) night\b", r"\bgood ?night\b",
            r"\bnight ?clubs?\b",
            r"\bovernight (solution|fix|success|sensation|change|transformation)s?\b",
            r"\b(solved|fixed|fix|change|changed|happen|happened|happens|disappear|disappeared) overnight\b",
        ],
    },
    "people": {
        "include": [
            r"crowded", r"overcrowded", r"empty", r"deserted", r"abandoned",
            r"alone", r"stranger", r"strangers", r"homeless", r"homelessness",
        ],
        "exclude": [
            r"\blet alone\b",
            r"\b(leave|leaves|leaving|left|let) (me|you|him|her|them|us|it|people|"
            r"others|everyone|kids|dogs?|cats?) alone\b",
            r"\b(that|this|these|those) alone\b",
            r"\b(i'?m|i am|you'?re|you are|we'?re|we are) (not|never) alone\b",
            r"\bin (saskatoon|saskatchewan|canada|the city|this city|this year|last year) alone\b",
            r"\bno stranger to\b", r"\bstranger things\b",
            r"\bempty (promises?|threats?|words?|gestures?|calories|nesters?)\b",
        ],
    },
}

ENV_CUE_NAMES = list(ENV_CUES)


@lru_cache(maxsize=None)
def _cue_regexes(cue: str):
    spec = ENV_CUES[cue]
    inc = re.compile(r"\b(?:" + "|".join(spec["include"]) + r")\b")
    exc = [re.compile(p) for p in spec.get("exclude", [])]
    exc_cs = [re.compile(p) for p in spec.get("exclude_case_sensitive", [])]
    return inc, exc, exc_cs


def cue_hits(text, cue: str) -> list[str]:
    """Words/phrases that count as `cue` in `text` under the corrected
    definitions (empty list = no cue)."""
    if not isinstance(text, str) or not text:
        return []
    inc, exc, exc_cs = _cue_regexes(cue)
    t = text
    for r in exc_cs:
        t = r.sub(" ", t)
    t = t.lower()
    for r in exc:
        t = r.sub(" ", t)
    return [m.group(0) for m in inc.finditer(t)]


def cue_flag(text, cue: str) -> bool:
    return bool(cue_hits(text, cue))


def original_cue_flag(text, cue: str) -> bool:
    return substring_match(text, ENV_CUES_ORIGINAL[cue])


# ---------------------------------------------------------------------------
# Sentiment
# ---------------------------------------------------------------------------

# Lexicon adjustment (October 2026). Stock VADER scores the seed terms "safe"
# (+1.9) and "safety" (+1.8) as positive but has no entry for the seed terms
# "unsafe", "sketchy" or "afraid", so "is it safe to walk downtown?" scores
# +0.44 and "this area is sketchy" scores 0. Fix:
#   - "safety" -> 0: it names the topic every post was searched on, not a stance.
#   - "unsafe" -> -1.9 (mirror of VADER's "safe"), "afraid" -> -1.9 (VADER's
#     "scared"), "sketchy" -> -1.5 (VADER's "suspicious").
#   - "safe" is kept: it carries stance and VADER's negation handling turns
#     "don't feel safe" negative.
VADER_LEXICON_ADJUSTMENTS: dict[str, float] = {
    "safety": 0.0,
    "unsafe": -1.9,
    "afraid": -1.9,
    "sketchy": -1.5,
}


@lru_cache(maxsize=2)
def _vader(adjusted: bool):
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    a = SentimentIntensityAnalyzer()
    if adjusted:
        for w, v in VADER_LEXICON_ADJUSTMENTS.items():
            if v == 0.0:
                a.lexicon.pop(w, None)
            else:
                a.lexicon[w] = v
    return a


def vader_compound(text, adjusted: bool = True) -> float:
    if not isinstance(text, str) or not text.strip():
        return 0.0
    return _vader(adjusted).polarity_scores(text)["compound"]


def sentiment_category(c: float) -> str:
    if c >= 0.05:
        return "positive"
    if c <= -0.05:
        return "negative"
    return "neutral"


def scrub_pii_keep_case(text) -> str:
    """Same PII scrub as the scraper's _scrub_pii, but without lower-casing,
    so VADER keeps its ALL-CAPS emphasis signal."""
    if not isinstance(text, str) or not text:
        return ""
    t = re.sub(r"http\S+|www\S+", " [URL] ", text)
    t = re.sub(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", " [PHONE] ", t)
    t = re.sub(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", " [EMAIL] ", t, flags=re.I)
    t = re.sub(
        r"\b\d+\s+[\w\s]{1,30}\s+"
        r"(street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd|crescent|cres|way|lane|ln)\b",
        " [ADDRESS] ", t, flags=re.I,
    )
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------------------
# Local time (Saskatchewan is UTC-6 year-round, no DST)
# ---------------------------------------------------------------------------

LOCAL_TZ = "America/Regina"
TIME_OF_DAY_ORDER = ["morning", "afternoon", "evening", "night"]
SEASON_ORDER = ["spring", "summer", "fall", "winter"]


def season_of(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "fall"


def time_of_day_of(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def add_local_time(df: pd.DataFrame, utc_col: str = "created_utc") -> pd.DataFrame:
    """Adds local_* columns. The raw files compute hour_local correctly but
    take month/day/season/day_of_week from the UTC timestamp, so anything
    posted 18:00-24:00 local is filed under the next calendar day."""
    d = pd.to_datetime(df[utc_col], unit="s", utc=True).dt.tz_convert(LOCAL_TZ)
    df["local_datetime"] = d.dt.strftime("%Y-%m-%d %H:%M:%S%z")
    df["local_date"] = d.dt.strftime("%Y-%m-%d")
    df["local_month"] = d.dt.month
    df["local_day_of_week"] = d.dt.dayofweek
    df["local_day_name"] = d.dt.day_name()
    df["local_hour"] = d.dt.hour
    df["local_season"] = df["local_month"].apply(season_of)
    df["local_time_of_day"] = df["local_hour"].apply(time_of_day_of)
    return df


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

N_BOOT = 2000
SEED = 20261016


def cluster_bootstrap_ci(values, clusters, stat=np.mean, n_boot: int = N_BOOT,
                         seed: int = SEED, alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI from resampling whole clusters (Reddit threads) with
    replacement. Comments in one thread are not independent observations, so
    resampling individual comments would overstate precision."""
    values = np.asarray(values, dtype=float)
    clusters = np.asarray(clusters)
    if len(values) < 2:
        return (np.nan, np.nan)
    uniq, inv = np.unique(clusters, return_inverse=True)
    groups = [values[inv == k] for k in range(len(uniq))]
    if len(groups) < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    stats = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.integers(0, len(groups), len(groups))
        stats[b] = stat(np.concatenate([groups[i] for i in pick]))
    lo, hi = np.percentile(stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return (float(lo), float(hi))


def cluster_bootstrap_diff_ci(a_vals, a_clusters, b_vals, b_clusters,
                              n_boot: int = N_BOOT, seed: int = SEED,
                              alpha: float = 0.05) -> tuple[float, float]:
    """CI for mean(a) - mean(b), resampling threads within each group."""
    a_vals, b_vals = np.asarray(a_vals, float), np.asarray(b_vals, float)
    if len(a_vals) < 2 or len(b_vals) < 2:
        return (np.nan, np.nan)

    def groups(v, c):
        u, inv = np.unique(np.asarray(c), return_inverse=True)
        return [v[inv == k] for k in range(len(u))]

    ga, gb = groups(a_vals, a_clusters), groups(b_vals, b_clusters)
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        sa = np.concatenate([ga[i] for i in rng.integers(0, len(ga), len(ga))])
        sb = np.concatenate([gb[i] for i in rng.integers(0, len(gb), len(gb))])
        diffs[b] = sa.mean() - sb.mean()
    lo, hi = np.percentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return (float(lo), float(hi))


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion (ignores thread clustering;
    used only where a quick bound on a small-n percentage is enough)."""
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    denom = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (float(centre - half), float(centre + half))


def thread_id(df: pd.DataFrame, record_type: str) -> pd.Series:
    """Cluster id for bootstrapping: a post is its own thread; a comment
    belongs to its parent post's thread."""
    return df["id"].astype(str) if record_type == "post" else df["parent_post_id"].astype(str)
