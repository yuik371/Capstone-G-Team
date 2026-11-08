"""Crop Roboflow COCO wound boxes and train an EfficientNet-B0 classifier.

Run from ``dev-YuIK`` with::

    python -m emergency_cdss.scripts.train_wound

The old ``train_wound_classifier.py`` entry point remains as a compatibility
wrapper. This module owns orchestration only; dataset parsing, model creation,
transforms, and metrics live in their respective packages.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    # Allow ``python emergency_cdss/scripts/train_wound.py`` as well as the
    # preferred module invocation from the dev-YuIK directory.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import numpy as np
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, WeightedRandomSampler
except ImportError as exc:  # pragma: no cover - exercised only without dependencies
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install emergency_cdss/requirements.txt."
    ) from exc

from emergency_cdss.datasets.wound_dataset import (
    CroppedWoundDataset,
    WOUND_CLASSES,
    WOUND_CLASS_TO_IDX,
    crop_coco_split,
    make_class_weights,
)
from emergency_cdss.models.efficientnet import WoundEfficientNet
from emergency_cdss.utils.metrics import classification_metrics
from emergency_cdss.utils.transforms import IMAGENET_MEAN, IMAGENET_STD, make_transforms


def parse_args() -> argparse.Namespace:
    project_dir = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Crop COCO wound boxes and train an ImageNet-pretrained EfficientNet-B0."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=project_dir,
        help="Roboflow export root containing train/valid/test folders (default: project root).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_dir / "dataset",
        help="Destination for cropped splits and checkpoints (default: ./dataset).",
    )
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument(
        "--optimizer",
        choices=("adamw", "sgd", "rmsprop"),
        default="adamw",
        help="Optimizer used for fine-tuning (default: adamw).",
    )
    parser.add_argument(
        "--scheduler",
        choices=("none", "cosine", "plateau"),
        default="none",
        help="Learning-rate scheduler (default: none for baseline compatibility).",
    )
    parser.add_argument(
        "--momentum",
        type=float,
        default=0.9,
        help="Momentum for SGD/RMSprop (default: 0.9).",
    )
    parser.add_argument(
        "--backbone-lr-factor",
        type=float,
        default=1.0,
        help="Backbone LR multiplied by this value; the classifier keeps --learning-rate.",
    )
    parser.add_argument(
        "--freeze-backbone-epochs",
        type=int,
        default=0,
        help="Keep the EfficientNet backbone frozen for this many initial epochs.",
    )
    parser.add_argument(
        "--label-smoothing",
        type=float,
        default=0.0,
        help="Cross-entropy label smoothing in [0, 1).",
    )
    parser.add_argument(
        "--class-weight-mode",
        choices=("custom", "sqrt", "none"),
        default="custom",
        help="Class weighting: custom wound rule, softened inverse frequency, or none.",
    )
    parser.add_argument(
        "--sampler",
        choices=("none", "weighted"),
        default="none",
        help="Use a class-balanced replacement sampler instead of ordinary shuffling.",
    )
    parser.add_argument(
        "--selection-metric",
        choices=("accuracy", "macro_f1", "balanced_accuracy"),
        default="accuracy",
        help="Validation metric used for checkpoint selection.",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=0,
        help="Early-stopping patience; 0 disables early stopping.",
    )
    parser.add_argument(
        "--min-delta",
        type=float,
        default=0.0,
        help="Minimum validation-score improvement required to reset patience.",
    )
    parser.add_argument(
        "--head-dropout",
        type=float,
        default=0.3,
        help="Dropout probability in the classifier head (default: 0.3).",
    )
    parser.add_argument(
        "--evaluate-test",
        action="store_true",
        help="Evaluate the untouched test split after training; never used for selection.",
    )
    parser.add_argument(
        "--crop-padding",
        type=float,
        default=0.05,
        help="Extra context around each clipped box as a fraction of its width/height.",
    )
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--no-pretrained",
        action="store_false",
        dest="pretrained",
        help="Do not load ImageNet weights; useful for offline smoke tests.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and rebuild an existing output directory.",
    )
    return parser.parse_args()


def seed_everything(seed: int) -> None:
    """Seed Python, NumPy, and PyTorch RNGs for repeatable experiments."""

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    class_names: tuple[str, ...],
    optimizer: torch.optim.Optimizer | None = None,
    backbone_frozen: bool = False,
) -> tuple[float, dict[str, Any]]:
    """Run one training or evaluation epoch and calculate class-aware metrics."""

    is_training = optimizer is not None
    model.train(is_training)
    if is_training and backbone_frozen:
        # Keep BatchNorm statistics fixed while only the classifier head learns.
        model.backbone.eval()

    total_loss = 0.0
    total_samples = 0
    targets: list[int] = []
    predictions: list[int] = []
    context = torch.enable_grad if is_training else torch.no_grad
    with context():
        for images, labels in loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            if is_training:
                optimizer.zero_grad(set_to_none=True)

            logits = model(images)
            loss = criterion(logits, labels)
            if is_training:
                loss.backward()
                optimizer.step()

            batch_size = labels.size(0)
            total_loss += loss.item() * batch_size
            total_samples += batch_size
            targets.extend(labels.detach().cpu().tolist())
            predictions.extend(logits.argmax(dim=1).detach().cpu().tolist())

    if total_samples == 0:
        raise RuntimeError("DataLoader returned no samples")
    metrics = classification_metrics(
        targets,
        predictions,
        num_classes=len(class_names),
        class_names=class_names,
    )
    return total_loss / total_samples, metrics


def _validate_args(args: argparse.Namespace) -> None:
    if args.epochs < 1 or args.batch_size < 1 or args.num_workers < 0:
        raise SystemExit("epochs and batch-size must be positive; num-workers cannot be negative")
    if args.learning_rate <= 0 or args.weight_decay < 0:
        raise SystemExit("learning-rate must be positive and weight-decay cannot be negative")
    if args.momentum < 0 or args.momentum >= 1:
        raise SystemExit("momentum must be in [0, 1)")
    if args.backbone_lr_factor <= 0:
        raise SystemExit("backbone-lr-factor must be positive")
    if args.freeze_backbone_epochs < 0 or args.freeze_backbone_epochs > args.epochs:
        raise SystemExit("freeze-backbone-epochs must be between 0 and epochs")
    if not 0 <= args.label_smoothing < 1:
        raise SystemExit("label-smoothing must be in [0, 1)")
    if not 0 <= args.head_dropout < 1:
        raise SystemExit("head-dropout must be in [0, 1)")
    if args.patience < 0 or args.min_delta < 0:
        raise SystemExit("patience and min-delta cannot be negative")
    if not 0 <= args.crop_padding <= 1:
        raise SystemExit("crop-padding must be between 0 and 1")
    if args.hidden_dim < 1:
        raise SystemExit("hidden-dim must be positive")


def _prepare_output_dir(data_root: Path, output_dir: Path, overwrite: bool) -> None:
    if output_dir == data_root or output_dir in data_root.parents:
        raise SystemExit(
            "Output directory cannot be the dataset root or one of its parent directories."
        )
    for split_name in ("train", "valid", "test"):
        source_split = (data_root / split_name).resolve()
        if source_split == output_dir or source_split in output_dir.parents:
            raise SystemExit(
                f"Output directory cannot be inside the source {split_name} folder."
            )
    if output_dir.exists() and any(output_dir.iterdir()):
        if not overwrite:
            raise SystemExit(
                f"Output directory is not empty: {output_dir}\n"
                "Choose another --output-dir or pass --overwrite to rebuild it."
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _make_optimizer(args: argparse.Namespace, model: WoundEfficientNet) -> torch.optim.Optimizer:
    optimizer_parameters = [
        {
            "params": model.backbone.parameters(),
            "lr": args.learning_rate * args.backbone_lr_factor,
        },
        {"params": model.classifier.parameters(), "lr": args.learning_rate},
    ]
    if args.optimizer == "adamw":
        return torch.optim.AdamW(optimizer_parameters, weight_decay=args.weight_decay)
    if args.optimizer == "sgd":
        return torch.optim.SGD(
            optimizer_parameters,
            weight_decay=args.weight_decay,
            momentum=args.momentum,
            nesterov=args.momentum > 0,
        )
    if args.optimizer == "rmsprop":
        return torch.optim.RMSprop(
            optimizer_parameters,
            weight_decay=args.weight_decay,
            momentum=args.momentum,
        )
    raise ValueError(f"Unsupported optimizer: {args.optimizer}")


def _make_scheduler(args: argparse.Namespace, optimizer: torch.optim.Optimizer) -> Any:
    if args.scheduler == "cosine":
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    if args.scheduler == "plateau":
        return torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode="max",
            factor=0.3,
            patience=max(1, args.patience // 2) if args.patience else 2,
        )
    return None


def main() -> None:
    args = parse_args()
    _validate_args(args)

    data_root = args.data_root.resolve()
    output_dir = args.output_dir.resolve()
    if not data_root.is_dir():
        raise SystemExit(f"Dataset root does not exist: {data_root}")
    _prepare_output_dir(data_root, output_dir, args.overwrite)

    seed_everything(args.seed)
    print(f"Reading Roboflow splits from: {data_root}")
    for split_name in ("train", "valid", "test"):
        split_dir = data_root / split_name
        if split_name == "test" and not (split_dir / "_annotations.coco.json").is_file():
            print("[test] split not found; skipping crop generation")
            continue
        crop_coco_split(split_dir, output_dir, split_name, args.crop_padding)

    train_transform, valid_transform = make_transforms()
    train_dataset = CroppedWoundDataset(output_dir / "train", transform=train_transform)
    valid_dataset = CroppedWoundDataset(output_dir / "valid", transform=valid_transform)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pin_memory = device.type == "cuda"
    sampler = None
    if args.sampler == "weighted":
        counts = Counter(train_dataset.targets)
        sample_weights = torch.DoubleTensor(
            [1.0 / counts[label] for label in train_dataset.targets]
        )
        sampler = WeightedRandomSampler(
            sample_weights,
            num_samples=len(train_dataset),
            replacement=True,
        )

    loader_options = {
        "batch_size": args.batch_size,
        "num_workers": args.num_workers,
        "pin_memory": pin_memory,
        "persistent_workers": args.num_workers > 0,
    }
    train_loader = DataLoader(
        train_dataset,
        shuffle=sampler is None,
        sampler=sampler,
        **loader_options,
    )
    valid_loader = DataLoader(valid_dataset, shuffle=False, **loader_options)

    weights = make_class_weights(train_dataset, device, args.class_weight_mode)
    print("Class order: " + ", ".join(WOUND_CLASSES))
    print(
        "Training crop counts: "
        + ", ".join(
            f"{name}={Counter(train_dataset.targets)[index]}"
            for name, index in WOUND_CLASS_TO_IDX.items()
        )
    )
    print("Cross-entropy weights: " + ", ".join(f"{value:.3f}" for value in weights.tolist()))
    print(
        f"Device: {device}; train crops: {len(train_dataset)}; "
        f"valid crops: {len(valid_dataset)}; sampler: {args.sampler}"
    )

    model = WoundEfficientNet(
        num_classes=len(WOUND_CLASSES),
        hidden_dim=args.hidden_dim,
        dropout=args.head_dropout,
        pretrained=args.pretrained,
    ).to(device)
    train_criterion = nn.CrossEntropyLoss(
        weight=None if args.class_weight_mode == "none" else weights,
        label_smoothing=args.label_smoothing,
    )
    eval_criterion = nn.CrossEntropyLoss()
    optimizer = _make_optimizer(args, model)
    scheduler = _make_scheduler(args, optimizer)

    best_selection_score = -float("inf")
    best_epoch = 0
    epochs_without_improvement = 0
    history: list[dict[str, Any]] = []
    checkpoint_path = output_dir / "best_efficientnet_b0_wound.pt"
    for epoch in range(1, args.epochs + 1):
        backbone_frozen = epoch <= args.freeze_backbone_epochs
        for parameter in model.backbone.parameters():
            parameter.requires_grad = not backbone_frozen

        train_loss, train_metrics = run_epoch(
            model,
            train_loader,
            train_criterion,
            device,
            WOUND_CLASSES,
            optimizer=optimizer,
            backbone_frozen=backbone_frozen,
        )
        valid_loss, valid_metrics = run_epoch(
            model, valid_loader, eval_criterion, device, WOUND_CLASSES
        )
        selection_score = valid_metrics[args.selection_metric]
        if isinstance(scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
            scheduler.step(selection_score)
        elif scheduler is not None:
            scheduler.step()

        current_lrs = ",".join(f"{group['lr']:.2e}" for group in optimizer.param_groups)
        history.append(
            {
                "epoch": epoch,
                "learning_rates": current_lrs,
                "backbone_frozen": backbone_frozen,
                "train_loss": train_loss,
                "train_metrics": train_metrics,
                "valid_loss": valid_loss,
                "valid_metrics": valid_metrics,
            }
        )
        print(
            f"Epoch {epoch:03d}/{args.epochs:03d} | "
            f"Train Loss: {train_loss:.4f} | Train Top-1: {train_metrics['accuracy'] * 100:.2f}% | "
            f"Train Macro-F1: {train_metrics['macro_f1'] * 100:.2f}% | "
            f"Valid Loss: {valid_loss:.4f} | Valid Top-1: {valid_metrics['accuracy'] * 100:.2f}% | "
            f"Valid Macro-F1: {valid_metrics['macro_f1'] * 100:.2f}% | "
            f"Valid Balanced Acc: {valid_metrics['balanced_accuracy'] * 100:.2f}% | LR: {current_lrs}"
        )

        if selection_score > best_selection_score + args.min_delta:
            best_selection_score = selection_score
            best_epoch = epoch
            epochs_without_improvement = 0
            torch.save(
                {
                    "model_name": "efficientnet_b0",
                    "model_state_dict": model.state_dict(),
                    "classes": list(WOUND_CLASSES),
                    "class_to_idx": dict(WOUND_CLASS_TO_IDX),
                    "input_size": 224,
                    "mean": IMAGENET_MEAN,
                    "std": IMAGENET_STD,
                    "pretrained_backbone": args.pretrained,
                    "best_valid_accuracy": valid_metrics["accuracy"],
                    "best_valid_macro_f1": valid_metrics["macro_f1"],
                    "best_valid_balanced_accuracy": valid_metrics["balanced_accuracy"],
                    "selection_metric": args.selection_metric,
                    "best_selection_score": best_selection_score,
                    "epoch": epoch,
                    "class_weights": weights.detach().cpu(),
                },
                checkpoint_path,
            )
        else:
            epochs_without_improvement += 1
            if args.patience and epochs_without_improvement >= args.patience:
                print(
                    f"Early stopping at epoch {epoch}: no {args.selection_metric} "
                    f"improvement for {args.patience} epochs."
                )
                break

    history_payload: dict[str, Any] = {
        "config": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
        "best_epoch": best_epoch,
        "best_selection_score": best_selection_score,
        "history": history,
    }
    history_path = output_dir / "training_history.json"
    history_path.write_text(
        json.dumps(history_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"Best validation {args.selection_metric}: "
        f"{best_selection_score * 100:.2f}% at epoch {best_epoch}"
    )
    print(f"Best checkpoint saved to: {checkpoint_path}")

    if args.evaluate_test:
        test_root = output_dir / "test"
        if not test_root.is_dir():
            print("Test split is unavailable; skipping test evaluation.")
        else:
            test_dataset = CroppedWoundDataset(test_root, transform=valid_transform)
            test_loader = DataLoader(test_dataset, shuffle=False, **loader_options)
            checkpoint = torch.load(checkpoint_path, map_location=device)
            model.load_state_dict(checkpoint["model_state_dict"])
            test_loss, test_metrics = run_epoch(
                model, test_loader, eval_criterion, device, WOUND_CLASSES
            )
            history_payload["test"] = {"loss": test_loss, "metrics": test_metrics}
            history_path.write_text(
                json.dumps(history_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(
                f"Test Loss: {test_loss:.4f} | "
                f"Test Top-1: {test_metrics['accuracy'] * 100:.2f}% | "
                f"Test Macro-F1: {test_metrics['macro_f1'] * 100:.2f}% | "
                f"Test Balanced Acc: {test_metrics['balanced_accuracy'] * 100:.2f}%"
            )
            print(
                "Test per-class F1: "
                + ", ".join(
                    f"{name}={score * 100:.2f}%"
                    for name, score in test_metrics["per_class_f1"].items()
                )
            )
    else:
        print("The test split was not used for training or checkpoint selection.")
        print("Pass --evaluate-test only for a final, one-time evaluation.")
    print(f"Training history saved to: {history_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTraining interrupted by user.", file=sys.stderr)
        raise SystemExit(130)

