# KG-to-MR static validation comparison — exploratory v1.0

**Publication-venue-neutral.** This is a completed, fixture-only engineering comparison, not clinical validation, upstream KG-to-MR population, or proof of novelty.

## Included materials

- `Chapter4_Compiler_Release_Candidate_RC1.zip`: byte-identical original compiler RC1 release provided in the research files, preserved for provenance.
- `run_matched_comparison.py`: standard-library-only comparison runner.
- `results/case_level_comparison.csv`: one row per original or deliberately invalid candidate.
- `results/study_report.json`: counts, manifest state, fingerprints, run environment and comparator outcomes.
- `results/rc1_unit_tests_stderr.txt`: fresh 291-test RC1 unit suite results.
- `results/SHA256SUMS.txt`: integrity for result files.
- `VERIFY_AND_LIMITATIONS.md`: scope and interpretation.

## Windows reproduction

Extract the package ZIP. In PowerShell, from inside the extracted directory:

```powershell
py .\run_matched_comparison.py --compiler-zip ".\Chapter4_Compiler_Release_Candidate_RC1.zip" --out ".\results_reproduced"
```

Only Python's standard library is needed. No credentials, Grok calls, patient records or network access are used.

Optional recheck of the original compiler test suite:

```powershell
Expand-Archive ".\Chapter4_Compiler_Release_Candidate_RC1.zip" ".\rc1_original" -Force
cd .\rc1_original\Chapter4_Compiler_Release_Candidate_RC1
py -m unittest discover -s tests -q
```

The case CSV is stable across runs. `study_report.json` contains the UTC timestamp, operating system and Python version and will accordingly differ in those metadata fields.

## Experimental boundaries

This comparison was constructed and executed after reviewing existing fixtures and is **exploratory, not prospectively registered**. The 12 candidates are Chapter 4 fixture-derived, not externally clinically reviewed MRs. Exactly 117 manually specified invalid mutations were created across ten mutation categories (certain categories are not applicable to every candidate); 12 unchanged candidates were controls. The outcome oracle is known by construction, so the experiment does not measure detection of unforeseen errors.

The strict conventional validator is given the same structured information and same validation requirements as the RC1 candidate validator; the thin operator-only baseline has intentionally fewer requirements and is presented solely as an ablation. No engineering superiority follows from outperforming that thin baseline. No developer-effort or latency comparison was performed. Real-patient datasets are not involved in this compiler-only stage.
