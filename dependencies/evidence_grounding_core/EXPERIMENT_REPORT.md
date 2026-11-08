# Experiment report — 5 November 2026

| Item | Result |
|---|---:|
| Eligible synthetic patients | 100 |
| As-of scenarios (source + frozen 3-day delay) | 200 |
| Prespecified faulty target implementations | 15 |
| Correct + faulty implementation evaluations | 3,200 |
| Correct-target agreement with separate engineering reference | 200/200 |
| Faulty implementations detected by action or evidence trace at least once | 12/15 |
| Frozen generated MR oracle TRUE on correct reference target | 85/100 |
| Frozen generated MR oracle FALSE on correct reference target | **15/100** |

**Interpretation:** The supplemental as-of decision and evidence-trace oracle exposed deliberately injected logic defects. The unchanged generated MR operator successfully delayed a selected result by exactly three days. However, the corresponding frozen relation produced 15 unexpected FALSE outcomes even for the reference-consistent target; hence the original relation is not yet validated for this target. The mutation score MUST NOT be represented as compiler-generated MR performance alone.

**Method:** deterministic MR-validation pilot subset, engineering review flag defined using a 20% relative change and minimum 3 observed nonacute values, as-of issue timestamps, 15 mutation implementations, no external data or LLM. No patients or intervention outcomes. No claim of causal inference, clinical usefulness, or broad generalizability.

**Files:** `results/summary.json`, `results/fault_summary.csv`, `results/case_results.csv`, `results/delay_relation_screen.csv`.
