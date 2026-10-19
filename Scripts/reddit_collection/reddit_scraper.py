"""
reddit_scraper.py
=================
ComputerVision_Sentinel | Reddit crime- and safety-narrative collector (r/saskatoon)

Project: A Privacy-Preserving GeoAI Framework for Urban CPTED Decision Support
Co-Leads: Dr. Varuni Jayasooriya (SENS) & Dr. Timothy Kang (Sociology)
Funder:   USask AIRI Research Capacity Building Grant (2026)

PURPOSE
-------
Collects r/saskatoon posts (and their comment threads) for a date window, as the
study's main source of crime and safety narratives (revised work plan, October
2026: Reddit replaces the survey). Default window: the study period, 1 June -
31 August 2026, in Saskatoon local time.

SEED TERMS
----------
Two sets, both searched by default; every post records which searches found it
(`found_by`) and which set's words its text contains (`text_has_*_term`), so the
analysis can be restricted to either set.

  safety  The 12 narrow safety-perception terms used in the June 2026
          collection (Dr. Kang, 3 June 2026), unchanged for comparability.
  crime   Added October 2026 so the collection captures crime narratives too
          ("my car got broken into"), as Dr. Jayasooriya asked (1 Oct 2026).
          Aligned with the selected crime categories: break and enter, theft
          from vehicle, motor vehicle theft, mischief/graffiti, robbery, assault.

RETRIEVAL
---------
Reddit's search returns at most ~250 results per query and sort order, and
cannot filter by date, so each term is searched under four sort orders
(relevance, new, top, comments) and results are filtered to the window. The
year's top listing is added to catch high-traffic threads. This raises recall
but is not exhaustive; posts that use none of the seed terms are not found.

USAGE
-----
  python3 reddit_scraper.py                          # 2026-06-01 .. 2026-08-31
  python3 reddit_scraper.py --start 2026-06-01 --end 2026-08-31 --out <dir>
  python3 reddit_scraper.py --probe                  # test credentials only

CREDENTIALS
-----------
PRAW_CLIENT_ID, PRAW_CLIENT_SECRET, PRAW_USER_AGENT and COMPUTERVISION_SENTINEL_HASH_SALT
are read from the environment, or from the `.env` file at the repository root
(tracked in the private repo; a copy is in .venv/keys.txt). The salt keys the author hashes. It stays private
and is reused across collections so hashes remain comparable.

OUTPUTS (in --out)
------------------
  saskatoon_safety_posts_<YYYYMMDD>.csv      posts, tagged
  saskatoon_safety_comments_<YYYYMMDD>.csv   comment threads (post-linked)
  saskatoon_safety_metadata_<YYYYMMDD>.json  run parameters and counts
  saskatoon_safety_gis_<YYYYMMDD>.csv        one row per post x neighbourhood
  saskatoon_safety_summary_<YYYYMMDD>.txt    human-readable summary
  search_query_log_<YYYYMMDD>.csv            results returned per term x sort
  computervision_sentinel_scraper.log        run log
  collection_code/                           exact copies of this script and
                                             common.py used for the run

ETHICS
------
- Authors anonymized via salted HMAC-SHA-256 (16 hex chars).
- Deleted/removed content excluded; PII scrubbed from cleaned_text.
- No direct quotation of users in any downstream publication without a separate
  consent process; this dataset is for thematic analysis only.

HISTORY
-------
June 2026: first collection (initial_sraper.py, preserved unchanged in
Data/reddit_2025-06-11_2026-06-11/01_raw_collection/). October 2026: whole-word tagging from
common.py, local-time fields, enforced comment depth, salted hashes, adjusted
sentiment, crime seed terms, multi-sort search, date-window CLI.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

HERE = Path(__file__).resolve().parent
COMMON_DIR = HERE.parent / "reddit_analysis" / "scripts"
sys.path.insert(0, str(COMMON_DIR))
import common  # noqa: E402  (shared vocabularies and matchers)

try:
    import praw
    from praw.models import MoreComments
except ImportError:
    raise SystemExit("praw is required: pip install -r requirements.txt")

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False

SCRAPER_VERSION = "2026-10"
LOCAL_TZ = ZoneInfo(common.LOCAL_TZ)
REPO_ROOT = HERE.parents[1]

logger = logging.getLogger("ComputerVision_Sentinel")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEED_TERMS: dict[str, list[str]] = {
    "safety": [
        "safety", "safe", "unsafe", "danger", "dangerous",
        "sketchy", "scary", "afraid", "nervous", "worried",
        "is it safe", "feel safe",
    ],
    "crime": [
        "crime", "stolen", "theft", "broken into", "break in",
        "vandalism", "vandalized", "graffiti", "catalytic converter",
        "car stolen", "smashed window",
        "robbed", "robbery", "mugged",
        "assault", "assaulted", "attacked", "stabbed", "stabbing",
    ],
}


def search_query(term: str, seed_set: str) -> str:
    """Multi-word crime terms are searched as exact phrases. Safety terms are
    sent exactly as in the June 2026 run (unquoted) for comparability."""
    return f'"{term}"' if seed_set == "crime" and " " in term else term


@dataclass
class ScraperConfig:
    """Collection parameters. Defaults reproduce the October 2026 study-period run."""
    subreddit: str = "saskatoon"
    start_local: date = date(2026, 6, 1)
    end_local: date = date(2026, 8, 31)          # inclusive
    seed_sets: tuple[str, ...] = ("safety", "crime")
    search_sorts: tuple[str, ...] = ("relevance", "new", "top", "comments")
    max_top_posts: int = 1000

    collect_comments: bool = True
    max_comment_depth: int = 4          # replies to replies to replies to replies
    max_comments_per_post: int = 200
    replace_more_limit: int | None = 0  # 0 = do not expand "load more" stubs

    inter_query_sleep: float = 2.0
    inter_post_sleep: float = 1.0
    output_dir: Path = field(default_factory=lambda: Path("output"))

    @property
    def window_utc(self) -> tuple[int, int]:
        """Inclusive local-date window as UTC epoch seconds (start, end)."""
        start = datetime.combine(self.start_local, dtime.min, LOCAL_TZ)
        end = datetime.combine(self.end_local, dtime.max, LOCAL_TZ)
        return int(start.timestamp()), int(end.timestamp())

    @property
    def search_time_filter(self) -> str:
        """Reddit search can only filter by 'year'/'all'; use 'year' when the
        whole window lies within the past year."""
        days = (datetime.now(LOCAL_TZ).date() - self.start_local).days
        return "year" if days <= 360 else "all"

    def seed_regex(self, seed_set: str) -> re.Pattern:
        """Whole-word regex matching any term in one seed set."""
        return re.compile(r"\b(?:" + "|".join(re.escape(t) for t in SEED_TERMS[seed_set]) + r")\b")


SASKATOON_NEIGHBOURHOODS: dict[str, list[str]] = common.NEIGHBOURHOODS
ENVIRONMENTAL_CUE_NAMES: list[str] = common.ENV_CUE_NAMES


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class SaskatoonSafetyCollector:
    """Reddit collector for the narrative pillar (read-only API access)."""

    def __init__(self, praw_credentials: dict, config: ScraperConfig | None = None):
        self.config = config or ScraperConfig()
        self.reddit = praw.Reddit(
            client_id=praw_credentials["client_id"],
            client_secret=praw_credentials["client_secret"],
            user_agent=praw_credentials["user_agent"],
        )
        self.reddit.read_only = True
        logger.info("PRAW initialized in read-only mode for r/%s", self.config.subreddit)
        self.sentiment = SentimentIntensityAnalyzer() if VADER_AVAILABLE else None
        self._regex = {s: self.config.seed_regex(s) for s in SEED_TERMS}
        self._posts: dict[str, dict] = {}
        self._comment_records: list[dict] = []
        self.query_log: list[dict] = []

    # ------------------------------------------------------------------
    # 1. Retrieval
    # ------------------------------------------------------------------

    def collect(self) -> None:
        """Run every search and the top listing, then fetch comments for captured posts."""
        sub = self.reddit.subreddit(self.config.subreddit)
        w0, w1 = self.config.window_utc
        logger.info("Window (local): %s .. %s  |  UTC %s .. %s",
                    self.config.start_local, self.config.end_local,
                    datetime.fromtimestamp(w0, timezone.utc), datetime.fromtimestamp(w1, timezone.utc))

        for seed_set in self.config.seed_sets:
            for term in SEED_TERMS[seed_set]:
                for sort in self.config.search_sorts:
                    self._search(sub, term, seed_set, sort)

        self._listing(sub.top(time_filter=self.config.search_time_filter,
                              limit=self.config.max_top_posts), label="top/year")

        logger.info("Retrieval complete. Unique in-window posts: %d", len(self._posts))
        if self.config.collect_comments:
            self._collect_comments()

    def _search(self, sub, term: str, seed_set: str, sort: str) -> None:
        """One search (term x sort). Out-of-window results are dropped; counts go to query_log."""
        q = search_query(term, seed_set)
        seen = kept = 0
        try:
            for s in sub.search(q, sort=sort, time_filter=self.config.search_time_filter, limit=None):
                seen += 1
                kept += self._capture(s, source=f"search:{seed_set}:{term}")
        except Exception as exc:  # noqa: BLE001 - log and continue with other queries
            logger.warning("Search failed (%s | %s): %s", q, sort, exc)
        self.query_log.append({"seed_set": seed_set, "term": term, "query": q, "sort": sort,
                               "results_returned": seen, "in_window_new_or_repeat": kept})
        logger.info("Search %-8s %-22s %-9s -> %3d returned, %3d in window", seed_set, q, sort, seen, kept)
        time.sleep(self.config.inter_query_sleep)

    def _listing(self, listing, label: str) -> None:
        """Capture listing posts whose title or body contains a seed term."""
        kept = 0
        try:
            for s in listing:
                text = f"{s.title or ''} {s.selftext or ''}".lower()
                if any(self._regex[k].search(text) for k in self.config.seed_sets):
                    kept += self._capture(s, source=label)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Listing %s failed: %s", label, exc)
        logger.info("Listing %s -> %d in-window posts mentioning a seed term", label, kept)

    def _capture(self, s, source: str) -> int:
        """Store an in-window submission (or add a source to one already seen)."""
        w0, w1 = self.config.window_utc
        if not (w0 <= int(s.created_utc) <= w1):
            return 0
        if s.id in self._posts:
            self._posts[s.id]["_found_by"].add(source)
            return 1
        rec = self._extract_post(s)
        rec["_found_by"] = {source}
        self._posts[s.id] = rec
        return 1

    # ------------------------------------------------------------------
    # 2. Record extraction
    # ------------------------------------------------------------------

    def _extract_post(self, s) -> dict:
        """Submission -> flat record. The author is hashed later, in _anonymize."""
        body, title = s.selftext or "", s.title or ""
        return {
            "id": s.id,
            "source": "",                         # filled at export (first finder)
            "subreddit": str(s.subreddit) if s.subreddit else self.config.subreddit,
            "title": title,
            "selftext": body,
            "full_text": f"{title} {body}".strip(),
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

    def _collect_comments(self) -> None:
        """Comment threads for every captured post, capped by max_comment_depth and
        max_comments_per_post. "Load more" stubs are not expanded (replace_more_limit=0)."""
        posts = list(self._posts.values())
        logger.info("Collecting comments for %d posts", len(posts))
        w0, w1 = self.config.window_utc
        for idx, post in enumerate(posts, start=1):
            if idx % 25 == 0:
                logger.info("  Comment progress: %d / %d posts", idx, len(posts))
            try:
                submission = self.reddit.submission(id=post["id"])
                submission.comments.replace_more(limit=self.config.replace_more_limit)
                comments = [
                    c for c in submission.comments.list()
                    if not isinstance(c, MoreComments)
                    and int(getattr(c, "depth", 0)) <= self.config.max_comment_depth
                ][: self.config.max_comments_per_post]
                for c in comments:
                    rec = self._extract_comment(c, post["id"])
                    rec["comment_in_window"] = bool(w0 <= rec["created_utc"] <= w1)
                    self._comment_records.append(rec)
                time.sleep(self.config.inter_post_sleep)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Comment fetch failed for post %s: %s", post["id"], exc)
        logger.info("Comments collected: %d across %d posts", len(self._comment_records), len(posts))

    @staticmethod
    def _extract_comment(c, parent_post_id: str) -> dict:
        return {
            "comment_id": c.id,
            "parent_post_id": parent_post_id,
            "parent_id": c.parent_id,
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
        """Captured posts and comments -> processed (posts_df, comments_df)."""
        records = []
        for rec in self._posts.values():
            found = sorted(rec.pop("_found_by", set()))
            rec = dict(rec)
            rec["source"] = found[0] if found else ""
            rec["found_by"] = ";".join(found)
            rec["found_by_seed_sets"] = ";".join(sorted({f.split(":")[1] for f in found
                                                         if f.startswith("search:")}))
            records.append(rec)
        posts_df = pd.DataFrame(records)
        comments_df = pd.DataFrame(self._comment_records)
        if posts_df.empty:
            logger.warning("No posts captured")
            return posts_df, comments_df

        posts_df = self._process(posts_df, text_col="full_text")
        if not comments_df.empty:
            comments_df = self._process(comments_df, text_col="body")
        return posts_df, comments_df

    def _process(self, df: pd.DataFrame, text_col: str) -> pd.DataFrame:
        """Clean, add time fields, tag places/cues/seed terms, hash authors, score sentiment."""
        df = self._clean(df, text_col=text_col)
        df = self._add_temporal(df, date_col="created_date")
        df = self._tag_neighbourhoods(df, text_col=text_col)
        df = self._tag_environmental_cues(df, text_col=text_col)
        for seed_set, rx in self._regex.items():
            df[f"text_has_{seed_set}_term"] = df[text_col].fillna("").str.lower().apply(
                lambda t, r=rx: bool(r.search(t)))
        df = self._anonymize(df, author_col="author")
        if self.sentiment:
            df = self._add_sentiment(df, text_col="cleaned_text")
        return df

    @staticmethod
    def _clean(df: pd.DataFrame, text_col: str) -> pd.DataFrame:
        """Drop deleted/bot rows and duplicates; add PII-scrubbed cleaned_text."""
        df = df[~df[text_col].isin(["[deleted]", "[removed]", ""])].copy()
        df = df[~df["author"].isin(["[deleted]", "AutoModerator", "[removed]"])]
        df = df.drop_duplicates(subset=[df.columns[0]])
        df["cleaned_text"] = df[text_col].apply(SaskatoonSafetyCollector._scrub_pii)
        df["text_length"] = df["cleaned_text"].str.len()
        df["word_count"] = df["cleaned_text"].str.split().str.len()
        return df

    @staticmethod
    def _scrub_pii(text: str) -> str:
        """Lower-cased text with URLs, phone numbers, emails and street addresses tokenised."""
        if not isinstance(text, str) or not text:
            return ""
        t = text.lower()
        t = re.sub(r"http\S+|www\S+", " [URL] ", t)
        t = re.sub(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", " [PHONE] ", t)
        t = re.sub(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", " [EMAIL] ", t)
        t = re.sub(
            r"\b\d+\s+[\w\s]{1,30}\s+"
            r"(street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd|crescent|cres|way|lane|ln)\b",
            " [ADDRESS] ", t,
        )
        return re.sub(r"\s+", " ", t).strip()

    @staticmethod
    def _add_temporal(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
        """Calendar fields in Saskatoon local time, plus season and time-of-day buckets."""
        d_utc = pd.to_datetime(df[date_col], utc=True)
        d = d_utc.dt.tz_convert(common.LOCAL_TZ)
        df["year"] = d.dt.year
        df["month"] = d.dt.month
        df["day"] = d.dt.day
        df["day_of_week"] = d.dt.dayofweek
        df["day_name"] = d.dt.day_name()
        df["hour_utc"] = d_utc.dt.hour
        df["hour_local"] = d.dt.hour
        df["week_of_year"] = d.dt.isocalendar().week.astype(int)
        df["season"] = df["month"].apply(common.season_of)
        # Bucket of POSTING time, not of the experience described.
        df["time_of_day"] = df["hour_local"].apply(common.time_of_day_of)
        return df

    @staticmethod
    def _tag_neighbourhoods(df: pd.DataFrame, text_col: str) -> pd.DataFrame:
        """loc_* flags and a neighbourhoods_mentioned list per record."""
        # Whole-word matching; other-city references ("downtown Regina") are
        # removed at analysis time from the hand-review file.
        df["neighbourhoods_mentioned"] = df[text_col].apply(
            lambda t: [n for n, p in SASKATOON_NEIGHBOURHOODS.items() if common.bounded_match(t, p)])
        df["n_neighbourhoods"] = df["neighbourhoods_mentioned"].apply(len)
        df["any_neighbourhood"] = df["n_neighbourhoods"] > 0
        for name in SASKATOON_NEIGHBOURHOODS:
            df[common.slug(name, "loc_")] = df["neighbourhoods_mentioned"].apply(lambda lst, n=name: n in lst)
        return df

    @staticmethod
    def _tag_environmental_cues(df: pd.DataFrame, text_col: str) -> pd.DataFrame:
        """env_* flag per cue category, plus n_env_cues."""
        for cue in ENVIRONMENTAL_CUE_NAMES:
            df[f"env_{cue}"] = df[text_col].apply(lambda t, q=cue: common.cue_flag(t, q))
        df["n_env_cues"] = df[[f"env_{k}" for k in ENVIRONMENTAL_CUE_NAMES]].sum(axis=1)
        return df

    @staticmethod
    def _anonymize(df: pd.DataFrame, author_col: str) -> pd.DataFrame:
        """Replace the author with a 16-hex-char HMAC-SHA-256 hash (salted, see CREDENTIALS)."""
        salt = os.environ["COMPUTERVISION_SENTINEL_HASH_SALT"].encode()
        df["author_hash"] = df[author_col].apply(
            lambda a: hmac.new(salt, str(a).encode(), hashlib.sha256).hexdigest()[:16])
        return df.drop(columns=[author_col])

    def _add_sentiment(self, df: pd.DataFrame, text_col: str) -> pd.DataFrame:
        """Standard VADER scores, plus the adjusted-lexicon compound used as the primary measure."""
        def score(text: str) -> dict:
            if not isinstance(text, str) or not text.strip():
                return {"compound": 0.0, "pos": 0.0, "neu": 1.0, "neg": 0.0}
            return self.sentiment.polarity_scores(text)

        scores = df[text_col].apply(score)
        df["sentiment_compound"] = scores.apply(lambda s: s["compound"])
        df["sentiment_positive"] = scores.apply(lambda s: s["pos"])
        df["sentiment_neutral"] = scores.apply(lambda s: s["neu"])
        df["sentiment_negative"] = scores.apply(lambda s: s["neg"])
        df["sentiment_category"] = df["sentiment_compound"].apply(common.sentiment_category)
        # Adjusted lexicon (seed-term fix, see common.VADER_LEXICON_ADJUSTMENTS): primary measure.
        df["sentiment_adj_compound"] = df[text_col].apply(common.vader_compound)
        df["sentiment_adj_category"] = df["sentiment_adj_compound"].apply(common.sentiment_category)
        return df

    # ------------------------------------------------------------------
    # 4. Export
    # ------------------------------------------------------------------

    def export(self, posts_df: pd.DataFrame, comments_df: pd.DataFrame) -> str:
        """Write every output to output_dir and copy the collection code beside it.
        Returns the date stamp used in the file names."""
        stamp = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
        out = self.config.output_dir
        for name, df in [("posts", posts_df), ("comments", comments_df)]:
            if df.empty:
                continue
            df = df.copy()
            if "neighbourhoods_mentioned" in df.columns:
                df["neighbourhoods_mentioned"] = df["neighbourhoods_mentioned"].apply(
                    lambda lst: "|".join(lst) if isinstance(lst, list) else "")
            path = out / f"saskatoon_safety_{name}_{stamp}.csv"
            df.to_csv(path, index=False)
            logger.info("%s saved: %s (%d rows)", name.capitalize(), path, len(df))
        pd.DataFrame(self.query_log).to_csv(out / f"search_query_log_{stamp}.csv", index=False)
        self._write_metadata(posts_df, comments_df, stamp)
        self._write_gis(posts_df, stamp)
        self._write_summary(posts_df, comments_df, stamp)
        code_dir = out / "collection_code"
        code_dir.mkdir(exist_ok=True)
        shutil.copy2(Path(__file__), code_dir / Path(__file__).name)
        shutil.copy2(COMMON_DIR / "common.py", code_dir / "common.py")
        return stamp

    def _write_metadata(self, posts_df, comments_df, stamp: str) -> None:
        """Run parameters and counts -> saskatoon_safety_metadata_<stamp>.json."""
        w0, w1 = self.config.window_utc
        meta = {
            "collection_run_utc": datetime.now(timezone.utc).isoformat(),
            "scraper_version": SCRAPER_VERSION,
            "subreddit": self.config.subreddit,
            "window_local": [str(self.config.start_local), str(self.config.end_local)],
            "window_timezone": common.LOCAL_TZ,
            "window_utc": [datetime.fromtimestamp(w0, timezone.utc).isoformat(),
                           datetime.fromtimestamp(w1, timezone.utc).isoformat()],
            "seed_sets": {k: SEED_TERMS[k] for k in self.config.seed_sets},
            "search_sorts": list(self.config.search_sorts),
            "search_time_filter": self.config.search_time_filter,
            "tagging": "whole-word matching; vocabularies from reddit_analysis/scripts/common.py",
            "n_neighbourhoods_tracked": len(SASKATOON_NEIGHBOURHOODS),
            "n_environmental_cue_categories": len(ENVIRONMENTAL_CUE_NAMES),
            "vader_lexicon_adjustments": common.VADER_LEXICON_ADJUSTMENTS,
            "time_fields": f"local time ({common.LOCAL_TZ})",
            "author_hash": "HMAC-SHA-256 with private salt, first 16 hex chars",
            "replace_more_limit": self.config.replace_more_limit,
            "max_comment_depth": self.config.max_comment_depth,
            "max_comments_per_post": self.config.max_comments_per_post,
            "posts_collected": int(len(posts_df)),
            "comments_collected": int(len(comments_df)),
            "comments_in_window": int(comments_df["comment_in_window"].sum()) if not comments_df.empty else 0,
            "posts_by_seed_set_found": (posts_df["found_by_seed_sets"].value_counts().to_dict()
                                        if not posts_df.empty else {}),
            "posts_by_month": (posts_df["month"].value_counts().sort_index().to_dict()
                               if not posts_df.empty else {}),
            "posts_mentioning_a_neighbourhood": int(posts_df["any_neighbourhood"].sum()) if not posts_df.empty else 0,
            "sentiment_available": bool(self.sentiment),
        }
        path = self.config.output_dir / f"saskatoon_safety_metadata_{stamp}.json"
        path.write_text(json.dumps(meta, indent=2, default=str))
        logger.info("Metadata saved: %s", path)

    def _write_gis(self, posts_df: pd.DataFrame, stamp: str) -> None:
        """One row per post x neighbourhood mentioned -> saskatoon_safety_gis_<stamp>.csv."""
        if posts_df.empty:
            return
        ex = posts_df.explode("neighbourhoods_mentioned").rename(
            columns={"neighbourhoods_mentioned": "neighbourhood"})
        ex = ex[ex["neighbourhood"].notna()]
        keep = [c for c in ["id", "neighbourhood", "created_date", "year", "month", "season",
                            "time_of_day", "score", "num_comments", "n_env_cues",
                            "sentiment_compound", "sentiment_category",
                            "sentiment_adj_compound", "sentiment_adj_category"] if c in ex.columns]
        path = self.config.output_dir / f"saskatoon_safety_gis_{stamp}.csv"
        ex[keep].to_csv(path, index=False)
        logger.info("GIS export saved: %s (%d neighbourhood-mentions)", path, len(ex))

    def _write_summary(self, posts_df, comments_df, stamp: str) -> None:
        """Human-readable counts -> saskatoon_safety_summary_<stamp>.txt."""
        path = self.config.output_dir / f"saskatoon_safety_summary_{stamp}.txt"
        lines = ["=" * 70, "ComputerVision_Sentinel | Reddit Crime & Safety Narrative Collection",
                 f"r/{self.config.subreddit} | {self.config.start_local} – {self.config.end_local} "
                 f"(local time) | scraper {SCRAPER_VERSION}", "=" * 70, ""]
        if posts_df.empty:
            lines.append("No posts collected.")
        else:
            lines += [f"Posts: {len(posts_df)}", f"Comments: {len(comments_df)}"
                      + (f" ({int(comments_df['comment_in_window'].sum())} posted inside the window)"
                         if not comments_df.empty else ""), ""]
            lines.append("--- Posts by seed set that found them ---")
            lines += [f"  {k or '(listing only)':16s} {v}" for k, v in posts_df["found_by_seed_sets"].value_counts().items()]
            lines.append("\n--- Posts by month (local) ---")
            lines += [f"  {k:2d}  {v}" for k, v in posts_df["month"].value_counts().sort_index().items()]
            lines.append("\n--- Posts by neighbourhood mentioned ---")
            ex = posts_df.explode("neighbourhoods_mentioned")["neighbourhoods_mentioned"].dropna()
            lines += [f"  {k:28s} {v}" for k, v in ex.value_counts().items()]
            lines.append("\n--- Environmental cues mentioned (posts) ---")
            lines += [f"  {c:14s} {int(posts_df[f'env_{c}'].sum())}" for c in ENVIRONMENTAL_CUE_NAMES]
            if "sentiment_adj_category" in posts_df.columns:
                lines.append("\n--- Sentiment (posts, adjusted VADER) ---")
                lines += [f"  {k:9s} {v}" for k, v in posts_df["sentiment_adj_category"].value_counts().items()]
                lines.append(f"  mean compound: {posts_df['sentiment_adj_compound'].mean():.3f}")
        path.write_text("\n".join(lines) + "\n")
        logger.info("Summary saved: %s", path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

REQUIRED_ENV = {
    "PRAW_CLIENT_ID": "Reddit app client ID",
    "PRAW_CLIENT_SECRET": "Reddit app client secret",
    "COMPUTERVISION_SENTINEL_HASH_SALT": "private random string used to key author hashes",
}


def load_env_file(path: Path) -> None:
    """Minimal .env reader (KEY=VALUE lines); existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def setup_logging(out_dir: Path | None) -> None:
    """Log to the console, and to the run log in out_dir when given."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if out_dir is not None:
        handlers.append(logging.FileHandler(out_dir / "computervision_sentinel_scraper.log"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
                        handlers=handlers, force=True)


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[1], formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--start", default="2026-06-01", help="first day, local time (YYYY-MM-DD)")
    p.add_argument("--end", default="2026-08-31", help="last day inclusive, local time (YYYY-MM-DD)")
    p.add_argument("--out", default=None, help="output folder (default: Data/reddit_<start>_<end>/01_raw_collection)")
    p.add_argument("--seed-sets", default="safety,crime", help="comma list of: " + ",".join(SEED_TERMS))
    p.add_argument("--no-comments", action="store_true", help="skip comment collection")
    p.add_argument("--probe", action="store_true", help="check credentials with one search and exit")
    return p.parse_args(argv)


def main(argv=None) -> None:
    """CLI entry point: check credentials, collect, export."""
    args = parse_args(argv)
    load_env_file(REPO_ROOT / ".env")
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise SystemExit("Missing environment variables (set them or add to "
                         f"{REPO_ROOT / '.env'}):\n" + "\n".join(f"  {k}: {REQUIRED_ENV[k]}" for k in missing))
    creds = {"client_id": os.environ["PRAW_CLIENT_ID"],
             "client_secret": os.environ["PRAW_CLIENT_SECRET"],
             "user_agent": os.getenv("PRAW_USER_AGENT", "ComputerVision_Sentinel/1.0 by /u/ocamporyan")}

    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    seed_sets = tuple(s.strip() for s in args.seed_sets.split(",") if s.strip())
    unknown = set(seed_sets) - set(SEED_TERMS)
    if unknown:
        raise SystemExit(f"Unknown seed set(s): {sorted(unknown)}")

    if args.probe:
        setup_logging(None)
        collector = SaskatoonSafetyCollector(creds, ScraperConfig(start_local=start, end_local=end))
        n = sum(1 for _ in collector.reddit.subreddit("saskatoon").search("safe", sort="new", limit=5))
        logger.info("Credentials OK: probe search returned %d results", n)
        return

    out = Path(args.out) if args.out else REPO_ROOT / "Data" / f"reddit_{start}_{end}" / "01_raw_collection"
    out.mkdir(parents=True, exist_ok=True)
    setup_logging(out)
    config = ScraperConfig(start_local=start, end_local=end, seed_sets=seed_sets,
                           collect_comments=not args.no_comments, output_dir=out)
    collector = SaskatoonSafetyCollector(creds, config)
    logger.info("=" * 70)
    logger.info("ComputerVision_Sentinel | r/%s | %s .. %s (local) | seed sets: %s | sorts: %s",
                config.subreddit, start, end, ",".join(seed_sets), ",".join(config.search_sorts))
    logger.info("=" * 70)
    collector.collect()
    posts_df, comments_df = collector.build_dataframes()
    stamp = collector.export(posts_df, comments_df)
    logger.info("Collection complete (%s): %d posts, %d comments -> %s",
                stamp, len(posts_df), len(comments_df), out)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Interrupted by user — partial outputs may exist.")
