# CAD Edit Dataset Pipeline V1

V1 是 CAD 编辑数据构造系统中的参数级编辑分支。

最终训练任务保持不变：

```text
input:
  原始零件的带尺寸三视图
  自然语言编辑指令

output:
  编辑后的可执行 CadQuery 代码
```

V1 只修改原始 CadQuery 代码中的高置信数值参数。`target_code` 必须由 `original_code` 通过确定性 source-span replacement 生成，不允许由大模型生成。

## 范围

V1 支持简单单参数编辑：

| edit_type | 目标 API | 语义 |
|---|---|---|
| `parameter_circle` | `.circle(r)` | 修改圆半径 |
| `parameter_hole` | `.hole(d)` | 修改孔直径 |
| `parameter_extrude` | `.extrude(depth)` | 修改拉伸深度 |
| `parameter_box` | `.box(x, y, z)` | 修改 box 的单个尺寸 |
| `parameter_chamfer` | `.chamfer(c)` | 修改倒角尺寸 |
| `parameter_fillet` | `.fillet(r)` | 修改圆角半径 |

当前 Expert3 Stage 1 输出中实际覆盖：

| edit_type | candidates | validated | pass rate |
|---|---:|---:|---:|
| `parameter_chamfer` | 1,260 | 1,122 | 89.05% |
| `parameter_circle` | 6,547 | 6,402 | 97.79% |
| `parameter_extrude` | 15,971 | 15,971 | 100.00% |
| `parameter_fillet` | 2,396 | 2,171 | 90.61% |
| `parameter_hole` | 2,850 | 2,845 | 99.82% |

Stage 1 validated total:

```text
v1_parameter: 29,024 candidates / 28,511 validated
```

Stage 1.5 capped subset keeps:

```text
v1_parameter: 10,000 selected records
```

## Deterministic Code Generation

V1 uses Python AST and source spans to find high-confidence numeric arguments in CadQuery method calls.

For each candidate:

1. Parse `original_code`.
2. Locate a numeric literal argument in a supported CadQuery call.
3. Generate a deterministic new value using a stable scale factor.
4. Replace only the exact numeric literal span.
5. Keep all unrelated source text unchanged.

The edit is one output row per parameter change.

Example edit record:

```json
{
  "kind": "circle",
  "call": "circle",
  "arg_index": 0,
  "old": 39.0,
  "new": 58.5,
  "matched_text": "39"
}
```

## Validation

V1 validation requires:

- `original_code` parses and executes;
- `target_code` parses and executes;
- `result` exists after execution;
- generated geometry is non-empty and valid;
- source replacement only touches the selected numeric span;
- no unrelated code rewrite occurs.

Rejected samples stay out of Stage 1 validated outputs.

## Stage 1 Output

Canonical Stage 1 output:

```text
outputs/stage1/v1_parameter_validated.jsonl
```

Each record is normalized into the shared intermediate schema:

```json
{
  "sample_id": "...",
  "source_sample_id": "...",
  "images": ["front.png", "top.png", "left.png"],
  "branch": "v1_parameter",
  "edit_type": "parameter_circle",
  "original_code": "...",
  "target_code": "...",
  "intermediate_code": null,
  "edit_record": {},
  "validation_report": {
    "ok": true
  },
  "generation_meta": {
    "pipeline_stage": "stage1_deterministic_generation",
    "target_code_generated_by": "deterministic_rule",
    "instruction_generated": false,
    "mllm_used": false
  }
}
```

## Stage 1.5 Selection

Stage 1.5 performs source-level split and balancing. It prevents the same original three-view drawing from appearing in multiple splits.

Current capped dataset:

```text
outputs/stage1_5/v1_10k_v2_12k/
```

V1 selected distribution:

| edit_type | selected |
|---|---:|
| `parameter_chamfer` | 1,122 |
| `parameter_circle` | 2,236 |
| `parameter_extrude` | 2,236 |
| `parameter_fillet` | 2,171 |
| `parameter_hole` | 2,235 |

## Stage 2 Instruction Generation

Stage 2 generates English natural-language instructions only. It does not generate or modify `target_code`.

MLLM visible inputs:

- original three-view images, ordered as Front, Top, Left;
- hidden `original_code`, used only as construction context;
- sanitized `edit_record`.

MLLM never receives:

- `target_code`;
- `intermediate_code`;
- source spans, block spans, CSG implementation details.

V1 uses `parameter` instruction mode. Extra constraints:

- old and new values from `edit_record` must appear exactly;
- do not convert radius to diameter or diameter to radius;
- do not describe add/delete/replace/move/rotate/copy;
- instruction must say the rest of the part remains unchanged.

Example:

```text
Change the main circle radius from 39 to 58.5, keeping the rest of the part unchanged.
```

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

`--workers` controls concurrent MLLM calls. Start with `--workers 4`; increase only if the API does not rate-limit.

If MLLM output fails validation, deterministic fallback is used. The final JSONL records:

- `fallback_used`;
- `quality_reasons`;
- `fallback_reason_summary`;
- rejected MLLM instruction when available.

## Legacy Single-Branch Script

The older V1-only script is still useful for smoke tests:

```powershell
conda run -n cadedit-v1 python scripts\generate_cad_edit_dataset.py `
  --input data_t.jsonl `
  --output outputs\cad_edit_v1.jsonl
```

For current dataset generation, prefer the Stage 1 / Stage 1.5 / Stage 2 pipeline.

## Limitations

- V1 does not add, delete, move, or replace structures.
- V1 does not infer semantic intent from chain reasoning text in the source JSON.
- It relies on high-confidence numeric literals; symbolic expressions and complex helper functions are skipped.
