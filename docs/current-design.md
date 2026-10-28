# Current cpu-llm design

Working-tree design snapshot, 2026-10-27. This describes the implementation in
this checkout. A published package may be older. Earlier versioned
specifications and the white paper describe historical stages.

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

After retrieval and final judgment, an insufficient-evidence result can enter
the bounded [post-retrieval repair/confirmation loop](post-retrieval-repair.md).
Clear slots stay missing-fact outcomes; a broad definition with evidence for a
different supported relation offers explicit interpretations for user confirmation.
It never silently converts an action into a definition or occupation.

Definition questions require a supported definition/type/role construction.
An event mentioning the subject does not satisfy that request: `Mary baked a
cake.` cannot answer `What is Mary?` or `Who is Mary?`. A source-backed role
such as `Mary is a harbor archivist.` can answer. Present/past question tense
still applies. Unrecognized definition forms abstain rather than falling back
to arbitrary sentences about the subject, even if those sentences passed audit.

An explicit compound prompt first receives a bounded [request plan](request-separation.md).
Each separated task runs the lifecycle below with the same caller scope/history
and an independent query. The parent retains per-task outcomes and pauses on
clarification rather than blending all questions into one retrieval embedding.

1. Authenticate/resolve the caller and enforce source scope. Empty authorization
   refuses the request before conversational state is used. Guard the raw prompt
   before any conversational or source-derived clarification; guard the resolved
   prompt again before retrieval.
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
   article/tag matches, sense-specific resonance tags, and a bounded authorized
   graph neighborhood. Prioritize the requested relationship, entity, and
   direction when ranking candidates. A resonance tag is a candidate passage,
   not an answer. Resonance tags are off unless `resonance_tags=True`. When they
   are on, a sense question is asked only when stored classes name two referents
   or the question never names one. Several facts about one entity, including
   color, engine, place, and departure, are not several meanings. Cluster size
   is not a meaning. Without a session id the question is returned but no
   pending follow-up is stored. Channel prototype scores route; they do not
   prove the relationship.
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
same explicit `session_id`. A short criterion such as "how it tastes" or
"by price" continues the pending ranking. A numbered or worded sense choice
continues a pending sense question. A new question, including one with
`?`, abandons it and says so with `clarification_abandoned`. The library
returns loop state; it does not send messages or run a background conversation
by itself.

## Six-channel representation

Response depth is a separate request-local classification, exposed as
`response_plan`. Explicit brief/detailed overviews and sentence/item limits guide
bounded retrieval and source-backed summary/list selection. This presentation
budget does not truncate required factual proof or imply complete topic coverage.
See [response-depth classification](response-depth.md) for defaults and limits.

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
of indexed graph scalability. A source prefix matches only its own paragraph
ids, `prefix` plus at least four digits and an optional `-v` correction suffix.
Replacement ingestion, correction, and deletion maintain current facts. Historical queries bypass current-graph expansion.
Correction rows use the editor-supplied valid-from timestamp. Current vector
search applies time filtering even on a newly opened index; it does not depend
on whether that process performed a correction. Model01 pair storage honors
`VECTORPRISM_PG_DSN` as well as an explicit DSN.
Current-only article, word-tag, and resonance-tag expansion is also skipped for
historical queries. Resonance tags live in the namespace's `resonance_tags.db`.
Ingest, replacement, correction, and deletion keep that file aligned with the
source. A tag whose only overlap with the question is a hub word is not added.
`word_tags.json` remains. Resonance-tag expansion is off unless
`resonance_tags=True`.
For scoped or historical turns, legacy deep-search, comparison, summary, creative,
and lexical fallback paths are limited to the current turn's filtered retrieval
evidence. They cannot use global/current lookups or a prior caller's shortlist.
This conservative restriction reduces expansion coverage until those older APIs
have explicit source and temporal filtering.

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
Aliases have a strict two-hop identity bound independent of source order. Explicit
class aliases can support the membership-to-rule join. Identity-binding premises
are returned in `supporting_evidence`; class-alias and membership premises remain
with the applicable rule evidence. Direct color/lifespan values cannot silently
hide conflicting applicable universal rules.

## Conversation state and optional models

