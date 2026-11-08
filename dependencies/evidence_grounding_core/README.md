# venue-neutral evidence-availability experiment v1.0 — exploratory synthetic prototype

**Status: executable engineering pilot, NOT submission-ready clinical validation.**

This builds on the supplied Chapter 4 compiler and Phase-2 synthetic CKD pilot data. The upstream generated MR source and Phase-2 observations are copied unchanged into `upstream/`. It introduces a separate *non-clinical engineering* CDS decision policy, an independently coded expected-behavior function, 15 prespecified deterministic faulty variants, a decision-time evidence trace, and automated local reproducibility tests.

## Reproduce

Python 3.11+ with pandas and numpy installed:

```bash
python run_experiment.py --patients 100 --output results_replay
python test_experiment.py
```

`results/` contains `case_results.csv`, `fault_summary.csv`, `delay_relation_screen.csv`, `fault_catalogue.json` and `summary.json`.

## Policy / independent expected behavior

All as-of decisions use only observations issued on or before the decision timestamp; exclude missing eGFR values and acute-like observations; sort by effective time; require at least three observations; compare the first with the most recent eGFR. A **simulated engineering review flag** is returned if relative decline is at least 20%, otherwise MONITOR. Insufficient evidence leads to ABSTAIN. **This threshold is an experimental engineering definition, not a KDIGO recommendation, validated clinical decision rule or treatment recommendation.** The reference is separately implemented from the fault-injected prototype, but shares its policy assumptions.

## Selection and derived cases

Select up to 100 eligible patients in sorted ID order from the existing *pilot* cohort's MR-validation partition, with >=4 observed nonacute observations. For each, choose the latest-issued observed nonacute result and set decision timestamp equal to its original issue timestamp. Use the frozen compiler's `DELAY_RESULT_ENTRY` generated module, exactly +3 days, selecting that observation explicitly. Source and delayed cases form 200 evaluations for each implementation; total 3,200 (correct plus 15 mutants).

The data are synthetic and are reused from a related CKD benchmark; these are NOT independent clinical observations. Patient selection and decision cutoff intentionally exercise availability faults, and the denominator is conditional on eligibility.

## Critical findings

- The correct engineering target agrees with the separately implemented policy reference for 200/200 scenario evaluations. This is a consistency check under shared assumptions, **not** clinical accuracy.
- 12/15 deliberately seeded faulty variants differed at least once from the expected action or provenance trace. The remaining three are survivors in this restricted cohort; this does not estimate field defect prevalence.
- The **actual frozen generated MR oracle** (`PRESERVE_OR_ABSTAIN_IF_UNAVAILABLE` with recorded unavailable-result context) returns 85 TRUE and **15 FALSE** on 100 source/delayed pairs of the reference-policy system. Therefore, the frozen relation cannot presently be treated as a clinically valid decision oracle. Its expectations conflict with a reasonable synthetic policy when withdrawing a latest result changes the decision to another non-abstention action. That is an MR specification/assumption issue, **not 15 demonstrated CDS failures**.
- Mutation detections rely on an **additional independently coded as-of expected-decision/evidence-trace oracle**. **Do not attribute those 12 detections to the frozen MR oracle alone.**

## Next validation needed before venue-neutral

1. Obtain clinical review of a concrete decision-policy specification and whether the frozen delay relation is appropriate for that policy. Do not change or overwrite frozen artifacts to improve apparent results.
2. Add an independent set of new cases and stronger baseline methods; include predeclared endpoints and confidence intervals where defensible.
3. Build/evaluate a real generative or LLM recommender with reproducible model/prompt settings to substantiate specialized collection fit, or choose regular venue-neutral Systems route.
4. Disclose related CKD a related CKD manuscript submission and reuse of synthetic benchmark infrastructure; ensure results are genuinely new and publication policies are observed.
5. Do not report medical efficacy, causal effects, or calibrated uncertainty from these engineering results.
