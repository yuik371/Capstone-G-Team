"""Download and index the public facial image/landmark dataset from Google Drive.

The shared folder is organized as::

    root/
      01.원천데이터/image/F1350/*.png
      02.라벨링데이터/F1350/json/*.json

This script discovers Drive file identifiers from the public folder HTML, caches
the matched PNG/JSON pairs locally, and writes a manifest suitable for an
identity-disjoint multimodal experiment.  Network access is intentionally kept
in this preparation step so that training itself only reads local files.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT_FOLDER_ID = "199ntogVynV_ZMt3H7ZE_VE1hvw0Jjr-p"
# These IDs are stable identifiers for the public folder supplied by the user.
# Keeping them here also avoids depending on locale-specific Korean aria labels
# in Drive's HTML shell.
SOURCE_FOLDER_ID = "1XAM0F7D1yxpg9t0fz8R46Ge63621rDZb"
LABEL_FOLDER_ID = "17f18IbQ8UQCgGZR4bsZouUGLmml4wZ1l"
IMAGE_FOLDER_ID = "1Ke_z-k5gSXEbyPDFy4HtvTczv0xwCnSe"


def _download_bytes(url: str) -> bytes:
    command = [
        "curl.exe",
        "-L",
        "--fail",
        "--silent",
        "--show-error",
        "--retry",
        "3",
        "--retry-delay",
        "1",
        "--connect-timeout",
        "30",
        "--max-time",
        "180",
        url,
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError("curl.exe is required to access the public Drive folder") from exc
    return result.stdout


def _folder_url(folder_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{folder_id}"


def _file_url(file_id: str) -> str:
    return (
        "https://drive.usercontent.google.com/download?"
        f"id={file_id}&export=download&confirm=t"
    )


def _clean_name(label: str) -> str:
    cleaned = label.strip()
    file_match = re.match(r"^(.*?\.(?:json|png|obj))\b", cleaned, re.IGNORECASE)
    if file_match:
        return file_match.group(1)
    cleaned = re.sub(r"\s+(?:Unknown|Shared|Shared folder|알 수 없음|공유됨).*$", "", cleaned)
    return cleaned.strip()


def parse_drive_items(html: str) -> list[dict[str, str]]:
    """Extract visible Drive row identifiers and names from public HTML."""

    items: list[dict[str, str]] = []
    row_pattern = re.compile(r"<tr[^>]+role=\"row\".*?</tr>", re.IGNORECASE | re.DOTALL)
    id_pattern = re.compile(r'data-file-icon[^>]+data-id="([A-Za-z0-9_-]+)"')
    for row in row_pattern.findall(html):
        id_match = id_pattern.search(row)
        if id_match is None:
            continue
        labels = re.findall(r'aria-label="([^"]+)"', row)
        name = None
        for label in labels:
            candidate = _clean_name(label)
            if candidate and candidate not in {"Unknown", "Shared", "Shared folder"}:
                if re.search(r"(?:\.json|\.png|\.obj)$", candidate, re.IGNORECASE):
                    name = candidate
                    break
                if candidate == "json" or candidate == "image" or re.fullmatch(r"F\d+", candidate):
                    name = candidate
                    break
        if name is None:
            continue
        items.append({"id": id_match.group(1), "name": name})
    return items


def _find(items: Iterable[dict[str, str]], name: str) -> dict[str, str]:
    matches = [item for item in items if item["name"] == name]
    if len(matches) != 1:
        available = ", ".join(sorted(item["name"] for item in items)[:20])
        raise RuntimeError(f"Expected one Drive item named {name!r}; found {len(matches)} ({available})")
    return matches[0]


def _cached_download(file_id: str, path: Path) -> None:
    if path.is_file() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_download_bytes(_file_url(file_id)))
    if path.stat().st_size == 0:
        raise RuntimeError(f"Downloaded an empty file: {path}")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not parse label JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected an object in label JSON: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("dataset/drive_landmark"))
    parser.add_argument("--target", default="expression", help="JSON metadata field used as the class label")
    parser.add_argument(
        "--views",
        nargs="+",
        default=["H", "L", "M"],
        help="Image suffixes to include; use H only for a smaller smoke dataset",
    )
    parser.add_argument("--limit-subjects", type=int, default=0, help="0 keeps all public subjects")
    parser.add_argument("--skip-images", action="store_true", help="Download labels and write a manifest without PNGs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.limit_subjects < 0:
        raise SystemExit("--limit-subjects cannot be negative")
    views = {str(view).upper() for view in args.views}
    if not views:
        raise SystemExit("--views must contain at least one suffix")

    output_dir = args.output_dir.resolve()
    labels_dir = output_dir / "labels"
    images_dir = output_dir / "images"
    output_dir.mkdir(parents=True, exist_ok=True)

    label_samples = parse_drive_items(_download_bytes(_folder_url(LABEL_FOLDER_ID)).decode("utf-8", "replace"))
    image_samples = parse_drive_items(_download_bytes(_folder_url(IMAGE_FOLDER_ID)).decode("utf-8", "replace"))
    label_by_name = {item["name"]: item for item in label_samples if re.fullmatch(r"F\d+", item["name"])}
    image_by_name = {item["name"]: item for item in image_samples if re.fullmatch(r"F\d+", item["name"])}
    subject_names = sorted(set(label_by_name) & set(image_by_name))
    if args.limit_subjects:
        subject_names = subject_names[: args.limit_subjects]
    if not subject_names:
        raise RuntimeError("No matching image/label subject folders were found")

    records: list[dict[str, Any]] = []
    for subject_name in subject_names:
        label_children = parse_drive_items(
            _download_bytes(_folder_url(label_by_name[subject_name]["id"])).decode("utf-8", "replace")
        )
        json_folder = _find(label_children, "json")
        label_files = parse_drive_items(
            _download_bytes(_folder_url(json_folder["id"])).decode("utf-8", "replace")
        )
        label_files_by_name = {
            item["name"]: item for item in label_files if item["name"].lower().endswith(".json")
        }

        image_children = parse_drive_items(
            _download_bytes(_folder_url(image_by_name[subject_name]["id"])).decode("utf-8", "replace")
        )
        image_files_by_name = {
            item["name"]: item for item in image_children if item["name"].lower().endswith(".png")
        }

        for label_name, label_file in sorted(label_files_by_name.items()):
            stem = Path(label_name).stem
            view = stem.rsplit("_", 1)[-1].upper()
            if view not in views:
                continue
            image_name = f"{stem}.png"
            if not args.skip_images and image_name not in image_files_by_name:
                raise RuntimeError(f"Missing image counterpart for {subject_name}/{label_name}")

            local_label = labels_dir / subject_name / label_name
            _cached_download(label_file["id"], local_label)
            payload = _read_json(local_label)
            if args.target not in payload:
                raise RuntimeError(f"Target field {args.target!r} is absent from {local_label}")
            local_image = images_dir / subject_name / image_name
            if not args.skip_images:
                _cached_download(image_files_by_name[image_name]["id"], local_image)

            records.append(
                {
                    "subject_id": str(payload.get("filename", subject_name)),
                    "sample_id": str(payload.get("id", subject_name)),
                    "image": str(local_image.relative_to(output_dir)) if not args.skip_images else None,
                    "label": str(local_label.relative_to(output_dir)),
                    "target": str(payload[args.target]),
                    "target_field": args.target,
                    "view": view,
                    "metadata": {
                        key: payload.get(key)
                        for key in ("gender", "proficiency", "age", "expression", "light")
                        if key in payload
                    },
                }
            )
        print(f"[{subject_name}] indexed {sum(r['subject_id'] == subject_name for r in records)} records", flush=True)

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "root_folder_id": ROOT_FOLDER_ID,
        "subjects": sorted({record["subject_id"] for record in records}),
        "num_records": len(records),
        "target_field": args.target,
        "classes": sorted({record["target"] for record in records}),
        "views": sorted({record["view"] for record in records}),
        "manifest": str(manifest_path),
    }
    (output_dir / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
