# Inference expansion and lean execution specification

Status: bounded implementation completed. Baseline: `7c8f6a3`.
Tracking companion: `node-inference-lean-review.md`.

## Contracts

- One authorized, versioned snapshot per research request. No cross-user cache.
- Prepared inference reuses parsed facts and bounded closures. Receipt replay
  remains available independently against original sources.
- Deduction proves only registered rules over explicit source premises.
- Numerical/temporal calculations record inputs, policies and limitations.
- Abduction, induction and analogy never acquire a deductive truth label.
- Strict mode, guards, source permissions and historical snapshots retain priority.
- Existing public fields remain compatible; new metadata is additive.

## Work packages and acceptance

1. Eliminate duplicate inference in combined research. Nammade can defer it to
   the owning coordinator. Test one attachment and one rendered section.
2. Prepare immutable request-local facts and cache closure by family and resource
   budgets. Test extraction/closure counts, deterministic receipts, replay, limits,
   conflicting premises and authorization isolation.
3. Use the inference service as the execution owner; remove the unused graph
   adapter (revised after the follow-up audit). Cache channel input preparation within
   the request; do not merge six distinct channel results.
4. Add explicit taxonomy, registered relation composition/inverses and conditional
   class requirements to the deductive registry. Reject statistical inheritance,
   unregistered rules and arbitrary relation transitivity. Every new rule must
   pass independent proof replay and conflict tests.
5. Reuse existing constraint interval comparison and numerical scanning. Attach
   deduction to selected CrossDomain source prefixes without changing its numerical
   or hypothesis claim status. No second numeric solver.
6. Add bounded temporal checks over explicit ISO dates/intervals; no inferred
   current validity, causal ordering or imputed dates.
7. Broaden explanatory alternatives using the existing AbductiveBridge service;
   require explicit model alternatives, evidence and distinguishing tests. Keep
   existing specialized domain behavior and unverified claim status.
8. Add optional structured statistical induction with sample size and uncertainty;
   no source-text mining into universal rules and no automatic activation on
   ordinary lookups. Unsupported distributions/inputs fail explicitly.
9. Document routing/producer ownership. Preserve specialized parser contracts,
   existing negation/quote handling and one primary response producer. Refactor
   incrementally rather than replacing all established classifiers in one change.

## Verification and tracking

Use focused inference/research/channel/routing tests, plus regressions for public
ask entry points. Count duplicate work directly; report measured latency only
when controlled measurements are actually run. Broader repository failures must
remain visible and separate from this change's verification.

Implementation results and remaining boundaries are recorded below as work lands.

## Implementation tracker

- [x] WP1: combined research passes `_defer_inference=True` to Nammade and
  renders one coordinator-owned inference section. Invocation-count regression.
- [x] WP2: `PreparedInference` copies the authorized snapshot, extracts facts and
  computes the input digest once, and caches closures per rule family/budget.
  Returned receipts are defensively copied; independent public replay reprocesses
  original sources. No cross-request cache.
- [x] WP3: the six channel stages share prepared passages and identity anchor in
  their request-local turn, invalidated when related rows change. Public explicit
  inference records `execution_owner=inference_service`. The follow-up audit
  removed the unused adapter; the core graph now has 27 stages.
- [x] WP4: taxonomy membership/subclass transitivity, strict physical-part
  transitivity, derived containment, physical-part/location joins and conditional
  class requirements. No arbitrary source-installed rules. Inverse containment
  is one-way: containment alone does not establish a physical-component relation.
- [x] WP5: CrossDomain/Constraint Check retain their existing interval and numerical
  implementations and can attach deduction from selected authorized KB prefixes.
- [x] WP6: `mode=temporal` over explicit JSON interval records, with closed-date
  intersection and ordering. No timezone imputation or inferred current validity.
- [x] WP7: the existing `AbductiveBridgeNode.compare_explanations` accepts declared
  observation coverage and multiple explanation alternatives with distinct tests.
  It preserves unverified status; it does not infer physical coverage from text.
- [x] WP8: `mode=inductive` over unique structured Bernoulli observations, reporting
  sample size, proportion and a 95% Wilson interval with sampling assumptions.
- [x] WP9: `classifier.specialist_plan` centralizes specialist seed classification
  and precedence while retaining specialized parsers, session continuation, strict
  mode, compound-task handling and existing producer contracts. Conflicting
  standalone inference/specialist API options are rejected explicitly.

## Additional compatibility fixes

- Ordinary questions fall through to normal answering when deduction cannot
  settle them; strict natural questions keep quotation answering.
- Unsupported natural-question syntax is not an API error. Malformed explicit
  inference commands request clarification; invalid API configurations still fail
  validation.
- Non-exact normalized sentence spans (for example abbreviation/newline cases)
  are skipped rather than aborting all research requests on a snapshot.
- Lazy entity capture preserves explicit negation; explicit negative-only support
  is `CONTRADICTED_BY_RULES`, not missing support. Proper-part cycles conflict.
- Scope sets are normalized to sorted receipt lists. Structured JSON rejects
  duplicate keys and nonstandard constants; observations cannot be double counted.

## Deliberate boundaries

All capabilities above are bounded forms, not unrestricted inference engines.
Generic arbitrary conditional programs, causal counterfactual solving, automatic
discovery of explanatory coverage, free-text statistical extraction, holdout
model learning and general scientific proof remain outside this implementation.
The core graph has 27 stages after removing its idle inference adapter. Shared
service inference remains available without that duplicate execution path.
No latency speedup, scientific discovery or enterprise benchmark score is claimed.

## Reproduction

Focused suites cover inference, expansion, research, Nammade, AbductiveBridge,
channels, flag contracts, reply selection, prompt planning, response budgets,
document workflows and strict evidence. Localhost HTTP tests require socket
access in this environment.

`examples/inference_expansion_smoke.py --dsn <disposable-pgvector-dsn>` ingests
synthetic records and runs eight cases covering taxonomy/requirements,
physical-part location, calendar intervals, statistics, explanatory alternatives,
research integration, strict refusal and restricted-scope missing support. Results
are saved under `build/inference-expansion-smoke/results.json`, with baseline
revision and source hashes to identify the tested working tree.

### Recorded verification, 2026-11-18

- **304 focused regression tests passed**, including localhost HTTP strict-mode
  tests. These are the named component suites above, not the full repository suite.
- **8/8 PostgreSQL smoke cases passed** using the existing disposable pgvector
  database and cached encoders. This included real catalog ingestion, direct
  deductions, structured analyses, combined research, strict mode and source scope.
- `compileall` and `git diff --check` passed. The HTTP tests initially encountered
  sandbox socket restrictions and passed when rerun with localhost access.
- Smoke output is synthetic integration evidence, not a scientific validation or
  an enterprise accuracy benchmark. The tested source hashes are in its JSON file.

### Follow-up audit, 2026-11-19

The validated remaining issues and their fixes are recorded in
[the audit resolution](inference-audit-resolution.md). Ordinary questions now
attach receipts only from retrieved rows, avoiding a full-snapshot inference
attempt. Prepared contexts retain only required source fields; extraction hashes
each chunk once. Atomic-entity validation is shared by requests and source facts.
Scoped Research, Nammade and CrossDomain now have serialization regressions.
Verification: **338 regression tests** (310 focused, 25 live pipeline, 3 HTTP)
and **8 PostgreSQL smoke cases** passed. See the resolution for scope and warnings.
