# Facial landmark and image fusion: methodology and validation plan

## Scope of the claim

The supplied sample contains facial-expression labels (`Anger`, `Disgust`, `Fear`, `Joy`, `Neutral`, `Sadness`, and `Surprise`). It does not contain clinical condition labels, diagnoses, or patient outcomes. The experiment therefore measures **identity-held-out facial-expression classification**. It cannot support a claim of facial-condition diagnosis or clinical screening. A CVPR submission should frame the task accordingly and add a substantially larger, externally collected cohort before making population-level or clinical claims.

The sample contains 210 paired photographs and 3D facial meshes from ten identities. Each identity has 21 examples: seven expressions under three illumination labels. The limited number of independent identities, rather than the image count, is the main constraint on generalization.

## Task and inputs

For sample (i), let (I_i) denote the RGB face crop, (P_i = \{p_{i,k}\}_{k=1}^{N}) the ordered 3D facial-mesh vertices, and (y_i \in \{1,\ldots,7\}) the expression label. The JSON files contain (N=1{,}220) `v x y z` vertices and mesh-face indices; they do not provide 2D landmark coordinates. The model consumes the ordered xyz vertices as a structured vector and does not interpret the mesh-face indices as image-space points.

The source photographs are stored rotated by 90 degrees. We rotate them counter-clockwise, detect a frontal face with OpenCV's Haar cascade, expand the detection by 28% of its longer side, make a square crop, and resize it to (224\times224). When the detector returns no face, the pipeline uses a fixed central crop and records that fallback in the manifest. Images are converted to RGB and normalized with ImageNet channel statistics. Train-only augmentation applies synchronized horizontal reflection (including reflection of the mesh x coordinate) and mild brightness, contrast, saturation, and hue jitter. Validation and outer-test samples receive deterministic preprocessing.

For each mesh, we subtract its vertex centroid and divide xyz coordinates by the robust x-axis face width (the 98th minus 2nd percentile). This removes translation and global scale while retaining relative facial proportions. Per-feature standardization is not applied across subjects, which preserves the geometry scale after normalization.

## Identity-disjoint protocol

We use five-fold group cross-validation with two identities in each outer test fold. In each fold, two of the remaining identities form the validation set and the other six form the training set. The same fold assignment is used for both architectures. The code fixes the subject order with seed 2027 and saves the exact assignment in `folds.json`. Every identity appears in one outer test fold, so every recorded test prediction is out of fold. Epoch checkpoint selection uses only validation macro F1 (validation loss breaks ties); the training loop completes the configured number of epochs and the selected checkpoint is evaluated once on that fold's test identities.

Each split contains all seven labels because the source is balanced within identity. This design blocks identity leakage between train, validation, and test. With only ten groups, fold estimates remain noisy; confidence intervals resample identities, not individual photographs, and should be interpreted descriptively.

## Image and landmark encoders

The image encoder is ImageNet-initialized EfficientNet-B0 with its classification layer removed. A 1,280-dimensional pooled feature is projected through a 256-unit MLP layer with batch normalization, GELU, and dropout. The vision-only baseline uses a 192-unit GELU/dropout classifier and the same image encoder, optimizer, augmentation, split, and checkpoint-selection rule.

The structured branch maps the normalized (3N=3{,}660)-dimensional mesh vector through layer normalization and fully connected layers of 512 and 128 units, with GELU and dropout. The fusion model concatenates the 256-dimensional image projection and 128-dimensional landmark embedding, then classifies the 384-dimensional joint representation with a 192-unit MLP and a seven-class output layer. Thus, the baseline and fusion model differ only by the structured encoder and its concatenated representation.

Both models minimize label-smoothed cross entropy (smoothing 0.05) with AdamW and weight decay (10^{-4}). The pretrained backbone is frozen for the first three epochs, then fine-tuned at learning rate (2\times10^{-5}); the trainable heads use learning rate (8\times10^{-4}). A cosine schedule spans all configured epochs. Default execution uses 100 epochs, batch size 16, and seed 2027. The full run, including both model families and all five folds, has a four-hour wall-clock budget.

## Geometric descriptors

We report two mesh-based descriptors alongside classification. They are computed from normalized test meshes without using test labels to fit a reference.

**Left-right asymmetry.** Let (R(x,y,z)=(-x,y,z)) reflect across the mesh x-midline. A topology-free global asymmetry score is

\[
A_{LR}(P) = \frac{1}{N}\sum_{k=1}^{N}\min_{j\in\{1,\dots,N\}}
\left\|p_k-R(p_j)\right\|_2.
\]

