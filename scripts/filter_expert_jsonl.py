#!/usr/bin/env python3
"""Filter CADExpert-style JSONL records by system content and fix image paths."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_TARGET_CONTENT = "You are an AI assistant specialized as Expert 3"
IMAGE_DIR_MAP = {
    "input_circle": "Circles",
    "input_polygon": "Polygons",
    "input_rect": "Rects",
}


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            yield line_number, record


def record_has_content(record: dict[str, Any], target_content: str) -> bool:
    messages = record.get("messages")
    if not isinstance(messages, list):
        return False
    return any(isinstance(message, dict) and message.get("content") == target_content for message in messages)


def fixed_image_path(image_path: str, image_root: str) -> str:
    normalized = image_path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    filename = parts[-1] if parts else normalized
    for source_dir, target_dir in IMAGE_DIR_MAP.items():
        if source_dir in parts:
            return f"{image_root.rstrip('/')}/{target_dir}/{filename}"
    return image_path


def fixed_record_images(record: dict[str, Any], image_root: str) -> tuple[dict[str, Any], Counter[str]]:
    stats: Counter[str] = Counter()
    updated = dict(record)
    images = record.get("images")
    if not isinstance(images, list):
        stats["records_missing_images"] += 1
        return updated, stats

    fixed_images: list[Any] = []
    for image_path in images:
        if not isinstance(image_path, str):
            fixed_images.append(image_path)
            stats["non_string_images"] += 1
            continue
        fixed = fixed_image_path(image_path, image_root)
        fixed_images.append(fixed)
        if fixed != image_path:
            stats["fixed_image_paths"] += 1
        for source_dir, target_dir in IMAGE_DIR_MAP.items():
            if source_dir in image_path.replace("\\", "/").split("/"):
                stats[f"mapped_{source_dir}_to_{target_dir}"] += 1
                break
    updated["images"] = fixed_images
    return updated, stats


def missing_images(record: dict[str, Any], workspace_root: Path) -> list[str]:
    images = record.get("images")
    if not isinstance(images, list):
        return []
    missing: list[str] = []
    for image_path in images:
        if not isinstance(image_path, str):
            continue
        path = Path(image_path)
        if not path.is_absolute():
            path = workspace_root / path
        if not path.exists():
            missing.append(image_path)
    return missing


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("data.jsonl"), type=Path)
    parser.add_argument("--output", default=Path("outputs/data_expert3_fixed_paths.jsonl"), type=Path)
    parser.add_argument("--target-content", default=DEFAULT_TARGET_CONTENT)
    parser.add_argument("--image-root", default="./image")
    parser.add_argument("--require-images", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    summary: Counter[str] = Counter()
    missing_examples: list[dict[str, Any]] = []
    workspace_root = Path.cwd()

    with args.output.open("w", encoding="utf-8", newline="\n") as output_handle:
        for source_line, record in read_jsonl(args.input):
            summary["input_records"] += 1
            if not record_has_content(record, args.target_content):
                continue

            summary["matched_records"] += 1
            fixed, stats = fixed_record_images(record, args.image_root)
            summary.update(stats)
            missing = missing_images(fixed, workspace_root)
            if missing:
                summary["records_with_missing_images"] += 1
                summary["missing_images"] += len(missing)
                if len(missing_examples) < 5:
                    missing_examples.append({"source_line": source_line, "missing_images": missing})
                if args.require_images:
                    continue

            output_handle.write(json.dumps(fixed, ensure_ascii=False) + "\n")
            summary["output_records"] += 1

    printable: dict[str, Any] = dict(sorted(summary.items()))
    printable["output_path"] = str(args.output)
    if missing_examples:
        printable["missing_examples"] = missing_examples
    print(json.dumps(printable, ensure_ascii=False, indent=2))

    if args.require_images and summary.get("missing_images", 0):
        return 1
    if summary.get("matched_records", 0) == 0:
        print("no records matched target content", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
