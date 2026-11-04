# Long response and draft composition corrections

Date: November 4, 2026. Source branch: codex/research-cycle-nodes.
Not part of published cpu-llm 1.11.2. This extends the initial research planner.

## Reproduced failures

An 80-record fixture exposed limits hidden by the earlier six-fact example:
“detailed” selected only 16 chunks, “1,000 words” selected 20, and “60 items”
also selected only 20. Research questions were attached to a quotation renderer
rather than a default bounded prose compositor. Email facts were assigned to
Overview instead of Details, and email output used the report layout. Blank
sections did not distinguish absent evidence from evidence omitted by pagination.

## Length and source selection

Document pages now use source-body word targets: 120 for brief/concise requests,
400 for an unqualified document, 1,000 for detailed/long requests. An explicit
word count overrides this, up to 20,000 effective words. Explicit item/sentence
budgets select up to 500 atomic source records rather than silently stopping at
20. This document-only ceiling does not increase ordinary short-answer budgets.

The existing 10,000-chunk/8-million-character snapshot and 200,000-character
atomic source-text page limits remain. Whole records and qualifications are never
truncated. Word targets are approximate: a record may cross the target, and
verified composition can change the final word count. Content is never repeated
or invented to fill a requested length.

Coverage exposes body words separately from headings, citations and notices;
effective versus requested targets; target success, word/item shortfall, operator
clamping and evidence-exhaustion/page-budget reasons. A clamped target cannot be
reported as fulfillment of the original larger request.

Word-based continuation recomputes deterministic atomic boundaries using the
same source order, outline and as-of snapshot. It retains the word target and,
for email/letter drafts, the recipient. Explicit source-item budgets are not
combined into fewer presentation units by the ordinary compositor.

## Bounded neutral prose

Ordinary document requests activate document_compose and document_inverse_verify.
This is neutral factual composition, not an inferred request for an emotional
tone. The existing narrow predicate parser and independent inverse grammar are
reused. Supported source predicates can be joined without adding a relationship,
cause, qualifier or number. Unrecognized/conditional material remains attributed
literal text. Original source proofs and canonical quotation presentation remain.

Document verification supports up to 500 selected records; an explicit
StyleOptions sentence budget still applies and fails without dropping claims.
Different subjects cannot share a compound predicate batch. Pronouns require an
explicit nonhuman identity for that same subject; another subject's identity
cannot license “It”. Explicit tone requests still run their separately documented
post-stage. Strict documents never use neutral/tone rewriting.

## Coverage and email presentation

Sections distinguish supported, missing and omitted-by-budget states. Research
facet gaps are separately exposed; gaps in explicitly required facets prevent a
false completed judgment. Optional research suggestions stay in metadata; a
missing explanation is not filled with an invented bridge. Candidate question
coverage remains a retrieval diagnostic, not independent factual validation.

Default email/letter drafts render a subject, optional named greeting, sourced
body and conventional closing. No sender identity, promise, deadline, approval
or sending authority is invented. Explicit table/list layouts still use their
requested renderer. HTML escapes source and recipient text. Short drafts with
four small facts no longer paginate merely because the old limit was three
records. Large datasets can still require pagination under a brief word target.

## Verification

`tests/test_long_document_composition.py` adds rich-data word/item tests,
continuation checks, scope/proof retention, shortfall/clamping, email formatting,
research gaps, strict isolation, multi-subject and pronoun regressions.

Full default-suite and actual Appliance examples are recorded in the linked
[implementation record](research-cycle-implementation.md). The rich retention
fixture is intentionally repetitive to test budgets; it is not a benchmark of
editorial quality, broad factual understanding or semantic completeness.
