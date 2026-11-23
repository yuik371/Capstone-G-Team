#!/usr/bin/env python3
"""Repeat run_validation.py over seeds x mesh-feature configs and report mean +/- std.

Each seed also reshuffles the identity-to-fold assignment, so this is repeated K-fold
cross-validation, not just a re-initialisation of the same split.

Example (from the repository root):
    .venv/Scripts/python.exe other-dev/dev-shs/run_repeats.py \
        --seeds 2027 2028 2029 --configs raw aligned subject \
        --output-root results/repeats -- --max-epochs 80 --hours 3

Arguments after "--" are passed to run_validation.py unchanged. Completed runs
(metrics.json present) are skipped, so an interrupted sweep can be resumed.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_validation.py"
FOCUS_PAIR = ("Anger", "Sadness")


def run_one(run_dir: Path, seed: int, config: str, extra: list[str]) -> None:
    if (run_dir / "metrics.json").exists():
        print(f"[skip] {run_dir} already complete", flush=True)
        return
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit(
            f"{run_dir} has partial output from an interrupted run; delete it and re-run to resume."
        )
    cmd = [
        sys.executable, str(RUNNER),
        "--seed", str(seed),
        "--mesh-features", config,
        "--output-dir", str(run_dir),
        *extra,
    ]
    print(f"[run] {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)


def mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return float("nan"), float("nan")
    return statistics.fmean(values), (statistics.stdev(values) if len(values) > 1 else 0.0)


def summarize(output_root: Path, seeds: list[int], configs: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for config in configs:
        per_model: dict[str, dict[str, list[float]]] = {}
        used_seeds: list[int] = []
        for seed in seeds:
            metrics_path = output_root / config / f"seed_{seed}" / "metrics.json"
            if not metrics_path.exists():
                continue
            used_seeds.append(seed)
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            classes = metrics["classes"]
            for model, summary in metrics["models"].items():
                bucket = per_model.setdefault(model, {})
                for key in ("accuracy", "macro_f1", "balanced_accuracy", "auroc_ovr_macro"):
                    bucket.setdefault(key, []).append(float(summary[key]))
                matrix = summary.get("confusion_matrix", {}).get("counts")
                if matrix and all(name in classes for name in FOCUS_PAIR):
                    a, s = (classes.index(name) for name in FOCUS_PAIR)
                    bucket.setdefault("anger_sadness_confusions", []).append(
                        float(matrix[a][s] + matrix[s][a])
                    )
                    for name, idx in zip(FOCUS_PAIR, (a, s)):
                        total = sum(matrix[idx])
                        bucket.setdefault(f"recall_{name}", []).append(
                            matrix[idx][idx] / total if total else float("nan")
                        )
        for model, bucket in sorted(per_model.items()):
            row: dict[str, object] = {"config": config, "model": model, "n_seeds": len(used_seeds)}
            for key, values in bucket.items():
                mean, std = mean_std(values)
                row[f"{key}_mean"] = round(mean, 4)
                row[f"{key}_std"] = round(std, 4)
            rows.append(row)
    return rows


def write_reports(output_root: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        print("No completed runs to summarise.")
        return
    fieldnames: list[str] = []
    for row in rows:
        fieldnames.extend(k for k in row if k not in fieldnames)
    with (output_root / "summary.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    def fmt(row: dict[str, object], key: str, digits: int = 3) -> str:
        if f"{key}_mean" not in row:
            return "-"
        return f"{row[f'{key}_mean']:.{digits}f} ± {row[f'{key}_std']:.{digits}f}"

    lines = [
        "| config | model | seeds | macro-F1 | accuracy | AUROC | Anger↔Sadness errors | recall Anger | recall Sadness |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['config']} | {row['model']} | {row['n_seeds']} | {fmt(row, 'macro_f1')} | "
            f"{fmt(row, 'accuracy')} | {fmt(row, 'auroc_ovr_macro')} | "
            f"{fmt(row, 'anger_sadness_confusions', 1)} | {fmt(row, 'recall_Anger')} | "
            f"{fmt(row, 'recall_Sadness')} |"
        )
    note = (
        "\nValues are out-of-fold metrics pooled over all test identities per seed, "
        "reported as mean ± sample std across seeds.\n"
    )
    (output_root / "summary.md").write_text("\n".join(lines) + "\n" + note, encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    argv = sys.argv[1:]
    extra: list[str] = []
    if "--" in argv:
        split = argv.index("--")
        argv, extra = argv[:split], argv[split + 1:]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", type=int, nargs="+", default=[2027, 2028, 2029])
    parser.add_argument("--configs", nargs="+", default=["raw", "aligned", "subject"],
                        choices=["raw", "aligned", "subject"])
    parser.add_argument("--output-root", type=Path, default=Path("results/repeats"))
    parser.add_argument("--summary-only", action="store_true", help="Only aggregate existing runs.")
    args = parser.parse_args(argv)
    reserved = {"--seed", "--mesh-features", "--output-dir"}
    if reserved & set(extra):
        parser.error(f"{sorted(reserved)} are set by run_repeats.py; do not pass them after '--'.")

    args.output_root.mkdir(parents=True, exist_ok=True)
    if not args.summary_only:
        for seed in args.seeds:
            for config in args.configs:
                run_one(args.output_root / config / f"seed_{seed}", seed, config, extra)
    write_reports(args.output_root, summarize(args.output_root, args.seeds, args.configs))


if __name__ == "__main__":
    main()
