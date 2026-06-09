#!/usr/bin/env python3
"""Run coverage audit for V1/V2/V3/V4 CAD edit pipelines."""

from __future__ import annotations

import argparse
import ast
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import generate_cad_edit_dataset as v1  # noqa: E402
import generate_cad_edit_delete_dataset as v3  # noqa: E402
import generate_cad_edit_replace_dataset as v4  # noqa: E402
import generate_cad_edit_structural_dataset as v2  # noqa: E402


CATEGORY_NAMES = ("Circles", "Rects", "Polygons")
V2_EDIT_TYPES = ["add_through_hole", "add_blind_hole", "add_rectangular_slot", "add_pocket"]
BRANCH_NAMES = {
    "v1_parameter": "V1 parameter",
    "v2_add": "V2 add",
    "v3_delete": "V3 delete",
    "v4_replace": "V4 replace",
}
V4_CIRCULAR_CUTOUT_RE = re.compile(
    r"\.cut\s*\(\s*cq\.Workplane\s*\([^)]*\)\s*\.circle\s*\([^)]*\)\s*\.extrude\s*\(",
    re.DOTALL,
)


def read_jsonl(path: Path):
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
            yield line_number, record


def category_from_images(images: list[str]) -> str:
    joined = "/".join(images).replace("\\", "/")
    for category in CATEGORY_NAMES:
        if f"/{category}/" in joined or joined.startswith(f"./image/{category}/"):
            return category
    return "Unknown"


def percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100.0, 4)


def nested_counter() -> defaultdict[str, Counter[str]]:
    return defaultdict(Counter)


class BranchStats:
    def __init__(self, name: str) -> None:
        self.name = name
        self.candidates = 0
        self.validated = 0
        self.failed_validation = 0
        self.by_category: defaultdict[str, Counter[str]] = nested_counter()
        self.by_edit_type: defaultdict[str, Counter[str]] = nested_counter()
        self.rejections: Counter[str] = Counter()

    def add_candidate(self, category: str, edit_type: str) -> None:
        self.candidates += 1
        self.by_category[category]["candidates"] += 1
        self.by_edit_type[edit_type]["candidates"] += 1

    def add_validated(self, category: str, edit_type: str) -> None:
        self.validated += 1
        self.by_category[category]["validated"] += 1
        self.by_edit_type[edit_type]["validated"] += 1

    def add_failed(self, category: str, edit_type: str, report: dict[str, Any]) -> None:
        self.failed_validation += 1
        self.by_category[category]["failed_validation"] += 1
        self.by_edit_type[edit_type]["failed_validation"] += 1
        errors = report.get("errors")
        if isinstance(errors, list) and errors:
            reason = str(errors[0])[:160]
        else:
            reason = str(report.get("error", "validation_failed"))[:160]
        self.rejections[f"validation:{reason}"] += 1

    def add_rejections(self, stats: Counter[str], prefix: str = "") -> None:
        for key, value in stats.items():
            if value <= 0:
                continue
            if key in {
                "candidate_records",
                "attempted_edits",
                "emitted_ok",
                "validated_output_records",
                "candidate_output_records",
                "instruction_output_records",
                "output_records",
            }:
                continue
            if key.startswith("delete_candidate_records"):
                continue
            reason = f"{prefix}{key}" if prefix else key
            self.rejections[reason] += value

    def to_dict(self) -> dict[str, Any]:
        by_category: dict[str, Any] = {}
        for category in sorted(set(CATEGORY_NAMES) | set(self.by_category.keys())):
            counts = self.by_category.get(category, Counter())
            candidates = counts.get("candidates", 0)
            validated = counts.get("validated", 0)
            by_category[category] = {
                "candidates": candidates,
                "validated": validated,
                "failed_validation": counts.get("failed_validation", 0),
                "pass_rate_percent": percent(validated, candidates),
            }

        by_edit_type: dict[str, Any] = {}
        for edit_type, counts in sorted(self.by_edit_type.items()):
            candidates = counts.get("candidates", 0)
            validated = counts.get("validated", 0)
            by_edit_type[edit_type] = {
                "candidates": candidates,
                "validated": validated,
                "failed_validation": counts.get("failed_validation", 0),
                "pass_rate_percent": percent(validated, candidates),
            }

        return {
            "branch": self.name,
            "candidates": self.candidates,
            "validated": self.validated,
            "failed_validation": self.failed_validation,
            "pass_rate_percent": percent(self.validated, self.candidates),
            "by_category": by_category,
            "by_edit_type": by_edit_type,
            "top_rejection_reasons": dict(self.rejections.most_common(30)),
        }


