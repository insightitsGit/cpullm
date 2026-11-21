# Reversal Research Node — implementation specification and tracker

Version 0.2 · 2026-11-19 · **Design only; implementation pending.**
Architecture: [revised design](reversal-research-design.md).
Baseline services: commit `65ce600`; core graph: 27 stages.

## Proposed module and request contract

Place orchestration in `cpu_llm.research.reversal` or a dedicated
`cpu_llm.reversal_research` package, after checking existing package ownership.
Reuse existing public inference types/services rather than defining another
incompatible top-level `EpistemicStatus` or duplicate proof engine.

Use Pydantic v2 with forbidden extra fields, finite validated numeric values,
immutable/defensively copied nested data, unique IDs and validated references.
Do not copy the original loose schemas verbatim.

Required typed contracts:

- `ReversalRequest`: question, explicit scope prefixes, snapshot, validated scan
  and inference budgets, scoring-policy ID, and optional caller-selected candidate
  IDs. The request cannot alter authorization or register executable rules.
- `ScopeManifest`: permitted unique chunk IDs/versions, counts, actual byte count,
  snapshot token, completeness and unsupported-extraction counts.
- `GroundedPredicate`: atom/arguments, polarity or typed numeric interval, units,
  temporal/regime context and exact source binding.
- `PremiseAdmission`: application policy/version, accepted/disputed/unknown
  classification, assumption IDs and justification. Source text cannot select
  its admission policy.
- `CandidateDefinition`: sourced model/entity identity, explicit necessary
  consequences, rule/model versions, parameter bindings and stated assumptions.
- `ConflictRecord`: opposed predicate IDs, matching context and decision reason;
  distinguish observation conflict from model-conditioned incompatibility.
- `ProjectionReceipt`: per-clue conditional proof, unknown/proposed context status,
  score eligibility and disjoint output partitions.
- `ReversalTrace`: all manifest/policy/proof inputs, exclusions, exact scores,
  tied outcomes, resource counters and replay hash.

The original `run(query, spans, ...)` may be a pure fixture-level entry point.
It must label supplied-span scope honestly and cannot assert full-KB coverage.
The application entry point receives the authorized scope provider/manifest.
Status callbacks report structured scope/progress events; callback delivery is
separate from the deterministic reasoning trace and has a documented error policy.

## Integration and conflict prevention

Proposed caller syntax: `Reversal research: <question>` or `ask(..., reversal=...)`.
These names remain inactive until the classifier, API schema, request validation
and tests are implemented together. Do not add inactive consumers to the current
runtime prompt-flag map.

The classifier chooses one coordinator. Strict mode and guard take precedence.
Mixed explicit specialist options fail before retrieval; internal calls use one
source context without recursive `ask` or nested specialist dispatch. Existing
ordinary, Nammade, invention, CrossDomain and inference tests must remain valid.

Pass immutable prepared contexts to safe read-only branches. Do not share a
thread-affine database connection or encoder across worker threads. Compute
inference once per relevant rule family/budget. Preserve current source and
snapshot restrictions in all candidate/projection/model calls.

## Tracked gates

- [x] Preserve the supplied specification and record the design review.
- [x] Define the new logical service, component ownership and collision rules.
- [x] Correct conflict ordering, epistemic labels, scoring and benchmark claims.
- [ ] Implement strict typed schemas, scope manifest and source-reference checks.
- [ ] Implement application-owned premise admission and context normalization.
- [ ] Implement candidate extraction/adapters with explicit unsupported outcomes.
- [ ] Implement pre-elimination quarantine and shared-rule falsification receipts.
- [ ] Implement contextual projection without upgrading unknown contexts.
- [ ] Implement decimal scoring, deduplication, semantic ties and trace replay.
- [ ] Add a scoped full-sweep provider, bounded counts and progress callbacks.
- [ ] Add explicit classifier/API routing, strict refusal and collision validation.
- [ ] Add rendering and provenance-preserving follow-up behavior.
- [ ] Run synthetic logic, adversarial and sourced-physics integration tests.
- [ ] Update README/runtime trigger map only when the public route is active.

## Acceptance matrix expressed as test requirements

1. Opposed same-context observations are quarantined before they can eliminate
   any candidate; input ordering does not change the result.
2. Inconsistent immutable axioms return `INCONSISTENT_PREMISES`.
3. Different time/velocity/model contexts do not create direct observation conflicts.
4. Unknown ground conditions or unobserved absences cannot prove reconciliation
   or falsify a candidate. Mere lexical similarity cannot prove an implication.
5. Every elimination has a valid replayable source/rule/model proof. A changed
   source, policy, parameter or rule invalidates replay.
6. Synthetic constant-model bounds can eliminate the fixed candidate; the same
   observations remain individually admissible under a varying model.
7. Unknown model parameters or missing core-radius/offset adapters return missing
   inputs rather than invented numerical results.
8. Duplicate source chunks/clues do not inflate ranking; semantic ties remain tied.
9. The original 7.0 toy score is earned only with supported contextual derivations
   and the explicitly recorded correlated-weighting policy.
10. Counts refer to distinct chunks. A relevant premise after the first 32/50
    records is inspected in a complete sweep. Permission filtering applies before
    counts/notices; inaccessible sources do not appear in output.
11. Caps distinguish partial coverage from no candidates and total elimination.
    Unknown extraction/model coverage is visible even after every chunk is read.
12. A callback notice is emitted before logical scanning. Synchronous HTTP does
    not claim live progress without an implemented transport.
13. Strict mode never scans or runs this strategy. Negated/quoted trigger words
    and ordinary conversation do not activate it.
14. One request produces one snapshot context, one coordinator and one final
    response; existing public requests have no extra full-scope scan.
15. All scoring and trace outputs are deterministic under input reordering and
    survive a JSON round trip without changing numeric meaning.

## Release evidence

Record fixed revision, source hashes, dataset manifests, exact prompts, complete
responses, trace replay results, failures and scope completeness. Report logic
correctness, abstention, extraction coverage and empirical validation separately.
No benchmark has been run for this proposed service yet.
