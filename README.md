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
- [V3 structural delete edits](CAD_EDIT_PIPELINE_V3.md): conservative `delete_hole` code-block deletion for high-confidence `.hole(...)` features.
- [V4 structural replace edits](CAD_EDIT_PIPELINE_V4.md): conservative `replace_hole_with_slot` implemented as delete + appended slot CSG.

## Quick Start

```powershell
conda env create -f environment.yml
conda run -n cadedit-v1 python scripts/generate_cad_edit_dataset.py --input data_t.jsonl --output outputs/cad_edit_v1.jsonl --no-final-output
conda run -n cadedit-v1 python scripts/generate_cad_edit_structural_dataset.py --input data_t.jsonl --output outputs/cad_edit_v2.jsonl
conda run -n cadedit-v1 python scripts/generate_cad_edit_delete_dataset.py --input data.jsonl --output outputs/cad_edit_v2_delete.jsonl
conda run -n cadedit-v1 python scripts/generate_cad_edit_replace_dataset.py --input data.jsonl --output outputs/cad_edit_v4_replace.jsonl
```

For MLLM instruction generation, set the Bailian/DashScope API key in the shell before running the instruction stage:

```powershell
$env:DASHSCOPE_API_KEY = "<your api key>"
```

Do not commit API keys or full raw datasets.
