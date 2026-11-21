# Reversal Research Node — revised architecture

Version 0.2 · 2026-11-19 · **Proposed; not implemented or publicly available.**

This revises the [supplied specification](reversal-inference-original-spec.md)
using the [design review](reversal-inference-design-review.md). The canonical
project remains `cpu-llm` / `cpullm`.

## Purpose and node boundary

Add **ReversalResearchNode**, an optional research coordinator for candidate
explanation, necessary-consequence testing, disputed-clue analysis and transparent
ranking. User-facing name: **Reversal Research**. It is a logical node/service
outside the ordinary 27-stage graph, not another default graph stage.

The new capability is the coordinated elimination/projection workflow. Existing
services continue to own deduction, explanation candidates, numeric feasibility
and source comparisons. There will be one final response owner and one authorized
snapshot per reversal request. No competing abduction or arithmetic engine is added.

The highest-ranked candidate remains an unverified hypothesis. Deterministic
execution makes a run reproducible; it does not establish source truth, exhaust
all real-world explanations or prove that a surviving model is correct.

## Proposed activation and precedence

The proposed explicit prompt is `Reversal research: <question>`. The proposed
Python/HTTP option is `reversal={...}`. These are reserved design names, not
currently accepted API fields. The existing `inference` modes are unchanged.

1. Apply guard, caller/tenant authorization and strict operator/request floors.
2. Strict mode refuses reversal research before source scanning or candidate work.
3. An explicit reversal request selects this coordinator alone. It invokes the
   shared methods internally; it does not dispatch a second public `ask` call.
4. Conflicting explicit specialist options produce a documented validation error
   before retrieval. No silent precedence between reversal and standalone
   Nammade, invention, inference, cycle or payment requests.
5. Ordinary `Research`, `Investigate`, `Invention`, Nammade and hypothesis prompts
   retain current behavior. Everyday questions do not trigger exhaustive research.
6. The initial implementation handles standalone reversal requests. Compound
   prompt integration requires its own planner and continuation tests before
   activation; it must not duplicate scans per subtask.

Later natural-language activation may recognize explicit requests to compare and
eliminate candidate explanations, after false-positive, negation and quote tests.
The word “reverse” by itself is not a trigger.

## Scope, coverage and progress

Domain names select registered KB prefixes inside the caller's existing source
permissions. They cannot grant access. Scope aliases and defaults must be explicit;
an ambiguous or missing target scope asks for clarification.

A scope provider supplies an authorized snapshot manifest with unique chunk IDs,
versions, byte counts and expected/scanned counts. Pagination must retain one
snapshot token. Source spans include chunk IDs, document IDs, exact offsets and
hashes; span count is not substituted for chunk count.

Full coverage means every authorized chunk in the selected scope was inspected
under the recorded extraction/model versions. It does not mean every sentence
was understood. Record rejected/unsupported spans and model coverage separately.

Default latency notice threshold: more than 50 unique chunks. Emit an authorized
count notice before logical scanning through an optional status callback. If
scope enumeration itself is expensive, report that phase accurately. Synchronous
HTTP can return the notice in its result; live pre-execution notification requires
a separately implemented preflight, streaming or job transport.

Reuse current snapshot limits initially: at most 10,000 rows and 8,000,000 text
characters. Record actual bytes separately. Additional proposed defaults are
128 candidates, 256 clues, 256 rules, 1,024 conflict pairs and 100,000 operations;
deductive depth/state limits remain those enforced by the shared inference engine.
All limits need validation and operator ceilings. A cap yields partial coverage,
not an exhaustive verdict or global winner. No unbounded “all physics” promise.

## Revised four-phase execution

### 1. Source-backed candidate expansion and premise admission

Retrieve the complete permitted scope within the declared budget. Parse supported
typed records/clauses and extract source-backed candidate definitions and links
to the query. Keep unsupported text as source context without manufacturing rules.
Nammade can annotate comparisons but its bounded comparison list must not replace
the complete premise manifest.

Use two independent state axes:

- Evidence: accepted premise for this run, disputed observation, unvalidated clue,
  or unsupported/uninterpreted record.
- Candidate: possible, eliminated in this run, or surviving unverified hypothesis.

An application-owned admission policy decides which observations may become hard
premises. A source's own confidence field cannot promote itself. Query assumptions
are labeled separately. If the original CERTAINTY enum is retained for migration,
its meaning is explicitly limited to accepted premises under the run's assumptions.

### 2. Conflict quarantine, then deductive elimination

Normalize predicates, units, contexts, quantifiers and time/regime conditions.
Opposed observations conflict only if their meanings and contexts match.
Different-velocity bounds are compatible observations until a model adds an
incompatible cross-regime equality requirement.

Quarantine contested observations before constructing the hard premise set.
Retain both sources and conflict IDs. Apply explicit trust policy; never silently
demote immutable application axioms. Inconsistent axioms terminate as
`INCONSISTENT_PREMISES` rather than producing an arbitrary winner.

