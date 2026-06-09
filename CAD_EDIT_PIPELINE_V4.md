# CAD Edit Dataset Pipeline V4

V4 adds the first conservative structural replacement branch on top of:

- V1 parameter edits;
- V2 add-only structural edits;
- V3 high-confidence structural deletion.

The initial V4 scope is intentionally narrow:

- implemented: `replace_hole_with_slot`
- not implemented: arbitrary feature replacement, slot-to-hole replacement, pocket replacement, boss replacement, edited three-view generation

The training task remains:

```text
input:  original dimensioned three-view drawings + natural-language replace instruction
output: edited executable CadQuery code after replacing the target structure
```

`P1` is generated deterministically. The MLLM is only used after validation to write the natural-language replace instruction. It never generates target CadQuery code.

## Version Boundary

- V1: parameter-level numeric edits.
- V2: add-only structural edits through appended CSG blocks.
- V3: high-confidence `delete_hole` through source code block deletion.
- V4: high-confidence `replace_hole_with_slot` implemented as `delete + add`.

V4 does not rewrite V1/V2/V3. It adds a separate script:

```text
scripts/generate_cad_edit_replace_dataset.py
```

## Flow

```text
CADExpert-style JSONL
  |
  v
1. Extract P0 and images
  |
  v
2. Reuse V3 delete_hole candidate extraction
  |
  v
3. Delete the hole source block to produce P_deleted
  |
  v
4. Validate P0 -> P_deleted with V3 delete checks
  |
  v
5. Build a rectangular slot cutter near the deleted-hole changed region
  |
  v
6. Append an explicit CSG cut block to P_deleted to produce P_replace
  |
  v
7. Validate P_deleted -> P_replace and P0 -> P_replace
  |
  v
8. Generate instruction after validation
  |
  v
9. Emit final records
```

## Output Files

Default V4 outputs:

```text
outputs/cad_edit_v4_replace_candidates.jsonl
outputs/cad_edit_v4_validated_replace_edits.jsonl
outputs/cad_edit_v4_replace_instructions.jsonl
outputs/cad_edit_v4_replace.jsonl
```

## Candidate Schema

A V4 candidate is a structural replace record:

```json
{
  "candidate_id": "v4rep_000001_001",
  "images": ["./image/Circles/3000_1.png", "./image/Circles/3000_2.png", "./image/Circles/3000_3.png"],
  "original_code": "import cadquery as cq\nresult = ... .hole(12)",
  "intermediate_code": "import cadquery as cq\nresult = ...",
  "target_code": "import cadquery as cq\nresult = ...\n# V4 structural replacement: replace_hole_with_slot ...",
  "replace_candidate": {
    "candidate_type": "structural_replace",
    "edit_type": "replace_hole_with_slot",
    "old_feature": {
      "candidate_type": "structural_delete",
      "edit_type": "delete_hole",
      "source_api": "hole",
      "parameters": {
        "diameter": 12.0
      }
    },
    "new_feature": {
      "feature": "rectangular_slot",
      "replaces": "hole",
      "center": {"x": 0.0, "y": 0.0, "z": 0.0},
      "dims": {"x": 26.4, "y": 9.0, "z": 24.0},
      "human_dimensions": {
        "length": 26.4,
        "width": 9.0
      },
      "affected_region_bbox": {"xmin": -13.2, "xmax": 13.2, "ymin": -4.5, "ymax": 4.5, "zmin": -12.0, "zmax": 12.0}
    },
    "insertion_strategy": {
      "operation": "cut",
      "append_csg_block": true,
      "method": "delete_then_append_slot_cutter"
    },
    "instruction_hints": {
      "operation": "replace",
      "old_feature_name": "圆孔",
      "new_feature_name": "矩形槽",
      "diameter": 12.0,
      "length": 26.4,
      "width": 9.0
    }
  },
  "delete_validation_report": {"ok": true},
  "validation_report": {"ok": true, "mode": "cadquery_structural_replace"}
}
```

Unlike V2 add candidates, V4 candidates include `intermediate_code` and `target_code` because the replacement candidate is defined by the concrete delete+add transformation.

## Code Generation

V4 first removes the exact V3 delete span:

```python
intermediate_code = original_code[:block_span_start] + original_code[block_span_end:]
```

