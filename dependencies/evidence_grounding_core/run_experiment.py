#!/usr/bin/env python3
"""Synthetic, preclinical evidence-availability mutation study.
Uses frozen C4 generated DELAY_RESULT_ENTRY.transform. No clinical guidance or causal claims.
"""
import argparse, csv, hashlib, importlib.util, json, sys
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
UP=ROOT/'upstream'; C4=UP/'chapter4_rc1'; P2=UP/'phase2_ckd_benchmark_v1'
sys.path.insert(0,str(C4));sys.path.insert(0,str(ROOT))
from pilot_adapter import case_from_rows

MUTANTS={
 'M01_NO_AVAILABILITY_FILTER':'never filters observations by issue time',
 'M02_USE_EFFECTIVE_TIME':'uses specimen date rather than issue date for availability',
 'M03_ONE_DAY_PREMATURE':'accepts results one day before issue',
 'M04_THREE_DAYS_PREMATURE':'accepts results three days before issue',
 'M05_INCLUDE_MISSING':'allows missing eGFR observations as zero',
 'M06_REVERSE_VISIT_ORDER':'uses reverse effective-time ordering for final trend',
 'M07_LATEST_BY_ISSUE':'uses issue time instead of clinical time to choose most recent observation',
 'M08_DROP_EARLIEST':'drops earliest available baseline observation',
 'M09_USE_SECOND_LAST':'uses penultimate instead of most recent measurement',
 'M10_LOWER_REVIEW_THRESHOLD':'changes relative deterioration threshold from 0.20 to 0.10',
 'M11_HIGHER_REVIEW_THRESHOLD':'changes relative deterioration threshold from 0.20 to 0.40',
 'M12_TWO_OBS_SUFFICIENT':'permits decisions with two observations, not three',
 'M13_NO_ACUTE_EXCLUSION':'uses acute-like observations in longitudinal decision',
 'M14_ABSOLUTE_DROP':'uses a 10-unit absolute drop rather than relative deterioration',
 'M15_ALWAYS_REVIEW':'returns REVIEW when enough observations exist irrespective of trend',
}

def frozen_delay_module():
    for f in (C4/'fixtures/researcher_c4_014_generated_modules').glob('mr_*.py'):
        if 'DELAY_RESULT_ENTRY' in f.read_text():
            sp=importlib.util.spec_from_file_location('frozen_delay',f)
            m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
            assert m.SPEC['T']['operator_id']=='DELAY_RESULT_ENTRY'
            assert m.CONTROL['execution_gate']=='PROCEED'
            assert next(x['value'] for x in m.SPEC['T']['bound_parameters'] if x['name']=='delay_days')==3
            return m
    raise FileNotFoundError('frozen delay MR')

def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))

def reference(case, at):
    """Independently specified engineering policy (not KDIGO, not treatment advice).
    Available, nonacute, nonmissing evidence; latest relative eGFR drop >=20% -> REVIEW;
    min 3 observations -> decision; else ABSTAIN. Includes evidence trace.
    """
    available=[r for r in case['observations'] if dt(r['issued_time'])<=at and not r.get('acute_like',False)
               and r.get('value') is not None]
    available.sort(key=lambda r:(dt(r['effective_time']),r['id']))
    ids=[r['id'] for r in available]
    if len(available)<3:return {'action':'ABSTAIN','used_ids':ids}
    baseline=float(available[0]['value']);last=float(available[-1]['value'])
    action='REVIEW' if baseline>0 and (baseline-last)/baseline>=0.20 else 'MONITOR'
    return {'action':action,'used_ids':ids}

