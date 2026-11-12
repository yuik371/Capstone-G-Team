# What can 10 subjects tell us? A controlled evaluation study of RGB and 3D-mesh expression classification

*Method, executed experiments, results and limitations. Every number below is copied from a saved
artifact under `results/cvpr2027/`; the file is named next to each table.*

## 1. Scope and claims

This is a study of **experimental design**, not a new method and not a state-of-the-art claim.
It uses only the public *sample* of the AI-Hub face-landmark dataset: 10 subjects (F1350–F1359),
7 instructed expressions, 3 lighting levels, 210 images. The full dataset was not available, and
nothing here says anything about it.

The first version of this work claimed that fusing a 3D mesh with the image improves expression
classification. That claim was not supported (79.05% vs 79.52% pooled accuracy, 13 vs 14 discordant
images; `results/legacy_5fold_v1/`). It is replaced by three questions that 10 subjects *can*
inform, and one secondary question:

- **Q1.** How much does an image-level random split inflate accuracy compared with subject-disjoint evaluation?
- **Q2.** Does the mesh carry expression information, and does it still do so after identity is removed?
- **Q3.** How well does each model generalise to a lighting level it never saw in training?
- **Secondary.** Does image + mesh fusion beat the image alone? This is claimed only if the 95% interval
  of the paired subject-level difference excludes zero.

The labels are *instructed (posed) expression categories*. The task is recovering the instructed
category, not recognising felt emotion.

## 2. Data and mesh provenance

Each image `F13xx_<expr>_1_<light>.png` (1440×1080 RGB) has a JSON annotation with the same stem
that holds `expression`, `light`, and a `3Dlandmark` array of 1,220 vertices with a `face` list of
2,304 triangles. The topology is identical in all 210 files. `age`, `gender` and `id` are present
and never used as inputs; `light` is used only for splitting and reporting. The folder layout is
documented in `README.md`; the data itself is not in the repository.

A capture **triplet** is the three lighting variants of one subject × expression. There are 70
triplets, 7 per subject.

**Provenance check** (`mesh_provenance.py` → `results/cvpr2027/mesh_provenance.json`):

| Check | Result |
|---|---|
| JSON `3Dlandmark` vs first 1,220 `v` lines of the same-stem OBJ | bit-identical in 210 / 210 files (max abs difference 0.0); face lists identical in 210 / 210 |
| Remaining 1,220 `v` lines of each OBJ | `z = 0` everywhere, coordinates in about [0.5, 99.5] × [3.7, 90.1], **identical in all 210 files** |
| Same subject, same expression, different light: bit-identical mesh pairs | 0 of 210 pairs |
| RMS vertex distance after rigid alignment (normalised units), median | different light 0.016; different expression 0.092; different subject 0.049 |
| Light-to-expression ratio of those medians | 0.18 |
| Is the light-to-light displacement field shared across subjects? (mean pairwise cosine; triplet-swap permutation p) | H–L 0.015 (p = 0.31), H–M 0.002 (p = 0.40), L–M 0.099 (p = 0.12) |

What this implies:

1. **The OBJ adds nothing.** The JSON vertices are a copy of the OBJ vertices. There is no second,
   independent 3D measurement to validate the mesh against. The extra OBJ block is a constant 2D
   layout shared by every file (most plausibly a texture/UV template), not per-image data.
2. **Each image has its own mesh.** The mesh is not one scan per expression reused for the three
   lighting images. The three meshes of a triplet differ by about 18% of a typical
   expression-to-expression difference, with no detectable common direction across subjects.
3. **Scan or fit is still unknown.** A fixed 1,220-vertex topology with an exact left–right vertex
   correspondence (46 midline vertices, 587 mirrored pairs; `flip_permutation.json`) means the mesh
   is a *registered template*, not a raw scan. Whether that template was registered to a depth
   capture or fitted to the RGB image cannot be decided from these files. Per-image variation is
   consistent with either (three separate captures, or three separate fits). If it was fitted from
   the image, the mesh is a re-encoding of pixel information, and "RGB + 3D" is not two modalities.
   We could not rule this out, so no multimodality claim is made.
