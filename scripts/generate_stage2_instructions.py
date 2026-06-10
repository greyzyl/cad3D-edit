#!/usr/bin/env python3
"""Stage 2 MLLM instruction generation for frozen CAD edit intermediates."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_MODEL = "qwen3-vl-plus"
DEFAULT_API_KEY_ENVS = ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY", "QWEN_API_KEY")
SPLITS = ("train", "val", "test")

MODE_BY_BRANCH = {
    "v1_parameter": "parameter",
    "v2_add": "structural_add",
    "v3_delete": "structural_delete",
    "v4_replace": "structural_replace",
}

FORBIDDEN_CODE_TOKENS = (
    "cadquery",
    "cq",
    "workplane",
    "result =",
    "source span",
    "block span",
    "source_span",
    "block_span",
    "csg",
    "cutter",
    "target code",
    "target_code",
    "intermediate code",
    "intermediate_code",
    "source_api",
    "block_text",
    "append_csg",
    "代码",
    "源码",
    "坐标原点",
    "坐标轴",
    "坐标",
    "xy平面",
    "xz平面",
    "yz平面",
    "+x方向",
    "+y方向",
    "+z方向",
    "-x方向",
    "-y方向",
    "-z方向",
    "距离中心",
    "中心约",
)

PRESERVE_PATTERNS = (
    "其余结构保持不变",
    "其他结构保持不变",
    "保持其余结构不变",
    "保持其他结构不变",
    "不改变其余结构",
    "不改变其他结构",
)

ADD_TOKENS = ("添加", "新增", "开孔", "打孔", "开槽", "增加", "加入", "加上", "做一个")
DELETE_TOKENS = ("删除", "移除", "去掉", "去除", "填充", "取消", "恢复为直角", "去掉")
REPLACE_TOKENS = ("替换", "改成", "换成", "变为")
MOVE_TOKENS = ("移动", "旋转", "复制", "平移")

FEATURE_WORDS_BY_EDIT_TYPE = {
    "add_through_hole": ("贯穿圆孔", "通孔", "圆孔"),
    "add_blind_hole": ("盲孔",),
    "add_rectangular_slot": ("矩形槽", "槽"),
    "add_pocket": ("矩形凹陷", "凹陷", "pocket"),
    "delete_hole": ("圆孔", "孔"),
    "delete_circular_cutout": ("圆形切口", "圆形通孔", "圆孔", "切口"),
    "delete_polygonal_cutout": ("多边形通孔", "多边形切口", "边形通孔"),
    "delete_fillet": ("圆角",),
    "delete_chamfer": ("倒角",),
    "replace_circular_cutout_with_slot": ("圆形通孔", "圆形切口", "矩形槽", "槽"),
    "replace_loop_holes_with_slots": ("圆孔", "孔", "矩形槽", "槽"),
    "replace_circular_cutout_with_polygonal_cutout": ("圆形通孔", "圆形切口", "六边形通孔", "多边形通孔"),
    "replace_polygonal_cutout_with_circular_cutout": ("多边形通孔", "边形通孔", "圆形通孔", "圆孔"),
    "replace_polygonal_cutout_with_slot": ("多边形通孔", "边形通孔", "矩形槽", "槽"),
    "replace_chamfer_with_fillet": ("倒角", "圆角"),
    "replace_fillet_with_chamfer": ("圆角", "倒角"),
}

# English Stage 2 prompt/validation constants. These override the legacy
# mojibake constants above while keeping the older file layout stable.
FORBIDDEN_CODE_TOKENS = (
    "cadquery",
    "cq",
    "workplane",
    "result =",
    "source span",
    "block span",
    "source_span",
    "block_span",
    "csg",
    "cutter",
    "target code",
    "target_code",
    "intermediate code",
    "intermediate_code",
    "source_api",
    "block_text",
    "append_csg",
    "code implementation",
    "coordinate origin",
    "coordinate axis",
)

PRESERVE_PATTERNS = (
    "keeping the rest of the part unchanged",
    "keep the rest of the part unchanged",
    "leave the rest of the part unchanged",
    "leaving the rest of the part unchanged",
    "keep the rest of the geometry unchanged",
    "keeping the rest of the geometry unchanged",
    "leaving the rest of the geometry unchanged",
    "without changing the rest of the part",
    "without changing the rest of the geometry",
    "keep all other features unchanged",
    "keeping all other features unchanged",
    "leave all other features unchanged",
    "leaving all other features unchanged",
    "keep all other geometry unchanged",
    "keeping all other geometry unchanged",
    "leave all other geometry unchanged",
    "leaving all other geometry unchanged",
)

ADD_TOKENS = ("add", "create", "drill", "cut a", "cut an", "make a", "make an", "open a", "open an")
DELETE_TOKENS = ("remove", "delete", "eliminate", "get rid of", "fill", "restore")
REPLACE_TOKENS = ("replace", "convert", "swap", "change into", "turn into")
MOVE_TOKENS = ("move", "moving", "rotate", "rotating", "copy", "translate", "translation", "duplicate")

FEATURE_WORDS_BY_EDIT_TYPE = {
    "add_through_hole": ("through circular hole", "through hole", "circular hole", "hole"),
    "add_blind_hole": ("blind hole", "hole"),
    "add_rectangular_slot": ("rectangular slot", "slot"),
    "add_pocket": ("rectangular recess", "pocket", "recess"),
    "delete_hole": ("circular hole", "hole"),
    "delete_circular_cutout": ("circular cutout", "circular through hole", "circular hole", "cutout"),
    "delete_polygonal_cutout": (
        "polygonal through hole",
        "polygonal cutout",
        "polygonal hole",
        "sided through hole",
        "sided cutout",
        "triangular cutout",
        "pentagonal cutout",
        "hexagonal cutout",
    ),
    "delete_fillet": ("fillet", "rounded edge", "round"),
    "delete_chamfer": ("chamfer", "beveled edge", "bevel"),
    "replace_circular_cutout_with_slot": ("circular through hole", "circular cutout", "rectangular slot", "slot"),
    "replace_loop_holes_with_slots": ("circular holes", "holes", "rectangular slots", "slots"),
    "replace_circular_cutout_with_polygonal_cutout": (
        "circular through hole",
        "circular cutout",
        "hexagonal through hole",
        "polygonal through hole",
    ),
    "replace_polygonal_cutout_with_circular_cutout": (
        "polygonal through hole",
        "sided through hole",
        "polygonal cutout",
        "sided cutout",
        "triangular cutout",
        "pentagonal cutout",
        "hexagonal cutout",
        "circular through hole",
        "circular cutout",
        "circular hole",
    ),
    "replace_polygonal_cutout_with_slot": (
        "polygonal through hole",
        "sided through hole",
        "polygonal cutout",
        "sided cutout",
        "triangular cutout",
        "pentagonal cutout",
        "hexagonal cutout",
        "rectangular slot",
        "slot",
    ),
    "replace_chamfer_with_fillet": ("chamfer", "fillet", "rounded edge"),
    "replace_fillet_with_chamfer": ("fillet", "chamfer", "beveled edge"),
}

IMPLEMENTATION_DETAIL_KEYS = {
    "block_span_start",
    "block_span_end",
    "block_text",
    "source_api",
    "replacement",
    "deletion_strategy",
    "insertion_strategy",
    "source_span",
    "source_span_start",
    "source_span_end",
    "append_csg_block",
    "target_region",
    "affected_region_bbox",
    "center",
    "axis",
    "normal",
    "plane",
    "tangent_axes",
    "bbox",
    "origin",
    "translate",
    "workplane",
    "extrude",
    "instruction_template",
    "human_feature_name",
    "old_feature_name",
    "new_feature_name",
    "delete_verbs",
    "replace_verbs",
    "preferred_position_style",
}


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


def append_jsonl(path: Path, records: list[dict[str, Any]], overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "a"
    with path.open(mode, encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_existing_sample_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            sample_id = record.get("sample_id")
            if isinstance(sample_id, str):
                seen.add(sample_id)
    return seen


def first_api_key(env_names: list[str]) -> tuple[str, str]:
    for env_name in env_names:
        value = os.environ.get(env_name)
        if value:
            return value, env_name
    raise RuntimeError(f"missing API key; set one of: {', '.join(env_names)}")


def instruction_mode(record: dict[str, Any]) -> str:
    branch = record.get("branch")
    if isinstance(branch, str) and branch in MODE_BY_BRANCH:
        return MODE_BY_BRANCH[branch]
    edit_type = str(record.get("edit_type") or "")
    if edit_type.startswith("add_"):
        return "structural_add"
    if edit_type.startswith("delete_"):
        return "structural_delete"
    if edit_type.startswith("replace_"):
        return "structural_replace"
    return "parameter"


def normalize_number(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        rounded = round(value, 4)
        if rounded == int(rounded):
            return str(int(rounded))
        return f"{rounded:.4f}".rstrip("0").rstrip(".")
    text = str(value)
    return text.strip()


def number_variants(value: Any) -> set[str]:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        text = str(value).strip()
        return {text} if text else set()
    variants = {normalize_number(value)}
    rounded = round(float(value), 3)
    rounded_2 = round(float(value), 2)
    variants.add(str(rounded))
    variants.add(str(rounded_2))
    variants.add(f"{rounded:.1f}")
    variants.add(f"{rounded_2:.2f}".rstrip("0").rstrip("."))
    variants.add(f"{rounded:.3f}".rstrip("0").rstrip("."))
    if rounded == int(rounded):
        variants.add(str(int(rounded)))
    return {item for item in variants if item}


def mm(value: Any) -> str:
    return f"{normalize_number(value)} mm"


def ensure_preserve_clause(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "其余结构保持不变。"
    if any(pattern in stripped for pattern in PRESERVE_PATTERNS):
        return stripped if stripped.endswith(("。", "！", "？")) else stripped + "。"
    stripped = stripped.rstrip("。！？；;，, ")
    return f"{stripped}，其余结构保持不变。"


def nested_get(mapping: dict[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def instruction_hints(edit_record: dict[str, Any]) -> dict[str, Any]:
    hints = edit_record.get("instruction_hints")
    if isinstance(hints, dict):
        return hints
    return {}


def parameters(edit_record: dict[str, Any]) -> dict[str, Any]:
    params = edit_record.get("parameters")
    if isinstance(params, dict):
        return params
    return {}


def fallback_parameter_instruction(edit_record: dict[str, Any]) -> str:
    call = str(edit_record.get("call") or edit_record.get("kind") or "参数")
    label = {
        "circle": "圆半径",
        "hole": "孔直径",
        "extrude": "拉伸深度",
        "box": "长方体尺寸参数",
        "chamfer": "倒角尺寸",
        "fillet": "圆角半径",
    }.get(call, f"{call} 参数")
    old = normalize_number(edit_record.get("old", ""))
    new = normalize_number(edit_record.get("new", ""))
    return f"将{label}从 {old} 修改为 {new}，其余结构保持不变。"


def fallback_add_instruction(edit_record: dict[str, Any]) -> str:
    edit_type = edit_record.get("edit_type")
    hints = instruction_hints(edit_record)
    primitive = edit_record.get("primitive") if isinstance(edit_record.get("primitive"), dict) else {}
    dims = primitive.get("dims") if isinstance(primitive.get("dims"), dict) else {}

    diameter = hints.get("diameter")
    radius = hints.get("radius", primitive.get("radius"))
    if diameter is None and isinstance(radius, (int, float)):
        diameter = radius * 2
    depth = hints.get("depth", primitive.get("depth"))
    length = hints.get("length", dims.get("x"))
    width = hints.get("width", dims.get("y"))

    if edit_type == "add_through_hole":
        if isinstance(diameter, (int, float)):
            return f"在零件主平面上添加一个直径为 {mm(diameter)} 的贯穿圆孔，其余结构保持不变。"
        return "在零件主平面上添加一个贯穿圆孔，其余结构保持不变。"
    if edit_type == "add_blind_hole":
        if isinstance(diameter, (int, float)) and isinstance(depth, (int, float)):
            return f"在零件主平面上添加一个直径为 {mm(diameter)}、深度为 {mm(depth)} 的盲孔，其余结构保持不变。"
        if isinstance(diameter, (int, float)):
            return f"在零件主平面上添加一个直径为 {mm(diameter)} 的盲孔，其余结构保持不变。"
        return "在零件主平面上添加一个盲孔，其余结构保持不变。"
    if edit_type == "add_rectangular_slot":
        if isinstance(length, (int, float)) and isinstance(width, (int, float)):
            return f"在零件主平面上添加一个长度为 {mm(length)}、宽度为 {mm(width)} 的矩形槽，其余结构保持不变。"
        return "在零件主平面上添加一个矩形槽，其余结构保持不变。"
    if edit_type == "add_pocket":
        if all(isinstance(value, (int, float)) for value in (length, width, depth)):
            return f"在零件主平面上添加一个长度为 {mm(length)}、宽度为 {mm(width)}、深度为 {mm(depth)} 的矩形凹陷，其余结构保持不变。"
        if isinstance(length, (int, float)) and isinstance(width, (int, float)):
            return f"在零件主平面上添加一个长度为 {mm(length)}、宽度为 {mm(width)} 的矩形凹陷，其余结构保持不变。"
        return "在零件主平面上添加一个矩形凹陷，其余结构保持不变。"

    template = edit_record.get("instruction_template")
    if isinstance(template, str) and template.strip():
        return ensure_preserve_clause(template)
    feature_name = str(hints.get("human_feature_name") or "局部结构")
    return f"在零件主平面上添加一个{feature_name}，其余结构保持不变。"


def fallback_delete_instruction(edit_record: dict[str, Any]) -> str:
    edit_type = edit_record.get("edit_type")
    hints = instruction_hints(edit_record)
    params = parameters(edit_record)
    diameter = hints.get("diameter", params.get("diameter"))
    radius = hints.get("radius", params.get("radius"))
    sides = hints.get("sides", params.get("sides"))
    count = hints.get("count", params.get("count"))
    distance = hints.get("distance", params.get("distance"))
    feature_name = str(hints.get("human_feature_name") or "")

    if edit_type == "delete_hole":
        if isinstance(count, int) and count > 1 and isinstance(diameter, (int, float)):
            return f"删除零件上这组 {count} 个直径为 {mm(diameter)} 的圆孔，其余结构保持不变。"
        if isinstance(diameter, (int, float)):
            return f"删除零件上直径为 {mm(diameter)} 的圆孔，其余结构保持不变。"
        return "删除零件上的圆孔，其余结构保持不变。"
    if edit_type == "delete_circular_cutout":
        name = feature_name or "圆形切口"
        if isinstance(diameter, (int, float)):
            return f"删除零件上直径为 {mm(diameter)} 的{name}，其余结构保持不变。"
        if isinstance(radius, (int, float)):
            return f"删除零件上半径为 {mm(radius)} 的{name}，其余结构保持不变。"
        return f"删除零件上的{name}，其余结构保持不变。"
    if edit_type == "delete_polygonal_cutout":
        if isinstance(sides, int) and isinstance(radius, (int, float)):
            return f"删除零件上半径为 {mm(radius)} 的 {sides} 边形通孔，其余结构保持不变。"
        return "删除零件上的多边形通孔，其余结构保持不变。"
    if edit_type == "delete_fillet":
        if isinstance(radius, (int, float)):
            return f"删除零件边缘半径为 R{normalize_number(radius)} 的圆角，使边缘恢复为直角，其余结构保持不变。"
        return "删除零件边缘的圆角，使边缘恢复为直角，其余结构保持不变。"
    if edit_type == "delete_chamfer":
        if isinstance(distance, (int, float)):
            return f"删除零件边缘尺寸为 C{normalize_number(distance)} 的倒角，使边缘恢复为直角，其余结构保持不变。"
        return "删除零件边缘的倒角，使边缘恢复为直角，其余结构保持不变。"

    template = edit_record.get("instruction_template")
    if isinstance(template, str) and template.strip():
        return ensure_preserve_clause(template)
    return f"删除零件上的{feature_name or '目标结构'}，其余结构保持不变。"


def old_feature_params(edit_record: dict[str, Any]) -> dict[str, Any]:
    old_feature = edit_record.get("old_feature")
    if isinstance(old_feature, dict):
        return parameters(old_feature)
    return {}


def fallback_replace_instruction(edit_record: dict[str, Any]) -> str:
    edit_type = edit_record.get("edit_type")
    hints = instruction_hints(edit_record)
    old_name = str(hints.get("old_feature_name") or "目标结构")
    new_name = str(hints.get("new_feature_name") or "新结构")
    diameter = hints.get("diameter", old_feature_params(edit_record).get("diameter"))
    radius = hints.get("radius")
    sides = hints.get("sides")
    count = nested_get(edit_record, "old_feature", "parameters", "count")
    length = hints.get("length", nested_get(edit_record, "new_feature", "human_dimensions", "length"))
    width = hints.get("width", nested_get(edit_record, "new_feature", "human_dimensions", "width"))
    distance = hints.get("distance")

    if edit_type in {"replace_circular_cutout_with_slot", "replace_loop_holes_with_slots", "replace_polygonal_cutout_with_slot"}:
        prefix = f"将零件上的{old_name}"
        if edit_type == "replace_loop_holes_with_slots" and isinstance(count, int) and count > 1:
            prefix = f"将零件上这组 {count} 个{old_name}"
        if isinstance(diameter, (int, float)):
            prefix = f"将零件上直径为 {mm(diameter)} 的{old_name}"
        if isinstance(length, (int, float)) and isinstance(width, (int, float)):
            return f"{prefix}替换为长度为 {mm(length)}、宽度为 {mm(width)} 的矩形槽，其余结构保持不变。"
        return f"{prefix}替换为矩形槽，其余结构保持不变。"
    if edit_type == "replace_circular_cutout_with_polygonal_cutout":
        if isinstance(radius, (int, float)):
            return f"将零件上半径为 {mm(radius)} 的圆形通孔替换为六边形通孔，其余结构保持不变。"
        return "将零件上的圆形通孔替换为六边形通孔，其余结构保持不变。"
    if edit_type == "replace_polygonal_cutout_with_circular_cutout":
        if isinstance(sides, int):
            return f"将零件上的 {sides} 边形通孔替换为圆形通孔，其余结构保持不变。"
        return "将零件上的多边形通孔替换为圆形通孔，其余结构保持不变。"
    if edit_type == "replace_chamfer_with_fillet":
        if isinstance(distance, (int, float)) and isinstance(radius, (int, float)):
            return f"将零件边缘尺寸为 C{normalize_number(distance)} 的倒角替换为 R{normalize_number(radius)} 的圆角，其余结构保持不变。"
        return "将零件边缘的倒角替换为圆角，其余结构保持不变。"
    if edit_type == "replace_fillet_with_chamfer":
        if isinstance(radius, (int, float)) and isinstance(distance, (int, float)):
            return f"将零件边缘半径为 R{normalize_number(radius)} 的圆角替换为 C{normalize_number(distance)} 的倒角，其余结构保持不变。"
        return "将零件边缘的圆角替换为倒角，其余结构保持不变。"

    template = edit_record.get("instruction_template")
    if isinstance(template, str) and template.strip():
        return ensure_preserve_clause(template)
    return f"将零件上的{old_name}替换为{new_name}，其余结构保持不变。"


def fallback_instruction(record: dict[str, Any]) -> str:
    edit_record = record.get("edit_record")
    if not isinstance(edit_record, dict):
        return "根据给定编辑记录修改零件，其余结构保持不变。"
    mode = instruction_mode(record)
    if mode == "parameter":
        return fallback_parameter_instruction(edit_record)
    if mode == "structural_add":
        return fallback_add_instruction(edit_record)
    if mode == "structural_delete":
        return fallback_delete_instruction(edit_record)
    if mode == "structural_replace":
        return fallback_replace_instruction(edit_record)
    return ensure_preserve_clause(str(edit_record.get("instruction_template") or "修改零件局部结构。"))


def sanitize_for_prompt(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if key_text in IMPLEMENTATION_DETAIL_KEYS:
                continue
            if "span" in lowered or "block_text" in lowered:
                continue
            if key_text == "avoid_implementation_details":
                continue
            sanitized[key_text] = sanitize_for_prompt(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_prompt(item) for item in value]
    return value


def validation_summary(record: dict[str, Any]) -> dict[str, Any]:
    report = record.get("validation_report")
    if not isinstance(report, dict):
        return {"ok": False}
    checks = report.get("checks")
    good_checks = []
    if isinstance(checks, dict):
        good_checks = [key for key, value in checks.items() if value is True]
    summary: dict[str, Any] = {
        "ok": report.get("ok") is True,
        "mode": report.get("mode"),
        "passed_checks": good_checks[:20],
    }
    for key in ("volume_delta", "final_volume_delta"):
        value = report.get(key)
        if isinstance(value, (int, float)):
            summary[key] = value
    return summary


def prompt_rules(mode: str) -> list[str]:
    common = [
        "只生成一条中文 CAD 编辑指令，像真实用户给 CAD 工程师的修改请求。",
        "只返回 JSON 对象，格式为 {\"instruction\": \"...\", \"confidence\": \"high|medium|low\"}。",
        "不要输出 Markdown，不要解释推理过程。",
        "不要提到 CadQuery、cq、Workplane、result、代码、source span、block span、CSG、cutter、坐标原点或实现细节。",
        "不要引用 target code 或 intermediate code；这些内容不会提供给你。",
        "必须表达其余结构保持不变或等价含义。",
        "不要虚构 edit_record 和三视图中没有支持的额外结构、数量或编辑动作。",
    ]
    if mode == "parameter":
        return common + [
            "这是参数级编辑。必须表达 old value 到 new value 的变化。",
            "禁止表达添加、删除、替换、移动、旋转、复制等结构级编辑。",
            "如果无法从三视图判断具体几何语义，就保守描述为参数或尺寸修改。",
        ]
    if mode == "structural_add":
        return common + [
            "这是结构添加编辑。必须表达添加、新增、开孔、开槽或添加凹陷等添加语义。",
            "必须描述新增 feature 类型；如果 edit_record 有尺寸，尽量包含尺寸。",
            "禁止表达删除或替换。",
        ]
    if mode == "structural_delete":
        return common + [
            "这是结构删除编辑。必须表达删除、移除、去掉、填充或恢复为直角等删除语义。",
            "必须描述被删除的 feature 类型；如果 edit_record 有尺寸，尽量包含尺寸。",
            "禁止表达添加或替换。",
        ]
    if mode == "structural_replace":
        return common + [
            "这是结构替换编辑。必须表达替换、改成或换成等替换语义。",
            "必须同时描述 old feature 和 new feature；如果 edit_record 有尺寸，尽量包含尺寸。",
            "禁止只表达添加或只表达删除；禁止表达移动、旋转、复制。",
        ]
    return common


def build_prompt_text(record: dict[str, Any]) -> str:
    mode = instruction_mode(record)
    edit_record = record.get("edit_record") if isinstance(record.get("edit_record"), dict) else {}
    prompt_payload = {
        "task": "基于已验证的 CAD 编辑记录生成自然语言编辑指令",
        "instruction_mode": mode,
        "branch": record.get("branch"),
        "edit_type": record.get("edit_type"),
        "rules": prompt_rules(mode),
        "original_cadquery_code_hidden_context": record.get("original_code"),
        "sanitized_edit_record": sanitize_for_prompt(edit_record),
        "validation_summary": validation_summary(record),
        "template_fallback_example": fallback_instruction(record),
        "not_provided": ["编辑后的目标代码", "替换过程中的中间代码"],
    }
    return json.dumps(prompt_payload, ensure_ascii=False, indent=2)


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


def count_existing_images(record: dict[str, Any], image_root: Path) -> int:
    images = record.get("images")
    if not isinstance(images, list):
        return 0
    count = 0
    for item in images:
        if isinstance(item, str) and resolve_image_path(image_root, item).exists():
            count += 1
    return count


def build_messages(
    record: dict[str, Any],
    image_root: Path,
    allow_missing_images: bool,
    image_min_pixels: int | None = None,
    image_max_pixels: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
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
            image_item: dict[str, Any] = {"type": "image_url", "image_url": {"url": image_to_data_url(resolved)}}
            if image_min_pixels is not None:
                image_item["min_pixels"] = image_min_pixels
            if image_max_pixels is not None:
                image_item["max_pixels"] = image_max_pixels
            content.append(image_item)
            image_count += 1
    return [
        {
            "role": "system",
            "content": "你是 CAD 数据集构造助手，只负责把已验证的结构化编辑记录改写成自然、准确、无代码细节的中文 CAD 编辑指令。",
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
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if extra_payload:
        payload.update(extra_payload)
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
        texts = [item.get("text") for item in content if isinstance(item, dict) and isinstance(item.get("text"), str)]
        if texts:
            return "\n".join(texts)
    raise ValueError("response message content is not text")


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
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


def contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token and token in text for token in tokens)


def contains_preserve_clause(text: str) -> bool:
    return any(pattern in text for pattern in PRESERVE_PATTERNS)


def expected_values(record: dict[str, Any]) -> list[Any]:
    mode = instruction_mode(record)
    edit_record = record.get("edit_record")
    if not isinstance(edit_record, dict):
        return []
    values: list[Any] = []
    if mode == "parameter":
        values.extend([edit_record.get("old"), edit_record.get("new")])
    else:
        hints = instruction_hints(edit_record)
        params = parameters(edit_record)
        for key in ("diameter", "radius", "length", "width", "depth", "sides", "count", "distance"):
            value = hints.get(key, params.get(key))
            if value is not None:
                values.append(value)
        if mode == "structural_replace":
            for path in (
                ("old_feature", "parameters", "diameter"),
                ("old_feature", "parameters", "radius"),
                ("old_feature", "parameters", "sides"),
                ("old_feature", "parameters", "count"),
                ("new_feature", "human_dimensions", "length"),
                ("new_feature", "human_dimensions", "width"),
            ):
                value = nested_get(edit_record, *path)
                if value is not None:
                    values.append(value)
    deduped: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = str(value)
        if key not in seen:
            seen.add(key)
            deduped.append(value)
    return deduped


def required_structural_values(record: dict[str, Any]) -> list[Any]:
    edit_record = record.get("edit_record")
    if not isinstance(edit_record, dict):
        return []
    edit_type = str(record.get("edit_type") or edit_record.get("edit_type") or "")
    hints = instruction_hints(edit_record)
    params = parameters(edit_record)

    def first_number(*values: Any) -> Any:
        for value in values:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
        return None

    required: list[Any] = []
    diameter_or_radius = first_number(hints.get("diameter"), params.get("diameter"), hints.get("radius"), params.get("radius"))
    if edit_type in {
        "add_through_hole",
        "add_blind_hole",
        "delete_hole",
        "delete_circular_cutout",
        "delete_polygonal_cutout",
        "replace_circular_cutout_with_polygonal_cutout",
        "replace_polygonal_cutout_with_circular_cutout",
    } and diameter_or_radius is not None:
        required.append(diameter_or_radius)

    if edit_type == "delete_polygonal_cutout":
        sides = first_number(hints.get("sides"), params.get("sides"))
        if sides is not None:
            required.append(sides)

    if edit_type == "add_blind_hole":
        depth = first_number(hints.get("depth"), params.get("depth"))
        if depth is not None:
            required.append(depth)

    if edit_type in {
        "add_rectangular_slot",
        "add_pocket",
        "replace_circular_cutout_with_slot",
        "replace_loop_holes_with_slots",
        "replace_polygonal_cutout_with_slot",
    }:
        length = first_number(hints.get("length"), nested_get(edit_record, "new_feature", "human_dimensions", "length"))
        width = first_number(hints.get("width"), nested_get(edit_record, "new_feature", "human_dimensions", "width"))
        if length is not None:
            required.append(length)
        if width is not None:
            required.append(width)

    if edit_type == "add_pocket":
        depth = first_number(hints.get("depth"))
        if depth is not None:
            required.append(depth)

    if edit_type == "replace_chamfer_with_fillet":
        distance = first_number(hints.get("distance"), nested_get(edit_record, "old_feature", "parameters", "distance"))
        radius = first_number(hints.get("radius"), nested_get(edit_record, "new_feature", "radius"))
        if distance is not None:
            required.append(distance)
        if radius is not None:
            required.append(radius)
    if edit_type == "replace_fillet_with_chamfer":
        radius = first_number(hints.get("radius"), nested_get(edit_record, "old_feature", "parameters", "radius"))
        distance = first_number(hints.get("distance"), nested_get(edit_record, "new_feature", "distance"))
        if radius is not None:
            required.append(radius)
        if distance is not None:
            required.append(distance)

    deduped: list[Any] = []
    seen: set[str] = set()
    for value in required:
        key = normalize_number(value)
        if key not in seen:
            seen.add(key)
            deduped.append(value)
    return deduped


def validate_instruction(instruction: str, record: dict[str, Any], require_key_values: bool = True) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    text = instruction.strip()
    lowered = text.lower()
    mode = instruction_mode(record)
    edit_type = str(record.get("edit_type") or "")

    if not text:
        reasons.append("empty instruction")
    if any(token in lowered for token in FORBIDDEN_CODE_TOKENS):
        reasons.append("instruction contains code or implementation detail")
    if contains_any(text, MOVE_TOKENS):
        reasons.append("instruction mentions unsupported move/rotate/copy edit")
    if not contains_preserve_clause(text):
        reasons.append("instruction does not preserve other geometry")

    if mode == "parameter":
        if contains_any(text, ADD_TOKENS + DELETE_TOKENS + REPLACE_TOKENS):
            reasons.append("parameter instruction mentions structural edit")
        edit_record = record.get("edit_record")
        if require_key_values and isinstance(edit_record, dict):
            for label, value in (("old", edit_record.get("old")), ("new", edit_record.get("new"))):
                variants = number_variants(value)
                if variants and not any(variant in text for variant in variants):
                    reasons.append(f"parameter instruction missing {label} value")
    elif mode == "structural_add":
        if not contains_any(text, ADD_TOKENS):
            reasons.append("structural add instruction does not mention add operation")
        if contains_any(text, DELETE_TOKENS) or contains_any(text, REPLACE_TOKENS):
            reasons.append("structural add instruction mentions delete or replace")
    elif mode == "structural_delete":
        if not contains_any(text, DELETE_TOKENS):
            reasons.append("structural delete instruction does not mention delete operation")
        if contains_any(text, ADD_TOKENS) or contains_any(text, REPLACE_TOKENS):
            reasons.append("structural delete instruction mentions add or replace")
    elif mode == "structural_replace":
        if not contains_any(text, REPLACE_TOKENS):
            reasons.append("structural replace instruction does not mention replace operation")
        if not any(word in text for word in FEATURE_WORDS_BY_EDIT_TYPE.get(edit_type, ())):
            reasons.append("structural replace instruction does not mention expected features")
    if mode in {"structural_add", "structural_delete"}:
        feature_words = FEATURE_WORDS_BY_EDIT_TYPE.get(edit_type, ())
        if feature_words and not any(word in text for word in feature_words):
            reasons.append("instruction does not mention expected feature")

    if require_key_values:
        values_to_check = []
        if mode == "parameter":
            values_to_check = []
        else:
            values_to_check = required_structural_values(record)
        for value in values_to_check:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                variants = number_variants(value)
                if variants and not any(variant in text for variant in variants):
                    reasons.append(f"instruction missing key dimension {normalize_number(value)}")
                    break

    return not reasons, reasons


def response_format_payload(mode: str, strict: bool) -> dict[str, Any]:
    if mode == "none":
        return {}
    if mode == "json_object":
        return {"response_format": {"type": "json_object"}}
    if mode == "json_schema":
        return {
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "cad_edit_instruction",
                    "description": "One English CAD edit instruction generated from a validated edit record.",
                    "strict": strict,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "instruction": {
                                "type": "string",
                                "description": "A single English CAD edit instruction.",
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                        },
                        "required": ["instruction", "confidence"],
                    },
                },
            }
        }
    raise ValueError(f"unsupported response format mode: {mode}")


def request_extra_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload = response_format_payload(args.response_format, args.json_schema_strict)
    if args.vl_high_resolution_images:
        payload["vl_high_resolution_images"] = True
    return payload


# ---------------------------------------------------------------------------
# English Stage 2 implementation. These definitions intentionally override the
# older Chinese-template functions above.


def ensure_preserve_clause(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "Keep the rest of the part unchanged."
    lowered = stripped.lower()
    if any(pattern in lowered for pattern in PRESERVE_PATTERNS):
        return stripped if stripped.endswith((".", "!", "?")) else stripped + "."
    stripped = stripped.rstrip(".!?,; ")
    return f"{stripped}, keeping the rest of the part unchanged."


def parameter_label(edit_record: dict[str, Any]) -> str:
    call = str(edit_record.get("call") or edit_record.get("kind") or "parameter")
    return {
        "circle": "circle radius",
        "hole": "hole diameter",
        "extrude": "extrusion depth",
        "box": "box dimension parameter",
        "chamfer": "chamfer size",
        "fillet": "fillet radius",
    }.get(call, f"{call} parameter")


def fallback_parameter_instruction(edit_record: dict[str, Any]) -> str:
    label = parameter_label(edit_record)
    old = normalize_number(edit_record.get("old", ""))
    new = normalize_number(edit_record.get("new", ""))
    return f"Change the {label} from {old} to {new}, keeping the rest of the part unchanged."


def fallback_add_instruction(edit_record: dict[str, Any]) -> str:
    edit_type = edit_record.get("edit_type")
    hints = instruction_hints(edit_record)
    primitive = edit_record.get("primitive") if isinstance(edit_record.get("primitive"), dict) else {}
    dims = primitive.get("dims") if isinstance(primitive.get("dims"), dict) else {}

    diameter = hints.get("diameter")
    radius = hints.get("radius", primitive.get("radius"))
    if diameter is None and isinstance(radius, (int, float)):
        diameter = radius * 2
    depth = hints.get("depth", primitive.get("depth"))
    length = hints.get("length", dims.get("x"))
    width = hints.get("width", dims.get("y"))

    if edit_type == "add_through_hole":
        if isinstance(diameter, (int, float)):
            return f"Add a through circular hole with a diameter of {mm(diameter)} on the main face, keeping the rest of the part unchanged."
        return "Add a through circular hole on the main face, keeping the rest of the part unchanged."
    if edit_type == "add_blind_hole":
        if isinstance(diameter, (int, float)) and isinstance(depth, (int, float)):
            return f"Add a blind hole with a diameter of {mm(diameter)} and a depth of {mm(depth)} on the main face, keeping the rest of the part unchanged."
        if isinstance(diameter, (int, float)):
            return f"Add a blind hole with a diameter of {mm(diameter)} on the main face, keeping the rest of the part unchanged."
        return "Add a blind hole on the main face, keeping the rest of the part unchanged."
    if edit_type == "add_rectangular_slot":
        if isinstance(length, (int, float)) and isinstance(width, (int, float)):
            return f"Add a rectangular slot {mm(length)} long and {mm(width)} wide on the main face, keeping the rest of the part unchanged."
        return "Add a rectangular slot on the main face, keeping the rest of the part unchanged."
    if edit_type == "add_pocket":
        if all(isinstance(value, (int, float)) for value in (length, width, depth)):
            return f"Add a rectangular recess {mm(length)} long, {mm(width)} wide, and {mm(depth)} deep on the main face, keeping the rest of the part unchanged."
        if isinstance(length, (int, float)) and isinstance(width, (int, float)):
            return f"Add a rectangular recess {mm(length)} long and {mm(width)} wide on the main face, keeping the rest of the part unchanged."
        return "Add a rectangular recess on the main face, keeping the rest of the part unchanged."

    return "Add the specified local feature on the main face, keeping the rest of the part unchanged."


def fallback_delete_instruction(edit_record: dict[str, Any]) -> str:
    edit_type = edit_record.get("edit_type")
    hints = instruction_hints(edit_record)
    params = parameters(edit_record)
    diameter = hints.get("diameter", params.get("diameter"))
    radius = hints.get("radius", params.get("radius"))
    sides = hints.get("sides", params.get("sides"))
    count = hints.get("count", params.get("count"))
    distance = hints.get("distance", params.get("distance"))

    if edit_type == "delete_hole":
        if isinstance(count, int) and count > 1 and isinstance(diameter, (int, float)):
            return f"Remove the group of {count} circular holes with a diameter of {mm(diameter)}, keeping the rest of the part unchanged."
        if isinstance(diameter, (int, float)):
            return f"Remove the circular hole with a diameter of {mm(diameter)}, keeping the rest of the part unchanged."
        return "Remove the circular hole, keeping the rest of the part unchanged."
    if edit_type == "delete_circular_cutout":
        if isinstance(diameter, (int, float)):
            return f"Remove the circular cutout with a diameter of {mm(diameter)}, keeping the rest of the part unchanged."
        if isinstance(radius, (int, float)):
            return f"Remove the circular cutout with a radius of {mm(radius)}, keeping the rest of the part unchanged."
        return "Remove the circular cutout, keeping the rest of the part unchanged."
    if edit_type == "delete_polygonal_cutout":
        if isinstance(sides, int) and isinstance(radius, (int, float)):
            return f"Remove the {sides}-sided through hole with a radius of {mm(radius)}, keeping the rest of the part unchanged."
        return "Remove the polygonal through hole, keeping the rest of the part unchanged."
    if edit_type == "delete_fillet":
        if isinstance(radius, (int, float)):
            return f"Remove the R{normalize_number(radius)} fillet and restore the edge to a sharp corner, keeping the rest of the part unchanged."
        return "Remove the edge fillet and restore the edge to a sharp corner, keeping the rest of the part unchanged."
    if edit_type == "delete_chamfer":
        if isinstance(distance, (int, float)):
            return f"Remove the C{normalize_number(distance)} chamfer and restore the edge to a sharp corner, keeping the rest of the part unchanged."
        return "Remove the edge chamfer and restore the edge to a sharp corner, keeping the rest of the part unchanged."

    return "Remove the specified local feature, keeping the rest of the part unchanged."


def fallback_replace_instruction(edit_record: dict[str, Any]) -> str:
    edit_type = edit_record.get("edit_type")
    hints = instruction_hints(edit_record)
    diameter = hints.get("diameter", old_feature_params(edit_record).get("diameter"))
    radius = hints.get("radius")
    sides = hints.get("sides")
    count = nested_get(edit_record, "old_feature", "parameters", "count")
    length = hints.get("length", nested_get(edit_record, "new_feature", "human_dimensions", "length"))
    width = hints.get("width", nested_get(edit_record, "new_feature", "human_dimensions", "width"))
    distance = hints.get("distance")

    if edit_type in {"replace_circular_cutout_with_slot", "replace_loop_holes_with_slots", "replace_polygonal_cutout_with_slot"}:
        old_feature = "circular through hole"
        if edit_type == "replace_loop_holes_with_slots":
            old_feature = "circular holes"
        if edit_type == "replace_polygonal_cutout_with_slot":
            old_feature = "polygonal through hole"
        prefix = f"Replace the {old_feature}"
        if edit_type == "replace_loop_holes_with_slots" and isinstance(count, int) and count > 1:
            prefix = f"Replace the group of {count} circular holes"
        if isinstance(diameter, (int, float)) and edit_type != "replace_polygonal_cutout_with_slot":
            prefix = f"Replace the {old_feature} with a diameter of {mm(diameter)}"
        if isinstance(length, (int, float)) and isinstance(width, (int, float)):
            return f"{prefix} with a rectangular slot {mm(length)} long and {mm(width)} wide, keeping the rest of the part unchanged."
        return f"{prefix} with a rectangular slot, keeping the rest of the part unchanged."
    if edit_type == "replace_circular_cutout_with_polygonal_cutout":
        if isinstance(radius, (int, float)):
            return f"Replace the circular through hole with a radius of {mm(radius)} with a hexagonal through hole, keeping the rest of the part unchanged."
        return "Replace the circular through hole with a hexagonal through hole, keeping the rest of the part unchanged."
    if edit_type == "replace_polygonal_cutout_with_circular_cutout":
        if isinstance(sides, int):
            return f"Replace the {sides}-sided through hole with a circular through hole, keeping the rest of the part unchanged."
        return "Replace the polygonal through hole with a circular through hole, keeping the rest of the part unchanged."
    if edit_type == "replace_chamfer_with_fillet":
        if isinstance(distance, (int, float)) and isinstance(radius, (int, float)):
            return f"Replace the C{normalize_number(distance)} chamfer with an R{normalize_number(radius)} fillet, keeping the rest of the part unchanged."
        return "Replace the edge chamfer with a fillet, keeping the rest of the part unchanged."
    if edit_type == "replace_fillet_with_chamfer":
        if isinstance(radius, (int, float)) and isinstance(distance, (int, float)):
            return f"Replace the R{normalize_number(radius)} fillet with a C{normalize_number(distance)} chamfer, keeping the rest of the part unchanged."
        return "Replace the edge fillet with a chamfer, keeping the rest of the part unchanged."

    return "Replace the specified local feature with the requested new feature, keeping the rest of the part unchanged."


def fallback_instruction(record: dict[str, Any]) -> str:
    edit_record = record.get("edit_record")
    if not isinstance(edit_record, dict):
        return "Modify the specified CAD feature, keeping the rest of the part unchanged."
    mode = instruction_mode(record)
    if mode == "parameter":
        return fallback_parameter_instruction(edit_record)
    if mode == "structural_add":
        return fallback_add_instruction(edit_record)
    if mode == "structural_delete":
        return fallback_delete_instruction(edit_record)
    if mode == "structural_replace":
        return fallback_replace_instruction(edit_record)
    return "Modify the specified local feature, keeping the rest of the part unchanged."


def prompt_rules(mode: str, include_template_reference: bool = True) -> list[str]:
    common = [
        "Generate one English CAD edit instruction that reads like a real user request to a CAD engineer.",
        "Use the original dimensioned three-view drawings when choosing natural wording. The attached images are ordered as Front view, Top view, and Left view.",
        "Do not invent unsupported features, counts, or locations.",
        "Return only a JSON object with this schema: {\"instruction\": \"...\", \"confidence\": \"high|medium|low\"}.",
        "Do not output Markdown or explain your reasoning.",
        "Do not mention CadQuery, cq, Workplane, result, code, source spans, block spans, CSG, cutters, coordinate origins, coordinate axes, or implementation details.",
        "Do not refer to edited target code or intermediate code.",
        "The instruction must say that the rest of the part remains unchanged, or use an equivalent phrase.",
    ]
    if include_template_reference:
        common.append(
            "Write naturally; the deterministic template reference is only a constraint reference, not the desired final style."
        )
    else:
        common.append("Write naturally and avoid a rigid fixed-template style.")
    if mode == "parameter":
        return common + [
            "This is a parameter edit. The instruction must express the old value changing to the new value.",
            "The old and new numeric values in edit_record are authoritative. Copy those values exactly into the instruction.",
            "Do not convert, double, halve, or reinterpret the values based on the drawing. If the parameter is a radius, keep it as a radius; do not rewrite it as a diameter.",
            "Use the parameter name suggested by the edit record, such as circle radius, hole diameter, extrusion depth, box dimension, chamfer size, or fillet radius.",
            "Do not describe adding, deleting, replacing, moving, rotating, or copying a structure.",
        ]
    if mode == "structural_add":
        return common + [
            "This is a structural add edit. The instruction must express adding, creating, drilling, cutting a slot, or adding a recess.",
            "Describe the new feature type and include key dimensions when available.",
            "Do not describe deleting or replacing a feature.",
        ]
    if mode == "structural_delete":
        return common + [
            "This is a structural delete edit. The instruction must express removing, deleting, filling, or restoring an edge to a sharp corner.",
            "Describe the removed feature type and include key dimensions when available.",
            "Do not describe adding or replacing a feature.",
        ]
    if mode == "structural_replace":
        return common + [
            "This is a structural replacement edit. The instruction must express replacing, converting, or swapping one feature for another.",
            "Mention both the old feature and the new feature, and include key dimensions when available.",
            "Do not describe only an add operation or only a delete operation.",
        ]
    return common


def build_prompt_text(record: dict[str, Any], include_template_reference: bool = True) -> str:
    mode = instruction_mode(record)
    edit_record = record.get("edit_record") if isinstance(record.get("edit_record"), dict) else {}
    prompt_payload = {
        "rules": prompt_rules(mode, include_template_reference=include_template_reference),
        "image_order": ["Front", "Top", "Left"],
        "edit_type": record.get("edit_type"),
        "original_cadquery_code_hidden_context": record.get("original_code"),
        "edit_record": sanitize_for_prompt(edit_record),
    }
    if mode == "parameter":
        prompt_payload["parameter_value_constraints"] = {
            "parameter_name_hint": parameter_label(edit_record),
            "old_value_must_appear_exactly": normalize_number(edit_record.get("old")),
            "new_value_must_appear_exactly": normalize_number(edit_record.get("new")),
            "do_not_convert_between_radius_and_diameter": True,
        }
    if include_template_reference:
        prompt_payload["deterministic_template_reference_not_final_style"] = {
            "purpose": "Fixed-template constraint reference only. Use it to preserve edit facts, but write a more natural English CAD request when possible.",
            "text": fallback_instruction(record),
        }
    return json.dumps(prompt_payload, ensure_ascii=False, indent=2)


def build_messages(
    record: dict[str, Any],
    image_root: Path,
    allow_missing_images: bool,
    image_min_pixels: int | None = None,
    image_max_pixels: int | None = None,
    include_template_reference: bool = True,
) -> tuple[list[dict[str, Any]], int]:
    content: list[dict[str, Any]] = [
        {"type": "text", "text": build_prompt_text(record, include_template_reference=include_template_reference)}
    ]
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
            image_item: dict[str, Any] = {"type": "image_url", "image_url": {"url": image_to_data_url(resolved)}}
            if image_min_pixels is not None:
                image_item["min_pixels"] = image_min_pixels
            if image_max_pixels is not None:
                image_item["max_pixels"] = image_max_pixels
            content.append(image_item)
            image_count += 1
    return [
        {
            "role": "system",
            "content": (
                "You are a CAD dataset construction assistant. Generate one concise English CAD edit instruction "
                "by combining the original dimensioned three-view drawings with the structured edit record. "
                "The attached images are ordered as Front view, Top view, and Left view. "
                "The instruction should read like a real user request to a CAD engineer, and it must not include "
                "code names, implementation details, target code, or intermediate code."
            ),
        },
        {"role": "user", "content": content},
    ], image_count


def contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    for token in tokens:
        if not token:
            continue
        if re.fullmatch(r"[a-z]+", token):
            if re.search(rf"\b{re.escape(token)}\b", lowered):
                return True
        elif token in lowered:
            return True
    return False


def contains_preserve_clause(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in PRESERVE_PATTERNS)


def contains_cjk(text: str) -> bool:
    return re.search(r"[\u4e00-\u9fff]", text) is not None


def validate_instruction(instruction: str, record: dict[str, Any], require_key_values: bool = True) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    text = instruction.strip()
    lowered = text.lower()
    mode = instruction_mode(record)
    edit_type = str(record.get("edit_type") or "")

    if not text:
        reasons.append("empty instruction")
    if contains_cjk(text):
        reasons.append("instruction is not English")
    if any(token in lowered for token in FORBIDDEN_CODE_TOKENS):
        reasons.append("instruction contains code or implementation detail")
    if contains_any(text, MOVE_TOKENS):
        reasons.append("instruction mentions unsupported move/rotate/copy edit")
    if not contains_preserve_clause(text):
        reasons.append("instruction does not preserve other geometry")

    if mode == "parameter":
        if contains_any(text, ADD_TOKENS + DELETE_TOKENS + REPLACE_TOKENS):
            reasons.append("parameter instruction mentions structural edit")
        edit_record = record.get("edit_record")
        if require_key_values and isinstance(edit_record, dict):
            for label, value in (("old", edit_record.get("old")), ("new", edit_record.get("new"))):
                variants = number_variants(value)
                if variants and not any(variant in text for variant in variants):
                    reasons.append(f"parameter instruction missing {label} value")
    elif mode == "structural_add":
        if not contains_any(text, ADD_TOKENS):
            reasons.append("structural add instruction does not mention add operation")
        if contains_any(text, DELETE_TOKENS) or contains_any(text, REPLACE_TOKENS):
            reasons.append("structural add instruction mentions delete or replace")
    elif mode == "structural_delete":
        if not contains_any(text, DELETE_TOKENS):
            reasons.append("structural delete instruction does not mention delete operation")
        if contains_any(text, ADD_TOKENS) or contains_any(text, REPLACE_TOKENS):
            reasons.append("structural delete instruction mentions add or replace")
    elif mode == "structural_replace":
        if not contains_any(text, REPLACE_TOKENS):
            reasons.append("structural replace instruction does not mention replace operation")
        feature_words = FEATURE_WORDS_BY_EDIT_TYPE.get(edit_type, ())
        if feature_words and not any(word in lowered for word in feature_words):
            reasons.append("structural replace instruction does not mention expected features")
    if mode in {"structural_add", "structural_delete"}:
        feature_words = FEATURE_WORDS_BY_EDIT_TYPE.get(edit_type, ())
        if feature_words and not any(word in lowered for word in feature_words):
            reasons.append("instruction does not mention expected feature")

    if require_key_values:
        values_to_check = [] if mode == "parameter" else required_structural_values(record)
        for value in values_to_check:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                variants = number_variants(value)
                if variants and not any(variant in text for variant in variants):
                    reasons.append(f"instruction missing key dimension {normalize_number(value)}")
                    break

    return not reasons, reasons


def cache_key(record: dict[str, Any], model: str, request_config: dict[str, Any] | None = None) -> str:
    include_template_reference = True
    if request_config is not None:
        include_template_reference = bool(request_config.get("include_template_reference", True))
    payload = {
        "sample_id": record.get("sample_id"),
        "model": model,
        "prompt": build_prompt_text(record, include_template_reference=include_template_reference),
        "images": record.get("images"),
        "request_config": request_config or {},
    }
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    sample_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(record.get("sample_id") or "sample"))
    return f"{sample_id}_{digest[:16]}"


def cache_path(cache_dir: Path, model: str, record: dict[str, Any], request_config: dict[str, Any] | None = None) -> Path:
    safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "_", model)
    return cache_dir / safe_model / f"{cache_key(record, model, request_config)}.json"


def read_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def write_cache(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def create_progress_bar(total: int, desc: str, enabled: bool) -> Any | None:
    if not enabled:
        return None
    try:
        from tqdm.auto import tqdm
    except Exception:  # noqa: BLE001 - plain text fallback is handled in process_file
        return None
    return tqdm(total=total, desc=desc, unit="rec", dynamic_ncols=True)


def summarize_fallback_reasons(reasons: list[str]) -> str:
    if not reasons:
        return "Fallback was used because the MLLM instruction did not pass validation."

    summaries: list[str] = []
    for reason in reasons:
        if reason == "dry_run":
            summaries.append("dry-run mode used the deterministic template without calling the MLLM")
        elif "missing key dimension" in reason:
            summaries.append("the MLLM instruction omitted a required dimension from the edit record")
        elif "does not preserve other geometry" in reason:
            summaries.append("the MLLM instruction did not clearly say that unchanged geometry should be preserved")
        elif "does not mention expected feature" in reason or "expected features" in reason:
            summaries.append("the MLLM instruction did not mention the expected edited feature")
        elif "contains code or implementation detail" in reason:
            summaries.append("the MLLM instruction exposed code or implementation details")
        elif "not English" in reason:
            summaries.append("the MLLM instruction was not valid English")
        elif "wrong semantics" in reason or "mentions add or replace" in reason or "mentions delete or replace" in reason:
            summaries.append("the MLLM instruction used the wrong edit operation")
        else:
            summaries.append(reason)

    deduped = list(dict.fromkeys(summaries))
    return "Fallback was used because " + "; ".join(deduped) + "."


def build_instruction_record(
    record: dict[str, Any],
    instruction: str,
    *,
    generator: str,
    model: str,
    fallback_used: bool,
    validation_ok: bool,
    quality_reasons: list[str],
    image_count: int,
    raw_response_cached: bool,
    api_error: str | None = None,
    usage: dict[str, Any] | None = None,
    rejected_mllm_instruction: str | None = None,
    rejected_mllm_confidence: str | None = None,
) -> dict[str, Any]:
    selection_meta = record.get("selection_meta") if isinstance(record.get("selection_meta"), dict) else {}
    split = selection_meta.get("split")
    meta: dict[str, Any] = {
        "generator": generator,
        "model": model,
        "instruction_mode": instruction_mode(record),
        "fallback_used": fallback_used,
        "validation_ok": validation_ok,
        "quality_reasons": quality_reasons,
        "fallback_reason_summary": summarize_fallback_reasons(quality_reasons) if fallback_used else "",
        "included_target_code": False,
        "included_intermediate_code": False,
        "used_original_code": True,
        "used_edit_record": True,
        "used_images_count": image_count,
        "raw_response_cached": raw_response_cached,
    }
    if api_error:
        meta["api_error"] = api_error
    if usage:
        meta["usage"] = usage
    if rejected_mllm_instruction is not None:
        meta["rejected_mllm_instruction"] = rejected_mllm_instruction
        meta["rejected_mllm_response_cached"] = raw_response_cached
        if rejected_mllm_confidence is not None:
            meta["rejected_mllm_confidence"] = rejected_mllm_confidence
    return {
        "sample_id": record.get("sample_id"),
        "source_sample_id": record.get("source_sample_id"),
        "split": split,
        "branch": record.get("branch"),
        "edit_type": record.get("edit_type"),
        "instruction": instruction,
        "instruction_meta": meta,
    }


def generate_one_instruction(
    record: dict[str, Any],
    args: argparse.Namespace,
    api_key: str | None,
) -> dict[str, Any]:
    fallback = fallback_instruction(record)
    fallback_ok, fallback_reasons = validate_instruction(fallback, record, args.require_key_values)
    if not fallback_ok:
        # Fallbacks are deterministic and should pass; keep the record usable with a minimal safe clause.
        fallback = ensure_preserve_clause(fallback)
        fallback_ok, fallback_reasons = validate_instruction(fallback, record, False)

    image_count = count_existing_images(record, args.image_root)
    if args.dry_run:
        return build_instruction_record(
            record,
            fallback,
            generator="template_fallback",
            model=args.model,
            fallback_used=True,
            validation_ok=fallback_ok,
            quality_reasons=["dry_run"] + fallback_reasons,
            image_count=image_count,
            raw_response_cached=False,
        )

    cache_config = {
        "response_format": args.response_format,
        "json_schema_strict": args.json_schema_strict,
        "vl_high_resolution_images": args.vl_high_resolution_images,
        "image_min_pixels": args.image_min_pixels,
        "image_max_pixels": args.image_max_pixels,
        "include_template_reference": not args.omit_template_reference,
    }
    cache_file = cache_path(args.cache_dir, args.model, record, cache_config)
    cached = read_cache(cache_file)
    raw_response = None
    raw_response_cached = False
    api_error = None

    if cached is not None and isinstance(cached.get("raw_response"), dict):
        raw_response = cached["raw_response"]
        raw_response_cached = True
        image_count = int(cached.get("image_count") or image_count)
    else:
        try:
            if api_key is None:
                raise RuntimeError("missing API key")
            messages, image_count = build_messages(
                record,
                args.image_root,
                args.allow_missing_images,
                args.image_min_pixels,
                args.image_max_pixels,
                include_template_reference=not args.omit_template_reference,
            )
            last_error: Exception | None = None
            for attempt in range(args.retries + 1):
                try:
                    raw_response = call_bailian_chat(
                        args.base_url,
                        api_key,
                        args.model,
                        messages,
                        args.temperature,
                        args.max_tokens,
                        args.timeout_seconds,
                        request_extra_payload(args),
                    )
                    write_cache(cache_file, {"raw_response": raw_response, "image_count": image_count})
                    break
                except Exception as exc:  # noqa: BLE001 - keep batch jobs alive
                    last_error = exc
                    if attempt < args.retries:
                        time.sleep(args.retry_sleep_seconds)
            if raw_response is None:
                raise RuntimeError(str(last_error) if last_error else "unknown API error")
        except Exception as exc:  # noqa: BLE001
            api_error = str(exc)

    if raw_response is not None:
        try:
            parsed = extract_json_object(response_text(raw_response))
            instruction = parsed.get("instruction")
            if not isinstance(instruction, str):
                raise ValueError("model JSON missing instruction")
            confidence = parsed.get("confidence")
            rejected_confidence = confidence if isinstance(confidence, str) else None
            ok, reasons = validate_instruction(instruction, record, args.require_key_values)
            usage = raw_response.get("usage") if isinstance(raw_response.get("usage"), dict) else None
            if ok:
                return build_instruction_record(
                    record,
                    instruction.strip(),
                    generator=args.model,
                    model=args.model,
                    fallback_used=False,
                    validation_ok=True,
                    quality_reasons=[],
                    image_count=image_count,
                    raw_response_cached=raw_response_cached,
                    usage=usage,
                )
            return build_instruction_record(
                record,
                fallback,
                generator="template_fallback",
                model=args.model,
                fallback_used=True,
                validation_ok=fallback_ok,
                quality_reasons=reasons,
                image_count=image_count,
                raw_response_cached=raw_response_cached,
                usage=usage,
                rejected_mllm_instruction=instruction.strip(),
                rejected_mllm_confidence=rejected_confidence,
            )
        except Exception as exc:  # noqa: BLE001
            api_error = str(exc)

    return build_instruction_record(
        record,
        fallback,
        generator="template_fallback",
        model=args.model,
        fallback_used=True,
        validation_ok=fallback_ok,
        quality_reasons=([api_error] if api_error else []) + fallback_reasons,
        image_count=image_count,
        raw_response_cached=raw_response_cached,
        api_error=api_error,
    )


def summarize_instruction_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    branch_counts: Counter[str] = Counter()
    edit_type_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    generator_counts: Counter[str] = Counter()
    fallback_by_branch: dict[str, Counter[str]] = defaultdict(Counter)
    fallback_by_edit_type: dict[str, Counter[str]] = defaultdict(Counter)
    reason_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    target_code_leaks = 0
    original_code_leaks = 0
    validation_ok = 0

    for record in records:
        branch = str(record.get("branch") or "unknown")
        edit_type = str(record.get("edit_type") or "unknown")
        split = str(record.get("split") or "unknown")
        meta = record.get("instruction_meta") if isinstance(record.get("instruction_meta"), dict) else {}
        mode = str(meta.get("instruction_mode") or "unknown")
        generator = str(meta.get("generator") or "unknown")
        fallback = bool(meta.get("fallback_used"))
        instruction = str(record.get("instruction") or "")

        branch_counts[branch] += 1
        edit_type_counts[edit_type] += 1
        split_counts[split] += 1
        mode_counts[mode] += 1
        generator_counts[generator] += 1
        fallback_by_branch[branch]["fallback" if fallback else "mllm"] += 1
        fallback_by_edit_type[edit_type]["fallback" if fallback else "mllm"] += 1
        if meta.get("validation_ok") is True:
            validation_ok += 1
        for reason in meta.get("quality_reasons") or []:
            reason_counts[str(reason)] += 1
        lowered = instruction.lower()
        if "target_code" in lowered or "target code" in lowered:
            target_code_leaks += 1
        if "original_code" in lowered or "original code" in lowered or "原始代码" in instruction:
            original_code_leaks += 1

    total = len(records)
    fallback_count = sum(1 for r in records if isinstance(r.get("instruction_meta"), dict) and r["instruction_meta"].get("fallback_used"))
    mllm_count = total - fallback_count
    return {
        "records": total,
        "mllm_success": mllm_count,
        "fallback_used": fallback_count,
        "fallback_rate": fallback_count / total if total else 0.0,
        "validation_pass_rate": validation_ok / total if total else 0.0,
        "branch_counts": dict(sorted(branch_counts.items())),
        "edit_type_counts": dict(sorted(edit_type_counts.items())),
        "instruction_mode_counts": dict(sorted(mode_counts.items())),
        "generator_counts": dict(sorted(generator_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "fallback_by_branch": {
            key: {
                "fallback": counter.get("fallback", 0),
                "mllm": counter.get("mllm", 0),
                "fallback_rate": counter.get("fallback", 0) / sum(counter.values()) if sum(counter.values()) else 0.0,
            }
            for key, counter in sorted(fallback_by_branch.items())
        },
        "fallback_by_edit_type": {
            key: {
                "fallback": counter.get("fallback", 0),
                "mllm": counter.get("mllm", 0),
                "fallback_rate": counter.get("fallback", 0) / sum(counter.values()) if sum(counter.values()) else 0.0,
            }
            for key, counter in sorted(fallback_by_edit_type.items())
        },
        "validation_failure_reasons": dict(reason_counts.most_common()),
        "target_code_instruction_leaks": target_code_leaks,
        "original_code_instruction_leaks": original_code_leaks,
        "stage2_ready": target_code_leaks == 0 and original_code_leaks == 0 and validation_ok == total,
    }


def markdown_table(counter: dict[str, Any], headers: tuple[str, str] = ("Name", "Count")) -> str:
    lines = [f"| {headers[0]} | {headers[1]} |", "|---|---:|"]
    for key, value in counter.items():
        lines.append(f"| `{key}` | {value} |")
    return "\n".join(lines)


def write_report(
    path: Path,
    *,
    title: str,
    input_paths: list[str],
    output_paths: list[str],
    summary: dict[str, Any],
    samples: list[dict[str, Any]],
) -> None:
    lines = [
        f"# {title}",
        "",
        "## Inputs",
        "",
    ]
    lines.extend(f"- `{item}`" for item in input_paths)
    lines.extend(["", "## Outputs", ""])
    lines.extend(f"- `{item}`" for item in output_paths)
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- records: `{summary['records']}`",
            f"- MLLM success: `{summary['mllm_success']}`",
            f"- fallback used: `{summary['fallback_used']}`",
            f"- fallback rate: `{summary['fallback_rate']:.4f}`",
            f"- validation pass rate: `{summary['validation_pass_rate']:.4f}`",
            f"- target_code leaks: `{summary['target_code_instruction_leaks']}`",
            f"- original_code leaks: `{summary['original_code_instruction_leaks']}`",
            f"- Stage 2 ready: `{summary['stage2_ready']}`",
            "",
            "## Instruction Modes",
            "",
            markdown_table(summary["instruction_mode_counts"]),
            "",
            "## Branch Distribution",
            "",
            markdown_table(summary["branch_counts"]),
            "",
            "## Edit Type Distribution",
            "",
            markdown_table(summary["edit_type_counts"]),
            "",
            "## Top Failure Reasons",
            "",
        ]
    )
    reasons = dict(list(summary["validation_failure_reasons"].items())[:20])
    lines.append(markdown_table(reasons) if reasons else "No validation failures.")
    lines.extend(["", "## Fallback Rate By Branch", "", "| Branch | Fallback | MLLM | Rate |", "|---|---:|---:|---:|"])
    for branch, item in summary["fallback_by_branch"].items():
        lines.append(f"| `{branch}` | {item['fallback']} | {item['mllm']} | {item['fallback_rate']:.4f} |")
    lines.extend(["", "## Fallback Rate By Edit Type", "", "| Edit Type | Fallback | MLLM | Rate |", "|---|---:|---:|---:|"])
    for edit_type, item in summary["fallback_by_edit_type"].items():
        lines.append(f"| `{edit_type}` | {item['fallback']} | {item['mllm']} | {item['fallback_rate']:.4f} |")
    lines.extend(["", "## Sample Instructions", ""])
    for record in samples[:20]:
        lines.append(f"- `{record.get('sample_id')}` `{record.get('edit_type')}`: {record.get('instruction')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def process_file(
    input_path: Path,
    output_path: Path,
    args: argparse.Namespace,
    api_key: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = read_jsonl(input_path)
    if args.limit is not None:
        records = records[: args.limit]
    existing = set() if args.overwrite else load_existing_sample_ids(output_path)
    if args.overwrite:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("", encoding="utf-8")
    pending_records: list[dict[str, Any]] = []
    skipped_existing = 0
    for record in records:
        sample_id = record.get("sample_id")
        if isinstance(sample_id, str) and sample_id in existing:
            skipped_existing += 1
        else:
            pending_records.append(record)

    output_records: list[dict[str, Any]] = []
    desc = f"Stage2 {input_path.stem}"
    workers = max(1, int(args.workers))
    progress = create_progress_bar(len(pending_records), desc, args.progress)
    plain_progress = args.progress and progress is None
    report_every = max(1, len(pending_records) // 100) if pending_records else 1

    def handle_completed(instruction_record: dict[str, Any], completed: int) -> None:
        output_records.append(instruction_record)
        append_jsonl(output_path, [instruction_record], overwrite=False)
        if progress is not None:
            progress.update(1)
        elif plain_progress and (completed == 1 or completed == len(pending_records) or completed % report_every == 0):
            print(
                f"{desc}: done {completed}/{len(pending_records)} new={len(output_records)} skipped={skipped_existing}",
                file=sys.stderr,
                flush=True,
            )

    try:
        if workers == 1:
            for completed, record in enumerate(pending_records, start=1):
                sample_id = record.get("sample_id")
                sample_label = str(sample_id or f"record_{completed}")
                if progress is not None:
                    progress.set_postfix_str(sample_label[:48], refresh=False)
                elif plain_progress and (completed == 1 or completed == len(pending_records) or completed % report_every == 0):
                    print(
                        f"{desc}: starting {completed}/{len(pending_records)} sample_id={sample_label}",
                        file=sys.stderr,
                        flush=True,
                    )

                instruction_record = generate_one_instruction(record, args, api_key)
                handle_completed(instruction_record, completed)
                if args.sleep_seconds > 0 and completed < len(pending_records):
                    time.sleep(args.sleep_seconds)
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = []
                for record in pending_records:
                    futures.append(executor.submit(generate_one_instruction, record, args, api_key))
                    if args.sleep_seconds > 0:
                        time.sleep(args.sleep_seconds)
                for completed, future in enumerate(as_completed(futures), start=1):
                    instruction_record = future.result()
                    if progress is not None:
                        sample_label = str(instruction_record.get("sample_id") or f"record_{completed}")
                        progress.set_postfix_str(sample_label[:48], refresh=False)
                    handle_completed(instruction_record, completed)
    finally:
        if progress is not None:
            progress.close()

    all_records = read_jsonl(output_path)
    summary = summarize_instruction_records(all_records)
    summary.update(
        {
            "input_path": str(input_path),
            "output_path": str(output_path),
            "input_records": len(records),
            "new_output_records": len(output_records),
            "skipped_existing": skipped_existing,
            "workers": workers,
        }
    )
    return all_records, summary


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Single Stage 1.5 intermediate JSONL input.")
    parser.add_argument("--output", type=Path, help="Single instruction JSONL output.")
    parser.add_argument("--input-dir", type=Path, help="Directory containing train/val/test intermediate files.")
    parser.add_argument("--output-dir", type=Path, help="Directory for train/val/test instruction outputs and reports.")
    parser.add_argument("--splits", default=",".join(SPLITS), help="Comma-separated split names for directory mode.")
    parser.add_argument("--image-root", default=Path("."), type=Path)
    parser.add_argument("--cache-dir", default=Path("outputs/stage2/cache"), type=Path)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key-env", default=",".join(DEFAULT_API_KEY_ENVS))
    parser.add_argument("--temperature", default=0.2, type=float)
    parser.add_argument("--max-tokens", default=256, type=int)
    parser.add_argument(
        "--response-format",
        choices=("json_schema", "json_object", "none"),
        default="json_schema",
        help="Structured output mode for the Qwen MLLM API.",
    )
    parser.add_argument("--no-json-schema-strict", dest="json_schema_strict", action="store_false")
    parser.set_defaults(json_schema_strict=True)
    parser.add_argument(
        "--vl-high-resolution-images",
        action="store_true",
        help="Pass the DashScope/Qwen-VL high-resolution image flag when supported.",
    )
    parser.add_argument("--image-min-pixels", default=None, type=int)
    parser.add_argument("--image-max-pixels", default=None, type=int)
    parser.add_argument("--timeout-seconds", default=120, type=int)
    parser.add_argument("--retries", default=2, type=int)
    parser.add_argument("--retry-sleep-seconds", default=2.0, type=float)
    parser.add_argument("--sleep-seconds", default=0.0, type=float)
    parser.add_argument("--workers", default=1, type=int, help="Number of concurrent MLLM request workers.")
    parser.add_argument("--limit", default=None, type=int)
    parser.add_argument("--seed", default=42, type=int, help="Recorded for reproducibility; Stage 2 does not resample records.")
    parser.add_argument("--dry-run", action="store_true", help="Generate deterministic template fallback instructions only.")
    parser.add_argument("--allow-missing-images", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Rewrite output instead of resuming existing records.")
    parser.add_argument("--no-require-key-values", dest="require_key_values", action="store_false")
    parser.set_defaults(require_key_values=True)
    parser.add_argument(
        "--omit-template-reference",
        action="store_true",
        help="Do not include the deterministic template reference text in the MLLM prompt.",
    )
    parser.add_argument("--no-progress", dest="progress", action="store_false", help="Disable the per-file progress bar.")
    parser.set_defaults(progress=True)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--report-output", type=Path)
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    if args.workers < 1:
        raise ValueError("--workers must be >= 1")
    single = args.input is not None or args.output is not None
    directory = args.input_dir is not None or args.output_dir is not None
    if single and directory:
        raise ValueError("use either --input/--output or --input-dir/--output-dir, not both")
    if single:
        if args.input is None or args.output is None:
            raise ValueError("single-file mode requires both --input and --output")
    elif directory:
        if args.input_dir is None or args.output_dir is None:
            raise ValueError("directory mode requires both --input-dir and --output-dir")
    else:
        raise ValueError("provide --input/--output or --input-dir/--output-dir")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    validate_args(args)

    api_key = None
    api_key_env = None
    if not args.dry_run:
        env_names = [item.strip() for item in args.api_key_env.split(",") if item.strip()]
        api_key, api_key_env = first_api_key(env_names)

    if args.input is not None and args.output is not None:
        records, summary = process_file(args.input, args.output, args, api_key)
        summary["api_key_env"] = api_key_env
        if args.summary_output:
            args.summary_output.parent.mkdir(parents=True, exist_ok=True)
            args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.report_output:
            write_report(
                args.report_output,
                title="Stage 2 Instruction Report",
                input_paths=[str(args.input)],
                output_paths=[str(args.output)],
                summary=summary,
                samples=records,
            )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    assert args.input_dir is not None and args.output_dir is not None
    splits = [item.strip() for item in args.splits.split(",") if item.strip()]
    all_records: list[dict[str, Any]] = []
    split_summaries: dict[str, Any] = {}
    input_paths: list[str] = []
    output_paths: list[str] = []
    for split in splits:
        input_path = args.input_dir / f"{split}_intermediate.jsonl"
        output_path = args.output_dir / f"{split}_instructions.jsonl"
        records, split_summary = process_file(input_path, output_path, args, api_key)
        split_summaries[split] = split_summary
        all_records.extend(records)
        input_paths.append(str(input_path))
        output_paths.append(str(output_path))

    summary = summarize_instruction_records(all_records)
    summary.update(
        {
            "input_dir": str(args.input_dir),
            "output_dir": str(args.output_dir),
            "split_summaries": split_summaries,
            "api_key_env": api_key_env,
            "dry_run": args.dry_run,
            "model": args.model,
            "seed": args.seed,
            "workers": args.workers,
            "response_format": args.response_format,
            "json_schema_strict": args.json_schema_strict,
            "vl_high_resolution_images": args.vl_high_resolution_images,
        }
    )
    summary_path = args.summary_output or (args.output_dir / "instruction_summary.json")
    report_path = args.report_output or (args.output_dir / "instruction_report.md")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(
        report_path,
        title=f"Stage 2 Instruction Report - {args.output_dir.name}",
        input_paths=input_paths,
        output_paths=output_paths + [str(summary_path), str(report_path)],
        summary=summary,
        samples=all_records,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
