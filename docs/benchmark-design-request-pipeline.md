# Fresh-corpus request-pipeline benchmark design

Proposed 2026-10-27. This is an evaluation specification, not a completed run or
an accuracy claim. Execution handoff: [handoff](handoff-fresh-pipeline-benchmark.md).
Reference contracts: [current design](current-design.md),
[request separation](request-separation.md), [response depth](response-depth.md).

## Questions this run must answer

Does separating a compound prompt improve retrieval and task coverage? Does each
answer address the requested entity, relationship, direction, and polarity? Are
all proof premises permitted and preserved through the final judge? Does the
library ask for missing intent rather than inventing it? How much CPU time and
memory does this cost as the corpus grows?

Cover every documented behavior family and its negative cases. This is bounded
coverage, not a claim to cover every possible English prompt. Distinguish a
supported-contract failure from an unsupported capability handled safely.

## Fresh fictional data and independent gold

Create a versioned `corpus.jsonl`, `cases.jsonl`, `conversations.jsonl`, and
`manifest.json`. Use three fictional domains: observatory instruments, botanical
conservatory exhibits, and warehouse vehicles. Do not reuse Cedar, Iris, lobster,
crane, bat, spring, Millhaven, or existing fixture values. Use seed 271027 for
development and a separate recorded seed for a frozen holdout. Gold is stored
outside ingestion: never insert answers, case labels, or expected outcomes into
the retrievable corpus.

Start with at least 120 hand-audited factual paragraphs, spread over public,
restricted, conflicting, and historical sources, plus 300 matched distractor
paragraphs. Include exact-name collisions, near names, irrelevant same-number
facts, reversed relations, negated predicates, and same-attribute other-entity
facts. Keep provenance and stable paragraph IDs for every sentence. Retain original
source text and the actual IDs assigned by ingestion; fail on mapping errors.

Illustrative development facts (not a frozen holdout):

```text
The Vesper is a survey rover.
The Vesper is amber.
The Vesper is found in Orinth.
The Vesper has a camera.
Every survey rover has a beacon.
Every survey rover lives for 17 years.
The Vesper stopped because its battery failed.
The Nacre is a display rover.
Some display rovers have a beacon.
```

For Vesper lifespan the gold proof is membership plus the universal rule; for
possession it includes the direct camera fact and both beacon premises. Nacre
does not inherit a beacon from `Some`. Add a separate restricted document with a
different Vesper color and a unique secret marker. Explicit correction events
must have fixed valid-from timestamps and separate expected current/as-of answers.
Do not assume these illustrative grammars all work: the benchmark must reveal
extraction failures rather than change its source wording after observing results.

Author gold from source meaning, independently of runtime extractors. Record
alternative minimal proof sets where several proofs are valid. For bounded joins,
also compare against a small independent SQLite membership/rule join oracle;
do not import the library's selector into the oracle. Freeze the holdout before
running it; after a bug fix, report that holdout as a known regression set and
create a new holdout for a new generalization claim.

## Coverage inventory

Minimum 180 standalone cases: 120 development and 60 frozen holdout, with all
three domains represented in every family. Assign one primary family per case
for denominator accounting; additional tags describe intersections. Minimum
counts below sum to 180:

- Direct attributes, identity, direction, polarity: 24. Include location, type,
  color, possession, lifespan, unknown entity, and a present but irrelevant fact.
- Licensed joins and rejected joins: 28. Universal versus some/average/unquantified
  class; missing membership or rule; alias bound; conflicting direct/rule values;
  both possession types; proof removed, out of scope, deleted, or not yet valid.
- Dictionary and lexical interpretation: 12. Known synonyms, spelling variants,
  antonyms, ambiguous senses, and unknown local glosses. A source-specific synonym
  not supported by the current implementation is a capability probe, not an
  assumed positive answer.
- Cause, scope of the effect, and contrast: 12. Exact stated cause versus a
  different action/entity, reversed cause, adjacent but noncausal facts; explicit
  comparison forms use the current unsupported contract where applicable.
- Ambiguity, references, and criteria: 16. Many attributes of one entity versus
  two referents sharing a name; singular/plural/event references; best without a
  criterion, criterion with/without explicit ranking evidence.
- Response depth and presentation: 16. Brief/default/detailed overview, list,
  counts 1/3/20/21, contradictory style cues, quoted style words, sparse evidence,
  strict-word-count request marked unenforced, required proof above format budget.
- Separation and retrieval targeting: 36. Two/three/eight tasks; question marks,
  numbered lists, semicolons and recognized command conjunctions; quote/code/name
  protection; source spans; local/global style; explicit long Context:/Questions:;
  partial answers, conflicts and unsupported children; one-item budget with three
  tasks; mixed factual and existing specialist requests.
