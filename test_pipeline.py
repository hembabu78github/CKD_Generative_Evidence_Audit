import json,tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from evaluate_llm import manifest,score

class EvaluationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.items=manifest(5)
 def test_conditions(self):
  self.assertEqual(len(self.items),15)
  self.assertEqual({x['condition'] for x in self.items},{'source','delayed_3d','delayed_with_pending_notice'})
 def test_fixture_results(self):
  a=[{'case_id':x['case_id'],'response':{'action':x['expected_action'],'used_ids':x['expected_used_ids']}} for x in self.items]
  _,s,_=score(self.items,a)
  self.assertEqual(s['action_matches'],15);self.assertEqual(s['trace_exact_ordered'],15)
 def test_detect_unavailable_leak(self):
  x=next(x for x in self.items if x['condition']=='delayed_3d')
  r={'case_id':x['case_id'],'response':{'action':x['expected_action'],'used_ids':x['expected_used_ids']+[x['selected_delayed_observation_id']]}}
  _,s,_=score([x],[r]);self.assertEqual(s['unavailable_evidence_use_cases'],1)
 def test_detect_invalid_response(self):
  x=self.items[0];_,s,_=score([x],[{'case_id':x['case_id'],'response':'non-JSON'}]);self.assertEqual(s['schema_valid'],0)
 def test_missing_denominator(self):
  _,s,ids=score(self.items,[]);self.assertEqual(s['missing_responses'],15);self.assertEqual(len(ids),15)
 def test_pending_value_not_exposed(self):
  for x in self.items:
   if x['condition']=='delayed_with_pending_notice':
    q=json.loads(x['user_prompt']);v=[r for r in q['observations'] if r['id']==x['selected_delayed_observation_id']]
    self.assertEqual(v[0]['status'],'PENDING_NOT_AVAILABLE');self.assertNotIn('egfr',v[0])
 def test_duplicate_rejected(self):
  x=self.items[0];a={'case_id':x['case_id'],'response':{}}
  with self.assertRaises(ValueError):score(self.items,[a,a])
if __name__=='__main__':unittest.main()
