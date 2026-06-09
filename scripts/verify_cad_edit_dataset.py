#!/usr/bin/env python3
"""Verify generated CAD edit dataset JSONL records."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


V1_EDIT_KEYS = ("kind", "call", "arg_index", "old", "new", "matched_text")
V2_EDIT_KEYS = (
    "edit_type",
    "target_region",
    "primitive",
    "insertion_strategy",
    "affected_region_bbox",
    "instruction_template",
)
V2_DELETE_EDIT_KEYS = (
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
V2_REPLACE_EDIT_KEYS = (
    "candidate_type",
    "edit_type",
    "old_feature",
    "new_feature",
    "insertion_strategy",
    "instruction_hints",
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
    images = record.get("images")
    if not isinstance(images, list) or not images or not all(isinstance(item, str) for item in images):
        errors.append("images must be a non-empty string list")
    elif len(images) != 3:
        errors.append(f"images should contain exactly 3 paths, got {len(images)}")

    instruction = record.get("instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        errors.append("instruction must be non-empty")

    target_code = record.get("target_code")
    if not isinstance(target_code, str) or not target_code.strip():
        errors.append("target_code must be non-empty")
    else:
        try:
            ast.parse(target_code)
        except SyntaxError as exc:
            errors.append(f"target_code syntax error: {exc}")

    hidden = record.get("hidden")
    if not isinstance(hidden, dict):
        errors.append("hidden must be an object")
        return [f"line {line_number}: {error}" for error in errors]

    original_code = hidden.get("original_code")
    if not isinstance(original_code, str) or not original_code.strip():
        errors.append("hidden.original_code must be non-empty")

    edit_record = hidden.get("edit_record")
    if not isinstance(edit_record, dict):
        errors.append("hidden.edit_record must be an object")
    else:
        is_v1_edit = isinstance(edit_record.get("kind"), str)
        is_v2_edit = isinstance(edit_record.get("edit_type"), str)
        if is_v1_edit:
            for key in V1_EDIT_KEYS:
                if key not in edit_record:
                    errors.append(f"hidden.edit_record missing {key}")
        elif is_v2_edit and (
            edit_record.get("candidate_type") == "structural_delete"
            or str(edit_record.get("edit_type", "")).startswith("delete_")
        ):
            for key in V2_DELETE_EDIT_KEYS:
                if key not in edit_record:
                    errors.append(f"hidden.edit_record missing {key}")
            if edit_record.get("candidate_type") != "structural_delete":
                errors.append("hidden.edit_record.candidate_type must be structural_delete")
            if not isinstance(edit_record.get("parameters"), dict):
                errors.append("hidden.edit_record.parameters must be an object")
        elif is_v2_edit and (
            edit_record.get("candidate_type") == "structural_replace"
            or str(edit_record.get("edit_type", "")).startswith("replace_")
        ):
            for key in V2_REPLACE_EDIT_KEYS:
                if key not in edit_record:
                    errors.append(f"hidden.edit_record missing {key}")
            if edit_record.get("candidate_type") != "structural_replace":
                errors.append("hidden.edit_record.candidate_type must be structural_replace")
            if not isinstance(edit_record.get("old_feature"), dict):
                errors.append("hidden.edit_record.old_feature must be an object")
            if not isinstance(edit_record.get("new_feature"), dict):
                errors.append("hidden.edit_record.new_feature must be an object")
            if edit_record.get("insertion_strategy", {}).get("append_csg_block") is not True:
                errors.append("hidden.edit_record.insertion_strategy.append_csg_block must be true")
        elif is_v2_edit:
            for key in V2_EDIT_KEYS:
                if key not in edit_record:
                    errors.append(f"hidden.edit_record missing {key}")
            if edit_record.get("insertion_strategy", {}).get("append_csg_block") is not True:
                errors.append("hidden.edit_record.insertion_strategy.append_csg_block must be true")
        else:
            errors.append("hidden.edit_record must be either a V1 parameter edit or V2 structural edit")

    validation_report = hidden.get("validation_report")
    if not isinstance(validation_report, dict):
        errors.append("hidden.validation_report must be an object")
    elif validation_report.get("ok") is not True:
        errors.append("hidden.validation_report.ok must be true")

    return [f"line {line_number}: {error}" for error in errors]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("outputs/cad_edit_v1.jsonl"), type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    records = read_jsonl(args.input)
    errors: list[str] = []
    kind_counts: Counter[str] = Counter()
    structural_edit_type_counts: Counter[str] = Counter()

    for index, record in enumerate(records, start=1):
        errors.extend(validate_record(record, index))
        hidden = record.get("hidden")
        if isinstance(hidden, dict):
            edit_record = hidden.get("edit_record")
            if isinstance(edit_record, dict) and isinstance(edit_record.get("kind"), str):
                kind_counts[edit_record["kind"]] += 1
            if isinstance(edit_record, dict) and isinstance(edit_record.get("edit_type"), str):
                structural_edit_type_counts[edit_record["edit_type"]] += 1

    summary = {
        "records": len(records),
        "kind_counts": dict(sorted(kind_counts.items())),
        "structural_edit_type_counts": dict(sorted(structural_edit_type_counts.items())),
        "errors": len(errors),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if not records:
        print("dataset is empty", file=sys.stderr)
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