We also report the same nearest-reflection distance over lower, middle, and upper thirds of the mesh's y coordinate. These bands are geometric partitions, not anatomically annotated regions; the scores should not be described as clinical measurements.

**Geometric shift from neutral.** For fold (f), let (\mu^{(f)}_0) be the vertex-wise mean of the normalized neutral meshes belonging to the six training identities. For test mesh (P_i), we report

\[
G_i^{(f)} = \sqrt{\frac{1}{N}\sum_{k=1}^{N}
\left\|p_{i,k}-\mu^{(f)}_{0,k}\right\|_2^2}.
\]

The neutral template is estimated from training data only. This score is a descriptive displacement from a training neutral reference; it includes between-identity shape variation and is not a pure expression-change estimate. It is not used as an input to either classifier.

## Evaluation and deployment measurements

We report out-of-fold macro F1, balanced accuracy, macro one-vs-rest AUROC, and macro average precision, with per-class precision-recall curves and confusion matrices. Identity-level bootstrap intervals resample the ten subjects as clusters. We compare EfficientNet-B0 alone against the same backbone with feature-level mesh fusion.

For compactness, we record trainable parameter count and serialized checkpoint size. For inference, we record batch-one p50 and p95 forward-pass latency after warm-up on the available GPU and CPU. These are host measurements; a real-device claim requires an additional benchmark on the intended phone or edge accelerator, including face detection, crop, image resize, and model execution. Results are therefore reported as model-only latency, with face-crop fallback and preprocessing counts documented separately.

## Reproduction

From `dev-YuIK`, install the tested Windows CUDA environment in `emergency_cdss/requirements-face-validation.txt`, then run:

```powershell
python -m pip install -r emergency_cdss/requirements-face-validation.txt
python -m emergency_cdss.scripts.validate_face_multimodal --epochs 100 --batch-size 16 --time-budget-hours 4
```

The script writes the split manifest, per-fold checkpoints, training histories, out-of-fold probabilities, metrics, precision-recall curves, and the requested 6x6 qualitative grid to `outputs/face_multimodal_cvpr_2027/`. The grid shows each test face crop, ground-truth and predicted expression, prediction confidence, and a separate x-y projection of that sample's 3D mesh.

## Pilot run on the supplied sample

The configured run completed all 100 epochs for both models in all five folds (1,000 model-epochs total) in 15.8 minutes on an NVIDIA GeForce RTX 5070 Laptop GPU, within the four-hour allocation. Each model produced one out-of-fold prediction for each of the 210 samples. Face detection succeeded on 206 images; four used the logged central-crop fallback.

| Model | Macro F1 | Balanced accuracy | Macro AUROC (OvR) | Macro AP | Parameters | Checkpoint size | CUDA p50 / p95 | CPU p50 / p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| EfficientNet-B0 vision-only | 0.5864 | 0.6048 | 0.8992 | 0.6879 | 4.39M | 17.03 MB | 6.26 / 9.16 ms | 17.44 / 18.83 ms |
| EfficientNet-B0 + mesh fusion | 0.6525 | 0.6619 | 0.9301 | 0.7620 | 6.36M | 24.55 MB | 6.16 / 8.75 ms | 17.54 / 19.16 ms |

The paired identity-cluster bootstrap estimated fusion-minus-vision differences of +0.0661 macro F1 (95% interval ([-0.0316, 0.1443])), +0.0571 balanced accuracy (([-0.0382, 0.1286])), +0.0309 macro AUROC (([0.0105, 0.0501])), and +0.0741 macro AP (([0.0295, 0.1222])). The F1 and balanced-accuracy intervals include zero; the sample does not establish a reliable classification improvement. The AUROC and AP intervals are positive in this bootstrap, but ten identities are still too few for a strong generalization claim. Fusion increases parameters by about 45%; measured batch-one latency on this host was similar for the two models. Latency excludes image decoding, face detection, cropping, and any mobile-runtime conversion.

The machine-readable per-class metrics, identity bootstrap intervals, geometric analyses, and full histories are in `outputs/face_multimodal_cvpr_2027/metrics.json`. The 6x6 grid and PR curves are generated artifacts, not hand-selected illustrations.

## Evidence required for a CVPR submission

The current ten-identity sample is suitable for validating the pipeline and checking failure cases, not for a high-confidence empirical claim. A submission should add more independent identities, a locked external test set, repeated group-level uncertainty estimates, ablations (image-only, mesh-only, fusion, and geometry descriptors), robustness analyses by illumination and demographic strata, calibrated performance, and measured inference on the stated edge hardware. Any reported result must use the generated metrics rather than a planned or illustrative value.
