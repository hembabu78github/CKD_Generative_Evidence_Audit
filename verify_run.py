#!/usr/bin/env python3
"""Verify local audit continuity and produce a provenance/coverage report. Does not prove external API authenticity."""
import argparse,collections,datetime,hashlib,json,pathlib
from audit_utils import verify_events,sha,utc

def jsonl(p):
    with open(p,encoding='utf-8') as f:return [json.loads(x) for x in f if x.strip()]

def verify(responses,manifest,prompts,score_dir=None):
    responses=pathlib.Path(responses);manifest=pathlib.Path(manifest);prompts=pathlib.Path(prompts)
    meta=responses.with_suffix('.metadata.json'); audit=responses.with_suffix('.audit.jsonl')
    errors=[];warnings=[]
    if not all(p.exists() for p in (responses,manifest,prompts,meta,audit)):
        return {'verification_pass':False,'errors':['Missing essential evidence file: '+str(p) for p in (responses,manifest,prompts,meta,audit) if not p.exists()]}
    m=json.loads(meta.read_text(encoding='utf-8'));r=jsonl(responses);a=jsonl(audit);items=jsonl(manifest)
    cmap={x['case_id'] for x in items};selected=set(m.get('selected_case_ids',[]))
    if sha(manifest)!=m.get('manifest_sha256'):errors.append('Manifest SHA-256 mismatch')
    if sha(prompts)!=m.get('prompts_sha256'):errors.append('Prompts SHA-256 mismatch')
    chain=verify_events(audit)
    if not chain.get('valid'):errors.append('Audit hash chain failed')
    if len(set(x.get('case_id') for x in r))!=len(r):errors.append('Duplicate response case IDs')
    if not set(x.get('case_id') for x in r).issubset(selected):errors.append('Response outside selected case IDs')
    if not selected.issubset(cmap):errors.append('Selected cases missing from manifest')
    by_id={x.get('case_id'):x for x in r}
    for row in r:
        if row.get('response_sha256')!=hashlib.sha256(row.get('response','').encode('utf-8')).hexdigest():errors.append('Response text hash mismatch: '+str(row.get('case_id')))
        if row.get('response_provenance')!='REAL_XAI_API' or not row.get('response_id'):errors.append('Missing API response provenance/id: '+str(row.get('case_id')))
    persisted=[x for x in a if x.get('event')=='response_persisted']
    if len(persisted)!=len(r):errors.append('Persisted response count does not match audit entries (possible archive tampering or interrupted write)')
    for p in persisted:
        rr=by_id.get(p['case_id'])
        if not rr or rr.get('response_id')!=p.get('response_id') or rr.get('response_sha256')!=p.get('response_sha256'):errors.append('Audit response mismatch: '+p['case_id'])
    terminated=[x for x in a if x.get('event')=='session_end']
    if not terminated:warnings.append('No session_end event; possible abrupt termination or aborted run')
    for x in terminated:
        if x.get('complete') is True and x.get('selected_cases')!=x.get('persisted_cases'):errors.append('Invalid session completeness record')
    if len(r)!=len(selected):warnings.append(f'PARTIAL: {len(r)}/{len(selected)} selected cases have confirmed stored results')
    if any(x.get('event') in ('api_http_error','api_network_error') for x in a):warnings.append('API attempts failed or were retried; provider-side usage may exceed recorded successful usage')
    if score_dir:
        sd=pathlib.Path(score_dir);summ=sd/'score_summary.json'
        if summ.exists():
            sc=json.loads(summ.read_text(encoding='utf-8'))
            if sc.get('evaluated_responses')!=len(r):errors.append('Scorer count does not match response count')
        else:warnings.append('Scoring report absent')
    return {'verification_pass':not errors,'complete':len(r)==len(selected),'status':'COMPLETE' if len(r)==len(selected) else 'PARTIAL',
        'verified_at_utc':utc(),'audit_chain':chain,'selected_cases':len(selected),'stored_responses':len(r),'manifest_cases':len(items),
        'unique_api_response_ids':len(set(x.get('response_id') for x in r)),'events':collections.Counter(x.get('event') for x in a),
        'total_recorded_tokens':{'input':sum((x.get('usage') or {}).get('input_tokens',0) or 0 for x in r),'output':sum((x.get('usage') or {}).get('output_tokens',0) or 0 for x in r)},
        'artifacts_sha256':{p.name:sha(p) for p in (responses,meta,audit,manifest,prompts)},
        'errors':errors,'warnings':warnings,
        'limitations':['Local timestamps and hashes can be altered by someone controlling all files; this is not trusted timestamping or a digital signature.',
                       'API response IDs and usage metadata are captured from returned JSON; independent API-provider attestation is not provided.',
                       'Verifier establishes internal consistency, not model correctness, clinical validity, nor independent authorship.',
                       'The API key and any HTTP error bodies are intentionally excluded from audit evidence.']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--responses',type=pathlib.Path,required=True);p.add_argument('--manifest',type=pathlib.Path,default=pathlib.Path('results/evaluation_manifest.jsonl'));p.add_argument('--prompts',type=pathlib.Path,default=pathlib.Path('results/model_prompts.jsonl'));p.add_argument('--score-dir',type=pathlib.Path);a=p.parse_args()
    report=verify(a.responses,a.manifest,a.prompts,a.score_dir)
    dst=a.responses.with_suffix('.verification.json');dst.write_text(json.dumps(report,indent=2,default=dict),encoding='utf-8');print(json.dumps(report,indent=2,default=dict));print('Saved',dst)
    if not report['verification_pass']:raise SystemExit(2)
    if not report['complete']:raise SystemExit(3)
if __name__=='__main__':main()
