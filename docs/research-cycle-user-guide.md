# Research planning and cycle exploration: source-branch guide

These features are implemented on `codex/research-cycle-nodes`, after 1.11.2.
They are not in the published 1.11.2 package. No release has been built here.

## Short writing requests

After the usual database/encoder setup, use the existing appliance API:

```python
result = app.ask('Write a detailed article about Helios and PostgreSQL.')
print(result['research_plan']['expanded_prompt'])
print(result['research_plan']['questions'])
print(result['reply']['text'])
```

Recognized ordinary document requests now return `research_plan`, containing
the original prompt, observed keyword spans, template questions, an inspectable
expanded instruction, a stable plan hash, coverage and snapshot/budget metadata.
Observed keywords are annotations, not evidence that arbitrary constraints have
been understood. The existing document parser remains the interpretation boundary.
Explicit subject names are required for ambiguous references such as “it”.

The planner uses one bounded authorized/as-of snapshot, independently recalls
the named sides of an explicit conjunction and follows one layer of explicit
source relations (at most 32 lead labels). It retains complete source records.
It does not require all topic names to occur in a single chunk. A related class
quotation is not rewritten into a property of an individual. The plan's question
coverage says `candidate_evidence`, not that a verified answer was found.

Long-response fixes now use word-based page selection and neutral inverse-verified
predicate composition for ordinary documents. “1,000 words” is not reduced to 20
records; explicit item counts can select up to 500 records. Email/letter defaults
use a draft layout. See [length and composition details](long-document-composition-spec.md).
Body words exclude headings and citations. Evidence shortage is reported rather
than filled with unsupported content.

Cause questions are only added for explicit why/cause/reason wording; recognized
negative directives suppress them. This is a curated phrase/template system,
not an unrestricted prompt interpreter. Unknown constraints remain in the original
prompt. There is no recursive replanning or unbounded subquestion dispatch.

Additional ordinary genres include document, email, letter, memo, proposal,
specification, briefing and summary. Example:

```python
result = app.ask('Draft a concise email to Alex about Helios.')
assert result['research_plan']['recipient'] == 'Alex'
assert result['research_plan']['sending_authorized'] is False
```

These are source-backed drafts; they do not invent a sender, commitment,
approval or deadline. No email is sent. Strict mode retains its original
document genres/selection and does not run the new research planner.

## Multiple cycles through a starting label

Opt in explicitly; response length or an article prompt does not activate this:

```python
result = app.ask(
    'Explore the documented relationship loops through Alpha.',
    cycle_search={'seed': 'Alpha', 'limits': {'max_rounds': 1000}},
)
search = result['cycle_exploration']
print(search['stop_reason'], search['complete'])
for cycle in search['cycles']:
    print(cycle['length'], cycle['qualification'])
    for edge in cycle['edges']:
        print(edge['subject'], edge['relation'], edge['object'])
        print(edge['channels'], edge['proof'])
```

`/v1/ask` accepts the same `cycle_search` JSON object. See the checked-in OpenAPI
schema for exact fields and ceilings. This path runs outside the ordinary graph.
Strict API/header/operator enable wins: cycle exploration returns `unsupported`
before retrieving evidence. Guard and caller/source scope still apply.

The graph is reconstructed only from the authorized/time-valid source snapshot,
not the unversioned persistent companion graph. This avoids changing its existing
three-hop behavior or migrating stored data. Edges retain source spans and hashes.
All six connection functions are evaluated using the existing symbolic evaluator;
no new vector embedding/calibration is performed by this traversal. Unavailable
vector evidence does not vote. Cycle selection requires explicit source relations.

Traversal is iterative and directed. It collects multiple loops and preserves
alternative paths. It prunes internal repeated-node branches, self-loops and
alias-only loops; no synthetic reverse edge is inserted. It does not infer new
facts or a cause from a closed path. A taxonomy cycle can indicate a data problem.

**Identity limitation:** endpoints currently use exact normalized whole labels,
not fully disambiguated canonical entity/sense IDs. Results explicitly carry
`qualification='lexical_candidate'` and an unresolved-sense notice. Do not present
these as semantically validated cycles; quotations retain their independent
attribution. Learned identity distance does not resolve this limitation.

## Search limits and outcomes

- Default maximum rounds 1,000; positive integer ceiling 100,000. One round is
  one outgoing-edge layer. Booleans and nonintegers are rejected, not coerced.
- Defaults: 10,000 nodes; 50,000 examined edges (including graph construction);
  100,000 retained states; 10,000 frontier states; 32 cycles; 64 MiB accounted
  working data; 5 seconds cooperative search time.
- Operator ceilings: 100,000 nodes; 200,000 edges/states; 100,000 frontier;
  100 cycles; 128 MiB accounted data; 60 seconds search time.
- Snapshot bounds remain 10,000 chunks and 8 million characters. Snapshot SQL
  time follows the existing database path, not a new end-to-end deadline.
- Python object/allocator overhead is not a hard operating-system RSS bound;
  memory accounting estimates encoded retained data plus state overhead, not a sandbox.
- Literal reply quotations are bounded at 100,000 characters; presentation
  truncation is reported. The structured cycle result remains separately bounded
  by the search memory/state/result caps.

Increasing rounds does not increase other caps. `complete=False` and `stop_reason`
explain budget exhaustion. Only `frontier_exhausted` is exhaustive for this retained
lexical graph and policy. No-cycle results do not establish absence of relationships
and do not block normal factual answering. No checkpoint/resume is offered yet;
`continuation` is null. A new explicit call is a new search, not hidden continuation.

## Implementation boundaries still open

Persistent canonical entity/sense migration, calibrated vector-assisted ordering,
checkpoint/resume with revocation, broad syntax/constraint interpretation and
adaptive multi-pass research remain separate follow-up stages. The initial nodes
do not advertise those proposed capabilities as implemented.

[Actual long-response and corrected email examples](examples/2026-11-04-long-document-fix/README.md).
