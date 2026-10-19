# Handoff: investigate unanswered-question presentation

**ID:** HO-cpullm-core-answerability-001  
**Date:** 2026-10-18  
**Framing corrected:** 2026-10-19, following the user's disputed retrieval result.  
**Baseline:** `5737285`, package metadata 1.8.0.  
**Status:** A scoped output observation is preserved. The user reports correct retrieval in their run; the exact prompt, corpus, and call need comparison. No fix is implemented by this handoff.  
**Triage:** Investigate relevance/presentation under the intended output contract. A retrieval defect and project-wide P1 severity have not been established by the seven-paragraph test.

## Correction to the original handoff

The original framing overreached in three ways. First, the synthetic corpus did not contain France's capital, so that test cannot demonstrate failure to retrieve a correct passage that was available. Second, passing `audit_passed` is not itself an auditor defect: that checker tests realized text against supplied propositions, not whether those propositions answer the question. Third, the demonstration did not compare customer utility or a retrieval baseline and cannot establish that the library lacks value.

The observed issue is narrower: this particular question/corpus produced source-backed but nonresponsive displayed text. Whether that is a bug, a missing label, or an intentional nearest-passage behavior depends on the agreed API contract. An answer-only policy and the architectural changes below are proposals, not established requirements. Do not rewrite the retriever or freeze unrelated work on the strength of this test.

A subsequent rerun on the existing default corpus returned France Area/Manila passages; the isolated demo namespace returned its same kestrel/travel sentences. This does not disprove the user's successful run. Its exact inputs, source availability, namespace, options, and current code must be matched before drawing a conclusion about that discrepancy.

## Mission

Investigate whether the intended document-question-answering contract is the following, or whether it deliberately permits a labeled nearest-passage result:

> Given supplied documents, answer a supported question using evidence that actually answers it, cite that evidence, and explicitly abstain when the available evidence does not settle the question.

The saved observation is that an out-of-corpus question received nonresponsive stored sentences while proposition/grounding checks passed. That is not proof of fabricated content or of a malfunctioning retriever. The exercise did not measure comparative value over retrieval-only; that remains an optional evaluation question, not an established negative conclusion about the library.

Keep this investigation focused. Do not impose a project-wide feature freeze, replace the existing architecture, or assume a larger decoder is needed. Confirm the intended behavior and the user's successful case first.

## Reconcile work already in progress

At handoff creation, HEAD was still `5737285`. Existing modifications included README, `docs/library-consumer-guide.md`, and `src/cpu_llm/agents/reply.py`; `src/cpu_llm/ranking.py` and `tests/test_ranking.py` were untracked. These belong to concurrent work and may address part of the issue.

Read current instructions, status, commits, and those diffs before editing. Revalidate the baseline case on the current code. Preserve concurrent changes; do not restore the old checkout, overwrite ranking/reply work, stash, or delete files to make the failure reappear. Inspection shows that `ranking.py` handles questions about stated best/worst/order rankings; it is not a general retrieval reranker or evidence that the France case was fixed. Evaluate each change against its actual purpose.

This focused handoff complements [the nine-finding correctness handoff](handoff-claim-verification-review.md); it does not replace its writer, rule, construction, format, and capacity findings.

## Portable evidence

- [Live-run prompts, outputs, retrieval candidates, and flags](reviews/2026-10-18-feature-demo/feature-demonstration-20261018.json).
- [Runnable Appliance demonstration](reviews/2026-10-18-feature-demo/feature-demonstration-20261018.py).
- [Feature observations and limitations](reviews/2026-10-18-feature-demo/real-features-20261018.md).
- [Separate finance-component observations](reviews/2026-10-18-feature-demo/feature-components-20261018.json), included for completeness, not the focus of this task.

