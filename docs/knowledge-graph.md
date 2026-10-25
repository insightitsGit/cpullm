# Source-backed relationship retrieval

New ingestion through `Appliance.index_chunks`, `catalog_chunks`, or `ingest`
stores a directed fact graph in the namespace's
`.chorusgraph/cpu-llm/<namespace>/knowledge_graph.db`. Existing documents must
be ingested again to populate this graph; opening an old namespace does not
backfill it. Calling VectorPrism directly does not populate it.

The initial extractor accepts explicit affirmative clauses for `is_a`,
`alias_of`, `lives_in`, `has_color`, and `has`. Each edge retains its document
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
