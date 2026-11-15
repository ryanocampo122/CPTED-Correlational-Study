#!/usr/bin/env python3
"""
load_models.py
==============
CPTED Vision | Stage 3 of ./flight: load the two models, smoke-test them, record what was loaded

  CLIP   openai/clip-vit-base-patch32 at the pinned revision (pilot_lib.CLIP_REVISION) through
         Scripts/cv_pilot/pilot_lib.ClipEncoder (the class pilot.py score
         uses), scored on one published pilot image with the prompts in clip_prompts.json
  VADER  stock and adjusted lexicons through Scripts/reddit_analysis/scripts/common.py (what the collector and
         the analysis use), scored on fixed test sentences

Writes one JSON (--out): library versions, the model revision and size, the device, lexicon hashes, the smoke-test
outputs and a PASS/FAIL per model. Exit code 1 if either model fails to load or fails its smoke test.

USAGE (repository root):  .venv/bin/python Scripts/flight/load_models.py --out <models.json>
  --fetch-only   stage 1 of ./flight: make sure the pinned CLIP files are in the Hugging Face cache
                 (downloading them if not) and report where; no smoke tests
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as md
import json
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Scripts" / "cv_pilot"))
sys.path.insert(0, str(REPO / "Scripts" / "reddit_analysis" / "scripts"))
import pilot_lib as L  # noqa: E402

PILOT_IMAGES = REPO / "Data" / "cv_pilot_2026-10" / "cbd_latest_imagery" / "images"
# (sentence, what the adjusted lexicon must do with it)
VADER_TESTS = [
    ("Is it safe to walk downtown at night?", "unchanged: 'safe' keeps its stock score"),
    ("Downtown feels unsafe after dark.", "negative: 'unsafe' added at -1.9"),
    ("That parkade is sketchy.", "negative: 'sketchy' added at -1.5"),
    ("I was afraid to walk past the bus mall.", "more negative: 'afraid' added at -1.9"),
    ("Community safety meeting at the library tonight.", "neutral: 'safety' removed (it names the topic)"),
]


def version(pkg: str) -> str:
    try:
        return md.version(pkg)
    except md.PackageNotFoundError:
        return "not installed"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_clip(model_name: str, revision: str) -> dict:
    """The pinned CLIP files in the Hugging Face cache, downloaded if missing: where they are and their size."""
    from huggingface_hub import try_to_load_from_cache
    from transformers import CLIPModel, CLIPProcessor

    t0 = time.time()
    CLIPModel.from_pretrained(model_name, revision=revision)
    CLIPProcessor.from_pretrained(model_name, revision=revision)
    config = try_to_load_from_cache(model_name, "config.json", revision=revision)
    folder = Path(config).parent if isinstance(config, str) else None
    files = sorted(folder.iterdir()) if folder else []
    return {"model": model_name, "revision": revision, "cache_folder": str(folder),
            "files": [f.name for f in files], "megabytes": round(sum(f.stat().st_size for f in files) / 1e6),
            "seconds": round(time.time() - t0, 1), "status": "PASS" if folder else "FAIL"}


def load_clip(model_name: str, revision: str) -> dict:
    """Load CLIP once, score one published pilot image, and check the outputs are sane."""
    import numpy as np
    from PIL import Image

    t0 = time.time()
    enc = L.ClipEncoder(model_name, revision=revision)
    load_s = time.time() - t0
    prompts = L.load_prompts()
    scorer = L.ClipScorer(enc, prompts, views=3)
    scorer.prepare()
    image = sorted(p for p in PILOT_IMAGES.glob("*.jpg") if not p.stem.endswith("_left"))[0]
    t1 = time.time()
    scores = scorer.score(Image.open(image).convert("RGB"))
    text = enc.encode_texts(["a photo of a street"])
    typ = [v for k, v in scores.items() if k.startswith("typ_")]
    checks = {
        "pinned_revision_loaded": getattr(enc.model.config, "_commit_hash", None) == revision,
        "embedding_unit_norm": bool(abs(float(np.linalg.norm(text[0])) - 1) < 1e-6),
        "typology_probabilities_sum_to_1": bool(abs(sum(typ) - 1) < 0.01),
        "cue_probabilities_in_0_1": all(0 <= v <= 1 for k, v in scores.items() if k.startswith("cue_")),
    }
    return {
        "model": model_name,
        "revision": getattr(enc.model.config, "_commit_hash", None),
        "parameters": int(sum(p.numel() for p in enc.model.parameters())),
        "embedding_dim": int(text.shape[1]),
        "device": enc.device,
        "logit_scale": round(enc.logit_scale, 4),
        "load_seconds": round(load_s, 1),
        "prompts_file": "Scripts/cv_pilot/clip_prompts.json",
        "prompts_sha256": sha256(REPO / "Scripts" / "cv_pilot" / "clip_prompts.json"),
        "typology_labels": len(typ),
        "cues": len([k for k in scores if k.startswith("cue_") and k.endswith("_mean")]),
        "smoke_test": {"image": str(image.relative_to(REPO)), "seconds": round(time.time() - t1, 2),
                       "typology_top1": scores["typology_top1"], "typology_top1_prob": scores["typology_top1_prob"],
                       "checks": checks},
        "libs": {"torch": version("torch"), "transformers": version("transformers"), "pillow": version("pillow")},
        "status": "PASS" if all(checks.values()) else "FAIL",
    }


def load_vader() -> dict:
    """Load stock and adjusted VADER from common.py and check the lexicon adjustments took effect."""
    import vaderSentiment
    import common as c

    stock, adj = c._vader(False), c._vader(True)
    lex_file = Path(vaderSentiment.__file__).resolve().parent / "vader_lexicon.txt"
    rows = []
    for text, expect in VADER_TESTS:
        rows.append({"text": text, "expected": expect,
                     "stock": stock.polarity_scores(text)["compound"],
                     "adjusted": adj.polarity_scores(text)["compound"]})
    by = {r["text"]: r for r in rows}
    checks = {
        "adjustments_applied": all(
            (w not in adj.lexicon) if v == 0.0 else adj.lexicon.get(w) == v
            for w, v in c.VADER_LEXICON_ADJUSTMENTS.items()),
        "stock_lexicon_untouched": stock.lexicon.get("safety") is not None and "unsafe" not in stock.lexicon,
        "safe_unchanged": by[VADER_TESTS[0][0]]["stock"] == by[VADER_TESTS[0][0]]["adjusted"],
        "unsafe_negative": by[VADER_TESTS[1][0]]["adjusted"] <= -0.05,
        "sketchy_negative": by[VADER_TESTS[2][0]]["adjusted"] <= -0.05,
        "afraid_more_negative": by[VADER_TESTS[3][0]]["adjusted"] < by[VADER_TESTS[3][0]]["stock"],
        "safety_neutral": abs(by[VADER_TESTS[4][0]]["adjusted"]) < 0.05,
    }
    return {
        "package": "vaderSentiment", "version": version("vaderSentiment"),
        "lexicon_file": lex_file.name, "lexicon_sha256": sha256(lex_file),
        "lexicon_entries_stock": len(stock.lexicon), "lexicon_entries_adjusted": len(adj.lexicon),
        "adjustments": c.VADER_LEXICON_ADJUSTMENTS, "adjustments_source": "Scripts/reddit_analysis/scripts/common.py",
        "smoke_test": {"sentences": rows, "checks": checks},
        "status": "PASS" if all(checks.values()) else "FAIL",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="models JSON to write")
    ap.add_argument("--clip-model", default=L.CLIP_MODEL)
    ap.add_argument("--clip-revision", default=L.CLIP_REVISION)
    ap.add_argument("--fetch-only", action="store_true", help="only make sure the pinned CLIP files are present")
    a = ap.parse_args()
    out = {"python": sys.version.split()[0]}
    if a.fetch_only:
        try:
            out["clip"] = fetch_clip(a.clip_model, a.clip_revision)
        except Exception as e:                              # noqa: BLE001
            traceback.print_exc()
            out["clip"] = {"model": a.clip_model, "revision": a.clip_revision, "status": "FAIL",
                           "error": f"{type(e).__name__}: {e}"}
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))
        return 0 if out["clip"]["status"] == "PASS" else 1
    for name, fn in (("vader", load_vader), ("clip", lambda: load_clip(a.clip_model, a.clip_revision))):
        try:
            out[name] = fn()
        except Exception as e:                              # noqa: BLE001
            traceback.print_exc()
            out[name] = {"status": "FAIL", "error": f"{type(e).__name__}: {e}"}
        print(f"[models] {name}: {out[name]['status']}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, indent=2, default=str))
    return 0 if all(out[k]["status"] == "PASS" for k in ("vader", "clip")) else 1


if __name__ == "__main__":
    sys.exit(main())
