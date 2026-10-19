# cpu-llm design v1.8: span-grounded semantic memory

**Status:** Stage 1 is implemented in this tree. Stages 2 through 5 are not.

**Package:** 1.7.1 until a release is cut for this design. This document is the design version, not a PyPI version.

**Author:** Amin Parva (AI Architect & Staff Applied AI Engineer)

The 2026-10-15 discussion asked for a memory of entities, event roles, attributes, and provenance, so a question can be answered by joining those records on CPU. This design keeps that direction and keeps the rule the appliance already runs: a role is stored only when it is a slice of a sentence the realizer can repeat. A parsed graph is not allowed to say something the paragraph did not say.

The current retrieval path is unchanged for every other question. A plain question still ends on the checked sentence.

---

## What stage 1 stores

Stage 1 is `src/cpu_llm/memory/frames.py`. The record schema is `stage1-v2`. Offsets are relative to the sentence, not the whole chunk.

Ingest stores `event_frame` only when two checks both pass. The realizer must repeat the first sentence. That sentence must also be this clause, with nothing left over:

```text
subject verb object location? time?
object   = (a|an|the) color? noun
location = (in|at|on) (his|her|their|the|a|an|my|our|your) noun
time     = (in|on) YEAR | yesterday | today | tomorrow | tonight
```

A copula is `The|A|An noun` plus `is|are|was|were` plus one color word. The patient of an action is the noun inside the object span. A repeated noun in the subject does not supply that span. `The apple seller ate a yellow apple in his house.` keeps the object apple at sentence offsets 30:35.

These do not become frames: negation, a condition (`if`), a nested object (`a picture of the apple`), an extra attachment (`with Mary`), coordination, and a clause the grammar does not finish. Round-trip alone does not create a frame. There is no owner role.

The query uses the stored `event_frame` when its schema is `stage1-v2`. Otherwise it runs the same extractor on the retrieved paragraph. There is one extractor. The join still sees only the retrieved shortlist.

Supported questions, and only the whole question:

* `What color was the apple?`
* `What color was the apple John ate?`
* `What color was the apple John ate in 2019?`
* `In 2019, what color was the apple John ate?`
* `Where did John eat the apple?`
* `Who ate the apple?`

A year in the question is kept whether it is a prefix or a suffix. An undated sentence does not answer a dated question. A present sentence (`The apple is yellow.`) does not answer `What color was the apple?` The past copula answer keeps the source auxiliary, so `The apples were yellow.` stays plural.

`frame_result.status` is `answered`, `missing`, `ambiguous`, `conflicting`, `unsupported`, or `ignored`. `verified` is true only for an answered sentence whose role spans and permitted words were checked. `answer` stays the checked sentence. `audit_passed` on that sentence is not verification of `reply["text"]`. The node also sets `frame_verified`.

When the frame question is the only optional step, `reply["text"]` is the joined sentence or a visible non-answer. A missing color says so. Two colors conflict and name neither color. A question outside the supported form says it is unsupported. Another optional agent keeps the checked sentence and adds an `Event:` section.

A Shine rejection (`shine_ok` false or `shine_enforced`), an audit block, or a grammar block is the delivered text. The frame node is not routed, and a frame result already in the state cannot replace that text or add an `Event:` section.

`better`, `worse`, and a comparison do not enter this node. `eat` / `ate` / `eaten` is in the realizer's closed irregular list so the apple sentence can round-trip. The join is not stored as a new proposition.

---

## Worked record

Source: `John ate a yellow apple in his house.`

```text
agent:     John
predicate: ate          lemma eat, tense PAST
patient:   apple
color:     yellow
location:  in his house
time:      (none)
```

`What color was the apple John ate?` speaks `The apple John ate was yellow.`

`Where did John eat the apple?` speaks `John ate the apple in his house.`

It does not speak that John owns the house.

---

## Stages that are not built

| Stage | Work | Why it waits |
|-------|------|----------------|
| 2 | Negation, conditions, and uncertainty as their own frames, still tied to a span | Stage 1 drops a negated sentence. It does not answer "what did John not eat?" |
| 3 | One entity id across sentences and documents, with aliases | `John` in two paragraphs is still two subject strings. |
| 4 | A durable role index so the join is not limited to the retrieved shortlist | Stage 1 only sees passages the existing retrieval already returned. |
| 5 | Tenant boundaries, deletion, and corrections | The tenant remains the fixed string `cpu-llm`. |

These stay out of the engine until a stage needs them:

* A generative model at ingest or at phrasing time.
* Edges created because two vectors are near each other.
* A bilinear relation operator, neural coreference, or a new modality.
* Persian or any second language.
* Access-control lists, tombstones, and a GPU fallback.
* A comparison that picks a winner the store does not state.
* A larger embedding in place of the missing roles.

---

## How a later stage is accepted

A stage is accepted when a labeled set of passages, including the apple sentence, a negation, a time bound, a contradiction, and a comparison, shows:

* the joined answer's content words occur in the source sentence
* a missing role abstains
* a contradiction does not pick a side
* a plain question still ends on the checked sentence

The unit tests in `tests/test_frames.py` cover that contract for stage 1. They are not the full labeled-corpus study.

The wording model that follows this stage is [v1.9, the realizer](cpu-llm-v1.9-realizer.md). The non-neural plan and checker are implemented. No checkpoint is trained. The earlier pointer note and the evidence-conditioned proposal are the review record behind that file.

A request that names a document format is not a frame join and not a new realizer. It is specified in [output formats and scale](cpu-llm-output-formats-and-scale.md). The body is still retrieved sentences.
