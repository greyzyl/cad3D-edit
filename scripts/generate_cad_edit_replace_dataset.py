#!/usr/bin/env python3
"""Generate V4 high-confidence structural replace CAD edit records."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_cad_edit_dataset import extract_images, extract_original_code, read_jsonl  # noqa: E402
from generate_cad_edit_delete_dataset import (  # noqa: E402
    apply_delete_candidate,
    bbox_not_global,
    bbox_same,
    generate_delete_candidates_for_record,
    validate_delete_edit,
)
from generate_cad_edit_structural_dataset import (  # noqa: E402
    AXES,
    bbox_center,
    bbox_dims,
    bbox_from_center_dims,
    bbox_within,
    execute_shape,
    expand_bbox,
    format_tuple,
    geometry_info,
    round_float,
)

PLANE_NORMAL_AXIS = {"YZ": "x", "XZ": "y", "XY": "z"}
FACES_AXIS = {"X": "x", "Y": "y", "Z": "z"}
NUMBER_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"

SLOT_REPLACE_TYPES = {
    "replace_hole_with_slot",
    "replace_loop_holes_with_slots",
    "replace_circular_cutout_with_slot",
    "replace_polygonal_cutout_with_slot",
}
DIRECT_CUTOUT_REPLACE_TYPES = {
    "replace_circular_cutout_with_polygonal_cutout",
    "replace_polygonal_cutout_with_circular_cutout",
}
FINISHING_REPLACE_TYPES = {
    "replace_chamfer_with_fillet",
    "replace_fillet_with_chamfer",
}


def infer_normal_axis_from_delete_candidate(delete_candidate: dict[str, Any], changed_dims: dict[str, float]) -> str:
    block_text = str(delete_candidate.get("block_text", ""))
    for face_axis, axis in FACES_AXIS.items():
        if f'.faces(">{face_axis}")' in block_text or f".faces('>{face_axis}')" in block_text:
            return axis
        if f'.faces("<{face_axis}")' in block_text or f".faces('<{face_axis}')" in block_text:
            return axis
    for plane, axis in PLANE_NORMAL_AXIS.items():
        if f'Workplane("{plane}")' in block_text or f"Workplane('{plane}')" in block_text:
            return axis
    return max(AXES, key=lambda axis: changed_dims[axis])


def delete_feature_name(old_feature: dict[str, Any]) -> str:
    edit_type = old_feature.get("edit_type")
    if edit_type == "delete_circular_cutout":
        return "圆形通孔"
    if edit_type == "delete_polygonal_cutout":
        return "多边形通孔"
    if edit_type == "delete_chamfer":
        return "倒角"
    if edit_type == "delete_fillet":
        return "圆角"
    return "圆孔"


def replace_block_text(original_code: str, old_feature: dict[str, Any], new_block_text: str) -> str:
    start = old_feature["block_span_start"]
    end = old_feature["block_span_end"]
    block_text = old_feature["block_text"]
    if original_code[start:end] != block_text:
        raise ValueError("replace block span does not match source text")
    target_code = original_code[:start] + new_block_text + original_code[end:]
    compile(target_code, "<cadquery_source>", "exec")
    return target_code


def replace_first(pattern: str, replacement: str, text: str) -> tuple[str, bool]:
    new_text, count = re.subn(pattern, replacement, text, count=1)
    return new_text, count == 1


def replacement_slot_from_delete_report(candidate: dict[str, Any], delete_report: dict[str, Any]) -> dict[str, Any] | None:
    old_feature = candidate["delete_candidate"]
    parameters = old_feature.get("parameters", {})
    diameter = parameters.get("diameter")
    if not isinstance(diameter, (int, float)):
        radius = parameters.get("radius")
        if isinstance(radius, (int, float)):
            diameter = radius * 2
    if not isinstance(diameter, (int, float)) or diameter <= 0:
        return None

    changed_bbox = delete_report.get("changed_region_bbox")
    if not isinstance(changed_bbox, dict):
        return None
    changed_dims = bbox_dims(changed_bbox)
    center = bbox_center(changed_bbox)
    normal_axis = infer_normal_axis_from_delete_candidate(old_feature, changed_dims)
    tangent_axes = [axis for axis in AXES if axis != normal_axis]
    major_tangent = max(tangent_axes, key=lambda axis: changed_dims[axis])
    minor_tangent = [axis for axis in tangent_axes if axis != major_tangent][0]

    if old_feature.get("edit_type") == "delete_circular_cutout":
        width = round_float(max(float(diameter) * 0.5, 1.0))
        desired_length = max(float(diameter) * 1.2, changed_dims[major_tangent] * 1.02)
        reference_dims = candidate.get("original_geometry", {}).get("dims")
        if isinstance(reference_dims, dict) and isinstance(reference_dims.get(major_tangent), (int, float)):
            desired_length = min(desired_length, float(reference_dims[major_tangent]) * 0.72)
        if desired_length <= width * 1.3:
            return None
        length = round_float(desired_length)
    elif old_feature.get("edit_type") == "delete_polygonal_cutout":
        width = round_float(max(float(diameter) * 0.7, changed_dims[minor_tangent] * 0.7, 1.0))
        desired_length = max(float(diameter) * 1.5, changed_dims[major_tangent] * 1.15)
        reference_dims = candidate.get("original_geometry", {}).get("dims")
        if isinstance(reference_dims, dict) and isinstance(reference_dims.get(major_tangent), (int, float)):
            desired_length = min(desired_length, float(reference_dims[major_tangent]) * 0.72)
        if desired_length <= width * 1.2:
            return None
        length = round_float(desired_length)
    elif isinstance(parameters.get("count"), int) and parameters["count"] > 1:
        length = round_float(max(float(diameter) * 2.2, changed_dims[major_tangent] * 1.05))
        width = round_float(max(float(diameter) * 0.9, changed_dims[minor_tangent] * 0.35, 1.0))
    else:
        length = round_float(max(float(diameter) * 2.2, changed_dims[major_tangent] * 1.8))
        width = round_float(max(float(diameter) * 0.75, 1.0))
    margin = round_float(max(float(diameter) * 0.15, 1.0))
    depth = round_float(changed_dims[normal_axis] + 2 * margin)

    dims = {axis: width for axis in AXES}
    dims[major_tangent] = length
    dims[normal_axis] = depth
    dims = {axis: round_float(value) for axis, value in dims.items()}
    affected_bbox = bbox_from_center_dims(center, dims)
    return {
        "kind": "box",
        "feature": "rectangular_slot",
        "replaces": old_feature.get("edit_type", "delete_hole"),
        "source_delete_strategy": old_feature.get("deletion_strategy"),
        "normal_axis": normal_axis,
        "tangent_axes": [major_tangent, minor_tangent],
        "center": {axis: round_float(center[axis]) for axis in AXES},
        "dims": dims,
        "human_dimensions": {
            "length": length,
            "width": width,
        },
        "affected_region_bbox": affected_bbox,
    }


def slot_csg_block(candidate_id: str, edit_type: str, slot: dict[str, Any]) -> str:
    dims = slot["dims"]
    center = slot["center"]
    return "\n".join(
        [
            "",
            f"# V4 structural replacement: {edit_type} ({candidate_id})",
            "v4_slot_cutter = "
            f"cq.Workplane('XY').box({dims['x']}, {dims['y']}, {dims['z']})"
            f".translate({format_tuple(center)})",
            "result = result.cut(v4_slot_cutter)",
        ]
    )


def apply_replace_candidate(candidate: dict[str, Any]) -> str:
    replace_candidate = candidate["replace_candidate"]
    strategy = replace_candidate.get("insertion_strategy", {})
    if isinstance(strategy, dict) and strategy.get("method") == "direct_source_replacement":
        return candidate["target_code"]
    return (
        candidate["intermediate_code"].rstrip()
        + "\n"
        + slot_csg_block(candidate["candidate_id"], replace_candidate["edit_type"], replace_candidate["new_feature"])
        + "\n"
    )


def replace_edit_type_for_delete(old_feature: dict[str, Any]) -> str:
    if old_feature.get("edit_type") == "delete_circular_cutout":
        return "replace_circular_cutout_with_slot"
    if old_feature.get("edit_type") == "delete_polygonal_cutout":
        return "replace_polygonal_cutout_with_slot"
    parameters = old_feature.get("parameters")
    if isinstance(parameters, dict) and isinstance(parameters.get("count"), int) and parameters["count"] > 1:
        return "replace_loop_holes_with_slots"
    return "replace_hole_with_slot"


def build_direct_replace_candidate(
    candidate_id: str,
    source_record: dict[str, Any],
    delete_candidate: dict[str, Any],
    delete_report: dict[str, Any],
    intermediate_code: str,
    edit_type: str,
    new_block_text: str,
    new_feature: dict[str, Any],
    instruction_template: str,
    instruction_hints: dict[str, Any],
) -> dict[str, Any]:
    old_feature = delete_candidate["delete_candidate"]
    target_code = replace_block_text(delete_candidate["original_code"], old_feature, new_block_text)
    replace_candidate = {
        "candidate_type": "structural_replace",
        "edit_type": edit_type,
        "old_feature": old_feature,
        "new_feature": new_feature,
        "insertion_strategy": {
            "operation": "replace",
            "append_csg_block": False,
            "method": "direct_source_replacement",
        },
        "instruction_template": instruction_template,
        "instruction_hints": instruction_hints,
    }
    return {
        "candidate_id": candidate_id,
        "sample_index": delete_candidate["sample_index"],
        "source_line": delete_candidate["source_line"],
        "images": source_record["images"],
        "original_code": delete_candidate["original_code"],
        "intermediate_code": intermediate_code,
        "delete_validation_report": delete_report,
        "replace_candidate": replace_candidate,
        "target_code": target_code,
    }


def build_circular_cutout_to_polygonal_candidate(
    candidate_id: str,
    source_record: dict[str, Any],
    delete_candidate: dict[str, Any],
    delete_report: dict[str, Any],
    intermediate_code: str,
) -> dict[str, Any] | None:
    old_feature = delete_candidate["delete_candidate"]
    if old_feature.get("edit_type") != "delete_circular_cutout":
        return None
    parameters = old_feature.get("parameters", {})
    radius = parameters.get("radius")
    if not isinstance(radius, (int, float)) or radius <= 0:
        return None
    block_text = old_feature.get("block_text")
    if not isinstance(block_text, str):
        return None
    new_block_text, ok = replace_first(rf"\.circle\s*\(\s*({NUMBER_RE})\s*\)", r".polygon(6, \1)", block_text)
    if not ok:
        return None
    radius = round_float(radius)
    return build_direct_replace_candidate(
        candidate_id=candidate_id,
        source_record=source_record,
        delete_candidate=delete_candidate,
        delete_report=delete_report,
        intermediate_code=intermediate_code,
        edit_type="replace_circular_cutout_with_polygonal_cutout",
        new_block_text=new_block_text,
        new_feature={
            "feature": "polygonal_cutout",
            "feature_type": "polygonal_cutout",
            "sides": 6,
            "radius": radius,
        },
        instruction_template=f"将零件上半径为 {radius} 的圆形通孔替换为六边形通孔，其余结构保持不变。",
        instruction_hints={
            "operation": "replace",
            "old_feature_name": "圆形通孔",
            "new_feature_name": "六边形通孔",
            "radius": radius,
            "sides": 6,
            "replace_verbs": ["替换", "改成", "换成"],
            "preserve_other_geometry": True,
            "avoid_implementation_details": ["source_span", "block_span", "workplane", "csg", "cutter"],
        },
    )


def build_polygonal_cutout_to_circular_candidate(
    candidate_id: str,
    source_record: dict[str, Any],
    delete_candidate: dict[str, Any],
    delete_report: dict[str, Any],
    intermediate_code: str,
) -> dict[str, Any] | None:
    old_feature = delete_candidate["delete_candidate"]
    if old_feature.get("edit_type") != "delete_polygonal_cutout":
        return None
    parameters = old_feature.get("parameters", {})
    sides = parameters.get("sides")
    radius = parameters.get("radius")
    if not isinstance(sides, int) or not isinstance(radius, (int, float)) or radius <= 0:
        return None
    block_text = old_feature.get("block_text")
    if not isinstance(block_text, str):
        return None
    new_radius = round_float(float(radius) * math.cos(math.pi / sides))
    if new_radius <= 0:
        return None
    new_block_text, ok = replace_first(rf"\.polygon\s*\(\s*\d+\s*,\s*({NUMBER_RE})\s*\)", f".circle({new_radius})", block_text)
    if not ok:
        return None
    old_radius = round_float(radius)
    return build_direct_replace_candidate(
        candidate_id=candidate_id,
        source_record=source_record,
        delete_candidate=delete_candidate,
        delete_report=delete_report,
        intermediate_code=intermediate_code,
        edit_type="replace_polygonal_cutout_with_circular_cutout",
        new_block_text=new_block_text,
        new_feature={
            "feature": "circular_cutout",
            "feature_type": "circular_cutout",
            "radius": new_radius,
            "source_polygon_radius": old_radius,
        },
        instruction_template=f"将零件上的 {sides} 边形通孔替换为圆形通孔，其余结构保持不变。",
        instruction_hints={
            "operation": "replace",
            "old_feature_name": f"{sides} 边形通孔",
            "new_feature_name": "圆形通孔",
            "radius": new_radius,
            "source_polygon_radius": old_radius,
            "sides": sides,
            "replace_verbs": ["替换", "改成", "换成"],
            "preserve_other_geometry": True,
            "avoid_implementation_details": ["source_span", "block_span", "workplane", "csg", "cutter"],
        },
    )


def build_finishing_direct_candidate(
    candidate_id: str,
    source_record: dict[str, Any],
    delete_candidate: dict[str, Any],
    delete_report: dict[str, Any],
    intermediate_code: str,
) -> dict[str, Any] | None:
    old_feature = delete_candidate["delete_candidate"]
    edit_type = old_feature.get("edit_type")
    parameters = old_feature.get("parameters", {})
    block_text = old_feature.get("block_text")
    if not isinstance(block_text, str):
        return None
    if edit_type == "delete_chamfer":
        distance = parameters.get("distance")
        if not isinstance(distance, (int, float)) or distance <= 0:
            return None
        new_block_text, ok = replace_first(rf"\.chamfer\s*\(\s*({NUMBER_RE})\s*\)", r".fillet(\1)", block_text)
        if not ok:
            return None
        distance = round_float(distance)
        return build_direct_replace_candidate(
            candidate_id=candidate_id,
            source_record=source_record,
            delete_candidate=delete_candidate,
            delete_report=delete_report,
            intermediate_code=intermediate_code,
            edit_type="replace_chamfer_with_fillet",
            new_block_text=new_block_text,
            new_feature={"feature": "fillet", "feature_type": "fillet", "radius": distance},
            instruction_template=f"将零件边缘尺寸为 C{distance} 的倒角替换为 R{distance} 的圆角，其余结构保持不变。",
            instruction_hints={
                "operation": "replace",
                "old_feature_name": "倒角",
                "new_feature_name": "圆角",
                "distance": distance,
                "radius": distance,
                "replace_verbs": ["替换", "改成", "换成"],
                "preserve_other_geometry": True,
                "avoid_implementation_details": ["source_span", "block_span", "workplane", "csg", "cutter"],
            },
        )
    if edit_type == "delete_fillet":
        radius = parameters.get("radius")
        if not isinstance(radius, (int, float)) or radius <= 0:
            return None
        new_block_text, ok = replace_first(rf"\.fillet\s*\(\s*({NUMBER_RE})\s*\)", r".chamfer(\1)", block_text)
        if not ok:
            return None
        radius = round_float(radius)
        return build_direct_replace_candidate(
            candidate_id=candidate_id,
            source_record=source_record,
            delete_candidate=delete_candidate,
            delete_report=delete_report,
            intermediate_code=intermediate_code,
            edit_type="replace_fillet_with_chamfer",
            new_block_text=new_block_text,
            new_feature={"feature": "chamfer", "feature_type": "chamfer", "distance": radius},
            instruction_template=f"将零件边缘半径为 R{radius} 的圆角替换为 C{radius} 的倒角，其余结构保持不变。",
            instruction_hints={
                "operation": "replace",
                "old_feature_name": "圆角",
                "new_feature_name": "倒角",
                "radius": radius,
                "distance": radius,
                "replace_verbs": ["替换", "改成", "换成"],
                "preserve_other_geometry": True,
                "avoid_implementation_details": ["source_span", "block_span", "workplane", "csg", "cutter"],
            },
        )
    return None


def build_replace_candidate(
    candidate_id: str,
    source_record: dict[str, Any],
    delete_candidate: dict[str, Any],
    delete_report: dict[str, Any],
    intermediate_code: str,
    slot: dict[str, Any],
) -> dict[str, Any]:
    old_feature = delete_candidate["delete_candidate"]
    parameters = old_feature.get("parameters", {})
    diameter = parameters.get("diameter")
    human_dims = slot["human_dimensions"]
    edit_type = replace_edit_type_for_delete(old_feature)
    old_feature_name = delete_feature_name(old_feature)
    replace_candidate = {
        "candidate_type": "structural_replace",
        "edit_type": edit_type,
        "old_feature": old_feature,
        "new_feature": slot,
        "insertion_strategy": {
            "operation": "cut",
            "append_csg_block": True,
            "method": "delete_then_append_slot_cutter",
        },
        "instruction_template": (
            f"将零件上的{old_feature_name}替换为长度 {human_dims['length']}、宽度 {human_dims['width']} 的矩形槽，其余结构保持不变。"
        ),
        "instruction_hints": {
            "operation": "replace",
            "old_feature_name": old_feature_name,
            "new_feature_name": "矩形槽",
            "diameter": diameter,
            "length": human_dims["length"],
            "width": human_dims["width"],
            "replace_verbs": ["替换", "改成", "换成"],
            "preserve_other_geometry": True,
            "avoid_implementation_details": ["source_span", "block_span", "workplane", "csg", "cutter"],
        },
    }
    candidate = {
        "candidate_id": candidate_id,
        "sample_index": delete_candidate["sample_index"],
        "source_line": delete_candidate["source_line"],
        "images": source_record["images"],
        "original_code": delete_candidate["original_code"],
        "intermediate_code": intermediate_code,
        "delete_validation_report": delete_report,
        "replace_candidate": replace_candidate,
    }
    candidate["target_code"] = apply_replace_candidate(candidate)
    return candidate


def changed_geometry(shape_a: Any, shape_b: Any) -> tuple[dict[str, float], float] | None:
    try:
        diff_shape = shape_a.cut(shape_b)
        info = geometry_info(diff_shape)
    except Exception:
        return None
    if info.volume <= 1e-6:
        return None
    return info.bbox, info.volume


def bbox_center_distance(a: dict[str, float], b: dict[str, float]) -> float:
    ca = bbox_center(a)
    cb = bbox_center(b)
    return sum((ca[axis] - cb[axis]) ** 2 for axis in AXES) ** 0.5


def validate_slot_replace_edit(candidate: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": False,
        "mode": "cadquery_structural_replace",
        "checks": {},
        "errors": [],
        "delete_validation_report": candidate["delete_validation_report"],
    }
    try:
        original_shape = execute_shape(candidate["original_code"])
        deleted_shape = execute_shape(candidate["intermediate_code"])
        replaced_shape = execute_shape(candidate["target_code"])
        original_geometry = geometry_info(original_shape)
        deleted_geometry = geometry_info(deleted_shape)
        replaced_geometry = geometry_info(replaced_shape)
        delete_delta = round_float(deleted_geometry.volume - original_geometry.volume)
        slot_delta = round_float(replaced_geometry.volume - deleted_geometry.volume)
        final_delta = round_float(replaced_geometry.volume - original_geometry.volume)
        old_bbox = candidate["delete_validation_report"].get("changed_region_bbox")
        slot_bbox = candidate["replace_candidate"]["new_feature"]["affected_region_bbox"]

        report.update(
            {
                "original_volume": original_geometry.volume,
                "deleted_volume": deleted_geometry.volume,
                "replaced_volume": replaced_geometry.volume,
                "delete_volume_delta": delete_delta,
                "slot_volume_delta": slot_delta,
                "final_volume_delta": final_delta,
                "original_bbox": original_geometry.bbox,
                "deleted_bbox": deleted_geometry.bbox,
                "replaced_bbox": replaced_geometry.bbox,
                "old_feature_changed_region_bbox": old_bbox,
                "new_feature_affected_region_bbox": slot_bbox,
            }
        )

        checks = report["checks"]
        checks["delete_stage_ok"] = candidate["delete_validation_report"].get("ok") is True
        checks["original_executes"] = original_geometry.volume > 1e-6
        checks["deleted_executes"] = deleted_geometry.volume > 1e-6
        checks["replaced_executes"] = replaced_geometry.volume > 1e-6
        checks["replaced_non_empty"] = replaced_geometry.volume > 1e-6
        checks["delete_volume_increased"] = delete_delta > 1e-6
        checks["slot_volume_decreased_from_deleted"] = slot_delta < -1e-6
        checks["bbox_stable_original_to_deleted"] = bbox_same(deleted_geometry.bbox, original_geometry.bbox)
        checks["bbox_stable_deleted_to_replaced"] = bbox_within(replaced_geometry.bbox, expand_bbox(deleted_geometry.bbox, 1e-3))
        checks["bbox_not_collapsed"] = all(
            replaced_geometry.dims[axis] > max(original_geometry.dims[axis] * 0.5, 1e-6) for axis in AXES
        )

        slot_change = changed_geometry(deleted_shape, replaced_shape)
        if slot_change is None:
            checks["slot_changed_region_non_empty"] = False
            checks["slot_changed_region_local"] = False
            checks["slot_near_deleted_hole"] = False
        else:
            slot_changed_bbox, slot_changed_volume = slot_change
            report["slot_changed_region_bbox"] = slot_changed_bbox
            report["slot_changed_region_volume"] = slot_changed_volume
            slot_changed_dims = bbox_dims(slot_changed_bbox)
            checks["slot_changed_region_non_empty"] = slot_changed_volume > 1e-6
            checks["slot_changed_region_local"] = bbox_not_global(slot_changed_dims, deleted_geometry.dims) and bbox_within(
                slot_changed_bbox, expand_bbox(slot_bbox, max(deleted_geometry.dims.values()) * 0.02), tolerance=1e-3
            )
            if isinstance(old_bbox, dict):
                checks["slot_near_deleted_hole"] = bbox_center_distance(slot_changed_bbox, old_bbox) <= max(
                    candidate["replace_candidate"]["new_feature"]["dims"].values()
                )
            else:
                checks["slot_near_deleted_hole"] = False

        removed_final = changed_geometry(original_shape, replaced_shape)
        added_final = changed_geometry(replaced_shape, original_shape)
        checks["final_change_local"] = True
        if removed_final is not None:
            removed_bbox, removed_volume = removed_final
            report["final_removed_region_bbox"] = removed_bbox
            report["final_removed_region_volume"] = removed_volume
            checks["final_change_local"] = checks["final_change_local"] and bbox_not_global(
                bbox_dims(removed_bbox), original_geometry.dims
            )
        if added_final is not None:
            added_bbox, added_volume = added_final
            report["final_added_region_bbox"] = added_bbox
            report["final_added_region_volume"] = added_volume
            checks["final_change_local"] = checks["final_change_local"] and bbox_not_global(
                bbox_dims(added_bbox), original_geometry.dims
            )
        checks["final_has_geometric_change"] = removed_final is not None or added_final is not None

        failed = [name for name, value in checks.items() if not value]
        if failed:
            report["errors"].extend(f"failed check: {name}" for name in failed)
        report["ok"] = not failed
    except Exception as exc:
        report["errors"].append(str(exc))
    return report


def validate_cutout_replace_edit(candidate: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": False,
        "mode": "cadquery_structural_replace",
        "validation_policy": "cutout_replace",
        "checks": {},
        "errors": [],
        "delete_validation_report": candidate["delete_validation_report"],
    }
    try:
        original_shape = execute_shape(candidate["original_code"])
        deleted_shape = execute_shape(candidate["intermediate_code"])
        replaced_shape = execute_shape(candidate["target_code"])
        original_geometry = geometry_info(original_shape)
        deleted_geometry = geometry_info(deleted_shape)
        replaced_geometry = geometry_info(replaced_shape)
        delete_delta = round_float(deleted_geometry.volume - original_geometry.volume)
        final_delta = round_float(replaced_geometry.volume - original_geometry.volume)
        old_bbox = candidate["delete_validation_report"].get("changed_region_bbox")

        report.update(
            {
                "original_volume": original_geometry.volume,
                "deleted_volume": deleted_geometry.volume,
                "replaced_volume": replaced_geometry.volume,
                "delete_volume_delta": delete_delta,
                "final_volume_delta": final_delta,
                "original_bbox": original_geometry.bbox,
                "deleted_bbox": deleted_geometry.bbox,
                "replaced_bbox": replaced_geometry.bbox,
                "old_feature_changed_region_bbox": old_bbox,
            }
        )

        checks = report["checks"]
        checks["delete_stage_ok"] = candidate["delete_validation_report"].get("ok") is True
        checks["original_executes"] = original_geometry.volume > 1e-6
        checks["deleted_executes"] = deleted_geometry.volume > 1e-6
        checks["replaced_executes"] = replaced_geometry.volume > 1e-6
        checks["replaced_non_empty"] = replaced_geometry.volume > 1e-6
        checks["bbox_stable_original_to_deleted"] = bbox_same(deleted_geometry.bbox, original_geometry.bbox)
        checks["bbox_stable_original_to_replaced"] = bbox_same(replaced_geometry.bbox, original_geometry.bbox)
        checks["bbox_not_collapsed"] = all(
            replaced_geometry.dims[axis] > max(original_geometry.dims[axis] * 0.5, 1e-6) for axis in AXES
        )

        new_cut = changed_geometry(deleted_shape, replaced_shape)
        if new_cut is None:
            checks["new_feature_changed_region_non_empty"] = False
            checks["new_feature_changed_region_local"] = False
            checks["new_feature_near_old_feature"] = False
        else:
            new_bbox, new_volume = new_cut
            report["new_feature_changed_region_bbox"] = new_bbox
            report["new_feature_changed_region_volume"] = new_volume
            checks["new_feature_changed_region_non_empty"] = new_volume > 1e-6
            checks["new_feature_changed_region_local"] = bbox_not_global(bbox_dims(new_bbox), deleted_geometry.dims)
            if isinstance(old_bbox, dict):
                checks["new_feature_near_old_feature"] = bbox_center_distance(new_bbox, old_bbox) <= max(
                    max(bbox_dims(old_bbox).values()), max(bbox_dims(new_bbox).values())
                )
            else:
                checks["new_feature_near_old_feature"] = False

        removed_final = changed_geometry(original_shape, replaced_shape)
        added_final = changed_geometry(replaced_shape, original_shape)
        checks["final_change_local"] = True
        if removed_final is not None:
            removed_bbox, removed_volume = removed_final
            report["final_removed_region_bbox"] = removed_bbox
            report["final_removed_region_volume"] = removed_volume
            checks["final_change_local"] = checks["final_change_local"] and bbox_not_global(
                bbox_dims(removed_bbox), original_geometry.dims
            )
        if added_final is not None:
            added_bbox, added_volume = added_final
            report["final_added_region_bbox"] = added_bbox
            report["final_added_region_volume"] = added_volume
            checks["final_change_local"] = checks["final_change_local"] and bbox_not_global(
                bbox_dims(added_bbox), original_geometry.dims
            )
        checks["final_has_geometric_change"] = removed_final is not None or added_final is not None

        failed = [name for name, value in checks.items() if not value]
        if failed:
            report["errors"].extend(f"failed check: {name}" for name in failed)
        report["ok"] = not failed
    except Exception as exc:
        report["errors"].append(str(exc))
    return report


def validate_finishing_replace_edit(candidate: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": False,
        "mode": "cadquery_structural_replace",
        "validation_policy": "finishing_replace",
        "checks": {},
        "errors": [],
        "delete_validation_report": candidate["delete_validation_report"],
    }
    try:
        original_shape = execute_shape(candidate["original_code"])
        replaced_shape = execute_shape(candidate["target_code"])
        original_geometry = geometry_info(original_shape)
        replaced_geometry = geometry_info(replaced_shape)
        final_delta = round_float(replaced_geometry.volume - original_geometry.volume)
        report.update(
            {
                "original_volume": original_geometry.volume,
                "replaced_volume": replaced_geometry.volume,
                "final_volume_delta": final_delta,
                "original_bbox": original_geometry.bbox,
                "replaced_bbox": replaced_geometry.bbox,
            }
        )

        checks = report["checks"]
        checks["original_executes"] = original_geometry.volume > 1e-6
        checks["replaced_executes"] = replaced_geometry.volume > 1e-6
        checks["replaced_non_empty"] = replaced_geometry.volume > 1e-6
        checks["bbox_stable"] = bbox_same(replaced_geometry.bbox, original_geometry.bbox)
        checks["bbox_not_collapsed"] = all(
            replaced_geometry.dims[axis] > max(original_geometry.dims[axis] * 0.5, 1e-6) for axis in AXES
        )
        checks["volume_changed_nontrivially"] = abs(final_delta) > max(original_geometry.volume * 1e-7, 1e-4)

        removed_final = changed_geometry(original_shape, replaced_shape)
        added_final = changed_geometry(replaced_shape, original_shape)
        geometry_change_volume = 0.0
        if removed_final is not None:
            removed_bbox, removed_volume = removed_final
            report["final_removed_region_bbox"] = removed_bbox
            report["final_removed_region_volume"] = removed_volume
            geometry_change_volume += removed_volume
        if added_final is not None:
            added_bbox, added_volume = added_final
            report["final_added_region_bbox"] = added_bbox
            report["final_added_region_volume"] = added_volume
            geometry_change_volume += added_volume
        report["geometry_change_volume"] = round_float(geometry_change_volume)
        checks["geometry_changed_nontrivially"] = geometry_change_volume > max(original_geometry.volume * 1e-7, 1e-4)

        failed = [name for name, value in checks.items() if not value]
        if failed:
            report["errors"].extend(f"failed check: {name}" for name in failed)
        report["ok"] = not failed
    except Exception as exc:
        report["errors"].append(str(exc))
    return report


def validate_replace_edit(candidate: dict[str, Any]) -> dict[str, Any]:
    replace_candidate = candidate.get("replace_candidate") if isinstance(candidate, dict) else None
    edit_type = replace_candidate.get("edit_type") if isinstance(replace_candidate, dict) else None
    if edit_type in FINISHING_REPLACE_TYPES:
        return validate_finishing_replace_edit(candidate)
    if edit_type in DIRECT_CUTOUT_REPLACE_TYPES:
        return validate_cutout_replace_edit(candidate)
    return validate_slot_replace_edit(candidate)


def fallback_instruction(candidate: dict[str, Any]) -> str:
    replace_candidate = candidate["replace_candidate"]
    edit_type = replace_candidate.get("edit_type")
    hints = replace_candidate["instruction_hints"]
    diameter = hints.get("diameter")
    length = hints.get("length")
    width = hints.get("width")
    old_feature = hints.get("old_feature_name", "圆孔")
    new_feature = hints.get("new_feature_name", "新结构")

    if edit_type in SLOT_REPLACE_TYPES and all(isinstance(value, (int, float)) for value in (diameter, length, width)):
        return f"将直径为 {diameter} 的{old_feature}替换为长度 {length}、宽度 {width} 的矩形槽，其余结构保持不变。"
    if edit_type == "replace_circular_cutout_with_polygonal_cutout":
        radius = hints.get("radius")
        if isinstance(radius, (int, float)):
            return f"将零件上半径为 {radius} 的圆形通孔替换为六边形通孔，其余结构保持不变。"
        return "将零件上的圆形通孔替换为六边形通孔，其余结构保持不变。"
    if edit_type == "replace_polygonal_cutout_with_circular_cutout":
        sides = hints.get("sides")
        if isinstance(sides, int):
            return f"将零件上的 {sides} 边形通孔替换为圆形通孔，其余结构保持不变。"
        return "将零件上的多边形通孔替换为圆形通孔，其余结构保持不变。"
    if edit_type == "replace_chamfer_with_fillet":
        distance = hints.get("distance")
        radius = hints.get("radius")
        if isinstance(distance, (int, float)) and isinstance(radius, (int, float)):
            return f"将零件边缘尺寸为 C{distance} 的倒角替换为 R{radius} 的圆角，其余结构保持不变。"
        return "将零件边缘的倒角替换为圆角，其余结构保持不变。"
    if edit_type == "replace_fillet_with_chamfer":
        radius = hints.get("radius")
        distance = hints.get("distance")
        if isinstance(radius, (int, float)) and isinstance(distance, (int, float)):
            return f"将零件边缘半径为 R{radius} 的圆角替换为 C{distance} 的倒角，其余结构保持不变。"
        return "将零件边缘的圆角替换为倒角，其余结构保持不变。"
    if edit_type in SLOT_REPLACE_TYPES:
        return f"将零件上的{old_feature}替换为矩形槽，其余结构保持不变。"
    return f"将零件上的{old_feature}替换为{new_feature}，其余结构保持不变。"


def final_record(validated: dict[str, Any], instruction_record: dict[str, Any] | None = None) -> dict[str, Any]:
    instruction = validated["fallback_instruction"]
    instruction_meta = {
        "generator": "structural_replace_template",
        "fallback_used": True,
        "included_target_code": False,
        "instruction_mode": "structural_replace",
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
            "intermediate_code": validated["intermediate_code"],
            "edit_record": validated["edit_record"],
            "validation_report": validated["validation_report"],
            "instruction_meta": instruction_meta,
        },
    }


def generate_replace_candidates_for_record(
    source_record: dict[str, Any],
    sample_index: int,
    source_line: int,
    max_replacements_per_sample: int,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    stats: Counter[str] = Counter()
    images = extract_images(source_record)
    original_code = extract_original_code(source_record)
    if not original_code:
        stats["skipped_no_code"] += 1
        return [], stats

    source_for_delete = dict(source_record)
    source_for_delete["images"] = images
    source_for_delete["original_code"] = original_code
    source_for_delete.setdefault("hidden", {})
    if isinstance(source_for_delete["hidden"], dict):
        source_for_delete["hidden"]["original_code"] = original_code

    delete_candidates, delete_stats = generate_delete_candidates_for_record(
        source_record=source_for_delete,
        sample_index=sample_index,
        source_line=source_line,
        max_deletes_per_sample=max_replacements_per_sample,
    )
    stats.update({f"delete_{key}": value for key, value in delete_stats.items()})
    replace_candidates: list[dict[str, Any]] = []
    candidate_index = 1
    for delete_candidate in delete_candidates:
        if len(replace_candidates) >= max_replacements_per_sample:
            break
        intermediate_code = apply_delete_candidate(delete_candidate)
        delete_report = validate_delete_edit(original_code, intermediate_code, delete_candidate)
        old_feature = delete_candidate["delete_candidate"]
        old_edit_type = old_feature.get("edit_type")
        built_for_delete = 0

        def add_candidate(candidate: dict[str, Any] | None) -> None:
            nonlocal candidate_index, built_for_delete
            if candidate is None or len(replace_candidates) >= max_replacements_per_sample:
                return
            replace_candidates.append(candidate)
            stats["candidate_records"] += 1
            candidate_index += 1
            built_for_delete += 1

        if old_edit_type in {"delete_hole", "delete_circular_cutout", "delete_polygonal_cutout"}:
            if not delete_report.get("ok"):
                stats["skipped_delete_validation_failed"] += 1
                continue
            if old_edit_type == "delete_circular_cutout":
                add_candidate(
                    build_circular_cutout_to_polygonal_candidate(
                        candidate_id=f"v4rep_{sample_index:06d}_{candidate_index:03d}",
                        source_record={"images": images},
                        delete_candidate=delete_candidate,
                        delete_report=delete_report,
                        intermediate_code=intermediate_code,
                    )
                )
            if old_edit_type == "delete_polygonal_cutout":
                add_candidate(
                    build_polygonal_cutout_to_circular_candidate(
                        candidate_id=f"v4rep_{sample_index:06d}_{candidate_index:03d}",
                        source_record={"images": images},
                        delete_candidate=delete_candidate,
                        delete_report=delete_report,
                        intermediate_code=intermediate_code,
                    )
                )
            if len(replace_candidates) < max_replacements_per_sample:
                slot = replacement_slot_from_delete_report(delete_candidate, delete_report)
                if slot is None:
                    stats["skipped_slot_geometry"] += 1
                else:
                    add_candidate(
                        build_replace_candidate(
                            candidate_id=f"v4rep_{sample_index:06d}_{candidate_index:03d}",
                            source_record={"images": images},
                            delete_candidate=delete_candidate,
                            delete_report=delete_report,
                            intermediate_code=intermediate_code,
                            slot=slot,
                        )
                    )
        elif old_edit_type in {"delete_chamfer", "delete_fillet"}:
            add_candidate(
                build_finishing_direct_candidate(
                    candidate_id=f"v4rep_{sample_index:06d}_{candidate_index:03d}",
                    source_record={"images": images},
                    delete_candidate=delete_candidate,
                    delete_report=delete_report,
                    intermediate_code=intermediate_code,
                )
            )
        else:
            stats["skipped_missing_dependency_delete_type"] += 1

        if built_for_delete == 0:
            stats["skipped_no_replace_for_delete_candidate"] += 1

    if not replace_candidates:
        stats["skipped_no_replace_candidate"] += 1
    return replace_candidates, stats


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("data_t.jsonl"), type=Path)
    parser.add_argument("--output", default=Path("outputs/cad_edit_v4_replace.jsonl"), type=Path)
    parser.add_argument("--candidates-output", default=Path("outputs/cad_edit_v4_replace_candidates.jsonl"), type=Path)
    parser.add_argument(
        "--validated-output", default=Path("outputs/cad_edit_v4_validated_replace_edits.jsonl"), type=Path
    )
    parser.add_argument("--instructions-output", default=Path("outputs/cad_edit_v4_replace_instructions.jsonl"), type=Path)
    parser.add_argument("--max-replacements-per-sample", default=1, type=int)
    parser.add_argument("--keep-failed", action="store_true")
    parser.add_argument("--no-final-output", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.max_replacements_per_sample <= 0:
        raise ValueError("--max-replacements-per-sample must be positive")

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
                candidates, stats = generate_replace_candidates_for_record(
                    source_record=source_record,
                    sample_index=sample_index,
                    source_line=source_line,
                    max_replacements_per_sample=args.max_replacements_per_sample,
                )
                summary.update(stats)
                for candidate in candidates:
                    validation_report = validate_replace_edit(candidate)
                    candidate["validation_report"] = validation_report
                    candidates_handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
                    summary["candidate_output_records"] += 1
                    if not validation_report.get("ok") and not args.keep_failed:
                        summary["failed_validation"] += 1
                        for error in validation_report.get("errors", [])[:1]:
                            summary[f"validation_error:{error[:80]}"] += 1
                        continue
                    validated = {
                        "candidate_id": candidate["candidate_id"],
                        "sample_index": candidate["sample_index"],
                        "source_line": candidate["source_line"],
                        "images": candidate["images"],
                        "original_code": candidate["original_code"],
                        "intermediate_code": candidate["intermediate_code"],
                        "replace_candidate": candidate["replace_candidate"],
                        "edit_candidate": candidate["replace_candidate"],
                        "target_code": candidate["target_code"],
                        "edit_record": candidate["replace_candidate"],
                        "validation_report": validation_report,
                        "fallback_instruction": fallback_instruction(candidate),
                    }
                    validated_handle.write(json.dumps(validated, ensure_ascii=False) + "\n")
                    summary["validated_output_records"] += 1
                    instruction_record = {
                        "candidate_id": candidate["candidate_id"],
                        "instruction": validated["fallback_instruction"],
                        "instruction_meta": {
                            "generator": "structural_replace_template",
                            "fallback_used": True,
                            "used_original_code": True,
                            "used_candidate": True,
                            "included_target_code": False,
                            "instruction_mode": "structural_replace",
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
