# InferenceNode architecture and implementation design

Version 0.2, November 18, 2026. Status proposed. Supersedes the supplied v0.1
sketch. Implementation and verification are pending.

## Purpose

Add bounded inference over authorized records and explicitly registered rules.
Every conclusion carries a replayable proof. Report entailment relative to the
premises and rules, scoped counts, or qualified candidate explanations.

## Existing implementation and reuse

The main graph in `src/cpu_llm/pipeline.py::_compile` registers 27 nodes.
It has source span, thinking, grammar and audit stages, but no single
source-span/conflict-review node matching the original proposal.
`semantic.py` defines AnswerRequest, AnswerDecision and ProofSpan.
`prompt_intent.py::select_channel_answer` already implements universal
membership joins. `abductive_bridge.py` compares sourced numeric bounds and
proposes unverified mediating variables. Reuse these contracts and consolidate
compatible join behavior behind a shared inference service.

Strict evidence, research and specialist requests have separate entry paths.
Registering graph node inference alone cannot cover all those paths. The
integration must explicitly enumerate the supported callers.

## Input and trust boundary

The engine obtains caller identity, authorized source scope and snapshot time
from the application context. Source restrictions are applied before inference
or rule retrieval. Prompt text cannot grant source access or register a trusted
rule.

A grounded predicate contains an immutable predicate ID, normalized entity IDs,
relation, object or typed value, polarity, quantifier scope and temporal scope.
Its source reference contains document/chunk ID, source version, exact quote,
character offsets and content hash. Validate both quote integrity and the
predicate's semantic binding to the quote through an approved extractor.
Reject arbitrary user-supplied triples paired with unrelated quotations.

Rules contain an immutable ID and version, provenance, author or registry
authority, applicability scope, typed variables, antecedent patterns and a
consequent pattern. Each instantiated rule binds its variables explicitly.
Declare relation properties such as asymmetric or irreflexive separately.
Validate rule safety and supported forms when registering the rule.

## Supported rule forms and initial scope

First implement direct predicate matches, same-relation transitivity, and
universal membership joins. Examples:

```text
greater_than(x, y) AND greater_than(y, z) -> greater_than(x, z)
member_of(x, c) AND every_member_has(c, y) -> has(x, y)
```

Transitivity is available only for a relation explicitly declared transitive.
Membership inheritance requires a universal source rule. Average, some,
conditional or historical statements retain their restrictions.

Symmetry, inverse relations, multi-precondition causal rules and broader
aggregation follow only after their semantics and regressions are implemented.
Unsupported rule forms return a reason.

## Deduction and proof receipts

Perform deterministic bounded closure over eligible verified predicates and
registered rules. Use stable predicate and rule IDs to order traversal and
resolve equal-cost proofs. Maintain a visited state keyed by instantiated
predicate, polarity and scope to prevent cycles. Direct evidence remains
eligible even when the relation has a transitive rule.

Each proof step records its input predicate IDs, instantiated bindings, rule
ID/version and derived predicate ID. Leaf steps identify exact source spans.
This forms a proof DAG rather than a list of quoted edges. A separate verifier
replays the DAG and checks every rule application, source binding and scope.

Use ENTAILED_BY_RULES as the public meaning of a successful deduction. If an
internal compatibility label PROVEN is retained, document that it is relative
to the supplied premises and rules. Present the conclusion as derived text and
the leaves as quotations. Exact-quotation APIs keep the original source text.

## Conflict handling

Represent explicit negative predicates. Reversed edges establish conflict only
when the registered relation semantics require asymmetry. Check both source
premises and derived conclusions for conflicting facts or derivations under
compatible entity, unit, temporal and quantifier scope.

Return the affected proof and both sides of the conflict. Unrelated conflicts
do not halt every query. Equivalent source duplicates preserve provenance.
Superseded records follow the existing temporal rules. Absence of a predicate
is unknown unless a declared closed-world policy applies to that population.

## Scoped aggregation

Require a complete, authorized population manifest with record identity and
snapshot version. Record eligibility, exclusion reasons, duplicate/version
policy and treatment of missing attributes. Deduplicate by the population's
logical record key rather than chunk count.

Return integer numerator and denominator, with exact rational coverage.
Report missing, contradictory and exception counts separately. Even 100 percent
coverage licenses only a statement about that declared snapshot. It does not
create a universal domain rule. Replace the ambiguous min_record_support
setting with an explicit output selection policy. Lower coverage can still
produce exact counts.

## Candidate explanations

Backward-chain only through registered causal implication rules. Track each
candidate's satisfied, refuted and unknown preconditions, source proof and
alternative candidates. An observed effect alone never proves its cause.
Eliminate refuted candidates and ask questions that distinguish surviving
candidates. Retrieval channel scores may rank candidates for inspection.

Reuse the existing abductive claim status UNVERIFIED_HYPOTHESIS and extend its
receipt for causal candidates. In strict mode, emit qualified clarification
or a nonanswer under an explicit application policy. Never publish a candidate
cause as an entailed conclusion.

## Budgets and deterministic outcomes

Configure limits for input records, rules, hops, visited states, generated
predicates, candidates, elapsed time and receipt size. Define a hop as one rule
application, independently of the number of source leaves.

Outcomes include entailed, conflict, insufficient support, scoped summary,
candidate explanations, unsupported rule and budget exhausted. A truncated
search cannot establish that no proof exists. Record the limiting resource.
Deterministic ordering is guaranteed for complete runs with the same inputs,
rules and configuration. Time-limited partial results may vary by machine and
must be labeled accordingly.

