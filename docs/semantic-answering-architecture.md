# General semantic answering architecture

Proposal, 2026-10-27. Design only; no implementation or demonstrated accuracy is
implied. This is the architectural basis for the
[implementation plan](benchmark-v2-improvement-design.md), not an additional list
of benchmark-specific exceptions. Benchmark subjects and expected strings must
never enter runtime parsing, extraction, routing or decision rules.

## Problem and governing invariant

The current library has useful components: source ingestion, dense retrieval,
six-channel signals, explicit facts, bounded joins, conversation state, specialist
producers and evidence checks. Their interpretations are not fully unified.
Question-form regexes, event frames, source extractors, reply selection and the
delivery judge can disagree about what is being asked or what a sentence proves.

The governing invariant is: **every delivered factual claim must answer a declared
part of the request and carry an applicable, authorized, temporally valid proof.**
A relevant passage is a candidate. A source sentence is an assertion. A proof
licenses a bounded conclusion. A rendered response presents that conclusion.
These are four different objects. No similarity score or successful audit can
substitute for a missing step.

Checked against `ir/schema.py`, the reply path, and the fresh v2 measurement.
`EIRProposition` is one epistemic proposition. It is not the four records above.
Its quantifier is all/some/none/exactly/bounds, with no aggregate. Its object is
a typed entity, not a measurement, interval, or statistical value. It has a
source span and a derivation trace, and no separate proof or answer decision.
`compose_reply` still lets the event frame, the summary, the channel assessment,
and an audited sentence compete, and the public evidence list is chosen again
from the spoken text. That race is what the shadow path in section 8 must log.
The fresh run's main miss was a retrieved sentence that never became cited proof,
plus a parent marked complete while a child's requested relation was a place.

## 1. Shared intermediate representation

Create a typed semantic IR with separate request, source-assertion, proof and
answer-decision records. Build on `ir/schema.py`, proposition storage and frame
records through adapters; assess their representational gaps before extending
them. Do not create a new parallel database simply because the types are new.

All records have schema/version, stable IDs, producer version and provenance.
Source assertions preserve exact spans, document/version, scope and valid-time
intervals. Parsing confidence is extraction metadata, not factual truth.

A request contains task ID, speech act, target entity/sense candidates, requested
predicate/roles, constraints, polarity, quantifier/statistical scope, time context,
requested coverage and presentation plan. Source assertions contain corresponding
role/value fields, units, modality, quantifier and conditions. Preserve unresolved
fields explicitly. A value can be an entity, literal, measurement, interval or
statistical aggregate; do not collapse them to an untyped string.

For example, `average(lifespan, group)` differs from `lifespan(individual)`.
`has_part(A, B)` differs from `has_part(B, A)`. `not P` differs from missing P.
An asserted possibility differs from a universal rule. A source-specific alias
has a provenance boundary and does not automatically merge all matching names.

One parser service owns the request IR. Existing channel/answerability/frame
parsers become adapters emitting candidates into it. Disagreement creates an
explicit unresolved interpretation, not a race where the last producer wins.

## 2. Prompt understanding as a bounded compiler

Process a prompt in ordered stages:

1. Enforce caller access and raw-input guards.
2. Separate instructions, explicit background, quoted/code data and presentation.
3. Segment supported tasks; record spans, order and dependencies.
4. Resolve references using prior user context and explicit bindings.
5. Parse each task into semantic candidates and select a producer by capability.
6. Ask the minimum useful clarification when materially different readings remain.

Sentence length does not determine task count or response length. A long background
may yield one short answer; a short list of questions may need several answers.
Quoted words such as `fictional`, `poem`, `short` and `long` are not instructions
by themselves. Intent classification uses syntactic/request position, not global
keyword presence. Presentation is stripped only at recognized instruction boundaries.

Use a plugin interface for CPU parsing, morphology and reference adapters. Start
with deterministic supported grammars plus the existing adapters. A future learned
parser may propose IR candidates, but must satisfy the same span, ambiguity and
proof checks. Choose additional dependencies only after comparing coverage,
latency, licensing and model availability on an independent parser evaluation.
No requirement to adopt a particular new NLP package is implied here.

## 3. Vocabulary and relation registry

Replace scattered predicate/color/question lists with a versioned relation registry.
Each supported relation declares argument roles and types, lexical forms, allowed
normalizations, value schema, extraction adapters, question adapters, inference
rules, conflict policy and rendering constructions. It also declares whether a
slot is single-valued, multi-valued, or context-dependent.

