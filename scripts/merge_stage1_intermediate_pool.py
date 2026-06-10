#!/usr/bin/env python3
"""Merge chunked Stage 1 intermediate pool outputs."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import generate_stage1_intermediate_pool as stage1  # noqa: E402


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield json.loads(stripped)


def load_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_count_table(target: dict[str, Counter[str]], source: dict[str, Any]) -> None:
    for key, counts in source.items():
        bucket = target[key]
        for count_key in ("candidates", "validated", "failed_validation"):
            value = counts.get(count_key)
            if isinstance(value, int):
                bucket[count_key] += value


def merged_branch_dict(branch: str, summaries: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = 0
    validated = 0
    failed = 0
    by_edit_type: dict[str, Counter[str]] = defaultdict(Counter)
    by_category: dict[str, Counter[str]] = defaultdict(Counter)
    reasons: Counter[str] = Counter()
    for summary in summaries:
        data = summary["branches"].get(branch)
        if not isinstance(data, dict):
            continue
        candidates += int(data.get("candidates", 0))
        validated += int(data.get("validated", 0))
        failed += int(data.get("failed_validation", 0))
        merge_count_table(by_edit_type, data.get("by_edit_type", {}))
        merge_count_table(by_category, data.get("by_category", {}))
        reasons.update(data.get("top_rejection_reasons", {}))

    edit_types = {}
    for edit_type, counts in sorted(by_edit_type.items()):
        edit_types[edit_type] = {
            "candidates": counts["candidates"],
            "validated": counts["validated"],
            "failed_validation": counts["failed_validation"],
            "pass_rate_percent": stage1.pass_rate(counts["candidates"], counts["validated"]),
        }
    categories = {}
    for category, counts in sorted(by_category.items()):
        categories[category] = {
            "candidates": counts["candidates"],
            "validated": counts["validated"],
            "failed_validation": counts["failed_validation"],
            "pass_rate_percent": stage1.pass_rate(counts["candidates"], counts["validated"]),
        }
    return {
        "branch": branch,
        "candidates": candidates,
        "validated": validated,
        "failed_validation": failed,
        "pass_rate_percent": stage1.pass_rate(candidates, validated),
        "by_edit_type": edit_types,
        "by_category": categories,
        "top_rejection_reasons": dict(reasons.most_common(30)),
    }


def structural_ratio(branches: dict[str, dict[str, Any]]) -> dict[str, Any]:
    counts = {branch: int(branches.get(branch, {}).get("validated", 0)) for branch in stage1.STRUCTURAL_BRANCHES}
    positive = [count for count in counts.values() if count > 0]
    max_to_min = None
    passes = False
    if positive:
        max_to_min = round(max(positive) / min(positive), 4)
        passes = max_to_min <= 9
    return {
        "validated_counts": counts,
        "max_to_min_ratio": max_to_min,
        "passes_max_ratio_lte_9": passes,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks-dir", default=Path("outputs/stage1_chunks"), type=Path)
    parser.add_argument("--output-dir", default=Path("outputs/stage1"), type=Path)
    parser.add_argument("--preview-samples-per-edit-type", default=5, type=int)
    parser.add_argument("--no-preview", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    chunk_dirs = sorted(path for path in args.chunks_dir.iterdir() if path.is_dir())
    if not chunk_dirs:
        raise ValueError(f"no chunk directories found in {args.chunks_dir}")

    summaries = []
    for chunk_dir in chunk_dirs:
        summary_path = chunk_dir / stage1.SUMMARY_NAME
        if not summary_path.exists():
            raise FileNotFoundError(f"missing chunk summary: {summary_path}")
        summaries.append(load_summary(summary_path))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = stage1.branch_output_paths(args.output_dir)
    preview_samples: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    handles: dict[str, Any] = {}
    try:
        for branch in stage1.BRANCHES:
            handles[branch] = paths[branch].open("w", encoding="utf-8", newline="\n")
        handles["all"] = paths["all"].open("w", encoding="utf-8", newline="\n")
        for chunk_dir in chunk_dirs:
            for branch in stage1.BRANCHES:
                branch_path = chunk_dir / stage1.BRANCH_OUTPUT_NAMES[branch]
                if not branch_path.exists():
                    continue
                for record in read_jsonl(branch_path):
                    line = json.dumps(record, ensure_ascii=False)
                    handles[branch].write(line + "\n")
                    handles["all"].write(line + "\n")
                    key = (record["branch"], record["edit_type"])
                    bucket = preview_samples[key]
                    if len(bucket) < args.preview_samples_per_edit_type:
                        bucket.append(record)
    finally:
        for handle in handles.values():
            handle.close()

    branches = {branch: merged_branch_dict(branch, summaries) for branch in stage1.BRANCHES}
    output_paths = {branch: str(paths[branch]) for branch in stage1.BRANCHES}
    output_paths["all_validated_intermediate"] = str(paths["all"])
    output_paths["stage1_summary"] = str(paths["summary"])
    output_paths["stage1_coverage"] = str(paths["coverage"])
    output_paths["preview_gallery"] = str(paths["preview_gallery"])
    preview_records = [record for key in sorted(preview_samples) for record in preview_samples[key]]
    preview_report = None
    if not args.no_preview:
        preview_report = stage1.render_preview_gallery(preview_records, args.output_dir / "preview_gallery")

    summary = {
        "input_path": summaries[0].get("input_path"),
        "input_records": sum(int(summary.get("input_records", 0)) for summary in summaries),
        "start_index": min(int(summary.get("start_index", 1)) for summary in summaries),
        "limit": None,
        "elapsed_seconds": round(sum(float(summary.get("elapsed_seconds", 0.0)) for summary in summaries), 3),
        "total_validated": sum(int(branch["validated"]) for branch in branches.values()),
        "branches": branches,
        "structural_add_delete_replace_ratio": structural_ratio(branches),
        "outputs": output_paths,
        "preview": preview_report,
        "generation_meta": dict(stage1.GENERATION_META),
        "chunk_reports": [str(chunk_dir / stage1.SUMMARY_NAME) for chunk_dir in chunk_dirs],
    }
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    stage1.write_coverage_md(summary, paths["coverage"])
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