The demonstration used actual `Appliance` ingestion, local PostgreSQL, encoder, worker pool, graph, and reply generation. It was not a mocked pipeline. It used fresh namespace `feature_demo_5dba7941222e`, stored seven paragraphs, and issued 15 prompts. No existing source was changed. The copied runner creates another fresh namespace per run and retains it; its output filename was adjusted to write a unique rerun JSON file beside itself, preserving the baseline observations. It requires the installed dependencies and a reachable database. Do not run it against an unprepared production deployment or confuse its small synthetic corpus with a representative benchmark.

## Exact critical reproduction

Ingest `SourceDocument("feature-notes", (...))` with these seven paragraphs, in order:

```text
The harbor kestrel is a small coastal falcon.
The harbor kestrel nests in coastal cliffs.
The harbor kestrel eats small fish.
John ate a yellow apple in his house.
Business class is allowed for flights over six hours.
The flight from Boston to Paris takes eight hours.
The flight from Boston to Chicago takes two hours.
```

The bird descriptions are synthetic test data. Ask:

```python
result = app.ask("What is the capital of France?")
```

**Actual `reply.text`:**

```text
The harbor kestrel is a small coastal falcon. it eats small fish. Business class is allowed for flights over six hours.
```

**Actual diagnostics:** `audit_passed=True`, `shine_ok=True`, no typo rewrites, and `thinker_directive="gather"`.

**Proposed answer-only outcome, subject to the intended contract:** an explicit non-answer indicating that these passages do not establish France's capital. If nearest-passage presentation is intentional, retain it with accurate labeling instead. Do not treat it as a capital-of-France claim. Adding Paris from model world knowledge would not establish a source-backed answer from this particular corpus.

## Additional observations to preserve

- Supported apple color/location/agent questions worked end to end.
- An unstated pear color produced a proper frame non-answer.
- Definition, extractive summary, deep search, per-topic comparison, an email layout, arithmetic, and one supported rule example worked on their selected inputs.
- The source-list request for the kestrel also listed two flight paragraph IDs. A retrieved candidate is not automatically evidence for a delivered claim.
- All 15 prompts reported `gather` while delivering some text. The fix must not blindly block every `gather`, because that would also discard supported answers in this run.
- `realization="evidence_neural"` reported `deterministic_fallback` and a null checkpoint. No trained v1.9 realizer was exercised. Adding that model is not a prerequisite to solving the issue.

## Likely causes and code to inspect

These are concrete investigation leads, not a claim of an exhaustive root-cause analysis:

1. **Candidate fallback becomes answer eligibility.** In `src/cpu_llm/assembly.py`, `_in_scope` returns `list(hits)` when no retrieved item shares content words with the question. This makes zero matching evidence become permission to realize unrelated propositions. `realization_order` then passes those IDs to cognition. Separate fallback candidate retrieval from authorization to answer.
2. **Proposition integrity and responsiveness have different scopes.** `_cognize` in `pipeline.py` realizes/audits stored propositions. A sentence can match a proposition perfectly while not answering the question. The existing auditor does not take the user's question as its relevance contract, so its success here is not proof that it malfunctioned. Check how callers are meant to interpret the field.
3. **Grounding is incomplete as an answerability check.** `grounding.py` runs Shine with its external judge and tier-3 span model disabled, plus lexical/numeric checks. The France case passes. Do not simply relabel `shine_ok` as a comprehensive semantic guarantee.
4. **Reply fallback can still display an unrelated candidate.** `_body`/`_quote` and any concurrent ranking changes in `agents/reply.py` must distinguish direct answer, relevant evidence quote, unrelated nearest passage, and abstention. Fixing only one rendering branch leaves other producers capable of replacing a correct non-answer.
5. **Evidence attribution is shortlist-based in places.** Inspect `_brief`/sources and all reply producers. IDs supporting each actual claim must be distinguished from IDs merely returned by retrieval.
6. **Optional producer checks have different scopes.** Review frame, rule, math, finance, document, and N0 replacement precedence. Scope the initial patch to a declared surface, but make every displayed status clear and prevent an optional producer from silently overriding a rejected answer.

