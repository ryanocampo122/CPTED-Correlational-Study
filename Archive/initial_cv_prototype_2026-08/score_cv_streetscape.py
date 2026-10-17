"""
09_score_cv_streetscape.py

Scores each collected street image on CPTED-relevant visual cues using
CLIP zero-shot classification - no training data or labeling needed,
which matters given the timeline. For each cue, CLIP compares the image
embedding against a "present" and "absent" text prompt and returns which
is more similar; the margin between them doubles as a confidence-style
score, so this behaves like a lightweight, explainable image classifier
per cue rather than an opaque single number.

This is the standard low-effort way to get a real CV signal out of street
imagery without a labeled training set (Place Pulse-style CNNs exist but
require sourcing/replicating their trained weights, which is a much
bigger lift for the return you'd get here).

Install: pip install open_clip_torch torch pillow pandas --break-system-packages

Output:
    ../data_pkg_august/05_cv_streetscape/cv_scores_by_image.csv
    ../data_pkg_august/05_cv_streetscape/cv_streetscape_by_site.csv
"""

import glob
import os

import open_clip
import pandas as pd
import torch
from PIL import Image

DATA_DIR = "../data_pkg_august/05_cv_streetscape"
POINTS_CSV = os.path.join(DATA_DIR, "streetview_points.csv")

# Each cue is a (present, absent) prompt pair. Add/edit freely - this is
# the part you'll want to tune against a handful of images by eye before
# trusting the aggregate numbers.
CUE_PROMPTS = {
    "lighting_adequate": (
        "a well-lit street at night with working streetlights",
        "a dark, poorly-lit street with no visible streetlights",
    ),
    "greenery_present": (
        "a street with trees and green landscaping",
        "a bare street with no vegetation",
    ),
    "maintenance_poor": (
        "a neglected street with graffiti, broken windows, or boarded-up buildings",
        "a well-maintained, clean street with no visible damage",
    ),
    "natural_surveillance": (
        "a street lined with building windows and active storefronts facing the street",
        "a street lined with blank walls, fences, or parking lots facing the street",
    ),
}

# Overall score prompt pair - this is the number most directly comparable
# to Reddit mean_sentiment (-1 to 1 style scale).
OVERALL_PROMPTS = (
    "a safe, well-maintained, welcoming street",
    "an unsafe, neglected, uninviting street",
)


def load_model():
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="laion2b_s34b_b79k"
    )
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    model.eval()
    return model, preprocess, tokenizer


def text_embeddings(model, tokenizer, prompts):
    tokens = tokenizer(prompts)
    with torch.no_grad():
        emb = model.encode_text(tokens)
        emb /= emb.norm(dim=-1, keepdim=True)
    return emb


def score_image(model, preprocess, image_path, prompt_pairs, overall_emb):
    image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        img_emb = model.encode_image(image)
        img_emb /= img_emb.norm(dim=-1, keepdim=True)

    result = {}
    for cue, (pos_emb, neg_emb) in prompt_pairs.items():
        sim_pos = (img_emb @ pos_emb.T).item()
        sim_neg = (img_emb @ neg_emb.T).item()
        result[cue] = sim_pos - sim_neg  # positive = cue present

    sim_pos = (img_emb @ overall_emb[0:1].T).item()
    sim_neg = (img_emb @ overall_emb[1:2].T).item()
    result["cv_safety_score"] = sim_pos - sim_neg

    return result


def main():
    points = pd.read_csv(POINTS_CSV)
    model, preprocess, tokenizer = load_model()

    prompt_pairs = {}
    for cue, (pos, neg) in CUE_PROMPTS.items():
        emb = text_embeddings(model, tokenizer, [pos, neg])
        prompt_pairs[cue] = (emb[0:1], emb[1:2])
    overall_emb = text_embeddings(model, tokenizer, list(OVERALL_PROMPTS))

    rows = []
    for _, row in points.iterrows():
        if not os.path.exists(row["image_path"]):
            continue
        scores = score_image(model, preprocess, row["image_path"], prompt_pairs, overall_emb)
        rows.append({"site": row["site"], "image_id": row["image_id"], **scores})
        print(f"scored {row['image_id']}")

    per_image = pd.DataFrame(rows)
    per_image_path = os.path.join(DATA_DIR, "cv_scores_by_image.csv")
    per_image.to_csv(per_image_path, index=False)
    print(f"wrote {len(per_image)} rows -> {per_image_path}")

    by_site = per_image.groupby("site").agg(
        n_images=("image_id", "count"),
        mean_cv_safety_score=("cv_safety_score", "mean"),
        pct_lighting_adequate=("lighting_adequate", lambda s: (s > 0).mean() * 100),
        pct_greenery_present=("greenery_present", lambda s: (s > 0).mean() * 100),
        pct_maintenance_poor=("maintenance_poor", lambda s: (s > 0).mean() * 100),
        pct_natural_surveillance=("natural_surveillance", lambda s: (s > 0).mean() * 100),
    ).reset_index()

    by_site_path = os.path.join(DATA_DIR, "cv_streetscape_by_site.csv")
    by_site.to_csv(by_site_path, index=False)
    print(f"wrote site summary -> {by_site_path}")
    print(by_site)


if __name__ == "__main__":
    main()
