# Stylistic node stage-1 smoke evaluation

October 30, 2026. This evaluates the new working-tree stylistic companion node, not an installed release. `summary.json` records runtime source hashes. The October 29 benchmark and its scores remain unchanged.

## What the node actually generates

Stage 1 adds two closed constructions selected explicitly through `Appliance.ask(..., style=...)`:

- Formal: `The Nevazite is purple.` becomes **`The color of the Nevazite is purple.`**
- Friendly: `The Kemanema is found in Mamakema Reach.` becomes **`You can find the Kemanema in Mamakema Reach.`**

The output sentence is assembled at request time; it does not need to exist verbatim in the source database. Subject, attribute/location value and accepted proof come from the canonical decision. A separate inverse-grammar node verifies the generated candidate against that snapshot. Neither cosine similarity nor a model-generated judgment is used to establish equivalence.

This extends existing bounded construction generation; CPU LLM already had Model01. It does not establish a new general-purpose language model. It fills a small wording-variation gap rather than missing facts, unsupported inference, retrieval relevance, general creative writing or long-form coherence.

## Saved-response replay

The evaluator streamed all **680 saved October 29 responses** and requested both profiles: **1,360 top-level profile invocations**. It also visited completed batch children independently:

- **264 generated companion sentences**, counting repeated cases and child results. This is not 264 distinct claims or newly correct answers.
- **1,328 skipped leaf evaluations**, because the frame or profile/construction pair was outside stage-1 scope.
- **272 batch-parent records**, routed to children rather than given a new aggregate sentence.
- The leaf denominator is **1,592**, so generation coverage is **16.58%** of evaluated leaves. Skips are deliberate conservative behavior, not a measured answer-failure rate.
- Assertions confirmed that original result dictionaries were not mutated; existing canonical fields stayed equal for every evaluated result/child; each generated proof matched the accepted original evidence; and generated text matched a separate expected-surface check.
- Replay execution took **9.63 seconds** on this machine, including streaming/deserializing and checking saved responses. This is not model inference latency, a warm performance benchmark or a training time.

`replay.jsonl` records each top-level profile result and elapsed time. Batch parents record routing status; child coverage/proof checks were asserted during execution, with selected generated examples in `summary.json`. It is not a complete dump of every child sidecar. Original responses remain in the October 29 compressed artifacts; rerun the evaluator to inspect further cases.

## Isolation and publication

Stage 1 publishes generated wording only in `result["stylistic"]`. Existing `reply.text`, `answer`, outcome, audit/judgment, proof and rendered tables/reports remain canonical. A companion is a derived paraphrase and must not be labeled a verbatim quotation. No automatic promotion of a quoted answer to an asserted answer occurs.

`stylistic -> style_verify` is a real ChorusGraph subgraph, invoked after canonical dispatch/final judgment/repair and before layout rendering. No style argument means no style graph import/compilation through `ask`. Invalid profiles fail before retrieval. No new facts, database schema, projection heads, required arguments or existing response-plan flags are introduced. Profiles are request-local; no automatic tone inference or relationship-register selection is implemented yet.

## Tests and saved evidence

The targeted unit run has **28 passed, zero failures** (`unit.xml`). It covers actual subgraph execution, disabled behavior, malformed/unsupported frames, changed entity/value, negation/conditions/quantifiers, proof removal, stale fingerprints, tampered generated candidates, batch isolation, concurrent inputs and public `ask` integration using a controlled dispatch result.

The final `suite.xml` / `suite.log` record **738 passed, 2 skipped, 3 expected failures and zero unexpected failures**, with `CPU_LLM_LIVE_TESTS=1`, including a real PostgreSQL/encoder/judge smoke test for both constructions and empty caller scope. Final counts are in `verification.json`; the 28 targeted tests are included in the successful full-suite run and must not be added again. Two earlier attempts exhausted host memory; their logs are preserved as `suite-aborted.log`, `suite-isolated-aborted.log` and `suite-part-0.log`. The successful retry used a fresh database after host memory recovered and took 303.68 seconds. Six existing NumPy overflow warnings remain. PostgreSQL was stopped after completion.

`build.log` and `verification.json` record wheel-build/package-content checks. Cached pretrained encoder assets and the existing clean dependency environment were reused; this is not a new cold-download installation audit. No model training ran.

## Remaining gaps

The full ten-tone classifier, intensity scoring, relationship masks, sense-aware SoA lexicon, broad morphology and additional predicate constructions are still design work. Stage 1 uses only the two declared profiles/constructions. Unsupported color words, non-ASCII slots, constraints, joins requiring multiple premises and other producers skip. Literal quotations remain literal; style does not repair a bad upstream accepted claim. The proof-bound grammar has a finite reviewed scope, not a universal semantic-equivalence guarantee.

Visible-answer replacement requires a separate trusted publisher and explicit final-verification integration; it is not enabled here. HTTP request schemas and persistent session style settings are also unchanged. Future tests should independently score style preference and naturalness, not infer them from deterministic construction success.

## Reproduction

```powershell
# From this checkout, using an environment with its declared dependencies.
python tools/benchmarks/stylistic_smoke.py --out <new-output-directory>
python -m pytest tests/test_stylistic.py
# With a disposable PostgreSQL/pgvector database and cached encoder:
$env:CPU_LLM_LIVE_TESTS="1"
python -m pytest tests/test_stylistic_live.py
```

See the [design](../../stylistic-generation-design.md), [machine-readable spec](../../stylistic-generation-spec.json) and [consumer guide](../../library-consumer-guide.md).
