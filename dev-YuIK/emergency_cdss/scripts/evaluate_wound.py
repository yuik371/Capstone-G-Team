"""Evaluate a trained wound checkpoint and predict arbitrary images.

Examples from ``dev-YuIK``::

    python -m emergency_cdss.scripts.evaluate_wound
    python -m emergency_cdss.scripts.evaluate_wound \
        --image dataset/test/abrasions/crop_000001.jpg
    python -m emergency_cdss.scripts.evaluate_wound \
        --image path/to/photo.jpg --bbox 20 30 240 180 \
        --save-annotated-dir predictions

The classifier was trained on cropped wound regions. A full scene photo can be
used for a rough experiment, but an explicit ``--bbox X Y WIDTH HEIGHT`` is
recommended when the photo contains a large amount of background.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import torch
    import torch.nn as nn
    from PIL import Image, ImageDraw
    from torch.utils.data import DataLoader
except ImportError as exc:  # pragma: no cover - exercised only without dependencies
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install emergency_cdss/requirements.txt."
    ) from exc

from emergency_cdss.datasets.wound_dataset import CroppedWoundDataset, WOUND_CLASSES
from emergency_cdss.models.efficientnet import WoundEfficientNet
from emergency_cdss.utils.metrics import classification_metrics
from emergency_cdss.utils.transforms import make_transforms


def parse_args() -> argparse.Namespace:
    project_dir = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Report wound test metrics and predict one or more images."
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=project_dir / "dataset" / "best_efficientnet_b0_wound.pt",
        help="Trained checkpoint path.",
    )
    parser.add_argument(
        "--test-root",
        type=Path,
        default=project_dir / "dataset" / "test",
        help="Cropped test root containing one folder per wound class.",
    )
    parser.add_argument(
        "--image",
        type=Path,
        action="append",
        default=[],
        help="Image to predict; repeat this option for multiple images.",
    )
    parser.add_argument(
        "--bbox",
        type=int,
        nargs=4,
        metavar=("X", "Y", "WIDTH", "HEIGHT"),
        help="Optional crop box for every --image, in pixel xywh format.",
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default="auto",
        help="Inference device (default: auto).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional path for machine-readable test metrics and predictions.",
    )
    parser.add_argument(
        "--save-annotated-dir",
        type=Path,
        help="Optional directory for images annotated with prediction/probabilities.",
    )
    return parser.parse_args()


def _select_device(choice: str) -> torch.device:
    if choice == "cuda" and not torch.cuda.is_available():
        raise SystemExit("--device cuda was requested, but CUDA is not available")
    if choice == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(choice)


def _load_model(
    checkpoint_path: Path,
    device: torch.device,
) -> tuple[WoundEfficientNet, tuple[str, ...], dict[str, Any]]:
    if not checkpoint_path.is_file():
        raise SystemExit(f"Checkpoint does not exist: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location=device)
    state_dict = checkpoint.get("model_state_dict")
    if not isinstance(state_dict, dict):
        raise ValueError("Checkpoint does not contain a model_state_dict")

    classes = tuple(checkpoint.get("classes", WOUND_CLASSES))
    if classes != tuple(WOUND_CLASSES):
        raise ValueError(
            "This evaluator expects the current wound class order "
            f"{WOUND_CLASSES}; checkpoint contains {classes}."
        )
    first_head_weight = state_dict.get("classifier.0.weight")
    if first_head_weight is None or first_head_weight.ndim != 2:
        raise ValueError("Could not infer classifier hidden dimension from checkpoint")
    hidden_dim = int(first_head_weight.shape[0])

    model = WoundEfficientNet(
        num_classes=len(classes),
        hidden_dim=hidden_dim,
        dropout=0.0,
        pretrained=False,
    ).to(device)
    model.load_state_dict(state_dict)
    model.eval()
    return model, classes, checkpoint


def _evaluate_test_set(
    model: WoundEfficientNet,
    test_root: Path,
    device: torch.device,
    classes: tuple[str, ...],
    batch_size: int,
    num_workers: int,
) -> dict[str, Any]:
    if not test_root.is_dir():
        raise SystemExit(f"Test root does not exist: {test_root}")
    if batch_size < 1 or num_workers < 0:
        raise SystemExit("batch-size must be positive and num-workers cannot be negative")

    _, valid_transform = make_transforms()
    dataset = CroppedWoundDataset(test_root, transform=valid_transform)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=device.type == "cuda",
        persistent_workers=num_workers > 0,
    )
    criterion = nn.CrossEntropyLoss()
    targets: list[int] = []
    predictions: list[int] = []
    total_loss = 0.0
    total_samples = 0

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            logits = model(images)
            loss = criterion(logits, labels)
            batch_size_actual = labels.size(0)
            total_loss += loss.item() * batch_size_actual
            total_samples += batch_size_actual
            targets.extend(labels.cpu().tolist())
            predictions.extend(logits.argmax(dim=1).cpu().tolist())

    metrics = classification_metrics(
        targets,
        predictions,
        num_classes=len(classes),
        class_names=classes,
    )
    metrics["loss"] = total_loss / total_samples if total_samples else 0.0
    metrics["num_samples"] = total_samples
    return metrics


def _validate_bbox(bbox: Sequence[int] | None) -> tuple[int, int, int, int] | None:
    if bbox is None:
        return None
    x, y, width, height = bbox
    if width <= 0 or height <= 0:
        raise SystemExit("bbox width and height must be positive")
    return x, y, width, height


def _predict_image(
    model: WoundEfficientNet,
    image_path: Path,
    transform: Any,
    device: torch.device,
    classes: tuple[str, ...],
    top_k: int,
    bbox: tuple[int, int, int, int] | None,
) -> tuple[dict[str, Any], Image.Image]:
    if not image_path.is_file():
        raise SystemExit(f"Image does not exist: {image_path}")
    if top_k < 1:
        raise SystemExit("top-k must be positive")

    with Image.open(image_path) as image_file:
        image = image_file.convert("RGB")
    original_image = image.copy()
    if bbox is not None:
        x, y, width, height = bbox
        left = max(0, x)
        top = max(0, y)
        right = min(image.width, x + width)
        bottom = min(image.height, y + height)
        if right <= left or bottom <= top:
            raise SystemExit(f"bbox does not intersect image: {image_path}")
        image = image.crop((left, top, right, bottom))

    tensor = transform(image).unsqueeze(0).to(device)
    with torch.no_grad():
        probabilities = torch.softmax(model(tensor), dim=1)[0]
    values, indices = torch.topk(probabilities, k=min(top_k, len(classes)))
    top_predictions = [
        {"class": classes[int(index)], "probability": float(value)}
        for value, index in zip(values.cpu(), indices.cpu())
    ]
    result = {
        "image": str(image_path.resolve()),
        "predicted_class": top_predictions[0]["class"],
        "confidence": top_predictions[0]["probability"],
        "top_predictions": top_predictions,
    }
    if bbox is not None:
        result["bbox_xywh"] = list(bbox)
    return result, original_image


def _save_annotated_image(
    image: Image.Image,
    result: dict[str, Any],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{Path(result['image']).stem}_prediction.jpg"
    canvas = image.copy()
    draw = ImageDraw.Draw(canvas)
    if "bbox_xywh" in result:
        x, y, width, height = result["bbox_xywh"]
        draw.rectangle((x, y, x + width, y + height), outline=(255, 0, 0), width=3)
    lines = [
        f"Prediction: {result['predicted_class']}",
        f"Confidence: {result['confidence'] * 100:.2f}%",
    ]
    for prediction in result["top_predictions"]:
        lines.append(f"{prediction['class']}: {prediction['probability'] * 100:.2f}%")
    line_height = 22
    draw.rectangle((0, 0, canvas.width, line_height * len(lines) + 8), fill=(0, 0, 0))
    for line_number, line in enumerate(lines):
        draw.text((8, 4 + line_number * line_height), line, fill=(255, 255, 255))
    canvas.save(output_path, format="JPEG", quality=95)
    return output_path


def _print_metrics(metrics: dict[str, Any], classes: tuple[str, ...]) -> None:
    print("=== Wound test metrics ===")
    print(f"Samples:            {metrics['num_samples']}")
    print(f"Loss:               {metrics['loss']:.6f}")
    print(f"Accuracy:           {metrics['accuracy'] * 100:.2f}%")
    print(f"Macro-F1:           {metrics['macro_f1'] * 100:.2f}%")
    print(f"Balanced Accuracy:  {metrics['balanced_accuracy'] * 100:.2f}%")
    print()
    print("Class                 Support  Precision  Recall  F1")
    print("-" * 58)
    for class_name in classes:
        print(
            f"{class_name:<20} "
            f"{metrics['per_class_support'][class_name]:>7}  "
            f"{metrics['per_class_precision'][class_name] * 100:>8.2f}%  "
            f"{metrics['per_class_recall'][class_name] * 100:>6.2f}%  "
            f"{metrics['per_class_f1'][class_name] * 100:>5.2f}%"
        )
    print()
    print("Confusion matrix (row=true, column=predicted):")
    print("                 " + "  ".join(f"{name:>10}" for name in classes))
    for class_name, row in zip(classes, metrics["confusion_matrix"]):
        print(f"{class_name:<16} " + "  ".join(f"{value:>10}" for value in row))


def main() -> None:
    args = parse_args()
    device = _select_device(args.device)
    bbox = _validate_bbox(args.bbox)
    model, classes, checkpoint = _load_model(args.checkpoint.resolve(), device)
    print(f"Checkpoint: {args.checkpoint.resolve()}")
    print(f"Device: {device}")
    selection_metric = checkpoint.get("selection_metric")
    best_selection_score = checkpoint.get("best_selection_score")
    if selection_metric and best_selection_score is not None:
        print(f"Best validation {selection_metric}: {best_selection_score * 100:.2f}%")
    elif checkpoint.get("best_valid_accuracy") is not None:
        # Older checkpoints predate selection_metric metadata.
        print(
            "Checkpoint validation accuracy: "
            f"{checkpoint['best_valid_accuracy'] * 100:.2f}%"
        )
    else:
        print("Checkpoint validation metadata: unavailable")

    payload: dict[str, Any] = {
        "checkpoint": str(args.checkpoint.resolve()),
        "device": str(device),
        "test": None,
        "predictions": [],
    }
    if args.test_root.is_dir():
        metrics = _evaluate_test_set(
            model,
            args.test_root.resolve(),
            device,
            classes,
            args.batch_size,
            args.num_workers,
        )
        _print_metrics(metrics, classes)
        payload["test"] = metrics
    elif not args.image:
        raise SystemExit(
            f"Test root does not exist: {args.test_root}. "
            "Provide --test-root or at least one --image."
        )
    else:
        print(f"Test root not found; running image-only inference: {args.test_root}")

    if args.image:
        _, valid_transform = make_transforms()
        print("=== Image predictions ===")
        for image_path in args.image:
            result, original_image = _predict_image(
                model,
                image_path.resolve(),
                valid_transform,
                device,
                classes,
                args.top_k,
                bbox,
            )
            payload["predictions"].append(result)
            print(f"Image: {result['image']}")
            print(
                f"Prediction: {result['predicted_class']} "
                f"({result['confidence'] * 100:.2f}%)"
            )
            print(
                "  "
                + ", ".join(
                    f"{item['class']}={item['probability'] * 100:.2f}%"
                    for item in result["top_predictions"]
                )
            )
            if args.save_annotated_dir:
                saved_path = _save_annotated_image(
                    original_image, result, args.save_annotated_dir.resolve()
                )
                result["annotated_image"] = str(saved_path)
                print(f"Annotated image: {saved_path}")

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"JSON result: {args.output_json.resolve()}")


if __name__ == "__main__":
    main()
