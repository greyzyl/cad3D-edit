#!/usr/bin/env python3
"""Verify intermediate V1 CAD edit-candidate JSONL records."""

from __future__ import annotations

import argparse
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
    if "target_code" in record:
        errors.append("candidate record must not contain target_code")
    if "validation_report" in record:
        errors.append("candidate record must not contain validation_report")

    for key in ("candidate_id", "sample_index", "source_line", "images", "original_code", "edit_candidate"):
        if key not in record:
            errors.append(f"missing {key}")

    images = record.get("images")
    if not isinstance(images, list) or not all(isinstance(item, str) for item in images):
        errors.append("images must be a string list")

    original_code = record.get("original_code")
    if not isinstance(original_code, str) or not original_code.strip():
        errors.append("original_code must be non-empty")

    candidate = record.get("edit_candidate")
    if not isinstance(candidate, dict):
        errors.append("edit_candidate must be an object")
    else:
        required = (
            "kind",
            "call",
            "arg_index",
            "old",
            "new",
            "matched_text",
            "span_start",
            "span_end",
            "replacement",
            "scale_factor",
        )
        for key in required:
            if key not in candidate:
                errors.append(f"edit_candidate missing {key}")
        if isinstance(candidate.get("span_start"), int) and isinstance(candidate.get("span_end"), int):
            if candidate["span_start"] >= candidate["span_end"]:
                errors.append("edit_candidate span_start must be before span_end")

    return [f"line {line_number}: {error}" for error in errors]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("outputs/cad_edit_v1_candidates.jsonl"), type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    records = read_jsonl(args.input)
    errors: list[str] = []
    kind_counts: Counter[str] = Counter()

    for index, record in enumerate(records, start=1):
        errors.extend(validate_record(record, index))
        candidate = record.get("edit_candidate")
        if isinstance(candidate, dict) and isinstance(candidate.get("kind"), str):
            kind_counts[candidate["kind"]] += 1

    summary = {
        "records": len(records),
        "kind_counts": dict(sorted(kind_counts.items())),
        "errors": len(errors),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if not records:
        print("candidate dataset is empty", file=sys.stderr)
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
