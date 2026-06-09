# CAD Edit Dataset Pipeline V4

V4 is the conservative structural replacement branch. It builds training samples for:

```text
input:  original dimensioned three-view drawings + natural-language replace instruction
output: edited executable CadQuery code after replacing the target structure
```

Target CadQuery `P1` is generated only by deterministic code editing or deterministic CSG composition. The MLLM is used only after validation to write the natural-language replacement instruction.

## Scope

Implemented replace edit types:

| Edit type | Strategy | Notes |
|---|---|---|
| `replace_circular_cutout_with_slot` | delete circular cutout + append slot cutter | reuses V3 circular cutout deletion |
| `replace_loop_holes_with_slots` | delete simple loop holes + append slot cutter | reuses V3 simple loop hole deletion |
| `replace_circular_cutout_with_polygonal_cutout` | direct source replacement | `.circle(r)` -> `.polygon(6, r)` inside the cut block |
| `replace_polygonal_cutout_with_circular_cutout` | direct source replacement | `.polygon(n, r)` -> conservative `.circle(r_in)` |
| `replace_polygonal_cutout_with_slot` | delete polygonal cutout + append slot cutter | conservative geometry placement; many unsafe cases skipped |
| `replace_chamfer_with_fillet` | direct source replacement | `.chamfer(c)` -> `.fillet(c)` |
| `replace_fillet_with_chamfer` | direct source replacement | `.fillet(r)` -> `.chamfer(r)` |

Not implemented:

- arbitrary feature replacement;
- slot-to-hole replacement;
- pocket/boss replacement;
- replace via low-confidence geometry inference;
- edited three-view image generation.

## Version Boundary

- V1: parameter-level numeric edits.
- V2: add-only structural edits through appended CSG blocks.
- V3: high-confidence structural deletion through source span deletion.
- V4: high-confidence structural replacement as `delete + add` or direct primitive source replacement.

V4 does not rewrite V1/V2/V3. It adds:

```text
scripts/generate_cad_edit_replace_dataset.py
```

## Flow

```text
CADExpert-style JSONL
  |
  v
1. Extract images and original CadQuery P0
  |
  v
2. Reuse V3 delete candidate extraction
  |
  v
3. Build one or more replace candidates from each compatible delete candidate
  |
  v
4. Generate P_replace deterministically
  |
  v
5. Execute P0, intermediate code if any, and P_replace
  |
  v
6. Run replacement-type-specific validation
  |
  v
7. Generate natural-language replace instruction after validation
  |
  v
8. Emit final records: images + instruction -> edited CadQuery
```

## Replacement Strategies

### Delete Then Append Slot Cutter

Used by:

- `replace_circular_cutout_with_slot`
- `replace_loop_holes_with_slots`
- `replace_polygonal_cutout_with_slot`

V4 first removes the old subtractive feature using the V3 delete span:

```python
intermediate_code = original_code[:block_span_start] + original_code[block_span_end:]
```

Then it appends a deterministic rectangular slot cutter:

```python
# V4 structural replacement: replace_circular_cutout_with_slot (v4rep_000001_001)
v4_slot_cutter = cq.Workplane('XY').box(slot_x, slot_y, slot_z).translate((cx, cy, cz))
result = result.cut(v4_slot_cutter)
```

Slot dimensions are derived from the old feature changed-region bbox and original bbox. If a safe local slot cannot be estimated, the candidate is skipped.

### Direct Cutout Primitive Replacement

Used by:

- `replace_circular_cutout_with_polygonal_cutout`
- `replace_polygonal_cutout_with_circular_cutout`

Examples:

```python
.cut(cq.Workplane("XZ").circle(10).extrude(20))
```

becomes:

```python
.cut(cq.Workplane("XZ").polygon(6, 10).extrude(20))
```

For polygon-to-circle replacement, V4 uses a conservative inscribed-circle radius:

```text
r_in = polygon_radius * cos(pi / sides)
```

This avoids replacing a polygonal cutout with an oversized circular cutout that would destroy the outer profile.

### Direct Finishing Replacement

Used by:

- `replace_chamfer_with_fillet`
- `replace_fillet_with_chamfer`

Examples:

```python
.edges("|Z").chamfer(4)
.edges("|Z").fillet(4)
```

become:

```python
.edges("|Z").fillet(4)
.edges("|Z").chamfer(4)
```

