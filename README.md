# CAD3D Edit Dataset Pipeline

V1 prototype for building CAD edit datasets from dimensioned three-view drawings and CadQuery programs.

The training task is:

```text
input:  original dimensioned three-view drawings + natural-language edit instruction
output: edited executable CadQuery code
```

The target code is generated deterministically from the original CadQuery code and edit candidates. A multimodal LLM is used only after CadQuery validation to write natural edit instructions.

See [CAD_EDIT_PIPELINE_V1.md](CAD_EDIT_PIPELINE_V1.md) for the full workflow, commands, intermediate JSONL formats, and validation steps.

## Quick Start

```powershell
conda env create -f environment.yml
conda run -n cadedit-v1 python scripts/generate_cad_edit_dataset.py --input data_t.jsonl --output outputs/cad_edit_v1.jsonl --no-final-output
```

For MLLM instruction generation, set the Bailian/DashScope API key in the shell before running the instruction stage:

```powershell
$env:DASHSCOPE_API_KEY = "<your api key>"
```

Do not commit API keys or full raw datasets.
