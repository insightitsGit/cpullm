# Benchmark v2 result review

Implementation proposal: [improvement design and handoff](../../benchmark-v2-improvement-design.md).
It specifies request/delivery contracts, routing fixes, extraction improvements,
evaluator corrections and acceptance tests in implementation order.

Reviewed 2026-10-27 Pacific time. Run directories use 2026-10-28 UTC:
`build/benchmark-request-pipeline-v2-fresh-2026-10-28` and the separate v2 replay.
Runtime revision: `391adbb`; evaluator/gold/runner changes are uncommitted.
Original run artifacts and runtime code were not changed during this review.

## Assessment

The fresh run provides useful failure evidence and confirms selected-meaning
continuation improvements. It does not pass readiness gates. The recorded live
suite has 566 passed, 5 failed, 2 skipped, 3 expected failures. This review checked
that log, not a new full-suite run. Four current evaluator tests passed locally.

Counting `scores/rescored-v2.1.jsonl` independently reproduces 456 saved raw rows,
454 established rows, 235 passing rows and two rows flagged false. The report
states 76/272 answer-like passes. These are evaluator-specific results rather
than an independently adjudicated semantic accuracy estimate. A different fresh
corpus and revised scorer make comparison with the old headline misleading.

## Evaluator/report corrections still needed

1. **The two false-assertion flags do not demonstrate an invalid average join.**
   Both are `join-cross-10`: the actual question is `How long does the average
   display loom live?` The answer quotes `The average display loom lives for
   3 years.` It preserves the explicitly asked average and cites the source.
   Gold nevertheless expects insufficient evidence and forbids `3 years`.
   This is not an individual inheriting a class average. Adjudicate the existing
   result and add a separate individual-lifespan question as the negative test.
   Do not change the runtime to refuse all explicit questions about averages.
   No corrected overall false-assertion count is certified by this targeted review.

2. **Alternate valid proof IDs remain excluded.** Dense expiry/reset answers cite
   a `known as` sentence that explicitly states the requested type. These are
   valid alternative definitions, not citation omissions merely because gold
   names the plain type sentence. Add alternative minimal proof sets after
   independent source review. Conversely, resonance expiry/reset raw outputs
   ask for a meaning, rather than delivering the alias definitions claimed for
   both arms in the report. They do not resume the stale location, but are not
   successful definition completions either.

3. **Machine-readable summaries have mixed scorer versions.** `metrics.json`
   still aggregates v2 (eight false flags), while the report uses the v2.1
   rescored JSONL (two). The known replay report also mixes v2 and v2.1 counts
   in different sections. Publish versioned metrics/failure catalogs matching
   each report and identify the authoritative version. Keep older outputs intact.

4. **Semantic and child-level checks are incomplete in the fresh gold.** Only
   39 of 180 standalone cases contain typed bindings; none contain child specs.
   Thus the scorer's new child/binding tests do not establish equivalent coverage
   in the actual evaluation. Only four standalone cases have atomic references.
   Add per-child gold and allowed proof alternatives, rather than pooling all
   claim words and IDs. The adjudication file mostly reproduces scorer verdicts;
   the report correctly admits it is not independent manual review of all failures.

5. **Scale correctness is not on the same scoring version.** Scale files retain
   v2 factual-probe false flags on licensed joins that v2.1 later corrected in
   the main set. Do not interpret them as new runtime failures without re-scoring
   from saved proof/response data or rerunning the affected probes. True session
   process restart remains unmeasured; a storage reopen check is a different test.
   Optional-unit overflow remains unavailable where not independently measured.

## Verified runtime work, in priority order

1. **Unrelated relation accepted as successful.** `separation-arc-25` asks
   `Does the Sable have a shade? What is the Reed?`. q2 returns `The Reed is
   found in Rim.`; both children are marked evidence_quote and the parent says
   complete. Tasks are structurally present, so call this wrong-relation success
   rather than literal task removal. `auth-arc-08` asks the Sable frame's shape
   and receives `The Sable is the best survey pane for color.` The final judge
   must validate the requested relation on every accepted fallback response.

2. **Factual entities containing "fictional" are refused.** The live log records
   five failures in `tests/test_join_pipeline.py`. The creative detector matches
   the word anywhere and delivery refuses ordinary factual questions about
   `the fictional lobster`. Distinguish a creative instruction from an entity
   description; retain deliberate poem/story refusals. Do not weaken join tests.

3. **Extraction/wording coverage misses retrieved facts.** `direct-har-01` finds
   copper evidence but abstains; `direct-arc-01` similarly misses slate. The brief
   color prompt `depth-har-01` returns an unsupported event-frame notice plus a
   type summary. Fix normalization/producer routing separately from retrieval;
   finding a passage does not prove the later parser can use its requested fact.

4. **Proof delivery needs a categorized audit.** The report's 153
   retrieved-but-not-cited flags include true misses, safe abstentions and gold
   proof-alternative errors. Split those categories before treating all 153 as
   evidence dropped by rendering or judgment.

## What improved and what the timing establishes

Both arms complete the recorded numbered and text class-choice scripts on the
selected class. The dense expiry/reset outputs no longer answer the prior place.
These observations support the reviewed fixes without establishing general
coreference or distributed-session correctness.

The 10k timing files report dense warm p95 around 0.233–0.263 seconds and resonance
around 1.311–1.326 seconds. The main scores show little quality separation. These
results support keeping resonance opt-in. Do not infer a causal separator gain:
there is no comparable pre-separator arm on this corpus. No production SLA or
memory guarantee is established.

Next: correct average/alternative-proof adjudication and publish aligned v2.1
metrics, fix wrong-relation success and the factual-fiction trigger, then run
focused live regressions before another expensive full evaluation. Preserve this
run and use a new run ID for later runtime results.
