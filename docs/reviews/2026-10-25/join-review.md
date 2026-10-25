# Evidence join and response review — 25 October 2026

The reviewed source passed the complete test suite: **420 passed, 2 skipped**,
with no test files excluded and no tests deselected. The skips are optional
trained-extractor checkpoint tests. Six NumPy overflow warnings in earlier
cognition/numeric paths remain numerical diagnostics to investigate; a passing
suite does not establish numerical stability for arbitrary tensors.

See the [complete pytest transcript](pytest-join-review.txt),
[current design](../../current-design.md), and
[response-case checklist](../../response-cases.md).

## Environment and method

- Windows, Python 3.12.10, PostgreSQL 18.1, and the locally installed pgvector extension.
- A new PostgreSQL cluster under ignored `build/join-audit-pgdata`, bound only to
  loopback port 55433. Validation used a fresh disposable database and a separate
  working directory so existing application data and caches were not reused.
- Existing cached CPU encoder/checkpoint assets; no model download during the run.
- `CPU_LLM_LIVE_TESTS=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `HF_HUB_OFFLINE=1`,
  and `TRANSFORMERS_OFFLINE=1`. `VECTORPRISM_PG_DSN` pointed to the disposable database.
- Pytest ran the entire repository `tests` directory, using an explicit writable
  `--basetemp` and the repository as `--rootdir`. The local server was stopped afterward.
- Wheel and source-distribution builds succeeded with `python -m build --no-isolation`.

To reproduce, provision a **disposable** PostgreSQL database with pgvector,
install the project, cache the encoder, and run all tests from a fresh working
directory. Set the environment variables above and invoke
`python -m pytest <checkout>/tests --rootdir <checkout> --basetemp <fresh-temp> -rA`.
The suite writes fixture documents, schemas, and training-pair rows; do not use
a production database. The live join tests skip unless explicitly enabled.

## What was fixed

- Conversation cancellation now clears both pending-ranking and reference state.
- Ranking output cannot override partial execution, node errors, or delivery holds;
  replacement status/evidence fields stay synchronized and do not inherit an audit.
- Reference and typo interpretation update the retrieval query and ranking topic.
  One confirmation cannot merge a person and an object into the same referent.
- Scoped/historical legacy specialists use the current turn's filtered evidence;
  historical initial retrieval skips current-only article/tag/graph expansion.
- Alias traversal has an order-independent two-hop bound. Identity provenance is
  exposed separately; explicit class aliases can support a membership join.
- A direct color/lifespan value cannot suppress an applicable conflicting universal rule.
- Attribute-repair traces retain membership facts discovered by a successful retry.
- Correction vectors use the supplied correction timestamp. Reopened indexes still
  filter retired versions on current searches. Model01 pair storage follows the
  configured database rather than always selecting its hard-coded default.
- Supported direct location questions now recognize common spatial prepositions,
  including on/above/under, while retaining subject, predicate, negation, and clause checks.

## Join evidence

`test_join_contract.py` compares production selection with an independent SQLite
`INNER JOIN` for the four supported attributes. It tests rejected quantifiers,
conditions, modal statements, wrong classes, sibling/reversed membership, alias
depth/provenance, class aliases, direct-versus-universal conflicts, preserved
numeric bounds, and rejection of unimplemented transitive inferences.

The seven opt-in `test_join_pipeline.py` cases run the actual Appliance, encoder,
SQLite fact graph, and PostgreSQL. They cover both-premise attribution, source
authorization, dictionary plus alias routing, conversation continuation and missing
facts, conflict handling, replacement/deletion, correction times, and reopening
the vector index.

The existing four-question retrieval lab recorded hit-rate@5=1.0 and spoken
attribution=1.0 after the location fix. These are four controlled examples,
not evidence of general accuracy or commercial readiness.

## Test-contract changes

The first complete run exposed six older pipeline failures. Tests shared a tenant
and implicitly depended on documents/propositions left by earlier tests; one
expected an article that it never ingested. Pipeline tests now use independent
namespaces and supply their corpus. Expectations were aligned with the documented
contract: definition answers can quote an alias-bearing source, shortened audited
answers need not include unrelated measurement sentences, diagnostic flags are
not delivery failures, and creative output need not have a base `answer` field.
Tests still require actual delivered text, correct source IDs, legal evidence,
and successful execution rather than merely accepting a nonempty result.

The transcript was captured before committing this review; its embedded lab
`commit` field identifies the parent checkout, while the tested working-tree
changes are included in the commit carrying this record.

## Remaining scope

Broad source-text coreference, edibility/permission/personal-safety intent,
arbitrary comparison/recommendation, exceptions and general quantified reasoning,
unit/range reconciliation, prediction, and unrestricted sentence generation are
not completed by this review. Fastcoref inference, channel calibration/training,
production load/concurrency, durable sessions, and cross-store atomicity remain
unverified or open. The response checklist records these explicitly.
