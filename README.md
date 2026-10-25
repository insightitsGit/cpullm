# cpu-llm

**A local, CPU-based library for answering questions from your documents and explicit rules.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-orange)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-insightitsGit%2Fcpullm-181717?logo=github)](https://github.com/insightitsGit/cpullm)

cpu-llm is an embeddable Python library for document question answering. It indexes paragraphs in PostgreSQL/pgvector, retrieves relevant passages using VectorPrism, and produces supported answers, source quotations, or explicit nonanswers for recognized question forms. It combines trained embedding retrieval with deterministic sentence constructions, limited event-role extraction, pattern-based policy reasoning, arithmetic, and document layouts. It also includes supplied-field finance checks and an authenticated HTTP entry point.

**Author:** [Amin Parva](mailto:parvaamin@gmail.com). **Package version:** 1.9.1. PyPI `1.9.0` is an earlier upload and does not include the one-sentence reply selection or the ban and upper-limit reading. This checkout is 1.9.1. The [targeted review](docs/reviews/2026-10-19/review-9d6fbe8.md) of commit [`9d6fbe8`](https://github.com/insightitsGit/cpullm/commit/9d6fbe8fabcf9dac10ec6cc409fa7852f77e948d) covers an earlier snapshot. Installing `cpu-llm==1.8.0` or `cpu-llm==1.9.0` does not include this reply and rule-reading behavior.

**Correctness boundary:** source copying and component checks do not guarantee source truth or that every displayed sentence answers the question. `answer`, `reply["text"]`, and component-specific verification fields have different meanings. Recognized query shapes expose answerability outcomes; other requests can use different producers or fallback behavior. Evaluate the actual reply and its supporting evidence for your application. The [latest targeted review](docs/reviews/2026-10-19/review-9d6fbe8.md) and [executed audit](docs/reviews/2026-10-19/audit.md) distinguish tested behavior, historical failures, and limits.

For an agent integrating the library, start with [the consumer guide](docs/library-consumer-guide.md): complete `ask` arguments, result interpretation, credentials, HTTP contracts, and operational limitations.

## New in this checkout

The [current design](docs/current-design.md) describes the implementation as of October 25, including changes not yet committed or released. The package version alone does not establish that an installed PyPI distribution includes these changes.

- **Explicit connections and intent:** ingestion saves source-backed facts and channel memberships in a namespace-local knowledge graph. Recognized prompts prioritize the requested entity, relationship, and direction when selecting evidence. Multiple channels can apply to one connection.
- **Dictionary-assisted questions:** a small, inspectable lexicon recognizes supported synonyms and equivalent expressions. It preserves the original question and can retrieve with one canonical variant. Antonyms remain distinct; this is not a complete dictionary or arbitrary semantic understanding.
- **Missing-attribute retrieval:** for supported lifespan, location, color, and possession questions, a bounded retry searches the entity and verified connected types. A type membership plus an explicit universal rule can support a limited join; a class average or a statement about some members cannot establish an individual fact.
- **Clarification loops:** a question such as “Which lobster is best?” asks for the user's criterion. Follow-ups retain that criterion and request comparison evidence when it is missing. The library does not invent a winner from retrieval scores.
- **Optional reference resolution:** a CPU Coreferee adapter can bind supported uses of “it,” “them,” possessives, and demonstratives to prior user context. Ambiguous or unresolved references ask for clarification. A FastCoref adapter is also implemented, but its real model has not been validated here.

The six semantic channels are dense, relational, disentangled, hyperbolic/taxonomy, identity, and causal/time. The shipped VectorPrism checkpoint enables **dense and identity**; symbolic associations in the other channels do not mean those projection heads are trained and enabled. Epistemic source support is separate metadata. Exact fact connections are stored alongside the vectors, not recoverable as a complete word network from vector coordinates. Reingest existing sources to populate the new fact graph.

These additions select evidence and support bounded sentence constructions. They do not provide unrestricted sentence generation or establish missing facts. See the [supported-use-case backlog](docs/intent-support-backlog.md) for remaining gaps.

## Where it can be useful

The intended use is a document assistant inside another application: for example, looking up facts in a manual, answering supported questions about an internal policy, or preparing a structured summary from stored passages. Local CPU execution and explicit source records can be useful when the developer wants to keep the runtime and indexed documents under their control.

This is a candidate for a **bounded, human-supervised pilot**. Industry usefulness, customer time savings, and production reliability have not been established by the repository tests. Before deployment, evaluate real documents and independently written questions, including missing facts and conflicting sources, against your existing search workflow. Broad conversation, arbitrary language understanding, and a trained general-purpose sentence generator are outside the demonstrated scope.

## Requirements and installation

- Python 3.11 or newer and a 64-bit CPU.
- PostgreSQL with the `vector` extension; the documented development configuration uses PostgreSQL 16.
- The frozen `sentence-transformers/all-mpnet-base-v2` encoder. First use may download model assets; subsequent offline use requires those assets already cached.
- Writable local storage for `.chorusgraph/cpu-llm/` under the process's **current working directory**, in addition to the PostgreSQL data.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
```

Run these commands from a checkout of this repository to use the features documented here. This source identifies itself as 1.9.1; published packages can describe an earlier implementation.

The pins in [pyproject.toml](pyproject.toml) are authoritative. The editable install makes packaged retrieval assets and sample corpora available; it does **not** start PostgreSQL, populate its corpus, or train a realizer. It does not bundle the optional fact-bridge T5 checkpoints or declare all their optional runtime dependencies.

A disposable development database can be started with Docker:

```powershell
docker run -d --name cpullm-pgvector -p 127.0.0.1:5433:5432 -e POSTGRES_USER=vectorprism -e POSTGRES_PASSWORD=vectorprism -e POSTGRES_DB=vectorprism pgvector/pgvector:pg16
```

If that container already exists, use `docker start cpullm-pgvector`. These are development credentials. The default DSN is:

```text
postgresql://vectorprism:vectorprism@localhost:5433/vectorprism
```

Set `VECTORPRISM_PG_DSN` or pass `Appliance(dsn=...)` to select another database. Namespace initialization needs permission to create a schema/table; extension setup also requires suitable PostgreSQL privileges. Missing database connectivity prevents constructing an `Appliance`.

The code runs the encoder/retrieval on CPU and clears `CUDA_VISIBLE_DEVICES`; its CPU guard refuses a process in which an already imported PyTorch reports CUDA available. On Windows, the retrieval module imports `pyarrow` before the torch-dependent stack to avoid the observed import-order fault.

## Quick start: ingest before asking

```python
from cpu_llm.documents import SourceDocument
from cpu_llm.pipeline import Appliance

def main():
    with Appliance(namespace="demo") as app:
        receipt = app.ingest(SourceDocument(
            "field-guide",
            (
                "The harbor kestrel is a small coastal falcon.",
                "The harbor kestrel nests in coastal cliffs.",
                "John ate a yellow apple in his house.",
            ),
        ))
        print(receipt["ids"])

        result = app.ask("Where does the harbor kestrel nest?")
        print((result.get("reply") or {}).get("text", ""))
        print(result.get("answer_status"))
        print(result.get("answer_evidence"))

        frame = app.ask("What color was the apple John ate?")
        print((frame.get("reply") or {}).get("text", ""))
        print(frame.get("frame_result"))


if __name__ == "__main__":
    main()
```

Save the example as a Python file and run it with PostgreSQL available. Keep appliance construction inside the guarded `main()` entry point when running scripts on Windows: the Thinker pool starts child processes. Use a context manager, or call `close()`, to release workers. Reuse an appliance rather than loading the encoder and worker pool for each question. A named namespace starts with its own vector table; it does not inherit the default tenant's indexed passages. Use a namespace dedicated to your example data.

The nesting query can return `answer_status="evidence_quote"`: the displayed text is a cited source passage, while `answer` is cleared. The apple-color question uses the separate frame result. Keep those response types distinct when integrating.

## Follow-up questions and clarification

Pass the same explicit `session_id` on related turns. Your application displays the returned question and sends the user's response back through `ask`; the library does not contact the user itself.

```python
# Inside the existing Appliance context:
result = app.ask("Which lobster is best?", session_id="chat-1")
print((result.get("reply") or {}).get("text", ""))
print(result.get("needs_clarification"))

# After the user supplies a criterion:
result = app.ask("taste", session_id="chat-1")
print((result.get("reply") or {}).get("text", ""))
```

The first turn asks what “best” means and what it is for. The next turn uses the supplied criterion; without an explicit supporting ranking, it asks for comparison evidence. User-provided `Source: ...` follow-ups remain attributed, unverified statements and are not permanently ingested as facts.

Reference resolution is disabled by default. To enable the tested optional backend, install its dependencies and model assets explicitly:

```powershell
python -m pip install -e ".[coreference]"
python -m spacy download en_core_web_sm
python -m coreferee install en
```

Construct the appliance with `reference_backend="coreferee"` inside the guarded `main()` shown above. After ingesting relevant documents, related calls can use:

```python
app.ask("Tell me about the European lobster.", session_id="chat-2")
result = app.ask("Where does it live?", session_id="chat-2")
print(result.get("resolved_query"))
print(result.get("reference_resolution"))
```

Resolving “it” identifies the requested entity; the answer still requires authorized source evidence. Multiple plausible antecedents trigger a question. Without a backend, unresolved references request an explicit name. Session state is in memory, scoped by tenant/caller/source scope/session/history date, expires after 30 minutes, and is capped at 256 sessions per state store. Restarting loses it; omitting `session_id` does not enable cross-call context. See [reference resolution](docs/reference-resolution.md) and [clarification loops](docs/clarification-loops.md) for setup, cancellation, budgets, and limits.

Sample corpora ship as files and must be ingested. The CLI loads the **default tenant**, not `namespace="demo"`:

```powershell
cpu-llm-ingest              # WikiText validation, AI primer, finance primer
cpu-llm-ingest --textbook   # AI primer only
cpu-llm-ingest --finance    # finance primer only
cpu-llm-ingest --test       # WikiText test split only
```

The same entry point is `python -m cpu_llm.ingest`. If multiple flags are supplied, the implementation prioritizes `--test`, then `--textbook`, then `--finance`; use one flag at a time.

## Inputs, IDs, and lifecycle

`ingest` accepts a file, a directory, a `SourceDocument`, or an iterable of those. Readers support `.txt`, `.md`, `.markdown`, `.html`, `.htm`, `.pdf`, `.docx`, `.csv`, `.xlsx`, `.xlsm`, and `.epub`. These readers extract existing text; this API does not provide an OCR pipeline for scanned PDFs. Legacy `.doc` and `.xls` are unsupported.

```python
with Appliance(namespace="demo") as app:
    receipt = app.ingest("notes/harbor-field-guide.pdf")
    # The path must exist on the machine running the library.
    print(receipt)  # documents, chunks, ids, connections
```

File IDs use a normalized name/stem and a paragraph number, for example `harbor-field-guide-p0001`. Retain `receipt["ids"]`; do not guess identifiers for later authorization or correction. Different files with the same normalized stem can collide within a tenant. A spreadsheet with source/target-style columns contributes text and explicit word connections; other rows become column/value text.

Reingesting a source replaces vector rows sharing its source prefix. Ingestion also updates local graph/word metadata, but it is not a general versioned transaction across every store. `delete_source("field-guide")` deletes that whole source prefix, even when supplied a paragraph ID. It returns vector/graph/word-index counts and any `nodes_remaining`. It leaves resonance and the word-relations file unchanged; it is not a complete erasure receipt for every derived artifact.

`correct(document_id, prior_sentence, new_sentence, actor_id=..., timestamp=...)` is a separate version/supersession operation. It retains the old graph node and closes an old vector validity interval. Replacement text must round-trip. See the [consumer guide](docs/library-consumer-guide.md#corrections-and-history) for the history contract and limits.

## Available behaviors

- **Document questions:** retrieve paragraphs and deliberate over supported stored propositions. Recognized definition, named-attribute, present-action/location, and weight questions bind to supporting sentences or report insufficient/conflicting evidence. Examples include `What is the harbor kestrel?`, `What is the capital of France?`, `Where does the harbor kestrel nest?`, and `How much does the harbor kestrel weigh?`. The proposition extractor considers a paragraph's first sentence; other text can still be retrieved or quoted. These are narrow English grammars, not arbitrary question answering.
- **Event questions:** supported color, location, and agent forms, such as `What color was the apple John ate?`, `Where did John eat the apple?`, and `Who ate the apple?`. Dates and tense constrain matching. Limited negative/conditional frame forms and paragraph-local alias helpers also exist; this is not general semantic parsing or arbitrary coreference. The query frame node operates on the retrieved passages, not an exhaustive role-index search.
- **Rule answers:** return `YES`, `NO`, `CONTESTED`, `UNKNOWN`, `CAUSE`, or `NONE` under `reply.situation`. The pattern reader distinguishes asked permission, obligation, and prohibition, and compares a stored measurement with a numeric condition. A sufficient allowance alone leaves cases outside its condition unknown. Missing measurements also produce UNKNOWN. When that reader returns `NONE`, a permission question (`can`, `may`, `could`, or `am I allowed`) can still use two stored wordings. A ban that shares a topic word with the question (`may not`, `must not`, `cannot`, `not allowed`, `prohibited`, `forbidden`, and the same family) is quoted as `NO`. A question that names a quantity is compared with a stored upper limit in the same unit (`up to`, `no more than`, `at most`, `a maximum of`, `may not exceed`): within the limit is `YES`, above it is `NO`, and the source sentence is quoted. A different unit is not converted on that path, and a ban about a different subject stays `NONE`. Category matching, conflict handling, and background-memory assumptions remain limited; evaluate the source sentences before using a verdict in a decision.
- **Summary/explanation/list/sources:** optional brief output over stored sentences. When one of these is requested, the checked sentence stays and the section is appended. Model01 does not replace that sentence. An empty summary, explanation, or list says so in that section. Explanations look for stated causes. Comparisons present per-topic evidence; they do not establish a new comparative judgment.
- **Deep search:** expands candidate paragraphs using lexical tags/relation hands. `deep_min_similarity` defaults to `0.62`; setting it to `None` removes that additional dense-similarity floor. A shortlist is not proof that all relevant evidence or contradictions were found.
- **Creative mode:** selects varying subsets of stored sentences. The same prompt can yield different passages; this feature is not deterministic across runs.
- **Math:** evaluates supported arithmetic in a separate agent. A computed value is not a retrieved proposition.
- **Document layouts:** 31 built-in formats, including email, report, checklist, essay, and FAQ. A named format/topic can replace the main reply with copied topic-related sentences. This is text layout, not DOCX/PDF export or unrestricted prose generation. Missing roles should remain unfilled; topic-to-header binding has known limitations.
- **Finance checks:** local RefundProof, LedgerCovenant, and Ledgerlock routines consume supplied fields. They do not fetch financial records or perform external writes.

The supported grammar and explicit non-answer statuses are part of the interface. A name or possessive in a sentence does not establish arbitrary identity, ownership, or causality.

## How a question moves

```text
guard
  → retrieve → resonate → six channel readings → catalog → detail → spans
  → think → cognize → grammar → Shine
  → deep search, gather, imagine, compare, brief, math, finance, event frame
  → Model01
  → reply
```

This diagram summarizes the older core pipeline. The current request lifecycle also applies clarification, optional reference resolution, dictionary interpretation, intent routing, source-backed graph expansion, and bounded attribute retrieval repair; see the [current lifecycle](docs/current-design.md#request-lifecycle).

PrismGuard can stop the turn before retrieval. Dense similarity supplies the trained retrieval core. Channel assessments and symbolic facts help prioritize supported intent and graph evidence; disabled projection heads are excluded from vector scoring. Think, cognize, the grammar, and Shine then check the stored proposition. Cognize rebuilds a sentence from subject, verb, and object; the auditor has to accept that rebuild.

Specialists run only when the prompt selects them, in the order above. Gather loads the article's paragraphs for an imagined passage. Math evaluates the expression in the question, so `17*24` is reported as `17*24 = 408.` Finance runs RefundProof, LedgerCovenant, or Ledgerlock on the fields in the question. An event-frame question answers color, place, or agent from a stored frame. Model01 then builds licensed sentences from passages that share a content word with the prompt, or that contain a named entity as that name. A passage with no such word is not a source. If the prompt leaves no content word, Model01 receives no passages.

The reply uses the first owner that applies. Math, finance, an event frame, a document draft, and a rule verdict each replace the body. A recognized question with no binding, or with conflicting stored values, replaces the body with an explicit gap such as "The retrieved passages do not settle that." A summary, explanation, or list keeps the checked sentence and appends that section. On the remaining turns, the displayed Model01 text is one sentence: the sentence that states a ranking when one of the licensed sentences does, otherwise the first licensed sentence. A later sentence that only shares a topic word is left out. A ranking question then adds a `Ranking:` section. That section quotes the stored order, says the sentence above already states it, or says the passages do not state a ranking. When nothing was retrieved, it says no ranking is stored. Retrieval score is not that order. `model01` can still hold a longer checked text than the line the reply displays.

`Appliance.sleep()` is a separate caller-started cycle. It is not a step of `ask`. It links stored nodes that already share a taxonomy category when their relational-channel cosine is above 0.75 and PrismCognition does not call the pair a contradiction.

## Models and the meaning of deterministic

The retrieval encoder and shipped `vectorprism.pt` projection are distinct from sentence generation. Dense retrieval is trained; the other subspace readings and relation signatures are not a trained fact generator.

There are **three separate wording paths**:

1. The construction realizer associated with the v1.9 design has N0 plans/constructions/checking but **no trained ranker checkpoint**. `realization="evidence_neural"` currently reports deterministic fallback. It is opt-in, does not affect every plain reply, and is not a delivered neural graph decoder. `account=True` opts into an account of authorized records.
2. **Model01 is a deterministic construction generator**, despite its name. It runs before the reply, after enabled specialists such as math, finance, and event frames. It builds licensed sentences from retrieved records. The reply shows one of them: the sentence that states a ranking when one does, otherwise the first. A second sentence that only shares a topic word is not displayed. Entity filtering keeps a named subject on passages that contain that name. A ranking prompt adds a `Ranking:` section for a stored order, or states that none is stored. Model01 loads no trained generation checkpoint, and `checkpoint_id` stays null. `realization="model01"` is accepted, but the Model01 graph node already runs on the ordinary path; that argument does not enable a separate trained model. The package exports `prepare()` and `train()` through `cpu_llm.model01`: `prepare()` stores checker-approved records in `model01_training_pair`, marking the WikiText test split as `test`; `train()` is a training-signal survey that runs no optimizer and always reports `checkpoint_written=False`. Training stays unready while every plan has one legal sentence.
3. The fact-bridge rule path can **automatically load local FLAN-T5 extraction and writing models** when the pattern path misses, the prompt/passages have rule cues, and model directories are found. This can happen with the default `realization="deterministic"`. Model lookup checks `FACTBRIDGE_MODELS`, then `models/` and `cpullm-factbridge/models/` relative to the package installation root. An explicit root is also supported by the low-level fact-bridge API.

The latter requires external checkpoints and optional tooling such as Transformers, torch, SentencePiece, and safetensors. A missing/incompatible writer or dependency can raise during a question. The current `Appliance.ask` has no public switch that guarantees this automatic fallback is disabled; inspect deployment assets and `reply.situation.wording.path`. The learned writer currently returns a nonempty candidate without calling its verifier. Its output is not covered by the earlier `answer` audit.

Thus, “CPU-only” does not mean “no decoder,” and default mode does not guarantee every path uses only deterministic templates. This project makes no universal truth or zero-hallucination guarantee.

## Reading results correctly

Always use `.get(...)` for optional fields. Access refusals and seat failures may have a different shape from normal graph results.

- `reply.text`: the displayed output. It may be a base answer, quote, frame/non-answer, rule verdict, math result, finance result, or document layout.
- `answer`: the EIR answer/fallback, possibly narrowed or cleared by query assessment. It is cleared for `insufficient_evidence`, `conflicting`, and `evidence_quote` outcomes; it can differ from `reply.text` when a specialist or Model01 supplies the display.
- `answer_status`, `answer_evidence`, `verification_scope`: present for queries handled by the answerability layer, and also copied into `reply`. Statuses include `answered`, `evidence_quote`, `insufficient_evidence`, and `conflicting`. Scope `query` records the supported query-binding checks; scope `retrieval` identifies a quote. Neither scope proves the source itself true. These fields are not universal across all response producers.
- `__partial__`, `__node_error__`: graph-failure indicators. A failed graph can return a dictionary with no `reply`; treat this as an execution failure, not an abstention or successful answer.
- `audit_passed`: the audit of the base realized propositions; it does **not** certify the entire displayed reply, source truth, document fields, or learned rule wording.
- `shine_ok`, `shine_enforced`, `delivery_blocked`: grounding/delivery diagnostics for the checked path. Never restore a withheld candidate using a debug field.
- `frame_result.status` / `verified`, `frame_verified`: frame-specific outcomes. `answered`, `missing`, `ambiguous`, `conflicting`, `unsupported`, and sometimes `ignored` distinguish response types.
- `reply.situation`: rule verdict, delivered rule text, `because` source sentences, and wording-path metadata. Those sources can currently include synthesized background memory; do not equate them automatically with original retrieved citations.
- `reply.draft`: document format/topic/text, missing fields, and source IDs. Header provenance/binding is not a universal guarantee.
- `model01`: construction status, text, verification outcome, input records, and a null generation-checkpoint ID. Its result is not necessarily the displayed reply. `math_result`, `finance_result`, and `realization_result` likewise have their own contracts; do not apply `audit_passed` to every producer.
- `related`: retrieved items using `chunk_id`; `passages` uses `document_id`. These are paragraph IDs, not source URLs.
- `thinker_directive`, `gather_questions`: sufficiency advice. `gather`, `refuse`, or `escalate` are not themselves a guarantee that all later display is suppressed; apply a consumer policy explicitly.
- `typos`, `original_message`: actual query rewrites. The corrected query is used by later stages. `original_message` is present when a rewrite occurred.
- `needs_clarification`, `clarification`, `user_criteria`: conversational outcomes and the missing slot. Display the clarification and submit the user's reply with the same `session_id`; do not treat it as a factual answer.
- `resolved_query`, `reference_resolution`: the interpreted retrieval query and reference-binding diagnostics. A resolved name does not verify a fact about that entity.
- `attribute_search`: bounded repair queries, membership evidence, budget, and outcome when supported missing-attribute retrieval runs. A completed search can still leave evidence insufficient.

For applications that make decisions, separate the transport outcome, component status, actual wording, supporting source, and consumer approval policy. An HTTP 200 or a nonempty string is not an accepted factual result. See [result routing guidance](docs/library-consumer-guide.md#result-routing-for-an-agent).

## Tenants, authentication, and service

`Appliance(namespace="tenant_alpha")` uses a normalized namespace, PostgreSQL schema/table `ns_tenant_alpha.psm_document_embeddings`, and local files under `.chorusgraph/cpu-llm/tenant_alpha/`. The default namespace is tenant `cpu-llm`. Local paths are relative to the working directory: use a stable working directory and isolate deployments that use different DSNs.

Direct Python calls are trusted integration calls. Omitting `caller` is unscoped within the selected tenant; constructing a `CallerContext` is not authentication. For source-scoped callers use exact paragraph IDs or a source prefix ending in `-p`, such as `field-guide-p`. An empty scope permits no reads. Use the authenticated `Entry`/HTTP service when callers are not already trusted.

Scoped and historical turns limit legacy deep-search, summary, comparison, and creative expansion to this turn's filtered retrieval evidence. Historical queries also skip current-only article/tag/fact-graph expansion. This can reduce recall; `as_of` is not a transactional snapshot across all stores.

```powershell
cpu-llm-serve --secrets credentials.json --host 127.0.0.1 --port 8765
```

The credential file contains `secret_sha256` digests plus tenant, caller, and allowed-source mappings. Requests send the actual secret in `Authorization: Bearer ...`. The service provides POST `/v1/ask`, `/v1/ingest`, `/v1/correct`, and `/v1/delete`; it is a local stdlib HTTP server without built-in TLS. The [consumer guide](docs/library-consumer-guide.md#authenticated-http-service) includes a credential-generation example, exact request fields, and error semantics.

## Concurrency and scaling

`ask` is synchronous and uses the appliance's main Thinker pool. Do not concurrently call `ask` on the same instance as if it were a stateless function. `ask_concurrent` provides an experimental local-seat path with a lock and Thinker per seat, returning `seat`/`request_id` on success or an error such as `other_server`/`seat_failed`. `other_server` is a capacity outcome: it does not provision or execute on another machine.

The built-in HTTP entry currently forwards to `ask`, not `ask_concurrent`. Its threaded HTTP server is not proof of safe concurrent conversational use. Follow-up state, graph/index writes, reingestion, and multi-store lifecycle operations need explicit coordination. Scale counters and memory estimates have known gaps; they are not measured production capacity guarantees.

## Finance checks without PostgreSQL

For a supplied-field check alone, the pure local dispatcher can be used without constructing `Appliance`:

```python
from cpu_llm.finance import validate_message

result = validate_message("""Attest this Ledgerlock field.
 document type: w2_stip
 document id: w2-1
 document text: Wages 84210.00
 field: w2_box1_wages 84210.00 confidence 0.99 span 6-14
""")
print(result["checks"])
```

Use decimal strings for numeric fields in JSON; Python/JSON floats are refused by the relevant finance validators. Ledgerlock's SHA-256 digest is not a digital signature, document-authenticity proof, underwriting decision, or loan-system update. RefundProof distinguishes potential and actionable amounts and requires its supplied evidence/approval fields for stronger states. LedgerCovenant resolves figures using its implemented precedence rules, not outside financial data. See [finance input and scope](docs/library-consumer-guide.md#finance-inputs).

## Tests, measurements, and limits

```powershell
python -m pytest
```

Tests under `test_pipeline.py`, parts of `test_upload.py`, and `test_tenant_isolation.py` use a real local PostgreSQL service; other tests use fixtures/fakes or pure functions. Service tests bind a local port. Optional model tests can skip when checkpoints/dependencies are absent, and can run a real local model when present. Use a fresh writable `--basetemp` if the default temporary directory is restricted.

Run database integration tests against a disposable test database: some tests use fixed tenant/document/model IDs and write or delete fixture records. The complete suite was not run in the latest targeted review.

### What has actually been demonstrated

- For the October 25 join/response review, the **full suite passed 420 tests**, with two optional extraction-checkpoint tests skipped and no test files excluded or tests deselected. This used isolated PostgreSQL 18.1/pgvector and cached CPU encoder assets, including seven live join/lifecycle/history tests. The four-question diagnostic lab recorded hit-rate@5 and spoken attribution of 1.0; this is not a broad accuracy estimate. Wheel and source builds succeeded. Earlier real Coreferee smoke tests covered five reference forms plus ambiguity and user confirmation; FastCoref remains unvalidated. See the [validation record and transcript](docs/reviews/2026-10-25/join-review.md) and [response-case checklist](docs/response-cases.md).
- At `9d6fbe8`, **126 targeted tests passed**, with one fixed-ID database test deselected. Five additional live Appliance checks passed for missing duration, complete entity names, a short name, and exclusion of an unrelated passage. [Review and scope](docs/reviews/2026-10-19/review-9d6fbe8.md), [test transcript](docs/reviews/2026-10-19/pytest-9d6fbe8.txt), [live inputs and outputs](docs/reviews/2026-10-19/review-9d6fbe8-probes.json). That count does not include the later one-sentence reply selection or the ban and upper-limit reading. Those have tests in `tests/test_model01.py` and `tests/test_fact_bridge.py`.
- At the preceding `1183b77` revision, the **27 original diagnostic cases passed** on a 17-paragraph controlled corpus: 17 factual checks, four policy checks, four missing-fact nonanswers, and two arithmetic checks. Three repetitions through retrieval and the pipeline produced **162 measured calls without exceptions**. [Recorded benchmark](docs/reviews/2026-10-19/audit-1183b77-small/summary.json).
- At `edf54ee`, the same 27 cases passed with both 17 and 217 paragraphs, including 200 shipped WikiText distractors. That is a small distractor test, not evidence of production-scale retrieval. [Recorded comparison and follow-up findings](docs/reviews/2026-10-19/followup-review-edf54ee.md).

These are distinct source revisions. The 27-question benchmark was not repeated at `9d6fbe8`; its fixes were checked with the targeted suite and five live cases. Repetition counts are timing samples, not additional independent accuracy examples. No customer-corpus accuracy, business time savings, independent security certification, or general throughput guarantee has been established.

The `1183b77` run observed a 37.6 ms median and 58.9 ms nearest-rank p95 for 81 warmed, serialized, in-process pipeline calls on an Intel Core Ultra 9 275HX workstation. Encoding was included; startup, ingestion, and HTTP overhead were excluded. The workstation was not reserved exclusively for benchmarking. These figures describe that run, not an API latency promise.

To reproduce the diagnostic benchmark with installed dependencies, a cached encoder, and the development PostgreSQL service:

```powershell
python docs/reviews/2026-10-19/benchmark.py --out C:/path/to/new-audit
python docs/reviews/2026-10-19/analyze.py C:/path/to/new-audit
```

Use a new output directory. The harness freezes source, creates a fresh namespace, and retains the corpus, expectations, raw results, source hashes, and timing samples. Review new outputs before accepting its narrow fixture scores. It is not a general semantic correctness evaluator; optional models in a nested checkout directory are not copied into the frozen benchmark.

Older reports remain evidence for their recorded checkout/environment:

- [October 18 suite record](docs/test-results-2026-10-18.md): 180 passes and 17 PostgreSQL setup errors in that run.
- [Enterprise foundation record](docs/cpu-llm-enterprise-foundation.md): a later pipeline/upload run is recorded there.
- [Four-sentence retrieval lab](docs/retrieval-measurement-2026-10-18.md): a small labeled run, not customer-corpus quality or a production pass threshold.
- [Question benchmark, 18 October 2026](https://github.com/insightitsGit/cpullm/blob/main/docs/benchmark-cpu-llm-2026-10-18.md): seven questions on `DESKTOP-H3RO1EI`. Startup was 11.5 s. The middle question time was 167.0 ms. Grok and Gemini were not called.

That benchmark records seven individual question times, not a repeated-run percentile study. It includes abstentions and an unrelated answer to the France-capital question; timing results are not an accuracy score.

Additional limits include narrow English extraction grammars, incomplete retrieval coverage, limited alias/coreference handling, no general code generation or translation, and no universal transaction/rollback across PostgreSQL and local stores. Accepted schemas and credentials do not constitute an independent security certification.

## Source and design map

- [Current design](docs/current-design.md): current request lifecycle, channel semantics, storage, budgets, and validation limits.
- [Response cases](docs/response-cases.md): evidence-join semantics, covered examples, and cases still missing.
- [knowledge_graph.py](src/cpu_llm/knowledge_graph.py), [connection_channels.py](src/cpu_llm/connection_channels.py): explicit source facts and independent channel assessments; [graph design](docs/knowledge-graph.md).
- [prompt_intent.py](src/cpu_llm/prompt_intent.py), [query_dictionary.py](src/cpu_llm/query_dictionary.py), [attribute_search.py](src/cpu_llm/attribute_search.py): intent, lexical variants, and bounded retrieval repair; [dictionary design](docs/dictionary-assisted-paraphrases.md), [attribute retrieval](docs/attribute-directed-retrieval.md).
- [clarification.py](src/cpu_llm/clarification.py), [references.py](src/cpu_llm/references.py): session-local clarification and optional reference backends; [remaining use cases](docs/intent-support-backlog.md).
- [pipeline.py](src/cpu_llm/pipeline.py): `Appliance`, graph order, ingestion, scoped asks, concurrency, lifecycle.
- [reply.py](src/cpu_llm/agents/reply.py), [answering.py](src/cpu_llm/answering.py), [fact_bridge](src/fact_bridge/__init__.py): displayed-reply selection and rule inference.
- [answerability.py](src/cpu_llm/answerability.py), [model01](src/cpu_llm/model01/): supported query bindings and deterministic construction generation.
- [frames.py](src/cpu_llm/memory/frames.py), [realizer](src/cpu_llm/realizer/): role extraction, constructions, and separate verification scopes.
- [entry.py](src/cpu_llm/entry.py), [serve.py](src/cpu_llm/serve.py), [access.py](src/cpu_llm/access.py): credentials, routes, and source scopes.
- [Consumer guide](docs/library-consumer-guide.md): integration contract and operational examples.
- [Semantic memory](docs/cpu-llm-v1.8-semantic-memory.md), [final v1.9 realizer design](docs/cpu-llm-v1.9-realizer.md), [enterprise foundation](docs/cpu-llm-enterprise-foundation.md), [formats/scale](docs/cpu-llm-output-formats-and-scale.md): design intent; verify implementation and tests for the supported case.
- [Latest targeted review](docs/reviews/2026-10-19/review-9d6fbe8.md): verified fixes and exact validation scope. The [earlier correctness handoff](docs/handoff-claim-verification-review.md) and design proposals are historical records; some findings have since been fixed, and others require separate verification.

## License and attribution

Code: Apache-2.0; see [LICENSE](LICENSE). Shipped WikiText-2 text has its own CC BY-SA 3.0/GFDL attribution in the [dataset provenance](src/cpu_llm/data/wikitext-2-raw-v1/PROVENANCE.txt). The AI and finance primers are additional packaged text, separate from WikiText. Preserve the applicable source attribution when redistributing retrieved passages.

Amin Parva — AI Architect & Staff Applied AI Engineer — [parvaamin@gmail.com](mailto:parvaamin@gmail.com).

```bibtex
@software{cpullm2026,
  title = {cpu-llm: CPU-only answers and documents from stored text},
  author = {Amin Parva},
  year = {2026},
  url = {https://github.com/insightitsGit/cpullm},
  license = {Apache-2.0}
}
```
