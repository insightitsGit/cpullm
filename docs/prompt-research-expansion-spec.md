# Design A: Prompt expansion and research planning

Status: proposed specification; documentation only. Date: November 4, 2026.
Implementation baseline: published cpu-llm 1.11.2. No new node is implemented.
Companion: [Design B](six-channel-cycle-exploration-spec.md).
Review and implementation gates: [design review](research-and-cycle-design-review.md).

## Intent and accepted requirements

Convert a short writing request into a fuller structured research plan, retrieve
relevant evidence, then compose the requested document. Expansion adds research
questions, not presumed facts, silently selected goals or invented constraints.
The authoritative artifact is a typed plan; a longer natural-language prompt is
an inspectable rendering of that plan, not a second source of authority.

Support requests for reports, articles, documents, drafts, emails and comparable
deliverables. Long response requests can widen evidence collection within limits;
short deliverables may also require substantial research. Response length and
retrieval depth are separate controls. Never promise length unsupported by evidence.

Preserve the original request, source spans for explicit controls, and provenance
for every interpretation. Ask for clarification when ambiguity changes subject,
scope, required action or interpretation of the evidence.

## Current code and proposed boundary

- `prompt_ingestion.py`: reversible normalization, explicit field expansion and
  optional parser annotations. It must not become a speculative fact generator.
- `request_planner.py`: explicit task separation, clarification continuation and
  parent response budgets. Research questions are children inside the relevant
  user task, not new independently requested tasks.
- `document_workflow.py`: bounded document snapshots, genre sections, coverage,
  pagination and rendering. Its current genre recognizer is narrower than this
  design, notably for emails/memos/proposals; these require explicit additions.
- `response_policy.py`, `flag_contract.py`: current depth/layout routing remains
  authoritative until a versioned extension is implemented and tested.

Proposed insertion: request interpretation -> per-task research plan -> scoped
retrieval, optionally Design B -> evidence judgment -> existing composition,
style verification and rendering. A single coordinator owns the shared budget.
Strict requests retain their existing bypass and answer grammar. A strict
research plan may organize authorized quotations; it must not enable new
inference, ordinary learned producers or tone rewriting.

## Recognition vocabulary v1

This is a bounded, versioned starting vocabulary, not a claim to recognize all
English expressions. Unknown phrases remain preserved or ask for clarification.
Use grammatical context, phrase boundaries and explicit negation/scope handling;
substring hits alone are insufficient. Quoted text and retrieved content are data.

- Deliverable verbs: write, draft, compose, create, prepare, produce.
- Genres: article, report, document, draft, email, letter, memo, proposal,
  specification, design document, briefing, summary, overview.
- Depth/length: brief, short, concise, detailed, comprehensive, thorough,
  in-depth, elaborate, executive summary; explicit word/paragraph/section limits.
- Research facets: what, who, when, where, how, why, explain, investigate,
  describe, define, background, mechanism, process, evidence, limitations.
- Connections: related to, connected to, belongs to, member of, type of, uses,
  depends on, requires, affects, causes. These identify questions, not facts.
- Comparison: compare, versus, differences, similarities, trade-offs,
  advantages, disadvantages. Missing evaluation criteria may need clarification.
- Layout: table, bullets, numbered list, sections, headings, steps, citations,
  references, Markdown, HTML. Preserve current supported-format validation.
- Audience/tone: technical, executive, beginner, formal, neutral, friendly.
  Unsupported combinations do not authorize fabricated style or content.
- Scope/conditions: only, exclude, include, without, before, after, as of,
  within, must, must not, except, unless, if, not, never, source-only.

Negation can disable a facet: “do not explain why” must not add why questions.
“Detailed” does not imply the existing deep agent flag. Explicit API controls
override conflicting inferred presentation; strict/operator restrictions win.
Conflicting explicit instructions require clarification or documented precedence,
not silent selection. Tone remains separate from topic retrieval.

## Plan contract: proposed research-plan-v1

Required fields:

- `original_prompt`, `request_id`, `parent_task_id`, `schema_version`.
- `intent`: genre, subjects with resolved sense IDs, audience, purpose, scope,
  time bounds, output format/tone and response budget.
- `requirements`: values plus origin (`explicit_prompt`, `explicit_api`,
  `confirmed_context`, `template_suggestion`) and source span/context reference.
- `questions`: stable ID, question text, facet, required/optional, prerequisites,
  source/tenant/time scope, channel interests and assigned retrieval budget.
- `expanded_prompt`: deterministic rendering of the plan, marked as instructions
  derived from the user's request, never as knowledge-base evidence.
- `clarifications`, `coverage`, `budget`, `stop_reason`, `status` and plan hash.

Store questions and facts separately. A question's premise remains unconfirmed
until evidence supports it. Context bindings require explicit, scoped references;
do not bind “it” by spelling proximity when several candidates exist.

## Expansion process

1. Interpret explicit controls and bind authorized, unambiguous context.
2. Select a genre template. Sections are research needs, not asserted facts.
3. Produce prerequisite-aware what/how/why/when/where/comparison questions only
   where relevant to purpose. Do not mechanically generate every facet.
4. Clarify mandatory missing information. “Email them about it” has no safe
   recipient/topic if context supplies neither. Missing recipient names can
   remain labeled placeholders in a draft if the user permits that behavior.
5. Retrieve a baseline evidence set under caller/source/as-of restrictions.
6. Expand supported leads through ordinary evidence retrieval or opt-in Design B.
   Replan only under the remaining budget; never recursively invoke this planner.
7. Judge facts and contradictions independently of the plan's desired narrative.
8. Compose from accepted evidence, retain proofs, and report missing coverage.
   Apply requested style only through supported verified transformations.
9. Preserve plan/snapshot identity for pagination and clarification continuation.

For “Write a detailed article about A and B,” first ask whether a connection is
documented. Only then investigate its mechanism. Ask why only when a causal
explanation is relevant; distinguish absence of causal evidence from no cause.
No documented relationship is a valid outcome. Never invent a bridge.

Email templates separate sourced factual content from conventional presentation.
Salutations and sign-offs may be clearly nonfactual formatting; promises,
deadlines, approvals, sender identity and requested actions require explicit
user authority or clarification. Drafting does not authorize sending.

## Budgets and determinism

Proposed defaults, subject to performance validation: at most 16 research
questions per user task, two evidence-driven replan passes, and 64 retrieval
operations across the complete request. These are proposals, not current limits.
Nested tasks and Design B consume the same shared budget; no per-child reset.
Respect existing snapshot, token, output and pagination caps; surface truncation.

For fixed plan policy, evidence snapshot, model versions and operation budgets,
ordering and plan expansion must be stable. A wall-clock deadline can stop at
different points across machines; report partial coverage rather than claiming
identical output or exhaustive search.

## Acceptance scenarios before implementation

- Short Helios report yields relevant questions, independent tone/layout controls
  and only source-supported sections; why is not automatically a causal claim.
- “Brief email” has a short output budget while evidence needs remain explicit.
- No source connects A/B: preserve their independent facts, mark the missing
  connection, do not invent a relationship or run endless replanning.
- Ambiguous entity, missing mandatory context, “best” without criteria and
  conflicting requirements lead to scoped clarification with resumable state.
- Quoted directives, source prompt injection and negated facets cannot activate
  nodes or override source permissions.
- Strict mode, explicit API precedence, multi-task continuation, temporal scope,
  proof retention and total output/retrieval budgets remain intact.
- Small factual/social requests retain their existing path unless expansion is
  explicitly requested or a supported deliverable activates the planner.

See Design B for cycle exploration. A document request alone does not silently
activate expensive loop search in this proposal.
