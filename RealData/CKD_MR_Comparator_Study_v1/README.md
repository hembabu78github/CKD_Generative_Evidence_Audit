# CKD real-derived engineering comparison — v1.0

## Scope and scientific boundary

This runnable study compares an **actual Chapter 4 RC1 generated candidate** (`CMR-3fbe15eb0c59f7367ebdd879`, `PRESERVE_CLINICAL_STATE`) with two conventional deterministic validators on real MIMIC-IV Demo v2.2 creatinine trajectories and explicitly **synthetic software faults**.

The test target is a deliberately trivial **nonclinical parity-of-eligible-evidence-count software function**, not a CKD classifier, clinician decision policy, deployed CDS, or validated risk predictor. The generated CandidateMR is marked `UNREVIEWED` and is **fixture-backed**, not independently licensed from clinically reviewed CKD-TKG propositions.

**No incremental superiority over a fully equipped conventional validator is established.** An enhanced conventional comparator implementing both trace validation and the same decision-invariance contract detects the same injected faults as the union of the original MR and trace-only validator.

## Data

User-provided file `mimic-iv-clinical-database-demo-2.2.zip`. Not included in this package. This is the 100-patient deidentified sample. Serum creatinine is mapped to `itemid=50912`. `charttime` is observation time and `storetime` is used only as an **imperfect availability proxy**. Deidentified patient data are processed locally and never exported by this runner.

## Code provenance

The files below are copied without modification from the attached `Chapter4_Compiler_Release_Candidate_RC1(1).zip`:

- `vendor/runtime/executable_runtime.py`
- `vendor/generated/mr_cmr_3fbe15eb0c59f7367ebdd879.py`

Their SHA-256 hashes are in `PROVENANCE.json`. The generated module carries the original compiler-produced control and specification in code and is *actually executed* via its `transform` and `execute` methods.

## Windows reproduction

Extract this package to a folder and place `mimic-iv-clinical-database-demo-2.2.zip` in the same folder. With PowerShell open in the extracted package folder:

```powershell
py -m pip install pandas
py .\run_comparison.py --mimic-zip ".\mimic-iv-clinical-database-demo-2.2.zip" --out ".\results_reproduced"
```

Review `results_reproduced/comparison_report.json`, `aggregate_comparison.csv`, and `SHA256SUMS.txt`.

## Test scenarios per usable patient

- **Control:** no fault; unchanged auxiliary information should preserve toy decision and evidence IDs.
- **Auxiliary coupling:** the toy target incorrectly changes decision when a non-state auxiliary field changes; a generated MR detects the output violation.
- **Future evidence leak:** the target reports an actual MIMIC record from a later time than the decision reference; trace validator detects it.

The trace-only validator checks membership and cardinality. An enhanced conventional validator also checks output invariance. The independently defined ground truth is the known injected fault assignment, NOT clinical correctness.

## Executed findings

The MIMIC source yielded 3,003 valid creatinine rows and 98 evaluable trajectories with both eligible and future records at the chosen cut time (two skipped). There were 294 target-condition evaluations:

| Condition | N | Trace-only detects | Generated MR detects | Enhanced conventional detects |
|---|---:|---:|---:|---:|
| Control | 98 | 0 | 0 | 0 |
| Auxiliary coupling | 98 | 0 | 98 | 98 |
| Future evidence leak | 98 | 98 | 0 | 98 |

All injected faults are artificial and tailored to their respective checking contracts. Thus these numbers are **functional checks**, not a fair field-representative fault-detection benchmark.

## Blocked or unsupported MR coverage

This experiment executes only `PRESERVE_CLINICAL_STATE`. Although the compilation package contains 12 generated candidates (8 execution-admissible and 4 control-blocked), it is **not valid to count all 12 as real-record tests**. `DELAY_RESULT_ENTRY` is not scored here, as source-versus-delayed decisions may legitimately change when a laboratory result becomes unavailable. Other candidates require justified clinical or application semantics and independent policy validation.

## Next research tasks

1. Freeze a clinical/engineering target and all admissibility gates before selection of MR operators.
2. Add **fair** conventional comparators with the same specified contracts, not only deliberately limited checks.
3. Execute non-fixture CKD knowledge-source-to-MR provenance integration, including independently reviewed semantics.
4. Evaluate realistic mutants and blind faults with independent, prespecified adjudication; report failure-to-detect and false positives.
5. Obtain clinical review before claims about CKD decisions. No external LLM API is used for these real records.
