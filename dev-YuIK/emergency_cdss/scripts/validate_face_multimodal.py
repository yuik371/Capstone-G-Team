"""Identity-disjoint EfficientNet-B0 and landmark-fusion validation pipeline.

Runs five-fold subject-grouped cross-validation. Each fold uses six subjects
for training, two for validation, and two for its untouched outer test set.
Every subject is tested exactly once across the out-of-fold predictions.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sklearn
import timm
import torch
import torch.nn.functional as F
import torchvision
from PIL import Image, ImageDraw, ImageEnhance
from scipy.spatial import cKDTree
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

from emergency_cdss.models.face_multimodal import FaceExpressionNet


CLASSES = ["Anger", "Disgust", "Fear", "Joy", "Neutral", "Sadness", "Surprise"]
CLASS_TO_ID = {name: index for index, name in enumerate(CLASSES)}
IMAGE_MEAN = (0.485, 0.456, 0.406)
IMAGE_STD = (0.229, 0.224, 0.225)


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve()
    project_root = here.parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root", type=Path, default=project_root / "안면_인식_랜드마크_Sample"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=project_root / "outputs" / "face_multimodal_cvpr_2027"
    )
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--freeze-backbone-epochs", type=int, default=3)
    parser.add_argument("--pretrained", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--time-budget-hours", type=float, default=4.0)
    parser.add_argument("--cpu-benchmark-runs", type=int, default=20)
    parser.add_argument("--gpu-benchmark-runs", type=int, default=100)
    parser.add_argument("--summarize-only", action="store_true")
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def mesh_from_json(annotation: dict[str, Any]) -> np.ndarray:
    raw = annotation.get("3Dlandmark")
    if not isinstance(raw, list) or not raw:
        raise ValueError("JSON has no 3Dlandmark vertex list")
    vertices: list[list[float]] = []
    for item in raw:
        fields = str(item).split()
        if len(fields) != 4 or fields[0].lower() != "v":
            continue
        vertices.append([float(value) for value in fields[1:]])
    points = np.asarray(vertices, dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 100:
        raise ValueError(f"Expected a dense xyz mesh, got {points.shape}")
    if not np.isfinite(points).all():
        raise ValueError("Mesh contains non-finite coordinates")
    return points


def normalize_mesh(points: np.ndarray) -> np.ndarray:
    centered = points - points.mean(axis=0, keepdims=True)
    width = float(np.quantile(points[:, 0], 0.98) - np.quantile(points[:, 0], 0.02))
    if not math.isfinite(width) or width < 1e-6:
        width = float(np.linalg.norm(np.ptp(points, axis=0)))
    return (centered / max(width, 1e-6)).astype(np.float32)


def mesh_geometry(points: np.ndarray) -> dict[str, float]:
    """Compute topology-free mirror and vertical-band shape descriptors."""
    mirrored = points.copy()
    mirrored[:, 0] *= -1.0
    tree = cKDTree(mirrored)
    distances = tree.query(points, k=1, workers=1)[0]
    y = points[:, 1]
    cuts = np.quantile(y, [1 / 3, 2 / 3])
    bands = (y <= cuts[0], (y > cuts[0]) & (y <= cuts[1]), y > cuts[1])
    return {
        "asymmetry_global": float(np.mean(distances)),
        "asymmetry_lower": float(np.mean(distances[bands[0]])),
        "asymmetry_middle": float(np.mean(distances[bands[1]])),
        "asymmetry_upper": float(np.mean(distances[bands[2]])),
    }


def square_crop(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    height, width = image.shape[:2]
    x1, y1, x2, y2 = box
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)
    side = max(x2 - x1, y2 - y1, 2)
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    side = min(side, max(width, height))
    sx1, sy1 = int(round(cx - side / 2)), int(round(cy - side / 2))
    sx2, sy2 = sx1 + side, sy1 + side
    canvas = np.zeros((side, side, 3), dtype=np.uint8)
    src_x1, src_y1 = max(0, sx1), max(0, sy1)
    src_x2, src_y2 = min(width, sx2), min(height, sy2)
    dst_x1, dst_y1 = src_x1 - sx1, src_y1 - sy1
    canvas[dst_y1 : dst_y1 + src_y2 - src_y1, dst_x1 : dst_x1 + src_x2 - src_x1] = image[
        src_y1:src_y2, src_x1:src_x2
    ]
    return cv2.resize(canvas, (224, 224), interpolation=cv2.INTER_AREA)


def crop_face(path: Path, cascade: cv2.CascadeClassifier) -> tuple[np.ndarray, tuple[int, int, int, int], bool]:
    try:
        with Image.open(path) as source:
            image = np.asarray(source.convert("RGB"))
    except OSError as exc:
        raise ValueError(f"Could not read image: {path}") from exc
    # The supplied photographs are stored with the head to the right; rotate
    # counter-clockwise before face detection and use the same policy for all.
    image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    boxes = cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5, minSize=(64, 64))
    if len(boxes):
        x, y, w, h = max(boxes, key=lambda item: item[2] * item[3])
        pad = int(round(0.28 * max(w, h)))
        box = (x - pad, y - pad, x + w + pad, y + h + pad)
        return square_crop(image, box), box, True

    # Fixed central fallback; its use is counted and written to the manifest.
    height, width = image.shape[:2]
    box = (int(width * 0.24), int(height * 0.25), int(width * 0.76), int(height * 0.73))
    return square_crop(image, box), box, False


def discover_records(data_root: Path, image_size: int) -> list[dict[str, Any]]:
    del image_size  # crop_face emits canonical 224x224 RGB crops
    label_root = data_root / "02.라벨링데이터"
    image_root = data_root / "01.원천데이터" / "image"
    if not label_root.is_dir() or not image_root.is_dir():
        raise FileNotFoundError(f"Expected image and JSON folders beneath {data_root}")

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cascade.empty():
        raise RuntimeError("OpenCV frontal-face cascade could not be loaded")

    records: list[dict[str, Any]] = []
    for json_path in sorted(label_root.glob("*/json/*.json")):
        annotation = json.loads(json_path.read_text(encoding="utf-8"))
        label_name = annotation.get("expression")
        if label_name not in CLASS_TO_ID:
            raise ValueError(f"Unknown expression label {label_name!r} in {json_path}")
        subject = str(annotation.get("id") or json_path.parent.parent.name)
        image_path = image_root / json_path.parent.parent.name / f"{json_path.stem}.png"
        if not image_path.is_file():
            raise FileNotFoundError(f"No paired image for {json_path}: {image_path}")

        raw_mesh = mesh_from_json(annotation)
        mesh = normalize_mesh(raw_mesh)
        crop, box, detected = crop_face(image_path, cascade)
        records.append(
            {
                "sample_id": json_path.stem,
                "subject_id": subject,
                "label": CLASS_TO_ID[label_name],
                "label_name": label_name,
                "light": str(annotation.get("light", "unknown")),
                "image_path": str(image_path.resolve()),
                "json_path": str(json_path.resolve()),
                "crop": crop,
                "crop_box": list(map(int, box)),
                "face_detected": detected,
                "mesh": mesh,
                "landmark_features": mesh.reshape(-1),
                "geometry": mesh_geometry(mesh),
                "raw_mesh_vertices": int(len(raw_mesh)),
            }
        )

    if not records:
        raise ValueError(f"No paired samples were discovered under {data_root}")
    counts = Counter(record["label_name"] for record in records)
    expected = set(CLASSES)
    if set(counts) != expected:
        raise ValueError(f"Dataset must contain every class {sorted(expected)}; found {dict(counts)}")

    subjects = sorted({record["subject_id"] for record in records})
    if len(subjects) < 10:
        raise ValueError(f"Five-fold group validation needs >=10 subjects; found {len(subjects)}")
    for subject in subjects:
        subject_records = [record for record in records if record["subject_id"] == subject]
        if len(subject_records) != 21 or {r["label_name"] for r in subject_records} != expected:
            raise ValueError(
                f"Expected 21 samples and all seven labels per subject; {subject} has "
                f"{len(subject_records)} samples"
            )
    return records


def make_folds(records: list[dict[str, Any]], seed: int) -> list[dict[str, list[str]]]:
    subjects = sorted({record["subject_id"] for record in records})
    rng = np.random.default_rng(seed)
    order = list(np.asarray(subjects)[rng.permutation(len(subjects))])
    if len(order) != 10:
        raise ValueError(f"This protocol is fixed for 10 subjects; found {len(order)}")
    test_groups = [list(map(str, order[i : i + 2])) for i in range(0, len(order), 2)]
    folds = []
    for index, test_subjects in enumerate(test_groups):
        val_subjects = test_groups[(index + 1) % len(test_groups)]
        train_subjects = sorted(set(subjects) - set(test_subjects) - set(val_subjects))
        folds.append(
            {
                "train": train_subjects,
                "validation": sorted(val_subjects),
                "test": sorted(test_subjects),
            }
        )
    return folds


class FaceMeshDataset(Dataset):
    def __init__(self, records: list[dict[str, Any]], image_size: int, training: bool):
        self.records = records
        self.training = training
        self.image_transform = transforms.Compose(
            [
                transforms.Resize((image_size, image_size)),
                transforms.ToTensor(),
                transforms.Normalize(IMAGE_MEAN, IMAGE_STD),
            ]
        )
        self.color_jitter = transforms.ColorJitter(
            brightness=0.18, contrast=0.18, saturation=0.12, hue=0.025
        )

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, int]:
        record = self.records[index]
        image = Image.fromarray(record["crop"], mode="RGB")
        points = record["mesh"].copy()
        if self.training:
            if random.random() < 0.5:
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                points[:, 0] *= -1.0
            image = self.color_jitter(image)
        image_tensor = self.image_transform(image)
        landmark_tensor = torch.from_numpy(points.reshape(-1).astype(np.float32))
        return image_tensor, landmark_tensor, torch.tensor(record["label"], dtype=torch.long), index


def batches(
    records: list[dict[str, Any]], args: argparse.Namespace, training: bool
) -> DataLoader:
    dataset = FaceMeshDataset(records, args.image_size, training)
    return DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=training,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
        drop_last=False,
    )


def split_records(
    records: list[dict[str, Any]], subjects: list[str]
) -> list[dict[str, Any]]:
    selected = set(subjects)
    return [record for record in records if record["subject_id"] in selected]


def collect_predictions(
    model: FaceExpressionNet,
    loader: DataLoader,
    device: torch.device,
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    model.eval()
    probabilities: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    indices: list[np.ndarray] = []
    with torch.inference_mode():
        for images, landmarks, targets, sample_indices in loader:
            images = images.to(device, non_blocking=True)
            landmarks = landmarks.to(device, non_blocking=True)
            logits = model(images, landmarks)
            probabilities.append(torch.softmax(logits, dim=1).cpu().numpy())
            labels.append(targets.numpy())
            indices.append(sample_indices.numpy())
    return np.concatenate(labels), np.concatenate(probabilities), np.concatenate(indices).tolist()


def metric_bundle(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    predictions = probabilities.argmax(axis=1)
    one_hot = np.eye(len(CLASSES), dtype=np.int32)[y_true]
    per_class: dict[str, dict[str, float]] = {}
    for class_id, name in enumerate(CLASSES):
        per_class[name] = {
            "f1": float(f1_score(y_true == class_id, predictions == class_id, zero_division=0)),
            "auroc_ovr": float(roc_auc_score(one_hot[:, class_id], probabilities[:, class_id])),
            "average_precision": float(
                average_precision_score(one_hot[:, class_id], probabilities[:, class_id])
            ),
        }
    return {
        "n": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, predictions)),
        "macro_f1": float(f1_score(y_true, predictions, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predictions)),
        "macro_auroc_ovr": float(
            roc_auc_score(one_hot, probabilities, multi_class="ovr", average="macro")
        ),
        "macro_average_precision": float(
            average_precision_score(one_hot, probabilities, average="macro")
        ),
        "confusion_matrix": confusion_matrix(y_true, predictions, labels=range(len(CLASSES))).tolist(),
        "per_class": per_class,
    }


def identity_bootstrap_ci(
    records: list[dict[str, Any]],
    out_of_fold: list[dict[str, Any]],
    iterations: int = 1000,
    seed: int = 2027,
) -> dict[str, dict[str, float]]:
    rng = np.random.default_rng(seed)
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in out_of_fold:
        by_subject[row["subject_id"]].append(row)
    subjects = sorted(by_subject)
    estimates: dict[str, list[float]] = defaultdict(list)
    for _ in range(iterations):
        chosen = rng.choice(subjects, size=len(subjects), replace=True)
        rows = [row for subject in chosen for row in by_subject[str(subject)]]
        y_true = np.asarray([row["label"] for row in rows], dtype=np.int64)
        probs = np.stack([row["probabilities"] for row in rows])
        scores = metric_bundle(y_true, probs)
        for name in ("macro_f1", "balanced_accuracy", "macro_auroc_ovr", "macro_average_precision"):
            estimates[name].append(float(scores[name]))
    del records
    return {
        name: {
            "lower_95": float(np.quantile(values, 0.025)),
            "upper_95": float(np.quantile(values, 0.975)),
        }
        for name, values in estimates.items()
    }


def paired_identity_bootstrap(
    vision_rows: list[dict[str, Any]],
    fusion_rows: list[dict[str, Any]],
    iterations: int = 1000,
    seed: int = 2027,
) -> dict[str, Any]:
    """Paired cluster bootstrap for the fusion-minus-vision OOF difference."""
    vision_by_id = {row["sample_id"]: row for row in vision_rows}
    fusion_by_id = {row["sample_id"]: row for row in fusion_rows}
    if set(vision_by_id) != set(fusion_by_id):
        raise ValueError("Vision-only and fusion OOF sample IDs do not match")
    subjects = sorted({row["subject_id"] for row in vision_rows})
    vision_by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    fusion_by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample_id in sorted(vision_by_id):
        vrow, frow = vision_by_id[sample_id], fusion_by_id[sample_id]
        if vrow["label"] != frow["label"] or vrow["subject_id"] != frow["subject_id"]:
            raise ValueError(f"OOF labels or subjects disagree for {sample_id}")
        vision_by_subject[vrow["subject_id"]].append(vrow)
        fusion_by_subject[frow["subject_id"]].append(frow)

    def score(rows: list[dict[str, Any]]) -> dict[str, float]:
        return metric_bundle(
            np.asarray([row["label"] for row in rows], dtype=np.int64),
            np.asarray([row["probabilities"] for row in rows], dtype=np.float64),
        )

    vision_point = score(vision_rows)
    fusion_point = score(fusion_rows)
    metric_names = (
        "macro_f1",
        "balanced_accuracy",
        "macro_auroc_ovr",
        "macro_average_precision",
    )
    differences: dict[str, list[float]] = defaultdict(list)
    rng = np.random.default_rng(seed)
    for _ in range(iterations):
        selected_subjects = rng.choice(subjects, size=len(subjects), replace=True)
        vrows = [row for subject in selected_subjects for row in vision_by_subject[str(subject)]]
        frows = [row for subject in selected_subjects for row in fusion_by_subject[str(subject)]]
        vscore, fscore = score(vrows), score(frows)
        for metric_name in metric_names:
            differences[metric_name].append(fscore[metric_name] - vscore[metric_name])

    return {
        "comparison": "fusion_minus_vision_only",
        "n_subjects": len(subjects),
        "bootstrap_iterations": iterations,
        "point_difference": {
            name: float(fusion_point[name] - vision_point[name]) for name in metric_names
        },
        "identity_cluster_bootstrap_95_ci": {
            name: {
                "lower_95": float(np.quantile(values, 0.025)),
                "upper_95": float(np.quantile(values, 0.975)),
            }
            for name, values in differences.items()
        },
    }


def read_prediction_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        for source in csv.DictReader(handle):
            probabilities = [float(source[f"p_{name}"]) for name in CLASSES]
            predicted = int(np.argmax(probabilities))
            rows.append(
                {
                    "sample_id": source["sample_id"],
                    "subject_id": source["subject_id"],
                    "label": CLASS_TO_ID[source["ground_truth"]],
                    "prediction": predicted,
                    "confidence": float(source["confidence"]),
                    "probabilities": probabilities,
                }
            )
    return rows


def train_one(
    mode: str,
    fold_index: int,
    train_records: list[dict[str, Any]],
    val_records: list[dict[str, Any]],
    args: argparse.Namespace,
    device: torch.device,
) -> tuple[FaceExpressionNet, dict[str, Any]]:
    fusion = mode == "fusion"
    model = FaceExpressionNet(
        num_classes=len(CLASSES),
        landmark_dim=len(train_records[0]["landmark_features"]),
        fusion=fusion,
        pretrained=args.pretrained,
    ).to(device)
    backbone_parameters = list(model.backbone.parameters())
    head_parameters = [
        parameter
        for name, parameter in model.named_parameters()
        if not name.startswith("backbone.")
    ]
    optimizer = torch.optim.AdamW(
        [
            {"params": backbone_parameters, "lr": 2e-5},
            {"params": head_parameters, "lr": 8e-4},
        ],
        weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    train_loader = batches(train_records, args, training=True)
    val_loader = batches(val_records, args, training=False)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    history: list[dict[str, float]] = []
    best_f1 = -1.0
    best_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    best_epoch = 0
    start = time.perf_counter()

    for epoch in range(1, args.epochs + 1):
        model.train()
        frozen = epoch <= args.freeze_backbone_epochs
        for parameter in model.backbone.parameters():
            parameter.requires_grad_(not frozen)
        epoch_loss = 0.0
        num_seen = 0
        for images, landmarks, targets, _ in train_loader:
            images = images.to(device, non_blocking=True)
            landmarks = landmarks.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
                logits = model(images, landmarks)
                loss = F.cross_entropy(logits, targets, label_smoothing=0.05)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            epoch_loss += float(loss.detach()) * len(targets)
            num_seen += len(targets)
        scheduler.step()

        val_labels, val_probs, _ = collect_predictions(model, val_loader, device)
        val_preds = val_probs.argmax(axis=1)
        val_f1 = float(f1_score(val_labels, val_preds, average="macro", zero_division=0))
        val_loss = float(-np.log(np.maximum(val_probs[np.arange(len(val_labels)), val_labels], 1e-8)).mean())
        row = {
            "epoch": epoch,
            "train_loss": epoch_loss / max(num_seen, 1),
            "validation_loss": val_loss,
            "validation_macro_f1": val_f1,
            "backbone_frozen": float(frozen),
        }
        history.append(row)
        if val_f1 > best_f1 or (math.isclose(val_f1, best_f1) and val_loss < best_loss):
            best_f1, best_loss, best_epoch = val_f1, val_loss, epoch
            best_state = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}
        if epoch == 1 or epoch % 10 == 0 or epoch == args.epochs:
            print(
                f"fold={fold_index + 1} model={mode} epoch={epoch:03d}/{args.epochs} "
                f"train_loss={row['train_loss']:.4f} val_macro_f1={val_f1:.4f}",
                flush=True,
            )

    if best_state is None:
        raise RuntimeError("Training completed without a selected validation checkpoint")
    model.load_state_dict(best_state)
    history_info = {
        "fold": fold_index + 1,
        "model": mode,
        "epochs_completed": args.epochs,
        "best_epoch": best_epoch,
        "best_validation_macro_f1": best_f1,
        "best_validation_loss": best_loss,
        "duration_seconds": time.perf_counter() - start,
        "history": history,
    }
    return model, history_info


def synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def benchmark_latency(
    model: FaceExpressionNet,
    record: dict[str, Any],
    device: torch.device,
    runs: int,
) -> dict[str, Any]:
    original_device = next(model.parameters()).device
    model.to(device)
    transform = transforms.Compose(
        [transforms.Resize((224, 224)), transforms.ToTensor(), transforms.Normalize(IMAGE_MEAN, IMAGE_STD)]
    )
    image = transform(Image.fromarray(record["crop"])).unsqueeze(0).to(device)
    landmark = torch.from_numpy(record["landmark_features"].copy()).float().unsqueeze(0).to(device)
    model.eval()
    try:
        with torch.inference_mode():
            for _ in range(10):
                model(image, landmark)
            synchronize(device)
            times = []
            for _ in range(runs):
                synchronize(device)
                start = time.perf_counter()
                model(image, landmark)
                synchronize(device)
                times.append((time.perf_counter() - start) * 1000.0)
    finally:
        model.to(original_device)
    return {
        "device": str(device),
        "runs": runs,
        "batch_size": 1,
        "p50_ms": float(np.percentile(times, 50)),
        "p95_ms": float(np.percentile(times, 95)),
        "mean_ms": float(np.mean(times)),
    }


def plot_pr_curves(
    y_true: np.ndarray, probabilities: np.ndarray, output_path: Path, title: str
) -> None:
    fig, axes = plt.subplots(2, 4, figsize=(15, 7), constrained_layout=True)
    for index, ax in enumerate(axes.flat):
        if index >= len(CLASSES):
            ax.axis("off")
            continue
        positive = y_true == index
        precision, recall, _ = precision_recall_curve(positive, probabilities[:, index])
        ap = average_precision_score(positive, probabilities[:, index])
        ax.plot(recall, precision, lw=2, color="#275dad")
        ax.axhline(float(positive.mean()), lw=1, ls="--", color="#888888")
        ax.set_title(f"{CLASSES[index]} (AP={ap:.3f})")
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.2)
    fig.suptitle(title, fontsize=15)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def make_grid_tile(record: dict[str, Any], prediction: dict[str, Any]) -> Image.Image:
    image = Image.fromarray(record["crop"]).resize((224, 224), Image.Resampling.LANCZOS)
    tile = Image.new("RGB", (224, 280), (20, 23, 28))
    tile.paste(image, (0, 0))
    draw = ImageDraw.Draw(tile)
    draw.rectangle((0, 224, 223, 279), fill=(20, 23, 28))
    mesh = record["mesh"]
    x = mesh[:, 0]
    y = mesh[:, 1]
    x = (x - x.min()) / max(float(np.ptp(x)), 1e-6)
    y = (y - y.min()) / max(float(np.ptp(y)), 1e-6)
    stride = max(1, len(mesh) // 650)
    for px, py in zip(x[::stride], y[::stride]):
        xx = int(5 + px * 214)
        yy = int(229 + (1.0 - py) * 43)
        draw.ellipse((xx - 1, yy - 1, xx + 1, yy + 1), fill=(72, 208, 155))
    draw.text((6, 262), "mesh x-y projection", fill=(205, 213, 220))
    return tile


def render_qualitative_grid(
    records: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    output_path: Path,
    seed: int,
) -> None:
    by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in predictions:
        by_class[row["label"]].append(row)
    selected: list[dict[str, Any]] = []
    rng = random.Random(seed)
    for label in range(len(CLASSES)):
        errors = [row for row in by_class[label] if row["prediction"] != label]
        correct = [row for row in by_class[label] if row["prediction"] == label]
        errors.sort(key=lambda row: row["confidence"], reverse=True)
        correct.sort(key=lambda row: row["confidence"])
        group = errors[:2] + correct[: max(0, 5 - min(2, len(errors)))]
        if len(group) < 5:
            remaining = [row for row in errors[2:] if row not in group]
            group.extend(remaining[: 5 - len(group)])
        selected.extend(group[:5])
    leftovers = [row for row in predictions if row not in selected]
    errors = [row for row in leftovers if row["prediction"] != row["label"]]
    extra = errors[0] if errors else min(leftovers, key=lambda row: row["confidence"])
    selected.append(extra)
    rng.shuffle(selected)

    indexed = {record["sample_id"]: record for record in records}
    fig, axes = plt.subplots(6, 6, figsize=(23, 28), constrained_layout=True)
    for ax, row in zip(axes.flat, selected):
        record = indexed[row["sample_id"]]
        ax.imshow(make_grid_tile(record, row))
        color = "#20a35a" if row["prediction"] == row["label"] else "#d43f3a"
        ax.set_title(
            f"GT {CLASSES[row['label']]} | Pred {CLASSES[row['prediction']]}\n"
            f"p={row['confidence']:.2f} · {row['subject_alias']}",
            color=color,
            fontsize=8,
            pad=2,
        )
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(
        "Identity-held-out test predictions: face crop and 3D mesh projection",
        fontsize=17,
    )
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    return value


def write_predictions_csv(path: Path, records: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    by_sample = {record["sample_id"]: record for record in records}
    fieldnames = [
        "sample_id",
        "subject_id",
        "fold",
        "ground_truth",
        "prediction",
        "confidence",
        "geometric_shift_from_train_neutral",
        *[f"p_{name}" for name in CLASSES],
        *[f"{name}" for name in ("asymmetry_global", "asymmetry_lower", "asymmetry_middle", "asymmetry_upper")],
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            source = by_sample[row["sample_id"]]
            writer.writerow(
                {
                    "sample_id": row["sample_id"],
                    "subject_id": row["subject_id"],
                    "fold": row["fold"],
                    "ground_truth": CLASSES[row["label"]],
                    "prediction": CLASSES[row["prediction"]],
                    "confidence": f"{row['confidence']:.6f}",
                    "geometric_shift_from_train_neutral": f"{row['geometric_shift']:.6f}",
                    **{f"p_{name}": f"{row['probabilities'][i]:.6f}" for i, name in enumerate(CLASSES)},
                    **source["geometry"],
                }
            )


def save_manifest(path: Path, records: list[dict[str, Any]], folds: list[dict[str, list[str]]]) -> None:
    subject_aliases = {
        subject: f"S{index + 1:02d}"
        for index, subject in enumerate(sorted({record["subject_id"] for record in records}))
    }
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        fieldnames = [
            "sample_id",
            "subject_id",
            "subject_alias",
            "label",
            "light",
            "image_path",
            "json_path",
            "face_detected",
            "crop_box_xyxy_rotated",
            "mesh_vertices",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "sample_id": record["sample_id"],
                    "subject_id": record["subject_id"],
                    "subject_alias": subject_aliases[record["subject_id"]],
                    "label": record["label_name"],
                    "light": record["light"],
                    "image_path": record["image_path"],
                    "json_path": record["json_path"],
                    "face_detected": record["face_detected"],
                    "crop_box_xyxy_rotated": json.dumps(record["crop_box"]),
                    "mesh_vertices": record["raw_mesh_vertices"],
                }
            )
    (path.parent / "folds.json").write_text(
        json.dumps({"folds": folds, "subject_aliases": subject_aliases}, indent=2),
        encoding="utf-8",
    )


def save_summary_markdown(path: Path, results: dict[str, Any]) -> None:
    lines = [
        "# Facial Expression Landmark Fusion: Validation Results",
        "",
        f"Run date: {results['run_started_utc']}",
        "",
        "## Dataset and protocol",
        "",
        f"- Samples: {results['dataset']['samples']} across {results['dataset']['subjects']} identities.",
        f"- Labels: {', '.join(CLASSES)}.",
        f"- Face detector found a face in {results['dataset']['detected_faces']}/{results['dataset']['samples']} samples; "
        f"{results['dataset']['fallback_crops']} used the fixed central crop.",
        "- Five-fold subject-grouped cross-validation; each outer test fold contains two identities.",
        f"- Training epochs completed per fold and model: {results['configuration']['epochs']}.",
        "",
        "## Out-of-fold comparison",
        "",
        "| Model | Macro F1 | Balanced accuracy | Macro AUROC (OvR) | Macro AP | Parameters | Checkpoint size |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for mode, value in results["models"].items():
        metrics = value["out_of_fold_metrics"]
        lines.append(
            f"| {mode} | {metrics['macro_f1']:.4f} | {metrics['balanced_accuracy']:.4f} | "
            f"{metrics['macro_auroc_ovr']:.4f} | {metrics['macro_average_precision']:.4f} | "
            f"{value['parameters']:,} | {value['checkpoint_size_mb']:.2f} MB |"
        )
    lines += [
        "",
        "## Paired subject-level comparison",
        "",
        "Intervals resample identities jointly for both models, preserving their paired out-of-fold samples.",
        "",
        "| Metric | Fusion minus vision-only | Paired identity bootstrap 95% interval |",
        "|---|---:|---:|",
    ]
    comparison = results.get("paired_comparison")
    if comparison:
        for name, delta in comparison["point_difference"].items():
            interval = comparison["identity_cluster_bootstrap_95_ci"][name]
            lines.append(
                f"| {name} | {delta:+.4f} | [{interval['lower_95']:+.4f}, {interval['upper_95']:+.4f}] |"
            )
    else:
        lines.append("| Pending | — | — |")
    lines += [
        "",
        "## Landmark geometry by expression",
        "",
        "Shift uses the fold-specific training neutral template; asymmetry is normalized reflected-nearest-neighbor distance.",
        "",
        "| Expression | Mean shift | Shift SD | Mean left-right asymmetry |",
        "|---|---:|---:|---:|",
    ]
    for name, values in results.get("geometric_analysis", {}).get("per_expression", {}).items():
        lines.append(
            f"| {name} | {values['mean_geometric_shift']:.5f} | "
            f"{values['std_geometric_shift']:.5f} | {values['mean_left_right_asymmetry']:.5f} |"
        )
    lines += [
        "",
        "## Inference latency",
        "",
        "Latency is batch-one model execution after warm-up. Face-crop preprocessing is excluded; detector and fallback counts are reported above.",
        "",
        "| Model | Device | p50 (ms) | p95 (ms) |",
        "|---|---|---:|---:|",
    ]
    for mode, value in results["models"].items():
        for device_name, timing in value["latency"].items():
            lines.append(f"| {mode} | {device_name} | {timing['p50_ms']:.2f} | {timing['p95_ms']:.2f} |")
    lines += [
        "",
        "## Interpretation boundary",
        "",
        "This sample is a small facial-expression dataset with ten identities. Results are an engineering benchmark, "
        "not evidence of clinical facial-condition diagnosis or population-level generalization. The identity-level "
        "bootstrap interval is descriptive and remains uncertain with ten people.",
        "",
        "See `metrics.json`, `out_of_fold_predictions.csv`, `precision_recall_*.png`, and "
        "`qualitative_test_grid_6x6.png` for the complete artifacts.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.time_budget_hours <= 0:
        raise SystemExit("epochs, batch size, and time budget must be positive")
    started = time.perf_counter()
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.summarize_only:
        metrics_path = args.output_dir / "metrics.json"
        results = json.loads(metrics_path.read_text(encoding="utf-8"))
        vision_rows = read_prediction_csv(args.output_dir / "vision_only_out_of_fold_predictions.csv")
        fusion_rows = read_prediction_csv(args.output_dir / "out_of_fold_predictions.csv")
        results["paired_comparison"] = paired_identity_bootstrap(
            vision_rows, fusion_rows, seed=args.seed
        )
        metrics_path.write_text(
            json.dumps(to_jsonable(results), indent=2, allow_nan=False), encoding="utf-8"
        )
        save_summary_markdown(args.output_dir / "results.md", results)
        print("Updated paired subject-bootstrap comparison in metrics.json and results.md")
        return
    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    print(f"Device: {device}; time budget: {args.time_budget_hours:.2f} hours", flush=True)
    records = discover_records(args.data_root, args.image_size)
    folds = make_folds(records, args.seed)
    aliases = {
        subject: f"S{index + 1:02d}"
        for index, subject in enumerate(sorted({record["subject_id"] for record in records}))
    }
    for record in records:
        record["subject_alias"] = aliases[record["subject_id"]]
    save_manifest(args.output_dir / "sample_manifest.csv", records, folds)
    print(
        f"Loaded {len(records)} samples from {len(aliases)} identities; "
        f"face detection {sum(r['face_detected'] for r in records)}/{len(records)}",
        flush=True,
    )

    model_rows: dict[str, list[dict[str, Any]]] = {"vision_only": [], "fusion": []}
    model_fits: dict[str, list[dict[str, Any]]] = {"vision_only": [], "fusion": []}
    parameter_counts: dict[str, int] = {}
    checkpoint_sizes: dict[str, int] = {}
    latencies: dict[str, dict[str, Any]] = {"vision_only": {}, "fusion": {}}

    for fold_index, fold in enumerate(folds):
        train_records = split_records(records, fold["train"])
        val_records = split_records(records, fold["validation"])
        test_records = split_records(records, fold["test"])
        neutral_train_meshes = [
            record["mesh"] for record in train_records if record["label_name"] == "Neutral"
        ]
        if not neutral_train_meshes:
            raise RuntimeError("Training fold has no neutral reference meshes")
        neutral_template = np.mean(np.stack(neutral_train_meshes), axis=0)
        for split_name, split_subjects in fold.items():
            if set(split_subjects) & (set(fold["train"]) if split_name != "train" else set()):
                raise RuntimeError("Identity overlap detected in fold construction")
        print(
            f"Fold {fold_index + 1}/5 subjects: train={fold['train']} "
            f"validation={fold['validation']} test={fold['test']}",
            flush=True,
        )

        for mode in ("vision_only", "fusion"):
            fit_seed = args.seed + fold_index * 100 + (0 if mode == "vision_only" else 1)
            set_seed(fit_seed)
            model, fit_info = train_one(
                mode,
                fold_index,
                train_records,
                val_records,
                args,
                device,
            )
            model_fits[mode].append(fit_info)
            key = f"fold_{fold_index + 1}"
            parameter_counts[mode] = sum(parameter.numel() for parameter in model.parameters())

            checkpoint_path = args.output_dir / f"{mode}_{key}.pt"
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "classes": CLASSES,
                    "model": mode,
                    "fold": fold_index + 1,
                    "train_subjects": fold["train"],
                    "validation_subjects": fold["validation"],
                    "test_subjects": fold["test"],
                    "seed": fit_seed,
                    "image_size": args.image_size,
                    "mesh_vertices": int(len(records[0]["mesh"])),
                    "pretrained": args.pretrained,
                },
                checkpoint_path,
            )
            checkpoint_sizes[mode] = max(
                checkpoint_sizes.get(mode, 0), checkpoint_path.stat().st_size
            )

            test_loader = batches(test_records, args, training=False)
            y_true, probabilities, indices = collect_predictions(model, test_loader, device)
            if len(indices) != len(test_records):
                raise RuntimeError("Test inference count does not match outer test split")
            prediction_rows = []
            for local_index, record in enumerate(test_records):
                probs = probabilities[local_index]
                predicted = int(probs.argmax())
                prediction_rows.append(
                    {
                        "sample_id": record["sample_id"],
                        "subject_id": record["subject_id"],
                        "subject_alias": record["subject_alias"],
                        "fold": fold_index + 1,
                        "label": int(y_true[local_index]),
                        "prediction": predicted,
                        "confidence": float(probs[predicted]),
                        "geometric_shift": float(
                            np.sqrt(np.mean(np.sum((record["mesh"] - neutral_template) ** 2, axis=1)))
                        ),
                        **record["geometry"],
                        "probabilities": probs.tolist(),
                    }
                )
            model_rows[mode].extend(prediction_rows)

            if fold_index == 0:
                latency_runs = args.gpu_benchmark_runs if device.type == "cuda" else args.cpu_benchmark_runs
                latencies[mode][str(device)] = benchmark_latency(
                    model, test_records[0], device, max(10, latency_runs)
                )
                if device.type == "cuda":
                    latencies[mode]["cpu"] = benchmark_latency(
                        model, test_records[0], torch.device("cpu"), args.cpu_benchmark_runs
                    )

            del model
            if device.type == "cuda":
                torch.cuda.empty_cache()

        elapsed = time.perf_counter() - started
        print(
            f"Completed fold {fold_index + 1}/5 in {elapsed / 60:.1f} min "
            f"({elapsed / 3600:.2f}/{args.time_budget_hours:.2f} hours)",
            flush=True,
        )

    results: dict[str, Any] = {
        "run_started_utc": started_utc,
        "dataset": {
            "samples": len(records),
            "subjects": len(aliases),
            "class_counts": dict(Counter(record["label_name"] for record in records)),
            "detected_faces": sum(record["face_detected"] for record in records),
            "fallback_crops": sum(not record["face_detected"] for record in records),
            "mesh_vertices_per_sample": int(len(records[0]["mesh"])),
            "classes": CLASSES,
        },
        "configuration": {
            "seed": args.seed,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "image_size": args.image_size,
            "pretrained": args.pretrained,
            "time_budget_hours": args.time_budget_hours,
            "device": str(device),
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
            "timm": timm.__version__,
            "scikit_learn": sklearn.__version__,
            "opencv": cv2.__version__,
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "folds": folds,
        },
        "models": {},
    }
    geometry_rows = {
        row["sample_id"]: row for row in model_rows["fusion"]
    }
    results["geometric_analysis"] = {
        "shift_definition": "RMS vertex displacement from the mean neutral mesh of the fold's training identities",
        "per_expression": {
            name: {
                "mean_geometric_shift": float(
                    np.mean([row["geometric_shift"] for row in geometry_rows.values() if row["label"] == index])
                ),
                "std_geometric_shift": float(
                    np.std([row["geometric_shift"] for row in geometry_rows.values() if row["label"] == index])
                ),
                "mean_left_right_asymmetry": float(
                    np.mean([row["asymmetry_global"] for row in geometry_rows.values() if row["label"] == index])
                ),
            }
            for index, name in enumerate(CLASSES)
        },
    }
    for mode in ("vision_only", "fusion"):
        rows = sorted(model_rows[mode], key=lambda row: row["sample_id"])
        y_true = np.asarray([row["label"] for row in rows], dtype=np.int64)
        probabilities = np.asarray([row["probabilities"] for row in rows], dtype=np.float64)
        metrics = metric_bundle(y_true, probabilities)
        confidence_intervals = identity_bootstrap_ci(records, rows, seed=args.seed)
        results["models"][mode] = {
            "out_of_fold_metrics": metrics,
            "identity_bootstrap_95_ci": confidence_intervals,
            "parameters": parameter_counts[mode],
            "checkpoint_size_bytes": checkpoint_sizes[mode],
            "checkpoint_size_mb": checkpoint_sizes[mode] / (1024 * 1024),
            "latency": latencies[mode],
            "fits": model_fits[mode],
        }
        if mode == "vision_only":
            write_predictions_csv(args.output_dir / "vision_only_out_of_fold_predictions.csv", records, rows)
        else:
            write_predictions_csv(args.output_dir / "out_of_fold_predictions.csv", records, rows)
            plot_pr_curves(
                y_true,
                probabilities,
                args.output_dir / "precision_recall_fusion.png",
                "Landmark-fused model: identity-held-out out-of-fold PR curves",
            )
            render_qualitative_grid(
                records,
                rows,
                args.output_dir / "qualitative_test_grid_6x6.png",
                args.seed,
            )

    results["paired_comparison"] = paired_identity_bootstrap(
        model_rows["vision_only"], model_rows["fusion"], seed=args.seed
    )

    results["elapsed_seconds"] = time.perf_counter() - started
    results["within_time_budget"] = results["elapsed_seconds"] <= args.time_budget_hours * 3600
    (args.output_dir / "metrics.json").write_text(
        json.dumps(to_jsonable(results), indent=2, allow_nan=False), encoding="utf-8"
    )
    save_summary_markdown(args.output_dir / "results.md", results)
    print(
        f"Finished all 5 folds and 10 model fits in {results['elapsed_seconds'] / 60:.1f} minutes; "
        f"within 4-hour budget={results['within_time_budget']}",
        flush=True,
    )
    print(f"Artifacts: {args.output_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