Morphology maps declared forms of a predicate to one ID while preserving arguments,
tense and polarity. Synonyms require compatible senses and provenance. Antonyms
remain relations, not substitutions. A definition or glossary scoped to one source
does not change another source's language. Keep literal original values alongside
normalized values for attribution and reversible inspection.

For open values, prefer explicitly typed source constructions: `color(X, Y)` can
accept a new Y once Y is produced by a declared grammar, without adding that Y
at each call site. A versioned color vocabulary and an explicit attribute
construction (`X has color Y`, `the color of X is Y`) may emit a color reading.
A bare copula stays ambiguous: `X is copper` can be color or material, `slate`
can be a name, and `X is a copper instrument` is a type. The question's slot
may choose which retrieved readings to inspect. It cannot create a color proof
from a copula the grammar did not type. An untyped copula abstains. Record a
vocabulary hit as a qualified grammar reading, and keep the original span.

Adding a capability then means adding a coherent relation adapter with its positive,
negative and ambiguity contract, rather than editing five unrelated regex lists.

## 4. Entities, senses and the six channels

Use stable entity and mention IDs with explicit supported identity edges. Different
names may identify one entity; the same spelling may identify different entities.
Multiple roles or types do not alone prove ambiguity: one person may be both a
parent and an engineer. Absence of an is_a link between those roles is not proof
of different people. Require positive evidence of competing referents, incompatible
applicable claims, or unresolved mention candidates before forcing a sense choice.
Two applicable type assertions about the same mention, with no source identifying
them as one type, are competing readings and the path asks. A missing link
between unrelated roles is not that evidence: one entity may be both a parent
and an engineer. When evidence cannot settle this, expose uncertainty rather
than merge or split identities automatically.

Retain the six channels as independent annotations and retrieval priorities:
dense similarity for candidate relevance; relational roles for predicate matches;
disentangled features for discriminating alternatives; taxonomy/hyperbolic signals
for type candidates; identity for name binding; causal/time signals for event
dependencies. Query tasks may activate several channels. Record enabled-head
availability and symbolic support separately. Unavailable geometry is unknown,
not false, and prototype scores are not calibrated intention probabilities.

Epistemic metadata describes assertion/verification state; it is not a seventh
semantic channel. Exact word and entity edges remain stored explicitly. A vector
signature can help find that network but cannot reconstruct its provenance or
license every connected claim.

## 5. Evidence-directed retrieval and bounded inference

Plan retrieval from missing proof obligations, not just related words. For a
lifespan task, first seek a direct assertion about the bound entity, then permitted
identity/type premises and applicable rules. Ask for source evidence when necessary;
ask the user for intent when intent is missing. Those are different gaps.

Dense search, tags, lexical variants and graph lookup all return candidates in the
same scope/time context. Re-rank by the request's predicate/roles and distinguish
initial candidates, repair candidates and accepted proof. Stop on a decisive
answer, recognized conflict or fixed resource budget. Record budget exhaustion
without implying that the entire corpus was exhaustively searched.

Inference rules are explicit and typed. The SQL-like membership join is:
member(e, T) AND forall(x in T, P(x, v)) -> P(e, v), subject to compatible time,
conditions, identity, scope and value types. Preserve both premises and identity
bindings. `some`, typical values, and averages cannot supply an individual's fact.
An explicit question about a group's average quotes that group's stored average
and cites it. Refusing that question is not the individual-inheritance ban.
Gold that marks the quoted average as a false assertion is an evaluator defect;
do not change the runtime to satisfy it. The negative case is a named individual
whose only lifespan sentence is the group average.
Do not add arbitrary transitive inheritance, contraposition, or closed-world
negation. Missing P is not proof of not-P.

A definition request is discharged by a registered type assertion, including an
alias whose identity path is supported. A place, color, or ranking sentence does
not discharge it. If the only sentence about the entity is a place, the type
slot is missing.

Conflict is computed only inside the caller's scope and the requested time.
An assertion outside that scope is absent, not a second value. Two in-scope
values of a single-valued predicate are a conflict; dropping both and reporting
insufficient evidence hides the disagreement. Two possessions may both be true.
Two colors may reflect time, parts, or different sources rather than one
contradiction. Preserve unresolved disagreement and qualifications.
Typed storage/indexes should support entity/predicate/time/provenance lookup;
profile current full scans before selecting an indexing migration.

## 6. Proof-carrying decisions and sentence generation

Every successful decision carries a proof graph: accepted source spans, rule IDs,
identity edges, derived conclusion and qualifications. A source quotation can
answer directly; a template can express a licensed derived conclusion. Quotes
and conclusions have distinct verification scopes. Do not label a derived
sentence as a verbatim source quotation.

