# Document workflow repair and replay

The shared `document-plan-v1` / `evidence-document-v1` implementation is in the source checkout; no published 1.10.0 distribution was replaced. See `docs/document-workflow-spec.md` for the exact contract and boundaries.

## Observed before and after

- Detailed report: five source findings before; twelve atomic source quotations after.
- Detailed overview as report: two factual sentences before; twelve source quotations after.
- Article: five source sentences before; twelve source quotations after.
- Design document: generic five-item document before; twelve source quotations organized into sections after, with missing Interfaces explicitly marked and `partial` status.
- Forced-deep report: two factual sentences before; twelve source quotations after. The new path uses a bounded authorized SQL snapshot, not graph expansion; this is recorded in `document.retrieval`.
- Twelve-sentence bullet request: two bullets before; twelve atomic source records after. Exact sentence/word counts are not guaranteed for multi-sentence source chunks.
- HTML: the same twelve quotes as Markdown, rendered as escaped HTML rather than different selected facts.
- Styled report: quote body preserved; unsupported general-prose tone rewriting is explicitly skipped.
- Strict report: unsupported before; twelve exact source quotations under the separate strict document contract after, with no learned generation or tone execution.
- The independent three-question table remains partial for its typed database question. This document fix does not invent an unrecorded object-category assertion; the database statement itself is now retained in the report. Arbitrary typed factual queries remain outside this document change.

These counts are observations on twelve fictional Helios records plus two distractors, not general accuracy percentages. No unseen-data or competitive model result is claimed. The source statements are quotations, not newly inferred facts.

## Validation

The full regression suite completed successfully during implementation, with optional integration tests skipped, the three existing expected failures and the existing six NumPy warnings. After defensive refinements, 92 focused document/planning/renderer/registry/trigger tests passed. A separate real PostgreSQL run passed three integration tests: the new document scope/time/strict/format/continuation test and both existing tone integration tests.

The initial replay receipt records base Git revision `5766172` with dirty runtime. `after/runner.py`, inputs and full responses preserve that replay. `after/final-runtime-hashes.json` separately records the final refined runtime, which added outline/output-limit/argument safeguards after the replay. The final integration and focused tests cover those refinements; do not describe the replay as a clean committed revision or conflate it with the final hash manifest.

## Remaining declared limits

Topic matching is lexical and requires topic tokens within each selected chunk; semantic aliases, class joins and unrelated inferred facts are not automatically added. Sections are organized by deterministic cues. Prose contradictions are not universally detected; only recognized literal attribute conflicts are flagged. Exact word/sentence output lengths are not asserted. Oversized scans/atomic output fail closed. Continuation preserves page size and time validity while reapplying current permissions; it is not a signed immutable snapshot. Broader tone construction and novel architecture proposals require separate explicit designs.

## Final verification receipt

The refined replay is retained under `final/` with the original ten cases. The final focused/live run passed **98 tests**, with its JUnit receipt alongside the responses. The registry and whole-word section-cue refinements made afterwards passed **39 focused tests**; `final/runtime-hashes.json` captures the resulting files. Those final refinements do not change the fixture quotations; the replay and dirty-tree receipt are not a clean-release benchmark.
