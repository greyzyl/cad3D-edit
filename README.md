# CAD3D Edit Dataset Pipeline

Dataset pipeline for building CAD edit supervision from dimensioned three-view drawings and CadQuery programs.

The training task is:

```text
input:  original dimensioned three-view drawings + natural-language edit instruction
output: edited executable CadQuery code
```

The target code is generated deterministically from the original CadQuery code and edit candidates. A multimodal LLM is used only after CadQuery validation to write natural edit instructions.

Available branches:

- [V1 parameter edits](CAD_EDIT_PIPELINE_V1.md): single numeric edits for `.circle()`, `.hole()`, `.extrude()`, `.box()`, `.chamfer()`, and `.fillet()`.
- [V2 structural add edits](CAD_EDIT_PIPELINE_V2.md): add-only local structures such as through holes, blind holes, rectangular slots, and pockets.
- [V3 structural delete edits](CAD_EDIT_PIPELINE_V3.md): conservative source-span deletion for holes, circular/polygonal cutouts, fillets, and chamfers.
- [V4 structural replace edits](CAD_EDIT_PIPELINE_V4.md): conservative replacement through delete+add CSG or direct primitive replacement, including cutout, slot, chamfer, and fillet replacements.

## Quick Start

```powershell
conda env create -f environment.yml
conda run -n cadedit-v1 python scripts/generate_cad_edit_dataset.py --input data_t.jsonl --output outputs/cad_edit_v1.jsonl --no-final-output
conda run -n cadedit-v1 python scripts/generate_cad_edit_structural_dataset.py --input data_t.jsonl --output outputs/cad_edit_v2.jsonl
conda run -n cadedit-v1 python scripts/generate_cad_edit_delete_dataset.py --input data_expert3_fixed_paths.jsonl --output outputs/cad_edit_v3_delete.jsonl --max-deletes-per-sample 6
conda run -n cadedit-v1 python scripts/generate_cad_edit_replace_dataset.py --input data_expert3_fixed_paths.jsonl --output outputs/cad_edit_v4_replace.jsonl --max-replacements-per-sample 10
```

Current full-audit validated counts on `data_expert3_fixed_paths.jsonl`:

| Branch | Candidates | Validated | Pass rate |
|---|---:|---:|---:|
| V3 delete | 9,302 | 7,049 | 75.78% |
| V4 replace | 9,903 | 8,012 | 80.90% |

Audit reports:

- `outputs/coverage_v3_delete_expanded/coverage_audit.json`
- `outputs/coverage_v4_replace_expanded/coverage_audit.json`

For MLLM instruction generation, set the Bailian/DashScope API key in the shell before running the instruction stage:

```powershell
$env:DASHSCOPE_API_KEY = "<your api key>"
```

Stage 2 uses the Bailian OpenAI-compatible chat completions endpoint with `qwen3-vl-plus` by default and requests structured JSON output via `response_format=json_schema`. It sends the original three-view images, hidden original CadQuery code, sanitized edit record, and validation summary to the MLLM; it never sends `target_code` or `intermediate_code`.

```powershell
conda run -n cadedit-v1 python scripts/generate_stage2_instructions.py `
  --input-dir outputs/stage1_5/structural_balanced `
  --output-dir outputs/stage2/structural_balanced `
  --model qwen3-vl-plus `
  --response-format json_schema `
  --image-root . `
  --cache-dir outputs/stage2/cache `
  --seed 42
```

Use `--dry-run` to generate deterministic template fallback instructions without API calls.

Do not commit API keys or full raw datasets.
