#!/usr/bin/env python3
"""Generate the Stage 1 deterministic validated intermediate pool.

Stage 1 does not call an MLLM and does not generate final instructions. It
normalizes validated V1/V2/V3/V4 records into one intermediate schema for the
later instruction-generation stage.
"""

from __future__ import annotations

import argparse
import ast
import html
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import cadquery as cq
from cadquery import exporters

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import generate_cad_edit_dataset as v1  # noqa: E402
import generate_cad_edit_delete_dataset as v3  # noqa: E402
import generate_cad_edit_replace_dataset as v4  # noqa: E402
import generate_cad_edit_structural_dataset as v2  # noqa: E402


BRANCHES = ("v1_parameter", "v2_add", "v3_delete", "v4_replace")
STRUCTURAL_BRANCHES = ("v2_add", "v3_delete", "v4_replace")
GENERATION_META = {
    "pipeline_stage": "stage1_deterministic_generation",
    "target_code_generated_by": "deterministic_rule",
    "instruction_generated": False,
    "mllm_used": False,
}
BRANCH_OUTPUT_NAMES = {
    "v1_parameter": "v1_parameter_validated.jsonl",
    "v2_add": "v2_add_validated.jsonl",
    "v3_delete": "v3_delete_validated.jsonl",
    "v4_replace": "v4_replace_validated.jsonl",
}
SUMMARY_NAME = "stage1_summary.json"
COVERAGE_NAME = "stage1_coverage.md"
ALL_NAME = "all_validated_intermediate.jsonl"


def read_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            yield line_number, record


