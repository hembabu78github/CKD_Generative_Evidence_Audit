from __future__ import annotations
import argparse, hashlib, json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier

SUMMARY_FEATURES = [
    'age','sex_m','baseline_egfr','last_egfr','min_egfr','mean_egfr','std_egfr','slope_per_year',
    'relative_change','obs_count','span_days','baseline_acr_log','last_acr_log','missing_ratio','max_delay_days',
    'g_stage_num','acr_stage_num'
]
SEQ_GRID = np.array([0,90,180,270,365,455,545,635,730], dtype=float)


def load_data(data_dir: Path):
    p=pd.read_csv(data_dir/'patients.csv'); o=pd.read_csv(data_dir/'observations.csv')
    return p,o


def _patient_obs(obs: pd.DataFrame, pid: str) -> pd.DataFrame:
    return obs[obs.patient_id==pid].copy()


def _valid_rows(rows: pd.DataFrame, fault: Optional[str]=None) -> pd.DataFrame:
    x=rows.copy()
    if fault != 'F-04':
        x=x[~x.acute_like.astype(bool)]
    if fault == 'F-01':
        x['time_for_model']=x['issued_day']
    else:
        x['time_for_model']=x['effective_day']
    if fault != 'F-02':
        x=x.sort_values(['time_for_model','record_order'], kind='mergesort')
    # Correct target preprocessing collapses exact redundant clinical records; F-06 disables this protection.
    if fault != 'F-06':
        dedup_cols=['effective_day','issued_day','egfr_observed','acr_observed_mg_g','acute_like','aux_creatinine_value','aux_creatinine_unit']
        x=x.drop_duplicates(subset=[c for c in dedup_cols if c in x.columns], keep='first')
    # F-02 deliberately preserves incoming serialization order.
    return x


def input_state(rows: pd.DataFrame, fault: Optional[str]=None) -> str:
    x=_valid_rows(rows,fault)
    eg=x.egfr_observed
    if len(x)<3: return 'INDETERMINATE'
    if pd.isna(x.iloc[0].egfr_observed):
        return 'TRUE' if fault=='F-03' else 'INDETERMINATE'
    if eg.notna().sum()<3: return 'INDETERMINATE'
    return 'TRUE'


def summary_features(patient_row: pd.Series, rows: pd.DataFrame, fault: Optional[str]=None) -> Tuple[Optional[np.ndarray],str]:
    state=input_state(rows,fault)
    x=_valid_rows(rows,fault)
    if state!='TRUE': return None,state
    eg=x.egfr_observed.copy()
    if fault=='F-03' and pd.isna(eg.iloc[0]): eg.iloc[0]=0.0
    mask=eg.notna()
    xx=x.loc[mask].copy(); yy=eg.loc[mask].to_numpy(float)
    tt=xx.time_for_model.to_numpy(float)
    if len(yy)<3: return None,'INDETERMINATE'
    baseline=float(yy[0]); last=float(yy[-1])
    if tt.max()==tt.min(): slope=0.0
    else: slope=float(np.polyfit(tt/365.25,yy,1)[0])
    if fault=='F-07': slope=-slope
    acr=xx.acr_observed_mg_g.to_numpy(float)
    gnum={'G1':1,'G2':2,'G3a':3,'G3b':4,'G4':5,'G5':6}[patient_row.baseline_g_category]
    anum={'A1':1,'A2':2,'A3':3}[patient_row.baseline_acr_category]
    vals=[
      float(patient_row.age), 1.0 if patient_row.sex=='M' else 0.0, baseline,last,float(np.min(yy)),float(np.mean(yy)),float(np.std(yy)),slope,
      (last-baseline)/baseline if baseline else -1.0,float(len(yy)),float(tt.max()-tt.min()),float(np.log1p(acr[0])),float(np.log1p(acr[-1])),
      float(1.0-mask.mean()),float(xx.availability_delay_days.max()),float(gnum),float(anum)
    ]
    return np.array(vals,dtype=float), 'TRUE'


