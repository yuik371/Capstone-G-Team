# Identity-Disjoint RGB–3D Face Expression Classification

## Methodology draft

### Task and data contract

The linked sample contains paired RGB crops and JSON annotations organized by subject and sample stem. The inspected annotation exposes `expression`, `light`, `age`, `gender`, and an identity field, together with a 1,220-vertex `3Dlandmark` array and 2,304 triangle faces. The sample’s target is therefore an **expression class** (for example, the inspected record is labeled `Joy`); it is not a diagnosis or a facial-condition label. The implementation uses `expression` as the default target and does not use identity, age, gender, or lighting metadata as model inputs. Lighting is retained for nuisance-stratified reporting.

Each RGB image is paired with its JSON annotation by the shared sample stem, e.g. `F1350_01_1_H.png` ↔ `F1350_01_1_H.json`. The annotation’s mesh vertex order and face list define a fixed topology. We treat those 3D mesh vertices as the structured modality; we do not describe them as 2D facial landmarks. The paired 3D data folder is not needed by this protocol.

### Identity-disjoint evaluation

All samples belonging to one subject remain in one partition. The runner uses five deterministic outer folds over subject IDs. In fold $k$, two IDs form the test set, the next two IDs form the validation set, and the remaining six form the training set (for the ten subject folders currently visible in Drive). Each subject is tested in exactly one fold, and its out-of-fold predictions are used for aggregate metrics and visual inspection. If the discovered subject count differs, the runner distributes IDs across five folds and records the exact assignments. It fails if a fold lacks a required partition or a class is absent from training.

The expression-label vocabulary defines the classification task and is held fixed across folds; it is never supplied as an input feature. The class-agnostic mesh template used for geometric-shift measurement is averaged from training subjects only. No image, annotation, or near-duplicate capture from a test identity enters training or validation. The split manifest is written before model fitting.

### Preprocessing and augmentation

