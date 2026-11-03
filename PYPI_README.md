# cpu-llm 1.11.1

**Evidence-Based AI Engine.** A CPU-first Python library for questions about your documents and explicit
rules. It combines trained retrieval with bounded verified sentence construction,
structured finance checks, source evidence and explicit nonanswers. It is not
an unrestricted conversational or clinical decision model.

## Included in this release

- HTTP requests execute on one serving thread, preserving cached SQLite/graph ownership across clients. Connections close after responses. This corrects the 1.11.0 threaded-service defect.

- A shared evidence-backed report/article/design-document workflow with
  section coverage, exact source proofs, formats and bounded continuation.
- Prompt-triggered tone: `Write a detailed article about Helios in a friendly tone.`
  Tone is a presentation control, not a phrase required in the knowledge base.
- New technical prose from supported source predicates, with independent inverse
  verification. Unsupported/conditional records remain attributed quotations;
  missing design sections stay missing. Strict documents keep quotation-only output.
- Strict evidence policy v3: source quotations, recognized conflict checks,
  bounded batches/joins, exact arithmetic and explicit unsupported outcomes.
- A reviewed default conversation pack: eight basic intents, 51 phrases,
  original application identity/help, controlled variants and disable controls.
- A verified stylistic companion node for five factual relations. It retains
  accepted claims/proofs; unsupported expressive tones can use neutral fallback.
- Prompt interpretation, request separation, clarification, response budgets,
  source permissions, numeric precision fixes and Markdown/HTML output layouts.
- RefundProof, LedgerCovenant and Ledgerlock supplied-field checks.
- The trained VectorPrism projection, sample corpora, conversation pack and
  fictional healthcare/conversation demo datasets.
- Installed demo and conversation-candidate commands; no repository clone or
  Git executable is needed for those commands.

## Install and prepare

After this version has been published:

```shell
python -m pip install "cpu-llm==1.11.1"
```

Before asking document questions, configure PostgreSQL with pgvector and set
`VECTORPRISM_PG_DSN`. The package includes the trained projection; the pretrained
`sentence-transformers/all-mpnet-base-v2` encoder assets must also be downloaded
on first use or cached for offline use. Installation does not start PostgreSQL
or ingest your documents. No retraining is needed for the bundled demos.

Prepare the encoder while connected (set cache variables before Python starts):

```sh
export HF_HOME="$PWD/model-cache"
export HF_HUB_CACHE="$HF_HOME/hub"
python -c "import pyarrow; from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-mpnet-base-v2', device='cpu')"
```

For deployment, transfer the complete cache and set `HF_HUB_OFFLINE=1` and
`TRANSFORMERS_OFFLINE=1`. On PowerShell use `$env:HF_HOME = Join-Path $PWD 'model-cache'`
and `$env:HF_HUB_CACHE = Join-Path $env:HF_HOME 'hub'` instead of `export`.
See [offline setup](https://github.com/insightitsGit/cpullm/blob/main/docs/offline-setup.md)
for verification and optional-model limits. A repository checkout also supplies
`docker compose up -d --wait postgres`; see
[database setup](https://github.com/insightitsGit/cpullm/blob/main/docs/development-database.md)
for matching connection strings. The source server contract is documented in
[OpenAPI](https://github.com/insightitsGit/cpullm/blob/main/docs/openapi.json).

For optional spaCy prompt parsing, install `cpu-llm[prompt_nlp]==1.11.1` and
provision `en_core_web_sm`. The examples below use the built-in rules parser.

```python
from cpu_llm.documents import SourceDocument
from cpu_llm.pipeline import Appliance

def main():
    with Appliance(namespace="my_demo", strict_evidence=True,
                   prompt_backend="rules") as app:
        app.ingest(SourceDocument("manual", (
            "The material of Example Device is steel.",
        )))
        result = app.ask("What is the material of Example Device?")
        print(result["answer_status"])
        print(result["reply"]["text"])
        print(result["answer_evidence"])

if __name__ == "__main__":
    main()
```

Keep the guarded `main()` on Windows because the engine starts worker processes.
Reuse an appliance and close it after use. Production applications should use
authenticated caller contexts or the HTTP entry service for tenant/source scope.

## Run the packaged demos

With a demo database and cached encoder assets:

```shell
cpu-llm-demo healthcare --out healthcare-demo-new-run
cpu-llm-demo conversation --out conversation-demo-new-run
```

Each output directory must be new. The commands create isolated namespaces,
ingest packaged fictional records and save actual responses and expected-result
checks. Healthcare examples demonstrate label/record lookups, equivalent units,
conflicts, missing information, treatment refusal and arithmetic. Correct
nonanswers count as expected outcomes, not correct medical answers.

The candidate review tool is also installed:

```shell
cpu-llm-conversation-candidates --help
cpu-llm-serve --help
cpu-llm-ingest --help
```

## Response and safety boundaries

Use `answer_status`, evidence, per-task outcomes and structured calculation
fields together. A nonempty `reply.text` alone is not proof of correctness.
Default social replies have `response_kind="conversation"`, empty evidence and
no clinical validation. Disable them with `small_talk=False` or service
`--no-small-talk`. Pure conversational matching never replaces a substantive
healthcare/finance question with a greeting response.

Strict mode bypasses learned answer generators, including the automatic
fact-bridge FLAN-T5 fallback. It does not validate source truth, infer arbitrary
prose contradictions or guarantee 100% accuracy/clinical safety. Outside strict
mode, optional learned fallback paths can require additional model assets that
are not bundled. Coreferee, FastCoref and spaCy model assets are also not bundled.

Tone is opt-in through Python `style=...` or an explicit prompt directive.
API tone overrides prompt tone. Single-fact responses keep a companion; document
responses can publish verified derived prose while preserving source proofs and
the canonical quotation view. Neither gives source facts an independent truth
audit. Unsupported expressive styles can use neutral fallback. Strict mode
bypasses generated tone.
Financial checks operate on supplied fields/rules, not independently authenticated
documents or professional tax/legal advice. Fictional record lookup does not
establish diagnostic or prescribing capability.

## Documentation and real examples

- [Full guide and setup](https://github.com/insightitsGit/cpullm#readme)
- [Document and tone user manual](https://github.com/insightitsGit/cpullm/blob/main/docs/document-generation-user-guide.md)
- [Generated article and report](https://github.com/insightitsGit/cpullm/blob/main/docs/examples/2026-11-03-prompt-tone/README.md)
- [Strict evidence contract](https://github.com/insightitsGit/cpullm/blob/main/docs/strict-evidence-spec.md)
- [Healthcare sample chat](https://github.com/insightitsGit/cpullm/blob/main/examples/healthcare/sample-run/README.md)
- [Tone-node chat examples](https://github.com/insightitsGit/cpullm/blob/main/docs/examples/2026-11-02-tone-chat/TRANSCRIPT.md)
- [Default conversation examples](https://github.com/insightitsGit/cpullm/blob/main/docs/examples/2026-11-02-conversation/TRANSCRIPT.md)
- [Medical acceptance comparison](https://github.com/insightitsGit/cpullm/blob/main/docs/benchmarks/2026-11-02-medical-local/REPORT.md)

The project is Apache-2.0 licensed. The shipped default pack is original; external
dialogue corpora are not bundled. Dataset review tooling does not import external
assistant answers into the runtime or medical knowledge base.
