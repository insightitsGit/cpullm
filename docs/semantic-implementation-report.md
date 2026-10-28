# Semantic answering implementation, 2026-10-28

This change connects existing components through the shared request and decision
records in `semantic.py`. It adds no model, external judge or additional database.
Six-channel signals still select candidates; source proof licenses an answer.

## Implemented

- Assessment and final judgment use the same assessment service for supported
  factual slots. An audited sentence about the correct subject cannot replace a
  bound answer about a different relation. Final delivery rejects that replacement.
- Definition commands and identity copulas share the definition contract. A
  bounded proper-name equality supports scientific names; action sentences,
  adjectives and an alias of an embedded object do not define the subject.
- Shape and material have separate attribute slots. Bare values use declared
  vocabulary; ambiguous color/material words require an explicit material marker.
- Possession question and extraction forms share declared have/contain/include/
  possess forms. Membership joins keep both premises. Causal normalization allows
  bounded verb inflection while retaining the subject and effect arguments.
- Presentation normalization handles supported overview, brief, detailed and
  sentence-count prefixes without creating extra tasks. Creative classification
  requires an instruction rather than a creative word inside a factual subject.
- Unchanged replies publish accepted proof too. Summary citations use the
  producer's selected source IDs. A held answer clears its decision proof and
  outcome, including a final Shine hold.
- Scorer v2.2 matches whole lexical entities rather than substrings. Newly
  generated gold corrects explicit ranking continuations and uniquely resolved
  last-child references. Historical benchmark outputs remain unchanged.

New regressions are in `tests/test_semantic_integration.py`. Existing live join,
scope/history, request planning, choice, budget and proof tests remain required.
The original query encoding test now allows bounded distinct repair encodings,
while still requiring reuse of the original query tensor.

## Operational limits and remaining architecture

This is a migration through adapters to the existing parsers, not a general
natural-language compiler. Unsupported question forms remain bounded. Multiple
roles versus genuinely different senses still use the existing conservative
clarification rules. Full typed measurement/statistical IR, a complete relation
registry, and a single per-task trace covering every specialist are future work.
Specialist producer contracts remain separate; attaching their selected sources
does not independently prove every summary sentence. Yes/no forms outside the
declared contracts also need further coverage.

Reingest affected documents to populate newly supported possession graph edges.
Do not assume changing the extractor updates existing stored facts. Keep resonance
opt-in and preserve source authorization and valid-time filtering.

The full live validation records its base revision and working-tree diff under
`build/semantic-implementation-validation/`; console output is saved to
`build/semantic-live-suite.log`. This validates a recorded working tree, not a
new committed revision. A new frozen benchmark is still needed to measure quality
on unseen data; passing regression tests is not a headline accuracy score.

Final live result: **635 passed, 2 skipped, 3 expected failures**, in 78.55 seconds.
The skipped tests require an unavailable trained extractor checkpoint. The three
expected failures are the existing resonance sense-grouping cases. Six existing
NumPy overflow warnings remain. PostgreSQL used a separate disposable database
and was stopped after validation. `git diff --check` passed.
