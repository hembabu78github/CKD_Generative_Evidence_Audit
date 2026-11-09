#!/usr/bin/env python3
"""Publication-neutral MIMIC-IV demo temporal evidence engineering PILOT.
No LLM calls or clinical decisions. Storage time is an availability proxy only.
"""
import argparse, datetime as dt, gzip, hashlib, io, json, platform, sys, zipfile
from pathlib import Path
import numpy as np
import pandas as pd

VERSION='1.0.0'; ITEMID=50912; SEED=20261108

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def records(frame, at, use='storetime'):
 return frame.loc[(frame.charttime<=at)&(frame[use]<=at)&frame.valuenum.notna()].sort_values(['charttime','storetime','labevent_id'],kind='stable').labevent_id.astype('int64').tolist()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mimic-zip',required=True);ap.add_argument('--out',default='mimic_temporal_pilot_results');args=ap.parse_args()
 src=Path(args.mimic_zip);out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(src) as z:
  target=next(x for x in z.namelist() if x.endswith('/hosp/labevents.csv.gz'))
  with gzip.GzipFile(fileobj=io.BytesIO(z.read(target))) as stream:
   df=pd.read_csv(stream,usecols=['labevent_id','subject_id','itemid','charttime','storetime','valuenum','valueuom'])
 df=df.loc[df.itemid.eq(ITEMID)].copy()
 for k in ['charttime','storetime']: df[k]=pd.to_datetime(df[k],errors='coerce')
 df=df.dropna(subset=['subject_id','labevent_id','charttime','storetime','valuenum']).copy()
 df['subject_id']=df.subject_id.astype('int64');df['labevent_id']=df.labevent_id.astype('int64')
 counts={k:0 for k in ['order_permutation_pass','future_observation_exclusion_pass','mask_required_result_pass','foreign_evidence_id_rejection_pass','duplicate_conflict_flag_pass','availability_delay_monotonicity_pass']}
 patients=0; tests=[]; audit=[]; rng=np.random.default_rng(SEED)
 all_ids=set(df.labevent_id.tolist())
 for pid,grp in df.groupby('subject_id',sort=True):
  grp=grp.sort_values(['storetime','charttime','labevent_id'],kind='stable').reset_index(drop=True)
  if len(grp)<2:continue
  patients+=1
  at=grp.storetime.iloc[len(grp)//2]
  base=records(grp,at)
  if len(base)==0: continue
  perm=grp.sample(frac=1,random_state=int(rng.integers(1,2**31-1)))
  passed=base==records(perm,at);counts['order_permutation_pass']+=int(passed);tests.append(('order_permutation',pid,passed))
  # Add a synthetically future-dated, otherwise valid record of same patient.
  future=grp.iloc[[0]].copy();future.loc[:,'labevent_id']=int(max(all_ids))+1000000+int(pid)
  future.loc[:,'charttime']=at+pd.Timedelta(days=1);future.loc[:,'storetime']=at+pd.Timedelta(days=1)
  passed=base==records(pd.concat([grp,future],ignore_index=True),at)
  counts['future_observation_exclusion_pass']+=int(passed);tests.append(('future_observation_exclusion',pid,passed))
  # Mask the only eligible result in a minimal fixture: must return no evidence.
  selected=grp.loc[grp.labevent_id.eq(base[0])].copy();selected.loc[:,'valuenum']=np.nan
  passed=records(selected,at)==[]
  counts['mask_required_result_pass']+=int(passed);tests.append(('mask_required_result',pid,passed))
  other=next((int(x) for x in df.loc[df.subject_id.ne(pid),'labevent_id'].head(1)),None)
  passed=other is not None and other not in set(grp.labevent_id)
  counts['foreign_evidence_id_rejection_pass']+=int(passed);tests.append(('foreign_evidence_id_rejection',pid,passed))
  # A synthetic same-charttime duplicate with a conflicting value is flagged, not resolved.
  e=grp.loc[grp.labevent_id.eq(base[0])].iloc[0].copy();e['labevent_id']=int(max(all_ids))+2000000+int(pid);e['valuenum']=float(e['valuenum'])+1.0
  combined=pd.concat([grp,pd.DataFrame([e])],ignore_index=True)
  elig=combined.loc[combined.labevent_id.isin(records(combined,at))]
  conflicts=elig.groupby('charttime').valuenum.nunique(dropna=True)
  passed=bool((conflicts>1).any())
  counts['duplicate_conflict_flag_pass']+=int(passed);tests.append(('duplicate_conflict_flag',pid,passed))
  # Delaying availability proxy cannot introduce an originally unavailable record.
  delayed=grp.copy(); delayed['storetime']=delayed.storetime+pd.Timedelta(days=3)
  after=records(delayed,at)
  passed=set(after).issubset(set(base))
  counts['availability_delay_monotonicity_pass']+=int(passed);tests.append(('availability_delay_monotonicity',pid,passed))
  audit.append({'patient_index':patients,'observations':len(grp),'eligible_at_reference':len(base),'eligible_after_3d_proxy_delay':len(after)})
 details=pd.DataFrame(tests,columns=['test','subject_id','pass']); summary=details.groupby('test').agg(n=('pass','size'),passed=('pass','sum')).reset_index();summary['failed']=summary.n-summary.passed
 # Only aggregate test counts are published; no row-level patient exports.
 summary.to_csv(out/'test_summary.csv',index=False)
 report={'protocol':'MIMIC temporal integrity engineering pilot v1.0','status':'EXPLORATORY PILOT — NOT FROZEN MAIN STUDY','utc_execution':dt.datetime.now(dt.timezone.utc).isoformat(),'input_sha256':sha(src),'source_table':target,'itemid':ITEMID,'seed':SEED,'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'valid_creatinine_observations':len(df),'patients_tested':patients,'tests':summary.to_dict('records'),'limitations':['Not a CKD clinical decision accuracy test','Source is a nonrepresentative 100-patient demo sample','storetime is a storage-time availability proxy, not clinician visibility','Injected future timestamps, masks, duplicates, and delays are synthetic faults','Tests verify internal engineering invariants, not incremental KG/MR benefit']}
 (out/'pilot_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 (out/'SHA256SUMS.txt').write_text(''.join(f'{sha(out/f)}  {f}\n' for f in ['test_summary.csv','pilot_report.json']),encoding='utf-8')
 print(json.dumps({'patients_tested':patients,'creatinine_observations':len(df),'results':summary.to_dict('records'),'output_dir':str(out)},indent=2))
 if summary.failed.sum(): sys.exit(2)
if __name__=='__main__':main()
