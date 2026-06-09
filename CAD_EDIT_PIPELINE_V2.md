# CAD Edit Dataset Pipeline V2

V2 adds deterministic structural CAD edits on top of the existing V1 parameter-edit pipeline. V1 remains unchanged. V2 focuses on add-only local structures in the first prototype:

- `add_through_hole`
- `add_blind_hole`
- `add_rectangular_slot`
- `add_pocket`

The current deletion branch adds a conservative high-confidence first delete atom:

- `delete_hole`

The training task is still:

```text
input:  original dimensioned three-view drawings + natural-language edit instruction
output: edited executable CadQuery code
```

`P1` is generated from `P0` by deterministic CadQuery CSG rules. The MLLM is only used after validation to generate the natural-language instruction.

## Flow

```text
data_t.jsonl
  |
  v
1. Extract P0, execute P0, collect bbox / volume / axis-aligned exterior faces
   -> outputs/cad_edit_v2_structural_candidates.jsonl
  |
  v
2. Append an explicit CSG edit block to P0 and validate P1
   -> outputs/cad_edit_v2_validated_structural_edits.jsonl
  |
  v
3. Generate instruction after validation
   -> outputs/cad_edit_v2_instructions.jsonl
  |
  v
4. Assemble final training records
   -> outputs/cad_edit_v2.jsonl
```

V2 candidates do not contain `target_code`. They describe the planned structural edit before `P1` is generated.

## Run

Generate candidates and validated edits:

```powershell
conda run -n cadedit-v1 python scripts/generate_cad_edit_structural_dataset.py --input data_t.jsonl --output outputs/cad_edit_v2.jsonl --no-final-output
```

Generate instructions without calling the MLLM:

```powershell
conda run -n cadedit-v1 python scripts/generate_cad_edit_instructions.py --input outputs/cad_edit_v2_validated_structural_edits.jsonl --output outputs/cad_edit_v2_instructions.jsonl --dry-run
```

Generate MLLM instructions:

```powershell
$env:DASHSCOPE_API_KEY = "<your Bailian/DashScope API key>"
conda run -n cadedit-v1 python scripts/generate_cad_edit_instructions.py --input outputs/cad_edit_v2_validated_structural_edits.jsonl --output outputs/cad_edit_v2_instructions.jsonl --model qwen-vl-plus
```

Assemble final V2 data:

```powershell
conda run -n cadedit-v1 python scripts/assemble_cad_edit_dataset.py --validated-input outputs/cad_edit_v2_validated_structural_edits.jsonl --instructions-input outputs/cad_edit_v2_instructions.jsonl --output outputs/cad_edit_v2.jsonl
```

Audit and render:

```powershell
conda run -n cadedit-v1 python scripts/verify_cad_edit_structural_candidates.py --input outputs/cad_edit_v2_structural_candidates.jsonl
conda run -n cadedit-v1 python scripts/verify_cad_edit_validated_structural_edits.py --input outputs/cad_edit_v2_validated_structural_edits.jsonl
conda run -n cadedit-v1 python scripts/verify_cad_edit_dataset.py --input outputs/cad_edit_v2.jsonl
conda run -n cadedit-v1 python scripts/render_cad_edit_pairs.py --input outputs/cad_edit_v2.jsonl --output-dir outputs/cad_edit_v2_renders
```

Open:

```text
outputs/cad_edit_v2_renders/index.html
```

## Candidate Record

Each V2 candidate includes:

```json
{
  "candidate_id": "v2_000001_001",
  "images": ["./image/Circles/3000_1.png", "./image/Circles/3000_2.png", "./image/Circles/3000_3.png"],
  "original_code": "import cadquery as cq\nresult = ...",
  "original_geometry": {
    "volume": 651395.3464,
    "bbox": {"xmin": -88.0, "xmax": 88.0, "ymin": -32.0, "ymax": 0.0, "zmin": -88.0, "zmax": 88.0},
    "dims": {"x": 176.0, "y": 32.0, "z": 176.0}
  },
  "structural_candidate": {
    "edit_type": "add_through_hole",
    "target_region": {"region_type": "axis_aligned_exterior_face", "axis": "y", "side": "+"},
    "primitive": {"kind": "cylinder", "radius": 10.56, "depth": 60.16, "axis": "y"},
    "insertion_strategy": {"operation": "cut", "append_csg_block": true},
    "affected_region_bbox": {"xmin": 46.64, "xmax": 67.76, "ymin": -46.08, "ymax": 14.08, "zmin": -10.56, "zmax": 10.56},
    "instruction_template": "在零件主平面上添加一个贯穿圆孔。",
    "instruction_hints": {
      "human_feature_name": "贯穿圆孔",
      "diameter": 21.12,
      "radius": 10.56,
      "through": true,
      "do_not_mention_depth": true
    }
  }
}
```

