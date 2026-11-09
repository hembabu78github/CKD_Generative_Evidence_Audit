# Real-record temporal evidence integrity pilot v1.0

Publication-venue-neutral and exploratory. This executes six engineering invariant checks per patient on the 100-patient MIMIC-IV Demo 2.2 laboratory table. **This is not a CKD diagnostic, clinical safety, longitudinal CKD progression, or KG/MR superiority evaluation.** It uses real de-identified lab results with synthetic fault injection.

## Windows instructions
1. Install Python 3.10+ with `py -m pip install pandas numpy` (or `python -m pip install pandas numpy`).
2. Place `run_mimic_temporal_pilot.py` and the original `mimic-iv-clinical-database-demo-2.2.zip` in the same folder (do not extract the source ZIP).
3. Run from PowerShell:

```powershell
py -m pip install pandas numpy
py .\run_mimic_temporal_pilot.py --mimic-zip ".\mimic-iv-clinical-database-demo-2.2.zip" --out ".\my_pilot_results"
```

Outputs: `pilot_report.json`, `test_summary.csv`, `SHA256SUMS.txt`. No row-level patient exports or API requests. Input file hash and environment versions recorded. Checks may use synthetic altered test records only in process; source is not overwritten.

## Interpretive cautions
- Fixed assay `itemid=50912` and numeric serum creatinine values only. `charttime` and `storetime` are used for evidence selection; `storetime` **is only a storage-time proxy** and does not establish actual clinician visibility.
- Six tests are engineering contract checks and share the same implementation for generation and validation; a pass is a smoke test, not independent cross-validation. The foreign-ID test checks that an ID from a different patient is absent from the per-patient source ID set.
- No patient-level inference or independent clinical conclusions. The MIMIC demo is a small nonrepresentative acute-care sample. Synthetic faults are not observed clinical faults.
- This pilot is deliberately not the frozen main experiment; a separate prespecified independent oracle and KG/MR vs reference comparator are required before publication-oriented conclusions.
