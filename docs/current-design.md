# Current cpu-llm design

Working-tree design snapshot, 2026-10-25. This describes the implementation in
this checkout, including changes not yet committed or released. Earlier
versioned specifications and the white paper describe historical stages.

## Purpose and correctness boundary

The library answers from supplied source text on CPU. It interprets recognized
question forms, retrieves relevant passages and explicit connections, and
selects or constructs bounded source-supported responses. It asks for missing
criteria or unresolved references rather than silently supplying them.

Source attribution, vector similarity, grammatical verification, user preferences,
and factual truth are separate. A source-backed sentence can still be false in
the world. A graph path is not automatically an inference, and a recognized
intent does not establish that the requested fact exists. Arbitrary intention
understanding and free-form sentence generation have not been demonstrated.

## Request lifecycle

1. Authenticate/resolve the caller and enforce source scope. Empty authorization
   refuses the request before conversational state is used.
2. For subjective rankings, inspect missing criteria. A request such as "Which
   lobster is best?" asks what best means and what the user wants it for. No
   embedding or database search is performed for that early clarification.
3. Resolve references against session-local user context with an optional CPU
   backend, or ask for an explicit entity name. Preserve the original prompt,
   mention offsets, antecedent, and resolved retrieval query.
4. Apply typo handling and dictionary-assisted interpretation. Keep the original
   query and optionally encode one recognized equivalent expression. Antonyms
   are not synonyms; unresolved senses and guarded negation are not rewritten.
5. Encode the query using the frozen sentence encoder and VectorPrism projection.
   Evaluate six independent intent channels with explicit question-form cues and
   enabled-head prototype scores. These prototype scores are soft priorities,
   not calibrated intention probabilities.
6. Retrieve dense candidates, optional equivalent-expression candidates, named
   article/tag matches, and a bounded authorized graph neighborhood. Prioritize
   the requested relationship, entity, and direction when ranking candidates.
7. If a supported attribute is missing, perform bounded retrieval repair for the
   entity and verified connected types. Re-plan when a retry discovers a useful
   membership edge, without exceeding the fixed query budget.
8. Run the existing specialist producers and delivery checks. Select supporting
   sentences or licensed template constructions. Missing evidence stays missing;
   recognized conflicting values remain conflicting.
9. For clarified rankings, require a source ranking explicitly tied to the topic
   and the user's criterion terms. If absent, ask for comparison evidence. Quote
   user-supplied statements with attribution; do not ingest them as verified facts.
   Downstream guard/audit/grammar/Shine holds remain authoritative.

The host application displays `reply.text` and returns user replies with the
same explicit `session_id`. The library returns loop state; it does not send
messages or run a background conversation by itself.

## Six-channel representation

The installed VectorPrism tensor is **1,024 dimensions**: a 16-value header,
a 368-value dense core, and five 128-value slices for relational, disentangled,
hyperbolic/taxonomy, identity, and causal/time signals. Epistemic truth is header
metadata, not one of the six semantic slices.

The shipped checkpoint enables dense and identity. The other projection slices
may contain computed numbers but are not treated as enabled trained retrieval
heads. Symbolic channel associations remain available independently: a stated
alias supports identity and relational membership; a stated type supports taxonomy
and relational membership. These labels do not certify trained geometry.

Every connection assessment separates symbolic support, vector score, configured
threshold, vector match, head availability, and combined membership. A word or
entity can participate in connections across several channels. Unavailable or
uncalibrated vector decisions remain unknown. Prompt routing uses cached intent
prototypes, scored with the appropriate channel metric, only for enabled heads.

## Connections, evidence, and storage

- PostgreSQL/pgvector stores passage text and VectorPrism tensors.
- The original word-cooccurrence graph stores untyped associations. Three-hop
  neighbor summaries are hashed into 32 values in the relational slice's tail;
  that signature cannot reconstruct the exact graph or establish a typed fact.
- The namespace's `knowledge_graph.db` stores explicit directed facts and their
  source sentences, including aliases, type membership, location, color,
  possession, lifespan, causes, and contrasts. Endpoint channel assessments are
  stored alongside these facts. Existing data needs re-ingestion for the new data.
- Existing semantic memory retains propositions, event roles, and taxonomy tags.
  Source-text reference resolution is still limited and is not replaced by the
  new conversation-prompt coreference adapter.

