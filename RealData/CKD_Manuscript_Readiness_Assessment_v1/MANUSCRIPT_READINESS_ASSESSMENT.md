# CKD evidence-grounded assurance — manuscript readiness assessment

**Prepared:** 2026-11-08  
**Status:** Completed evidence consolidation and editorial feasibility assessment, **not** an acceptance prediction, clinical validation, or new model experiment.  
**Artifact and naming policy:** Publication-venue-neutral. No source datasets or patient-level records are redistributed in this report.

## Executive verdict

**Suitable as a bounded systems/engineering research submission after substantial revision; not submission-ready for a collection requiring intervention-effect estimation or clinical decision effectiveness.** The reproducible engineering findings are real, but the currently completed comparisons fail to demonstrate superiority over a conventional implementation receiving equivalent requirements. The appropriate distinctive claim is **conservative, provenance-closed generation and auditability of executable evidence-policy checks**, not superior CDS accuracy, clinical safety, or causal inference.

## Evidence register: independently checked packages and limits

| Study block | Verified evidence | Permissible manuscript statement | Prohibited inference |
|---|---|---|---|
| RC1 CKD KG-to-MR compiler | 12 fixture-derived candidates; 12 modules; eight gate PROCEED and four ABSTAIN; 291/291 unit tests pass | Frozen compiler can assemble/validate constrained candidate relations and apply execution gates to controlled fixtures | Clinical correctness of the 12 propositions; use of theorem prover; external clinical validation |
| Grok original and confirmatory | 300 responses in each; same 100 synthetic patients x 3 conditions; action match 300/300 both; exact eligible-trace 208/300 then 300/300; independently audited confirmatory hashes | Revised explicit *dual evidence trace* response contract is associated with complete trace match on previously used synthetic scenarios | Independent blind replication; 600 independent patients; proof of improved clinical outcomes or reduced hallucinations generally |
| Tawam source audit | 491 hospital-derived records, 25 source fields; 485 positive-follow-up cohort, 56 events | Usable for real-world baseline covariates, missingness and engineering robustness | Availability of longitudinal event-level lab records; empirical observation of reporting delays |
| NHANES 2021–23 audit | 11,933 demographic records; 5,552 adults with serum creatinine, urine albumin and urine creatinine | Kidney-related cross-sectional input validation and representational diversity | Longitudinal CKD progression; unweighted population prevalence conclusions |
| MIMIC-IV Demo v2.2 audit | 100 deidentified real hospital patients; 3,003 item-50912 serum creatinine rows; 98 patients with at least three distinct measurement timestamps | Real-record temporal parsing and controlled injected fault testing | Broad representative CKD outcomes; clinician-visible timestamp from storetime |
| MIMIC temporal pilot | 600/600 engineered self-checks across 100 patients | Local software self-test passed under stated injection/oracle rules | Independent detection ability, clinical decision accuracy |
| MIMIC compiled MR comparator | 98 patient trajectories, 294 cases; fixture-compiled auxiliary-invariance MR detected 98/98 engineered auxiliary-coupling faults; ordinary enhanced validator did likewise; trace validator detected 98/98 future-leak faults | MR and trace checks reveal distinct classes; complete conventional check can cover both | KG/MR outperforms enhanced conventional code; validates CKD decisions (toy parity target) |
| Matched static candidate validation | 12 controls + 117 known invalid single-field variants; RC1 validator and requirements-matched conventional validator both 117/117 reject and 0/12 controls flag; thin baseline 12/117 | Complete requirements explain detection improvement over thin operator-only checks; cross-platform reproduction succeeds | Intrinsic KG compiler superiority; end-to-end generation evaluation |

## The five claims most defensible today

1. A bounded source- and provenance-aware pipeline produces executable candidate relations from controlled CKD-related knowledge fixtures, with explicit execution-admissibility gates.
2. Static validation and deterministic replay are reproducible across the recorded environments and release artifacts.
3. Evidence-availability and provenance assertions can be checked on timestamped, de-identified *real-derived* hospital laboratory data, while faults are deliberately injected in software.
4. Structured LLM action agreement and *complete evidence-trace agreement* are distinct endpoints; the exact output contract matters.
5. Conventional checks supplied with equivalent semantic requirements can match the frozen KG/MR validator's performance; improvement cannot be attributed simply to the KG representation.

## Critical gaps, ordered by impact

