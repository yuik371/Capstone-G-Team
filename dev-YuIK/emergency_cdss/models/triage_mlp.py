"""Small MLP for numeric triage features such as landmarks and vitals.

This model is modality-agnostic: it can consume face landmarks, pose-derived
angles, tabular clinical values, or a fused numeric feature vector. A future
multimodal model can use it as the structured-data branch beside an image
encoder.
"""

from __future__ import annotations

try:
    import torch
    import torch.nn as nn
except ImportError as exc:  # pragma: no cover - exercised only without dependencies
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install emergency_cdss/requirements.txt."
    ) from exc


class TriageMLP(nn.Module):
    """Configurable classifier for fixed-length numeric features."""

    def __init__(
        self,
        input_dim: int,
        num_classes: int,
        hidden_dim: int = 128,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        if input_dim < 1 or num_classes < 1 or hidden_dim < 1:
            raise ValueError("input_dim, num_classes, and hidden_dim must be positive")
        if not 0 <= dropout < 1:
            raise ValueError("dropout must be in [0, 1)")
        self.network = nn.Sequential(
            nn.LayerNorm(input_dim),
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features)


__all__ = ["TriageMLP"]

