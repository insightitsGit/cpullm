# Follow-up code review: edf54ee

Reviewed on 19 October 2026, America/Los_Angeles. Range: 5737285..edf54eeebc3ba3b746b10d8ec16d905ea6b4e93f (four new commits). Source was clean at review start. No production code was modified in this review.

## Confirmed improvements

The original 27 regression cases now pass on both the 17-paragraph controlled corpus and the 217-paragraph corpus with the same 200 WikiText distractors. Each configuration ran three repetitions through both retrieval and the full pipeline: **324 measured live calls, zero exceptions**. All 27 displayed replies were stable across repetitions in each configuration. Both runs used identical frozen source hashes and fresh PostgreSQL namespaces.

The previous final tested source passed 21/27 of those cases: factual 15/17, policy 1/4, missing-fact nonanswers 3/4, math 2/2. This commit passes factual 17/17, policy 4/4, missing-fact nonanswers 4/4, math 2/2. Nesting replies now include the correct location; absent weight returns a nonanswer; below-threshold permission remains unknown; an allowed flight is correctly answered NO when asked whether it is forbidden. The color/colour case also remains a nonanswer with distractors.

These are passes of explicit fixture checks, including source quotes where appropriate, not proof of general QA correctness. The new counterexamples below are outside that original set.

## Remaining findings

### P1: verdict normalization covers only one modality combination

Location: `src/fact_bridge/__init__.py:565-576`, with the unchanged prohibition NO branch at 596-601.

Live reproduction with an allowance and an eight-hour flight:

- Question: `Is business class required from Boston to Paris?`
- Actual: `Yes. Business class is allowed for the flight from Boston to Paris: it lasts 8 hours, and business class is allowed for flights over 6 hours.`
- Expected: UNKNOWN about a requirement. An allowance does not establish an obligation.

With an explicit prohibition and the same flight:

- Question: `Is business class forbidden from Boston to Paris?`
- Actual: `No. Business class is not allowed for the flight from Boston to Paris: it lasts 8 hours, and business class is not allowed for flights over 6 hours.`
- Expected: YES, since the stored prohibition applies.

The new `_asked_modality` value recognizes required/forbidden, but only the allowed-to-forbidden YES branch uses it to change the verdict. Other branches still return whether an action is allowed instead of answering the asked proposition. Suggested fix: derive the supported permission/obligation/prohibition first, then map it to the question's modality and polarity for all branches, and use that same result in the writer plan. Add a modality cross-product regression set, including UNKNOWN when permission alone is supplied for an obligation question.

### P1: relation support can bind a nested clause's predicate to the wrong subject

Location: `src/cpu_llm/answerability.py:318-333`.

Live fixture includes `The harbor kestrel eats a fish that nests in coastal cliffs.` It contains no nesting statement about the bird. Asking `Where does the harbor kestrel nest?` produces that sentence with **`answer_status: answered` and `verification_scope: query`**. The fish's nesting predicate passes the bird's support check.

The matcher checks that the sentence starts with the queried subject, then finds a verb and `in` anywhere later. It never binds that predicate to the subject. Direct assessment probes show the same issue for `The harbor kestrel watches a heron eat small fish.` and a weight keyword inside `The harbor kestrel watches a fish that weighs two kilograms.` The latter live reply is labeled `evidence_quote`, so this review does not claim it falsely asserts the bird weighs two kilograms; the supporting-relation check itself is nevertheless too permissive.

Suggested fix: require a subject-predicate-object or subject-predicate-location binding within the same clause. Start with strict supported clause forms and abstain or quote candidates without query verification when the grammar cannot bind them. Acceptance: direct `The harbor kestrel nests in coastal cliffs.` remains supported, while all nested-clause counterexamples above fail the bird relation check.

### P2: Model01's new filter admits partial entity matches and drops short subjects

Location: `src/cpu_llm/pipeline.py:1063-1079`.

Live question `Tell me about the harbor kestrel.` returns a bird description and appends `The picnic was held beside a harbor.` The picnic survives because the filter requires only one substring from the prompt; `harbor` alone is enough. That turn has no answerability assessment to filter the final Model01 sentence afterward.

The opposite failure occurs with `Tell me about Ada.` Although `Ada is a mathematician.` is in the source, the four-character token minimum discards Ada, Model01 reports `missing`, and delivery falls back to the earlier body, which in this fixture includes unrelated policy, bird, and picnic sentences. This is an observed loss of Model01 evidence filtering, not a claim that Ada's fact failed retrieval.

Suggested fix: retain short entity tokens and bind complete subjects/entities for supported query forms; use token boundaries instead of arbitrary substrings, and remove instruction/function words. When no supported entity can be bound, preserve a clearly scoped quote/nonanswer policy rather than silently reverting to a broad body. Acceptance: the picnic is absent from the bird reply, and Ada's evidence reaches Model01 without unrelated sentences being delivered.

## Executed tests and evidence

- Targeted repository suite: **121 passed**, with one fixed-ID database test deselected. Fourteen files cover frames, answering, answerability, realizer, finance, documents, ranking, Model01, fact-bridge, typos, comparison, math, review and summaries. The exact output is [saved](pytest-edf54ee.txt). Collection independently confirmed 121 selected / 122 total tests. This is not the complete repository test suite.
- [17-paragraph benchmark summary](audit-edf54ee-small/summary.json), [per-case outputs](audit-edf54ee-small/case-results.json), [CSV comparison](audit-edf54ee-small/comparison.csv).
- [217-paragraph benchmark summary](audit-edf54ee-distractors/summary.json), [per-case outputs](audit-edf54ee-distractors/case-results.json), [CSV comparison](audit-edf54ee-distractors/comparison.csv).
- [Additional live counterexamples and direct module probes](followup-probes-edf54ee.json), produced by [this executable script](followup-probes-edf54ee.py). Six additional live questions used two fresh namespaces; three additional probes called the assessment module directly. Expected behavior and the complete fixture corpus accompany each observation.

The original executable benchmark and scorer are unchanged. Reproduce them using a new `--out` directory with `benchmark.py`, then `analyze.py`; add `--distractors 200` for the larger fixture. The benchmark freezes package source and uses the cached CPU encoder. Optional fact-bridge models under the nested checkout directory are not copied into that frozen benchmark; these original regression cases exercise deterministic rule handling. The separate live counterexamples and repository tests use the actual checkout model discovery. Raw protocol files record versions, namespaces, corpus and commit. Existing corpus documents were not changed.

Observed full-pipeline latency was 40.4 ms median / 57.1 ms p95 for 17 paragraphs, and 64.5 ms median / 120.4 ms p95 for 217 paragraphs (81 calls per distribution; nearest-rank p95, warmed serialized in-process requests, startup and ingestion excluded). The developer workstation was not reserved exclusively for timing. The larger corpus took 71.0 seconds to ingest, so ingestion throughput still merits separate profiling; this review does not identify its component-level cause.

No tests or counterexamples in this report establish production-scale reliability or a security guarantee. Model01 remains a deterministic construction generator with no trained realization checkpoint loaded; the new commits improve grounding and routing, rather than demonstrating a newly trained neural sentence model.
