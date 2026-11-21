# Abductive–deductive reversal design review

Date: 2026-11-19. Code baseline: `65ce600`.
Status: proposed design review; no runtime implementation is added by this document.
Original supplied specification: [preserved source](reversal-inference-original-spec.md).
The corrections are now incorporated into the [revised architecture](reversal-research-design.md)
and [implementation tracker](reversal-research-spec.md). Those remain proposed;
they do not describe an active runtime service.

## Intended capability

The proposal adds an explicit research cycle: collect possible explanations,
test their necessary consequences against accepted observations, preserve
disputed clues, and rank surviving explanations by their documented coverage.
This could produce a more useful comparison than returning only a research
question when a candidate model cannot satisfy the selected constraints.

The main new behavior is orchestration and traceable candidate elimination,
quarantine and projection. Consequences derived from a candidate are conditional
predictions; matching them to observations is abductive assessment. It is not a
proof that the candidate is true or a new general inference calculus.

## Existing components to reuse

- `inference.py`: authorized, versioned source context, bounded registered rules,
  contradiction-aware receipts and independent replay.
- `AbductiveBridgeNode`: existing domain-bound tension analysis and structured
  comparison of declared explanation alternatives. Extend this contract rather
  than introducing a competing generic abduction implementation.
- `cross_domain_claims.py`: exact interval comparisons with units, conditions
  and conventions. Reuse for comparable numeric premises.
- `constraint_evaluator.py` and trusted model adapters: numerical feasibility and
  parameter scans. They supply actual model predictions; descriptive source text
  cannot substitute for these computations.
- `invention.execute_invention`: combined research coordinator and single scoped
  snapshot. Nammade supplies passage comparisons, not truth certification.

Keep explicit full-scope research separate from ordinary retrieval. The recent
removal of implicit full-KB inference scans should not be reversed.

## Required design corrections

### 1. Quarantine contradictions before irreversible elimination

The proposed order applies Modus Tollens before identifying disputed hard facts.
If a candidate requires P, a record says not-P, and another record says P, the
candidate can be eliminated before not-P is demoted. The result depends on order.

Normalize and classify premises, detect same-context conflicts, apply the
application's trust policy, and only then select the hard premise set and prune.
Distinguish immutable application axioms from observational records. Conflicting
immutable axioms require an inconsistent-model result; witnesses cannot silently
demote application axioms. Elimination is relative to the run's model, assumptions
and snapshot, and can be reconsidered in a later run with revised evidence.

### 2. Evidence authenticity is different from factual certainty

Offsets and hashes verify that text came from a record. They do not establish
its truth. Lack of another contradictory source does not make a record hard
validated knowledge. A default source confidence of 1.0 has no calibration.

Specify application-owned evidence admission criteria. Prefer an accepted-premise
label scoped to the run. If retaining CERTAINTY for compatibility, explicitly
limit its meaning to accepted premises under stated assumptions. Separate fact
validation status, candidate lifecycle and synthesized-claim type.

### 3. Necessary consequences require typed, sourced rules

`necessary_conditions: Dict[str, Any]` and consequence strings do not specify how
the engine establishes implication, negation, compatible units, context or
exceptions. Similarity and Nammade span matching cannot establish these rules.

Require typed predicates and operators, rule IDs/versions, variable bindings,
assumption and context IDs, and source-bound premises for each derivation. Keep
source text non-executable. Typical associations cannot be used as necessary
consequences for Modus Tollens. Unsupported clauses remain unsupported.

### 4. Apparent tensions and logical contradictions differ

Two bounds at different velocities are not contradictory propositions. They
become incompatible only under an added constant-cross-section model assumption.
Keep observation conflicts separate from model-conditioned incompatibility.

Likewise, an animal possessing claws, claws being retracted, and claw marks being
visible are different predicates. They cannot be substituted for each other.
Two opposed reports about the same impression cannot both be validated merely
because the animal has retractable claws.

### 5. Reconciliation needs a contextual proof

A mechanism M resolves opposed claims only if sourced or explicitly assumed
contexts X and Y make the two observations compatible and the registered model
derives each conditional consequence. Do not invent different ground conditions,
times or locations to earn reconciliation points.

When those contexts are unknown, output a proposed reconciliation and a test;
the original conflict remains unresolved. Distinguish explained-under-model,
proposed-reconciliation and independently-validated outcomes.

### 6. Unknown is not false

A finite KB does not justify treating missing observations as negative evidence.
Missing canopy-breakage or mud-depth text cannot be counted as an observed
absence without a detection/coverage assumption. Preserve unknown states. Query
assumptions also need to remain distinct from authenticated observations.

### 7. Full-scope coverage needs a retrieval contract

`run(query, spans)` can inspect supplied spans but cannot establish that every
authorized chunk in a domain was retrieved. `domain_name` must not grant access.
Require tenant/caller scope, an as-of snapshot, source manifest, unique chunk
IDs, expected/scanned counts, byte and candidate budgets, and completeness status.

