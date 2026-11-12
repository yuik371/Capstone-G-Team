#!/usr/bin/env python3
"""Subject-disjoint RGB / 3D-mesh expression study on the AI-Hub face-landmark SAMPLE.

Protocols (all written to a split manifest before any training starts):
  inner     3-fold CV over the 9 TRAINING subjects of each outer fold; picks the epoch count.
  loso      10-fold leave-one-subject-out, fixed epochs, final-epoch weights, >=5 seeds.
  random    image-level stratified random 10-fold (deliberately leaky; Q1).
  triplet   capture-triplet-grouped random 10-fold (lighting variants kept together; Q1).
  lightout  LOSO where one lighting level is also removed from training (Q3).

No test fold is ever used for model selection, early stopping or checkpoint choice:
there is no validation-based checkpointing at all. Every run trains for a fixed number
of epochs with a step-based cosine schedule and is evaluated once with its final weights.

Run from the repository root, e.g.
    python other-dev/dev-shs/run_validation.py --data-root <AI-Hub sample folder> --stage all
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist
from torch import nn
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0

# Repository root is two levels above this file (other-dev/dev-shs/run_validation.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
# Relative default; override with --data-root or the FACE_DATA_ROOT environment variable.
DEFAULT_DATA_ROOT = Path(os.environ.get("FACE_DATA_ROOT", "dev-YuIK/안면_인식_랜드마크_Sample"))

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
NEUTRAL_LABEL = "Neutral"


# --------------------------------------------------------------------------------------
# Experimental conditions
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Condition:
    arch: str  # image | mesh | scalars | fused
    flip: str  # none | naive | perm   (image-only models: "perm" just means "flip the image")
    mesh_mode: str = "raw"  # raw | neutral
    shuffled: bool = False  # mesh taken from a different expression of the same subject
    epochs_from: str | None = None  # condition whose inner-CV epoch choice is reused


CONDITIONS: dict[str, Condition] = {
    # image-only
    "image_flip": Condition("image", "perm"),
    "image_noflip": Condition("image", "none", epochs_from="image_flip"),
    # mesh-only MLP
    "mesh_raw": Condition("mesh", "perm"),
    "mesh_naiveflip": Condition("mesh", "naive", epochs_from="mesh_raw"),
    "mesh_noflip": Condition("mesh", "none", epochs_from="mesh_raw"),
    "mesh_shuffled": Condition("mesh", "perm", shuffled=True, epochs_from="mesh_raw"),
    "mesh_neutral": Condition("mesh", "perm", mesh_mode="neutral"),
    # image + the two scalars [A, G] only
    "scalars": Condition("scalars", "perm"),
    # image + mesh MLP (late concatenation)
    "fused_perm": Condition("fused", "perm"),
    "fused_naiveflip": Condition("fused", "naive", epochs_from="fused_perm"),
    "fused_noflip": Condition("fused", "none", epochs_from="fused_perm"),
    "fused_shuffled": Condition("fused", "perm", shuffled=True, epochs_from="fused_perm"),
    "fused_neutral": Condition("fused", "perm", mesh_mode="neutral"),
}
# Ablation/control variants reuse the epoch count of their default configuration so that the
# ablated factor is the only difference. Conditions listed here get their own inner CV.
INNER_CONDITIONS = [name for name, c in CONDITIONS.items() if c.epochs_from is None]
LOSO_CONDITIONS = list(CONDITIONS)
SPLIT_CONDITIONS = ["image_flip", "mesh_raw", "fused_perm"]
LIGHT_CONDITIONS = ["image_flip", "mesh_raw", "fused_perm"]
IMAGE_EPOCH_GRID = (10, 20, 30)
MESH_EPOCH_GRID = (25, 50, 100, 200)


def epoch_grid(condition: str) -> tuple[int, ...]:
    return MESH_EPOCH_GRID if CONDITIONS[condition].arch == "mesh" else IMAGE_EPOCH_GRID


# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------
@dataclass
class Sample:
    stem: str
    subject: str
    image_path: Path
    json_path: Path
    label: str
    light: str
    vertices: np.ndarray  # median-centred, RMS-radius-normalised (N, 3)

    @property
    def triplet(self) -> str:
        """Capture triplet: same subject and expression under the three lighting levels."""
        return f"{self.subject}_{self.label}"


def parse_vertices(items: list[str]) -> np.ndarray:
    points = []
    for item in items:
        parts = item.strip().split()
        if len(parts) >= 4 and parts[0].lower() == "v":
            points.append([float(parts[1]), float(parts[2]), float(parts[3])])
    result = np.asarray(points, dtype=np.float64)
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
            ids = [int(p.split("/")[0]) - 1 for p in parts[1:4]]  # OBJ faces are 1-indexed
            if min(ids) < 0 or max(ids) >= n_vertices:
                raise ValueError("Triangle index is outside the vertex array.")
            triangles.append(ids)
    result = np.asarray(triangles, dtype=np.int64)
    if result.ndim != 2 or result.shape[1] != 3 or len(result) == 0:
        raise ValueError("Annotation has no valid triangular face array.")
    return result


def normalize_vertices(vertices: np.ndarray) -> np.ndarray:
    centered = vertices - np.median(vertices, axis=0, keepdims=True)
    radius = float(np.sqrt(np.mean(np.sum(centered * centered, axis=1))))
    return centered / max(radius, 1e-8)


def discover_samples(data_root: Path, label_key: str) -> tuple[list[Sample], np.ndarray, str]:
    image_root = data_root / "01.원천데이터" / "image"
    annotation_root = data_root / "02.라벨링데이터"
    for folder in (image_root, annotation_root):
        if not folder.is_dir():
            raise FileNotFoundError(
                f"Expected folder not found: {folder}. See other-dev/dev-shs/README.md for the "
                "AI-Hub folder layout and pass --data-root."
            )
    images: dict[tuple[str, str], Path] = {}
    for path in image_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            key = (path.parent.name, path.stem)
            if key in images:
                raise ValueError(f"Duplicate image key {key}")
            images[key] = path

    samples: list[Sample] = []
    topology_hash: str | None = None
    faces: np.ndarray | None = None
    for json_path in sorted(annotation_root.rglob("*.json")):
        with json_path.open("r", encoding="utf-8-sig") as handle:
            annotation = json.load(handle)
        subject = json_path.relative_to(annotation_root).parts[0]
        image_path = images.get((subject, json_path.stem))
        if image_path is None:
            raise ValueError(f"Annotation without same-stem image: {json_path.name}")
        if annotation.get(label_key) in (None, ""):
            raise ValueError(f"Annotation lacks label key {label_key!r}: {json_path.name}")
        vertices = parse_vertices(annotation["3Dlandmark"])
        raw_hash = hashlib.sha256("\n".join(annotation["face"]).encode("utf-8")).hexdigest()
        if topology_hash is None:
            topology_hash = raw_hash
            faces = parse_faces(annotation["face"], len(vertices))
        elif raw_hash != topology_hash:
            raise ValueError(f"Mesh topology differs from the first annotation: {json_path.name}")
        samples.append(
            Sample(
                stem=json_path.stem,
                subject=subject,
                image_path=image_path,
                json_path=json_path,
                label=str(annotation[label_key]),
                light=str(annotation.get("light", "unknown")),
                vertices=normalize_vertices(vertices),
            )
        )
    if not samples or faces is None:
        raise ValueError("No paired image/annotation samples were found.")
    if len({s.vertices.shape[0] for s in samples}) != 1:
        raise ValueError("All samples must share one ordered vertex count.")
    return samples, faces, topology_hash or ""


def load_images(samples: list[Sample]) -> torch.Tensor:
    """Decode once: short side -> 256 (bicubic), centre crop 224. Returns uint8 (n, 3, 224, 224)."""
    out = np.zeros((len(samples), 224, 224, 3), dtype=np.uint8)
    for i, sample in enumerate(samples):
        with Image.open(sample.image_path) as handle:
            image = handle.convert("RGB")
        w, h = image.size
        scale = 256.0 / min(w, h)
        image = image.resize((max(256, round(w * scale)), max(256, round(h * scale))), Image.BICUBIC)
        w, h = image.size
        left, top = (w - 224) // 2, (h - 224) // 2
        out[i] = np.asarray(image.crop((left, top, left + 224, top + 224)))
    return torch.from_numpy(out).permute(0, 3, 1, 2).contiguous()


# --------------------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------------------
def mesh_edges(faces: np.ndarray) -> np.ndarray:
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]], axis=0)
    return np.unique(np.sort(edges, axis=1), axis=0)


def local_edge_lengths(vertices: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Mean length of the edges incident to each vertex. vertices: (n, N, 3) -> (n, N)."""
    n, n_vertices, _ = vertices.shape
    lengths = np.linalg.norm(vertices[:, edges[:, 0]] - vertices[:, edges[:, 1]], axis=-1)
    sums = np.zeros((n, n_vertices))
    degree = np.zeros(n_vertices)
    for column in (0, 1):
        np.add.at(sums, (slice(None), edges[:, column]), lengths)
        np.add.at(degree, edges[:, column], 1.0)
    if (degree == 0).any():
        raise ValueError("Mesh topology has isolated vertices.")
    return sums / degree


