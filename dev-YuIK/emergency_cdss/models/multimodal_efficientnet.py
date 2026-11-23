"""EfficientNet-B0 image baseline and landmark-fused classifier."""

from __future__ import annotations

try:
    import timm
    import torch
    import torch.nn as nn
except ImportError as exc:  # pragma: no cover - dependency guard
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install emergency_cdss/requirements.txt."
    ) from exc


class EfficientNetB0Multimodal(nn.Module):
    """Compact EfficientNet-B0 with an optional structured landmark branch.

    ``mode='vision'`` is the requested image-only baseline. ``mode='joint'``
    projects normalized landmark coordinates into a compact embedding and
    concatenates it with the pooled image representation before classification.
    """

    def __init__(
        self,
        landmark_dim: int,
        num_classes: int,
        *,
        mode: str = "joint",
        landmark_hidden_dim: int = 128,
        fusion_dim: int = 256,
        dropout: float = 0.3,
        pretrained: bool = True,
    ) -> None:
        super().__init__()
        if landmark_dim < 1 or num_classes < 1:
            raise ValueError("landmark_dim and num_classes must be positive")
        if mode not in {"vision", "joint"}:
            raise ValueError("mode must be 'vision' or 'joint'")
        if not 0 <= dropout < 1:
            raise ValueError("dropout must be in [0, 1)")
        self.mode = mode
        self.landmark_dim = landmark_dim
        self.num_classes = num_classes
        self.backbone = timm.create_model(
            "efficientnet_b0", pretrained=pretrained, num_classes=0
        )
        image_dim = int(self.backbone.num_features)
        self.image_dim = image_dim
        if mode == "joint":
            self.landmark_branch = nn.Sequential(
                nn.LayerNorm(landmark_dim),
                nn.Linear(landmark_dim, landmark_hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(landmark_hidden_dim, landmark_hidden_dim),
                nn.GELU(),
            )
            self.fusion = nn.Sequential(
                nn.Linear(image_dim + landmark_hidden_dim, fusion_dim),
                nn.LayerNorm(fusion_dim),
                nn.GELU(),
                nn.Dropout(dropout),
            )
        else:
            self.landmark_branch = None
            self.fusion = None
        classifier_input_dim = image_dim if mode == "vision" else fusion_dim
        self.classifier = nn.Sequential(
            nn.Linear(classifier_input_dim, fusion_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(fusion_dim, num_classes),
        )

    def forward(
        self,
        images: torch.Tensor,
        landmarks: torch.Tensor | None = None,
        *,
        return_features: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, dict[str, torch.Tensor]]:
        image_features = self.backbone(images)
        if self.mode == "vision":
            representation = image_features
            landmark_features = image_features.new_zeros((image_features.shape[0], 0))
        else:
            if landmarks is None:
                raise ValueError("landmarks are required in joint mode")
            landmark_features = self.landmark_branch(landmarks)
            representation = self.fusion(torch.cat([image_features, landmark_features], dim=1))
        logits = self.classifier(representation)
        if return_features:
            return logits, {
                "image_features": image_features,
                "landmark_features": landmark_features,
                "representation": representation,
            }
        return logits


def count_parameters(model: nn.Module) -> dict[str, int]:
    total = sum(parameter.numel() for parameter in model.parameters())
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    return {"total": int(total), "trainable": int(trainable)}


__all__ = ["EfficientNetB0Multimodal", "count_parameters"]
