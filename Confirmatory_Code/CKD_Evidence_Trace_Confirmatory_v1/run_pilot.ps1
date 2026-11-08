$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {throw 'Install Python 3.10+ first'}
if (-not $env:XAI_API_KEY) {
 $secure=Read-Host 'xAI API key (hidden)' -AsSecureString
 $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
 try {$env:XAI_API_KEY=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}
 finally {[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}
}
python run_grok.py --prompts results/model_prompts.jsonl --manifest results/evaluation_manifest.jsonl --out results/confirmatory_pilot_responses.jsonl --patients 5 --cost-ceiling 2
if ($LASTEXITCODE -ne 0) {throw 'API pilot stopped. Existing persisted results are retained.'}
python confirmatory.py score --responses results/confirmatory_pilot_responses.jsonl --out results/confirmatory_pilot_score
if ($LASTEXITCODE -ne 0) {throw 'Scoring failed.'}
python verify_run.py --responses results/confirmatory_pilot_responses.jsonl --manifest results/evaluation_manifest.jsonl --prompts results/model_prompts.jsonl --score-dir results/confirmatory_pilot_score
if ($LASTEXITCODE -ne 0) {throw 'Audit verification failed.'}
Write-Host 'Pilot passed integrity verification. Review scoring before full run.'