Nammade currently returns bounded comparisons; its selected spans cannot certify
an exhaustive domain scan. Use a complete authorized snapshot or paginated
snapshot provider, then run comparisons without dropping premises. Existing
snapshot caps require partial/unsupported outcomes, not a completeness claim.

Count unique chunks rather than spans. The example with 75 spans sharing one
document ID cannot establish 75 distinct chunks without chunk identifiers.

### 8. A pre-execution alert needs actual transport support

For callbacks, perform an authorized scope count and emit the notice before
inference scanning. Supplying an already-materialized span list means retrieval
has already happened. The notice must accurately identify which work remains.
The current synchronous HTTP response cannot deliver a live progress banner
before completion without a preflight, streaming or job mechanism. A final
receipt's alert is not a live notification.

### 9. Scores are heuristics, not probabilities

Retain policy-versioned, finite nonnegative weights and exact decimal scoring.
De-duplicate observations, conflict pairs and supporting spans. The proposed 7.0
score rewards both a reconciled pair and its two clues; explicitly document that
as intentional weighting or choose nonoverlapping counts.

More source chunks do not imply independent evidence. Distinct-span density can
reward duplicate/correlated content. Preserve semantic ties; lexicographic IDs
can stabilize display order without making one tied model scientifically better.
Use highest-ranked-under-policy rather than an unqualified Most Possible label.

### 10. Termination and complexity contracts need limits

Distinguish no candidates extracted, unsupported model, all candidates falsified,
inconsistent premises and incomplete search. An empty extracted pool is not a
falsification trace. Incomplete scans must not declare a globally best candidate.

Add caps for rows, bytes, candidates, clues, rules, pairs, traversal depth and
operations. Candidate-to-clue projection can use indexed lookups, but enumerating
all contradictory pairs can produce quadratically many output pairs. The blanket
O(N*M) promise does not account for that output or deterministic sorting costs.

### 11. The schemas do not yet enforce the logical contracts

Add exact source offsets/hashes/versions, chunk IDs, typed predicates, contexts,
trust/admission policy, rule provenance, model parameters and tolerances,
completeness/budget reasons, score-policy versions and replay hashes. Validate
unique IDs and references, finite numeric values and disjoint outcome sets;
forbid unknown fields. Pydantic frozen models do not freeze nested mutable data.

An exhaustive full-scope reader and deterministic predicate/rule extraction
adapter are both missing from the proposed `run` interface. These are required
implementation components, not details that can be inferred from the examples.

## Scientific and benchmark corrections

- The animal example introduces pad geometry, sinkage and canopy observations
  after the initial inputs. Put every observation, context and rule into the
  fixture before execution. Label anatomical/mass mappings as synthetic unless
  sourced; impression area alone does not supply the stated mass implication.
- The 0.1 cm²/g cluster-density preference in the saved PDG review should not be
  relabeled as a Bullet Cluster-specific measurement. Its source, observable,
  assumptions, regime and uncertainty must remain attached. See
  [PDG 2024, section 27.4.2](https://pdg.lbl.gov/2024/reviews/rpp2024-rev-dark-matter.pdf).
- The VD-SIDM example needs sigma0, v0 and b values and an actual computation to
  produce the quoted 2.0 and 0.05 results. Cross-section values alone do not
  compute galaxy core radii or merger offsets; those require model adapters/data.
- Separate synthetic logic fixtures with stipulated bounds from real literature
  integration tests. The expected winner cannot be encoded as a hard-coded
  species/model name or a preselected score.

## Recommended execution sequence

1. Validate an explicit research request, permissions, snapshot and scan budget.
2. Emit scope notice using an authorized count/provider contract.
3. Collect premises and source-backed candidate/model definitions completely.
4. Normalize contexts and quarantine contested observations under a trust policy.
5. Apply registered necessary-consequence rules to the accepted hard premise set.
6. Record candidate falsifications with replayable proofs.
7. Project conditional predictions onto remaining clues; keep unknowns explicit.
8. Score supported explanations and proposed reconciliations separately, preserving
   ties, completeness status and policy assumptions.
9. Return labeled hypotheses, unresolved inputs and distinguishing experiments.

The integration should be an opt-in research strategy coordinating existing
services. Natural-language triggers require an explicit request for alternative
explanations or candidate elimination; ordinary questions retain retrieval-based
answering. Existing strict-evidence behavior remains unchanged.

## Acceptance tests to add before release

- Opposed observations are quarantined before they can eliminate a candidate.
- Different-time/regime observations are not labeled direct contradictions.
- Unknown contexts cannot earn a resolved-conflict reward.
- Missing observations cannot supply a hard negative or an absence penalty.
- Typed rule violations eliminate candidates; mere similarity never does.
- Empty extraction, total elimination and resource caps have distinct statuses.
- Duplicate spans/observations cannot inflate the ranking; semantic ties survive.
- Reordered inputs reproduce the same trace; tampered source/rule inputs fail replay.
- Scoped counts and notices expose no inaccessible data; count spans vs chunks.
- Whole-domain coverage beyond Nammade's comparison limit is checked explicitly.
- Both synthetic constant/velocity-dependent fixtures and sourced physics cases
  keep their assumptions and provenance, including unknown model computations.
