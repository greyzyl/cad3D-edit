# CAD Edit Dataset Pipeline V1

本项目构建一个面向“基于工程图的 CAD 编辑”的 V1 数据集生成 pipeline。

目标学习任务是：

```text
输入：
  原始零件的带尺寸三视图 D0
  自然语言编辑指令 I

输出：
  编辑后的可执行 CadQuery 代码 P1
```

数据构造阶段可以使用原始 CadQuery 代码 `P0`，但 `P0` 只作为隐藏监督和构造依据，不能作为模型推理输入。`P1` 必须由确定性规则从 `P0` 和 edit candidate 生成，不能由大模型生成。

## 当前流程

V1 采用四阶段流程：

```text
data_t.jsonl
  |
  v
1. 抽取 P0，生成 edit candidates
   -> outputs/cad_edit_v1_candidates.jsonl
  |
  v
2. 确定性应用 candidate 得到 P1，并执行 CadQuery 验证
   -> outputs/cad_edit_v1_validated_edits.jsonl
  |
  v
3. 对验证通过的编辑调用百炼多模态模型生成自然语言 instruction
   -> outputs/cad_edit_v1_instructions.jsonl
  |
  v
4. 合并 validated_edits + instructions，生成最终训练数据
   -> outputs/cad_edit_v1.jsonl
```

MLLM instruction 阶段只接收：

- 原始三视图 `images`
- 原始 CadQuery 代码 `P0`
- `edit_candidate`
- 验证通过摘要

MLLM 默认不接收 `target_code` / `P1`，对应元数据为：

```json
{"included_target_code": false}
```

## V1 支持的编辑

当前只生成简单、高置信的单参数编辑：

- `.circle(radius)`
- `.hole(diameter)`
- `.cboreHole(...)` 的第一个直径类参数
- `.extrude(depth)`
- `.box(length, width, height)` 的单个维度
- `.chamfer(amount)`
- `.fillet(radius)`

默认编辑幅度是 `--scale-factor 1.5`，即把目标数值放大 50%，便于肉眼检查 before/after 差异。

## 环境

创建环境：

```powershell
conda env create -f environment.yml
```

如果环境已存在：

```powershell
conda env update -n cadedit-v1 -f environment.yml
```

验证 CadQuery：

```powershell
conda run -n cadedit-v1 python -c "import cadquery as cq; print(cq.__version__)"
```

## 一键运行

完整 MLLM 流程：

```powershell
$env:DASHSCOPE_API_KEY = "<your Bailian/DashScope API key>"
./scripts/run_cad_edit_pipeline.ps1 -UseMllmInstructions
```

不调用 API，只用 fallback 模板 instruction 验证链路：

```powershell
./scripts/run_cad_edit_pipeline.ps1 -DryRunInstructions
```

如果需要更新 conda 环境：

```powershell
./scripts/run_cad_edit_pipeline.ps1 -UpdateEnv
```

不要把 API key 写入代码、文档或 JSONL。只在 shell 环境变量中临时设置。

## 分阶段运行

阶段 1：生成 candidates 和 validated edits，不写最终训练数据：

```powershell
conda run -n cadedit-v1 python scripts/generate_cad_edit_dataset.py --input data_t.jsonl --output outputs/cad_edit_v1.jsonl --no-final-output
conda run -n cadedit-v1 python scripts/verify_cad_edit_candidates.py --input outputs/cad_edit_v1_candidates.jsonl
conda run -n cadedit-v1 python scripts/verify_cad_edit_validated_edits.py --input outputs/cad_edit_v1_validated_edits.jsonl
```

阶段 2：为验证通过的编辑生成 MLLM instruction：

```powershell
$env:DASHSCOPE_API_KEY = "<your Bailian/DashScope API key>"
conda run -n cadedit-v1 python scripts/generate_cad_edit_instructions.py --input outputs/cad_edit_v1_validated_edits.jsonl --output outputs/cad_edit_v1_instructions.jsonl --model qwen-vl-plus
conda run -n cadedit-v1 python scripts/verify_cad_edit_instructions.py --input outputs/cad_edit_v1_instructions.jsonl
```

阶段 3：组装最终训练数据：

```powershell
conda run -n cadedit-v1 python scripts/assemble_cad_edit_dataset.py --validated-input outputs/cad_edit_v1_validated_edits.jsonl --instructions-input outputs/cad_edit_v1_instructions.jsonl --output outputs/cad_edit_v1.jsonl
conda run -n cadedit-v1 python scripts/verify_cad_edit_dataset.py --input outputs/cad_edit_v1.jsonl
```

阶段 4：渲染 before/after 预览：

```powershell
conda run -n cadedit-v1 python scripts/render_cad_edit_pairs.py --input outputs/cad_edit_v1.jsonl --output-dir outputs/cad_edit_v1_renders
```

打开：

```text
outputs/cad_edit_v1_renders/index.html
```

## 产物说明

### `outputs/cad_edit_v1_candidates.jsonl`

P1 生成前的候选编辑中间产物。每条记录包含：

- `candidate_id`
- `sample_index`
- `source_line`
- `images`
- `original_code`
- `edit_candidate`

`edit_candidate` 包含精确源码定位：

