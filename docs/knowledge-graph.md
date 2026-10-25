# Source-backed relationship retrieval

See [the current design](current-design.md) for the complete request lifecycle,
conversation loops, verification scope, and remaining limitations.

New ingestion through `Appliance.index_chunks`, `catalog_chunks`, or `ingest`
stores a directed fact graph in the namespace's
`.chorusgraph/cpu-llm/<namespace>/knowledge_graph.db`. Existing documents must
be ingested again to populate this graph; opening an old namespace does not
backfill it. Calling VectorPrism directly does not populate it.

The initial extractor accepts explicit affirmative clauses for `is_a`,
`alias_of`, `lives_in`, `has_color`, `has`, `has_lifespan`, `causes`, and
`differs_from`. Each edge retains its document
ID and exact supporting sentence. `has` preserves possession wording without
assuming that every possessed object is a body part. Negated, conditional,
modal, and unresolved pronoun claims are excluded. This is a limited rule
extractor, not a general relationship understanding model.

Ordinary retrieval supplements dense results with at most 12 documents from a
two-hop neighborhood capped at 24 facts. Exact normalized entity phrases seed
the traversal; multiword entities take priority over shorter substrings.
Traversal can follow either endpoint for discovery; stored facts remain directed.
Only authorized edges can participate, including intermediate edges. Returned
paragraphs must still contain the supporting sentence. Passage records expose
the matching `graph_evidence`. Paths discover source evidence and do not prove
transitive claims or automatically produce a new answer.

Replacement ingestion clears replaced facts, corrections replace current facts,
and source deletion removes its fact edges. Historical queries bypass graph
expansion because this first graph stores current facts only. The original
word-cooccurrence graph and vector signatures continue unchanged.

The implementation currently scans the namespace's fact rows for matching
endpoints. Output size and hop depth are bounded; lookup cost still grows with
graph size. Large deployments need indexed entity lookup and traversal before
treating this as a scalability improvement.

## Six independent channel memberships

Connections now retain an assessment for all six VectorPrism channels. These
are independent predicates: an explicit alias can support both `identity` and
`relational`; a type statement supports `hyperbolic` and `relational`; a stated
cause supports `causal` and `relational`. Explicit contrast statements provide
symbolic `disentangled` relevance. These symbolic labels do not assert that
an untrained projection learned taxonomy, identity, causality, or disentanglement.

At ingestion, endpoint phrases are encoded through the same VectorPrism
encoder/projection in batches. For enabled heads the connection assessment
records channel scores: cosine for dense/disentangled, negative distance for
relational/identity, negative Poincare distance for hyperbolic, and the directed
bilinear score for causal. A caller must supply calibrated `thresholds` on the
`KnowledgeGraph` before these scores can produce boolean vector matches.
Disabled heads never vote; missing or uncalibrated results remain unknown.
The shipped checkpoint still has only dense and identity enabled. This change
does not enable or train the other heads, and it does not overwrite channel
slices with boolean labels.

Every assessment separates `symbolic_supported`, `vector_match`, `vector_score`,
`head_enabled`, and combined `active` membership. `active` is true if either
explicit symbolic support or a calibrated vector match exists; otherwise it is
false for a measured vector nonmatch, or null for an unknown result. Channel
association is not factual entailment. Epistemic/source support is separate
metadata; source presence never assigns a truth score of one.

Use `graph.neighborhood(question, channels={"identity", "hyperbolic"})` to
filter traversal to those supported channels, or `graph.word_channels(word)`
to inspect a word/phrase's incident connections by channel. Access restrictions
apply before either operation traverses edges. Ordinary retrieval exposes the
assessments in `graph_evidence`, including for dense hits already present; the
six channel readings expose their matching connections. Legacy fact tables
migrate automatically; re-ingest to compute endpoint vector scores for old rows.

## Prompt intent routing and sentence selection

`VectorPrismIndex.intent_for` reuses the prompt's full 1024-dimensional encoding
and compares enabled channel slices with six cached intent prototypes. Each
channel uses its own scoring function (cosine, negative Euclidean/Poincare
distance, or directed causal score). Recognized prompt forms provide independent
symbolic channel activations. Prototype scores are uncalibrated soft priorities,
not trained intention labels, and disabled heads contribute no vector score.

Ordinary retrieval now returns `prompt_intent`, prioritizes matching graph
relationships before applying the graph budget, and reranks candidates using
the requested relationship and channel weights. Alias connections remain
available as bridges. Source restrictions still apply before traversal and
before candidate ranking; historical requests still skip current-graph expansion.
Dense retrieval supplies the initial candidates; this does not turn disabled
VectorPrism projection heads into trained multichannel ANN indexes.

For supported question forms, answer selection requires the same entity (or
an explicit alias), requested relation, direction, and supported channel. Current
forms cover kind/type, lifespan, color, location (`live`/`reside`), possession, and directed
causes, including explicit `because` sentences. The selected output quotes its
supporting sentence rather than inventing a sentence from nearby words. Missing
relations produce a nonanswer; incompatible color values retain a conflict.
Other question shapes retain their existing producers. Comparative intent is
reported but does not yet implement a general contrast answer generator.

Dictionary-assisted equivalent expressions now precede this routing step.
See [the paraphrase design](dictionary-assisted-paraphrases.md) for vocabulary,
guards, secondary-query embedding, tests, and remaining limits, and the
[support backlog](intent-support-backlog.md) for the other design questions.

For recognized missing lifespan, location, color, and possession attributes, the agent performs a bounded
second retrieval before concluding that evidence is insufficient. See
[attribute-directed retrieval and applicability joins](attribute-directed-retrieval.md).
