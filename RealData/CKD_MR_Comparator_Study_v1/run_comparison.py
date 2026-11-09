#!/usr/bin/env python3
"""Publication-neutral real-derived engineering assay: generated Chapter-4 MR vs simple trace validator.

Synthetic software faults are injected into a toy *nonclinical* target. The target is not an actual CDS.
No patient-level results are written to disk. MIMIC storetime is a proxy, not a verified clinician-visibility time.
"""
import argparse,csv,datetime as dt,gzip,hashlib,io,json,platform,sys,zipfile
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
from generated import mr_cmr_3fbe15eb0c59f7367ebdd879 as generated_mr

SEED=20261108
ITEMID=50912
REQUIREMENT='ENGINEERING_ONLY'

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()

def load(mimic):
 with zipfile.ZipFile(mimic) as z:
  target=next(n for n in z.namelist() if n.endswith('/hosp/labevents.csv.gz'))
  with gzip.GzipFile(fileobj=io.BytesIO(z.read(target))) as stream:
   df=pd.read_csv(stream,usecols=['labevent_id','subject_id','itemid','charttime','storetime','valuenum','valueuom'])
 df=df.loc[df.itemid.eq(ITEMID)].copy()
 for k in ['charttime','storetime']:df[k]=pd.to_datetime(df[k],errors='coerce')
 df=df.dropna(subset=['subject_id','labevent_id','charttime','storetime','valuenum'])
 df['subject_id']=df.subject_id.astype('int64');df['labevent_id']=df.labevent_id.astype('int64')
 return df,target

def iso(ts):
 return ts.tz_localize('UTC').isoformat().replace('+00:00','Z')

