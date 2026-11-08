# CKD Evidence Trace Confirmatory Experiment — v1.0

**Publication-venue neutral.** This package runs a NEW 300-prompt experiment using Grok `grok-4.7` and exactly the same 100 synthetic CKD cases as the exploratory experiment, but with a **prespecified, unambiguous two-level evidence trace contract**.

## Scientific question

Does explicit specification of (A) all eligible evidence IDs and (B) the first/last decision-determining IDs resolve the citation-completeness ambiguity observed in the prior exploratory experiment?

This is a **same-cases confirmatory prompt-contract test**; it is **not an independent held-out clinical evaluation**. The 20% decline threshold and MONITOR/REVIEW labels are synthetic software fixtures, not KDIGO care guidelines. No causal treatment effect is estimated.

## Prespecified primary metrics

1. Exact action match (REVIEW/MONITOR/ABSTAIN).
2. Exact ordered `all_eligible_ids` match, including every eligible observation.
3. Exact ordered `decision_basis_ids` match, containing the first and last eligible ID, or [] on abstention.

Secondary metrics: unknown/unavailable evidence citations, missed eligible IDs, extra noneligible IDs, and ordering-only mismatches. All missing cases remain explicit. **Do not edit the prompts, answer keys or scoring rules after running the model.** Rationale and uncertainty text require separate qualitative review; these scripts cannot validate the truth of prose.

## Run on Windows

1. Install Python 3.10+ (no third-party Python packages required for this slim runner).
2. Unzip this package to a new directory, separate from the original study.
3. Obtain your own xAI API key at https://console.x.ai/ . Never share the key or include it in uploaded results.
4. In PowerShell in the extracted directory run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_pilot.ps1
```

5. Inspect the pilot score and logs, then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_full.ps1
```

The script uses hidden key entry. It keeps all partial successful responses, retries transient HTTP 429 and server errors, and resumes from saved response records. Do not rename, delete or edit `.jsonl`, `.audit.jsonl` or `.metadata.json` files while resuming. Responses that reached the API but were not saved may be charged again after a retry.

## Evidence preservation

Keep an **unaltered copy of the entire results folder** after the run, including original prompts/manifest, raw responses, per-request provider response IDs, token usage, cost estimates, timestamps, audit JSONL hash chain, verification JSON and case-level scorer CSV. Save API provider usage screenshots/invoices separately if independently corroborating execution time is important. Local hashes and timestamps are **integrity/self-consistency aids, not notarized proof**.

For reruns, use a new output prefix or directory. Do not mix responses between model versions, prompt versions, or reasoning settings. Keep provider-side costs separate from estimates. Report the base synthetic case reuse explicitly when publishing.

## Scope of interpretation

No patient data, no validated clinical CDS, no clinical treatment recommendation, no calibration or counterfactual treatment effects. Perfect test scores could reflect explicit deterministic instructions in prompts and do not by themselves prove clinical correctness. Clinical/domain review and independent unseen cases remain future necessities.

## Reproducibility

`experiment_plan.json`, `frozen_baseline_hashes.json`, `model_prompts.jsonl` and `evaluation_manifest.jsonl` are created before any API calls. The model sees only `model_prompts.jsonl` (which contains no expected answers); the scorer uses the separately saved manifest. The names contain no journal or conference references.
