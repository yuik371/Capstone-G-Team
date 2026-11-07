"""Image preprocessing shared by image-classification datasets."""

from __future__ import annotations

try:
    from torchvision import transforms
except ImportError as exc:  # pragma: no cover - exercised only without dependencies
    missing = getattr(exc, "name", None) or str(exc)
    raise SystemExit(
        f"Missing dependency ({missing}). Install emergency_cdss/requirements.txt."
    ) from exc


IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def make_transforms(
    image_size: int = 224,
) -> tuple[transforms.Compose, transforms.Compose]:
    """Return train and validation transforms for ImageNet backbones.

    Augmentation is applied only to training data. Validation and test data use
    deterministic preprocessing so metrics reflect the same input policy.
    """

    train_transform = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
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
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    return train_transform, valid_transform


__all__ = ["IMAGENET_MEAN", "IMAGENET_STD", "make_transforms"]