The final judge checks request satisfaction, proof validity and delivered claims.
Grammar, audit and grounding are additional checks, never replacements for those
three. The renderer receives a decision and proof, rather than choosing a new
answer from arbitrary retrieved text. The public evidence list is the proof
graph's accepted source spans. It is not a second search through the spoken
sentence, and a derived conclusion is not labeled as a verbatim quotation.
The renderer may vary phrasing only through supported constructions that
preserve roles, values, quantifier, polarity and qualifications.
No post-judge factual sentence may be appended without a new proof check.

Summary/list producers choose supported claims under the shared optional budget.
Required premises and qualifications are mandatory. Specialist producers declare
their input/output contract: a calculation carries its inputs and computation;
a source-backed letter carries selected source claims and unfilled fields. An
unsupported creative request cannot be replaced by unrelated factual output.

Parent completion requires every task's declared obligations to be discharged.
Existence of a child result or a legacy `answered` flag is insufficient. An open
list must not claim exhaustive completeness without an explicit coverage basis;
report the supported items found. Preserve answered, missing, conflicting,
unsupported and pending outcomes without turning them into one false success.

## 7. Conversation is a state machine, not hidden reinterpretation

Represent pending state explicitly: missing entity, sense choice, criterion,
evidence request or task structure. Store the original semantic request and
acceptable response type; a user's choice fills a field in that request rather
than appending keywords and reparsing the whole question. The selected meaning
must constrain retrieval, inference, assessment and final rendering.

Use one scoped session coordinator for parent/child state, timeouts, cancellation,
attempt budgets and serialization. Tenant/caller/scope/history are part of the
state key. Persisted evidence is separate from in-memory user conversation state.
Document process-local versus durable guarantees; add durability only as an explicit
feature. Unsupported workflow dependencies must remain visible rather than executed
through accidental text matching.

## 8. Generalization and implementation strategy

Migrate incrementally behind internal adapters. First define IR and invariants;
then run the new parser/decision path in read-only shadow mode beside the existing
path, on the candidates that retrieval already returned. Record disagreements
without changing user answers or issuing a second search.
Move one relation family at a time to the authoritative path; keep a single owner
per migrated family. Remove legacy fallbacks after parity and negative tests pass.
Do not leave two competing production judges indefinitely.

Version extracted assertions, parser adapters and rules. Reindex only affected
facts, retain source versions, and verify correction/delete/history behavior before
switching reads. Never silently treat old untyped graphs as new validated facts.
Measure CPU/latency/memory overhead and cache only within scope/version boundaries.

Validate architecture through invariants and transformations, not fixture strings:

- Rename entities and change values: the logical outcome and proof structure stay.
- Reorder sources or add unrelated distractors: no change to a settled answer.
- Swap relation roles, negate a premise or remove a required edge: success stops.
- Change a universal to some/average: individual inheritance stops.
- Ask explicitly for the average: source-backed aggregate remains answerable.
- Add a style directive or irrelevant background: factual binding stays unchanged.
- Remove authorization or change as_of: excluded proof cannot contribute.
- Select another sense: the entire path follows it or reports missing evidence.
- Decrease response budget: mandatory proof and task outcomes survive.

Use independent gold and inference oracles, per-child scoring, valid proof alternatives,
and fresh domain/wording holdouts. Track parser coverage, complete-proof retrieval,
decision precision, answer coverage, conversation completion and final-delivery
consistency separately. Capability limits must be explicit. A new relation or
parser adapter is an expansion to evaluate, not a claim of arbitrary language
understanding. This architecture improves where errors can occur and be caught;
its reliability still has to be demonstrated on independent data.

## Deliverable sequence

1. IR/schema specification, relation registry and scope/time/proof invariants.
2. Shared request compiler and capability ownership; shadow disagreement traces.
3. Direct facts, definitions and selected meaning on the proof-carrying decision path.
   Adjudicate an explicit average question before treating abstention on it as success.
4. Membership/rule joins and missing-obligation repair on that same path.
5. Specialist adapters, renderer constraints and one final public response mapping.
6. Unified conversation coordination, extraction migration and measured indexing.
7. Independent transformed/holdout evaluation and removal of obsolete fallbacks.

Keep small regression fixes that restore an existing contract, but require every
new fix to identify the general invariant and its owner. Do not train or modify
runtime logic to satisfy particular benchmark wording. Implementing this proposal
is separate work; this document does not claim the migration is complete.
