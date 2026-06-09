#!/usr/bin/env python3
"""Verify V2 structural delete-candidate JSONL records."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_DELETE_KEYS = (
    "candidate_type",
    "edit_type",
    "source_api",
    "block_span_start",
    "block_span_end",
    "block_text",
    "parameters",
    "expected_effect",
    "instruction_hints",
)

SUPPORTED_DELETE_EDIT_TYPES = {
    "delete_hole",
    "delete_circular_cutout",
    "delete_polygonal_cutout",
    "delete_fillet",
    "delete_chamfer",
}
SUPPORTED_SOURCE_APIS = {"hole", "cut", "cut_polygon", "fillet", "chamfer"}


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
    for key in ("candidate_id", "sample_index", "source_line", "images", "original_code", "original_geometry", "delete_candidate"):
        if key not in record:
            errors.append(f"missing {key}")
    if "target_code" in record:
        errors.append("delete candidate must not contain target_code")
    if "validation_report" in record:
        errors.append("delete candidate must not contain validation_report")

    original_code = record.get("original_code")
    if not isinstance(original_code, str) or not original_code.strip():
        errors.append("original_code must be non-empty")

    candidate = record.get("delete_candidate")
    if not isinstance(candidate, dict):
        errors.append("delete_candidate must be an object")
    else:
        for key in REQUIRED_DELETE_KEYS:
            if key not in candidate:
                errors.append(f"delete_candidate missing {key}")
        if candidate.get("candidate_type") != "structural_delete":
            errors.append("delete_candidate.candidate_type must be structural_delete")
        edit_type = candidate.get("edit_type")
        if edit_type not in SUPPORTED_DELETE_EDIT_TYPES:
            errors.append("delete_candidate.edit_type is unsupported")
        if candidate.get("source_api") not in SUPPORTED_SOURCE_APIS:
            errors.append("delete_candidate.source_api is unsupported")
        start = candidate.get("block_span_start")
        end = candidate.get("block_span_end")
        block_text = candidate.get("block_text")
        if not isinstance(start, int) or not isinstance(end, int) or start >= end:
            errors.append("delete_candidate block span must be a valid integer range")
        elif isinstance(original_code, str) and isinstance(block_text, str) and original_code[start:end] != block_text:
            errors.append("delete_candidate block span does not match block_text")
        parameters = candidate.get("parameters")
        if not isinstance(parameters, dict):
            errors.append("delete_candidate.parameters must be an object")
        elif edit_type in {"delete_hole", "delete_circular_cutout"}:
            if not isinstance(parameters.get("diameter"), (int, float)):
                errors.append("delete_candidate.parameters.diameter must be numeric")
        elif edit_type == "delete_polygonal_cutout":
            if not isinstance(parameters.get("sides"), int) or not isinstance(parameters.get("radius"), (int, float)):
                errors.append("delete_candidate.parameters.sides and radius are required for polygonal cutout")
        elif edit_type == "delete_fillet":
            if not isinstance(parameters.get("radius"), (int, float)):
                errors.append("delete_candidate.parameters.radius must be numeric for fillet")
        elif edit_type == "delete_chamfer":
            if not isinstance(parameters.get("distance"), (int, float)):
                errors.append("delete_candidate.parameters.distance must be numeric for chamfer")

    return [f"line {line_number}: {error}" for error in errors]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("outputs/cad_edit_v2_delete_candidates.jsonl"), type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    records = read_jsonl(args.input)
    errors: list[str] = []
    counts: Counter[str] = Counter()
    for index, record in enumerate(records, start=1):
        errors.extend(validate_record(record, index))
        candidate = record.get("delete_candidate")
        if isinstance(candidate, dict) and isinstance(candidate.get("edit_type"), str):
            counts[candidate["edit_type"]] += 1

    summary = {"records": len(records), "edit_type_counts": dict(sorted(counts.items())), "errors": len(errors)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not records:
        print("delete candidates dataset is empty", file=sys.stderr)
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