## Canonical audit record

Hash canonical UTF-8 serialization of the schema version, mode, requested
target, authorized scope identifier, snapshot, rule versions, premise IDs and
hashes, result, proof DAG, aggregation metrics, candidates, policy, configured
budgets and completion reason. Canonicalize sets and typed values and reject
non-finite numbers. Preserve the audit record with its digest. A digest detects
record changes; it does not establish source truth or identity.

## Pipeline and delivery

```text
Authorized snapshot and source-bound predicates
  -> bounded inference service
  -> independent proof/conflict verification
  -> existing AnswerDecision and evidence receipts
  -> existing realization, final judge and delivery
```

Determine the exact graph insertion point during implementation by tracing
which state contains verified predicates and where each route performs final
judgment. Add inference as graph node 28 only after adapting those state
contracts and flag consumer validation. Strict mode derived assertions require
an explicit policy and proof-verification gate. Strict source quotation keeps
its existing output contract.

Initially expose an explicit inference request option with validated mode and
rule selection. Natural-language routing should target only recognized forms.
Induction and abduction need their own explicit triggers and ambiguity policy.
Record the selected mode and executed node in routing receipts. Factual
lookups retain the existing path when inference adds no supported operation.

Attach conclusions and proof leaves to the existing evidence panel. Research
workspace cards carry explanatory candidates and their missing preconditions.
PrismLexicon and tone rendering preserve proof text, quantities, modality and
epistemic labels. Follow-up turns retain scoped context, and corrections or
source deletion invalidate dependent proofs. Cache keys include caller scope,
snapshot and rule versions.

## Acceptance tests and release gates

- Direct match, two-hop ordering and universal membership join.
- Missing intermediate premise, unknown relation and unsupported rule.
- Negative conclusion, asymmetric reversal and contradiction derived through
  another chain. Include an unrelated conflict that does not affect the query.
- Invalid source offsets/hash and a quote that does not support its triple.
- Historical corrections, revoked access, cross-tenant inputs and deleted
  sources. No inaccessible span may appear in conclusions or diagnostics.
- Aggregation with missing fields, duplicates, mixed versions, empty population
  and complete coverage restricted to the declared snapshot.
- Abduction with satisfied, unknown and refuted preconditions and multiple
  candidate causes.
- Cycles, each resource cap and explicit incomplete outcome.
- Input reordering produces identical complete results and canonical hashes.
- Final delivery retains the verified conclusion, citations and uncertainty.
- Existing direct answers, research paths and strict quotations pass regression.

Benchmark deduction success, proof replay validity, scope isolation, conflict
detection, aggregation count accuracy and qualified explanation behavior.
Report coverage and abstention separately. Measure latency and memory under
declared record and rule sizes. Keep the feature gated until these checks pass.

## Open implementation decisions

Select the predicate extractor forms, rule registry persistence, default
resource limits and strict-derived-answer policy before implementation.
Define the first aggregation population manifest adapter and causal rule
schema before enabling those modes. No schema migration is justified until
the existing storage and source version contracts have been inspected.

## Initial implementation

The experimental deductive service is implemented in `cpu_llm.inference`.
The versioned built-in registry supports `bigger_than.transitive.v1` and
`membership.possession.v1`. Explicit source clauses are the only predicate
input. The request cannot register rules or supply arbitrary source triples.

Use `Infer whether the elephant is bigger than the cat.`, or pass
`inference={"subject": "elephant", "relation": "bigger_than", "object": "cat"}`
to `ask` or the HTTP ask endpoint. The caller's authorized temporal snapshot
is read once. The result includes an inference receipt with a proof DAG,
input digest, rule versions and audit hash. Successful assertions use
`derived_inference`, with leaf citations in the normal evidence panel.
Strict Evidence Mode returns unsupported for this operation.

Graph node 28 is registered between spans and think. Its adapter accepts only
a validated internal request and reuses the service's deduction engine over
the graph's permitted passages. Ordinary graph requests leave the stage idle.
The explicit public route uses a full authorized snapshot before the ordinary
graph, so top-k truncation cannot silently define its proof population. Its
receipt records inference as a dispatch stage. This is an explicit routing
choice for the first implementation.

A hop is a rule application above its deepest premise. Direct facts have depth
zero. The API caps predicates at 256, generated states at 1,024 and pair
comparisons at 100,000. Budget exhaustion returns partial. A hop-limited
nonanswer explicitly describes the bounded search. There is no source or
inference cache.

Inductive population manifests, causal candidate explanations, user-managed
rule registries, automatic question classification and strict derived-answer
policies remain pending. The implementation does not enable these modes.

## Validation recorded for the initial implementation

170 focused tests passed across inference, flag routing, existing answer
selection, attribute repair, access-related design contracts, research and
PrismLexicon. The inference regressions include proof tampering, document
changes, input ordering, scope and snapshot isolation, contradictory premises,
unsupported qualifiers, and resource caps.

A disposable PostgreSQL/pgvector run ingested five synthetic source chunks.
It returned two cited deductions (ordering and membership), a missing-support
nonanswer, and an ordinary cited color lookup. A restricted caller could not
complete the ordering chain, and adding an explicit negative premise changed
the result to conflict. Local results are in
`build/inference-live/results.json`. This validates the implemented subset;
the remaining modes and the complete repository suite remain release gates.
