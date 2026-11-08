#!/usr/bin/env python3
"""Prespecified dual-trace synthetic-evidence contract. No API calls.
Use a separate, immutable run from the exploratory study; never re-label old responses.
"""
import argparse,csv,datetime as DT,hashlib,json,pathlib,collections
ROOT=pathlib.Path(__file__).resolve().parent
SCHEMA='dual_trace_contract_v1'
SYSTEM=("You are testing a SYNTHETIC SOFTWARE POLICY, not providing clinical advice. "
"Return exactly one JSON object with keys action, all_eligible_ids, decision_basis_ids, rationale, uncertainty. "
"Allowed action values are REVIEW, MONITOR and ABSTAIN. "
"Eligible observations must have issued_time on or before decision_time, a non-null egfr value, and acute_like=false. "
"Sort eligible observations by effective_time, then id, ascending. "
"all_eligible_ids MUST contain EVERY eligible observation ID in that order (not just the endpoints). "
"If fewer than three eligible observations exist, action=ABSTAIN and decision_basis_ids must be []. "
"Otherwise, decision_basis_ids must contain exactly two IDs in order: first eligible and last eligible. "
"Use only those two observations to compute (first_egfr-last_egfr)/first_egfr. "
"If first_egfr>0 and the decline is at least 0.20, action=REVIEW; otherwise action=MONITOR. "
"The pending notice is not an available measurement; do not invent its value. "
"Include any limitations in uncertainty. These arbitrary actions are engineering labels only, not KDIGO treatment recommendations. "
"No medical or treatment recommendations. No additional keys or surrounding Markdown.")
def readj(path):
 return [json.loads(s) for s in pathlib.Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]
def writej(path,rows):
 with open(path,'w',encoding='utf-8',newline='\n') as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
def t(s):return DT.datetime.fromisoformat(s.replace('Z','+00:00'))
def expected(prompt):
 v=json.loads(prompt)
 rows=[r for r in v['observations'] if r.get('issued_time') is not None and t(r['issued_time'])<=t(v['decision_time']) and r.get('egfr') is not None and r.get('acute_like') is False]
 rows=sorted(rows,key=lambda r:(t(r['effective_time']),r['id']))
 full=[r['id'] for r in rows]
 if len(rows)<3:return 'ABSTAIN',full,[]
 first,last=rows[0],rows[-1]
 decision='REVIEW' if first['egfr']>0 and (first['egfr']-last['egfr'])/first['egfr']>=.20 else 'MONITOR'
 return decision,full,[first['id'],last['id']]
def prepare(base,out):
 base=readj(base);out.mkdir(parents=True,exist_ok=True)
 ids=[];man=[];pr=[]
 for x in base:
  a,full,basis=expected(x['user_prompt'])
  if a!=x['expected_action'] or full!=x['expected_used_ids']:raise ValueError('Recomputed answer disagrees with frozen benchmark: '+x['case_id'])
  cid=hashlib.sha256((SCHEMA+'|'+x['case_id']).encode()).hexdigest()[:16]
  x2={k:v for k,v in x.items() if k not in ('case_id','system_prompt','expected_used_ids')}
  x2.update({'case_id':cid,'baseline_case_id':x['case_id'],'system_prompt':SYSTEM,'expected_action':a,'expected_all_eligible_ids':full,'expected_decision_basis_ids':basis,'prespecified_contract':SCHEMA})
  man.append(x2)
  pr.append({'case_id':cid,'condition':x['condition'],'system_prompt':SYSTEM,'user_prompt':x['user_prompt']})
  ids.append(cid)
 if len(set(ids))!=len(ids):raise ValueError('Duplicate case IDs')
 writej(out/'evaluation_manifest.jsonl',man);writej(out/'model_prompts.jsonl',pr)
 (out/'experiment_plan.json').write_text(json.dumps({'contract_version':SCHEMA,'analysis_status':'PRESPECIFIED_BEFORE_NEW_MODEL_RESPONSES','n_cases':len(pr),'n_synthetic_patients':len({i['synthetic_patient_id'] for i in man}),'conditions':dict(collections.Counter(i['condition'] for i in man)),'primary_endpoints':['action_match','full_eligible_trace_exact','decision_basis_exact'],'secondary_endpoints':['used_unavailable_or_pending_ids','wrong_evidence_ids','missing_eligible_ids','ordering_only_mismatches'],'scoring_rules':'Strict ordered array equality; wrong/extraneous ID and omission tracked separately; all metrics denominator is all responses with explicit invalid rows.','comparison_limit':'Same synthetic cases as prior exploratory run; does not constitute independent external validation or causal estimation.','reference_manifest_sha256':hashlib.sha256((ROOT/'frozen_baseline_manifest.jsonl').read_bytes()).hexdigest()},indent=2),encoding='utf-8')
 return man
