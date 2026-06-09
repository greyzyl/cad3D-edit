#!/usr/bin/env python3
"""Merge chunked coverage audit reports."""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audit_cad_edit_coverage import markdown_report, percent, write_jsonl  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def merge_count_dict(target: Counter[str], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, (int, float)):
            target[key] += int(value)


def empty_branch(branch_name: str) -> dict[str, Any]:
    return {
        "branch": branch_name,
        "candidates": 0,
        "validated": 0,
        "failed_validation": 0,
        "by_category": defaultdict(Counter),
        "by_edit_type": defaultdict(Counter),
        "top_rejection_reasons": Counter(),
    }


def finalize_branch(branch: dict[str, Any]) -> dict[str, Any]:
    by_category = {}
    for category, counts in sorted(branch["by_category"].items()):
        candidates = counts["candidates"]
        validated = counts["validated"]
        by_category[category] = {
            "candidates": candidates,
            "validated": validated,
            "failed_validation": counts["failed_validation"],
            "pass_rate_percent": percent(validated, candidates),
        }
    by_edit_type = {}
    for edit_type, counts in sorted(branch["by_edit_type"].items()):
        candidates = counts["candidates"]
        validated = counts["validated"]
        by_edit_type[edit_type] = {
            "candidates": candidates,
            "validated": validated,
            "failed_validation": counts["failed_validation"],
            "pass_rate_percent": percent(validated, candidates),
        }
    return {
        "branch": branch["branch"],
        "candidates": branch["candidates"],
        "validated": branch["validated"],
        "failed_validation": branch["failed_validation"],
        "pass_rate_percent": percent(branch["validated"], branch["candidates"]),
        "by_category": by_category,
        "by_edit_type": by_edit_type,
        "top_rejection_reasons": dict(branch["top_rejection_reasons"].most_common(30)),
    }


def edit_type_for_sample(record: dict[str, Any]) -> str:
    hidden = record.get("hidden")
    if isinstance(hidden, dict) and isinstance(hidden.get("audit_edit_type"), str):
        return hidden["audit_edit_type"]
    return "unknown"


def choose_samples(records: list[dict[str, Any]], per_edit_type: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        buckets[edit_type_for_sample(record)].append(record)
    selected: list[dict[str, Any]] = []
    for edit_type in sorted(buckets):
        bucket = buckets[edit_type]
        if len(bucket) <= per_edit_type:
            selected.extend(bucket)
        else:
            selected.extend(rng.sample(bucket, per_edit_type))
    return selected


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks-dir", default=Path("outputs/coverage_expert3/chunks"), type=Path)
    parser.add_argument("--output-dir", default=Path("outputs/coverage_expert3"), type=Path)
    parser.add_argument("--samples-per-edit-type", default=3, type=int)
    parser.add_argument("--seed", default=0, type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    reports = sorted(args.chunks_dir.glob("chunk_*\\coverage_audit.json")) + sorted(
        args.chunks_dir.glob("chunk_*/coverage_audit.json")
    )
    # Deduplicate paths when the platform accepts both glob forms.
    reports = sorted(set(reports))
    if not reports:
        raise FileNotFoundError(f"no chunk reports found under {args.chunks_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    input_records = 0
    elapsed_seconds = 0.0
    input_path = None
    category_records: Counter[str] = Counter()
    branch_accumulators: dict[str, dict[str, Any]] = {}
    hole_overall: Counter[str] = Counter()
    hole_by_category: dict[str, Counter[str]] = defaultdict(Counter)
    sample_records: list[dict[str, Any]] = []

    for report_path in reports:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        input_records += int(report.get("input_records", 0))
        elapsed_seconds = max(elapsed_seconds, float(report.get("elapsed_seconds", 0.0)))
        input_path = input_path or report.get("input_path")
        merge_count_dict(category_records, report.get("category_records", {}))
        for branch_key, branch in report.get("branches", {}).items():
            accumulator = branch_accumulators.setdefault(branch_key, empty_branch(branch.get("branch", branch_key)))
            accumulator["candidates"] += int(branch.get("candidates", 0))
            accumulator["validated"] += int(branch.get("validated", 0))
            accumulator["failed_validation"] += int(branch.get("failed_validation", 0))
            for category, counts in branch.get("by_category", {}).items():
                merge_count_dict(accumulator["by_category"][category], counts)
            for edit_type, counts in branch.get("by_edit_type", {}).items():
                merge_count_dict(accumulator["by_edit_type"][edit_type], counts)
            merge_count_dict(accumulator["top_rejection_reasons"], branch.get("top_rejection_reasons", {}))
        diagnostics = report.get("v4_hole_diagnostics", {})
        merge_count_dict(hole_overall, diagnostics.get("overall", {}))
        for category, counts in diagnostics.get("by_category", {}).items():
            merge_count_dict(hole_by_category[category], counts)
        sample_records.extend(read_jsonl(report_path.parent / "preview_samples.jsonl"))

    final_samples = choose_samples(sample_records, args.samples_per_edit_type, args.seed)
    samples_path = args.output_dir / "preview_samples.jsonl"
    write_jsonl(samples_path, final_samples)

    merged = {
        "input_path": input_path,
        "input_records": input_records,
        "start_index": 1,
        "limit": None,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "category_records": dict(sorted(category_records.items())),
        "branches": {key: finalize_branch(branch_accumulators[key]) for key in sorted(branch_accumulators)},
        "v4_hole_diagnostics": {
            "overall": dict(hole_overall.most_common()),
            "by_category": {category: dict(counts.most_common()) for category, counts in sorted(hole_by_category.items())},
        },
        "sample_seen_counts": Counter(edit_type_for_sample(record) for record in sample_records),
        "sample_records_path": str(samples_path),
        "render_gallery_path": str(args.output_dir / "preview_gallery" / "index.html"),
        "chunk_reports": [str(path) for path in reports],
    }
    merged["sample_seen_counts"] = dict(sorted(merged["sample_seen_counts"].items()))
    (args.output_dir / "coverage_audit.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "coverage_audit.md").write_text(markdown_report(merged), encoding="utf-8", newline="\n")
    print(json.dumps(merged, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
