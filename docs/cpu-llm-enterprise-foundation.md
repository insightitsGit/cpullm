# cpu-llm design: enterprise foundation

**ID:** DES-cpullm-004  
**Status:** Phase 1 is implemented in this tree. Phases 2–5 are specified here and are not built.  
**Package:** 1.7.1 until a release is cut. This document is the design version, not a PyPI version.  
**Baseline:** `fdb4d78` on `main`, plus the uncommitted source delete, cued category list, uncovered-decision reply, and typo pass if those are still only in the working tree.  
**Source handoff:** [HO-cpullm-003](handoff-enterprise-gaps.md)  
**Author:** Amin Parva (AI Architect & Staff Applied AI Engineer)

cpu-llm is one CPU process that answers from stored text. The spoken result is a checked sentence, a rule verdict, an event frame, a calculation, or a document filled with retrieved sentences. Multi-tenant use is a boundary around that process. It does not change the reasoning path, the realizer, or the auditor.

This document is the implementation contract. HO-cpullm-003 states the problems. DES-cpullm-003, the second write-up reviewed on 18 October 2026, is not an implementation spec.

---

## Order

| Phase | Scope | Done when |
| --- | --- | --- |
| 1 | Tenant isolation, access control, authenticated entry, operations | Customer A's evidence cannot reach Customer B's execution or outputs |
| 2 | Corrections | A new version is stored. The old wording remains. |
| 3 | Retrieval evaluation | Recall and attribution are measured on a labeled corpus. No pass-bar is chosen before that run. |
| 4 | Memory stages 2–4 | More questions can be answered from spans. No fabricated proposition or relation. |
| 5 | Concurrent asks | Seats follow the six-process engine rule. |

Operations are part of Phase 1. Phases 2–5 are specified here so they are not redesigned while Phase 1 is built. Their code waits until the Phase 1 gate passes.

---

## Three decisions

### 1. The request carries identity

Every request carries:

| Field | Meaning |
| --- | --- |
| `tenant_id` | The slug from `_namespace_slug`, or `cpu-llm` when the caller omits a namespace |
| `caller_id` | Who is asking |
| `allowed_sources` | Source prefixes or document ids this caller may read. Empty means this caller may read nothing |
| `request_id` | One id for this turn, copied onto diagnostics |

That context is what PostgreSQL, the graph store, PrismRAG, the format-sense cache, the typo vocabulary, and every intermediate artifact use. A Postgres schema on its own is not isolation. The graph today is still opened with `tenant_id="cpu-llm"` even when `namespace` is set.

### 2. Authorization happens before ranking

A passage outside `allowed_sources` is removed before the dense-core order is cut to `top_k`. The same rule applies to deep search, which keeps every reached paragraph that clears its floor. Dropping forbidden rows after a shortlist of five is a failed test: a forbidden row at rank 1 must not push an allowed row out of the five.

`RetrievalEngine.search` (`vectorprism` 0.1.3) accepts the 1024-d query, the query text, `top_k`, and optional `as_of` / `as_of_transaction`. `query_dense_slice` can restrict epistemic truth, anchor distance, model version, and those two timestamps. Neither call accepts a list of document ids. Phase 1 adds that predicate in this repository's query, using the same dense-core order and HNSW settings. The implementation records that the installed search does not take the predicate. It does not call `search(top_k=5)` and drop rows afterward, and it does not describe a larger `top_k` followed by a drop as the same guarantee.

### 3. A correction is a new version

Phase 2 appends the new wording. The old node stays. The new sentence is spoken only when the realizer can repeat it. A sentence that does not round-trip stays text and receives no proposition.

A live question reads the version that is valid now. A past version is read only when the caller passes `as_of` and is allowed to. Two live wordings of the same claim stay `CONTESTED`. The parking-van case stays `CONTESTED`.

PrismCortex nodes have no `valid_from` or `valid_to`. Those times, if stored on a node, are attributes this application writes. `Operation.ACCOMMODATE` sets `valid_to` on an existing edge and inserts another edge. It does not retire a node. `Operation.PRUNE` does not delete a node. The supersession link is an edge from the new node to the old node. When no earlier edge exists, the new edge is assimilated. `ACCOMMODATE` is used when an edge is the object being replaced.

Vector rows use the columns the installed query already reads: `valid_timestamp` and `valid_to_timestamp`. `query_dense_slice` applies them when `as_of` is set. A separate `is_active` flag is not added, because that query would not see it and the old wording would stay in the shortlist.

---

## Invariants

These stay as they are while every phase is built.

