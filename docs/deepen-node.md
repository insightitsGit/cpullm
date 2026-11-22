# Deepen node

Frontier searches wide and returns many candidate hypotheses. Deepen takes **one** hypothesis and examines it
link by link over one authorized snapshot.

## Triggers

- `Deepen: <hypothesis>.` in chat. The text must use a Frontier form, for example "A may constrain C through B.",
  "A and B may jointly drive C.", "Gains in C from A may be offset by B." or "A and B may move together because both
  depend on C."
- `ask(message, deepen=<hypothesis>)` in Python. Passing a hypothesis object from a Frontier receipt is the most
  precise form, because it carries the exact anchors and the relation of each edge. A string, or `deepen=True`
  (which reads the message), is also accepted.
- `"deepen": <text | object | true>` on `/v1/ask`.

Deepen cannot be combined with Frontier or another specialist in one request.
Frontier can automatically check several leading proposals; callers can also
deepen selected entries in separate requests. No single winner is forced and
the new assessments do not remove alternatives.

## What it returns (`deepen` receipt)

| Field | Content |
|---|---|
| `links` | One entry per adjacent path link, including all three links of a two-mediator chain; A → C and B → C for a shared target; C → A and C → B for a shared source. Each entry has its supporting edges, its contrary edges (opposite direction, or negated), co-mentions, and a `status`: `supported`, `contested`, `counter_only`, `weak` (co-mention only) or `missing`. |
| `verdict` | `all_links_supported`, `partly_supported`, `contested`, `unsupported` or `incomplete` |
| `predictions` | Source sentences with a prediction marker that name at least two of the hypothesis terms |
| `setups` | Source sentences describing experiments, datasets or benchmarks that involve its terms |
| `confounders` | Other causes of the outcome stated in the sources, each cited |
| `test_plan` | The design (mediation, 2×2 factorial or common cause), what to manipulate, measure and block, the controls (the confounders), steps, and `fails_if` |

Text hypotheses retain their requested end-to-end direction. Chain evidence is composed using the same relation rules as Frontier; two negative links can support a positive effect. `direction_check` reports consistent, contradicted, contested, unresolved or unspecified direction. Local link support alone does not establish the requested end-to-end effect.

Directions are compared by sign. `constrains` counts as capacity-positive (more A allows more B), so a source saying
that A *reduces* B contradicts it. Links reuse Frontier's relation graph and parse cache, its related-term matching,
and, when the appliance has an encoder, the cosine check on head-noun bridges.

## Automatic use inside Frontier

A Frontier run in the appliance checks its first five entries with Deepen by default (`frontier={"deepen_top": n}`,
0–10). It passes its own relation graph, bridge check and sentence index to `run_deepen(..., graph=..., similar=...,
sentences=..., budget=...)`, so the snapshot is read and parsed once and every child shares the same request deadline. Each checked entry carries `check.verdict` and per-link
statuses. Contested entries are flagged in the reply with the contrary quotes.

**Reading the verdicts.** Each Frontier entry is built from source edges, so each of its links has at least its own
premise, and "all links supported" is close to guaranteed for those entries. This does not validate the proposed composition or its setting assumptions. The informative results are
`contested` (a source states the opposite or negates a link) and `missing`/`weak` (a link rests on a bridge that no
source states). For a hypothesis written by a person, every status is informative.

## Contract

The hypothesis remains `UNVERIFIED_HYPOTHESIS` with `promotion: blocked`. Nothing is written to the index. The
standard invention note is appended. Strict evidence mode disables Deepen. The execution stages are recorded in
`routing.post_stages`: `deepen_snapshot`, `deepen_links`, `deepen_evidence`, `deepen_plan`.

Evaluation: [docs/reviews/2026-11-21-deepen/report.md](reviews/2026-11-21-deepen/report.md).


## Correctness and budget contract (2026-11-21)

- Structured hypotheses validate patterns, anchor/path lengths, nonempty string
  terms and citation shapes before source retrieval. Invalid objects request
  clarification rather than producing an unhandled exception. Citation order does
  not determine the expected path relation.
- A chain carries every intermediary. `path_nodes` lists the full ordered path;
  `test_plan.mediators` lists every mediator to test. The compatibility parser
  tuple retains its single `b` field; use `read_hypothesis(...).links()` or receipt
  `path_nodes` for multi-mediator paths.
- Negation identifies the exact subject/relation/object proposition and retains
  its document, quote, offsets and hash. “Does not reduce” is not counter-evidence
  against “increases.” Other observed negations remain visible under `negations`.