Clarification and reference state are keyed by tenant, caller, source scope,
session ID, and historical timestamp. Without a session ID, pending context is
not shared between calls. Each store caps state at 256 sessions, expires it after
30 minutes, and bounds questioning to three attempts per stage. State is local
to the process and is not durable. Callers should serialize turns within a session.
`cancel` and `start over` clear both stores, even when a ranking clarification
would otherwise return before the reference stage.

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

## Delivery judgment

`judgment` (`channel-evidence-judgment-v1`) is the delivery decision. It records
the requested entity, relationship, and direction; which channels were active
because the question form said so and which heads were enabled; the outcome;
reason codes; accepted evidence spans; and supporting proof edges. Outcomes are
`answered`, `evidence_quote`, `clarification`, `insufficient_evidence`,
`conflicting`, `unsupported`, and `blocked`. Prototype scores are copied only
as uncalibrated routing signals.

The same decision is attached before an early sense clarification and again
after ranking quotes, realization, and other `ask()` replacements. Reply
rendering does not get a second vote. A delivered claim must be the same
sentence as a licensed one, including polarity. A negation, an added clause,
or a sentence about a different entity is withheld
(`final_text_not_in_evidence` or `selector_rejected`). A claim inserted before
or after the licensed body is removed (`prefixed_text_removed`,
`appended_text_removed`) and the licensed body stays. A recognized request
with no matching evidence does not keep an earlier answer about another
entity. A conflict is the public reply: `answer` is empty, the status is
`conflicting`, and both source sentences stay visible as disagreement. A
summary, math result, or other specialist reply is checked against the text
that producer returned. A later sentence that is not in that proof is removed,
and a replaced number or sentence is put back to the producer text. `shine_final`
is the grounding record for the claims actually delivered. It is not the
earlier grounding node's metadata. That earlier acceptance is reused only when
those delivered claims are the licensed sentences. A Shine hold clears
`reply.text`, `reply.body`, `supported_text`, and nested evidence together.
The rejected wording is kept only on `rejected_candidate`. An empty-retrieval
abstention keeps its abstention sentence and is not checked again.

A because-sentence answers only the effect it states. The same sentence does
not answer a different subject or a different action. When, a bare count, and
an explicit comparison stay the fixed unsupported sentence.

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
Ranking follow-ups keep top-level `answer_status`, `answer_evidence`, and
`verification_scope` consistent with the replacement reply. Partial execution,
node errors, and grammar/guard/delivery holds cannot be replaced by a ranking
quote or clarification. Reference confirmation updates both the retrieval query
and ranking topic; a later typo correction preserves the actual original input.

## Verification and remaining work

The full join/response review passed **420 tests**, with two optional extraction
checkpoint tests skipped and no tests deselected or test files excluded. This
supersedes the earlier 356-test selection and its unavailable-database limitation.
The run used an isolated PostgreSQL 18.1/pgvector database, a fresh working
directory, Python 3.12.10, cached CPU model assets, disabled pytest plugin autoload,
and offline model-download settings. Live join tests were explicitly enabled.
Tests cover independent SQLite join-oracle comparisons, full Appliance joins,
authorization of both premises, source replacement/deletion, correction history,
reopening the vector index, conversation loops, and legacy pipeline integration.
The four-case retrieval lab recorded hit-rate@5 and spoken attribution of 1.0;
this is a tiny diagnostic corpus, not a general accuracy estimate.
The [validation record](reviews/2026-10-25/join-review.md) links the full transcript,
records the fixture/contract changes, and distinguishes remaining numerical
warnings from failures. The [response cases](response-cases.md) enumerate supported
examples, rejected joins, and open scenarios.
The reviewed source built successfully as a wheel and source distribution.
Earlier Coreferee 1.5.0 with English spaCy model 3.8.0
passed real CPU smoke examples for `it`, `them`, `its`, `she`, and "that lobster",
plus ambiguity and user confirmation. Models were installed only under ignored
`build/coreference-deps` for these tests. This is not a broad accuracy benchmark.

Real Fastcoref inference, CPU latency/memory studies,
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
- [Response cases and join contract](response-cases.md)
- [Integration contract](library-consumer-guide.md)
