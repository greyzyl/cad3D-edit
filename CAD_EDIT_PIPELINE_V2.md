# CAD Edit Dataset Pipeline V2

V2 is the structural add branch. It adds new local features to an existing CAD part while preserving the original V1 parameter-edit logic.

The target task remains:

```text
input:  original dimensioned three-view drawings + natural-language add instruction
output: edited executable CadQuery code
```

`target_code` is generated deterministically. MLLM is used only later, after validation, to write the English instruction.

## Scope

V2 is add-only. It does not delete or replace existing features.

Implemented edit types:

| edit_type | operation | implementation |
|---|---|---|
| `add_through_hole` | add circular through hole | append cutter + `result.cut(cutter)` |
| `add_blind_hole` | add blind hole | append finite-depth cutter + `result.cut(cutter)` |
| `add_rectangular_slot` | add rectangular slot | append box cutter + `result.cut(cutter)` |
| `add_pocket` | add rectangular recess | append shallow box cutter + `result.cut(cutter)` |

Stage 1 validated counts:

| edit_type | candidates | validated | pass rate |
|---|---:|---:|---:|
| `add_blind_hole` | 14,550 | 13,966 | 95.99% |
| `add_pocket` | 14,550 | 14,388 | 98.89% |
| `add_rectangular_slot` | 14,550 | 14,527 | 99.84% |
| `add_through_hole` | 14,550 | 14,010 | 96.29% |

Stage 1 validated total:

```text
v2_add: 58,200 candidates / 56,891 validated
```

Stage 1.5 capped subset keeps:

```text
v2_add: 12,000 selected records
```

## Candidate Representation

V2 candidates describe the structure to add before `target_code` is generated.

Required concepts:

- `candidate_type: structural_add`;
- `edit_type`;
- target feature primitive;
- target region or high-confidence face;
- insertion strategy;
- affected region estimate;
- instruction hints.

Example:

```json
{
  "candidate_type": "structural_add",
  "edit_type": "add_pocket",
  "primitive": {
    "feature_type": "rectangular_pocket",
    "length": 38.72,
    "width": 21.12,
    "depth": 14.08
  },
  "insertion_strategy": {
    "operation": "append_csg_cut"
  },
  "instruction_hints": {
    "human_feature_name": "rectangular pocket",
    "length": 38.72,
    "width": 21.12,
    "depth": 14.08
  }
}
```

## Deterministic Code Generation

V2 does not insert code into the middle of the original CadQuery chain. It appends an explicit CSG block after `original_code`.

Simplified pattern:

```python
# V2 structural edit: add_pocket
cutter = ...
result = result.cut(cutter)
```

This keeps edits auditable and avoids fragile chain surgery.

## Geometry Placement

V2 first executes `P0` and extracts geometric context:

- volume;
- bounding box;
- high-confidence exterior planes;
- safe margins.

Candidate placement prefers:

- large exterior faces;
- axis-aligned normals;
- sufficient margin from the boundary;
- feature size small enough to avoid global geometry damage.

Low-confidence placements are skipped.

## Validation

V2 validation requires:

- `P0` executes;
- `P1` executes;
- `P1` is non-empty and valid;
- volume direction is consistent with subtractive add features;
- bbox does not collapse or explode;
- changed region is local;
- non-target geometry is preserved as much as practical.

V2 rejects samples when the changed region is invalid or global.

## Stage 1 Output

Canonical Stage 1 output:

```text
outputs/stage1/v2_add_validated.jsonl
```

Records use the shared intermediate schema:

```json
{
  "branch": "v2_add",
  "edit_type": "add_rectangular_slot",
  "original_code": "...",
  "target_code": "...",
  "intermediate_code": null,
  "edit_record": {},
  "validation_report": {
    "ok": true
  }
}
```

## Stage 1.5 Selection

Current capped selected V2 distribution:

| edit_type | selected |
|---|---:|
| `add_blind_hole` | 3,000 |
| `add_pocket` | 3,000 |
| `add_rectangular_slot` | 3,000 |
| `add_through_hole` | 3,000 |

## Stage 2 Instruction Generation

V2 uses `structural_add` instruction mode.

MLLM instructions must:

- express adding, drilling, cutting a slot, or adding a recess;
- mention the new feature type;
- include key dimensions when available;
- say the rest of the part remains unchanged;
- avoid delete and replace semantics;
- avoid code terms such as CadQuery, Workplane, CSG, cutter, source span.

Example MLLM output:

```text
Add a rectangular pocket 38.72 mm long, 21.12 mm wide, and 14.08 mm deep on the front face of the part, keeping the rest of the part unchanged.
```

Current Stage 2 prompt uses:

- English-only output;
- Front, Top, Left image order;
- no `target_code`;
- no `intermediate_code`;
- no deterministic template reference when `--omit-template-reference` is passed.

## Recommended Stage 2 Command

```powershell
$env:DASHSCOPE_API_KEY="your_api_key"; python scripts\generate_stage2_instructions.py `
  --input-dir outputs\stage1_5\v1_10k_v2_12k `
  --output-dir outputs\stage2\v1_10k_v2_12k `
  --model qwen3-vl-plus `
  --image-root . `
  --cache-dir outputs\stage2\cache `
  --omit-template-reference `
  --timeout-seconds 60 `
  --retries 0 `
  --workers 4
```

## Legacy Single-Branch Script

For V2-only smoke tests:

```powershell
conda run -n cadedit-v1 python scripts\generate_cad_edit_structural_dataset.py `
  --input data_t.jsonl `
  --output outputs\cad_edit_v2.jsonl
```

For current dataset generation, prefer the Stage 1 / Stage 1.5 / Stage 2 pipeline.

## Limitations

- No structural deletion in V2.
- No replacement in V2.
- No arbitrary feature placement.
- No edited three-view drawing generation.
- Boss/pad additions are not part of the current validated production subset.
