"""Local dataset adapter for RGB facial crops paired with OBJ landmarks."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Sequence

try:
    import torch
    from PIL import Image, ImageOps, UnidentifiedImageError
    from torch.utils.data import Dataset
except ImportError as exc:  # pragma: no cover - dependency guard
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install emergency_cdss/requirements.txt."
    ) from exc


VERTEX_PATTERN = re.compile(
    r"^v\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*$"
)
SOURCE_ROTATION_DEGREES = 90


def parse_obj_vertices(lines: Sequence[str]) -> torch.Tensor:
    """Parse OBJ ``v x y z`` lines into a ``[num_vertices, 3]`` tensor."""

    vertices: list[list[float]] = []
    for line in lines:
        match = VERTEX_PATTERN.match(str(line).strip())
        if match is None:
            continue
        vertices.append([float(value) for value in match.groups()])
    if not vertices:
        raise ValueError("The 3Dlandmark field contains no OBJ vertex lines")
    values = torch.tensor(vertices, dtype=torch.float32)
    if not torch.isfinite(values).all():
        raise ValueError("Landmark vertices contain non-finite values")
    return values


def normalize_landmarks(vertices: torch.Tensor) -> torch.Tensor:
    """Center and scale landmarks without changing their topology."""

    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ValueError("vertices must have shape [num_vertices, 3]")
    centered = vertices - vertices.mean(dim=0, keepdim=True)
    scale = centered.norm(dim=1).amax().clamp_min(1e-6)
    return centered / scale


def flatten_landmarks(vertices: torch.Tensor) -> torch.Tensor:
    return normalize_landmarks(vertices).reshape(-1)


class FaceMultimodalDataset(Dataset):
    """Read a prepared manifest and return image, normalized landmarks, label."""

    def __init__(
        self,
        manifest_path: Path,
        *,
        transform: Any | None = None,
        subjects: set[str] | None = None,
        class_names: Sequence[str] | None = None,
    ) -> None:
        self.manifest_path = Path(manifest_path)
        self.root = self.manifest_path.parent
        self.transform = transform
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not payload:
            raise ValueError(f"Manifest must be a non-empty JSON list: {self.manifest_path}")
        records = [record for record in payload if isinstance(record, dict)]
        if subjects is not None:
            records = [record for record in records if str(record.get("subject_id")) in subjects]
        if not records:
            raise ValueError("No records remain after subject filtering")

        inferred_classes = sorted({str(record["target"]) for record in records})
        self.classes = tuple(class_names or inferred_classes)
        self.class_to_idx = {name: index for index, name in enumerate(self.classes)}
        self.records: list[dict[str, Any]] = []
        for record in records:
            target = str(record.get("target"))
            if target not in self.class_to_idx:
                raise ValueError(f"Unknown class {target!r} in manifest")
            if not record.get("image"):
                raise ValueError("Manifest record has no image path; run preparation without --skip-images")
            label_path = self.root / str(record["label"])
            if not label_path.is_file():
                raise FileNotFoundError(label_path)
            self.records.append(record)
        self.targets = [self.class_to_idx[str(record["target"])] for record in self.records]
        self.subject_ids = [str(record["subject_id"]) for record in self.records]
        self.landmark_dim = self._infer_landmark_dim()

    def _infer_landmark_dim(self) -> int:
        payload = json.loads((self.root / str(self.records[0]["label"])).read_text(encoding="utf-8"))
        vertices = parse_obj_vertices(payload.get("3Dlandmark", []))
        return int(vertices.numel())

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        image_path = self.root / str(record["image"])
        label_path = self.root / str(record["label"])
        try:
            with Image.open(image_path) as image_file:
                image = ImageOps.exif_transpose(image_file.convert("RGB")).rotate(
                    SOURCE_ROTATION_DEGREES, expand=True
                )
        except (OSError, UnidentifiedImageError) as exc:
            raise RuntimeError(f"Could not read image: {image_path}") from exc
        if self.transform is not None:
            image = self.transform(image)
        payload = json.loads(label_path.read_text(encoding="utf-8"))
        landmark_tensor = flatten_landmarks(parse_obj_vertices(payload.get("3Dlandmark", [])))
        if landmark_tensor.numel() != self.landmark_dim:
            raise ValueError(
                f"Inconsistent landmark dimension for {label_path}: "
                f"expected {self.landmark_dim}, got {landmark_tensor.numel()}"
            )
        return {
            "image": image,
            "landmarks": landmark_tensor,
            "target": torch.tensor(self.targets[index], dtype=torch.long),
            "subject_id": self.subject_ids[index],
            "sample_id": str(record.get("sample_id", record.get("subject_id", ""))),
            "view": str(record.get("view", "")),
            "image_path": str(image_path),
            "label_path": str(label_path),
        }


def split_subjects(
    subject_ids: Sequence[str],
    *,
    seed: int = 42,
    train_fraction: float = 0.6,
    valid_fraction: float = 0.2,
) -> dict[str, set[str]]:
    """Create deterministic, identity-disjoint train/valid/test subject sets."""

    import random

    unique = sorted(set(subject_ids))
    if len(unique) < 3:
        raise ValueError("At least three identities are required for train/valid/test splitting")
    if not (0 < train_fraction < 1 and 0 < valid_fraction < 1 and train_fraction + valid_fraction < 1):
        raise ValueError("Split fractions must be positive and sum to less than one")
    generator = random.Random(seed)
    generator.shuffle(unique)
    train_count = max(1, int(math.floor(len(unique) * train_fraction)))
    valid_count = max(1, int(math.floor(len(unique) * valid_fraction)))
    if train_count + valid_count >= len(unique):
        valid_count = 1
        train_count = len(unique) - 2
    return {
        "train": set(unique[:train_count]),
        "valid": set(unique[train_count : train_count + valid_count]),
        "test": set(unique[train_count + valid_count :]),
    }


__all__ = [
    "FaceMultimodalDataset",
    "flatten_landmarks",
    "normalize_landmarks",
    "parse_obj_vertices",
    "SOURCE_ROTATION_DEGREES",
    "split_subjects",
]