Then it appends a CSG slot cutter:

```python
# V4 structural replacement: replace_hole_with_slot (v4rep_000001_001)
v4_slot_cutter = cq.Workplane('XY').box(slot_x, slot_y, slot_z).translate((cx, cy, cz))
result = result.cut(v4_slot_cutter)
```

The first prototype only uses axis-aligned rectangular slot cutters. It skips batch hole deletion candidates and arbitrary hole contexts.

## Validation

V4 validation is two-stage plus a final locality check.

Delete stage, `P0 -> P_deleted`:

- `P0` executes.
- `P_deleted` executes.
- volume increases after removing the subtractive hole.
- bbox remains stable.
- changed region is local.

Slot stage, `P_deleted -> P_replace`:

- `P_replace` executes and is non-empty.
- volume decreases relative to `P_deleted`.
- changed region is local and near the deleted-hole changed region.
- bbox remains stable and does not collapse.

Final check, `P0 -> P_replace`:

- final geometry is valid and non-empty.
- final changed region is local.
- final shape has a real geometric change.

Failures are skipped by default.

## Instruction Generation

The shared instruction generator now supports:

- `parameter`
- `structural_add`
- `structural_delete`
- `structural_replace`

For `structural_replace`, the MLLM prompt receives:

- original three-view images;
- original CadQuery `P0`;
- replace candidate / edit record;
- validation summary.

It does not receive `target_code`.

Allowed wording includes:

- 替换
- 改成
- 换成
- 将圆孔替换为矩形槽

Forbidden wording includes:

- adding unrelated structures;
- deleting unrelated structures;
- moving, rotating, or copying;
- implementation details such as CadQuery, Workplane, source span, block span, CSG, or cutter.

## Commands

Generate candidates, validated edits, fallback instructions, and final records:

```powershell
conda run -n cadedit-v1 python scripts/generate_cad_edit_replace_dataset.py --input data.jsonl --output outputs/cad_edit_v4_replace.jsonl
```

Audit:

```powershell
conda run -n cadedit-v1 python scripts/verify_cad_edit_replace_candidates.py --input outputs/cad_edit_v4_replace_candidates.jsonl
conda run -n cadedit-v1 python scripts/verify_cad_edit_validated_replace_edits.py --input outputs/cad_edit_v4_validated_replace_edits.jsonl
conda run -n cadedit-v1 python scripts/verify_cad_edit_dataset.py --input outputs/cad_edit_v4_replace.jsonl
```

Generate MLLM instructions after validation:

```powershell
$env:DASHSCOPE_API_KEY = "<your Bailian/DashScope API key>"
conda run -n cadedit-v1 python scripts/generate_cad_edit_instructions.py --input outputs/cad_edit_v4_validated_replace_edits.jsonl --output outputs/cad_edit_v4_replace_instructions.jsonl --model qwen-vl-plus
```

Assemble final MLLM-instruction data:

```powershell
conda run -n cadedit-v1 python scripts/assemble_cad_edit_dataset.py --validated-input outputs/cad_edit_v4_validated_replace_edits.jsonl --instructions-input outputs/cad_edit_v4_replace_instructions.jsonl --output outputs/cad_edit_v4_replace.jsonl
```

Render before/after previews:

```powershell
conda run -n cadedit-v1 python scripts/render_cad_edit_pairs.py --input outputs/cad_edit_v4_replace.jsonl --output-dir outputs/cad_edit_v4_replace_renders
```

## Smoke Test

Synthetic smoke output:

```text
outputs/cad_edit_v4_replace_smoke.jsonl
outputs/cad_edit_v4_replace_smoke_renders/index.html
```

Validated result:

```text
records: 1
edit_type: replace_hole_with_slot
candidate audit errors: 0
validated audit errors: 0
final dataset errors: 0
unit tests: 26 OK
```

## Current Limitations

V4 is intentionally conservative:

- only single high-confidence `.hole(...)` source blocks are supported;
- batch holes are skipped;
- arrayed `pushPoints`, `rarray`, and `polarArray` hole edits are skipped through the reused V3 branch;
- slot orientation is axis-aligned;
- no arbitrary replacement or delete-slot/add-hole mode is implemented;
- no edited three-view image generation is implemented.
