#!/usr/bin/env python3
"""Non-clinical exploratory adapter for frozen C4 CandidateMRs and Phase-2 synthetic CKD simulator.
Does not edit either upstream package. Reports mechanical feasibility separately from clinical validity.
"""
import argparse, copy, csv, hashlib, importlib.util, json, sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE=datetime(2020,1,1,tzinfo=timezone.utc)
PILOTS=('PRESERVE_CLINICAL_STATE','RESAMPLE_TRAJECTORY','DELAY_RESULT_ENTRY')

def iso(day):
    return (BASE+timedelta(days=int(day))).isoformat().replace('+00:00','Z')
def day_from_iso(ts):
    d=datetime.fromisoformat(ts.replace('Z','+00:00'))
    out=(d-BASE).total_seconds()/86400
    if not out.is_integer(): raise ValueError('Non-integer day offset cannot be represented by Phase-2 model')
    return int(out)

def pyval(x):
    if pd.isna(x): return None
    if isinstance(x,np.generic): return x.item()
    return x

def case_from_rows(patient, rows):
    observations=[]
    sort=rows.sort_values(['effective_day','record_order'],kind='mergesort').reset_index(drop=True)
    valid=sort[(~sort.acute_like.astype(bool)) & sort.egfr_observed.notna()]
    anchors=set(valid.iloc[[0,-1]].visit_id.tolist()) if len(valid)>1 else set()
    for _,r in sort.iterrows():
        observations.append({'id':str(r.visit_id),'effective_time':iso(r.effective_day),
             'issued_time':iso(r.issued_day),'time_index':float(r.effective_day),
             'value':pyval(r.egfr_observed),'unit':'mL/min/1.73m2',
             'anchor':str(r.visit_id) in anchors,
             'protected_anchor':str(r.visit_id) in anchors,
             'available':True,'required':str(r.visit_id) in anchors})
    return {'subject':{'id':str(patient.patient_id)}, 'observations':observations,
            'observation_order':[r['id'] for r in observations],
            'non_state_auxiliary_field':'fixture_A',
            'derived':{'risk_context':'not_clinically_adjudicated'},
            'trajectory':{'protected_anchors':sorted(anchors)}}

def rows_from_case(source_rows, transformed):
    """Only supported reversible projection: drop records / update existing timing and eGFR fields.
    Never invent a new observation or reinterpret a unit-conversion transformation."""
    by_id={str(x['id']):x for x in transformed['observations']}
    source_ids=set(source_rows.visit_id.astype(str))
    if not set(by_id).issubset(source_ids): raise ValueError('new/generated observation ID has no Phase-2 row mapping')
    out=source_rows[source_rows.visit_id.astype(str).isin(by_id)].copy(deep=True)
    for idx,row in out.iterrows():
        item=by_id[str(row.visit_id)]
        out.at[idx,'effective_day']=day_from_iso(item['effective_time'])
        out.at[idx,'issued_day']=day_from_iso(item['issued_time'])
        out.at[idx,'availability_delay_days']=int(out.at[idx,'issued_day']-out.at[idx,'effective_day'])
        out.at[idx,'egfr_observed']=float(item['value']) if item['value'] is not None else np.nan
        out.at[idx,'missing_egfr']=item['value'] is None
    # Phase-2 record_order semantics are original serialization order (unchanged for these three MRs).
    return out

def load_module(path, root):
    sys.path.insert(0,str(root)) if str(root) not in sys.path else None
    spec=importlib.util.spec_from_file_location('frozen_'+path.stem,str(path))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def generate_matrix(root):
    modules=root/'fixtures/researcher_c4_014_generated_modules'
    records=[]; index={}
    for path in sorted(modules.glob('mr_*.py')):
        m=load_module(path,root)
        op=m.SPEC['T']['operator_id'];gate=m.CONTROL['execution_gate']; params={x['name']:x['value'] for x in m.SPEC['T'].get('bound_parameters',[])}
        if gate!='PROCEED': status='BLOCKED_BY_FROZEN_GATE'; note='No target dispatch permitted'
        elif op=='PRESERVE_CLINICAL_STATE':status='MECHANICAL_PILOT';note='Non-state field changed; tests equality of A1_RULE action only, not clinical validation'
        elif op=='RESAMPLE_TRAJECTORY':status='MECHANICAL_PILOT';note='Anchors protected by adapter assumption; semantic alignment of source KG anchors not established'
        elif op=='DELAY_RESULT_ENTRY':status='TRANSFORM_ONLY';note='A1_RULE has no as-of-issued-time decision cutoff; evidence grounding cannot be inferred'
        elif op=='SHIFT_TIME':status='UNMAPPED';note='Phase-2 horizon uses absolute days; global shift semantics need review'
        elif op=='CONVERT_UNIT':status='UNMAPPED';note='Frozen conversion targets eGFR; Phase-2 unit adapter uses creatinine'
        elif op=='REMOVE_REDUNDANT_OBSERVATION':status='UNMAPPED';note='Frozen redundancy_key is a fixture ID, not a Phase-2 visit ID'
        elif op=='INCREASE_SLOPE':status='UNMAPPED';note='Frozen slope_delta uses different time/value semantics and needs independent clinical direction check'
        elif op=='INSERT_TRANSIENT_AKI':status='UNMAPPED';note='Derived observations do not map to Phase-2 acute_like event schema without added verified policy'
        else:status='UNMAPPED';note='Not reviewed for Phase-2 compatibility'
        item={'candidate_id':m.SPEC['candidate_mr_id'],'operator':op,'frozen_gate':gate,
              'relation_family':m.SPEC['R']['relation_family'],'bound_parameters':json.dumps(params,sort_keys=True),
              'integration_status':status,'reason':note}
        records.append(item);index[op]=m
    return records,index

