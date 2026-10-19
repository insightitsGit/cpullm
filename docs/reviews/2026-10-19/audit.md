# Executed audit: retrieval, displayed answers, and latency

Run date: 19 October 2026 UTC. **648 measured live calls, zero API exceptions**, across four frozen source/corpus configurations. Each configuration ran 27 questions three times through retrieval and three times through the full Appliance. No remote language model was used. These are hand-authored diagnostic cases, not a representative accuracy benchmark.

## What the evidence establishes

Retrieval found **all declared premises for 21/21 answerable questions** in every configuration. The gold fact was in the top five for all 17 factual questions. The live France question correctly returned Paris when the source explicitly stated that Paris is the capital of France. This audit does not support the earlier general claim that retrieval is broken.

The initial frozen source answered **15/17 factual questions**, **2/4 absent-fact questions with an explicit nonanswer**, **2/2 arithmetic questions**, and **1/4 policy questions under the source-only implication rubric**. The 217-paragraph run kept the same factual score but explicit nonanswers fell to **1/4**.

A concurrent answerability change was detected and retested as snapshot B. It narrowed capital answers to the requested country and explicitly declined the missing Spain fact. It also declined two supported diet questions that snapshot A answered. Snapshot B scored **13/17 factual answers, 3/4 absent-fact nonanswers, 2/2 arithmetic answers, and 1/4 policy answers**.

The final jointly frozen source/test version, snapshot C, scored **15/17 factual answers, 3/4 absent-fact nonanswers, 2/2 arithmetic answers, and 1/4 policy answers**. Its [individual outputs](audit-20261019-run4/case-results.json) determine whether an earlier finding remains reproducible. These counts refer to distinct questions; repetitions are not additional accuracy samples. The four configurations are versioned observations, not independent experiments on one unchanged checkout.

## Comparison and timing

Open the companion comparison canvas beside the chat for the full table and a question-by-question inspector. Portable tables are also available as CSV:

- [Snapshot A, 17 paragraphs](audit-20261019-run1/comparison.csv)
- [Snapshot A, 217 paragraphs](audit-20261019-run2/comparison.csv)
- [Snapshot B, 17 paragraphs](audit-20261019-run3-current/comparison.csv)
- [Snapshot C, 17 paragraphs](audit-20261019-run4/comparison.csv)

Snapshot A, 17 paragraphs: retrieval median **27.5 ms**, p95 **39.9 ms**; full pipeline median **43.7 ms**, p95 **59.2 ms**.

Snapshot A, 217 paragraphs: retrieval median **46.4 ms**, p95 **58.0 ms**; full pipeline median **71.2 ms**, p95 **131.6 ms**.

Snapshot B, 17 paragraphs: retrieval median **26.4 ms**, p95 **38.8 ms**; full pipeline median **41.8 ms**, p95 **60.3 ms**.

Snapshot C, 17 paragraphs: retrieval median **23.5 ms**, p95 **27.8 ms**; full pipeline median **34.7 ms**, p95 **53.6 ms**.

Each latency distribution contains 81 serialized calls. Startup/ingestion/warmups are excluded. One warmup per method preceded measurement; method order alternates by repetition, with retrieval first for two repetitions and pipeline first for one. p95 is the nearest-rank percentile, not a confidence bound. These are in-process calls including query encoding; full pipeline also includes its graph, reasoners and reply construction. No HTTP overhead is measured. Developer activity was not suspended, so timing differences cannot be attributed solely to corpus growth.

Startup was 10.77, 9.36, and 10.05 seconds respectively. Total ingestion was 0.36, 79.87, and 0.36 seconds. In particular, the 217-paragraph ingestion took about 80 seconds; profiling is needed before attributing that cost to an individual component. This is not a large-corpus scaling test.

## Reproduced findings and concrete handoff

