"""Dataset adapter for landmarks, pose coordinates, vitals, and tabular data."""

from __future__ import annotations

from typing import Sequence

try:
    import torch
    from torch.utils.data import Dataset
except ImportError as exc:  # pragma: no cover - exercised only without dependencies
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install emergency_cdss/requirements.txt."
    ) from exc


class LandmarkDataset(Dataset):
    """Wrap fixed-length numeric features and integer labels as tensors.

    The same adapter can represent face landmarks, 3D pose features, clinical
    measurements, or stroke follow-up vectors after preprocessing. Variable-
    length sequences should be padded or summarized in a dedicated collate
    function before reaching this dataset.
    """

    def __init__(
        self,
        features: Sequence[Sequence[float]] | torch.Tensor,
        targets: Sequence[int] | torch.Tensor,
    ) -> None:
        self.features = torch.as_tensor(features, dtype=torch.float32)
        self.targets = torch.as_tensor(targets, dtype=torch.long)
        if self.features.ndim != 2:
            raise ValueError("features must have shape [num_samples, num_features]")
        if self.targets.ndim != 1:
            raise ValueError("targets must have shape [num_samples]")
        if len(self.features) != len(self.targets):
            raise ValueError("features and targets must contain the same number of samples")
        if len(self.features) == 0:
            raise ValueError("features and targets cannot be empty")

    def __len__(self) -> int:
        return len(self.targets)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.features[index], self.targets[index]


__all__ = ["LandmarkDataset"]