Only high-confidence chain suffixes are supported.

## Candidate Schema

A V4 candidate stores original, intermediate if applicable, target code, and the deterministic replacement record:

```json
{
  "candidate_id": "v4rep_000001_001",
  "images": ["./image/Circles/3000_1.png", "./image/Circles/3000_2.png", "./image/Circles/3000_3.png"],
  "original_code": "import cadquery as cq\nresult = ...",
  "intermediate_code": "import cadquery as cq\nresult = ...",
  "target_code": "import cadquery as cq\nresult = ...",
  "replace_candidate": {
    "candidate_type": "structural_replace",
    "edit_type": "replace_circular_cutout_with_polygonal_cutout",
    "old_feature": {
      "candidate_type": "structural_delete",
      "edit_type": "delete_circular_cutout",
      "source_api": "cut",
      "parameters": {
        "radius": 10.0,
        "diameter": 20.0,
        "depth": 30.0
      }
    },
    "new_feature": {
      "feature": "polygonal_cutout",
      "feature_type": "polygonal_cutout",
      "sides": 6,
      "radius": 10.0
    },
    "insertion_strategy": {
      "operation": "replace",
      "append_csg_block": false,
      "method": "direct_source_replacement"
    },
    "instruction_hints": {
      "operation": "replace",
      "old_feature_name": "圆形通孔",
      "new_feature_name": "六边形通孔",
      "radius": 10.0,
      "sides": 6
    }
  },
  "delete_validation_report": {"ok": true},
  "validation_report": {"ok": true, "mode": "cadquery_structural_replace"}
}
```

Validated rows add `fallback_instruction`; final rows expose only:

```text
images
instruction
target_code
hidden.original_code
hidden.intermediate_code
hidden.edit_record
hidden.validation_report
```

## Validation

V4 uses type-specific validators.

### Slot Replacement Validator

Applies to:

- `replace_circular_cutout_with_slot`
- `replace_loop_holes_with_slots`
- `replace_polygonal_cutout_with_slot`
- `replace_hole_with_slot` where present

Checks:

- delete stage is valid;
- `P0`, `P_deleted`, and `P_replace` execute;
- `P_replace` is non-empty;
- deleting the old subtractive feature increases volume;
- adding the slot decreases volume relative to `P_deleted`;
- bbox remains stable and does not collapse;
- slot changed region is local and near the old feature;
- final geometry differs from original and remains local.

### Cutout Replacement Validator

Applies to:

- `replace_circular_cutout_with_polygonal_cutout`
- `replace_polygonal_cutout_with_circular_cutout`

Checks:

- delete stage is valid;
- `P0`, `P_deleted`, and `P_replace` execute;
- `P_replace` is non-empty;
- bbox remains stable;
- new cutout creates non-empty geometry change;
- new changed region is local and near the old feature;
- final shape differs from original.

Final volume direction is not constrained, because replacement may increase or decrease material depending on old/new primitive area.

### Finishing Replacement Validator

Applies to:

- `replace_chamfer_with_fillet`
- `replace_fillet_with_chamfer`

Checks:

- `P0` and `P_replace` execute;
- `P_replace` is non-empty;
- bbox remains stable and does not collapse;
- volume changes non-trivially;
- geometry changes non-trivially.

No tiny local changed-region constraint is required because edge finishing may affect many edges.

## Instruction Generation

Instruction generation uses `structural_replace` mode.

Allowed expressions include:

- 替换
- 改成
- 换成
- 将 A 替换为 B

Examples:

```text
将零件上的圆形通孔替换为六边形通孔，其余结构保持不变。
将零件上的多边形通孔替换为圆形通孔，其余结构保持不变。
将零件上的多边形通孔替换为矩形槽，其余结构保持不变。
将零件边缘的倒角替换为圆角，其余结构保持不变。
将零件边缘的圆角替换为倒角，其余结构保持不变。
```

Forbidden expressions include:

- adding unrelated structures;
- deleting unrelated structures;
- moving, rotating, copying;
- CadQuery / Workplane / source span / block span / CSG / cutter implementation details.

The MLLM prompt receives original three-view images, hidden original CadQuery `P0`, replace candidate/edit record, and validation summary. It does not receive `target_code`.

## Commands

Generate V4 records:

