# Face-expression validation study (AI-Hub landmark sample)

A small, controlled study of **evaluation design** on the AI-Hub "안면 인식 랜드마크" *sample*
(10 subjects × 7 expressions × 3 lighting levels = 210 images). It is not a state-of-the-art claim.
Method, results and limitations: [`methodology_cvpr2027.md`](methodology_cvpr2027.md).
Generated numbers: [`results/cvpr2027/RESULTS.md`](../../results/cvpr2027/RESULTS.md).

## Data is not in this repository

The images, JSON annotations and OBJ meshes show real people and are distributed by AI-Hub under
its own terms. **Do not commit them** (they are listed in `.gitignore`). Download the sample from
AI-Hub yourself and keep it outside version control.

> The data was committed to this repository in earlier commits. Removing it from the working
> tree does not remove it from the git history or from existing clones; see the note at the end.

### Expected folder layout

Point `--data-root` (or the `FACE_DATA_ROOT` environment variable) at the folder that contains
`01.원천데이터` and `02.라벨링데이터`. If neither is given, the scripts look for
`dev-YuIK/안면_인식_랜드마크_Sample` relative to the repository root.

```
<data-root>/
├── 01.원천데이터/
│   ├── image/
│   │   └── F1350/ … F1359/            one folder per subject
│   │       └── F1350_01_1_H.png       <subject>_<expression code>_<take>_<light>.png  (1440×1080 RGB)
│   └── 3D data/
│       └── F1350/ … F1359/
│           └── F1350_01_1_H.obj       same stem as the image (not needed for training)
└── 02.라벨링데이터/
    └── F1350/ … F1359/
        └── json/
            └── F1350_01_1_H.json      same stem as the image
```

- Expression codes: `01` Joy, `02` Neutral, `03` Surprise, `04` Disgust, `05` Sadness, `06` Anger, `07` Fear.
- Light codes: `H` highlight, `M` middlelight, `L` lowlight.
- JSON fields used: `expression` (label), `light` (reporting only), `3Dlandmark` (1,220 lines
  `v x y z`), `face` (2,304 lines `f i j k`, 1-indexed). `age`, `gender`, `id`, `proficiency` are
  present and are never used as model inputs.
- Each OBJ holds the same 1,220 vertices and 2,304 faces as its JSON, followed by a second block
  of 1,220 `v` lines with `z = 0` that is identical in every file (see `mesh_provenance.py`).

## Running

From the repository root, with a PyTorch/torchvision build that matches your CUDA or CPU setup:

```powershell
.\.venv\Scripts\python.exe -m pip install -r other-dev/dev-shs/requirements.txt

# 1. Mesh provenance check (seconds, CPU)
.\.venv\Scripts\python.exe other-dev/dev-shs/mesh_provenance.py --data-root <data-root>

# 2. All experiments (hours on one GPU; resumable — finished runs are skipped)
.\.venv\Scripts\python.exe other-dev/dev-shs/run_validation.py --data-root <data-root> --stage all

# 3. Statistics, tables and figures
.\.venv\Scripts\python.exe other-dev/dev-shs/analyze_results.py
```

`run_validation.py --smoke --output-dir <scratch folder>` runs every protocol for one epoch on two
folds as a pipeline check. `--stage` can be `manifest`, `inner`, `loso`, `splits`, `lightout` or `all`.

## What gets written (`results/cvpr2027/`)

| File | Content |
|---|---|
| `split_manifest.csv` | every train/test partition of every protocol, written **before** training (its SHA-256 is in `environment.json`) |
| `environment.json`, `data_summary.json` | package versions, device, git commit, hyper-parameters, seeds; dataset counts (relative paths only) |
| `flip_permutation.json` | left-right vertex permutation diagnostics for each LOSO training template |
| `epoch_selection.csv`, `epoch_selection_inner_runs.csv` | inner-CV accuracy for each candidate epoch count and the selected value |
| `logs/runs.jsonl` | one record per training run: seed, epochs, optimiser steps, per-epoch training loss, test probabilities, seconds |
| `logs/run_stdout.log` | console log of the sweep |
| `predictions_{loso,random,triplet,lightout}.csv` | per-image predictions and class probabilities |
| `mesh_provenance.json` | JSON-vs-OBJ comparison and mesh variation across lighting |
| `analysis/` | summary tables, paired contrasts, confusion matrices, calibration bins, figures |
| `RESULTS.md` | all reported tables, generated from the files above |

No model checkpoints are saved: nothing is selected on validation or test data, so the final-epoch
weights are evaluated once and discarded. `results/legacy_5fold_v1/` holds the superseded first
experiment (5-fold, validation-selected checkpoints, wall-clock schedule) for reference only.

## Data governance note

Untracking a file does not delete it from history. The face images, JSON/OBJ meshes and model
checkpoints are still reachable in earlier commits of this repository and in any clone or fork.
Removing them requires rewriting history (e.g. `git filter-repo`) and force-pushing, which every
collaborator must coordinate, plus confirming with AI-Hub/NIA what redistribution of the sample is
permitted. That decision belongs to the repository owner and the supervisor; it has not been done here.
