# Review of 8eaabd6 and 1183b77

Reviewed against edf54ee on 19 October 2026, America/Los_Angeles. No production code was changed.

## Findings

### P1: missing measurements break the UNKNOWN verdict path

Location: `src/fact_bridge/__init__.py:642`.

The refactor appends five fields to each opinion: `(verdict, stance, rule, fact, value)`. The final UNKNOWN branch still unpacks four. A matched entity with a different measurement, or incompatible measurement units, now triggers `ValueError: too many values to unpack (expected 4)` instead of returning UNKNOWN.

Executed reproduction:

```python
from fact_bridge import answer

answer(
    "Can I fly business class from Boston to Paris?",
    [
        "Business class is allowed for flights over six hours.",
        "The flight from Boston to Paris weighs three tons.",
    ],
    child_safety=False,
)
```

The public function raises the exception above. Through the live `Appliance.ask`, the graph instead returns a partial result with no `reply`, `__partial__` set, and `__node_error__` identifying the reply service with `invalid_input`. It does not return the intended missing-duration answer. This distinction is recorded in the raw observations.

Suggested fix: unpack the stance as well, or use a named record for opinions. Add missing-metric and incompatible-unit cases that exercise the final UNKNOWN branch. Acceptance: the public function returns UNKNOWN without raising, and the Appliance returns a complete reply explaining which measurement is missing or incompatible.

### P2: entity filtering removes words inside complete names

Location: `src/cpu_llm/pipeline.py:1100-1116`.

`_prompt_entity` passes the extracted entity through `_content_phrase`, which removes stopwords from inside the name. The exact-phrase filter then searches for a different name:

- `Tell me about Bank of America.` becomes `Bank America`.
- `Tell me about Research and Development.` becomes `Research Development`.

In the live fixture, `Bank of America is a bank.` and `Research and Development is a department.` are ingested and available. Both questions return `The retrieved passages do not settle that.` because their actual names cannot match the altered phrases. This regresses valid entity queries while fixing the earlier partial-name leakage.

Suggested fix: preserve the internal tokens of an extracted entity. Separate instruction-prefix/leading-determiner normalization from fallback keyword stopword filtering, and retain the complete name for phrase matching. Acceptance: both named facts reach Model01 and are delivered, while Ada remains supported and the unrelated picnic stays out of the harbor-kestrel reply.

## Confirmed fixes

The exact six live counterexamples from the previous review were rerun:

- Permission no longer establishes an obligation.
- An applicable prohibition answers YES to a forbidden question.
- Nested fish-weight and fish-nesting predicates no longer answer the outer bird's question.
- The picnic sentence is excluded from the harbor-kestrel reply.
- Ada's short name reaches Model01 and produces the scoped reply.

The three direct assessment probes from that review also now return insufficient evidence for the incorrectly bound outer-subject relations. Results are saved in [the prior-case recheck](recheck-1183b77-prior-probes.json).

## Verification

- **124 targeted tests passed; 1 database test deselected.** Fourteen files cover fact-bridge, answerability, Model01, answering, frames, realizer, typos, finance, documents, comparison, math, review, summaries and ranking. [Exact pytest output](pytest-1183b77.txt).
- **27/27 original benchmark cases passed**, with three repetitions through retrieval and the pipeline: **162 measured calls, zero exceptions** on the 17-paragraph controlled corpus. Factual checks 17/17, policy checks 4/4, missing-fact nonanswers 4/4, math 2/2. This benchmark does not include the two new counterexamples above. [Summary](audit-1183b77-small/summary.json), [raw runs](audit-1183b77-small/runs.jsonl), [per-case outputs](audit-1183b77-small/case-results.json).
- Full-pipeline warmed latency: median 37.6 ms, nearest-rank p95 58.9 ms over 81 serialized calls. This developer workstation was not isolated for timing; startup and ingestion are excluded. No larger-corpus benchmark was repeated for this follow-up review.
- [Executable review probes](review-1183b77-probes.py) create fresh namespaces and preserve existing corpus documents. [New counterexample observations](review-1183b77-probes.json) include the public-function stack trace, the Appliance partial result, and name-filter observations. Run the script from the checkout with dependencies, cached encoder and the configured PostgreSQL available. `--extras-only` skips the already completed prior-case recheck.

This is a targeted review of the two commits, not a full repository certification or a representative QA accuracy estimate. Source was frozen for the benchmark. The separate live review probes exercised checkout source and actual local model discovery. The new findings are separate from the previously reported defects that these commits successfully fixed.
