"""
ComputerVision_Sentinel | Reddit Safety Perception Scraper
========================================================
Saskatoon Safety Narrative Collection (June 2025 – June 2026)

Project: A Privacy-Preserving GeoAI Framework for Urban CPTED Decision Support
         Using Environmental Sensing and Community Narratives
Co-Leads: Dr. Varuni Jayasooriya (SENS) & Dr. Timothy Kang (Sociology)
Funder:   USask AIRI Research Capacity Building Grant (2026)

PURPOSE
-------
This script collects Reddit posts and comments from r/saskatoon over the past
12 months (June 2025 – June 2026) to support the project's narrative criminology
component. Following Dr. Kang's guidance (3 June 2026), the script begins with
a deliberately narrow set of safety/danger seed terms and captures the
surrounding discursive context (full comment threads, neighbourhood mentions,
temporal markers) rather than pre-categorizing posts into crime / weather /
pandemic buckets as the prior pandemic-era scraper did.

DESIGN PHILOSOPHY
-----------------
The example thread Dr. Kang shared (river-running-at-night) illustrates the
phenomenon of interest: posts where an underlying perception of threat is
communally validated despite a lack of direct evidence of harm. To capture
these dynamics, the script:

  1. Uses minimal seed terms (safety, danger, unsafe, sketchy, scary, afraid,
     and a small set of close synonyms) to surface posts where users are
     thinking about safety, without prejudging the subject matter.
  2. Captures full comment trees, not just post bodies — community consensus
     and validation patterns are visible in comments, not OPs.
  3. Tags neighbourhood/site mentions inline (Pleasant Hill, Riversdale,
     downtown, 20th Street, bus terminal, Confederation Mall, etc.) so the
     dataset can be filtered to the lit-review's identified pilot sites.
  4. Records temporal context (time of day, season, day of week) for the
     environmental sensing pillar.
  5. Treats this as a discovery dataset — researchers can refine keywords
     and categories AFTER reading what the seed terms actually return.

WHAT THIS SCRIPT IS NOT
-----------------------
- It is NOT a crime keyword counter. The previous pandemic scraper's exhaustive
  crime/weather/pandemic keyword lists are deliberately not reused.
- It is NOT a multi-city collection. Scope is r/saskatoon only.
- It is NOT a categorical classifier. Posts are surfaced by safety-perception
  seed terms and tagged for context; interpretation is human-led downstream.

INPUT
-----
PRAW credentials (Reddit API).

OUTPUTS
-------
- saskatoon_safety_posts_<YYYYMMDD>.csv         Main posts dataset
- saskatoon_safety_comments_<YYYYMMDD>.csv      Comment threads (post-linked)
- saskatoon_safety_metadata_<YYYYMMDD>.json     Collection metadata
- saskatoon_safety_gis_<YYYYMMDD>.csv           GIS-ready (neighbourhood-tagged)
- computervision_sentinel_scraper.log                     Detailed log

ETHICS
------
- Authors anonymized via SHA-256 hash (truncated to 16 chars).
- Deleted/removed content excluded.
- PII (phone numbers, emails, street addresses) scrubbed from cleaned_text.
- No direct quotation of users in any downstream publication without separate
  consent process; this dataset is for thematic analysis only.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

try:
    import praw
    from praw.models import MoreComments, Submission
    PRAW_AVAILABLE = True
except ImportError:
    print("Error: praw not installed. Install with: pip install praw")
    PRAW_AVAILABLE = False
    raise SystemExit(1)

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    print("Warning: vaderSentiment not installed. Sentiment analysis disabled.")
    print("Install with: pip install vaderSentiment")
    VADER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("computervision_sentinel_scraper.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("ComputerVision_Sentinel")


@dataclass
class ScraperConfig:
    """All tunable parameters for the collection run live here."""

    # Scope
    subreddit: str = "saskatoon"

    # Time window: June 11 2025 – June 11 2026 (past 12 months, all four seasons)
    start_date: datetime = field(
        default_factory=lambda: datetime(2025, 6, 11, tzinfo=timezone.utc)
    )
    end_date: datetime = field(
        default_factory=lambda: datetime(2026, 6, 11, tzinfo=timezone.utc)
    )

    # Per-query collection limits (Reddit's hard ceiling is ~1000)
    max_per_search: int = 500
    max_top_posts: int = 500
    max_new_posts: int = 1000

    # Comment collection
    collect_comments: bool = True
    max_comment_depth: int = 4          # Replies to replies to replies to replies
    max_comments_per_post: int = 200    # Cap to keep dataset manageable

    # Rate limiting (seconds between calls)
    inter_query_sleep: float = 2.5
    inter_post_sleep: float = 1.5

    # Output paths (filled in at runtime with date stamp)
    output_dir: Path = field(default_factory=lambda: Path("output"))


# ---------------------------------------------------------------------------
# Seed terms — kept deliberately narrow per Dr. Kang's "start broad" guidance.
# The principle: surface posts where the AUTHOR is reasoning about safety,
# rather than pre-deciding what counts as a safety-relevant post.
# ---------------------------------------------------------------------------

SAFETY_SEED_TERMS: list[str] = [
    # The core pair Dr. Kang named
    "safety", "safe", "unsafe",
    "danger", "dangerous",
    # Affective register — how people actually talk about felt threat
    "sketchy", "scary", "afraid", "nervous", "worried",
    # Spatial/temporal-relational safety language
    "is it safe", "feel safe",
]

# Saskatoon neighbourhoods/sites named in the literature review.
# These are tagged in posts but NOT used as filters — every post returned
# by the seed terms is kept; neighbourhood tags become an analytical
# dimension, not a gatekeeping criterion.
SASKATOON_NEIGHBOURHOODS: dict[str, list[str]] = {
    # West-side core (Priority Areas)
    "Pleasant Hill":       ["pleasant hill"],
    "Riversdale":          ["riversdale"],
    "Meadowgreen":         ["meadowgreen"],
    "Westmount":           ["westmount"],
    "Mount Royal":         ["mount royal"],
    "King George":         ["king george"],
    "Caswell Hill":        ["caswell hill", "caswell"],
    "Mayfair":             ["mayfair"],
    # Central/downtown
    "Downtown / CBD":      ["downtown", "cbd", "central business district",
                            "20th street", "20th st", "23rd street", "23rd st"],
    "Broadway":            ["broadway"],
    "Nutana":              ["nutana"],
    # Transit
    "Downtown Terminal":   ["downtown terminal", "bus terminal", "bus depot",
                            "transit terminal"],
    "Confederation Mall":  ["confederation mall", "confed mall"],
    "Market Mall":         ["market mall"],
    "Place Riel / USask":  ["place riel", "usask", "u of s", "university of saskatchewan"],
    # River and adjacent
    "Riverbank / Meewasin": ["river", "meewasin", "riverbank", "river trail"],
    # Outer comparisons
    "Stonebridge":         ["stonebridge"],
    "Lakeridge":           ["lakeridge"],
    "Briarwood":           ["briarwood"],
    "Arbor Creek":         ["arbor creek"],
    "Silverspring":        ["silverspring", "silver spring"],
}

# Light environmental-condition vocabulary — to flag posts where users describe
# the kinds of variables our IoT sensors will measure (lighting, noise, etc.).
# Used only for tagging, not filtering.
ENVIRONMENTAL_CUES: dict[str, list[str]] = {
    "lighting":   ["light", "lit", "dark", "lighting", "streetlight", "unlit"],
    "noise":      ["loud", "noisy", "quiet", "noise", "screaming", "yelling"],
    "weather":    ["snow", "ice", "cold", "winter", "freezing", "rain", "slush"],
    "time_of_day":["night", "evening", "late", "early morning", "midnight",
                   "2am", "3am", "afterhours", "after dark"],
    "people":     ["crowded", "empty", "deserted", "abandoned", "alone",
                   "stranger", "strangers", "homeless"],
}


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class SaskatoonSafetyCollector:
    """
    Reddit collector for the ComputerVision_Sentinel narrative-criminology pillar.

    Reuses architectural patterns from Ryan's prior pandemic-era scraper
    (multi-strategy retrieval, monthly dedup, VADER sentiment, PII scrub,
    SHA-256 author anonymization) and replaces its categorical keyword
    schema with a discovery-first safety-perception design.
    """

    def __init__(self, praw_credentials: dict, config: ScraperConfig | None = None):
        self.config = config or ScraperConfig()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        self.reddit = praw.Reddit(
            client_id=praw_credentials["client_id"],
            client_secret=praw_credentials["client_secret"],
            user_agent=praw_credentials["user_agent"],
        )
        # Read-only mode — we don't post, vote, or modify anything.
        self.reddit.read_only = True
        logger.info("PRAW initialized in read-only mode for r/%s", self.config.subreddit)

        self.sentiment = (
            SentimentIntensityAnalyzer() if VADER_AVAILABLE else None
        )
        if self.sentiment:
            logger.info("VADER sentiment analyzer initialized")

        self._seen_post_ids: set[str] = set()
        self._post_records: list[dict] = []
        self._comment_records: list[dict] = []

    # ------------------------------------------------------------------
    # 1. Retrieval — multi-strategy, all filtered to the 12-month window
    # ------------------------------------------------------------------

    def collect(self) -> None:
        """Run all retrieval strategies in sequence, deduplicated by post ID."""
        sub = self.reddit.subreddit(self.config.subreddit)
        window = (
            int(self.config.start_date.timestamp()),
            int(self.config.end_date.timestamp()),
        )
        logger.info(
            "Collection window: %s – %s",
            self.config.start_date.date(),
            self.config.end_date.date(),
        )

        # Strategy 1 — seed-term searches (the primary signal)
        for term in SAFETY_SEED_TERMS:
            self._search_strategy(sub, term, window)

        # Strategy 2 — top posts of the year (catches viral safety threads)
        self._listing_strategy(sub.top(time_filter="year", limit=self.config.max_top_posts),
                               window, label="top/year")

        # Strategy 3 — new posts (broad coverage, recent posts surfaced even if
        # not yet indexed by search)
        self._listing_strategy(sub.new(limit=self.config.max_new_posts),
                               window, label="new")

        logger.info("Retrieval complete. Unique posts captured: %d",
                    len(self._post_records))

        # Strategy 4 — comment trees, for every captured post that mentions
        # safety in title or body (we don't pull comments from unrelated top
        # posts to save API budget)
        if self.config.collect_comments:
            self._collect_comments_for_relevant_posts()

    def _search_strategy(self, sub, term: str, window: tuple[int, int]) -> None:
        """Reddit's search endpoint, filtered to our time window after the fact."""
        logger.info("Search: '%s'", term)
        try:
            for submission in sub.search(
                term,
                time_filter="year",
                limit=self.config.max_per_search,
                sort="relevance",
            ):
                self._maybe_capture(submission, window, source=f"search:{term}")
            time.sleep(self.config.inter_query_sleep)
        except Exception as exc:
            logger.warning("Search failed for '%s': %s", term, exc)
            time.sleep(self.config.inter_query_sleep * 2)

    def _listing_strategy(self, listing: Iterable[Submission],
                          window: tuple[int, int], label: str) -> None:
        """Iterate a generic listing (top/new/hot) and capture in-window posts."""
        logger.info("Listing: %s", label)
        count = 0
        try:
            for submission in listing:
                if self._maybe_capture(submission, window, source=label):
                    count += 1
            logger.info("  Listing %s yielded %d new posts", label, count)
            time.sleep(self.config.inter_query_sleep)
        except Exception as exc:
            logger.warning("Listing %s failed: %s", label, exc)

    def _maybe_capture(self, submission: Submission, window: tuple[int, int],
                       source: str) -> bool:
        """Add a submission to the dataset if it's in-window and new."""
        ts = int(submission.created_utc)
        if not (window[0] <= ts <= window[1]):
            return False
        if submission.id in self._seen_post_ids:
            return False

        record = self._extract_post(submission, source=source)
        # Apply text-relevance filter to listing-strategy posts (top/new).
        # Posts found via seed-term search already passed Reddit's match.
        if source.startswith(("top", "new")):
            if not self._mentions_safety(record["full_text"]):
                return False

        self._post_records.append(record)
        self._seen_post_ids.add(submission.id)
        return True

    @staticmethod
    def _mentions_safety(text: str) -> bool:
        """Lightweight in-script filter mirroring the seed terms.

        Used only for top/new listings (which surface posts on any topic);
        keeps the dataset thematically coherent without over-narrowing it.
        """
        if not text:
            return False
        haystack = text.lower()
        return any(term in haystack for term in SAFETY_SEED_TERMS)

    # ------------------------------------------------------------------
    # 2. Per-submission and per-comment record extraction
    # ------------------------------------------------------------------

    def _extract_post(self, s: Submission, source: str) -> dict:
        body = s.selftext or ""
        title = s.title or ""
        full_text = f"{title} {body}".strip()
        return {
            "id": s.id,
            "source": source,
            "subreddit": str(s.subreddit) if s.subreddit else self.config.subreddit,
            "title": title,
            "selftext": body,
            "full_text": full_text,
            "created_utc": float(s.created_utc),
            "created_date": datetime.fromtimestamp(s.created_utc, tz=timezone.utc),
            "author": str(s.author) if s.author else "[deleted]",
            "score": int(s.score),
            "num_comments": int(s.num_comments),
            "upvote_ratio": float(getattr(s, "upvote_ratio", 0.0)),
            "permalink": s.permalink,
            "url": s.url,
            "link_flair_text": s.link_flair_text,
            "is_self": bool(s.is_self),
            "over_18": bool(s.over_18),
            "spoiler": bool(s.spoiler),
            "stickied": bool(s.stickied),
            "locked": bool(s.locked),
        }

    def _collect_comments_for_relevant_posts(self) -> None:
        """Walk comment trees on captured posts to gather community narratives.

        Comments are where validation of safety perceptions happens — the
        r/saskatoon river-at-night thread Dr. Kang flagged is the prototype.
        """
        total = len(self._post_records)
        logger.info("Collecting comments for %d posts", total)
        for idx, post in enumerate(self._post_records, start=1):
            if idx % 25 == 0:
                logger.info("  Comment progress: %d / %d posts", idx, total)
            try:
                submission = self.reddit.submission(id=post["id"])
                submission.comments.replace_more(
                    limit=0  # Skip "load more" stubs to control API budget
                )
                comments = submission.comments.list()[: self.config.max_comments_per_post]
                for c in comments:
                    if isinstance(c, MoreComments):
                        continue
                    self._comment_records.append(self._extract_comment(c, post["id"]))
                time.sleep(self.config.inter_post_sleep)
            except Exception as exc:
                logger.warning("Comment fetch failed for post %s: %s",
                               post["id"], exc)
        logger.info("Comments collected: %d across %d posts",
                    len(self._comment_records), total)

    def _extract_comment(self, c, parent_post_id: str) -> dict:
        return {
            "comment_id": c.id,
            "parent_post_id": parent_post_id,
            "parent_id": c.parent_id,         # May be the post or another comment
            "body": c.body or "",
            "created_utc": float(c.created_utc),
            "created_date": datetime.fromtimestamp(c.created_utc, tz=timezone.utc),
            "author": str(c.author) if c.author else "[deleted]",
            "score": int(c.score),
            "depth": int(getattr(c, "depth", 0)),
            "is_submitter": bool(getattr(c, "is_submitter", False)),
            "stickied": bool(getattr(c, "stickied", False)),
        }

    # ------------------------------------------------------------------
    # 3. Processing — clean, tag, anonymize, sentiment
    # ------------------------------------------------------------------

    def build_dataframes(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        posts_df = pd.DataFrame(self._post_records)
        comments_df = pd.DataFrame(self._comment_records)

        if posts_df.empty:
            logger.warning("No posts captured — returning empty DataFrames")
            return posts_df, comments_df

        posts_df = self._clean(posts_df, text_col="full_text", title_col="title")
        posts_df = self._add_temporal(posts_df, date_col="created_date")
        posts_df = self._tag_neighbourhoods(posts_df, text_col="full_text")
        posts_df = self._tag_environmental_cues(posts_df, text_col="full_text")
        posts_df = self._anonymize(posts_df, author_col="author")
        if self.sentiment:
            posts_df = self._add_sentiment(posts_df, text_col="cleaned_text")

        if not comments_df.empty:
            comments_df = self._clean(comments_df, text_col="body", title_col=None)
            comments_df = self._add_temporal(comments_df, date_col="created_date")
            comments_df = self._tag_neighbourhoods(comments_df, text_col="body")
            comments_df = self._tag_environmental_cues(comments_df, text_col="body")
            comments_df = self._anonymize(comments_df, author_col="author")
            if self.sentiment:
                comments_df = self._add_sentiment(comments_df, text_col="cleaned_text")

        return posts_df, comments_df

    # ---- cleaning helpers -------------------------------------------------

    @staticmethod
    def _clean(df: pd.DataFrame, text_col: str, title_col: str | None) -> pd.DataFrame:
        # Filter out deleted / removed content
        df = df[~df[text_col].isin(["[deleted]", "[removed]", ""])].copy()
        df = df[~df["author"].isin(["[deleted]", "AutoModerator", "[removed]"])]
        df = df.drop_duplicates(subset=[df.columns[0]])  # dedup by primary id

        # Light PII scrub on a SEPARATE cleaned_text column.
        # We keep the raw text too for qualitative coding by Dr. Kang's team.
        df["cleaned_text"] = df[text_col].apply(SaskatoonSafetyCollector._scrub_pii)
        df["text_length"] = df["cleaned_text"].str.len()
        df["word_count"] = df["cleaned_text"].str.split().str.len()
        return df

    @staticmethod
    def _scrub_pii(text: str) -> str:
        if not isinstance(text, str) or not text:
            return ""
        t = text.lower()
        # URLs
        t = re.sub(r"http\S+|www\S+", " [URL] ", t)
        # Phone numbers (NANP)
        t = re.sub(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", " [PHONE] ", t)
        # Email addresses
        t = re.sub(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", " [EMAIL] ", t)
        # Street addresses (rough)
        t = re.sub(
            r"\b\d+\s+[\w\s]{1,30}\s+"
            r"(street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd|crescent|cres|way|lane|ln)\b",
            " [ADDRESS] ", t,
        )
        # Collapse whitespace; keep punctuation for sentiment & coding
        t = re.sub(r"\s+", " ", t).strip()
        return t

    # ---- temporal helpers -------------------------------------------------

    @staticmethod
    def _add_temporal(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
        d = pd.to_datetime(df[date_col], utc=True)
        df["year"] = d.dt.year
        df["month"] = d.dt.month
        df["day"] = d.dt.day
        df["day_of_week"] = d.dt.dayofweek
        df["day_name"] = d.dt.day_name()
        df["hour_utc"] = d.dt.hour
        # Local Saskatoon time (CST, UTC-6) — Saskatchewan does not observe DST
        df["hour_local"] = (d.dt.hour - 6) % 24
        df["week_of_year"] = d.dt.isocalendar().week.astype(int)

        def season(m: int) -> str:
            if m in (12, 1, 2):  return "winter"
            if m in (3, 4, 5):   return "spring"
            if m in (6, 7, 8):   return "summer"
            return "fall"

        df["season"] = df["month"].apply(season)

        # Time-of-day bucket — winter darkness in Saskatoon is a key sensor
        # variable; aligning posts to dark/light bands matters for CPTED.
        def tod(h: int) -> str:
            if 5 <= h < 12:   return "morning"
            if 12 <= h < 17:  return "afternoon"
            if 17 <= h < 21:  return "evening"
            return "night"

        df["time_of_day"] = df["hour_local"].apply(tod)
        return df

    # ---- neighbourhood and environmental tagging -------------------------

    @staticmethod
    def _tag_neighbourhoods(df: pd.DataFrame, text_col: str) -> pd.DataFrame:
        def matches(text: str) -> list[str]:
            if not isinstance(text, str) or not text:
                return []
            t = text.lower()
            hits = []
            for name, patterns in SASKATOON_NEIGHBOURHOODS.items():
                if any(p in t for p in patterns):
                    hits.append(name)
            return hits

        df["neighbourhoods_mentioned"] = df[text_col].apply(matches)
        df["n_neighbourhoods"] = df["neighbourhoods_mentioned"].apply(len)
        df["any_neighbourhood"] = df["n_neighbourhoods"] > 0
        # Convenient binary flags for the highest-priority sites
        for priority_name in ["Pleasant Hill", "Riversdale", "Downtown / CBD",
                              "Downtown Terminal", "Confederation Mall",
                              "Riverbank / Meewasin"]:
            col = "loc_" + re.sub(r"[^a-z0-9]+", "_", priority_name.lower()).strip("_")
            df[col] = df["neighbourhoods_mentioned"].apply(
                lambda lst, name=priority_name: name in lst
            )
        return df

    @staticmethod
    def _tag_environmental_cues(df: pd.DataFrame, text_col: str) -> pd.DataFrame:
        for cue_name, patterns in ENVIRONMENTAL_CUES.items():
            col = f"env_{cue_name}"
            df[col] = df[text_col].apply(
                lambda t, p=patterns: bool(
                    isinstance(t, str) and any(w in t.lower() for w in p)
                )
            )
        df["n_env_cues"] = df[[f"env_{k}" for k in ENVIRONMENTAL_CUES]].sum(axis=1)
        return df

    # ---- anonymization ---------------------------------------------------

    @staticmethod
    def _anonymize(df: pd.DataFrame, author_col: str) -> pd.DataFrame:
        df["author_hash"] = df[author_col].apply(
            lambda a: hashlib.sha256(str(a).encode()).hexdigest()[:16]
        )
        df = df.drop(columns=[author_col])
        return df

    # ---- sentiment -------------------------------------------------------

    def _add_sentiment(self, df: pd.DataFrame, text_col: str) -> pd.DataFrame:
        def score(text: str) -> dict:
            if not isinstance(text, str) or not text.strip():
                return {"compound": 0.0, "pos": 0.0, "neu": 1.0, "neg": 0.0}
            return self.sentiment.polarity_scores(text)

        scores = df[text_col].apply(score)
        df["sentiment_compound"] = scores.apply(lambda s: s["compound"])
        df["sentiment_positive"] = scores.apply(lambda s: s["pos"])
        df["sentiment_neutral"] = scores.apply(lambda s: s["neu"])
        df["sentiment_negative"] = scores.apply(lambda s: s["neg"])

        def category(c: float) -> str:
            if c >= 0.05:  return "positive"
            if c <= -0.05: return "negative"
            return "neutral"

        df["sentiment_category"] = df["sentiment_compound"].apply(category)
        return df

    # ------------------------------------------------------------------
    # 4. Export
    # ------------------------------------------------------------------

    def export(self, posts_df: pd.DataFrame, comments_df: pd.DataFrame) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        outdir = self.config.output_dir

        # Drop the raw 'selftext' / 'body' columns before saving — qualitative
        # researchers should work from the source post (linked via permalink)
        # rather than from raw scraped text, to preserve context.
        posts_path = outdir / f"saskatoon_safety_posts_{stamp}.csv"
        export_posts = posts_df.copy()
        # Convert list column to pipe-delimited string for CSV
        if "neighbourhoods_mentioned" in export_posts.columns:
            export_posts["neighbourhoods_mentioned"] = export_posts[
                "neighbourhoods_mentioned"
            ].apply(lambda lst: "|".join(lst) if isinstance(lst, list) else "")
        export_posts.to_csv(posts_path, index=False)
        logger.info("Posts saved: %s (%d rows)", posts_path, len(export_posts))

        if not comments_df.empty:
            comments_path = outdir / f"saskatoon_safety_comments_{stamp}.csv"
            export_comments = comments_df.copy()
            if "neighbourhoods_mentioned" in export_comments.columns:
                export_comments["neighbourhoods_mentioned"] = export_comments[
                    "neighbourhoods_mentioned"
                ].apply(lambda lst: "|".join(lst) if isinstance(lst, list) else "")
            export_comments.to_csv(comments_path, index=False)
            logger.info("Comments saved: %s (%d rows)",
                        comments_path, len(export_comments))

        self._write_metadata(posts_df, comments_df, stamp)
        self._write_gis(posts_df, stamp)
        self._write_summary(posts_df, comments_df, stamp)

    def _write_metadata(self, posts_df, comments_df, stamp: str) -> None:
        meta = {
            "collection_run_utc": datetime.now(timezone.utc).isoformat(),
            "subreddit": self.config.subreddit,
            "window_start": self.config.start_date.isoformat(),
            "window_end": self.config.end_date.isoformat(),
            "seed_terms": SAFETY_SEED_TERMS,
            "n_neighbourhoods_tracked": len(SASKATOON_NEIGHBOURHOODS),
            "n_environmental_cue_categories": len(ENVIRONMENTAL_CUES),
            "posts_collected": int(len(posts_df)),
            "comments_collected": int(len(comments_df)),
            "by_season": (
                posts_df["season"].value_counts().to_dict()
                if not posts_df.empty else {}
            ),
            "by_time_of_day": (
                posts_df["time_of_day"].value_counts().to_dict()
                if not posts_df.empty else {}
            ),
            "posts_mentioning_a_neighbourhood": (
                int(posts_df["any_neighbourhood"].sum())
                if not posts_df.empty else 0
            ),
            "sentiment_available": bool(self.sentiment),
        }
        path = self.config.output_dir / f"saskatoon_safety_metadata_{stamp}.json"
        with open(path, "w") as f:
            json.dump(meta, f, indent=2, default=str)
        logger.info("Metadata saved: %s", path)

    def _write_gis(self, posts_df: pd.DataFrame, stamp: str) -> None:
        """One row per (post, neighbourhood) mention — directly map-ready.

        We do NOT geocode at the post level via subreddit centroid (the old
        scraper's approach), because every post here is from r/saskatoon and
        that would collapse all data to a single point. Instead, we explode
        on neighbourhood mentions so each tagged neighbourhood gets its own
        record, suitable for ArcGIS chloropleth / point density mapping.
        """
        if posts_df.empty or "neighbourhoods_mentioned" not in posts_df.columns:
            return

        exploded = posts_df.explode("neighbourhoods_mentioned").rename(
            columns={"neighbourhoods_mentioned": "neighbourhood"}
        )
        exploded = exploded[exploded["neighbourhood"].notna()]

        keep = [
            "id", "neighbourhood", "created_date", "year", "month", "season",
            "time_of_day", "score", "num_comments", "n_env_cues",
        ]
        if "sentiment_compound" in exploded.columns:
            keep += ["sentiment_compound", "sentiment_category"]
        keep = [c for c in keep if c in exploded.columns]

        path = self.config.output_dir / f"saskatoon_safety_gis_{stamp}.csv"
        exploded[keep].to_csv(path, index=False)
        logger.info("GIS export saved: %s (%d neighbourhood-mentions)",
                    path, len(exploded))

    def _write_summary(self, posts_df, comments_df, stamp: str) -> None:
        path = self.config.output_dir / f"saskatoon_safety_summary_{stamp}.txt"
        with open(path, "w") as f:
            f.write("=" * 70 + "\n")
            f.write("ComputerVision_Sentinel | Reddit Safety Perception Collection\n")
            f.write(f"r/{self.config.subreddit} | "
                    f"{self.config.start_date.date()} – {self.config.end_date.date()}\n")
            f.write("=" * 70 + "\n\n")

            if posts_df.empty:
                f.write("No posts collected.\n")
                return

            f.write(f"Posts: {len(posts_df)}\n")
            f.write(f"Comments: {len(comments_df)}\n\n")

            f.write("--- Posts by season ---\n")
            for k, v in posts_df["season"].value_counts().items():
                f.write(f"  {k:8s}  {v}\n")

            f.write("\n--- Posts by time-of-day (local) ---\n")
            for k, v in posts_df["time_of_day"].value_counts().items():
                f.write(f"  {k:10s}  {v}\n")

            f.write("\n--- Posts by neighbourhood mentioned ---\n")
            exploded = posts_df.explode("neighbourhoods_mentioned")
            for k, v in exploded["neighbourhoods_mentioned"].value_counts().items():
                if pd.notna(k):
                    f.write(f"  {k:28s}  {v}\n")

            f.write("\n--- Environmental cues mentioned ---\n")
            for cue in ENVIRONMENTAL_CUES:
                col = f"env_{cue}"
                if col in posts_df.columns:
                    f.write(f"  {cue:14s}  {int(posts_df[col].sum())}\n")

            if "sentiment_category" in posts_df.columns:
                f.write("\n--- Sentiment ---\n")
                for k, v in posts_df["sentiment_category"].value_counts().items():
                    f.write(f"  {k:9s}  {v}\n")
                f.write(f"  mean compound: {posts_df['sentiment_compound'].mean():.3f}\n")

        logger.info("Summary saved: %s", path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # PRAW credentials.
    #
    # SECURITY NOTE: These should NOT be committed to a public repository.
    # Before pushing to GitHub, either:
    #   (a) move these into environment variables and read via os.getenv, OR
    #   (b) add this file (or a separate config.py) to .gitignore, OR
    #   (c) rotate the credentials at https://www.reddit.com/prefs/apps
    #       and treat the new ones as secret.
    #
    # The script first checks for environment variables; if absent, it falls
    # back to the hard-coded values below.
    # [2026-10-16] Hard-coded credential values redacted from this copy before
    # it was placed under version control. Set PRAW_CLIENT_ID /
    # PRAW_CLIENT_SECRET in the environment instead.
    import os
    praw_credentials = {
        "client_id":     os.getenv("PRAW_CLIENT_ID",     "<REDACTED>"),
        "client_secret": os.getenv("PRAW_CLIENT_SECRET", "<REDACTED>"),
        "user_agent":    os.getenv("PRAW_USER_AGENT",    "ComputerVision_Sentinel/1.0 by /u/ocamporyan"),
    }

    config = ScraperConfig()
    collector = SaskatoonSafetyCollector(praw_credentials, config)

    logger.info("=" * 70)
    logger.info("ComputerVision_Sentinel | Reddit Safety Perception Collection")
    logger.info("Scope:  r/%s", config.subreddit)
    logger.info("Window: %s – %s",
                config.start_date.date(), config.end_date.date())
    logger.info("Seeds:  %s", ", ".join(SAFETY_SEED_TERMS))
    logger.info("=" * 70)

    collector.collect()
    posts_df, comments_df = collector.build_dataframes()
    collector.export(posts_df, comments_df)

    logger.info("=" * 70)
    logger.info("Collection complete.")
    logger.info("=" * 70)


if __name__ == "__main__":
    if not PRAW_AVAILABLE:
        raise SystemExit("PRAW is required. Install with: pip install praw")
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Interrupted by user — partial outputs may exist.")
    except Exception as exc:
        logger.error("Fatal: %s", exc, exc_info=True)
        raise
