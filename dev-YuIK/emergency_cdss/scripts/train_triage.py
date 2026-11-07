"""Reserved entry point for structured and multimodal triage training.

This is intentionally a scaffold until the clinical, stroke follow-up, face,
medication, and 3D pose schemas are finalized. Implementing a trainer before
those labels, patient-level split rules, and temporal sampling policies are
fixed would make the experiment difficult to reproduce.
"""

from __future__ import annotations


def main() -> None:
    raise SystemExit(
        "train_triage.py is a scaffold. Finalize the shared manifest and labels "
        "before adding multimodal training."
    )


if __name__ == "__main__":
    main()

