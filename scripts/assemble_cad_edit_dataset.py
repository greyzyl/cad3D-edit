#!/usr/bin/env python3
"""Assemble final CAD edit dataset from validated edits and generated instructions."""

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


def load_instructions(path: Path) -> dict[str, dict[str, Any]]:
    instructions: dict[str, dict[str, Any]] = {}
    for record in read_jsonl(path):
        candidate_id = record.get("candidate_id")
        instruction = record.get("instruction")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError(f"{path}: instruction row missing candidate_id")
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError(f"{path}: instruction row {candidate_id} missing instruction")
        instructions[candidate_id] = record
    return instructions


def build_final_record(
    validated: dict[str, Any],
    instruction_record: dict[str, Any] | None,
    allow_fallback: bool,
) -> dict[str, Any] | None:
    candidate_id = validated.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("validated edit missing candidate_id")

    instruction = None
    instruction_meta = None
    if instruction_record is not None:
        instruction = instruction_record["instruction"]
        meta = instruction_record.get("instruction_meta")
        if isinstance(meta, dict):
            instruction_meta = meta
    elif allow_fallback:
        instruction = validated.get("fallback_instruction")
        instruction_meta = {"generator": "fallback_template", "fallback_used": True}
    else:
        return None

    if not isinstance(instruction, str) or not instruction.strip():
        return None

    hidden: dict[str, Any] = {
        "candidate_id": candidate_id,
        "original_code": validated["original_code"],
        "edit_record": validated["edit_record"],
        "validation_report": validated["validation_report"],
    }
    if instruction_meta is not None:
        hidden["instruction_meta"] = instruction_meta

    return {
        "images": validated["images"],
        "instruction": instruction,
        "target_code": validated["target_code"],
        "hidden": hidden,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validated-input", default=Path("outputs/cad_edit_v1_validated_edits.jsonl"), type=Path)
    parser.add_argument("--instructions-input", default=Path("outputs/cad_edit_v1_instructions.jsonl"), type=Path)
    parser.add_argument("--output", default=Path("outputs/cad_edit_v1.jsonl"), type=Path)
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Use fallback template instructions when MLLM instructions are missing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    validated_records = read_jsonl(args.validated_input)
    instruction_records = load_instructions(args.instructions_input)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary: Counter[str] = Counter()
    with args.output.open("w", encoding="utf-8", newline="\n") as output_handle:
        for validated in validated_records:
            summary["validated_records"] += 1
            candidate_id = validated.get("candidate_id")
            instruction_record = instruction_records.get(candidate_id) if isinstance(candidate_id, str) else None
            if instruction_record is None:
                summary["missing_instruction"] += 1
            final_record = build_final_record(validated, instruction_record, args.allow_fallback)
            if final_record is None:
                summary["skipped_records"] += 1
                continue
            meta = final_record.get("hidden", {}).get("instruction_meta")
            if isinstance(meta, dict) and meta.get("fallback_used"):
                summary["fallback_records"] += 1
            else:
                summary["mllm_instruction_records"] += 1
            output_handle.write(json.dumps(final_record, ensure_ascii=False) + "\n")
            summary["output_records"] += 1

    printable_summary = dict(sorted(summary.items()))
    printable_summary["output_path"] = str(args.output)
    print(json.dumps(printable_summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
