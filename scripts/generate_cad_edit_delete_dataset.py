#!/usr/bin/env python3
"""Generate V2 high-confidence structural delete CAD edit records."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_cad_edit_dataset import extract_images, extract_original_code, read_jsonl  # noqa: E402
from generate_cad_edit_structural_dataset import (  # noqa: E402
    AXES,
    bbox_dims,
    bbox_within,
    execute_shape,
    expand_bbox,
    geometry_info,
    round_float,
)


REQUIRED_DELETE_CHECKS = (
    "original_executes",
    "edited_executes",
    "edited_non_empty",
    "volume_direction_ok",
    "bbox_stable",
    "bbox_not_collapsed",
    "changed_region_non_empty",
    "changed_region_not_global",
    "volume_delta_matches_changed_region",
)

CUTOUT_DELETE_TYPES = {
    "delete_hole",
    "delete_circular_cutout",
    "delete_polygonal_cutout",
}
FINISHING_DELETE_TYPES = {
    "delete_fillet",
    "delete_chamfer",
}

DELETE_TYPE_METADATA = {
    "delete_hole": {
        "human_feature_name": "圆孔",
        "volume_effect": "increase",
        "operation": "remove_subtractive_feature",
    },
    "delete_circular_cutout": {
        "human_feature_name": "圆形切口",
        "volume_effect": "increase",
        "operation": "remove_subtractive_feature",
    },
    "delete_polygonal_cutout": {
        "human_feature_name": "多边形通孔",
        "volume_effect": "increase",
        "operation": "remove_subtractive_feature",
    },
    "delete_fillet": {
        "human_feature_name": "圆角",
        "volume_effect": "change",
        "operation": "remove_finishing_feature",
    },
    "delete_chamfer": {
        "human_feature_name": "倒角",
        "volume_effect": "change",
        "operation": "remove_finishing_feature",
    },
}


def line_offsets(source: str) -> list[int]:
    offsets = [0]
    for index, char in enumerate(source):
        if char == "\n":
            offsets.append(index + 1)
    return offsets


def absolute_position(offsets: list[int], line_number: int, column: int) -> int:
    return offsets[line_number - 1] + column


def is_hole_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "hole"
    )


def is_cut_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "cut"
    )


def is_finishing_call(node: ast.AST, attr: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attr
    )


def assigned_to_result(node: ast.Assign | ast.AnnAssign) -> bool:
    targets: list[ast.AST]
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    else:
        targets = [node.target]
    return any(isinstance(target, ast.Name) and target.id == "result" for target in targets)


def numeric_literal_value(node: ast.AST) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
    ):
        return -float(node.operand.value)
    return None


def hole_parameters(node: ast.Call) -> dict[str, Any] | None:
    diameter: float | None = None
    depth: float | None = None
    if node.args:
        diameter = numeric_literal_value(node.args[0])
    for keyword in node.keywords:
        if keyword.arg == "diameter":
            diameter = numeric_literal_value(keyword.value)
        elif keyword.arg == "depth":
            depth = numeric_literal_value(keyword.value)
    if diameter is None or diameter <= 0:
        return None
    parameters: dict[str, Any] = {"diameter": round_float(diameter)}
    if depth is not None and depth > 0:
        parameters["depth"] = round_float(depth)
    return parameters


def outer_result_hole_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and assigned_to_result(node) and is_hole_call(node.value):
            calls.append(node.value)
        elif isinstance(node, ast.AnnAssign) and assigned_to_result(node) and is_hole_call(node.value):
            calls.append(node.value)
    return sorted(calls, key=lambda item: (item.lineno, item.col_offset))


def outer_result_cut_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and assigned_to_result(node) and is_cut_call(node.value):
            calls.append(node.value)
        elif isinstance(node, ast.AnnAssign) and assigned_to_result(node) and is_cut_call(node.value):
            calls.append(node.value)
    return sorted(calls, key=lambda item: (item.lineno, item.col_offset))


def first_numeric_circle_call(node: ast.AST) -> tuple[ast.Call, float] | None:
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "circle"
            and child.args
        ):
            radius = numeric_literal_value(child.args[0])
            if radius is not None and radius > 0:
                return child, radius
    return None


def first_numeric_polygon_call(node: ast.AST) -> tuple[ast.Call, int, float] | None:
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "polygon"
            and len(child.args) >= 2
        ):
            sides_value = numeric_literal_value(child.args[0])
            radius = numeric_literal_value(child.args[1])
            if (
                sides_value is not None
                and radius is not None
                and sides_value == int(sides_value)
                and int(sides_value) >= 3
                and radius > 0
            ):
                return child, int(sides_value), radius
    return None


def first_numeric_extrude_call(node: ast.AST) -> tuple[ast.Call, float] | None:
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "extrude"
            and child.args
        ):
            depth = numeric_literal_value(child.args[0])
            if depth is not None and abs(depth) > 0:
                return child, abs(depth)
    return None


def has_extrude_call(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "extrude"
        for child in ast.walk(node)
    )


def outer_result_finishing_calls(tree: ast.AST, attr: str) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and assigned_to_result(node) and is_finishing_call(node.value, attr):
            calls.append(node.value)
        elif isinstance(node, ast.AnnAssign) and assigned_to_result(node) and is_finishing_call(node.value, attr):
            calls.append(node.value)
    return sorted(calls, key=lambda item: (item.lineno, item.col_offset))


def simple_range_count(node: ast.AST) -> int | None:
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "range"
        and 1 <= len(node.args) <= 3
        and not node.keywords
    ):
        return None
    values = [numeric_literal_value(arg) for arg in node.args]
    if any(value is None for value in values):
        return None
    int_values = [int(value) for value in values if value is not None]
    if any(value != int(value) for value in values if value is not None):
        return None
    if len(int_values) == 1:
        start, stop, step = 0, int_values[0], 1
    elif len(int_values) == 2:
        start, stop = int_values
        step = 1
    else:
        start, stop, step = int_values
    if step == 0:
        return None
    count = len(range(start, stop, step))
    return count if count > 0 else None


def result_workplane_suffix_span(source: str, node: ast.Assign | ast.AnnAssign, offsets: list[int]) -> int | None:
    value = node.value
    if not isinstance(value, ast.Call) or value.end_lineno is None or value.end_col_offset is None:
        return None
    value_start = absolute_position(offsets, value.lineno, value.col_offset)
    value_end = absolute_position(offsets, value.end_lineno, value.end_col_offset)
    value_text = source[value_start:value_end]
    workplane_index = value_text.rfind(".workplane(")
    faces_index = value_text.rfind(".faces(", 0, workplane_index if workplane_index >= 0 else len(value_text))
    if faces_index < 0 or workplane_index < faces_index:
        return None
    return value_start + faces_index


def simple_loop_hole_blocks(tree: ast.AST, source: str, offsets: list[int]) -> list[tuple[ast.For, ast.Call, int, int, int, str]]:
    blocks: list[tuple[ast.For, ast.Call, int, int, int, str]] = []
    module_body = tree.body if isinstance(tree, ast.Module) else []
    for index, node in enumerate(module_body):
        if not isinstance(node, ast.For) or len(node.body) != 1 or node.orelse:
            continue
        if index == 0:
            continue
        previous = module_body[index - 1]
        if not isinstance(previous, (ast.Assign, ast.AnnAssign)) or not assigned_to_result(previous):
            continue
        previous_suffix_start = result_workplane_suffix_span(source, previous, offsets)
        if previous_suffix_start is None:
            continue
        count = simple_range_count(node.iter)
        if count is None:
            continue
        statement = node.body[0]
        if not isinstance(statement, ast.Assign) or not assigned_to_result(statement) or not is_hole_call(statement.value):
            continue
        if node.end_lineno is None or node.end_col_offset is None:
            continue
        block_end = absolute_position(offsets, node.end_lineno, node.end_col_offset)
        block_text = source[previous_suffix_start:block_end]
        if any(item in block_text for item in (".pushPoints(", ".rarray(", ".polarArray(")):
            continue
        blocks.append((node, statement.value, count, previous_suffix_start, block_end, block_text))
    return sorted(blocks, key=lambda item: (item[0].lineno, item[0].col_offset))


def locate_delete_block(source: str, node: ast.Call, offsets: list[int]) -> tuple[int, int, str] | None:
    if node.end_lineno is None or node.end_col_offset is None:
        return None
    call_start = absolute_position(offsets, node.lineno, node.col_offset)
    call_end = absolute_position(offsets, node.end_lineno, node.end_col_offset)
    call_text = source[call_start:call_end]
    hole_index = call_text.rfind(".hole")
    if hole_index < 0:
        return None
    prefix = call_text[:hole_index]
    faces_index = prefix.rfind(".faces(")
    workplane_index = prefix.rfind(".workplane(")
    if faces_index < 0 or workplane_index < faces_index:
        return None
    block_start = call_start + faces_index
    block_end = call_end
    block_text = source[block_start:block_end]
    if ".pushPoints(" in block_text or ".rarray(" in block_text or ".polarArray(" in block_text:
        return None
    return block_start, block_end, block_text


def circular_cutout_parameters(node: ast.Call) -> dict[str, Any] | None:
    if not node.args:
        return None
    cutter = node.args[0]
    if not has_extrude_call(cutter):
        return None
    circle = first_numeric_circle_call(cutter)
    if circle is None:
        return None
    _, radius = circle
    return {
        "radius": round_float(radius),
        "diameter": round_float(radius * 2),
    }


def polygonal_cutout_parameters(node: ast.Call) -> dict[str, Any] | None:
    if not node.args:
        return None
    cutter = node.args[0]
    extrude = first_numeric_extrude_call(cutter)
    if extrude is None:
        return None
    polygon = first_numeric_polygon_call(cutter)
    if polygon is None:
        return None
    _, sides, radius = polygon
    _, depth = extrude
    return {
        "sides": sides,
        "radius": round_float(radius),
        "depth": round_float(depth),
    }


def locate_circular_cutout_delete_block(source: str, node: ast.Call, offsets: list[int]) -> tuple[int, int, str] | None:
    if node.end_lineno is None or node.end_col_offset is None:
        return None
    call_start = absolute_position(offsets, node.lineno, node.col_offset)
    call_end = absolute_position(offsets, node.end_lineno, node.end_col_offset)
    call_text = source[call_start:call_end]
    cut_index = call_text.rfind(".cut(")
    if cut_index < 0:
        return None
    block_start = call_start + cut_index
    block_end = call_end
    block_text = source[block_start:block_end]
    if ".circle(" not in block_text or ".extrude(" not in block_text:
        return None
    return block_start, block_end, block_text


def locate_polygonal_cutout_delete_block(source: str, node: ast.Call, offsets: list[int]) -> tuple[int, int, str] | None:
    if node.end_lineno is None or node.end_col_offset is None:
        return None
    call_start = absolute_position(offsets, node.lineno, node.col_offset)
    call_end = absolute_position(offsets, node.end_lineno, node.end_col_offset)
    call_text = source[call_start:call_end]
    cut_index = call_text.rfind(".cut(")
    if cut_index < 0:
        return None
    block_start = call_start + cut_index
    block_end = call_end
    block_text = source[block_start:block_end]
    if ".polygon(" not in block_text or ".extrude(" not in block_text:
        return None
    return block_start, block_end, block_text


def finishing_parameters(node: ast.Call, attr: str) -> dict[str, Any] | None:
    if not is_finishing_call(node, attr) or len(node.args) != 1 or node.keywords:
        return None
    value = numeric_literal_value(node.args[0])
    if value is None or value <= 0:
        return None
    key = "radius" if attr == "fillet" else "distance"
    return {key: round_float(value)}


def locate_finishing_delete_block(
    source: str,
    node: ast.Call,
    offsets: list[int],
    attr: str,
) -> tuple[int, int, str] | None:
    if node.end_lineno is None or node.end_col_offset is None:
        return None
    call_start = absolute_position(offsets, node.lineno, node.col_offset)
    call_end = absolute_position(offsets, node.end_lineno, node.end_col_offset)
    call_text = source[call_start:call_end]
    feature_index = call_text.rfind(f".{attr}(")
    if feature_index < 0:
        return None
    prefix = call_text[:feature_index]
    edges_index = prefix.rfind(".edges(")
    if edges_index < 0:
        return None
    block_start = call_start + edges_index
    block_end = call_end
    block_text = source[block_start:block_end]
    if ".edges(" not in block_text or f".{attr}(" not in block_text:
        return None
    return block_start, block_end, block_text


def apply_delete_candidate(candidate: dict[str, Any]) -> str:
    delete_candidate = candidate["delete_candidate"]
    original_code = candidate["original_code"]
    start = delete_candidate["block_span_start"]
    end = delete_candidate["block_span_end"]
    block_text = delete_candidate["block_text"]
    if original_code[start:end] != block_text:
        raise ValueError("delete block span does not match source text")
    target_code = original_code[:start] + original_code[end:]
    ast.parse(target_code)
    return target_code


def build_delete_candidate(
    candidate_id: str,
    sample_index: int,
    source_line: int,
    images: list[str],
    original_code: str,
    original_geometry: dict[str, Any],
    block_start: int,
    block_end: int,
    block_text: str,
    parameters: dict[str, Any],
    deletion_strategy: str = "chain_suffix",
    edit_type: str = "delete_hole",
    source_api: str = "hole",
) -> dict[str, Any]:
    metadata = DELETE_TYPE_METADATA.get(edit_type, DELETE_TYPE_METADATA["delete_hole"])
    human_feature_name = metadata["human_feature_name"]
    if edit_type in {"delete_hole", "delete_circular_cutout"} and isinstance(parameters.get("diameter"), (int, float)):
        instruction_template = f"删除零件上直径为 {parameters['diameter']} 的{human_feature_name}，其余结构保持不变。"
    elif edit_type == "delete_polygonal_cutout":
        sides = parameters.get("sides")
        radius = parameters.get("radius")
        if isinstance(sides, int) and isinstance(radius, (int, float)):
            instruction_template = f"删除零件上半径为 {radius} 的 {sides} 边形通孔，其余结构保持不变。"
        else:
            instruction_template = "删除零件上的多边形通孔，其余结构保持不变。"
    elif edit_type == "delete_fillet":
        instruction_template = "删除零件边缘的圆角，使边缘恢复为直角，其余结构保持不变。"
    elif edit_type == "delete_chamfer":
        instruction_template = "删除零件边缘的倒角，使边缘恢复为直角，其余结构保持不变。"
    else:
        instruction_template = f"删除零件上的{human_feature_name}，其余结构保持不变。"
    instruction_hints = {
        "operation": "delete",
        "human_feature_name": human_feature_name,
        "delete_verbs": ["删除", "移除", "去掉"],
        "preserve_other_geometry": True,
        "preferred_position_style": "visual_surface_region",
        "avoid_implementation_details": ["block_span", "source_api", "workplane", "origin"],
    }
    for key in ("diameter", "radius", "depth", "sides", "distance", "count"):
        if key in parameters:
            instruction_hints[key] = parameters[key]
    if edit_type in FINISHING_DELETE_TYPES:
        instruction_hints["restore_edge_style"] = "right_angle"
    return {
        "candidate_id": candidate_id,
        "sample_index": sample_index,
        "source_line": source_line,
        "images": images,
        "original_code": original_code,
        "original_geometry": original_geometry,
        "delete_candidate": {
            "candidate_type": "structural_delete",
            "edit_type": edit_type,
            "source_api": source_api,
            "block_span_start": block_start,
            "block_span_end": block_end,
            "block_text": block_text,
            "replacement": "",
            "parameters": parameters,
            "deletion_strategy": deletion_strategy,
            "expected_effect": {
                "volume": metadata["volume_effect"],
                "bbox": "stable",
                "operation": metadata["operation"],
            },
            "instruction_template": instruction_template,
            "instruction_hints": instruction_hints,
        },
    }


def generate_delete_candidates_for_record(
    source_record: dict[str, Any],
    sample_index: int,
    source_line: int,
    max_deletes_per_sample: int,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    stats: Counter[str] = Counter()
    images = extract_images(source_record)
    original_code = extract_original_code(source_record)
    if not original_code:
        stats["skipped_no_code"] += 1
        return [], stats

    try:
        tree = ast.parse(original_code)
    except SyntaxError as exc:
        stats["skipped_syntax_error"] += 1
        stats[f"syntax_error:{str(exc)[:80]}"] += 1
        return [], stats

    try:
        original_shape = execute_shape(original_code)
        geometry = geometry_info(original_shape)
    except Exception as exc:
        stats["skipped_geometry_error"] += 1
        stats[f"geometry_error:{str(exc)[:80]}"] += 1
        return [], stats

    offsets = line_offsets(original_code)
    original_geometry = {
        "volume": geometry.volume,
        "bbox": geometry.bbox,
        "dims": geometry.dims,
    }
    candidates: list[dict[str, Any]] = []
    candidate_index = 1
    for node in outer_result_hole_calls(tree):
        if len(candidates) >= max_deletes_per_sample:
            break
        parameters = hole_parameters(node)
        if parameters is None:
            stats["skipped_non_numeric_hole"] += 1
            continue
        block = locate_delete_block(original_code, node, offsets)
        if block is None:
            stats["skipped_unsupported_hole_context"] += 1
            continue
        block_start, block_end, block_text = block
        candidate_id = f"v2del_{sample_index:06d}_{candidate_index:03d}"
        candidate = build_delete_candidate(
            candidate_id=candidate_id,
            sample_index=sample_index,
            source_line=source_line,
            images=images,
            original_code=original_code,
            original_geometry=original_geometry,
            block_start=block_start,
            block_end=block_end,
            block_text=block_text,
            parameters=parameters,
        )
        try:
            apply_delete_candidate(candidate)
        except Exception as exc:
            stats["skipped_target_syntax_error"] += 1
            stats[f"target_syntax_error:{str(exc)[:80]}"] += 1
            continue
        candidates.append(candidate)
        stats["candidate_records"] += 1
        candidate_index += 1

    for loop_node, hole_node, count, block_start, block_end, block_text in simple_loop_hole_blocks(tree, original_code, offsets):
        if len(candidates) >= max_deletes_per_sample:
            break
        parameters = hole_parameters(hole_node)
        if parameters is None:
            stats["skipped_non_numeric_loop_hole"] += 1
            continue
        parameters["count"] = count
        candidate_id = f"v2del_{sample_index:06d}_{candidate_index:03d}"
        candidate = build_delete_candidate(
            candidate_id=candidate_id,
            sample_index=sample_index,
            source_line=source_line,
            images=images,
            original_code=original_code,
            original_geometry=original_geometry,
            block_start=block_start,
            block_end=block_end,
            block_text=block_text,
            parameters=parameters,
            deletion_strategy="simple_for_hole_block",
        )
        try:
            apply_delete_candidate(candidate)
        except Exception as exc:
            stats["skipped_target_syntax_error"] += 1
            stats[f"target_syntax_error:{str(exc)[:80]}"] += 1
            continue
        candidates.append(candidate)
        stats["candidate_records"] += 1
        candidate_index += 1

    for node in outer_result_cut_calls(tree):
        if len(candidates) >= max_deletes_per_sample:
            break
        parameters = circular_cutout_parameters(node)
        edit_type = "delete_circular_cutout"
        source_api = "cut"
        deletion_strategy = "circular_cutout_suffix"
        block = locate_circular_cutout_delete_block(original_code, node, offsets) if parameters is not None else None
        if parameters is None or block is None:
            parameters = polygonal_cutout_parameters(node)
            edit_type = "delete_polygonal_cutout"
            source_api = "cut_polygon"
            deletion_strategy = "polygonal_cutout_suffix"
            block = locate_polygonal_cutout_delete_block(original_code, node, offsets) if parameters is not None else None
        if parameters is None or block is None:
            stats["skipped_unsupported_cut_context"] += 1
            continue
        block_start, block_end, block_text = block
        candidate_id = f"v2del_{sample_index:06d}_{candidate_index:03d}"
        candidate = build_delete_candidate(
            candidate_id=candidate_id,
            sample_index=sample_index,
            source_line=source_line,
            images=images,
            original_code=original_code,
            original_geometry=original_geometry,
            block_start=block_start,
            block_end=block_end,
            block_text=block_text,
            parameters=parameters,
            deletion_strategy=deletion_strategy,
            edit_type=edit_type,
            source_api=source_api,
        )
        try:
            apply_delete_candidate(candidate)
        except Exception as exc:
            stats["skipped_target_syntax_error"] += 1
            stats[f"target_syntax_error:{str(exc)[:80]}"] += 1
            continue
        candidates.append(candidate)
        stats["candidate_records"] += 1
        candidate_index += 1

    for attr, edit_type, source_api, deletion_strategy in (
        ("fillet", "delete_fillet", "fillet", "finishing_fillet_suffix"),
        ("chamfer", "delete_chamfer", "chamfer", "finishing_chamfer_suffix"),
    ):
        for node in outer_result_finishing_calls(tree, attr):
            if len(candidates) >= max_deletes_per_sample:
                break
            parameters = finishing_parameters(node, attr)
            if parameters is None:
                stats[f"skipped_non_numeric_{attr}"] += 1
                continue
            block = locate_finishing_delete_block(original_code, node, offsets, attr)
            if block is None:
                stats[f"skipped_unsupported_{attr}_context"] += 1
                continue
            block_start, block_end, block_text = block
            candidate_id = f"v2del_{sample_index:06d}_{candidate_index:03d}"
            candidate = build_delete_candidate(
                candidate_id=candidate_id,
                sample_index=sample_index,
                source_line=source_line,
                images=images,
                original_code=original_code,
                original_geometry=original_geometry,
                block_start=block_start,
                block_end=block_end,
                block_text=block_text,
                parameters=parameters,
                deletion_strategy=deletion_strategy,
                edit_type=edit_type,
                source_api=source_api,
            )
            try:
                apply_delete_candidate(candidate)
            except Exception as exc:
                stats["skipped_target_syntax_error"] += 1
                stats[f"target_syntax_error:{str(exc)[:80]}"] += 1
                continue
            candidates.append(candidate)
            stats["candidate_records"] += 1
            candidate_index += 1

    if not candidates:
        stats["skipped_no_delete_candidate"] += 1
    return candidates, stats


def bbox_same(a: dict[str, float], b: dict[str, float], tolerance: float = 1e-3) -> bool:
    return bbox_within(a, expand_bbox(b, tolerance)) and bbox_within(b, expand_bbox(a, tolerance))


def bbox_not_global(changed_dims: dict[str, float], reference_dims: dict[str, float]) -> bool:
    smaller_axes = 0
    for axis in AXES:
        if changed_dims[axis] <= max(reference_dims[axis] * 0.8, 1e-6):
            smaller_axes += 1
    return smaller_axes >= 2


def validate_cutout_delete_edit(original_code: str, target_code: str, candidate: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": False,
        "mode": "cadquery_structural_delete",
        "checks": {},
        "errors": [],
    }
    try:
        original_shape = execute_shape(original_code)
        edited_shape = execute_shape(target_code)
        original_geometry = geometry_info(original_shape)
        edited_geometry = geometry_info(edited_shape)
        volume_delta = round_float(edited_geometry.volume - original_geometry.volume)
        report.update(
            {
                "original_volume": original_geometry.volume,
                "edited_volume": edited_geometry.volume,
                "volume_delta": volume_delta,
                "original_bbox": original_geometry.bbox,
                "edited_bbox": edited_geometry.bbox,
            }
        )

        checks = report["checks"]
        checks["original_executes"] = original_geometry.volume > 1e-6
        checks["edited_executes"] = edited_geometry.volume > 1e-6
        checks["edited_non_empty"] = edited_geometry.volume > 1e-6
        checks["volume_direction_ok"] = volume_delta > 1e-6
        checks["bbox_stable"] = bbox_same(edited_geometry.bbox, original_geometry.bbox)
        checks["bbox_not_collapsed"] = all(
            edited_geometry.dims[axis] > max(original_geometry.dims[axis] * 0.5, 1e-6) for axis in AXES
        )

        try:
            changed_shape = edited_shape.cut(original_shape)
            changed_geometry = geometry_info(changed_shape)
            report["changed_region_bbox"] = changed_geometry.bbox
            report["changed_region_volume"] = changed_geometry.volume
            changed_dims = bbox_dims(changed_geometry.bbox)
            checks["changed_region_non_empty"] = changed_geometry.volume > 1e-6
            checks["changed_region_not_global"] = bbox_not_global(changed_dims, original_geometry.dims)
            checks["volume_delta_matches_changed_region"] = abs(volume_delta - changed_geometry.volume) <= max(
                volume_delta * 0.25, 1e-3
            )
        except Exception as exc:
            checks["changed_region_non_empty"] = False
            checks["changed_region_not_global"] = False
            checks["volume_delta_matches_changed_region"] = False
            report["errors"].append(f"changed-region check failed: {exc}")

        failed = [name for name, value in checks.items() if not value]
        if failed:
            report["errors"].extend(f"failed check: {name}" for name in failed)
        report["ok"] = not failed
    except Exception as exc:
        report["errors"].append(str(exc))
    return report


def difference_volume(shape_a: Any, shape_b: Any) -> tuple[float, dict[str, float] | None]:
    try:
        diff_shape = shape_a.cut(shape_b)
        diff_geometry = geometry_info(diff_shape)
    except Exception:
        return 0.0, None
    if diff_geometry.volume <= 1e-6:
        return 0.0, None
    return diff_geometry.volume, diff_geometry.bbox


def validate_finishing_delete_edit(original_code: str, target_code: str, candidate: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": False,
        "mode": "cadquery_structural_delete",
        "validation_policy": "finishing_feature_delete",
        "checks": {},
        "errors": [],
    }
    try:
        original_shape = execute_shape(original_code)
        edited_shape = execute_shape(target_code)
        original_geometry = geometry_info(original_shape)
        edited_geometry = geometry_info(edited_shape)
        volume_delta = round_float(edited_geometry.volume - original_geometry.volume)
        report.update(
            {
                "original_volume": original_geometry.volume,
                "edited_volume": edited_geometry.volume,
                "volume_delta": volume_delta,
                "original_bbox": original_geometry.bbox,
                "edited_bbox": edited_geometry.bbox,
            }
        )

        checks = report["checks"]
        checks["original_executes"] = original_geometry.volume > 1e-6
        checks["edited_executes"] = edited_geometry.volume > 1e-6
        checks["edited_non_empty"] = edited_geometry.volume > 1e-6
        checks["bbox_stable"] = bbox_same(edited_geometry.bbox, original_geometry.bbox)
        checks["bbox_not_collapsed"] = all(
            edited_geometry.dims[axis] > max(original_geometry.dims[axis] * 0.5, 1e-6) for axis in AXES
        )
        checks["volume_changed_nontrivially"] = abs(volume_delta) > max(original_geometry.volume * 1e-7, 1e-4)

        added_volume, added_bbox = difference_volume(edited_shape, original_shape)
        removed_volume, removed_bbox = difference_volume(original_shape, edited_shape)
        geometry_change_volume = round_float(added_volume + removed_volume)
        report["geometry_change_volume"] = geometry_change_volume
        if added_bbox is not None:
            report["added_region_bbox"] = added_bbox
            report["added_region_volume"] = round_float(added_volume)
        if removed_bbox is not None:
            report["removed_region_bbox"] = removed_bbox
            report["removed_region_volume"] = round_float(removed_volume)
        checks["geometry_changed_nontrivially"] = geometry_change_volume > max(original_geometry.volume * 1e-7, 1e-4)

        failed = [name for name, value in checks.items() if not value]
        if failed:
            report["errors"].extend(f"failed check: {name}" for name in failed)
        report["ok"] = not failed
    except Exception as exc:
        report["errors"].append(str(exc))
    return report


def validate_delete_edit(original_code: str, target_code: str, candidate: dict[str, Any]) -> dict[str, Any]:
    delete_candidate = candidate.get("delete_candidate") if isinstance(candidate, dict) else None
    edit_type = delete_candidate.get("edit_type") if isinstance(delete_candidate, dict) else None
    if edit_type in FINISHING_DELETE_TYPES:
        return validate_finishing_delete_edit(original_code, target_code, candidate)
    return validate_cutout_delete_edit(original_code, target_code, candidate)


def fallback_instruction(candidate: dict[str, Any]) -> str:
    delete_candidate = candidate["delete_candidate"]
    parameters = delete_candidate.get("parameters", {})
    edit_type = delete_candidate.get("edit_type")
    diameter = parameters.get("diameter")
    count = parameters.get("count")
    if edit_type == "delete_polygonal_cutout":
        sides = parameters.get("sides")
        radius = parameters.get("radius")
        if isinstance(sides, int) and isinstance(radius, (int, float)):
            return f"删除零件上半径为 {radius} 的 {sides} 边形通孔，其余结构保持不变。"
        return "删除零件上的多边形通孔，其余结构保持不变。"
    if edit_type == "delete_fillet":
        return "删除零件边缘的圆角，使边缘恢复为直角，其余结构保持不变。"
    if edit_type == "delete_chamfer":
        return "删除零件边缘的倒角，使边缘恢复为直角，其余结构保持不变。"
    feature_name = "圆形切口" if edit_type == "delete_circular_cutout" else "圆孔"
    if isinstance(diameter, (int, float)):
        if isinstance(count, int) and count > 1:
            return f"删除零件上这一组共 {count} 个直径为 {diameter} 的{feature_name}，其余结构保持不变。"
        return f"删除零件上直径为 {diameter} 的{feature_name}，其余结构保持不变。"
    return f"删除零件上的{feature_name}，其余结构保持不变。"


def final_record(validated: dict[str, Any], instruction_record: dict[str, Any] | None = None) -> dict[str, Any]:
    instruction = validated["fallback_instruction"]
    instruction_meta = {
        "generator": "structural_delete_template",
        "fallback_used": True,
        "included_target_code": False,
        "instruction_mode": "structural_delete",
    }
    if instruction_record is not None:
        instruction = instruction_record["instruction"]
        meta = instruction_record.get("instruction_meta")
        if isinstance(meta, dict):
            instruction_meta = meta
    return {
        "images": validated["images"],
        "instruction": instruction,
        "target_code": validated["target_code"],
        "hidden": {
            "candidate_id": validated["candidate_id"],
            "original_code": validated["original_code"],
            "edit_record": validated["edit_record"],
            "validation_report": validated["validation_report"],
            "instruction_meta": instruction_meta,
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("data_t.jsonl"), type=Path)
    parser.add_argument("--output", default=Path("outputs/cad_edit_v2_delete.jsonl"), type=Path)
    parser.add_argument("--candidates-output", default=Path("outputs/cad_edit_v2_delete_candidates.jsonl"), type=Path)
    parser.add_argument(
        "--validated-output", default=Path("outputs/cad_edit_v2_validated_delete_edits.jsonl"), type=Path
    )
    parser.add_argument(
        "--instructions-output", default=Path("outputs/cad_edit_v2_delete_instructions.jsonl"), type=Path
    )
    parser.add_argument("--max-deletes-per-sample", default=2, type=int)
    parser.add_argument("--keep-failed", action="store_true")
    parser.add_argument("--no-final-output", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.max_deletes_per_sample <= 0:
        raise ValueError("--max-deletes-per-sample must be positive")

    for path in (args.candidates_output, args.validated_output, args.instructions_output, args.output):
        path.parent.mkdir(parents=True, exist_ok=True)

    summary: Counter[str] = Counter()
    with args.candidates_output.open("w", encoding="utf-8", newline="\n") as candidates_handle, args.validated_output.open(
        "w", encoding="utf-8", newline="\n"
    ) as validated_handle, args.instructions_output.open("w", encoding="utf-8", newline="\n") as instructions_handle:
        final_handle = None if args.no_final_output else args.output.open("w", encoding="utf-8", newline="\n")
        try:
            for sample_index, (source_line, source_record) in enumerate(read_jsonl(args.input), start=1):
                summary["input_records"] += 1
                candidates, stats = generate_delete_candidates_for_record(
                    source_record=source_record,
                    sample_index=sample_index,
                    source_line=source_line,
                    max_deletes_per_sample=args.max_deletes_per_sample,
                )
                summary.update(stats)
                for candidate in candidates:
                    candidates_handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
                    summary["candidate_output_records"] += 1
                    target_code = apply_delete_candidate(candidate)
                    validation_report = validate_delete_edit(candidate["original_code"], target_code, candidate)
                    if not validation_report.get("ok") and not args.keep_failed:
                        summary["failed_validation"] += 1
                        for error in validation_report.get("errors", [])[:1]:
                            summary[f"validation_error:{error[:80]}"] += 1
                        continue
                    delete_candidate = candidate["delete_candidate"]
                    validated = {
                        "candidate_id": candidate["candidate_id"],
                        "sample_index": candidate["sample_index"],
                        "source_line": candidate["source_line"],
                        "images": candidate["images"],
                        "original_code": candidate["original_code"],
                        "delete_candidate": delete_candidate,
                        "edit_candidate": delete_candidate,
                        "target_code": target_code,
                        "edit_record": delete_candidate,
                        "validation_report": validation_report,
                        "fallback_instruction": fallback_instruction(candidate),
                    }
                    validated_handle.write(json.dumps(validated, ensure_ascii=False) + "\n")
                    summary["validated_output_records"] += 1
                    instruction_record = {
                        "candidate_id": candidate["candidate_id"],
                        "instruction": validated["fallback_instruction"],
                        "instruction_meta": {
                            "generator": "structural_delete_template",
                            "fallback_used": True,
                            "used_original_code": True,
                            "used_candidate": True,
                            "included_target_code": False,
                            "instruction_mode": "structural_delete",
                        },
                    }
                    instructions_handle.write(json.dumps(instruction_record, ensure_ascii=False) + "\n")
                    summary["instruction_output_records"] += 1
                    if final_handle is not None:
                        final_handle.write(json.dumps(final_record(validated, instruction_record), ensure_ascii=False) + "\n")
                        summary["output_records"] += 1
        finally:
            if final_handle is not None:
                final_handle.close()

    printable = dict(sorted(summary.items()))
    printable["output_path"] = str(args.output)
    printable["candidates_output_path"] = str(args.candidates_output)
    printable["validated_output_path"] = str(args.validated_output)
    printable["instructions_output_path"] = str(args.instructions_output)
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
