# Review: prompt research planning and six-channel cycle exploration

Date: November 4, 2026. Status: original design review, not runtime proof.
Subsequent initial implementation and remaining stages are recorded in
[the implementation record](research-cycle-implementation.md).

- [Design A: prompt expansion](prompt-research-expansion-spec.md).
- [Design B: cycle exploration](six-channel-cycle-exploration-spec.md).

## Confirmed owner decisions

Design A turns brief document-writing requests into richer evidence-seeking
research plans. Design B follows related entities and relations across layers,
assesses the six channels, and seeks cycles through the starting entity/sense.
Default maximum rounds is 1,000, configurable from 1 to an absolute ceiling of
100,000. Other resource safeguards still apply. **Collect multiple loops within
budget**, continuing other branches after each closure.

Only these design documents are being added. No runtime node, API flag, database
migration, release or benchmark result is implied.

## Gaps resolved in the proposed specification

1. **Prompt expansion could invent intent.** Separate explicit controls, confirmed
   context and suggested research facets. Preserve spans/origins and clarify
   material ambiguity. A rendered long prompt is derived planning text, not facts.
2. **Why questions could assume a relationship/cause.** Require existence and
   relationship evidence before mechanism/causal investigation; no cause inferred
   from similarity, channel agreement or a closed path.
3. **A cycle could become a mandatory answer gate.** Keep factual answerability
   separate. Acyclic evidence remains useful; closing a cycle proves no new fact.
4. **Repeated spelling could create false identity.** Use tenant/entity/sense
   keys; aliases require evidence. Values and multiword entities remain typed.
5. **Cycle search could run forever or explode in one round.** Iterative paged
   expansion with hop, node, edge, frontier, memory, I/O, result and time limits.
   A 100,000-round allowance is not a promise to complete that depth.
6. **A global visited set could discard valid alternative loops.** Path-local
   cycle checks plus canonical state/result deduplication, bounded retained
   ancestry and honest completeness flags.
7. **Undirected traversal could manufacture loops.** Preserve asserted direction;
   reverse navigation is explicit, and synthetic reverse bounces do not qualify.
8. **Six-channel voting could manufacture confidence.** Evaluate every channel,
   preserve symbolic/vector distinctions and unknown states; require relation-
   appropriate checks and independent source/identity/permission gates.
9. **Disabled heads could look trained.** Reuse current head availability and
   calibration metadata. No score from a disabled head is a positive vote.
10. **Nested expansion could evade budgets.** One request-wide ledger includes
    children, replans, rejected edges, DB pages, verification and continuation.
11. **Changing sources could invalidate paths.** Consistent snapshots, validity
    intervals, scoped caches, revocation rechecks and expirable checkpoints.
12. **Genre promises could exceed implementation.** Email/memo/proposal support
    is explicitly proposed; current document recognition is narrower. Drafting
    cannot send mail or invent approvals/deadlines/sender identity.

## Remaining implementation gates

These are design choices requiring agreement or implementation evidence. They
are not silently presented as existing features.

### G1. Cycle qualification and useful explanation

The proposal excludes trivial alias-only loops and synthetic reverse bounces,
and admits source-backed directed simple cycles. Before coding, define the
relation-composition registry and example meaningful loops for the intended use
cases. Decide whether broader navigation should have a separate non-cycle path
discovery mode. A directed taxonomy may have no cycles by design; do not corrupt
its edges merely to force closure. A cycle in a supposed hierarchy may instead
be a data-quality problem. Classify rather than reward it automatically.

### G2. Activation and operating modes

Proposed initial policy: Design A activates for supported explicit deliverables;
Design B requires explicit opt-in. Agree the API field names, prompt controls,
operator ceilings, and strict-mode policy before updating flag_contract/OpenAPI.
Recommended first strict behavior: keep Design B off; later discovery-only
integration needs adversarial tests before any expansion of strict answers.

### G3. Storage and stable identifiers

The current companion graph uses normalized text endpoints and bounded SQLite
neighborhood reads, not a canonical entity/sense graph or a transactionally frozen
cross-store snapshot API. Design B therefore needs a versioned schema/adapter,
canonicalization policy, span-level proof references, indices and migration plan.
Specify synchronization with PostgreSQL corrections/deletion/time validity and
prove failure recovery before long traversal. Preserve current data contracts.

### G4. Resource budgets and scheduling

Only the 1,000/default and 100,000/maximum round limits are owner-approved exact
values. Other numeric defaults in the specs are proposals for load testing.
Benchmark high-degree hubs, long chains and many cycles to set realistic memory,
latency, I/O and path retention limits. Choose priority versus breadth scheduling,
and disclose whether pruning prevents exhaustive search. Wall-clock truncation
does not guarantee identical selected results across runs.

### G5. Calibration and semantic judgments

Determine relation-specific mandatory checks and calibrate enabled vector
thresholds on held-out data. Untrained channels cannot become learned validators
by configuration. Contradiction, uncertainty, negation and temporal conditions
need explicit eligible-edge rules and adversarial cases.

### G6. Prompt templates and unsupported formats

Agree genre templates, mandatory fields and placeholder/clarification behavior.
Add an initial curated phrase registry and unknown-phrase policy. Avoid promising
“all keywords” or unrestricted interpretation. Align existing task, encoder,
snapshot, response and pagination caps with proposed research questions.

### G7. Evaluation and rollout

Freeze a baseline and separate plan fidelity, retrieval recall/precision,
cycle correctness, claim correctness, evidence completeness, abstention and
resource behavior. Evaluate each new node independently and together. A node can
find more words/cycles while making final answers worse; measure that explicitly.
Use fixture/existing-failure regressions plus fresh independently written queries.
Keep new behavior behind optional controls until the acceptance gates pass.

## Suggested staged implementation after design approval

1. Add typed plans, phrase registry, provenance and baseline-compatible dry-run
   planning; test intent preservation before changing retrieval.
2. Add graph entity/edge adapters and snapshot/budget contracts with compatibility
   migration tests; do not raise the legacy hop cap globally.
3. Add iterative multi-cycle exploration and complete six-channel receipts on
   synthetic authorized graphs; validate limits and failure outcomes.
4. Integrate scoped retrieval and evidence judgment, then document composition,
   response budgets and resumable clarification. Preserve strict isolation.
5. Run independent and combined evaluations, update flags/API/manuals, and only
   then decide defaults or release claims.

## Review basis

Read current source symbols in prompt_ingestion.py, request_planner.py,
document_workflow.py, flag_contract.py, knowledge_graph.py, channels.py and
connection_channels.py. The documents distinguish current behavior from proposed
contracts. No runtime tests were run: this change adds design documentation only.
