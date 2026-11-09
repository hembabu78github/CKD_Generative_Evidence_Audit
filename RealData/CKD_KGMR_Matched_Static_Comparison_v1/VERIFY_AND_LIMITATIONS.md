# Verification and interpretation — KG/MR matched static comparison

## Completed execution

- Original Chapter 4 RC1 archive used without editing: source ZIP SHA-256 is recorded in `results/study_report.json`.
- Twelve frozen fixture-derived CandidateMR specifications were loaded.
- Twelve original generated Python modules were found and their hashes were compared with the frozen release manifest.
- Release manifest contains eight execution `PROCEED` gates and four `ABSTAIN` gates; these were **read from the manifest**, not newly established by a live clinical target run.
- 117 single-field defect mutations across 10 categories were generated, plus 12 unchanged controls (129 evaluated specifications).
- The original `compiler/candidate_validation.py` from the RC1 archive was executed, not reconstructed.
- A separately coded conventional reference received the same semantic requirements as the frozen validator; its rejection decisions agreed on all 129 inputs.
- A thin conventional operator-only template had no provenance, condition, exception or review-status checks.
- The original RC1 unit suite was independently rerun: **291 tests, all passed**.

## Results

| Static validation variant | Invalid variants rejected | Clean candidates incorrectly rejected |
|---|---:|---:|
| Frozen RC1 candidate validator | 117/117 | 0/12 |
| Requirement-matched conventional validator | 117/117 | 0/12 |
| Thin operator-only template (ablation) | 12/117 | 0/12 |

**Interpretation:** Requirement completeness, not choice of implementation, explains the gap to the thin baseline. When requirements are matched, there is no detected advantage in this deliberately bounded static experiment.

## Why it does not establish research novelty

1. Both strict validators use exactly the same candidate JSON, so upstream knowledge representation, graph traversal, SHACL constraints, compiler provenance construction and candidate-selection quality were not independently compared.
2. The defects are deliberately injected into known schema/semantic fields. The detector and mutations refer to overlapping requirements, causing a favorable built-in test distribution.
3. There is no independent expert assessment of source clinical knowledge, no actual EHR CDS decision validity, no measured labor savings, and no independent external benchmark.
4. The fixture-derived MRs are labeled `UNREVIEWED` and four are control-blocked in the frozen release.
5. A fair upstream compilation benchmark requires *identical, expert-reviewed source propositions and acceptance contracts supplied to both competing generators* with blind checking of output correctness, candidate coverage, expert effort and provenance. This is a new evaluation stage, not something simulated by adding more patient records or model calls.

## Research decision

Freeze this result as **negative/equivalence exploratory evidence**. Do not use a 100% rejection rate to claim superiority, robustness of a clinical CDS, or higher accuracy for KG-derived compilation. The next high-value action is to obtain independently reviewed knowledge proposition source records/permissions and have a second implementation or blinded evaluator generate/check equivalent relations, rather than repeat the same mutations.
