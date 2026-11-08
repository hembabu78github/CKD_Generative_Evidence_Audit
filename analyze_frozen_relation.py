import csv,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent
up=(ROOT/'dependencies/evidence_grounding_core') if (ROOT/'dependencies/evidence_grounding_core').exists() else (ROOT.parent/'evidence_grounding_core')
src=up/'results/delay_relation_screen.csv'
rows=list(csv.DictReader(src.open()))
transitions=Counter((r['source_action'],r['delayed_action']) for r in rows)
failed=[r for r in rows if r['preserve_or_abstain'].upper()=='FALSE']
report={'n_pairs':len(rows),'frozen_oracle_true':len(rows)-len(failed),'frozen_oracle_false':len(failed),
        'transition_counts':{a+' -> '+b:n for (a,b),n in sorted(transitions.items())},
        'false_transition_counts':{a+' -> '+b:n for (a,b),n in sorted(Counter((r['source_action'],r['delayed_action']) for r in failed).items())},
        'false_case_ids':[r['patient_id'] for r in failed],
        'interpretation':'A previously available latest observation becomes unavailable after 3-day delay. A correctly implemented as-of policy can change MONITOR to REVIEW or REVIEW to MONITOR without abstaining. A preserve-or-abstain universal oracle is therefore not justified for this policy. These are semantic-oracle mismatches, not demonstrated CDS software defects.',
        'resolution':'Do not alter frozen MR. Mark not clinically validated; seek independently reviewed policy-specific conditional relation or use independently specified as-of evidence-trace oracle as distinct experimental endpoint.'}
(ROOT/'results/frozen_relation_failure_analysis.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
