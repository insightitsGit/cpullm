# Grounded inference follow-up audit resolution

Date: 2026-11-19. Reviewed baseline: `fcd34f3`.
Source: the supplied “remaining grounded inference fixes” handoff.

## Finding disposition

- **A — valid, fixed.** Natural questions no longer call `execute_inference` or
  fetch a source snapshot before normal retrieval. After ordinary answering,
  `augment_retrieved_inference` can attach a useful receipt over retrieved rows
  only. It labels the subset explicitly and does not rewrite the normal answer.
  Explicit commands/API requests and research retain their scoped snapshot paths.
  Prepared contexts copy only document ID, text and source version, ignoring heavy
  auxiliary metadata. Chunk hashes are calculated once per extracted chunk.
- **B — valid, fixed.** Removed the idle graph inference adapter, registration and
  edges. The ordinary graph has 27 stages; the shared inference service is a
  service consumer in the flag map. There is no promise that every service is a
  registered graph stage.
- **C — valid ambiguity, fixed conservatively.** The quantifier was already lazy;
  the actual problem was allowing full coordinated/qualified phrases as entities.
  Shared validation rejects coordinators and supported trailing prepositional
  markers. Ambiguous source clauses are skipped; malformed natural questions
  retain ordinary routing; explicit commands request clarification. Coordinated
  objects are not automatically split, and complex legitimate names may be refused.
- **D — valid missing coverage, added.** Scoped Research, Nammade and CrossDomain
  tests use a frozenset source prefix, a real two-premise chain and a contradictory
  inaccessible source. They require entailment and a JSON-serializable response
  without the inaccessible source appearing.
- **E — valid consistency/documentation improvement, applied.** Explicit
  inference/specialist option conflicts intentionally remain validation errors
  (HTTP 400). OpenAPI documents that contract. Malformed-command clarification and
  blocked replies use the same inference response envelope as the service.

The already-fixed findings 1–6 do not require reverting their fixes. The audit's
suggested full-snapshot subject/object membership precheck was not adopted: the
retrieval-only implicit path avoids loading that snapshot altogether.

## Regression coverage

Tests assert zero implicit snapshot calls, shared chunk hashing, exclusion of
unused heavy metadata, correct atomic-entity rejection, no core inference stage,
proof replay over retrieved evidence, unchanged ordinary replies, and scoped
research serialization. Existing strict evidence and research contracts remain.

The audit's unrelated cycle-composition failures were not changed by this work.
This patch does not claim full natural-language parsing or full repository-suite
coverage. Verification results are recorded after the component and live runs.

## Recorded verification

- 310 focused component tests passed.
- All 25 `tests/test_pipeline.py` cases passed against the disposable PostgreSQL
  database. The run emitted six NumPy overflow warnings; no test failed.
- All 3 localhost strict-evidence HTTP cases passed.
- All 8 synthetic ingestion/inference smoke cases passed. Source hashes and full
  responses are saved in `build/inference-expansion-smoke/results.json`.
- Compilation and `git diff --check` passed.

Total: **338 regression tests plus 8 smoke cases**. No claim is made about the
unrun full repository suite or scientific/enterprise accuracy.
