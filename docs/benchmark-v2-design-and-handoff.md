# Request-pipeline benchmark v2: design and execution handoff

Prepared 2026-10-27 after reviewing `4752eb7` and `7f602c8`.
**Design only. Do not run an official evaluation until the preflight gates pass.**
Use the [original coverage specification](benchmark-design-request-pipeline.md)
and [handoff](handoff-fresh-pipeline-benchmark.md), with the corrections below.
The [first-run review](reviews/2026-10-27/fresh-benchmark-review.md) explains why
its headline accuracy and false-assertion counts are not accepted baselines.

## Current review and entry gates

The original numbered-choice failure now passes through the public `ask()` path:
`What kind of thing is the Lumen?` -> choose `2` -> display mark, with no survey
mark replacement. The focused suite returned 132 passed and three existing
expected failures. This is development validation, not benchmark accuracy.

One new blocking counterexample remains in `_constrain_channel_class`:

```text
The Lumen is a survey mark.
The Lumen is a display mark.
The European lobster is a species of crustacean.
```

For `What kind of thing is the Lumen?`, the first two rows alone ask for a meaning.
Adding the unrelated third row changes the answer to survey mark. The current
species exemption checks every row rather than the requested entity. Restrict
the exemption to relevant, identity-bound evidence and preserve genuine sense
ambiguity. Add an end-to-end regression before the official run.

Before freezing v2, require:

1. This counterexample and all previously reviewed choice/resume regressions pass.
2. The scorer rejects wrong entity, wrong relation, reversed direction, negated
   expected claim, unlicensed quantifier application, and retrieval-only proof.
3. The gold scripts and clock/reset experiments are corrected as described below.
4. The full live suite passes on the exact recorded runtime revision. Report
   skips/expected failures explicitly; no silent deselection or unavailable arms.

## Two distinct evaluations

**Known regression replay:** preserve the first run and re-score its raw results
with a versioned corrected scorer in a new output directory. Mark invalid gold
cases as adjudicated, retaining old and corrected expectations and reasons.
Re-run changed reference-clock/restart experiments, since saved raw outputs
cannot establish the corrected experiment. Replay fixed library cases against
current code separately. Never call this now-known corpus an independent holdout.

**Fresh quality evaluation:** create new fictional subjects, values, local glosses
and source wording across three domains. Do not reuse Lumen, Vesper, Helion,
Bramble or other old subjects in the fresh split. Keep old counterexamples only
in the regression replay. Use at least 180 standalone cases and 24 scripts with
the original family counts, development/holdout split and proof requirements.
Record new seeds, freeze gold before execution, and include source-order and
distractor variants. The person implementing the scorer must not use library
extraction/answer selection as the semantic oracle.

## Mandatory clarification matrix

For `What is X?` and `What kind of thing is X?`, test dense and resonance arms,
both numbered and textual choices, and both possible choices:

- Two unlinked classes: ask first; complete the selected meaning on the next turn.
- Selected class first/last in retrieved order: same final selected answer.
- Selected evidence absent: insufficient evidence, never the other meaning.
- Selected evidence alone: answer without asking again.
- Unrelated species sentence in initial/final retrieval: no suppression of ambiguity.
- Actual relevant taxonomy and linked classes: preserve the intended definition.
- Invalid/tied choice, cancel, new question, stateless call, TTL, restart and changed
  caller/scope/history: correct bounded state transition without cross-session use.
- Compound request with clarification first/middle/last: remaining tasks stay pending,
  resume in order, preserve the combined response budget and every outcome.

A valid earlier singular antecedent remains valid when a different entity occurs
later. For a genuine ambiguous-reference script, name two plausible entities
*before* the pronoun. A best-ranking positive case needs explicit criterion-bound
ranking evidence; an ordinary color fact does not establish best by color.
Source-backed letter generation is supported and must remain a positive specialist
case. Separate genre compliance from factual assertion truth.

## Correct scorer and measurement contracts

Store gold assertions as subject/relation/object/direction/polarity/quantifier
bindings, with permitted alternatives and required proof sets. Match endorsed
assertions to these bindings and source spans. Exact value-word presence alone
cannot pass a case. Record irrelevant-but-true answers, omissions, false claims,
conflicts, clarifications and abstentions independently.

Read citations only from accepted evidence/supporting-evidence fields, recursively
using the same whitelist for children. Retrieved candidates, rejected text and
diagnostic IDs never satisfy a proof. Check each child's response against its own
gold; pooled aggregate words/evidence cannot answer the wrong task. Check public
status/answer/audit/judgment consistency and proof licensing before accepting an
aggregate completion claim.

Budget metadata required by a case must be present. Compare requested and effective
parent allocations to child sentence/item ceilings. Measure optional source-backed
producer units independently rather than trusting a runtime `optional_overflow`
flag. Keep mandatory proof/citations/notices separate; if reliable unit attribution
is unavailable, mark overflow measurement unavailable. Do not enforce a hard word
limit the library does not promise. Compare identical tasks under short versus long
Context:, brief/default/detailed and explicit global counts.

Inject one controlled clock into all relevant session stores. Start each independent
script with all session state cleared. A restart probe must create a new process,
reopen the same persisted corpus, and demonstrate that in-memory plans are absent.
Do not call an in-place reset a process restart. Real concurrency requires overlapping
calls, correct store ownership, separate callers/sessions, and captured exceptions.

## Run and report

Implement the scorer/gold corrections first, then run development and frozen holdout
on both arms in isolated databases/namespaces with cached models and recorded head
availability. Include independently authored atomic references for compound cases
in both splits, and publish paired retrieval/proof/coverage differences. Without a
comparable historical arm, make no causal improvement claim about the separator.

At 1k and 10k distractors, re-score factual gold as well as latency. Include a join
whose premises are absent from the first dense shortlist, lifecycle checks, and
three source-order seeds. Report cold/warm timing by outcome and task count,
startup, ingest, peak process/database RSS, and storage. Keep the original timing
protocol where comparable; label changed workloads and unavailable measurements.

Create a new UTC run directory, refuse overwrite, record exact commit/patch,
dependencies/models, redacted environment, scorer version, seeds and byte hashes
of written artifacts. Preserve raw per-child responses and staged retrieval traces.
Write a completed manual adjudication record for every uncertain/failing case and
a seeded 10% sample of passes, not just a review queue.

Report exact denominators per family, prompt, child, conversation, split and arm.
Apply the original readiness gates only to supported contracts, reporting safe
unsupported handling separately. No gate passes on missing measurements. Deliver
`REPORT.md`, versioned metrics, raw data, gold/scorer sources and selftests,
adjudications, reproduction commands, full-suite log, and a prioritized failures
handoff. Keep runtime fixes outside the evaluation run. No commit/push or execution
is requested by this design document.
