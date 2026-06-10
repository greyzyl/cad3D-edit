#!/usr/bin/env python3
"""Create a capped CAD edit subset from Stage 1.5 and Stage 2 outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SPLITS = ("train", "val", "test")
BRANCHES = ("v1_parameter", "v2_add", "v3_delete", "v4_replace")
FAMILY_BY_BRANCH = {
    "v1_parameter": "parameter",
    "v2_add": "structural_add",
    "v3_delete": "structural_delete",
    "v4_replace": "structural_replace",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected object")
            records.append(value)
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def stable_score(seed: int, *parts: Any) -> float:
    text = "|".join(str(part) for part in (seed, *parts))
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(0xFFFFFFFFFFFFFFFF)


def category_from_images(record: dict[str, Any]) -> str:
    images = record.get("images")
    if not isinstance(images, list) or not images:
        return "Unknown"
    first = str(images[0]).replace("\\", "/")
    parts = [part for part in first.split("/") if part]
    if "image" in parts:
        index = parts.index("image")
        if index + 1 < len(parts):
            return parts[index + 1]
    return "Unknown"


def validation_score(record: dict[str, Any]) -> int:
    report = record.get("validation_report")
    if not isinstance(report, dict):
        return 0
    score = 0
    if report.get("ok") is True:
        score += 10
    checks = report.get("checks")
    if isinstance(checks, dict):
        score += sum(1 for value in checks.values() if value is True)
    for key in (
        "volume",
        "volume_delta",
        "original_volume",
        "edited_volume",
        "final_volume_delta",
        "bbox",
        "original_bbox",
        "edited_bbox",
        "changed_region_bbox",
    ):
        if key in report:
            score += 1
    errors = report.get("errors")
    if isinstance(errors, list):
        score -= len(errors) * 2
    warnings = report.get("warnings")
    if isinstance(warnings, list):
        score -= len(warnings)
    return score


def allocate_integer_quota(total: int, buckets: dict[str, int]) -> dict[str, int]:
    if total <= 0 or not buckets:
        return {key: 0 for key in buckets}
    available_total = sum(buckets.values())
    total = min(total, available_total)
    raw = {key: total * value / available_total for key, value in buckets.items()}
    quota = {key: min(buckets[key], int(math.floor(value))) for key, value in raw.items()}
    remaining = total - sum(quota.values())
    order = sorted(
        buckets,
        key=lambda key: (raw[key] - math.floor(raw[key]), buckets[key], key),
        reverse=True,
    )
    while remaining > 0:
        changed = False
        for key in order:
            if remaining <= 0:
                break
            if quota[key] < buckets[key]:
                quota[key] += 1
                remaining -= 1
                changed = True
        if not changed:
            break
    return quota


def equalized_type_quotas(records: list[dict[str, Any]], target: int) -> dict[str, int]:
    available = Counter(str(record.get("edit_type") or "unknown") for record in records)
    if target >= sum(available.values()):
        return dict(available)
    quotas = {key: 0 for key in available}
    remaining_types = set(available)
    remaining_target = target
    while remaining_types and remaining_target > 0:
        fair_share = remaining_target / len(remaining_types)
        saturated = {key for key in remaining_types if available[key] <= fair_share}
        if not saturated:
            break
        for key in sorted(saturated):
            quotas[key] = available[key]
            remaining_target -= quotas[key]
            remaining_types.remove(key)
    if remaining_types and remaining_target > 0:
        base = int(remaining_target // len(remaining_types))
        for key in sorted(remaining_types):
            add = min(base, available[key] - quotas[key])
            quotas[key] += add
            remaining_target -= add
        order = sorted(remaining_types, key=lambda key: (available[key] - quotas[key], key), reverse=True)
        while remaining_target > 0:
            changed = False
            for key in order:
                if remaining_target <= 0:
                    break
                if quotas[key] < available[key]:
                    quotas[key] += 1
                    remaining_target -= 1
                    changed = True
            if not changed:
                break
    return quotas


def select_ranked(records: list[dict[str, Any]], count: int, seed: int) -> list[dict[str, Any]]:
    if count >= len(records):
        return list(records)
    ranked = sorted(
        records,
        key=lambda record: (
            -validation_score(record),
            stable_score(seed, record.get("sample_id"), record.get("source_sample_id"), record.get("edit_type")),
        ),
    )
    return ranked[:count]


def select_branch_records(records: list[dict[str, Any]], target: int, seed: int) -> list[dict[str, Any]]:
    if target >= len(records):
        return list(records)
    selected: list[dict[str, Any]] = []
    type_quotas = equalized_type_quotas(records, target)
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_type[str(record.get("edit_type") or "unknown")].append(record)

    for edit_type, type_records in sorted(by_type.items()):
        type_target = type_quotas.get(edit_type, 0)
        if type_target <= 0:
            continue
        split_available = Counter(str(record.get("selection_meta", {}).get("split") or "unknown") for record in type_records)
        split_quota = allocate_integer_quota(type_target, dict(split_available))
        for split, split_target in split_quota.items():
            if split_target <= 0:
                continue
            split_records = [
                record
                for record in type_records
                if str(record.get("selection_meta", {}).get("split") or "unknown") == split
            ]
            category_available = Counter(category_from_images(record) for record in split_records)
            category_quota = allocate_integer_quota(split_target, dict(category_available))
            for category, category_target in category_quota.items():
                category_records = [record for record in split_records if category_from_images(record) == category]
                selected.extend(select_ranked(category_records, category_target, seed))

    if len(selected) < target:
        selected_ids = {record.get("sample_id") for record in selected}
        remaining = [record for record in records if record.get("sample_id") not in selected_ids]
        selected.extend(select_ranked(remaining, target - len(selected), seed))
    elif len(selected) > target:
        selected = select_ranked(selected, target, seed)
    return selected


def with_subset_meta(record: dict[str, Any], dataset_version: str, seed: int) -> dict[str, Any]:
    copied = dict(record)
    meta = dict(copied.get("selection_meta") if isinstance(copied.get("selection_meta"), dict) else {})
    previous_version = meta.get("dataset_version")
    meta.update(
        {
            "pipeline_stage": "stage1_5_capped_subset",
            "dataset_version": dataset_version,
            "parent_dataset_version": previous_version,
            "selected": True,
            "selection_seed": seed,
        }
    )
    copied["selection_meta"] = meta
    return copied


def summarize(records: list[dict[str, Any]], dropped: Counter[str]) -> dict[str, Any]:
    branch_counts = Counter(str(record.get("branch") or "unknown") for record in records)
    edit_type_counts = Counter(str(record.get("edit_type") or "unknown") for record in records)
    category_counts = Counter(category_from_images(record) for record in records)
    family_counts = Counter(FAMILY_BY_BRANCH.get(str(record.get("branch")), "unknown") for record in records)
    split_counts = Counter(str(record.get("selection_meta", {}).get("split") or "unknown") for record in records)
    split_branch: dict[str, Counter[str]] = defaultdict(Counter)
    source_to_split: dict[str, set[str]] = defaultdict(set)
    image_to_split: dict[tuple[str, ...], set[str]] = defaultdict(set)
    per_source = Counter()

    for record in records:
        split = str(record.get("selection_meta", {}).get("split") or "unknown")
        branch = str(record.get("branch") or "unknown")
        split_branch[split][branch] += 1
        source_id = record.get("source_sample_id")
        if isinstance(source_id, str):
            source_to_split[source_id].add(split)
            per_source[source_id] += 1
        images = record.get("images")
        if isinstance(images, list):
            key = tuple(str(item).replace("\\", "/") for item in images)
            image_to_split[key].add(split)

    structural_counts = {
        "add": branch_counts.get("v2_add", 0),
        "delete": branch_counts.get("v3_delete", 0),
        "replace": branch_counts.get("v4_replace", 0),
    }
    positive_structural = [value for value in structural_counts.values() if value > 0]
    ratio = max(positive_structural) / min(positive_structural) if positive_structural else None
    return {
        "records": len(records),
        "source_sample_ids": len(per_source),
        "branch_counts": dict(sorted(branch_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "edit_type_counts": dict(sorted(edit_type_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "split_branch_counts": {key: dict(sorted(value.items())) for key, value in sorted(split_branch.items())},
        "structural_counts": structural_counts,
        "structural_max_min_ratio": ratio,
        "source_cross_split_count": sum(1 for splits in source_to_split.values() if len(splits) > 1),
        "image_triplet_cross_split_count": sum(1 for splits in image_to_split.values() if len(splits) > 1),
        "average_edits_per_source": round(statistics.mean(per_source.values()), 4) if per_source else 0,
        "max_edits_per_source": max(per_source.values()) if per_source else 0,
        "dropped_records": dict(sorted(dropped.items())),
        "stage2_ready": True,
    }


def markdown_table(items: dict[str, Any], headers: tuple[str, str] = ("Name", "Count")) -> str:
    lines = [f"| {headers[0]} | {headers[1]} |", "|---|---:|"]
    for key, value in items.items():
        lines.append(f"| `{key}` | {value} |")
    return "\n".join(lines)


def write_report(path: Path, summary: dict[str, Any], args: argparse.Namespace) -> None:
    lines = [
        "# Capped CAD Edit Subset Report",
        "",
        f"Input intermediate dir: `{args.intermediate_dir}`",
        f"Input instruction dir: `{args.instruction_dir}`",
        f"Output intermediate dir: `{args.output_intermediate_dir}`",
        f"Output instruction dir: `{args.output_instruction_dir}`",
        f"Dataset version: `{args.dataset_version}`",
        "",
        "## Summary",
        "",
        f"- records: `{summary['records']}`",
        f"- source_sample_ids: `{summary['source_sample_ids']}`",
        f"- source cross split count: `{summary['source_cross_split_count']}`",
        f"- image triplet cross split count: `{summary['image_triplet_cross_split_count']}`",
        f"- average edits per source: `{summary['average_edits_per_source']}`",
        f"- max edits per source: `{summary['max_edits_per_source']}`",
        f"- structural add/delete/replace ratio: `{summary['structural_max_min_ratio']:.4f}`",
        "",
        "## Branch Distribution",
        "",
        markdown_table(summary["branch_counts"]),
        "",
        "## Edit Type Distribution",
        "",
        markdown_table(summary["edit_type_counts"]),
        "",
        "## Category Distribution",
        "",
        markdown_table(summary["category_counts"]),
        "",
        "## Split Distribution",
        "",
        markdown_table(summary["split_counts"]),
        "",
        "## Dropped Records",
        "",
        markdown_table(summary["dropped_records"]) if summary["dropped_records"] else "No dropped records.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_instruction_subset(
    instruction_dir: Path,
    output_dir: Path,
    selected_sample_ids: set[str],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    all_instruction_records: list[dict[str, Any]] = []
    missing = Counter()
    for split in SPLITS:
        input_path = instruction_dir / f"{split}_instructions.jsonl"
        records = read_jsonl(input_path)
        selected = [record for record in records if record.get("sample_id") in selected_sample_ids]
        write_jsonl(output_dir / f"{split}_instructions.jsonl", selected)
        all_instruction_records.extend(selected)
        present_ids = {record.get("sample_id") for record in records}
        split_selected_ids = {sample_id for sample_id in selected_sample_ids if sample_id in present_ids}
        if len(split_selected_ids) != len(selected):
            missing[split] += abs(len(split_selected_ids) - len(selected))
    return all_instruction_records, missing


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intermediate-dir", default=Path("outputs/stage1_5/structural_balanced"), type=Path)
    parser.add_argument("--instruction-dir", default=Path("outputs/stage2/structural_balanced"), type=Path)
    parser.add_argument("--output-intermediate-dir", default=Path("outputs/stage1_5/v1_10k_v2_12k"), type=Path)
    parser.add_argument("--output-instruction-dir", default=Path("outputs/stage2/v1_10k_v2_12k"), type=Path)
    parser.add_argument("--dataset-version", default="v1_10k_v2_12k")
    parser.add_argument("--v1-count", default=10000, type=int)
    parser.add_argument("--v2-count", default=12000, type=int)
    parser.add_argument("--v3-count", default=None, type=int)
    parser.add_argument("--v4-count", default=None, type=int)
    parser.add_argument("--seed", default=42, type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    all_records: list[dict[str, Any]] = []
    for split in SPLITS:
        all_records.extend(read_jsonl(args.intermediate_dir / f"{split}_intermediate.jsonl"))

    by_branch: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in all_records:
        by_branch[str(record.get("branch") or "unknown")].append(record)

    branch_targets = {
        "v1_parameter": args.v1_count,
        "v2_add": args.v2_count,
        "v3_delete": args.v3_count,
        "v4_replace": args.v4_count,
    }

    selected: list[dict[str, Any]] = []
    dropped = Counter()
    for branch in BRANCHES:
        records = by_branch.get(branch, [])
        target = branch_targets.get(branch)
        if target is None:
            branch_selected = list(records)
        else:
            branch_selected = select_branch_records(records, min(target, len(records)), args.seed)
        selected_ids = {record.get("sample_id") for record in branch_selected}
        dropped[f"{branch}_cap"] = len(records) - len(branch_selected)
        selected.extend(with_subset_meta(record, args.dataset_version, args.seed) for record in branch_selected)

    selected.sort(
        key=lambda record: (
            str(record.get("selection_meta", {}).get("split") or ""),
            str(record.get("source_sample_id") or ""),
            str(record.get("sample_id") or ""),
        )
    )

    selected_by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in selected:
        split = str(record.get("selection_meta", {}).get("split") or "unknown")
        selected_by_split[split].append(record)

    for split in SPLITS:
        write_jsonl(args.output_intermediate_dir / f"{split}_intermediate.jsonl", selected_by_split.get(split, []))
    write_jsonl(args.output_intermediate_dir / "selected_intermediate.jsonl", selected)

    selected_sample_ids = {str(record.get("sample_id")) for record in selected if isinstance(record.get("sample_id"), str)}
    instruction_records, instruction_missing = build_instruction_subset(
        args.instruction_dir,
        args.output_instruction_dir,
        selected_sample_ids,
    )
    if instruction_missing:
        dropped.update({f"instruction_missing_{key}": value for key, value in instruction_missing.items()})

    summary = summarize(selected, dropped)
    summary.update(
        {
            "input_intermediate_dir": str(args.intermediate_dir),
            "input_instruction_dir": str(args.instruction_dir),
            "output_intermediate_dir": str(args.output_intermediate_dir),
            "output_instruction_dir": str(args.output_instruction_dir),
            "dataset_version": args.dataset_version,
            "requested_branch_caps": {
                "v1_parameter": args.v1_count,
                "v2_add": args.v2_count,
                "v3_delete": args.v3_count,
                "v4_replace": args.v4_count,
            },
            "instruction_records": len(instruction_records),
            "instruction_missing": dict(instruction_missing),
        }
    )
    args.output_intermediate_dir.mkdir(parents=True, exist_ok=True)
    args.output_instruction_dir.mkdir(parents=True, exist_ok=True)
    (args.output_intermediate_dir / "selection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_instruction_dir / "instruction_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_report(args.output_intermediate_dir / "selection_report.md", summary, args)
    write_report(args.output_instruction_dir / "instruction_report.md", summary, args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
