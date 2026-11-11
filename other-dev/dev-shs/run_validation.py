#!/usr/bin/env python3
"""Identity-disjoint RGB + 3D face-expression validation pipeline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont, ImageOps
from scipy.spatial import cKDTree
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.transforms import InterpolationMode
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


@dataclass
class Sample:
    stem: str
    subject: str
    image_path: Path
    json_path: Path
    label: str
    light: str
    vertices: np.ndarray
    faces: np.ndarray


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def seed_worker(worker_id: int) -> None:
    del worker_id
    worker_seed = torch.initial_seed() % (2**32)
    np.random.seed(worker_seed)
    random.seed(worker_seed)


def parse_vertices(items: list[str]) -> np.ndarray:
    points = []
    for item in items:
        parts = item.strip().split()
        if len(parts) >= 4 and parts[0].lower() == "v":
            points.append([float(parts[1]), float(parts[2]), float(parts[3])])
    result = np.asarray(points, dtype=np.float32)
    if result.ndim != 2 or result.shape[1] != 3 or len(result) < 3:
        raise ValueError("Annotation has no valid 3D vertex array.")
    if not np.isfinite(result).all():
        raise ValueError("Annotation contains non-finite 3D coordinates.")
    return result


def parse_faces(items: list[str], n_vertices: int) -> np.ndarray:
    triangles = []
    for item in items:
        parts = item.strip().split()
        if len(parts) >= 4 and parts[0].lower() == "f":
            # Drive sample uses 1-indexed triangular OBJ-style faces.
            ids = [int(p.split("/")[0]) - 1 for p in parts[1:4]]
            if min(ids) < 0 or max(ids) >= n_vertices:
                raise ValueError("Triangle index is outside the vertex array.")
            triangles.append(ids)
    result = np.asarray(triangles, dtype=np.int32)
    if result.ndim != 2 or result.shape[1] != 3 or len(result) == 0:
        raise ValueError("Annotation has no valid triangular face array.")
    return result


def normalize_vertices(vertices: np.ndarray) -> np.ndarray:
    center = np.median(vertices, axis=0, keepdims=True)
    centered = vertices - center
    radius = float(np.sqrt(np.mean(np.sum(centered * centered, axis=1))))
    return (centered / max(radius, 1e-8)).astype(np.float32)


def discover_samples(
    image_root: Path, annotation_root: Path, label_key: str
) -> tuple[list[Sample], np.ndarray, str]:
    if not image_root.is_dir():
        raise FileNotFoundError(f"Image directory not found: {image_root}")
    if not annotation_root.is_dir():
        raise FileNotFoundError(f"Annotation directory not found: {annotation_root}")

    images: dict[tuple[str, str], Path] = {}
    for path in image_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            key = (path.parent.name, path.stem)
            if key in images:
                raise ValueError(f"Duplicate image key {key}: {images[key]} and {path}")
            images[key] = path

    samples: list[Sample] = []
    topology_hash: str | None = None
    face_reference: np.ndarray | None = None
    missing_images: list[str] = []
    missing_labels: list[str] = []

    for json_path in sorted(annotation_root.rglob("*.json")):
        with json_path.open("r", encoding="utf-8-sig") as handle:
            annotation = json.load(handle)
        relative_parts = json_path.relative_to(annotation_root).parts
        subject = relative_parts[0] if len(relative_parts) > 1 else json_path.parent.name
        image_path = images.get((subject, json_path.stem))
        if image_path is None:
            missing_images.append(str(json_path))
            continue
        if label_key not in annotation or annotation[label_key] in (None, ""):
            missing_labels.append(str(json_path))
            continue
        if "3Dlandmark" not in annotation or "face" not in annotation:
            raise ValueError(f"Expected 3Dlandmark and face fields in {json_path}")

        vertices = parse_vertices(annotation["3Dlandmark"])
        raw_faces = annotation["face"]
        raw_topology_hash = hashlib.sha256("\n".join(raw_faces).encode("utf-8")).hexdigest()
        if topology_hash is None:
            topology_hash = raw_topology_hash
            face_reference = parse_faces(raw_faces, len(vertices))
        elif raw_topology_hash != topology_hash:
            raise ValueError(f"Mesh topology differs from the first annotation: {json_path}")
        assert face_reference is not None

        samples.append(
            Sample(
                stem=json_path.stem,
                subject=subject,
                image_path=image_path,
                json_path=json_path,
                label=str(annotation[label_key]),
                light=str(annotation.get("light", "unknown")),
                vertices=normalize_vertices(vertices),
                faces=face_reference,
            )
        )

    if missing_images:
        raise ValueError(
            f"{len(missing_images)} annotations have no same-stem image; first: {missing_images[0]}"
        )
    if missing_labels:
        raise ValueError(
            f"{len(missing_labels)} annotations lack label key {label_key!r}; first: {missing_labels[0]}"
        )
    if not samples:
        raise ValueError("No paired image/annotation samples were found.")

    annotated_keys = {(s.subject, s.stem) for s in samples}
    orphan_images = sorted(set(images) - annotated_keys)
    if orphan_images:
        print(f"Warning: {len(orphan_images)} images have no annotation; they will be excluded.")
    return samples, face_reference, topology_hash or ""


def make_folds(samples: list[Sample], n_folds: int, seed: int) -> list[dict[str, Any]]:
    groups = sorted({sample.subject for sample in samples})
    if n_folds < 3 or len(groups) < n_folds:
        raise ValueError(f"Need at least {n_folds} identity groups for {n_folds}-fold evaluation.")
    rng = np.random.default_rng(seed)
    shuffled = list(np.asarray(groups)[rng.permutation(len(groups))])
    group_folds = [list(map(str, fold)) for fold in np.array_split(shuffled, n_folds)]
    all_groups = set(groups)

    folds: list[dict[str, Any]] = []
    for i in range(n_folds):
        test_groups = set(group_folds[i])
        val_groups = set(group_folds[(i + 1) % n_folds])
        train_groups = all_groups - test_groups - val_groups
        if not train_groups or not val_groups or not test_groups:
            raise ValueError(f"Fold {i + 1} has an empty identity partition.")
        if train_groups & val_groups or train_groups & test_groups or val_groups & test_groups:
            raise AssertionError("Identity leakage detected in fold construction.")
        folds.append(
            {
                "fold": i + 1,
                "train_groups": sorted(train_groups),
                "val_groups": sorted(val_groups),
                "test_groups": sorted(test_groups),
            }
        )
    return folds


def mesh_edges(faces: np.ndarray, n_vertices: int) -> list[np.ndarray]:
    edges = np.concatenate(
        [faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]], axis=0
    )
    edges = np.sort(edges, axis=1)
    edges = np.unique(edges, axis=0)
    adjacency: list[list[int]] = [[] for _ in range(n_vertices)]
    for a, b in edges.tolist():
        adjacency[a].append(b)
        adjacency[b].append(a)
    if any(not neighbors for neighbors in adjacency):
        raise ValueError("Mesh topology has isolated vertices.")
    return [np.asarray(neighbors, dtype=np.int32) for neighbors in adjacency]


def procrustes_shift(points: np.ndarray, template: np.ndarray) -> float:
    p = points.astype(np.float64)
    t = template.astype(np.float64)
    pc = p.mean(axis=0, keepdims=True)
    tc = t.mean(axis=0, keepdims=True)
    x, y = p - pc, t - tc
    u, _, vt = np.linalg.svd(x.T @ y, full_matrices=False)
    correction = np.eye(3, dtype=np.float64)
    correction[-1, -1] = np.linalg.det(u @ vt)
    rotation = u @ correction @ vt
    aligned = x @ rotation + tc
    return float(np.sqrt(np.mean(np.sum((aligned - t) ** 2, axis=1))))


def asymmetry_metric(points: np.ndarray) -> float:
    mirrored = points.copy()
    mirrored[:, 0] *= -1.0
    forward = cKDTree(points).query(mirrored, k=1)[0]
    reverse = cKDTree(mirrored).query(points, k=1)[0]
    return float(0.5 * (forward.mean() + reverse.mean()))


def build_training_template(samples: list[Sample], train_indices: list[int]) -> np.ndarray:
    by_subject: dict[str, list[np.ndarray]] = {}
    for idx in train_indices:
        sample = samples[idx]
        by_subject.setdefault(sample.subject, []).append(sample.vertices)
    subject_means = [np.mean(shapes, axis=0) for shapes in by_subject.values()]
    if not subject_means:
        raise ValueError("Cannot build a mesh template without training identities.")
    return np.mean(subject_means, axis=0).astype(np.float32)


def structural_features(
    samples: list[Sample],
    template: np.ndarray,
    adjacency: list[np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n_samples = len(samples)
    n_vertices = samples[0].vertices.shape[0]
    nodes = np.zeros((n_samples, n_vertices, 4), dtype=np.float32)
    nodes_mirror = np.zeros_like(nodes)
    metrics = np.zeros((n_samples, 2), dtype=np.float32)
    metrics_mirror = np.zeros_like(metrics)

    for i, sample in enumerate(samples):
        points = sample.vertices.copy()
        local_edge = np.empty((n_vertices, 1), dtype=np.float32)
        for vertex, neighbors in enumerate(adjacency):
            local_edge[vertex, 0] = np.linalg.norm(points[vertex] - points[neighbors], axis=1).mean()

        mirrored = points.copy()
        mirrored[:, 0] *= -1.0
        nodes[i] = np.concatenate([points, local_edge], axis=1)
        nodes_mirror[i] = np.concatenate([mirrored, local_edge], axis=1)
        metrics[i] = [asymmetry_metric(points), procrustes_shift(points, template)]
        metrics_mirror[i] = [asymmetry_metric(mirrored), procrustes_shift(mirrored, template)]

    return nodes, nodes_mirror, metrics, metrics_mirror


class FaceDataset(Dataset):
    def __init__(
        self,
        samples: list[Sample],
        labels: np.ndarray,
        nodes: np.ndarray,
        nodes_mirror: np.ndarray,
        metrics: np.ndarray,
        metrics_mirror: np.ndarray,
        indices: list[int],
        training: bool,
    ) -> None:
        self.samples = samples
        self.labels = labels
        self.nodes = nodes
        self.nodes_mirror = nodes_mirror
        self.metrics = metrics
        self.metrics_mirror = metrics_mirror
        self.indices = list(indices)
        self.training = training
        base = [
            transforms.Resize(256, interpolation=InterpolationMode.BICUBIC),
            transforms.CenterCrop(224),
        ]
        if training:
            base.append(transforms.ColorJitter(brightness=0.20, contrast=0.20, saturation=0.15, hue=0.03))
        base.extend([transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)])
        self.transform = transforms.Compose(base)

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, int, int]:
        sample_index = self.indices[index]
        sample = self.samples[sample_index]
        image = Image.open(sample.image_path).convert("RGB")
        mirror = self.training and random.random() < 0.5
        if mirror:
            image = ImageOps.mirror(image)
            node_array = self.nodes_mirror[sample_index]
            metric_array = self.metrics_mirror[sample_index]
        else:
            node_array = self.nodes[sample_index]
            metric_array = self.metrics[sample_index]
        return (
            self.transform(image),
            torch.from_numpy(node_array.reshape(-1).copy()),
            torch.from_numpy(metric_array.copy()),
            int(self.labels[sample_index]),
            int(sample_index),
        )


class FaceClassifier(nn.Module):
    def __init__(self, n_classes: int, n_vertices: int, mode: str, weights: Any) -> None:
        super().__init__()
        if mode not in {"vision", "fused"}:
            raise ValueError(f"Unknown model mode: {mode}")
        self.mode = mode
        self.encoder = efficientnet_b0(weights=weights)
        visual_dim = self.encoder.classifier[1].in_features
        self.encoder.classifier = nn.Identity()
        if mode == "vision":
            self.vision_head = nn.Sequential(
                nn.Linear(visual_dim, 512),
                nn.GELU(),
                nn.Dropout(0.30),
                nn.Linear(512, n_classes),
            )
        else:
            self.image_projection = nn.Sequential(
                nn.Linear(visual_dim, 256), nn.GELU(), nn.Dropout(0.20)
            )
            mesh_dim = n_vertices * 4 + 2
            self.mesh_mlp = nn.Sequential(
                nn.Linear(mesh_dim, 512),
                nn.LayerNorm(512),
                nn.GELU(),
                nn.Dropout(0.30),
                nn.Linear(512, 128),
                nn.GELU(),
            )
            self.fusion_head = nn.Sequential(
                nn.Linear(384, 256),
                nn.GELU(),
                nn.Dropout(0.30),
                nn.Linear(256, n_classes),
            )

    def forward(
        self, image: torch.Tensor, mesh: torch.Tensor | None = None, metrics: torch.Tensor | None = None
    ) -> torch.Tensor:
        visual = self.encoder(image)
        if self.mode == "vision":
            return self.vision_head(visual)
        if mesh is None or metrics is None:
            raise ValueError("Fused model requires mesh and geometric metric inputs.")
        image_z = self.image_projection(visual)
        mesh_z = self.mesh_mlp(torch.cat([mesh, metrics], dim=1))
        return self.fusion_head(torch.cat([image_z, mesh_z], dim=1))


def model_logits(
    model: FaceClassifier,
    batch: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    image, mesh, metrics, target, sample_index = batch
    image = image.to(device, non_blocking=True)
    mesh = mesh.to(device, non_blocking=True)
    metrics = metrics.to(device, non_blocking=True)
    target = target.to(device, non_blocking=True)
    logits = model(image, mesh, metrics)
    return logits, target, sample_index, image


def predict_loader(
    model: FaceClassifier,
    loader: DataLoader,
    device: torch.device,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    model.eval()
    probs_all: list[np.ndarray] = []
    y_all: list[np.ndarray] = []
    index_all: list[np.ndarray] = []
    with torch.inference_mode():
        for batch in loader:
            logits, target, sample_index, _ = model_logits(model, batch, device)
            probs_all.append(torch.softmax(logits, dim=1).cpu().numpy())
            y_all.append(target.cpu().numpy())
            index_all.append(sample_index.numpy())
    return np.concatenate(y_all), np.concatenate(probs_all), np.concatenate(index_all)


def compute_metrics(y_true: np.ndarray, probabilities: np.ndarray, n_classes: int) -> dict[str, Any]:
    y_pred = probabilities.argmax(axis=1)
    labels = np.arange(n_classes)
    report: dict[str, Any] = {
        "n": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", labels=labels, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "auroc_ovr_macro": None,
        "macro_average_precision": None,
        "per_class_average_precision": {},
    }
    try:
        report["auroc_ovr_macro"] = float(
            roc_auc_score(y_true, probabilities, multi_class="ovr", average="macro", labels=labels)
        )
    except ValueError as exc:
        report["auroc_note"] = str(exc)

    aps = []
    for class_index in labels:
        binary = (y_true == class_index).astype(np.uint8)
        if binary.sum() and binary.sum() < len(binary):
            ap = float(average_precision_score(binary, probabilities[:, class_index]))
            report["per_class_average_precision"][str(int(class_index))] = ap
            aps.append(ap)
        else:
            report["per_class_average_precision"][str(int(class_index))] = None
    if aps:
        report["macro_average_precision"] = float(np.mean(aps))
    return report


def subject_bootstrap_ci(
    records: list[dict[str, Any]], n_classes: int, seed: int, replicates: int = 2000
) -> dict[str, Any]:
    by_subject: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_subject.setdefault(str(record["subject_id"]), []).append(record)
    subjects = sorted(by_subject)
    if len(subjects) < 2:
        return {"subjects": len(subjects), "replicates": 0, "macro_f1_95_ci": None, "balanced_accuracy_95_ci": None}

    rng = np.random.default_rng(seed)
    macro_f1_values: list[float] = []
    balanced_accuracy_values: list[float] = []
    for _ in range(replicates):
        draw = rng.choice(subjects, size=len(subjects), replace=True)
        resampled = [record for subject in draw for record in by_subject[str(subject)]]
        y = np.asarray([record["label_id"] for record in resampled], dtype=np.int64)
        pred = np.asarray([record["prediction_id"] for record in resampled], dtype=np.int64)
        macro_f1_values.append(
            float(f1_score(y, pred, average="macro", labels=np.arange(n_classes), zero_division=0))
        )
        balanced_accuracy_values.append(float(balanced_accuracy_score(y, pred)))

    def interval(values: list[float]) -> list[float]:
        return [float(v) for v in np.quantile(values, [0.025, 0.975])]

    return {
        "subjects": len(subjects),
        "replicates": replicates,
        "unit": "identity cluster",
        "macro_f1_95_ci": interval(macro_f1_values),
        "balanced_accuracy_95_ci": interval(balanced_accuracy_values),
    }


def train_model(
    model: FaceClassifier,
    train_loader: DataLoader,
    val_loader: DataLoader,
    train_labels: np.ndarray,
    n_classes: int,
    device: torch.device,
    deadline: float,
    max_epochs: int,
    checkpoint_path: Path,
    log_path: Path,
    run_label: str,
    learning_rate: float,
) -> dict[str, Any]:
    counts = np.bincount(train_labels, minlength=n_classes).astype(np.float32)
    class_weights = counts.sum() / (n_classes * np.maximum(counts, 1.0))
    class_weights[counts == 0] = 0.0
    criterion = nn.CrossEntropyLoss(
        weight=torch.tensor(class_weights, dtype=torch.float32, device=device), label_smoothing=0.05
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    best_f1 = -math.inf
    best_epoch = 0
    epoch = 0
    started = time.perf_counter()
    slot_seconds = max(deadline - started, 1.0)

    while epoch < max_epochs:
        epoch += 1
        epoch_started = time.perf_counter()
        progress = min((epoch_started - started) / slot_seconds, 1.0)
        scheduled_lr = learning_rate * 0.5 * (1.0 + math.cos(math.pi * progress))
        for param_group in optimizer.param_groups:
            param_group["lr"] = scheduled_lr
        model.train()
        losses: list[float] = []
        for batch in train_loader:
            logits, target, _, _ = model_logits(model, batch, device)
            loss = criterion(logits, target)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))

        y_val, p_val, _ = predict_loader(model, val_loader, device)
        val_metrics = compute_metrics(y_val, p_val, n_classes)
        if val_metrics["macro_f1"] > best_f1:
            best_f1 = val_metrics["macro_f1"]
            best_epoch = epoch
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "epoch": epoch,
                    "val_macro_f1": best_f1,
                    "mode": model.mode,
                },
                checkpoint_path,
            )
        event = {
            "run": run_label,
            "epoch": epoch,
            "train_loss": float(np.mean(losses)) if losses else None,
            "val_macro_f1": val_metrics["macro_f1"],
            "val_balanced_accuracy": val_metrics["balanced_accuracy"],
            "val_auroc_ovr_macro": val_metrics["auroc_ovr_macro"],
            "epoch_seconds": time.perf_counter() - epoch_started,
            "run_elapsed_seconds": time.perf_counter() - started,
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        print(json.dumps(event, ensure_ascii=False), flush=True)

        # The budget is checked only after all batches and validation for this epoch finish.
        if time.perf_counter() >= deadline:
            break

    if not checkpoint_path.exists():
        raise RuntimeError(f"No complete epoch produced a checkpoint for {run_label}.")
    best = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(best["state_dict"])
    return {
        "epochs_completed": epoch,
        "best_epoch": best_epoch,
        "best_validation_macro_f1": float(best_f1),
        "training_seconds": time.perf_counter() - started,
    }


def benchmark_latency(
    model: FaceClassifier,
    dataset: FaceDataset,
    sample_index: int,
    device: torch.device,
    warmup: int = 40,
    repeats: int = 150,
) -> dict[str, float]:
    model.eval()
    image, mesh, metrics, _, _ = dataset[dataset.indices.index(sample_index)]
    image = image.unsqueeze(0).to(device)
    mesh = mesh.unsqueeze(0).to(device)
    metrics = metrics.unsqueeze(0).to(device)
    with torch.inference_mode():
        for _ in range(warmup):
            model(image, mesh, metrics)
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        durations = []
        for _ in range(repeats):
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            start = time.perf_counter()
            model(image, mesh, metrics)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            durations.append((time.perf_counter() - start) * 1000.0)
    return {
        "median_ms": float(np.median(durations)),
        "p95_ms": float(np.percentile(durations, 95)),
        "throughput_samples_per_second": float(1000.0 / np.mean(durations)),
    }


def draw_mesh_panel(vertices: np.ndarray, size: tuple[int, int]) -> Image.Image:
    width, height = size
    panel = Image.new("RGB", size, (13, 20, 30))
    draw = ImageDraw.Draw(panel)
    xy = vertices[:, :2].astype(np.float64)
    low = xy.min(axis=0)
    high = xy.max(axis=0)
    span = np.maximum(high - low, 1e-6)
    scale = min((width - 12) / span[0], (height - 12) / span[1])
    offset_x = (width - span[0] * scale) / 2.0
    offset_y = (height - span[1] * scale) / 2.0
    for x, y in xy:
        px = int(offset_x + (x - low[0]) * scale)
        py = int(height - (offset_y + (y - low[1]) * scale))
        draw.ellipse((px - 1, py - 1, px + 1, py + 1), fill=(62, 215, 234))
    return panel


def choose_grid_indices(records: list[dict[str, Any]], count: int = 36) -> list[int]:
    by_class: dict[int, list[int]] = {}
    for index, record in enumerate(records):
        by_class.setdefault(int(record["label_id"]), []).append(index)
    for class_indices in by_class.values():
        class_indices.sort(key=lambda i: (records[i]["correct"], records[i]["confidence"]))
    selected: list[int] = []
    classes = sorted(by_class)
    while len(selected) < min(count, len(records)):
        added = False
        for class_id in classes:
            if by_class[class_id]:
                selected.append(by_class[class_id].pop(0))
                added = True
                if len(selected) >= count:
                    break
        if not added:
            break
    return selected


def save_qualitative_grid(
    samples: list[Sample],
    records: list[dict[str, Any]],
    classes: list[str],
    output_path: Path,
) -> None:
    selected = choose_grid_indices(records, 36)
    tile_w, tile_h = 300, 190
    columns, rows = 6, 6
    canvas = Image.new("RGB", (tile_w * columns, tile_h * rows), (238, 241, 245))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for slot, record_index in enumerate(selected):
        record = records[record_index]
        sample = samples[int(record["sample_index"])]
        left = (slot % columns) * tile_w
        top = (slot // columns) * tile_h
        border = (34, 145, 75) if record["correct"] else (205, 55, 55)
        draw.rectangle((left, top, left + tile_w - 1, top + tile_h - 1), outline=border, width=4)

        with Image.open(sample.image_path) as image_file:
            face = image_file.convert("RGB")
            face.thumbnail((136, 136), Image.Resampling.LANCZOS)
        face_tile = Image.new("RGB", (136, 136), (20, 20, 20))
        face_tile.paste(face, ((136 - face.width) // 2, (136 - face.height) // 2))
        mesh_tile = draw_mesh_panel(sample.vertices, (136, 136))
        canvas.paste(face_tile, (left + 8, top + 8))
        canvas.paste(mesh_tile, (left + 156, top + 8))

        gt = classes[int(record["label_id"])]
        pred = classes[int(record["prediction_id"])]
        confidence = float(record["confidence"])
        draw.text((left + 8, top + 150), f"GT: {gt}   Pred: {pred}", fill=(20, 20, 20), font=font)
        draw.text((left + 8, top + 166), f"p={confidence:.2f}  {sample.subject}  {sample.light}", fill=(35, 35, 35), font=font)
    canvas.save(output_path, format="PNG", optimize=True)


def save_pr_plot(
    predictions: dict[str, list[dict[str, Any]]], classes: list[str], output_path: Path
) -> None:
    fig, axes = plt.subplots(1, len(predictions), figsize=(7 * len(predictions), 5), squeeze=False)
    for ax, (mode, records) in zip(axes[0], predictions.items()):
        y_true = np.asarray([r["label_id"] for r in records], dtype=np.int64)
        probs = np.asarray([r["probabilities"] for r in records], dtype=np.float32)
        for class_index, class_name in enumerate(classes):
            binary = (y_true == class_index).astype(np.uint8)
            if binary.sum() == 0 or binary.sum() == len(binary):
                continue
            precision, recall, _ = precision_recall_curve(binary, probs[:, class_index])
            ap = average_precision_score(binary, probs[:, class_index])
            ax.plot(recall, precision, label=f"{class_name} AP={ap:.3f}")
        ax.set_title(f"{mode}: out-of-fold test PR")
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def make_loader(
    samples: list[Sample],
    labels: np.ndarray,
    features: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    indices: list[int],
    training: bool,
    seed: int,
    batch_size: int,
    workers: int,
    device: torch.device,
) -> DataLoader:
    dataset = FaceDataset(samples, labels, *features, indices, training)
    generator = torch.Generator()
    generator.manual_seed(seed)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=training,
        num_workers=workers,
        pin_memory=(device.type == "cuda"),
        generator=generator,
        worker_init_fn=seed_worker,
        persistent_workers=workers > 0,
    )


def aggregate_records(
    samples: list[Sample],
    indices: np.ndarray,
    y_true: np.ndarray,
    probabilities: np.ndarray,
    fold_number: int,
    classes: list[str],
) -> list[dict[str, Any]]:
    records = []
    for sample_index, target, probs in zip(indices.tolist(), y_true.tolist(), probabilities.tolist()):
        prediction = int(np.argmax(probs))
        sample = samples[sample_index]
        records.append(
            {
                "fold": fold_number,
                "sample_index": int(sample_index),
                "sample_id": sample.stem,
                "subject_id": sample.subject,
                "image_path": str(sample.image_path),
                "json_path": str(sample.json_path),
                "label_id": int(target),
                "label": classes[int(target)],
                "prediction_id": prediction,
                "prediction": classes[prediction],
                "confidence": float(max(probs)),
                "correct": prediction == int(target),
                "light": sample.light,
                "probabilities": [float(v) for v in probs],
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--image-root", type=Path)
    parser.add_argument("--annotation-root", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("results/cvpr2027"))
    parser.add_argument("--label-key", default="expression")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--hours", type=float, default=4.0)
    parser.add_argument("--eval-reserve", type=float, default=0.15)
    parser.add_argument("--max-epochs", type=int, default=100000)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--weights", choices=("imagenet", "random"), default="imagenet")
    args = parser.parse_args()

    if args.hours <= 0 or not 0.0 <= args.eval_reserve < 0.5:
        parser.error("--hours must be positive and --eval-reserve must be in [0, 0.5).")
    if args.max_epochs < 1 or args.batch_size < 1 or args.workers < 0:
        parser.error("Epochs and batch size must be positive; workers cannot be negative.")

    run_started = time.perf_counter()
    set_seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if any(args.output_dir.iterdir()):
        raise FileExistsError(
            f"Output directory is not empty: {args.output_dir}. Choose a fresh directory to avoid mixing runs."
        )
    image_root = args.image_root or args.data_root / "01.원천데이터" / "image"
    annotation_root = args.annotation_root or args.data_root / "02.라벨링데이터"
    samples, faces, topology_hash = discover_samples(image_root, annotation_root, args.label_key)
    subjects = sorted({sample.subject for sample in samples})
    classes = sorted({sample.label for sample in samples})
    if len(classes) < 2:
        raise ValueError(f"Classification requires at least two classes; found {classes}.")
    class_to_id = {label: i for i, label in enumerate(classes)}
    labels = np.asarray([class_to_id[sample.label] for sample in samples], dtype=np.int64)
    n_vertices = int(samples[0].vertices.shape[0])
    if any(sample.vertices.shape[0] != n_vertices for sample in samples):
        raise ValueError("All samples must use the same ordered mesh vertex count.")
    folds = make_folds(samples, args.folds, args.seed)
    adjacency = mesh_edges(faces, n_vertices)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    weight_enum = EfficientNet_B0_Weights.DEFAULT if args.weights == "imagenet" else None
    run_dir = args.output_dir.resolve()
    (run_dir / "checkpoints").mkdir(exist_ok=True)

    environment = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torchvision": __import__("torchvision").__version__,
        "numpy": np.__version__,
        "scipy": __import__("scipy").__version__,
        "scikit_learn": __import__("sklearn").__version__,
        "matplotlib": matplotlib.__version__,
        "pillow": __import__("PIL").__version__,
        "device": str(device),
        "cuda_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "seed": args.seed,
        "weights": args.weights,
        "budget_hours": args.hours,
        "eval_reserve_fraction": args.eval_reserve,
    }
    (run_dir / "environment.json").write_text(
        json.dumps(environment, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "data_summary.json").write_text(
        json.dumps(
            {
                "samples": len(samples),
                "subjects": subjects,
                "class_counts": {label: int(sum(s.label == label for s in samples)) for label in classes},
                "classes": classes,
                "vertices_per_mesh": n_vertices,
                "triangles_per_mesh": int(len(faces)),
                "topology_sha256": topology_hash,
                "image_root": str(image_root.resolve()),
                "annotation_root": str(annotation_root.resolve()),
                "label_key": args.label_key,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    split_rows = []
    for fold in folds:
        for partition in ("train", "val", "test"):
            for subject in fold[f"{partition}_groups"]:
                split_rows.append({"fold": fold["fold"], "partition": partition, "subject_id": subject})
    write_csv(run_dir / "splits.csv", split_rows, ["fold", "partition", "subject_id"])

    train_cutoff = run_started + args.hours * 3600.0 * (1.0 - args.eval_reserve)
    total_train_runs = len(folds) * 2
    completed_train_runs = 0
    fold_metrics: list[dict[str, Any]] = []
    predictions: dict[str, list[dict[str, Any]]] = {"vision": [], "fused": []}
    geometry_rows: list[dict[str, Any]] = []
    latency_rows: list[dict[str, Any]] = []
    fold_contexts: dict[int, dict[str, Any]] = {}
    fit_summaries: dict[tuple[str, int], dict[str, Any]] = {}

    for fold in folds:
        train_groups = set(fold["train_groups"])
        val_groups = set(fold["val_groups"])
        test_groups = set(fold["test_groups"])
        train_indices = [i for i, s in enumerate(samples) if s.subject in train_groups]
        val_indices = [i for i, s in enumerate(samples) if s.subject in val_groups]
        test_indices = [i for i, s in enumerate(samples) if s.subject in test_groups]
        if not train_indices or not val_indices or not test_indices:
            raise ValueError(f"Fold {fold['fold']} has an empty sample partition.")
        train_classes = set(labels[train_indices].tolist())
        if train_classes != set(range(len(classes))):
            missing = [classes[i] for i in sorted(set(range(len(classes))) - train_classes)]
            raise ValueError(f"Fold {fold['fold']} training identities omit classes: {missing}")

        template = build_training_template(samples, train_indices)
        features = structural_features(samples, template, adjacency)
        fold_contexts[fold["fold"]] = {"features": features, "test_indices": test_indices}

        for mode in ("vision", "fused"):
            completed_train_runs += 1
            remaining_runs = total_train_runs - completed_train_runs + 1
            slot_seconds = max(0.0, (train_cutoff - time.perf_counter()) / remaining_runs)
            deadline = time.perf_counter() + slot_seconds
            train_loader = make_loader(
                samples, labels, features, train_indices, True,
                args.seed + fold["fold"] * 100 + (mode == "fused"), args.batch_size,
                args.workers, device,
            )
            val_dataset = FaceDataset(
                samples, labels, *features, val_indices, False
            )
            val_loader = DataLoader(
                val_dataset, batch_size=args.batch_size, shuffle=False,
                num_workers=args.workers, pin_memory=device.type == "cuda",
                persistent_workers=args.workers > 0,
            )
            model = FaceClassifier(len(classes), n_vertices, mode, weight_enum).to(device)
            checkpoint = run_dir / "checkpoints" / f"{mode}_fold_{fold['fold']}.pt"
            fit_summary = train_model(
                model,
                train_loader,
                val_loader,
                labels[train_indices],
                len(classes),
                device,
                deadline,
                args.max_epochs,
                checkpoint,
                run_dir / "training_log.jsonl",
                f"{mode}_fold_{fold['fold']}",
                args.learning_rate,
            )
            fit_summaries[(mode, fold["fold"])] = fit_summary
            del model, train_loader, val_loader, val_dataset
            if device.type == "cuda":
                torch.cuda.empty_cache()

    # Test inference starts only after every training run has finished.
    for fold in folds:
        fold_number = fold["fold"]
        features = fold_contexts[fold_number]["features"]
        test_indices = fold_contexts[fold_number]["test_indices"]
        for idx in test_indices:
            geometry_rows.append(
                {
                    "fold": fold_number,
                    "sample_id": samples[idx].stem,
                    "subject_id": samples[idx].subject,
                    "label": samples[idx].label,
                    "light": samples[idx].light,
                    "asymmetry": float(features[2][idx, 0]),
                    "geometric_shift": float(features[2][idx, 1]),
                }
            )
        test_dataset = FaceDataset(
            samples, labels, *features, test_indices, False
        )
        test_loader = DataLoader(
            test_dataset, batch_size=args.batch_size, shuffle=False,
            num_workers=args.workers, pin_memory=device.type == "cuda",
            persistent_workers=args.workers > 0,
        )
        for mode in ("vision", "fused"):
            checkpoint = run_dir / "checkpoints" / f"{mode}_fold_{fold_number}.pt"
            model = FaceClassifier(len(classes), n_vertices, mode, None).to(device)
            saved = torch.load(checkpoint, map_location=device)
            model.load_state_dict(saved["state_dict"])
            y_test, probs_test, sample_indices = predict_loader(model, test_loader, device)
            fold_result = compute_metrics(y_test, probs_test, len(classes))
            fold_metrics.append(
                {"model": mode, "fold": fold_number, **fit_summaries[(mode, fold_number)], **fold_result}
            )
            predictions[mode].extend(
                aggregate_records(samples, sample_indices, y_test, probs_test, fold_number, classes)
            )
            latency = benchmark_latency(model, test_dataset, int(test_indices[0]), device)
            latency_rows.append(
                {
                    "model": mode,
                    "fold": fold_number,
                    "parameters_total": sum(p.numel() for p in model.parameters()),
                    "parameters_trainable": sum(p.numel() for p in model.parameters() if p.requires_grad),
                    "checkpoint_bytes": checkpoint.stat().st_size,
                    **latency,
                }
            )
            print(
                json.dumps(
                    {"event": "test_fold_complete", "model": mode, "fold": fold_number, **fold_result},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            del model
            if device.type == "cuda":
                torch.cuda.empty_cache()
        del test_loader, test_dataset

    write_csv(
        run_dir / "fold_metrics.csv",
        fold_metrics,
        [
            "model", "fold", "epochs_completed", "best_epoch", "best_validation_macro_f1",
            "training_seconds", "n", "accuracy", "macro_f1", "balanced_accuracy",
            "auroc_ovr_macro", "macro_average_precision",
        ],
    )
    write_csv(
        run_dir / "geometry_metrics.csv",
        geometry_rows,
        ["fold", "sample_id", "subject_id", "label", "light", "asymmetry", "geometric_shift"],
    )

    prediction_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for mode, records in predictions.items():
        records.sort(key=lambda r: r["sample_index"])
        y_true = np.asarray([r["label_id"] for r in records], dtype=np.int64)
        probabilities = np.asarray([r["probabilities"] for r in records], dtype=np.float32)
        summary = compute_metrics(y_true, probabilities, len(classes))
        summary["fold_macro_f1_mean"] = float(
            np.mean([r["macro_f1"] for r in fold_metrics if r["model"] == mode])
        )
        summary["fold_macro_f1_std"] = float(
            np.std([r["macro_f1"] for r in fold_metrics if r["model"] == mode], ddof=1)
        )
        summary["subject_bootstrap_95_ci"] = subject_bootstrap_ci(
            records, len(classes), args.seed + (1 if mode == "fused" else 0)
        )
        lighting_strata: dict[str, Any] = {}
        for light in sorted({str(record["light"]) for record in records}):
            subset = [record for record in records if str(record["light"]) == light]
            if subset:
                light_y = np.asarray([record["label_id"] for record in subset], dtype=np.int64)
                light_probs = np.asarray([record["probabilities"] for record in subset], dtype=np.float32)
                lighting_strata[light] = compute_metrics(light_y, light_probs, len(classes))
        summary["lighting_strata"] = lighting_strata
        summaries[mode] = summary
        for record in records:
            row = {k: v for k, v in record.items() if k != "probabilities"}
            row.update({f"prob_{classes[i]}": record["probabilities"][i] for i in range(len(classes))})
            prediction_rows.append({"model": mode, **row})

    write_csv(
        run_dir / "predictions_oof.csv",
        prediction_rows,
        [
            "model", "fold", "sample_index", "sample_id", "subject_id", "image_path", "json_path",
            "label_id", "label", "prediction_id", "prediction", "confidence", "correct", "light",
            *[f"prob_{label}" for label in classes],
        ],
    )
    latency_summary: dict[str, Any] = {}
    for mode in ("vision", "fused"):
        rows = [row for row in latency_rows if row["model"] == mode]
        latency_summary[mode] = {
            "parameters_total": int(statistics.median(row["parameters_total"] for row in rows)),
            "parameters_trainable": int(statistics.median(row["parameters_trainable"] for row in rows)),
            "checkpoint_bytes_median": int(statistics.median(row["checkpoint_bytes"] for row in rows)),
            "median_ms_mean_across_folds": float(np.mean([row["median_ms"] for row in rows])),
            "median_ms_std_across_folds": float(np.std([row["median_ms"] for row in rows], ddof=1)),
            "p95_ms_mean_across_folds": float(np.mean([row["p95_ms"] for row in rows])),
            "throughput_mean_across_folds": float(
                np.mean([row["throughput_samples_per_second"] for row in rows])
            ),
        }
    write_csv(
        run_dir / "latency_parameters.csv",
        latency_rows,
        [
            "model", "fold", "parameters_total", "parameters_trainable", "checkpoint_bytes",
            "median_ms", "p95_ms", "throughput_samples_per_second",
        ],
    )

    for mode, records in predictions.items():
        save_qualitative_grid(
            samples, records, classes,
            run_dir / ("qualitative_6x6.png" if mode == "fused" else "qualitative_6x6_vision.png"),
        )
    save_pr_plot(predictions, classes, run_dir / "precision_recall_oof.png")
    summary = {
        "status": "completed",
        "elapsed_seconds": time.perf_counter() - run_started,
        "budget_seconds": args.hours * 3600.0,
        "device": str(device),
        "classes": classes,
        "samples": len(samples),
        "subjects": subjects,
        "folds": folds,
        "models": summaries,
        "deployment": latency_summary,
        "notes": [
            "All test predictions are identity-disjoint out-of-fold predictions.",
            "Latency values were measured on the device recorded in environment.json; they are not target-device claims unless that device matches the deployment target.",
            "Expression labels are used because that is the target field observed in the supplied JSON schema.",
        ],
    }
    (run_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"event": "run_complete", "summary": str(run_dir / "metrics.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
