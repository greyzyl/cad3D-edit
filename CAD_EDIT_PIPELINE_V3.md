# CAD Edit Dataset Pipeline V3

V3 is the conservative structural deletion branch. It builds training samples for:

```text
input:  original dimensioned three-view drawings + natural-language delete instruction
output: edited executable CadQuery code after deleting the target structure
```

The edited target code `P1` is generated only by deterministic source-code deletion from the original CadQuery program `P0`. The MLLM is used only after validation to write the natural-language instruction.

## Scope

Implemented delete edit types:

| Edit type | Source pattern | Code generation |
|---|---|---|
| `delete_hole` | high-confidence `.hole(...)` suffix or simple loop hole block | exact source-span deletion |
| `delete_circular_cutout` | `.cut(cq.Workplane(...).circle(...).extrude(...))` | exact `.cut(...)` span deletion |
| `delete_polygonal_cutout` | `.cut(cq.Workplane(...).polygon(...).extrude(...))` | exact `.cut(...)` span deletion |
| `delete_fillet` | high-confidence `.edges(...).fillet(r)` suffix | exact suffix deletion |
| `delete_chamfer` | high-confidence `.edges(...).chamfer(c)` suffix | exact suffix deletion |

Not implemented in V3:

- arbitrary geometry deletion;
- delete slot, pocket, boss, or pad;
- plug-based hole filling as the primary method;
- replace operations.

V4 replacement is documented separately in [CAD_EDIT_PIPELINE_V4.md](CAD_EDIT_PIPELINE_V4.md).

## Flow

```text
CADExpert-style JSONL
  |
  v
1. Extract images and original CadQuery P0
  |
  v
2. Locate high-confidence structural delete candidates
  |
  v
3. Delete the exact source span to produce P1
  |
  v
4. Execute P0 and P1 with CadQuery
  |
  v
5. Run delete-type-specific validation
  |
  v
6. Generate natural-language delete instruction after validation
  |
  v
7. Emit final records: images + instruction -> edited CadQuery
```

The script is:

```text
scripts/generate_cad_edit_delete_dataset.py
```

The script still defaults to `outputs/cad_edit_v2_delete*.jsonl` for backward compatibility. Prefer explicit V3 output names for new runs.

## Candidate Schema

Delete candidates describe the existing code block to remove, not a new primitive:

```json
{
  "candidate_id": "v2del_000001_001",
  "images": ["./image/Circles/3002_1.png", "./image/Circles/3002_2.png", "./image/Circles/3002_3.png"],
  "original_code": "import cadquery as cq\nresult = ...",
  "delete_candidate": {
    "candidate_type": "structural_delete",
    "edit_type": "delete_polygonal_cutout",
    "source_api": "cut_polygon",
    "block_span_start": 89,
    "block_span_end": 140,
    "block_text": ".cut(cq.Workplane(\"YZ\").polygon(6, 20).extrude(30))",
    "replacement": "",
    "parameters": {
      "sides": 6,
      "radius": 20.0,
      "depth": 30.0
    },
    "deletion_strategy": "polygonal_cutout_suffix",
    "expected_effect": {
      "volume": "increase",
      "bbox": "stable",
      "operation": "remove_subtractive_feature"
    },
    "instruction_hints": {
      "operation": "delete",
      "human_feature_name": "多边形通孔",
      "delete_verbs": ["删除", "移除", "去掉"],
      "preserve_other_geometry": true
    }
  }
}
```

Candidate rows intentionally describe the edit target. Validated rows add `target_code`, `validation_report`, and fallback instruction metadata.

## Supported Patterns

### Hole Suffix

```python
result = cq.Workplane("XY").box(80, 60, 20).faces(">Z").workplane().hole(12)
```

Deleted span:

```python
.faces(">Z").workplane().hole(12)
```

### Simple Loop Holes

```python
result = cq.Workplane("XY").circle(39).extrude(27).faces(">Z").workplane()
for i in range(3):
    result = result.rotate((0,0,0), (0, 0, 1), 120.0).moveTo(15, 0).hole(6)
```

V3 deletes the workplane suffix plus the loop body together, so `result` remains a solid instead of a workplane context.

### Circular And Polygonal Cutouts

```python
result = base.cut(cq.Workplane("XZ").circle(10).extrude(20))
result = base.cut(cq.Workplane("XZ").polygon(6, 10).extrude(20))
```

Only simple numeric `circle`, `polygon`, and `extrude` arguments are accepted. Unsupported or ambiguous `.cut(...)` blocks are skipped.

### Finishing Features

```python
result = cq.Workplane("XY").box(80, 60, 20).edges("|Z").fillet(4)
result = cq.Workplane("XY").box(80, 60, 20).edges("|Z").chamfer(4)
```

Only high-confidence chain suffixes are deleted. Fillet/chamfer blocks in complex middle-chain contexts are skipped.

## Code Generation

V3 uses exact span deletion:

```python
target_code = original_code[:block_span_start] + original_code[block_span_end:]
```

