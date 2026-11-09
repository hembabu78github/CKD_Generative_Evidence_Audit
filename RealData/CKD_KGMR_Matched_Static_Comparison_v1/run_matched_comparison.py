"""Publication-neutral, fixture-derived static validation comparator.
No patient data, credentials, third-party services, or clinical verdicts.
"""
import argparse, copy, csv, hashlib, importlib.util, io, json, os, platform, re, sys, zipfile
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

ALLOWED_OPERATORS={"SHIFT_TIME","RESAMPLE_TRAJECTORY","DELAY_RESULT_ENTRY","SWAP_EQUIVALENT_ORDER","REMOVE_REDUNDANT_OBSERVATION","MASK_REQUIRED_OBSERVATION","INCREASE_SLOPE","DECREASE_SLOPE","INSERT_TRANSIENT_AKI","CONVERT_UNIT","PRESERVE_CLINICAL_STATE"}
RELATIONS={"EQUALITY_WITHIN_TOLERANCE","MONOTONIC_INCREASE","MONOTONIC_DECREASE","ORDINAL_NONDECREASE","ORDINAL_NONINCREASE","BOUNDED_CHANGE","DECISION_LEVEL"}
CONDITIONS={"CLINICAL","DATA_AVAILABILITY","TEMPORAL","APPLICABILITY","TERMINOLOGY"}
INVARIANTS={"VALUE","IDENTITY","TIME","STATE","STRUCTURE","UNIT_CANONICAL_VALUE","CUSTOM_DECLARED"}
P_KEYS=("source_knowledge_item_ids","source_locator_refs","graph_path_ids","kg_release","ontology_release","shacl_release","proposition_ir_version","compiler_version","operator_library_version","operator_selection_fingerprint","parameter_provenance_refs","inference_profile","closure_policy_version","srew_version","compiler_config_id","generation_status","mr_expert_validation_status")

def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def condition_errors(c):
    if not isinstance(c,dict):return ['nonobject condition']
    if 'op' in c:
        if c['op'] in ('ALL','ANY'):return ['empty condition'] if not c.get('children') else sum((condition_errors(x) for x in c['children']),[])
        if c['op']=='NOT':return condition_errors(c.get('child'))
        return ['unknown condition op']
    return (["invalid condition type"] if c.get('predicate_type') not in CONDITIONS else []) + (["missing evidence policy"] if c.get('missing_evidence_result')!='INDETERMINATE' else []) + (["missing condition provenance"] if not c.get('source_refs') else []) + (["missing condition evaluator"] if not c.get('evaluator_id') else [])

def matched_reference_errors(s):
    """Standalone conventional rules validator receiving the SAME requirements as RC1.
    Written independently from frozen specification; not a clinician or ontology prover.
    """
    required=['candidate_mr_id','representation_version','candidate_status','C','T','R','I','E','P']
    missing=[x for x in required if x not in s]
    if missing:return ['required fields missing: '+','.join(missing)]
    e=[]
    if s['representation_version']!='CandidateMR-R1.0':e.append('representation version')
    if s['candidate_status']!='COMPILED_CANDIDATE':e.append('candidate status')
    e+=condition_errors(s['C'])
    t=s['T'];r=s['R'];p=s['P']
    if t.get('operator_id') not in ALLOWED_OPERATORS:e.append('operator')
    for prm in t.get('bound_parameters',[]):
        if prm.get('source_kind') not in ('kg','source_evidence','compiler_config') or not prm.get('source_ref'):e.append('parameter provenance')
    fam=r.get('relation_family')
    if fam not in RELATIONS:e.append('relation family')
    params=r.get('parameters',{})
    if fam=='EQUALITY_WITHIN_TOLERANCE' and ('epsilon' not in params or params.get('tolerance_mode') not in ('absolute','relative','mixed')):e.append('tolerance')
    if fam in ('ORDINAL_NONDECREASE','ORDINAL_NONINCREASE') and not params.get('ordering_id'):e.append('ordering')
    if fam=='BOUNDED_CHANGE' and not {'lower_bound','upper_bound','delta_definition'}.issubset(params):e.append('bounds')
    if fam=='DECISION_LEVEL' and not params.get('decision_comparator_id'):e.append('decision comparator')
    for inv in s['I']:
        if inv.get('invariant_type') not in INVARIANTS:e.append('invariant type')
        if not inv.get('source_selector') or not inv.get('followup_selector'):e.append('invariant selector')
        if not inv.get('comparator_id') or not inv.get('source_refs'):e.append('invariant provenance')
    for exc in s['E']:
        if exc.get('precedence_tier') not in {'P'+str(i) for i in range(9)}:e.append('exception tier')
        c=exc.get('condition',{})
        if c.get('predicate_type')!='EXCEPTION':e.append('exception predicate')
        if c.get('missing_evidence_result')!='INDETERMINATE':e.append('exception indeterminacy')
        if 'observed_fixture_truth' in c:e.append('truth leakage')
        if not exc.get('evidence_refs'):e.append('exception provenance')
    for key in P_KEYS:
        if key not in p:e.append('missing provenance field '+key)
    if p.get('generation_status')!='CANDIDATE':e.append('generation status')
    if p.get('mr_expert_validation_status')!='UNREVIEWED':e.append('expert review status')
    if not p.get('source_knowledge_item_ids') or not p.get('source_locator_refs'):e.append('source knowledge provenance')
    return e