| Priority | Gap | Decision / remediation | Status |
|---|---|---|---|
| P0 | Narrow AEGIS intervention/counterfactual scope | No patient outcome counterfactual, treatment-policy evaluation or causal estimand. Reframe as systems/assurance, or secure editorial fit confirmation before special-collection submission | OPEN (editorial) |
| P0 | Clinical source governance | All 12 fixture candidate source propositions unreviewed; permissions and clinical appropriateness unestablished | OPEN (domain expert) |
| P0 | Fair novelty evidence | No independent end-to-end KG-to-MR versus equally specified rule-to-template compiler benchmark, no blinded expert effort measure | OPEN (research) |
| P1 | Manuscript version mismatch | Current revised manuscript reports Phase-1 controlled fixture benchmark only and describes no patient data; later Tawam/NHANES/MIMIC/Grok evidence is in separate packages | OPEN (writing) |
| P1 | Related-work and distinctness | Differentiate KG-to-MR JAR-rejected manuscript, Discover Computing temporal CKD paper and other published/under-review work; disclose reused infrastructure and avoid dual publication | OPEN (author disclosure) |
| P1 | Reproduction archive | Assemble deterministic scripts, dependencies, source IDs, execution metadata, version/hash manifest and availability statements. Do not redistribute secondary patient-level data where the original repository/license should instead be cited | PARTIAL |
| P1 | Clinical terms | Explicitly label model's 20% decline as synthetic engineering reference, MIMIC storage time as database proxy, 'intervention' as information-input perturbation | REQUIRED WRITING CHANGE |
| P2 | Model external validity | Current Grok results reuse same synthetic patients; held-out/second model not completed | OPTIONAL unless claiming generality |

## Recommended manuscript architecture (systems track)

1. **Problem and novelty:** How to compile auditable, bounded evidence-policy tests when temporal context and source governance are incomplete.
2. **Source semantics:** Versioned provenance fields, UNKNOWN/ABSTAIN behavior, deterministic transformation library and the non-invention principle.
3. **Method:** Compiler contract and traceability; add exact delineation of oracle, generated test, and clinical rule.
4. **Evaluation A — compilation:** Frozen RC1 12 candidate fixtures; 291 unit tests; 8/4 gate decisions; deterministic replay.
5. **Evaluation B — comparison:** Requirements-matched static 129 cases and honest equivalence; thin baseline interpreted as a requirements ablation.
6. **Evaluation C — real-derived engineering:** 98 MIMIC trajectories, 294 scenarios and local temporal pilot; clear toy target and injected fault caveat.
7. **Evaluation D — generative evidence-grounding:** Original versus confirmatory 300 prompts each, with reused patients and revised response contract; framed as complementary demonstration, not KG compiler superiority.
8. **Sensitivity/limitations:** No real clinical decision oracle, no patient benefit or interventional counterfactual, possible selection/prompt optimization, limited MIMIC demo, source expert review outstanding.
9. **Reproducibility/disclosure:** Source datasets cited but not republished; versioned code; reproducible commands; ethics/data-use/copyright as applicable.

**Paper-scope caution:** A manuscript containing A–D may become unfocused and face overlap risks. Before writing the final version, determine whether D is a concise downstream feasibility demonstration or belongs in a separate paper. The existing manuscript is Phase-1-centered. Do not automatically append four new experiments or imply the Phase-1 paper includes real patients without updating Methods, Results and Ethics.

## Immediate author decisions / required human actions

**Action A — Before clinical validity claims or final submission:** Ask a nephrologist/clinical informatician to review the candidate CKD policy propositions and adjudicate which are valid for the intended population and temporal settings. Do not portray the current `UNREVIEWED` fixtures as clinically authorized.

**Action B — Before journal targeting and submission:** Choose whether to submit the honest systems-assurance paper to the JHIR regular systems track or to seek a scope opinion from the AEGIS special-collection editors. The latter seeks intervention-focused/causal evidence not presently demonstrated. This action need not block engineering manuscript drafting.

**Action C — Before submission:** Author confirmation of prior manuscripts submitted/published that overlap the CKD temporal robustness work and the previously rejected KG compiler manuscript, so overlapping text/data and novelty can be declared correctly. External manuscript status is not inferred from local files.

**No user action required for today's consolidation.** No additional repeat runs, downloads, or API fees are recommended solely for manuscript readiness.

## Next research decision gate

Proceed with a **single prespecified end-to-end matched compilation study only if the paper's primary claim is that KG-driven compilation improves test generation**. That requires the same independently evaluated source propositions and acceptance contract for KG and conventional generator, a held-out expert-blinded review of emitted MRs, and measured time/coverage/provenance. If those inputs cannot be secured before the deadline, narrow the paper to a defensible engineering feasibility/equivalence report or choose a better-fit venue. Do not fabricate superiority.

## Source and venue policy notes

The *Journal of Healthcare Informatics Research* is described as covering analytics, systems and human factors research in healthcare informatics (journal overview: https://institute4hi.org/wp/publications/journal/). An advertised AEGIS-themed collection focuses on causal healthcare AI and interventional systems (https://www.linkedin.com/posts/ieeeichi_check-out-this-special-opportunity-under-activity-7474560909906956288-ZhU1). Exact submission conditions and deadline should be confirmed from an official collection page before submission.

Springer Nature describes Data Availability and Code Availability expectations and advises authors not to re-share external secondary data; instead cite original sources and describe access terms (https://www.springernature.com/gp/authors/research-data-policy/journal-policies/15369670 and https://springeronlineservice.freshdesk.com/en/support/solutions/articles/6000237604-data-my-journal-expects-me-to-share). See journal-specific submission guidelines for additional requirements.

## Audit provenance

This assessment uses reports and zip archives available in this conversation's working container as of 2026-11-08, without executing new model evaluations or independently adjudicating medical correctness. The appended machine-readable manifest lists the source files and their SHA-256 digests. Source files are intentionally excluded from the deliverable.
