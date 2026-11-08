"""EfficientNet image classifier used for wound images."""

from __future__ import annotations

try:
    import timm
    import torch
    import torch.nn as nn
except ImportError as exc:  # pragma: no cover - exercised only without dependencies
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install emergency_cdss/requirements.txt."
    ) from exc


class WoundEfficientNet(nn.Module):
    """EfficientNet-B0 feature extractor with a configurable MLP head."""

    def __init__(
        self,
        num_classes: int = 4,
        hidden_dim: int = 256,
        dropout: float = 0.3,
        pretrained: bool = True,
    ) -> None:
        super().__init__()
        if num_classes < 1:
            raise ValueError("num_classes must be positive")
        if hidden_dim < 1:
            raise ValueError("hidden_dim must be positive")
        if not 0 <= dropout < 1:
            raise ValueError("dropout must be in [0, 1)")

        self.backbone = timm.create_model(
            "efficientnet_b0", pretrained=pretrained, num_classes=0
        )
        feature_dim = self.backbone.num_features
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        features = self.backbone(images)
        return self.classifier(features)


__all__ = ["WoundEfficientNet"]