def sequence_features(patient_row: pd.Series, rows: pd.DataFrame, fault: Optional[str]=None) -> Tuple[Optional[np.ndarray],str]:
    state=input_state(rows,fault); x=_valid_rows(rows,fault)
    if state!='TRUE': return None,state
    eg=x.egfr_observed.copy()
    if fault=='F-03' and pd.isna(eg.iloc[0]): eg.iloc[0]=0.0
    mask=eg.notna(); xx=x.loc[mask].copy(); yy=eg.loc[mask].to_numpy(float); tt=xx.time_for_model.to_numpy(float)
    if len(yy)<3: return None,'INDETERMINATE'
    # Rebase times to preserve invariance to global calendar shifts.
    tr=tt-tt.min()
    # Deduplicate times deterministically by mean if fault-free; order-sensitive fault uses last occurrence.
    tmp=pd.DataFrame({'t':tr,'eg':yy,'acr':xx.acr_observed_mg_g.to_numpy(float)})
    if fault=='F-02': tmp=tmp.groupby('t',sort=False).last().reset_index()
    else: tmp=tmp.groupby('t',sort=True).mean(numeric_only=True).reset_index()
    tr=tmp.t.to_numpy(float); yy=tmp.eg.to_numpy(float); aa=np.log1p(tmp.acr.to_numpy(float))
    if len(tr)<2: return None,'INDETERMINATE'
    eg_i=np.interp(SEQ_GRID,tr,yy,left=yy[0],right=yy[-1]); acr_i=np.interp(SEQ_GRID,tr,aa,left=aa[0],right=aa[-1])
    base=eg_i[0] if eg_i[0]!=0 else 1.0
    seq=np.concatenate([eg_i/base, acr_i, SEQ_GRID/730.0, np.array([float(patient_row.age)/100.0, 1.0 if patient_row.sex=='M' else 0.0])])
    return seq,'TRUE'


def rule_output(rows: pd.DataFrame, cfg: dict, fault: Optional[str]=None) -> dict:
    state=input_state(rows,fault)
    if state!='TRUE': return {'truth_state':'INDETERMINATE','risk_probability':None,'risk_ordinal':None,'action':'ABSTAIN'}
    x=_valid_rows(rows,fault)
    eg=x.egfr_observed.copy()
    if fault=='F-03' and pd.isna(eg.iloc[0]): eg.iloc[0]=0.0
    x=x.assign(_eg=eg).dropna(subset=['_eg'])
    if len(x)<3: return {'truth_state':'INDETERMINATE','risk_probability':None,'risk_ordinal':None,'action':'ABSTAIN'}
    base=float(x.iloc[0]._eg); threshold=base*(1-cfg['phase2_endpoint']['relative_decline_threshold'])
    min_days=30 if fault=='F-09' else cfg['phase2_endpoint']['confirmation_min_days']
    crosses=x[(x.time_for_model>x.iloc[0].time_for_model)&(x._eg<=threshold)]
    truth='FALSE'
    if not crosses.empty:
        for _,r in crosses.iterrows():
            later=x[(x.time_for_model>=r.time_for_model+min_days)&(x._eg<=threshold)&(x.time_for_model<=cfg['phase2_endpoint']['horizon_days'])]
            if not later.empty: truth='TRUE'; break
        if truth=='FALSE' and x.time_for_model.max()<crosses.iloc[0].time_for_model+min_days: truth='INDETERMINATE'
    if truth=='INDETERMINATE': return {'truth_state':truth,'risk_probability':None,'risk_ordinal':None,'action':'ABSTAIN'}
    p=1.0 if truth=='TRUE' else 0.0
    return {'truth_state':truth,'risk_probability':p,'risk_ordinal':2 if p else 0,'action':'PROCEED'}


def policy_from_probability(prob: Optional[float], cfg: dict, fault: Optional[str]=None) -> dict:
    if prob is None or (isinstance(prob,float) and np.isnan(prob)):
        return {'risk_ordinal':None,'risk_category':None,'monitoring_priority':None,'referral_support':None,'action':'ABSTAIN'}
    lo=cfg['policy_engineering_thresholds']['risk_low_upper']; hi=cfg['policy_engineering_thresholds']['risk_moderate_upper']
    if fault=='F-08': hi=0.70
    if prob<lo: ordinal=0; cat='LOW'; mon=1
    elif prob<hi: ordinal=1; cat='MODERATE'; mon=2
    else: ordinal=2; cat='HIGH'; mon=3
    return {'risk_ordinal':ordinal,'risk_category':cat,'monitoring_priority':mon,'referral_support':bool(ordinal==2),'action':'PROCEED'}


def convert_aux_creatinine(value: float, unit: str, fault: Optional[str]=None) -> float:
    # The reviewed engineering fixture uses divide by 88.4 for umol/L -> mg/dL.
    if unit=='mg/dL': return float(value)
    if unit!='umol/L': raise ValueError(unit)
    divisor=100.0 if fault=='F-05' else 88.4
    return float(value)/divisor

@dataclass
class ModelBundle:
    lr: object
    hgb: object
    seq: object


