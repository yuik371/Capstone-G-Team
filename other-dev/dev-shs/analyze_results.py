#!/usr/bin/env python3
"""Subject-level statistics, tables and figures from the saved prediction files.

Reads   results/cvpr2027/predictions_{loso,random,triplet,lightout,lightmatch}.csv
Writes  results/cvpr2027/analysis/*.csv, *.png, analysis.json and results/cvpr2027/RESULTS.md

Unit of analysis is the SUBJECT (10 held-out identities). The 210 images are never treated
as independent: per-image predictions are first reduced to one accuracy per subject (averaged
over seeds), and every interval / test is computed on those 10 values or 10 paired differences.

Run from the repository root:  python other-dev/dev-shs/analyze_results.py
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[2]
CHANCE = 1.0 / 7.0
RNG_SEED = 2027
N_BOOT = 10000

# Chart tokens (light surface): categorical slots in fixed order, one sequential hue.
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#8a4fd3", "#b8860b"]
MARKERS = ["o", "s", "^", "D", "v"]
SEQ = matplotlib.colors.LinearSegmentedColormap.from_list("seq_blue", ["#fcfcfb", "#cde2fb", "#5598e7", "#0d366b"])

LABELS = {
    "image_flip": "Image only",
    "image_noflip": "Image only, no flip",
    "mesh_raw": "Mesh only",
    "mesh_naiveflip": "Mesh only, naive flip",
    "mesh_noflip": "Mesh only, no flip",
    "mesh_shuffled": "Mesh only, shuffled mesh",
    "mesh_neutral": "Mesh only, Neutral-subtracted",
    "mesh_neutral_ref": "Mesh only, 1 Neutral reference",
    "scalars": "Image + [A, G] scalars",
    "fused_perm": "Fused (image + mesh)",
    "fused_naiveflip": "Fused, naive flip",
    "fused_noflip": "Fused, no flip",
    "fused_shuffled": "Fused, shuffled mesh",
    "fused_neutral": "Fused, Neutral-subtracted mesh",
    "fused_neutral_ref": "Fused, 1 Neutral reference",
}
ORDER = list(LABELS)
# Korean names used in RESULTS.md and in contrast names. Figures and the "label" CSV column stay English.
KO = {
    "image_flip": "이미지 단독",
    "image_noflip": "이미지 단독, 반전 없음",
    "mesh_raw": "메시 단독",
    "mesh_naiveflip": "메시 단독, 단순 반전",
    "mesh_noflip": "메시 단독, 반전 없음",
    "mesh_shuffled": "메시 단독, 셔플 메시",
    "mesh_neutral": "메시 단독, Neutral 차감",
    "mesh_neutral_ref": "메시 단독, Neutral 기준 1개",
    "scalars": "이미지 + [A, G] 스칼라",
    "fused_perm": "융합 (이미지 + 메시)",
    "fused_naiveflip": "융합, 단순 반전",
    "fused_noflip": "융합, 반전 없음",
    "fused_shuffled": "융합, 셔플 메시",
    "fused_neutral": "융합, Neutral 차감 메시",
    "fused_neutral_ref": "융합, Neutral 기준 1개",
}
IMAGE_SET_KO = {"scored": "채점 대상 이미지", "non-Neutral": "비Neutral 이미지"}
MAIN = ["image_flip", "mesh_raw", "fused_perm"]
# Personalised protocol: must match REFERENCE_LIGHT in run_validation.py. The single Neutral capture
# of each subject at this lighting level is the calibration sample and is never scored.
REFERENCE_LIGHT = "middlelight"
PERSONAL = ["mesh_neutral_ref", "fused_neutral_ref"]
SAME_LIGHT = ["mesh_neutral", "fused_neutral"]
# (name, a, b, images): a - b on per-subject accuracy over the personalised scoring set.
PERSONAL_CONTRASTS = [
    ("개인화 융합 대 이미지 단독", "fused_neutral_ref", "image_flip", "scored"),
    ("개인화 메시 단독 대 이미지 단독", "mesh_neutral_ref", "image_flip", "scored"),
    ("개인화 메시 단독 대 원본 메시 단독", "mesh_neutral_ref", "mesh_raw", "scored"),
    ("개인화 융합 대 원본 융합", "fused_neutral_ref", "fused_perm", "scored"),
    ("메시 단독: 고정 기준 1개 대 같은 조명 기준", "mesh_neutral_ref", "mesh_neutral", "non-Neutral"),
    ("융합: 고정 기준 1개 대 같은 조명 기준", "fused_neutral_ref", "fused_neutral", "non-Neutral"),
]

# (name, a, b, role): difference a - b on per-subject accuracy. b=None -> a minus chance (1/7).
CONTRASTS = [
    ("융합 이득 (부차 질문)", "fused_perm", "image_flip", "secondary"),
    ("Q2 메시 단독 대 우연 수준", "mesh_raw", None, "Q2"),
    ("Q2 Neutral 차감 메시 단독 대 우연 수준", "mesh_neutral", None, "Q2"),
    ("Q2 셔플 메시 단독 대 우연 수준 (음성 대조군)", "mesh_shuffled", None, "Q2"),
    ("Q2 메시 단독에서 신원 제거 효과", "mesh_neutral", "mesh_raw", "Q2"),
    ("메시 단독 대 이미지 단독", "mesh_raw", "image_flip", "Q2"),
    ("대조: 실제 메시 융합 대 셔플 메시 융합", "fused_perm", "fused_shuffled", "control"),
    ("대조: 셔플 메시 융합 대 이미지 단독", "fused_shuffled", "image_flip", "control"),
    ("대조: 이미지 + 스칼라 대 이미지 단독", "scalars", "image_flip", "control"),
    ("대조: Neutral 차감 융합 대 이미지 단독", "fused_neutral", "image_flip", "control"),
    ("대조: Neutral 차감 융합 대 융합", "fused_neutral", "fused_perm", "control"),
    ("반전: 융합, 순열 반전 대 단순 반전", "fused_perm", "fused_naiveflip", "flip"),
    ("반전: 융합, 순열 반전 대 반전 없음", "fused_perm", "fused_noflip", "flip"),
    ("반전: 융합, 단순 반전 대 반전 없음", "fused_naiveflip", "fused_noflip", "flip"),
    ("반전: 메시 단독, 순열 반전 대 단순 반전", "mesh_raw", "mesh_naiveflip", "flip"),
    ("반전: 메시 단독, 순열 반전 대 반전 없음", "mesh_raw", "mesh_noflip", "flip"),
    ("반전: 메시 단독, 단순 반전 대 반전 없음", "mesh_naiveflip", "mesh_noflip", "flip"),
    ("반전: 이미지 단독, 반전 대 반전 없음", "image_flip", "image_noflip", "flip"),
]


# --------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------
def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    prob_cols = [c for c in rows[0] if c.startswith("prob_")] if rows else []
    for row in rows:
        row["seed"] = int(row["seed"])
        row["correct"] = int(row["correct"])
        row["probs"] = [float(row[c]) for c in prob_cols]
        row["confidence"] = max(row["probs"])
    return rows


def group(rows: list[dict], *keys: str) -> dict[tuple, list[dict]]:
    out: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        out[tuple(row[k] for k in keys)].append(row)
    return out


# --------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------
def accuracy(rows: list[dict]) -> float:
    return float(np.mean([r["correct"] for r in rows])) if rows else float("nan")


def macro_f1(rows: list[dict], classes: list[str]) -> float:
    scores = []
    for c in classes:
        tp = sum(r["label"] == c and r["prediction"] == c for r in rows)
        fp = sum(r["label"] != c and r["prediction"] == c for r in rows)
        fn = sum(r["label"] == c and r["prediction"] != c for r in rows)
        scores.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
    return float(np.mean(scores))


def ece(rows: list[dict], bins: int = 10) -> tuple[float, list[dict]]:
    conf = np.asarray([r["confidence"] for r in rows])
    corr = np.asarray([r["correct"] for r in rows], dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total, table = 0.0, []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (conf > lo) & (conf <= hi)
        if mask.any():
            gap = abs(corr[mask].mean() - conf[mask].mean())
            total += mask.mean() * gap
            table.append({"bin_low": round(lo, 2), "bin_high": round(hi, 2), "n": int(mask.sum()),
                          "mean_confidence": float(conf[mask].mean()), "accuracy": float(corr[mask].mean())})
    return float(total), table


def per_seed(rows: list[dict], fn) -> np.ndarray:
    by_seed = group(rows, "seed")
    return np.asarray([fn(by_seed[k]) for k in sorted(by_seed)])


def subject_accuracy(rows: list[dict], subjects: list[str]) -> np.ndarray:
    """(seeds, subjects) matrix of per-subject accuracy."""
    by = group(rows, "seed", "subject_id")
    seeds = sorted({r["seed"] for r in rows})
    return np.asarray([[accuracy(by.get((seed, s), [])) for s in subjects] for seed in seeds])


def is_reference(row: dict) -> bool:
    return row["label"] == "Neutral" and row["light"] == REFERENCE_LIGHT


def confusion_matrix(rows: list[dict], classes: list[str]) -> np.ndarray:
    m = np.zeros((len(classes), len(classes)), dtype=int)
    for r in rows:
        m[classes.index(r["label"]), classes.index(r["prediction"])] += 1
    return m


def triplet_structure(path: Path) -> dict | None:
    """How often the subject of a held-out capture triplet appears in training, and with which labels."""
    if not path.exists():
        return None
    folds: dict[tuple, dict[str, set]] = defaultdict(lambda: {"train": set(), "test": set()})
    with path.open("r", encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            if r["protocol"] == "triplet":
                folds[(r["seed"], r["fold"])][r["partition"]].add((r["sample_id"], r["subject_id"], r["label"]))
    same_label, same_subject = [], []
    for parts in folds.values():
        for subject, label in {(s, l) for _, s, l in parts["test"]}:
            same_label.append(sum(s == subject and l == label for _, s, l in parts["train"]))
            same_subject.append(sum(s == subject for _, s, l in parts["train"]))
    if not same_subject:
        return None
    return {"folds": len(folds), "held_out_captures": len(same_subject),
            "train_images_same_subject_same_label_max": int(max(same_label)),
            "train_images_same_subject_min": int(min(same_subject)),
            "train_images_same_subject_max": int(max(same_subject))}


def triplet_stats(rows: list[dict]) -> tuple[float, float]:
    """Fraction of capture triplets whose 3 lighting variants get the same prediction / are all correct."""
    by = group(rows, "seed", "triplet_id")
    same = [len({r["prediction"] for r in g}) == 1 for g in by.values() if len(g) == 3]
    allc = [all(r["correct"] for r in g) for g in by.values() if len(g) == 3]
    return float(np.mean(same)), float(np.mean(allc))


# --------------------------------------------------------------------------------------
# Subject-level inference
# --------------------------------------------------------------------------------------
def paired_stats(diff: np.ndarray, rng: np.random.Generator) -> dict:
    """Statistics for n subject-level (paired) differences."""
    d = np.asarray(diff, dtype=float)
    n = len(d)
    mean, sd = float(d.mean()), float(d.std(ddof=1))
    boot = d[rng.integers(0, n, size=(N_BOOT, n))].mean(axis=1)
    t_half = float(stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n))
    # Exact sign-flip permutation test on the mean (all 2^n sign assignments).
    signs = np.asarray(list(itertools.product([-1.0, 1.0], repeat=n)))
    null = np.abs((signs * d).mean(axis=1))
    p_perm = float((null >= abs(mean) - 1e-12).mean())
    if np.allclose(d, 0):
        p_wilcoxon = 1.0
    else:
        p_wilcoxon = float(stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided").pvalue)
    return {
        "n_subjects": n,
        "mean_diff": mean,
        "sd_diff": sd,
        "cohen_dz": float(mean / sd) if sd > 0 else float("nan"),
        "boot_ci_low": float(np.quantile(boot, 0.025)),
        "boot_ci_high": float(np.quantile(boot, 0.975)),
        "t_ci_low": mean - t_half,
        "t_ci_high": mean + t_half,
        "signflip_p": p_perm,
        "wilcoxon_p": p_wilcoxon,
        "wins": int((d > 1e-12).sum()),
        "losses": int((d < -1e-12).sum()),
        "ties": int((np.abs(d) <= 1e-12).sum()),
    }


def holm(pvalues: list[float]) -> list[float]:
    order = np.argsort(pvalues)
    adjusted = np.empty(len(pvalues))
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (len(pvalues) - rank) * pvalues[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted.tolist()


# --------------------------------------------------------------------------------------
# Output helpers
# --------------------------------------------------------------------------------------
def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields: list[str] = []
    for row in rows:
        fields.extend(k for k in row if k not in fields)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def pm(mean: float, sd: float, digits: int = 1) -> str:
    return f"{100 * mean:.{digits}f} ± {100 * sd:.{digits}f}"


def pct(x: float, digits: int = 1, signed: bool = False) -> str:
    return f"{100 * x:+.{digits}f}" if signed else f"{100 * x:.{digits}f}"


def style_axes(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig, path: Path) -> None:
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    fig.savefig(path, dpi=170, facecolor=SURFACE)
    plt.close(fig)


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-dir", type=Path, default=Path("results/cvpr2027"))
    args = parser.parse_args()
    root = args.results_dir if args.results_dir.is_absolute() else REPO_ROOT / args.results_dir
    out = root / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RNG_SEED)

    loso = load(root / "predictions_loso.csv")
    if not loso:
        raise SystemExit("predictions_loso.csv not found; run run_validation.py first.")
    subjects = sorted({r["subject_id"] for r in loso})
    classes = sorted({r["label"] for r in loso})
    lights = sorted({r["light"] for r in loso})
    seeds = sorted({r["seed"] for r in loso})
    by_condition = group(loso, "condition")
    conditions = [c for c in ORDER if (c,) in by_condition]
    report: dict = {"subjects": subjects, "classes": classes, "seeds": seeds, "chance": CHANCE,
                    "bootstrap_replicates": N_BOOT, "min_attainable_signflip_p_n10": 2 / 2 ** len(subjects)}
    md: list[str] = []

    # ---------------- LOSO summary ----------------
    subj_acc: dict[str, np.ndarray] = {}
    summary_rows, subject_rows, epochs_rows = [], [], []
    for c in conditions:
        rows = by_condition[(c,)]
        matrix = subject_accuracy(rows, subjects)  # (seeds, subjects)
        subj_acc[c] = matrix.mean(axis=0)
        acc_seed = per_seed(rows, accuracy)
        f1_seed = per_seed(rows, lambda r: macro_f1(r, classes))
        ece_seed = per_seed(rows, lambda r: ece(r)[0])
        conf_seed = per_seed(rows, lambda r: float(np.mean([x["confidence"] for x in r])))
        non_neutral = per_seed([r for r in rows if r["label"] != "Neutral"], accuracy)
        same, allc = triplet_stats(rows)
        boot = subj_acc[c][rng.integers(0, len(subjects), size=(N_BOOT, len(subjects)))].mean(axis=1)
        epochs = sorted({int(r["epochs"]) for r in rows})
        summary_rows.append({
            "condition": c, "label": LABELS[c], "n_seeds": len(acc_seed),
            "accuracy_mean_over_seeds": acc_seed.mean(), "accuracy_sd_over_seeds": acc_seed.std(ddof=1),
            "macro_f1_mean": f1_seed.mean(), "macro_f1_sd": f1_seed.std(ddof=1),
            "subject_mean_accuracy": subj_acc[c].mean(), "subject_sd": subj_acc[c].std(ddof=1),
            "subject_boot_ci_low": float(np.quantile(boot, 0.025)), "subject_boot_ci_high": float(np.quantile(boot, 0.975)),
            "worst_subject": subj_acc[c].min(), "best_subject": subj_acc[c].max(),
            "accuracy_without_neutral_class_mean": non_neutral.mean(), "accuracy_without_neutral_class_sd": non_neutral.std(ddof=1),
            "ece_mean": ece_seed.mean(), "ece_sd": ece_seed.std(ddof=1), "mean_confidence": conf_seed.mean(),
            "triplet_same_prediction_rate": same, "triplet_all_correct_rate": allc,
            "epochs_used": "/".join(map(str, epochs)),
        })
        for seed, row in zip(seeds, matrix):
            for s, v in zip(subjects, row):
                subject_rows.append({"condition": c, "seed": seed, "subject_id": s, "accuracy": v})
    write_csv(out / "loso_summary.csv", summary_rows)
    write_csv(out / "per_subject_accuracy_by_seed.csv", subject_rows)
    write_csv(out / "per_subject_accuracy.csv",
              [{"subject_id": s, **{c: subj_acc[c][i] for c in conditions}} for i, s in enumerate(subjects)])
    report["loso_summary"] = summary_rows

    md += ["# 결과 (analyze_results.py가 생성한 파일입니다. 직접 수정하지 마세요)", "",
           f"데이터: AI-Hub 안면 랜드마크 **샘플만** 사용했습니다. 피험자 {len(subjects)}명, 표정 {len(classes)}종, "
           f"조명 {len(lights)}단계, 이미지 {len(subjects) * len(classes) * len(lights)}장입니다. "
           f"시드: {seeds}. 우연 수준 = {pct(CHANCE)}%.", "",
           "모든 구간과 검정의 단위는 **피험자**입니다(n = 10). 피험자가 10명이라 구간은 모두 넓고 검정력은 모두 낮습니다. "
           f"정확 부호 반전 검정이 낼 수 있는 가장 작은 양측 p값은 {2 / 2 ** len(subjects):.4f}입니다. "
           "군집이 10개인 부트스트랩 구간은 실제보다 좁게 나오는 것으로 알려져 있어 t 구간을 함께 제시합니다.", "",
           "대비 표의 괄호 안 영문(`fused_perm − image_flip` 등)은 코드의 조건 이름입니다. 표정 이름(Anger, Neutral 등), "
           "조명 이름(highlight, lowlight, middlelight), 프로토콜 이름(`random`, `triplet`, `loso`, `lightout`, "
           "`lightmatch`)은 데이터와 코드의 표기를 그대로 씁니다.", "",
           "## 1. 피험자 단위 교차검증 LOSO (10 fold, 고정 epoch, 마지막 epoch 가중치)", "",
           "| 모델 | 정확도 % (시드 평균 ± SD) | Macro-F1 % | 피험자 평균 정확도 % [95% 부트스트랩 CI] | 최저 / 최고 피험자 % | Neutral 클래스 제외 정확도 % | ECE % | 캡처 3장 예측 일치율 % | Epoch |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in summary_rows:
        md.append(
            f"| {KO[r['condition']]} | {pm(r['accuracy_mean_over_seeds'], r['accuracy_sd_over_seeds'])} | "
            f"{pm(r['macro_f1_mean'], r['macro_f1_sd'])} | {pct(r['subject_mean_accuracy'])} "
            f"[{pct(r['subject_boot_ci_low'])}, {pct(r['subject_boot_ci_high'])}] | "
            f"{pct(r['worst_subject'])} / {pct(r['best_subject'])} | "
            f"{pm(r['accuracy_without_neutral_class_mean'], r['accuracy_without_neutral_class_sd'])} | "
            f"{pm(r['ece_mean'], r['ece_sd'])} | {pct(r['triplet_same_prediction_rate'])} | {r['epochs_used']} |")
    md += ["", "시드 간 SD는 학습의 무작위성만 반영합니다(LOSO 분할은 결정적입니다). 새 피험자에 대한 불확실성은 "
           "반영하지 않습니다. ECE는 시드마다 fold 밖 예측 210개를 모아(서로 다른 fold 모델 10개, 구간 10개) 계산한 "
           "거친 추정치입니다. 캡처 3장 예측 일치율은 한 캡처의 세 조명 이미지가 같은 예측을 받은 비율입니다.", "",
           "`Neutral 기준 1개` 두 행은 여기서 210장 전체로 채점했고, 각 피험자의 기준 캡처(입력이 전부 0)도 "
           "**포함**되어 있습니다. 공정한 평가는 7절에 있습니다.", ""]

    # ---------------- contrasts ----------------
    contrast_rows = []
    for name, a, b, role in CONTRASTS:
        if a not in subj_acc or (b is not None and b not in subj_acc):
            continue
        diff = subj_acc[a] - (subj_acc[b] if b else CHANCE)
        seed_a = per_seed(by_condition[(a,)], accuracy)
        seed_b = per_seed(by_condition[(b,)], accuracy) if b else np.full(len(seed_a), CHANCE)
        seed_diff = seed_a - seed_b
        contrast_rows.append({"contrast": name, "role": role, "a": a, "b": b or "chance",
                              **paired_stats(diff, rng),
                              "per_seed_diff_mean": float(seed_diff.mean()),
                              "per_seed_diff_sd": float(seed_diff.std(ddof=1)),
                              "per_seed_diff_min": float(seed_diff.min()),
                              "per_seed_diff_max": float(seed_diff.max())})
    for row, adj in zip(contrast_rows, holm([r["signflip_p"] for r in contrast_rows])):
        row["signflip_p_holm"] = adj
    write_csv(out / "contrasts.csv", contrast_rows)
    report["contrasts"] = contrast_rows

    def contrast_table(rows: list[dict]) -> list[str]:
        lines = ["| 대비 (a − b) | 평균 차이, pp | 95% 부트스트랩 CI | 95% t CI | Cohen d_z | 피험자 승 / 패 / 무 | 부호 반전 p | Holm p | Wilcoxon p | 시드 수준 차이, pp (평균 ± SD) |",
                 "|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(
                f"| {r['contrast']} ({r['a']} − {r['b']}) | {pct(r['mean_diff'], 1, True)} | "
                f"[{pct(r['boot_ci_low'], 1, True)}, {pct(r['boot_ci_high'], 1, True)}] | "
                f"[{pct(r['t_ci_low'], 1, True)}, {pct(r['t_ci_high'], 1, True)}] | {r['cohen_dz']:.2f} | "
                f"{r['wins']} / {r['losses']} / {r['ties']} | {r['signflip_p']:.4f} | "
                f"{r.get('signflip_p_holm', float('nan')):.4f} | {r['wilcoxon_p']:.4f} | "
                + (f"{pct(r['per_seed_diff_mean'], 1, True)} ± {pct(r['per_seed_diff_sd'])} |"
                   if np.isfinite(r["per_seed_diff_sd"]) else "해당 없음 |"))
        return lines

    md += ["## 2. 피험자 단위 대응 대비 (LOSO)", "",
           "피험자별 정확도를 시드에 대해 평균한 뒤 차이를 구했습니다(n = 10쌍). 10쌍에 대한 Wilcoxon 부호 순위 검정은 "
           "검정력이 낮으며, 유의하지 않다는 결과는 효과가 없다는 증거가 **아닙니다**. "
           f"대비 {len(contrast_rows)}개를 보고하며, Holm 보정한 부호 반전 p값은 Holm 열에 있습니다.", ""]
    md += contrast_table(contrast_rows) + [""]

    # ---------------- confusion matrices ----------------
    confusion: dict[str, np.ndarray] = {}
    anger_sad_rows = []
    for c in conditions:
        m = confusion_matrix(by_condition[(c,)], classes)
        confusion[c] = m
        write_csv(out / f"confusion_{c}.csv",
                  [{"true": classes[i], **{classes[j]: int(m[i, j]) for j in range(len(classes))}} for i in range(len(classes))])
        if "Anger" in classes and "Sadness" in classes:
            a, s = classes.index("Anger"), classes.index("Sadness")
            errors = int(m.sum() - np.trace(m))
            anger_sad_rows.append({
                "condition": c, "label": LABELS[c], "n_seeds": len(seeds),
                "anger_to_sadness_total": int(m[a, s]), "sadness_to_anger_total": int(m[s, a]),
                "all_errors_total": errors,
                "share_of_all_errors": float((m[a, s] + m[s, a]) / errors) if errors else float("nan"),
                "anger_recall": float(m[a, a] / m[a].sum()), "sadness_recall": float(m[s, s] / m[s].sum())})
    write_csv(out / "anger_sadness_confusion.csv", anger_sad_rows)
    report["anger_sadness"] = anger_sad_rows
    recall_rows = [{"condition": c, **{cls: float(confusion[c][i, i] / confusion[c][i].sum()) for i, cls in enumerate(classes)}}
                   for c in conditions]
    write_csv(out / "per_class_recall.csv", recall_rows)
    md += ["## 3. 혼동 (모든 시드를 합한 건수, 행 = 실제 클래스)", "",
           "| 모델 | Anger→Sadness | Sadness→Anger | 전체 오류 중 비율 % | Anger 재현율 % | Sadness 재현율 % |",
           "|---|---|---|---|---|---|"]
    for r in anger_sad_rows:
        md.append(f"| {KO[r['condition']]} | {r['anger_to_sadness_total']} | {r['sadness_to_anger_total']} | "
                  f"{pct(r['share_of_all_errors'])} | {pct(r['anger_recall'])} | {pct(r['sadness_recall'])} |")
    md += ["", "클래스별 재현율(%), 모든 시드 합산:", "",
           "| 모델 | " + " | ".join(classes) + " |", "|---|" + "---|" * len(classes)]
    for r in recall_rows:
        md.append(f"| {KO[r['condition']]} | " + " | ".join(pct(r[c]) for c in classes) + " |")
    md.append("")

    # ---------------- calibration ----------------
    calibration_rows = []
    for c in conditions:
        _, table = ece(by_condition[(c,)])
        calibration_rows += [{"condition": c, **row} for row in table]
    write_csv(out / "calibration_bins.csv", calibration_rows)

    # ---------------- Q1: split comparison ----------------
    q1_rows, q1_contrasts = [], []
    split_rows = {"random": load(root / "predictions_random.csv"), "triplet": load(root / "predictions_triplet.csv")}
    if all(split_rows.values()):
        split_conditions = [c for c in MAIN if any(r["condition"] == c for r in split_rows["random"])]
        subj_split: dict[tuple[str, str], np.ndarray] = {}
        seed_split: dict[tuple[str, str], np.ndarray] = {}
        for c in split_conditions:
            for protocol in ("random", "triplet", "loso"):
                rows = [r for r in (loso if protocol == "loso" else split_rows[protocol]) if r["condition"] == c]
                acc_seed = per_seed(rows, accuracy)
                subj_split[(protocol, c)] = subject_accuracy(rows, subjects).mean(axis=0)
                seed_split[(protocol, c)] = acc_seed
                q1_rows.append({"condition": c, "label": LABELS[c], "protocol": protocol, "n_seeds": len(acc_seed),
                                "accuracy_mean_over_seeds": acc_seed.mean(), "accuracy_sd_over_seeds": acc_seed.std(ddof=1),
                                "subject_mean_accuracy": subj_split[(protocol, c)].mean(),
                                "epochs_used": "/".join(map(str, sorted({int(r["epochs"]) for r in rows})))})
            for pa, pb in (("random", "loso"), ("triplet", "loso"), ("random", "triplet")):
                seed_diff = seed_split[(pa, c)] - seed_split[(pb, c)]
                q1_contrasts.append({"contrast": f"{LABELS[c]}: {pa} − {pb}", "role": "Q1", "a": pa, "b": pb,
                                     **paired_stats(subj_split[(pa, c)] - subj_split[(pb, c)], rng),
                                     "per_seed_diff_mean": float(seed_diff.mean()),
                                     "per_seed_diff_sd": float(seed_diff.std(ddof=1)), "condition": c})
        for row, adj in zip(q1_contrasts, holm([r["signflip_p"] for r in q1_contrasts])):
            row["signflip_p_holm"] = adj
        write_csv(out / "q1_split_comparison.csv", q1_rows)
        write_csv(out / "q1_split_contrasts.csv", q1_contrasts)
        report["q1"] = {"table": q1_rows, "contrasts": q1_contrasts}
        md += ["## 4. Q1: 이미지 단위 무작위 분할과 피험자 분리 평가의 비교", "",
               "`random`: 이미지 단위 층화 10-fold입니다(같은 사람이 학습 세트에 있고, 대개 같은 캡처의 다른 두 조명 "
               "이미지도 있습니다). `triplet`: 한 캡처의 세 조명 이미지를 한 묶음으로 둔 10-fold입니다(같은 사람은 "
               "여전히 학습에 있습니다). `loso`: 피험자 분리입니다. 세 프로토콜 모두 fold마다 189장으로 학습하고 "
               "21장으로 평가합니다.", "",
               "| 모델 | 프로토콜 | 정확도 % (시드 평균 ± SD) | Epoch |", "|---|---|---|---|"]
        for r in q1_rows:
            md.append(f"| {KO[r['condition']]} | {r['protocol']} | {pm(r['accuracy_mean_over_seeds'], r['accuracy_sd_over_seeds'])} | {r['epochs_used']} |")
        md += ["", "피험자 단위 대응 비교(모든 프로토콜에서 각 피험자의 이미지는 fold 밖 모델로 채점됩니다):", ""]
        md += contrast_table(q1_contrasts) + [""]
        structure = triplet_structure(root / "split_manifest.csv")
        if structure:
            report["q1"]["triplet_structure"] = structure
            md += ["**`triplet`이 `random`과 `loso` 사이가 아니라 `loso`보다 낮은 이유.** "
                   f"`split_manifest.csv`에서 fold {structure['folds']}개의 보류 캡처 "
                   f"{structure['held_out_captures']}개를 확인했습니다. 보류 캡처의 피험자는 학습 세트에 항상 "
                   f"{structure['train_images_same_subject_min']}~{structure['train_images_same_subject_max']}장 "
                   "들어 있고, 그중 보류된 표정을 가진 이미지는 "
                   f"{'한 장도 없습니다' if structure['train_images_same_subject_same_label_max'] == 0 else '일부 있습니다'}. "
                   "따라서 학습에서 그 사람의 신원은 *틀린* 라벨과만 짝지어집니다. 신원에 의존하는 모델은 정답 클래스에서 "
                   "멀어지게 됩니다. `loso`에서는 신원을 본 적이 없어 이런 일이 생기지 않고, `random`에서는 같은 사람의 "
                   "같은 표정이 학습에 있어 반대로 작용합니다. 즉 `triplet`은 약한 누수가 아니라 신원에 대해 적대적인 "
                   "분할입니다. 하락은 이미지 모델에서 가장 크고 메시 단독 모델에서는 나타나지 않습니다. 이는 분할 "
                   "구조와 일치하는 설명이며, 따로 검증한 기전은 아닙니다.", ""]

    # ---------------- Q3: leave-one-light-out ----------------
    lightout = load(root / "predictions_lightout.csv")
    lightmatch = load(root / "predictions_lightmatch.csv")
    q3_rows, q3_contrasts = [], []
    if lightout:
        for c in [c for c in MAIN if any(r["condition"] == c for r in lightout)]:
            rows_c = [r for r in lightout if r["condition"] == c]
            rows_m = [r for r in lightmatch if r["condition"] == c]
            base_c = by_condition[(c,)]
            subj_parts: dict[str, list] = defaultdict(list)
            seed_parts: dict[str, list] = defaultdict(list)
            for light in lights:
                parts = {"unseen": [r for r in rows_c if r["held_out_light"] == light and r["light"] == light],
                         "seen": [r for r in rows_c if r["held_out_light"] == light and r["light"] != light],
                         "base": [r for r in base_c if r["light"] == light]}
                if rows_m:
                    parts["matched"] = [r for r in rows_m if r["light"] == light]
                subj = {k: subject_accuracy(v, subjects).mean(axis=0) for k, v in parts.items()}
                seed = {k: per_seed(v, accuracy) for k, v in parts.items()}
                for k in parts:
                    subj_parts[k].append(subj[k]); seed_parts[k].append(seed[k])
                row = {"condition": c, "label": LABELS[c], "held_out_light": light,
                       "acc_unseen_light_mean": seed["unseen"].mean(), "acc_unseen_light_sd": seed["unseen"].std(ddof=1),
                       "acc_same_light_when_trained_on_all_lights_mean": seed["base"].mean(),
                       "acc_same_light_when_trained_on_all_lights_sd": seed["base"].std(ddof=1),
                       "acc_on_the_two_seen_lights_mean": seed["seen"].mean(),
                       "acc_on_the_two_seen_lights_sd": seed["seen"].std(ddof=1)}
                references = [("base", "같은 조명, 전체 조명으로 학습")]
                if rows_m:
                    row["acc_same_light_size_matched_mean"] = seed["matched"].mean()
                    row["acc_same_light_size_matched_sd"] = seed["matched"].std(ddof=1)
                    references.append(("matched", "같은 조명, 학습량을 맞춘 학습"))
                q3_rows.append(row)
                for key, text in references:
                    q3_contrasts.append({"contrast": f"{KO[c]}: 미관측 {light} − {text}",
                                         "role": "Q3", "a": "lightout", "b": "loso" if key == "base" else "lightmatch",
                                         **paired_stats(subj["unseen"] - subj[key], rng),
                                         "per_seed_diff_mean": float((seed["unseen"] - seed[key]).mean()),
                                         "per_seed_diff_sd": float((seed["unseen"] - seed[key]).std(ddof=1)), "condition": c})
            subj_mean = {k: np.mean(v, axis=0) for k, v in subj_parts.items()}
            seed_mean = {k: np.mean(v, axis=0) for k, v in seed_parts.items()}
            pairs = [("base", "같은 조명, 전체 조명으로 학습 (189장)"),
                     ("matched", "같은 조명, 학습량을 맞춘 학습 (126장, 전체 조명)"),
                     ("seen", "본 조명, 같은 모델")]
            for key, text in pairs:
                if key not in subj_mean:
                    continue
                q3_contrasts.append({"contrast": f"{KO[c]}: 미관측 조명 − {text} (3개 조명 평균)",
                                     "role": "Q3", "a": "lightout", "b": {"base": "loso", "matched": "lightmatch"}.get(key, "lightout"),
                                     **paired_stats(subj_mean["unseen"] - subj_mean[key], rng),
                                     "per_seed_diff_mean": float((seed_mean["unseen"] - seed_mean[key]).mean()),
                                     "per_seed_diff_sd": float((seed_mean["unseen"] - seed_mean[key]).std(ddof=1)),
                                     "condition": c})
            if "matched" in subj_mean:
                q3_contrasts.append({"contrast": f"{KO[c]}: 학습량 맞춤 (126장) − 전체 조명 (189장), 같은 테스트 이미지",
                                     "role": "Q3", "a": "lightmatch", "b": "loso",
                                     **paired_stats(subj_mean["matched"] - subj_mean["base"], rng),
                                     "per_seed_diff_mean": float((seed_mean["matched"] - seed_mean["base"]).mean()),
                                     "per_seed_diff_sd": float((seed_mean["matched"] - seed_mean["base"]).std(ddof=1)),
                                     "condition": c})
        for row, adj in zip(q3_contrasts, holm([r["signflip_p"] for r in q3_contrasts])):
            row["signflip_p_holm"] = adj
        write_csv(out / "q3_lightout.csv", q3_rows)
        write_csv(out / "q3_lightout_contrasts.csv", q3_contrasts)
        report["q3"] = {"table": q3_rows, "contrasts": q3_contrasts}
        has_match = bool(lightmatch)
        md += ["## 5. Q3: 조명 하나를 뺀 학습 (LOSO 안에서)", "",
               "각 모델은 피험자 9명 × 조명 2단계(126장)로 학습하고 보류한 피험자로 평가합니다. `미관측 조명` = 학습에서 "
               "한 번도 보지 못한 조명 단계의 그 피험자 이미지에 대한 정확도입니다. 기준 1 = 세 조명 모두로 학습한 LOSO "
               "모델(189장)을 같은 이미지로 채점한 값입니다. 이 모델은 조명 범위**뿐 아니라** 학습 세트 크기도 다릅니다. "
               "기준 2 = 같은 조명 제외 모델을 학습에서 본 두 조명으로 채점한 값입니다."
               + (" 기준 3(학습량 맞춤) = 같은 피험자 9명, 같은 이미지 수(126장)로 학습하되 캡처마다 조명 하나씩을 빼서 "
                  "세 조명이 모두 들어가게 한 모델(조명당 42장)을 같은 이미지로 채점한 값입니다. 미관측 − 기준 3이 "
                  "그 조명을 본 적이 없다는 것만의 효과를 분리합니다." if has_match else ""), "",
               "| 모델 | 제외한 조명 | 미관측 조명 정확도 % | 같은 조명, 전체 조명으로 학습 (189장) % | "
               + ("같은 조명, 학습량 맞춤 (126장) % | " if has_match else "") + "본 조명, 같은 모델 % |",
               "|---|---|---|---|---|" + ("---|" if has_match else "")]
        for r in q3_rows:
            md.append(f"| {KO[r['condition']]} | {r['held_out_light']} | {pm(r['acc_unseen_light_mean'], r['acc_unseen_light_sd'])} | "
                      f"{pm(r['acc_same_light_when_trained_on_all_lights_mean'], r['acc_same_light_when_trained_on_all_lights_sd'])} | "
                      + (f"{pm(r['acc_same_light_size_matched_mean'], r['acc_same_light_size_matched_sd'])} | " if has_match else "")
                      + f"{pm(r['acc_on_the_two_seen_lights_mean'], r['acc_on_the_two_seen_lights_sd'])} |")
        md += ["", "시드 평균 ± SD입니다. 피험자 단위 대응 비교:", ""] + contrast_table(q3_contrasts) + [""]

    # LOSO accuracy per lighting level (all lights seen in training)
    light_rows = []
    for c in conditions:
        for light in lights:
            a = per_seed([r for r in by_condition[(c,)] if r["light"] == light], accuracy)
            light_rows.append({"condition": c, "light": light, "accuracy_mean": a.mean(), "accuracy_sd": a.std(ddof=1)})
    write_csv(out / "loso_accuracy_by_light.csv", light_rows)

    # ---------------- epoch selection summary ----------------
    selection_path = root / "epoch_selection.csv"
    if selection_path.exists():
        with selection_path.open("r", encoding="utf-8") as handle:
            sel = list(csv.DictReader(handle))
        md += ["## 6. Epoch 선택 (바깥 fold마다 학습 피험자 9명에 대한 내부 3-fold CV)", "",
               "| 모델 | 바깥 fold별 선택된 epoch (01…10) |", "|---|---|"]
        for c in sorted({r["condition"] for r in sel}, key=ORDER.index):
            md.append(f"| {KO[c]} | " + ", ".join(r["selected_epochs"] for r in sel if r["condition"] == c) + " |")
        md.append("")

    # ---------------- personalised protocol ----------------
    personal_present = [c for c in PERSONAL if c in subj_acc]
    scored: dict[str, list[dict]] = {c: [r for r in by_condition[(c,)] if not is_reference(r)] for c in conditions}
    personal_rows, personal_contrasts = [], []
    if personal_present:
        table_conditions = [c for c in MAIN + SAME_LIGHT + PERSONAL if c in subj_acc]
        subj_scored = {c: subject_accuracy(scored[c], subjects).mean(axis=0) for c in conditions}
        subj_non_neutral = {c: subject_accuracy([r for r in scored[c] if r["label"] != "Neutral"], subjects).mean(axis=0)
                            for c in conditions}
        for c in table_conditions:
            rows = scored[c]
            acc_seed = per_seed(rows, accuracy)
            nn_seed = per_seed([r for r in rows if r["label"] != "Neutral"], accuracy)
            ref_seed = per_seed([r for r in rows if r["light"] == REFERENCE_LIGHT], accuracy)
            other_seed = per_seed([r for r in rows if r["light"] != REFERENCE_LIGHT], accuracy)
            boot = subj_scored[c][rng.integers(0, len(subjects), size=(N_BOOT, len(subjects)))].mean(axis=1)
            personal_rows.append({
                "condition": c, "label": LABELS[c],
                "reference": {True: "Neutral 캡처 1장 (" + REFERENCE_LIGHT + ")", False: "없음"}[c in PERSONAL]
                if c not in SAME_LIGHT else "Neutral 캡처 3장 (조명마다 1장)",
                "n_scored_images": len(rows) // len(seeds),
                "accuracy_mean_over_seeds": acc_seed.mean(), "accuracy_sd_over_seeds": acc_seed.std(ddof=1),
                "subject_mean_accuracy": subj_scored[c].mean(),
                "subject_boot_ci_low": float(np.quantile(boot, 0.025)), "subject_boot_ci_high": float(np.quantile(boot, 0.975)),
                "worst_subject": subj_scored[c].min(), "best_subject": subj_scored[c].max(),
                "accuracy_non_neutral_mean": nn_seed.mean(), "accuracy_non_neutral_sd": nn_seed.std(ddof=1),
                "accuracy_reference_light_mean": ref_seed.mean(), "accuracy_reference_light_sd": ref_seed.std(ddof=1),
                "accuracy_other_lights_mean": other_seed.mean(), "accuracy_other_lights_sd": other_seed.std(ddof=1)})
        for name, a, b, images in PERSONAL_CONTRASTS:
            if a not in subj_acc or b not in subj_acc:
                continue
            source = subj_scored if images == "scored" else subj_non_neutral
            pick = (lambda r: True) if images == "scored" else (lambda r: r["label"] != "Neutral")
            seed_diff = (per_seed([r for r in scored[a] if pick(r)], accuracy)
                         - per_seed([r for r in scored[b] if pick(r)], accuracy))
            personal_contrasts.append({"contrast": f"{name} [{IMAGE_SET_KO[images]}]", "role": "personalised", "a": a, "b": b,
                                       **paired_stats(source[a] - source[b], rng),
                                       "per_seed_diff_mean": float(seed_diff.mean()),
                                       "per_seed_diff_sd": float(seed_diff.std(ddof=1))})
        for row, adj in zip(personal_contrasts, holm([r["signflip_p"] for r in personal_contrasts])):
            row["signflip_p_holm"] = adj
        write_csv(out / "personalised.csv", personal_rows)
        write_csv(out / "personalised_contrasts.csv", personal_contrasts)
        report["personalised"] = {"reference_light": REFERENCE_LIGHT, "table": personal_rows, "contrasts": personal_contrasts}
        n_scored = personal_rows[0]["n_scored_images"]
        md += ["## 7. 개인화 프로토콜: 테스트 피험자마다 Neutral 기준 1개", "",
               "1~6절과는 다른 사용 상황입니다. 시스템은 새 사람의 **라벨이 붙은 Neutral 캡처 1장**"
               f"(`{REFERENCE_LIGHT}` 조명, 이 실험을 돌리기 전에 정함)을 받아, 그 메시를 그 사람의 다른 모든 메시에서 "
               "세 조명 모두에 대해 뺍니다. 그 캡처는 보정용 샘플이며 **채점하지 않습니다**. 아래 모든 모델은 같은 "
               f"{n_scored}장(피험자당 {n_scored // len(subjects)}장)으로 평가했습니다. 기준이 없는 모델은 1절과 같은 "
               "LOSO 실행을 이 이미지 집합으로 다시 채점한 것입니다. 1절의 Neutral 차감 행은 *같은* 조명의 Neutral "
               "캡처를 기준으로 쓰므로(피험자당 기준 3개), 이 채점 집합에 남은 Neutral 이미지 2장은 자기 자신이 기준인 "
               "0 벡터입니다. 그 모델들에는 `비Neutral 이미지` 열만 공정합니다. 기준 1개 모델의 epoch 수는 대응하는 "
               "같은 조명 기준 모델에 대해 내부 CV가 고른 값을 그대로 썼습니다.", "",
               "| 모델 | 테스트 때 주어지는 기준 | 정확도 % (시드 평균 ± SD) | 피험자 평균 정확도 % [95% 부트스트랩 CI] | "
               "최저 / 최고 피험자 % | 비Neutral 이미지 정확도 % | 기준 조명에서의 정확도 % | 나머지 두 조명에서의 정확도 % |",
               "|---|---|---|---|---|---|---|---|"]
        for r in personal_rows:
            md.append(f"| {KO[r['condition']]} | {r['reference']} | {pm(r['accuracy_mean_over_seeds'], r['accuracy_sd_over_seeds'])} | "
                      f"{pct(r['subject_mean_accuracy'])} [{pct(r['subject_boot_ci_low'])}, {pct(r['subject_boot_ci_high'])}] | "
                      f"{pct(r['worst_subject'])} / {pct(r['best_subject'])} | "
                      f"{pm(r['accuracy_non_neutral_mean'], r['accuracy_non_neutral_sd'])} | "
                      f"{pm(r['accuracy_reference_light_mean'], r['accuracy_reference_light_sd'])} | "
                      f"{pm(r['accuracy_other_lights_mean'], r['accuracy_other_lights_sd'])} |")
        md += ["", "피험자 단위 대응 비교입니다. `채점 대상 이미지` = 기준 캡처를 뺀 모든 이미지, `비Neutral 이미지` = "
               "Neutral이 아닌 여섯 표정만. Holm 보정은 이 절의 대비들에 대해 적용했습니다.", ""]
        md += contrast_table(personal_contrasts) + [""]

    # ---------------- figures ----------------
    # Models shown in the per-subject, confusion and reliability figures. When the personalised runs
    # exist, all five models are drawn on the same scoring set (reference capture excluded).
    if personal_present:
        fig_models = [c for c in MAIN + PERSONAL if c in subj_acc]
        fig_rows = {c: scored[c] for c in fig_models}
        fig_scope = f"{len(scored[fig_models[0]]) // len(seeds) // len(subjects)} images each, reference capture excluded"
    else:
        fig_models = [c for c in MAIN + SAME_LIGHT if c in subj_acc]
        fig_rows = {c: by_condition[(c,)] for c in fig_models}
        fig_scope = "21 images each"
    fig_subj = {c: subject_accuracy(fig_rows[c], subjects).mean(axis=0) for c in fig_models}
    fig_style = {c: (SERIES[k % len(SERIES)], MARKERS[k % len(MARKERS)]) for k, c in enumerate(fig_models)}
    write_csv(out / "figure_models_per_subject.csv",
              [{"subject_id": s, **{c: fig_subj[c][i] for c in fig_models}} for i, s in enumerate(subjects)])
    for c in fig_models:
        m = confusion_matrix(fig_rows[c], classes)
        write_csv(out / f"figure_confusion_{c}.csv",
                  [{"true": classes[i], **{classes[j]: int(m[i, j]) for j in range(len(classes))}} for i in range(len(classes))])
    # (a) all LOSO conditions: subject-mean accuracy with subject-bootstrap CI
    fig, ax = plt.subplots(figsize=(8.2, 0.42 * len(summary_rows) + 1.4))
    style_axes(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ys = np.arange(len(summary_rows))[::-1]
    for y, r in zip(ys, summary_rows):
        ax.plot([100 * r["subject_boot_ci_low"], 100 * r["subject_boot_ci_high"]], [y, y], color=SERIES[0], linewidth=2,
                solid_capstyle="round")
        ax.plot(100 * r["subject_mean_accuracy"], y, "o", color=SERIES[0], markersize=8, markeredgecolor=SURFACE, markeredgewidth=2)
        ax.text(101.5, y, pct(r["subject_mean_accuracy"]), va="center", fontsize=9, color=INK2)
    ax.axvline(100 * CHANCE, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(100 * CHANCE + 1, len(summary_rows) - 0.45, "chance", fontsize=8.5, color=MUTED, va="center")
    ax.set_yticks(ys, [r["label"] for r in summary_rows], color=INK)
    ax.set_xlim(0, 108)
    ax.set_xlabel("Leave-one-subject-out accuracy, % (dot: mean of 10 subjects; bar: 95% subject bootstrap CI)", color=INK2, fontsize=9)
    ax.set_title(f"Accuracy on unseen subjects, {len(seeds)} seeds, 10 subjects", loc="left", fontsize=11, color=INK)
    save(fig, out / "fig_loso_conditions.png")

    # (b) per-subject accuracy and per-subject paired difference to the image-only baseline
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(9.4, 6.8), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    x = np.arange(len(subjects))
    step = 0.15
    for k, c in enumerate(fig_models):
        color, marker = fig_style[c]
        offset = (k - (len(fig_models) - 1) / 2) * step
        style_axes(ax)
        ax.plot(x + offset, 100 * fig_subj[c], marker, color=color, markersize=7.5,
                markeredgecolor=SURFACE, markeredgewidth=1.3, linestyle="none", label=LABELS[c])
        if c != "image_flip" and "image_flip" in fig_subj:
            ax2.plot(x + offset, 100 * (fig_subj[c] - fig_subj["image_flip"]), marker, color=color, markersize=7.5,
                     markeredgecolor=SURFACE, markeredgewidth=1.3, linestyle="none")
    style_axes(ax2)
    ax2.axhline(0, color=AXIS, linewidth=1)
    ax2.set_ylabel("Difference to Image only, pp", color=INK2, fontsize=9)
    ax2.set_xticks(x, subjects)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Accuracy on that held-out subject, %", color=INK2, fontsize=9)
    ax.set_title(f"Per-subject accuracy ({fig_scope}, mean over seeds)", loc="left", fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=8.5, ncol=3, loc="lower left", labelcolor=INK2)
    save(fig, out / "fig_per_subject.png")

    # (c) confusion matrices, row-normalised
    ncols = min(3, len(fig_models))
    nrows = int(np.ceil(len(fig_models) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols, 4.5 * nrows), squeeze=False)
    for ax in axes.ravel()[len(fig_models):]:
        ax.set_visible(False)
    for ax, c in zip(axes.ravel(), fig_models):
        m = confusion_matrix(fig_rows[c], classes)
        frac = m / m.sum(axis=1, keepdims=True)
        ax.imshow(frac, cmap=SEQ, vmin=0, vmax=1)
        for i in range(len(classes)):
            for j in range(len(classes)):
                if m[i, j]:
                    ax.text(j, i, f"{100 * frac[i, j]:.0f}", ha="center", va="center", fontsize=8,
                            color="#ffffff" if frac[i, j] > 0.55 else INK)
        ax.set_xticks(range(len(classes)), classes, rotation=45, ha="right", fontsize=8, color=INK2)
        ax.set_yticks(range(len(classes)), classes, fontsize=8, color=INK2)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(LABELS[c], loc="left", fontsize=10, color=INK)
        ax.set_xlabel("Predicted", fontsize=9, color=INK2)
        ax.set_ylabel("True (row %, all seeds pooled)", fontsize=9, color=INK2)
    save(fig, out / "fig_confusion.png")

    # (d) reliability diagrams; the number above each point is the count of predictions in that bin
    fig, axes = plt.subplots(1, len(fig_models), figsize=(3.3 * len(fig_models), 3.9), squeeze=False, sharey=True)
    figure_bins = []
    for ax, c in zip(axes[0], fig_models):
        style_axes(ax)
        ece_seed = per_seed(fig_rows[c], lambda r: ece(r)[0])
        _, bins = ece(fig_rows[c])
        figure_bins += [{"condition": c, **b} for b in bins]
        ax.plot([0, 1], [0, 1], color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
        ax.plot([b["mean_confidence"] for b in bins], [b["accuracy"] for b in bins], "-" + fig_style[c][1],
                color=fig_style[c][0], linewidth=2, markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.3)
        for b in bins:
            ax.annotate(str(b["n"]), (b["mean_confidence"], b["accuracy"]), textcoords="offset points",
                        xytext=(0, 7), ha="center", fontsize=7, color=INK2)
        ax.set_title(f"{LABELS[c]}\nECE {pct(float(ece_seed.mean()))}%", loc="left", fontsize=9.5, color=INK)
        ax.set_xlabel("Confidence (n per bin above each point)", fontsize=8.5, color=INK2)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1.08)
    axes[0][0].set_ylabel("Accuracy in bin", fontsize=9, color=INK2)
    write_csv(out / "figure_calibration_bins.csv", figure_bins)
    save(fig, out / "fig_reliability.png")

    # (e) Q1 split comparison
    if q1_rows:
        fig, ax = plt.subplots(figsize=(7.2, 4.0))
        style_axes(ax)
        protocols = ["random", "triplet", "loso"]
        names = {"random": "Image-level\nrandom split", "triplet": "Capture-triplet\ngrouped split", "loso": "Leave-one-\nsubject-out"}
        cs = [c for c in MAIN if any(r["condition"] == c for r in q1_rows)]
        width = 0.24
        for k, c in enumerate(cs):
            vals = [[r for r in q1_rows if r["condition"] == c and r["protocol"] == p][0] for p in protocols]
            xs = np.arange(len(protocols)) + (k - (len(cs) - 1) / 2) * (width + 0.02)
            ax.bar(xs, [100 * v["accuracy_mean_over_seeds"] for v in vals], width=width, color=SERIES[k], label=LABELS[c])
            ax.errorbar(xs, [100 * v["accuracy_mean_over_seeds"] for v in vals],
                        yerr=[100 * v["accuracy_sd_over_seeds"] for v in vals], fmt="none", ecolor=INK2, elinewidth=1, capsize=2)
            for xv, v in zip(xs, vals):
                ax.text(xv, 100 * v["accuracy_mean_over_seeds"] + 2.5, pct(v["accuracy_mean_over_seeds"]), ha="center", fontsize=8, color=INK2)
        ax.set_xticks(np.arange(len(protocols)), [names[p] for p in protocols], color=INK)
        ax.set_ylim(0, 112)
        ax.set_ylabel("Accuracy, % (mean ± SD over seeds)", color=INK2, fontsize=9)
        ax.set_title("Same models, same training-set size, three ways to split", loc="left", fontsize=11, color=INK)
        ax.legend(frameon=False, fontsize=9, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.16), labelcolor=INK2)
        save(fig, out / "fig_q1_split.png")

    # (f) Q3 leave-one-light-out
    if q3_rows:
        cs = [c for c in MAIN if any(r["condition"] == c for r in q3_rows)]
        fig, axes = plt.subplots(1, len(cs), figsize=(3.7 * len(cs), 3.8), squeeze=False, sharey=True)
        for k, (ax, c) in enumerate(zip(axes[0], cs)):
            style_axes(ax)
            rows = [r for r in q3_rows if r["condition"] == c]
            xs = np.arange(len(rows))
            ax.errorbar(xs - 0.2, [100 * r["acc_same_light_when_trained_on_all_lights_mean"] for r in rows],
                        yerr=[100 * r["acc_same_light_when_trained_on_all_lights_sd"] for r in rows], fmt="o", color=MUTED,
                        markersize=7, elinewidth=1, capsize=2, label="Light seen, 189 training images")
            if "acc_same_light_size_matched_mean" in rows[0]:
                ax.errorbar(xs, [100 * r["acc_same_light_size_matched_mean"] for r in rows],
                            yerr=[100 * r["acc_same_light_size_matched_sd"] for r in rows], fmt="D", color=INK2,
                            markersize=6, elinewidth=1, capsize=2, label="Light seen, 126 images (size-matched)")
            ax.errorbar(xs + 0.2, [100 * r["acc_unseen_light_mean"] for r in rows],
                        yerr=[100 * r["acc_unseen_light_sd"] for r in rows], fmt=MARKERS[k], color=SERIES[k],
                        markersize=7, elinewidth=1, capsize=2, label="Light never seen, 126 images")
            ax.set_xticks(xs, [r["held_out_light"].replace("light", "") for r in rows], color=INK)
            ax.set_xlim(-0.5, len(rows) - 0.5); ax.set_ylim(0, 105)
            ax.set_title(LABELS[c], loc="left", fontsize=10, color=INK)
            ax.set_xlabel("Test lighting level", fontsize=9, color=INK2)
            ax.legend(frameon=False, fontsize=7.5, loc="lower left", labelcolor=INK2)
        axes[0][0].set_ylabel("Accuracy on held-out subject, %\n(mean ± SD over seeds)", fontsize=9, color=INK2)
        save(fig, out / "fig_q3_lightout.png")

    (out / "analysis.json").write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    (root / "RESULTS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):  # the report has non-ASCII characters; consoles may be cp949
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(md))


if __name__ == "__main__":
    main()
