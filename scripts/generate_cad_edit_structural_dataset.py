#!/usr/bin/env python3
"""Generate V2 add-only structural CAD edit dataset records."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cadquery as cq

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_cad_edit_dataset import extract_images, extract_original_code, read_jsonl  # noqa: E402


SUBTRACTIVE_EDITS = {"add_through_hole", "add_blind_hole", "add_rectangular_slot", "add_pocket"}
PLANE_FOR_AXIS = {"x": "YZ", "y": "XZ", "z": "XY"}
EXTRUDE_SIGN_FOR_AXIS = {"x": 1, "y": -1, "z": 1}
AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
AXES = ("x", "y", "z")


@dataclass(frozen=True)
class GeometryInfo:
    volume: float
    bbox: dict[str, float]
    dims: dict[str, float]


@dataclass(frozen=True)
class SurfaceRegion:
    axis: str
    side: str
    normal: tuple[float, float, float]
    plane: str
    tangent_axes: tuple[str, str]
    center: dict[str, float]
    area: float


def round_float(value: float, digits: int = 4) -> float:
    rounded = round(float(value), digits)
    if rounded == int(rounded):
        return float(int(rounded))
    return rounded


def tuple3(values: Iterable[float]) -> tuple[float, float, float]:
    value_tuple = tuple(float(item) for item in values)
    if len(value_tuple) != 3:
        raise ValueError(f"expected 3 values, got {value_tuple!r}")
    return value_tuple


def bbox_dict_from_shape(shape: Any) -> dict[str, float]:
    bbox = shape.BoundingBox()
    return {
        "xmin": round_float(bbox.xmin),
        "xmax": round_float(bbox.xmax),
        "ymin": round_float(bbox.ymin),
        "ymax": round_float(bbox.ymax),
        "zmin": round_float(bbox.zmin),
        "zmax": round_float(bbox.zmax),
    }


def bbox_dims(bbox: dict[str, float]) -> dict[str, float]:
    return {
        "x": round_float(bbox["xmax"] - bbox["xmin"]),
        "y": round_float(bbox["ymax"] - bbox["ymin"]),
        "z": round_float(bbox["zmax"] - bbox["zmin"]),
    }


def bbox_center(bbox: dict[str, float]) -> dict[str, float]:
    return {
        "x": round_float((bbox["xmin"] + bbox["xmax"]) / 2),
        "y": round_float((bbox["ymin"] + bbox["ymax"]) / 2),
        "z": round_float((bbox["zmin"] + bbox["zmax"]) / 2),
    }


def geometry_info(shape: Any) -> GeometryInfo:
    bbox = bbox_dict_from_shape(shape)
    return GeometryInfo(volume=round_float(shape.Volume()), bbox=bbox, dims=bbox_dims(bbox))


def execute_cadquery_source(source: str) -> Any:
    namespace: dict[str, Any] = {"cq": cq, "cadquery": cq}
    exec(compile(source, "<cadquery_source>", "exec"), namespace)
    if "result" not in namespace:
        raise RuntimeError("result variable was not defined")
    return namespace["result"]


def shape_from_result(result: Any) -> Any:
    if hasattr(result, "val") and callable(result.val):
        return result.val()
    return result


def execute_shape(source: str) -> Any:
    return shape_from_result(execute_cadquery_source(source))


def dominant_axis_from_normal(normal: tuple[float, float, float], threshold: float = 0.95) -> tuple[str, str] | None:
    absolute = [abs(value) for value in normal]
    index = max(range(3), key=lambda item: absolute[item])
    if absolute[index] < threshold:
        return None
    axis = AXES[index]
    side = "+" if normal[index] >= 0 else "-"
    return axis, side


def tangent_axes_for(axis: str) -> tuple[str, str]:
    return tuple(item for item in AXES if item != axis)  # type: ignore[return-value]


def find_axis_aligned_regions(shape: Any) -> list[SurfaceRegion]:
    regions: list[SurfaceRegion] = []
    for face in shape.Faces():
        try:
            normal = tuple3(face.normalAt().toTuple())
            dominant = dominant_axis_from_normal(normal)
            if dominant is None:
                continue
            axis, side = dominant
            center_tuple = tuple3(face.Center().toTuple())
            center = {axis_name: round_float(center_tuple[index]) for index, axis_name in enumerate(AXES)}
            regions.append(
                SurfaceRegion(
                    axis=axis,
                    side=side,
                    normal=tuple(round_float(value) for value in normal),
                    plane=PLANE_FOR_AXIS[axis],
                    tangent_axes=tangent_axes_for(axis),
                    center=center,
                    area=round_float(face.Area()),
                )
            )
        except Exception:
            continue
    return sorted(regions, key=lambda item: item.area, reverse=True)


def choose_target_region(shape: Any, geometry: GeometryInfo) -> SurfaceRegion | None:
    regions = find_axis_aligned_regions(shape)
    positive_regions = [region for region in regions if region.side == "+"]
    candidates = positive_regions or regions
    for region in candidates:
        tangent_dims = [geometry.dims[axis] for axis in region.tangent_axes]
        normal_dim = geometry.dims[region.axis]
        if min(tangent_dims) > 1e-6 and normal_dim > 1e-6:
            return region
    return None


def feature_origin(geometry: GeometryInfo, region: SurfaceRegion) -> dict[str, float]:
    bbox = geometry.bbox
    dims = geometry.dims
    center = bbox_center(bbox)
    tangent_dims = {axis: dims[axis] for axis in region.tangent_axes}
    major_axis = max(region.tangent_axes, key=lambda axis: tangent_dims[axis])
    origin = dict(center)
    origin[region.axis] = bbox[f"{region.axis}max"] if region.side == "+" else bbox[f"{region.axis}min"]
    origin[major_axis] = round_float(center[major_axis] + 0.65 * dims[major_axis] / 2)
    return origin


def bbox_from_center_dims(center: dict[str, float], dims: dict[str, float]) -> dict[str, float]:
    return {
        "xmin": round_float(center["x"] - dims["x"] / 2),
        "xmax": round_float(center["x"] + dims["x"] / 2),
        "ymin": round_float(center["y"] - dims["y"] / 2),
        "ymax": round_float(center["y"] + dims["y"] / 2),
        "zmin": round_float(center["z"] - dims["z"] / 2),
        "zmax": round_float(center["z"] + dims["z"] / 2),
    }


def cylinder_affected_bbox(origin: dict[str, float], axis: str, radius: float, start: float, end: float) -> dict[str, float]:
    bbox: dict[str, float] = {}
    for item in AXES:
        if item == axis:
            bbox[f"{item}min"] = round_float(min(start, end))
            bbox[f"{item}max"] = round_float(max(start, end))
        else:
            bbox[f"{item}min"] = round_float(origin[item] - radius)
            bbox[f"{item}max"] = round_float(origin[item] + radius)
    return bbox


def primitive_dims_for_box(
    geometry: GeometryInfo,
    region: SurfaceRegion,
    edit_type: str,
    margin: float,
) -> tuple[dict[str, float], float]:
    dims = {axis: 0.0 for axis in AXES}
    tangent_a, tangent_b = region.tangent_axes
    major_axis = max(region.tangent_axes, key=lambda axis: geometry.dims[axis])
    minor_axis = tangent_b if major_axis == tangent_a else tangent_a
    normal_dim = geometry.dims[region.axis]

    if edit_type == "add_rectangular_slot":
        dims[major_axis] = round_float(max(margin * 2.0, geometry.dims[major_axis] * 0.28))
        dims[minor_axis] = round_float(max(margin * 0.8, geometry.dims[minor_axis] * 0.08))
        dims[region.axis] = round_float(normal_dim + 2 * margin)
        normal_center_offset = 0.0
    elif edit_type == "add_pocket":
        dims[major_axis] = round_float(max(margin * 1.5, geometry.dims[major_axis] * 0.22))
        dims[minor_axis] = round_float(max(margin, geometry.dims[minor_axis] * 0.12))
        dims[region.axis] = round_float(max(normal_dim * 0.2, margin))
        normal_center_offset = -dims[region.axis] / 2 if region.side == "+" else dims[region.axis] / 2
    else:
        raise ValueError(f"unsupported box edit type: {edit_type}")
    return dims, normal_center_offset


def cylinder_instruction_hints(edit_type: str, radius: float, depth: float | None = None) -> dict[str, Any]:
    hints: dict[str, Any] = {
        "feature": "through_hole" if edit_type == "add_through_hole" else "blind_hole",
        "human_feature_name": "贯穿圆孔" if edit_type == "add_through_hole" else "盲孔",
        "diameter": round_float(radius * 2),
        "radius": radius,
        "preferred_position_style": "visual_surface_region",
        "avoid_implementation_details": ["workplane", "origin", "axis_coordinates", "cutter_depth"],
    }
    if edit_type == "add_through_hole":
        hints["through"] = True
        hints["do_not_mention_depth"] = True
    elif depth is not None:
        hints["depth"] = depth
    return hints


def box_instruction_hints(
    edit_type: str,
    geometry: GeometryInfo,
    region: SurfaceRegion,
    dims: dict[str, float],
) -> dict[str, Any]:
    tangent_a, tangent_b = region.tangent_axes
    major_axis = max(region.tangent_axes, key=lambda axis: geometry.dims[axis])
    minor_axis = tangent_b if major_axis == tangent_a else tangent_a
    hints: dict[str, Any] = {
        "feature": "rectangular_slot" if edit_type == "add_rectangular_slot" else "pocket",
        "human_feature_name": "矩形槽" if edit_type == "add_rectangular_slot" else "矩形凹陷",
        "length": round_float(dims[major_axis]),
        "width": round_float(dims[minor_axis]),
        "preferred_position_style": "visual_surface_region",
        "avoid_implementation_details": ["workplane", "origin", "axis_coordinates", "cutter_depth"],
    }
    if edit_type == "add_rectangular_slot":
        hints["through"] = True
        hints["do_not_mention_depth"] = True
    else:
        hints["depth"] = round_float(dims[region.axis])
    return hints


def build_structural_candidate(
    candidate_id: str,
    sample_index: int,
    source_line: int,
    images: list[str],
    original_code: str,
    geometry: GeometryInfo,
    region: SurfaceRegion,
    edit_type: str,
) -> dict[str, Any] | None:
    normal_dim = geometry.dims[region.axis]
    tangent_dims = [geometry.dims[axis] for axis in region.tangent_axes]
    min_tangent = min(tangent_dims)
    margin = round_float(max(min_tangent * 0.08, normal_dim * 0.08, 1.0))
    if min_tangent <= margin * 4 or normal_dim <= 1e-6:
        return None

    origin = feature_origin(geometry, region)
    primitive: dict[str, Any]
    insertion_strategy: dict[str, Any]
    instruction_hints: dict[str, Any]

    if edit_type in {"add_through_hole", "add_blind_hole"}:
        radius = round_float(max(min_tangent * 0.05, margin * 0.75))
        if radius * 2 >= min_tangent - 2 * margin:
            return None
        workplane_sign = EXTRUDE_SIGN_FOR_AXIS[region.axis]
        if edit_type == "add_through_hole":
            if workplane_sign > 0:
                start = geometry.bbox[f"{region.axis}min"] - margin
            else:
                start = geometry.bbox[f"{region.axis}max"] + margin
            depth = round_float(geometry.dims[region.axis] + 2 * margin)
            end = round_float(start + workplane_sign * depth)
            extrude = depth
            origin_for_code = dict(origin)
            origin_for_code[region.axis] = round_float(start)
            instruction_template = "在零件主平面上添加一个贯穿圆孔。"
        else:
            depth = round_float(max(normal_dim * 0.45, margin))
            side_sign = 1 if region.side == "+" else -1
            inward_sign = -side_sign
            start = (
                geometry.bbox[f"{region.axis}max"] + margin * 0.05
                if region.side == "+"
                else geometry.bbox[f"{region.axis}min"] - margin * 0.05
            )
            total_depth = round_float(depth + margin * 0.1)
            end = round_float(start + inward_sign * total_depth)
            extrude = round_float((inward_sign / workplane_sign) * total_depth)
            origin_for_code = dict(origin)
            origin_for_code[region.axis] = round_float(start)
            instruction_template = "在零件主平面上添加一个盲孔。"

        primitive = {
            "kind": "cylinder",
            "radius": radius,
            "depth": depth,
            "axis": region.axis,
            "center": {axis: round_float(origin[axis]) for axis in AXES},
        }
        instruction_hints = cylinder_instruction_hints(edit_type, radius, depth if edit_type == "add_blind_hole" else None)
        insertion_strategy = {
            "operation": "cut",
            "workplane": region.plane,
            "origin": {axis: round_float(origin_for_code[axis]) for axis in AXES},
            "extrude": extrude,
            "append_csg_block": True,
        }
        affected_bbox = cylinder_affected_bbox(origin, region.axis, radius, start, end)
    elif edit_type in {"add_rectangular_slot", "add_pocket"}:
        dims, normal_offset = primitive_dims_for_box(geometry, region, edit_type, margin)
        center = dict(origin)
        if edit_type == "add_rectangular_slot":
            center[region.axis] = round_float((geometry.bbox[f"{region.axis}min"] + geometry.bbox[f"{region.axis}max"]) / 2)
            instruction_template = "在零件主平面上添加一个矩形槽。"
        else:
            center[region.axis] = round_float(origin[region.axis] + normal_offset)
            instruction_template = "在零件主平面上添加一个矩形凹陷。"

        primitive = {
            "kind": "box",
            "dims": {axis: round_float(dims[axis]) for axis in AXES},
            "center": {axis: round_float(center[axis]) for axis in AXES},
        }
        instruction_hints = box_instruction_hints(edit_type, geometry, region, dims)
        insertion_strategy = {
            "operation": "cut",
            "workplane": "XY",
            "origin": {"x": 0.0, "y": 0.0, "z": 0.0},
            "translate": {axis: round_float(center[axis]) for axis in AXES},
            "append_csg_block": True,
        }
        affected_bbox = bbox_from_center_dims(center, dims)
    else:
        raise ValueError(f"unsupported edit type: {edit_type}")

    return {
        "candidate_id": candidate_id,
        "sample_index": sample_index,
        "source_line": source_line,
        "images": images,
        "original_code": original_code,
        "original_geometry": {
            "volume": geometry.volume,
            "bbox": geometry.bbox,
            "dims": geometry.dims,
        },
        "structural_candidate": {
            "edit_type": edit_type,
            "target_region": {
                "region_type": "axis_aligned_exterior_face",
                "axis": region.axis,
                "side": region.side,
                "normal": list(region.normal),
                "plane": region.plane,
                "tangent_axes": list(region.tangent_axes),
                "center": {axis: round_float(origin[axis]) for axis in AXES},
                "face_area": region.area,
            },
            "primitive": primitive,
            "insertion_strategy": insertion_strategy,
            "affected_region_bbox": affected_bbox,
            "instruction_template": instruction_template,
            "instruction_hints": instruction_hints,
        },
    }


def format_tuple(values: dict[str, float]) -> str:
    return f"({values['x']}, {values['y']}, {values['z']})"


def csg_block_for_candidate(candidate: dict[str, Any]) -> str:
    structural = candidate["structural_candidate"]
    edit_type = structural["edit_type"]
    primitive = structural["primitive"]
    strategy = structural["insertion_strategy"]
    candidate_id = candidate["candidate_id"]

    lines = [
        "",
        f"# V2 structural edit: {edit_type} ({candidate_id})",
    ]
    if primitive["kind"] == "cylinder":
        lines.append(
            "v2_cutter = "
            f"cq.Workplane({strategy['workplane']!r}, origin={format_tuple(strategy['origin'])})"
            f".circle({primitive['radius']}).extrude({strategy['extrude']})"
        )
        lines.append("result = result.cut(v2_cutter)")
    elif primitive["kind"] == "box":
        dims = primitive["dims"]
        translate = strategy["translate"]
        lines.append(
            "v2_cutter = "
            f"cq.Workplane('XY').box({dims['x']}, {dims['y']}, {dims['z']})"
            f".translate({format_tuple(translate)})"
        )
        lines.append("result = result.cut(v2_cutter)")
    else:
        raise ValueError(f"unsupported primitive: {primitive['kind']}")
    return "\n".join(lines)


def apply_structural_candidate(candidate: dict[str, Any]) -> str:
    return candidate["original_code"].rstrip() + "\n" + csg_block_for_candidate(candidate) + "\n"


def expand_bbox(bbox: dict[str, float], amount: float) -> dict[str, float]:
    return {
        "xmin": bbox["xmin"] - amount,
        "xmax": bbox["xmax"] + amount,
        "ymin": bbox["ymin"] - amount,
        "ymax": bbox["ymax"] + amount,
        "zmin": bbox["zmin"] - amount,
        "zmax": bbox["zmax"] + amount,
    }


def bbox_within(inner: dict[str, float], outer: dict[str, float], tolerance: float = 1e-4) -> bool:
    return (
        inner["xmin"] >= outer["xmin"] - tolerance
        and inner["xmax"] <= outer["xmax"] + tolerance
        and inner["ymin"] >= outer["ymin"] - tolerance
        and inner["ymax"] <= outer["ymax"] + tolerance
        and inner["zmin"] >= outer["zmin"] - tolerance
        and inner["zmax"] <= outer["zmax"] + tolerance
    )


def bbox_not_collapsed(dims: dict[str, float], reference_dims: dict[str, float]) -> bool:
    return all(dims[axis] > max(reference_dims[axis] * 0.5, 1e-6) for axis in AXES)


def difference_shape(shape_a: Any, shape_b: Any) -> Any:
    return shape_a.cut(shape_b)


def validate_structural_edit(original_code: str, target_code: str, candidate: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": False,
        "mode": "cadquery_structural",
        "checks": {},
        "errors": [],
    }
    try:
        original_shape = execute_shape(original_code)
        edited_shape = execute_shape(target_code)
        original_geometry = geometry_info(original_shape)
        edited_geometry = geometry_info(edited_shape)
        volume_delta = round_float(edited_geometry.volume - original_geometry.volume)
        affected_bbox = candidate["structural_candidate"]["affected_region_bbox"]
        edit_type = candidate["structural_candidate"]["edit_type"]

        report.update(
            {
                "original_volume": original_geometry.volume,
                "edited_volume": edited_geometry.volume,
                "volume_delta": volume_delta,
                "original_bbox": original_geometry.bbox,
                "edited_bbox": edited_geometry.bbox,
                "affected_region_bbox": affected_bbox,
            }
        )

        checks = report["checks"]
        checks["original_executes"] = original_geometry.volume > 1e-6
        checks["edited_executes"] = edited_geometry.volume > 1e-6
        checks["edited_non_empty"] = edited_geometry.volume > 1e-6

        if edit_type in SUBTRACTIVE_EDITS:
            checks["volume_direction_ok"] = volume_delta < -1e-6
            checks["bbox_growth_ok"] = bbox_within(edited_geometry.bbox, expand_bbox(original_geometry.bbox, 1e-3))
        else:
            checks["volume_direction_ok"] = volume_delta > 1e-6
            checks["bbox_growth_ok"] = True
        checks["bbox_not_collapsed"] = bbox_not_collapsed(edited_geometry.dims, original_geometry.dims)

        try:
            removed_shape = difference_shape(original_shape, edited_shape)
            removed_geometry = geometry_info(removed_shape)
            report["changed_region_bbox"] = removed_geometry.bbox
            report["changed_region_volume"] = removed_geometry.volume
            expanded_affected = expand_bbox(affected_bbox, max(original_geometry.dims.values()) * 0.02)
            checks["locality_ok"] = removed_geometry.volume > 1e-6 and bbox_within(
                removed_geometry.bbox, expanded_affected, tolerance=1e-3
            )
            checks["volume_delta_matches_changed_region"] = abs(abs(volume_delta) - removed_geometry.volume) <= max(
                abs(volume_delta) * 0.25, 1e-3
            )
        except Exception as exc:
            checks["locality_ok"] = False
            checks["volume_delta_matches_changed_region"] = False
            report["errors"].append(f"changed-region check failed: {exc}")

        failed = [name for name, value in checks.items() if not value]
        if failed:
            report["errors"].extend(f"failed check: {name}" for name in failed)
        report["ok"] = not failed
    except Exception as exc:
        report["errors"].append(str(exc))
    return report


def fallback_instruction(candidate: dict[str, Any]) -> str:
    structural = candidate["structural_candidate"]
    primitive = structural["primitive"]
    hints = structural.get("instruction_hints")
    if not isinstance(hints, dict):
        hints = {}
    edit_type = structural["edit_type"]
    if edit_type == "add_through_hole":
        diameter = hints.get("diameter", round_float(primitive["radius"] * 2))
        return f"在零件主平面上添加一个直径为 {diameter} 的贯穿圆孔。"
    if edit_type == "add_blind_hole":
        diameter = hints.get("diameter", round_float(primitive["radius"] * 2))
        depth = hints.get("depth", primitive["depth"])
        return f"在零件主平面上添加一个直径为 {diameter}、深度为 {depth} 的盲孔。"
    if edit_type == "add_rectangular_slot":
        length = hints.get("length")
        width = hints.get("width")
        if length is not None and width is not None:
            return f"在零件主平面上添加一个长度约为 {length}、宽度约为 {width} 的矩形槽。"
        dims = primitive["dims"]
        return f"在零件主平面上添加一个矩形槽。"
    if edit_type == "add_pocket":
        length = hints.get("length")
        width = hints.get("width")
        depth = hints.get("depth")
        if length is not None and width is not None and depth is not None:
            return f"在零件主平面上添加一个长度约为 {length}、宽度约为 {width}、深度约为 {depth} 的矩形凹陷。"
        dims = primitive["dims"]
        return f"在零件主平面上添加一个尺寸约为 {dims['x']} x {dims['y']} x {dims['z']} 的矩形凹陷。"
    return structural["instruction_template"]


def final_record(validated: dict[str, Any], instruction_record: dict[str, Any] | None = None) -> dict[str, Any]:
    instruction = validated["fallback_instruction"]
    instruction_meta = {"generator": "structural_template", "fallback_used": True, "included_target_code": False}
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


def generate_candidates_for_record(
    source_record: dict[str, Any],
    sample_index: int,
    source_line: int,
    max_edits_per_sample: int,
    edit_types: list[str],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    stats: Counter[str] = Counter()
    images = extract_images(source_record)
    original_code = extract_original_code(source_record)
    if not original_code:
        stats["skipped_no_code"] += 1
        return [], stats

    try:
        shape = execute_shape(original_code)
        geometry = geometry_info(shape)
        region = choose_target_region(shape, geometry)
    except Exception as exc:
        stats["skipped_geometry_error"] += 1
        stats[f"geometry_error:{str(exc)[:80]}"] += 1
        return [], stats

    if region is None:
        stats["skipped_no_high_confidence_region"] += 1
        return [], stats

    candidates: list[dict[str, Any]] = []
    for candidate_index, edit_type in enumerate(edit_types[:max_edits_per_sample], start=1):
        candidate_id = f"v2_{sample_index:06d}_{candidate_index:03d}"
        candidate = build_structural_candidate(
            candidate_id=candidate_id,
            sample_index=sample_index,
            source_line=source_line,
            images=images,
            original_code=original_code,
            geometry=geometry,
            region=region,
            edit_type=edit_type,
        )
        if candidate is None:
            stats["skipped_bad_candidate_geometry"] += 1
            continue
        candidates.append(candidate)
        stats["candidate_records"] += 1
    return candidates, stats


def parse_edit_types(value: str) -> list[str]:
    edit_types = [item.strip() for item in value.split(",") if item.strip()]
    unsupported = sorted(set(edit_types) - SUBTRACTIVE_EDITS)
    if unsupported:
        raise argparse.ArgumentTypeError(f"unsupported V2 edit types: {unsupported}")
    return edit_types


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("data_t.jsonl"), type=Path)
    parser.add_argument("--output", default=Path("outputs/cad_edit_v2.jsonl"), type=Path)
    parser.add_argument(
        "--candidates-output",
        default=Path("outputs/cad_edit_v2_structural_candidates.jsonl"),
        type=Path,
    )
    parser.add_argument(
        "--validated-output",
        default=Path("outputs/cad_edit_v2_validated_structural_edits.jsonl"),
        type=Path,
    )
    parser.add_argument("--instructions-output", default=Path("outputs/cad_edit_v2_instructions.jsonl"), type=Path)
    parser.add_argument("--max-edits-per-sample", default=4, type=int)
    parser.add_argument(
        "--edit-types",
        default=parse_edit_types("add_through_hole,add_blind_hole,add_rectangular_slot,add_pocket"),
        type=parse_edit_types,
    )
    parser.add_argument("--keep-failed", action="store_true")
    parser.add_argument("--no-final-output", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.max_edits_per_sample <= 0:
        raise ValueError("--max-edits-per-sample must be positive")

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
                candidates, stats = generate_candidates_for_record(
                    source_record=source_record,
                    sample_index=sample_index,
                    source_line=source_line,
                    max_edits_per_sample=args.max_edits_per_sample,
                    edit_types=args.edit_types,
                )
                summary.update(stats)
                for candidate in candidates:
                    candidates_handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
                    summary["candidate_output_records"] += 1
                    target_code = apply_structural_candidate(candidate)
                    validation_report = validate_structural_edit(candidate["original_code"], target_code, candidate)
                    if not validation_report.get("ok") and not args.keep_failed:
                        summary["failed_validation"] += 1
                        for error in validation_report.get("errors", [])[:1]:
                            summary[f"validation_error:{error[:80]}"] += 1
                        continue
                    structural = candidate["structural_candidate"]
                    validated = {
                        "candidate_id": candidate["candidate_id"],
                        "sample_index": candidate["sample_index"],
                        "source_line": candidate["source_line"],
                        "images": candidate["images"],
                        "original_code": candidate["original_code"],
                        "structural_candidate": structural,
                        "edit_candidate": structural,
                        "target_code": target_code,
                        "edit_record": structural,
                        "validation_report": validation_report,
                        "fallback_instruction": fallback_instruction(candidate),
                    }
                    validated_handle.write(json.dumps(validated, ensure_ascii=False) + "\n")
                    summary["validated_output_records"] += 1
                    instruction_record = {
                        "candidate_id": candidate["candidate_id"],
                        "instruction": validated["fallback_instruction"],
                        "instruction_meta": {
                            "generator": "structural_template",
                            "fallback_used": True,
                            "used_original_code": True,
                            "used_candidate": True,
                            "included_target_code": False,
                            "instruction_mode": "structural",
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