4. **Consequence for the experiments.** Because the three meshes of a triplet are near-duplicates,
   a mesh model evaluated with an image-level random split sees an almost identical copy of each
   test mesh during training. Q1 measures this directly.

## 3. Evaluation protocols

All partitions for all protocols and seeds are written to `split_manifest.csv` **before any
training starts**; its SHA-256 is stored in `environment.json`. The script asserts that no
subject (or triplet, or held-out light) crosses a partition that is supposed to exclude it.

**Leave-one-subject-out (LOSO, primary).** 10 folds. Each fold trains on 9 subjects (189 images)
and tests on the remaining subject (21 images). There is no validation partition.

**Fixed training length, chosen by inner cross-validation on training subjects only.** For each
outer fold, the 9 training subjects are split into 3 inner folds of 3 subjects. For each candidate
epoch count a model is trained on 6 subjects and scored on the other 3. The epoch count with the
highest mean inner accuracy is selected (ties → fewer epochs) and used to retrain on all 9
subjects. Candidates: 10 / 20 / 30 epochs for models with an image encoder, 25 / 50 / 100 / 200
for the mesh-only MLP. The held-out test subject takes no part in this choice. Selection results:
`epoch_selection.csv`. Ablation and control variants reuse the epoch count of their default
configuration, so that the ablated factor is the only difference.

**No checkpoint selection.** Every run trains for its fixed number of epochs and is evaluated once
with its **final-epoch weights**. No checkpoints are saved, and no test or validation score
influences which weights are reported.

**Step-based schedule.** The learning rate follows a cosine from 3e-4 to 0 over
`epochs × ceil(n_train / 16)` optimiser steps. It depends on the step count only, never on
wall-clock time, so every model in a fold gets the same schedule on any hardware.

**Seeds.** Five seeds (2027–2031) for every LOSO condition. The LOSO partition is deterministic, so
seeds vary initialisation of the new layers, data order and augmentation. Within one seed and
fold, all conditions share the same data order and augmentation draws (common random numbers),
which makes paired comparisons tighter.

**No cross-fold ensembles.** Models trained in different folds are never combined and scored
out-of-fold: a fold-*k* model has trained on the test subjects of every other fold, so such an
ensemble would not be subject-disjoint.

**Split comparison (Q1).** Two deliberately weaker protocols with the same train/test sizes
(189 / 21 per fold, 10 folds, 5 seeds, a new partition per seed):
- `random`: image-level split stratified by expression. The same person, and usually the other
  lighting variants of the same capture, are in training.
- `triplet`: the three lighting variants of a capture are kept together, but the person is still
  in training.

These protocols have no clean set of "training subjects", so they reuse the lower median of the
LOSO-selected epoch counts for the same model.

**Leave-one-light-out (Q3).** Inside each LOSO fold, one lighting level is also removed from
training (9 subjects × 2 lights = 126 images). The model is tested on all 21 images of the
held-out subject, which gives accuracy on the unseen light and on the two seen lights. Epoch
counts are those selected for the same outer fold. 3 lights × 10 folds × 5 seeds.

## 4. Inputs

**Image.** Short side resized to 256 (bicubic), centre crop 224, ImageNet normalisation. Training
augmentation: horizontal flip (p = 0.5) and per-image brightness (±20%), contrast (±20%) and
saturation (±15%) jitter. Test images get no augmentation.

**Mesh.** Each mesh is median-centred and divided by its RMS radius. Per vertex the input is
`[x, y, z, ℓ]`, where ℓ is the mean length of the edges incident to that vertex. Two scalars are
appended: **A**, the symmetric Chamfer distance between the mesh and its x-mirror, and **G**, the RMS
distance to a mean template after rotation-only Procrustes alignment. The template is the mean
mesh of the **training** samples of that fold (training identities weighted equally). All mesh
inputs are standardised per feature with the training-set mean and standard deviation.

