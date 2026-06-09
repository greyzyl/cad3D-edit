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
SUPPORTED_REPLACE_EDIT_TYPES = {
    "replace_hole_with_slot",
    "replace_loop_holes_with_slots",
    "replace_circular_cutout_with_slot",
    "replace_polygonal_cutout_with_slot",
    "replace_circular_cutout_with_polygonal_cutout",
    "replace_polygonal_cutout_with_circular_cutout",
    "replace_chamfer_with_fillet",
    "replace_fillet_with_chamfer",
}
SLOT_REPLACE_TYPES = {
    "replace_hole_with_slot",
    "replace_loop_holes_with_slots",
    "replace_circular_cutout_with_slot",
    "replace_polygonal_cutout_with_slot",
}
DIRECT_CUTOUT_REPLACE_TYPES = {
    "replace_circular_cutout_with_polygonal_cutout",
    "replace_polygonal_cutout_with_circular_cutout",
}
FINISHING_REPLACE_TYPES = {
    "replace_chamfer_with_fillet",
    "replace_fillet_with_chamfer",
}


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
        edit_type = replace_candidate.get("edit_type")
        if edit_type not in SUPPORTED_REPLACE_EDIT_TYPES:
            errors.append("replace_candidate.edit_type must be a supported V4 replace edit")
        old_feature = replace_candidate.get("old_feature")
        if not isinstance(old_feature, dict):
            errors.append("replace_candidate.old_feature must be an object")
        elif edit_type in SLOT_REPLACE_TYPES and old_feature.get("edit_type") not in {
            "delete_hole",
            "delete_circular_cutout",
            "delete_polygonal_cutout",
        }:
            errors.append("slot replace old_feature.edit_type must be delete_hole/delete_circular_cutout/delete_polygonal_cutout")
        elif edit_type == "replace_circular_cutout_with_polygonal_cutout" and old_feature.get("edit_type") != "delete_circular_cutout":
            errors.append("circular-to-polygon replace old_feature.edit_type must be delete_circular_cutout")
        elif edit_type == "replace_polygonal_cutout_with_circular_cutout" and old_feature.get("edit_type") != "delete_polygonal_cutout":
            errors.append("polygon-to-circular replace old_feature.edit_type must be delete_polygonal_cutout")
        elif edit_type == "replace_chamfer_with_fillet" and old_feature.get("edit_type") != "delete_chamfer":
            errors.append("chamfer-to-fillet replace old_feature.edit_type must be delete_chamfer")
        elif edit_type == "replace_fillet_with_chamfer" and old_feature.get("edit_type") != "delete_fillet":
            errors.append("fillet-to-chamfer replace old_feature.edit_type must be delete_fillet")
        new_feature = replace_candidate.get("new_feature")
        if not isinstance(new_feature, dict):
            errors.append("replace_candidate.new_feature must be an object")
        elif edit_type in SLOT_REPLACE_TYPES:
            if new_feature.get("feature") != "rectangular_slot":
                errors.append("replace_candidate.new_feature.feature must be rectangular_slot")
            errors.extend(validate_bbox(new_feature.get("affected_region_bbox"), "replace_candidate.new_feature.affected_region_bbox"))
        elif edit_type == "replace_circular_cutout_with_polygonal_cutout":
            if new_feature.get("feature_type") != "polygonal_cutout" or new_feature.get("sides") != 6:
                errors.append("replace_candidate.new_feature must describe a six-sided polygonal_cutout")
        elif edit_type == "replace_polygonal_cutout_with_circular_cutout":
            if new_feature.get("feature_type") != "circular_cutout":
                errors.append("replace_candidate.new_feature must describe a circular_cutout")
        elif edit_type == "replace_chamfer_with_fillet":
            if new_feature.get("feature_type") != "fillet":
                errors.append("replace_candidate.new_feature must describe a fillet")
        elif edit_type == "replace_fillet_with_chamfer":
            if new_feature.get("feature_type") != "chamfer":
                errors.append("replace_candidate.new_feature must describe a chamfer")
        strategy = replace_candidate.get("insertion_strategy")
        if not isinstance(strategy, dict):
            errors.append("replace_candidate.insertion_strategy must be an object")
        elif edit_type in SLOT_REPLACE_TYPES and strategy.get("append_csg_block") is not True:
            errors.append("slot replace insertion_strategy.append_csg_block must be true")
        elif edit_type in DIRECT_CUTOUT_REPLACE_TYPES | FINISHING_REPLACE_TYPES and strategy.get("method") != "direct_source_replacement":
            errors.append("direct replace insertion_strategy.method must be direct_source_replacement")

    delete_report = record.get("delete_validation_report")
    if not isinstance(delete_report, dict):
        errors.append("delete_validation_report must be an object")

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