* One CPU process. No GPU decoder, no cloud chat client, no GGUF runtime, no unconstrained next-token sampler.
* `EpistemicEntailmentAuditor` and the PrismManifest numeric span checks stay as they are.
* `Modality` stays declarative, obligative, permissive, probabilistic, and counterfactual. `POSSIBLE` and `CONJECTURAL` are not added.
* In `_compile`, think connects directly to cognize. Imagine stays on the optional-agent path after Shine.
* No proposition is synthesized from a `{category}:{term}` tag. No neural coreference, spaCy, or coreferee. No bilinear relation operator. The relational, disentangled, hyperbolic, and causal heads do not pick a passage and do not bind an entity across sentences. Only the trained dense core `[16:384]` picks the passage.
* Installed `vectorprism`, `prismcortex`, and `chorusgraph` are not patched. Extensions live in this repository.
* Child safety and fact-bridge `verify()` stay off the answering path.
* Discovery runs only when the caller passes `discover=True`.
* Typo correction runs before `encode_query`. Candidates are that tenant's stored words. The score is character-pair and character-triple cosine, floor 0.45, gap 0.05. A word already in that vocabulary is left as written. The retrieval encoder's cosine is not the spelling score.
* A document body is retrieved sentences. A missing field stays unfilled.
* A refusal is a sentence the appliance already speaks. `answer is None` is not the security check. The check is that Customer A's tokens are absent from Customer B's reply, preface, draft, and diagnostics.
* No latency, size, timeout, retention period, or recall bar is written down unless a named machine produced it and the command is recorded. The only question times on record are the 13 October 2026 table in the README.

---

## Phase 1

### Tenant

`_namespace_slug` remains the normalizer: lowercase, characters outside `[a-z0-9_]` become `_`, length at most 48. A namespace that becomes empty raises `ValueError`. The default, when the caller passes no namespace, remains the string `cpu-llm`.

The default tenant keeps the directory `.chorusgraph/cpu-llm/` and the file `graph_store.db` inside it. A named namespace keeps the directory `.chorusgraph/cpu-llm/<slug>/`, which `Appliance` already creates. What changes is the identity stored inside that directory:

* `SqliteGraphStore` is opened with `tenant_id=<slug>` (or `cpu-llm` for the default).
* The turn state sets `tenant_id` to that same slug.
* `_compile` builds `Graph(tenant_id=<slug>, graph_id=f"appliance_{slug}")`.
* `PrismRAG` is constructed with the keyword `tenant_id=<slug>`. The parameter name is `tenant_id`. Omitting it mints a random id, so the call always passes the slug. The object in `word_taxonomy.py` uses an in-memory store. The file that must not be shared is `word_tags.json` in that tenant's directory.
* `format_sense_cache` rows stay keyed by `(tenant_id, message_key)` using this slug.
* Format node ids stay `output-format:{id}`. They are the shared layout catalog, installed into that tenant's store. They are not renamed.

PostgreSQL keeps `_namespace_dsn`: schema `ns_<slug>`, `search_path` `ns_<slug>, public`. A missing schema is created by that function today. An explicit request for a tenant whose schema cannot be opened raises before `encode_query`. The default tenant stays on the current DSN and the `public` search path.

The typo cache in `typos.py` is keyed by the tenant as well as the word-index object. A second tenant's words are not candidates.

### Access

`allowed_sources` is a set of source prefixes or document ids. The Phase 1 query adds a predicate on `document_id` before the dense-core ordering and the limit. Deep search applies the same predicate to every reached paragraph before the possibility list is kept.

When the caller may read nothing, or every candidate falls outside `allowed_sources`, the shortlist is empty. The spoken line is one the appliance already uses for an empty retrieval (`No passage was retrieved.`) or for an uncovered decision (`The retrieved passages do not settle that.`). The result may also carry a typed error for the caller. The spoken line, the preface, `gather_questions`, and any draft contain no forbidden token, document id, or title.

### Authenticated entry

A local entry in this repository wraps `ingest`, `ask`, and `delete_source`. It is not a separate service. A credential maps to `tenant_id`, `caller_id`, and `allowed_sources`. Comparison of the secret uses `hmac.compare_digest`. A failed credential raises before typo correction and before `encode_query`.

Where the secret is stored is chosen at implementation from a file this process can read. The design does not add a new hash algorithm or a key format beyond that constant-time check.

### Operations in this phase

Chunks and vectors remain until `delete_source`. That call deletes `psm_document_embeddings` rows for the source prefix, graph nodes whose ids start with the prefix, and those document ids in the word index. The resonance ledger and `word_relations.json` are left in place. Docs and the return value say so.

