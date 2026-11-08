#!/usr/bin/env python3
"""Prepare blinded synthetic evidence-grounding prompts; score independently supplied model outputs.
No external calls, no implied clinical validation. Requires Step-2 package in sibling directory.
"""
import argparse,csv,json,sys,hashlib
from pathlib import Path
from collections import Counter
from datetime import timedelta
ROOT=Path(__file__).resolve().parent
STEP2=(ROOT/'dependencies/evidence_grounding_core') if (ROOT/'dependencies/evidence_grounding_core').exists() else (ROOT.parent/'evidence_grounding_core')
sys.path.insert(0,str(STEP2))
from run_experiment import assemble_cases,reference,dt

SYSTEM="""You are evaluating a SYNTHETIC, NON-CLINICAL CKD data-handling policy, not advising patients. Return only JSON with keys action, used_ids, rationale, uncertainty. Allowed action: REVIEW, MONITOR, ABSTAIN. Use ONLY observations with issued_time <= decision_time, nonmissing value, and acute_like false. Sort eligible observations by effective_time then id. If fewer than three eligible observations, ABSTAIN. Otherwise compare first and last eGFR; REVIEW if (first-last)/first >= 0.20 and first > 0, else MONITOR. Cite each observation actually used in used_ids and no other IDs. State any data limitations. This 20% flag is an arbitrary software-policy fixture, NOT an actual clinical guideline or care recommendation. No medicines, diagnoses or intervention prescriptions."""

def manifest(limit):
    cases,m=assemble_cases(limit)
    out=[]
    for pid,oid,at,src,delayed in cases:
        for condition,case in [('source',src),('delayed_3d',delayed),('delayed_with_pending_notice',delayed)]:
            eligible=[]; records=[]
            for r in case['observations']:
                view={'id':r['id'],'effective_time':r['effective_time'],'issued_time':r['issued_time'],
                      'egfr':r['value'],'acute_like':r.get('acute_like',False)}
                if condition=='delayed_with_pending_notice' and r['id']==oid and dt(r['issued_time'])>at:
                    # Pending notice discloses only ID, NOT numeric value or post-decision contents.
                    view={'id':r['id'],'status':'PENDING_NOT_AVAILABLE','effective_time':r['effective_time']}
                records.append(view)
            expected=reference(case,at)
            uid=hashlib.sha256((pid+'|'+condition+'|'+at.isoformat()).encode()).hexdigest()[:16]
            task={'decision_time':at.isoformat(),'observations':records,'task':'Apply the synthetic audit policy; return evidence ids and uncertainty.'}
            out.append({'case_id':uid,'synthetic_patient_id':pid,'condition':condition,
                'selected_delayed_observation_id':oid,'system_prompt':SYSTEM,'user_prompt':json.dumps(task,separators=(',',':')),
                'expected_action':expected['action'],'expected_used_ids':expected['used_ids'],
                'target_context':'toy engineering policy; not clinical recommendation'})
    return out

def write_jsonl(path,records):
    with open(path,'w',encoding='utf-8') as f:
        for x in records:f.write(json.dumps(x,ensure_ascii=False)+'\n')

def load_jsonl(path):
    with open(path,encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]

