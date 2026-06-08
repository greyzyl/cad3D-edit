#!/usr/bin/env python3
"""Verify MLLM-generated CAD edit instruction JSONL records."""

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
    candidate_id = record.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        errors.append("candidate_id must be non-empty")

    instruction = record.get("instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        errors.append("instruction must be non-empty")

    meta = record.get("instruction_meta")
    if not isinstance(meta, dict):
        errors.append("instruction_meta must be an object")
    else:
        if meta.get("included_target_code") is not False:
            errors.append("instruction_meta.included_target_code must be false")
        if meta.get("used_candidate") is not True:
            errors.append("instruction_meta.used_candidate must be true")
        if meta.get("used_original_code") is not True:
            errors.append("instruction_meta.used_original_code must be true")

    if "target_code" in record:
        errors.append("instruction record must not contain target_code")

    return [f"line {line_number}: {error}" for error in errors]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("outputs/cad_edit_v1_instructions.jsonl"), type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    records = read_jsonl(args.input)
    errors: list[str] = []
    generator_counts: Counter[str] = Counter()

    for index, record in enumerate(records, start=1):
        errors.extend(validate_record(record, index))
        meta = record.get("instruction_meta")
        if isinstance(meta, dict) and isinstance(meta.get("generator"), str):
            generator_counts[meta["generator"]] += 1

    summary = {
        "records": len(records),
        "generator_counts": dict(sorted(generator_counts.items())),
        "errors": len(errors),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if not records:
        print("instruction dataset is empty", file=sys.stderr)
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
