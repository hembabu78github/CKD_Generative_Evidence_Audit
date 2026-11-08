$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python 3.10 or newer required.' }
if (-not $env:XAI_API_KEY) {
  $secure = Read-Host 'xAI API key (hidden; never saved to files)' -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try { $env:XAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}
python run_grok.py --patients 5 --out results/grok_pilot_responses.jsonl --cost-ceiling 1
if ($LASTEXITCODE -ne 0) { throw 'Pilot run stopped with an error; retain response and audit files for inspection.' }
python evaluate_llm.py score --manifest results/evaluation_manifest.jsonl --responses results/grok_pilot_responses.jsonl --out results/grok_pilot_score
if ($LASTEXITCODE -ne 0) { throw 'Scoring failed.' }
python verify_run.py --responses results/grok_pilot_responses.jsonl --score-dir results/grok_pilot_score
if ($LASTEXITCODE -ne 0) { throw 'Evidence check failed or the selected pilot is incomplete.' }
Write-Host 'Pilot finished. Upload response, metadata, audit, verification and scoring report files (never your API key).'
