"""Train and evaluate the vision-only and landmark-fused face classifiers."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import numpy as np
    import torch
    import torch.nn as nn
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    from torch.utils.data import DataLoader
except ImportError as exc:  # pragma: no cover - dependency guard
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install emergency_cdss/requirements.txt."
    ) from exc

from emergency_cdss.datasets.face_multimodal_dataset import (
    FaceMultimodalDataset,
    parse_obj_vertices,
    SOURCE_ROTATION_DEGREES,
    split_subjects,
)
from emergency_cdss.models.multimodal_efficientnet import EfficientNetB0Multimodal, count_parameters
from emergency_cdss.utils.metrics import (
    classification_metrics,
    landmark_geometry_metrics,
    probabilistic_metrics,
)
from emergency_cdss.utils.transforms import make_transforms


def parse_args() -> argparse.Namespace:
    project_dir = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=project_dir / "dataset/drive_landmark/manifest.json")
    parser.add_argument("--output-dir", type=Path, default=project_dir / "dataset/face_experiments")
    parser.add_argument("--mode", choices=("vision", "joint"), default="joint")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--landmark-hidden-dim", type=int, default=128)
    parser.add_argument("--fusion-dim", type=int, default=256)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--label-smoothing", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--schedule-hours", type=float, default=0.0, help="Optional wall-clock budget; 8.0 records the requested CVPR schedule")
    parser.add_argument("--train-fraction", type=float, default=0.6)
    parser.add_argument("--valid-fraction", type=float, default=0.2)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--no-pretrained", action="store_false", dest="pretrained")
    parser.add_argument("--no-grid", action="store_true", help="Skip the 6x6 qualitative grid")
    return parser.parse_args()


def _select_device(choice: str) -> torch.device:
    if choice == "cuda" and not torch.cuda.is_available():
        raise SystemExit("--device cuda was requested, but CUDA is unavailable")
    if choice == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(choice)


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _loader(dataset: FaceMultimodalDataset, batch_size: int, num_workers: int, device: torch.device, shuffle: bool) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=device.type == "cuda",
        persistent_workers=num_workers > 0,
    )


def _move_batch(batch: dict[str, Any], device: torch.device) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    images = batch["image"].to(device, non_blocking=True)
    landmarks = batch["landmarks"].to(device, non_blocking=True)
    targets = batch["target"].to(device, non_blocking=True)
    return images, landmarks, targets


def _run_epoch(
    model: EfficientNetB0Multimodal,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    class_names: tuple[str, ...],
    *,
    optimizer: torch.optim.Optimizer | None = None,
) -> tuple[float, dict[str, Any], list[dict[str, Any]], list[torch.Tensor]]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    total_samples = 0
    targets: list[int] = []
    predictions: list[int] = []
    probabilities: list[list[float]] = []
    prediction_rows: list[dict[str, Any]] = []
    landmark_batches: list[torch.Tensor] = []
    context = torch.enable_grad() if training else torch.no_grad()
    with context:
        for batch in loader:
            images, landmarks, labels = _move_batch(batch, device)
            logits = model(images, landmarks)
            loss = criterion(logits, labels)
            if training:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
                optimizer.step()
            batch_size = labels.size(0)
            total_loss += float(loss.item()) * batch_size
            total_samples += batch_size
            probs = torch.softmax(logits, dim=1)
            preds = probs.argmax(dim=1)
            targets.extend(labels.detach().cpu().tolist())
            predictions.extend(preds.detach().cpu().tolist())
            probabilities.extend(probs.detach().cpu().tolist())
            landmark_batches.append(landmarks.detach().cpu().reshape(batch_size, -1, 3))
            for row_index in range(batch_size):
                prediction_rows.append(
                    {
                        "image_path": str(batch["image_path"][row_index]),
                        "subject_id": str(batch["subject_id"][row_index]),
                        "view": str(batch["view"][row_index]),
                        "target": int(labels[row_index].item()),
                        "prediction": int(preds[row_index].item()),
                        "probabilities": [float(value) for value in probs[row_index].detach().cpu().tolist()],
                    }
                )
    metrics = classification_metrics(
        targets,
        predictions,
        num_classes=len(class_names),
        class_names=class_names,
    )
    metrics.update(
        probabilistic_metrics(
            targets,
            probabilities,
            num_classes=len(class_names),
            class_names=class_names,
        )
    )
    return total_loss / max(1, total_samples), metrics, prediction_rows, landmark_batches


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _save_qualitative_grid(
    prediction_rows: list[dict[str, Any]],
    class_names: tuple[str, ...],
    output_path: Path,
    *,
    limit: int = 36,
) -> None:
    """Create a 6x6 test grid with labels and a projected landmark trace."""

    cell_width, image_height, text_height = 260, 224, 54
    canvas = Image.new("RGB", (cell_width * 6, (image_height + text_height) * 6), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
    for index, row in enumerate(prediction_rows[:limit]):
        x0 = (index % 6) * cell_width
        y0 = (index // 6) * (image_height + text_height)
        try:
            with Image.open(row["image_path"]) as image_file:
                image = ImageOps.exif_transpose(image_file.convert("RGB")).rotate(
                    SOURCE_ROTATION_DEGREES, expand=True
                ).resize((cell_width, image_height))
        except (OSError, ValueError):
            image = Image.new("RGB", (cell_width, image_height), "#dddddd")
        canvas.paste(image, (x0, y0))
        correct = row["target"] == row["prediction"]
        color = "#008000" if correct else "#cc0000"
        draw.rectangle((x0, y0, x0 + cell_width - 1, y0 + image_height - 1), outline=color, width=3)
        target_name = class_names[row["target"]]
        predicted_name = class_names[row["prediction"]]
        lines = [
            f"GT: {target_name}",
            f"Pred: {predicted_name} ({max(row['probabilities']):.2f})",
            f"ID: {row['subject_id']} / {row['view']}",
        ]
        for line_index, line in enumerate(lines):
            draw.text((x0 + 4, y0 + image_height + 3 + line_index * 16), line, fill=color, font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG")


def _geometry_summary(prediction_rows: list[dict[str, Any]], landmark_batches: list[torch.Tensor]) -> dict[str, Any]:
    if not landmark_batches:
        return {}
    landmarks = torch.cat(landmark_batches, dim=0)
    metrics = landmark_geometry_metrics(landmarks)
    asymmetry = [value for value in metrics["spatial_asymmetry"] if np.isfinite(value)]
    by_subject: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(prediction_rows):
        by_subject[row["subject_id"]].append(index)
    shifts: list[float] = []
    for indices in by_subject.values():
        reference = landmarks[indices[0]].unsqueeze(0).repeat(len(indices), 1, 1)
        subject_metrics = landmark_geometry_metrics(landmarks[indices], reference)
        shifts.extend(value for value in subject_metrics["geometric_shift"] if np.isfinite(value))
    return {
        "mean_spatial_asymmetry": float(np.mean(asymmetry)) if asymmetry else None,
        "mean_geometric_shift": float(np.mean(shifts)) if shifts else None,
        "num_asymmetry_samples": len(asymmetry),
        "num_shift_samples": len(shifts),
    }


def _measure_latency(
    model: EfficientNetB0Multimodal,
    loader: DataLoader,
    device: torch.device,
    *,
    warmup: int = 3,
    repeats: int = 20,
) -> dict[str, Any]:
    """Measure forward-pass latency on a fixed test batch."""

    batch = next(iter(loader))
    images, landmarks, _ = _move_batch(batch, device)
    model.eval()
    with torch.no_grad():
        for _ in range(warmup):
            model(images, landmarks)
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        elapsed_ms: list[float] = []
        for _ in range(repeats):
            start = time.perf_counter()
            model(images, landmarks)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            elapsed_ms.append((time.perf_counter() - start) * 1000.0 / images.shape[0])
    ordered = sorted(elapsed_ms)
    p50 = ordered[len(ordered) // 2]
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    return {
        "device": str(device),
        "batch_size": int(images.shape[0]),
        "warmup_runs": warmup,
        "timed_runs": repeats,
        "p50_ms_per_sample": float(p50),
        "p95_ms_per_sample": float(p95),
    }


def main() -> None:
    args = parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.num_workers < 0:
        raise SystemExit("epochs and batch-size must be positive; num-workers cannot be negative")
    if args.schedule_hours < 0:
        raise SystemExit("schedule-hours cannot be negative")
    _seed_everything(args.seed)
    device = _select_device(args.device)
    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"Manifest does not exist: {manifest_path}")
    records = json.loads(manifest_path.read_text(encoding="utf-8"))
    class_names = tuple(sorted({str(record["target"]) for record in records}))
    all_subjects = [str(record["subject_id"]) for record in records]
    split = split_subjects(
        all_subjects,
        seed=args.seed,
        train_fraction=args.train_fraction,
        valid_fraction=args.valid_fraction,
    )
    # Spatial image transforms are safe for the vision baseline.  The joint
    # model keeps geometry fixed unless landmark coordinates are transformed by
    # the exact same affine map; color jitter remains modality-independent.
    train_transform, valid_transform = make_transforms(spatial_augment=args.mode == "vision")
    train_dataset = FaceMultimodalDataset(manifest_path, transform=train_transform, subjects=split["train"], class_names=class_names)
    valid_dataset = FaceMultimodalDataset(manifest_path, transform=valid_transform, subjects=split["valid"], class_names=class_names)
    test_dataset = FaceMultimodalDataset(manifest_path, transform=valid_transform, subjects=split["test"], class_names=class_names)
    train_loader = _loader(train_dataset, args.batch_size, args.num_workers, device, True)
    valid_loader = _loader(valid_dataset, args.batch_size, args.num_workers, device, False)
    test_loader = _loader(test_dataset, args.batch_size, args.num_workers, device, False)

    model = EfficientNetB0Multimodal(
        train_dataset.landmark_dim,
        len(class_names),
        mode=args.mode,
        landmark_hidden_dim=args.landmark_hidden_dim,
        fusion_dim=args.fusion_dim,
        dropout=args.dropout,
        pretrained=args.pretrained,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / f"best_{args.mode}.pt"
    history: list[dict[str, Any]] = []
    best_score = -float("inf")
    start_time = time.time()
    deadline = start_time + args.schedule_hours * 3600 if args.schedule_hours > 0 else None

    print(f"Device: {device} | Mode: {args.mode} | Classes: {class_names}")
    print(f"Split subjects: { {key: sorted(value) for key, value in split.items()} }")
    print(f"Samples: train={len(train_dataset)} valid={len(valid_dataset)} test={len(test_dataset)}")
    print(f"Parameters: {count_parameters(model)}")
    for epoch in range(1, args.epochs + 1):
        if deadline is not None and time.time() >= deadline:
            print(f"Reached schedule wall-clock budget before epoch {epoch}")
            break
        train_loss, train_metrics, _, _ = _run_epoch(model, train_loader, criterion, device, class_names, optimizer=optimizer)
        valid_loss, valid_metrics, _, _ = _run_epoch(model, valid_loader, criterion, device, class_names)
        scheduler.step()
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "valid_loss": valid_loss,
                "train_metrics": train_metrics,
                "valid_metrics": valid_metrics,
                "learning_rate": optimizer.param_groups[0]["lr"],
                "elapsed_seconds": time.time() - start_time,
            }
        )
        print(
            f"Epoch {epoch:03d}/{args.epochs:03d} | "
            f"train loss {train_loss:.4f} | valid macro-F1 {valid_metrics['macro_f1']:.4f} | "
            f"valid balanced acc {valid_metrics['balanced_accuracy']:.4f}"
        )
        score = float(valid_metrics["macro_f1"])
        if score > best_score:
            best_score = score
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "mode": args.mode,
                    "classes": list(class_names),
                    "landmark_dim": train_dataset.landmark_dim,
                    "landmark_hidden_dim": args.landmark_hidden_dim,
                    "fusion_dim": args.fusion_dim,
                    "dropout": args.dropout,
                    "pretrained": args.pretrained,
                    "best_valid_macro_f1": best_score,
                    "epoch": epoch,
                },
                checkpoint_path,
            )

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_loss, test_metrics, prediction_rows, landmark_batches = _run_epoch(model, test_loader, criterion, device, class_names)
    geometry = _geometry_summary(prediction_rows, landmark_batches)
    latency = _measure_latency(model, test_loader, device)
    payload = {
        "config": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        "device": str(device),
        "classes": list(class_names),
        "split_subjects": {key: sorted(value) for key, value in split.items()},
        "num_samples": {"train": len(train_dataset), "valid": len(valid_dataset), "test": len(test_dataset)},
        "parameters": count_parameters(model),
        "checkpoint": str(checkpoint_path),
        "history": history,
        "test": {"loss": test_loss, "metrics": test_metrics, "geometry": geometry, "latency": latency},
        "runtime_seconds": time.time() - start_time,
    }
    metrics_path = output_dir / f"metrics_{args.mode}.json"
    metrics_path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    prediction_path = output_dir / f"predictions_{args.mode}.json"
    prediction_path.write_text(json.dumps(_json_safe(prediction_rows), ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.no_grid:
        _save_qualitative_grid(prediction_rows, class_names, output_dir / f"qualitative_grid_{args.mode}_6x6.png")
    print(f"Test Macro-F1: {test_metrics['macro_f1']:.4f}")
    print(f"Test Balanced Accuracy: {test_metrics['balanced_accuracy']:.4f}")
    print(f"Test Macro AUROC: {test_metrics['macro_auroc']}")
    print(f"Saved: {metrics_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
