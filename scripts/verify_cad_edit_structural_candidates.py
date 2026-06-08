#!/usr/bin/env python3
"""Verify V2 structural edit-candidate JSONL records."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_STRUCTURAL_KEYS = (
    "edit_type",
    "target_region",
    "primitive",
    "insertion_strategy",
    "affected_region_bbox",
    "instruction_template",
)
REQUIRED_BBOX_KEYS = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
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
            records.append(record)
    return records


def validate_bbox(value: Any, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    for key in REQUIRED_BBOX_KEYS:
        if not isinstance(value.get(key), (int, float)):
            errors.append(f"{label}.{key} must be numeric")
    if not errors:
        for axis in ("x", "y", "z"):
            if value[f"{axis}min"] >= value[f"{axis}max"]:
                errors.append(f"{label}.{axis}min must be smaller than {axis}max")
    return errors


def validate_record(record: dict[str, Any], line_number: int) -> list[str]:
    errors: list[str] = []
    for key in ("candidate_id", "sample_index", "source_line", "images", "original_code", "original_geometry", "structural_candidate"):
        if key not in record:
            errors.append(f"missing {key}")

    if "target_code" in record:
        errors.append("structural candidate must not contain target_code")
    if "validation_report" in record:
        errors.append("structural candidate must not contain validation_report")

    images = record.get("images")
    if not isinstance(images, list) or not all(isinstance(item, str) for item in images):
        errors.append("images must be a string list")

    if not isinstance(record.get("original_code"), str) or not record.get("original_code", "").strip():
        errors.append("original_code must be non-empty")

    geometry = record.get("original_geometry")
    if not isinstance(geometry, dict):
        errors.append("original_geometry must be an object")
    else:
        if not isinstance(geometry.get("volume"), (int, float)) or geometry.get("volume", 0) <= 0:
            errors.append("original_geometry.volume must be positive")
        errors.extend(validate_bbox(geometry.get("bbox"), "original_geometry.bbox"))

    structural = record.get("structural_candidate")
    if not isinstance(structural, dict):
        errors.append("structural_candidate must be an object")
    else:
        for key in REQUIRED_STRUCTURAL_KEYS:
            if key not in structural:
                errors.append(f"structural_candidate missing {key}")
        if not isinstance(structural.get("edit_type"), str) or not structural.get("edit_type", "").startswith("add_"):
            errors.append("structural_candidate.edit_type must be add-only")
        errors.extend(validate_bbox(structural.get("affected_region_bbox"), "structural_candidate.affected_region_bbox"))
        if not isinstance(structural.get("target_region"), dict):
            errors.append("structural_candidate.target_region must be an object")
        if not isinstance(structural.get("primitive"), dict):
            errors.append("structural_candidate.primitive must be an object")
        strategy = structural.get("insertion_strategy")
        if not isinstance(strategy, dict):
            errors.append("structural_candidate.insertion_strategy must be an object")
        elif strategy.get("append_csg_block") is not True:
            errors.append("insertion_strategy.append_csg_block must be true")

    return [f"line {line_number}: {error}" for error in errors]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("outputs/cad_edit_v2_structural_candidates.jsonl"), type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    records = read_jsonl(args.input)
    errors: list[str] = []
    counts: Counter[str] = Counter()

    for index, record in enumerate(records, start=1):
        errors.extend(validate_record(record, index))
        structural = record.get("structural_candidate")
        if isinstance(structural, dict) and isinstance(structural.get("edit_type"), str):
            counts[structural["edit_type"]] += 1

    summary = {"records": len(records), "edit_type_counts": dict(sorted(counts.items())), "errors": len(errors)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not records:
        print("structural candidates dataset is empty", file=sys.stderr)
        return 1
    if errors:
        for error in errors[:50]:
            print(error, file=sys.stderr)
        if len(errors) > 50:
            print(f"... {len(errors) - 50} more errors", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
