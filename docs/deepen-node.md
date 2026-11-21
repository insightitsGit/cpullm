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

## What it returns (`deepen` receipt)

| Field | Content |
|---|---|
| `links` | One entry per link: A → B and B → C for a chain; A → C and B → C for a shared target; C → A and C → B for a shared source. Each entry has its supporting edges, its contrary edges (opposite direction, or negated), co-mentions, and a `status`: `supported`, `contested`, `counter_only`, `weak` (co-mention only) or `missing`. |
| `verdict` | `all_links_supported`, `partly_supported`, `contested` or `unsupported` |
| `predictions` | Source sentences with a prediction marker that name at least two of the hypothesis terms |
| `setups` | Source sentences describing experiments, datasets or benchmarks that involve its terms |
| `confounders` | Other causes of the outcome stated in the sources, each cited |
| `test_plan` | The design (mediation, 2×2 factorial or common cause), what to manipulate, measure and block, the controls (the confounders), steps, and `fails_if` |

Directions are compared by sign. `constrains` counts as capacity-positive (more A allows more B), so a source saying
that A *reduces* B contradicts it. Links reuse Frontier's relation graph and parse cache, its related-term matching,
and, when the appliance has an encoder, the cosine check on head-noun bridges.

## Contract

The hypothesis remains `UNVERIFIED_HYPOTHESIS` with `promotion: blocked`. Nothing is written to the index. The
standard invention note is appended. Strict evidence mode disables Deepen. The execution stages are recorded in
`routing.post_stages`: `deepen_snapshot`, `deepen_links`, `deepen_evidence`, `deepen_plan`.

Evaluation: [docs/reviews/2026-11-21-deepen/report.md](reviews/2026-11-21-deepen/report.md).
