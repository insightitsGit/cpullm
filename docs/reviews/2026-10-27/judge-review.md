# Code review: channel-evidence judge

Reviewed commit: `0fe9bb7d37663cce4077be3fa0d3aa464f635c64`, against `af39da6`.
Date: 2026-10-27. No library or test implementation was changed during review.

## Assessment

The commit improves channel diagnostics, sense handling, causal binding, and the
existing benchmark. However, the finalizer can still approve an unrelated or
modified response, or record a negative judgment without applying it to the
public answer. It is not yet the authoritative delivery boundary described by
the design and handoff.

## Actionable findings

### R1 — P1: final verification does not cover the complete delivered claims

Locations: `src/cpu_llm/evidence_judge.py:237-250`, `288-300`, `368-381`.

`_allowed` accepts a sentence when it contains a licensed span. This admits
`It is not true that the Cedar is white.` when the only fact is
`The Cedar is white.` The finalizer retains the negated body and returns
`judgment.outcome=answered` and `shine_final.ok=True`.

Separately, when the licensed body occurs in `reply.text`, the code validates the
body and tail but retains the preceding `head` verbatim. A probe prepended
`The access code is 4419.` to the licensed color sentence; the invented fixture
claim survived with a successful reused Shine verdict. No actual secret was used.

The reuse condition accepts a licensed substring rather than an identical verified
deliverable. If reuse is not taken, `body = claim` still makes Shine verify the
licensed template rather than the changed delivered sentence.

Fix: validate all claim-bearing text, preserve polarity and entity bindings, and
verify the actual normalized deliverable. Parse attribution/headings explicitly,
not as arbitrary unverified prefix text. Reuse a verdict only when its checked
claim/evidence/context matches the final deliverable. Add prefix, negation, and
same-sentence clause regressions, not only appended independent sentences.

### R2 — P2: failed channel selection is discarded in favor of the candidate answer

Location: `src/cpu_llm/evidence_judge.py:200-205`.

If the selector recognizes a request but finds no matching evidence, its
`insufficient_evidence` decision is reset to `None`. `_spans` then uses the prior
candidate's evidence/body, and the candidate's `answered` status survives.

Reproduction: ask `What color is the Larch?` with a candidate saying Cedar is white
and only the Cedar fact in the turn. The judge reports entity `larch`, outcome
`answered`, evidence about Cedar, and a successful final Shine verdict.

Fix: distinguish an unsupported selector (`None`) from a recognized request with
failed proof. The latter must reject the candidate or request clarification; it
cannot fall back to the unsupported producer assertion. A source-supported fact
about the wrong entity is still not a supported answer to this request.

### R3 — P2: a conflict judgment does not change the public answer

Locations: `src/cpu_llm/evidence_judge.py:217-218`, `277-280`, `344`.

The selector correctly detects two Cedar colors and sets the judgment outcome to
`conflicting`. `_reject_unlicensed` immediately returns for that outcome, and the
final Shine branch is skipped. Nothing applies the conflict to the old reply.

Reproduction: a prior white answer with both white and red facts returns
`judgment.outcome=conflicting` alongside `answer_status=answered`,
`answer="The Cedar is white."`, and the same positive reply.

Fix: apply every structured outcome to public fields atomically. A conflict must
clear the asserted answer, render the conflict, and preserve its conflicting
evidence as evidence of disagreement. Do not merely attach the negative verdict
as diagnostic metadata.

### R4 — P2: specialist flags bypass both structural checks and final Shine

Locations: `src/cpu_llm/evidence_judge.py:191-199`, `277-278`, `417-418`.

Any listed specialist flag with no ordinary requested relation sets
`verification=specialist_contract`. This is a label, not a verified result from a
specialist adapter; it bypasses both final text checking and Shine.

Reproduction: a summary with one authorized color sentence and an appended
unsupported access-code claim returns the whole text unchanged. Its final record
only says the specialist contract was not checked.

Fix: preserve each specialist's supported behavior through an explicit producer
contract/proof, not a blanket flag-based exemption. Require the produced text to
match that proof, and verify later modifications. Include summaries and at least
one numeric specialist in negative late-modification integration tests.

### R5 — P2: a final Shine hold leaves rejected content in public reply fields

Location: `src/cpu_llm/evidence_judge.py:404-415`.

On final Shine rejection, the code replaces `reply.text` and clears top-level
answer evidence, but leaves `reply.body`, `reply.supported_text`, and existing
reply evidence untouched. The held judgment can also retain its evidence without
clearly separating rejected-candidate diagnostics from delivered-answer fields.

A controlled test forces `verify_grounding` to return a hold. The result says
`insufficient_evidence` in status/text while `reply.body` still contains the
rejected asserted color sentence. Consumers rendering the documented body field
can therefore display held content.

Fix: synchronize the entire public response on a hold. Use a dedicated diagnostic
field for the rejected candidate if retention is needed, and add assertions for
body, supported text, nested evidence, status, verification scope, and audit state.

## Verification and evidence

- Focused existing tests: **41 passed** (`test_evidence_judge`,
  `test_shine_enforcement`, `test_prompt_intent`, `test_design_connections`).
- Full suite on a fresh isolated local PostgreSQL 18 database: **487 passed,
  2 skipped, 3 strict expected failures, 6 existing NumPy warnings in 71.96 s**.
  Live tests were enabled; no deselection. The two skips require missing trained
  extractor checkpoints. The three expected failures are the documented crane cases.
- Replayed 41 turns per arm using the existing Millhaven harness/corpus:
  **17/18 factual cases and 5/5 completed conversations in each arm**. This improves
  the preceding resonance run's 9/18; dense remains at 17/18. The missing synonym
  remains. The causal case remains a contract disagreement rather than a false
  claim. Dense bare spring abstains instead of asking, which still fails that
  case's clarification expectation.
- The above actionable findings are targeted finalizer boundary probes, not
  claims that the ordinary Millhaven questions themselves produced those failures.
  That distinction explains why the full suite and narrow replay can pass while
  these negative cases remain unprotected.
- No new large-corpus, ingestion-cost, or memory benchmark was run.

Ignored local evidence:

- `build/judge-review-unit-1027.log`.
- `build/judge-review-live-1027.log` (suite and replay).
- `build/benchmark-review-1027_judge/dense.json` and `resonance.json`.
- `build/judge-review-probes-1027.jsonl`.
- Reproducers: `build/probe_judge_review_1027.py`,
  `build/probe_judge_specialist_1027.py`, `build/probe_judge_prefix_1027.py`.

The local cluster was stopped after validation. Benchmark baseline artifacts were
not overwritten. Recommended next action: add the failing boundary cases as tests,
then make judgment application and final-text verification authoritative before
relying on `shine_final.ok` as approval of the actual response.