- Authorization, history, guard, lifecycle: 24. Public/restricted/empty scope,
  tenant separation, raw/resolved guard, corrections/as-of, reopen, replacement,
  reingestion and deletion; secret-bearing background is not authorized evidence.
- Unsupported forms and resource boundaries: 12. Arbitrary ellipsis, forward/event
  references, compare-those-answers dependency, unlabeled narrative, nine tasks,
  32,001-character prompt, 1,001-character batch task, actual tokenizer overflow,
  batch payment proposal. Include just-below/at-limit counterparts among the 36
  separation cases. No silent dropping, unlicensed action, or completion claim.

Add at least 24 multi-turn scripts (12 development, 12 holdout), separately
counted from standalone cases: reference and criterion completion, evidence quote
attribution, cancel/start over, new-question abandonment, two successive
clarifications, first/middle/last child clarification, stateless follow-up,
same session under different caller/scope/as-of/tenant, expiration, restart, and
concurrent first-time parents. Record expected pending and completed task IDs at
each turn. Use a controllable clock for TTL checks; no 30-minute sleep.

Six-channel coverage means recording explicit cues, enabled-head flags, symbolic
edges, unavailable heads, and chosen relation, across dense, relational,
disentangled, taxonomy/hyperbolic, identity, and causal/time readings. Do not
require all six to activate, force unavailable heads on, interpret scores as
probabilities, or classify epistemic metadata as a seventh semantic channel.

## Case schema and scorer

### Combined response budget: required coverage after the separator fix

Include these checks within the existing response-depth/separation cases and
conversation scripts; the minimum totals remain 180 cases and 24 scripts:

- Two overview tasks plus `Answer in three sentences.` allocate two optional
  units to q1 and one to q2. Check allocation and actual child producer ceilings.
- Brief mode gives each task one optional unit; standard mode shares six and
  detailed mode shares sixteen, with at least one per task. Test two, three and
  eight tasks. Longer Context: text must not increase the allocations.
- Global sentence/item counts are shared, not multiplied by task count. Counts
  below task count retain all outcomes and expose the coverage override. Combined
  allocation is capped at 160 optional units, with coverage taking priority.
- Local brief/count instructions may reduce allocations; local detailed wording
  cannot bypass the shared ceiling. Local bullet counts use item ceilings, not
  sentence ceilings. Existing producer ceilings may be below allocated shares;
  unused capacity need not be filled.
- Clarification at the first/middle child and its resumed turn retain original
  allocations. Completed answers and pending tasks remain visible.
- Aggregate rendering no longer automatically repeats full question headings.
  Original questions, order, IDs and spans remain in the plan/results. Legitimate
  answer words that also occur in the question are not a repetition failure.
- Required join premises, conflicting evidence, citations, specialist output and
  clarification notices may exceed the optional budget. No clipped claim, lost
  premise, missing outcome, or post-judge text alteration is acceptable. This is
  not a hard rendered-length limit; strict word counts remain unenforced.

Save `response_plan.combined_budget`, its requested/effective optional budgets,
`task_allocations`, `hard_limit`, and coverage override, plus each child's
`response_plan.combined_task_budget` and sentence/item ceilings. Report actual
aggregate words/characters, optional producer units, repeated-heading overhead,
and proof/notice overhead separately where traceable. Mark unavailable measures
explicitly rather than guessing. Compare paired prompts with identical questions
and short versus long background. Shorter output is not an improvement if
coverage or proof is lost.

### Gold and outcome scoring

Every case specifies ID, split, primary family, tags, source IDs, exact prompt,
caller/scope/as_of, constructor settings, optional session/turn, contract version,
expected task order and relations, semantic outcome, allowed claim tuples,
required/alternative proof sets, forbidden assertions and private markers.
Use typed outcomes: answer, quote, clarification, conflict, insufficient evidence,
unsupported, blocked, budget refusal, pending, and cancelled. Capture actual raw
status vocabulary and map it explicitly to these evaluation outcomes.

Score independently:

1. Plan exactness: task boundaries/order, source offsets, bound entity, relation,
   dependencies, and no accidental tasks from quoted/source text.
2. Retrieval: gold evidence recall@k/precision@k for initial dense candidates and
   final expanded candidates separately, complete-proof recall, repair counts.
   Record all calls per child through a read-only instrumentation wrapper. Without
   stage visibility mark that metric unavailable; do not infer it from citations.
3. Claims: supported correct assertions, false assertions, omitted required claims,
   unnecessary clarification, appropriate abstention, recognized conflict.
   A true partial answer is incomplete, not false. Clarification options are not
   assertions. Contradiction quotes in a conflict are not endorsed facts.
4. Evidence: accepted claim/proof alignment, all premises present, valid source,
   historical interval and authorization. Similarity and channel labels are not
   proof. Include `supporting_evidence` identity bindings where needed.
