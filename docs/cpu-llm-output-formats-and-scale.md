# cpu-llm design: output formats, semantic trigger, and scale

**Status:** Implemented in this tree.

**Package:** 1.7.1 until a release is cut for this design. This document is the design version, not a PyPI version.

**Author:** Amin Parva (AI Architect & Staff Applied AI Engineer)

A request that names a document and a topic is not a free decoder. The layout comes from a stored format. The sentences in that layout come from the passages this turn already retrieved. A person, a date, or an attendee list is filled only when a retrieved passage states that role. A second value for the same role is reported as a conflict and is not chosen.

A plain question still ends on the checked sentence, the rule verdict, the event frame, or the calculation. A poem or a story stays on the creative path and is not turned into one of these formats.

---

## Formats

The catalog is `OUTPUT_FORMATS` in `src/cpu_llm/formats.py`.

| Id | Spoken name | Fields | Body |
| --- | --- | --- | --- |
| email | Email | To, From, Date, Subject | paragraphs |
| letter | Letter | Date, To, From, Subject | paragraphs |
| memo | Memo | To, From, Date, Subject | paragraphs |
| document | Document | Title | numbered sentences |
| report | Report | Title | findings, then sources |
| agenda | Agenda | Title, Date | numbered sentences |
| minutes | Minutes | Title, Attendees, Date | recorded sentences |
| notice | Notice | Title, Date | paragraphs |
| checklist | Checklist | Title | check boxes |
| faq | FAQ | Title | one question, then each stored answer |
| outline | Outline | Title | numbered sentences |
| status | Status update | Subject, Date | bullets |
| proposal | Proposal | Title, To | bullets |
| briefing | Briefing | Subject | bullets |
| essay | Essay | Title | paragraphs, then sources |
| article | Article | Title, By | paragraphs, then sources |
| blog | Blog post | Title | paragraphs |
| press | Press release | Title, Date | paragraphs |
| abstract | Abstract | Title | paragraphs |
| paper | Paper | Title | findings, then sources |
| case | Case study | Title | findings, then sources |
| newsletter | Newsletter | Title, Date | paragraphs |
| speech | Speech | Title | paragraphs |
| biography | Biography | Title | paragraphs |
| review | Review | Title | paragraphs |
| tutorial | Tutorial | Title | numbered sentences |
| procedure | Procedure | Title | numbered sentences |
| decision | Decision record | Title | bullets, then sources |
| incident | Incident report | Title, Date | findings, then sources |
| invitation | Invitation | To, Date, Subject | paragraphs |
| post | Post | Title | bullets |

The subject or title is the topic the user named. A blank role is the sentence "Not stated in the retrieved passages." A sentence is included only when it shares a content word with the topic. An unrelated retrieved passage is left out.

"Write an email" with no topic does not invent one. The reply names that format and lists every format with its fields. "Write about the late shipment" keeps the topic and asks which format.

`Appliance` writes each format into PrismCortex as one node. The id is `output-format:{id}`, the kind is `output_format`, and the embedding is empty. The attributes are the name, the aliases, a field bitmask, a one-letter body code, a source flag, and the catalog index. Retrieval skips nodes that have no embedding, and sleep skips `output_format` nodes. A second save writes nothing when that record is already stored.

---

## When a request is a document order

`parse_order` accepts a creation verb (`write`, `draft`, `compose`, `create`, `prepare`, `produce`, `send`, `make`) plus a format name and, when present, the topic after about, regarding, concerning, titled, on, of, or for.

A paraphrase that names a format but does not use those verbs goes to `FormatSense` in `src/cpu_llm/format_sense.py`. The encoder is the frozen retrieval encoder, `all-mpnet-base-v2`, already loaded by VectorPrism. It is not a second model. The comparison is between two readings that share the topic:

```text
Write an email about the late shipment.
What is the late shipment?
```

The request is that format only when the order reading is closer by at least **0.15**. That margin was measured on this encoder:

* "Put together an email about the late shipment." beat the question by 0.289.
* "Whip up a short essay regarding the docking delay." beat the question by 0.241.
* "What is an email?" lost by 0.707.
* "I need a writeup on the late shipment." never named a format and never cleared 0.15, so it is not assigned an essay or an article.

The decision is a row in `format_sense_cache` in the ChorusGraph sqlite file: tenant, request hash, format, topic, and gap. The same request does not encode again. Those rows are not passage embeddings.

`ask` runs this check after the prompt is encoded, and only when the exact parser found no order and the prompt is not creative writing. The graph state carries `draft_order`. The reply speaks the format instead of the checked sentence. A guard block and a Shine, audit, or grammar rejection stay as they are. A calculation that is the whole turn still wins.

---

## Scale

`src/cpu_llm/scale.py` counts capacity. It does not publish a timed benchmark.

One stored chunk is a 1024-d float32 tensor, **4096 bytes**, plus the UTF-8 text and the JSON ChorusGraph writes for that node. `chunk_footprint` measures that JSON. `performance_matrix` adds it up and says how many engines the stored bytes need, and whether the last engine fits on this machine.

One engine runs one thinker turn at a time. `WarmEvaluatorPool` holds its lock across the five heads, so those heads already run together for that one turn. A second waiting turn is another engine: five head processes plus the engine process. The next engine stays on this server only when `cpu_count` covers `engines * 6`. Otherwise the order says `other_server`.

`scale_order` returns `hold` or `add_engine`. Memory that is larger than the available physical bytes adds engines until each engine's share fits. A busy engine with a waiting turn adds one engine even when the bytes fit.

`EngineManager` is the balancer, in the same shape as PrismCortex: a read pool, a write pool, and a manager in front of the seats. The write side takes one turn at a time. The pools are `CPU_LLM_READ_POOL` and `CPU_LLM_WRITE_POOL`. A new seat on another machine is reached with `ChorusSpine`. The frame carries the chunk id, the text, the text size, and `tensor_bytes` 4096. The 64-wide fabric slot is the wire shape. It is not a reduced copy of the 1024-d tensor. The manager catalog is the shared list of which seat holds which chunk.

`python -m cpu_llm.scale` prints the matrix for a file, or for `--chunks N --bytes B`, using this machine's CPU count and available physical memory.

`Appliance.ask` does not itself open a second thinker pool. The manager is the control plane that records the order and ships the chunk frame.

---

## Checks

| Path | What it locks |
| --- | --- |
| `tests/test_formats.py` | Every format's fields, topic filtering, a missing topic, PrismCortex nodes with no embedding |
| `tests/test_format_sense.py` | The cache row, and the measured paraphrases and rejections on the real encoder |
| `tests/test_scale.py` | Counted bytes, same-server versus other-server placement, a fabric handoff, one write at a time |

Pipeline tests that construct `Appliance` against Postgres are a separate run. They need `localhost:5433`.
