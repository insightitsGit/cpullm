# Implementation handoff: grounded inference review fixes

Prepared 2026-11-18 against `7c8f6a3` (review range `5bcecb2^..7c8f6a3`, the
two commits "Add grounded deductive inference…" and "Integrate grounded
inference into research and Nammade workflows").
No implementation changes were made in this handoff turn. Inspect current HEAD
and the working tree before starting; other work may have landed subsequently.

> **Superseded in part.** `fcd34f3` fixed findings 1–6. For the remaining work,
> see [handoff-inference-fixes-after-fcd34f3.md](handoff-inference-fixes-after-fcd34f3.md).
> This document is kept as the record of the original review.

## Working-tree state at handoff

Uncommitted edits existed in `classifier.py`, `crossdomin.py`, `inference.py`,
`invention.py`, `nammade/execute.py` and `pipeline.py` (new relations, a
`PreparedInference` cache, `specialist_plan`, `_defer_inference`, structured
`evidence_analysis` modes). Those edits were **not** reviewed. Rebase this work on
them rather than on `7c8f6a3`, and recheck each finding against that code. The
status column below records what the working tree appeared to do at handoff.

| # | Finding | Severity | Status in working tree |
| - | ------- | -------- | ---------------------- |
| 1 | Raw frozenset scope crashes receipt digest | High | Likely fixed for deduction (`PreparedInference` sorts scope); verify `evidence_analysis.analyze(scope=allowed)` |
| 2 | Ordinary yes/no questions are rerouted into inference | High | **Wider**: more question shapes are now rewritten |
| 3 | Unparseable rewritten questions raise from `ask()` | High | Not fixed; a further `ValueError` was added for combined flags |
| 4 | Abbreviation followed by a newline aborts extraction for the snapshot | High | Not fixed |
| 5 | Research reply runs inference twice and duplicates the section | Medium | Fixed via `_defer_inference=True` |
| 6 | Explicit negation reported as `INSUFFICIENT_SUPPORT` | Medium | Not fixed |
| 7 | Repeated full-snapshot extraction and hashing per reply | Medium | Partly fixed (cached facts/closure); per-receipt `input_digest` and `deepcopy` of all rows remain |
| 8 | Graph `inference` node can never run | Low | Not fixed |
| 9 | Greedy entity capture misses compound sentences | Low | Not fixed |

Findings 1, 3 and 4 were reproduced against `7c8f6a3` with direct calls.

## Findings and required fixes

### 1. Raw frozenset scope crashes the receipt digest

`execute_invention` and `execute_nammade` pass `scope=allowed` (the caller's
`frozenset`) into `attach_inference`. At `7c8f6a3` this reaches
`receipt["scope"]`, and `digest(receipt)` calls `json.dumps`, which raises
`TypeError: Object of type frozenset is not JSON serializable`. Any scoped
caller running Research, Invention or Nammade over chainable facts fails.
`execute_inference` already passes `sorted(allowed)`.

Fix: normalize scope in one place, at the inference boundary (the
`PreparedInference` constructor in the working tree). Apply the same
normalization in `evidence_analysis.analyze`, and make sure no receipt stores a
set.

Test: call `attach_inference(..., scope=frozenset({"pub-p"}))` with
`pub-p0001`/`pub-p0002` elephant/donkey/cat rows. Assert that it returns an
`ENTAILED_BY_RULES` receipt and that the response is `json.dumps`-serializable.
Add the same test through `Appliance.ask` with a scoped `CallerContext` for the
Research route.

### 2. Ordinary yes/no questions are rerouted into inference

`classifier.inference_prompt` rewrites every `Does X have Y?` and
`Is X bigger than Y?` into `Infer whether …`. `Appliance.ask` then returns
`execute_inference` before normal retrieval and question answering run. The
narrow regex rule extractor replaces ordinary answering for very common
question shapes. For example, if the KB says "The Kestrel carries a VHF radio.",
then "Does the Kestrel have a radio?" now gets `insufficient_evidence`. In strict
mode the same question returns "Rule inference requires standard evidence mode"
instead of a strict quotation. The working tree also rewrites `require`,
`located in`, `member of`, `subclass of`, `physical part of` and
`physically contain`.

Fix (preferred): make the explicit `Infer whether …` command and the API
`inference` object the only triggers for the standalone route. For natural
questions, either do not rewrite them, or try inference only as an augmentation:
run the normal pipeline, and attach a receipt only when the verdict is
`ENTAILED_BY_RULES` or `CONFLICT`. Never let inference replace the ordinary
answer when it finds nothing. Strict mode must keep its existing behaviour for
these questions.

Tests: with the "carries a VHF radio" KB, `ask("Does the Kestrel have a radio?")`
does not return `answer_status == "insufficient_evidence"` from the inference
route. The strict-mode variant returns a strict-evidence result, not the
inference refusal. The explicit `Infer whether …` command still routes to
inference.

### 3. Unparseable rewritten questions raise from `ask()`

After rewriting, `request_from` raises `ValueError` whenever the body falls
outside `_ENTITY` or contains a `_QUALIFIED` word. `ask()` does not catch it, so
the library raises and HTTP returns 400 for ordinary questions:

- `ask("Does the contract have a $5,000 cap?")` raises "Use 'Infer whether X is bigger than Y'…"
- `ask("Does the policy have some exclusions?")` raises "Inference requires individual entities."

Fix: a natural-question rewrite must return `None` (fall through to the normal
pipeline) when it cannot produce a valid request. Raise only for an explicit
`Infer whether …` command or an explicit API `inference` object, and present the
explicit-command failure as `needs_clarification` rather than an exception. The
same applies to the new working-tree `ValueError` for combined specialist flags:
decide whether it should be a structured refusal rather than a raise.

Tests: both prompts above return a normal response without raising.
`ask("Infer whether the contract has a $5,000 cap.")` returns a clarification
response.

### 4. An abbreviation followed by a newline aborts extraction for the snapshot

`_extracted` raises `ValueError("Source sentence is missing from its chunk.")`
when `chunk.find(sentence, cursor)` fails. `answerability._sentences` splits on
`\s+` and re-joins abbreviation fragments with a single space, so a chunk such as
`"Dr.\nSmith is a surgeon."` produces a sentence that is not a substring of the
chunk. `attach_inference` now runs on every Nammade, Invention, Research (and,
in the working tree, CrossDomain) reply, so one such chunk anywhere in a tenant
breaks all of those routes.

Fix: do not use `_sentences` output as offsets. Either use a splitter that
returns `(start, end)` spans over the original text, or skip a sentence that
cannot be located instead of raising. Never fail the whole snapshot for one
chunk. Proof spans must stay exact substrings, because `verify_proof` binds them.

Test: deduction over `["Dr.\nSmith is a surgeon.", elephant/donkey/cat rows]`
still entails `elephant bigger_than cat`. A Nammade scan over a KB containing
that chunk succeeds.

### 5. Research reply runs inference twice

At `7c8f6a3`, `execute_nammade` (inside the `execute_invention` thread pool)
attaches inference to its reply. That reply text is embedded under
`### Nammade comparison`, and `execute_invention` attaches inference again, so
the "Rule inference" block appears twice. The working-tree `_defer_inference`
flag addresses this. Keep it, and add a test asserting the block appears exactly
once for `Propose a testable hypothesis about elephant`.

### 6. Explicit negation is reported as missing evidence

`deduce` collects a negative source fact matching the target as a goal. The
verdict then ignores it unless a positive counterpart also exists. With only
"The Kestrel does not have a radio.", `Infer whether the Kestrel has a radio`
returns `INSUFFICIENT_SUPPORT`, and the reply says the records "do not
establish" the relationship while citing the sentence that refutes it.

Fix: add a verdict such as `REFUTED_BY_SOURCE` (status `refuted` or similar)
when the negated target is a source fact and no positive derivation exists.
Keep `CONFLICT` when both exist. Update `execute_inference` text, the OpenAPI
enum and `docs/inference-node-design.md`.

Test: the case above yields the new verdict, cites the source, and passes
`verify_receipt`.

### 7. Repeated work over the full snapshot

At `7c8f6a3`, each research reply ran `_extracted` plus up to 8 `deduce` calls,
each re-extracting and re-hashing every row: about 9 full passes, doubled by
finding 5. The working tree caches facts and closures in `PreparedInference`.
Two costs remain: `_deduce_prepared` recomputes `input_digest` (sha256 of every
chunk) per receipt, and the constructor `deepcopy`s up to 10k rows / 8 MB.

Fix: compute `input_digest` once in `PreparedInference.__init__`, and hash each
chunk once (reuse that hash for `chunk_sha256` in `_extracted`). Copy only the
fields used (`document_id`, `chunk_text`, `source_version`) instead of
deep-copying rows. A shallow tuple of immutable strings is enough.

### 8. The graph `inference` node can never run

`graph_inference` acts only when `state["inference_request"]` is set, and
nothing sets that key: `ask()` short-circuits to `execute_inference` first. The
node is wired between `spans` and `think` on every query, and `flag_contract`
advertises a `core_graph` stage that never fires.

Fix: either remove the node, edges and `core_graph` binding, or populate
`inference_request` in graph state and drop the short-circuit. Pick one path so
that two implementations are not maintained. Update `docs/prompt-flag-map.*`
accordingly.

### 9. Greedy entity capture misses compound sentences

The `_ENTITY` class allows spaces and patterns use `fullmatch`, so the object
swallows the rest of the clause. "The Kestrel has a radio and a crew of five."
extracts `has(kestrel, "radio and a crew of five")`. "The elephant is bigger
than the donkey in Kenya." yields object `donkey in kenya` and breaks chains.

Fix (conservative): reject, rather than extract, objects containing
coordinators or trailing prepositional phrases (`and`, `or`, `,`, `in`, `at`,
`during`, …). A wrong predicate is worse than a missing one in this design.
Splitting coordinated objects is optional and needs its own tests.

## Out of scope / pre-existing

- `tests/test_cycle_composition.py::test_document_consumes_cycles_after_style_from_one_snapshot`
  and `::test_document_api_and_prompt_override_and_scope` fail on the code
  **before** these commits as well (`strict_source_rows` called twice). Not caused
  by this review range.
- `tests/test_inference.py` passes at `7c8f6a3`. No CI runs the test suite;
  only `.github/workflows/pypi-release.yml` exists.

## Acceptance

- Every test named above exists and passes. `tests/test_inference.py`,
  `tests/test_nammade.py` and `tests/test_pipeline.py` still pass.
- A scoped caller can run Research, Invention, Nammade and CrossDomain over
  chainable facts, and the response is JSON-serializable.
- No natural question that previously reached the normal pipeline raises
  or loses its ordinary answer because of inference.
- Release notes and `docs/inference-node-design.md` describe the final trigger
  rules and any new verdict.