def basic_template_errors(s):
    """Thin conventional generator: operator existence + template availability only."""
    return [] if s.get('T',{}).get('operator_id') in ALLOWED_OPERATORS else ['unknown operator']

def mutation(s,tag):
    x=copy.deepcopy(s)
    if tag=='operator_unknown':x['T']['operator_id']='UNKNOWN_OP'
    elif tag=='relation_unknown':x['R']['relation_family']='UNKNOWN_REL'
    elif tag=='condition_source_removed':
        c=x['C']; leaf=(c['children'][0] if 'children' in c else c);leaf['source_refs']=[]
    elif tag=='invariant_provenance_removed':x['I'][0]['source_refs']=[]
    elif tag=='source_locator_removed':x['P']['source_locator_refs']=[]
    elif tag=='expert_status_forged':x['P']['mr_expert_validation_status']='VALIDATED'
    elif tag=='condition_missingness_flipped':
        c=x['C'];leaf=(c['children'][0] if 'children' in c else c);leaf['missing_evidence_result']='FALSE'
    elif tag=='parameter_source_removed':
        if not x['T'].get('bound_parameters'):return None
        x['T']['bound_parameters'][0]['source_ref']=''
    elif tag=='exception_evidence_removed':
        if not x['E']:return None
        x['E'][0]['evidence_refs']=[]
    elif tag=='forbidden_fixture_truth':
        if not x['E']:return None
        x['E'][0]['condition']['observed_fixture_truth']='TRUE'
    else:raise ValueError(tag)
    return x

TAGS=['operator_unknown','relation_unknown','condition_source_removed','invariant_provenance_removed','source_locator_removed','expert_status_forged','condition_missingness_flipped','parameter_source_removed','exception_evidence_removed','forbidden_fixture_truth']