It does not reformat, refactor, or regenerate unrelated code.

## Validation

V3 has two validation policies.

Cutout-style deletion:

- applies to `delete_hole`, `delete_circular_cutout`, and `delete_polygonal_cutout`;
- requires `P0` and `P1` to execute;
- requires non-empty edited geometry;
- requires `volume_delta > 0`;
- requires bbox stability and no bbox collapse;
- requires changed region to be non-empty, local, and broadly consistent with volume delta.

Finishing-feature deletion:

- applies to `delete_fillet` and `delete_chamfer`;
- requires `P0` and `P1` to execute;
- requires non-empty edited geometry;
- requires bbox stability and no bbox collapse;
- requires non-trivial volume and geometry change;
- does not require a tiny local changed-region bbox, because edge finishing may affect many edges.

Failures are skipped by default.

## Instruction Generation

Instruction generation uses `structural_delete` mode.

Allowed expressions include:

- 删除
- 移除
- 去掉
- 填充
- 恢复为直角

Forbidden expressions include:

- 添加
- 新增
- 替换
- 移动
- 旋转
- 复制
- CadQuery / Workplane / source span / block span / CSG details

The MLLM prompt receives original three-view images, hidden original CadQuery `P0`, the delete candidate/edit record, and validation summary. It does not receive `target_code`.

## Commands

Generate V3 records with explicit V3 output names:

```powershell
conda run -n cadedit-v1 python scripts/generate_cad_edit_delete_dataset.py `
  --input data_expert3_fixed_paths.jsonl `
  --candidates-output outputs/cad_edit_v3_delete_candidates.jsonl `
  --validated-output outputs/cad_edit_v3_validated_delete_edits.jsonl `
  --instructions-output outputs/cad_edit_v3_delete_instructions.jsonl `
  --output outputs/cad_edit_v3_delete.jsonl `
  --max-deletes-per-sample 6
```

Run V3-only coverage audit:

```powershell
conda run -n cadedit-v1 python scripts/audit_cad_edit_coverage.py `
  --input data_expert3_fixed_paths.jsonl `
  --output-dir outputs/coverage_v3_delete_expanded `
  --branches v3_delete `
  --v3-max-deletes-per-sample 6 `
  --samples-per-edit-type 4
```

Generate MLLM instructions after validation:

```powershell
$env:DASHSCOPE_API_KEY = "<your Bailian/DashScope API key>"
conda run -n cadedit-v1 python scripts/generate_cad_edit_instructions.py `
  --input outputs/cad_edit_v3_validated_delete_edits.jsonl `
  --output outputs/cad_edit_v3_delete_instructions.jsonl `
  --model qwen-vl-plus
```

Render before/after previews:

```powershell
conda run -n cadedit-v1 python scripts/render_cad_edit_pairs.py `
  --input outputs/coverage_v3_delete_expanded/preview_samples.jsonl `
  --output-dir outputs/coverage_v3_delete_expanded/preview_gallery
```

## Current Full Audit

Latest full audit:

```text
input: data_expert3_fixed_paths.jsonl
records: 14,935
report: outputs/coverage_v3_delete_expanded/coverage_audit.json
preview: outputs/coverage_v3_delete_expanded/preview_gallery/index.html
```

Branch summary:

| Branch | Candidates | Validated | Pass rate | Failed |
|---|---:|---:|---:|---:|
| V3 delete | 9,302 | 7,049 | 75.78% | 2,253 |

By edit type:

| Edit type | Candidates | Validated | Pass rate |
|---|---:|---:|---:|
| `delete_chamfer` | 1,260 | 1,260 | 100.00% |
| `delete_circular_cutout` | 1,600 | 1,600 | 100.00% |
| `delete_fillet` | 2,396 | 1,213 | 50.63% |
| `delete_hole` | 2,839 | 1,769 | 62.31% |
| `delete_polygonal_cutout` | 1,207 | 1,207 | 100.00% |

By category:

| Category | Candidates | Validated | Pass rate |
|---|---:|---:|---:|
| Circles | 3,170 | 3,170 | 100.00% |
| Polygons | 3,659 | 1,406 | 38.43% |
| Rects | 2,473 | 2,473 | 100.00% |

Main rejection reasons:

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 5,455 |
| `skipped_unsupported_hole_context` | 2,850 |
| `validation:failed check: bbox_stable` | 2,115 |
| `validation:failed check: changed_region_not_global` | 121 |
| `skipped_syntax_error` | 96 |
| `skipped_geometry_error` | 82 |

The low pass rate for some polygon/fillet samples is intentional: V3 keeps bbox and geometry checks strict instead of increasing coverage with noisy deletions.

## Current Limitations

- No arbitrary feature-map reasoning.
- No delete slot / pocket / boss / pad.
- No `pushPoints`, `rarray`, or `polarArray` hole deletion.
- No plug-union hole filling as the main method.
- No replacement generation inside the V3 script.
- No edited three-view image generation.