def run(root, phase2, out, n):
    sys.path.insert(0,str(phase2))
    from p2_targets_v1 import rule_output
    cfg=json.loads((phase2/'p2_config_v1.json').read_text())
    patients=pd.read_csv(phase2/'data/pilot/patients.csv')
    obs=pd.read_csv(phase2/'data/pilot/observations.csv')
    matrix,index=generate_matrix(root)
    rows=[]; selected=patients[(patients.partition=='mr_validation')].head(n)
    for _,patient in selected.iterrows():
        source=obs[obs.patient_id==patient.patient_id].copy()
        case=case_from_rows(patient,source)
        for op in PILOTS:
            mr=index[op]; result={'patient_id':str(patient.patient_id),'operator':op,
                 'candidate_id':mr.SPEC['candidate_mr_id'],'execution_gate':mr.CONTROL['execution_gate'],
                 'evaluation_class':'MECHANICAL_ONLY','oracle_truth':'NOT_EVALUATED','reason':''}
            try:
                follow_case=mr.transform(case)
                follow_rows=rows_from_case(source,follow_case)
                result['source_observations']=int(len(source));result['followup_observations']=int(len(follow_rows))
                if op=='DELAY_RESULT_ENTRY':
                    result['evaluation_class']='TRANSFORM_ONLY'
                    result['reason']='No decision-time evidence filter in Phase-2 A1_RULE; skipping oracle and detection claims'
                else:
                    a=rule_output(source,cfg);b=rule_output(follow_rows,cfg)
                    result['source_action']=a.get('action');result['followup_action']=b.get('action')
                    if a.get('truth_state')=='INDETERMINATE' or b.get('truth_state')=='INDETERMINATE':
                        result['oracle_truth']='INDETERMINATE';result['reason']='A1_RULE endpoint indeterminate'
                    elif op=='PRESERVE_CLINICAL_STATE':
                        r=mr.oracle(a['action'],b['action']);result['oracle_truth']=r['truth'];result['reason']=r['reason']
                    elif op=='RESAMPLE_TRAJECTORY':
                        ordering=['LOW','MODERATE','HIGH']
                        def cat(v): return None if v is None else ('HIGH' if int(v)==2 else 'MODERATE' if int(v)==1 else 'LOW')
                        r=mr.oracle(cat(a['risk_ordinal']),cat(b['risk_ordinal']),runtime_config={'ordinal_orderings':{'risk_low_moderate_high_v1':ordering}})
                        result['oracle_truth']=r['truth'];result['reason']=r['reason']
            except Exception as e:
                result['evaluation_class']='INTEGRATION_ERROR'; result['oracle_truth']='NOT_EVALUATED';result['reason']=type(e).__name__+': '+str(e)
            rows.append(result)
    # Validate all frozen gates dispatch no target requests when blocked.
    gates=[]
    for item in matrix:
        if item['frozen_gate']=='PROCEED':continue
        m=index[item['operator']] if item['operator']!='SHIFT_TIME' else None
        if m is None:
            m=next(load_module(p,root) for p in (root/'fixtures/researcher_c4_014_generated_modules').glob('mr_*.py') if item['candidate_id'] in p.read_text())
        calls=[]
        res=m.execute({'observations':[]},lambda c:calls.append(c))
        gates.append({'candidate_id':item['candidate_id'],'status':res['status'],'target_calls':len(calls)})
    out.mkdir(parents=True,exist_ok=True)
    with (out/'compatibility_matrix.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
    with (out/'pilot_results.csv').open('w',newline='') as f:
        keys=['patient_id','operator','candidate_id','execution_gate','evaluation_class','oracle_truth','reason','source_observations','followup_observations','source_action','followup_action']
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    totals={op:dict(Counter(x['oracle_truth'] for x in rows if x['operator']==op)) for op in PILOTS}
    summary={'n_patients':len(selected),'n_candidates':len(matrix),'frozen_gates':dict(Counter(x['frozen_gate'] for x in matrix)),
             'compatibility_status':dict(Counter(x['integration_status'] for x in matrix)),
             'pilot_oracle_states':totals,'gate_checks':gates,
             'limitations':['Only a preliminary mechanical adapter; not a new scientifically independent experiment.',
             'The existing Phase-2 A1_RULE simulation endpoint is not a validated clinical decision policy.',
             'Source KG fixture terms and Phase-2 patient feature semantics have not undergone expert adjudication.',
             'No evidence-availability as-of filter exists in Phase-2 A1_RULE; DELAY_RESULT_ENTRY is transform-only.',
             'Source and follow-up comparisons share the Phase-2 simulated endpoint; do not interpret as clinical accuracy.',
             'Not a new LLM or causal intervention study; no venue-neutral scientific performance claim established.']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    return summary

if __name__=='__main__':
    pa=argparse.ArgumentParser()
    pa.add_argument('--compiler-root',type=Path,required=True)
    pa.add_argument('--phase2-root',type=Path,required=True)
    pa.add_argument('--output',type=Path,default=Path('results'))
    pa.add_argument('--patients',type=int,default=30)
    args=pa.parse_args()
    print(json.dumps(run(args.compiler_root,args.phase2_root,args.output,args.patients),indent=2))
