#!/usr/bin/env python3
"""Stage 3 assembly of final CAD edit training datasets."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import random
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SPLITS = ("train", "val", "test")
STRUCTURAL_BRANCHES = ("v2_add", "v3_delete", "v4_replace")
BRANCH_TO_FAMILY = {
    "v1_parameter": "parameter",
    "v2_add": "structural_add",
    "v3_delete": "structural_delete",
    "v4_replace": "structural_replace",
}
SYSTEM_PROMPT = "You are an AI assistant specialized in precise CAD editing with CadQuery."

TRAINING_FORBIDDEN_KEYS = {
    "source_sample_id",
    "metadata",
    "hidden",
    "original_code",
    "intermediate_code",
    "edit_record",
    "validation_report",
    "selection_meta",
    "instruction_meta",
}
INSTRUCTION_FORBIDDEN_TOKENS = (
    "cadquery",
    "workplane",
    "result =",
    "source span",
    "block span",
    "source_span",
    "block_span",
    "csg",
    "cutter",
    "target_code",
    "intermediate_code",
    "original_code",
    "source_api",
    "block_text",
    "坐标原点",
    "代码实现",
)


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
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            records.append(value)
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


def resolve_image_path(image_root: Path, image_path: str) -> Path:
    path = Path(image_path)
    if path.is_absolute():
        return path
    return image_root / path


def split_from_intermediate(record: dict[str, Any]) -> str | None:
    selection_meta = record.get("selection_meta")
    if isinstance(selection_meta, dict) and isinstance(selection_meta.get("split"), str):
        return selection_meta["split"]
    return None


def split_from_instruction(record: dict[str, Any]) -> str | None:
    split = record.get("split")
    return split if isinstance(split, str) else None


def instruction_mode(record: dict[str, Any]) -> str:
    meta = record.get("instruction_meta")
    if isinstance(meta, dict) and isinstance(meta.get("instruction_mode"), str):
        return meta["instruction_mode"]
    branch = record.get("branch")
    if branch == "v1_parameter":
        return "parameter"
    if branch == "v2_add":
        return "structural_add"
    if branch == "v3_delete":
        return "structural_delete"
    if branch == "v4_replace":
        return "structural_replace"
    return "unknown"


def instruction_has_forbidden_detail(instruction: str) -> bool:
    lowered = instruction.lower()
    return any(token.lower() in lowered for token in INSTRUCTION_FORBIDDEN_TOKENS)


def image_paths_exist(images: Any, image_root: Path) -> bool:
    if not isinstance(images, list) or not images:
        return False
    for image in images:
        if not isinstance(image, str) or not resolve_image_path(image_root, image).exists():
            return False
    return True


def load_instruction_map(path: Path) -> tuple[dict[str, dict[str, Any]], Counter[str]]:
    records = read_jsonl(path)
    by_id: dict[str, dict[str, Any]] = {}
    warnings: Counter[str] = Counter()
    for record in records:
        sample_id = record.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id:
            warnings["instruction_missing_sample_id"] += 1
            continue
        if sample_id in by_id:
            warnings["duplicate_instruction_sample_id"] += 1
            continue
        by_id[sample_id] = record
    return by_id, warnings


def merge_intermediate_and_instruction(
    intermediate: dict[str, Any],
    instruction_record: dict[str, Any],
    split: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    sample_id = intermediate.get("sample_id")
    if not isinstance(sample_id, str) or not sample_id:
        reasons.append("missing_sample_id")
    if instruction_record.get("sample_id") != sample_id:
        reasons.append("sample_id_mismatch")

    intermediate_split = split_from_intermediate(intermediate)
    instruction_split = split_from_instruction(instruction_record)
    if intermediate_split != split:
        reasons.append("intermediate_split_mismatch")
    if instruction_split != split:
        reasons.append("instruction_split_mismatch")

    instruction = instruction_record.get("instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        reasons.append("missing_instruction")
    elif instruction_has_forbidden_detail(instruction):
        reasons.append("instruction_contains_implementation_detail")

    target_code = intermediate.get("target_code")
    if not isinstance(target_code, str) or not target_code.strip():
        reasons.append("missing_target_code")

    validation_report = intermediate.get("validation_report")
    if not isinstance(validation_report, dict) or validation_report.get("ok") is not True:
        reasons.append("validation_report_not_ok")

    instruction_meta = instruction_record.get("instruction_meta")
    if not isinstance(instruction_meta, dict):
        reasons.append("instruction_meta_missing")
    else:
        validation_ok = instruction_meta.get("validation_ok") is True
        fallback_used = instruction_meta.get("fallback_used") is True
        if not validation_ok and not fallback_used:
            reasons.append("instruction_not_validated")
        if instruction_meta.get("included_target_code") is not False:
            reasons.append("instruction_meta_included_target_code")
        if instruction_meta.get("included_intermediate_code") not in (None, False):
            reasons.append("instruction_meta_included_intermediate_code")

    images = intermediate.get("images")
    if not isinstance(images, list) or not images:
        reasons.append("missing_images")

    if reasons:
        return None, reasons

    assert isinstance(sample_id, str)
    assert isinstance(instruction, str)
    assert isinstance(target_code, str)
    metadata = {
        "branch": intermediate.get("branch"),
        "edit_type": intermediate.get("edit_type"),
        "instruction_meta": instruction_meta,
        "selection_meta": intermediate.get("selection_meta"),
    }
    hidden = {
        "original_code": intermediate.get("original_code"),
        "intermediate_code": intermediate.get("intermediate_code"),
        "edit_record": intermediate.get("edit_record"),
        "validation_report": validation_report,
    }
    return (
        {
            "sample_id": sample_id,
            "source_sample_id": intermediate.get("source_sample_id"),
            "split": split,
            "images": images,
            "instruction": instruction.strip(),
            "target_code": target_code,
            "metadata": metadata,
            "hidden": hidden,
        },
        [],
    )


def build_training_record(full_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": full_record["sample_id"],
        "images": full_record["images"],
        "instruction": full_record["instruction"],
        "target_code": full_record["target_code"],
    }


def build_chat_sft_record(full_record: dict[str, Any]) -> dict[str, Any]:
    user_text = (
        "<image><image><image> Given the original dimensioned three-view drawings and the edit instruction, "
        "generate the edited executable CadQuery code. "
        f"Edit instruction: {full_record['instruction']}"
    )
    return {
        "sample_id": full_record["sample_id"],
        "images": full_record["images"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": f"<code>{full_record['target_code']}</code>"},
        ],
    }


def recursive_forbidden_key_paths(value: Any, forbidden_keys: set[str], prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in forbidden_keys:
                paths.append(path)
            paths.extend(recursive_forbidden_key_paths(item, forbidden_keys, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(recursive_forbidden_key_paths(item, forbidden_keys, f"{prefix}[{index}]"))
    return paths


def validate_training_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed = {"sample_id", "images", "instruction", "target_code"}
    extra = sorted(set(record) - allowed)
    if extra:
        errors.append(f"training_extra_fields:{','.join(extra)}")
    forbidden_paths = recursive_forbidden_key_paths(record, TRAINING_FORBIDDEN_KEYS)
    if forbidden_paths:
        errors.append("training_hidden_field_leak")
    if not isinstance(record.get("instruction"), str) or not record["instruction"].strip():
        errors.append("training_missing_instruction")
    elif instruction_has_forbidden_detail(record["instruction"]):
        errors.append("training_instruction_implementation_detail")
    if not isinstance(record.get("target_code"), str) or not record["target_code"].strip():
        errors.append("training_missing_target_code")
    return errors


def validate_chat_sft_record(record: dict[str, Any], target_code: str, original_code: str | None) -> list[str]:
    errors: list[str] = []
    messages = record.get("messages")
    if not isinstance(messages, list) or len(messages) != 3:
        return ["chat_sft_bad_messages"]
    user_content = messages[1].get("content") if isinstance(messages[1], dict) else None
    assistant_content = messages[2].get("content") if isinstance(messages[2], dict) else None
    if not isinstance(user_content, str):
        errors.append("chat_sft_missing_user_content")
    else:
        if target_code and target_code in user_content:
            errors.append("chat_sft_user_contains_target_code")
        if original_code and original_code in user_content:
            errors.append("chat_sft_user_contains_original_code")
        if "CadQuery code:" in user_content or "original_code" in user_content:
            errors.append("chat_sft_user_code_leak")
    expected = f"<code>{target_code}</code>"
    if assistant_content != expected:
        errors.append("chat_sft_assistant_not_exact_target_code")
    return errors


def leakage_checks(records_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    source_to_split: dict[str, set[str]] = defaultdict(set)
    image_to_split: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for split, records in records_by_split.items():
        for record in records:
            source_id = record.get("source_sample_id")
            if isinstance(source_id, str):
                source_to_split[source_id].add(split)
            image_key = tuple(str(item).replace("\\", "/") for item in record.get("images", []))
            if image_key:
                image_to_split[image_key].add(split)
    source_cross = {key: sorted(value) for key, value in source_to_split.items() if len(value) > 1}
    image_cross = {"|".join(key): sorted(value) for key, value in image_to_split.items() if len(value) > 1}
    return {
        "source_sample_id_cross_split_count": len(source_cross),
        "image_triplet_cross_split_count": len(image_cross),
        "source_sample_id_cross_split_examples": dict(list(source_cross.items())[:10]),
        "image_triplet_cross_split_examples": dict(list(image_cross.items())[:10]),
        "ok": not source_cross and not image_cross,
    }


def branch_family(branch: str) -> str:
    return BRANCH_TO_FAMILY.get(branch, "unknown")


def execute_code_check(source: str, timeout_seconds: int, python_executable: str | None = None) -> dict[str, Any]:
    if not isinstance(source, str) or not source.strip():
        return {"ok": False, "error": "empty source"}
    payload = base64.b64encode(source.encode("utf-8")).decode("ascii")
    runner = (
        "import base64, json, sys\n"
        "import cadquery as cq\n"
        f"source = base64.b64decode({payload!r}).decode('utf-8')\n"
        "ns = {'cq': cq, 'cadquery': cq}\n"
        "try:\n"
        "    exec(compile(source, '<stage3_target>', 'exec'), ns)\n"
        "    result = ns.get('result')\n"
        "    if result is None:\n"
        "        raise RuntimeError('result variable was not defined')\n"
        "    shape = result.val() if hasattr(result, 'val') and callable(result.val) else result\n"
        "    volume = float(shape.Volume()) if hasattr(shape, 'Volume') else None\n"
        "    print(json.dumps({'ok': True, 'volume': volume}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}))\n"
        "    sys.exit(1)\n"
    )
    executable = python_executable or sys.executable
    try:
        completed = subprocess.run(
            [executable, "-c", runner],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout after {timeout_seconds}s"}
    text = (completed.stdout or completed.stderr).strip()
    try:
        parsed = json.loads(text.splitlines()[-1]) if text else {}
    except json.JSONDecodeError:
        parsed = {"ok": False, "error": text or "no output"}
    if completed.returncode != 0:
        parsed["ok"] = False
    return parsed


def sample_for_code_verification(records: list[dict[str, Any]], sample_size: int, seed: int) -> list[dict[str, Any]]:
    if sample_size <= 0:
        return []
    if sample_size >= len(records):
        return list(records)
    rng = random.Random(seed)
    by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        key = (str(record.get("split")), str(metadata.get("branch")), str(metadata.get("edit_type")))
        by_key[key].append(record)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in sorted(by_key):
        record = sorted(by_key[key], key=lambda item: str(item.get("sample_id")))[0]
        selected.append(record)
        seen.add(str(record.get("sample_id")))
        if len(selected) >= sample_size:
            return selected
    remaining = [record for record in records if str(record.get("sample_id")) not in seen]
    rng.shuffle(remaining)
    selected.extend(remaining[: max(0, sample_size - len(selected))])
    return selected


def verify_target_codes(
    records: list[dict[str, Any]],
    sample_size: int,
    verify_all: bool,
    seed: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    selected = list(records) if verify_all else sample_for_code_verification(records, sample_size, seed)
    failures: list[dict[str, Any]] = []
    for record in selected:
        result = execute_code_check(record.get("target_code", ""), timeout_seconds)
        if result.get("ok") is not True:
            failures.append({"sample_id": record.get("sample_id"), "error": result.get("error")})
    return {
        "requested": "all" if verify_all else sample_size,
        "checked": len(selected),
        "failed": len(failures),
        "failures": failures[:50],
        "ok": len(failures) == 0,
    }


def choose_preview_records(records: list[dict[str, Any]], per_edit_type: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        key = (str(record.get("split")), str(metadata.get("branch")), str(metadata.get("edit_type")))
        buckets[key].append(record)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key, bucket in sorted(buckets.items()):
        bucket = list(bucket)
        rng.shuffle(bucket)
        for record in bucket[:per_edit_type]:
            sample_id = str(record.get("sample_id"))
            if sample_id not in seen:
                selected.append(record)
                seen.add(sample_id)
    return selected


def render_gallery(records: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        import cadquery as cq  # type: ignore
        from cadquery import exporters  # type: ignore
    except Exception as exc:  # noqa: BLE001
        index = output_dir / "index.html"
        index.write_text(
            f"<!doctype html><meta charset='utf-8'><p>CadQuery import failed: {html.escape(str(exc))}</p>\n",
            encoding="utf-8",
        )
        return {"records": len(records), "rendered": 0, "failed": len(records), "index": str(index), "error": str(exc)}

    def execute(source: str) -> Any:
        namespace: dict[str, Any] = {"cq": cq, "cadquery": cq}
        exec(compile(source, "<stage3_preview>", "exec"), namespace)
        result = namespace.get("result")
        if result is None:
            raise RuntimeError("result variable was not defined")
        return result.val() if hasattr(result, "val") and callable(result.val) else result

    cards: list[str] = []
    rendered = 0
    failed = 0
    for index, record in enumerate(records, start=1):
        sample_id = str(record.get("sample_id"))
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        hidden = record.get("hidden") if isinstance(record.get("hidden"), dict) else {}
        before_svg = output_dir / f"sample_{index:04d}_before.svg"
        after_svg = output_dir / f"sample_{index:04d}_after.svg"
        error = ""
        before_panel = after_panel = ""
        try:
            original_code = hidden.get("original_code")
            if not isinstance(original_code, str):
                raise RuntimeError("missing original_code")
            before_shape = execute(original_code)
            after_shape = execute(str(record.get("target_code")))
            before_svg.write_text(exporters.getSVG(before_shape), encoding="utf-8", newline="\n")
            after_svg.write_text(exporters.getSVG(after_shape), encoding="utf-8", newline="\n")
            before_panel = f'<object data="{html.escape(before_svg.name)}" type="image/svg+xml"></object>'
            after_panel = f'<object data="{html.escape(after_svg.name)}" type="image/svg+xml"></object>'
            rendered += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            error = f"{type(exc).__name__}: {exc}"
        validation = hidden.get("validation_report") if isinstance(hidden.get("validation_report"), dict) else {}
        checks = validation.get("checks")
        checks_text = ""
        if isinstance(checks, dict):
            bad = [key for key, value in checks.items() if value is not True]
            checks_text = "all checks passed" if not bad else "failed: " + ", ".join(bad[:5])
        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        cards.append(
            f"""
            <section class="pair">
              <header>
                <h2>{html.escape(sample_id)}</h2>
                <span>{html.escape(str(record.get('split')))}</span>
                <span>{html.escape(str(metadata.get('branch')))}</span>
                <span>{html.escape(str(metadata.get('edit_type')))}</span>
              </header>
              <p class="instruction">{html.escape(str(record.get('instruction')))}</p>
              <p class="meta">validation ok={html.escape(str(validation.get('ok')))}; {html.escape(checks_text)}</p>
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
  <title>Final CAD Edit Preview</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; background: #f6f7f8; color: #1f2933; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 20px; font-size: 24px; }}
    .pair {{ background: #fff; border: 1px solid #d8dee4; border-radius: 8px; margin-bottom: 20px; padding: 16px; }}
    .pair header {{ display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; margin-bottom: 8px; }}
    .pair h2 {{ font-size: 17px; margin: 0; flex: 1; }}
    .pair span {{ font-size: 12px; color: #52616b; border: 1px solid #d8dee4; border-radius: 999px; padding: 2px 8px; }}
    .instruction {{ margin: 0 0 8px; font-size: 14px; }}
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
    <h1>Final CAD Edit Preview</h1>
    {''.join(cards)}
  </main>
</body>
</html>
"""
    index_path = output_dir / "index.html"
    index_path.write_text(document, encoding="utf-8", newline="\n")
    return {"records": len(records), "rendered": rendered, "failed": failed, "index": str(index_path)}


def count_records(records_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {split: len(records_by_split.get(split, [])) for split in SPLITS}


def summarize(records_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    branch_counts: Counter[str] = Counter()
    edit_type_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    fallback = 0
    mllm = 0
    sources_by_split: dict[str, set[str]] = {split: set() for split in SPLITS}
    split_branch_counts: dict[str, Counter[str]] = {split: Counter() for split in SPLITS}

    all_records = []
    for split, records in records_by_split.items():
        all_records.extend(records)
        for record in records:
            metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
            branch = str(metadata.get("branch") or "unknown")
            edit_type = str(metadata.get("edit_type") or "unknown")
            branch_counts[branch] += 1
            edit_type_counts[edit_type] += 1
            split_branch_counts[split][branch] += 1
            source_id = record.get("source_sample_id")
            if isinstance(source_id, str):
                sources_by_split[split].add(source_id)
            instruction_meta = metadata.get("instruction_meta") if isinstance(metadata.get("instruction_meta"), dict) else {}
            mode_counts[str(instruction_meta.get("instruction_mode") or instruction_mode(record))] += 1
            if instruction_meta.get("fallback_used") is True:
                fallback += 1
            else:
                mllm += 1

    structural = {
        "add": branch_counts.get("v2_add", 0),
        "delete": branch_counts.get("v3_delete", 0),
        "replace": branch_counts.get("v4_replace", 0),
    }
    positive = [value for value in structural.values() if value > 0]
    ratio = max(positive) / min(positive) if positive else None
    total = len(all_records)
    return {
        "records_total": total,
        "records_by_split": count_records(records_by_split),
        "source_sample_ids_by_split": {split: len(sources_by_split[split]) for split in SPLITS},
        "branch_counts": dict(sorted(branch_counts.items())),
        "edit_type_counts": dict(sorted(edit_type_counts.items())),
        "instruction_mode_counts": dict(sorted(mode_counts.items())),
        "fallback_instruction_count": fallback,
        "fallback_instruction_rate": fallback / total if total else 0.0,
        "mllm_instruction_count": mllm,
        "mllm_instruction_rate": mllm / total if total else 0.0,
        "structural_add_delete_replace_counts": structural,
        "structural_add_delete_replace_max_min_ratio": ratio,
        "structural_add_delete_replace_ratio_lte_9": ratio is not None and ratio <= 9,
        "split_branch_counts": {split: dict(sorted(counter.items())) for split, counter in split_branch_counts.items()},
    }


def training_file_leakage_check(paths: list[Path]) -> dict[str, Any]:
    errors: list[str] = []
    for path in paths:
        for line_number, record in enumerate(read_jsonl(path), start=1):
            record_errors = validate_training_record(record)
            for error in record_errors:
                errors.append(f"{path}:{line_number}:{error}")
    return {"ok": not errors, "errors": errors[:50], "error_count": len(errors)}


def chat_sft_leakage_check(paths: list[Path], full_records_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    for path in paths:
        for line_number, record in enumerate(read_jsonl(path), start=1):
            sample_id = record.get("sample_id")
            full = full_records_by_id.get(sample_id) if isinstance(sample_id, str) else None
            if full is None:
                errors.append(f"{path}:{line_number}:unknown_sample_id")
                continue
            hidden = full.get("hidden") if isinstance(full.get("hidden"), dict) else {}
            original_code = hidden.get("original_code") if isinstance(hidden.get("original_code"), str) else None
            for error in validate_chat_sft_record(record, full.get("target_code", ""), original_code):
                errors.append(f"{path}:{line_number}:{error}")
    return {"ok": not errors, "errors": errors[:50], "error_count": len(errors)}


def write_report(summary: dict[str, Any], path: Path) -> None:
    def table(counts: dict[str, Any], key_name: str = "Name") -> list[str]:
        lines = [f"| {key_name} | Count |", "|---|---:|"]
        for key, value in counts.items():
            lines.append(f"| `{key}` | {value} |")
        return lines

    lines = [
        "# Final Dataset Report",
        "",
        "## Inputs",
        "",
    ]
    for item in summary["input_intermediate_paths"]:
        lines.append(f"- intermediate: `{item}`")
    for item in summary["input_instruction_paths"]:
        lines.append(f"- instruction: `{item}`")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["output_paths"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- total records: `{summary['records_total']}`",
            f"- ready for training: `{summary['ready_for_training']}`",
            "",
            "### Train/Val/Test Records",
            "",
            *table(summary["records_by_split"], "Split"),
            "",
            "### Source Sample IDs",
            "",
            *table(summary["source_sample_ids_by_split"], "Split"),
            "",
            "### Branch Distribution",
            "",
            *table(summary["branch_counts"]),
            "",
            "### Edit Type Distribution",
            "",
            *table(summary["edit_type_counts"]),
            "",
            "### Instruction Modes",
            "",
            *table(summary["instruction_mode_counts"]),
            "",
            "## Instruction Source",
            "",
            f"- fallback count: `{summary['fallback_instruction_count']}`",
            f"- fallback rate: `{summary['fallback_instruction_rate']:.4f}`",
            f"- MLLM count: `{summary['mllm_instruction_count']}`",
            f"- MLLM rate: `{summary['mllm_instruction_rate']:.4f}`",
            "",
            "## Structural Ratio",
            "",
            *table(summary["structural_add_delete_replace_counts"], "Family"),
            "",
            f"Max/min ratio: `{summary['structural_add_delete_replace_max_min_ratio']}`",
            f"Ratio <= 9: `{summary['structural_add_delete_replace_ratio_lte_9']}`",
            "",
            "## Leakage Checks",
            "",
            f"- source split leakage: `{summary['leakage_checks']['source_sample_id_cross_split_count']}`",
            f"- image triplet split leakage: `{summary['leakage_checks']['image_triplet_cross_split_count']}`",
            f"- training-only leakage ok: `{summary['training_only_leakage_check']['ok']}`",
            f"- chat_sft leakage ok: `{summary.get('chat_sft_leakage_check', {}).get('ok')}`",
            f"- instruction implementation-detail leaks: `{summary['instruction_implementation_detail_leaks']}`",
            "",
            "## Image Paths",
            "",
            f"- missing image records: `{summary['missing_image_records']}`",
            f"- image path check ok: `{summary['image_path_check_ok']}`",
            "",
            "## Code Verification",
            "",
            f"- checked: `{summary['code_verification']['checked']}`",
            f"- failed: `{summary['code_verification']['failed']}`",
            f"- ok: `{summary['code_verification']['ok']}`",
            "",
            "## Preview",
            "",
            f"- gallery: `{summary['preview_gallery']['index']}`",
            f"- rendered: `{summary['preview_gallery']['rendered']}`",
            f"- failed: `{summary['preview_gallery']['failed']}`",
            "",
            "## Dropped Records",
            "",
            *table(summary["dropped_reasons"], "Reason"),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def assemble_dataset(args: argparse.Namespace) -> dict[str, Any]:
    records_by_split: dict[str, list[dict[str, Any]]] = {split: [] for split in SPLITS}
    dropped: Counter[str] = Counter()
    input_intermediate_paths: list[str] = []
    input_instruction_paths: list[str] = []
    missing_image_records = 0
    instruction_implementation_detail_leaks = 0

    for split in SPLITS:
        intermediate_path = args.intermediate_dir / f"{split}_intermediate.jsonl"
        instruction_path = args.instruction_dir / f"{split}_instructions.jsonl"
        input_intermediate_paths.append(str(intermediate_path))
        input_instruction_paths.append(str(instruction_path))
        instruction_map, instruction_warnings = load_instruction_map(instruction_path)
        dropped.update(instruction_warnings)
        for intermediate in read_jsonl(intermediate_path):
            sample_id = intermediate.get("sample_id")
            if not isinstance(sample_id, str):
                dropped["intermediate_missing_sample_id"] += 1
                continue
            instruction_record = instruction_map.get(sample_id)
            if instruction_record is None:
                dropped["missing_instruction_record"] += 1
                continue
            if not image_paths_exist(intermediate.get("images"), args.image_root):
                missing_image_records += 1
                if not args.allow_missing_images:
                    dropped["missing_image_path"] += 1
                    continue
            merged, reasons = merge_intermediate_and_instruction(intermediate, instruction_record, split)
            if merged is None:
                dropped.update(reasons)
                if "instruction_contains_implementation_detail" in reasons:
                    instruction_implementation_detail_leaks += 1
                continue
            records_by_split[split].append(merged)

    output_paths: dict[str, str] = {}
    full_paths: list[Path] = []
    training_paths: list[Path] = []
    chat_paths: list[Path] = []
    all_full_records: list[dict[str, Any]] = []
    for split in SPLITS:
        full_records = records_by_split[split]
        all_full_records.extend(full_records)
        training_records = [build_training_record(record) for record in full_records]
        full_path = args.output_dir / "full_metadata" / f"{split}.jsonl"
        training_path = args.output_dir / "training" / f"{split}.jsonl"
        write_jsonl(full_path, full_records)
        write_jsonl(training_path, training_records)
        full_paths.append(full_path)
        training_paths.append(training_path)
        output_paths[f"full_metadata_{split}"] = str(full_path)
        output_paths[f"training_{split}"] = str(training_path)
        if args.export_chat_sft:
            chat_records = [build_chat_sft_record(record) for record in full_records]
            chat_path = args.output_dir / "chat_sft" / f"{split}.jsonl"
            write_jsonl(chat_path, chat_records)
            chat_paths.append(chat_path)
            output_paths[f"chat_sft_{split}"] = str(chat_path)

    summary = summarize(records_by_split)
    summary["input_intermediate_paths"] = input_intermediate_paths
    summary["input_instruction_paths"] = input_instruction_paths
    summary["output_paths"] = output_paths
    summary["dropped_reasons"] = dict(sorted(dropped.items()))
    summary["missing_image_records"] = missing_image_records
    summary["image_path_check_ok"] = missing_image_records == 0 or args.allow_missing_images
    summary["instruction_implementation_detail_leaks"] = instruction_implementation_detail_leaks
    summary["leakage_checks"] = leakage_checks(records_by_split)
    summary["training_only_leakage_check"] = training_file_leakage_check(training_paths)
    full_by_id = {record["sample_id"]: record for record in all_full_records}
    summary["chat_sft_leakage_check"] = chat_sft_leakage_check(chat_paths, full_by_id) if args.export_chat_sft else {
        "ok": True,
        "error_count": 0,
        "errors": [],
    }
    summary["code_verification"] = verify_target_codes(
        all_full_records,
        args.verify_code_sample,
        args.verify_all,
        args.seed,
        args.verify_timeout_seconds,
    )
    preview_records = choose_preview_records(all_full_records, args.preview_per_edit_type, args.seed)
    summary["preview_gallery"] = render_gallery(preview_records, args.output_dir / "preview_gallery")
    summary["ready_for_training"] = (
        summary["records_total"] > 0
        and not dropped
        and summary["leakage_checks"]["ok"]
        and summary["training_only_leakage_check"]["ok"]
        and summary["chat_sft_leakage_check"]["ok"]
        and summary["target_code_nonempty_ok"]
        if "target_code_nonempty_ok" in summary
        else True
    )
    target_nonempty = all(isinstance(record.get("target_code"), str) and bool(record["target_code"].strip()) for record in all_full_records)
    instruction_nonempty = all(isinstance(record.get("instruction"), str) and bool(record["instruction"].strip()) for record in all_full_records)
    summary["target_code_nonempty_ok"] = target_nonempty
    summary["instruction_nonempty_ok"] = instruction_nonempty
    summary["ready_for_training"] = (
        summary["records_total"] > 0
        and not dropped
        and summary["leakage_checks"]["ok"]
        and summary["training_only_leakage_check"]["ok"]
        and summary["chat_sft_leakage_check"]["ok"]
        and summary["image_path_check_ok"]
        and target_nonempty
        and instruction_nonempty
        and summary["instruction_implementation_detail_leaks"] == 0
        and summary["code_verification"]["ok"]
    )
    summary_path = args.output_dir / "final_summary.json"
    report_path = args.output_dir / "final_report.md"
    output_paths["final_summary"] = str(summary_path)
    output_paths["final_report"] = str(report_path)
    output_paths["preview_gallery"] = summary["preview_gallery"]["index"]
    summary["output_paths"] = output_paths
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(summary, report_path)
    return summary


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intermediate-dir", required=True, type=Path)
    parser.add_argument("--instruction-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--export-chat-sft", action="store_true")
    parser.add_argument("--verify-code-sample", default=0, type=int)
    parser.add_argument("--verify-all", action="store_true")
    parser.add_argument("--verify-timeout-seconds", default=20, type=int)
    parser.add_argument("--image-root", default=Path("."), type=Path)
    parser.add_argument("--seed", default=42, type=int)
    parser.add_argument("--allow-missing-images", action="store_true")
    parser.add_argument("--preview-per-edit-type", default=5, type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = assemble_dataset(args)
    printable = {
        "dataset_version": str(args.output_dir),
        "records_by_split": summary["records_by_split"],
        "branch_counts": summary["branch_counts"],
        "edit_type_counts": summary["edit_type_counts"],
        "fallback_rate": summary["fallback_instruction_rate"],
        "mllm_instruction_rate": summary["mllm_instruction_rate"],
        "add_delete_replace_ratio": summary["structural_add_delete_replace_max_min_ratio"],
        "leakage_check_ok": summary["leakage_checks"]["ok"],
        "code_verification": summary["code_verification"],
        "ready_for_training": summary["ready_for_training"],
    }
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0 if summary["ready_for_training"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