Inspect the current `ranking.py` and `test_ranking.py` if they exist. Do not duplicate them or assume a ranking heuristic establishes semantic entailment.

## Optional solution directions if an answer-only policy is agreed

### 1. Introduce a query-specific answer plan

Before realizing a factual answer, determine what the supported query asks for: subject/entity, relation or attribute, requested value type, and relevant temporal/polarity/modality constraints. For example, a capital question asks for a capital-of relation for France; an unrelated copula about a bird does not bind that request.

Start with a declared, conservative set of query shapes already supported by the implementation. When the parser cannot establish the query or evidence binding, return unsupported/missing rather than silently dropping constraints. Preserve paraphrase support through explicit aliases or evaluated matching; do not make exact surface-word equality the whole solution.

Retrieved candidates are inputs to this plan, not approved claims. A learned relevance model may later rank candidates, but confidence or cosine similarity alone does not establish the requested relation.

### 2. Separate answerability from realization verification

Represent at least these independent outcomes:

- **Retrieval:** candidate IDs/scores and scope/completeness.
- **Answerability:** answered, insufficient evidence, ambiguous, conflicting, unsupported, or blocked, with reason codes and bound evidence.
- **Faithfulness:** checks that a proposed answer preserves its selected evidence/plan.
- **Delivery:** what is actually shown and whether an explicit hold applies.

Do not overload `audit_passed`. Retain compatibility where practical and add explicit, documented fields such as `answer_status`, `answer_evidence`, `verification_scope`, and producer identity. These field names are suggestions; settle one coherent schema rather than adding another disconnected success flag.

An unanswerable question may retrieve candidates and still have `answer_status="insufficient_evidence"`. A source-faithful sentence can fail answerability. A faithful answer can also reflect a false source; do not claim source truth.

### 3. Make abstention survive final composition

Do not merely set an intermediate field and let `_quote`, a draft, a rule writer, or a full-account renderer overwrite it. Check the actual `reply.text` on every path the initial patch supports. Preserve prior authentication/guard/audit/grammar/Shine holds.

Provide an optional, distinctly labeled evidence preview when useful. Its presence must not turn a missing answer into an affirmative claim or get an answer-verification label. Do not auto-fill unsupported answers from pretrained model knowledge.

Do not use `thinker_directive != "answer"` as the sole fix. In the saved run every supported case also reported `gather`; investigate whether that is diagnostic advice, routing behavior, or a separate sufficiency bug and document the intended contract.

### 4. Bind citations to actual claims

For a direct answer, return source/chunk IDs and exact source sentence or span for each claim. Preserve entity, relation, value, unit, and time bindings. Keep `retrieved_candidates` separate from `supporting_evidence`.

For the kestrel sources case, flight paragraphs must not appear as support for the bird claims. If displaying all retrieval candidates remains useful, name that collection accurately. A request for sources is not permission to invent a proposition or accept a fabricated background sentence as retrieval.

### 5. Validate before expanding scope

Make the baseline failure and supported cases regression tests first. Then evaluate on frozen, held-out documents/questions that were not used to tune thresholds. A reranker or a tighter abstention threshold is a candidate improvement, not sufficient evidence of correctness.

## Suggested regression families for an answer-only policy

1. Exact seven-paragraph France-capital reproduction: explicit non-answer; no unrelated factual answer and no misleading whole-answer verification status.
2. Same question with an explicit France-capital sentence in the allowed corpus: answer from that sentence, with its actual ID/span.
3. Distractors sharing `France`, `capital`, or both: an office named France Area, a financial capital amount, and an unrelated country's capital must not satisfy the relation merely through word overlap.
4. Supported paraphrases and explicitly stated aliases: do not solve abstention by rejecting all non-exact wording.
5. Correct value for the wrong entity, right entity with wrong attribute, mismatched year/tense, and negated/conditional claims.
6. Conflicting claims and equivalent duplicates, under permutations of candidate order. No arbitrary winner.
7. Evidence exists but falls outside caller scope: do not answer or expose it. Missing allowed evidence remains missing.
8. Relevant evidence is present but cannot round-trip: clearly distinguish evidence quote from a verified direct answer; do not substitute an unrelated round-trippable sentence.
9. Typo rewrite and multi-turn follow-up cases: retain original/corrected query and ensure the rewrite or previous context did not change the question's identity unnoticed.
10. `reply.text`, sources, and status for base, frame, brief, and opt-in N0 paths; extend to other producers only with explicit coverage. A blocked candidate must stay blocked.

