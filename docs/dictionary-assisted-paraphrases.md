# Dictionary-assisted paraphrase design

This addresses backlog item 1 within a bounded vocabulary. It does not supply
missing facts or solve arbitrary semantics. The packaged `query-lexicon.json`
records sense-labeled synonyms, equivalent question expressions, related terms,
antonyms, and known ambiguities. The first vocabulary is deliberately small
and inspectable; it is not a comprehensive dictionary or a trained sense model.

## Pipeline

1. Preserve the exact user prompt and its VectorPrism encoding.
2. Look up terms and match a complete equivalent-expression pattern. Entity
   text is copied, not replaced with every possible synonym.
3. Leave guarded negation/conditions, unresolved references, compound entities,
   and explicitly ambiguous senses unchanged.
4. Route a recognized canonical expression through the six intent functions.
   Encode at most one canonical query through the same full VectorPrism pipeline
   and supplement original-query retrieval with up to five additional candidates.
5. Retain source and historical restrictions, deduplicate document IDs, expand
   authorized graph connections, and rank the requested relationship.
6. Select a sentence only when the evidence states the entity, relation, and
   direction. Return the original source wording; dictionary terms are not evidence.

Example: "Where would I encounter the coastal moth?" becomes the retrieval
expression "Where does the coastal moth live?" The source "The coastal moth
lives in Norway" supports geographic information, not an exact encounter site
or a guarantee that the user will encounter one.

`prompt_intent.dictionary` exposes the original prompt, canonical expression,
bounded variants, matched entry/sense, term relationships, and expansion status.
Numeric prototype scores still come only from enabled heads and remain soft
signals; lexical expansion does not train or enable any projection head.

## Relationship rules

- Synonyms are sense-specific aids; current rewrites require a full expression.
- Related terms are annotations in this first version, not equivalent queries.
- Antonyms remain labeled contrasts and never enter synonym expansion.
- Known ambiguity (for example "bank") suppresses rewriting until a sense can
  be resolved. An unknown word is not automatically assigned a meaning.
- An expression outside the vocabulary follows the existing pipeline unchanged.

## Verification and remaining scope

Regression tests cover location, color, taxonomy, and causal paraphrases;
negation, conditions, unresolved references, ambiguity, and antonym isolation;
missing evidence; and actual secondary-query encoding with unchanged source
scope and timestamp. Broad paraphrase support remains partial. Extending the
dictionary requires new positive examples and negative examples that must not
be rewritten. Live PostgreSQL validation remains separate from these tests.
