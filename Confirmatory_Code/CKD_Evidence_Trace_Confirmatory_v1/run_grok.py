#!/usr/bin/env python3
"""Real xAI Grok 4.7 run for synthetic CKD evidence-grounding prompts.
Uses the public xAI Responses API. Python standard library only.
No calls until explicitly invoked with XAI_API_KEY set.
"""
import argparse, datetime, hashlib, json, os, pathlib, sys, time, urllib.error, urllib.request, uuid, platform
from audit_utils import append_event, sha as sha_file, environment, utc, verify_events
from evaluate_llm import load_jsonl

API='https://api.x.ai/v1/responses'
MODEL='grok-4.7'
INPUT_RATE=2.00 / 1_000_000
OUTPUT_RATE=6.00 / 1_000_000

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def parse_response(data):
    parts=[]
    for output in data.get('output',[]):
        for c in output.get('content',[]):
            if c.get('type')=='output_text' and isinstance(c.get('text'),str):
                parts.append(c['text'])
    # Responses can return reasoning before text; ignore hidden reasoning and use output_text only.
    return '\n'.join(parts)

def send(item, timeout=120, reasoning='low', max_tokens=700):
    payload={'model':MODEL,'instructions':item['system_prompt'],'input':item['user_prompt'],
             'reasoning':{'effort':reasoning},'max_output_tokens':max_tokens,'store':False}
    data=json.dumps(payload).encode('utf-8')
    req=urllib.request.Request(API,data=data,headers={'Authorization':'Bearer '+os.environ['XAI_API_KEY'],
                                                       'Content-Type':'application/json','Accept':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as f:
        return json.load(f)

def run(a):
    prompts=a.prompts.resolve(); manifest=a.manifest.resolve(); out=a.out.resolve()
    if not os.environ.get('XAI_API_KEY'):raise SystemExit('XAI_API_KEY is not set. Use run_pilot.ps1 or run_full.ps1.')
    if not prompts.exists() or not manifest.exists():raise SystemExit('Missing prompts or evaluation manifest')
    all_prompts=load_jsonl(prompts); items=load_jsonl(manifest)
    lookup={q['case_id']:q for q in items}
    if len(lookup)!=len(items):raise SystemExit('Duplicate case IDs in manifest')
    for p in all_prompts:
        if p['case_id'] not in lookup:raise SystemExit('Unrecognized case_id in prompts')
        if p.get('system_prompt')!=lookup[p['case_id']]['system_prompt'] or p.get('user_prompt')!=lookup[p['case_id']]['user_prompt']:
            raise SystemExit('Prompt/manifest mismatch')
        if any(key.startswith('expected_') for key in p):raise SystemExit('Prompts expose expected answers; aborting')
    if a.patients:
        patient_ids=set(); selected=[]
        for p in all_prompts:
            pid=lookup[p['case_id']]['synthetic_patient_id']
            if pid not in patient_ids and len(patient_ids)>=a.patients:continue
            patient_ids.add(pid);selected.append(p)
        all_prompts=selected
    if a.max_cases: all_prompts=all_prompts[:a.max_cases]
    out.parent.mkdir(parents=True,exist_ok=True)
    audit=out.with_suffix('.audit.jsonl')
    session=str(uuid.uuid4())
    meta=out.with_suffix('.metadata.json')
    config={'model':MODEL,'endpoint':API,'manifest_sha256':sha(manifest),'prompts_sha256':sha(prompts),
            'reasoning_effort':a.reasoning,'max_output_tokens':a.max_output_tokens,
            'selected_case_ids':[i['case_id'] for i in all_prompts],
            'rates_usd_per_million':{'input':2,'output':6},'intended_provenance':'REAL_XAI_API',
            'api_request_configuration':{'store':False,'temperature':'provider_default','endpoint_type':'Responses API'}}
    if meta.exists():
        prev=json.loads(meta.read_text(encoding='utf-8'))
        for k in ('model','manifest_sha256','prompts_sha256','reasoning_effort','max_output_tokens','selected_case_ids'):
            if prev.get(k)!=config[k]:raise SystemExit('Existing output metadata differs; use a new --out file')
    else:
        if out.exists() and out.stat().st_size:raise SystemExit('Output exists without metadata; use a new --out path')
        config['created_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        meta.write_text(json.dumps(config,indent=2),encoding='utf-8')
    done={};total_input=total_output=0
    if out.exists():
        for row in load_jsonl(out):
            if row['case_id'] in done:raise SystemExit('Duplicate case IDs in resume file')
            done[row['case_id']]=row
            u=row.get('usage') or {};total_input+=u.get('input_tokens',0) or 0;total_output+=u.get('output_tokens',0) or 0
    append_event(audit,'session_start',session_id=session,environment=environment(),config_sha256=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest(),output_file=str(out.name),existing_completions=len(done),code_sha256=sha_file(pathlib.Path(__file__)))
    count=len(all_prompts); print(f'Grok {MODEL}: {count} prompts; {len(done)} already completed; no raw patient data (synthetic only).',flush=True)
    for n,p in enumerate(all_prompts,1):
        cid=p['case_id']
        if cid in done:continue
        response=None
        for attempt in range(1,4):
            try:
                append_event(audit,'api_attempt_start',session_id=session,case_id=cid,attempt=attempt,request_payload_sha256=hashlib.sha256(json.dumps({'model':MODEL,'instructions':p['system_prompt'],'input':p['user_prompt'],'reasoning':{'effort':a.reasoning},'max_output_tokens':a.max_output_tokens,'store':False},sort_keys=True).encode()).hexdigest())
                t0=time.monotonic();response=send(p,timeout=a.timeout,reasoning=a.reasoning,max_tokens=a.max_output_tokens)
                elapsed=round(time.monotonic()-t0,3)
                append_event(audit,'api_attempt_success',session_id=session,case_id=cid,attempt=attempt,elapsed_seconds=elapsed,response_id=response.get('id'),model=response.get('model'),status=response.get('status'),usage=response.get('usage') or {})
                break
            except urllib.error.HTTPError as e:
                append_event(audit,'api_http_error',session_id=session,case_id=cid,attempt=attempt,http_status=e.code,warning='API error body intentionally not persisted; may include sensitive content')
                body='See xAI console and verify configuration; HTTP error body omitted to protect secrets.'
                if e.code in (400,401,403,404,402):raise SystemExit(f'API HTTP {e.code} (no retry): {body}')
                if e.code not in (408,409,429,500,502,503,504) or attempt==3:raise SystemExit(f'API HTTP {e.code}: {body}')
                print(f'  HTTP {e.code} attempt {attempt}/3; retrying',flush=True)
            except (urllib.error.URLError,TimeoutError) as e:
                append_event(audit,'api_network_error',session_id=session,case_id=cid,attempt=attempt,error_type=type(e).__name__,note='Attempt may have incurred tokens or charges despite no confirmed response')
                if attempt==3:raise SystemExit(f'Network failed: {e}')
                print(f'  network retry {attempt}/3: {e}',flush=True)
            time.sleep(attempt*3)
        text=parse_response(response)
        usage=response.get('usage') or {}
        it=usage.get('input_tokens',0) or 0; ot=usage.get('output_tokens',0) or 0
        total_input+=it;total_output+=ot
        record={'case_id':cid,'response':text,'model':response.get('model',MODEL),
                'response_id':response.get('id'), 'response_status':response.get('status'),
                'created_utc':utc(),'run_session_id':session,'api_endpoint':API,
                'response_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
                'elapsed_seconds':elapsed,'usage':usage,'response_provenance':'REAL_XAI_API',
                'json_parseable':is_json_object(text)}
        with out.open('a',encoding='utf-8') as f:
            f.write(json.dumps(record,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        append_event(audit,'response_persisted',session_id=session,case_id=cid,response_id=record['response_id'],response_sha256=record['response_sha256'],usage=usage,elapsed_seconds=elapsed)
        cost=total_input*INPUT_RATE+total_output*OUTPUT_RATE
        print(f'  {n}/{count} {cid} status={record["response_status"]} json={record["json_parseable"]} tokens={it}+{ot} cumulative_est_USD=${cost:.4f}',flush=True)
        if a.cost_ceiling and cost>=a.cost_ceiling:
            append_event(audit,'soft_cost_ceiling',session_id=session,cumulative_estimated_usd=cost,limit_usd=a.cost_ceiling)
            print(f'Cost ceiling ${a.cost_ceiling} reached; partial outputs saved. You may resume later.',flush=True)
            break
    completed_ids={r['case_id'] for r in load_jsonl(out)} if out.exists() else set()
    finished=len(completed_ids.intersection({p['case_id'] for p in all_prompts}))
    append_event(audit,'session_end',session_id=session,selected_cases=count,persisted_cases=finished,complete=(finished==count),output_sha256=sha_file(out) if out.exists() else None,estimated_token_cost_usd=round(total_input*INPUT_RATE+total_output*OUTPUT_RATE,6))
    print(f'AUDIT: {audit} chain={verify_events(audit)}',flush=True)
    print(f'DONE. File={out}; total input={total_input}; total output={total_output}; estimated token cost=${total_input*INPUT_RATE+total_output*OUTPUT_RATE:.4f}',flush=True)
    print('Next: python confirmatory.py score --manifest results/evaluation_manifest.jsonl --responses '+str(out)+' --out results/confirmatory_score',flush=True)

def is_json_object(s):
    try:return isinstance(json.loads(s),dict)
    except (ValueError,TypeError):return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--prompts',type=pathlib.Path,default=pathlib.Path('results/model_prompts.jsonl'))
    ap.add_argument('--manifest',type=pathlib.Path,default=pathlib.Path('results/evaluation_manifest.jsonl'))
    ap.add_argument('--out',type=pathlib.Path,default=pathlib.Path('results/grok_real_responses.jsonl'))
    ap.add_argument('--patients',type=int,default=0,help='First N patients (3 conditions each); 0 means all')
    ap.add_argument('--max-cases',type=int,default=0,help='Optional cap after patient selection')
    ap.add_argument('--reasoning',choices=['low','medium','high'],default='low')
    ap.add_argument('--max-output-tokens',type=int,default=700)
    ap.add_argument('--cost-ceiling',type=float,default=3.0)
    ap.add_argument('--timeout',type=int,default=120)
    a=ap.parse_args()
    if a.patients<0 or a.max_cases<0:ap.error('counts must be >=0')
    run(a)
if __name__=='__main__':main()
