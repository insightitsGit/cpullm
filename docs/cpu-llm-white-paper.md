# Technical White Paper: cpu-llm

**A Deterministic, Pure-CPU Epistemic Reasoning Appliance Operating Over Grounded Subspace Manifolds**

**Author:** Amin Parva (AI Architect & Staff Applied AI Engineer)

**Retrieval & Representation Substrate:** VectorPrism (PSM 1024-d Tensor Architecture)

**Target Runtime:** Commodity CPU, PostgreSQL (`pgvector`), Python 3.11+

**Repository:** [https://github.com/insightitsGit/cpullm](https://github.com/insightitsGit/cpullm)

**Package:** [cpu-llm 1.7.1](https://pypi.org/project/cpu-llm/1.7.1/)

---

## Executive Summary

Autoregressive transformer language models formulate textual synthesis as probabilistic token sampling conditioned on previous context. That formulation has a structural failure mode in applications that need a source for every claim: a fluent continuation can state something the retrieved text does not say.

`cpu-llm` is a different appliance. It runs on a CPU. It does not sample a next token, and it does not call a decoder. A frozen encoder stores each paragraph as a 1024-dimensional VectorPrism tensor. A proposition is cut only when the realizer can repeat that paragraph's first sentence. The sentence a caller hears is that rebuilt sentence, and it is kept only when PrismShine and `EpistemicEntailmentAuditor` accept it.

A missing cause, policy, target, or causal graph stays empty. Discovery stays off until the caller passes `discover=True`.

```text
stored paragraphs → VectorPrism 1024-d index
                 → cpu-llm ask
                 → checked sentence, plus any extra section the question asked for

prompt → GPU chat model → free-form tokens
prompt → a local GGUF decode
```

The second picture is a different product.

---

## 1. Architectural Principles

### 1. A sentence is spoken only when it can be rebuilt

* No proposition is minted from a `{category}:{term}` tag.
* A proposition is stored only when the surface realizer can repeat the paragraph's first sentence.
* A paragraph that does not round-trip stays searchable text. It is not given an invented triple.
* PrismShine and `EpistemicEntailmentAuditor` see the rebuilt sentence. A failed check withholds it.
* Numbers in that sentence must occur in the retrieved passages (`state["manifest_spans"]`).

### 2. The search rank is a contiguous CPU array

* Retrieval, resonance, and the channel readings operate on NumPy arrays.
* The process clears `CUDA_VISIBLE_DEVICES` at startup and refuses to continue if PyTorch was already imported with CUDA available.
* There is no Gemini client, no OpenAI client, and no decoder.

### 3. A gap stays a gap

* `PrismCognition` can return `needs_evidence_propositions` when a retrieved paragraph was not stored as a proposition. The reply then quotes the closest passage and says so.
* When deliberation abstains, the proposition is negative: the system does not possess sufficient verified evidence.
* Missing parameters are surfaced as gather questions, including `no numeric threshold on hypothesis or objective` and `causal_graph is required`. Those questions are not filled in from the prose.

---

## 2. Representation Layer: Positional Subspace Multiplexing (PSM)

Each stored vector is 1024 contiguous floats. VectorPrism assigns fixed slices:

```text
┌─────────┬───────────────────┬─────────────┬──────────────┬──────────────┬──────────────┬─────────────┐
│ Header  │    Dense Core     │ Relational  │ Disentangled │  Hyperbolic  │   Identity   │   Causal    │
│ [0:16]  │    [16:384]       │  [384:512]  │  [512:640]   │  [640:768]   │  [768:896]   │  [896:1024] │
└─────────┴───────────────────┴─────────────┴──────────────┴──────────────┴──────────────┴─────────────┘
```

1. **Header (`[0:16]`).** Packed tensor metadata. Slots 3 and 4 hold a timestamp. The header is not an embedding, and it is not part of the resonance amplitude. The shipped checkpoint's header bitmask is 17: the dense channel and the identity channel are on.
2. **Dense core (`[16:384]`).** The trained search rank. It is the normalized projection of a frozen `sentence-transformers/all-mpnet-base-v2` embedding. pgvector search uses this slice, then cpu-llm re-ranks the shortlist on the same core.
3. **Relational (`[384:512]`).** The shipped checkpoint leaves this head off, so the slice is not a search rank. Indexing still writes a length-0.05 signature into the tail 32 slots (`[480:512]`) from the relation hands (`apply_relation_signature`). The rest of the channel stays as VectorPrism stored it.
4. **Disentangled (`[512:640]`).** Off in the shipped checkpoint. When a head is off, its slice is not used as a rank. The channel node still records the reading.
5. **Hyperbolic (`[640:768]`).** Off in the shipped checkpoint. Poincaré distance is still checked, and only for points inside the open unit ball:

$$d_{\mathbb{D}}(u, v) = \operatorname{arcosh}\left(1 + 2 \frac{\lVert u - v \rVert^2}{(1 - \lVert u \rVert^2)(1 - \lVert v \rVert^2)}\right)$$

6. **Identity (`[768:896]`).** On in the shipped checkpoint. This reading tracks a shared name or title in the retrieved passage.
7. **Causal (`[896:1024]`).** Off in the shipped checkpoint. A cause is spoken only when a retrieved sentence already states one (`because`, `due to`, `caused`, `therefore`).

---

## 3. Ingestion

`Appliance.ingest` and the `cpu-llm-ingest` console script write into one pgvector index. The tenant on this appliance is `cpu-llm`.

Accepted files are `.txt`, `.md`, `.html`, `.pdf`, `.docx`, `.csv`, `.xlsx`, `.xlsm`, and `.epub`. Legacy `.doc`, `.xls`, and `.ppt` are refused. A spreadsheet whose headers name two ends of a connection stores a paragraph and those edges.

```text
Raw document or paragraph
        │
        ▼
Document splitter
        │
        ▼
VectorPrism PSM encoding  →  1024-d tensor in pgvector
        │
        ▼
First-sentence proposition cut
        │
        ├── round-trip succeeds → attributes["proposition"]
        └── round-trip fails    → searchable text, no minted proposition
```

Lexical tags are stored beside the chunk and registered with PrismResonance on the dense slice `[16:384]`. They are candidate recall keys. They are not turned into propositions at query time.

The package ships two corpora. WikiText-2 validation uses the prefix `wikitext2-`. The original artificial-intelligence primer is `src/cpu_llm/data/artificial-intelligence.md`, 70 paragraphs, prefix `artificial-intelligence-md-`. WikiText remains under CC BY-SA 3.0 and GFDL. The code is Apache-2.0.

A file id uses the stem. `harbor-field-guide.pdf` is stored as `harbor-field-guide-p0001`, not with the suffix repeated.

---

## 4. Query-Time Execution

ChorusGraph in `src/cpu_llm/pipeline.py` orders one turn. The prompt is encoded once. That same 1024-d tensor is the query for the scan and for every later channel. Think goes straight to cognize. Imagine is not inserted between them.

```text
guard → retrieve → resonate
     → dense → relational → disentangled → hyperbolic → identity → causal
     → catalog → detail → spans
     → think → cognize → grammar → shine
     → deep → creative (gather → imagine) → compare → brief → math
     → reply
     → discover only when ask(..., discover=True)
```

A blocked guard stops at the reply. A blocked delivery skips the optional agents, including math.

| Step | What it does |
|------|----------------|
| guard | PrismGuard checks the prompt. |
| retrieve | pgvector HNSW, `ef_search` 400, `top_k` 5, then a dense-core re-rank. Not IVFFlat. |
| resonate | PrismResonance ranks the shortlist by dense-channel interference. |
| channels | Six readings of that same shortlist. Dense cosine is the trained rank. |
| catalog | Labels each chunk with the article slug already in its document id. |
| detail | Writes the six readings into one template. It does not add a sentence. |
| spans | PrismManifest keeps numeric tokens that were cut from the retrieved chunks. |
| think | PrismThinker names answer, gather, refuse, or escalate. Five heads start with the appliance and are reused. |
| cognize | PrismCognition deliberates over stored propositions. |
| grammar | The realizer compiles one clause per proposition. |
| shine | PrismShine checks the retrieval trace and the sentence. The external judge stays off. |
| agents | Optional, and only when the prompt or the caller asked. Order: deep search, creative writing, comparison, brief, math. |
| reply | The checked sentence, plus any section those agents produced. |
| discover | Off unless `ask(..., discover=True)`. |

---

## 5. Agents

Each optional agent is a deterministic step over stored text. None of them samples a continuation.

| Agent | What it does | What it refuses |
|-------|----------------|-----------------|
| Direct answer | Realizes the checked sentence from a stored proposition. | A sentence the realizer cannot rebuild, or a number absent from the passages. |
| Deep search | Keeps every paragraph of the prompt's content-word seeds, then every paragraph reached through one, two, and three relation hands. | It does not replace the checked sentence, and it does not change stored vectors. |
| Comparison | Splits the retrieved paragraphs by the named topics. | It does not walk relation hands, and it does not invent a contrast the store does not state. |
| Brief | PrismCognition ranks stored sentences. Summarize keeps 3. A list keeps 8. Explain keeps a sentence that already states a cause. Sources names the paragraph ids. | A contradiction whose ruin distance is at least 1 withholds the summary. |
| Imagine | Realizes a varying subset of stored sentences from the gathered article. The same prompt does not have to return the same passage. | A sentence that was not in the article. |
| Math | Evaluates the arithmetic the prompt writes, with decimal arithmetic and an expression tree. No `eval()`. | A year, a measurement, or a comparison does not enter this node. The number is not stored as a proposition. |

When math is the only optional agent, `reply["text"]` is the calculation. `answer` remains the checked sentence. When another agent also ran, the checked sentence stays and a `Math:` section is appended.

---

## 6. Numeric Spans

`amount_min` is set only from a money span. A length is not money.

| Written span | Recorded as |
|--------------|-------------|
| `4,399 m` | Length in metres |
| `14,440 feet`, `14,440-foot` | Length in feet |
| `10 million`, `five million` | `amount_min` of 10000000 or 5000000 when the span is money-shaped |
| `$5 m`, `£ 1.7 million`, `CZK 8 million` | Money, scaled |
| `20 million men`, `28 million years`, `15 million copies` | The noun is what was counted. Not money |
| `4,399 m` and `$ 10 million` in one paragraph | Length and money, both kept |

A height in the retrieved text can still select PrismThinker's empirical regime. The threshold and the causal graph stay empty until the caller supplies them.

---

## 7. Measured Latency

These times are from one machine on 13 October 2026: an Intel Core Ultra 9 275HX, 24 cores, 64 GB of RAM, Windows 11, Python 3.12.10. One appliance, three runs of each prompt, after the model was already loaded and after one warmup question. Load time is not included in the question times. Per-stage timings were not measured separately.

Starting the appliance took 9.8 seconds on the six-mode run and 10.2 seconds on the deep-search rerun. The warmup question took 233 ms.

| Mode | Prompt | Median | Three runs |
|------|--------|--------|------------|
| Normal | What is the European lobster? | 66 ms | 83, 56, 66 |
| Explain | Why is the European lobster fished with pots? | 60 ms | 87, 60, 59 |
| Summarize | Summarize the European lobster. | 63 ms | 72, 60, 63 |
| Compare | Compare the European lobster and Robert Boulter. | 61 ms | 87, 61, 61 |
| Creative | Imagine the European lobster. | 66 ms | 67, 66, 66 |
| Deep search | Deep search the European lobster. | 593 ms | 577, 593, 629 |

Deep search kept 582 possibilities and wrote a 32,639-character reply. Ingesting a two-sentence note took 4.50 s, then 2.07 s, then 2.40 s, because each paragraph is encoded. The encoder cache is about 418 MiB. The shipped checkpoint is about 3.6 MB.

This machine is the one that was measured. It is not a minimum specification. This release answers one question at a time on the calling thread.

---

## 8. What the Appliance Is For

The design is aimed at callers who need a sentence they can trace to a stored paragraph: policy text, a formulary, a field manual, or any corpus the operator ingested. It does not rewrite a passage, translate it, write code, or pick a winner the store does not state. It does not expose an HTTP upload API or a per-customer tenant. Every source shares one pgvector index.

---

## 9. License and Next Release

The code is Apache-2.0, Copyright 2026 Amin Parva.

The next release is working on serving multiple threads, so one process can answer concurrent questions. This release does not do that. It also does not add a bilinear relation operator, a neural coreference model, or an extra modality between the stored propositions and the spoken sentence.

**Code:** [https://github.com/insightitsGit/cpullm](https://github.com/insightitsGit/cpullm)

**Contact:** [parvaamin@gmail.com](mailto:parvaamin@gmail.com)