Postgres down, a schema that cannot be opened, and a failed credential are typed errors. A traceback is not the caller-facing body.

### Phase 1 gate

All six are required before Phase 2 starts. Each private token is distinctive and is checked in the reply, the preface, the draft, and the diagnostics.

1. Text ingested as tenant A never appears in tenant B's outputs.
2. A forbidden document at dense rank 1 does not remove an allowed document from the five.
3. An unknown tenant, a bad credential, and an empty `allowed_sources` stop before retrieval.
4. Typo correction for tenant A does not rewrite from tenant B's words.
5. The graph, PrismRAG, and the format-sense cache for A are unchanged by a turn that runs as B.
6. One process runs A, then B, then A again, including a failed credential and a turn that is interrupted. The second A sees only A's words and A's passages.

Existing single-tenant refusals, numeric grounding, and the auditor stay as they are on a caller who passes no namespace.

---

## Phase 2

`Appliance.correct` takes `document_id`, `prior_sentence`, `new_sentence`, `actor_id`, and a timestamp. `new_sentence` is stored as a proposition only when the realizer repeats it. Otherwise the correction is refused.

The old graph node remains. The new wording is a new node. An edge records that the new node supersedes the old one, with the actor and the timestamp in the edge attributes. The new vector row is inserted under a versioned document id. The old row's `valid_to_timestamp` is set to that timestamp. A question without `as_of` reads rows whose validity interval contains now, using the same `as_of` path `query_dense_slice` already has. A question with `as_of` reads the interval that contains that time, and only if this caller may read that source.

---

## Phase 3

The 102/104 figure is a wording score with the passages handed in. It is not retrieval recall.

The labeled set is, for each question: the question, the relevant document ids, and distractor ids that share words or a nearby vector and do not state the answer. Two counts are recorded, with the commit, the machine, and the command:

* The fraction of questions for which at least one relevant id is in the five. That is hit-rate at 5. It is not the set-overlap formula that divides by the number of relevant ids.
* The fraction of questions whose spoken sentence was realized from a proposition whose document id is relevant. A sentence realized from a distractor counts as a miss.

Docker on port 5433 and `python -m pytest tests/test_pipeline.py tests/test_upload.py --tb=short` are the regression for the appliance. They are not this measurement. No pass threshold is written in the README from this design.

---

## Phase 4

Stage 1 in `memory/frames.py` stays the who, where, and color grammar. Its refusal sentences stay, including `No stored sentence states that color in 2018.`

Stage 2 puts negation and a condition on the span. A question whose polarity matches that span speaks the span. A positive question against a negative span, or a condition the question does not meet, uses an existing refusal. The negated span is not rewritten as a permission.

Stage 3 gives one entity id to two mentions only when the surface string is the same, or the text itself states the alias. A `{category}:{term}` tag is not an alias. A pronoun with more than one possible antecedent stays unbound. No edge is created because two vectors are close.

Stage 4 reads a role only from a span that was cut from a round-tripped sentence. If retrieval did not return that sentence, the reply says no stored sentence states that role. It does not walk a new relation edge invented from the prose.

---

## Phase 5

One engine is the engine process plus five thinker heads, six processes. `WarmEvaluatorPool` keeps its lock for one turn on that seat. A second seat is started on this machine only when `cpu_count >= engines * 6`, which is `_place` in `scale.py`. When `_place` returns `other_server`, the turn waits for a free local seat or the result reports `other_server`. The wait does not mean a second machine was started, and it does not share the locked pool.

The ChorusSpine frame keeps the 64-wide slot. It carries the request id, the tenant, the caller scope, and the chunk ids for that turn. Deep search sends every kept id. The 1024-d tensor is not copied into the frame. A seat that dies returns a typed error for that `request_id` and is started again. No timeout duration is chosen in this document.

---

## Closed

These were proposed and are not part of the build.

* A path `.chorusgraph/<tenant>/<tenant>.db` that abandons `.chorusgraph/cpu-llm/`.
* A slug pattern that allows hyphens, in place of `_namespace_slug`.
* Format ids prefixed with the tenant.
* `PrismRAG(..., tenant=...)`.
* Filtering a finished top five, or a larger top-k, and calling that authorization before rank.
* An `is_active` column the dense query does not read.
* A new spoken refusal such as "the system does not possess sufficient verified evidence."
* Binding "the species" or a pronoun through a taxonomy tag or the hyperbolic head.
* Treating `{category}:{term}` as a proposition or as coreference.
* A spine frame limited to five chunk ids.
* A worker count of `floor(cpu_count / 2)`.
* Recall, latency, memory, connection, or retention numbers that were not measured on a named machine.