5. Delivery contract: check `reply.text`, `reply.body`, `answer`, status,
   `answer_status`, `audit_passed`, `judgment`, `shine_final`, evidence and every
   child result. Validate the documented per-task aggregate: `answer=None`,
   `audit_passed=False`, explicit pending/missing tasks, `complete` only when all
   required tasks finish successfully. Rejected diagnostic text is not an answer.
6. Conversation: completion, attempts, correct pause/resume, isolation, cancellation,
   abandoned-plan cleanup, and no retrieval before an early guard/scope refusal.

Use assertion and proof matching, not whole-answer equality or phrase presence
alone. Keep a small manually reviewed scorer fixture set: complete, partial,
wrong entity, reversed/negated claim, valid alternative proof, missing premise,
conflict quote, clarification options, private diagnostic leak, aggregate partial.
Inspect every failed/uncertain judgment and a seeded 10% of passes. Record manual
adjudication as a separate versioned artifact; never silently rewrite raw scores.
Contract disagreements are visible and excluded from accuracy until adjudicated,
with the count and excluded denominator reported. No cloud judge is required.

## Arms and paired measurement

Run dense default and resonance opt-in on identical frozen sources and prompts,
each with its own clean namespace and fresh local stores. Keep reference backend
`None` for the primary run. Optional installed coreference adapters are separate
arms, never unreported substitutions. Record enabled trained heads and exact
model/checkpoint hashes; no automatic downloads.

For each compound case, also execute its independently authored gold atomic
queries as a retrieval reference. Compare compound child retrieval to those
queries, preserving source scope/history and avoiding shared conversation state.
Where the pre-separator commit can run the same contract, add a separately labeled
historical arm; do not fake an ablation by rewriting the current private pipeline.
An atomic-query reference is not itself a causal proof of improvement.

Report per family, per child, per prompt, per conversation, and per arm. Include
macro and micro scores with numerator/denominator; all expected answer cases stay
in answer-coverage denominators even if the system asks or abstains. For retrieval,
report both conditional-on-search and end-to-end coverage, including zero-search
misses. Never average pending children into successful responses.

## Scale and operational checks

After correctness, run 1,000 and 10,000 seeded distractor paragraphs, including a
frequent-name ambiguity stress set. Preserve factual gold and vary distractor
order with three seeds. Include ingestion/reopen/correction/deletion checks at
each scale. At 10,000 paragraphs test complete joins beyond the first shortlist.
Do not call a partial ingest a completed scale run.

Measure startup/model load, ingestion throughput, peak process-tree RSS including
database separately, database/local-store bytes, and cold versus warm query time.
Warm measurements: one excluded warmup then 20 repetitions of a fixed 30-prompt
mix per arm/scale. Report p50/p95/max and sample count, separated by answer,
clarification, abstention, and task count. Include retrieval/repair calls and
timeouts. Concurrency probes: 1/4/8 callers with distinct sessions, plus controlled
same-session ordering; do not imply distributed session guarantees.

## Decision gates and immutable artifacts

These are proposed acceptance thresholds, not measured results:

- Zero unauthorized evidence/marker disclosure, unlicensed executed action,
  false successful completion, or silent task loss. Any one blocks readiness.
- Zero false assertions on mandatory curated negative cases; report all false
  assertions separately on the larger generated set.
- At least 95% supported-task correctness and full-proof retention overall;
  at least 90% within each supported primary family. Small slices report exact
  counts and uncertainty, not just percentages.
- At least 95% plan exactness and conversation completion on supported scripts;
  no regression in scope/guard/history invariants in either arm.
- At least 95% complete-proof retrieval on supported answerable cases. Publish
  paired changes against atomic and available historical arms, including losses.
- Performance has no invented absolute SLA: publish measurements and regressions;
  flag >20% warm p95 increase against a comparable arm for investigation. A
  timeout/incomplete scale run remains a failure to establish that scale result.

Keep unsupported probes in a separate capability report with safe handling and
unmet behavior recorded. Do not turn them into supported answers to improve a
headline score. Passing fictional data is not a production or real-world truth
certification; later customer-domain evaluation remains necessary.

Every run writes a new nonexisting directory with UTC run ID: source commit,
dirty diff/status, environment and dependency/model hashes, database version and
settings, seeds and SHA-256 manifests, complete sources/gold, scorer version,
ingestion mapping, raw public results and instrumented retrieval traces, timings,
machine-readable verdicts, suite output, manual adjudications, and `REPORT.md`.
Redact DSN credentials. Reject dirty runtime trees for an official baseline;
an exploratory mixed-tree run must archive its patch and be labeled accordingly.
Never overwrite the October 25 baseline or conflate its scorer with this one.

