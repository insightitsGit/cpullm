# cpu-llm

**A deterministic, CPU-native epistemic reasoning appliance. Mathematically verified answers and multi-agent synthesis from indexed corpora without GPUs or hallucination.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Runtime](https://img.shields.io/badge/runtime-CPU--only-2f9e7a)](src/cpu_llm/cpu_guard.py)
[![Architecture](https://img.shields.io/badge/architecture-neural--symbolic-8A2BE2)](docs/cpu-llm-v1.6.1-architecture-spec.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-orange)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-insightitsGit%2Fcpullm-181717?logo=github)](https://github.com/insightitsGit/cpullm)

> **One query in. An audited, mathematically verified assertion out.**
> Derived directly from stored epistemic propositions and verified against source evidence spans. Zero probabilistic token guessing, zero cloud APIs, zero GPU overhead.

**Author:** [Amin Parva](mailto:parvaamin@gmail.com) · **Retrieval plane:** [VectorPrism](https://github.com/insightitsGit/VectorPrism) · **Version:** 1.7.1

---

## Why cpu-llm?

Modern enterprise AI faces a hard reliability barrier: **probabilistic autoregressive models (LLMs) cannot provide mathematical guarantees against hallucination.** In regulatory compliance, medical informatics, financial reporting, and statutory law, a fluent generative model is an unmonitored liability.

`cpu-llm` is a neural-symbolic alternative. A frozen encoder stores each paragraph. The spoken sentence is rebuilt from a proposition cut out of that paragraph, and it is kept only when the rebuild matches the stored text and the auditor accepts it.

* **Deterministic semantic grounding.** `cpu-llm` does not sample a next-token distribution. It indexes paragraphs into 1024-dimensional tensors, cuts a proposition only when the realizer can repeat the paragraph's first sentence, and deliberates over that stored evidence. A paragraph that does not round-trip stays text. It is not given an invented triple.
* **Audited truth invariants.** The spoken sentence is checked by PrismShine and by `EpistemicEntailmentAuditor`. A failed check withholds the sentence. If no stored sentence states a cause, the reply says so. Discovery stays off until the caller passes `discover=True`.
* **Bare-metal CPU execution.** Retrieval and the six channel readings run on CPU. Startup clears `CUDA_VISIBLE_DEVICES` and refuses to continue if PyTorch was already imported with CUDA available. There is no Gemini client, no OpenAI client, and no decoder.

```text
stored paragraphs → VectorPrism 1024-d index
                 → cpu-llm ask
                 → checked sentence, plus any extra section the question asked for
```

```text
prompt → GPU chat model → free-form tokens
prompt → “CPU LLM” GGUF decode
```

The second picture is a different product.

### What this library is for

* **A checked sentence, not a sample.** The words a caller hears are a stored sentence the realizer can rebuild. The auditor and PrismShine see that sentence. They do not see a free-form completion.
* **One index for every source.** WikiText, the shipped artificial-intelligence primer, a PDF, a Word file, a spreadsheet, and paragraphs a developer already split land in the same pgvector index. A later question can hit any of them.
* **Agents that chain.** Deep search, creative writing, comparison, a brief (summarize, explain, list, cite), and math read what the earlier step kept. The checked sentence stays in front, except when the question is only a calculation.
* **A calculation of its own.** Addition, multiplication, percentages, roots, and a short list of numbers run in a math agent. The number is computed. It is not stored as a proposition.
* **Numbers that stay what they are.** A height in metres is not turned into money. A cause is quoted only when the paragraph already states one. A missing policy, target, or causal graph is left empty.
* **CPU, after one load.** On the measured machine, loading takes about 10 seconds. A question after that is 60–66 ms, and a deep search that keeps every match is about 0.6 s.

---

## Architectural workflow

```text
Query
  │
  ▼
PrismGuard (prompt check; a blocked prompt stops at the reply)
  │
  ▼
VectorPrism 1024-d index (dense core [16:384], HNSW ef_search 400, then a dense-core re-rank)
  │
  ▼
PrismResonance (dense-channel interference on that shortlist; the header is a timestamp, not a coordinate)
  │
  ▼
6-channel readings of the same shortlist
    Dense · Relational · Disentangled · Hyperbolic · Identity · Causal
  │
  ▼
PrismThinker (answer / gather / refuse / escalate)
  │
  ▼
PrismCognition + realizer + EpistemicEntailmentAuditor
  │
  ▼
PrismShine (retrieval trace and sentence gate; no external judge)
  │
  ▼
Optional agents, in this order: deep search → creative writing → comparison → brief → math → event frame
A document order replaces that reply with a stored format. See docs/cpu-llm-output-formats-and-scale.md.
  │
  ▼
Verified reply
  │
  ▼
Discovery only when ask(..., discover=True)
```

The prompt is encoded once. That same 1024-d tensor is the query for the scan and for every later channel. Think goes straight to cognize. Imagine is not inserted between them.

Only the dense channel was trained. Relational, disentangled, hyperbolic, and causal heads are still at initialization, and the identity anchor is unset. Those five readings are reported. They do not pick the passage. A quoted cause is not turned into a graph edge.

| Channel | What the node reports | Used to pick the passage |
|---------|----------------------|--------------------------|
| Dense | Cosine on the trained dense core `[16:384]` | Yes |
| Relational | A stored proposition that shares the prompt's words. Relation hands live in the tail `[480:512]` | No |
| Disentangled | Words that appear in only one passage | No |
| Hyperbolic | Poincaré distance, inside the open unit ball | No |
| Identity | Names and title tokens shared with the prompt | No |
| Causal | A sentence that already says *because*, *due to*, *caused*, or *therefore* | No |

PrismThinker can return `answer`, `gather`, `refuse`, or `escalate`. A gather result still realizes the grounded sentence when a proposition exists. The open questions stay on `gather_questions`. Its five head processes start with the appliance and are reused. They do not run two questions at once.

---

## What a question can ask

`answer` is the checked sentence. The reply prints that sentence first. Extra sections appear only when the question asked for them: summary, explanation, list, or sources, then comparison, then an imagined passage, then deep-search possibilities.

| Question | What runs | What the reply adds |
|----------|-----------|---------------------|
| What is the European lobster? | The fixed chain | The checked sentence |
| Deep search the European lobster. | Every tagged paragraph of the seeds, plus relation-hand neighbors | A possibility list. The checked sentence stays |
| Imagine the European lobster. | Stored sentences from the article, a different subset each run when more than one passed | An imagined passage after the checked sentence |
| Compare the European lobster and Robert Boulter. | Each side's own stored article or the paragraphs tagged with that side | A comparison. No invented "X differs from Y" sentence |
| Summarize the European lobster. | PrismCognition ranks stored sentences by epistemic weight, then by alignment to the question | Up to three sentences. A contradiction withholds the summary |
| Why is the European lobster fished with pots? | Only stored sentences that state a cause | An explanation, or "No stored sentence states a cause." |
| List the European lobster. | The same ranking, kept longer | Up to eight sentences |
| Cite sources for the European lobster. | The paragraph ids that were used | A source list |
| What is 17 times 24? | The math agent | The calculation. A question that is only arithmetic is answered with that result |
| What color was the apple John ate? | An event frame cut from a round-tripped sentence that matches the closed clause | The color, when that word is in the object. A missing color, a second color, a mismatched year, or a Shine rejection is spoken instead of a guessed color |
| Write an email about the late shipment. | A stored output format | That format's fields. The body is the retrieved sentences about the topic. A missing recipient stays unfilled |

Those agents chain. "Deep search and compare the European lobster and Robert Boulter" gathers first, then splits the kept paragraphs by topic. "Summarize that" with no new topic words reuses the previous turn's paragraph ids. A normal follow-up such as "what about the claws?" does not.

Creative writing runs when the prompt says imagine, what if, story, poem, fiction, or creative writing, or when `ask(..., imagine=True)`. One eligible sentence cannot vary. `answer` stays the checked sentence.

---

## The default corpus

Two sources ship inside the package.

**WikiText-2 raw**, the Salesforce validation and test splits. They are English Wikipedia articles that editors marked Good or Featured. The validation split is 60 articles and 1,841 paragraphs, stored under `wikitext2-`. The test split is a second set of articles with no shared title, stored under `wikitext2test-`. A proposition is stored only when the realizer can repeat the paragraph's first sentence. The rest stay text. License of that text: CC BY-SA 3.0 and GFDL, as stated in the provenance file next to the parquet. That license is the dataset's, separate from the Apache-2.0 license of this code.

**An original primer on artificial intelligence**, `src/cpu_llm/data/artificial-intelligence.md`, 70 paragraphs. It is text written for this package. It is not a copy of another textbook. Each paragraph's first sentence round-trips, so a question about search, learning, a transformer, or cpu-llm itself can be answered from those paragraphs. Its ids start with `artificial-intelligence-md-`, so loading it does not delete WikiText.

| Command | What it writes |
|---------|----------------|
| `cpu-llm-ingest` | WikiText validation, then the primer |
| `cpu-llm-ingest --textbook` | The primer only |
| `cpu-llm-ingest --test` | The WikiText test split only |

The same entry point is `python -m cpu_llm.ingest`.

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

A clean install works when those pins can be downloaded from PyPI. PrismAgenticPay 1.4.1 requires PrismThinker 1.2.0, and both are imported at startup.

### Ask

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

`catalog_chunks` is the lower-level call when you already have `(document_id, paragraph)` pairs. Leave `ObjectiveSpec`, policy rules, and causal edges empty unless you are supplying them. The appliance does not invent them from prose.

A two-page sample field guide, `samples/harbor-field-guide.pdf`, is the upload check: nine paragraphs go in, and a later question about the harbor kestrel or the marsh kite is answered from that file.

### Tests

```bash
python -m pytest
```

---

## For developers

The public entry point is `cpu_llm.pipeline.Appliance`. Construct it, ingest, ask, then close it. A `with` block closes the Thinker worker pool.

```python
from cpu_llm.documents import SourceDocument
from cpu_llm.pipeline import Appliance

with Appliance() as appliance:
    appliance.ingest(SourceDocument("notes", ("The harbor kestrel is a small coastal falcon.",)))
    result = appliance.ask("What is the harbor kestrel?")
```

`ask` accepts the question and these keyword arguments:

| Argument | Default | Effect |
|----------|---------|--------|
| `discover` | `False` | Runs the discovery loop. A why question does not turn this on |
| `imagine` | `False` | Forces creative writing |
| `deep` | `False` | Forces deep search |
| `math` | `False` | Forces the math agent |
| `propositions` | `None` | Overrides the stored propositions for this turn |
| `payment`, `authority` | both or neither | A payment turn needs both a proposal and an authority snapshot |
| `objective`, `hypothesis`, `causal_graph` | `None` | Caller-owned. The appliance does not invent them |

`ingest` accepts a path, a folder of accepted files, a `SourceDocument`, or a list of those. It returns `documents`, `chunks`, `ids`, and `connections`. Reading the same source again replaces rows whose ids share that source's prefix. `catalog_chunks` is the same write when the caller already has `(document_id, paragraph)` pairs. `sleep` refreshes relation tails on stored tensors.

A paragraph stores a proposition when its first sentence round-trips. The shapes that do are a copula or *have*: `The harbor kestrel is a small coastal falcon.` A sentence the realizer cannot repeat is stored as text and is not spoken.

File ids use the file stem: `harbor-field-guide.pdf` becomes `harbor-field-guide-p0001`. A name that still includes its suffix, such as `artificial-intelligence.md`, keeps that suffix in the slug.

Read these fields on the result. The graph also returns the channel readings and the Thinker trace. The spoken string is `reply["text"]`.

| Field | What it is |
|-------|------------|
| `answer` | The checked sentence. Shine and the auditor see this |
| `reply["text"]` | That sentence, then Summary, Explanation, List, Sources, Comparison, Imagined passage, and Possibilities, in that order, and only when that section was asked for |
| `audit_passed` | Whether the auditor accepted the realized sentence |
| `thinker_directive`, `gather_questions` | Sufficiency: answer, gather, refuse, or escalate, plus the gaps |
| `related` | The shortlist. Each item has a `chunk_id` |
| `possibilities`, `possibility_count` | Present after deep search |
| `comparison` | Per-side stored sentences |
| `imagination` | The creative passage. `answer` is unchanged |
| `math_result` | The calculated value. It is not an audited proposition |
| `brief` | Summary, explanation, list, and source ids |

`reply` also carries `preface`, `follow_ups`, and `next_steps` for the caller. Those strings are not written into `reply["text"]`.

---

## Runtime

cpu-llm runs on a CPU. It does not use a GPU.

| Requirement | This release |
|-------------|----------------|
| Python | 3.11 or newer |
| Processor | A 64-bit CPU. No CUDA device |
| Encoder | `sentence-transformers/all-mpnet-base-v2`, about 418 MiB, downloaded on first use and run on the CPU |
| Checkpoint | `vectorprism.pt`, about 3.6 MB, shipped inside the package |
| Database | PostgreSQL 16 with the `vector` extension |
| Questions | One `ask` at a time on the calling thread |

### Measured latency

These times are from one machine on 13 October 2026: an Intel Core Ultra 9 275HX with 24 cores and 64 GB of RAM, Windows 11, Python 3.12. One appliance, three runs of each prompt, after the model was already loaded and after one warmup question. Load time is not included in the question times.

Starting the appliance took 9.8 seconds on the six-mode run and 10.2 seconds on the deep-search rerun. The warmup question took 233 ms. After that load, every measured question finished in under a second.

| Mode | Prompt | Median | Three runs |
|------|--------|--------|------------|
| Normal | What is the European lobster? | 66 ms | 83, 56, 66 |
| Explain | Why is the European lobster fished with pots? | 60 ms | 87, 60, 59 |
| Summarize | Summarize the European lobster. | 63 ms | 72, 60, 63 |
| Compare | Compare the European lobster and Robert Boulter. | 61 ms | 87, 61, 61 |
| Creative | Imagine the European lobster. | 66 ms | 67, 66, 66 |
| Deep search | Deep search the European lobster. | 593 ms | 577, 593, 629 |

Deep search kept 582 possibilities and wrote a 32,639-character reply. Creative writing returned a different passage on each run. Ingesting a two-sentence note took 4.50 s, then 2.07 s, then 2.40 s, because each paragraph is encoded.

This machine is the one that was measured. It is not a minimum specification.

### Next release

The next release is working on serving multiple threads, so one process can answer concurrent questions under heavy load. This release keeps each question on the calling thread.

---

## Numeric spans

`amount_min` is set only from a money span.

| Written span | Recorded as |
|--------------|-------------|
| `4,399 m` | Length in metres. Not money |
| `14,440 feet`, `14,440-foot` | Length in feet |
| `10 million`, `exceeds 10 million`, `five million` | `amount_min = 10000000` or `5000000` |
| `$5 m`, `£ 1.7 million` | Money, scaled by one million |
| `28 million years`, `15 million copies` | Not money. The noun is what was counted |
| `4,399 m` and `$ 10 million` in one paragraph | Length and money, both kept |

A height in the retrieved text can still select PrismThinker's empirical regime. The threshold and the causal graph stay empty until the caller supplies them.

---

## What this package does not do

It does not rewrite a passage in a new style, translate it, write code, or pick a winner the store does not state. A named document format lays retrieved sentences into that format. It does not invent the body. It does not expose an HTTP upload API or a per-customer tenant. The tenant on this appliance is `cpu-llm`, and every source shares one pgvector index. A paragraph that does not round-trip is stored and can be retrieved. It is not spoken. Another engine is a separate seat in `EngineManager`. `ask` itself still runs one thinker turn.

---

## Structure

```text
cpu-llm/
  pyproject.toml                              package metadata, pins, cpu-llm-ingest script
  LICENSE                                     Apache-2.0, Copyright 2026 Amin Parva
  README.md
  src/cpu_llm/
    pipeline.py                               Appliance: ask, ingest, catalog_chunks, sleep
    ingest.py                                 WikiText and the primer loader
    documents.py                              file, folder, and spreadsheet readers
    source.py                                 paragraph cuts for the shipped sources
    retrieval.py                              VectorPrism encode, search, default checkpoint
    clauses.py                                first-sentence propositions
    realizer/                                 controlled English from a proposition
    audit/                                    EpistemicEntailmentAuditor
    cognition/                                PrismCognition deliberation adapter
    agents/                                   deep_search, gather, imagine, summarize, math, reply, discovery
    memory/frames.py                          event roles cut from a round-tripped sentence
    formats.py                                output-format catalog, stored in PrismCortex
    format_sense.py                           paraphrase trigger, cached in ChorusGraph
    scale.py                                  chunk bytes, scale order, engine manager
    comparison.py                             two-topic split
    classifier.py                             which optional agent the prompt asked for
    channels.py                               six readings and the detail template
    measurements.py                           lengths, money spans, qualifiers
    relations.py                              word edges and relation hands
    word_taxonomy.py                          word → article → paragraph index
    taxonomy.py                               tags written beside a chunk
    thinker_pool.py                           five Thinker heads, started once
    assembly.py                               which stored sentences are realized together
    manifest_spans.py                         numbers in the answer must occur in the passages
    cpu_guard.py                              refuse an already-initialized CUDA runtime
    checkpoints/vectorprism.pt                trained projection shipped in the package
    data/wikitext-2-raw-v1/                   shipped WikiText parquet files
    data/artificial-intelligence.md          shipped primer, 70 paragraphs
  tests/                                      the suite, including the PDF upload check
  samples/harbor-field-guide.pdf              two-page field guide used as an upload example
  docs/cpu-llm-white-paper.md                 technical white paper
  docs/cpu-llm-v1.8-semantic-memory.md        stage 1 of span-grounded event memory
  docs/cpu-llm-v1.9-realizer.md               final wording design: rank licensed constructions
  docs/cpu-llm-v1.8-copy-realizer.md          review record: sentence copy from retrieved roles
  docs/cpu-llm-v1.9-evidence-conditioned-realizer-proposal.md
                                                review record: claim plan and constrained actions
  docs/cpu-llm-v1.6.1-architecture-spec.md
  docs/cpu-llm-output-formats-and-scale.md    document formats, semantic trigger, and scale
```

`cpu-llm-ingest` is the console script for `python -m cpu_llm.ingest`.

---

## Author

**Amin Parva**, AI Architect & Staff Applied AI Engineer, wrote cpu-llm.

- Email: [parvaamin@gmail.com](mailto:parvaamin@gmail.com)
- Repository: [https://github.com/insightitsGit/cpullm](https://github.com/insightitsGit/cpullm)
- Retrieval plane: [VectorPrism](https://github.com/insightitsGit/VectorPrism)

---

## Citation

```bibtex
@software{cpullm2026,
  title  = {cpu-llm: A Deterministic CPU Epistemic Text Engine on VectorPrism},
  author = {Amin Parva},
  year   = {2026},
  url    = {https://github.com/insightitsGit/cpullm},
  license = {Apache-2.0}
}
```

---

## Links

- Author: **Amin Parva**, AI Architect & Staff Applied AI Engineer ([parvaamin@gmail.com](mailto:parvaamin@gmail.com))
- White paper: [docs/cpu-llm-white-paper.md](docs/cpu-llm-white-paper.md)
- Design v1.8, stage 1: [docs/cpu-llm-v1.8-semantic-memory.md](docs/cpu-llm-v1.8-semantic-memory.md)
- Design v1.9, the realizer (final, not built): [docs/cpu-llm-v1.9-realizer.md](docs/cpu-llm-v1.9-realizer.md)
- Design v1.8, copy realizer (review record): [docs/cpu-llm-v1.8-copy-realizer.md](docs/cpu-llm-v1.8-copy-realizer.md)
- Design v1.9, evidence-conditioned proposal (review record): [docs/cpu-llm-v1.9-evidence-conditioned-realizer-proposal.md](docs/cpu-llm-v1.9-evidence-conditioned-realizer-proposal.md)
- This repository: [https://github.com/insightitsGit/cpullm](https://github.com/insightitsGit/cpullm)
- Retrieval engine: [https://github.com/insightitsGit/VectorPrism](https://github.com/insightitsGit/VectorPrism)
- License: [Apache License 2.0](LICENSE)
