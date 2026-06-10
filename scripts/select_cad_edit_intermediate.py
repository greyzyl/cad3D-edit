#!/usr/bin/env python3
"""Stage 1.5 source-level selection, balancing, and split for CAD edit intermediates."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import statistics
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any


BRANCHES = ("v1_parameter", "v2_add", "v3_delete", "v4_replace")
FAMILY_BY_BRANCH = {
    "v1_parameter": "parameter",
    "v2_add": "structural_add",
    "v3_delete": "structural_delete",
    "v4_replace": "structural_replace",
}
STRUCTURAL_FAMILIES = ("structural_add", "structural_delete", "structural_replace")
SPLITS = ("train", "val", "test")


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


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def normalized_image_key(record: dict[str, Any]) -> tuple[str, ...]:
    images = record.get("images")
    if not isinstance(images, list):
        return ()
    return tuple(str(item).replace("\\", "/") for item in images)


def category_from_images(record: dict[str, Any]) -> str:
    images = normalized_image_key(record)
    if not images:
        return "Unknown"
    parts = [part for part in images[0].split("/") if part]
    if "image" in parts:
        index = parts.index("image")
        if index + 1 < len(parts):
            return parts[index + 1]
    return "Unknown"


def family_for(record: dict[str, Any]) -> str:
    return FAMILY_BY_BRANCH.get(str(record.get("branch")), "unknown")


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        if item not in self.parent:
            self.parent[item] = item
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: str, b: str) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def stable_score(seed: int, *parts: Any) -> float:
    text = "|".join(str(part) for part in (seed, *parts))
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(0xFFFFFFFFFFFFFFFF)


def validation_completeness(record: dict[str, Any]) -> int:
    report = record.get("validation_report")
    if not isinstance(report, dict):
        return 0
    score = 0
    checks = report.get("checks")
    if isinstance(checks, dict):
        score += sum(1 for value in checks.values() if value is True)
    for key in (
        "volume",
        "volume_delta",
        "final_volume_delta",
        "original_volume",
        "edited_volume",
        "replaced_volume",
        "bbox",
        "original_bbox",
        "edited_bbox",
        "replaced_bbox",
    ):
        if key in report:
            score += 1
    if not report.get("errors"):
        score += 5
    return score


def sorted_records(records: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda record: (
            -validation_completeness(record),
            stable_score(seed, record.get("sample_id"), record.get("edit_type")),
            str(record.get("sample_id")),
        ),
    )


def select_diverse_records(
    records: list[dict[str, Any]],
    max_edits: int,
    seed: int,
    branch_order: tuple[str, ...],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    if max_edits <= 0 or len(records) <= max_edits:
        return list(sorted_records(records, seed)), Counter()

    buckets: dict[tuple[str, str], deque[dict[str, Any]]] = {}
    for record in records:
        key = (str(record.get("branch")), str(record.get("edit_type")))
        buckets.setdefault(key, deque()).append(record)
    for key, bucket in list(buckets.items()):
        buckets[key] = deque(sorted_records(list(bucket), seed))

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    edit_type_counts: Counter[str] = Counter()

    while len(selected) < max_edits:
        progressed = False
        for branch in branch_order:
            if len(selected) >= max_edits:
                break
            candidate_keys = [
                key for key, bucket in buckets.items() if key[0] == branch and bucket
            ]
            if not candidate_keys:
                continue
            candidate_keys.sort(
                key=lambda key: (
                    edit_type_counts[key[1]],
                    stable_score(seed, branch, key[1]),
                    key[1],
                )
            )
            key = candidate_keys[0]
            record = buckets[key].popleft()
            sample_id = str(record.get("sample_id"))
            if sample_id in selected_ids:
                continue
            selected.append(record)
            selected_ids.add(sample_id)
            edit_type_counts[key[1]] += 1
            progressed = True
        if not progressed:
            break

    dropped = Counter({"max_edits_per_source": max(0, len(records) - len(selected))})
    return selected, dropped


def sample_balanced_by_edit_type(
    records: list[dict[str, Any]],
    target_count: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if target_count >= len(records):
        return records, []
    buckets: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for record in records:
        buckets[str(record.get("edit_type"))].append(record)
    for edit_type, bucket in list(buckets.items()):
        buckets[edit_type] = deque(sorted_records(list(bucket), seed))

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    while len(selected) < target_count:
        progressed = False
        keys = [key for key, bucket in buckets.items() if bucket]
        keys.sort(key=lambda key: (len(buckets[key]), stable_score(seed, "add_balance", key), key))
        for key in keys:
            if len(selected) >= target_count:
                break
            if not buckets[key]:
                continue
            record = buckets[key].popleft()
            sample_id = str(record.get("sample_id"))
            if sample_id in selected_ids:
                continue
            selected.append(record)
            selected_ids.add(sample_id)
            progressed = True
        if not progressed:
            break

    selected_set = {str(record.get("sample_id")) for record in selected}
    dropped = [record for record in records if str(record.get("sample_id")) not in selected_set]
    return selected, dropped


def validate_input_record(record: dict[str, Any]) -> str | None:
    if not record.get("source_sample_id"):
        return "missing_source_sample_id"
    if not isinstance(record.get("target_code"), str) or not record["target_code"].strip():
        return "missing_target_code"
    images = record.get("images")
    if not isinstance(images, list) or not images or not all(isinstance(item, str) and item for item in images):
        return "missing_images"
    report = record.get("validation_report")
    if not isinstance(report, dict) or report.get("ok") is not True:
        return "validation_not_ok"
    if record.get("branch") not in BRANCHES:
        return "unsupported_branch"
    if not isinstance(record.get("edit_type"), str) or not record["edit_type"]:
        return "missing_edit_type"
    return None


def build_source_groups(records: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, set[str]]]:
    records_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    image_to_sources: dict[tuple[str, ...], set[str]] = defaultdict(set)
    uf = UnionFind()
    for record in records:
        source_id = str(record["source_sample_id"])
        records_by_source[source_id].append(record)
        uf.find(source_id)
        image_key = normalized_image_key(record)
        if image_key:
            image_node = "image:" + "\u241f".join(image_key)
            uf.union(source_id, image_node)
            image_to_sources[image_key].add(source_id)

    leakage_groups: dict[str, set[str]] = defaultdict(set)
    for source_id in records_by_source:
        leakage_groups[uf.find(source_id)].add(source_id)
    return records_by_source, leakage_groups


def split_sources(
    leakage_groups: dict[str, set[str]],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> dict[str, str]:
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 1e-6:
        raise ValueError("--train-ratio + --val-ratio + --test-ratio must equal 1")
    group_items = sorted(leakage_groups.items(), key=lambda item: sorted(item[1])[0])
    rng = random.Random(seed)
    rng.shuffle(group_items)
    total = len(group_items)
    train_count = int(round(total * train_ratio))
    val_count = int(round(total * val_ratio))
    if train_count + val_count > total:
        val_count = max(0, total - train_count)

    source_to_split: dict[str, str] = {}
    for index, (_, source_ids) in enumerate(group_items):
        if index < train_count:
            split = "train"
        elif index < train_count + val_count:
            split = "val"
        else:
            split = "test"
        for source_id in source_ids:
            source_to_split[source_id] = split
    return source_to_split


def with_selection_meta(record: dict[str, Any], split: str, dataset_version: str, seed: int) -> dict[str, Any]:
    selected = dict(record)
    selected["selection_meta"] = {
        "pipeline_stage": "stage1_5_selection",
        "split": split,
        "dataset_version": dataset_version,
        "selected": True,
        "selection_seed": seed,
    }
    return selected


def select_full_version(
    records_by_source: dict[str, list[dict[str, Any]]],
    source_to_split: dict[str, str],
    max_edits_per_source: int,
    seed: int,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    selected: list[dict[str, Any]] = []
    dropped: Counter[str] = Counter()
    branch_order = ("v3_delete", "v4_replace", "v2_add", "v1_parameter")
    for source_id in sorted(records_by_source):
        records = records_by_source[source_id]
        source_seed = int(stable_score(seed, source_id) * 1_000_000_000)
        chosen, local_dropped = select_diverse_records(records, max_edits_per_source, source_seed, branch_order)
        dropped.update(local_dropped)
        split = source_to_split[source_id]
        selected.extend(with_selection_meta(record, split, "full", seed) for record in chosen)
    return selected, dropped


def select_structural_balanced_version(
    records_by_source: dict[str, list[dict[str, Any]]],
    source_to_split: dict[str, str],
    max_edits_per_source: int,
    seed: int,
    structural_ratio_limit: float,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    preliminary: list[dict[str, Any]] = []
    dropped: Counter[str] = Counter()
    branch_order = ("v3_delete", "v4_replace", "v2_add", "v1_parameter")
    for source_id in sorted(records_by_source):
        records = records_by_source[source_id]
        source_seed = int(stable_score(seed, "balanced", source_id) * 1_000_000_000)
        chosen, local_dropped = select_diverse_records(records, max_edits_per_source, source_seed, branch_order)
        dropped.update(local_dropped)
        split = source_to_split[source_id]
        preliminary.extend(with_selection_meta(record, split, "structural_balanced", seed) for record in chosen)

    final: list[dict[str, Any]] = []
    for split in SPLITS:
        split_records = [record for record in preliminary if record["selection_meta"]["split"] == split]
        structural_counts = Counter(family_for(record) for record in split_records if family_for(record) in STRUCTURAL_FAMILIES)
        add_count = structural_counts["structural_add"]
        delete_count = structural_counts["structural_delete"]
        replace_count = structural_counts["structural_replace"]
        min_anchor = min(count for count in (delete_count, replace_count) if count > 0) if delete_count and replace_count else 0
        max_add = int(structural_ratio_limit * min_anchor) if min_anchor else 0
        if add_count > max_add:
            add_records = [record for record in split_records if family_for(record) == "structural_add"]
            kept_add, dropped_add = sample_balanced_by_edit_type(add_records, max_add, seed)
            kept_add_ids = {str(record["sample_id"]) for record in kept_add}
            final.extend(record for record in split_records if family_for(record) != "structural_add")
            final.extend(record for record in kept_add if str(record["sample_id"]) in kept_add_ids)
            dropped["structural_balance_add_downsample"] += len(dropped_add)
        else:
            final.extend(split_records)
    final.sort(key=lambda record: (record["selection_meta"]["split"], record["source_sample_id"], record["sample_id"]))
    return final, dropped


def count_distribution(records: list[dict[str, Any]]) -> dict[str, Any]:
    branch = Counter(str(record.get("branch")) for record in records)
    edit_type = Counter(str(record.get("edit_type")) for record in records)
    family = Counter(family_for(record) for record in records)
    category = Counter(category_from_images(record) for record in records)
    split = Counter(record.get("selection_meta", {}).get("split", "unknown") for record in records)
    split_branch: dict[str, Counter[str]] = defaultdict(Counter)
    split_edit_type: dict[str, Counter[str]] = defaultdict(Counter)
    split_category: dict[str, Counter[str]] = defaultdict(Counter)
    split_family: dict[str, Counter[str]] = defaultdict(Counter)
    source_counts: Counter[str] = Counter()
    split_sources: dict[str, set[str]] = defaultdict(set)
    for record in records:
        split_name = record.get("selection_meta", {}).get("split", "unknown")
        split_branch[split_name][str(record.get("branch"))] += 1
        split_edit_type[split_name][str(record.get("edit_type"))] += 1
        split_category[split_name][category_from_images(record)] += 1
        split_family[split_name][family_for(record)] += 1
        source_id = str(record.get("source_sample_id"))
        source_counts[source_id] += 1
        split_sources[split_name].add(source_id)
    edits_per_source = list(source_counts.values())
    return {
        "record_count": len(records),
        "source_sample_id_count": len(source_counts),
        "average_edits_per_source": round(sum(edits_per_source) / len(edits_per_source), 4) if edits_per_source else 0.0,
        "median_edits_per_source": statistics.median(edits_per_source) if edits_per_source else 0,
        "max_edits_per_source": max(edits_per_source) if edits_per_source else 0,
        "branch_distribution": dict(branch),
        "family_distribution": dict(family),
        "edit_type_distribution": dict(edit_type),
        "category_distribution": dict(category),
        "split_record_distribution": dict(split),
        "split_source_distribution": {split_name: len(split_sources[split_name]) for split_name in SPLITS},
        "split_branch_distribution": {key: dict(value) for key, value in split_branch.items()},
        "split_family_distribution": {key: dict(value) for key, value in split_family.items()},
        "split_edit_type_distribution": {key: dict(value) for key, value in split_edit_type.items()},
        "split_category_distribution": {key: dict(value) for key, value in split_category.items()},
    }


def structural_ratio(records: list[dict[str, Any]], structural_ratio_limit: float) -> dict[str, Any]:
    counts = Counter(family_for(record) for record in records)
    structural = {family: counts[family] for family in STRUCTURAL_FAMILIES}
    positive = [value for value in structural.values() if value > 0]
    ratio = None
    passes = False
    if len(positive) == len(STRUCTURAL_FAMILIES):
        ratio = round(max(positive) / min(positive), 4)
        passes = ratio <= structural_ratio_limit
    return {
        "validated_counts": structural,
        "max_to_min_ratio": ratio,
        "ratio_limit": structural_ratio_limit,
        "passes_max_ratio": passes,
    }


def leakage_checks(records: list[dict[str, Any]]) -> dict[str, Any]:
    source_to_split: dict[str, set[str]] = defaultdict(set)
    image_to_split: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for record in records:
        split = record.get("selection_meta", {}).get("split")
        source_to_split[str(record.get("source_sample_id"))].add(str(split))
        image_to_split[normalized_image_key(record)].add(str(split))
    leaking_sources = sorted(source for source, splits in source_to_split.items() if len(splits) > 1)
    leaking_images = sorted(image for image, splits in image_to_split.items() if len(splits) > 1)
    return {
        "source_sample_id_cross_split_count": len(leaking_sources),
        "image_triplet_cross_split_count": len(leaking_images),
        "ok": not leaking_sources and not leaking_images,
        "leaking_source_sample_ids_preview": leaking_sources[:20],
        "leaking_image_triplets_preview": [list(item) for item in leaking_images[:5]],
    }


def quality_checks(records: list[dict[str, Any]]) -> dict[str, Any]:
    missing_target = 0
    missing_source = 0
    missing_images = 0
    invalid_validation = 0
    instructions = 0
    for record in records:
        if not isinstance(record.get("target_code"), str) or not record["target_code"].strip():
            missing_target += 1
        if not record.get("source_sample_id"):
            missing_source += 1
        images = record.get("images")
        if not isinstance(images, list) or not images:
            missing_images += 1
        if record.get("validation_report", {}).get("ok") is not True:
            invalid_validation += 1
        if "instruction" in record:
            instructions += 1
    return {
        "missing_target_code": missing_target,
        "missing_source_sample_id": missing_source,
        "missing_images": missing_images,
        "validation_not_ok": invalid_validation,
        "records_with_instruction_field": instructions,
        "ok": not any((missing_target, missing_source, missing_images, invalid_validation, instructions)),
    }


def write_version_outputs(
    output_dir: Path,
    version: str,
    records: list[dict[str, Any]],
    input_path: Path,
    input_record_count: int,
    source_count_total: int,
    dropped: Counter[str],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int,
    structural_ratio_limit: float,
) -> dict[str, Any]:
    version_dir = output_dir / version
    version_dir.mkdir(parents=True, exist_ok=True)
    records = sorted(records, key=lambda record: (record["selection_meta"]["split"], record["source_sample_id"], record["sample_id"]))
    split_records = {split: [record for record in records if record["selection_meta"]["split"] == split] for split in SPLITS}
    write_jsonl(version_dir / "selected_intermediate.jsonl", records)
    for split in SPLITS:
        write_jsonl(version_dir / f"{split}_intermediate.jsonl", split_records[split])

    distribution = count_distribution(records)
    split_distribution = {split: count_distribution(split_records[split]) for split in SPLITS}
    ratio = structural_ratio(records, structural_ratio_limit)
    summary = {
        "input_path": str(input_path),
        "dataset_version": version,
        "selection_seed": seed,
        "train_ratio": train_ratio,
        "val_ratio": val_ratio,
        "test_ratio": test_ratio,
        "max_edits_per_source": distribution["max_edits_per_source"],
        "input_validated_records": input_record_count,
        "selected_records": len(records),
        "dropped_records": input_record_count - len(records),
        "dropped_reasons": dict(dropped),
        "source_sample_id_total_before_selection": source_count_total,
        "distribution": distribution,
        "split_distribution": split_distribution,
        "structural_add_delete_replace_ratio": ratio,
        "quality_checks": quality_checks(records),
        "leakage_checks": leakage_checks(records),
        "stage2_ready": quality_checks(records)["ok"] and leakage_checks(records)["ok"],
        "outputs": {
            "selected_intermediate": str(version_dir / "selected_intermediate.jsonl"),
            "train_intermediate": str(version_dir / "train_intermediate.jsonl"),
            "val_intermediate": str(version_dir / "val_intermediate.jsonl"),
            "test_intermediate": str(version_dir / "test_intermediate.jsonl"),
            "selection_summary": str(version_dir / "selection_summary.json"),
            "selection_report": str(version_dir / "selection_report.md"),
        },
    }
    (version_dir / "selection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    write_report(summary, version_dir / "selection_report.md")
    return summary


def write_counter_table(lines: list[str], title: str, data: dict[str, int], limit: int | None = None) -> None:
    lines.extend([f"## {title}", "", "| Name | Count |", "|---|---:|"])
    items = sorted(data.items(), key=lambda item: (-item[1], item[0]))
    if limit is not None:
        items = items[:limit]
    for key, value in items:
        lines.append(f"| `{key}` | {value} |")
    lines.append("")


def write_report(summary: dict[str, Any], path: Path) -> None:
    dist = summary["distribution"]
    ratio = summary["structural_add_delete_replace_ratio"]
    lines: list[str] = [
        f"# Stage 1.5 Selection Report - {summary['dataset_version']}",
        "",
        f"Input: `{summary['input_path']}`",
        f"Input validated records: {summary['input_validated_records']}",
        f"Selected records: {summary['selected_records']}",
        f"Dropped records: {summary['dropped_records']}",
        f"Source sample IDs before selection: {summary['source_sample_id_total_before_selection']}",
        f"Selected source sample IDs: {dist['source_sample_id_count']}",
        f"Average edits per source: {dist['average_edits_per_source']}",
        f"Median edits per source: {dist['median_edits_per_source']}",
        f"Max edits per source: {dist['max_edits_per_source']}",
        f"Stage 2 ready: `{summary['stage2_ready']}`",
        "",
        "## Split Summary",
        "",
        "| Split | Source Count | Record Count |",
        "|---|---:|---:|",
    ]
    for split in SPLITS:
        lines.append(
            f"| {split} | {dist['split_source_distribution'].get(split, 0)} | {dist['split_record_distribution'].get(split, 0)} |"
        )
    lines.append("")
    write_counter_table(lines, "Branch Distribution", dist["branch_distribution"])
    write_counter_table(lines, "Family Distribution", dist["family_distribution"])
    write_counter_table(lines, "Edit Type Distribution", dist["edit_type_distribution"])
    write_counter_table(lines, "Category Distribution", dist["category_distribution"])
    lines.extend(
        [
            "## Structural Add/Delete/Replace Ratio",
            "",
            "| Family | Count |",
            "|---|---:|",
        ]
    )
    for family, count in ratio["validated_counts"].items():
        lines.append(f"| {family} | {count} |")
    lines.extend(
        [
            "",
            f"Max/min ratio: `{ratio['max_to_min_ratio']}`",
            f"Ratio limit: `{ratio['ratio_limit']}`",
            f"Passes ratio: `{ratio['passes_max_ratio']}`",
            "",
            "## Dropped Records",
            "",
            "| Reason | Count |",
            "|---|---:|",
        ]
    )
    for reason, count in sorted(summary["dropped_reasons"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| `{reason}` | {count} |")
    lines.extend(["", "## Quality Checks", "", "| Check | Value |", "|---|---:|"])
    for key, value in summary["quality_checks"].items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Leakage Checks", "", "| Check | Value |", "|---|---:|"])
    for key, value in summary["leakage_checks"].items():
        if key.endswith("_preview"):
            continue
        lines.append(f"| `{key}` | `{value}` |")
    lines.append("")
    lines.append("## Per-Split Distribution")
    lines.append("")
    for split in SPLITS:
        split_dist = summary["split_distribution"][split]
        lines.extend([f"### {split}", "", "Branch:", ""])
        lines.extend(f"- `{key}`: {value}" for key, value in sorted(split_dist["branch_distribution"].items()))
        lines.extend(["", "Family:", ""])
        lines.extend(f"- `{key}`: {value}" for key, value in sorted(split_dist["family_distribution"].items()))
        lines.extend(["", "Category:", ""])
        lines.extend(f"- `{key}`: {value}" for key, value in sorted(split_dist["category_distribution"].items()))
        lines.append("")
    lines.extend(
        [
            "## Outputs",
            "",
        ]
    )
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("outputs/stage1/all_validated_intermediate.jsonl"), type=Path)
    parser.add_argument("--output-dir", default=Path("outputs/stage1_5"), type=Path)
    parser.add_argument("--train-ratio", default=0.8, type=float)
    parser.add_argument("--val-ratio", default=0.1, type=float)
    parser.add_argument("--test-ratio", default=0.1, type=float)
    parser.add_argument("--seed", default=42, type=int)
    parser.add_argument("--max-edits-per-source", default=6, type=int)
    parser.add_argument("--structural-ratio-limit", default=9.0, type=float)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.max_edits_per_source <= 0:
        raise ValueError("--max-edits-per-source must be positive")
    if args.structural_ratio_limit <= 0:
        raise ValueError("--structural-ratio-limit must be positive")

    records_raw = read_jsonl(args.input)
    valid_records: list[dict[str, Any]] = []
    dropped_input: Counter[str] = Counter()
    for record in records_raw:
        reason = validate_input_record(record)
        if reason is None:
            valid_records.append(record)
        else:
            dropped_input[reason] += 1

    records_by_source, leakage_groups = build_source_groups(valid_records)
    source_to_split = split_sources(
        leakage_groups=leakage_groups,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )

    if args.output_dir.exists():
        resolved = args.output_dir.resolve()
        cwd = Path.cwd().resolve()
        if cwd not in resolved.parents and resolved != cwd:
            raise ValueError(f"refusing to remove output outside workspace: {resolved}")
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    full_records, full_dropped = select_full_version(
        records_by_source=records_by_source,
        source_to_split=source_to_split,
        max_edits_per_source=args.max_edits_per_source,
        seed=args.seed,
    )
    balanced_records, balanced_dropped = select_structural_balanced_version(
        records_by_source=records_by_source,
        source_to_split=source_to_split,
        max_edits_per_source=args.max_edits_per_source,
        seed=args.seed,
        structural_ratio_limit=args.structural_ratio_limit,
    )
    full_dropped.update(dropped_input)
    balanced_dropped.update(dropped_input)

    full_summary = write_version_outputs(
        output_dir=args.output_dir,
        version="full",
        records=full_records,
        input_path=args.input,
        input_record_count=len(records_raw),
        source_count_total=len(records_by_source),
        dropped=full_dropped,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
        structural_ratio_limit=args.structural_ratio_limit,
    )
    balanced_summary = write_version_outputs(
        output_dir=args.output_dir,
        version="structural_balanced",
        records=balanced_records,
        input_path=args.input,
        input_record_count=len(records_raw),
        source_count_total=len(records_by_source),
        dropped=balanced_dropped,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
        structural_ratio_limit=args.structural_ratio_limit,
    )
    summary = {"full": full_summary, "structural_balanced": balanced_summary}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
