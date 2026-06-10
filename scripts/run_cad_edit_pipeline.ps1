param(
    [string]$InputPath = "data_t.jsonl",
    [string]$OutputPath = "outputs/cad_edit_v1.jsonl",
    [string]$EnvName = "cadedit-v1",
    [switch]$UpdateEnv,
    [switch]$UseMllmInstructions,
    [switch]$DryRunInstructions,
    [string]$InstructionModel = "qwen3-vl-plus",
    [string]$ApiKeyEnv = "DASHSCOPE_API_KEY,BAILIAN_API_KEY,QWEN_API_KEY"
)

$ErrorActionPreference = "Stop"
$outputParent = Split-Path $OutputPath -Parent
if (-not $outputParent) {
    $outputParent = "."
}
$outputStem = [System.IO.Path]::GetFileNameWithoutExtension($OutputPath)
$outputExtension = [System.IO.Path]::GetExtension($OutputPath)
if (-not $outputExtension) {
    $outputExtension = ".jsonl"
}
$CandidatesPath = Join-Path $outputParent ($outputStem + "_candidates" + $outputExtension)
$ValidatedPath = Join-Path $outputParent ($outputStem + "_validated_edits" + $outputExtension)
$InstructionsPath = Join-Path $outputParent ($outputStem + "_instructions" + $outputExtension)

$envList = conda env list
$envExists = $false
foreach ($line in $envList) {
    if ($line -match "^\s*$([regex]::Escape($EnvName))\s+") {
        $envExists = $true
        break
    }
}

if ($UpdateEnv -or $envExists) {
    conda env update -n $EnvName -f environment.yml
} else {
    conda env create -f environment.yml
}

conda run -n $EnvName python -c "import cadquery as cq; print(cq.__version__)"
conda run -n $EnvName python -m unittest discover -s tests

if ($UseMllmInstructions -or $DryRunInstructions) {
    conda run -n $EnvName python scripts/generate_cad_edit_dataset.py --input $InputPath --output $OutputPath --no-final-output
} else {
    conda run -n $EnvName python scripts/generate_cad_edit_dataset.py --input $InputPath --output $OutputPath
}

conda run -n $EnvName python scripts/verify_cad_edit_candidates.py --input $CandidatesPath
conda run -n $EnvName python scripts/verify_cad_edit_validated_edits.py --input $ValidatedPath

if ($UseMllmInstructions -or $DryRunInstructions) {
    $instructionArgs = @(
        "scripts/generate_cad_edit_instructions.py",
        "--input", $ValidatedPath,
        "--output", $InstructionsPath,
        "--model", $InstructionModel,
        "--api-key-env", $ApiKeyEnv
    )
    if ($DryRunInstructions) {
        $instructionArgs += "--dry-run"
    }
    conda run -n $EnvName python @instructionArgs
    conda run -n $EnvName python scripts/verify_cad_edit_instructions.py --input $InstructionsPath
    conda run -n $EnvName python scripts/assemble_cad_edit_dataset.py --validated-input $ValidatedPath --instructions-input $InstructionsPath --output $OutputPath
}

conda run -n $EnvName python scripts/verify_cad_edit_dataset.py --input $OutputPath
