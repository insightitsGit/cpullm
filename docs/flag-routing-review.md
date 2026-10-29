# Prompt flag wiring: review and enforcement

Reviewed 2026-10-29 against the implementation after `c8398a0`.
The [28-row mapping table](prompt-flag-map.md) and
[machine-readable mapping](prompt-flag-map.json) are generated from
`cpu_llm.flag_contract.FLAG_BINDINGS`. The JSON is tested for exact agreement
with that registry. This document explains the routing semantics and fixes.

## The mapping is not one flag = one new agent

There are three different effects:

1. **Agent switches** select optional graph nodes: deep search, creative gathering/
   imagination, comparison, summary/explanation/list/source handling, arithmetic,
   finance and event frames. Document drafting is inside `reply`; there is no
   separate graph node named `draft`.
2. **Budget controls** influence `retrieve` and `brief` through validated numeric
   budgets. A long answer does not activate the separate `deep` search agent.
   A detailed direct color question stays a color question; it does not force a
   broad summary or add unrelated facts.
3. **Presentation controls** choose post-judgment Jinja2/Tabulate rendering. HTML,
   Markdown, tables and reports do not select new factual agents or skip judging.
   Bullet/numbered overviews additionally select the existing list producer through
   the interpretation/response plan; direct factual answers retain their slot.

The six channel nodes are always evaluated on a normal allowed graph path.
`prompt_intent.channels.<name>.active` influences interpretation/ranking, not
whether a node is physically registered or skipped. Activation is not proof, and
does not imply its projection head is enabled or trained. The engine returns
actual channel metadata separately from initial interpreter rule cues.

## Normal request lifecycle

Caller/source scope and raw-prompt guards run before the optional NLP model and
request planning. Early clarification can return before graph execution. Each
executable child then uses its own resolved query, scope/time, response plan and
complete graph pipeline.

The normal fixed graph chain is:

```text
guard → retrieve → resonate → dense → relational → disentangled
→ hyperbolic → identity → causal → catalog → detail → spans
→ think → cognize → grammar → shine
```

After Shine, optional consumers have one authoritative order:

```text
deep → gather → imagine → compare → brief → math → finance → frame
→ model01 → reply → discover (only when explicitly enabled)
```

Only requested optional agents run. `gather → imagine` is a fixed pair for creative
requests. `brief` runs once for any combination of summarize/explain/list/sources.
Later requested agents still get their turn; choosing an earlier one must not
erase the remaining switches. `model01` is the normal bounded sentence stage,
not an LLM generation flag. `reply` is followed by final assessment and optional
layout rendering outside the graph.

## Holds and precedence

- Raw guard rejection prevents retrieval and all optional execution.
- Delivery/audit/Shine holds skip agents that consume retrieved claims: deep,
  gather/imagine, comparison, brief and frame. These holds are rechecked between
  optional stages, not only at the first branch.
- Arithmetic and finance can still inspect explicit prompt fields after a
  retrieved-claim hold. Their own producer contracts and final judging still apply.
  A raw guard block does not permit either one to run.
- `model01` may still execute after a delivery hold so it can return a bounded
  nonanswer. Its existing hold logic may not restore rejected facts.
- `discover` is an explicit API option, not a prompt-format flag. It can suggest
  follow-up queries after an allowed reply; suggestions are not licensed factual
  conclusions and do not make missing evidence available.
- Sources/citations are required by evidence contracts regardless of whether the
  user additionally asks for source display. A `sources` switch is not permission
  to cite arbitrary retrieved neighbors.

## Corrections made by this review

The earlier routing callbacks duplicated priority logic and did not consistently
recheck all delivery-hold indicators after an optional agent. They now delegate
to `next_optional()` in the flag contract. Registration validates every mapped
graph consumer exists, and each optional node checks that it was requested and
is permitted by the current guard/hold state before executing.

Presentation flags were previously descriptive without a common consistency
check. Classification and rendering now enforce agreement among flags, mode,
format, media and budgets. Unknown/missing/nonboolean flags, mismatched HTML or
table selectors, and disconnected retrieval expansion raise an internal contract
error instead of silently reaching the wrong consumer. Legacy low-level producers
without `response-plan-v1` remain supported; public classified requests use the
enforced contract.

Global keyword matching could treat a quoted arithmetic expression, a subject
named “list archive,” or the definition “What is deep search?” as an agent command.
Control matching now masks quoted/fenced text and requires recognized instruction
positions for the relevant summary/list/explanation/source controls. Explicit
negated controls do not activate those agents. This is bounded grammar, not a
claim to understand every negated or indirect utterance.

The draft boolean was not an actual gate in the low-level reply helper. Explicit
`draft=False` now prevents drafting; absence of the flag preserves standalone
reply-helper compatibility. The public pipeline computes the flag and order.

## Inspect actual execution

Graph-backed results expose `routing` with schema `flag-routing-contract-v1`:

- `requested_flags`: agent and presentation flags observed at graph entry.
- `executed_nodes`: node functions actually entered after optional-node checks.
- `observed`: whether graph execution was observed, not whether an answer is true.
- `post_stages`: actual calls to final assessment and selected output rendering.

Channel signals are in `prompt_intent`, since retrieval computes them later than
the entry switches. Early scope/guard/referral responses can have no graph trace.
Batch results retain child traces; the parent can record only its own rendering
stage. A substituted/mock graph has no observed real node sequence. A trace is
diagnostic execution evidence, never source proof or a promise that every requested
agent succeeded. Exceptions/partial results keep their existing failure semantics.

No extra body text is added for this diagnostic record. It contains routing
metadata, not retrieved private source text.

## Configuration and non-prompt controls

`prompt_backend`, reference backend, resonance tag configuration and trained-head
availability are application setup, not privileges a prompt can enable. `discover`,
realization/account options and structured payment/authority/objective/causal
inputs require their existing explicit API arguments. A format flag cannot invent
those objects or authorize a payment. Compatibility `grade`/per-turn `child_safety`
arguments remain inactive in the current pipeline; this review does not introduce
a safety agent or misrepresent them as enforced prompt flags. PrismGuard's actual
raw/resolved prompt guards remain separate and active.

## Verification and maintenance

`tests/test_flag_contract.py` checks all 256 combinations of the selected main
switches, stable ordering/no repetition, holds at each optional transition,
unrequested-node rejection, missing graph consumers, tampered presentation flags,
false triggers and the explicit draft gate. The live response-depth test verifies
actual node execution and that long retrieval is distinct from deep search.

Full live result: **709 passed, 2 skipped, 3 expected failures** in 87.04 seconds.
The skips need unavailable trained extractor checkpoints; the expected failures
remain the existing resonance sense-grouping cases. Six existing NumPy overflow
warnings remain. Local evidence: `build/flag-contract-suite.log` and
`build/flag-contract-validation/`. This is regression validation, not v3 benchmark
accuracy; the independent benchmark remains unexecuted.

When adding a flag, register its origin and consumers, wire the actual consumer,
update the generated mapping files, and add positive/negative routing tests. A new
consumer must exist in the compiled graph or be explicitly classified as an
external stage. Changes to routing precedence or holds need the exhaustive
combination checks and live regressions, not just an edited documentation row.