def main():
    a=argparse.ArgumentParser();a.add_argument('--compiler-zip',required=True);a.add_argument('--out',default='results_matched');args=a.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    src=Path(args.compiler_zip); raw=src.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist(); prefix=next(n.split('fixtures/c4_013_candidate_specs/')[0] for n in names if 'fixtures/c4_013_candidate_specs/' in n)
        specs=[json.loads(z.read(n)) for n in names if n.startswith(prefix+'fixtures/c4_013_candidate_specs/') and n.endswith('.json')]
        specs=sorted(specs,key=lambda s:s['candidate_mr_id'])
        validator_source=z.read(prefix+'compiler/candidate_validation.py')
        import types
        module=types.ModuleType('frozen_candidate_validation');exec(compile(validator_source, 'frozen_candidate_validation.py','exec'), module.__dict__)
        manifest=json.loads(z.read(prefix+'fixtures/researcher_c4_014_codegen_manifest.json'))
        if isinstance(manifest,dict):manifest=manifest.get('modules',manifest.get('generated_modules',manifest.get('rows',[])))
        manifest_gate={row['candidate_mr_id']:row.get('execution_gate') for row in manifest if isinstance(row,dict) and 'candidate_mr_id' in row}
        generated={n.rsplit('/',1)[-1]:z.read(n) for n in names if 'fixtures/researcher_c4_014_generated_modules/mr_' in n and n.endswith('.py')}
        module_hash_checks=[{'module':r['module_path'],'match':sha(generated.get(r['module_path'],b''))==r['generated_python_sha256']} for r in manifest]
    rows=[]; expected_invalid_count=0
    for spec in specs:
        for tag in ['control']+TAGS:
            cand=copy.deepcopy(spec) if tag=='control' else mutation(spec,tag)
            if cand is None:continue
            expected_invalid=tag!='control'; expected_invalid_count+=int(expected_invalid)
            rc1_error=module.validate_candidate(cand)
            matched_error=matched_reference_errors(cand)
            basic_error=basic_template_errors(cand)
            rows.append({'candidate_mr_id':spec['candidate_mr_id'],'scenario':tag,'expected_invalid':expected_invalid,'rc1_reject':bool(rc1_error),'matched_reference_reject':bool(matched_error),'basic_template_reject':bool(basic_error),'rc1_reason_count':len(rc1_error),'matched_reason_count':len(matched_error),'rc1_reasons':' | '.join(rc1_error),'reference_reasons':' | '.join(matched_error)})
    for col in ('rc1_reject','matched_reference_reject','basic_template_reject'):
        assert all(row[col]==row['expected_invalid'] for row in rows if col=='matched_reference_reject'), 'reference not matching intentionally injected defects'
    fieldnames=list(rows[0]);csv_path=out/'case_level_comparison.csv'
    with csv_path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fieldnames);w.writeheader();w.writerows(rows)
    rates={}
    for key in ('rc1_reject','matched_reference_reject','basic_template_reject'):
        rates[key]={'invalid_detected':sum(r[key] for r in rows if r['expected_invalid']),'invalid_total':expected_invalid_count,'valid_false_flags':sum(r[key] for r in rows if not r['expected_invalid']),'valid_total':len(specs)}
    mismatches=[{'id':r['candidate_mr_id'],'scenario':r['scenario'],'rc1':r['rc1_reject'],'reference':r['matched_reference_reject']} for r in rows if r['rc1_reject']!=r['matched_reference_reject']]
    gates=Counter(manifest_gate.values()); source_hashes={s['candidate_mr_id']:sha(canonical(s).encode()) for s in specs}
    report={'study':'CKD KG/MR fixture static-validation comparison (engineering, not clinical)','timestamp_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version.split()[0],'platform':platform.platform(),'original_compiler_zip_sha256':sha(raw),'frozen_validator_py_sha256':sha(validator_source),'candidate_count':len(specs),'generated_module_count':len(generated),'observed_generated_gates':dict(gates),'generated_manifest_gate_entries':len(manifest_gate),'generated_module_hash_matches':sum(item['match'] for item in module_hash_checks),'generated_module_hash_checks':module_hash_checks,'mutation_categories':TAGS,'test_cases':len(rows),'expected_invalid':expected_invalid_count,'metrics':rates,'full_vs_matched_disagreements':mismatches,'candidate_fingerprints':source_hashes,'limitation':'All candidate specs are fixture-derived and expert-unreviewed; matched baseline consumes the same structured candidates; no upstream raw KG proposition parsing, reviewer effort measurement, clinical CDS accuracy, or superiority is evaluated.'}
    (out/'study_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    checks={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt'}
    (out/'SHA256SUMS.txt').write_text(''.join(f'{h}  {n}\n' for n,h in checks.items()),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('candidate_count','generated_module_count','observed_generated_gates','test_cases','expected_invalid','metrics','full_vs_matched_disagreements')},indent=2))
if __name__=='__main__':main()
