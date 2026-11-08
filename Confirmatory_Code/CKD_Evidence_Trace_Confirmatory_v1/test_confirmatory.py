import json, pathlib, tempfile, unittest
from confirmatory import expected,prepare,score,readj
ROOT=pathlib.Path(__file__).resolve().parent
class ContractTests(unittest.TestCase):
 def test_prepare_and_hidden_answers(self):
  with tempfile.TemporaryDirectory() as td:
   items=prepare(ROOT/'frozen_baseline_manifest.jsonl',pathlib.Path(td))
   self.assertEqual(len(items),300)
   prompts=readj(pathlib.Path(td)/'model_prompts.jsonl')
   self.assertEqual(len({x['case_id'] for x in prompts}),300)
   self.assertFalse(any('expected_' in x for x in prompts))
   self.assertTrue(all('decision_basis_ids' in x['system_prompt'] for x in prompts))
 def test_score_perfect_fixture_does_not_claim_llm(self):
  with tempfile.TemporaryDirectory() as td:
   out=pathlib.Path(td);items=prepare(ROOT/'frozen_baseline_manifest.jsonl',out)
   rows=[{'case_id':x['case_id'],'response':json.dumps({'action':x['expected_action'],'all_eligible_ids':x['expected_all_eligible_ids'],'decision_basis_ids':x['expected_decision_basis_ids']})} for x in items]
   with (out/'test_responses.jsonl').open('w') as f:
    for r in rows:f.write(json.dumps(r)+'\n')
   result=score(out/'evaluation_manifest.jsonl',out/'test_responses.jsonl',out/'score')
   self.assertEqual(result['overall']['full_eligible_trace_exact'],300)
   self.assertEqual(result['overall']['decision_basis_exact'],300)
 def test_invalid_and_omission(self):
  with tempfile.TemporaryDirectory() as td:
   out=pathlib.Path(td);items=prepare(ROOT/'frozen_baseline_manifest.jsonl',out)
   x=items[0];missing=x['expected_all_eligible_ids'][1:-1]
   with (out/'responses.jsonl').open('w') as f:f.write(json.dumps({'case_id':x['case_id'],'response':json.dumps({'action':x['expected_action'],'all_eligible_ids':missing,'decision_basis_ids':x['expected_decision_basis_ids']})})+'\n')
   result=score(out/'evaluation_manifest.jsonl',out/'responses.jsonl',out/'score')
   self.assertEqual(result['overall']['full_eligible_trace_exact'],0)
   self.assertEqual(result['overall']['missing_evidence_cases'],1)
   self.assertEqual(result['missing_responses'],299)
if __name__=='__main__':unittest.main()
