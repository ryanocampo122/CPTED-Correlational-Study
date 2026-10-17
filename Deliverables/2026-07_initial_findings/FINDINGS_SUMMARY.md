# Saskatoon Safety-Perception Analysis — Findings Summary

**Project:** A Privacy-Preserving GeoAI Framework for Urban CPTED Decision Support
**Data window:** 11 June 2025 – 11 June 2026
**Source:** r/saskatoon (Reddit), safety-related posts and comments
**Dataset:** 426 posts · 14,889 comments

---

## What this work covered

Two tasks:

1. **Site identification** — figure out which parts of Saskatoon to focus the pilot on.
2. **Public-perception scan** — understand how people locally talk about safety and which
   environmental conditions they raise.

Both used the same underlying dataset: a year of Saskatoon subreddit activity filtered to
safety-related terms (safety, unsafe, sketchy, scary, dangerous, etc.), with each item scored
for tone (positive / neutral / negative) and tagged for the neighbourhood and environmental
cues it mentions.

---

## Task 1 — Where to focus (site identification)

The neighbourhood picture is more nuanced than a simple "fear map."

| Neighbourhood | Mentions | Overall tone | Read |
|---|---|---|---|
| Riverbank / Meewasin | 46 | Positive (+0.24) | Most-mentioned, but mostly recreation/nature, not fear |
| **Downtown / CBD** | **17** | **Negative (−0.10)** | **Clearest safety-concern cluster; most environment-linked complaints** |
| Place Riel / USask | 6 | Positive (+0.85) | Campus; not a concern area |
| Nutana | 5 | Positive (+0.87) | Not a concern area |
| Broadway | 5 | Positive (+0.82) | Not a concern area |
| Riversdale, Meadowgreen, Downtown Terminal, others | 1–2 each | Negative | Worth noting, but sample too small to rely on |

---

## Task 2 — What people care about (public-perception scan)

**Environmental cues mentioned (across 426 posts):**

| Cue | Posts | Why it matters |
|---|---|---|
| Weather | 172 | Most common; seasonal conditions shape how safe places feel |
| Lighting | 84 | Directly actionable through CPTED design |
| Time of day | 76 | "After dark" is a recurring theme |
| People / crowding | 24 | Presence or absence of others |
| Noise | 15 | Least mentioned |

Weather and lighting dominate — conveniently, lighting is one of the most directly actionable
CPTED levers.

**Time of day:** Evening posts are noticeably more negative (avg. +0.07) than morning,
afternoon, or night posts (all ~+0.30). This is consistent with people feeling less safe in the
evening and supports time-of-day as a meaningful factor in the framework.

**Overall tone:** Posts lean positive (61% positive, 31% negative). Comment threads are more
mixed (46% positive, 31% negative, 22% neutral) — discussion surfaces more concern than the
headline posts alone.

---

## Data-integrity note

The collection log recorded **428 posts / ~15,975 comments** retrieved, while the final saved
dataset holds **426 posts / 14,889 comments**. The difference is attributable to deduplication
and removed/deleted content. It does not affect any of the conclusions above, but is documented
here so the figures reconcile.

## Next steps

- Begin the human-ethics (REB) application with Prof. Kang for the survey/interview component.