For each candidate, derive necessary consequences using registered rules or
trusted model adapters. Eliminate only when a proved necessary consequence
contradicts an accepted hard premise under matching assumptions. Record source
IDs, rule/model versions, variable bindings and proof steps. Similarity, typical
associations and missing observations cannot justify Modus Tollens.

Elimination is permanent within the immutable run, not across later snapshots.

### 3. Hypothesis-conditioned prediction and clue projection

For each survivor, compare its proved conditional predictions with the clue pool.
Track explained-under-model clues, soft contradictions, unknown residuals and
proposed/validated contextual reconciliations separately.

Only a sourced or explicitly assumed context split plus a registered mechanism
can support a contextual reconciliation. If the split is unknown, retain a
proposed reconciliation and a distinguishing test. Do not mark the conflict
resolved. Missing canopy breakage, detector output or a laboratory bound remains
unknown unless an explicit detection/coverage model supports an absence claim.

None of these projections validates the candidate against the real world.

### 4. Policy scoring, ties and response

Preserve the original heuristic weight defaults: reconciliation 3, explanation 2,
soft contradiction 2.5 and residual 0.5. Use finite nonnegative decimal weights
with a versioned scoring policy and exact decimal serialization.

Scoring contract v1:

- De-duplicate clue IDs, conflict IDs and provenance references.
- A reconciled pair can receive the original combined 3+2+2 reward only when
  both context-specific derivations are supported. This intentional correlated
  weighting is disclosed; it is not three independent pieces of evidence.
- A proposed reconciliation with unknown contexts earns no reconciliation reward
  and cannot count both opposed claims as explained.
- Distinct span density means distinct supporting source spans, with duplicate
  source content collapsed for tie-breaking. It is not confidence or independent
  evidence strength.
- Preserve semantic ties after score, reconciled count, soft-conflict count and
  deduplicated provenance density. Lexicographic candidate ID orders display only.

Use “highest ranked under the recorded policy,” not a probability or scientific
most-likely claim. Partial coverage has no definitive global winner.

## Results and audit contract

Return distinct statuses: `HYPOTHESES_RANKED`, `NO_CANDIDATES`,
`ALL_CANDIDATES_ELIMINATED`, `INSUFFICIENT_SUPPORT`, `UNSUPPORTED_MODEL`,
`INCONSISTENT_PREMISES`, `PARTIAL`, `BLOCKED` and `UNSUPPORTED`.

For complete total elimination, preserve the requested text
“No testable hypothesis option was found” and include every falsification trace.
An empty extraction result or capped scan must not imply that every model failed.

The trace binds query, tenant/scope, snapshot, scan manifest, parser/model/rule/
admission/scoring versions, assumptions, budgets, source proofs, quarantined
conflicts, projection partitions, exact scores, tied candidate IDs and audit hash.
Provide independent replay and tamper detection. A candidate's prediction cannot
serve as its own independent confirming observation.

The rendered response separates source excerpts, accepted assumptions,
eliminations, surviving hypotheses, unresolved evidence and distinguishing tests.
Always append a hypothesis disclaimer to this service's hypothesis output. No
hypothesis is automatically written back as a KB fact or used as a hard premise
in follow-up turns. Follow-ups retain topic, provenance and claim status.

## Component ownership

- Research coordinator: scope plan, one snapshot, progress and final response.
- AbductiveBridge: source-backed candidate/alternative explanation contracts.
- Shared inference service: necessary-consequence proofs and proof replay.
- Existing interval/constraint/model tools: unit-aware numeric feasibility.
- Nammade: comparison diagnostics with explicit supported/unsupported signals.
- Reversal service: quarantine ordering, conditional projection orchestration,
  scoring policy and a combined trace. It does not replace component guarantees.

Carry available six-channel readings as diagnostics. An unavailable channel is
recorded as unavailable; six positive scores are neither required nor sufficient
for a logical proof.

## Benchmark integrity

Keep animal-identification fixtures synthetic unless every anatomical property,
observation and rule is independently sourced. All test inputs must exist before
execution; no late introduction of track geometry, ground conditions or absences.

For SIDM fixtures, different-regime bounds are not conflicting observations.
The constant-model assumption may create an empty common parameter interval;
that excludes the candidate under those fixtures, not all dark-matter models.
Velocity-dependent predictions require explicit parameters and trusted computation.
Explaining galaxy radii or merger offsets additionally requires the corresponding
data/model adapters. Preserve the PDG cluster-density bound's attribution rather
than relabeling it as a Bullet Cluster-specific measurement.

## Implementation status

This document reserves a new research strategy and defines its boundaries.
No new classifier trigger, API field, graph stage or runtime behavior has been
enabled. See [the implementation specification](reversal-research-spec.md) for
tracked implementation gates.