1. **Resolved during the audit: transient diet-question regression in snapshot B.** In snapshot B, `What does the harbor kestrel eat?` and the equivalent heron question returned `The retrieved passages do not settle that.` The corresponding `eats small fish` passage was retrieved. Both were answered in snapshot A and are answered again in snapshot C. The final C run also preserves the missing-country nonanswer. This is not an open failure in the final tested source. Keep the two positive diet cases as regression guards alongside negative same-entity/different-relation cases when changing `answerability.py` and its reply/assembly hooks.

2. **P1: polarity of a rule question is not reflected in the verdict.** `Is business class forbidden from Boston to Paris?` returns `Yes. Business class is allowed ...` in snapshots A, B, and C. Sources contain an allowance for flights over six hours and an eight-hour flight. Inspect `fact_bridge.answer`/`_answer` and the question-to-rule matching; the answer plan must carry the asked modality, rather than returning whether an allowance fires. Acceptance: `allowed?` yields YES, `forbidden?` yields NO for this fixture, with coherent text and the same evidence.

3. **P1 under the declared source-only rubric: permission is strengthened into an exclusive rule.** The two-hour and six-hour questions receive NO and wording that adds `only`, though the stored rule says `allowed for flights over six hours`. `_opinion` maps a nonmatching allowed condition to NO; its NO rendering introduces `only for`. Suggested fix: encode whether a rule states sufficient, necessary, or exclusive conditions. A sufficient allowance alone leaves the other cases unknown. If the product intentionally uses a closed-world policy convention, document and expose it explicitly. Under that convention, those two cases would pass instead; the modality failure above remains. This rubric is stated in the pre-execution case expectations, not inferred from the observed result.

4. **P2: retrieved location evidence is not delivered.** Both nesting questions retrieve the right passage first but display a definition and diet instead. This persists in the final snapshot C. Inspect the ingest proposition extraction and realization selection: `realization_order` only emits IDs that have stored EIR propositions. Suggested fix: trace the nesting sentence through extraction and add a checked locative realization, or return a clearly labeled directly supporting quotation when that form is outside the realizer grammar. Acceptance: the kestrel reply says `coastal cliffs`, and the heron reply says `tall trees`, without exchanging their subjects.

5. **P2: unsupported attributes can still yield unrelated text.** Asking the kestrel's weight gives its definition/diet in all four runs; with distractors it also includes a lobster's weight. No kestrel weight was supplied. This is an answer-responsiveness gap under an answer-only contract, not evidence that a retriever missed a nonexistent fact or that the quoted lobster weight was fabricated. Suggested fix: extend the declared relation/attribute support contract, with an explicit nonanswer or labeled evidence-only response when the asked attribute is absent. Acceptance: no unlabeled bird definition or lobster weight as the answer to the kestrel-weight question.

6. **P2: corpus vocabulary can change routing through spelling normalization.** In snapshot A with 200 distractors, `What color was the banana John ate?` becomes `What colour was the banana John ate?`; `frame_result` is null, and the displayed output is John's apple sentence. Without distractors the original question yields a missing-color nonanswer. The recorded `typos` field establishes the rewrite; no banana fact was supplied. Suggested fix: normalize supported spelling variants consistently in classifier/frame parsing, and protect grammatical routing terms from corpus-dependent typo replacement. Acceptance: both `color` and `colour` retain event-role semantics and decline this nonexistent banana event under both corpora. Snapshots B and C have only been tested on the 17-paragraph corpus, so this larger-corpus case remains unverified there.

These are observed examples, not an exhaustive defect inventory. The existing `audit_passed`/`shine_ok` fields must be interpreted by their actual contracts; their presence does not by itself certify that the displayed reply answers the user's question. Reproducing a nonresponsive reply with those flags is not proof that those checkers malfunction under their narrower proposition/source checks.

## Regression tests actually run

