# Improvement design and implementation handoff after benchmark v2

Architectural foundation: [general semantic answering architecture](semantic-answering-architecture.md).
Use its shared IR, capability ownership and proof obligations to implement the
steps below; do not treat these steps as independent benchmark patches.

Proposed 2026-10-27. Implementation progress is recorded in
[the implementation report](semantic-implementation-report.md); the remaining
architectural work below is not implied complete. This turns the
[result review](reviews/2026-10-27/benchmark-v2-results-review.md) into ordered
engineering work. Keep the original benchmark and its gold/results immutable.

## Intended outcome

A delivered answer must satisfy the user's requested entity, relation, direction,
polarity and selected meaning, using permitted evidence. Relevant but unrelated
sentences must never make a task complete. Presentation instructions may change
length and format, without changing the factual question. Missing extraction,
missing retrieval, missing proof, ambiguity and unsupported forms must remain
distinguishable so the next retrieval or clarification has a clear purpose.

Preserve the six-channel design. Channels prioritize interpretation and candidates;
they are not factual proof. No new GPU model, cloud judge, free-form generator or
unbounded graph inference is proposed. Start with correctness and observable
contracts, then expand supported wording and optimize measured bottlenecks.

## 1. One authoritative answer contract — highest priority

Affected modules: `prompt_intent.py`, `answerability.py`, `evidence_judge.py`,
`agents/reply.py`, `pipeline.py`, `request_planner.py`.

Introduce an internal versioned request contract shared by routing, assessment
and final judgment. Adapt existing parsers into this contract rather than
maintaining a second independent regex interpretation. Proposed fields:

```json
{
  "schema": "answer-request-v1",
  "task_id": "q2",
  "kind": "factual",
  "entity": "Reed",
  "relation": "is_a",
  "direction": "subject",
  "object_constraint": null,
  "polarity": "affirmative",
  "quantifier_scope": "individual",
  "selected_meaning": null,
  "parse_status": "supported"
}
```

This is proposed internal structure, not an existing public API. Preserve original
and normalized query text, and include caller scope/history in the execution
context. Do not replace literal subject names with corpus guesses. Implement
definitions (`What is X?`) and kind questions through the same is_a binding.
Attribute questions such as `What shape is X?` need an explicit attribute slot;
if the slot grammar is unsupported, return unsupported rather than treating it
as an unrestricted question about X.

Have assessment return a typed decision: outcome, reason, bound claim(s), source
spans, proof edges and verification scope. Render that decision, then validate
the final rendered claims against it. `audit_passed` for a stored sentence proves
neither the requested relation nor responsiveness. Remove the fallback that
replaces a bound decision with an unrelated audited `answer`.

For a recognized factual request, inability to bind evidence means insufficient
evidence, conflict or clarification. An unrecognized factual form may return
unsupported or request a clearer phrasing; it must not silently authorize a
neighboring fact as an answer. Existing specialist producers retain separate,
explicit contracts, including source-backed letters and arithmetic.

Example: `What is the Reed?` with only `The Reed is found in Rim.` must abstain
on the type slot. With `The Reed is a display pane.`, it may answer that definition.
An alias definition is equally valid if its identity path is supported.

Parent completion must depend on successful child decisions, not only a child's
legacy status string. Keep all tasks in order and preserve partial/pending results.
Do not rerun retrieval while aggregating and do not infer a new combined fact.

Acceptance: direct definition, kind, shape, possession and alias positives;
wrong-relation/type-versus-location negatives; correct quoted text with wrong
entity; selected meaning absent/present; conflicting values; scoped historical
facts; and a two-task batch where q1 succeeds and q2 lacks its requested relation.
Assert all public fields and the final judgment, not only `reply.text`.

## 2. Separate task instructions from factual subject words

Affected modules: `classifier.py`, `response_policy.py`, `request_planner.py`,
`pipeline.py`, `agents/reply.py`.

Classify creative instructions from request position and action/object structure,
instead of matching `fictional`, `story` or `poem` anywhere in a prompt. Examples:

- `How long does the fictional lobster live?` is a factual lifespan question.
- `What is the story archive?` is a factual definition of a named subject.
- `Write a fictional story about the lobster.` is an explicit creative task.
- `Draft a letter about the lobster.` retains the source-backed letter producer.

Mask quoted/code/source-background text when finding task directives. Resolve
explicit negation of a directive conservatively; never interpret `do not write
a poem` as an affirmative poem request. Keep the caller's explicit producer option
separate from inferred wording. Compute the decision once and pass it to delivery;
do not independently rediscover creative intent with a broader regex at the end.

Normalize anchored style instructions before factual parsing, including
`Briefly: What color is X?`, `In one sentence, what is X?`, and a recognized
trailing format sentence. Preserve structured financial/source fields verbatim.
Do not turn a direct color question into a general summary or an event request.
Factual intent and verbosity remain independent; brief/detailed direct answers
still require the same fact/proof. Cause questions stay on the causal path.

Acceptance: restore all five live join tests without editing their subjects or
weakening assertions; test positive creative refusals, supported letters, quoted
directive words, structured inputs, and style variants with identical factual
bindings. Verify global/local budgets and clarification resume still work.

## 3. Improve extraction with evidence-backed vocabulary

Affected modules: `knowledge_graph.py`, `query_dictionary.py`,
`answerability.py`, `prompt_intent.py` and source-ingestion tests.

The current color extractor recognizes a small fixed list. Improve this in two
bounded ways: expand a documented color vocabulary and support explicit source
attributes (`X has color Y`, `The color of X is Y`) where the source identifies
the attribute. Preserve the original value/span and normalize only for comparison.

