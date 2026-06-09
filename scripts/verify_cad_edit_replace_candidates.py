#!/usr/bin/env python3
"""Verify V4 structural replace-candidate JSONL records."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_REPLACE_KEYS = (
    "candidate_type",
    "edit_type",
    "old_feature",
    "new_feature",
    "insertion_strategy",
    "instruction_template",
    "instruction_hints",
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


def validate_code(value: Any, label: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{label} must be non-empty"]
    try:
        ast.parse(value)
    except SyntaxError as exc:
        return [f"{label} syntax error: {exc}"]
    return []


def validate_record(record: dict[str, Any], line_number: int) -> list[str]:
    errors: list[str] = []
    for key in (
        "candidate_id",
        "sample_index",
        "source_line",
        "images",
        "original_code",
        "intermediate_code",
        "target_code",
        "delete_validation_report",
        "replace_candidate",
        "validation_report",
    ):
        if key not in record:
            errors.append(f"missing {key}")

    images = record.get("images")
    if not isinstance(images, list) or not all(isinstance(item, str) for item in images):
        errors.append("images must be a string list")

    errors.extend(validate_code(record.get("original_code"), "original_code"))
    errors.extend(validate_code(record.get("intermediate_code"), "intermediate_code"))
    errors.extend(validate_code(record.get("target_code"), "target_code"))

    replace_candidate = record.get("replace_candidate")
    if not isinstance(replace_candidate, dict):
        errors.append("replace_candidate must be an object")
    else:
        for key in REQUIRED_REPLACE_KEYS:
            if key not in replace_candidate:
                errors.append(f"replace_candidate missing {key}")
        if replace_candidate.get("candidate_type") != "structural_replace":
            errors.append("replace_candidate.candidate_type must be structural_replace")
        if replace_candidate.get("edit_type") != "replace_hole_with_slot":
            errors.append("replace_candidate.edit_type must be replace_hole_with_slot")
        old_feature = replace_candidate.get("old_feature")
        if not isinstance(old_feature, dict):
            errors.append("replace_candidate.old_feature must be an object")
        elif old_feature.get("edit_type") != "delete_hole":
            errors.append("replace_candidate.old_feature.edit_type must be delete_hole")
        new_feature = replace_candidate.get("new_feature")
        if not isinstance(new_feature, dict):
            errors.append("replace_candidate.new_feature must be an object")
        else:
            if new_feature.get("feature") != "rectangular_slot":
                errors.append("replace_candidate.new_feature.feature must be rectangular_slot")
            errors.extend(validate_bbox(new_feature.get("affected_region_bbox"), "replace_candidate.new_feature.affected_region_bbox"))
        strategy = replace_candidate.get("insertion_strategy")
        if not isinstance(strategy, dict) or strategy.get("append_csg_block") is not True:
            errors.append("replace_candidate.insertion_strategy.append_csg_block must be true")

    delete_report = record.get("delete_validation_report")
    if not isinstance(delete_report, dict) or delete_report.get("ok") is not True:
        errors.append("delete_validation_report.ok must be true")

    report = record.get("validation_report")
    if not isinstance(report, dict):
        errors.append("validation_report must be an object")
    elif report.get("mode") != "cadquery_structural_replace":
        errors.append("validation_report.mode must be cadquery_structural_replace")

    return [f"line {line_number}: {error}" for error in errors]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("outputs/cad_edit_v4_replace_candidates.jsonl"), type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    records = read_jsonl(args.input)
    errors: list[str] = []
    counts: Counter[str] = Counter()
    for index, record in enumerate(records, start=1):
        errors.extend(validate_record(record, index))
        replace_candidate = record.get("replace_candidate")
        if isinstance(replace_candidate, dict) and isinstance(replace_candidate.get("edit_type"), str):
            counts[replace_candidate["edit_type"]] += 1

    summary = {"records": len(records), "edit_type_counts": dict(sorted(counts.items())), "errors": len(errors)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not records:
        print("replace candidates dataset is empty", file=sys.stderr)
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