def source_sample_id(record: dict[str, Any], source_line: int) -> str:
    for key in ("source_sample_id", "sample_id", "id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int):
            return str(value)
    return f"cadexpert_line_{source_line:06d}"


def category_from_images(images: Any) -> str:
    if not isinstance(images, list) or not images:
        return "Unknown"
    first = str(images[0]).replace("\\", "/")
    parts = [part for part in first.split("/") if part]
    if "image" in parts:
        index = parts.index("image")
        if index + 1 < len(parts):
            return parts[index + 1]
    return "Unknown"


def branch_output_paths(output_dir: Path) -> dict[str, Path]:
    paths = {branch: output_dir / filename for branch, filename in BRANCH_OUTPUT_NAMES.items()}
    paths["all"] = output_dir / ALL_NAME
    paths["summary"] = output_dir / SUMMARY_NAME
    paths["coverage"] = output_dir / COVERAGE_NAME
    paths["preview_gallery"] = output_dir / "preview_gallery" / "index.html"
    return paths


def pass_rate(candidates: int, validated: int) -> float:
    if candidates <= 0:
        return 0.0
    return round(validated * 100.0 / candidates, 4)


class BranchStats:
    def __init__(self, branch: str) -> None:
        self.branch = branch
        self.candidates = 0
        self.validated = 0
        self.failed_validation = 0
        self.by_edit_type: dict[str, Counter[str]] = defaultdict(Counter)
        self.by_category: dict[str, Counter[str]] = defaultdict(Counter)
        self.rejection_reasons: Counter[str] = Counter()

    def add_candidate(self, category: str, edit_type: str) -> None:
        self.candidates += 1
        self.by_edit_type[edit_type]["candidates"] += 1
        self.by_category[category]["candidates"] += 1

    def add_validated(self, category: str, edit_type: str) -> None:
        self.validated += 1
        self.by_edit_type[edit_type]["validated"] += 1
        self.by_category[category]["validated"] += 1

    def add_failed(self, category: str, edit_type: str, report: dict[str, Any]) -> None:
        self.failed_validation += 1
        self.by_edit_type[edit_type]["failed_validation"] += 1
        self.by_category[category]["failed_validation"] += 1
        errors = report.get("errors")
        if isinstance(errors, list) and errors:
            self.rejection_reasons[f"validation:{str(errors[0])[:120]}"] += 1
        else:
            error = str(report.get("error", "unknown"))[:120]
            self.rejection_reasons[f"validation:{error}"] += 1

    def add_generation_stats(self, stats: Counter[str]) -> None:
        for key, value in stats.items():
            if not isinstance(value, int) or value <= 0:
                continue
            if key.startswith("skipped") or key.startswith("geometry_error") or key.startswith("syntax_error"):
                self.rejection_reasons[key] += value
            elif key.startswith("validation_error"):
                self.rejection_reasons[key] += value

    def to_dict(self) -> dict[str, Any]:
        edit_types: dict[str, Any] = {}
        for edit_type, counts in sorted(self.by_edit_type.items()):
            candidates = counts["candidates"]
            validated = counts["validated"]
            failed = counts["failed_validation"]
            edit_types[edit_type] = {
                "candidates": candidates,
                "validated": validated,
                "failed_validation": failed,
                "pass_rate_percent": pass_rate(candidates, validated),
            }
        categories: dict[str, Any] = {}
        for category, counts in sorted(self.by_category.items()):
            candidates = counts["candidates"]
            validated = counts["validated"]
            failed = counts["failed_validation"]
            categories[category] = {
                "candidates": candidates,
                "validated": validated,
                "failed_validation": failed,
                "pass_rate_percent": pass_rate(candidates, validated),
            }
        return {
            "branch": self.branch,
            "candidates": self.candidates,
            "validated": self.validated,
            "failed_validation": self.failed_validation,
            "pass_rate_percent": pass_rate(self.candidates, self.validated),
            "by_edit_type": edit_types,
            "by_category": categories,
            "top_rejection_reasons": dict(self.rejection_reasons.most_common(30)),
        }


def v1_edit_type(edit_record: dict[str, Any]) -> str:
    call = edit_record.get("call") or edit_record.get("kind") or "parameter"
    return f"parameter_{call}"


def validated_v1_code(source: str) -> dict[str, Any]:
    try:
        ast.parse(source)
        shape = v2.execute_shape(source)
        geometry = v2.geometry_info(shape)
    except Exception as exc:
        return {"ok": False, "mode": "cadquery", "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True,
        "mode": "cadquery",
        "original_volume" if False else "volume": geometry.volume,
        "bbox": geometry.bbox,
    }


def normalize_record(
    *,
    branch: str,
    source_record: dict[str, Any],
    validated: dict[str, Any],
    edit_type: str,
    source_line: int,
    source_id: str,
    intermediate_code: str | None = None,
) -> dict[str, Any]:
    candidate_id = str(validated["candidate_id"])
    return {
        "sample_id": f"{branch}_{candidate_id}",
        "source_sample_id": source_id,
        "source_line": source_line,
        "images": validated["images"],
        "branch": branch,
        "edit_type": edit_type,
        "original_code": validated["original_code"],
        "target_code": validated["target_code"],
        "intermediate_code": intermediate_code,
        "edit_record": validated["edit_record"],
        "validation_report": validated["validation_report"],
        "generation_meta": dict(GENERATION_META),
    }


def generate_v1_records(
    source_record: dict[str, Any],
    sample_index: int,
    source_line: int,
    source_id: str,
    args: argparse.Namespace,
    stats: BranchStats,
) -> list[dict[str, Any]]:
    local_stats: Counter[str] = Counter()
    images = v1.extract_images(source_record)
    category = category_from_images(images)
    original_code = v1.extract_original_code(source_record)
    if not original_code:
        local_stats["skipped_no_code"] += 1
        stats.add_generation_stats(local_stats)
        return []

    original_report = validated_v1_code(original_code)
    if not original_report.get("ok"):
        local_stats["skipped_original_validation_failed"] += 1
        local_stats[f"validation_error:{str(original_report.get('error', 'unknown'))[:80]}"] += 1
        stats.add_generation_stats(local_stats)
        return []

    try:
        candidates = v1.find_edit_candidates(original_code)
    except SyntaxError:
        local_stats["skipped_original_syntax_error"] += 1
        stats.add_generation_stats(local_stats)
        return []
    if not candidates:
        local_stats["skipped_no_candidates"] += 1
        stats.add_generation_stats(local_stats)
        return []

    records: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(candidates[: args.v1_max_edits_per_sample], start=1):
        candidate_record = v1.build_candidate_record(
            sample_index=sample_index,
            source_line=source_line,
            candidate_index=candidate_index,
            images=images,
            original_code=original_code,
            candidate=candidate,
            scale_factor=args.v1_scale_factor,
        )
        if candidate_record is None:
            local_stats["skipped_bad_edit_value"] += 1
            continue
        edit_result = v1.apply_edit(original_code, candidate, args.v1_scale_factor)
        if edit_result is None:
            local_stats["skipped_bad_edit_value"] += 1
            continue
        edited_code, edit_record_obj = edit_result
        edit_record = v1.asdict(edit_record_obj)
        edit_type = v1_edit_type(edit_record)
        stats.add_candidate(category, edit_type)
        validation_report = validated_v1_code(edited_code)
        validation_report["original_validation_report"] = original_report
        if not validation_report.get("ok"):
            stats.add_failed(category, edit_type, validation_report)
            continue
        validated = v1.validated_edit_record(candidate_record, edited_code, edit_record_obj, validation_report)
        record = normalize_record(
            branch="v1_parameter",
            source_record=source_record,
            validated=validated,
            edit_type=edit_type,
            source_line=source_line,
            source_id=source_id,
        )
        records.append(record)
        stats.add_validated(category, edit_type)
    stats.add_generation_stats(local_stats)
    return records


def generate_v2_records(
    source_record: dict[str, Any],
    sample_index: int,
    source_line: int,
    source_id: str,
    args: argparse.Namespace,
    stats: BranchStats,
) -> list[dict[str, Any]]:
    candidates, local_stats = v2.generate_candidates_for_record(
        source_record=source_record,
        sample_index=sample_index,
        source_line=source_line,
        max_edits_per_sample=args.v2_max_edits_per_sample,
        edit_types=args.v2_edit_types,
    )
    stats.add_generation_stats(local_stats)
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        category = category_from_images(candidate["images"])
        structural = candidate["structural_candidate"]
        edit_type = structural["edit_type"]
        stats.add_candidate(category, edit_type)
        target_code = v2.apply_structural_candidate(candidate)
        validation_report = v2.validate_structural_edit(candidate["original_code"], target_code, candidate)
        if not validation_report.get("ok"):
            stats.add_failed(category, edit_type, validation_report)
            continue
        validated = {
            "candidate_id": candidate["candidate_id"],
            "sample_index": candidate["sample_index"],
            "source_line": candidate["source_line"],
            "images": candidate["images"],
            "original_code": candidate["original_code"],
            "target_code": target_code,
            "edit_record": structural,
            "validation_report": validation_report,
        }
        records.append(
            normalize_record(
                branch="v2_add",
                source_record=source_record,
                validated=validated,
                edit_type=edit_type,
                source_line=source_line,
                source_id=source_id,
            )
        )
        stats.add_validated(category, edit_type)
    return records


def generate_v3_records(
    source_record: dict[str, Any],
    sample_index: int,
    source_line: int,
    source_id: str,
    args: argparse.Namespace,
    stats: BranchStats,
) -> list[dict[str, Any]]:
    candidates, local_stats = v3.generate_delete_candidates_for_record(
        source_record=source_record,
        sample_index=sample_index,
        source_line=source_line,
        max_deletes_per_sample=args.v3_max_deletes_per_sample,
    )
    stats.add_generation_stats(local_stats)
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        category = category_from_images(candidate["images"])
        edit_record = candidate["delete_candidate"]
        edit_type = edit_record["edit_type"]
        stats.add_candidate(category, edit_type)
        target_code = v3.apply_delete_candidate(candidate)
        validation_report = v3.validate_delete_edit(candidate["original_code"], target_code, candidate)
        if not validation_report.get("ok"):
            stats.add_failed(category, edit_type, validation_report)
            continue
        validated = {
            "candidate_id": candidate["candidate_id"],
            "sample_index": candidate["sample_index"],
            "source_line": candidate["source_line"],
            "images": candidate["images"],
            "original_code": candidate["original_code"],
            "target_code": target_code,
            "edit_record": edit_record,
            "validation_report": validation_report,
        }
        records.append(
            normalize_record(
                branch="v3_delete",
                source_record=source_record,
                validated=validated,
                edit_type=edit_type,
                source_line=source_line,
                source_id=source_id,
            )
        )
        stats.add_validated(category, edit_type)
    return records


def generate_v4_records(
    source_record: dict[str, Any],
    sample_index: int,
    source_line: int,
    source_id: str,
    args: argparse.Namespace,
    stats: BranchStats,
) -> list[dict[str, Any]]:
    candidates, local_stats = v4.generate_replace_candidates_for_record(
        source_record=source_record,
        sample_index=sample_index,
        source_line=source_line,
        max_replacements_per_sample=args.v4_max_replacements_per_sample,
    )
    stats.add_generation_stats(local_stats)
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        category = category_from_images(candidate["images"])
        edit_record = candidate["replace_candidate"]
        edit_type = edit_record["edit_type"]
        stats.add_candidate(category, edit_type)
        validation_report = v4.validate_replace_edit(candidate)
        if not validation_report.get("ok"):
            stats.add_failed(category, edit_type, validation_report)
            continue
        validated = {
            "candidate_id": candidate["candidate_id"],
            "sample_index": candidate["sample_index"],
            "source_line": candidate["source_line"],
            "images": candidate["images"],
            "original_code": candidate["original_code"],
            "target_code": candidate["target_code"],
            "intermediate_code": candidate.get("intermediate_code"),
            "edit_record": edit_record,
            "validation_report": validation_report,
        }
        records.append(
            normalize_record(
                branch="v4_replace",
                source_record=source_record,
                validated=validated,
                edit_type=edit_type,
                source_line=source_line,
                source_id=source_id,
                intermediate_code=validated["intermediate_code"] if isinstance(validated.get("intermediate_code"), str) else None,
            )
        )
        stats.add_validated(category, edit_type)
    return records


def execute_cadquery(source: str) -> Any:
    namespace: dict[str, Any] = {"cq": cq, "cadquery": cq}
    exec(compile(source, "<cadquery_stage1_preview>", "exec"), namespace)
    if "result" not in namespace:
        raise RuntimeError("result variable was not defined")
    result = namespace["result"]
    if hasattr(result, "val") and callable(result.val):
        return result.val()
    return result


def safe_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)[:120]