**Identity-removed mesh (`neutral` mode).** Each mesh is rigidly aligned to the *Neutral* mesh of
the same subject under the same lighting level, and that Neutral mesh is subtracted. The inputs
become per-vertex displacement, the change in ℓ, the change in A, and the RMS displacement. This
uses a labelled Neutral capture of the test subject, so it is **not** a blind test-time procedure,
and Neutral samples become (near-)zero vectors that are trivially recognisable. Accuracy without
the Neutral class is therefore reported alongside.

**Horizontal flip of the mesh.** The first version negated x but left the vertex order unchanged,
which puts left-side anatomy at right-side indices; it also fitted G with a rotation-only alignment
of a mirror-image mesh. The corrected flip:

1. Mirror the training template in x and match it one-to-one to itself with the Hungarian
   algorithm (`scipy.optimize.linear_sum_assignment` on squared distances).
2. Verify that the resulting permutation is an involution (applying it twice gives the identity);
   the run aborts otherwise.
3. Flip a mesh by negating x **and** re-indexing vertices by the permutation; recompute ℓ and G
   for the flipped mesh.

Result (`flip_permutation.json`): the permutation is an involution in all 10 LOSO training
templates, identical across folds, with 46 fixed (midline) vertices and 587 swapped pairs; the
matching residual is 0.004 against a template RMS radius of 0.99; Hungarian and nearest-neighbour
matching agree.

## 5. Models and conditions

Image encoder: ImageNet-initialised EfficientNet-B0, fine-tuned end to end. Mesh branch: an MLP on
the flattened 1,220 × 4 + 2 inputs (512 → LayerNorm → GELU → dropout → 128). Fusion is late
concatenation of a 256-d image projection and the 128-d mesh code. Optimiser: AdamW (weight decay
1e-4), batch 16, class-weighted cross-entropy with label smoothing 0.05, FP32.

| Condition | Inputs | Flip | Purpose |
|---|---|---|---|
| `image_flip` | image | image | image-only baseline |
| `image_noflip` | image | none | flip ablation |
| `mesh_raw` | mesh | permuted | mesh-only baseline (Q2) |
| `mesh_naiveflip` / `mesh_noflip` | mesh | naive / none | flip ablation |
| `mesh_shuffled` | mesh of a *different expression* of the same subject and light | permuted | negative control: must be near chance |
| `mesh_neutral` | Neutral-subtracted mesh | permuted | Q2 after identity removal |
| `scalars` | image + [A, G] only | permuted | do the two scalars alone help? |
| `fused_perm` | image + mesh | permuted | fusion |
| `fused_naiveflip` / `fused_noflip` | image + mesh | naive / none | flip ablation |
| `fused_shuffled` | image + shuffled mesh | permuted | does fusion use the mesh's expression content? |
| `fused_neutral` | image + Neutral-subtracted mesh | permuted | fusion after identity removal |

In the shuffled controls the donor expression is redrawn at random for every training sample and
fixed (seeded) at test time. A shuffled mesh still tells the model which expression the sample is
*not*, so its ceiling is slightly above 1/7.

## 6. Statistics

- **Unit of analysis: the subject.** Predictions are reduced to one accuracy per held-out subject
  (averaged over seeds). All intervals and tests use those 10 values or 10 paired differences.
  The 210 images are never treated as independent.
- **Paired differences** are reported with the mean, Cohen's d_z, a 95% subject-bootstrap interval
  (10,000 resamples), a 95% t interval (9 d.f.), an exact sign-flip permutation p-value, a Wilcoxon
  signed-rank p-value, and the count of subjects won / lost / tied.
- **Low power, stated plainly.** With 10 pairs the smallest possible two-sided sign-flip p-value is
  0.002, the bootstrap with 10 clusters is known to be too narrow, and a non-significant test is
  not evidence of no effect. Holm-adjusted p-values are given because many contrasts are reported.
- **Seeds**: accuracy is also reported as mean ± SD over the 5 seeds. That SD measures training
  noise only, not uncertainty about new subjects.
- **Capture triplets**: for lighting questions, comparisons are made within subject, and the
  fraction of triplets whose three lighting variants receive the same prediction is reported.
