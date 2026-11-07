"""Wound image dataset preparation and loading.

This module owns the Roboflow COCO-to-crop conversion used by the current
wound classifier. The resulting directory layout is deliberately compatible
with an ImageFolder-style dataset::

    dataset/
      train/{abrasions,bruises,cut,stab}/
      valid/{abrasions,bruises,cut,stab}/
      test/{abrasions,bruises,cut,stab}/

Keeping the COCO parsing here means future burn, stroke, dermatology, or
medication image loaders can expose a similar dataset interface without
coupling their annotation formats to the training script.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import torch
    from PIL import Image, UnidentifiedImageError
    from torch.utils.data import Dataset
except ImportError as exc:  # pragma: no cover - exercised only without dependencies
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install emergency_cdss/requirements.txt."
    ) from exc


WOUND_CLASSES = ("abrasions", "bruises", "cut", "stab")
WOUND_CLASS_TO_IDX = {name: index for index, name in enumerate(WOUND_CLASSES)}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def _safe_image_path(split_dir: Path, file_name: str) -> Path | None:
    """Resolve a COCO image path without allowing directory traversal."""

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
    """Convert COCO ``xywh`` to a safe Pillow crop box.

    Returns ``(pixel_box, was_clipped, error)``. Malformed, non-finite,
    non-positive, and completely out-of-frame boxes are rejected cleanly.
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
        if name in WOUND_CLASS_TO_IDX:
            category_map[category_id] = name

    missing = set(WOUND_CLASSES) - set(category_map.values())
    if missing:
        raise ValueError(
            f"{annotation_path} is missing expected wound categories: "
            f"{', '.join(sorted(missing))}"
        )
    return category_map


def crop_coco_split(
    split_dir: Path,
    output_dir: Path,
    split_name: str,
    padding_fraction: float = 0.05,
) -> Counter[str]:
    """Crop wound annotations from one Roboflow COCO split.

    The function returns counters for auditability. It never silently accepts
    malformed boxes or paths outside the split directory.
    """

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
    for class_name in WOUND_CLASSES:
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
        if (image_info.get("width"), image_info.get("height")) != (
            image_width,
            image_height,
        ):
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
        + ", ".join(f"{name}={counts[name]}" for name in WOUND_CLASSES)
        + f" | clipped boxes={counts['clipped_boxes']}"
        + f" | skipped boxes={counts['invalid_boxes']}"
    )
    return counts


class CroppedWoundDataset(Dataset):
    """Read wound class folders with a fixed class order."""

    def __init__(self, root: Path, transform: Any | None = None) -> None:
        self.root = Path(root)
        self.transform = transform
        self.classes = list(WOUND_CLASSES)
        self.class_to_idx = dict(WOUND_CLASS_TO_IDX)
        self.samples: list[tuple[str, int]] = []
        for class_name, class_index in self.class_to_idx.items():
            class_dir = self.root / class_name
            if not class_dir.is_dir():
                continue
            for image_path in sorted(class_dir.rglob("*")):
                if image_path.is_file() and image_path.suffix.lower() in IMAGE_EXTENSIONS:
                    self.samples.append((str(image_path), class_index))
        if not self.samples:
            raise RuntimeError(f"No cropped images found under {self.root}")
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


def make_class_weights(
    train_dataset: CroppedWoundDataset,
    device: torch.device,
    mode: str = "custom",
) -> torch.Tensor:
    """Build the current wound-class loss weights.

    ``custom`` preserves the original project's extra emphasis for ``cut`` and
    ``stab``. ``sqrt`` is a milder inverse-frequency option and ``none``
    disables weighting. The function is kept with the wound dataset because
    the custom rule is domain-specific; future datasets should define their
    own imbalance policy.
    """

    counts = Counter(train_dataset.targets)
    missing = [name for name, index in WOUND_CLASS_TO_IDX.items() if counts[index] == 0]
    if missing:
        raise RuntimeError("The training split has no crops for: " + ", ".join(missing))

    total = len(train_dataset)
    frequency_weights = [
        math.sqrt(total / (len(WOUND_CLASSES) * counts[class_index]))
        for class_index in range(len(WOUND_CLASSES))
    ]
    if mode == "none":
        weights = [1.0] * len(WOUND_CLASSES)
    elif mode == "sqrt":
        weights = frequency_weights
    elif mode == "custom":
        easy_class_max = max(
            frequency_weights[WOUND_CLASS_TO_IDX["abrasions"]],
            frequency_weights[WOUND_CLASS_TO_IDX["bruises"]],
        )
        weights = frequency_weights.copy()
        for hard_class in ("cut", "stab"):
            hard_index = WOUND_CLASS_TO_IDX[hard_class]
            weights[hard_index] = max(weights[hard_index] * 1.75, easy_class_max * 1.5)
    else:
        raise ValueError(f"Unsupported class-weight mode: {mode}")

    weight_tensor = torch.tensor(weights, dtype=torch.float32, device=device)
    return weight_tensor / weight_tensor.mean()


__all__ = [
    "CroppedWoundDataset",
    "IMAGE_EXTENSIONS",
    "WOUND_CLASSES",
    "WOUND_CLASS_TO_IDX",
    "crop_coco_split",
    "make_class_weights",
]
