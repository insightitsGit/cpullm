# Bounded multi-request separation

`Appliance.ask()` now separates explicit multi-question/command prompts before
embedding. Each task runs the existing single-request pipeline: its own factual
intent, query embedding, scoped/historical retrieval, bounded repair, and final
evidence judgment. Single requests retain their existing path.

```python
result = app.ask(
    "What color is the Cedar, where does it live, and how long does it live? "
    "Answer in three bullets.",
    caller=caller,
    session_id="chat-1",
)
for task in result["task_results"]:
    print(task["id"], task["query"], task["status"])
```

The three query targets are color, location, and lifespan, rather than an entity
incorrectly parsed as `Cedar, where does it live ...`. A unique explicit Cedar
reference binds singular `it`/`its`. If Cedar and Rowan are both candidates, the
separator leaves the reference unresolved and the existing reference loop asks
for the full name. Event/cause descriptions are not treated as entity antecedents.
It does not split arbitrary occurrences of `and`, names such as Research and
Development, quoted questions, fenced examples, or blockquoted source text.

## Long background

Use explicit source/context and request boundaries:

```text
Context: [long background, including an explicit statement naming the Cedar]
Questions:
1. What color is the Cedar?
2. Where does it live?
```

Background stays in `request_plan.background`. Explicit affirmative subject names
can help reference binding, but the text is **not automatically ingested or accepted
as verified evidence**. Answers still require permitted stored sources. This is a
separator for retrieval requests, not a new document-upload or transient-document
QA implementation. Use normal source ingestion when the background itself must
become retrievable evidence.

Each batch task is limited to 1,000 characters; the full prompt is limited to
32,000 characters and eight tasks. The actual installed tokenizer window is also
checked before a batch executes. An over-budget batch asks for restructuring;
extra tasks are not silently dropped. The ordinary single-request embedding path
retains its existing encoder behavior. A long unlabelled narrative mixed with
requests may need the explicit Context:/Questions: form.

## Continuations and completion

Tasks execute in source order and stop at the first clarification. Later tasks
are explicitly `pending`. Send the answer through the same parent `session_id`;
the suspended child conversation resumes before later tasks execute. `cancel` or
`start over` cancels the remainder; a new explicit question abandons it. Parent
plans are in memory, expire after 30 minutes, and are capped at 256. Parent and
child session keys include tenant, caller, scope, and history date. Finished
internal child sessions are cleared so they do not crowd out pending sessions.
Restart loses pending plans, just as it loses ordinary conversation state.

Without a session, no pending parent/child state is saved. Restate unresolved
questions with their missing entity or criterion. After a completed session batch,
only the last user/resolved query is retained for ordinary reference context;
retrieved text and generated answers are not written into that context.

`request_plan.tasks` includes the original task spans, normalized queries, bindings,
and dependencies. `task_results` includes every task's status and full judged
result. If one fact is missing, the other answers remain visible and aggregate
status is `partial`; a waiting clarification uses `needs_clarification`. All
successfully answered tasks produce aggregate status `answered` with verification
`per_task`. The combined `answer` remains `None` and `audit_passed=False`: the
library has not independently audited a new synthesized overall claim. Render
`reply.text` or inspect the individual task results and evidence.

A trailing global style instruction such as `Answer in three bullets.` controls
group presentation. A combined optional-material budget is allocated before child
execution: brief mode allows one unit per task, standard mode shares six units,
and detailed mode shares sixteen. Every task receives at least one unit. Explicit
global sentence/item counts replace that total (up to 160 units); local brief or
count instructions can reduce a child's allocation. A local detailed instruction
does not bypass the shared ceiling. Allocations persist across clarification.
The private child budget caps both overview sentence and list item selection,
while factual relation handling and required proof remain unchanged.

For example, two overview tasks with `Answer in three sentences.` receive optional
budgets of two and one, rather than three each. Long Context: text does not increase
the answer budget. The aggregate renders ordered judged answers without repeating
the full question text; original questions remain in `request_plan.tasks`.
Pending tasks retain their task IDs and explicit notices. Inspect
`response_plan.combined_budget` for the total, per-task allocations and scope.

If a requested item
count is smaller than the task count, all tasks remain visible and the plan marks
`budget_overridden_for_coverage`. Required premises and citations are never cut
to meet a formatting budget. These are producer budgets for optional material,
not hard limits on total rendered length: direct proofs, specialist contracts,
citations, conflicting evidence, and clarification notices can exceed them.
Strict global word counts remain unenforced and are marked as such.

## Boundaries

The raw prompt guard and authorization checks precede batch execution. Source
scope, `as_of`, and other supported options are forwarded to every child. No
external actions are added; only existing `ask()` producers are invoked. Payment
proposals must be submitted separately as single requests. This implementation
does not solve arbitrary ellipsis such as `and its lifespan`, forward references,
unlabelled long documents, semantic workflow dependencies such as `compare those
answers`, or arbitrary natural-language command decomposition. Unrecognized
single forms retain the legacy path rather than claiming a complete plan.

## Validation

`tests/test_request_planner.py` covers boundaries, names/quoted/code content,
singular and ambiguous references, budgets, token preflight, caller/history session
isolation, cancellation, continuations, and early refusals. Live tests in
`tests/test_request_planner_live.py` cover independent channel intents, scoped
retrieval, a complete universal-rule join, missing facts, reference continuation,
and long background with short retrieval queries.

The final full combined checkout run on 2026-10-27 returned **545 passed, 2 skipped,
3 expected failures**, with six existing NumPy warnings, in 71.73 seconds. PostgreSQL/encoder
live tests were enabled. The two skips require missing trained extractor
checkpoints; the three expected failures remain the documented crane cases.
After protecting concurrent first-time parent-session registry initialization,
the focused planner/response-policy run returned **47 passed**, including the new
concurrent-parent test. No new large-corpus or independent accuracy benchmark is
implied. Local logs: `build/request-planner-final-suite.log` and
`build/request-planner-scope-final.log`.
