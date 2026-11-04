# Design B: Six-channel relationship and cycle exploration

Status: target specification with an initial source implementation. Further
stages remain proposed. Date: November 4, 2026. See
[actual implementation boundaries](research-cycle-implementation.md).
Working name: semi-deterministic exploration node. This describes bounded search
plus channel-guided prioritization, not a truth guarantee or a new trained model.
Companion: [Design A](prompt-research-expansion-spec.md).

## Accepted requirements

Start from a resolved entity/word sense A. Expand its connections into layer B,
then their connections into C, and continue beyond two or ten layers when budget
allows. Seek cycles returning to the same A. Preserve relations and full paths,
not merely flattened word lists. Evaluate all six channels for connections.

Default `max_rounds`: **1,000**. Configurable integers **1 through 100,000**,
inclusive. Reject booleans, fractions, strings, zero, negatives and larger values;
do not silently clamp. An operator ceiling may reduce the effective budget.

Owner decision: **collect multiple qualifying loops within the search budget**.
The first closure ends that branch, not the whole search. Other branches continue
until exhausted or a budget/result limit is reached. No unlimited enumeration.

## Current implementation versus proposal

`knowledge_graph.py` already stores directed source-backed facts and channel
assessments in a SQLite companion graph. Its neighborhood default is two hops
and implementation clamps traversal to three. `channels.py` reads the six
signals on a retrieved shortlist; `connection_channels.py` evaluates all six
connection functions, separating symbolic support from calibrated vector scores.
The dense retrieval index uses PostgreSQL/pgvector; the connection graph is not
currently that same database. Do not describe every graph edge as a dense vector.

This design needs a new bounded traversal interface and coordinator, not merely
raising the current `hops` cap. Preserve existing neighborhood behavior by default.
Only dense/identity heads are trained/bundled; missing or disabled vector heads
remain unavailable, never positive validation votes. Epistemic attribution/truth
metadata is separate from the six semantic channels.

## Graph and path contracts

A node key includes tenant, canonical entity ID and sense ID. Surface spelling
alone is insufficient. Unresolved aliases need evidence/clarification. Attribute
values, dates and quantities are typed endpoints, not automatically entities to
expand. Phrase concepts remain phrases; do not connect individual shared tokens
as if they were entity identity.

An edge contains stable ID, directed endpoints, relation type, original source
record/span/hash, validity interval, source authorization reference, extraction
version, symbolic/vector channel assessments and qualifiers/negation where
supported. Unsupported extraction must not discard qualifiers to create an edge.
Duplicate claims retain their distinct source proofs but share a canonical claim
key for traversal deduplication.

A path contains ordered node/edge IDs, navigation directions, proof references,
channel assessments, relation-composition status and budget counters. Similarity
links can discover candidates but cannot close an evidence-qualified factual cycle
without source-backed relationships. An explicit alias is not a causal edge.

Use authorized outgoing edges by default. Incoming edges can be an explicit
discovery option, always marked as reverse navigation; never reverse the asserted
relation. Reusing the same edge backward does not create a meaningful cycle.

## Round semantics and cycle algorithm

One round means expanding one complete frontier by at most one edge; it is a hop
layer, not one database request or one visited word. Closure at depth d occurs
during round d. The root itself is depth zero. Resource exhaustion partway through
a frontier leaves that round incomplete and must be recorded.

Use an iterative worklist, not language-stack recursion. Retrieve adjacency in
bounded pages; do not materialize a huge layer before checking resource limits.
Expand candidates in a stable ordering, with fixed-version optional channel
ranking and stable ID tie-breaks. Fair scheduling across seeds/tasks must prevent
one high-degree branch consuming the entire request unnoticed.

For each candidate extension:

1. Check shared budgets, snapshot visibility, authorization and edge eligibility.
2. Evaluate all six channel functions, retaining unknown/not-applicable states.
3. If the target is the same resolved A and the path qualifies, record a closed
   cycle and stop extending that branch. Continue other branches.
4. Otherwise, if the target already occurs on this path, prune this branch.
   A -> B -> C -> B cannot extend a simple cycle through A.
5. Deduplicate canonical equivalent states/cycles; preserve distinct relevant
   paths/proofs within budget. Do not globally suppress every revisited node:
   that would lose valid cycles reached through another path.
6. Queue eligible remaining extensions if the frontier/path memory limit allows.

A qualifying cycle contains at least two distinct semantic nodes and distinct
directed edge claims. Self-loops, an edge plus its synthetic reverse, repeated
nodes other than closing A and alias-only loops are excluded from meaningful
response results. They may be trace diagnostics; their existence is not evidence
of a substantive explanation. Repeated laps A -> ... -> A -> ... -> A are not new
cycles. Deduplicate cycles by ordered canonical edge claims anchored at A;
reverse paths remain distinct only if separately asserted directions exist.

This seeks bounded simple cycles, not every possible walk. Enumerating all cycles
can be combinatorial; no completeness claim is allowed after pruning/caps.

## Six-channel assessment policy

Evaluate all six channels per candidate; require the relevant checks for the edge
type, not six positive votes. Proposed common fields: `applicable`, `active`,
`symbolic_supported`, `vector_status`, `vector_score`, `threshold`, `reason`,
and evaluator/model versions. Preserve existing true/false/unknown semantics.

