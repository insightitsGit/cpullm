# Missing-attribute retrieval repair

A first retrieval miss does not establish missing data. For supported lifespan,
location, color, and possession/parts questions, the agent now performs one
bounded repair round before returning insufficient evidence.

## Plan and join

Recognize "How long does X live?", "How many years can X live?", and
"What is the lifespan/longevity of X?" as `has_lifespan` requests. Preserve the
entity, units, bounds, and original source sentence. Initial evidence may state
`X -> is_a -> Y`, with explicit aliases connecting the names of X.

If no direct or conflicting answer exists, encode a subject-attribute query
through VectorPrism, then queries for up to two explicitly connected classes:
`X lifespan longevity age years lived`, followed by equivalent attribute searches
for Y. Each query returns up to five candidates, at most three queries execute,
and repair stops early when the question is answered or conflicting. Every
query retains the caller's source scope and historical timestamp. The result's
`attribute_search` records the queries, verified membership premises, budget,
and final answerability status. This is retrieval over existing local data;
it does not browse the web or assume that the data contains a lifespan fact.

The same plan uses attribute-specific vocabulary for habitat/geographic range,
color/colour/hue, and parts/features/possessions. After each unsuccessful query,
it re-extracts authorized evidence: a newly discovered type membership can add
a class query within the same three-query budget. This closes the case where
the initial retrieval missed both the attribute and the type connection.

The analogy is an evidence join, with an applicability constraint:

- A new explicit lifespan fact about X can answer directly.
- A verified `X is_a Y` plus an explicit universal `All Y`/`Every Y` lifespan
  rule can answer by quoting both premises. This first implementation supports
  one type-membership hop and up to two alias hops, not arbitrary inheritance.
- Explicit aliases can bind the class named by a universal rule to the membership
  class. Alias traversal has a fixed two-hop bound independent of source order;
  identity premises remain in `supporting_evidence`, and class-alias premises
  needed by the join are retained with the quoted membership/rule evidence.
- The same universal-rule applicability check supports the other three
  recognized attributes. Ordinary class descriptions are never treated as
  universal inheritance rules.
- A value about `some Y`, an unquantified Y statement, or a group average is
  related evidence, but does not establish X's lifespan.
- Membership cannot be reversed, and an incidental word connection is not a
  type-membership premise. Conflicting direct values retain a conflict.
- A direct color/lifespan fact does not hide a conflicting applicable universal
  rule. Such evidence remains conflicting rather than silently preferring the
  direct sentence.

## Limits

The initial extractor accepts numeric year/month/day statements with optional
`up to`, `at least`, `about`, or `around` qualifiers. It deliberately rejects
many richer expressions, conditions, and unresolved pronouns. Universal rules
are source assertions, not independently established biological truths.
Evidence-qualified sentences are quoted rather than replaced by an invented
species-specific statistic. Attributes outside the four recognized relations
and complex inference remain open.

See [the response-case review](response-cases.md) for the independent SQLite
`INNER JOIN` test oracle, live PostgreSQL cases, and remaining response gaps.