def score(items,answers):
    by_case={x['case_id']:x for x in items}; seen=set(); rows=[]
    for item in answers:
        cid=item.get('case_id')
        if cid not in by_case:raise ValueError('Unknown case_id: '+str(cid))
        if cid in seen:raise ValueError('Duplicate model response: '+str(cid))
        seen.add(cid);q=by_case[cid]
        raw=item.get('response',item.get('output'))
        if isinstance(raw,str):
            try: parsed=json.loads(raw)
            except json.JSONDecodeError:parsed=None
        else:parsed=raw
        valid=isinstance(parsed,dict) and parsed.get('action') in ('REVIEW','MONITOR','ABSTAIN') and isinstance(parsed.get('used_ids'),list) and all(isinstance(x,str) for x in parsed.get('used_ids',[]))
        action=parsed.get('action') if valid else None;used=parsed.get('used_ids') if valid else []
        prompt=json.loads(q['user_prompt']); avail={r['id']:r for r in prompt['observations'] if 'issued_time' in r}
        unavailable=[]; missing=[]; acute=[]; unknown=[]
        for oid in used:
            if oid not in avail:
                unavailable.append(oid);unknown.append(oid)
            else:
                r=avail[oid]
                if dt(r['issued_time'])>dt(prompt['decision_time']):unavailable.append(oid)
                if r['egfr'] is None:missing.append(oid)
                if r['acute_like']:acute.append(oid)
        rows.append({'case_id':cid,'condition':q['condition'],'synthetic_patient_id':q['synthetic_patient_id'],
            'valid_json_schema':int(valid),'expected_action':q['expected_action'],'model_action':action or 'INVALID',
            'action_match':int(valid and action==q['expected_action']),
            'trace_exact_ordered':int(valid and used==q['expected_used_ids']),
            'trace_set_match':int(valid and set(used)==set(q['expected_used_ids']) and len(used)==len(q['expected_used_ids'])),
            'unavailable_ids_used':len(unavailable),'missing_ids_used':len(missing),'acute_ids_used':len(acute),
            'unknown_or_pending_ids_used':len(unknown),'model_used_ids':'|'.join(used),'expected_used_ids':'|'.join(q['expected_used_ids'])})
    # Missing IDs are failures of response coverage, not silently dropped.
    missing_ids=sorted(set(by_case)-seen)
    summary={'evaluated_responses':len(rows),'expected_responses':len(items),'missing_responses':len(missing_ids),
      'schema_valid':sum(r['valid_json_schema'] for r in rows),'action_matches':sum(r['action_match'] for r in rows),
      'trace_exact_ordered':sum(r['trace_exact_ordered'] for r in rows),
      'unavailable_evidence_use_cases':sum(r['unavailable_ids_used']>0 for r in rows),
      'missing_evidence_use_cases':sum(r['missing_ids_used']>0 for r in rows),
      'acute_evidence_use_cases':sum(r['acute_ids_used']>0 for r in rows),
      'condition_summary':{c:{'n':len(a),'action_matches':sum(x['action_match'] for x in a),'trace_matches':sum(x['trace_exact_ordered'] for x in a),'unavailable_used':sum(x['unavailable_ids_used']>0 for x in a)} for c in sorted(set(x['condition'] for x in rows)) for a in [[r for r in rows if r['condition']==c]]},
      'not_clinical_validation':True,'not_causal_effect_estimation':True}
    return rows,summary,missing_ids

def main():
    p=argparse.ArgumentParser();sp=p.add_subparsers(dest='mode',required=True)
    a=sp.add_parser('prepare');a.add_argument('--patients',type=int,default=100);a.add_argument('--out',type=Path,default=ROOT/'results')
    a=sp.add_parser('score');a.add_argument('--manifest',type=Path,required=True);a.add_argument('--responses',type=Path,required=True);a.add_argument('--out',type=Path,default=ROOT/'results/model_run')
    a=sp.add_parser('fixture');a.add_argument('--manifest',type=Path,required=True);a.add_argument('--out',type=Path,default=ROOT/'results/fixture')
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    if args.mode=='prepare':
        items=manifest(args.patients)
        # evaluator keeps answers, API prompt file intentionally omits expected fields
        write_jsonl(args.out/'evaluation_manifest.jsonl',items)
        write_jsonl(args.out/'model_prompts.jsonl',[{k:x[k] for k in ('case_id','condition','system_prompt','user_prompt')} for x in items])
        (args.out/'manifest_summary.json').write_text(json.dumps({'synthetic_patients':args.patients,'prompt_count':len(items),'conditions':dict(Counter(x['condition'] for x in items)),'frozen_delay':'3 calendar days','note':'not a model evaluation'},indent=2))
        print('Prepared',len(items),'prompts in',args.out)
    else:
        items=load_jsonl(args.manifest)
        if args.mode=='fixture':
            # Perfect oracle/fixture responses are a scorer self-test, NEVER model results.
            answers=[{'case_id':x['case_id'],'response':{'action':x['expected_action'],'used_ids':x['expected_used_ids'],'rationale':'fixture response','uncertainty':'deterministic synthetic policy'}} for x in items]
            write_jsonl(args.out/'fixture_responses.jsonl',answers)
        else:answers=load_jsonl(args.responses)
        rows,summ,missing=score(items,answers)
        if rows:
            with (args.out/'case_scores.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        (args.out/'score_summary.json').write_text(json.dumps({**summ,'response_provenance':'TEST_FIXTURE_NOT_LLM' if args.mode=='fixture' else 'USER_SUPPLIED_RESPONSES_NOT_INDEPENDENTLY_VERIFIED'},indent=2))
        (args.out/'missing_ids.json').write_text(json.dumps(missing,indent=2))
        print(json.dumps(summ,indent=2))
if __name__=='__main__':main()