`instruction_hints` is the preferred MLLM-facing edit summary. It separates human-visible feature dimensions from CSG implementation details such as cutter depth, workplane origin, and extrusion margin.

## Code Generation

V2 does not insert edits into the middle of the original CadQuery chain. It appends a CSG block at the end:

```python
# V2 structural edit: add_through_hole (v2_000001_001)
v2_cutter = cq.Workplane("XZ", origin=(57.2, 14.08, 0.0)).circle(10.56).extrude(60.16)
result = result.cut(v2_cutter)
```

Subtractive edits use `result.cut(v2_cutter)`. Future additive edits such as boss / pad should use `result.union(primitive)`.

## Validation

The structural validator requires:

- `P0` executes and yields non-empty geometry.
- `P1` executes and yields non-empty geometry.
- subtractive edits reduce volume.
- bbox does not collapse or grow unexpectedly.
- changed-region bbox is inside the candidate `affected_region_bbox` after a small tolerance expansion.
- volume removed by CSG roughly matches the reported volume delta.

Failed edits are skipped by default.

## Instruction Generation

The shared instruction generator now detects `instruction_mode`:

- V1 parameter edits require old/new values and forbid新增、删除、移动、替换等 complex operation words.
- V2 structural edits allow expressions like添加孔、开槽、添加凹陷, but still reject unsupported delete / move / rotate / replace wording in this add-only prototype.

The MLLM prompt receives:

- original three-view images;
- original CadQuery `P0`;
- structural candidate;
- `instruction_hints` for human-facing feature wording;
- validation summary.

It does not receive `target_code`.

## Current Smoke Result

On `data_t.jsonl`, the V2 prototype currently produces 4 validated records:

- `add_through_hole`: 1
- `add_blind_hole`: 1
- `add_rectangular_slot`: 1
- `add_pocket`: 1

Preview output:

```text
outputs/cad_edit_v2_renders/index.html
```

## Scope

Not implemented yet:

- delete slot / pocket / boss;
- replace hole with slot;
- feature-level recovery from arbitrary original CadQuery chains;
- boss / pad union edits.

Deletion and replacement should only be added after the pipeline can reliably identify independent `.hole()`, `.cut()`, or feature blocks.

## Delete Hole Branch

The first deletion prototype is separate from the add-only generator and only handles high-confidence CadQuery `.hole(...)` blocks.

Supported pattern:

```python
result = cq.Workplane("XY").box(80, 60, 20).faces(">Z").workplane().hole(10)
```

The delete candidate removes the whole feature block:

```text
.faces(">Z").workplane().hole(10)
```

Result:

```python
result = cq.Workplane("XY").box(80, 60, 20)
```

Skipped for now:

- `.pushPoints(...).hole(...)`
- arrayed holes
- nested helper functions
- non-numeric hole diameter
- cases where deleting the block makes the code invalid or fails CadQuery validation

Delete outputs:

```text
outputs/cad_edit_v2_delete_candidates.jsonl
outputs/cad_edit_v2_validated_delete_edits.jsonl
outputs/cad_edit_v2_delete_instructions.jsonl
outputs/cad_edit_v2_delete.jsonl
```

Run:

```powershell
conda run -n cadedit-v1 python scripts/generate_cad_edit_delete_dataset.py --input data_t.jsonl --output outputs/cad_edit_v2_delete.jsonl
```

Audit:

```powershell
conda run -n cadedit-v1 python scripts/verify_cad_edit_delete_candidates.py --input outputs/cad_edit_v2_delete_candidates.jsonl
conda run -n cadedit-v1 python scripts/verify_cad_edit_validated_delete_edits.py --input outputs/cad_edit_v2_validated_delete_edits.jsonl
conda run -n cadedit-v1 python scripts/verify_cad_edit_dataset.py --input outputs/cad_edit_v2_delete.jsonl
```

MLLM instruction generation reuses the shared instruction script:

```powershell
conda run -n cadedit-v1 python scripts/generate_cad_edit_instructions.py --input outputs/cad_edit_v2_validated_delete_edits.jsonl --output outputs/cad_edit_v2_delete_instructions.jsonl --model qwen-vl-plus
conda run -n cadedit-v1 python scripts/assemble_cad_edit_dataset.py --validated-input outputs/cad_edit_v2_validated_delete_edits.jsonl --instructions-input outputs/cad_edit_v2_delete_instructions.jsonl --output outputs/cad_edit_v2_delete.jsonl
```

Delete validation checks:

- `P0` executes and yields non-empty geometry.
- `P1` executes and yields non-empty geometry.
- volume increases after deleting a subtractive hole.
- bbox remains stable.
- `edited_shape.cut(original_shape)` is non-empty.
- changed-region bbox is not global.
- changed-region volume roughly matches `volume_delta`.
