# CPU-LLM: Evidence-Based AI Engine

**A neuro-symbolic and constraint engine for source-backed answers, deterministic checks, and cross-domain research on commodity CPUs.**

[![PyPI](https://img.shields.io/pypi/v/cpu-llm)](https://pypi.org/project/cpu-llm/)
[![Code license Apache 2.0](https://img.shields.io/badge/Code-Apache_2.0-green)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](pyproject.toml)

`cpu-llm` / `cpullm` is an embeddable, CPU-first Python library that retrieves
evidence from your knowledge base and uses it to answer questions, verify rules
and calculations, and assemble cited reports. Version 1.12.0 also
supports cross-domain research, hypothesis generation, and numerical scans
with supported model adapters.

Use **strict evidence mode** when you need exact source quotations, recognized
calculations, or a clear unsupported result. Use the **research and invention
routes** to explore relationships, join cited premises across knowledge bases,
or formulate hypotheses. Hypotheses carry their own label, and numerical results
are conditional on the selected model and supplied constraints.

**This release: 1.13.0.** Author: **Amin Parva, Independent Engineer**.

**Licenses:** code [Apache-2.0](LICENSE); bundled WikiText-2 data has separate
**CC BY-SA 3.0/GFDL** terms and attribution. See [third-party notices](THIRD_PARTY_NOTICES.md).

## Architecture in 30 seconds

CPU-LLM is a Python evidence engine. The package name refers to its CPU-first
language pipeline. It uses a pretrained encoder for retrieval and applies
rules or model adapters according to the request.

```text
Question + authorized knowledge base
  |
  +-- Strict evidence --> Exact quotes, deterministic checks, or unsupported
  |
  +-- Research ---------> Retrieve evidence and assemble cited responses
       |
       +-- CrossDomain --> Join cited premises across selected KBs
       +-- Invention ---> Propose hypotheses and run supported model scans
```

## Verification contract compared with generative RAG

This compares execution contracts, not measured product accuracy or cost.
Generative RAG systems can also add citations, calculators and deployment controls.

| Dimension           | Generative RAG without enforced verification   | CPU-LLM verification contract                                                    |
| ------------------- | --------------------------------------------- | -------------------------------------------------------------------------------- |
| Answer construction | Generated prose needs independent checks.     | Strict mode quotes exact spans, runs supported checks, or returns `unsupported`. |
| Arithmetic          | Accuracy depends on the calculator in use.    | Inspectable decimal and integer policies, including explicit half-up rounding.   |
| Infrastructure      | Depends on model and hosting choices.         | CPU-first Python, PostgreSQL with pgvector, and cached encoder assets.             |
| Audit evidence      | Depends on the application's evidence layer.  | Source IDs, quote offsets, chunk hashes, and receipts for supported tone output.  |
| Data location       | Hosted or self-managed.                       | On-premises execution with prepared assets. Operators enforce network isolation. |

“Zero hallucination” is not a universal accuracy guarantee. Strict selection can
preserve an incorrect source, and an unsupported request can be refused. Ordinary
mode has different verification limits, including optional learned producers.

## Core capabilities

### Strict evidence: quote or abstain

After setup, ingest atomic statements and ask an explicit attribute question.
Save this as a script; use the main guard on Windows:

```python
from cpu_llm.pipeline import Appliance
from cpu_llm.documents import SourceDocument

def main():
    with Appliance(namespace="label_example", prompt_backend="rules") as app:
        app.ingest(SourceDocument("fictional-label", (
            "The strength of Fictional Luma is 0.75 mg.",
        )))
        for question in (
            "What is the strength of Fictional Luma?",
            "Which antibiotic should Case Birch receive?",
        ):
            result = app.ask(question, strict_evidence=True, small_talk=False)
            print(result["answer_status"])
            print(result["reply"]["text"])
            print(result.get("answer_evidence", []))

if __name__ == "__main__":
    main()
```

The [recorded healthcare demo](examples/healthcare/sample-run/README.md) shows:

```text
What is the strength of Fictional Luma?
status: evidence_quote
The strength of Fictional Luma is 0.75 mg.

Which antibiotic should Case Birch receive?
status: unsupported
Unsupported strict request; use explicit named attribute questions.
```

Evidence includes document IDs, quotation offsets and chunk hashes. These are
fictional label-handling fixtures, not a diagnostic or prescribing system.
Use one factual statement per record for the recognized strict grammar;
multisentence records can be rejected rather than losing a qualifier.
[Strict grammar and limits](docs/strict-evidence-spec.md).

### Deterministic finance: explicit fields and precision

`LedgerCovenant` evaluates supplied covenant fields. `RefundProof` reviews
supplied sales-tax findings; it is a separate check, not a covenant synonym.
The direct validator needs no database or encoder:

```python
from cpu_llm.finance import validate_message

result = validate_message("""Decide this LedgerCovenant test.
comparator: lte
threshold: 4.50
numerator: compliance_certificate 9000001
denominator: compliance_certificate 2000000
ratio places: 6
""")
print(result["text"])
print(result["checks"])
```

```text
Raw ratio:               9000001 / 2000000 = 4.5000005
Six-place half-up value: 4.500001x
Allowed threshold:      lte 4.500000x
Decision:               BREACH
```

The block summarizes the inspectable calculation; the command prints the full
result and precedence trace. `4.500001` is the policy-rounded value, not the raw
quotient. Precision is explicit, not a universal six-decimal rule or binary-float
approximation. Supplied fields are not authenticated financial records, and a
breach result is not a legal declaration of default.

### Verified document generation: bounded inverse grammar

Using an appliance configured as above:

```python
app.ingest(SourceDocument("helios-manual", (
    "Helios is a backup service.",
    "Helios stores encrypted backups.",
    "Helios uses PostgreSQL for metadata.",
    "Helios does not support automatic regional failover.",
)))
result = app.ask("Write a detailed article about Helios in a friendly tone.")
print(result["reply"]["text"])
```

Supported predicate joins can produce:

```text
Helios stores encrypted backups and uses PostgreSQL for metadata.
```

The tone request is removed from the retrieval topic. Bounded inverse grammar
checks supported constructions against source predicates while retaining proofs,
numbers, negation and qualifiers. Unsupported constructions remain quotations;
missing sections remain explicit. Strict documents bypass tone rewriting.
This produces bounded new wording, not arbitrary creative prose or new facts.
[Article/report receipts](docs/examples/2026-11-03-prompt-tone/README.md) ·
[Document and tone manual](docs/document-generation-user-guide.md).

### Six-signal retrieval and explicit routing

The ordinary pipeline registers 27 graph nodes, including **dense, relational,
disentangled, hyperbolic, identity and causal** retrieval signals backed by
PostgreSQL/pgvector. **Only dense and identity projection heads are trained and
bundled**; the other channels use their implemented signals or symbolic paths.
A similarity score or connection is not factual proof. Strict requests and document
workflows can bypass the ordinary graph; not every request runs every node.
See the [architecture](docs/current-design.md) and [prompt-to-node mapping](docs/prompt-flag-map.md).

## Research, relationship loops, invention, and CrossDomain

These features are included in **1.12.0**. For a development install from a Git
checkout, use the commands below and complete the database and encoder setup
in the quickstart.

```shell
git clone https://github.com/insightitsGit/cpullm.git
cd cpullm
python -m pip install -e .
```

- **Research planning:** `Write a detailed article about Helios.` or
  `Draft a concise email to Alex about Helios.` automatically creates an
  inspectable `research_plan`. Named topics and one layer of explicit relations
  select evidence from one authorized snapshot.
- **Long responses:** `Write an article about Helios in 1000 words.` uses a
  source-body word target; `Write a report about Helios in 60 items.` can select
  60 separate source items. Evidence shortage is reported, never padded.
- **Loop exploration:** `Show relationship loops for Alpha.` or
  `Explore cycles through Alpha.` activates bounded multi-cycle search.
- **Invention:** `Invention: Fernhouse.`, `Imagine Fernhouse.`, or
  `Create a new concept from Fernhouse.` combines cited relationships across
  chunks and proposes new connections to test. Use `invent=True` in Python or
  `"invent": true` in HTTP. “Imagine a story” uses the existing story workflow.
  You can also say `Guess: Fernhouse.`, `Speculate about Fernhouse.`, or
  `Brainstorm ideas for Fernhouse.` to request hypotheses.
- **Loops inside a document:** `Write a detailed report about Alpha, including
  relationship loops through Alpha.` consumes the discovered paths in a
  Relationship loops section, using the same snapshot as the report.
- **Tone:** append `in a friendly tone` for the supported tone stage. Ordinary
  documents already use neutral inverse-verified composition. Path sentences
  preserve their source clauses and are not rewritten by tone.

Inside an existing appliance (use the main guard on Windows), a minimal fixture:

```python
app.ingest(SourceDocument("loop-example", (
    "Alpha causes Beta.",
    "Beta causes Gamma.",
    "Gamma causes Alpha.",
)))
result = app.ask("Show relationship loops for Alpha.")
print(result["reply"]["text"])
```

Supported output includes:

```text
The source records describe a closed lexical path: Alpha causes Beta; Beta causes Gamma; Gamma causes Alpha.
```

Each clause keeps its source proof, direction and six-channel receipt. This
does **not** infer the shortcut “Alpha causes Gamma” or resolve word senses.
Quoted/negative/background instructions do not activate loop search. General
articles do not automatically activate it either.

Python and HTTP `/v1/ask` can instead supply
`cycle_search={"seed": "Alpha", "limits": {"max_rounds": 1000}}`.
Explicit API options override the prompt seed. Default maximum rounds: 1,000;
absolute configurable ceiling: 100,000, with additional time/memory/edge limits.
Strict API/header/operator mode disables cycle exploration and prose rewriting.
Check `cycle_composition`, `cycle_exploration`, `answer_evidence` and coverage for
omitted paths or incomplete searches. [Full trigger and budget guide](docs/research-cycle-user-guide.md).

### Invention example

In a fictional greenhouse fixture, one source says Fernhouse uses soil moisture
sensors and another says it stores irrigation event logs. `Invention: Fernhouse.`
proposed a shared interface between them, cited both records, and suggested a
prototype comparison. The proposed link was absent from the five fixture records.
The shipped checkpoint scored dense and identity channels. The response keeps
all six channel outcomes and labels the proposals as hypotheses.

Every run sets `invention.potentially_nondeterministic=true` and appends this
note after the response, including empty and partial runs. The note applies to
the invention proposals within a mixed response. Strict-evidence mode disables
invention.

> Invention note. Proposals from the invention node are hypotheses. They may contain errors and can vary between runs.

See the fixture, ranked proposals, and current template limits in the
[invention spec](docs/taxonomy-invention-spec.md#fernhouse-test-record).

To develop a proposal over several turns, reuse the same `session_id`:

```python
app.ask("Invention: Fernhouse.", session_id="fernhouse-design")
app.ask("Explain proposal 1.", session_id="fernhouse-design")
app.ask("Go deeper.", session_id="fernhouse-design")
```

When there is one proposal, “Can you explain more?” is enough. When several
are available, the engine asks which one to expand. The first follow-up outlines
a prototype test and retrieves cited relationships involving the proposal's
terms. The second adds test controls and searches from the terms found in the
first follow-up. Proposed relationships stay labeled as hypotheses, and the
engine rechecks the cited premises on each turn. See the
[follow-up spec](docs/taxonomy-invention-spec.md#conversation-follow-ups).

### Join multiple knowledge bases with CrossDomain

Give sources an alphanumeric KB prefix followed by a hyphen, such as
`physics-seesaw.md`, `math-rotations.md`, or `numerics-rotation-checks.md`.
Ingest them into the same appliance with `app.ingest(...)`, then select
two to seven prefixes:

```python
reply = app.ask("CrossDomain: Casas-Ibarra using KBs: physics, math, numerics.")
print(reply["reply"]["text"])
```

The first KB anchors the topic. Each selected KB must contribute a cited
premise for the same join. The short prompt `CrossDomain: Casas-Ibarra.`
defaults to physics and mathematics. Research prompts also route here when they
name KBs explicitly, for example `Research Casas-Ibarra using KBs: physics, math, numerics.`
Use `Research`, `Investigate`, or `Explore` with that suffix. Ordinary research
requests use the research planner. CrossDomain currently verifies complex
orthogonality in the transpose convention. If a selected KB lacks a matching
premise, the reply names the gap and asks you to ingest a source under that prefix.
Strict evidence mode disables this invention route. See the
[CrossDomain spec](docs/taxonomy-invention-spec.md#crossdomain) for the join rule.

#### When to use CrossDomain and Constraint Check

Use **CrossDomain** to join source premises and check a shared mathematical
relation. Use **Constraint Check** to compare a prediction with a bound or
compare two reported measurement intervals after converting units.

For a numerical check, ingest one `CrossDomain claim: {…}` record per selected
KB. Give the records the same topic, quantity, conditions, and convention. A
prediction-versus-bound check uses a prediction record, a method record, and
a bound record. A measurement comparison uses two measurement records.

```python
math_check = app.ask("CrossDomain: Casas-Ibarra using KBs: physics, math.")
bound_check = app.ask("Constraint Check: Leptogenesis using KBs: physics, math, experiment.")
print(math_check["reply"]["text"])
print(bound_check["reply"]["text"])
```

In the leptogenesis example, the first node checks the rotation identity. The
second can check whether the illustrative **6.31 meV** prediction falls within
the supplied **28 meV** scenario. It cites each input and returns
`insufficient_evidence` when required claims are missing or incompatible.
CrossDomain prompts over structured claims still work and delegate the
comparison to Constraint Check. See the
[structured claim format](docs/cross-domain-research-spec.md#first-milestone).

#### Baryon asymmetry example

Why did the early universe end up with more matter than antimatter?
Leptogenesis is one proposed explanation. In this example, CrossDomain checks
one mathematical ingredient of the Casas–Ibarra parameterization used in a
leptogenesis model.

We ingested a physics note based on the
[Casas–Ibarra paper](https://arxiv.org/abs/hep-ph/0103065) and a math note derived
from [Orloff’s *Complex Variables with Applications*, section 2.8](https://math.libretexts.org/Bookshelves/Analysis/Complex_Variables_with_Applications_%28Orloff%29/02%3A_Analytic_Functions/2.08%3A_Gallery_of_Functions).
The live PostgreSQL/pgvector run returned `insufficient_evidence` with the
physics note alone. After ingesting both notes, it returned `hypotheses`:

```text
Prompt: CrossDomain: Casas-Ibarra.

Proposed model check: Verify the complex rotation using R^T R = I. For the rotation row, check cos(z)^2 + sin(z)^2 = 1.
The built-in check sampled three complex angles with maximum residual 2.29e-16.
[physics-casas-ibarra-p0001] The Casas-Ibarra matrix R is complex orthogonal and satisfies R^T R = I.
[math-orloff-complex-trigonometry-p0002] For complex z, the rotation built from cos(z) and sin(z) is complex orthogonal and satisfies R^T R = I.

Invention note. Proposals from the invention node are hypotheses. They may contain errors and can vary between runs.
```

The result checks the rotation identity at three complex angles. The separate
leptogenesis scan below explores whether the illustrative model satisfies the
cosmological and laboratory constraints.

### From a cited hypothesis to a numerical scan

With a knowledge base that describes competing explanations for baryon asymmetry,
`Invention: Baryogenesis.` can ask which mechanism to investigate.
`Invention: Leptogenesis.` can then propose testing whether a model reproduces
the observed asymmetry while satisfying neutrinoless double-beta decay constraints.
`Can you explain more?` and `Go deeper.` carry the hypothesis and its citation
forward. When the source names an observable but supplies no usable numerical
limit, the reply reports that gap.

When the leptogenesis brief lacks numeric constraints, chat runs a built-in
illustrative profile and cites its separate inputs. Follow-ups report a sampled
point and the refined crossing when available. For custom bounds or a different
grid, run the scan explicitly in Python:

```python
from cpu_llm.constraint_evaluator import ObservableLimit, ParameterAxis

reply = app.ask("Invention: Leptogenesis.", session_id="baryogenesis")
hypothesis = reply["invention"]["proposals"][0]  # Select a cited proposal from the reply.
scan = app.scan_leptogenesis(
    hypothesis,
    axes=[
        ParameterAxis("M1", "GeV", [1e11, 2e11, 3e11]),
        ParameterAxis("m_lightest", "eV", [0.003579]),
        ParameterAxis("re_z", "rad", [-0.7853981633974483]),
        ParameterAxis("im_z", "rad", [0.6333333333333333]),
    ],
    limits=[
        ObservableLimit("asymmetry", "eta_B", "1", "Diagnostic acceptance window",
                        lower=5.62e-10, upper=6.62e-10),
        ObservableLimit("effective-mass", "m_beta_beta", "eV", "Historical benchmark scenario",
                        upper=0.036),
    ],
)
print(scan["status"], scan["accepted_count"], scan["transition_brackets"])
```

The illustrative adapter uses normal ordering and an unflavored approximation.
Its brackets describe transitions between sampled points. See the
[constraint evaluator spec](docs/invention-constraint-evaluator-spec.md) for the
full scan inputs, reported limits, and interpretation.

## Quickstart and reproduction

Python 3.11+ is required. Release checks used Windows/Python 3.12.10.

```shell
python -m pip install --upgrade pip
python -m pip install "cpu-llm==1.13.0"
python -m pip check
python -c "import cpu_llm; print(cpu_llm.__version__)"
```

Before publication, install the supplied wheel instead of the version from PyPI.
To build from a checkout, run `python -m pip install build` and then
`python -m build --outdir dist/1.13.0`.

Document queries require PostgreSQL/pgvector and the pretrained
`sentence-transformers/all-mpnet-base-v2` encoder assets. The trained projection
is bundled; no retraining is required for these demos. Follow the
[database setup](docs/development-database.md) and [encoder preparation](docs/offline-setup.md).
Recorded installed-package checks used native PostgreSQL 18/pgvector.

**Docker alternative — configuration documented; container startup remains
unverified on the maintainer's current host.** For a disposable development
instance, this command binds only to loopback:

```shell
docker run -d --name pgvector-test -p 127.0.0.1:5434:5432 -e POSTGRES_PASSWORD=postgres pgvector/pgvector:pg16
docker exec pgvector-test pg_isready -U postgres -d postgres
```

After readiness succeeds, enable the extension:

```shell
docker exec pgvector-test psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;"
```

Set the matching connection string before running Python. POSIX shell:

```shell
export VECTORPRISM_PG_DSN='postgresql://postgres:postgres@127.0.0.1:5434/postgres'
```

PowerShell:

```powershell
$env:VECTORPRISM_PG_DSN = 'postgresql://postgres:postgres@127.0.0.1:5434/postgres'
```

After database and encoder preparation:

```shell
cpu-llm-demo healthcare --out healthcare-demo-output
cpu-llm-demo conversation --out conversation-demo-output
```

Use fresh output directories. The commands ingest demo records and save responses,
evidence and outcome checks. Initial encoder download time depends on connectivity
and caching; it is preparation, not training. For disconnected deployments,
prepare the Python wheelhouse, database installation/image and encoder cache
before transfer. Offline flags are not a substitute for network isolation.

## Enterprise and commercial evaluation

For pilot discussions with **Insight IT Solutions**, visit
[CPU-LLM research and commercial enquiries](https://www.insightits.com/research-tools/cpu-llm).
Potential scopes include:

- **Private-credit covenant monitoring:** map explicit source fields and policies
  into LedgerCovenant checks, with reviewable arithmetic and evidence.
- **On-premises and sovereign deployments:** prepare CPU runtime assets and
  evaluate isolation, identity and gateway controls in the target environment.
- **Regulatory workflow adapters:** integrate existing tenant/source permissions
  with enterprise RBAC, retention and audit systems. SOX/HIPAA requirements need
  a deployment-specific assessment; no certification is claimed.

These are pilot integration opportunities, not claims of deployed customer
results, automatic legal compliance or a turnkey zero-trust enclave.

## Inspect and manage chunks

Chunk inventory, confirmed deletion, team roles, and parallel ingestion are included in 1.13.0.

Ask `How many chunks do we have?`, `How many chunks are there in notes.pdf?`,
or `List chunks for notes.pdf.` Counts include active chunks visible to the
caller. Use the ingested filename or source prefix to filter by document.
The Python method `app.chunk_inventory("notes.pdf", limit=50, offset=0)`
and HTTP `POST /v1/chunks` return the total, exact chunk IDs, and the next
offset if another page is available. Omit the source to count the accessible
knowledge base.

### Delete one chunk with confirmation

In a team deployment, configure `"role": "admin"` on a trusted credential
record for users who can preview and confirm chunk deletion or delete a source.
Credentials without a role default to `reader`. Administrators still need
access to the target source or chunk. Readers can use inventory within their
source scope. A standalone Python appliance without a caller context acts as
the local operator.

Use `Delete chunk notes-p0001.` to preview the exact chunk in chat, or call
`app.delete_chunk("notes-p0001")` to obtain the preview and confirmation token.
After reviewing it, pass the token as `confirmation=` to a second call with the
same chunk ID. HTTP clients can POST the same fields to `/v1/delete-chunk`.
The token expires in five minutes and is tied to the caller and row revision.
Sibling chunks and correction versions require their own confirmations.
The legacy source deletion API operates on whole sources.
The shared resonance ledger and word-relation file are retained.
See the [chunk management spec](docs/chunk-management-spec.md) for receipts,
approval behavior, and team permissions.

### Ingest large documents

Ingestion encodes each chunk once and reuses the result for storage and graph
processing. Use `app.ingest("book.pdf", encoder_workers=4)` to try parallel
encoding. The default is one worker, and the maximum is four. In the 162-page
MIT PDF test, one worker completed in 85.7 seconds and used 3.00 GiB peak
process memory. Four workers took 113.7 seconds and used 6.53 GiB. Both
produced identical chunk text and dense vectors.
[Ingestion performance spec](docs/ingestion-performance-spec.md)

## Verification and deployment limits

The 1.11.2 source run reports **925 passed, 56 skipped, 3 expected
failures**: 54 skips were disabled opt-in integration cases; two lacked optional
extractor checkpoints. See the [1.11.2 build validation](docs/releases/1.11.2-build-validation.md). Separate installed-wheel checks covered strict/ordinary
HTTP and the healthcare demo's 12/12 authored outcomes.
[Commands, scope and receipts](docs/testing-results.md). No independent clinical,
customer-corpus or hosted-model comparison establishes superiority.

The authenticated HTTP service exposes POST `/v1/ask`, `/v1/ingest`, `/v1/correct`
and `/v1/delete`. Version 1.13.0 adds `/v1/chunks` and `/v1/delete-chunk`.
It serves requests serially. Lazy factories must construct
appliances on the serving thread. There is no built-in TLS or production gateway,
and long work blocks other requests. See [OpenAPI](docs/openapi.json) and the
[consumer guide](docs/library-consumer-guide.md#authenticated-http-service).

**Included in 1.11.2:** learned writer fallback requires
`CPU_LLM_ALLOW_LEARNED_WRITER=1`; HTTP bodies are capped at 1 MiB with a 10-second
socket inactivity timeout. Explicit child-safety controls warn that no pipeline
gate is applied; the standalone gate remains unvalidated. These changes extend 1.11.1. See the [hardening specification](docs/audit-hardening-spec.md).

Known limits include bounded English grammars, lexical topic matching, incomplete
aliases/joins and conflict detection. Hashes prove consistency with stored text,
not source authenticity or truth. Inspect response status, evidence and coverage
for the intended application.

## Documentation

- [Research planner and explicit cycle exploration](docs/research-cycle-user-guide.md).
- [Invention and CrossDomain](docs/taxonomy-invention-spec.md) and
  [numerical constraint evaluator](docs/invention-constraint-evaluator-spec.md).

- [1.11.1 release notes](docs/releases/1.11.1.md) and [build validation](docs/releases/1.11.1-build-validation.md).
- [Whitepaper](https://www.insightits.com/research-tools/cpu-llm/whitepaper) and [1.11.1 PDF](https://www.insightits.com/assets/whitepapers/cpu-llm-1.11.1-whitepaper.pdf).
- [Strict evidence](docs/strict-evidence-spec.md), [tone specification](docs/stylistic-generation-spec.md), [flag mapping](docs/prompt-flag-map.md).
- [Extended implementation reference](docs/reference/implementation-guide.md) and [release provenance](docs/release-publishing.md).

For citations: **cpu-llm: Evidence-Based AI Engine**, Amin Parva, repository URL,
and the exact version/commit evaluated. The Apache code label does not replace
bundled-data notices.
