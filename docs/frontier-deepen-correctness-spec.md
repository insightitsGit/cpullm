# Frontier and Deepen correctness fixes

Date: 2026-11-21. Reviewed baseline: `ec71024`.
Companion: [six-finding review and reproductions](reviews/2026-11-21-latest-commits-review/report.md).

## Design invariants

Frontier keeps its existing streamed candidate generator, ranking, hub/anchor
spread, default budgets, 50-result ceiling and optional three-edge paths.
Deepen retains source predictions, setups, confounders and test-plan generation.
One authorized snapshot is reused; there are no KB writes, automatic truth
promotion or hosted-model dependencies. All results remain unverified hypotheses.
Strict policy, scope and guard precedence remain enforced.

## Implementation tracker

- [x] Preserve text direction and evaluate the whole path with Frontier's existing
  composition rules. Opposite end-to-end effects are contested; unknown direction
  stays unresolved. Two negative physical links can still compose positively.
  Logical support/undermining uses the existing non-arithmetic composition rules.
- [x] Preserve typed negation and exact proof spans. Subject/object agreement
  alone cannot negate a different predicate. Relevant counters remain cited;
  other negations are exposed separately without counting as contrary evidence.
- [x] Introduce validated `HypothesisSpec` execution inputs. Keep all ordered
  intermediaries and match citation relations by endpoints, not citation order.
  Generated objects, text, leading checks and numbered follow-ups support all
  three path links. Multi-mediator test plans retain the complete mediator list.
- [x] Share the parent budget through whole-graph similarity preparation, sentence
  indexing, link checks and clue scans. Preserve candidate results if optional
  checking stops. Record requested/checked counts and per-phase completeness.
  Partial checks never advertise a complete judgment.
- [x] Reject malformed structured hypotheses with a clarification before source
  access. Validate every used pattern, term, relation, path and citation shape.
- [x] Check guard and strict policy before numbered session recall or any early
  follow-up clarification. Session isolation keys are unchanged.

## Receipt and compatibility contract

New additive fields include `path_nodes`, `expected_relation`, `direction_check`,
per-link `observed_relations`/`negations`, and `test_plan.mediators`. Public
`parse_hypothesis` retains its legacy tuple view; execution and multi-mediator
consumers use `read_hypothesis` and its ordered `links()`.

Frontier adds `candidate_search_complete` and `leading_check` (requested, checked,
complete, stop_reason). `deepened` counts completed checks. A partially checked
entry explicitly marks its own check incomplete. Overall `incomplete` also
reflects unfinished requested checks, while the candidate-search field allows
clients to distinguish that from unfinished enumeration.

Time bounds remain cooperative. External parser/encoder calls cannot be forcibly
interrupted; check their boundaries and report expiry rather than claim a hard
wall-clock guarantee. These changes do not add a general causal proof system or
infer that different-regime observations necessarily contradict each other.

## Verification

Regressions cover opposite-direction claims, two-negative compositions, typed
negation/citation integrity, three-edge round-trips and session follow-ups,
unordered citations, malformed JSON-compatible shapes, guard/strict precedence,
parent-deadline sharing, encoder overrun and preserved hypothesis status.

Controlled positive-case comparison against `ec71024` found identical candidate
counts, survivors, returned IDs/text, ordering and scores:

- Capacity chain: 5 generated, 5 survivors, 5 returned.
- Three-edge chain: 3 generated, 3 survivors, 3 returned.
- Signed pairs: 4 generated, 4 survivors, 4 returned.

[Recorded candidate-retention comparison](reviews/2026-11-21-latest-commits-review/candidate-retention.json).
These checks use the regex parser, a fixed clock and no optional leading checks
to isolate candidate generation. They demonstrate retention on those fixtures,
not universal quality or performance equivalence. Typed-negation corrections can
restore valid candidates previously suppressed by an unrelated negation.

Final component and live verification results are recorded below when complete.

### Recorded results

- **405 focused tests passed, 1 skipped** across the new semantic regressions and
  Frontier, Deepen, routing, inference, research, ordinary reply, document and strict
  evidence suites. The skip requires a spaCy English model absent in this environment.
- **28 live pipeline/localhost HTTP tests passed**. Six NumPy overflow warnings
  were emitted by existing numerical paths; no test failed.
- **6/6 database-backed Frontier/Deepen smoke cases passed**: full three-edge
  leading checks, numbered follow-up, opposite direction, unrelated negation,
  malformed input and strict-mode follow-up. Full responses and source hashes are
  saved in `build/frontier-deepen-fixed-smoke/results.json`.
- The three controlled candidate-retention comparisons all matched the reviewed
  revision exactly. Candidate generation and ranking were not weakened to make
  the semantic checks pass.
- Compilation and `git diff --check` passed. The complete repository suite and
  the large scientific evaluation corpora were not rerun.

Reproduce the source-level comparison with
`python docs/reviews/2026-11-21-latest-commits-review/compare-candidates.py`.
The companion `live-smoke.py` requires the documented disposable localhost
database and cached encoders; it contains only synthetic source data.
