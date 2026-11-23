"""Run the vision-only baseline and joint landmark-fused experiment."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    project_dir = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=project_dir / "dataset/drive_landmark/manifest.json")
    parser.add_argument("--output-dir", type=Path, default=project_dir / "dataset/face_experiments")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--schedule-hours", type=float, default=8.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--no-pretrained", action="store_true")
    parser.add_argument("--no-grid", action="store_true")
    return parser.parse_args()


def _run_mode(args: argparse.Namespace, mode: str, allocated_hours: float) -> None:
    command = [
        sys.executable,
        "-m",
        "emergency_cdss.scripts.train_face_multimodal",
        "--manifest",
        str(args.manifest.resolve()),
        "--output-dir",
        str(args.output_dir.resolve()),
        "--mode",
        mode,
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
        "--num-workers",
        str(args.num_workers),
        "--schedule-hours",
        str(allocated_hours),
        "--seed",
        str(args.seed),
        "--device",
        args.device,
    ]
    if args.no_pretrained:
        command.append("--no-pretrained")
    if args.no_grid:
        command.append("--no-grid")
    print("Running:", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main() -> None:
    args = parse_args()
    if args.schedule_hours < 0:
        raise SystemExit("schedule-hours cannot be negative")
    args.output_dir.resolve().mkdir(parents=True, exist_ok=True)
    allocated_hours = args.schedule_hours / 2.0 if args.schedule_hours > 0 else 0.0
    for mode in ("vision", "joint"):
        _run_mode(args, mode, allocated_hours)

    summaries: dict[str, dict[str, Any]] = {}
    for mode in ("vision", "joint"):
        path = args.output_dir.resolve() / f"metrics_{mode}.json"
        if not path.is_file():
            raise SystemExit(f"Expected experiment output is missing: {path}")
        summaries[mode] = json.loads(path.read_text(encoding="utf-8"))
    vision_test = summaries["vision"]["test"]["metrics"]
    joint_test = summaries["joint"]["test"]["metrics"]
    comparison = {
        "protocol": {
            "same_seed": args.seed,
            "same_identity_split": summaries["joint"]["split_subjects"],
            "schedule_hours": args.schedule_hours,
            "hours_per_model_allocation": allocated_hours,
            "test_used_only_after_checkpoint_selection": True,
        },
        "models": {
            mode: {
                "macro_f1": summaries[mode]["test"]["metrics"]["macro_f1"],
                "balanced_accuracy": summaries[mode]["test"]["metrics"]["balanced_accuracy"],
                "macro_auroc": summaries[mode]["test"]["metrics"]["macro_auroc"],
                "parameters": summaries[mode]["parameters"],
                "latency": summaries[mode]["test"]["latency"],
                "runtime_seconds": summaries[mode]["runtime_seconds"],
                "qualitative_grid": str(args.output_dir.resolve() / f"qualitative_grid_{mode}_6x6.png"),
            }
            for mode in ("vision", "joint")
        },
        "joint_minus_vision": {
            "macro_f1": joint_test["macro_f1"] - vision_test["macro_f1"],
            "balanced_accuracy": joint_test["balanced_accuracy"] - vision_test["balanced_accuracy"],
            "macro_auroc": joint_test["macro_auroc"] - vision_test["macro_auroc"]
            if joint_test["macro_auroc"] is not None and vision_test["macro_auroc"] is not None
            else None,
        },
    }
    output_path = args.output_dir.resolve() / "comparison.json"
    output_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