Snapshot A: **63 passed, 1 skipped, 1 deselected**, covering frames, answering, construction realizer, finance, documents, ranking, and Model01. Snapshot C, with source and tests frozen together: **79 passed, 1 skipped, 1 deselected**, additionally covering answerability. See the [final test transcript](audit-20261019-unit-current/pytest-results.txt) and [source/test hashes](audit-20261019-unit-current/sha256.json). An intermediate attempt ran newer tests against snapshot B and produced four failures; that mismatched-version transcript is retained but is not used as the regression verdict. The optional trained-extractor case was skipped because no trained extractor checkpoint was available. The Model01 PostgreSQL round-trip test was deliberately deselected because it writes a shared fixed model ID. These are targeted tests, not a claim that the entire repository suite passed. Live database behavior was tested independently by all 648 measured calls in unique namespaces.

## Reproduction, source identity, and limits

Python 3.12.10; Windows 11 build 26200; Intel Core Ultra 9 275HX, 24 reported cores/logical processors; 68,137,205,760 bytes physical RAM. Installed metadata: cpu-llm 1.8.0, torch 2.9.1, transformers 4.51.3, sentence-transformers 5.1.2, numpy 2.4.6, psycopg 3.3.4. Retrieval uses the installed MPNet model cache and the packaged projection. Hugging Face offline mode was forced.

HEAD was `5737285ff49714f2b3ea6759b719135040745961`, **with uncommitted source changes**. This was not a benchmark of a clean 1.8.0 release. Snapshot A was frozen before execution; the 217-paragraph run reused exactly that source. Snapshot B froze later concurrent edits. Snapshot C froze source and the corresponding tests together after further concurrent edits, and supplied the final test and live-question runs. [A-to-B changed source files](snapshot-changes.json) and each run's SHA-256 manifest identify the differences. Frozen source integrity was checked after each benchmark run. The full source snapshots remain in the local artifact directory; the portable review folder includes the raw observations and manifests. This report makes claims about the identified snapshots, not subsequent checkout edits. No source fixes were made as part of this audit.

The exact corpus, expected answers, expected supporting IDs, timestamps, versions, namespaces and dirty status are in each `protocol.json`. The additional 200 passages are the first eligible 150–1500 character rows in the shipped WikiText validation parquet, excluding the fixture's named entities and missing-fact terms. This is a reproducible distractor test, not a sampled public QA dataset. All 17 controlled facts stay in the same `audit-notes` source, so title routing with many source documents has not been measured. There are no adversarial access-control, concurrency, security, training-quality or production-scale claims here.

For factual retrieval, a hit means the declared source sentence was returned; multi-premise recall requires every gold ID. Top-one factual evidence coverage was 14/17 in all configurations, and top-five was 17/17. Full-pipeline factual answer scoring checks fixture-specific subject/value phrases, followed by review of every unique displayed reply. The scorer is intentionally transparent and narrow: it is not a reusable semantic truth evaluator. Extra source-faithful sentences do not fail a correct factual answer in this rubric. Retrieval-only output is a passage list; no unsupported-question abstention or policy-reasoning ability is attributed to that baseline.

From the repository, with dependencies, cached encoder and the documented development PostgreSQL running:

```powershell
python docs/reviews/2026-10-19/benchmark.py --out C:/path/to/new-run
python docs/reviews/2026-10-19/analyze.py C:/path/to/new-run
python docs/reviews/2026-10-19/benchmark.py --out C:/path/to/new-larger-run --source-root C:/path/to/new-run/snapshot --distractors 200
python docs/reviews/2026-10-19/analyze.py C:/path/to/new-larger-run
```

Use new output directories. Each execution creates and retains its own unique namespace and local cache for inspection; it does not modify existing corpus documents. The run-specific saved `benchmark.py` records exactly which harness version produced that run; invoke the repository harness for new executions because it resolves the checkout relative to its location. Inspect every new reply before accepting the fixture scores. A future agent should use the 27 cases as regression checks and add independent held-out examples before making broader quality claims.
