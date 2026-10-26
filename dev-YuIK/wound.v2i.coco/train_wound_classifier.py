#!/usr/bin/env python3
"""Train an EfficientNet-B0 wound classifier from Roboflow COCO exports.

The script first crops every wound annotation into an ImageFolder-like tree:

    dataset/
      train/{abrasions,bruises,cut,stab}/
      valid/{abrasions,bruises,cut,stab}/
      test/{abrasions,bruises,cut,stab}/

It then trains on ``train`` and validates on ``valid``. The ``test`` crops are
prepared but never used during training or model selection. By default the
Roboflow ``train``, ``valid``, and ``test`` directories are read from beside
this script. Requires Python packages: torch, torchvision, timm, and Pillow.

Example:
    python train_wound_classifier.py
    python train_wound_classifier.py --data-root /path/to/wound.v2i.coco \
        --output-dir /path/to/wound.v2i.coco/dataset --epochs 30

If the output directory already contains files, pass ``--overwrite`` to
rebuild it. This removes that output directory before creating new crops and
checkpoints; keep the output directory dedicated to this script.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import numpy as np
    import timm
    import torch
    import torch.nn as nn
    from PIL import Image, UnidentifiedImageError
    from torch.utils.data import DataLoader, Dataset
    from torchvision import transforms
except ImportError as exc:  # Show a useful message instead of a long traceback.
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install the required packages with:\n"
        "  pip install torch torchvision timm pillow numpy"
    ) from exc


CLASSES = ("abrasions", "bruises", "cut", "stab")
CLASS_TO_IDX = {name: index for index, name in enumerate(CLASSES)}
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Crop COCO wound boxes and train an ImageNet-pretrained EfficientNet-B0."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=script_dir,
        help="Roboflow export root containing train/valid/test folders (default: script folder).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=script_dir / "dataset",
        help="Destination for cropped splits and model checkpoints (default: ./dataset).",
    )
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument(
        "--crop-padding",
        type=float,
        default=0.05,
        help="Extra context around each clipped box as a fraction of its width/height (default: 0.05).",
    )
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and rebuild an existing output directory.",
    )
    return parser.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _safe_image_path(split_dir: Path, file_name: str) -> Path | None:
    """Resolve an annotation path while refusing paths outside its split."""
    candidate = (split_dir / file_name).resolve()
    try:
        candidate.relative_to(split_dir.resolve())
    except ValueError:
        return None
    return candidate


def _clip_box(
    bbox: Any,
    image_width: int,
    image_height: int,
    padding_fraction: float,
) -> tuple[tuple[int, int, int, int] | None, bool, str | None]:
    """Convert COCO xywh to a safe Pillow crop box, clipping to image bounds.

    Returns (pixel_box, was_clipped, error). A completely out-of-frame box is
    rejected cleanly, as are malformed, non-finite, or non-positive boxes.
    """
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None, False, "bbox must contain exactly four values"
    try:
        x, y, width, height = (float(value) for value in bbox)
    except (TypeError, ValueError, OverflowError):
        return None, False, "bbox contains a non-numeric value"
    if not all(math.isfinite(value) for value in (x, y, width, height)):
        return None, False, "bbox contains a non-finite value"
    if width <= 0 or height <= 0:
        return None, False, "bbox width and height must be positive"

    x2, y2 = x + width, y + height
    was_clipped = x < 0 or y < 0 or x2 > image_width or y2 > image_height

    # Intersect the annotation with the real image bounds before adding context.
    x1 = min(float(image_width), max(0.0, x))
    y1 = min(float(image_height), max(0.0, y))
    x2 = min(float(image_width), max(0.0, x2))
    y2 = min(float(image_height), max(0.0, y2))
    if x2 <= x1 or y2 <= y1:
        return None, was_clipped, "bbox does not intersect the image"

    pad_x = (x2 - x1) * padding_fraction
    pad_y = (y2 - y1) * padding_fraction
    left = max(0, min(image_width, math.floor(x1 - pad_x)))
    top = max(0, min(image_height, math.floor(y1 - pad_y)))
    right = max(0, min(image_width, math.ceil(x2 + pad_x)))
    bottom = max(0, min(image_height, math.ceil(y2 + pad_y)))
    if right <= left or bottom <= top:
        return None, was_clipped, "clipped crop has zero area"
    return (left, top, right, bottom), was_clipped, None


def _category_map(coco: dict[str, Any], annotation_path: Path) -> dict[int, str]:
    category_map: dict[int, str] = {}
    for category in coco.get("categories", []):
        try:
            category_id = int(category["id"])
            name = str(category["name"]).strip().lower()
        except (KeyError, TypeError, ValueError):
            continue
        # The Roboflow export also contains a generic parent category "wound".
        if name in CLASS_TO_IDX:
            category_map[category_id] = name

    missing = set(CLASSES) - set(category_map.values())
    if missing:
        raise ValueError(
            f"{annotation_path} is missing expected wound categories: {', '.join(sorted(missing))}"
        )
    return category_map


def crop_coco_split(
    split_dir: Path,
    output_dir: Path,
    split_name: str,
    padding_fraction: float,
) -> Counter[str]:
    annotation_path = split_dir / "_annotations.coco.json"
    if not annotation_path.is_file():
        raise FileNotFoundError(f"COCO annotation file not found: {annotation_path}")
    with annotation_path.open("r", encoding="utf-8") as annotation_file:
        coco = json.load(annotation_file)

    category_map = _category_map(coco, annotation_path)
    images_by_id: dict[int, dict[str, Any]] = {}
    for image_info in coco.get("images", []):
        try:
            images_by_id[int(image_info["id"])] = image_info
        except (KeyError, TypeError, ValueError):
            continue

    annotations_by_image: dict[int, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for sequence, annotation in enumerate(coco.get("annotations", [])):
        try:
            image_id = int(annotation["image_id"])
            category_id = int(annotation["category_id"])
        except (KeyError, TypeError, ValueError):
            continue
        if category_id in category_map:
            annotations_by_image[image_id].append((sequence, annotation))

    counts: Counter[str] = Counter()
    counts["images_in_json"] = len(images_by_id)
    output_split = output_dir / split_name
    for class_name in CLASSES:
        (output_split / class_name).mkdir(parents=True, exist_ok=True)

    crop_sequence = 0
    for image_id, image_info in images_by_id.items():
        image_annotations = annotations_by_image.get(image_id, [])
        if not image_annotations:
            counts["images_without_target_annotations"] += 1
            continue

        file_name = image_info.get("file_name")
        if not isinstance(file_name, str) or not file_name:
            counts["missing_images"] += len(image_annotations)
            continue
        image_path = _safe_image_path(split_dir, file_name)
        if image_path is None or not image_path.is_file():
            counts["missing_images"] += len(image_annotations)
            print(f"  Warning: image missing or outside split directory: {file_name}")
            continue

        try:
            with Image.open(image_path) as image_file:
                image = image_file.convert("RGB")
        except (OSError, UnidentifiedImageError) as exc:
            counts["unreadable_images"] += len(image_annotations)
            print(f"  Warning: cannot read {image_path.name}: {exc}")
            continue

        image_width, image_height = image.size
        metadata_width = image_info.get("width")
        metadata_height = image_info.get("height")
        if (metadata_width, metadata_height) != (image_width, image_height):
            counts["metadata_dimension_mismatches"] += 1

        for sequence, annotation in image_annotations:
            class_name = category_map[int(annotation["category_id"])]
            pixel_box, was_clipped, error = _clip_box(
                annotation.get("bbox"), image_width, image_height, padding_fraction
            )
            if was_clipped:
                counts["clipped_boxes"] += 1
            if error is not None or pixel_box is None:
                counts["invalid_boxes"] += 1
                print(
                    f"  Warning: skipping annotation {annotation.get('id', sequence)} "
                    f"in {image_path.name}: {error}"
                )
                continue

            try:
                crop = image.crop(pixel_box)
                crop_sequence += 1
                annotation_id = re.sub(
                    r"[^A-Za-z0-9_-]+", "_", str(annotation.get("id", sequence))
                )
                crop_name = f"crop_{crop_sequence:06d}_img{image_id}_ann{annotation_id}.jpg"
                crop.save(output_split / class_name / crop_name, format="JPEG", quality=95)
                counts[class_name] += 1
            except (OSError, ValueError) as exc:
                counts["crop_save_errors"] += 1
                print(
                    f"  Warning: could not save annotation {annotation.get('id', sequence)} "
                    f"from {image_path.name}: {exc}"
                )

    print(
        f"[{split_name}] crops: "
        + ", ".join(f"{name}={counts[name]}" for name in CLASSES)
        + f" | clipped boxes={counts['clipped_boxes']}"
        + f" | skipped boxes={counts['invalid_boxes']}"
    )
    return counts


class CroppedWoundDataset(Dataset):
    """Read class folders with a fixed class order, including empty folders."""

    def __init__(self, root: Path, transform: transforms.Compose | None = None) -> None:
        self.root = root
        self.transform = transform
        self.classes = list(CLASSES)
        self.class_to_idx = dict(CLASS_TO_IDX)
        self.samples: list[tuple[str, int]] = []
        for class_name, class_index in self.class_to_idx.items():
            class_dir = root / class_name
            if not class_dir.is_dir():
                continue
            for image_path in sorted(class_dir.rglob("*")):
                if image_path.is_file() and image_path.suffix.lower() in IMAGE_EXTENSIONS:
                    self.samples.append((str(image_path), class_index))
        if not self.samples:
            raise RuntimeError(f"No cropped images found under {root}")
        self.targets = [label for _, label in self.samples]

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        image_path, label = self.samples[index]
        with Image.open(image_path) as image_file:
            image = image_file.convert("RGB")
        if self.transform is not None:
            image = self.transform(image)
        return image, label


class WoundEfficientNet(nn.Module):
    """EfficientNet-B0 feature extractor with the requested regularized MLP head."""

    def __init__(self, num_classes: int = len(CLASSES), hidden_dim: int = 256) -> None:
        super().__init__()
        self.backbone = timm.create_model(
            "efficientnet_b0", pretrained=True, num_classes=0
        )
        feature_dim = self.backbone.num_features
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.3),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        features = self.backbone(images)
        return self.classifier(features)


def make_class_weights(train_dataset: CroppedWoundDataset, device: torch.device) -> torch.Tensor:
    """Use softened inverse-frequency weights plus extra emphasis for cut/stab."""
    counts = Counter(train_dataset.targets)
    missing = [name for name, index in CLASS_TO_IDX.items() if counts[index] == 0]
    if missing:
        raise RuntimeError(
            "The training split has no crops for: " + ", ".join(missing)
        )

    total = len(train_dataset)
    frequency_weights = []
    for class_name, class_index in CLASS_TO_IDX.items():
        # Square-root inverse frequency is less aggressive than full balancing.
        frequency_weight = math.sqrt(total / (len(CLASSES) * counts[class_index]))
        frequency_weights.append(frequency_weight)

    # Guarantee extra emphasis for both hard negatives, even if their raw
    # frequency would otherwise make their inverse-frequency weight smaller.
    easy_class_max = max(
        frequency_weights[CLASS_TO_IDX["abrasions"]],
        frequency_weights[CLASS_TO_IDX["bruises"]],
    )
    weights = frequency_weights.copy()
    for hard_class in ("cut", "stab"):
        hard_index = CLASS_TO_IDX[hard_class]
        weights[hard_index] = max(weights[hard_index] * 1.75, easy_class_max * 1.5)
    weight_tensor = torch.tensor(weights, dtype=torch.float32, device=device)
    # Keep the average weight at one so the loss scale remains comparable.
    return weight_tensor / weight_tensor.mean()


def make_transforms() -> tuple[transforms.Compose, transforms.Compose]:
    train_transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=15),
            transforms.ColorJitter(
                brightness=0.20, contrast=0.20, saturation=0.15, hue=0.03
            ),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    valid_transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    return train_transform, valid_transform


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
) -> tuple[float, float]:
    is_training = optimizer is not None
    model.train(is_training)
    total_loss = 0.0
    total_correct = 0
    total_samples = 0

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
            total_correct += (logits.argmax(dim=1) == labels).sum().item()
            total_samples += batch_size

    if total_samples == 0:
        raise RuntimeError("DataLoader returned no samples")
    return total_loss / total_samples, total_correct / total_samples


def main() -> None:
    args = parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.num_workers < 0:
        raise SystemExit("epochs and batch-size must be positive; num-workers cannot be negative")
    if args.learning_rate <= 0 or args.weight_decay < 0:
        raise SystemExit("learning-rate must be positive and weight-decay cannot be negative")
    if not 0 <= args.crop_padding <= 1:
        raise SystemExit("crop-padding must be between 0 and 1")
    if args.hidden_dim < 1:
        raise SystemExit("hidden-dim must be positive")

    data_root = args.data_root.resolve()
    output_dir = args.output_dir.resolve()
    if not data_root.is_dir():
        raise SystemExit(f"Dataset root does not exist: {data_root}")
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
        if not args.overwrite:
            raise SystemExit(
                f"Output directory is not empty: {output_dir}\n"
                "Choose another --output-dir or pass --overwrite to rebuild it."
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

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
    if len(train_dataset) == 0 or len(valid_dataset) == 0:
        raise RuntimeError("Both train and valid splits must contain cropped images")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pin_memory = device.type == "cuda"
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=pin_memory,
        persistent_workers=args.num_workers > 0,
    )
    valid_loader = DataLoader(
        valid_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=pin_memory,
        persistent_workers=args.num_workers > 0,
    )

    weights = make_class_weights(train_dataset, device)
    print("Class order: " + ", ".join(CLASSES))
    print(
        "Training crop counts: "
        + ", ".join(
            f"{name}={Counter(train_dataset.targets)[index]}" for name, index in CLASS_TO_IDX.items()
        )
    )
    print("Cross-entropy weights: " + ", ".join(f"{value:.3f}" for value in weights.tolist()))
    print(f"Device: {device}; train crops: {len(train_dataset)}; valid crops: {len(valid_dataset)}")

    model = WoundEfficientNet(num_classes=len(CLASSES), hidden_dim=args.hidden_dim).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )

    best_valid_accuracy = -1.0
    checkpoint_path = output_dir / "best_efficientnet_b0_wound.pt"
    for epoch in range(1, args.epochs + 1):
        train_loss, train_accuracy = run_epoch(
            model, train_loader, criterion, device, optimizer=optimizer
        )
        valid_loss, valid_accuracy = run_epoch(model, valid_loader, criterion, device)
        print(
            f"Epoch {epoch:03d}/{args.epochs:03d} | "
            f"Train Loss: {train_loss:.4f} | Train Top-1: {train_accuracy * 100:.2f}% | "
            f"Valid Loss: {valid_loss:.4f} | Valid Top-1: {valid_accuracy * 100:.2f}%"
        )

        if valid_accuracy > best_valid_accuracy:
            best_valid_accuracy = valid_accuracy
            torch.save(
                {
                    "model_name": "efficientnet_b0",
                    "model_state_dict": model.state_dict(),
                    "classes": list(CLASSES),
                    "class_to_idx": dict(CLASS_TO_IDX),
                    "input_size": 224,
                    "mean": IMAGENET_MEAN,
                    "std": IMAGENET_STD,
                    "best_valid_accuracy": best_valid_accuracy,
                    "epoch": epoch,
                    "class_weights": weights.detach().cpu(),
                },
                checkpoint_path,
            )

    print(f"Best validation Top-1: {best_valid_accuracy * 100:.2f}%")
    print(f"Best checkpoint saved to: {checkpoint_path}")
    print("The test split was not used for training or checkpoint selection.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTraining interrupted by user.", file=sys.stderr)
        raise SystemExit(130)
