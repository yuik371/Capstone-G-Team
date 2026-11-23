"""Classification metrics shared by training and evaluation scripts."""

from __future__ import annotations

import math
from typing import Any, Sequence

try:
    import torch
except ImportError as exc:  # pragma: no cover - exercised only without dependencies
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install emergency_cdss/requirements.txt."
    ) from exc


def classification_metrics(
    targets: Sequence[int],
    predictions: Sequence[int],
    *,
    num_classes: int = 4,
    class_names: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return accuracy, macro-F1, balanced accuracy, and a confusion matrix.

    ``balanced_accuracy`` is the mean per-class recall. It is included because
    raw accuracy can hide poor performance on rare emergency classes.
    """

    if len(targets) != len(predictions):
        raise ValueError("targets and predictions must have the same length")
    if num_classes < 1:
        raise ValueError("num_classes must be positive")
    if class_names is None:
        class_names = tuple(str(index) for index in range(num_classes))
    if len(class_names) != num_classes:
        raise ValueError("class_names length must equal num_classes")

    confusion = torch.zeros((num_classes, num_classes), dtype=torch.int64)
    for target, prediction in zip(targets, predictions):
        if not 0 <= target < num_classes or not 0 <= prediction < num_classes:
            raise ValueError("target and prediction labels must be valid class indices")
        confusion[target, prediction] += 1

    true_positive = confusion.diag().to(torch.float32)
    support = confusion.sum(dim=1).to(torch.float32)
    predicted = confusion.sum(dim=0).to(torch.float32)
    recall = torch.where(support > 0, true_positive / support, torch.zeros_like(support))
    precision = torch.where(
        predicted > 0, true_positive / predicted, torch.zeros_like(predicted)
    )
    f1_denominator = precision + recall
    f1 = torch.where(
        f1_denominator > 0,
        2 * precision * recall / f1_denominator,
        torch.zeros_like(f1_denominator),
    )
    total = int(confusion.sum().item())
    accuracy = float(true_positive.sum().item() / total) if total else 0.0
    return {
        "accuracy": accuracy,
        "macro_f1": float(f1.mean().item()),
        "balanced_accuracy": float(recall.mean().item()),
        "per_class_precision": {
            class_name: float(precision[index].item())
            for index, class_name in enumerate(class_names)
        },
        "per_class_recall": {
            class_name: float(recall[index].item())
            for index, class_name in enumerate(class_names)
        },
        "per_class_f1": {
            class_name: float(f1[index].item())
            for index, class_name in enumerate(class_names)
        },
        "per_class_support": {
            class_name: int(support[index].item())
            for index, class_name in enumerate(class_names)
        },
        "confusion_matrix": confusion.tolist(),
    }


def _binary_curve(
    labels: Sequence[int],
    scores: Sequence[float],
) -> tuple[list[float], list[float], float]:
    """Return FPR/TPR and ROC area using only the Python standard library."""

    positives = sum(1 for label in labels if label == 1)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return [], [], float("nan")
    order = sorted(range(len(scores)), key=lambda index: float(scores[index]), reverse=True)
    tps = fps = 0
    fpr = [0.0]
    tpr = [0.0]
    previous_score: float | None = None
    for index in order:
        score = float(scores[index])
        if previous_score is not None and score != previous_score:
            fpr.append(fps / negatives)
            tpr.append(tps / positives)
        if labels[index] == 1:
            tps += 1
        else:
            fps += 1
        previous_score = score
    fpr.append(1.0)
    tpr.append(1.0)
    area = sum(
        (fpr[index] - fpr[index - 1]) * (tpr[index] + tpr[index - 1]) / 2.0
        for index in range(1, len(fpr))
    )
    return fpr, tpr, float(area)


def _binary_pr_curve(
    labels: Sequence[int],
    scores: Sequence[float],
) -> tuple[list[float], list[float]]:
    positives = sum(1 for label in labels if label == 1)
    if positives == 0:
        return [], []
    order = sorted(range(len(scores)), key=lambda index: float(scores[index]), reverse=True)
    true_positives = false_positives = 0
    precision = [1.0]
    recall = [0.0]
    for index in order:
        if labels[index] == 1:
            true_positives += 1
        else:
            false_positives += 1
        precision.append(true_positives / max(1, true_positives + false_positives))
        recall.append(true_positives / positives)
    return recall, precision


def probabilistic_metrics(
    targets: Sequence[int],
    probabilities: Sequence[Sequence[float]],
    *,
    num_classes: int,
    class_names: Sequence[str],
) -> dict[str, Any]:
    """Add macro AUROC and per-class PR curves to discrete metrics."""

    if len(targets) != len(probabilities):
        raise ValueError("targets and probabilities must have the same length")
    if len(class_names) != num_classes:
        raise ValueError("class_names length must equal num_classes")
    aurocs: dict[str, float] = {}
    pr_curves: dict[str, dict[str, list[float]]] = {}
    for class_index, class_name in enumerate(class_names):
        labels = [int(target == class_index) for target in targets]
        scores = [float(row[class_index]) for row in probabilities]
        fpr, tpr, auc = _binary_curve(labels, scores)
        recall, precision = _binary_pr_curve(labels, scores)
        aurocs[class_name] = auc
        pr_curves[class_name] = {
            "fpr": fpr,
            "tpr": tpr,
            "recall": recall,
            "precision": precision,
        }
    valid_aurocs = [value for value in aurocs.values() if math.isfinite(value)]
    return {
        "macro_auroc": sum(valid_aurocs) / len(valid_aurocs) if valid_aurocs else float("nan"),
        "per_class_auroc": aurocs,
        "pr_curves": pr_curves,
    }


def landmark_geometry_metrics(
    landmarks: "torch.Tensor",
    reference: "torch.Tensor | None" = None,
) -> dict[str, list[float]]:
    """Measure reflection asymmetry and optional geometric shift per sample.

    The JSON data contains dense OBJ vertices rather than a semantic left/right
    landmark index map.  We therefore pair each point with its nearest point
    after reflection across the facial midline.  This metric is explicit about
    that assumption and remains reproducible for the supplied topology.
    """

    if landmarks.ndim != 3 or landmarks.shape[-1] != 3:
        raise ValueError("landmarks must have shape [batch, points, 3]")
    values: list[float] = []
    shifts: list[float] = []
    for index, points in enumerate(landmarks.detach().cpu()):
        centered = points - points.mean(dim=0, keepdim=True)
        scale = centered.norm(dim=1).amax().clamp_min(1e-6)
        normalized = centered / scale
        left = normalized[normalized[:, 0] < 0]
        right = normalized[normalized[:, 0] > 0]
        if len(left) == 0 or len(right) == 0:
            values.append(float("nan"))
        else:
            reflected_left = left.clone()
            reflected_left[:, 0] *= -1
            distances = torch.cdist(reflected_left, right)
            values.append(float(distances.min(dim=1).values.mean().item()))
        if reference is not None:
            ref = reference[index].detach().cpu()
            ref = ref - ref.mean(dim=0, keepdim=True)
            ref = ref / ref.norm(dim=1).amax().clamp_min(1e-6)
            if ref.shape == normalized.shape:
                shifts.append(float((normalized - ref).pow(2).mean().sqrt().item()))
            else:
                shifts.append(float("nan"))
    return {"spatial_asymmetry": values, "geometric_shift": shifts}


__all__ = ["classification_metrics"]
