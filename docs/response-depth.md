# Response-depth classification

`classify_response_request` in `cpu_llm.response_policy` is a bounded,
deterministic CPU classifier. It does not load a language model. `ask()` returns
its `response_plan` so an application and the delivery judge can inspect the
selected detail level, presentation format, budgets, matched directives, and
the normalized `content_query`.
Blocked prompts and empty authorization scopes keep their fast refusal path and
may omit the plan; classification does not run before those checks.

Examples:

- `Briefly explain the Cedar.` selects a one-sentence factual overview.
- `Explain the Cedar in detail.` selects an overview of up to eight supported
  sentences and a twelve-candidate initial retrieval budget.
- `Give a comprehensive overview of the Cedar.` uses the same detailed mode.
- `Explain the Cedar in three bullet points.` selects up to three supported items.
- `In one sentence: What color is the Cedar?` preserves the factual color request;
  it does not turn it into a general overview.

## Contract

The default detail level is `standard`. Overview/summary budgets are one sentence
for `brief`, three for `standard`, and eight for `detailed`. List budgets are
three, eight, and twelve respectively. Explicit sentence/item counts override
the corresponding budget, clamped to 1–20. The plan retains the original requested
count so clamping is visible. The latest recognized explicit depth cue wins.

Budgets are ceilings for optional source-backed overview/list material, not
promises to fill every slot. If only two eligible facts exist, a request for eight
does not create six more. Required proof premises, qualifications, and conflicting
evidence are not truncated to make a direct factual answer fit a presentation
limit. The classifier records word-count requests, but strict word-count generation
is not implemented (`word_limit_enforced=False`). There is no global hard token
or word cap, and existing document/specialist producers retain their contracts.

Recognized presentation prefixes/suffixes are separated from the retrieval query.
The original prompt remains available in `original_message` when it differs from
the executed query. General explanations with an explicit depth/count request and
overview requests use source-backed summaries; causal questions retain the causal
path. Explicit overview/list rendering uses the selected material directly, rather
than prepending the previous unrestricted body and defeating the budget.
Overview control phrases are protected from corpus typo correction: `Tell me
about` must not become `Bell me about` just because a source mentions a bell.
Typo correction still applies to the requested subject.

The six-channel factual intent remains independent from response depth. Ordinary
subject attributes such as `short claws`, `long lifespan`, and `detailed balance`
do not request verbosity changes. Double-quoted titles/terms are masked during
style classification. Unrecognized instructions keep defaults. This is not a
general natural-language understanding model or a calibrated complexity score.

Detailed mode increases only the initial bounded retrieval candidate count. Scope,
historical filtering, existing graph/repair budgets, and grounding requirements
still apply. More candidates are not proof of complete topic coverage. Automatic
decomposition of arbitrary multi-part questions, adaptive retrieval for every
requested subtopic, session-persistent style preferences, and strict word limits
remain future work. The plan is request-local and does not carry presentation
preferences across a later clarification reply.

## Validation

`tests/test_response_policy.py` covers classification, false triggers, count bounds,
normalized intent, graph integration, producer budgets, duplicate-body prevention,
and preservation of a multi-premise join despite a one-sentence request.
`tests/test_response_policy_live.py` provides opt-in PostgreSQL/encoder integration
checks for brief versus detailed overviews and a three-bullet request. These run
with `CPU_LLM_LIVE_TESTS=1` and a disposable database.

The classifier does not bypass the final evidence judge or lift any guard,
audit, grammar, or Shine hold. The response plan is passed through the graph and
returned alongside its judgment; coverage/completeness must not be inferred solely
from the length of the answer.

Validation on 2026-10-27: the complete working-tree suite with live PostgreSQL
tests enabled returned **516 passed, 2 skipped, 3 expected failures**, with six
existing NumPy warnings. Both new live response-depth tests passed. The skips need
trained extractor checkpoints; the expected failures are the existing crane cases.
After adding preservation of newline-sensitive untargeted requests, a focused
classifier/finance run returned **43 passed**. Local logs are
`build/response-policy-verified-suite.log` and
`build/response-policy-structured.log`. This validates the combined checkout,
including the concurrent judge fixes; it is not a new independent quality benchmark.
