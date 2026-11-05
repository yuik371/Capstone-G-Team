# Facial Expression Landmark Fusion: Validation Results

Run date: 2026-11-05T09:23:56Z

## Dataset and protocol

- Samples: 210 across 10 identities.
- Labels: Anger, Disgust, Fear, Joy, Neutral, Sadness, Surprise.
- Face detector found a face in 206/210 samples; 4 used the fixed central crop.
- Five-fold subject-grouped cross-validation; each outer test fold contains two identities.
- Training epochs completed per fold and model: 100.

## Out-of-fold comparison

| Model | Macro F1 | Balanced accuracy | Macro AUROC (OvR) | Macro AP | Parameters | Checkpoint size |
|---|---:|---:|---:|---:|---:|---:|
| vision_only | 0.5864 | 0.6048 | 0.8992 | 0.6879 | 4,386,691 | 17.03 MB |
| fusion | 0.6525 | 0.6619 | 0.9301 | 0.7620 | 6,358,683 | 24.55 MB |

## Paired subject-level comparison

Intervals resample identities jointly for both models, preserving their paired out-of-fold samples.

| Metric | Fusion minus vision-only | Paired identity bootstrap 95% interval |
|---|---:|---:|
| macro_f1 | +0.0661 | [-0.0316, +0.1443] |
| balanced_accuracy | +0.0571 | [-0.0382, +0.1286] |
| macro_auroc_ovr | +0.0309 | [+0.0105, +0.0501] |
| macro_average_precision | +0.0741 | [+0.0295, +0.1222] |

## Landmark geometry by expression

Shift uses the fold-specific training neutral template; asymmetry is normalized reflected-nearest-neighbor distance.

| Expression | Mean shift | Shift SD | Mean left-right asymmetry |
|---|---:|---:|---:|
| Anger | 0.02633 | 0.00661 | 0.00216 |
| Disgust | 0.03749 | 0.00738 | 0.00300 |
| Fear | 0.06148 | 0.01590 | 0.00279 |
| Joy | 0.03691 | 0.00756 | 0.00199 |
| Neutral | 0.01269 | 0.00385 | 0.00151 |
| Sadness | 0.02105 | 0.00539 | 0.00172 |
| Surprise | 0.06923 | 0.01032 | 0.00168 |

## Inference latency

Latency is batch-one model execution after warm-up. Face-crop preprocessing is excluded; detector and fallback counts are reported above.

| Model | Device | p50 (ms) | p95 (ms) |
|---|---|---:|---:|
| vision_only | cuda | 6.26 | 9.16 |
| vision_only | cpu | 17.44 | 18.83 |
| fusion | cuda | 6.16 | 8.75 |
| fusion | cpu | 17.54 | 19.16 |

## Interpretation boundary

This sample is a small facial-expression dataset with ten identities. Results are an engineering benchmark, not evidence of clinical facial-condition diagnosis or population-level generalization. The identity-level bootstrap interval is descriptive and remains uncertain with ten people.

See `metrics.json`, `out_of_fold_predictions.csv`, `precision_recall_*.png`, and `qualitative_test_grid_6x6.png` for the complete artifacts.