The current fact graph scans its rows for lookup; bounded output is not a claim
of indexed graph scalability. Replacement ingestion, correction, and deletion
maintain current facts. Historical queries bypass current-graph expansion.

## Budgets and applicability rules

Ordinary graph expansion uses at most two hops, 24 facts, and 12 added documents.
Dictionary expansion adds at most one equivalent query with five candidates.
Attribute repair executes at most three queries, five candidates per query,
and stops when evidence is answered or conflicting.

Repair currently covers lifespan, geographic location, color, and possession/
parts. A direct fact about the entity can answer. A verified type-membership
premise plus an explicit universal `All`/`Every` rule can support the bounded
join, with both premises retained. A group average, an ordinary unquantified
class description, or a statement about "some" members cannot be substituted
for the requested entity's attribute. This is not arbitrary multi-hop logic.

## Conversation state and optional models

Clarification and reference state are keyed by tenant, caller, source scope,
session ID, and historical timestamp. Without a session ID, pending context is
not shared between calls. Each store caps state at 256 sessions, expires it after
30 minutes, and bounds questioning to three attempts per stage. State is local
to the process and is not durable. Callers should serialize turns within a session.

Coreferee is the primary CPU-tested adapter. Fastcoref is an alternative adapter
whose real model remains untested here. The default backend is `None`, avoiding
automatic downloads; unresolved references then ask for explicit confirmation.
Only the latest user/resolved prompt is retained, up to 4,000 characters. Retrieved
documents and generated answers are not copied into reference history. Optional
adapters preserve compatible number/mention constraints and reject ambiguous,
partial, or ungrounded bindings. Standalone event references remain unresolved.

```python
from cpu_llm.pipeline import Appliance

app = Appliance(reference_backend="coreferee")  # install optional models first
app.ask("Tell me about the European lobster.", session_id="chat-1")
app.ask("Where does it live?", session_id="chat-1")
app.ask("Which lobster is best?", session_id="chat-1")  # asks for criteria
app.ask("taste", session_id="chat-1")  # retrieves, or asks for supporting evidence
```

See the setup document before enabling a backend. Resolving "it" does not by
itself distinguish edibility, permission, and individual safety in "Can I eat it?".

## Response contract

`prompt_intent` exposes channel cues, soft scores, requested relation, and dictionary
interpretation. `graph_evidence` exposes matching source connections and channel
assessments. `attribute_search` exposes repair queries, budget, membership premises,
answerability reason, and accepted evidence. `reference_resolution` records bindings;
`original_message` and `resolved_query` keep the interpretation inspectable.

`needs_clarification`, `clarification.slot`, and `status` tell the application when
to ask another question. Criteria and user-supplied sources are separate from
verified world facts. Quotes use `answer_status="evidence_quote"`; replacement
ranking text does not inherit the prior answer's successful audit verdict.
An early clarification returns `answer=None` with no retrieved passages.

## Verification and remaining work

The latest selected database-independent run passed **327 tests**, with eight
database-dependent/mixed test files excluded and one database test deselected.
The package built successfully. Coreferee 1.5.0 with English spaCy model 3.8.0
passed real CPU smoke examples for `it`, `them`, `its`, `she`, and "that lobster",
plus ambiguity and user confirmation. Models were installed only under ignored
`build/coreference-deps` for these tests. This is not a broad accuracy benchmark.

Live PostgreSQL integration, real Fastcoref inference, CPU latency/memory studies,
channel calibration/training, unrestricted paraphrases, source-text coreference,
general comparison and inference, predictions, and broad sentence construction
remain unverified or open. No test result establishes that the library never
returns an incorrect answer. Progress and examples stay in the support backlog.

## Detailed designs

- [Connections and six-channel assessments](knowledge-graph.md)
- [Dictionary-assisted paraphrases](dictionary-assisted-paraphrases.md)
- [Missing-attribute retrieval and joins](attribute-directed-retrieval.md)
- [Ranking clarification loops](clarification-loops.md)
- [Reference resolution setup and limits](reference-resolution.md)
- [Coreference library research](coreference-options.md)
- [Scenario backlog](intent-support-backlog.md)
- [Integration contract](library-consumer-guide.md)
