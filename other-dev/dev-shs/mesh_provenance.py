#!/usr/bin/env python3
"""Mesh provenance checks for the AI-Hub face-landmark sample (no training involved).

1. Is the JSON `3Dlandmark` array the same data as the OBJ file of the same stem?
2. Does the mesh differ between the highlight / middlelight / lowlight images of the same
   subject and expression, and how large is that difference compared with expression and
   identity differences?
3. Is the lighting-related difference systematic (same direction for different subjects)?

Writes results/cvpr2027/mesh_provenance.json. Run from the repository root:
    python other-dev/dev-shs/mesh_provenance.py --data-root <AI-Hub sample folder>
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np

from run_validation import DEFAULT_DATA_ROOT, REPO_ROOT, discover_samples, relative, rigid_align


def read_obj(path: Path) -> tuple[np.ndarray, list[str]]:
    vertices, faces = [], []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "v":
            vertices.append([float(v) for v in parts[1:4]])
        elif parts[0] == "f":
            faces.append(" ".join(parts))
    return np.asarray(vertices), faces


def read_json_raw(path: Path) -> tuple[np.ndarray, list[str]]:
    annotation = json.loads(path.read_text(encoding="utf-8-sig"))
    vertices = np.asarray([[float(v) for v in item.split()[1:4]] for item in annotation["3Dlandmark"]])
    return vertices, [" ".join(item.split()) for item in annotation["face"]]


def rms(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.sum((a - b) ** 2, axis=1))))


def summary(values: list[float]) -> dict[str, float]:
    v = np.asarray(values)
    return {"n": int(len(v)), "min": float(v.min()), "median": float(np.median(v)),
            "mean": float(v.mean()), "max": float(v.max())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output", type=Path, default=Path("results/cvpr2027/mesh_provenance.json"))
    parser.add_argument("--permutations", type=int, default=2000)
    args = parser.parse_args()
    data_root = args.data_root if args.data_root.is_absolute() else REPO_ROOT / args.data_root
    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    samples, _, _ = discover_samples(data_root, "expression")
    obj_root = data_root / "01.원천데이터" / "3D data"

    # ---------------- 1. JSON vs OBJ ----------------
    n_obj_vertices, first_block_diff, faces_equal, second_block = [], [], [], []
    affine_r2 = []
    for s in samples:
        json_v, json_f = read_json_raw(s.json_path)
        obj_v, obj_f = read_obj(obj_root / s.subject / f"{s.stem}.obj")
        n = len(json_v)
        n_obj_vertices.append(len(obj_v))
        first_block_diff.append(float(np.abs(obj_v[:n] - json_v).max()))
        faces_equal.append(obj_f == json_f)
        if len(obj_v) == 2 * n:
            extra = obj_v[n:]
            second_block.append(extra)
            # Is the extra block an affine image of the 3D (x, y) coordinates (i.e. a projection)?
            design = np.column_stack([json_v[:, :2], np.ones(n)])
            coef, *_ = np.linalg.lstsq(design, extra[:, :2], rcond=None)
            resid = extra[:, :2] - design @ coef
            affine_r2.append(float(1.0 - resid.var() / extra[:, :2].var()))
    json_vs_obj = {
        "files_compared": len(samples),
        "obj_vertex_lines_per_file": sorted(set(n_obj_vertices)),
        "json_vertices_per_file": int(samples[0].vertices.shape[0]),
        "max_abs_difference_first_block_vs_json": float(max(first_block_diff)),
        "files_with_identical_first_block": int(sum(d == 0.0 for d in first_block_diff)),
        "files_with_identical_face_list": int(sum(faces_equal)),
    }
    if second_block:
        stack = np.stack(second_block)
        json_vs_obj["second_vertex_block"] = {
            "files_with_second_block": len(second_block),
            "all_z_zero": bool((stack[..., 2] == 0).all()),
            "xy_min": stack[..., :2].min(axis=(0, 1)).tolist(),
            "xy_max": stack[..., :2].max(axis=(0, 1)).tolist(),
            "identical_in_all_files": bool((stack == stack[0]).all()),
            "max_abs_difference_between_files": float(np.abs(stack - stack[0]).max()),
            "r2_affine_fit_from_3d_xy_median": float(np.median(affine_r2)),
            "r2_affine_fit_from_3d_xy_min": float(min(affine_r2)),
        }

    # ---------------- 2. variation across lighting ----------------
    raw = {(s.subject, s.label, s.light): read_json_raw(s.json_path)[0] for s in samples}
    norm = {(s.subject, s.label, s.light): s.vertices for s in samples}
    subjects = sorted({s.subject for s in samples})
    labels = sorted({s.label for s in samples})
    lights = sorted({s.light for s in samples})

    def aligned_rms(a_key, b_key) -> float:
        return rms(rigid_align(norm[a_key], norm[b_key]), norm[b_key])

    light_raw, light_aligned, identical_pairs = [], [], 0
    for subject, label in itertools.product(subjects, labels):
        for a, b in itertools.combinations(lights, 2):
            ka, kb = (subject, label, a), (subject, label, b)
            identical_pairs += int(np.array_equal(raw[ka], raw[kb]))
            light_raw.append(rms(raw[ka], raw[kb]))
            light_aligned.append(aligned_rms(ka, kb))
    expression_aligned = [
        aligned_rms((subject, a, light), (subject, b, light))
        for subject in subjects for light in lights for a, b in itertools.combinations(labels, 2)
    ]
    identity_aligned = [
        aligned_rms((a, label, light), (b, label, light))
        for label in labels for light in lights for a, b in itertools.combinations(subjects, 2)
    ]
    raw_radius = float(np.mean([np.sqrt(np.mean(np.sum((v - v.mean(0)) ** 2, axis=1))) for v in raw.values()]))
    across_light = {
        "capture_triplets": len(subjects) * len(labels),
        "light_pairs_compared": len(light_raw),
        "bit_identical_pairs": identical_pairs,
        "raw_units_rms_vertex_distance": summary(light_raw),
        "raw_units_mean_rms_radius_of_a_mesh": raw_radius,
        "normalised_after_rigid_alignment": {
            "same_subject_same_expression_different_light": summary(light_aligned),
            "same_subject_same_light_different_expression": summary(expression_aligned),
            "same_expression_same_light_different_subject": summary(identity_aligned),
        },
        "ratio_light_to_expression_median": float(np.median(light_aligned) / np.median(expression_aligned)),
        "ratio_expression_to_identity_median": float(np.median(expression_aligned) / np.median(identity_aligned)),
    }

    # ---------------- 3. is the lighting difference systematic? ----------------
    # Per subject: mean (over expressions) displacement field between two lighting levels after
    # rigid alignment. If lighting changed the mesh in a consistent way (e.g. a fitting bias),
    # these fields would point the same way for different subjects (mean pairwise cosine > 0).
    rng = np.random.default_rng(2027)

    def mean_cosine(fields: np.ndarray) -> float:
        unit = fields / np.linalg.norm(fields, axis=1, keepdims=True)
        gram = unit @ unit.T
        return float(gram[np.triu_indices(len(unit), k=1)].mean())

    systematic = {}
    for a, b in itertools.combinations(lights, 2):
        per_triplet = np.stack([
            np.stack([(rigid_align(norm[(s, l, a)], norm[(s, l, b)]) - norm[(s, l, b)]).ravel() for l in labels])
            for s in subjects
        ])  # (subjects, expressions, 3N)
        observed = mean_cosine(per_triplet.mean(axis=1))
        null = []
        for _ in range(args.permutations):  # randomly swap the two lights within each triplet
            signs = rng.choice([-1.0, 1.0], size=per_triplet.shape[:2])[..., None]
            null.append(mean_cosine((per_triplet * signs).mean(axis=1)))
        null_arr = np.asarray(null)
        systematic[f"{a}_vs_{b}"] = {
            "mean_pairwise_cosine_between_subject_fields": observed,
            "null_mean": float(null_arr.mean()),
            "null_95th_percentile": float(np.quantile(null_arr, 0.95)),
            "permutation_p_one_sided": float((1 + (null_arr >= observed).sum()) / (1 + len(null_arr))),
            "note": "approximate: the triplet-swap null treats triplets of one subject as exchangeable units",
        }

    report = {
        "data_root": relative(data_root),
        "json_vs_obj": json_vs_obj,
        "variation_across_lighting": across_light,
        "systematic_lighting_effect": systematic,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