def as_case(pid, grp):
 grp=grp.sort_values(['storetime','charttime','labevent_id'],kind='stable').reset_index(drop=True)
 decision=grp.storetime.iloc[len(grp)//2]
 case={'subject':{'id':str(pid)}, 'decision_time':iso(decision),
       'non_state_auxiliary_field':0,
       'observations':[{'id':str(int(r.labevent_id)),'effective_time':iso(r.charttime),
                        'issued_time':iso(r.storetime),'value':float(r.valuenum),
                        'unit':str(r.valueuom)} for r in grp.itertuples(index=False)]}
 def eligible(r):return r.charttime<=decision and r.storetime<=decision
 allowed={str(int(r.labevent_id)) for r in grp.itertuples(index=False) if eligible(r)}
 future=next((str(int(r.labevent_id)) for r in grp.itertuples(index=False) if not eligible(r)),None)
 return case,allowed,future

def toy_target(case, fault, allowed, future):
 # engineering decision from eligible EVIDENCE COUNT, not a clinical recommendation or patient risk.
 ev=sorted(allowed,key=int)
 d='ENGINEERING_BIN_EVEN' if len(ev)%2==0 else 'ENGINEERING_BIN_ODD'
 if fault=='auxiliary_coupling' and case['non_state_auxiliary_field']!=0:
  d='ENGINEERING_BIN_ODD' if d=='ENGINEERING_BIN_EVEN' else 'ENGINEERING_BIN_EVEN'
 if fault=='future_evidence_leak' and future is not None:
  ev=ev+[future]
 return d,ev

def simple_validator(reported_ids,allowed):
 # independent trace-only validator: membership and exact cardinality; no decision-relation contract
 return set(reported_ids)==allowed and len(reported_ids)==len(allowed)

def compare_one(case,allowed,future,fault):
 result={'mr_truth':None,'baseline_detect':None,'enhanced_detect':None,'mr_detect':None,'oracle_fault':fault!='control'}
 # Test source / followup trace validity via independent trace checker.
 before_output, before_ids=toy_target(case,fault,allowed,future)
 mutated=generated_mr.transform(case,execution_context={'state_defining_fields':['observations','decision_time','subject']})
 after_output, after_ids=toy_target(mutated,fault,allowed,future)
 before_valid=simple_validator(before_ids,allowed)
 after_valid=simple_validator(after_ids,allowed)
 result['baseline_detect']=not(before_valid and after_valid)
 # stronger conventional validator adds the same explicit decision-invariance contract
 result['enhanced_detect']=result['baseline_detect'] or (before_output!=after_output)
 # actual compiled generated MR oracle, not a handwritten replacement for MR decision relation
 observed=generated_mr.execute(case,lambda c:toy_target(c,fault,allowed,future)[0],
                                execution_context={'state_defining_fields':['observations','decision_time','subject']})
 if observed['status']=='EXECUTED':
  result['mr_truth']=observed['oracle']['truth']
  result['mr_detect']=result['mr_truth']=='FALSE'
 else:
  result['mr_truth']='ABSTAIN'
  result['mr_detect']=False
 assert observed['status']=='EXECUTED'
 assert observed['source_output']==before_output and observed['followup_output']==after_output
 assert mutated['observations']==case['observations'] and mutated['subject']==case['subject']
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--mimic-zip',required=True);p.add_argument('--out',default='comparison_results');a=p.parse_args()
 dest=Path(a.out);dest.mkdir(parents=True,exist_ok=True)
 frame,source_table=load(Path(a.mimic_zip))
 per=[]; eligible_sizes=[]; skipped=0
 for pid,g in frame.groupby('subject_id',sort=True):
  if len(g)<2:skipped+=1;continue
  c,allow,future=as_case(pid,g)
  if not allow or future is None:skipped+=1;continue
  eligible_sizes.append(len(allow))
  for fault in ['control','auxiliary_coupling','future_evidence_leak']:
   x=compare_one(c,allow,future,fault)
   per.append({'condition':fault,'baseline_detect':x['baseline_detect'],'enhanced_detect':x['enhanced_detect'],'mr_detect':x['mr_detect'],
               'mr_truth':x['mr_truth'],'oracle_fault':x['oracle_fault']})
 # keep only aggregate stats and no direct identifiers
 names=['condition','cases','baseline_detect','enhanced_detect','mr_detect','either_detect','both_detect','neither_detect','mr_true','mr_false','mr_indeterminate']
 summary=[]
 for label in ['control','auxiliary_coupling','future_evidence_leak']:
  rows=[x for x in per if x['condition']==label]
  summary.append({'condition':label,'cases':len(rows),
                  'baseline_detect':sum(x['baseline_detect'] for x in rows),
                  'enhanced_detect':sum(x['enhanced_detect'] for x in rows),
                  'mr_detect':sum(x['mr_detect'] for x in rows),
                  'either_detect':sum(x['baseline_detect'] or x['mr_detect'] for x in rows),
                  'both_detect':sum(x['baseline_detect'] and x['mr_detect'] for x in rows),
                  'neither_detect':sum(not x['baseline_detect'] and not x['mr_detect'] for x in rows),
                  'mr_true':sum(x['mr_truth']=='TRUE' for x in rows),
                  'mr_false':sum(x['mr_truth']=='FALSE' for x in rows),
                  'mr_indeterminate':sum(x['mr_truth']=='INDETERMINATE' for x in rows)})
 with (dest/'aggregate_comparison.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,names);w.writeheader();w.writerows(summary)
 report={'title':'Real-derived engineering comparison: fixture-compiled MR vs trace-only validator',
         'study_status':'EXPLORATORY NONCLINICAL ENGINEERING, NOT CLINICAL VALIDATION',
         'utc_run':dt.datetime.now(dt.timezone.utc).isoformat(),'random_seed':SEED,
         'input_zip_sha256':sha(a.mimic_zip),'source_table':source_table,'creatinine_itemid':ITEMID,
         'source_creatinine_rows':len(frame),'patients_with_usable_split':len(eligible_sizes),
         'patients_skipped':skipped,'tests_executed':len(per),
         'generated_mr_id':generated_mr.SPEC['candidate_mr_id'],
         'source_mr_status':generated_mr.SPEC['P']['mr_expert_validation_status'],
         'source_mr_fixture_release':generated_mr.SPEC['P']['kg_release'],
         'generator_control':generated_mr.CONTROL,'python_version':platform.python_version(),
         'pandas_version':pd.__version__,
         'conditions':summary,
         'design':{'target':'Toy parity-based engineering decision, NOT a CKD clinical decision',
                   'control':'No injected fault','auxiliary_coupling':'Decision improperly changes with a nonclinical auxiliary field',
                   'future_evidence_leak':'Evidence trace improperly includes an actual later MIMIC laboratory record',
                   'baseline':'Trace-only deterministic validation; no decision-invariance checks',
                   'MR':'Original compiled Chapter 4 fixture candidate PRESERVE_CLINICAL_STATE',
                   'enhanced_comparator':'Conventional validator checks both trace integrity and auxiliary-field decision invariance',
                   'reference':'Known deterministic injected fault assignments, not independent patient clinical ground truth'},
         'limitations':['This is a demonstration of complementary contract coverage, not superiority over a fully specified conventional validator.',
          'Trace-only baseline intentionally checks evidence validity only; enhanced comparator adds the same invariance and is reported explicitly.',
          'The selected Chapter 4 MR is fixture-backed and unreviewed by clinical experts.',
          'MIMIC demo is a nonrepresentative sample of 100 real patients.',
          'Storetime is only a proxy for result availability; the underlying clinical visibility is unknown.',
          'Mutants are injected software faults; no observed real clinical errors are claimed.',
          'No patient-level records are exported; individual data are processed locally.',
          'Do not interpret 100% controlled-mutant rates as clinical model performance.']}
 (dest/'comparison_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 (dest/'SHA256SUMS.txt').write_text(''.join(sha(dest/n)+'  '+n+'\n' for n in ['aggregate_comparison.csv','comparison_report.json']),encoding='utf-8')
 print(json.dumps({'patients':len(eligible_sizes),'source_creatinine_rows':len(frame),'results':summary},indent=2))
if __name__=='__main__':main()
