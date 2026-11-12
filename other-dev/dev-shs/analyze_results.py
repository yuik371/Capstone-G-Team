#!/usr/bin/env python3
"""Subject-level statistics, tables and figures from the saved prediction files.

Reads   results/cvpr2027/predictions_{loso,random,triplet,lightout}.csv
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
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
MARKERS = ["o", "s", "^"]
SEQ = matplotlib.colors.LinearSegmentedColormap.from_list("seq_blue", ["#fcfcfb", "#cde2fb", "#5598e7", "#0d366b"])

LABELS = {
    "image_flip": "Image only",
    "image_noflip": "Image only, no flip",
    "mesh_raw": "Mesh only",
    "mesh_naiveflip": "Mesh only, naive flip",
    "mesh_noflip": "Mesh only, no flip",
    "mesh_shuffled": "Mesh only, shuffled mesh",
    "mesh_neutral": "Mesh only, Neutral-subtracted",
    "scalars": "Image + [A, G] scalars",
    "fused_perm": "Fused (image + mesh)",
    "fused_naiveflip": "Fused, naive flip",
    "fused_noflip": "Fused, no flip",
    "fused_shuffled": "Fused, shuffled mesh",
    "fused_neutral": "Fused, Neutral-subtracted mesh",
}
ORDER = list(LABELS)
MAIN = ["image_flip", "mesh_raw", "fused_perm"]

# (name, a, b, role): difference a - b on per-subject accuracy. b=None -> a minus chance (1/7).
CONTRASTS = [
    ("fusion gain (secondary question)", "fused_perm", "image_flip", "secondary"),
    ("Q2 mesh-only vs chance", "mesh_raw", None, "Q2"),
    ("Q2 Neutral-subtracted mesh-only vs chance", "mesh_neutral", None, "Q2"),
    ("Q2 shuffled mesh-only vs chance (negative control)", "mesh_shuffled", None, "Q2"),
    ("Q2 identity removal on mesh-only", "mesh_neutral", "mesh_raw", "Q2"),
    ("mesh-only vs image-only", "mesh_raw", "image_flip", "Q2"),
    ("control: fused with real vs shuffled mesh", "fused_perm", "fused_shuffled", "control"),
    ("control: shuffled-mesh fused vs image-only", "fused_shuffled", "image_flip", "control"),
    ("control: image + scalars vs image-only", "scalars", "image_flip", "control"),
    ("control: Neutral-subtracted fused vs image-only", "fused_neutral", "image_flip", "control"),
    ("control: Neutral-subtracted fused vs fused", "fused_neutral", "fused_perm", "control"),
    ("flip: fused permuted vs naive", "fused_perm", "fused_naiveflip", "flip"),
    ("flip: fused permuted vs none", "fused_perm", "fused_noflip", "flip"),
    ("flip: fused naive vs none", "fused_naiveflip", "fused_noflip", "flip"),
    ("flip: mesh-only permuted vs naive", "mesh_raw", "mesh_naiveflip", "flip"),
    ("flip: mesh-only permuted vs none", "mesh_raw", "mesh_noflip", "flip"),
    ("flip: mesh-only naive vs none", "mesh_naiveflip", "mesh_noflip", "flip"),
    ("flip: image-only flip vs none", "image_flip", "image_noflip", "flip"),
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

    md += ["# Results (generated by analyze_results.py — do not edit by hand)", "",
           f"Data: AI-Hub face-landmark **sample only** — {len(subjects)} subjects, {len(classes)} expressions, "
           f"{len(lights)} lighting levels, {len(subjects) * len(classes) * len(lights)} images. "
           f"Seeds: {seeds}. Chance = {pct(CHANCE)}%.", "",
           "All intervals and tests use the **subject** as the unit (n = 10). With 10 subjects every interval "
           "is wide and every test has low power; the smallest two-sided p-value an exact sign-flip test can "
           f"return is {2 / 2 ** len(subjects):.4f}. Bootstrap intervals with 10 clusters are known to be too narrow; "
           "the t-interval is given alongside.", "",
           "## 1. Leave-one-subject-out (10 folds, fixed epochs, final-epoch weights)", "",
           "| Model | Acc % (mean ± SD over seeds) | Macro-F1 % | Subject-mean acc % [95% boot CI] | Worst / best subject % | Acc % w/o Neutral class | ECE % | Triplet same-pred % | Epochs |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in summary_rows:
        md.append(
            f"| {r['label']} | {pm(r['accuracy_mean_over_seeds'], r['accuracy_sd_over_seeds'])} | "
            f"{pm(r['macro_f1_mean'], r['macro_f1_sd'])} | {pct(r['subject_mean_accuracy'])} "
            f"[{pct(r['subject_boot_ci_low'])}, {pct(r['subject_boot_ci_high'])}] | "
            f"{pct(r['worst_subject'])} / {pct(r['best_subject'])} | "
            f"{pm(r['accuracy_without_neutral_class_mean'], r['accuracy_without_neutral_class_sd'])} | "
            f"{pm(r['ece_mean'], r['ece_sd'])} | {pct(r['triplet_same_prediction_rate'])} | {r['epochs_used']} |")
    md += ["", "SD over seeds reflects training randomness only (the LOSO split is deterministic); it does not "
           "reflect uncertainty about new subjects. ECE is computed per seed on the 210 pooled out-of-fold "
           "predictions (10 different fold models, 10 bins) and is a coarse estimate.", ""]

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
        lines = ["| Contrast (a − b) | Mean diff, pp | 95% boot CI | 95% t CI | Cohen d_z | W / L / T subjects | Sign-flip p | Holm p | Wilcoxon p | Seed-level diff, pp (mean ± SD) |",
                 "|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(
                f"| {r['contrast']} ({r['a']} − {r['b']}) | {pct(r['mean_diff'], 1, True)} | "
                f"[{pct(r['boot_ci_low'], 1, True)}, {pct(r['boot_ci_high'], 1, True)}] | "
                f"[{pct(r['t_ci_low'], 1, True)}, {pct(r['t_ci_high'], 1, True)}] | {r['cohen_dz']:.2f} | "
                f"{r['wins']} / {r['losses']} / {r['ties']} | {r['signflip_p']:.4f} | "
                f"{r.get('signflip_p_holm', float('nan')):.4f} | {r['wilcoxon_p']:.4f} | "
                f"{pct(r['per_seed_diff_mean'], 1, True)} ± {pct(r['per_seed_diff_sd'])} |")
        return lines

    md += ["## 2. Paired subject-level contrasts (LOSO)", "",
           "Per-subject accuracy is averaged over seeds, then differenced (n = 10 pairs). Wilcoxon signed-rank "
           "on 10 pairs has low power; a non-significant result is **not** evidence of no effect. "
           f"{len(contrast_rows)} contrasts are reported; Holm-adjusted sign-flip p-values are in the Holm column.", ""]
    md += contrast_table(contrast_rows) + [""]

    # ---------------- confusion matrices ----------------
    confusion: dict[str, np.ndarray] = {}
    anger_sad_rows = []
    for c in conditions:
        m = np.zeros((len(classes), len(classes)), dtype=int)
        for r in by_condition[(c,)]:
            m[classes.index(r["label"]), classes.index(r["prediction"])] += 1
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
    md += ["## 3. Confusions (counts summed over all seeds; rows = true class)", "",
           "| Model | Anger→Sadness | Sadness→Anger | Share of all errors % | Anger recall % | Sadness recall % |",
           "|---|---|---|---|---|---|"]
    for r in anger_sad_rows:
        md.append(f"| {r['label']} | {r['anger_to_sadness_total']} | {r['sadness_to_anger_total']} | "
                  f"{pct(r['share_of_all_errors'])} | {pct(r['anger_recall'])} | {pct(r['sadness_recall'])} |")
    md += ["", "Per-class recall (%), summed over seeds:", "",
           "| Model | " + " | ".join(classes) + " |", "|---|" + "---|" * len(classes)]
    for r in recall_rows:
        md.append(f"| {LABELS[r['condition']]} | " + " | ".join(pct(r[c]) for c in classes) + " |")
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
        for c in split_conditions:
            for protocol in ("random", "triplet", "loso"):
                rows = [r for r in (loso if protocol == "loso" else split_rows[protocol]) if r["condition"] == c]
                acc_seed = per_seed(rows, accuracy)
                subj_split[(protocol, c)] = subject_accuracy(rows, subjects).mean(axis=0)
                q1_rows.append({"condition": c, "label": LABELS[c], "protocol": protocol, "n_seeds": len(acc_seed),
                                "accuracy_mean_over_seeds": acc_seed.mean(), "accuracy_sd_over_seeds": acc_seed.std(ddof=1),
                                "subject_mean_accuracy": subj_split[(protocol, c)].mean(),
                                "epochs_used": "/".join(map(str, sorted({int(r["epochs"]) for r in rows})))})
            for pa, pb in (("random", "loso"), ("triplet", "loso"), ("random", "triplet")):
                seed_a = [x["accuracy_mean_over_seeds"] for x in q1_rows if x["condition"] == c and x["protocol"] == pa][0]
                seed_b = [x["accuracy_mean_over_seeds"] for x in q1_rows if x["condition"] == c and x["protocol"] == pb][0]
                q1_contrasts.append({"contrast": f"{LABELS[c]}: {pa} − {pb}", "role": "Q1", "a": pa, "b": pb,
                                     **paired_stats(subj_split[(pa, c)] - subj_split[(pb, c)], rng),
                                     "per_seed_diff_mean": seed_a - seed_b, "per_seed_diff_sd": float("nan"),
                                     "condition": c})
        for row, adj in zip(q1_contrasts, holm([r["signflip_p"] for r in q1_contrasts])):
            row["signflip_p_holm"] = adj
        write_csv(out / "q1_split_comparison.csv", q1_rows)
        write_csv(out / "q1_split_contrasts.csv", q1_contrasts)
        report["q1"] = {"table": q1_rows, "contrasts": q1_contrasts}
        md += ["## 4. Q1 — image-level random split vs subject-disjoint evaluation", "",
               "`random`: stratified image-level 10-fold (the same person, and usually the other two lighting "
               "variants of the same capture, are in the training set). `triplet`: 10-fold with the three lighting "
               "variants of a capture kept together (same person still in training). `loso`: subject-disjoint. "
               "All three train on 189 images and test on 21 per fold.", "",
               "| Model | Protocol | Acc % (mean ± SD over seeds) | Epochs |", "|---|---|---|---|"]
        for r in q1_rows:
            md.append(f"| {r['label']} | {r['protocol']} | {pm(r['accuracy_mean_over_seeds'], r['accuracy_sd_over_seeds'])} | {r['epochs_used']} |")
        md += ["", "Paired by subject (each subject's images are scored out-of-fold under every protocol):", ""]
        md += contrast_table(q1_contrasts) + [""]

    # ---------------- Q3: leave-one-light-out ----------------
    lightout = load(root / "predictions_lightout.csv")
    q3_rows, q3_contrasts = [], []
    if lightout:
        for c in [c for c in MAIN if any(r["condition"] == c for r in lightout)]:
            rows_c = [r for r in lightout if r["condition"] == c]
            base_c = by_condition[(c,)]
            unseen_all, base_all, seen_all = [], [], []
            for light in lights:
                unseen = [r for r in rows_c if r["held_out_light"] == light and r["light"] == light]
                seen = [r for r in rows_c if r["held_out_light"] == light and r["light"] != light]
                base = [r for r in base_c if r["light"] == light]
                u, b, s = (subject_accuracy(x, subjects).mean(axis=0) for x in (unseen, base, seen))
                unseen_all.append(u); base_all.append(b); seen_all.append(s)
                u_seed, b_seed, s_seed = (per_seed(x, accuracy) for x in (unseen, base, seen))
                q3_rows.append({"condition": c, "label": LABELS[c], "held_out_light": light,
                                "acc_unseen_light_mean": u_seed.mean(), "acc_unseen_light_sd": u_seed.std(ddof=1),
                                "acc_same_light_when_trained_on_all_lights_mean": b_seed.mean(),
                                "acc_same_light_when_trained_on_all_lights_sd": b_seed.std(ddof=1),
                                "acc_on_the_two_seen_lights_mean": s_seed.mean(), "acc_on_the_two_seen_lights_sd": s_seed.std(ddof=1)})
                q3_contrasts.append({"contrast": f"{LABELS[c]}: unseen {light} − same light, trained on all lights",
                                     "role": "Q3", "a": "lightout", "b": "loso", **paired_stats(u - b, rng),
                                     "per_seed_diff_mean": float((u_seed - b_seed).mean()),
                                     "per_seed_diff_sd": float((u_seed - b_seed).std(ddof=1)), "condition": c})
            u, b, s = (np.mean(x, axis=0) for x in (unseen_all, base_all, seen_all))
            for label, d in ((f"{LABELS[c]}: unseen light − same light trained on all lights (mean of 3 lights)", u - b),
                             (f"{LABELS[c]}: unseen light − seen lights, same model (mean of 3 lights)", u - s)):
                q3_contrasts.append({"contrast": label, "role": "Q3", "a": "lightout", "b": "reference",
                                     **paired_stats(d, rng), "per_seed_diff_mean": float(d.mean()),
                                     "per_seed_diff_sd": float("nan"), "condition": c})
        for row, adj in zip(q3_contrasts, holm([r["signflip_p"] for r in q3_contrasts])):
            row["signflip_p_holm"] = adj
        write_csv(out / "q3_lightout.csv", q3_rows)
        write_csv(out / "q3_lightout_contrasts.csv", q3_contrasts)
        report["q3"] = {"table": q3_rows, "contrasts": q3_contrasts}
        md += ["## 5. Q3 — leave-one-light-out (inside LOSO)", "",
               "Each model is trained on 9 subjects × 2 lighting levels (126 images) and tested on the held-out "
               "subject. `Unseen light` = accuracy on that subject's images in the lighting level never seen in "
               "training. Reference 1 = the LOSO model trained on all three lights (189 images), scored on the same "
               "images. Reference 2 = the same leave-one-light-out model scored on the two lights it did see.", "",
               "| Model | Held-out light | Unseen light acc % | Same light, trained on all lights % | Seen lights, same model % |",
               "|---|---|---|---|---|"]
        for r in q3_rows:
            md.append(f"| {r['label']} | {r['held_out_light']} | {pm(r['acc_unseen_light_mean'], r['acc_unseen_light_sd'])} | "
                      f"{pm(r['acc_same_light_when_trained_on_all_lights_mean'], r['acc_same_light_when_trained_on_all_lights_sd'])} | "
                      f"{pm(r['acc_on_the_two_seen_lights_mean'], r['acc_on_the_two_seen_lights_sd'])} |")
        md += ["", "Mean ± SD over seeds. Paired by subject:", ""] + contrast_table(q3_contrasts) + [""]

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
        md += ["## 6. Epoch selection (inner 3-fold CV over the 9 training subjects of each outer fold)", "",
               "| Model | Selected epochs per outer fold (01…10) |", "|---|---|"]
        for c in sorted({r["condition"] for r in sel}, key=ORDER.index):
            md.append(f"| {LABELS[c]} | " + ", ".join(r["selected_epochs"] for r in sel if r["condition"] == c) + " |")
        md.append("")

    # ---------------- figures ----------------
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

    # (b) per-subject accuracy of the three main models
    main_present = [c for c in MAIN if c in subj_acc]
    fig, ax = plt.subplots(figsize=(8.2, 4.0))
    style_axes(ax)
    x = np.arange(len(subjects))
    for k, c in enumerate(main_present):
        ax.plot(x + (k - 1) * 0.18, 100 * subj_acc[c], MARKERS[k], color=SERIES[k], markersize=8,
                markeredgecolor=SURFACE, markeredgewidth=1.5, linestyle="none", label=LABELS[c])
    ax.set_xticks(x, subjects)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Accuracy on that held-out subject, %", color=INK2, fontsize=9)
    ax.set_title("Per-subject accuracy (21 images each, mean over seeds)", loc="left", fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=9, ncol=3, loc="lower left", labelcolor=INK2)
    save(fig, out / "fig_per_subject.png")

    # (c) confusion matrices, row-normalised
    fig, axes = plt.subplots(1, len(main_present), figsize=(4.6 * len(main_present), 4.6), squeeze=False)
    for ax, c in zip(axes[0], main_present):
        m = confusion[c]
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
    axes[0][0].set_ylabel("True (row %, all seeds pooled)", fontsize=9, color=INK2)
    save(fig, out / "fig_confusion.png")

    # (d) reliability diagrams
    fig, axes = plt.subplots(1, len(main_present), figsize=(3.6 * len(main_present), 3.7), squeeze=False, sharey=True)
    for k, (ax, c) in enumerate(zip(axes[0], main_present)):
        style_axes(ax)
        bins = [r for r in calibration_rows if r["condition"] == c]
        ax.plot([0, 1], [0, 1], color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
        ax.plot([b["mean_confidence"] for b in bins], [b["accuracy"] for b in bins], "-o", color=SERIES[k],
                linewidth=2, markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.5)
        row = [r for r in summary_rows if r["condition"] == c][0]
        ax.set_title(f"{LABELS[c]}\nECE {pct(row['ece_mean'])}%", loc="left", fontsize=10, color=INK)
        ax.set_xlabel("Confidence", fontsize=9, color=INK2)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
    axes[0][0].set_ylabel("Accuracy in bin", fontsize=9, color=INK2)
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
            ax.errorbar(xs - 0.1, [100 * r["acc_same_light_when_trained_on_all_lights_mean"] for r in rows],
                        yerr=[100 * r["acc_same_light_when_trained_on_all_lights_sd"] for r in rows], fmt="o", color=MUTED,
                        markersize=7, elinewidth=1, capsize=2, label="Light seen in training (all 3 lights)")
            ax.errorbar(xs + 0.1, [100 * r["acc_unseen_light_mean"] for r in rows],
                        yerr=[100 * r["acc_unseen_light_sd"] for r in rows], fmt=MARKERS[k], color=SERIES[k],
                        markersize=7, elinewidth=1, capsize=2, label="Light never seen in training")
            ax.set_xticks(xs, [r["held_out_light"].replace("light", "") for r in rows], color=INK)
            ax.set_xlim(-0.5, len(rows) - 0.5); ax.set_ylim(0, 105)
            ax.set_title(LABELS[c], loc="left", fontsize=10, color=INK)
            ax.set_xlabel("Test lighting level", fontsize=9, color=INK2)
            ax.legend(frameon=False, fontsize=8, loc="lower left", labelcolor=INK2)
        axes[0][0].set_ylabel("Accuracy on held-out subject, %\n(mean ± SD over seeds)", fontsize=9, color=INK2)
        save(fig, out / "fig_q3_lightout.png")

    (out / "analysis.json").write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    (root / "RESULTS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
