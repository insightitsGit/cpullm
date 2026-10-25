# Intent and response support backlog

Architecture and verification snapshot: [current design](current-design.md),
updated 2026-10-25. The statuses below separate bounded implementations from
general language capabilities that remain open.

Track these categories until they have been addressed and verified. Recording
a category does not mean its implementation has started. Do not mark one done
without a reproducible example, expected behavior, and regression coverage.

## Current work: 2. Contextual references

The agreed bounded implementation for scenario 1 is complete: dictionary-assisted
expressions, channel routing, scoped secondary retrieval for supported missing
attributes, applicability checks, and source-backed replies. Regression coverage
includes their combined retrieval-to-reply path. Scenario 2 now has optional
coreference adapters and conservative session-local clarification; see
[reference resolution](reference-resolution.md). General paraphrase understanding
and arbitrary reference resolution remain open.

Scenario-1 rationale: does an unsupported question form mean the answer
is absent from the stored vector chunks?

No. Distinguish these conditions for every category:

- Evidence exists in a chunk but retrieval does not find it.
- Evidence is retrieved but relationship extraction misses it.
- Facts exist but alias/reference resolution or a multi-step connection is missing.
- The question's intention is not recognized, or sentence selection/construction fails.
- Evidence genuinely is absent, insufficient, conflicting, or cannot support the requested conclusion.

Vectors are numeric representations of chunks, not an exhaustive inventory of
facts or supported question forms. Changing a question's wording does not
require storing that exact question or answer wording in the corpus.

Scenario-1 regression example:

- Source: "The coastal moth lives in Norway."
- Supported wording: "Where does the coastal moth live?"
- Paraphrase to evaluate: "Where would I encounter the coastal moth?"
- Expected behavior: find and cite the stated geographic information, without
  inferring an exact encounter site or guaranteeing an encounter.
- Status: partial; dictionary-assisted expression support implemented. See
  [design and limits](dictionary-assisted-paraphrases.md). Broad coverage remains open.

## Categories, in order

1. **Broad paraphrases** — recognize equivalent intentions across varied wording.
   Status: partial; bounded dictionary-assisted expressions implemented and tested.
   Broader wording and automatic word-sense resolution remain open.
2. **Contextual references** — resolve "it", "that lobster", and prior-turn entities;
   distinguish edibility, permission, and case-specific safety questions.
   Status: partial implementation. Optional Coreferee/Fastcoref adapters, scoped
   prompt resolution, and clarification/confirmation are connected to `ask`.
   See [usage and limits](reference-resolution.md). Coreferee has real CPU smoke
   coverage; Fastcoref and broad-domain accuracy remain unverified.
3. **Indirect facts** — bind pronouns, aliases, and descriptions within source text
   to the right entity without importing another entity's attributes.
   Status: open.
4. **General comparisons** — identify both subjects, comparison attributes, and
   missing evidence; construct a supported comparison.
   Status: open; comparative intent is detected, but answer construction is limited.
5. **Multi-step reasoning** — follow justified relationships, preserve direction,
   and distinguish discoverable paths from licensed inferences.
   Status: open.
6. **Hypotheticals and predictions** — separate stated facts from assumptions,
   model-based predictions, and unsupported speculation.
   Status: open.
7. **Opinions and recommendations** — obtain criteria and distinguish source
   opinions from facts and recommendations derived from explicit preferences.
   Status: partial; a [bounded ranking clarification loop](clarification-loops.md)
   now asks for criteria and missing evidence. General recommendations remain open.
8. **General sentence construction** — compose several supported facts coherently
   while preserving qualifiers, provenance, uncertainty, and contradictions.
   Status: open; selection and bounded templates already exist.

## Completion record for each category

### Missing-fact investigation: retrieval before declaring absence

Implemented bounded missing-attribute retrieval repair for lifespan, location,
color, and possession/parts, including re-planning from newly retrieved type edges.
It searches the requested entity and verified connected classes, and requires
direct evidence or an explicit universal rule before accepting a joined answer.
See [the design](attribute-directed-retrieval.md). Other missing attributes
and broader quantified reasoning remain open; this does not complete item 5.

Record the agreed scope, representative inputs and corpus, expected outputs,
observed failures, implementation, tests, remaining limits, and commit. A passing
small fixture is not evidence of arbitrary language understanding.
