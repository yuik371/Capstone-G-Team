"""EfficientNet-B0 and 3D facial-mesh classifiers for expression recognition."""

from __future__ import annotations

import torch
from torch import nn
import timm


class FaceExpressionNet(nn.Module):
    """EfficientNet-B0 with an image-only or landmark-fused MLP head.

    The landmark input is a flattened, per-mesh centered and scale-normalized
    array of xyz vertices. ``fusion=False`` is the matched vision-only baseline.
    """

    def __init__(
        self,
        num_classes: int,
        landmark_dim: int,
        fusion: bool,
        pretrained: bool = True,
        dropout: float = 0.35,
    ) -> None:
        super().__init__()
        if num_classes < 2 or landmark_dim < 1:
            raise ValueError("num_classes must be >= 2 and landmark_dim must be positive")

        self.fusion = fusion
        self.backbone = timm.create_model(
            "efficientnet_b0", pretrained=pretrained, num_classes=0
        )
        image_dim = int(self.backbone.num_features)
        self.image_projection = nn.Sequential(
            nn.Linear(image_dim, 256),
            nn.BatchNorm1d(256),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        if fusion:
            self.landmark_encoder = nn.Sequential(
                nn.LayerNorm(landmark_dim),
                nn.Linear(landmark_dim, 512),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(512, 128),
                nn.GELU(),
                nn.Dropout(dropout),
            )
            classifier_input_dim = 384
        else:
            self.landmark_encoder = None
            classifier_input_dim = 256

        self.classifier = nn.Sequential(
            nn.Linear(classifier_input_dim, 192),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(192, num_classes),
        )

    def forward(self, images: torch.Tensor, landmarks: torch.Tensor) -> torch.Tensor:
        image_features = self.image_projection(self.backbone(images))
        if self.fusion:
            if landmarks.ndim != 2:
                raise ValueError("landmarks must have shape [batch, feature_dim]")
            landmark_features = self.landmark_encoder(landmarks)
            image_features = torch.cat((image_features, landmark_features), dim=1)
        return self.classifier(image_features)


__all__ = ["FaceExpressionNet"]
