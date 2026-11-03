# Document generation findings and implementation requirements

Date: November 3, 2026. Applies to the source checkout after published 1.10.0.
Product: CPU LLM, Evidence-Based AI Engine.

## Findings and required behavior

1. **Presentation vocabulary is not knowledge.** A request for a friendly tone
   must not search for “friendly” in Helios documents. Parse explicit tone,
   genre, depth and layout controls separately from the topic. API tone wins
   over prompt tone; strict evidence wins over generation. Do not infer a user's
   emotional state, relationship or intention from an ambiguous tone cue.
2. **More retrieval alone does not produce a fuller answer.** The original
   overview retrieved twelve relevant technical records but spoke only two
   sentences because most records did not fit its proposition grammar. Preserve
   unrecognized technical records as attributed quotations rather than dropping
   them or pretending that they passed a semantic parser.
3. **Genre selection and depth must agree.** Detailed reports/articles/design
   documents use one plan for sections, coverage, budget and rendering. A design
   document is not just a numbered list. Missing Interfaces/Costs or other
   sections remain explicit gaps; the engine must not invent design decisions.
4. **Generation is permitted when meaning can be checked.** The document tone
   node can construct new sentences from complete source predicates. It need
   not retrieve the finished sentence. Same-subject conjunction and limited
   contractions must inverse-parse to all original predicates. Numbers, negatives,
   qualifiers and source hashes must survive. Ambiguous/conditional/unsupported
   records remain literal; no unsupported causal or comparative connective is added.
5. **New wording needs its own evidence contract.** Keep original quotes and
   proofs, identify generated prose as a derivation, and preserve the canonical
   quotation view. The document's `reply.text` can publish verified prose when
   requested; the older single-fact path continues publishing a companion.
   `audit_passed` remains false. Provenance does not prove real-world source truth.
6. **Tone and relationship limits remain enforceable.** The existing lexicon
   ranking uses semantic license, intensity, tone affinity and genericness.
   A winning score is not factual confidence. Risk exclusions precede ranking;
   unsupported expressive preferences report `neutral_fallback`. Generated “It”
   requires an explicit nonhuman source identity and an established same-section
   antecedent. Unknown or human identities do not acquire that pronoun.
7. **Output length is evidence-bounded.** String tone profiles use the document
   budget; explicit StyleOptions limits are honored. Never omit claims to fit a
   tone budget. Word/sentence requests guide atomic quote budgets rather than
   guaranteeing exact counts. Display overflow, partial coverage and continuation.
8. **Formatting must not change evidence.** Markdown/HTML reports, tables,
   bullets and numbering use the same document representation, with generated
   entries distinguished from literal source excerpts. Escape source markup.
9. **Access constraints precede content selection.** Caller scope, raw-message
   guard and historical validity apply before document scanning or generation.
   Continuation reuses the declared time/page budget and rechecks current access.
   Strict requests keep quotation-only output even when tone is requested.

## Implemented contracts and owners

- `stylistic/profiles.py`: explicit tone extraction; quoted/negated directives
  remain data. `pipeline.py`: API precedence, strict bypass and routing.
- `document_workflow.py`: genre/topic plan, bounded authorized snapshot,
  deterministic section coverage, atomic pagination and shared rendering.
- `stylistic/lexicon.py`: twelve reviewed entries: ten base fact constructions
  plus friendly/formal technical-document predicate constructions.
- `stylistic/document.py`: immutable source claims, the real
  `stylistic -> style_verify` output graph, inverse verification and literal fallback.
- `flag_contract.py` and `prompt-flag-map.json`: registered control consumers.
- `document-workflow-spec.md` and `stylistic-generation-spec.md`: detailed behavior.
- `document-generation-findings.json`: machine-readable requirements, executable
  prompt examples and declared remaining boundaries.

## Acceptance and evidence

The original probe and before/after reports are in
`reviews/2026-11-03-document-workflows/`. The prompt-only friendly article/report
run is in `examples/2026-11-03-prompt-tone/`: its KB contains no “friendly” wording,
and its twelve source claims were preserved in verified generated prose.

The saved full run passed 890 tests, skipped 56 optional tests and retained three
existing expected failures; six existing NumPy overflow warnings remained.
The focused/live run passed 101 checks; a final case-insensitive topic refinement
passed 18 document-tone regressions. These are distinct engineering checks on
their recorded working-tree states, not additive accuracy scores or a clean
release benchmark. The specifications do not retroactively change historical
benchmark reports or the published 1.10.0 wheel/whitepaper.

The JSON prompt examples are regression-tested against the actual planning and
tone-extraction functions. New findings should add a failing reproducer and a
declared contract before widening a grammar or producer. Do not put broad new
capability claims into a manual unless code and tests implement them.

## Remaining boundaries

Lexical topic matching is not general alias resolution, unrestricted relational
joins or a universal object-category classifier. The independent typed question
“What database does Helios use?” still has a matcher gap even though its stored
PostgreSQL statement is available in documents. Arbitrary prose contradictions,
novel architectures, general creative writing and exact-length guarantees are
not solved by the tone node. These require separate designs and tests.

This is deterministic interpretation/construction improvement, not automatic
learning from user chats. New KB records supply facts; broader language support
requires reviewed rules/constructions and regression coverage, not invented facts.