Do not treat every `X is Y` as color: copper can be a material, Slate can be a
name, and green can describe a policy. A bare recognized color word is a grammar
decision with ambiguity limits, not a license to invent a typed edge. Unknown
terms need an explicit attribute sentence or a source-local typed definition.
Do not promote arbitrary glossary equivalents to global synonyms or infer the
inverse of an unsupported relation. Keep antonyms distinct from equivalents.

Examples: the benchmark's `The Kestrel is copper.` can be covered by the declared
color vocabulary, while `The Kestrel is a copper instrument.` remains a type/
description unless the source explicitly states its color. Material and shape
remain separate slots; `The frame is brass` must not automatically become shape.

For causes, normalize only declared morphological variants inside the bound
predicate: `Why did X drift?` may match `X drifted because ...`. Preserve effect
arguments, polarity and direction. Never accept a cause about another action or
entity merely because the same noun appears.

Acceptance: unseen entity names with declared colors, explicit unknown color
values, material/name counterexamples, negation/conflicts, source-local gloss
isolation, base/past causal pairs, wrong-effect negatives, and reingestion/delete/
history behavior. New extraction rules require reingestion for stored graph edges;
document that migration requirement rather than assuming old stores are updated.

## 4. Make retrieval and proof failures diagnosable

Affected modules: `attribute_search.py`, `answerability.py`,
`evidence_judge.py`, `pipeline.py` and benchmark instrumentation.

Retain a compact trace per task: parsed slot, initial candidate IDs, authorized
expansion/repair IDs, extracted matching facts, accepted/rejected proof IDs and
reason, final claim bindings, and delivery outcome. Diagnostics are not accepted
evidence and must obey source authorization. Return trace details through existing
diagnostic mechanisms or an explicit debug option; do not add verbose internals
to user-facing prose.

Classify failure reasons separately: unsupported parsing, no candidates,
matching text not extracted, missing membership, missing universal rule,
out-of-scope/as-of premise, conflict, selected meaning missing, and final delivery
mismatch. Map legacy public fields consistently, keeping rejected candidate text
only in diagnostics. Do not increase retrieval breadth when the required text is
already present but misparsed.

Where an eligible supported slot lacks evidence, keep the existing bounded repair
queries and identity/type rules. Retrieve both membership and universal premises;
`some`, an average, a wrong class and similarity alone never license an individual.
A question explicitly asking for a stored class average is a different valid
request. Required proof and attribution survive the shared optional response budget.

Acceptance: independent SQL join oracle plus live public `ask()` tests; both
premises authorized and cited; alternate alias proofs; repair beyond initial
shortlist; bounds on calls; conflict preservation; no proof trimming for brevity.

## 5. Repair the evaluator before another headline score

Affected files: benchmark `gold_fresh.py`, `gold.py`, `scorer.py`,
`rescore_saved.py`, `run_eval.py`, and evaluator tests.

- Adjudicate `join-cross-10`: explicit average questions may quote an average.
  Add a separate named-individual negative. Do not generalize a group average.
- Add alternative minimal proof sets for equally valid alias/type sentences.
  Resolve corrected historical IDs from the saved ingestion mapping during rescoring.
- Give every factual/compound case typed bindings and per-child gold. A type answer
  cannot pass using a value or proof belonging to a different child.
- Separate wrong-but-relevant, unrelated-but-true, missing claim, false assertion,
  correct answer with missing proof, and safe abstention. Separate task omission
  from a present task incorrectly declared complete.
- Publish metrics, failure catalogs, adjudications and report from the same scorer
  version. Rescoring writes new files and refuses overwriting prior results.
- Re-score saved scale probes with the same version where raw evidence permits;
  otherwise mark them unavailable and rerun only the missing probes.
- Complete independent review of failures/uncertain cases and the seeded pass sample.
  A copied scorer verdict is not a second adjudication.

Acceptance: adversarial scorer fixtures for every distinction above; exact counts
recomputed from authoritative files; immutable original artifacts; no "passed"
claim for unavailable optional-unit measurement or process restart.

## Delivery sequence and exit criteria

Implement as small reviewable changes, each with focused regression results:

1. **Evaluator adjudication and version alignment.** Re-score saved results without
   a 70-minute rerun; publish corrected failure categories and preserve originals.
2. **Instruction normalization/creative trigger.** Restore the five failed joins
   and prove presentation does not change factual intent.
3. **Authoritative binding and final delivery.** Eliminate wrong-relation successful
   answers and false aggregate completion; retain specialist/clarification contracts.
4. **Extraction and causal coverage.** Add bounded vocabulary/grammar capabilities,
   their negative cases, and source reingestion instructions.
5. **Trace and bounded-repair integration.** Prove remaining misses can be assigned
   to stages; add no unbounded candidate expansion.

Run the full live suite on the resulting exact revision, including all join,
scope/history, choice/resume and budget tests. Keep existing documented expected
failures visible. Then use the [v2 benchmark handoff](benchmark-v2-design-and-handoff.md)
for a new frozen holdout and new output directory. Previously seen data becomes
the regression set. Require zero unauthorized disclosure, wrong-meaning or
wrong-relation completion on the mandatory curated cases; report coverage and
proof completeness separately before applying the broader benchmark thresholds.

Keep resonance opt-in during this work. Its measured latency is materially higher
without an established quality advantage. Optimize it only after profiling with
correct outcome-separated metrics, so an early refusal cannot look like a faster
correct answer. This design does not claim production readiness.
