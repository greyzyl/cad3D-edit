#!/usr/bin/env python3
"""Generate human-like CAD edit instructions with Bailian multimodal models."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_MODEL = "qwen-vl-plus"
DEFAULT_API_KEY_ENVS = ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY")
FORBIDDEN_CODE_TOKENS = ("cadquery", "cq.", "workplane", "```", "result =", "target_code")
FORBIDDEN_V1_COMPLEX_EDIT_TOKENS = ("新增", "添加", "删除", "移除", "移动", "旋转", "复制", "替换")
FORBIDDEN_V2_UNSUPPORTED_EDIT_TOKENS = ("删除", "移除", "移动", "旋转", "复制", "替换")
FORBIDDEN_V2_IMPLEMENTATION_TOKENS = ("workplane", "工作平面", "原点", "xy", "xz", "yz")


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


def first_api_key(env_names: list[str]) -> tuple[str, str]:
    for env_name in env_names:
        value = os.environ.get(env_name)
        if value:
            return value, env_name
    joined = ", ".join(env_names)
    raise RuntimeError(f"missing API key; set one of: {joined}")


def resolve_image_path(image_root: Path, image_path: str) -> Path:
    path = Path(image_path)
    if path.is_absolute():
        return path
    return image_root / path


def image_to_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type is None:
        mime_type = "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{data}"


def number_variants(value: Any) -> set[str]:
    if not isinstance(value, (int, float)):
        return {str(value)}
    rounded = round(float(value), 3)
    variants = {str(rounded), f"{rounded:.1f}", f"{rounded:.3f}".rstrip("0").rstrip(".")}
    if rounded == int(rounded):
        variants.add(str(int(rounded)))
    return {item for item in variants if item}


def edit_candidate_from_record(record: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("edit_candidate", "structural_candidate", "edit_record"):
        value = record.get(key)
        if isinstance(value, dict):
            return value
    return None


def is_structural_record(record: dict[str, Any]) -> bool:
    candidate = edit_candidate_from_record(record)
    return isinstance(candidate, dict) and isinstance(candidate.get("edit_type"), str)


def instruction_mode(record: dict[str, Any]) -> str:
    return "structural" if is_structural_record(record) else "parameter"


def fallback_structural_instruction(edit_record: dict[str, Any]) -> str:
    primitive = edit_record.get("primitive")
    if not isinstance(primitive, dict):
        primitive = {}
    edit_type = edit_record.get("edit_type")
    if edit_type == "add_through_hole":
        radius = primitive.get("radius", "")
        return f"在零件主平面上添加一个半径为 {radius} 的贯穿圆孔。"
    if edit_type == "add_blind_hole":
        radius = primitive.get("radius", "")
        depth = primitive.get("depth", "")
        return f"在零件主平面上添加一个半径为 {radius}、深度为 {depth} 的盲孔。"
    if edit_type == "add_rectangular_slot":
        return "在零件主平面上添加一个矩形槽。"
    if edit_type == "add_pocket":
        return "在零件主平面上添加一个矩形凹陷。"
    return "在零件主平面上添加一个局部结构。"


def fallback_instruction(record: dict[str, Any]) -> str:
    existing = record.get("fallback_instruction")
    if isinstance(existing, str) and existing.strip():
        return existing

    edit_record = edit_candidate_from_record(record)
    if not isinstance(edit_record, dict):
        return "根据给定参数修改零件尺寸，其他结构保持不变。"
    if isinstance(edit_record.get("edit_type"), str):
        return fallback_structural_instruction(edit_record)
    call = edit_record.get("call", "参数")
    old = edit_record.get("old", "")
    new = edit_record.get("new", "")
    return f"将 {call} 的参数从 {old} 修改为 {new}，其他结构保持不变。"


def build_prompt_text(record: dict[str, Any]) -> str:
    edit_candidate = edit_candidate_from_record(record)
    validation_report = record.get("validation_report")
    mode = instruction_mode(record)
    if mode == "structural":
        important_rules = [
            "只输出自然语言编辑指令，不要输出 CadQuery 代码。",
            "这是 V2 结构级 add-only 编辑，必须忠实表达 edit_candidate 中的 edit_type、target_region 和 primitive。",
            "如果 edit_candidate 中包含 instruction_hints，优先使用 instruction_hints 里的 human_feature_name、diameter、length、width、depth。",
            "可以使用添加孔、开槽、添加凹陷等人类 CAD 编辑表达。",
            "可以提到孔径、半径、深度、槽尺寸等 primitive 尺寸。",
            "不要把 insertion_strategy.extrude、cutter depth 或贯穿切削余量描述成用户要求的特征深度。",
            "不要照抄 Workplane、XY/XZ/YZ 平面、原点、坐标值或坐标轴正负方向等代码实现细节。",
            "如果位置无法从三视图稳定判断，就用主平面、外表面、靠右区域、中心附近等视觉表达，或者不描述精确位置。",
            "不要描述删除、移动、旋转、替换，除非 edit_candidate 明确支持。",
            "不要虚构未出现在 edit_candidate 或三视图中的额外结构、数量或位置。",
            "修改后的目标代码已经通过验证，但不会提供给你。",
        ]
        task = "为 CAD 结构级编辑数据生成自然语言指令"
        output_schema = {
            "instruction": "一句中文 CAD 结构编辑指令",
            "confidence": "high|medium|low",
            "mentions_old_new_values": False,
        }
    else:
        important_rules = [
            "只输出自然语言编辑指令，不要输出 CadQuery 代码。",
            "不要描述新增、删除、移动、旋转、替换等 V1 不支持的复杂编辑。",
            "必须忠实表达 edit_candidate 中的 old -> new。",
            "可以参考原始三视图，让表达更像人类 CAD 编辑请求。",
            "如果无法从三视图判断语义，就退化为参数级描述。",
            "修改后的目标代码已经通过验证，但不会提供给你。",
        ]
        task = "为 CAD 参数级编辑数据生成自然语言指令"
        output_schema = {
            "instruction": "一句中文 CAD 参数编辑指令",
            "confidence": "high|medium|low",
            "mentions_old_new_values": True,
        }
    prompt_payload = {
        "task": task,
        "instruction_mode": mode,
        "important_rules": important_rules,
        "original_cadquery_code": record.get("original_code"),
        "edit_candidate": edit_candidate,
        "validation": {
            "edited_code_executed": True,
            "ok": isinstance(validation_report, dict) and validation_report.get("ok") is True,
        },
        "output_schema": output_schema,
    }
    return (
        "请根据原始带尺寸三视图、原始 CadQuery 代码和 edit_candidate，生成贴近人类习惯的 CAD 编辑指令。\n"
        "你必须只返回一个 JSON 对象，不要返回 Markdown。\n\n"
        f"{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}"
    )


def build_messages(record: dict[str, Any], image_root: Path, allow_missing_images: bool) -> tuple[list[dict[str, Any]], int]:
    content: list[dict[str, Any]] = [{"type": "text", "text": build_prompt_text(record)}]
    image_count = 0
    images = record.get("images")
    if isinstance(images, list):
        for image_path in images:
            if not isinstance(image_path, str):
                continue
            resolved = resolve_image_path(image_root, image_path)
            if not resolved.exists():
                if allow_missing_images:
                    continue
                raise FileNotFoundError(f"image not found: {resolved}")
            content.append({"type": "image_url", "image_url": {"url": image_to_data_url(resolved)}})
            image_count += 1

    mode = instruction_mode(record)
    if mode == "structural":
        system_content = "你是 CAD 数据集构造助手，负责把确定性的结构级编辑改写成人类自然编辑指令。"
    else:
        system_content = "你是 CAD 数据集构造助手，负责把确定性的参数编辑改写成人类自然编辑指令。"

    return [
        {
            "role": "system",
            "content": system_content,
        },
        {"role": "user", "content": content},
    ], image_count


def call_bailian_chat(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        base_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def response_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("response missing choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("response missing choices[0].message")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                texts.append(item["text"])
        if texts:
            return "\n".join(texts)
    raise ValueError("response message content is not text")


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("model output JSON must be an object")
    return value


def validate_instruction(instruction: str, record: dict[str, Any], require_values: bool) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    normalized = instruction.lower()
    structural = is_structural_record(record)
    if not instruction.strip():
        reasons.append("empty instruction")
    if any(token in normalized for token in FORBIDDEN_CODE_TOKENS):
        reasons.append("instruction contains code-like token")
    if structural:
        if any(token in instruction for token in FORBIDDEN_V2_UNSUPPORTED_EDIT_TOKENS):
            reasons.append("instruction mentions unsupported structural edit")
        if any(token in normalized for token in FORBIDDEN_V2_IMPLEMENTATION_TOKENS):
            reasons.append("instruction mentions implementation detail")
    elif any(token in instruction for token in FORBIDDEN_V1_COMPLEX_EDIT_TOKENS):
        reasons.append("instruction mentions unsupported complex edit")

    if require_values and not structural:
        edit_record = edit_candidate_from_record(record)
        if isinstance(edit_record, dict):
            old_variants = number_variants(edit_record.get("old"))
            new_variants = number_variants(edit_record.get("new"))
            if not any(item in instruction for item in old_variants):
                reasons.append("instruction does not mention old value")
            if not any(item in instruction for item in new_variants):
                reasons.append("instruction does not mention new value")

    return not reasons, reasons


def build_instruction_record(
    record: dict[str, Any],
    instruction: str,
    model: str,
    base_url: str,
    image_count: int,
    fallback_used: bool,
    quality_reasons: list[str],
    api_key_env: str | None,
    raw_response: dict[str, Any] | None,
    save_raw_response: bool,
) -> dict[str, Any]:
    candidate_id = record.get("candidate_id")
    if not isinstance(candidate_id, str):
        raise ValueError("validated edit record missing candidate_id")

    meta: dict[str, Any] = {
        "generator": "fallback_template" if fallback_used else "bailian_mllm",
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "used_images_count": image_count,
        "used_original_code": True,
        "used_candidate": True,
        "included_target_code": False,
        "instruction_mode": instruction_mode(record),
        "validation_ok": True,
        "fallback_used": fallback_used,
        "quality_reasons": quality_reasons,
    }
    if raw_response is not None:
        usage = raw_response.get("usage")
        if isinstance(usage, dict):
            meta["usage"] = usage
        if save_raw_response:
            meta["raw_response"] = raw_response

    return {
        "candidate_id": candidate_id,
        "instruction": instruction,
        "instruction_meta": meta,
    }


def generate_one_instruction(
    record: dict[str, Any],
    args: argparse.Namespace,
    api_key: str | None,
    api_key_env: str | None,
) -> dict[str, Any]:
    messages, image_count = build_messages(record, args.image_root, args.allow_missing_images)
    fallback = fallback_instruction(record)
    raw_response = None

    if args.dry_run:
        return build_instruction_record(
            record,
            fallback,
            args.model,
            args.base_url,
            image_count,
            True,
            ["dry run"],
            api_key_env,
            None,
            args.save_raw_response,
        )

    try:
        if api_key is None:
            raise RuntimeError("missing API key")
        raw_response = call_bailian_chat(
            args.base_url,
            api_key,
            args.model,
            messages,
            args.temperature,
            args.max_tokens,
            args.timeout_seconds,
        )
        parsed = extract_json_object(response_text(raw_response))
        instruction = parsed.get("instruction")
        if not isinstance(instruction, str):
            raise ValueError("model JSON missing instruction")
        ok, reasons = validate_instruction(instruction, record, args.require_values)
        if not ok:
            if not args.fallback_on_error:
                raise ValueError("; ".join(reasons))
            return build_instruction_record(
                record,
                fallback,
                args.model,
                args.base_url,
                image_count,
                True,
                reasons,
                api_key_env,
                raw_response,
                args.save_raw_response,
            )
        return build_instruction_record(
            record,
            instruction.strip(),
            args.model,
            args.base_url,
            image_count,
            False,
            [],
            api_key_env,
            raw_response,
            args.save_raw_response,
        )
    except Exception as exc:
        if not args.fallback_on_error:
            raise
        return build_instruction_record(
            record,
            fallback,
            args.model,
            args.base_url,
            image_count,
            True,
            [str(exc)],
            api_key_env,
            raw_response,
            args.save_raw_response,
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("outputs/cad_edit_v1_validated_edits.jsonl"), type=Path)
    parser.add_argument("--output", default=Path("outputs/cad_edit_v1_instructions.jsonl"), type=Path)
    parser.add_argument("--image-root", default=Path("."), type=Path)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key-env", default=",".join(DEFAULT_API_KEY_ENVS))
    parser.add_argument("--temperature", default=0.2, type=float)
    parser.add_argument("--max-tokens", default=256, type=int)
    parser.add_argument("--timeout-seconds", default=120, type=int)
    parser.add_argument("--limit", default=None, type=int)
    parser.add_argument("--sleep-seconds", default=0.0, type=float)
    parser.add_argument("--dry-run", action="store_true", help="Write fallback instructions without calling the API.")
    parser.add_argument("--allow-missing-images", action="store_true")
    parser.add_argument("--no-require-values", dest="require_values", action="store_false")
    parser.set_defaults(require_values=True)
    parser.add_argument("--no-fallback-on-error", dest="fallback_on_error", action="store_false")
    parser.set_defaults(fallback_on_error=True)
    parser.add_argument("--save-raw-response", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    records = read_jsonl(args.input)
    if args.limit is not None:
        records = records[: args.limit]

    api_key = None
    api_key_env = None
    if not args.dry_run:
        env_names = [item.strip() for item in args.api_key_env.split(",") if item.strip()]
        api_key, api_key_env = first_api_key(env_names)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "input_records": len(records),
        "output_records": 0,
        "fallback_records": 0,
        "mllm_records": 0,
    }
    with args.output.open("w", encoding="utf-8", newline="\n") as output_handle:
        for index, record in enumerate(records, start=1):
            instruction_record = generate_one_instruction(record, args, api_key, api_key_env)
            output_handle.write(json.dumps(instruction_record, ensure_ascii=False) + "\n")
            summary["output_records"] += 1
            meta = instruction_record.get("instruction_meta")
            if isinstance(meta, dict) and meta.get("fallback_used"):
                summary["fallback_records"] += 1
            else:
                summary["mllm_records"] += 1
            if args.sleep_seconds > 0 and index < len(records):
                time.sleep(args.sleep_seconds)

    summary["output_path"] = str(args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
