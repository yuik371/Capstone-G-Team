"""Classification metrics shared by training and evaluation scripts."""

from __future__ import annotations

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


__all__ = ["classification_metrics"]