```json
{
  "kind": "circle",
  "call": "circle",
  "arg_index": 0,
  "old": 88.0,
  "new": 132.0,
  "matched_text": "88",
  "span_start": 70,
  "span_end": 72,
  "replacement": "132",
  "scale_factor": 1.5
}
```

其中：

```python
original_code[span_start:span_end] == matched_text
target_code = original_code[:span_start] + replacement + original_code[span_end:]
```

candidate 文件故意不包含 `target_code` 和 `validation_report`，用于在生成 P1 前审查“准备改哪里”。

### `outputs/cad_edit_v1_validated_edits.jsonl`

CadQuery 验证通过后的编辑中间产物。每条记录包含：

- `candidate_id`
- `images`
- `original_code`
- `edit_candidate`
- `target_code`
- `edit_record`
- `validation_report`
- `fallback_instruction`

这个文件是 MLLM instruction 生成阶段的输入。脚本会读取 `target_code` 用于组装和追踪，但不会把它放进 MLLM prompt。

### `outputs/cad_edit_v1_instructions.jsonl`

MLLM 生成的自然语言指令文件，按 `candidate_id` 与 validated edits 对齐。每条记录包含：

- `candidate_id`
- `instruction`
- `instruction_meta`

`instruction_meta` 用于审计生成来源，例如：

```json
{
  "generator": "bailian_mllm",
  "model": "qwen-vl-plus",
  "used_images_count": 3,
  "used_original_code": true,
  "used_candidate": true,
  "included_target_code": false,
  "fallback_used": false
}
```

如果 API 调用失败或 instruction 质量校验不通过，会回退到 `fallback_instruction`，并记录 `fallback_used: true`。

### `outputs/cad_edit_v1.jsonl`

最终训练数据。每条记录形如：

```json
{
  "images": ["./image/Circles/3000_1.png", "./image/Circles/3000_2.png", "./image/Circles/3000_3.png"],
  "instruction": "将外圆的半径从88修改为132",
  "target_code": "import cadquery as cq\nresult = ...",
  "hidden": {
    "candidate_id": "000001_001",
    "original_code": "import cadquery as cq\nresult = ...",
    "edit_record": {
      "kind": "circle",
      "call": "circle",
      "arg_index": 0,
      "old": 88.0,
      "new": 132.0,
      "matched_text": "88"
    },
    "validation_report": {
      "ok": true,
      "mode": "cadquery"
    },
    "instruction_meta": {
      "generator": "bailian_mllm",
      "included_target_code": false
    }
  }
}
```

## 脚本职责

| 脚本 | 作用 |
| --- | --- |
| `scripts/generate_cad_edit_dataset.py` | 抽取 `P0`，生成 candidates，确定性生成 `P1`，执行 CadQuery 验证，输出 candidates / validated edits |
| `scripts/generate_cad_edit_instructions.py` | 调用百炼多模态模型，为 validated edits 生成自然语言 instruction |
| `scripts/assemble_cad_edit_dataset.py` | 合并 validated edits 和 instructions，输出最终训练 JSONL |
| `scripts/render_cad_edit_pairs.py` | 渲染 before/after SVG 和 STEP，并生成 HTML 对比页 |
| `scripts/verify_cad_edit_candidates.py` | 审计 candidate JSONL |
| `scripts/verify_cad_edit_validated_edits.py` | 审计 validated edits JSONL |
| `scripts/verify_cad_edit_instructions.py` | 审计 instruction JSONL |
| `scripts/verify_cad_edit_dataset.py` | 审计最终训练 JSONL |
| `scripts/run_cad_edit_pipeline.ps1` | PowerShell 一键运行入口 |

## 验证命令

运行全部单元测试：

```powershell
conda run -n cadedit-v1 python -m unittest discover -s tests
```

审计当前产物：

```powershell
conda run -n cadedit-v1 python scripts/verify_cad_edit_candidates.py --input outputs/cad_edit_v1_candidates.jsonl
conda run -n cadedit-v1 python scripts/verify_cad_edit_validated_edits.py --input outputs/cad_edit_v1_validated_edits.jsonl
conda run -n cadedit-v1 python scripts/verify_cad_edit_instructions.py --input outputs/cad_edit_v1_instructions.jsonl
conda run -n cadedit-v1 python scripts/verify_cad_edit_dataset.py --input outputs/cad_edit_v1.jsonl
```

## 当前测试数据状态

测试输入：

```text
data_t.jsonl
```

当前已生成：

- `outputs/cad_edit_v1_candidates.jsonl`
- `outputs/cad_edit_v1_validated_edits.jsonl`
- `outputs/cad_edit_v1_instructions.jsonl`
- `outputs/cad_edit_v1.jsonl`
- `outputs/cad_edit_v1_renders/index.html`

当前测试样本产生 3 条编辑：

- 外圆半径 `88 -> 132`
- 拉伸厚度 `32 -> 48`
- 内圆半径 `46 -> 69`

## 设计约束

- `P1` 只能由确定性代码替换生成。
- MLLM 只生成 instruction，不生成 `target_code`。
- MLLM 默认不接收 `target_code`，避免目标泄漏。
- 只有 CadQuery 验证通过的编辑才进入 MLLM instruction 阶段。
- 任何阶段失败都应该保留可审计信息，并支持 fallback instruction。