class ReservoirSampler:
    def __init__(self, per_key: int, seed: int) -> None:
        self.per_key = per_key
        self.random = random.Random(seed)
        self.seen: Counter[str] = Counter()
        self.samples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def add(self, key: str, record: dict[str, Any]) -> None:
        if self.per_key <= 0:
            return
        self.seen[key] += 1
        bucket = self.samples[key]
        if len(bucket) < self.per_key:
            bucket.append(record)
            return
        index = self.random.randrange(self.seen[key])
        if index < self.per_key:
            bucket[index] = record

    def records(self) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for key in sorted(self.samples):
            output.extend(self.samples[key])
        return output

    def counts(self) -> dict[str, int]:
        return dict(sorted(self.seen.items()))


def annotate_sample(record: dict[str, Any], branch: str, category: str, edit_type: str, source_line: int) -> dict[str, Any]:
    annotated = dict(record)
    hidden = dict(annotated.get("hidden") if isinstance(annotated.get("hidden"), dict) else {})
    hidden.update(
        {
            "audit_branch": branch,
            "audit_category": category,
            "audit_edit_type": edit_type,
            "audit_source_line": source_line,
        }
    )
    annotated["hidden"] = hidden
    return annotated


def v1_edit_type(edit_record: v1.EditRecord | dict[str, Any]) -> str:
    if isinstance(edit_record, dict):
        return str(edit_record.get("call") or edit_record.get("kind") or "parameter")
    return edit_record.call


