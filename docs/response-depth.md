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
- `Give me a long response about the Cedar.`, `Please elaborate on the Cedar.`
  and `Tell me more about the Cedar.` select a detailed, source-backed overview.
- `What color is the Cedar? Please give a long answer.` keeps the color slot;
  it does not append unrelated facts to make the reply longer.
- `Explain the Cedar in 20 sentences.` allows up to 20 supported sentences and
  requests 24 initial retrieval candidates rather than the standard five.
- `Explain the Cedar in three bullet points.` selects up to three supported items.
- `In one sentence: What color is the Cedar?` preserves the factual color request;
  it does not turn it into a general overview.

## Contract

The [flag map](prompt-flag-map.md) connects length and expansion indicators to
validated numeric budgets in `retrieve`/`brief`. It does not map them to the
separate deep-search or creative agents. See the
[routing enforcement specification](flag-routing-review.md) for precedence,
holds and fail-closed contract checks. Benchmark v3 revision 2 independently
tests these bindings, including trace evidence and invalid internal plans.

The default detail level is `standard`. Overview/summary budgets are one sentence
for `brief`, three for `standard`, and eight for `detailed`. List budgets are
three, eight, and twelve respectively. Explicit sentence/item counts override
the corresponding budget, clamped to 1–20. The plan retains the original requested
count so clamping is visible. The latest recognized explicit depth cue wins.

Budgets are ceilings for optional source-backed overview/list material, not
promises to fill every slot. If only two eligible facts exist, a request for eight
does not create six more. Required proof premises, qualifications, and conflicting
evidence are not truncated to make a direct factual answer fit a presentation
limit. Word-count requests now inform an estimated sentence/item allocation:
one optional unit per 25 requested words, rounded up and clamped to 1–20. Explicit
sentence/item counts take precedence over that estimate. This is a planning
heuristic, not strict word-count generation (`word_limit_enforced=False`). There is no global hard token
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

The plan exposes three prompt-derived `flags`: `long_response`,
`expand_retrieval` and `extended_overview`. Detailed wording or a larger explicit
unit allocation activates the first two; the third additionally requires a
general overview request. The existing retrieval node consumes `retrieval_budget`,
and summary/list composition consumes the sentence/item budgets before final
judgment. Ordinary prose uses five initial candidates, a normal detailed overview
uses twelve, and larger requested outputs scale with the optional-unit allowance
plus four candidates (currently up to 24 after the 20-unit clamp). Detailed bullet
lists can therefore retrieve more candidates than detailed prose. Search-call
and missing-attribute repair limits remain unchanged.

Length instructions are recognized in explicit request positions, including a
trailing `Please include more details.` or `Please give a long response.` These
trailing instructions can apply to all children of a separated request. Quoted
and fenced text and negated length directives do not activate the flags.
These are per-request intentions, not evidence that a long answer was possible.
For existing installs, the output is still assembled from licensed source claims
and deterministic constructions; no free-form language decoder was added.

Detailed mode increases only the initial bounded retrieval candidate count. Scope,
historical filtering, existing graph/repair budgets, and grounding requirements
still apply. More candidates are not proof of complete topic coverage. Automatic
decomposition of arbitrary multi-part questions, adaptive retrieval for every
requested subtopic, session-persistent style preferences, and strict word limits
remain future work. The plan is request-local and does not carry presentation
preferences across a later clarification reply.

Explicit separated requests additionally share a combined optional-material budget;
see [request separation](request-separation.md). It caps child overview/list budgets
before production and persists during parent-plan clarification. It does not impose
a hard word limit or truncate mandatory evidence after judgment.

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

Latest validation on 2026-10-28 after prompt-derived long-response flags:
**676 passed, 2 skipped, 3 expected failures** in 80.98 seconds, with the same six
NumPy warnings. The live long-response case requested 20 sentences from a corpus
containing nine eligible facts, verified the 24-candidate retrieval allowance,
and returned a shorter supported summary with accepted evidence instead of
padding. Focused regressions cover conversational length requests, scoped factual
questions, quoted/fenced text, negation, larger sentence counts and approximate
word-based allocation. The local full-suite log is `build/response-flags-suite.log`.