def score(manifest,responses,out):
 items=readj(manifest);answers=readj(responses);lookup={i['case_id']:i for i in items};out.mkdir(parents=True,exist_ok=True)
 if len({r['case_id'] for r in answers})!=len(answers):raise ValueError('Duplicate responses')
 rows=[];by_case={}
 for r in answers:
  cid=r['case_id']
  if cid not in lookup:raise ValueError('Unknown case ID '+cid)
  q=lookup[cid];raw=r.get('response')
  try:obj=json.loads(raw) if isinstance(raw,str) else raw
  except (json.JSONDecodeError,TypeError):obj=None
  valid=isinstance(obj,dict) and obj.get('action') in ('REVIEW','MONITOR','ABSTAIN') and all(isinstance(obj.get(k),list) and all(isinstance(j,str) for j in obj[k]) for k in ('all_eligible_ids','decision_basis_ids'))
  full=obj['all_eligible_ids'] if valid else [];basis=obj['decision_basis_ids'] if valid else []
  expf=q['expected_all_eligible_ids'];expb=q['expected_decision_basis_ids'];schema=int(valid)
  observed=json.loads(q['user_prompt'])['observations']; allids={x['id'] for x in observed}
  invalidids=sorted(set(full+basis)-allids);unavailable=[]
  for record in observed:
   if record['id'] in set(full+basis) and (record.get('issued_time') is None or t(record['issued_time'])>t(json.loads(q['user_prompt'])['decision_time']) or record.get('egfr') is None or record.get('acute_like') is not False):unavailable.append(record['id'])
  setf=set(full); expectedf=set(expf); extra=sorted(setf-expectedf);omitted=sorted(expectedf-setf)
  row={'case_id':cid,'baseline_case_id':q['baseline_case_id'],'synthetic_patient_id':q['synthetic_patient_id'],'condition':q['condition'],'schema_valid':schema,'expected_action':q['expected_action'],'model_action':obj.get('action') if valid else 'INVALID','action_match':int(valid and obj['action']==q['expected_action']),'full_eligible_trace_exact':int(valid and full==expf),'full_eligible_set_match':int(valid and setf==expectedf and len(full)==len(expf)),'decision_basis_exact':int(valid and basis==expb),'omitted_eligible_count':len(omitted),'extra_noneligible_count':len(extra),'unknown_id_count':len(invalidids),'unavailable_or_invalid_id_count':len(set(unavailable+invalidids)),'ordering_only_full_trace':int(valid and setf==expectedf and len(full)==len(expf) and full!=expf),'expected_all_eligible_ids':'|'.join(expf),'actual_all_eligible_ids':'|'.join(full),'expected_decision_basis_ids':'|'.join(expb),'actual_decision_basis_ids':'|'.join(basis),'missing_ids':'|'.join(omitted),'extra_ids':'|'.join(extra),'response_id':r.get('response_id','')}
  rows.append(row)
 missing=sorted(set(lookup)-{r['case_id'] for r in answers});ms=collections.defaultdict(list)
 for row in rows:ms[row['condition']].append(row)
 metricnames=['schema_valid','action_match','full_eligible_trace_exact','full_eligible_set_match','decision_basis_exact','ordering_only_full_trace']
 def agg(a):return {'n':len(a),**{m:sum(x[m] for x in a) for m in metricnames},'missing_evidence_cases':sum(bool(x['omitted_eligible_count']) for x in a),'extra_evidence_cases':sum(bool(x['extra_noneligible_count']) for x in a),'unavailable_evidence_cases':sum(bool(x['unavailable_or_invalid_id_count']) for x in a)}
 summary={'experiment':SCHEMA,'response_provenance':'USER_SUPPLIED_REAL_API_RECORDS_CROSSCHECK_WITH_RUN_AUDIT','evaluated_responses':len(rows),'expected_responses':len(items),'missing_responses':len(missing),'overall':agg(rows),'by_condition':{k:agg(v) for k,v in sorted(ms.items())},'interpretation':'Toy synthetic software-policy agreement, not validated clinical accuracy, patient benefit, causal estimation or generative intervention effectiveness','analysis_note':'This experiment explicitly disambiguates all eligible evidence from two decision-determining endpoints.'}
 if rows:
  with open(out/'case_scores.csv','w',encoding='utf-8',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 (out/'score_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 (out/'missing_ids.json').write_text(json.dumps(missing,indent=2),encoding='utf-8')
 return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='mode',required=True)
 a=s.add_parser('prepare');a.add_argument('--baseline',type=pathlib.Path,default=ROOT/'frozen_baseline_manifest.jsonl');a.add_argument('--out',type=pathlib.Path,default=ROOT/'results')
 a=s.add_parser('score');a.add_argument('--manifest',type=pathlib.Path,default=ROOT/'results/evaluation_manifest.jsonl');a.add_argument('--responses',type=pathlib.Path,required=True);a.add_argument('--out',type=pathlib.Path,default=ROOT/'results/confirmatory_score')
 args=p.parse_args()
 if args.mode=='prepare':
  records=prepare(args.baseline,args.out);print('Prepared',len(records),'prompts; new IDs and independent answer keys. NO API calls.')
 else:print(json.dumps(score(args.manifest,args.responses,args.out),indent=2))
