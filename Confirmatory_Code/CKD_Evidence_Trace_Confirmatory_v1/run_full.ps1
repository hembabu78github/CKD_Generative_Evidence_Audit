$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {throw 'Install Python 3.10+ first'}
if (-not $env:XAI_API_KEY) {
 $secure=Read-Host 'xAI API key (hidden)' -AsSecureString
 $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
 try {$env:XAI_API_KEY=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}
 finally {[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}
}
python run_grok.py --prompts results/model_prompts.jsonl --manifest results/evaluation_manifest.jsonl --out results/confirmatory_full_responses.jsonl --cost-ceiling 7
if ($LASTEXITCODE -ne 0) {throw 'API run stopped. Re-run identical command after resolving issue to resume safely.'}
python confirmatory.py score --responses results/confirmatory_full_responses.jsonl --out results/confirmatory_full_score
if ($LASTEXITCODE -ne 0) {throw 'Scoring failed.'}
python verify_run.py --responses results/confirmatory_full_responses.jsonl --manifest results/evaluation_manifest.jsonl --prompts results/model_prompts.jsonl --score-dir results/confirmatory_full_score
if ($LASTEXITCODE -ne 0) {throw 'Run incomplete or verification failed. Resume after reviewing files.'}
Write-Host 'Confirmatory experiment complete. Archive the entire results directory without modifying it.'
