# cpu-llm

**A CPU epistemic text engine. It answers from paragraphs it has already stored.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![CPU](https://img.shields.io/badge/runtime-CPU--only-2f9e7a)](src/cpu_llm/cpu_guard.py)
[![GitHub](https://img.shields.io/badge/GitHub-insightitsGit%2Fcpullm-181717?logo=github)](https://github.com/insightitsGit/cpullm)

> One question in. A sentence rebuilt from a stored proposition and checked against the retrieved paragraphs. No decoder, no API key, no GPU.

**Author:** [Amin Parva](mailto:parvaamin@gmail.com), independent engineer · **Retrieval plane:** [VectorPrism](https://github.com/insightitsGit/VectorPrism)

---

## What cpu-llm is

cpu-llm is not a quantized chat model. A chat model writes the next token. cpu-llm retrieves a stored paragraph, rebuilds one sentence from a proposition cut out of that paragraph, and says that sentence only when the rebuild matches the stored text and the auditor accepts it.

The encoder is VectorPrism, frozen `all-mpnet-base-v2` plus the projection checkpoint, writing one 1024-dimensional tensor per paragraph into PostgreSQL with pgvector. Deliberation is PrismCognition. The turn graph is ChorusGraph. The sentence itself comes from the realizer in this package. If a paragraph does not round-trip, it stays in the index as text and is not given an invented triple.

```text
stored paragraphs → VectorPrism 1024-d index
                 → cpu-llm ask
                 → checked sentence, plus any extra section the question asked for
```

```text
prompt → GPU chat model → free-form tokens
prompt → “CPU LLM” GGUF decode
```

The second picture is a different product. There is no Gemini client, no OpenAI client, and no neural decoder in this package.

---

## What a question does

```text
prompt
  → PrismGuard
  → VectorPrism dense shortlist
  → PrismResonance on the dense core
  → six channel readings of that shortlist
  → PrismThinker
  → PrismCognition, the realizer, and the entailment auditor
  → PrismShine
  → optional agents, in this order: deep search, creative writing, comparison, brief
  → reply
  → discovery only when ask(..., discover=True)
```

A blocked prompt stops at the reply. Think goes straight to cognize. Imagine is not inserted between them.

The checked sentence is `answer`. The reply prints that sentence first. Extra sections are added only when the question asked for them, in this order: summary or explanation or list or sources, then comparison, then an imagined passage, then deep-search possibilities. Preface, follow-ups, and next steps are not spoken.

| Question | What runs | What the reply adds |
|----------|-----------|---------------------|
| What is the European lobster? | The fixed chain | The checked sentence only |
| Deep search the European lobster. | Every tagged paragraph of the seeds, plus relation-hand neighbors | A possibility list. The checked sentence stays |
| Imagine the European lobster. | Stored sentences from the article, a different subset each run | An imagined passage after the checked sentence |
| Compare the European lobster and Robert Boulter. | Each side's own stored article or tagged paragraphs | A comparison section. No invented "X differs from Y" sentence |
| Summarize the European lobster. | PrismCognition ranks the stored sentences | Up to three sentences. A contradiction withholds the summary |
| Why is the European lobster fished with pots? | Only stored sentences that state a cause | An explanation, or "No stored sentence states a cause." |
| List the European lobster. | The same ranking, kept longer | Up to eight sentences |
| Cite sources for the European lobster. | The paragraph ids that were used | A source list |

Those agents chain. "Deep search and compare the European lobster and Robert Boulter" gathers the possibilities first, then splits them by topic. "Summarize that" with no new topic words reuses the previous turn's paragraph ids. A normal follow-up such as "what about the claws?" does not.

Discovery stays off until `discover=True`. A why question does not turn it on.

---

## The default corpus

Two sources ship inside the package.

**WikiText-2 raw**, the Salesforce validation and test splits. They are English Wikipedia articles that editors marked Good or Featured. The validation split is 60 articles and 1,841 paragraphs, stored under `wikitext2-`. The test split is a second set of articles with no shared title, stored under `wikitext2test-`. A proposition is stored only when the realizer can repeat the paragraph's first sentence. The rest stay text. License of that text: CC BY-SA 3.0 and GFDL, as stated in the provenance file next to the parquet.

**An original primer on artificial intelligence**, `src/cpu_llm/data/artificial-intelligence.md`, 70 paragraphs. It is text written for this package. It is not a copy of another textbook. Each paragraph's first sentence is one the realizer can repeat, so a question about search, learning, a transformer, or cpu-llm itself can be answered from those paragraphs. Its ids start with `artificial-intelligence-md-`, so loading it does not delete WikiText.

```bash
cpu-llm-ingest
```

That command loads the WikiText validation split and then the primer. The same entry point is `python -m cpu_llm.ingest`.

| Command | What it writes |
|---------|----------------|
| `cpu-llm-ingest` | WikiText validation, then the primer |
| `cpu-llm-ingest --textbook` | The primer only. Use this when WikiText is already in the index |
| `cpu-llm-ingest --test` | The WikiText test split only |

---

## Install

Python 3.11 or newer. The GitHub repository is public. The package name on PyPI is `cpu-llm`. Install from a checkout:

```bash
git clone https://github.com/insightitsGit/cpullm.git
cd cpullm
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e .
```

`pip install -e .` installs the package, the trained checkpoint, the WikiText parquet files, and the primer. On Windows, import `pyarrow` before `torch` or VectorPrism. `cpu_llm.retrieval` already does that.

The appliance talks to PostgreSQL with the `vector` extension:

```text
image    pgvector/pgvector:pg16
port     localhost:5433
user     vectorprism
password vectorprism
database vectorprism
```

```text
postgresql://vectorprism:vectorprism@localhost:5433/vectorprism
```

`VECTORPRISM_PG_DSN` overrides that DSN.

Pinned libraries in `pyproject.toml`:

| Package | Role |
|---------|------|
| vectorprism 0.1.3 | 1024-d encode and dense-slice search |
| chorusgraph 1.3.0 | Turn graph |
| prismguard 0.1.10 | Prompt check |
| prismcognition 2.1.0 | Deliberation and summary ranking |
| prismrag-patch 0.2.1 | Article label from the document id |
| prismresonance 0.3.0 | Dense-core resonance |
| prismcortex 0.4.1 | Graph memory behind the sqlite store |
| prismmanifest 0.3.4 | Numeric span grammar on the CPU |
| prismshine 0.2.2 | Retrieval and sentence gate, judge off |
| prismthinker 1.2.0 | Sufficiency: answer, gather, refuse, escalate |
| prismagenticpay 1.4.1 | Payment check when both a proposal and an authority are passed |

A clean install works when those pins can be downloaded from PyPI. PrismThinker 1.2.0 and PrismAgenticPay 1.4.1 are both published. PrismAgenticPay 1.4.1 requires PrismThinker 1.2.0, and both are imported at startup.

---

## Runtime

cpu-llm runs on a CPU. It does not use a GPU. Startup clears `CUDA_VISIBLE_DEVICES`. If PyTorch was already imported and CUDA is available, the process refuses to continue.

| Requirement | This release |
|-------------|----------------|
| Python | 3.11 or newer |
| Processor | A 64-bit CPU. No CUDA device |
| Encoder | `sentence-transformers/all-mpnet-base-v2`, about 418 MiB, downloaded on first use and run on the CPU |
| Checkpoint | `vectorprism.pt`, about 3.6 MB, shipped inside the package |
| Database | PostgreSQL 16 with the `vector` extension |
| Questions | One `ask` at a time on the calling thread |

The five PrismThinker heads are separate processes, started once when the appliance loads. They do not let two questions run together.

### Measured latency

These times are from one machine on 13 October 2026: an Intel Core Ultra 9 275HX with 24 cores and 64 GB of RAM, Windows 11, Python 3.12. One appliance, three runs of each prompt, after the model was already loaded and after one warmup question. Load time is not included in the question times.

Starting the appliance took 9.8 seconds on the six-mode run and 10.2 seconds on the deep-search rerun. The warmup question took 233 ms.

| Mode | Prompt | Median | Three runs |
|------|--------|--------|------------|
| Normal | What is the European lobster? | 66 ms | 83, 56, 66 |
| Explain | Why is the European lobster fished with pots? | 60 ms | 87, 60, 59 |
| Summarize | Summarize the European lobster. | 63 ms | 72, 60, 63 |
| Compare | Compare the European lobster and Robert Boulter. | 61 ms | 87, 61, 61 |
| Creative | Imagine the European lobster. | 66 ms | 67, 66, 66 |
| Deep search | Deep search the European lobster. | 593 ms | 577, 593, 629 |

Deep search kept 582 possibilities and wrote a 32,639-character reply. Creative writing returned a different passage on each run. Ingesting a two-sentence note took 4.50 s, then 2.07 s, then 2.40 s, because each paragraph is encoded. A later upload of a 9-paragraph PDF stored every paragraph and answered from that file.

This machine is the one that was measured. It is not a minimum specification.

### Next release

The next release is working on serving multiple threads, so one process can answer concurrent questions under heavy load. This release keeps each question on the calling thread.

---

## Quickstart

Load the shipped sources, then ask.

```bash
cpu-llm-ingest
```

```python
from cpu_llm.pipeline import Appliance

with Appliance() as appliance:
    result = appliance.ask("What is artificial intelligence?")

print(result["answer"])
print(result["reply"]["text"])
```

`answer` is the checked sentence. Shine and the auditor see `answer` only.

### Index your own source

A source is a file, a folder, or paragraphs you already split. `ingest` stores those paragraphs in the same index, and a later `ask` reads them with the WikiText rows and the primer. Accepted files are `.txt`, `.md`, `.html`, `.pdf`, `.docx`, `.csv`, `.xlsx`, `.xlsm`, and `.epub`. A legacy `.doc` or `.xls` file is refused. Save it as `.docx` or `.xlsx`.

```python
from cpu_llm.documents import SourceDocument
from cpu_llm.pipeline import Appliance

guide = SourceDocument(
    "field-guide",
    (
        "The European lobster is Homarus gammarus.",
        "Homarus gammarus is a species of clawed lobster.",
    ),
)

with Appliance() as appliance:
    appliance.ingest(guide)
    appliance.ingest("notes/lobster.pdf")
    appliance.ingest("notes")
    result = appliance.ask("What is the European lobster?")
```

Reading the same source again replaces that source's paragraphs. A spreadsheet with `from` and `to` columns stores each row as a paragraph and stores the pair as a connection. Other sheets become `column: value` rows and do not invent a connection.

`catalog_chunks` is the lower-level call when you already have `(document_id, paragraph)` pairs. Pass `propositions=` when you already have an `EIRProposition` whose subject and object are slices of the chunk. `ask(..., propositions=...)` overrides that turn. The normal path reads the proposition stored with the chunk.

Leave `ObjectiveSpec`, policy rules, and causal edges empty unless you are supplying them. The appliance does not invent them from prose.

### Tests

```bash
python -m pytest
```

---

## How the checked sentence is chosen

VectorPrism searches once. The six channel nodes read that shortlist. They do not run six more database queries.

| Channel | What the node reports | Used to pick the passage |
|---------|----------------------|--------------------------|
| Dense | Cosine on the trained dense core | Yes |
| Relational | A stored proposition that shares the prompt's words | No |
| Disentangled | Words that appear in only one passage | No |
| Hyperbolic | Poincaré distance, inside the open unit ball | No |
| Identity | Names and title tokens shared with the prompt | No |
| Causal | A sentence that already says *because*, *due to*, *caused*, or *therefore* | No |

A quoted cause is not turned into a graph edge. The detail node prints all six. It does not replace the checked sentence.

The current checkpoint trained the dense channel. Relational, disentangled, hyperbolic, and causal heads are still at initialization. cpu-llm does not pretend those slices rank the search.

PrismThinker can return `answer`, `gather`, `refuse`, or `escalate`. A gather result still realizes the grounded sentence when a proposition exists. The open questions stay on `gather_questions`.

Creative writing runs when the prompt says imagine, what if, story, poem, fiction, or creative writing, or when `ask(..., imagine=True)`. It realizes stored sentences from the article and draws a different subset each time more than one sentence passed the auditor. One eligible sentence cannot vary. `answer` stays the checked sentence.

---

## Numeric spans

`amount_min` is set only from a money span.

| Written span | Recorded as |
|--------------|-------------|
| `4,399 m` | Length in metres. Not money |
| `14,440 feet`, `14,440-foot` | Length in feet |
| `10 million`, `exceeds 10 million`, `five million` | `amount_min = 10000000` or `5000000` |
| `$5 m`, `£ 1.7 million`, `CZK 8 million`, `$ 2.5 million in grants` | Money, scaled by one million |
| `28 million years`, `15 million copies`, `20 million men` | Not money. The noun is what was counted |
| `a viewership of 8.69 million` | Not money. The noun before `of` is what was counted |
| `4,399 m` and `$ 10 million` in one paragraph | Length and money, both kept |
| `. m` | Ignored. One bad paragraph does not drop the rest of the batch |

A height in the retrieved text can still select PrismThinker's empirical regime. The questions `no numeric threshold on hypothesis or objective` and `causal_graph is required` mean the caller did not supply those inputs. They are not a request for cpu-llm to invent a target.

---

## What this package does not do

It does not rewrite a passage in a new style, translate it, write code, or pick a winner the store does not state. It does not expose an HTTP upload API or a per-customer tenant. The tenant on this appliance is `cpu-llm`, and every source shares one pgvector index. Concurrent questions are the work of the next release.

A paragraph that does not round-trip is stored and can be retrieved. It is not spoken.

---

## Layout

```text
src/cpu_llm/pipeline.py                         turn graph and Appliance.ask / ingest
src/cpu_llm/checkpoints/vectorprism.pt          trained projection shipped in the package
src/cpu_llm/ingest.py                           WikiText and the primer loader
src/cpu_llm/data/wikitext-2-raw-v1/             shipped WikiText parquet files
src/cpu_llm/data/artificial-intelligence.md    shipped primer
src/cpu_llm/documents.py                        file, folder, and spreadsheet readers
src/cpu_llm/source.py                           paragraph cuts for the shipped sources
src/cpu_llm/clauses.py                          first-sentence propositions
src/cpu_llm/realizer/                           controlled English from a proposition
src/cpu_llm/audit/                              lexical entailment check
src/cpu_llm/cognition/                          deliberation adapter
src/cpu_llm/agents/                             deep search, creative writing, reply
src/cpu_llm/comparison.py                       two-topic split
src/cpu_llm/classifier.py                       which optional agent the prompt asked for
src/cpu_llm/measurements.py                     lengths, money spans, qualifiers
src/cpu_llm/channels.py                         six readings and the detail template
docs/cpu-llm-v1.6.1-architecture-spec.md
```

---

## Citation

```bibtex
@software{cpullm2026,
  title  = {cpu-llm: A CPU Epistemic Text Engine on VectorPrism},
  author = {Amin Parva, independent engineer},
  year   = {2026},
  url    = {https://github.com/insightitsGit/cpullm}
}
```

---

## Links

- Author: **Amin Parva**, independent engineer ([parvaamin@gmail.com](mailto:parvaamin@gmail.com))
- This repository: [https://github.com/insightitsGit/cpullm](https://github.com/insightitsGit/cpullm)
- Retrieval engine: [https://github.com/insightitsGit/VectorPrism](https://github.com/insightitsGit/VectorPrism)
