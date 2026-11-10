# CKD synthetic evidence-grounding evaluation — reproducible Grok 4.7 package

**Venue-neutral research package v*.*.** This project can support peer review, code review, independent replication, or a conference/journal supplementary release, subject to venue policies and scientific novelty requirements. No publication venue is named in source code, package paths, or results.

## Research scope and important limits

- Dataset: **100 synthetic patients × 3 evidence-availability conditions = 300 prompts**. This evaluates an *arbitrary software-policy fixture* for as-of result availability, not a medical treatment guideline.
- API: xAI Responses API; configured model `grok-4.7`. No clinical images, real patient records or patient care are involved.
- Original compiler/evidence experiment sources have been included for traceability; scientific code and previously collected data are not independently validated by this packaging work.
- Relevant prior/publication submissions and overlapping datasets or software must be disclosed by the researchers as required by the chosen venue; changing the package name does not create scientific novelty.
- Third-party datasets are not included and give their download links, and describe the response files as saved outputs of the real runs

## On Windows: quick start

1. Extract this ZIP to a directory without spaces if possible, e.g. `C:\Research\CKD_Evidence_Audit`.
2. Install **Python 3.10+** and confirm `python --version` in PowerShell.
3. Get an xAI API key via https://console.x.ai/ and configure API billing/credits; no API key is bundled.
4. In File Explorer, open the extracted folder containing `run_pilot.ps1`; enter `powershell` into the address bar to launch a shell there.
5. Execute the 5-patient pilot (15 prompts):

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\run_pilot.ps1
   ```

   If no `XAI_API_KEY` environment variable is set, the script requests it with hidden input. **Never send the key, paste it into a document, or add it to a ZIP**.

6. Inspect `results/grok_pilot_responses.verification.json` and `results/grok_pilot_score/score_summary.json`; expect `complete=true`, `stored_responses=15`, and `verification_pass=true` for a complete successful pilot.
7. Execute the full 100-patient run (300 prompts):

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\run_full.ps1
   ```

8. Check `results/grok_full_responses.verification.json`: `complete=true`, `verification_pass=true`, `stored_responses=300`; then analyze `results/grok_full_score/score_summary.json`. A pass of these checks **does not** imply good scientific performance.

If the call fails or the soft cost ceiling is reached, rerun the same script: completed cases resume. Keep the `*.audit.jsonl` and `*.metadata.json` files untouched. For a separate run/replicate choose a *new output filename*, not the same file. The three conditions are not independent patient samples, so compute condition-level and paired-patient comparisons appropriately.

## Execution evidence generated for each run

| File | Evidence |
|---|---|
| `results/grok_full_responses.jsonl` | Per-case raw model response text, returned model name, response ID, status, exact returned token usage, completion UTC timestamp, elapsed time, SHA-256 response hash, session ID |
| `results/grok_full_responses.metadata.json` | Frozen selected case IDs, configured model, prompt/manifest SHA-256, reasoning/output settings, price assumptions and run creation UTC time |
| `results/grok_full_responses.audit.jsonl` | Append-only local event log: session starts/ends, attempted API calls, retries/errors, success IDs and usage, saved responses, cumulative soft-cost stop; each entry links to previous entry by SHA-256 |
| `results/grok_full_responses.verification.json` | Automated verification of hash chain, response hashes, unique case IDs, prompt hashes, selected case coverage, response IDs, event matching, completion and scored count |
| `results/grok_full_score/case_scores.csv` | Scored row per completed case including schema, decision, evidence-trace matching, unavailable/missing/acute evidence flags |
| `results/grok_full_score/score_summary.json` | Aggregated counts and metrics; scores are synthetically defined, not clinical validation |
| `PACKAGE_FILES_SHA256.json` | Checksums for the originally distributed program files and inputs, allowing a verifier to compare a released package with a retained original |

### Audit authenticity and limitations

A local UTC timestamp alone is **not a trusted timestamp**; hash chains are **tamper-evident only when a trustworthy original head or copy is held independently**. The API response ID, provider usage dashboard and provider invoice can provide further external corroboration; these are not captured automatically or attested by xAI. Keep an untouched read-only copy of the final ZIP, audit files, raw responses and an externally saved SHA-256 checksum (for example a release in a research repository with release date/DOI). Independent reruns should compare environment, model version and outputs, not expect exact response text from a nondeterministic LLM.

Never share credentials or billing/payment details as evidence. Review any output for incidental sensitive information before public repository deposit. Synthetic input does not guarantee free-text model responses are appropriate for public release without review.

### Common failure scenarios addressed

- Interrupted runs: completed rows are flushed and `fsync`-ed; rerun to resume; the verifier reports partial coverage.
- Rate limit and transient network faults: up to three attempts logged, with an explicit warning that an unconfirmed API attempt may still be billed.
- Authentication and invalid-model responses: fail with actionable status, not silently treated as negative examples.
- Malformed JSON, blank response or incomplete generation: saved verbatim and scored as invalid; never filtered out.
- Dataset/prompt drift: SHA-256 comparisons to metadata stop an incompatible resumed run.
- Duplicate or unselected case IDs, missing API IDs, response tampering, broken event chain: detected by `verify_run.py`.
- Pilot vs full-run denominators: verification checks only selected cases; scorer's master-manifest `missing_responses` correctly includes intentionally unrun cases during a pilot.
- Model/provider/version drift: each response records provider-reported model; check for mixed versions manually before analysis.
- Cost: `--cost-ceiling` checks **after each successful response** and is not a hard spending cap. Actual billing may include retries or provider charges absent from successful-response usage; xAI billing is authoritative. Rate assumptions in this package ($2 input / $6 output per million tokens) can change.
- Scorer leakage: `model_prompts.jsonl` omits expected answers; `evaluation_manifest.jsonl` retains answer keys for scoring and is never included in request payloads.
- Clinical bias: the reference is a separately encoded toy policy, **not independent nephrologist validation**. The 15 previously observed frozen delay-MR disagreements are semantic-policy incompatibilities, not automatically CDS faults.
- Overlapping publications: independently verify novelty, distinguish new runs from pre-existing experiments, and disclose overlapping software/results when submitting.

## Commands for independent review

```powershell
python test_pipeline.py
python verify_run.py --responses results/grok_full_responses.jsonl --score-dir results/grok_full_score
python evaluate_llm.py score --manifest results/evaluation_manifest.jsonl --responses results/grok_full_responses.jsonl --out results/grok_full_score
```

For a new replicate, use a different output path and rerun scoring and verification for that output.

## Recommended evidence archive

After completing the full run, archive: the exact distributed code/input ZIP, the raw response JSONL, `*.metadata.json`, `*.audit.jsonl`, `*.verification.json`, scoring output directory and a copy of API usage/invoice summary with sensitive account and payment information redacted. Save the archive SHA-256 outside the archive. Document UTC start/end, provider/model, token totals, successful request count, retries, omissions and analysis exclusions in the methods/reproducibility section. When publishing, avoid representing local log timestamps as an independent time authority.