```powershell
conda run -n cadedit-v1 python scripts/generate_cad_edit_replace_dataset.py `
  --input data_expert3_fixed_paths.jsonl `
  --output outputs/cad_edit_v4_replace.jsonl `
  --candidates-output outputs/cad_edit_v4_replace_candidates.jsonl `
  --validated-output outputs/cad_edit_v4_validated_replace_edits.jsonl `
  --instructions-output outputs/cad_edit_v4_replace_instructions.jsonl `
  --max-replacements-per-sample 10
```

Run V4-only coverage audit:

```powershell
conda run -n cadedit-v1 python scripts/audit_cad_edit_coverage.py `
  --input data_expert3_fixed_paths.jsonl `
  --output-dir outputs/coverage_v4_replace_expanded `
  --branches v4_replace `
  --v4-max-replacements-per-sample 10 `
  --samples-per-edit-type 4
```

Generate MLLM instructions after validation:

```powershell
$env:DASHSCOPE_API_KEY = "<your Bailian/DashScope API key>"
conda run -n cadedit-v1 python scripts/generate_cad_edit_instructions.py `
  --input outputs/cad_edit_v4_validated_replace_edits.jsonl `
  --output outputs/cad_edit_v4_replace_instructions.jsonl `
  --model qwen-vl-plus
```

Assemble final MLLM-instruction data:

```powershell
conda run -n cadedit-v1 python scripts/assemble_cad_edit_dataset.py `
  --validated-input outputs/cad_edit_v4_validated_replace_edits.jsonl `
  --instructions-input outputs/cad_edit_v4_replace_instructions.jsonl `
  --output outputs/cad_edit_v4_replace.jsonl
```

Render before/after previews:

```powershell
conda run -n cadedit-v1 python scripts/render_cad_edit_pairs.py `
  --input outputs/coverage_v4_replace_expanded/preview_samples.jsonl `
  --output-dir outputs/coverage_v4_replace_expanded/preview_gallery
```

## Current Full Audit

Latest full audit:

```text
input: data_expert3_fixed_paths.jsonl
records: 14,935
report: outputs/coverage_v4_replace_expanded/coverage_audit.json
preview: outputs/coverage_v4_replace_expanded/preview_gallery/index.html
```

Branch summary:

| Branch | Candidates | Validated | Pass rate | Failed |
|---|---:|---:|---:|---:|
| V4 replace | 9,903 | 8,012 | 80.90% | 1,891 |

By edit type:

| Edit type | Candidates | Validated | Pass rate |
|---|---:|---:|---:|
| `replace_chamfer_with_fillet` | 1,260 | 1,260 | 100.00% |
| `replace_circular_cutout_with_polygonal_cutout` | 1,600 | 1,600 | 100.00% |
| `replace_circular_cutout_with_slot` | 1,600 | 1,600 | 100.00% |
| `replace_fillet_with_chamfer` | 2,396 | 1,213 | 50.63% |
| `replace_loop_holes_with_slots` | 1,769 | 1,749 | 98.87% |
| `replace_polygonal_cutout_with_circular_cutout` | 1,207 | 519 | 43.00% |
| `replace_polygonal_cutout_with_slot` | 71 | 71 | 100.00% |

By category:

| Category | Candidates | Validated | Pass rate |
|---|---:|---:|---:|
| Circles | 4,770 | 4,770 | 100.00% |
| Polygons | 2,660 | 769 | 28.91% |
| Rects | 2,473 | 2,473 | 100.00% |

Main rejection reasons:

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 6,703 |
| `delete_skipped_no_delete_candidate` | 5,455 |
| `delete_skipped_unsupported_hole_context` | 2,850 |
| `validation:failed check: bbox_stable` | 1,140 |
| `skipped_slot_geometry` | 1,136 |
| `skipped_delete_validation_failed` | 1,070 |
| `validation:failed check: new_feature_changed_region_local` | 519 |
| `validation:Bnd_Box is void` | 169 |

The current V4 branch covers seven replacement types and reaches 8,012 validated records. It is below the 10,000-12,000 aspirational target but now has the same order of magnitude as V3 delete while preserving conservative validation.

## Current Limitations

- Polygon replacement remains intentionally strict; many polygon samples are rejected because the replacement would change global bbox or create non-local geometry changes.
- Slot replacement is axis-aligned.
- No arbitrary replacement planner.
- No replacement for pockets, bosses, pads, or arbitrary `.cut(...)` blocks.
- No edited three-view image generation.