def target(case,at,mutant=None):
    """Fault-injected implementation, separate from the independently specified reference()."""
    selected=[]
    for r in case['observations']:
        if mutant=='M01_NO_AVAILABILITY_FILTER':eligible=True
        elif mutant=='M02_USE_EFFECTIVE_TIME':eligible=dt(r['effective_time'])<=at
        elif mutant=='M03_ONE_DAY_PREMATURE':eligible=(dt(r['issued_time']).timestamp()<=at.timestamp()+86400)
        elif mutant=='M04_THREE_DAYS_PREMATURE':eligible=(dt(r['issued_time']).timestamp()<=at.timestamp()+3*86400)
        else:eligible=dt(r['issued_time'])<=at
        if not eligible:continue
        if r.get('acute_like',False) and mutant!='M13_NO_ACUTE_EXCLUSION':continue
        if r.get('value') is None and mutant!='M05_INCLUDE_MISSING':continue
        selected.append(r)
    if mutant=='M05_INCLUDE_MISSING':selected=[{**r,'value':0.0 if r.get('value') is None else r['value']} for r in selected]
    selected.sort(key=lambda r:(dt(r['issued_time']) if mutant=='M07_LATEST_BY_ISSUE' else dt(r['effective_time']),r['id']))
    if mutant=='M06_REVERSE_VISIT_ORDER':selected.reverse()
    if mutant=='M08_DROP_EARLIEST' and selected:selected=selected[1:]
    ids=[r['id'] for r in selected]
    minobs=2 if mutant=='M12_TWO_OBS_SUFFICIENT' else 3
    if len(selected)<minobs:return {'action':'ABSTAIN','used_ids':ids}
    baseline=float(selected[0]['value']);last=float(selected[-2 if mutant=='M09_USE_SECOND_LAST' else -1]['value'])
    if mutant=='M15_ALWAYS_REVIEW':action='REVIEW'
    elif mutant=='M14_ABSOLUTE_DROP':action='REVIEW' if baseline-last>=10 else 'MONITOR'
    else:
        threshold=0.10 if mutant=='M10_LOWER_REVIEW_THRESHOLD' else 0.40 if mutant=='M11_HIGHER_REVIEW_THRESHOLD' else 0.20
        action='REVIEW' if baseline>0 and (baseline-last)/baseline>=threshold else 'MONITOR'
    return {'action':action,'used_ids':ids}

def assemble_cases(limit):
    patients=pd.read_csv(P2/'data/pilot/patients.csv')
    obs=pd.read_csv(P2/'data/pilot/observations.csv')
    source=patients[patients.partition=='mr_validation'].sort_values('patient_id')
    m=frozen_delay_module()
    out=[]
    for _,patient in source.iterrows():
        rows=obs[obs.patient_id==patient.patient_id]
        if rows.empty:continue
        case=case_from_rows(patient,rows)
        for r in case['observations']:
            item=rows.loc[rows.visit_id.astype(str)==r['id']].iloc[0]
            r['acute_like']=bool(item.acute_like)
        usable=sorted([r for r in case['observations'] if r['value'] is not None and not r['acute_like']], key=lambda r:(dt(r['issued_time']),r['id']))
        if len(usable)<4:continue
        chosen=usable[-1]
        at=dt(chosen['issued_time'])
        # Exactly as-of at issuance: original result is available, delayed result is not.
        mutated=m.transform(case,execution_context={'selected_observation_ids':[chosen['id']]})
        src_r=next(r for r in case['observations'] if r['id']==chosen['id'])
        dst_r=next(r for r in mutated['observations'] if r['id']==chosen['id'])
        assert (dt(dst_r['issued_time'])-dt(src_r['issued_time'])).days==3
        assert src_r['value']==dst_r['value'] and src_r['effective_time']==dst_r['effective_time']
        out.append((str(patient.patient_id),chosen['id'],at,case,mutated))
        if len(out)>=limit:break
    return out,m

