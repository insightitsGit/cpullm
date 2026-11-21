# Review of incoming Frontier and Deepen commits

Date: 2026-11-21. Reviewed range: `65ce600..ec71024` (23 commits).
Remote `main` and `feature/frontier-node` both point to `ec71024` at review time.
Local main was fast-forwarded; the non-overlapping Reversal Research drafts and
`docs/current-design.md` edits were preserved. This review changes no runtime code.

Follow-up: all six findings have been addressed in the working tree. See the
[correctness specification and verification](../../frontier-deepen-correctness-spec.md).
The findings and reproduction output below remain the historical baseline review.

## Findings

### P1 — Deepen text input loses directional meaning

Location: `src/cpu_llm/deepen.py:72–75`, consumed at `142–155`.

`parse_hypothesis` recognizes increase/reduce/etc. in text but returns an empty
expected-relation list. Every matched causal edge then counts as support, even
when its direction makes the proposed end-to-end effect go the opposite way.

Reproduction: sources say memory bandwidth **reduces** inference throughput and
throughput **increases** serving revenue. Deepen is asked whether memory bandwidth
may **increase** revenue through throughput. It returns two supported links and
`all_links_supported`, with both expected relations null.

Preserve the requested relation and evaluate its consistency with the composed
path. Do not assume every internal link must have the same sign: two negative
links can yield a positive composition. Until the mapping can be established,
report unspecified direction rather than claim support for the directional claim.
The existing test that expects text-form contrary evidence to count as support
currently encodes this defect and needs correction.

### P2 — Negation drops predicate identity and evidence provenance

Location: `src/cpu_llm/frontier.py:650–653`; `deepen.py:156–158`.

`graph.negatives` retains only subject/object keys, discarding the relation and
source proof. Negating any relation between the terms then blocks other relations
in Frontier and supplies an uncited counter-item to Deepen.

Reproduction: bandwidth increases throughput; a second source says bandwidth
does not reduce throughput. Deepen labels the increase link contested. The
negative counter-item contains no document, quote or hash. These claims are not
logical opposites.

Retain typed negated relations, contexts and exact source proofs. Match negation
to the applicable proposition; never treat all predicates between a pair as one.
Use the same typed contradiction check in Frontier and Deepen.

### P2 — Three-edge Frontier paths lose their second intermediate in Deepen

Location: `src/cpu_llm/deepen.py:62–65` and `_links`.

Frontier supports `max_path_edges=3` and emits two `via` terms. Deepen takes only
`via[0]` and constructs two links. It examines a shortcut instead of the original
three-link path, affecting standalone Deepen and Frontier's leading-entry checks.

Reproduction: bandwidth -> throughput -> revenue -> funding. Frontier produces
the complete path, but Deepen checks bandwidth -> throughput and throughput ->
funding, reporting the latter missing even though the actual three edges exist.

Represent ordered path nodes/relations explicitly and check every adjacent pair.
Test generated dicts, text round-trips, numbered follow-ups and leading checks.

### P2 — Leading-entry deadline expiry is not propagated

Location: `src/cpu_llm/frontier.py:1355–1363`; `deepen.py:224–234`.

Leading checks build a whole-graph encoder lookup and sentence index before the
parent budget check. Each `run_deepen` creates a fresh budget and does not charge
its link/sentence scans to the parent. Parent deadline expiry is caught and
silently breaks the leading loop; its reason never reaches the returned trace.

Using the supplied fake-clock interface, expire the deadline when the leading
phase begins. The result reports 100 seconds used against a 60-second limit,
`deepened=0`, `incomplete=false` and `stop_reason=null`.

Share/charge one request budget through preparation and link scans. Record a
separate leading-check completeness/reason if candidate enumeration completed
but verification did not. External encoding cannot be forcibly interrupted by a
cooperative budget, so document that boundary and check before and after it.

### P2 — Invalid structured Deepen input escapes validation

Location: `src/cpu_llm/deepen.py:59–64` and `_edge_kinds`.

The API accepts an arbitrary hypothesis dict, but parsing assumes `via[0]` is a
string and citation entries are dicts. A request with `pattern=chain`, two string
anchors and `via=[1]` raises an uncaught `AttributeError` instead of the normal
validation/clarification contract.

Validate a typed bounded hypothesis before use: pattern-specific anchor/path
lengths, string elements and citation shapes. Convert invalid input to the
documented API validation error or clarification; add malformed JSON-shape tests.

### P2 — Numbered follow-up clarification bypasses the guard

Location: `src/cpu_llm/pipeline.py:687–692`.

The session recall and missing-session clarification return before
`execute_deepen` checks the guard or strict mode. A guard that would deny the
request is never called when `Deepen idea 1` has no saved Frontier response.

Reproduction returns `needs_clarification` with guard call count zero. This is a
policy-order defect; it is not evidence of a cross-tenant leak (session keys
already include caller, scope and as-of).

Apply guard/strict precedence before session lookup or any early clarification
return. Test missing sessions, out-of-range numbers, denied requests and strict
operator floors.

## Verification and limits

- Focused run: **225 passed, 1 skipped** across Frontier, Deepen, natural routing,
  inference, flag contracts, invention and Nammade tests.
- Reproductions: [script](reproduce.py) and [captured output](reproduction.txt).
  All six findings reproduced using synthetic source rows and the regex parser;
  no hosted model, database or scientific assumptions were required.
- The full repository suite and large live evaluation datasets were not rerun.
- Evaluation additions are useful examples of literature-derived proposals;
  passing their existing tests does not resolve these counterexamples or validate
  the hypotheses experimentally.

The new methods preserve unverified-hypothesis labeling and reuse the authorized
snapshot, which are useful properties. The findings above concern whether their
support/counter-evidence classifications and execution contracts are accurate.