def train_models(data_dir: Path, cfg: dict, out_dir: Path) -> dict:
    p,o=load_data(data_dir); dev=p[(p.partition=='development') & p.phase2_endpoint_binary.notna()].copy()
    X=[]; y=[]; Xs=[]; ys=[]
    for _,pr in dev.iterrows():
        rows=_patient_obs(o,pr.patient_id)
        f,s=summary_features(pr,rows)
        sf,ss=sequence_features(pr,rows)
        if s=='TRUE' and f is not None:
            X.append(f); y.append(int(pr.phase2_endpoint_binary))
        if ss=='TRUE' and sf is not None:
            Xs.append(sf); ys.append(int(pr.phase2_endpoint_binary))
    X=np.vstack(X); y=np.array(y); Xs=np.vstack(Xs); ys=np.array(ys)
    lr=Pipeline([('scale',StandardScaler()),('clf',LogisticRegression(C=1.0,max_iter=1000,random_state=cfg['seeds']['lr_model']))])
    lr.fit(X,y)
    hgb=HistGradientBoostingClassifier(max_iter=150,max_depth=4,learning_rate=0.06,l2_regularization=0.1,random_state=cfg['seeds']['hgb_model'])
    hgb.fit(X,y)
    seq=Pipeline([('scale',StandardScaler()),('clf',LogisticRegression(C=0.7,max_iter=1000,random_state=cfg['seeds']['sequence_model']))])
    seq.fit(Xs,ys)
    out_dir.mkdir(parents=True,exist_ok=True)
    joblib.dump(lr,out_dir/'lr_model.joblib'); joblib.dump(hgb,out_dir/'hgb_model.joblib'); joblib.dump(seq,out_dir/'seq_model.joblib')
    meta={'training_partition':'development','n_summary_train':int(len(y)),'n_sequence_train':int(len(ys)),'event_rate_summary':float(y.mean()),'feature_names':SUMMARY_FEATURES,'seq_dimension':int(Xs.shape[1]),
          'hyperparameters':{'lr':{'C':1.0,'max_iter':1000},'hgb':{'max_iter':150,'max_depth':4,'learning_rate':0.06,'l2_regularization':0.1},'seq_lr':{'C':0.7,'max_iter':1000}}}
    (out_dir/'training_metadata.json').write_text(json.dumps(meta,indent=2)); return meta


def load_models(model_dir: Path) -> ModelBundle:
    return ModelBundle(joblib.load(model_dir/'lr_model.joblib'),joblib.load(model_dir/'hgb_model.joblib'),joblib.load(model_dir/'seq_model.joblib'))


def target_output(target: str, patient_row: pd.Series, rows: pd.DataFrame, cfg: dict, models: ModelBundle, fault: Optional[str]=None) -> dict:
    if target=='A1_RULE': return rule_output(rows,cfg,fault=fault)
    if target in {'A2_LR','A3_HGB','A5_POLICY','A6_E2E'}:
        f,state=summary_features(patient_row,rows,fault=fault)
        if state!='TRUE' or f is None:
            base={'truth_state':'INDETERMINATE','risk_probability':None,'action':'ABSTAIN'}
            if target in {'A5_POLICY','A6_E2E'}: base.update(policy_from_probability(None,cfg,fault=fault if target=='A5_POLICY' else None))
            return base
        model=models.lr if target in {'A2_LR','A5_POLICY'} else models.hgb
        prob=float(model.predict_proba(f.reshape(1,-1))[0,1])
        if target in {'A2_LR','A3_HGB'}: return {'truth_state':'TRUE','risk_probability':prob,'action':'PROCEED'}
        pol=policy_from_probability(prob,cfg,fault=fault if target=='A5_POLICY' else fault)
        return {'truth_state':'TRUE','risk_probability':prob,**pol}
    if target=='A4_SEQ':
        f,state=sequence_features(patient_row,rows,fault=fault)
        if state!='TRUE' or f is None: return {'truth_state':'INDETERMINATE','risk_probability':None,'action':'ABSTAIN'}
        prob=float(models.seq.predict_proba(f.reshape(1,-1))[0,1]); return {'truth_state':'TRUE','risk_probability':prob,'action':'PROCEED'}
    if target=='UNIT_ADAPTER':
        r=rows.iloc[0]; v=convert_aux_creatinine(float(r.aux_creatinine_value),str(r.aux_creatinine_unit),fault=fault); return {'truth_state':'TRUE','normalized_creatinine_mg_dl':v,'action':'PROCEED'}
    raise ValueError(target)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',required=True); ap.add_argument('--data-dir',required=True); ap.add_argument('--out-dir',required=True)
    a=ap.parse_args(); cfg=json.loads(Path(a.config).read_text()); meta=train_models(Path(a.data_dir),cfg,Path(a.out_dir)); print(json.dumps(meta,indent=2))
if __name__=='__main__': main()