def run(limit,out):
    cases,m=assemble_cases(limit);out.mkdir(parents=True,exist_ok=True)
    records=[]; counts=Counter(); base_mismatch=0
    for pid,selected,at,src,delayed in cases:
        for variant,case in [('source',src),('delay_3d',delayed)]:
            exp=reference(case,at)
            corr=target(case,at)
            assert corr==exp, (pid,variant,exp,corr)
            counts[f'baseline_{variant}_{exp["action"]}']+=1
            for mutant in [None,*MUTANTS]:
                actual=target(case,at,mutant)
                all_ids={r['id']:r for r in case['observations']}
                unissued=[oid for oid in actual['used_ids'] if dt(all_ids[oid]['issued_time'])>at]
                missing=[oid for oid in actual['used_ids'] if all_ids[oid].get('value') is None]
                acute=[oid for oid in actual['used_ids'] if all_ids[oid].get('acute_like',False)]
                mismatch=actual['action']!=exp['action']
                trace_error=actual['used_ids']!=exp['used_ids']
                killed=mismatch or trace_error
                records.append({'patient_id':pid,'scenario':variant,'selected_observation':selected,
                   'decision_time':at.isoformat(),'mutant':mutant or 'CORRECT',
                   'expected_action':exp['action'],'actual_action':actual['action'],
                   'action_mismatch':int(mismatch),'trace_mismatch':int(trace_error),'detected':int(killed),
                   'unissued_used':len(unissued),'missing_used':len(missing),'acute_used':len(acute),
                   'expected_evidence_ids':'|'.join(exp['used_ids']),'actual_evidence_ids':'|'.join(actual['used_ids'])})
    fields=list(records[0]) if records else []
    with (out/'case_results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
    summ=[]
    for mutant in ['CORRECT',*MUTANTS]:
        rr=[r for r in records if r['mutant']==mutant]
        for scenario in ['source','delay_3d','overall']:
            sub=[r for r in rr if r['scenario']==scenario] if scenario!='overall' else rr
            summ.append({'mutant':mutant,'scenario':scenario,'n':len(sub),
                'detected':sum(r['detected'] for r in sub),'action_mismatches':sum(r['action_mismatch'] for r in sub),
                'trace_mismatches':sum(r['trace_mismatch'] for r in sub),'unissued_exposures':sum(r['unissued_used']>0 for r in sub)})
    with (out/'fault_summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(summ[0]));w.writeheader();w.writerows(summ)
    # Evaluate a subset of the frozen relation independently: preserve or abstain under newly unavailable evidence.
    # Outcome compliance is a descriptive supplementary check; it cannot identify future evidence leaks when actions preserve.
    oracle=[]
    for pid,selected,at,src,delayed in cases:
        s=reference(src,at); d=reference(delayed,at)
        or_state=m.oracle(s['action'],d['action'],oracle_context={'available_at_decision': False})['truth']
        oracle.append({'patient_id':pid,'source_action':s['action'],'delayed_action':d['action'],'preserve_or_abstain':or_state})
    with (out/'delay_relation_screen.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(oracle[0]));w.writeheader();w.writerows(oracle)
    summary={'protocol':'venue-neutral-EVIDENCE-ASOF-PILOT-1.0','case_selection':'first eligible MR-validation patients in synthetic Phase-2 pilot cohort; deterministic sorted IDs; selected latest issued nonacute observed result, >=4 eligible records',
        'patient_scenarios':len(cases),'evaluations':len(records),'distinct_mutants':len(MUTANTS),
        'frozen_candidate_id':m.SPEC['candidate_mr_id'],'frozen_delay_days':3,
        'baseline_reference_agreement':sum(r['detected']==0 for r in records if r['mutant']=='CORRECT'),
        'baseline_reference_total':sum(r['mutant']=='CORRECT' for r in records),
        'baseline_counts':dict(counts),'delay_relation_screen':dict(Counter(x['preserve_or_abstain'] for x in oracle)),
        'relation_warning':'The frozen 3-day delayed-result relation rejects some correctly simulated decisions; its clinical/decision-level validity is NOT established.',
        'mutants_detected_at_least_once':sum(any(r['detected'] for r in records if r['mutant']==m) for m in MUTANTS),
        'mutant_detection_by_scenario':{k:sum(r['detected'] for r in records if r['mutant']!='CORRECT' and r['scenario']==k) for k in ('source','delay_3d')},
        'limitations':['Synthetic engineering target and independently coded policy specification, not validated KDIGO CDS or clinical care recommendation.',
        'Faults and adjudication policy deliberately specified in this study; engineering mutations are not an unbiased sample of real defects.',
        'Reference and implementation share synthetic engineering design assumptions, despite separate functions.',
        'The frozen compiler produced a 3-day DELAY_RESULT_ENTRY transform. Detection uses an additional as-of evidence-trace oracle; do not attribute all detections to the frozen CandidateMR relation alone.',
        'The frozen CandidateMR remains clinically UNREVIEWED and this study is not an LLM, causal or patient outcome evaluation.',
        'Synthetic source cohort and simulator framework overlap existing a related CKD manuscript CKD research; disclose overlap and establish distinct novelty before submission.',
        'Exploratory pilot with no confidence intervals or clinical evaluation; results are not submission-ready evidence of clinical effectiveness.']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    (out/'fault_catalogue.json').write_text(json.dumps(MUTANTS,indent=2))
    return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--patients',type=int,default=100);ap.add_argument('--output',type=Path,default=ROOT/'results');a=ap.parse_args()
    print(json.dumps(run(a.patients,a.output),indent=2))