- Guard and strict-mode policy apply before numbered session recall, including
  missing-session and invalid-number clarifications.
- Preparation, encoding and link/clue scans check the shared ledger. Encoding
  calls cannot be forcibly interrupted; deadlines are checked before and after.
  Expiry yields an incomplete receipt and a partial public Deepen response.
- No candidate becomes a verified fact, no KB write is introduced, and the
  existing breadth/result/path limits are unchanged.

[Fix specification and verification](frontier-deepen-correctness-spec.md).

## Research assessments (unreleased, after 1.15.0)

See the [strengthening specification](deepen-research-strengthening-spec.md).
These additions annotate proposals without changing Frontier enumeration,
ranking, diversity or result limits:

- `composition` separates component support from composition assumptions and an
  untested joint interaction. Changed endpoint modifiers trigger semantic review.
  Exact labels still do not establish semantic identity. This is a heuristic
  review, not a scientific-validity certificate.
- `composition.qualifications` keeps cited conditional/quantified statements.
  `source_contexts` and `scope_differences` retain explicit context metadata or
  plain-text `Workload: ...`, `Model: ...`, `Population: ...`, `Domain: ...`,
  `Version: ...`, `Regime: ...`, and `Temperature: ...` lines in ingested chunks.
  Missing context stays unknown; different contexts require review.
- `test_plan.variables` contains exact variable labels, user definitions, cited
  measurement hints and missing requirements. `readiness` is `needs_input` or
  `specified_for_review`, never proof that an experiment is valid or executed.
- `confounders` remains for compatibility, but items now carry `role`,
  `exposure_evidence`, `downstream_evidence` and a recommended action. Additional
  outcome causes are candidate controls. Evidence of a shared cause or downstream
  variable calls for causal review, not automatic adjustment.
- `test_plan.interaction_test` distinguishes the joint interaction contrast from
  individual effects. A zero contrast does not disprove those individual effects.
- `research_actions` lists unresolved requirements. After a Deepen response in
  the same session, `Go deeper`, `Explain more`, or `Deepen further` rechecks the
  authorized snapshot and focuses on a different requirement, with relevant
  evidence/measurement hints. `progress` reports whether source content changed;
  showing a requirement does not resolve it. An exhausted queue asks for inputs.
  A different request supersedes the Deepen focus. Use sequential requests within
  a session and separate sessions to explore alternatives independently.
- `novelty_review` is optional. Co-mentions in the authorized snapshot are
  potential overlap, not a prior demonstration. Absence is not scientific novelty.

### Supply operational definitions

Existing hypothesis strings/objects still work. An envelope adds review options:

```python
result = app.ask("Review this proposal.", session_id="bandwidth-study", deepen={
    "hypothesis": "Memory bandwidth may increase serving revenue through inference throughput.",
    "definitions": {
        "memory bandwidth": {"levels": ["configuration A", "configuration B"], "feasible": True},
        "inference throughput": {"measurement": "completed output tokens / elapsed time", "unit": "tokens/s"},
        "serving revenue": {"measurement": "sum of settled serving invoices", "unit": "USD/day"},
    },
    "protocol": {"replicates": 10, "acceptance_criterion": "pre-registered effect interval"},
    "novelty": True,
    "external_review": False,
})
follow_up = app.ask("Go deeper.", session_id="bandwidth-study")
```

Use the exact variable labels from the hypothesis; unknown definitions request
clarification. Definitions/protocol are user-supplied assumptions, not stored
facts or evidence. The example's repeat count is illustrative, not a power
analysis or recommendation. Review feasibility, causal identification, sample
size, uncertainty and acceptance thresholds before running an experiment.

### Optional external literature adapter

No network access is added by default. An operator may pass
`Appliance(..., literature_reviewer=my_reviewer)`. The callable receives keyword
arguments `query`, `max_results=6`, and `timeout_seconds`, and returns up to six
objects with `title`, an HTTPS `url` without credentials, and `excerpt`.
It is invoked only when a request sets both `novelty=True` and
`external_review=True`. The operator owns provider credentials, literature
coverage, network policy and timeout enforcement. Registration authorizes sending
hypothesis terms to that provider; no arbitrary endpoint is accepted from chat.

Returned records remain `external_overlap_candidate_not_kb_evidence`, separate
from component evidence and never ingested automatically. Provider errors and
invalid records produce an unavailable status, not an invented literature review.
Calls share the request deadline, checked before and after; in-process callbacks
cannot be forcibly interrupted and must honor the supplied timeout. Strict mode
and guard policy take precedence over session recall, source reads and adapters.
