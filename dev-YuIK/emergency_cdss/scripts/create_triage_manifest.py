"""Create and validate a clinician-review manifest for wound + triage research.

This script intentionally does *not* infer a KTAS level from an image or from
the wound-type class. KTAS is an assessment label that requires clinical
context and must be assigned/reviewed by an authorised clinical annotator.

Run from ``dev-YuIK``:

    python -m emergency_cdss.scripts.create_triage_manifest \
        --image-root dataset --output dataset/triage_manifest.csv
    python -m emergency_cdss.scripts.create_triage_manifest \
        --validate dataset/triage_manifest.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


WOUND_CLASSES = ("abrasions", "bruises", "cut", "stab")
SPLITS = ("train", "valid", "test")
KTAS_LEVELS = {"1", "2", "3", "4", "5"}

# Required when a clinical reviewer enters a definitive KTAS target.  The
# columns capture data needed to audit the decision; the official KTAS manual
# remains the source of the actual rule application.
REQUIRED_FOR_KTAS = (
    "deidentified_case_id",
    "chief_complaint",
    "injury_mechanism",
    "pain_nrs_0_10",
    "mental_status",
    "respiratory_status",
    "hemodynamic_status",
    "active_bleeding",
    "clinical_labeler_id",
    "clinical_labeler_role",
    "ktas_reference_code",
)

FIELDNAMES = (
    "sample_id",
    "image_path",
    "split",
    "wound_type_label",
    "source_image_id",
    # Do not place direct identifiers or protected health information here.
    "deidentified_case_id",
    "age_group",
    "chief_complaint",
    "injury_mechanism",
    "injury_site",
    "pain_nrs_0_10",
    "mental_status",  # e.g., AVPU/GCS recorded in the approved data system
    "respiratory_status",
    "hemodynamic_status",
    "active_bleeding",
    "bleeding_controlled",
    "neurovascular_compromise",
    "airway_concern",
    "clinical_ktas_level",
    "ktas_reference_code",
    "clinical_labeler_id",
    "clinical_labeler_role",
    "clinical_reviewed_at",
    "review_status",
    "adjudication_status",
    "label_notes",
)


def source_image_id(path: Path) -> str:
    """Stable local identifier only; it is not a patient/case identifier."""
    return path.stem.split(".rf.", maxsplit=1)[0]


def build_rows(image_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for split in SPLITS:
        for wound_class in WOUND_CLASSES:
            directory = image_root / split / wound_class
            if not directory.exists():
                continue
            for image_path in sorted(directory.glob("*.jpg")):
                row = {field: "" for field in FIELDNAMES}
                row.update(
                    sample_id=f"{split}:{wound_class}:{image_path.stem}",
                    image_path=image_path.as_posix(),
                    split=split,
                    wound_type_label=wound_class,
                    source_image_id=source_image_id(image_path),
                    review_status="pending_clinical_review",
                    adjudication_status="not_started",
                )
                rows.append(row)
    if not rows:
        raise FileNotFoundError(f"No cropped JPG images found beneath {image_root}")
    return rows


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    identifiers = set()
    for line_number, row in enumerate(rows, start=2):
        sample_id = row.get("sample_id", "")
        if not sample_id or sample_id in identifiers:
            errors.append(f"line {line_number}: missing or duplicate sample_id")
        identifiers.add(sample_id)
        if row.get("wound_type_label") not in WOUND_CLASSES:
            errors.append(f"line {line_number}: invalid wound_type_label")
        ktas = row.get("clinical_ktas_level", "").strip()
        if ktas:
            if ktas not in KTAS_LEVELS:
                errors.append(f"line {line_number}: clinical_ktas_level must be 1..5")
            missing = [name for name in REQUIRED_FOR_KTAS if not row.get(name, "").strip()]
            if missing:
                errors.append(f"line {line_number}: KTAS label is missing audit fields: {', '.join(missing)}")
            if row.get("review_status") not in {"clinically_reviewed", "adjudicated"}:
                errors.append(f"line {line_number}: KTAS label requires clinically_reviewed or adjudicated status")
        elif row.get("review_status") in {"clinically_reviewed", "adjudicated"}:
            errors.append(f"line {line_number}: reviewed row has no clinical_ktas_level")
    return errors


def write_manifest(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-root", type=Path, default=Path("dataset"))
    parser.add_argument("--output", type=Path, default=Path("dataset/triage_manifest.csv"))
    parser.add_argument("--validate", type=Path, metavar="CSV", help="Validate an edited manifest instead of creating one")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.validate:
        with args.validate.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing_headers = set(FIELDNAMES) - set(reader.fieldnames or [])
            if missing_headers:
                raise SystemExit(f"Missing required CSV columns: {sorted(missing_headers)}")
            rows = list(reader)
        errors = validate_rows(rows)
        if errors:
            raise SystemExit("Manifest validation failed:\n- " + "\n- ".join(errors))
        assigned = Counter(row["clinical_ktas_level"] for row in rows if row["clinical_ktas_level"])
        print(f"Valid manifest: {len(rows)} rows; assigned KTAS labels: {dict(sorted(assigned.items()))}")
        return

    rows = build_rows(args.image_root)
    write_manifest(rows, args.output)
    counts = Counter(row["wound_type_label"] for row in rows)
    print(f"Created {args.output} with {len(rows)} rows; wound labels: {dict(sorted(counts.items()))}")
    print("KTAS labels remain blank pending clinical review; no image-only severity label was generated.")


if __name__ == "__main__":
    main()