- **Calibration**: expected calibration error (10 bins) per seed on the pooled out-of-fold
  predictions. It pools 10 different fold models and is a coarse estimate.

## 7. Results

⟨pending: filled in from `results/cvpr2027/RESULTS.md` once the sweep and analysis have finished⟩

## 8. Limitations

- **10 identities.** Every estimate is about these 10 people. Intervals are wide, tests are weak,
  and one unusual subject moves a mean by several points. All subject IDs start with `F`; the
  sample's demographic spread was not analysed and cannot be assumed to be representative.
- **Sample only.** Nothing here transfers to the full AI-Hub dataset without rerunning on it.
- **The mesh is required at inference.** Every mesh-using model consumes the dataset's own 3D
  annotation. The repository contains no method to obtain that mesh from a camera image, so these
  models cannot run on RGB alone.
- **No end-to-end latency.** The first version reported network-forward latency only. Mesh
  acquisition, image decoding and preprocessing were not measured, and mesh acquisition would
  dominate. No latency or edge-deployment claim is made, and no latency was re-measured.
- **Mesh origin unknown** (Section 2). The mesh may be derived from the image.
- **Neutral subtraction needs a labelled Neutral capture** of the test subject, at the same
  lighting level.
- **Posed labels.** Categories are instructed poses; Anger/Sadness-type confusions may reflect
  ambiguous posing as much as model error.
- **Epoch selection is noisy.** The inner CV scores 3 subjects per fold; the selected epoch count
  varies between outer folds for that reason.
- **One architecture, one hyper-parameter setting.** No pretrained FER backbone, no
  FLAME/DECA/SMIRK expression parameters, no graph/mesh network, no early or attention fusion. A
  null result for this late-concatenation model says nothing about those.
- **Not corrected for everything.** Many contrasts are reported from one small dataset; treat them
  as descriptive.
- **Data governance.** The face images and meshes were committed to this repository earlier and
  are still in its history (see `README.md`).

## 9. What changed from the first version (`results/legacy_5fold_v1/`)

| First version | Now |
|---|---|
| 5-fold, 6 train / 2 val / 2 test subjects | 10-fold leave-one-subject-out, no validation subjects |
| Best-validation-F1 checkpoint (42 validation images) | Fixed epochs from inner CV on training subjects; final-epoch weights |
| Cosine schedule driven by wall-clock time; 99–141 epochs per run | Cosine schedule driven by optimiser steps |
| 1 seed | 5 seeds |
| Vision vs fused only | 13 conditions incl. mesh-only, scalars-only, shuffled and Neutral-subtracted controls |
| Flip negated x without permuting vertices | Verified left–right permutation; three-way flip ablation |
| Per-model bootstrap CIs over pooled images | Subject-level paired differences with CIs and exact tests |
| Latency table | Removed (no end-to-end measurement) |
| Hue jitter and CPU PIL augmentation | Brightness/contrast/saturation jitter on GPU (no hue) |
| Raw mesh coordinates fed to the MLP | Mesh inputs standardised with training-set statistics |

The legacy numbers are kept only as the record of what was first reported. They are not comparable
with the tables above (different folds, selection rule, schedule and input scaling).

## 10. Reproduction

See `README.md`. Environment, seeds, hyper-parameters and the git commit of the run are in
`results/cvpr2027/environment.json`; per-run logs (seed, epochs, optimiser steps, per-epoch
training loss, test probabilities, seconds) are in `results/cvpr2027/logs/runs.jsonl`.

## References

1. M. Tan and Q. V. Le. "EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks." ICML 2019. [arXiv:1905.11946](https://arxiv.org/abs/1905.11946).
2. G. C. Cawley and N. L. C. Talbot. "On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation." JMLR 11, 2010.
3. G. Varoquaux. "Cross-validation failure: small sample sizes lead to large error bars." NeuroImage, 2018.
4. S. Kapoor and A. Narayanan. "Leakage and the reproducibility crisis in machine-learning-based science." Patterns, 2023.
5. L. F. Barrett et al. "Emotional Expressions Reconsidered." Psychological Science in the Public Interest, 2019.
