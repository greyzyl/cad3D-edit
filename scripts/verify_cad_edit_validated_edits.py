#!/usr/bin/env python3
"""Verify post-validation V1 CAD edit JSONL records."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


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
        "sample_index",
        "source_line",
        "images",
        "original_code",
        "edit_candidate",
        "target_code",
        "edit_record",
        "validation_report",
        "fallback_instruction",
    ):
        if key not in record:
            errors.append(f"missing {key}")

    if "instruction" in record:
        errors.append("validated edit record should not contain final instruction")

    images = record.get("images")
    if not isinstance(images, list) or not images or not all(isinstance(item, str) for item in images):
        errors.append("images must be a non-empty string list")

    original_code = record.get("original_code")
    if not isinstance(original_code, str) or not original_code.strip():
        errors.append("original_code must be non-empty")

    target_code = record.get("target_code")
    if not isinstance(target_code, str) or not target_code.strip():
        errors.append("target_code must be non-empty")
    else:
        try:
            ast.parse(target_code)
        except SyntaxError as exc:
            errors.append(f"target_code syntax error: {exc}")

    validation_report = record.get("validation_report")
    if not isinstance(validation_report, dict):
        errors.append("validation_report must be an object")
    elif validation_report.get("ok") is not True:
        errors.append("validation_report.ok must be true")

    for object_key in ("edit_candidate", "edit_record"):
        value = record.get(object_key)
        if not isinstance(value, dict):
            errors.append(f"{object_key} must be an object")

    fallback_instruction = record.get("fallback_instruction")
    if not isinstance(fallback_instruction, str) or not fallback_instruction.strip():
        errors.append("fallback_instruction must be non-empty")

    return [f"line {line_number}: {error}" for error in errors]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("outputs/cad_edit_v1_validated_edits.jsonl"), type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    records = read_jsonl(args.input)
    errors: list[str] = []
    kind_counts: Counter[str] = Counter()

    for index, record in enumerate(records, start=1):
        errors.extend(validate_record(record, index))
        edit_record = record.get("edit_record")
        if isinstance(edit_record, dict) and isinstance(edit_record.get("kind"), str):
            kind_counts[edit_record["kind"]] += 1

    summary = {
        "records": len(records),
        "kind_counts": dict(sorted(kind_counts.items())),
        "errors": len(errors),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if not records:
        print("validated edits dataset is empty", file=sys.stderr)
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