Retain existing positive apple-role, supported definition, math, and summary cases. Add adversarial checker/writer regressions from the prior review where the modified delivery path touches them.

## Optional comparative evaluation, not a finding of missing value

Use the same frozen corpus, query set, source scopes, and retrieval candidates for comparison:

- **Baseline A:** retrieve the top passage and show it accurately labeled as a passage, without claiming it answers the question.
- **Baseline B:** current accepted checkpoint/checkout behavior, with its actual statuses.
- **Candidate:** revised answerability and delivery path.

Build a labeled dataset containing answerable queries, answerable paraphrases, absent answers, near-miss relations/entities, contradictions, and scope exclusions. Keep development/calibration questions separate from the final held-out set. Do not publish a success rate only on the apple examples or on the exact corpus that motivated the patch.

Report:

- Precision/correctness of actual delivered answers, with counts by query family.
- Coverage: how many answerable cases receive a correct answer.
- Unsupported-answer rate on unanswerable and adversarial cases.
- Abstention correctness, distinguishing appropriate abstention from missed available answers.
- Claim-level citation precision and whether the cited span actually supports the requested relation.
- Retrieval hit-rate separately from answer correctness, plus candidate-order sensitivity.
- Latency, startup, resource use, and reviewer task time where measured; do not invent savings.

Report the tradeoff, not just one score. Abstaining on everything is not success. Returning every top passage as a verified answer is not success. A lower unsupported-answer rate must not hide unusably low answer coverage.

Choose release acceptance targets and application-specific error costs explicitly before scoring the held-out set. For curated supported-contract regression tests, require no accepted unsupported claims in those fixtures, while acknowledging that this is not a universal proof. If the candidate adds no useful improvement over the passage baseline, report that plainly and limit the product's claim to the capability demonstrated.

## Suggested implementation sequence

1. Reconcile concurrent ranking/reply work and rerun the saved critical example.
2. Add negative and positive query-binding fixtures; establish the initial supported-query contract.
3. Correct the assembly eligibility fallback; add the query-specific plan/answerability outcome.
4. Enforce that outcome during actual reply rendering and attach claim-specific evidence.
5. Check compatibility with existing diagnostics and optional producer behavior.
6. Run the curated regression set, then the frozen comparison against retrieval-only and prior behavior.
7. Update README/consumer docs with the demonstrated scope and remaining limits; do not fix only the marketing language.

## Proposed acceptance criteria if this policy is selected

- The live France-capital case abstains correctly on the seven-paragraph corpus and answers correctly only when authorized supporting evidence is supplied.
- Supported positive cases still answer; near-miss/paraphrase/contradiction/scope cases are covered explicitly.
- A nonempty candidate and passing base-audit flags cannot be mistaken for a responsive verified answer.
- The actual delivered text, producer identity, query-specific status, and supporting citations agree.
- Prior rejection remains authoritative; unrelated nearest passages are separately labeled if shown.
- The evaluation reports answer precision, useful coverage, unsupported answers, and citation quality against the same retrieval baseline, with exact datasets/counts and limitations.
- The receiving agent reports fixed and remaining issues, changed files, commands/results, compatibility decisions, and whether useful improvement over simple retrieval was demonstrated.

The user requested a handoff describing the issue and possible solutions. This document does not independently authorize a new product contract, a feature freeze, or a broad rewrite. Resolve the disputed reproduction and intended behavior before implementing the optional changes above.
