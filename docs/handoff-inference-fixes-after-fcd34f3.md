# Implementation handoff: remaining grounded inference fixes after `fcd34f3`

Prepared 2026-11-18 against `fcd34f3` ("Expand grounded inference and clarify
source-only APIs and evidence contracts"). This follows
[handoff-inference-review-fixes.md](handoff-inference-review-fixes.md), which
records the original nine findings from the review of `5bcecb2` and `7c8f6a3`.
No implementation changes were made in this handoff turn. Inspect current HEAD
before starting; other work may have landed subsequently.

## Status after `fcd34f3`

`fcd34f3` resolves most of the original findings. Each status below was checked
by re-running the original reproductions against an extracted copy of
`fcd34f3`. `tests/test_inference.py`, `test_inference_expansion.py`,
`test_invention.py` and `test_nammade.py` all pass at that commit.

| # | Finding | Status at `fcd34f3` | Evidence |
| - | ------- | ------------------- | -------- |
| 1 | Raw frozenset scope crashed the receipt digest | **Fixed**; regression test missing | `PreparedInference` and `analyze` sort scope; repro returns `ENTAILED_BY_RULES` and serializes |
| 2 | Ordinary yes/no questions were rerouted into inference | **Fixed** | Natural questions return the inference result only for derived, conflicting, contradicted or blocked outcomes, otherwise fall through; strict mode and specialist flags skip it (`test_inference_expansion.py:223`) |
| 3 | Unparseable rewritten questions raised from `ask()` | **Fixed** | `request_from` returns `None` for natural questions; explicit commands give `needs_clarification` (`test_inference_expansion.py:213-218`) |
| 4 | Abbreviation plus newline aborted snapshot extraction | **Fixed** | `_extracted` skips sentences it cannot anchor (`test_inference_expansion.py:243`) |
| 5 | Research reply ran inference twice | **Fixed** | `_defer_inference=True`; `test_nammade.py:34` asserts one block |
| 6 | Explicit negation reported as missing evidence | **Fixed** | New `CONTRADICTED_BY_RULES` / `contradicted` (`test_inference_expansion.py:251`) |
| 7 | Repeated full-snapshot work | **Partly fixed; new cost added** | See below |
| 8 | Graph `inference` node can never run | **Open** | `inference_request` is still never placed in graph state |
| 9 | Greedy entity capture misses compound sentences | **Open** | "The Kestrel has a radio and a crew of five." still yields `INSUFFICIENT_SUPPORT` for `has radio` |

The original pre-existing failures are unchanged and out of scope:
`tests/test_cycle_composition.py::test_document_consumes_cycles_after_style_from_one_snapshot`
and `::test_document_api_and_prompt_override_and_scope` also fail before
`5bcecb2`. The full suite still has no CI; only
`.github/workflows/pypi-release.yml` exists.

## Remaining work

### A. Every matching natural question now fetches the whole snapshot first (finding 7, revised)

The fix for finding 2 tries inference before the normal pipeline for every
question shaped like `Does X have Y?`, `Is X bigger than Y?`, `Is X located
in Y?`, `Does X require Y?` and so on. Each attempt calls `execute_inference`.
That loads the authorized snapshot (`strict_source_rows`, up to 10k rows or 8 MB),
`deepcopy`s the rows in `PreparedInference.__init__`, hashes every chunk and
regex-scans every sentence. Usually it then falls through to ordinary
retrieval. This is added latency on very common question shapes, paid even when
no rule could apply.

The per-receipt `input_digest` is fixed (computed once), but these costs remain:

- `PreparedInference` deep-copies every row and the snapshot. Copy only
  `document_id`, `chunk_text` and `source_version` (immutable strings), or keep
  the rows read-only.
- `_extracted` computes `sha256(chunk)` once per matched sentence. Hash each chunk once.
- For implicit (natural-question) attempts, skip the snapshot unless the
  request's subject and object both occur in the KB. Cheaper still, run
  extraction only on retrieved candidate rows, and load the full snapshot only
  for an explicit `Infer whether …` command or API request.

Test: an implicit question that falls through must not call
`strict_source_rows` more than once, or must not call it at all if you adopt
the retrieval-gated approach. Add a timing or call-count assertion.

### B. The graph `inference` node can never run (finding 8)

`graph_inference` acts only when `state["inference_request"]` is set, and no
code sets it: `ask()` handles inference before the graph. The node is still
wired between `spans` and `think` on every query. `flag_contract` advertises it
as `core_graph`, and `fcd34f3` widened that description to cover structured
analysis that the node does not handle.

Fix: remove the node, its edges and the `core_graph` stage, or set the request
in graph state and drop the pre-graph short-circuit. Pick one path, and update
`docs/prompt-flag-map.*` and `docs/inference-node-design.md` to match.

### C. Greedy entity capture (finding 9)

`_ENTITY` allows spaces and the patterns use `fullmatch`, so objects swallow
trailing clauses. "…has a radio and a crew of five." yields object
`radio and a crew of five`. "…bigger than the donkey in Kenya." yields
`donkey in kenya` and breaks chains. The new relations in `fcd34f3`
(`requires`, `located_in`, `physically_contains`, …) inherit this.

Fix (conservative): refuse, rather than extract, subjects or objects containing
coordinators, commas or trailing prepositional phrases (`and`, `or`, `,`,
` in `, ` at `, ` during `, …). A wrong predicate is worse than a missing one in
this design. Splitting coordinated objects is optional and needs its own tests.
Apply the same rule to request parsing so request and fact entities stay
symmetric.

### D. Missing regression test for finding 1

The scope fix works, but no test covers a scoped caller hitting a research
route with chainable facts. That is the exact case that crashed. Add one:
`CallerContext(allowed_sources=frozenset({"pub-p"}))` over `pub-p0001`/`pub-p0002`
elephant/donkey/cat rows, through `Appliance.ask("Research elephant")` (and
Nammade/CrossDomain if practical). Assert an `ENTAILED_BY_RULES` receipt and
that `json.dumps(response)` succeeds.

### E. Minor (optional)

- With an explicit inference command, the specialist-flag conflict raises
  `ValueError` (HTTP 400) rather than returning a structured refusal. Fine if
  intended; document it in `docs/openapi.json`.
- The pre-graph `needs_clarification` and `blocked` responses built in
  `Appliance.ask` omit `message`, `tenant_id`, `answer` and `routing`, which
  `execute_inference.finish` includes. Consider routing them through one helper
  so response shapes match.

## Acceptance

- Items A–D are implemented with the tests named above.
  `tests/test_inference.py`, `test_inference_expansion.py`, `test_invention.py`,
  `test_nammade.py` and `test_pipeline.py` still pass.
- A natural question that falls through to ordinary answering does not pay
  for a full-snapshot inference pass, or pays for at most one fetch with no deep copy.
- `docs/inference-node-design.md`, `docs/prompt-flag-map.*` and the README
  describe where inference actually runs (pre-graph service vs graph node).
