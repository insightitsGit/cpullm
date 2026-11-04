# cpu-llm

**Evidence-Based AI Engine**

Answer questions from your documents and explicit rules, with source evidence
and CPU-first execution. **Published release: [1.11.1](https://pypi.org/project/cpu-llm/1.11.1/).**
Author: Amin Parva, Independent Engineer.

cpu-llm is an embeddable Python library combining document retrieval, bounded
sentence construction and explicit rule/calculation checks. It produces source
quotations, supported derived wording or explicit nonanswers for recognized
requests. Its name is the package name; it is not a general-purpose language model.

**Licensing:** code is [Apache-2.0](LICENSE). Bundled WikiText-2 text has separate
**CC BY-SA 3.0/GFDL** attribution and terms; see [third-party notices](THIRD_PARTY_NOTICES.md).

## Install and try

Python 3.11+ is required; release checks used Windows/Python 3.12.10.

```shell
python -m pip install --upgrade "cpu-llm==1.11.1"
python -m pip check
```

Before document queries, configure PostgreSQL with pgvector and set
`VECTORPRISM_PG_DSN`. Prepare the pretrained
`sentence-transformers/all-mpnet-base-v2` encoder assets. The trained projection
is bundled; demo use does not require retraining.

- [Database setup and matching connection strings](docs/development-database.md).
- [Encoder download, transferable cache and offline verification](docs/offline-setup.md).

The supplied Compose configuration validates, but its actual container launch
remains unverified on the maintainer's host because Docker Desktop crashes.
Recorded installed-package checks used native PostgreSQL 18/pgvector.

Once setup is complete, these installed commands ingest fictional demo records
and save responses, evidence and expected-outcome checks:

```shell
cpu-llm-demo healthcare --out healthcare-demo-new-run
cpu-llm-demo conversation --out conversation-demo-new-run
```

Use a new output directory each time. The healthcare demo includes supported
lookups, conflicts, missing data and treatment refusals; passing checks are
software-fixture outcomes, not clinical validation.

## Ask your documents

Run appliance construction under a main guard on Windows:

```python
from cpu_llm.pipeline import Appliance
from cpu_llm.documents import SourceDocument

def main():
    with Appliance(namespace="my_docs", prompt_backend="rules") as app:
        app.ingest(SourceDocument("helios-manual", (
            "Helios is a backup service.",
            "Helios stores encrypted backups.",
            "Helios uses PostgreSQL for metadata.",
            "Helios does not support automatic regional failover.",
        )))
        result = app.ask(
            "Write a detailed article about Helios in a friendly tone."
        )
        print(result["reply"]["text"])
        print(result.get("stylistic", {}).get("verification"))

if __name__ == "__main__":
    main()
```

The tone instruction is removed from the topic query; the KB does not need
friendly wording. Reviewed constructions can produce a new sentence such as
“Helios stores encrypted backups and uses PostgreSQL for metadata.” Original
source proofs remain available. Unsupported constructions remain attributed
quotations and missing document sections remain explicit.

[Document/tone manual](docs/document-generation-user-guide.md) ·
[Recorded article and report](docs/examples/2026-11-03-prompt-tone/README.md) ·
[Complete Python/HTTP consumer guide](docs/library-consumer-guide.md).

## Choose the evidence contract

- **Strict evidence:** use `strict_evidence=True` or the strict HTTP header.
  Recognized queries return quotations with provenance, bounded exact
  calculations, conflicts or nonanswers. Strict mode bypasses learned answer
  generation and tone rewriting. Source truth is not independently verified.
- **Ordinary requests:** support additional producers, document layouts and
  bounded verified tone constructions. Some optional FLAN-T5 fallback paths
  have different verification limits; there is no blanket “verified ordinary
  mode” or universal factual-accuracy claim.
- **Finance checks:** operate on supplied fields and explicit policies.
  Decimal arithmetic and decision precision are inspectable; these checks do
  not authenticate financial documents or establish professional approval.

The covenant boundary example uses raw `9000001/2000000 = 4.5000005`. Under its
explicit six-place half-up policy, the stored/displayed value is `4.500001`,
which breaches an `lte 4.500000` threshold. That is a bounded numeric-policy
check, not a claim that every finance question is understood.

Six retrieval signals exist: dense, relational, disentangled, hyperbolic,
identity and causal. **Only the dense and identity projection heads are trained
and bundled.** Channel signals and scores are not factual proof.

## HTTP and deployment

The authenticated stdlib server exposes POST `/v1/ask`, `/v1/ingest`,
`/v1/correct` and `/v1/delete`. See the [OpenAPI contract](docs/openapi.json)
and [credential/setup guide](docs/library-consumer-guide.md#authenticated-http-service).
The JSON file documents the API; the server does not serve Swagger/OpenAPI UI.

**Use 1.11.1 for HTTP.** It fixes 1.11.0's cached-appliance SQLite thread error.
Requests run serially on the serving thread and response connections close.
Lazy factories must construct appliances on that thread. The server has no
built-in TLS or production gateway controls, and slow work blocks later requests.
No production throughput or startup-latency guarantee is established.

## Evidence, tests and limits

The recorded 1.11.1 source run passed **905 tests**, skipped **56**, and retained
**3 existing expected failures**. Of the skips, **54 opt-in integration cases
were not enabled** and **2 lacked optional trained extractor checkpoints**.
Those 54 cases are not being represented as passed or as missing installed assets.

Separate installed-wheel checks verified strict and ordinary HTTP requests,
source scope and the packaged healthcare demo's 12/12 authored outcomes.
[Test-count explanation and receipts](docs/testing-results.md) distinguish these
from historical runs. There is no independent clinical, customer-corpus or
hosted-model comparison establishing general usefulness or superiority.

Known limits include bounded English grammars, lexical topic matching,
incomplete aliases/semantic joins, limited typed factual queries and conflict
detection, and no general creative or novel-architecture generation. Hashes prove
consistency with stored text, not authenticity or truth. Inspect actual output,
status, coverage and evidence for the intended application.

## Documentation

- [Published release notes](docs/releases/1.11.1.md) and [build validation](docs/releases/1.11.1-build-validation.md).
- [Current whitepaper](https://www.insightits.com/research-tools/cpu-llm/whitepaper) and [1.11.1 PDF](https://www.insightits.com/assets/whitepapers/cpu-llm-1.11.1-whitepaper.pdf).
- [Architecture](docs/current-design.md), [strict evidence](docs/strict-evidence-spec.md), [tone specification](docs/stylistic-generation-spec.md), and [flag mapping](docs/prompt-flag-map.md).
- [Extended implementation reference and historical observations](docs/reference/implementation-guide.md).
- [Release publishing and provenance](docs/release-publishing.md).

For citations, use **“cpu-llm: Evidence-Based AI Engine”**, by Amin Parva, with
the repository URL and the exact version/commit evaluated. Code is Apache-2.0;
that label does not replace the separate bundled-data notices.
