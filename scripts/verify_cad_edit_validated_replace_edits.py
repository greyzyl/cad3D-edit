#!/usr/bin/env python3
"""Verify V4 validated structural replace edit JSONL records."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SLOT_REQUIRED_CHECKS = (
    "delete_stage_ok",
    "original_executes",
    "deleted_executes",
    "replaced_executes",
    "replaced_non_empty",
    "delete_volume_increased",
    "slot_volume_decreased_from_deleted",
    "bbox_stable_original_to_deleted",
    "bbox_stable_deleted_to_replaced",
    "bbox_not_collapsed",
    "slot_changed_region_non_empty",
    "slot_changed_region_local",
    "slot_near_deleted_hole",
    "final_change_local",
    "final_has_geometric_change",
)
CUTOUT_REQUIRED_CHECKS = (
    "delete_stage_ok",
    "original_executes",
    "deleted_executes",
    "replaced_executes",
    "replaced_non_empty",
    "bbox_stable_original_to_deleted",
    "bbox_stable_original_to_replaced",
    "bbox_not_collapsed",
    "new_feature_changed_region_non_empty",
    "new_feature_changed_region_local",
    "new_feature_near_old_feature",
    "final_change_local",
    "final_has_geometric_change",
)
FINISHING_REQUIRED_CHECKS = (
    "original_executes",
    "replaced_executes",
    "replaced_non_empty",
    "bbox_stable",
    "bbox_not_collapsed",
    "volume_changed_nontrivially",
    "geometry_changed_nontrivially",
)
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
        "images",
        "original_code",
        "intermediate_code",
        "replace_candidate",
        "target_code",
        "edit_record",
        "validation_report",
        "fallback_instruction",
    ):
        if key not in record:
            errors.append(f"missing {key}")

    if "instruction" in record:
        errors.append("validated replace edit must not contain final instruction")

    errors.extend(validate_code(record.get("original_code"), "original_code"))
    errors.extend(validate_code(record.get("intermediate_code"), "intermediate_code"))
    errors.extend(validate_code(record.get("target_code"), "target_code"))

    replace_candidate = record.get("replace_candidate")
    edit_type = None
    if not isinstance(replace_candidate, dict):
        errors.append("replace_candidate must be an object")
    else:
        if replace_candidate.get("candidate_type") != "structural_replace":
            errors.append("replace_candidate.candidate_type must be structural_replace")
        edit_type = replace_candidate.get("edit_type")
        if edit_type not in SUPPORTED_REPLACE_EDIT_TYPES:
            errors.append("replace_candidate.edit_type must be a supported V4 replace edit")
        if not isinstance(replace_candidate.get("old_feature"), dict):
            errors.append("replace_candidate.old_feature must be an object")
        new_feature = replace_candidate.get("new_feature")
        if not isinstance(new_feature, dict):
            errors.append("replace_candidate.new_feature must be an object")
        elif edit_type in SLOT_REPLACE_TYPES and new_feature.get("feature") != "rectangular_slot":
            errors.append("replace_candidate.new_feature.feature must be rectangular_slot")
        elif edit_type == "replace_circular_cutout_with_polygonal_cutout" and new_feature.get("feature_type") != "polygonal_cutout":
            errors.append("replace_candidate.new_feature must describe a polygonal_cutout")
        elif edit_type == "replace_polygonal_cutout_with_circular_cutout" and new_feature.get("feature_type") != "circular_cutout":
            errors.append("replace_candidate.new_feature must describe a circular_cutout")
        elif edit_type == "replace_chamfer_with_fillet" and new_feature.get("feature_type") != "fillet":
            errors.append("replace_candidate.new_feature must describe a fillet")
        elif edit_type == "replace_fillet_with_chamfer" and new_feature.get("feature_type") != "chamfer":
            errors.append("replace_candidate.new_feature must describe a chamfer")
        strategy = replace_candidate.get("insertion_strategy")
        if not isinstance(strategy, dict):
            errors.append("replace_candidate.insertion_strategy must be an object")
        elif edit_type in SLOT_REPLACE_TYPES and strategy.get("append_csg_block") is not True:
            errors.append("slot replace insertion_strategy.append_csg_block must be true")
        elif edit_type in DIRECT_CUTOUT_REPLACE_TYPES | FINISHING_REPLACE_TYPES and strategy.get("method") != "direct_source_replacement":
            errors.append("direct replace insertion_strategy.method must be direct_source_replacement")

    report = record.get("validation_report")
    if not isinstance(report, dict):
        errors.append("validation_report must be an object")
    else:
        if report.get("ok") is not True:
            errors.append("validation_report.ok must be true")
        if report.get("mode") != "cadquery_structural_replace":
            errors.append("validation_report.mode must be cadquery_structural_replace")
        checks = report.get("checks")
        if not isinstance(checks, dict):
            errors.append("validation_report.checks must be an object")
        else:
            if edit_type in DIRECT_CUTOUT_REPLACE_TYPES:
                required_checks = CUTOUT_REQUIRED_CHECKS
            elif edit_type in FINISHING_REPLACE_TYPES:
                required_checks = FINISHING_REQUIRED_CHECKS
            else:
                required_checks = SLOT_REQUIRED_CHECKS
            for key in required_checks:
                if checks.get(key) is not True:
                    errors.append(f"validation_report.checks.{key} must be true")
        delete_delta = report.get("delete_volume_delta")
        slot_delta = report.get("slot_volume_delta")
        if edit_type in SLOT_REPLACE_TYPES and (not isinstance(delete_delta, (int, float)) or delete_delta <= 0):
            errors.append("validation_report.delete_volume_delta must be positive")
        if edit_type in SLOT_REPLACE_TYPES and (not isinstance(slot_delta, (int, float)) or slot_delta >= 0):
            errors.append("validation_report.slot_volume_delta must be negative")

    if not isinstance(record.get("fallback_instruction"), str) or not record.get("fallback_instruction", "").strip():
        errors.append("fallback_instruction must be non-empty")

    return [f"line {line_number}: {error}" for error in errors]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("outputs/cad_edit_v4_validated_replace_edits.jsonl"), type=Path)
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
        print("validated replace edits dataset is empty", file=sys.stderr)
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