def render_preview_gallery(records: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cards: list[str] = []
    rendered = 0
    failed = 0
    for index, record in enumerate(records, start=1):
        stem = f"{index:04d}_{safe_filename(record['sample_id'])}"
        before_svg = output_dir / f"{stem}_before.svg"
        after_svg = output_dir / f"{stem}_after.svg"
        error = ""
        try:
            before_shape = execute_cadquery(record["original_code"])
            after_shape = execute_cadquery(record["target_code"])
            before_svg.write_text(exporters.getSVG(before_shape), encoding="utf-8", newline="\n")
            after_svg.write_text(exporters.getSVG(after_shape), encoding="utf-8", newline="\n")
            rendered += 1
        except Exception as exc:
            failed += 1
            error = f"{type(exc).__name__}: {exc}"

        report = record.get("validation_report", {})
        checks = report.get("checks") if isinstance(report, dict) else None
        checks_summary = ""
        if isinstance(checks, dict):
            failed_checks = [name for name, ok in checks.items() if ok is not True]
            checks_summary = "all checks passed" if not failed_checks else "failed: " + ", ".join(failed_checks[:5])
        volume_bits = []
        for key in ("volume_delta", "final_volume_delta", "slot_volume_delta", "delete_volume_delta"):
            value = report.get(key) if isinstance(report, dict) else None
            if isinstance(value, (int, float)):
                volume_bits.append(f"{key}={value}")
        before_panel = (
            f'<object data="{html.escape(before_svg.name)}" type="image/svg+xml"></object>' if not error else ""
        )
        after_panel = f'<object data="{html.escape(after_svg.name)}" type="image/svg+xml"></object>' if not error else ""
        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        cards.append(
            f"""
            <section class="pair">
              <header>
                <h2>{html.escape(record['sample_id'])}</h2>
                <span>{html.escape(record['branch'])}</span>
                <span>{html.escape(record['edit_type'])}</span>
                <span>source line {record['source_line']}</span>
              </header>
              <p class="meta">validation: ok={html.escape(str(report.get('ok')))}; {html.escape(checks_summary)}; {html.escape('; '.join(volume_bits))}</p>
              {error_html}
              <div class="views">
                <figure><figcaption>Original</figcaption>{before_panel}</figure>
                <figure><figcaption>Edited</figcaption>{after_panel}</figure>
              </div>
            </section>
            """
        )
    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Stage 1 CAD Edit Preview</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; background: #f6f7f8; color: #1f2933; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 20px; font-size: 24px; }}
    .pair {{ background: #fff; border: 1px solid #d8dee4; border-radius: 8px; margin-bottom: 20px; padding: 16px; }}
    .pair header {{ display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; margin-bottom: 8px; }}
    .pair h2 {{ font-size: 17px; margin: 0; flex: 1; }}
    .pair span {{ font-size: 12px; color: #52616b; border: 1px solid #d8dee4; border-radius: 999px; padding: 2px 8px; }}
    .meta {{ margin: 0 0 12px; font-size: 13px; color: #52616b; }}
    .error {{ color: #b42318; }}
    .views {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    figure {{ margin: 0; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; overflow: hidden; }}
    figcaption {{ padding: 8px 10px; font-size: 13px; color: #52616b; border-bottom: 1px solid #e5e7eb; }}
    object {{ display: block; width: 100%; height: 360px; background: #fff; }}
  </style>
</head>
<body>
  <main>
    <h1>Stage 1 CAD Edit Preview</h1>
    {''.join(cards)}
  </main>
</body>
</html>
"""
    index = output_dir / "index.html"
    index.write_text(document, encoding="utf-8", newline="\n")
    return {"records": len(records), "rendered": rendered, "failed": failed, "index": str(index)}


def update_preview_samples(
    preview_samples: dict[tuple[str, str], list[dict[str, Any]]],
    records: list[dict[str, Any]],
    samples_per_edit_type: int,
) -> None:
    for record in records:
        key = (record["branch"], record["edit_type"])
        bucket = preview_samples[key]
        if len(bucket) < samples_per_edit_type:
            bucket.append(record)


def write_jsonl_record(handle: Any, record: dict[str, Any]) -> None:
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def structural_ratio(branch_stats: dict[str, BranchStats]) -> dict[str, Any]:
    counts = {branch: branch_stats[branch].validated for branch in STRUCTURAL_BRANCHES}
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


def write_coverage_md(summary: dict[str, Any], path: Path) -> None:
    lines: list[str] = [
        "# Stage 1 Coverage",
        "",
        f"Input: `{summary['input_path']}`",
        f"Records: {summary['input_records']}",
        f"Elapsed seconds: {summary['elapsed_seconds']}",
        "",
        "## Branch Summary",
        "",
        "| Branch | Candidates | Validated | Pass Rate | Failed Validation | Output |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for branch, data in summary["branches"].items():
        output_path = summary["outputs"][branch]
        lines.append(
            f"| {branch} | {data['candidates']} | {data['validated']} | "
            f"{data['pass_rate_percent']}% | {data['failed_validation']} | `{output_path}` |"
        )
    lines.extend(["", "## Validated By Edit Type", ""])
    for branch, data in summary["branches"].items():
        lines.extend([f"### {branch}", "", "| Edit Type | Candidates | Validated | Pass Rate |", "|---|---:|---:|---:|"])
        for edit_type, counts in data["by_edit_type"].items():
            lines.append(f"| `{edit_type}` | {counts['candidates']} | {counts['validated']} | {counts['pass_rate_percent']}% |")
        lines.append("")
    lines.extend(["## Validated By Category", ""])
    for branch, data in summary["branches"].items():
        lines.extend([f"### {branch}", "", "| Category | Candidates | Validated | Pass Rate |", "|---|---:|---:|---:|"])
        for category, counts in data["by_category"].items():
            lines.append(f"| {category} | {counts['candidates']} | {counts['validated']} | {counts['pass_rate_percent']}% |")
        lines.append("")
    lines.extend(
        [
            "## Structural Add/Delete/Replace Ratio",
            "",
            "| Branch | Validated |",
            "|---|---:|",
        ]
    )
    ratio = summary["structural_add_delete_replace_ratio"]
    for branch, count in ratio["validated_counts"].items():
        lines.append(f"| {branch} | {count} |")
    lines.extend(
        [
            "",
            f"Max/min ratio: `{ratio['max_to_min_ratio']}`",
            f"Passes max ratio <= 9: `{ratio['passes_max_ratio_lte_9']}`",
            "",
            "## Top Rejection Reasons",
            "",
        ]
    )
    for branch, data in summary["branches"].items():
        lines.extend([f"### {branch}", "", "| Reason | Count |", "|---|---:|"])
        for reason, count in data["top_rejection_reasons"].items():
            lines.append(f"| `{reason}` | {count} |")
        lines.append("")
    lines.extend(
        [
            "## Preview",
            "",
            f"Gallery: `{summary['outputs']['preview_gallery']}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_branches(value: str) -> list[str]:
    branches = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(branches) - set(BRANCHES))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown branches: {unknown}")
    return branches


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("data_expert3_fixed_paths.jsonl"), type=Path)
    parser.add_argument("--output-dir", default=Path("outputs/stage1"), type=Path)
    parser.add_argument("--branches", default=",".join(BRANCHES), type=parse_branches)
    parser.add_argument("--start-index", default=1, type=int)
    parser.add_argument("--limit", default=None, type=int)
    parser.add_argument("--progress-every", default=250, type=int)
    parser.add_argument("--preview-samples-per-edit-type", default=5, type=int)
    parser.add_argument("--v1-max-edits-per-sample", default=3, type=int)
    parser.add_argument("--v1-scale-factor", default=1.5, type=float)
    parser.add_argument("--v2-max-edits-per-sample", default=4, type=int)
    parser.add_argument("--v2-edit-types", default=sorted(v2.SUBTRACTIVE_EDITS), type=lambda value: v2.parse_edit_types(value) if isinstance(value, str) else value)
    parser.add_argument("--v3-max-deletes-per-sample", default=6, type=int)
    parser.add_argument("--v4-max-replacements-per-sample", default=10, type=int)
    parser.add_argument("--no-preview", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.start_index <= 0:
        raise ValueError("--start-index must be positive")
    for attr in (
        "v1_max_edits_per_sample",
        "v2_max_edits_per_sample",
        "v3_max_deletes_per_sample",
        "v4_max_replacements_per_sample",
        "preview_samples_per_edit_type",
    ):
        if getattr(args, attr) <= 0:
            raise ValueError(f"--{attr.replace('_', '-')} must be positive")
    if not math.isfinite(args.v1_scale_factor) or args.v1_scale_factor <= 0:
        raise ValueError("--v1-scale-factor must be a positive finite number")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = branch_output_paths(args.output_dir)
    branch_stats = {branch: BranchStats(branch) for branch in BRANCHES}
    preview_samples: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    input_records = 0
    processed_records = 0
    started = time.time()

    handles: dict[str, Any] = {}
    try:
        for branch in BRANCHES:
            handles[branch] = paths[branch].open("w", encoding="utf-8", newline="\n")
        handles["all"] = paths["all"].open("w", encoding="utf-8", newline="\n")

        for sample_index, (source_line, source_record) in enumerate(read_jsonl(args.input), start=1):
            if source_line < args.start_index:
                continue
            if args.limit is not None and processed_records >= args.limit:
                break
            input_records += 1
            processed_records += 1
            source_id = source_sample_id(source_record, source_line)

            branch_records: dict[str, list[dict[str, Any]]] = {}
            if "v1_parameter" in args.branches:
                branch_records["v1_parameter"] = generate_v1_records(
                    source_record, sample_index, source_line, source_id, args, branch_stats["v1_parameter"]
                )
            if "v2_add" in args.branches:
                branch_records["v2_add"] = generate_v2_records(
                    source_record, sample_index, source_line, source_id, args, branch_stats["v2_add"]
                )
            if "v3_delete" in args.branches:
                branch_records["v3_delete"] = generate_v3_records(
                    source_record, sample_index, source_line, source_id, args, branch_stats["v3_delete"]
                )
            if "v4_replace" in args.branches:
                branch_records["v4_replace"] = generate_v4_records(
                    source_record, sample_index, source_line, source_id, args, branch_stats["v4_replace"]
                )

            for branch, records in branch_records.items():
                for record in records:
                    write_jsonl_record(handles[branch], record)
                    write_jsonl_record(handles["all"], record)
                update_preview_samples(preview_samples, records, args.preview_samples_per_edit_type)

            if args.progress_every > 0 and processed_records % args.progress_every == 0:
                progress = {
                    "processed": processed_records,
                    "elapsed_seconds": round(time.time() - started, 3),
                    "validated": {branch: branch_stats[branch].validated for branch in args.branches},
                    "candidates": {branch: branch_stats[branch].candidates for branch in args.branches},
                }
                print(json.dumps(progress, ensure_ascii=False), flush=True)
    finally:
        for handle in handles.values():
            handle.close()

    preview_records = [record for key in sorted(preview_samples) for record in preview_samples[key]]
    preview_report = None
    if not args.no_preview:
        preview_report = render_preview_gallery(preview_records, args.output_dir / "preview_gallery")

    selected_stats = {branch: branch_stats[branch].to_dict() for branch in args.branches}
    output_paths = {branch: str(paths[branch]) for branch in args.branches}
    output_paths["all_validated_intermediate"] = str(paths["all"])
    output_paths["stage1_summary"] = str(paths["summary"])
    output_paths["stage1_coverage"] = str(paths["coverage"])
    output_paths["preview_gallery"] = str(paths["preview_gallery"])
    summary = {
        "input_path": str(args.input),
        "input_records": processed_records,
        "start_index": args.start_index,
        "limit": args.limit,
        "elapsed_seconds": round(time.time() - started, 3),
        "total_validated": sum(branch_stats[branch].validated for branch in args.branches),
        "branches": selected_stats,
        "structural_add_delete_replace_ratio": structural_ratio(branch_stats),
        "outputs": output_paths,
        "preview": preview_report,
        "generation_meta": dict(GENERATION_META),
    }
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    write_coverage_md(summary, paths["coverage"])
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
