$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python 3.10 or newer required.' }
if (-not $env:XAI_API_KEY) {
  $secure = Read-Host 'xAI API key (hidden; never saved to files)' -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try { $env:XAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}
python run_grok.py --out results/grok_full_responses.jsonl --cost-ceiling 5
if ($LASTEXITCODE -ne 0) { throw 'Full run stopped with an error; retain response and audit files for inspection.' }
python evaluate_llm.py score --manifest results/evaluation_manifest.jsonl --responses results/grok_full_responses.jsonl --out results/grok_full_score
if ($LASTEXITCODE -ne 0) { throw 'Scoring failed.' }
python verify_run.py --responses results/grok_full_responses.jsonl --score-dir results/grok_full_score
if ($LASTEXITCODE -ne 0) { throw 'Full run is incomplete or audit verification failed. Review results and resume the run.' }
Write-Host 'Full run verified. Preserve the entire results directory plus immutable copy and hashes.'
