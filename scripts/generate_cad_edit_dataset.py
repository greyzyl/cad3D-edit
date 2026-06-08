#!/usr/bin/env python3
"""Generate deterministic V1 CAD edit dataset records from CADExpert-style JSONL."""

from __future__ import annotations

import argparse
import ast
import base64
import json
import math
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


CADQUERY_MARKERS = ("import cadquery", "cq.Workplane", "cadquery as cq")
CODE_BLOCK_RE = re.compile(r"```(?:python|py|cadquery)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
TAG_BLOCK_RE = re.compile(
    r"<(?P<tag>code|cadquery|python|program)>\s*(?P<body>.*?)\s*</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
GENERIC_TAG_BLOCK_RE = re.compile(
    r"<(?P<tag>[A-Za-z][\w:-]*)[^>]*>\s*(?P<body>.*?)\s*</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")


@dataclass(frozen=True)
class EditCandidate:
    kind: str
    call: str
    arg_index: int
    old: float
    span_start: int
    span_end: int
    matched_text: str


@dataclass(frozen=True)
class EditRecord:
    kind: str
    call: str
    arg_index: int
    old: float
    new: float
    matched_text: str


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value!r}")


def read_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            yield line_number, value


def recursively_collect_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from recursively_collect_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from recursively_collect_strings(item)


def extract_images(record: dict[str, Any]) -> list[str]:
    for key in ("images", "image_paths", "views", "orthographic_views"):
        value = record.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str)]
        if isinstance(value, str):
            return [value]

    image_paths: list[str] = []
    for text in recursively_collect_strings(record):
        lowered = text.lower()
        if lowered.endswith(IMAGE_EXTENSIONS) and text not in image_paths:
            image_paths.append(text)
    return image_paths


def looks_like_cadquery(code: str) -> bool:
    return any(marker in code for marker in CADQUERY_MARKERS)


def strip_code_candidate(code: str) -> str:
    return code.strip().replace("\r\n", "\n").replace("\r", "\n")


def trim_inline_code_candidate(text: str) -> str:
    code_lines: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if stripped.startswith("</") or stripped.startswith("```"):
            break
        code_lines.append(line)
    return strip_code_candidate("\n".join(code_lines))


