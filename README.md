# cpu-llm

**Local, CPU-based question answering and document layouts over indexed text.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-orange)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-insightitsGit%2Fcpullm-181717?logo=github)](https://github.com/insightitsGit/cpullm)

cpu-llm indexes paragraphs in PostgreSQL/pgvector and retrieves them using VectorPrism. It can rebuild supported propositions, extract narrowly defined event roles, apply pattern-based rules, calculate arithmetic, and arrange retrieved sentences into named document formats. It also includes local finance-validation routines and an authenticated HTTP entry point.

**Author:** [Amin Parva](mailto:parvaamin@gmail.com). **Package metadata:** 1.8.0. This README describes the repository implementation inspected on 2026-10-18. Pin a commit or release tag when integrating; verify [PyPI release availability](https://pypi.org/project/cpu-llm/) separately rather than assuming an installed wheel contains every checkout feature. Recorded question times are in the [18 October 2026 benchmark](docs/benchmark-cpu-llm-2026-10-18.md).

**Correctness boundary:** source copying, deterministic execution, and lexical auditing are not mathematical guarantees of truth or absence of unsupported conclusions. `answer` and the user-visible `reply["text"]` can be different, with different checks. A retrieved neighbor is not an answer: for the supported “what is” and “capital of” shapes, `answer_status` says whether a retrieved sentence states the asked relation, and a question with no such sentence is not answered from model knowledge or from an unrelated paragraph. The counts and the remaining limits are in [the 18 October answerability note](docs/answerability-evaluation-2026-10-18.md). Known rule/writer, construction-checker, formatting, and capacity-accounting gaps are recorded in the [claim-verification handoff](docs/handoff-claim-verification-review.md). Use the structured outcome and its evidence, rather than treating every nonempty reply as a verified answer.

For an agent integrating the library, start with [the consumer guide](docs/library-consumer-guide.md): complete `ask` arguments, result interpretation, credentials, HTTP contracts, and operational limitations.

## Requirements and installation

- Python 3.11 or newer and a 64-bit CPU.
- PostgreSQL with the `vector` extension; the documented development configuration uses PostgreSQL 16.
- The frozen `sentence-transformers/all-mpnet-base-v2` encoder. First use may download model assets; subsequent offline use requires those assets already cached.
- Writable local storage for `.chorusgraph/cpu-llm/` under the process's **current working directory**, in addition to the PostgreSQL data.

To request the repository's `v1.8.0` tag explicitly, install from GitHub:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install "cpu-llm @ git+https://github.com/insightitsGit/cpullm.git@v1.8.0"
```

For a checkout you are editing, clone the repository and use `python -m pip install -e .` instead of the Git URL.

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

with Appliance(namespace="demo") as app:
    receipt = app.ingest(SourceDocument(
        "field-guide",
        (
            "The harbor kestrel is a small coastal falcon.",
            "John ate a yellow apple in his house.",
        ),
    ))
    print(receipt["ids"])  # field-guide-p0001, field-guide-p0002

    result = app.ask("What is the harbor kestrel?")
    print(result.get("answer"))
    print((result.get("reply") or {}).get("text", ""))

    frame = app.ask("What color was the apple John ate?")
    print(frame.get("frame_result"))
```

Use a context manager, or call `close()`, to release Thinker workers. Reuse an appliance rather than loading the encoder and worker pool for each question. A named namespace starts with its own vector table; it does not inherit the default tenant's indexed passages.

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

- **Plain questions:** deliberate over supported stored propositions. Only a paragraph's first sentence is considered by the proposition extractor. A paragraph that cannot be reconstructed can still be retrieved or quoted. A quotation is not a verified direct answer.
- **Event questions:** supported color, location, and agent forms, such as `What color was the apple John ate?`, `Where did John eat the apple?`, and `Who ate the apple?`. Dates and tense constrain matching. Limited negative/conditional frame forms and paragraph-local alias helpers also exist; this is not general semantic parsing or arbitrary coreference. The query frame node operates on the retrieved passages, not an exhaustive role-index search.
- **Rule answers:** return `YES`, `NO`, `CONTESTED`, `UNKNOWN`, `CAUSE`, or `NONE` under `reply.situation`. Pattern coverage is limited. This path still contains known implication, conflict, modality, and background-memory issues; it is not a complete policy engine.
- **Summary/explanation/list/sources:** optional brief output over stored sentences. Explanations look for stated causes. Comparisons present per-topic evidence; they do not establish a new comparative judgment.
- **Deep search:** expands candidate paragraphs using lexical tags/relation hands. `deep_min_similarity` defaults to `0.62`; setting it to `None` removes that additional dense-similarity floor. A shortlist is not proof that all relevant evidence or contradictions were found.
- **Creative mode:** selects varying subsets of stored sentences. The same prompt can yield different passages; this feature is not deterministic across runs.
- **Math:** evaluates supported arithmetic in a separate agent. A computed value is not a retrieved proposition.
- **Document layouts:** 31 built-in formats, including email, report, checklist, essay, and FAQ. A named format/topic can replace the main reply with copied topic-related sentences. This is text layout, not DOCX/PDF export or unrestricted prose generation. Missing roles should remain unfilled; topic-to-header binding has known limitations.
- **Finance checks:** local RefundProof, LedgerCovenant, and Ledgerlock routines consume supplied fields. They do not fetch financial records or perform external writes.

The supported grammar and explicit non-answer statuses are part of the interface. A name or possessive in a sentence does not establish arbitrary identity, ownership, or causality.

## Models and the meaning of deterministic

The retrieval encoder and shipped `vectorprism.pt` projection are distinct from sentence generation. Dense retrieval is trained; the other subspace readings and relation signatures are not a trained fact generator.

There are **three separate wording paths**:

1. The v1.9 construction realizer has N0 plans/constructions/checking but **no trained ranker checkpoint**. `realization="evidence_neural"` currently reports deterministic fallback. It is opt-in, does not affect every plain reply, and is not a delivered neural graph decoder. `account=True` opts into an account of authorized records.
2. Model01 sentence generator is the graph node immediately before the reply, after math, finance, and the event frame. It writes the checked sentence from the prompt and the stored records. Content words are copied from licensed spans. A ranking prompt quotes a stored order, or says the passages do not state one. A blocked prompt skips the node, and a withheld sentence stays the reply. It loads no checkpoint. `prepare()` stores checker-approved pairs in Postgres table `model01_training_pair`, with the WikiText test split marked `test`. `train()` writes nothing while every plan has one legal sentence.
3. The fact-bridge rule path can **automatically load local FLAN-T5 extraction and writing models** when the pattern path misses, the prompt/passages have rule cues, and model directories are found. This can happen with the default `realization="deterministic"`. Model lookup checks `FACTBRIDGE_MODELS`, then `models/` and `cpullm-factbridge/models/` relative to the package installation root. An explicit root is also supported by the low-level fact-bridge API.

The latter requires external checkpoints and optional tooling such as Transformers, torch, SentencePiece, and safetensors. A missing/incompatible writer or dependency can raise during a question. The current `Appliance.ask` has no public switch that guarantees this automatic fallback is disabled; inspect deployment assets and `reply.situation.wording.path`. The learned writer currently returns a nonempty candidate without calling its verifier. Its output is not covered by the earlier `answer` audit.

Thus, “CPU-only” does not mean “no decoder,” and default mode does not guarantee every path uses only deterministic templates. This project makes no universal truth or zero-hallucination guarantee.

## Reading results correctly

Always use `.get(...)` for optional fields. Access refusals and seat failures may have a different shape from normal graph results.

- `reply.text`: the displayed output. It may be a base answer, quote, frame/non-answer, rule verdict, math result, finance result, or document layout.
- `answer`: the base EIR-realized sentence or a substituted fallback. It may differ from `reply.text`.
- `audit_passed`: the audit of the base realized propositions; it does **not** certify the entire displayed reply, source truth, document fields, or learned rule wording.
- `shine_ok`, `shine_enforced`, `delivery_blocked`: grounding/delivery diagnostics for the checked path. Never restore a withheld candidate using a debug field.
- `frame_result.status` / `verified`, `frame_verified`: frame-specific outcomes. `answered`, `missing`, `ambiguous`, `conflicting`, `unsupported`, and sometimes `ignored` distinguish response types.
- `reply.situation`: rule verdict, delivered rule text, `because` source sentences, and wording-path metadata. Those sources can currently include synthesized background memory; do not equate them automatically with original retrieved citations.
- `reply.draft`: document format/topic/text, missing fields, and source IDs. Header provenance/binding is not a universal guarantee.
- `math_result`, `finance_result`, `realization_result`: separate component results; inspect their own fields instead of applying `audit_passed` to them.
- `related`: retrieved items using `chunk_id`; `passages` uses `document_id`. These are paragraph IDs, not source URLs.
- `thinker_directive`, `gather_questions`: sufficiency advice. `gather`, `refuse`, or `escalate` are not themselves a guarantee that all later display is suppressed; apply a consumer policy explicitly.
- `typos`, `original_message`: actual query rewrites. The corrected query is used by later stages. `original_message` is present when a rewrite occurred.

For applications that make decisions, separate the transport outcome, component status, actual wording, supporting source, and consumer approval policy. An HTTP 200 or a nonempty string is not an accepted factual result. See [result routing guidance](docs/library-consumer-guide.md#result-routing-for-an-agent).

## Tenants, authentication, and service

`Appliance(namespace="tenant_alpha")` uses a normalized namespace, PostgreSQL schema/table `ns_tenant_alpha.psm_document_embeddings`, and local files under `.chorusgraph/cpu-llm/tenant_alpha/`. The default namespace is tenant `cpu-llm`. Local paths are relative to the working directory: use a stable working directory and isolate deployments that use different DSNs.

Direct Python calls are trusted integration calls. Omitting `caller` is unscoped within the selected tenant; constructing a `CallerContext` is not authentication. For source-scoped callers use exact paragraph IDs or a source prefix ending in `-p`, such as `field-guide-p`. An empty scope permits no reads. Use the authenticated `Entry`/HTTP service when callers are not already trusted.

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

Historical reports are evidence for their recorded checkout/environment, not a current full-suite pass:

- [October 18 suite record](docs/test-results-2026-10-18.md): 180 passes and 17 PostgreSQL setup errors in that run.
- [Enterprise foundation record](docs/cpu-llm-enterprise-foundation.md): a later pipeline/upload run is recorded there.
- [Four-sentence retrieval lab](docs/retrieval-measurement-2026-10-18.md): a small labeled run, not customer-corpus quality or a production pass threshold.
- [Question benchmark, 18 October 2026](https://github.com/insightitsGit/cpullm/blob/main/docs/benchmark-cpu-llm-2026-10-18.md): seven questions on `DESKTOP-H3RO1EI`. Startup was 11.5 s. The middle question time was 167.0 ms. Grok and Gemini were not called.

That benchmark records seven individual question times, not a repeated-run percentile study. It includes abstentions and an unrelated answer to the France-capital question; timing results are not an accuracy score.

The October 13 measurement on an Intel Core Ultra 9 275HX/64 GB machine reported about 10 seconds to load, 60–66 ms median warm questions for several original modes, and 593 ms deep search. It predates rule-wording, finance, tenancy, and current concurrency changes and is **not a benchmark of this checkout**. No general minimum CPU, throughput, or p95 guarantee is established.

Additional limits include narrow English extraction grammars, incomplete retrieval coverage, limited alias/coreference handling, no general code generation or translation, and no universal transaction/rollback across PostgreSQL and local stores. Accepted schemas and credentials do not constitute an independent security certification.

## Source and design map

- [pipeline.py](src/cpu_llm/pipeline.py): `Appliance`, graph order, ingestion, scoped asks, concurrency, lifecycle.
- [reply.py](src/cpu_llm/agents/reply.py), [answering.py](src/cpu_llm/answering.py), [fact_bridge](src/fact_bridge/__init__.py): displayed-reply selection and rule inference.
- [frames.py](src/cpu_llm/memory/frames.py), [realizer](src/cpu_llm/realizer/): role extraction, constructions, and separate verification scopes.
- [entry.py](src/cpu_llm/entry.py), [serve.py](src/cpu_llm/serve.py), [access.py](src/cpu_llm/access.py): credentials, routes, and source scopes.
- [Consumer guide](docs/library-consumer-guide.md): integration contract and operational examples.
- [Semantic memory](docs/cpu-llm-v1.8-semantic-memory.md), [final v1.9 realizer design](docs/cpu-llm-v1.9-realizer.md), [enterprise foundation](docs/cpu-llm-enterprise-foundation.md), [formats/scale](docs/cpu-llm-output-formats-and-scale.md): design intent; verify implementation and tests for the supported case.
- [Correctness handoff](docs/handoff-claim-verification-review.md): known findings and required regression checks. Earlier proposals remain historical design records.

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
