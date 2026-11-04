# CPU-LLM: Evidence-Based AI Engine

**Deterministic Document Checks, Financial Covenant Verification & Evidence-Preserving Retrieval on Commodity CPUs.**

[![PyPI 1.11.2](https://img.shields.io/badge/PyPI-1.11.2-blue)](https://pypi.org/project/cpu-llm/1.11.2/)
[![Code license Apache 2.0](https://img.shields.io/badge/Code-Apache_2.0-green)](https://github.com/insightitsGit/cpullm/blob/main/LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://github.com/insightitsGit/cpullm/blob/main/pyproject.toml)

`cpu-llm` / `cpullm` is an embeddable Python engine for source-backed document
questions and explicit rule checks. It is intended for architects evaluating
controlled evidence workflows in financial compliance, private credit and
regulated enterprises, where unsupported answers, arithmetic errors and data
egress carry material risk.

Unlike unrestricted generative answering, its strict evidence path selects
quotations, executes recognized calculations or returns an explicit nonanswer.
This is a bounded evidence contract: it does not establish that a source is true,
that every question is understood, or that a deployment is compliant.

**This distribution: 1.11.2.** Use it instead of 1.11.0 for HTTP; it repairs a
cached-appliance SQLite thread-ownership defect. Author: **Amin Parva,
Independent Engineer**.

**Licenses:** code [Apache-2.0](https://github.com/insightitsGit/cpullm/blob/main/LICENSE); bundled WikiText-2 data has separate
**CC BY-SA 3.0/GFDL** terms and attribution. See [third-party notices](https://github.com/insightitsGit/cpullm/blob/main/THIRD_PARTY_NOTICES.md).

## Verification contract compared with generative RAG

This compares execution contracts, not measured product accuracy or cost.
Generative RAG systems can also add citations, calculators and deployment controls.

| Dimension | Generative RAG without an enforced verification layer | CPU-LLM contract |
| --- | --- | --- |
| Answer construction | Generated wording needs independent support checks | Strict mode returns source spans, recognized calculations, conflicts or nonanswers; unsupported forms return `unsupported` |
| Arithmetic | A generated numeric answer needs a calculator/checker | Explicit finance fields use inspectable decimal/integer policies; the example below uses six-place half-up rounding |
| Infrastructure | Depends on the chosen model and hosting | CPU-first Python plus PostgreSQL/pgvector and cached encoder assets; no GPU required for the documented path |
| Audit evidence | Depends on the application's evidence layer | Source IDs, quotation offsets and chunk hashes; supported tone constructions include inverse-verification receipts |
| Data location | Hosted or self-managed, depending on the system | Can run on premises with prepared dependencies and cached assets; air-gap enforcement is an operator responsibility |

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

The [recorded healthcare demo](https://github.com/insightitsGit/cpullm/blob/main/examples/healthcare/sample-run/README.md) shows:

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
[Strict grammar and limits](https://github.com/insightitsGit/cpullm/blob/main/docs/strict-evidence-spec.md).

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
[Article/report receipts](https://github.com/insightitsGit/cpullm/blob/main/docs/examples/2026-11-03-prompt-tone/README.md) ·
[Document and tone manual](https://github.com/insightitsGit/cpullm/blob/main/docs/document-generation-user-guide.md).

### Six-signal retrieval and explicit routing

The ordinary pipeline registers 27 graph nodes, including **dense, relational,
disentangled, hyperbolic, identity and causal** retrieval signals backed by
PostgreSQL/pgvector. **Only dense and identity projection heads are trained and
bundled**; the other channels use their implemented signals or symbolic paths.
A similarity score or connection is not factual proof. Strict requests and document
workflows can bypass the ordinary graph; not every request runs every node.
See the [architecture](https://github.com/insightitsGit/cpullm/blob/main/docs/current-design.md) and [prompt-to-node mapping](https://github.com/insightitsGit/cpullm/blob/main/docs/prompt-flag-map.md).

## Quickstart and reproduction

Python 3.11+ is required. Release checks used Windows/Python 3.12.10.

```shell
python -m pip install --upgrade "cpu-llm==1.11.2"
python -m pip check
```

Document queries require PostgreSQL/pgvector and the pretrained
`sentence-transformers/all-mpnet-base-v2` encoder assets. The trained projection
is bundled; no retraining is required for these demos. Follow the
[database setup](https://github.com/insightitsGit/cpullm/blob/main/docs/development-database.md) and [encoder preparation](https://github.com/insightitsGit/cpullm/blob/main/docs/offline-setup.md).
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

## Verification and deployment limits

The prepared 1.11.2 source run reports **925 passed, 56 skipped, 3 expected
failures**: 54 skips were disabled opt-in integration cases; two lacked optional
extractor checkpoints. See the [1.11.2 build validation](https://github.com/insightitsGit/cpullm/blob/main/docs/releases/1.11.2-build-validation.md). Separate installed-wheel checks covered strict/ordinary
HTTP and the healthcare demo's 12/12 authored outcomes.
[Commands, scope and receipts](https://github.com/insightitsGit/cpullm/blob/main/docs/testing-results.md). No independent clinical,
customer-corpus or hosted-model comparison establishes superiority.

The authenticated HTTP service exposes POST `/v1/ask`, `/v1/ingest`, `/v1/correct`
and `/v1/delete`. It serves requests serially; lazy factories must construct
appliances on the serving thread. There is no built-in TLS or production gateway,
and long work blocks other requests. See [OpenAPI](https://github.com/insightitsGit/cpullm/blob/main/docs/openapi.json) and the
[consumer guide](https://github.com/insightitsGit/cpullm/blob/main/docs/library-consumer-guide.md#authenticated-http-service).

**Included in 1.11.2:** learned writer fallback requires
`CPU_LLM_ALLOW_LEARNED_WRITER=1`; HTTP bodies are capped at 1 MiB with a 10-second
socket inactivity timeout. Explicit child-safety controls warn that no pipeline
gate is applied; the standalone gate remains unvalidated. These changes extend published 1.11.1. See the [hardening specification](https://github.com/insightitsGit/cpullm/blob/main/docs/audit-hardening-spec.md).

Known limits include bounded English grammars, lexical topic matching, incomplete
aliases/joins and conflict detection. Hashes prove consistency with stored text,
not source authenticity or truth. Inspect response status, evidence and coverage
for the intended application.

## Documentation

- [1.11.1 release notes](https://github.com/insightitsGit/cpullm/blob/main/docs/releases/1.11.1.md) and [build validation](https://github.com/insightitsGit/cpullm/blob/main/docs/releases/1.11.1-build-validation.md).
- [Whitepaper](https://www.insightits.com/research-tools/cpu-llm/whitepaper) and [1.11.1 PDF](https://www.insightits.com/assets/whitepapers/cpu-llm-1.11.1-whitepaper.pdf).
- [Strict evidence](https://github.com/insightitsGit/cpullm/blob/main/docs/strict-evidence-spec.md), [tone specification](https://github.com/insightitsGit/cpullm/blob/main/docs/stylistic-generation-spec.md), [flag mapping](https://github.com/insightitsGit/cpullm/blob/main/docs/prompt-flag-map.md).
- [Extended implementation reference](https://github.com/insightitsGit/cpullm/blob/main/docs/reference/implementation-guide.md) and [release provenance](https://github.com/insightitsGit/cpullm/blob/main/docs/release-publishing.md).

For citations: **cpu-llm: Evidence-Based AI Engine**, Amin Parva, repository URL,
and the exact version/commit evaluated. The Apache code label does not replace
bundled-data notices.
