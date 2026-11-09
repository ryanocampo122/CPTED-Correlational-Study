# Street images for the study (November 2026)

The full-scale computer-vision steps, built on the pilot's tools (`Scripts/cv_pilot/pilot_lib.py`). Outputs go to
`Data/cv_study_2026-11/` (its README lists every file); method and results: `Docs/cv_pipeline.md`.

| Script | Does | Needs |
|---|---|---|
| `images.py` | Decision D1 at every CBD sample point: the newest Mapillary image from 2020 on within 30 m whose camera faces along the point's road (within 30°); bridge and freeway points excluded; each panorama cut into two side views. `--recrop-to <folder>` cuts the side views again, offline, from the committed panoramas | Mapillary token (`~/.config/computervision_sentinel/secrets.env`) |
| `models.py` | Mask2Former (Swin-L, Mapillary Vistas, panoptic, pinned revision) for class shares and object counts, and CLIP for land-use type and cues, on every side view; per-segment indicators. The camera car of the 2023 panoramas is left out of every share | the two models (downloaded once into `~/.cache/huggingface/`, ~0.9 GB and ~0.6 GB); ~11 min on an Apple GPU |
| `validation.py` | `sample`: draws the 150 side views for blind labelling (30 shared with a second coder) by a fixed rule; `score`: precision, recall, F1 per cue and kappa between coders, once the sheets are filled in | nothing |

```bash
.venv/bin/python Scripts/cv_study/images.py
.venv/bin/python Scripts/cv_study/models.py
.venv/bin/python Scripts/cv_study/validation.py sample
.venv/bin/python Scripts/cv_study/validation.py score
.venv/bin/python Scripts/cv_study/tests/test_cv_study.py        # offline tests
```

Every script takes `--out` (and `models.py`/`validation.py` take `--study`) so `./flight` can rebuild everything in its
own folder and compare it with the published files. A repeat run of `models.py` on the same machine writes identical
files; nothing it produces is used until it passes the label check (`Docs/validation_plan.md`).