def asymmetry_metric(points: np.ndarray) -> float:
    """Symmetric Chamfer distance between a mesh and its x-mirror (correspondence-free)."""
    mirrored = points.copy()
    mirrored[:, 0] *= -1.0
    forward = cKDTree(points).query(mirrored, k=1)[0]
    reverse = cKDTree(mirrored).query(points, k=1)[0]
    return float(0.5 * (forward.mean() + reverse.mean()))


def rigid_align(points: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Rotation (det=+1) and translation that best map points onto target (no scaling)."""
    pc = points.mean(axis=0, keepdims=True)
    tc = target.mean(axis=0, keepdims=True)
    x, y = points - pc, target - tc
    u, _, vt = np.linalg.svd(x.T @ y, full_matrices=False)
    correction = np.eye(3)
    correction[-1, -1] = np.sign(np.linalg.det(u @ vt)) or 1.0
    return x @ (u @ correction @ vt) + tc


def procrustes_shift(points: np.ndarray, template: np.ndarray) -> float:
    aligned = rigid_align(points, template)
    return float(np.sqrt(np.mean(np.sum((aligned - template) ** 2, axis=1))))


def build_template(vertices: np.ndarray, subjects: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    """Class-agnostic mean mesh of the TRAINING samples, each training identity weighted equally."""
    means = [vertices[train_idx[subjects[train_idx] == s]].mean(axis=0) for s in np.unique(subjects[train_idx])]
    return np.mean(means, axis=0)


def flip_permutation(template: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """Left-right vertex correspondence from the mean template.

    The template is mirrored in x and matched one-to-one to itself with the Hungarian algorithm
    (scipy.optimize.linear_sum_assignment on squared distances). perm[i] is the index of the
    vertex that sits where the mirror image of vertex i lands. A valid left-right map must be an
    involution (perm[perm[i]] == i); this is verified and the run aborts otherwise.
    """
    t = template.astype(np.float64)
    x0 = float(t[:, 0].mean())
    perm = np.arange(len(t))
    for _ in range(3):  # refine the mirror-plane offset from the matched pairs
        mirrored = t.copy()
        mirrored[:, 0] = 2.0 * x0 - mirrored[:, 0]
        cost = cdist(mirrored, t, metric="sqeuclidean")
        rows, cols = linear_sum_assignment(cost)
        perm = cols[np.argsort(rows)]
        x0 = float(0.5 * (t[:, 0] + t[perm, 0]).mean())
    mirrored = t.copy()
    mirrored[:, 0] = 2.0 * x0 - mirrored[:, 0]
    residual = float(np.sqrt(np.mean(np.sum((mirrored - t[perm]) ** 2, axis=1))))
    nearest = cKDTree(t).query(mirrored, k=1)[1]
    info = {
        "is_involution": bool(np.array_equal(perm[perm], np.arange(len(t)))),
        "fixed_points": int((perm == np.arange(len(t))).sum()),
        "swapped_pairs": int((perm != np.arange(len(t))).sum() // 2),
        "mirror_plane_x": x0,
        "match_residual_rms": residual,
        "template_rms_radius": float(np.sqrt(np.mean(np.sum((t - t.mean(0)) ** 2, axis=1)))),
        "agrees_with_nearest_neighbour": bool(np.array_equal(nearest, perm)),
        "permutation_sha256": hashlib.sha256(perm.astype(np.int64).tobytes()).hexdigest(),
    }
    if not info["is_involution"]:
        raise RuntimeError(f"Left-right vertex permutation is not an involution: {info}")
    return perm, info


def mirror_permuted(vertices: np.ndarray, perm: np.ndarray) -> np.ndarray:
    """Anatomically consistent mirror: reflect x, then relabel vertices by their counterpart."""
    out = vertices[..., perm, :].copy()
    out[..., 0] *= -1.0
    return out


class Geometry:
    """Fold-independent mesh quantities plus per-training-set feature construction."""

    def __init__(self, samples: list[Sample], faces: np.ndarray) -> None:
        self.vertices = np.stack([s.vertices for s in samples])  # (n, N, 3)
        self.subjects = np.asarray([s.subject for s in samples])
        self.labels_text = np.asarray([s.label for s in samples])
        self.lights = np.asarray([s.light for s in samples])
        self.edges = mesh_edges(faces)
        self.edge_len = local_edge_lengths(self.vertices, self.edges)  # (n, N)
        self.asym = np.asarray([asymmetry_metric(v) for v in self.vertices])
        self.n, self.n_vertices = self.vertices.shape[:2]
        # Neutral reference of the same subject under the same lighting level.
        self.neutral_index = np.full(self.n, -1)
        for i in range(self.n):
            match = np.flatnonzero(
                (self.subjects == self.subjects[i])
                & (self.lights == self.lights[i])
                & (self.labels_text == NEUTRAL_LABEL)
            )
            if len(match) != 1:
                raise ValueError(f"Expected exactly one Neutral reference for sample {i}, found {len(match)}")
            self.neutral_index[i] = match[0]
        # Identity-removed representation: rigidly align each mesh to its Neutral reference and
        # subtract it. Uses only that subject's own Neutral capture (no template, no other subject).
        self.neutral_disp = np.zeros_like(self.vertices)
        for i in range(self.n):
            reference = self.vertices[self.neutral_index[i]]
            self.neutral_disp[i] = rigid_align(self.vertices[i], reference) - reference
        self.neutral_edge = self.edge_len - self.edge_len[self.neutral_index]
        self.neutral_scal = np.stack(
            [
                self.asym - self.asym[self.neutral_index],
                np.sqrt(np.mean(np.sum(self.neutral_disp**2, axis=2), axis=1)),
            ],
            axis=1,
        )
        self._cache: dict[tuple[str, str], Any] = {}
        self.flip_info: dict[str, dict[str, Any]] = {}

    def features(self, train_idx: np.ndarray, mesh_mode: str) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        """Standardised mesh inputs for the views {none, perm, naive}.

        Everything that is estimated (template, left-right permutation, mean/std) uses the
        training indices only. Returns view -> (nodes (n, N*4), scalars (n, 2)).
        """
        key = (hashlib.sha256(np.sort(train_idx).astype(np.int64).tobytes()).hexdigest(), mesh_mode)
        if key in self._cache:
            return self._cache[key]
        if len(self._cache) > 32:  # bound host memory; entries are cheap to rebuild
            self._cache.clear()
        template = build_template(self.vertices, self.subjects, train_idx)
        perm, info = flip_permutation(template)
        self.flip_info[key[0]] = info
        views: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        if mesh_mode == "raw":
            shift = lambda verts: np.asarray([procrustes_shift(v, template) for v in verts])  # noqa: E731
            v_perm = mirror_permuted(self.vertices, perm)
            v_naive = self.vertices.copy()
            v_naive[..., 0] *= -1.0
            views["none"] = (
                np.concatenate([self.vertices, self.edge_len[..., None]], axis=2),
                np.stack([self.asym, shift(self.vertices)], axis=1),
            )
            # Correct flip: vertices and local descriptors are permuted, G is recomputed for the
            # flipped mesh (it is now a proper face, so a rotation-only fit is meaningful).
            views["perm"] = (
                np.concatenate([v_perm, local_edge_lengths(v_perm, self.edges)[..., None]], axis=2),
                np.stack([self.asym, shift(v_perm)], axis=1),
            )
            # Original (buggy) flip kept for the ablation: x negated, vertex order untouched,
            # G fitted with a rotation-only alignment of a mirror-image mesh.
            views["naive"] = (
                np.concatenate([v_naive, self.edge_len[..., None]], axis=2),
                np.stack([self.asym, shift(v_naive)], axis=1),
            )
        elif mesh_mode == "neutral":
            views["none"] = (
                np.concatenate([self.neutral_disp, self.neutral_edge[..., None]], axis=2),
                self.neutral_scal,
            )
            views["perm"] = (
                np.concatenate(
                    [mirror_permuted(self.neutral_disp, perm), self.neutral_edge[:, perm][..., None]], axis=2
                ),
                self.neutral_scal,
            )
        else:
            raise ValueError(f"Unknown mesh mode: {mesh_mode}")

        nodes_train = views["none"][0][train_idx].reshape(len(train_idx), -1)
        scal_train = views["none"][1][train_idx]
        node_mean, node_std = nodes_train.mean(axis=0), nodes_train.std(axis=0)
        node_std = np.maximum(node_std, 1e-3 * float(node_std.mean()))
        scal_mean, scal_std = scal_train.mean(axis=0), np.maximum(scal_train.std(axis=0), 1e-8)
        out = {
            view: (
                ((nodes.reshape(self.n, -1) - node_mean) / node_std).astype(np.float32),
                ((scal - scal_mean) / scal_std).astype(np.float32),
            )
            for view, (nodes, scal) in views.items()
        }
        self._cache[key] = out
        return out


# --------------------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------------------
class FaceClassifier(nn.Module):
    def __init__(self, n_classes: int, n_vertices: int, arch: str, encoder_state: dict | None) -> None:
        super().__init__()
        if arch not in {"image", "mesh", "scalars", "fused"}:
            raise ValueError(f"Unknown architecture: {arch}")
        self.arch = arch
        if arch != "mesh":
            self.encoder = efficientnet_b0(weights=None)
            if encoder_state is not None:
                self.encoder.load_state_dict(encoder_state)
            visual_dim = self.encoder.classifier[1].in_features
            self.encoder.classifier = nn.Identity()
        if arch == "image":
            self.head = nn.Sequential(
                nn.Linear(visual_dim, 512), nn.GELU(), nn.Dropout(0.30), nn.Linear(512, n_classes)
            )
            return
        if arch in {"scalars", "fused"}:
            self.image_projection = nn.Sequential(nn.Linear(visual_dim, 256), nn.GELU(), nn.Dropout(0.20))
        if arch in {"mesh", "fused"}:
            self.mesh_mlp = nn.Sequential(
                nn.Linear(n_vertices * 4 + 2, 512), nn.LayerNorm(512), nn.GELU(), nn.Dropout(0.30),
                nn.Linear(512, 128), nn.GELU(),
            )
        if arch == "scalars":
            self.scalar_mlp = nn.Sequential(nn.Linear(2, 32), nn.GELU())
        joint = {"mesh": 128, "scalars": 256 + 32, "fused": 256 + 128}[arch]
        self.head = nn.Sequential(nn.Linear(joint, 256), nn.GELU(), nn.Dropout(0.30), nn.Linear(256, n_classes))

    def forward(self, image: torch.Tensor | None, mesh: torch.Tensor, scal: torch.Tensor) -> torch.Tensor:
        if self.arch == "mesh":
            return self.head(self.mesh_mlp(torch.cat([mesh, scal], dim=1)))
        visual = self.encoder(image)
        if self.arch == "image":
            return self.head(visual)
        image_z = self.image_projection(visual)
        if self.arch == "scalars":
            return self.head(torch.cat([image_z, self.scalar_mlp(scal)], dim=1))
        return self.head(torch.cat([image_z, self.mesh_mlp(torch.cat([mesh, scal], dim=1))], dim=1))


# --------------------------------------------------------------------------------------
# Splits
# --------------------------------------------------------------------------------------
@dataclass
class Job:
    protocol: str
    condition: str
    seed: int
    fold: str
    train_idx: np.ndarray
    test_idx: np.ndarray
    epochs: int = 0
    meta: dict[str, Any] | None = None

    @property
    def key(self) -> str:
        return f"{self.protocol}|{self.condition}|{self.seed}|{self.fold}|E{self.epochs}"


def loso_folds(subjects: np.ndarray) -> list[tuple[str, np.ndarray, np.ndarray]]:
    out = []
    for k, subject in enumerate(sorted(set(subjects.tolist())), start=1):
        test = np.flatnonzero(subjects == subject)
        train = np.flatnonzero(subjects != subject)
        out.append((f"{k:02d}", train, test))
    return out


def inner_folds(subjects: np.ndarray, train_idx: np.ndarray, seed: int, n_inner: int = 3):
    train_subjects = np.asarray(sorted(set(subjects[train_idx].tolist())))
    rng = np.random.default_rng(seed)
    groups = np.array_split(train_subjects[rng.permutation(len(train_subjects))], n_inner)
    out = []
    for j, group in enumerate(groups, start=1):
        val = train_idx[np.isin(subjects[train_idx], group)]
        fit = train_idx[~np.isin(subjects[train_idx], group)]
        out.append((j, fit, val))
    return out


def stratified_group_folds(units: np.ndarray, strata: np.ndarray, seed: int, n_folds: int = 10) -> np.ndarray:
    """Assign each unit (image or triplet) to a fold, balancing folds within each stratum."""
    rng = np.random.default_rng(seed)
    unit_ids, first = np.unique(units, return_index=True)
    unit_strata = strata[first]
    fold_of_unit = np.zeros(len(unit_ids), dtype=np.int64)
    for stratum in np.unique(unit_strata):
        members = np.flatnonzero(unit_strata == stratum)
        members = members[rng.permutation(len(members))]
        offset = int(rng.integers(n_folds))
        fold_of_unit[members] = (np.arange(len(members)) + offset) % n_folds
    lookup = dict(zip(unit_ids.tolist(), fold_of_unit.tolist()))
    return np.asarray([lookup[u] for u in units.tolist()])


def build_jobs(samples: list[Sample], seeds: list[int], inner_seed: int) -> dict[str, list[Job]]:
    """All splits for all protocols (epochs are filled in later for non-inner protocols)."""
    subjects = np.asarray([s.subject for s in samples])
    labels = np.asarray([s.label for s in samples])
    lights = np.asarray([s.light for s in samples])
    triplets = np.asarray([s.triplet for s in samples])
    stems = np.asarray([s.stem for s in samples])
    outer = loso_folds(subjects)
    jobs: dict[str, list[Job]] = {"inner": [], "loso": [], "random": [], "triplet": [], "lightout": []}
    for fold, train, test in outer:
        for j, fit, val in inner_folds(subjects, train, inner_seed + int(fold)):
            for condition in INNER_CONDITIONS:
                for epochs in epoch_grid(condition):
                    jobs["inner"].append(
                        Job("inner", condition, inner_seed, f"{fold}.{j}", fit, val, epochs, {"outer_fold": fold})
                    )
    for seed in seeds:
        for fold, train, test in outer:
            for condition in LOSO_CONDITIONS:
                jobs["loso"].append(Job("loso", condition, seed, fold, train, test, 0, {"outer_fold": fold}))
            for light in sorted(set(lights.tolist())):
                keep = train[lights[train] != light]
                for condition in LIGHT_CONDITIONS:
                    jobs["lightout"].append(
                        Job("lightout", condition, seed, f"{fold}.{light}", keep, test, 0,
                            {"outer_fold": fold, "held_out_light": light})
                    )
        for protocol, units in (("random", stems), ("triplet", triplets)):
            assignment = stratified_group_folds(units, labels, seed * 7 + (protocol == "triplet"))
            for k in range(10):
                train, test = np.flatnonzero(assignment != k), np.flatnonzero(assignment == k)
                for condition in SPLIT_CONDITIONS:
                    jobs[protocol].append(Job(protocol, condition, seed, f"{k + 1:02d}", train, test, 0, {}))
    return jobs


def write_manifest(path: Path, samples: list[Sample], jobs: dict[str, list[Job]]) -> str:
    """One row per (protocol, seed, fold, sample): the partition every model of that fold sees."""
    seen: set[tuple[str, int, str]] = set()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["protocol", "seed", "fold", "partition", "sample_id", "subject_id", "label", "light"])
        for protocol, job_list in jobs.items():
            for job in job_list:
                ident = (protocol, job.seed, job.fold)
                if ident in seen:
                    continue
                seen.add(ident)
                for partition, indices in (("train", job.train_idx), ("test", job.test_idx)):
                    for i in indices.tolist():
                        s = samples[i]
                        writer.writerow([protocol, job.seed, job.fold, partition, s.stem, s.subject, s.label, s.light])
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_splits(samples: list[Sample], jobs: dict[str, list[Job]]) -> None:
    subjects = np.asarray([s.subject for s in samples])
    triplets = np.asarray([s.triplet for s in samples])
    lights = np.asarray([s.light for s in samples])
    for protocol, job_list in jobs.items():
        for job in job_list:
            if set(job.train_idx.tolist()) & set(job.test_idx.tolist()):
                raise AssertionError(f"Sample overlap in {job.key}")
            if protocol in {"inner", "loso", "lightout"} and set(subjects[job.train_idx]) & set(subjects[job.test_idx]):
                raise AssertionError(f"Subject leakage in {job.key}")
            if protocol == "triplet" and set(triplets[job.train_idx]) & set(triplets[job.test_idx]):
                raise AssertionError(f"Triplet leakage in {job.key}")
            if protocol == "lightout" and job.meta["held_out_light"] in set(lights[job.train_idx]):
                raise AssertionError(f"Held-out light present in training: {job.key}")


# --------------------------------------------------------------------------------------
# Training
# --------------------------------------------------------------------------------------
class Runner:
    def __init__(self, samples, geometry, classes, device, args) -> None:
        self.samples = samples
        self.classes = classes
        self.device = device
        self.args = args
        self.geometry = geometry
        self.labels = torch.tensor([classes.index(s.label) for s in samples], device=device)
        self.images = load_images(samples).to(device)
        self.mean = torch.tensor(IMAGENET_MEAN, device=device).view(1, 3, 1, 1)
        self.std = torch.tensor(IMAGENET_STD, device=device).view(1, 3, 1, 1)
        weights = EfficientNet_B0_Weights.DEFAULT if args.weights == "imagenet" else None
        self.encoder_state = efficientnet_b0(weights=weights).state_dict() if weights else None
        # Donor candidates for the shuffled-mesh control: same subject, same light, other expression.
        g = self.geometry
        self.donors = torch.from_numpy(
            np.stack(
                [
                    np.flatnonzero(
                        (g.subjects == g.subjects[i]) & (g.lights == g.lights[i]) & (g.labels_text != g.labels_text[i])
                    )
                    for i in range(g.n)
                ]
            )
        ).to(device)
        self._feature_tensors: dict[tuple[str, str], dict[str, tuple[torch.Tensor, torch.Tensor]]] = {}

    def feature_tensors(self, train_idx: np.ndarray, mesh_mode: str):
        key = (hashlib.sha256(np.sort(train_idx).astype(np.int64).tobytes()).hexdigest(), mesh_mode)
        if key not in self._feature_tensors:
            if len(self._feature_tensors) > 64:
                self._feature_tensors.clear()
            views = self.geometry.features(train_idx, mesh_mode)
            self._feature_tensors[key] = {
                v: (torch.from_numpy(n).to(self.device), torch.from_numpy(s).to(self.device))
                for v, (n, s) in views.items()
            }
        return self._feature_tensors[key]

    def prepare_images(self, idx: torch.Tensor, flip: torch.Tensor | None, jitter: torch.Tensor | None) -> torch.Tensor:
        x = self.images[idx].float() / 255.0
        if flip is not None:
            x = torch.where(flip.view(-1, 1, 1, 1), x.flip(-1), x)
        if jitter is not None:  # brightness, contrast, saturation (fixed order), per sample
            b, c, s = (jitter[:, i].view(-1, 1, 1, 1) for i in range(3))
            x = (x * b).clamp(0, 1)
            gray = (0.299 * x[:, 0:1] + 0.587 * x[:, 1:2] + 0.114 * x[:, 2:3])
            x = ((x - gray.mean(dim=(1, 2, 3), keepdim=True)) * c + gray.mean(dim=(1, 2, 3), keepdim=True)).clamp(0, 1)
            gray = (0.299 * x[:, 0:1] + 0.587 * x[:, 1:2] + 0.114 * x[:, 2:3])
            x = ((x - gray) * s + gray).clamp(0, 1)
        return (x - self.mean) / self.std

    def run(self, job: Job) -> dict[str, Any]:
        cond = CONDITIONS[job.condition]
        args, device = self.args, self.device
        started = time.perf_counter()
        feats = self.feature_tensors(job.train_idx, cond.mesh_mode)
        # Same seed for every condition of a (seed, fold): data order, flips and colour jitter
        # are common random numbers across the paired conditions.
        run_seed = int(hashlib.sha256(f"{job.protocol}|{job.seed}|{job.fold}".encode()).hexdigest()[:8], 16)
        torch.manual_seed(run_seed)
        torch.cuda.manual_seed_all(run_seed)
        gen = torch.Generator().manual_seed(run_seed)
        model = FaceClassifier(len(self.classes), self.geometry.n_vertices, cond.arch, self.encoder_state).to(device)
        train_idx = torch.from_numpy(job.train_idx)
        counts = torch.bincount(self.labels[train_idx.to(device)], minlength=len(self.classes)).float()
        class_weights = counts.sum() / (len(self.classes) * counts.clamp(min=1.0))
        criterion = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=0.05)
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
        use_amp = args.amp and device.type == "cuda" and cond.arch != "mesh"
        scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
        steps_per_epoch = math.ceil(len(train_idx) / args.batch_size)
        total_steps = job.epochs * steps_per_epoch
        step = 0
        epoch_losses: list[float] = []
        model.train()
        for _ in range(job.epochs):
            order = train_idx[torch.randperm(len(train_idx), generator=gen)]
            losses = []
            for start in range(0, len(order), args.batch_size):
                batch = order[start:start + args.batch_size]
                # Step-based cosine schedule: depends only on the optimiser step count.
                lr = args.learning_rate * 0.5 * (1.0 + math.cos(math.pi * step / total_steps))
                for group in optimizer.param_groups:
                    group["lr"] = lr
                # Always draw the same random numbers, whether or not the condition uses them.
                flip_draw = torch.rand(len(batch), generator=gen) < 0.5
                jitter_draw = torch.rand(len(batch), 3, generator=gen)
                donor_draw = torch.randint(self.donors.shape[1], (len(batch),), generator=gen)
                batch_d = batch.to(device)
                flip = flip_draw.to(device) if cond.flip != "none" else torch.zeros(len(batch), dtype=torch.bool, device=device)
                span = torch.tensor([0.20, 0.20, 0.15])
                jitter = (1.0 + (2.0 * jitter_draw - 1.0) * span).to(device)
                mesh_idx = self.donors[batch_d, donor_draw.to(device)] if cond.shuffled else batch_d
                view = cond.flip if cond.flip != "none" else "none"
                nodes = torch.where(flip.view(-1, 1), feats[view][0][mesh_idx], feats["none"][0][mesh_idx])
                scal = torch.where(flip.view(-1, 1), feats[view][1][mesh_idx], feats["none"][1][mesh_idx])
                image = None
                if cond.arch != "mesh":
                    image = self.prepare_images(batch_d, flip, jitter)
                with torch.autocast("cuda", dtype=torch.float16, enabled=use_amp):
                    loss = criterion(model(image, nodes, scal), self.labels[batch_d])
                optimizer.zero_grad(set_to_none=True)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
                losses.append(float(loss.detach()))
                step += 1
            epoch_losses.append(float(np.mean(losses)))

        # Single evaluation with the final-epoch weights. No checkpoint selection of any kind.
        model.eval()
        test_idx = torch.from_numpy(job.test_idx).to(device)
        donor_rng = np.random.default_rng(run_seed)
        fixed_donor = torch.from_numpy(donor_rng.integers(self.donors.shape[1], size=len(test_idx))).to(device)
        mesh_idx = self.donors[test_idx, fixed_donor] if cond.shuffled else test_idx
        probs = []
        with torch.inference_mode():
            for start in range(0, len(test_idx), 64):
                sl = slice(start, start + 64)
                image = None
                if cond.arch != "mesh":
                    image = self.prepare_images(test_idx[sl], None, None)
                with torch.autocast("cuda", dtype=torch.float16, enabled=use_amp):
                    logits = model(image, feats["none"][0][mesh_idx[sl]], feats["none"][1][mesh_idx[sl]])
                probs.append(torch.softmax(logits.float(), dim=1).cpu())
        probabilities = torch.cat(probs).numpy()
        del model, optimizer
        return {
            "key": job.key,
            "protocol": job.protocol,
            "condition": job.condition,
            "seed": job.seed,
            "fold": job.fold,
            "epochs": job.epochs,
            "steps": total_steps,
            "meta": job.meta or {},
            "run_seed": run_seed,
            "n_train": int(len(job.train_idx)),
            "test_idx": job.test_idx.tolist(),
            "probabilities": np.round(probabilities, 6).tolist(),
            "train_loss_per_epoch": [round(v, 5) for v in epoch_losses],
            "seconds": round(time.perf_counter() - started, 2),
        }


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------
def load_done(path: Path) -> dict[str, dict[str, Any]]:
    done: dict[str, dict[str, Any]] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    record = json.loads(line)
                    done[record["key"]] = record
    return done


def execute(runner: Runner, jobs: list[Job], log_path: Path, label: str) -> dict[str, dict[str, Any]]:
    done = load_done(log_path)
    todo = [job for job in jobs if job.key not in done]
    print(f"[{label}] {len(jobs) - len(todo)} done, {len(todo)} to run", flush=True)
    started = time.perf_counter()
    # Cheap mesh-only jobs first, so a slow image job never blocks them.
    todo.sort(key=lambda j: CONDITIONS[j.condition].arch != "mesh")
    for n, job in enumerate(todo, start=1):
        record = runner.run(job)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        done[job.key] = record
        if n % 10 == 0 or n == len(todo):
            elapsed = time.perf_counter() - started
            eta = elapsed / n * (len(todo) - n)
            print(f"[{label}] {n}/{len(todo)} elapsed {elapsed / 60:.1f} min, eta {eta / 60:.1f} min "
                  f"(last: {job.key}, {record['seconds']}s)", flush=True)
    return {job.key: done[job.key] for job in jobs}


def accuracy_of(record: dict[str, Any], labels: np.ndarray) -> float:
    pred = np.asarray(record["probabilities"]).argmax(axis=1)
    return float((pred == labels[np.asarray(record["test_idx"])]).mean())


def select_epochs(inner_jobs: list[Job], results: dict[str, dict[str, Any]], labels: np.ndarray, out_dir: Path):
    """Epoch count per (condition, outer fold): best mean inner-validation accuracy; ties -> fewer epochs."""
    table: dict[tuple[str, str, int], list[float]] = {}
    rows = []
    for job in inner_jobs:
        acc = accuracy_of(results[job.key], labels)
        table.setdefault((job.condition, job.meta["outer_fold"], job.epochs), []).append(acc)
        rows.append({"condition": job.condition, "outer_fold": job.meta["outer_fold"], "inner_fold": job.fold,
                     "epochs": job.epochs, "inner_val_accuracy": round(acc, 6)})
    selection: dict[str, dict[str, int]] = {}
    summary = []
    for condition in INNER_CONDITIONS:
        selection[condition] = {}
        for fold in sorted({k[1] for k in table if k[0] == condition}):
            means = {e: float(np.mean(table[(condition, fold, e)])) for e in epoch_grid(condition)}
            best = min(means, key=lambda e: (-round(means[e], 9), e))
            selection[condition][fold] = best
            summary.append({"condition": condition, "outer_fold": fold, "selected_epochs": best,
                            **{f"mean_inner_val_acc_E{e}": round(v, 6) for e, v in means.items()}})
    write_rows(out_dir / "epoch_selection_inner_runs.csv", rows)
    write_rows(out_dir / "epoch_selection.csv", summary)
    return selection


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        fields.extend(k for k in row if k not in fields)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def assign_epochs(jobs: dict[str, list[Job]], selection: dict[str, dict[str, int]]) -> None:
    def source(condition: str) -> str:
        return CONDITIONS[condition].epochs_from or condition

    for protocol in ("loso", "lightout"):
        for job in jobs[protocol]:
            job.epochs = selection[source(job.condition)][job.meta["outer_fold"]]
    # Non-subject-disjoint protocols have no clean training-subject set to select on; they reuse
    # the (lower) median of the LOSO-selected epoch counts for the same model.
    for protocol in ("random", "triplet"):
        for job in jobs[protocol]:
            values = sorted(selection[source(job.condition)].values())
            job.epochs = values[(len(values) - 1) // 2]


def write_predictions(path: Path, samples: list[Sample], classes: list[str], jobs: list[Job],
                      results: dict[str, dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["protocol", "condition", "seed", "fold", "held_out_light", "epochs", "sample_id",
                         "subject_id", "label", "light", "triplet_id", "prediction", "correct",
                         *[f"prob_{c}" for c in classes]])
        for job in jobs:
            record = results[job.key]
            for i, probs in zip(record["test_idx"], record["probabilities"]):
                s = samples[i]
                pred = classes[int(np.argmax(probs))]
                writer.writerow([job.protocol, job.condition, job.seed, job.fold,
                                 (job.meta or {}).get("held_out_light", ""), job.epochs, s.stem, s.subject,
                                 s.label, s.light, s.triplet, pred, int(pred == s.label),
                                 *[f"{p:.6f}" for p in probs]])


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return None


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name  # never record an absolute, user-specific path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT,
                        help="AI-Hub sample folder containing 01.원천데이터/ and 02.라벨링데이터/ "
                             "(relative paths are resolved against the repository root).")
    parser.add_argument("--output-dir", type=Path, default=Path("results/cvpr2027"))
    parser.add_argument("--label-key", default="expression")
    parser.add_argument("--stage", default="all",
                        choices=("manifest", "inner", "loso", "splits", "lightout", "all"))
    parser.add_argument("--seeds", type=int, nargs="+", default=[2027, 2028, 2029, 2030, 2031])
    parser.add_argument("--inner-seed", type=int, default=2027)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weights", choices=("imagenet", "random"), default="imagenet")
    parser.add_argument("--amp", action="store_true",
                        help="Mixed precision (off by default: FP32 was as fast on the RTX 3060 used here).")
    parser.add_argument("--smoke", action="store_true",
                        help="Pipeline check only: 1 epoch, first two outer folds, one seed.")
    args = parser.parse_args()

    data_root = args.data_root if args.data_root.is_absolute() else REPO_ROOT / args.data_root
    out_dir = args.output_dir if args.output_dir.is_absolute() else REPO_ROOT / args.output_dir
    (out_dir / "logs").mkdir(parents=True, exist_ok=True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    samples, faces, topology_hash = discover_samples(data_root, args.label_key)
    classes = sorted({s.label for s in samples})
    labels = np.asarray([classes.index(s.label) for s in samples])
    seeds = args.seeds[:1] if args.smoke else args.seeds
    jobs = build_jobs(samples, seeds, args.inner_seed)
    if args.smoke:
        for protocol in jobs:
            jobs[protocol] = [j for j in jobs[protocol] if j.fold[:2] in {"01", "02"}]
            if protocol == "inner":
                jobs[protocol] = [j for j in jobs[protocol] if j.epochs == epoch_grid(j.condition)[0]]
                for j in jobs[protocol]:
                    j.epochs = 1
    check_splits(samples, jobs)

    # ---- everything below this line is written BEFORE any training ----
    manifest_hash = write_manifest(out_dir / "split_manifest.csv", samples, jobs)
    environment = {
        "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "command": " ".join(["run_validation.py", *sys.argv[1:]]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torchvision": __import__("torchvision").__version__,
        "numpy": np.__version__,
        "scipy": __import__("scipy").__version__,
        "pillow": __import__("PIL").__version__,
        "device": str(device),
        "cuda_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "mixed_precision": bool(args.amp and device.type == "cuda"),
        "seeds": seeds,
        "inner_seed": args.inner_seed,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "optimizer": "AdamW(weight_decay=1e-4), step-based cosine to 0, no warm-up",
        "loss": "class-weighted cross-entropy, label_smoothing=0.05",
        "weights": args.weights,
        "image_epoch_grid": list(IMAGE_EPOCH_GRID),
        "mesh_epoch_grid": list(MESH_EPOCH_GRID),
        "conditions": {name: vars(c) for name, c in CONDITIONS.items()},
        "split_manifest_sha256": manifest_hash,
        "smoke": args.smoke,
    }
    (out_dir / "environment.json").write_text(json.dumps(environment, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "data_summary.json").write_text(
        json.dumps(
            {
                "samples": len(samples),
                "subjects": sorted({s.subject for s in samples}),
                "classes": classes,
                "class_counts": {c: int(sum(s.label == c for s in samples)) for c in classes},
                "lights": sorted({s.light for s in samples}),
                "capture_triplets": len({s.triplet for s in samples}),
                "vertices_per_mesh": int(samples[0].vertices.shape[0]),
                "triangles_per_mesh": int(len(faces)),
                "topology_sha256": topology_hash,
                "data_root": relative(data_root),
                "label_key": args.label_key,
            },
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # Left-right vertex permutation of every LOSO training template, verified before training.
    geometry = Geometry(samples, faces)
    flip_report: dict[str, Any] = {"folds": {}}
    for fold, train, _ in loso_folds(geometry.subjects):
        geometry.features(train, "raw")
        key = hashlib.sha256(np.sort(train).astype(np.int64).tobytes()).hexdigest()
        flip_report["folds"][fold] = geometry.flip_info[key]
    hashes = {info["permutation_sha256"] for info in flip_report["folds"].values()}
    flip_report["all_folds_involution"] = all(i["is_involution"] for i in flip_report["folds"].values())
    flip_report["identical_permutation_across_folds"] = len(hashes) == 1
    (out_dir / "flip_permutation.json").write_text(json.dumps(flip_report, indent=2), encoding="utf-8")
    print(json.dumps({"event": "manifest_written", "sha256": manifest_hash,
                      "jobs": {k: len(v) for k, v in jobs.items()},
                      "flip_involution": flip_report["all_folds_involution"],
                      "flip_identical_across_folds": flip_report["identical_permutation_across_folds"]}), flush=True)
    if args.stage == "manifest":
        return

    runner = Runner(samples, geometry, classes, device, args)
    log_path = out_dir / "logs" / "runs.jsonl"
    stage = args.stage

    inner_results = execute(runner, jobs["inner"], log_path, "inner")
    if args.smoke:
        selection = {c: {f"{k:02d}": 1 for k in range(1, 11)} for c in INNER_CONDITIONS}
    else:
        selection = select_epochs(jobs["inner"], inner_results, labels, out_dir)
    assign_epochs(jobs, selection)
    check = {}
    for protocol, names in (("loso", ("loso",)), ("splits", ("random", "triplet")), ("lightout", ("lightout",))):
        if stage not in {protocol, "all"}:
            continue
        for name in names:
            results = execute(runner, jobs[name], log_path, name)
            write_predictions(out_dir / f"predictions_{name}.csv", samples, classes, jobs[name], results)
            check[name] = len(results)
    print(json.dumps({"event": "stage_complete", "stage": stage, "written": check}), flush=True)


if __name__ == "__main__":
    main()
