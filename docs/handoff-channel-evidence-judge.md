# Implementation handoff: channel-aware evidence judge and final PrismShine gate

Prepared 2026-10-26 against `af39da6f10fa8ef41e1d10bc31323829af8652f6`.
The user authorized implementation, then requested this handoff for another agent.
No implementation changes were made in this handoff turn. Inspect current HEAD
and local instructions before starting; other work may have landed subsequently.

## Objective and user intent

Use the user's prompt assessment across VectorPrism's six channels to select a
response supported by matching evidence, then verify it through the existing
PrismShine integration. The user's word "tone" means requested meaning/relationship
here; politeness or urgency is not evidence of a factual relationship.

Do not add another heuristic stage that competes with reply selection. Establish
one structured delivery decision; downstream rendering must preserve it. Several
channels may participate in a proof. A membership-plus-possession join needs both
type and relational evidence, not just a single highest-scoring channel.

Channel similarity is a routing signal, not proof. Match the entity, relationship,
direction, scope, temporal validity, and complete premises. Do not require numerical
equality between prompt and sentence vectors or manufacture confidence from
uncalibrated prototype scores.

## Read these first

- `docs/current-design.md`, `docs/resonance-tags.md`.
- `docs/reviews/2026-10-26/benchmark-followup-review.md` (review of earlier code).
- `docs/benchmarks/2026-10-25-baseline/REPORT.md` (historical baseline).
- Latest local run: `build/benchmark-2026-10-26/ASSESSMENT.md`, `summary.json`,
  `responses-dense.json`, `responses-resonance.json`, and before/after snapshots.
  These local artifacts are ignored by Git; preserve them if unavailable elsewhere.
- `src/cpu_llm/prompt_intent.py`, `connection_channels.py`, `attribute_search.py`,
  `answerability.py`, `grounding.py`, `pipeline.py`, and `agents/reply.py`.
- Tests: `test_prompt_intent.py`, `test_shine_enforcement.py`,
  `test_design_connections.py`, `test_review_regressions.py`,
  `test_resonance_groups.py`, and the opt-in `test_join_pipeline.py`.

## Verified PrismShine integration and its gaps

The installed package reports `prismshine==0.2.2`; its imported source is currently
`C:/code/PrismShine/prismshine`. That sibling repository is a dependency, not part
of this task's default writable workspace. Prefer an adapter in CPU-LLM and do not
assume permission to edit the sibling project.

`grounding.shine_gate()` currently builds a gate with `judge=None`,
`ShineConfig(judge_provider=None, disable_tier3=True)`. Runtime inspection confirmed
no judge and Tier 3 disabled. Existing checks still inspect grounding/coverage,
contradiction signals, and numeric copies; hard flags can withhold delivery.

The optional Tier-4 judge is a callable `(claims, context) -> JudgeResult`; its
built-in providers are cloud LLM adapters. CPU-only implementation does not require
enabling them. A custom local callable is supported, but its default arguments do
not directly carry the question, scope, relationship request, or proof graph.
Introduce the necessary explicit request-local adapter/context rather than hidden
shared mutable state. Tier-4 escalation is conditional and budgeted, so mandatory
structural checks must not rely on every request reaching that tier.

Current order is roughly grammar -> Shine -> optional specialists -> Model01 ->
reply. `ask()` can then apply realization/account output or replace the reply with
a ranking quote/clarification. A final Shine verdict must cover the actual final
deliverable, not an earlier answer that was subsequently replaced.

Sense clarification returns before `graph.invoke`, so it never reaches the current
Shine node. Merely turning on Tier 4 cannot fix false Cedar ambiguity.

## Required behavior and integration plan

1. Define a typed, versioned judgment result. Include the requested entity,
   relationship/direction, active channel rationale, outcome, reason codes,
   selected evidence IDs/spans, supporting proof edges, and verification status.
   Outcomes should distinguish answer, evidence quote, clarification, insufficient
   evidence, conflict, unsupported, and an existing execution/security hold.
2. Reuse `route_prompt` and existing source-backed selection/joins. Do not create
   a second dictionary or unrelated routing implementation. Explicit recognized
   forms and available trained heads have different evidential roles; expose both.
3. Resolve whether competing candidates identify distinct referents or merely
   different properties of one entity. Neither cluster size nor the existence of
   an attribute request establishes this. Preserve clarification when identity
   cannot be established. Compatible classes must not automatically become
   competing entities. If new metadata is needed, make it source-backed.
4. Pass only authorized, temporally applicable evidence to the judge. Every join
   premise and alias edge must be individually supported. Keep scope, session,
   tenant, and historical contexts separate. Similarity cannot override a denied
   source or missing premise. Retain existing fixed retrieval budgets.
5. Integrate the judgment before committing an early sense response and at the
   final delivery boundary. Centralize the decision so reply composition and
   specialist output cannot independently restore rejected content.
6. Reuse PrismShine for final grounding verification, with an explicit role for
   local structural proof checks. Check the actual deliverable after all producers
   and `ask()` postprocessing. Preserve existing guard/audit/grammar/Shine holds;
   a judge must not lift a hold merely because another source sentence looks useful.