def validate_v1_code_for_audit(source: str, args: argparse.Namespace) -> dict[str, Any]:
    if args.v1_audit_validation == "subprocess":
        return v1.validate_code(source, args.v1_validation_mode, args.timeout_seconds, args.validator_python)

    _, parse_error = v1.parse_and_check_result(source)
    if parse_error:
        return {"ok": False, "mode": "cadquery_audit_inprocess", "error": parse_error}
    if args.v1_validation_mode == "syntax":
        return {"ok": True, "mode": "syntax_audit_inprocess"}
    try:
        v2.execute_shape(source)
    except Exception as exc:
        return {"ok": False, "mode": "cadquery_audit_inprocess", "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "mode": "cadquery_audit_inprocess"}


def audit_v1_record(
    record: dict[str, Any],
    source_line: int,
    sample_index: int,
    category: str,
    stats: BranchStats,
    sampler: ReservoirSampler,
    args: argparse.Namespace,
) -> None:
    images = v1.extract_images(record)
    original_code = v1.extract_original_code(record)
    if not original_code:
        stats.rejections["skipped_no_code"] += 1
        return
    try:
        candidates = v1.find_edit_candidates(original_code)
    except SyntaxError:
        stats.rejections["skipped_original_syntax_error"] += 1
        return
    if not candidates:
        stats.rejections["skipped_no_candidates"] += 1
        return

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
            stats.rejections["skipped_bad_edit_value"] += 1
            continue
        edit_type = candidate.call
        stats.add_candidate(category, edit_type)
        edit_result = v1.apply_edit(original_code, candidate, args.v1_scale_factor)
        if edit_result is None:
            stats.rejections["skipped_bad_edit_value"] += 1
            continue
        edited_code, edit_record = edit_result
        validation_report = validate_v1_code_for_audit(edited_code, args)
        if validation_report.get("ok"):
            stats.add_validated(category, edit_type)
            final = v1.output_record(
                images,
                original_code,
                edited_code,
                edit_record,
                validation_report,
                candidate_id=candidate_record["candidate_id"],
            )
            sampler.add(edit_type, annotate_sample(final, "V1 parameter", category, edit_type, source_line))
        else:
            stats.add_failed(category, edit_type, validation_report)


def audit_v2_record(
    record: dict[str, Any],
    source_line: int,
    sample_index: int,
    category: str,
    stats: BranchStats,
    sampler: ReservoirSampler,
    args: argparse.Namespace,
) -> None:
    candidates, local_stats = v2.generate_candidates_for_record(
        source_record=record,
        sample_index=sample_index,
        source_line=source_line,
        max_edits_per_sample=args.v2_max_edits_per_sample,
        edit_types=V2_EDIT_TYPES,
    )
    stats.add_rejections(local_stats)
    for candidate in candidates:
        structural = candidate["structural_candidate"]
        edit_type = structural["edit_type"]
        stats.add_candidate(category, edit_type)
        target_code = v2.apply_structural_candidate(candidate)
        validation_report = v2.validate_structural_edit(candidate["original_code"], target_code, candidate)
        if validation_report.get("ok"):
            stats.add_validated(category, edit_type)
            validated = {
                "candidate_id": candidate["candidate_id"],
                "images": candidate["images"],
                "original_code": candidate["original_code"],
                "target_code": target_code,
                "edit_record": structural,
                "validation_report": validation_report,
                "fallback_instruction": v2.fallback_instruction(candidate),
            }
            final = v2.final_record(validated)
            sampler.add(edit_type, annotate_sample(final, "V2 add", category, edit_type, source_line))
        else:
            stats.add_failed(category, edit_type, validation_report)


def audit_v3_record(
    record: dict[str, Any],
    source_line: int,
    sample_index: int,
    category: str,
    stats: BranchStats,
    sampler: ReservoirSampler,
    args: argparse.Namespace,
) -> None:
    candidates, local_stats = v3.generate_delete_candidates_for_record(
        source_record=record,
        sample_index=sample_index,
        source_line=source_line,
        max_deletes_per_sample=args.v3_max_deletes_per_sample,
    )
    stats.add_rejections(local_stats)
    for candidate in candidates:
        delete_candidate = candidate["delete_candidate"]
        edit_type = delete_candidate["edit_type"]
        stats.add_candidate(category, edit_type)
        try:
            target_code = v3.apply_delete_candidate(candidate)
            validation_report = v3.validate_delete_edit(candidate["original_code"], target_code, candidate)
        except Exception as exc:
            validation_report = {"ok": False, "errors": [str(exc)]}
        if validation_report.get("ok"):
            stats.add_validated(category, edit_type)
            validated = {
                "candidate_id": candidate["candidate_id"],
                "images": candidate["images"],
                "original_code": candidate["original_code"],
                "target_code": target_code,
                "edit_record": delete_candidate,
                "validation_report": validation_report,
                "fallback_instruction": v3.fallback_instruction(candidate),
            }
            final = v3.final_record(validated)
            sampler.add(edit_type, annotate_sample(final, "V3 delete", category, edit_type, source_line))
        else:
            stats.add_failed(category, edit_type, validation_report)


def audit_v4_record(
    record: dict[str, Any],
    source_line: int,
    sample_index: int,
    category: str,
    stats: BranchStats,
    sampler: ReservoirSampler,
    args: argparse.Namespace,
) -> None:
    candidates, local_stats = v4.generate_replace_candidates_for_record(
        source_record=record,
        sample_index=sample_index,
        source_line=source_line,
        max_replacements_per_sample=args.v4_max_replacements_per_sample,
    )
    stats.add_rejections(local_stats)
    for candidate in candidates:
        replace_candidate = candidate["replace_candidate"]
        edit_type = replace_candidate["edit_type"]
        stats.add_candidate(category, edit_type)
        validation_report = v4.validate_replace_edit(candidate)
        if validation_report.get("ok"):
            stats.add_validated(category, edit_type)
            validated = {
                "candidate_id": candidate["candidate_id"],
                "images": candidate["images"],
                "original_code": candidate["original_code"],
                "intermediate_code": candidate["intermediate_code"],
                "target_code": candidate["target_code"],
                "edit_record": replace_candidate,
                "validation_report": validation_report,
                "fallback_instruction": v4.fallback_instruction(candidate),
            }
            final = v4.final_record(validated)
            sampler.add(edit_type, annotate_sample(final, "V4 replace", category, edit_type, source_line))
        else:
            stats.add_failed(category, edit_type, validation_report)


def call_text(source: str, node: ast.Call, offsets: list[int]) -> str:
    if node.end_lineno is None or node.end_col_offset is None:
        return ""
    start = v3.absolute_position(offsets, node.lineno, node.col_offset)
    end = v3.absolute_position(offsets, node.end_lineno, node.end_col_offset)
    return source[start:end]


def hole_skip_diagnostics(original_code: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    counts["circular_cutout_via_cut_circle_extrude"] += len(V4_CIRCULAR_CUTOUT_RE.findall(original_code))
    try:
        tree = ast.parse(original_code)
    except SyntaxError:
        counts["hole_parse_error_records"] += 1
        return counts

    offsets = v3.line_offsets(original_code)
    all_hole_calls = [node for node in ast.walk(tree) if v3.is_hole_call(node)]
    if not all_hole_calls:
        return counts

    simple_loop_call_ids = {id(hole_node) for _, hole_node, *_ in v3.simple_loop_hole_blocks(tree, original_code, offsets)}
    supported_single_ids = set()
    for node in v3.outer_result_hole_calls(tree):
        if v3.hole_parameters(node) is not None and v3.locate_delete_block(original_code, node, offsets) is not None:
            supported_single_ids.add(id(node))

    counts["hole_calls_total"] += len(all_hole_calls)
    for node in all_hole_calls:
        text = call_text(original_code, node, offsets)
        context_has_array = any(token in text for token in (".pushPoints(", ".rarray(", ".polarArray("))
        if id(node) in supported_single_ids:
            counts["single_high_confidence_hole"] += 1
        elif id(node) in simple_loop_call_ids:
            counts["simple_loop_holes"] += 1
        elif context_has_array:
            counts["pushpoints_rarray_polararray"] += 1
        elif v3.hole_parameters(node) is None:
            counts["non_numeric_diameter"] += 1
        else:
            counts["other_unsupported_hole_contexts"] += 1
    return counts


def merge_hole_diagnostics(
    total: Counter[str],
    by_category: defaultdict[str, Counter[str]],
    category: str,
    original_code: str | None,
) -> None:
    if not original_code:
        total["records_without_code"] += 1
        by_category[category]["records_without_code"] += 1
        return
    diagnostics = hole_skip_diagnostics(original_code)
    total.update(diagnostics)
    by_category[category].update(diagnostics)


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# CAD Edit Coverage Audit - Expert 3",
        "",
        f"Input: `{report['input_path']}`",
        f"Records: {report['input_records']}",
        f"Elapsed seconds: {report['elapsed_seconds']}",
        "",
        "## Branch Summary",
        "",
        "| Branch | Candidates | Validated | Pass Rate | Failed Validation |",
        "|---|---:|---:|---:|---:|",
    ]
    for branch in report["branches"].values():
        lines.append(
            f"| {branch['branch']} | {branch['candidates']} | {branch['validated']} | "
            f"{branch['pass_rate_percent']}% | {branch['failed_validation']} |"
        )

    lines.extend(["", "## By Category", ""])
    for branch_key, branch in report["branches"].items():
        lines.extend([f"### {branch['branch']}", "", "| Category | Candidates | Validated | Pass Rate |", "|---|---:|---:|---:|"])
        for category, counts in branch["by_category"].items():
            lines.append(
                f"| {category} | {counts['candidates']} | {counts['validated']} | {counts['pass_rate_percent']}% |"
            )
        lines.append("")

    lines.extend(["## By Edit Type", ""])
    for branch in report["branches"].values():
        lines.extend([f"### {branch['branch']}", "", "| Edit Type | Candidates | Validated | Pass Rate |", "|---|---:|---:|---:|"])
        for edit_type, counts in branch["by_edit_type"].items():
            lines.append(
                f"| {edit_type} | {counts['candidates']} | {counts['validated']} | {counts['pass_rate_percent']}% |"
            )
        lines.append("")

    lines.extend(["## Top Rejection Reasons", ""])
    for branch in report["branches"].values():
        lines.append(f"### {branch['branch']}")
        reasons = branch["top_rejection_reasons"]
        if not reasons:
            lines.append("")
            lines.append("No rejection reasons recorded.")
            lines.append("")
            continue
        lines.extend(["", "| Reason | Count |", "|---|---:|"])
        for reason, count in reasons.items():
            lines.append(f"| `{reason}` | {count} |")
        lines.append("")

    lines.extend(["## V4 Hole Diagnostics", "", "| Type | Count |", "|---|---:|"])
    for key, value in report["v4_hole_diagnostics"]["overall"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "### V4 Hole Diagnostics By Category", ""])
    for category, counts in report["v4_hole_diagnostics"]["by_category"].items():
        lines.extend([f"#### {category}", "", "| Type | Count |", "|---|---:|"])
        for key, value in counts.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")

    lines.extend(
        [
            "## Render Preview",
            "",
            f"Sample JSONL: `{report['sample_records_path']}`",
            f"Gallery: `{report['render_gallery_path']}`",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("data_expert3_fixed_paths.jsonl"), type=Path)
    parser.add_argument("--output-dir", default=Path("outputs/coverage_expert3"), type=Path)
    parser.add_argument("--start-index", default=1, type=int, help="1-based input record index to start processing.")
    parser.add_argument("--limit", default=None, type=int)
    parser.add_argument("--seed", default=0, type=int)
    parser.add_argument("--samples-per-edit-type", default=3, type=int)
    parser.add_argument("--timeout-seconds", default=20, type=int)
    parser.add_argument("--validator-python", default=None)
    parser.add_argument("--progress-every", default=250, type=int)
    parser.add_argument("--checkpoint-every", default=500, type=int)
    parser.add_argument("--v1-max-edits-per-sample", default=3, type=int)
    parser.add_argument("--v1-scale-factor", default=1.5, type=float)
    parser.add_argument("--v1-validation-mode", choices=("cadquery", "syntax"), default="cadquery")
    parser.add_argument(
        "--v1-audit-validation",
        choices=("inprocess", "subprocess"),
        default="inprocess",
        help="Use in-process CadQuery execution for faster audit, or subprocess to mirror V1 generator exactly.",
    )
    parser.add_argument("--v2-max-edits-per-sample", default=4, type=int)
    parser.add_argument("--v3-max-deletes-per-sample", default=2, type=int)
    parser.add_argument("--v4-max-replacements-per-sample", default=1, type=int)
    parser.add_argument(
        "--branches",
        default=",".join(BRANCH_NAMES),
        help="Comma-separated audit branches to run: v1_parameter,v2_add,v3_delete,v4_replace.",
    )
    return parser.parse_args(argv)


def selected_branch_keys(raw: str) -> list[str]:
    keys = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = [key for key in keys if key not in BRANCH_NAMES]
    if unknown:
        raise ValueError(f"unsupported audit branch(es): {', '.join(unknown)}")
    return keys


def build_report(
    args: argparse.Namespace,
    branch_stats: dict[str, BranchStats],
    category_records: Counter[str],
    hole_diagnostics: Counter[str],
    hole_diagnostics_by_category: defaultdict[str, Counter[str]],
    sampler: ReservoirSampler,
    input_records: int,
    elapsed_seconds: float,
) -> dict[str, Any]:
    output_dir = args.output_dir
    return {
        "input_path": str(args.input),
        "input_records": input_records,
        "start_index": args.start_index,
        "limit": args.limit,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "category_records": dict(sorted(category_records.items())),
        "branches": {key: branch_stats[key].to_dict() for key in sorted(branch_stats)},
        "v4_hole_diagnostics": {
            "overall": dict(hole_diagnostics.most_common()),
            "by_category": {
                category: dict(counts.most_common()) for category, counts in sorted(hole_diagnostics_by_category.items())
            },
        },
        "sample_seen_counts": sampler.counts(),
        "sample_records_path": str(output_dir / "preview_samples.jsonl"),
        "render_gallery_path": str(output_dir / "preview_gallery" / "index.html"),
    }


def write_report_files(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "coverage_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "coverage_audit.md").write_text(markdown_report(report), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sampler = ReservoirSampler(args.samples_per_edit_type, args.seed)
    selected_branches = selected_branch_keys(args.branches)
    branch_stats = {key: BranchStats(BRANCH_NAMES[key]) for key in selected_branches}
    category_records: Counter[str] = Counter()
    hole_diagnostics: Counter[str] = Counter()
    hole_diagnostics_by_category: defaultdict[str, Counter[str]] = nested_counter()

    start_time = time.time()
    input_records = 0
    for sample_index, (source_line, record) in enumerate(read_jsonl(args.input), start=1):
        if sample_index < args.start_index:
            continue
        if args.limit is not None and input_records >= args.limit:
            break
        input_records += 1
        images = v1.extract_images(record)
        category = category_from_images(images)
        category_records[category] += 1
        original_code = v1.extract_original_code(record)
        merge_hole_diagnostics(hole_diagnostics, hole_diagnostics_by_category, category, original_code)

        if "v1_parameter" in branch_stats:
            audit_v1_record(record, source_line, sample_index, category, branch_stats["v1_parameter"], sampler, args)
        if "v2_add" in branch_stats:
            audit_v2_record(record, source_line, sample_index, category, branch_stats["v2_add"], sampler, args)
        if "v3_delete" in branch_stats:
            audit_v3_record(record, source_line, sample_index, category, branch_stats["v3_delete"], sampler, args)
        if "v4_replace" in branch_stats:
            audit_v4_record(record, source_line, sample_index, category, branch_stats["v4_replace"], sampler, args)

        if args.progress_every > 0 and input_records % args.progress_every == 0:
            elapsed = time.time() - start_time
            print(
                json.dumps(
                    {
                        "processed": input_records,
                        "elapsed_seconds": round(elapsed, 2),
                        "v1_candidates": branch_stats["v1_parameter"].candidates
                        if "v1_parameter" in branch_stats
                        else None,
                        "v2_candidates": branch_stats["v2_add"].candidates if "v2_add" in branch_stats else None,
                        "v3_candidates": branch_stats["v3_delete"].candidates if "v3_delete" in branch_stats else None,
                        "v4_candidates": branch_stats["v4_replace"].candidates if "v4_replace" in branch_stats else None,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        if args.checkpoint_every > 0 and input_records % args.checkpoint_every == 0:
            report = build_report(
                args,
                branch_stats,
                category_records,
                hole_diagnostics,
                hole_diagnostics_by_category,
                sampler,
                input_records,
                time.time() - start_time,
            )
            write_report_files(report, args.output_dir)
            write_jsonl(args.output_dir / "preview_samples.jsonl", sampler.records())

    report = build_report(
        args,
        branch_stats,
        category_records,
        hole_diagnostics,
        hole_diagnostics_by_category,
        sampler,
        input_records,
        time.time() - start_time,
    )
    write_report_files(report, args.output_dir)
    write_jsonl(args.output_dir / "preview_samples.jsonl", sampler.records())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
