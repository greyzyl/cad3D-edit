#!/usr/bin/env python3
"""Generate V4 high-confidence structural replace CAD edit records."""

from __future__ import annotations

import argparse
import json
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


def replacement_slot_from_delete_report(candidate: dict[str, Any], delete_report: dict[str, Any]) -> dict[str, Any] | None:
    old_feature = candidate["delete_candidate"]
    parameters = old_feature.get("parameters", {})
    diameter = parameters.get("diameter")
    if not isinstance(diameter, (int, float)) or diameter <= 0:
        return None
    if parameters.get("count", 1) != 1:
        return None

    changed_bbox = delete_report.get("changed_region_bbox")
    if not isinstance(changed_bbox, dict):
        return None
    changed_dims = bbox_dims(changed_bbox)
    center = bbox_center(changed_bbox)
    normal_axis = max(AXES, key=lambda axis: changed_dims[axis])
    tangent_axes = [axis for axis in AXES if axis != normal_axis]

    # Keep the replacement local: longer than the old hole diameter, narrower than it,
    # and through the same local thickness as the removed hole plug.
    length = round_float(max(float(diameter) * 2.2, changed_dims[tangent_axes[0]] * 1.8))
    width = round_float(max(float(diameter) * 0.75, 1.0))
    margin = round_float(max(float(diameter) * 0.15, 1.0))
    depth = round_float(changed_dims[normal_axis] + 2 * margin)

    dims = {axis: width for axis in AXES}
    dims[tangent_axes[0]] = length
    dims[normal_axis] = depth
    dims = {axis: round_float(value) for axis, value in dims.items()}
    affected_bbox = bbox_from_center_dims(center, dims)
    return {
        "kind": "box",
        "feature": "rectangular_slot",
        "replaces": "hole",
        "normal_axis": normal_axis,
        "tangent_axes": tangent_axes,
        "center": {axis: round_float(center[axis]) for axis in AXES},
        "dims": dims,
        "human_dimensions": {
            "length": length,
            "width": width,
        },
        "affected_region_bbox": affected_bbox,
    }


def slot_csg_block(candidate_id: str, slot: dict[str, Any]) -> str:
    dims = slot["dims"]
    center = slot["center"]
    return "\n".join(
        [
            "",
            f"# V4 structural replacement: replace_hole_with_slot ({candidate_id})",
            "v4_slot_cutter = "
            f"cq.Workplane('XY').box({dims['x']}, {dims['y']}, {dims['z']})"
            f".translate({format_tuple(center)})",
            "result = result.cut(v4_slot_cutter)",
        ]
    )


def apply_replace_candidate(candidate: dict[str, Any]) -> str:
    return candidate["intermediate_code"].rstrip() + "\n" + slot_csg_block(candidate["candidate_id"], candidate["replace_candidate"]["new_feature"]) + "\n"


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
    replace_candidate = {
        "candidate_type": "structural_replace",
        "edit_type": "replace_hole_with_slot",
        "old_feature": old_feature,
        "new_feature": slot,
        "insertion_strategy": {
            "operation": "cut",
            "append_csg_block": True,
            "method": "delete_then_append_slot_cutter",
        },
        "instruction_template": (
            f"将直径为 {diameter} 的圆孔替换为长度 {human_dims['length']}、宽度 {human_dims['width']} 的矩形槽，其余结构保持不变。"
        ),
        "instruction_hints": {
            "operation": "replace",
            "old_feature_name": "圆孔",
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


def validate_replace_edit(candidate: dict[str, Any]) -> dict[str, Any]:
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


def fallback_instruction(candidate: dict[str, Any]) -> str:
    hints = candidate["replace_candidate"]["instruction_hints"]
    diameter = hints.get("diameter")
    length = hints.get("length")
    width = hints.get("width")
    if all(isinstance(value, (int, float)) for value in (diameter, length, width)):
        return f"将直径为 {diameter} 的圆孔替换为长度 {length}、宽度 {width} 的矩形槽，其余结构保持不变。"
    return "将零件上的圆孔替换为矩形槽，其余结构保持不变。"


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
    for index, delete_candidate in enumerate(delete_candidates, start=1):
        if len(replace_candidates) >= max_replacements_per_sample:
            break
        parameters = delete_candidate["delete_candidate"].get("parameters", {})
        if parameters.get("count", 1) != 1:
            stats["skipped_batch_hole"] += 1
            continue
        intermediate_code = apply_delete_candidate(delete_candidate)
        delete_report = validate_delete_edit(original_code, intermediate_code, delete_candidate)
        if not delete_report.get("ok"):
            stats["skipped_delete_validation_failed"] += 1
            continue
        slot = replacement_slot_from_delete_report(delete_candidate, delete_report)
        if slot is None:
            stats["skipped_slot_geometry"] += 1
            continue
        candidate_id = f"v4rep_{sample_index:06d}_{index:03d}"
        candidate = build_replace_candidate(
            candidate_id=candidate_id,
            source_record={"images": images},
            delete_candidate=delete_candidate,
            delete_report=delete_report,
            intermediate_code=intermediate_code,
            slot=slot,
        )
        replace_candidates.append(candidate)
        stats["candidate_records"] += 1

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
