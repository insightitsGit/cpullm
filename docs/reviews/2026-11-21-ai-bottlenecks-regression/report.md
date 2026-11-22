# AI-bottlenecks regression after Deepen strengthening

Date: 2026-11-21. Outcome: **all recorded regression invariants passed**.
This is a behavior-preservation and research-review integration run, not a
scientific accuracy score, novelty evaluation or enterprise certification.

## Fixed inputs and execution

- Same 64-source AI-bottleneck corpus and recorded PostgreSQL snapshot as the
  earlier `a4cbb03` baseline: 1,054 chunks, including 20 restored holdout passages.
- Verified the entire snapshot's document IDs and chunk text against the saved
  corpus before running. No re-ingestion or hosted-model calls.
- Three original broad prompts and the original focused prompt. The focused
  scope retained its original 25 sources / 360 chunks.
- Real CPU encoder and workspace spaCy `en_core_web_sm` 3.8.0 dependency model.
- Each Frontier request used a 120-second budget and five leading Deepen checks.
- Explicitly deepened the first three alternatives per case, with local novelty
  overlap review enabled. Two further follow-up turns examined the first focused
  proposal in its own session.
- The final source working tree is unreleased after 1.15.0. Exact SHA-256 hashes
  of all five changed runtime files are in the raw results and matched at the
  end of execution. The published 1.15.0 package was not changed.

## Frontier results

1. **AI energy bottlenecks:** 50 returned, same as baseline. 15.847 seconds.
2. **Training data supply:** 50 returned, same as baseline. 4.200 seconds.
3. **Memory bandwidth bottlenecks:** 7 returned, same as baseline. 3.822 seconds.
4. **Inference energy and output quality**, focused scope: 7 returned, same as
   baseline. 1.405 seconds.

All 114 returned entries across the four requests matched their respective
baseline candidate IDs, texts, ordering and scores exactly. These are entries
across requests, not a claim of 114 globally distinct discoveries. All searches
and leading checks completed without budget exhaustion. Timing is descriptive;
cache state and a single run do not establish a performance improvement.

## Explicit Deepen results

All 12 standalone checks completed. Their component-link verdicts remained
`all_links_supported`, as expected for proposals built from those same premises.
The new composition assessments distinguished their unresolved assumptions:

- 9 `requires_review`.
- 3 `conditional` (not scientifically validated).
- All 12 plans `needs_input`, with 8–10 missing requirements each: intervention
  definitions/feasibility, measurement procedures/scales, protocol and, where
  applicable, composition concerns. No units or measurements were invented.
- All 12 local novelty checks found no all-term sentence overlap in the snapshot.
  This narrow check does not certify novelty or rule out cross-passage prior work.
  No external literature review was requested or executed.
- Every proposal stayed unverified with promotion blocked, no KB-write request,
  and no experiment execution.

### H2O/vLLM example

Exact Frontier proposal:

> implementation of H2O and vLLM may jointly drive throughput, and their effects may compound.

Deepen retained the individual source evidence and reported composition
`requires_review`, interaction `untested`, and plan `needs_input`. The factorial
plan distinguishes a joint interaction from the individual performance effects.
This still concerns throughput rather than the full requested energy/quality
trade-off, and the broad combination was previously studied (see the
[baseline literature check](../2026-11-21-ai-bottlenecks-fixed-run/report.md)).

First follow-up, `Go deeper`:

> Next unresolved requirement: Resolve the listed endpoint meanings and source-setting differences.

It showed the exact throughput labels in the source quotes. These warnings can
include compatible specializations, so they request review rather than rejection.

Second follow-up, `Go deeper`:

> Next unresolved requirement: Supply intervention levels for implementation of H2O.

Both follow-ups reported no new source content and no gained empirical support.
They focused on different requirements instead of repeating the initial plan.

### Known invalid bridge

Exact preserved proposal:

> chunked prefill may increase divergence through memory access for prefill jobs (read as access).

The original component evidence was retained, but Deepen explicitly flagged
`access` versus `memory access for prefill jobs` for semantic review. The
institutional-access/hardware-access bridge was not certified valid or silently
removed. Its plan remained `needs_input`.

## Interpretation

The regression demonstrates that the new review layer preserved breadth and
ranking while exposing previously hidden assumptions and unmet experiment
requirements. It does not demonstrate that candidate generation itself became
more scientifically productive: vague variables and topic drift remain in the
list, and local overlap absence is a weak novelty signal. These are research
leads to screen, not established discoveries or ready-to-execute experiments.

## Reproduction and raw outputs

Runner: [run.py](run.py), invoked from the repository root against the existing
isolated database and saved baseline corpus. It refuses to overwrite a completed
run. No runtime code changed during this task.

- Machine-readable results: `build/ai-bottlenecks-regression-20261121/results.json`.
- Exact full conversations: `build/ai-bottlenecks-regression-20261121/responses.md`.
- Per-case receipts: `build/ai-bottlenecks-regression-20261121/case-1.json` through
  `case-4.json`.
- Execution log: `build/ai-bottlenecks-regression-20261121.log`.
