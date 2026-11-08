import json, tempfile
from pathlib import Path
from run_experiment import run,assemble_cases,reference,target,MUTANTS

def test_experiment():
    with tempfile.TemporaryDirectory() as d:
        s=run(25,Path(d))
        assert s['patient_scenarios']==25
        assert s['evaluations']==25*2*(len(MUTANTS)+1)
        assert s['baseline_reference_agreement']==s['baseline_reference_total']==50
        assert sum(s['delay_relation_screen'].values())==25
        assert s['frozen_delay_days']==3
        # Re-run proves exact deterministic results.
        with tempfile.TemporaryDirectory() as e:
            t=run(25,Path(e))
            assert s==t
            for name in ['case_results.csv','fault_summary.csv','delay_relation_screen.csv']:
                assert (Path(d)/name).read_bytes()==(Path(e)/name).read_bytes()

if __name__=='__main__':
    test_experiment(); print('Evidence-aware study smoke and reproducibility tests PASS')