- Dense: relevance signal; insufficient by itself for a factual connection.
- Relational: supported relation type, direction and source argument binding.
- Disentangled: explicit contrast or available calibrated factor signal; do not
  claim a disabled head proves distinct meanings.
- Hyperbolic: supported hierarchy/membership; geometry only if enabled/valid.
- Identity: explicit alias evidence or available calibrated identity signal;
  canonical sense identity remains mandatory even on non-alias edges.
- Causal: supported directed cause; correlation, adjacency or closure is not cause.

Source validity, authorization, temporal consistency, contradictions and identity
are independent mandatory checks. Never average a failing mandatory check into
a passing weighted score. Thresholds need calibration; unknown is not true.
Record channel outcomes at edge level and compose path status using an explicit,
versioned relation rule registry. Do not multiply scores into a truth probability.

## Resource policy: proposed defaults needing load validation

In addition to the accepted round limits, propose:

- 10,000 unique visited nodes; 50,000 examined edge records.
- 10,000 queued path states; 100,000 retained path-link records; 64 MiB tracked
  working-state ceiling. Use parent-linked paths, not full copies per extension.
- 32 returned qualifying cycles; maximum 1,000 hops materialized per displayed
  path, with full retained proof references only within storage/output budgets.
- 5-second exploration deadline and 64 adjacency-page reads per request.

These are safety defaults to benchmark, not measured throughput promises.
Increasing rounds does not increase these caps automatically. Reaching 1,000 or
100,000 hops may require separately authorized higher resource budgets, still
within operator ceilings. Runtime accounting includes rejected edges, channel
evaluation, database reads and retained paths. Bound raw text/IDs and checkpoint
sizes; an edge count alone is not a byte-memory bound.

All limits apply across seeds, child questions and replans through one parent
budget ledger. Individual database reads need bounded timeouts/cancellation;
no detached worker should keep searching after caller cancellation.

## Outcomes and meaningful response rules

Return `cycles`, `accepted_evidence`, `coverage`, `counters`, `limits`, `snapshot`,
`policy_versions`, `complete`, `stop_reason` and `continuation` where supported.

Stop reasons include `frontier_exhausted`, `max_rounds`, `node_limit`, `edge_limit`,
`frontier_limit`, `memory_limit`, `retrieval_limit`, `deadline`, `result_limit`,
`cancelled`, `clarification_required` and `error`. Partial cycles/evidence may be
returned after a budget stop, clearly marked incomplete. A closed path with an
unvalidated edge is a candidate, not a validated cycle.

“No cycle found within limits” is different from “no cycle exists.” Even exhaustive
search is only complete for the authorized, retained source snapshot and declared
edge policy. Do not reveal filtered source counts or inaccessible connectivity.

Critically, no cycle is required to answer an ordinary factual question. Taxonomies
and many useful directed graphs are acyclic. Accepted direct facts remain usable
when loop search finds nothing. Conversely, a cycle cannot create a new fact:
“A uses B; B stores C; C references A” supports that attributed path, not a causal
explanation or an unlicensed transitive conclusion about A and C.

Only evidence-supported claims feed existing answer judgment and bounded
composition. Strict mode must not gain new inference: either disable this node
for strict requests initially or use discovery-only candidates that independently
pass the existing strict answer contract. This choice is an implementation gate.

## Snapshot, continuation and activation

Freeze graph/source visibility at a consistent snapshot and `as_of`. Recheck
authorization before displaying proofs and after resume; invalidated evidence
cannot remain usable solely because a checkpoint retains it. Scope every cache
by tenant, permission fingerprint, time, seed sense, policy and model version.

Checkpoint frontier, path ancestry, explored states, selected cycles and consumed
budgets only within an explicitly bounded, access-controlled TTL store. Resume
cannot silently reset the parent budget or replay duplicate cycles. If consistency
cannot be preserved after corrections/deletion, expire the checkpoint and explain.

Propose explicit API opt-in plus unambiguous loop-search prompt controls. A broad
article prompt from Design A may recommend exploration but does not automatically
authorize expensive recursion. Operator disable wins. Exact API names, activation
phrases and checkpoint support remain pre-implementation decisions, not existing
consumer capabilities. HTTP forwards only documented fields until schema changes.

## Required acceptance scenarios

- A chain longer than ten edges closes correctly, with full directed proofs.
- Depth 1,000 is accepted by default; configured 100,000 is accepted; 100,001,
  bools and nonintegers fail validation. Small capped tests verify boundaries;
  a separately budgeted synthetic stress case checks a 100,000-hop chain.
- Two or more cycles through A are collected; the first does not end all search.
- A -> B -> C -> B, self-loops, duplicate sources, aliases and reverse-navigation
  bounce do not create endless work or false meaningful cycles.
- Acyclic data, disconnected data, high-degree hubs and 100,000-round settings
  stop within other caps and accurately expose incomplete coverage.
- Alternate paths survive deduplication; stable input/order yields stable
  operation-bounded results. Deadline-truncated results may differ and say so.
- All six assessments are present, disabled/uncalibrated heads stay unknown,
  mandatory failures cannot be outvoted, and causal claims need causal evidence.
- Tenant/source filtering applies at every hop; correction/deletion/as-of and
  resume cannot leak forbidden sources or retain revoked claims.
- Design A children share budgets; strict/tone/format/output contracts remain
  unchanged; no cycle is treated as a proof of a new transitive fact.