RGB crops are converted to RGB, resized so the short side is 256 pixels, center-cropped to $224\times224$, scaled to $[0,1]$, and normalized with ImageNet channel statistics. During training, we use moderate color and brightness perturbations to model illumination variation. A horizontal reflection is applied jointly to the image and the mesh’s lateral coordinate. We avoid independent geometric image warps because the dataset does not provide camera calibration or 2D projections that would let us transform the 3D mesh consistently. Validation and test inputs receive deterministic resizing and normalization only. The ImageNet normalization and inference resizing follow the documented EfficientNet-B0 weight transforms when ImageNet initialization is selected ([TorchVision EfficientNet-B0](https://docs.pytorch.org/vision/main/models/generated/torchvision.models.efficientnet_b0.html)).

For each mesh $V=\{v_i\}_{i=1}^{N}$, we subtract its coordinate-wise median and divide by its RMS radius:

\[
\tilde v_i = \frac{v_i-\operatorname{median}(V)}{\sqrt{N^{-1}\sum_j\|v_j-\operatorname{median}(V)\|_2^2}+\epsilon}.
\]

This removes global translation and isotropic scale while preserving the registered coordinate axes and left–right asymmetry. From the triangle list, we construct the fixed vertex adjacency graph $E$ and add one local descriptor per vertex,

\[
\ell_i=\frac{1}{|\mathcal N(i)|}\sum_{j\in\mathcal N(i)}\|\tilde v_i-\tilde v_j\|_2,
\]

so the structural input is the ordered array $[\tilde v_i,\ell_i]_{i=1}^N$. This gives the MLP access to both canonical vertex coordinates and local mesh geometry.

### Geometric asymmetry and shift

We report two training-independent, per-sample descriptors after the same centering and scale normalization. Let $R_\Pi$ reflect a point across the dataset’s registered midsagittal plane $\Pi$ (the lateral $x=0$ plane after centering). The normalized symmetric Chamfer asymmetry is

\[
A(V)=\frac{1}{2N}\left[\sum_i\min_j\|R_\Pi(\tilde v_i)-\tilde v_j\|_2 + \sum_i\min_j\|\tilde v_i-R_\Pi(\tilde v_j)\|_2\right].
\]

This measures spatial departure from bilateral symmetry without assuming anatomical vertex indices. For geometric shift, let $T_{\mathrm{tr}}$ be the class-agnostic mean mesh computed from training identities, with each identity weighted equally. After rigid Procrustes alignment $Q^*,t^*=\arg\min_{Q\in SO(3),t}\|Q\tilde V+t-T_{\mathrm{tr}}\|_F^2$, we report

\[
G(V;T_{\mathrm{tr}})=\sqrt{\frac{1}{N}\sum_i\|Q^*\tilde v_i+t^*-t_{\mathrm{tr},i}\|_2^2}.
\]

The scalar pair $[A,G]$ is appended to the structural MLP input. $A$ is invariant to reflection augmentation; $G$ is recomputed for the reflected mesh against the same training-only template. Both are reported by class and lighting condition as descriptive geometry measures, not as clinical severity scores.

### Network and fusion

The image branch is an ImageNet-initialized EfficientNet-B0 encoder. Its 1,280-dimensional pooled representation is passed through a task-specific MLP with a 512-unit hidden layer, GELU, dropout, and a $C$-class output layer. The documented ImageNet-1K EfficientNet-B0 weights contain 5,288,548 parameters before the task head ([TorchVision model specification](https://docs.pytorch.org/vision/main/models/generated/torchvision.models.efficientnet_b0.html)); the complete trainable parameter count is measured from the instantiated model and reported for each run.

The structured branch flattens the fixed-order $N\times4$ mesh descriptors and the two geometric scalars, then applies a fully connected network (512 hidden units, LayerNorm, GELU, dropout, and a 128-dimensional projection). For multimodal inference, the 256-dimensional image projection and 128-dimensional mesh projection are concatenated and passed through a 256-unit fusion MLP and the final classifier:

\[
z_I=h_I(f_{\mathrm{EffB0}}(I)),\quad z_M=h_M([\tilde V,\ell,A,G]),\quad
\hat y=\operatorname{softmax}(h_F([z_I;z_M])).
\]

The vision-only baseline uses the same EfficientNet-B0 initialization and task-specific image head, while omitting the mesh branch. Both models use the same folds, image preprocessing, optimizer family, and validation-based checkpoint selection. This isolates the contribution of landmark fusion.

### Optimization and four-hour schedule

Each fold/model run uses AdamW, class-weighted cross-entropy with label smoothing, a cosine learning-rate schedule, and a fixed global seed. The default four-hour wall-clock budget is divided evenly across the ten fold-by-model runs, with 15% reserved for out-of-fold test inference, metric calculation, and artifact export. A run checks its time boundary only after a full epoch, saves the best validation-macro-F1 checkpoint, and never truncates an epoch. The runner logs epoch-level training/validation metrics, elapsed time, hardware and software versions, and the exact fold assignments. If an epoch crosses its slot boundary, it completes and the remaining slots use the remaining budget; wall time is reported rather than assumed.

The test fold is evaluated once for each selected checkpoint. No test result is used for model selection. The five held-out folds produce one out-of-fold prediction per sample and identity. Primary results are macro F1, balanced accuracy, and one-vs-rest macro AUROC; per-class precision–recall curves and average precision are also saved. We additionally report fold-level and lighting-stratified metrics so performance is not hidden by capture-condition imbalance. Uncertainty intervals for macro F1 and balanced accuracy are estimated by resampling held-out identities as clusters (2,000 replicates); with only ten visible identities, these intervals are descriptive and should be interpreted as low-power estimates.

### Deployment measurements

For each fold checkpoint, the runner records total and trainable parameters, checkpoint bytes, and batch-one network-forward latency after warm-up on the recorded device in FP32. It reports median and 95th-percentile latency across repeated in-process calls; image decoding and preprocessing are excluded and should be measured separately for an end-to-end edge deployment result. These are host measurements; a real-device claim requires running the same benchmark on the named target device with its runtime, thread count, precision, and power mode recorded. No latency or accuracy values are asserted in this draft.

### Qualitative analysis

The runner writes a $6\times6$ image with 36 out-of-fold test examples. Each tile shows the RGB crop, an orthographic $x$–$y$ projection of the 3D mesh vertices, ground-truth and predicted expression labels, and prediction confidence; errors are outlined in red. The mesh is shown beside the crop rather than overlaid because the JSON provides 3D coordinates but no camera intrinsics or 2D landmark projection. The grid is intended to expose expression confusions, lighting sensitivity, and systematic failures across held-out identities. It is generated only from real test predictions.

## Run artifacts

`run_validation.py` writes the split manifest, epoch log, fold metrics, out-of-fold predictions, geometry metrics, PR curves, the 6×6 qualitative grid, per-fold checkpoints, and a compact JSON summary under the requested output directory.

The linked Google Drive connector is disabled by the workspace administrator. The folder was inspectable in the browser and Drive prepared an anonymous ZIP, but I could not locate the archive in the workspace or the standard Downloads folder. The four-hour experiment and qualitative grid therefore remain unexecuted; this draft deliberately contains no fabricated empirical results. To run, download the shared folder and use:

```powershell
python -m pip install -r requirements.txt
python run_validation.py --data-root "D:/path/to/dataset" --output-dir "results/cvpr2027" --hours 4
```

## References

1. Mingxing Tan and Quoc V. Le. “EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks.” ICML 2019. [arXiv:1905.11946](https://arxiv.org/abs/1905.11946).
2. TorchVision. [EfficientNet-B0 model and ImageNet weight transforms](https://docs.pytorch.org/vision/main/models/generated/torchvision.models.efficientnet_b0.html).
