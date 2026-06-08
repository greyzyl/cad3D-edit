#!/usr/bin/env python3
"""Verify V2 validated structural edit JSONL records."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_CHECKS = (
    "original_executes",
    "edited_executes",
    "edited_non_empty",
    "volume_direction_ok",
    "bbox_growth_ok",
    "bbox_not_collapsed",
    "locality_ok",
    "volume_delta_matches_changed_region",
)


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


def validate_record(record: dict[str, Any], line_number: int) -> list[str]:
    errors: list[str] = []
    for key in (
        "candidate_id",
        "images",
        "original_code",
        "structural_candidate",
        "target_code",
        "edit_record",
        "validation_report",
        "fallback_instruction",
    ):
        if key not in record:
            errors.append(f"missing {key}")

    if "instruction" in record:
        errors.append("validated structural edit must not contain final instruction")

    if not isinstance(record.get("original_code"), str) or not record.get("original_code", "").strip():
        errors.append("original_code must be non-empty")

    target_code = record.get("target_code")
    if not isinstance(target_code, str) or not target_code.strip():
        errors.append("target_code must be non-empty")
    else:
        try:
            ast.parse(target_code)
        except SyntaxError as exc:
            errors.append(f"target_code syntax error: {exc}")

    structural = record.get("structural_candidate")
    if not isinstance(structural, dict):
        errors.append("structural_candidate must be an object")
    else:
        edit_type = structural.get("edit_type")
        if not isinstance(edit_type, str) or not edit_type.startswith("add_"):
            errors.append("structural_candidate.edit_type must be add-only")
        strategy = structural.get("insertion_strategy")
        if not isinstance(strategy, dict) or strategy.get("append_csg_block") is not True:
            errors.append("structural_candidate.insertion_strategy.append_csg_block must be true")

    report = record.get("validation_report")
    if not isinstance(report, dict):
        errors.append("validation_report must be an object")
    else:
        if report.get("ok") is not True:
            errors.append("validation_report.ok must be true")
        if report.get("mode") != "cadquery_structural":
            errors.append("validation_report.mode must be cadquery_structural")
        checks = report.get("checks")
        if not isinstance(checks, dict):
            errors.append("validation_report.checks must be an object")
        else:
            for key in REQUIRED_CHECKS:
                if checks.get(key) is not True:
                    errors.append(f"validation_report.checks.{key} must be true")
        volume_delta = report.get("volume_delta")
        if not isinstance(volume_delta, (int, float)) or volume_delta >= 0:
            errors.append("validation_report.volume_delta must be negative for V2 subtractive add edits")

    if not isinstance(record.get("fallback_instruction"), str) or not record.get("fallback_instruction", "").strip():
        errors.append("fallback_instruction must be non-empty")

    return [f"line {line_number}: {error}" for error in errors]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("outputs/cad_edit_v2_validated_structural_edits.jsonl"), type=Path)
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
        print("validated structural edits dataset is empty", file=sys.stderr)
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