def extract_inline_cadquery_snippet(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start_index = None
    for index, line in enumerate(lines):
        if looks_like_cadquery(line) or line.lstrip().startswith("result ="):
            start_index = index
            break
    if start_index is None:
        return strip_code_candidate(text)
    return trim_inline_code_candidate("\n".join(lines[start_index:]))


def extract_code_from_text(text: str) -> str | None:
    for match in CODE_BLOCK_RE.finditer(text):
        candidate = strip_code_candidate(match.group(1))
        if looks_like_cadquery(candidate):
            return candidate

    for match in TAG_BLOCK_RE.finditer(text):
        candidate = strip_code_candidate(match.group("body"))
        if looks_like_cadquery(candidate):
            return candidate

    for match in GENERIC_TAG_BLOCK_RE.finditer(text):
        candidate = strip_code_candidate(match.group("body"))
        if looks_like_cadquery(candidate):
            return extract_inline_cadquery_snippet(candidate)

    if looks_like_cadquery(text):
        return extract_inline_cadquery_snippet(text)

    return None


def message_role(message: dict[str, Any]) -> str:
    for key in ("role", "from", "speaker", "author"):
        value = message.get(key)
        if isinstance(value, str):
            return value.lower()
    return ""


def message_content(message: dict[str, Any]) -> str:
    for key in ("content", "value", "text", "message"):
        if key in message:
            return "\n".join(recursively_collect_strings(message[key]))
    return "\n".join(recursively_collect_strings(message))


def iter_message_dicts(record: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for key in ("messages", "conversations", "conversation", "dialogue", "dialog"):
        value = record.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield item


def extract_original_code(record: dict[str, Any]) -> str | None:
    hidden = record.get("hidden")
    if isinstance(hidden, dict) and isinstance(hidden.get("original_code"), str):
        return strip_code_candidate(hidden["original_code"])

    if isinstance(record.get("original_code"), str):
        return strip_code_candidate(record["original_code"])

    assistant_texts: list[str] = []
    fallback_texts: list[str] = []
    for message in iter_message_dicts(record):
        content = message_content(message)
        role = message_role(message)
        if role in {"assistant", "gpt", "model"}:
            assistant_texts.append(content)
        elif content:
            fallback_texts.append(content)

    for text in assistant_texts + fallback_texts:
        code = extract_code_from_text(text)
        if code:
            return code

    for text in recursively_collect_strings(record):
        code = extract_code_from_text(text)
        if code:
            return code

    return None


def line_start_offsets(source: str) -> list[int]:
    offsets = [0]
    for match in re.finditer("\n", source):
        offsets.append(match.end())
    return offsets


def byte_col_to_char_col(line: str, byte_col: int) -> int:
    return len(line.encode("utf-8")[:byte_col].decode("utf-8", errors="ignore"))


def node_span(source: str, starts: list[int], node: ast.AST) -> tuple[int, int] | None:
    if (
        not hasattr(node, "lineno")
        or not hasattr(node, "col_offset")
        or not hasattr(node, "end_lineno")
        or not hasattr(node, "end_col_offset")
    ):
        return None
    lines = source.splitlines(keepends=True)
    start_line = getattr(node, "lineno") - 1
    end_line = getattr(node, "end_lineno") - 1
    if start_line < 0 or end_line < 0 or start_line >= len(lines) or end_line >= len(lines):
        return None
    start_col = byte_col_to_char_col(lines[start_line], getattr(node, "col_offset"))
    end_col = byte_col_to_char_col(lines[end_line], getattr(node, "end_col_offset"))
    return starts[start_line] + start_col, starts[end_line] + end_col


def numeric_value(node: ast.AST) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        value = float(node.value)
        if math.isfinite(value) and value > 0:
            return value
    return None


def editable_arg_indices(call_name: str, arg_count: int) -> list[int]:
    if call_name in {"circle", "hole", "extrude", "chamfer", "fillet"}:
        return [0] if arg_count >= 1 else []
    if call_name == "box":
        return [index for index in (0, 1, 2) if index < arg_count]
    if call_name == "cboreHole":
        return [0] if arg_count >= 1 else []
    return []


class CadEditCandidateVisitor(ast.NodeVisitor):
    def __init__(self, source: str) -> None:
        self.source = source
        self.starts = line_start_offsets(source)
        self.candidates: list[EditCandidate] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
            for arg_index in editable_arg_indices(call_name, len(node.args)):
                arg_node = node.args[arg_index]
                old = numeric_value(arg_node)
                span = node_span(self.source, self.starts, arg_node)
                if old is None or span is None:
                    continue
                matched_text = self.source[span[0] : span[1]]
                kind = "hole" if call_name == "cboreHole" else call_name
                self.candidates.append(
                    EditCandidate(
                        kind=kind,
                        call=call_name,
                        arg_index=arg_index,
                        old=old,
                        span_start=span[0],
                        span_end=span[1],
                        matched_text=matched_text,
                    )
                )
        self.generic_visit(node)


def find_edit_candidates(source: str) -> list[EditCandidate]:
    tree = ast.parse(source)
    visitor = CadEditCandidateVisitor(source)
    visitor.visit(tree)
    return sorted(visitor.candidates, key=lambda candidate: (candidate.span_start, candidate.span_end))


def format_number(value: float) -> str:
    rounded = round(value, 3)
    if rounded == int(rounded):
        return str(int(rounded))
    text = f"{rounded:.3f}".rstrip("0").rstrip(".")
    return text


def format_instruction_number(value: float) -> str:
    rounded = round(value, 3)
    if rounded == int(rounded):
        return f"{rounded:.1f}"
    return f"{rounded:.3f}".rstrip("0").rstrip(".")


def deterministic_new_value(old: float, scale_factor: float) -> float | None:
    new = round(old * scale_factor, 3)
    if not math.isfinite(new) or new <= 0 or new == old:
        return None
    return new


def apply_edit(source: str, candidate: EditCandidate, scale_factor: float) -> tuple[str, EditRecord] | None:
    new = deterministic_new_value(candidate.old, scale_factor)
    if new is None:
        return None

    replacement = format_number(new)
    edited = source[: candidate.span_start] + replacement + source[candidate.span_end :]
    record = EditRecord(
        kind=candidate.kind,
        call=candidate.call,
        arg_index=candidate.arg_index,
        old=round(candidate.old, 3),
        new=new,
        matched_text=candidate.matched_text,
    )
    return edited, record


def build_candidate_record(
    sample_index: int,
    source_line: int,
    candidate_index: int,
    images: list[str],
    original_code: str,
    candidate: EditCandidate,
    scale_factor: float,
) -> dict[str, Any] | None:
    new = deterministic_new_value(candidate.old, scale_factor)
    if new is None:
        return None

    return {
        "candidate_id": f"{sample_index:06d}_{candidate_index:03d}",
        "sample_index": sample_index,
        "source_line": source_line,
        "images": images,
        "original_code": original_code,
        "edit_candidate": {
            "kind": candidate.kind,
            "call": candidate.call,
            "arg_index": candidate.arg_index,
            "old": round(candidate.old, 3),
            "new": new,
            "matched_text": candidate.matched_text,
            "span_start": candidate.span_start,
            "span_end": candidate.span_end,
            "replacement": format_number(new),
            "scale_factor": scale_factor,
        },
    }


def instruction_for_edit(record: EditRecord) -> str:
    old = format_instruction_number(record.old)
    new = format_instruction_number(record.new)
    if record.call == "box":
        axis = ("length", "width", "height")[record.arg_index]
        return f"将 box 的 {axis} 参数从 {old} 修改为 {new}。"
    return f"将 {record.call} 的参数从 {old} 修改为 {new}。"


class ResultAssignmentVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.has_result = False

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == "result" and isinstance(node.ctx, ast.Store):
            self.has_result = True


def parse_and_check_result(source: str) -> tuple[ast.Module | None, str | None]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return None, f"SyntaxError: {exc}"
    visitor = ResultAssignmentVisitor()
    visitor.visit(tree)
    if not visitor.has_result:
        return tree, "result variable was not defined"
    return tree, None


def validate_code(source: str, mode: str, timeout_seconds: int, python_executable: str | None = None) -> dict[str, Any]:
    _, parse_error = parse_and_check_result(source)
    if parse_error:
        return {"ok": False, "mode": mode, "error": parse_error}

    if mode == "syntax":
        return {"ok": True, "mode": mode}

    executable = python_executable or sys.executable
    payload = base64.b64encode(source.encode("utf-8")).decode("ascii")
    runner = (
        "import base64, sys\n"
        f"source = base64.b64decode({payload!r}).decode('utf-8')\n"
        "namespace = {}\n"
        "try:\n"
        "    exec(compile(source, '<cadquery_edit>', 'exec'), namespace)\n"
        "    if 'result' not in namespace:\n"
        "        raise RuntimeError('result variable was not defined')\n"
        "except Exception as exc:\n"
        "    sys.stderr.write(type(exc).__name__ + ': ' + str(exc))\n"
        "    sys.exit(1)\n"
    )

    try:
        completed = subprocess.run(
            [executable, "-c", runner],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "mode": mode, "error": f"validation timed out after {timeout_seconds}s"}

    if completed.returncode != 0:
        error = (completed.stderr or completed.stdout or "cadquery execution failed").strip()
        return {"ok": False, "mode": mode, "error": error}

    return {"ok": True, "mode": mode}


def load_instruction_records(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for line_number, record in read_jsonl(path):
        candidate_id = record.get("candidate_id")
        instruction = record.get("instruction")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError(f"{path}:{line_number}: missing candidate_id")
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError(f"{path}:{line_number}: missing instruction")
        records[candidate_id] = record
    return records


def output_record(
    images: list[str],
    original_code: str,
    edited_code: str,
    edit_record: EditRecord,
    validation_report: dict[str, Any],
    candidate_id: str | None = None,
    instruction: str | None = None,
    instruction_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hidden: dict[str, Any] = {
        "original_code": original_code,
        "edit_record": asdict(edit_record),
        "validation_report": validation_report,
    }
    if candidate_id is not None:
        hidden["candidate_id"] = candidate_id
    if instruction_meta is not None:
        hidden["instruction_meta"] = instruction_meta

    return {
        "images": images,
        "instruction": instruction or instruction_for_edit(edit_record),
        "target_code": edited_code,
        "hidden": hidden,
    }


def validated_edit_record(
    candidate_record: dict[str, Any],
    edited_code: str,
    edit_record: EditRecord,
    validation_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_record["candidate_id"],
        "sample_index": candidate_record["sample_index"],
        "source_line": candidate_record["source_line"],
        "images": candidate_record["images"],
        "original_code": candidate_record["original_code"],
        "edit_candidate": candidate_record["edit_candidate"],
        "target_code": edited_code,
        "edit_record": asdict(edit_record),
        "validation_report": validation_report,
        "fallback_instruction": instruction_for_edit(edit_record),
    }


def generate_records(
    source_record: dict[str, Any],
    sample_index: int,
    source_line: int,
    max_edits_per_sample: int,
    validation_mode: str,
    timeout_seconds: int,
    keep_failed: bool,
    validator_python: str | None,
    scale_factor: float,
    candidate_writer: Callable[[dict[str, Any]], None] | None = None,
    validated_writer: Callable[[dict[str, Any]], None] | None = None,
    instruction_records: dict[str, dict[str, Any]] | None = None,
    require_instructions: bool = False,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    stats: Counter[str] = Counter()
    images = extract_images(source_record)
    original_code = extract_original_code(source_record)
    if not original_code:
        stats["skipped_no_code"] += 1
        return [], stats

    try:
        candidates = find_edit_candidates(original_code)
    except SyntaxError:
        stats["skipped_original_syntax_error"] += 1
        return [], stats

    if not candidates:
        stats["skipped_no_candidates"] += 1
        return [], stats

    records: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(candidates[:max_edits_per_sample], start=1):
        candidate_record = build_candidate_record(
            sample_index=sample_index,
            source_line=source_line,
            candidate_index=candidate_index,
            images=images,
            original_code=original_code,
            candidate=candidate,
            scale_factor=scale_factor,
        )
        if candidate_record is None:
            stats["skipped_bad_edit_value"] += 1
            continue
        if candidate_writer is not None:
            candidate_writer(candidate_record)
        stats["candidate_records"] += 1

        edit_result = apply_edit(original_code, candidate, scale_factor)
        if edit_result is None:
            stats["skipped_bad_edit_value"] += 1
            continue
        edited_code, edit_record = edit_result
        validation_report = validate_code(edited_code, validation_mode, timeout_seconds, validator_python)
        stats["attempted_edits"] += 1
        if validation_report.get("ok"):
            stats["emitted_ok"] += 1
            validated_record = validated_edit_record(candidate_record, edited_code, edit_record, validation_report)
            if validated_writer is not None:
                validated_writer(validated_record)
                stats["validated_output_records"] += 1

            instruction = None
            instruction_meta = None
            instruction_record = None
            if instruction_records is not None:
                instruction_record = instruction_records.get(candidate_record["candidate_id"])
                if instruction_record is not None:
                    instruction = instruction_record["instruction"]
                    meta = instruction_record.get("instruction_meta")
                    if isinstance(meta, dict):
                        instruction_meta = meta
                    stats["final_instruction_mllm"] += 1
                elif require_instructions:
                    stats["skipped_missing_instruction"] += 1
                    continue
            if instruction is None:
                stats["final_instruction_fallback"] += 1

            records.append(
                output_record(
                    images,
                    original_code,
                    edited_code,
                    edit_record,
                    validation_report,
                    candidate_id=candidate_record["candidate_id"],
                    instruction=instruction,
                    instruction_meta=instruction_meta,
                )
            )
        else:
            stats["failed_validation"] += 1
            error = str(validation_report.get("error", "unknown"))
            stats[f"validation_error:{error[:80]}"] += 1
            if keep_failed:
                records.append(
                    output_record(
                        images,
                        original_code,
                        edited_code,
                        edit_record,
                        validation_report,
                        candidate_id=candidate_record["candidate_id"],
                    )
                )
    return records, stats


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("data_t.jsonl"), type=Path, help="Input CADExpert-style JSONL path.")
    parser.add_argument("--output", default=Path("outputs/cad_edit_v1.jsonl"), type=Path, help="Output JSONL path.")
    parser.add_argument(
        "--no-final-output",
        action="store_true",
        help="Only write candidates/validated edits; skip writing the final training JSONL.",
    )
    parser.add_argument(
        "--candidates-output",
        default=None,
        type=Path,
        help="Intermediate JSONL written before P1 generation. Defaults to <output stem>_candidates.jsonl.",
    )
    parser.add_argument(
        "--no-candidates-output",
        action="store_true",
        help="Disable writing the intermediate edit-candidate JSONL.",
    )
    parser.add_argument(
        "--validated-output",
        default=None,
        type=Path,
        help="Validated edits JSONL written after P1 CadQuery validation. Defaults to <output stem>_validated_edits.jsonl.",
    )
    parser.add_argument(
        "--no-validated-output",
        action="store_true",
        help="Disable writing the post-validation edits JSONL.",
    )
    parser.add_argument(
        "--instructions-input",
        default=None,
        type=Path,
        help="Optional MLLM-generated instruction JSONL keyed by candidate_id.",
    )
    parser.add_argument(
        "--require-instructions",
        action="store_true",
        help="Skip final records that do not have a matching instruction in --instructions-input.",
    )
    parser.add_argument("--max-edits-per-sample", default=3, type=int, help="Maximum one-parameter edits per source row.")
    parser.add_argument(
        "--scale-factor",
        default=1.5,
        type=float,
        help="Deterministic multiplier for edited numeric parameters. Use larger values for more visible edits.",
    )
    parser.add_argument(
        "--validation-mode",
        choices=("cadquery", "syntax"),
        default="cadquery",
        help="Validate by executing CadQuery or by syntax/result checks only.",
    )
    parser.add_argument(
        "--keep-failed",
        nargs="?",
        const=True,
        default=False,
        type=parse_bool,
        help="Include validation failures in output JSONL. Accepts true/false.",
    )
    parser.add_argument("--timeout-seconds", default=20, type=int, help="Per-sample CadQuery validation timeout.")
    parser.add_argument(
        "--validator-python",
        default=None,
        help="Python executable used for CadQuery subprocess validation. Defaults to the current interpreter.",
    )
    return parser.parse_args(argv)


def default_candidates_output_path(output_path: Path) -> Path:
    suffix = output_path.suffix or ".jsonl"
    return output_path.with_name(f"{output_path.stem}_candidates{suffix}")


def default_validated_output_path(output_path: Path) -> Path:
    suffix = output_path.suffix or ".jsonl"
    return output_path.with_name(f"{output_path.stem}_validated_edits{suffix}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.max_edits_per_sample <= 0:
        raise ValueError("--max-edits-per-sample must be positive")
    if not math.isfinite(args.scale_factor) or args.scale_factor <= 0:
        raise ValueError("--scale-factor must be a positive finite number")

    output_path: Path = args.output
    if not args.no_final_output:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    candidates_output_path = None
    if not args.no_candidates_output:
        candidates_output_path = args.candidates_output or default_candidates_output_path(output_path)
        candidates_output_path.parent.mkdir(parents=True, exist_ok=True)
    validated_output_path = None
    if not args.no_validated_output:
        validated_output_path = args.validated_output or default_validated_output_path(output_path)
        validated_output_path.parent.mkdir(parents=True, exist_ok=True)

    instruction_records = None
    if args.instructions_input is not None:
        instruction_records = load_instruction_records(args.instructions_input)

    summary: Counter[str] = Counter()
    candidates_handle = None
    validated_handle = None
    output_handle = None
    try:
        if candidates_output_path is not None:
            candidates_handle = candidates_output_path.open("w", encoding="utf-8", newline="\n")
        if validated_output_path is not None:
            validated_handle = validated_output_path.open("w", encoding="utf-8", newline="\n")
        if not args.no_final_output:
            output_handle = output_path.open("w", encoding="utf-8", newline="\n")

        def write_candidate(record: dict[str, Any]) -> None:
            if candidates_handle is None:
                return
            candidates_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            summary["candidate_output_records"] += 1

        def write_validated(record: dict[str, Any]) -> None:
            if validated_handle is None:
                return
            validated_handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        candidate_writer = write_candidate if candidates_handle is not None else None
        validated_writer = write_validated if validated_handle is not None else None

        for sample_index, (source_line, source_record) in enumerate(read_jsonl(args.input), start=1):
            summary["input_records"] += 1
            generated, stats = generate_records(
                source_record=source_record,
                sample_index=sample_index,
                source_line=source_line,
                max_edits_per_sample=args.max_edits_per_sample,
                validation_mode=args.validation_mode,
                timeout_seconds=args.timeout_seconds,
                keep_failed=args.keep_failed,
                validator_python=args.validator_python,
                scale_factor=args.scale_factor,
                candidate_writer=candidate_writer,
                validated_writer=validated_writer,
                instruction_records=instruction_records,
                require_instructions=args.require_instructions,
            )
            summary.update(stats)
            for record in generated:
                if output_handle is None:
                    summary["final_records_not_written"] += 1
                else:
                    output_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    summary["output_records"] += 1
    finally:
        if output_handle is not None:
            output_handle.close()
        if candidates_handle is not None:
            candidates_handle.close()
        if validated_handle is not None:
            validated_handle.close()

    printable_summary = dict(sorted(summary.items()))
    printable_summary["output_path"] = str(output_path)
    if candidates_output_path is not None:
        printable_summary["candidates_output_path"] = str(candidates_output_path)
    if validated_output_path is not None:
        printable_summary["validated_output_path"] = str(validated_output_path)
    print(json.dumps(printable_summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
