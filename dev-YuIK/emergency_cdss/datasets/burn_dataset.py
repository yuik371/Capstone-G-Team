"""Folder-based burn image dataset loader.

The wound pipeline needs COCO box cropping, while a burn classifier will
usually receive already-cropped images grouped by severity. This loader keeps
that distinction explicit and accepts configurable class names so the final
clinical labeling policy does not have to be hard-coded here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

try:
    import torch
    from PIL import Image
    from torch.utils.data import Dataset
except ImportError as exc:  # pragma: no cover - exercised only without dependencies
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install emergency_cdss/requirements.txt."
    ) from exc

from .wound_dataset import IMAGE_EXTENSIONS


DEFAULT_BURN_CLASSES = ("degree_1", "degree_2", "degree_3")


class BurnDataset(Dataset):
    """Load burn images from ``root/<class_name>`` directories."""

    def __init__(
        self,
        root: Path,
        transform: Any | None = None,
        classes: Sequence[str] = DEFAULT_BURN_CLASSES,
    ) -> None:
        self.root = Path(root)
        self.transform = transform
        self.classes = list(classes)
        if not self.classes or len(set(self.classes)) != len(self.classes):
            raise ValueError("classes must be a non-empty sequence of unique names")
        self.class_to_idx = {name: index for index, name in enumerate(self.classes)}
        self.samples: list[tuple[str, int]] = []
        for class_name, class_index in self.class_to_idx.items():
            class_dir = self.root / class_name
            if not class_dir.is_dir():
                continue
            for image_path in sorted(class_dir.rglob("*")):
                if image_path.is_file() and image_path.suffix.lower() in IMAGE_EXTENSIONS:
                    self.samples.append((str(image_path), class_index))
        if not self.samples:
            raise RuntimeError(f"No burn images found under {self.root}")
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


__all__ = ["BurnDataset", "DEFAULT_BURN_CLASSES"]