7. Synchronize `answer`, `reply`, statuses, evidence, `needs_clarification`,
   `verification_scope`, and audit flags with the final judgment. A changed answer
   cannot inherit an earlier audit verdict. Conflicting evidence should remain
   visible with the conflict outcome, without becoming an asserted answer.
8. Add observable diagnostics explaining channel selection, accepted/rejected
   premises, ambiguity reasons, and final Shine resolution. Keep rejected
   candidates out of public answer fields. Bound judgment work and sense choices.

Exact module names and graph placement are implementation choices. Avoid duplicated
decisions hidden in both a graph node and an `ask()` wrapper. A shared finalizer may
be appropriate because both graph output and wrapper postprocessing can alter text.
Keep the existing early grounding gate if useful, but distinguish it from final
verification so its metadata cannot be mistaken for a verdict on later text.

## Concrete acceptance cases

- **Cedar color:** one ferry with color, engine, place, and departure facts answers
  white. These properties must not trigger a meaning-selection question.
- **Genuine ambiguous bat:** stored mammal and wooden-club referents require a sense
  clarification for `What kind of thing is the bat?`; do not pick the first class.
- **Cedar possessions:** direct engine plus municipal-ferry membership plus
  `Every municipal ferry has a life raft.` preserves the complete licensed answer
  and cites all three premises. Denying either join premise must remove the
  derived raft claim without discarding the authorized direct engine fact.
- **Causal binding:** an explicit Cedar/diesel cause can answer that exact causal
  request. The same because-sentence cannot answer a Larch question or a different
  Cedar action. The mere presence of "cause"/"because" is insufficient.
- **Missing facts:** captain missing means missing evidence, not several meanings
  of Cedar. Unsupported forms use the declared unsupported outcome consistently.
- **Final producer changes:** a specialist, Model01, ranking follow-up, or optional
  realization cannot append unverified facts after the final decision. Include a
  negative test that injects a changed final sentence and verifies rejection.
- **Ranking:** user criterion is required; quote supported rankings with source
  attribution. Do not submit user preferences as verified facts or lose existing
  ranking-loop behavior when adding the final verifier.
- **Security/history:** blocked and empty-scope turns still refuse before evidence
  lookup; stateless clarifications retain no state; simultaneous source scopes do
  not leak; correction/restart/as-of and five-digit source deletion keep working.
- **Other supported paths:** math, finance, frames, summaries, and document output
  retain their own evidence contracts. Do not reject all of them merely because
  `route_prompt` lacks an ordinary factual relation. Add integration coverage for
  the changed boundaries rather than blanket bypasses.

## Latest benchmark facts and how to validate

The saved `af39da6` run has 30 paragraphs and 41 turns per arm:

- Dense: 17/18 factual cases, 5/5 conversations, 4/4 abstentions.
- Resonance: 9/18 factual cases, 4/5 conversations, 3/4 abstentions.
- Resonance false Cedar ambiguity is the main regression from the preceding
  review's 16/18 replay. Its lifecycle/restart replies also still withhold bell and
  flag facts; deletion receipts alone do not diagnose the reply failure.
- 10,000-paragraph scoped lookup: 0.078 s dense, 2.014 s resonance. Small-corpus
  resonance median is an early clarification, not a faster factual answer.
- Memory readings are null. No fresh complete pytest result was included with
  this saved run; do not reuse an older suite count as the new implementation's result.

Run focused regressions, then the entire suite with live PostgreSQL tests in a
disposable database and cached encoder assets. Use fresh namespaces and keep the
test configuration and exact source snapshot with the results. Explain skips and
strict expected failures. Keep offline/CPU operation; do not activate external LLM
calls or silently download models for this task.

Replay both benchmark arms into a fresh output directory using the harness's
current output-directory option (inspect its CLI). Preserve all historical results.
The existing scorer still expects the explicit why/diesel cause to be unsupported.
Resolve/version that contract explicitly; do not label a sourced cause false solely
to match the old expectation or silently edit the old corpus. Separate false claims,
incomplete answers, unnecessary clarifications, and abstentions in the report.

Add an independently written holdout containing repeated names, real ambiguity,
missing facts, incomplete proofs, unauthorized premises, and changed final text.
Success is improving those cases while retaining the original cases, not another
Cedar-specific exemption. Keep resonance opt-in until evidence supports changing
that default. Source-specific synonym extraction remains a separate follow-up
unless essential to this judge; do not expand this task into a general NLP rewrite.

## Deliverables

- Working implementation with regression and live integration coverage.
- Updated design and consumer documentation describing the final decision owner,
  PrismShine's role, channel limitations, failure outcomes, and diagnostics.
- Fresh full-suite evidence and before/after dense/resonance benchmark artifacts.
- A short handoff listing remaining limitations, source revision, reproduction
  commands, measured costs, and any dependency changes. Do not claim general intent
  understanding or factual truth merely because evidence verification passes.
