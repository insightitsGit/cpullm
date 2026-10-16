# cpu-llm design v1.8: span-grounded semantic memory

**Status:** Stage 1 is implemented in this tree. Stages 2 through 5 are not.

**Package:** 1.7.1 until a release is cut for this design. This document is the design version, not a PyPI version.

**Author:** Amin Parva (AI Architect & Staff Applied AI Engineer)

The 2026-10-15 discussion asked for a memory of entities, event roles, attributes, and provenance, so a question can be answered by joining those records on CPU. This design keeps that direction and keeps the rule the appliance already runs: a role is stored only when it is a slice of a sentence the realizer can repeat. A parsed graph is not allowed to say something the paragraph did not say.

The current retrieval path is unchanged for every other question. A plain question still ends on the checked sentence.

---

## What changed in stage 1

Stage 1 is `src/cpu_llm/memory/frames.py`.

When the first sentence of a paragraph round-trips, ingestion stores an `event_frame` beside the proposition. The frame may contain:

| Role | When it is stored |
|------|-------------------|
| agent | The subject of an action sentence. A copula such as "The apple was yellow" has no agent. |
| predicate | The verb token, plus the lemma and tense the realizer used. |
| patient | The head noun of the object, or of the subject when the object is only a color. |
| color | A closed color word written next to that noun, or the whole object when the verb is `be` and the object is that color word. |
| location | A trailing `in` / `at` / `on` phrase with a determiner, such as `in his house`. |
| time | A trailing year phrase, such as `in 2019`, or `yesterday`, `today`, `tomorrow`, `tonight`. |

Each role stores the exact text and the character offsets. `sentence[start:end]` is that text. There is no owner role. `his house` stays the location phrase.

A negated sentence (`not`, `never`, `no`, `n't`) does not become an affirmative frame.

At query time the frame node runs after the other optional agents and before the reply, and only for three question shapes:

* `What color was the apple John ate?`
* `Where did John eat the apple?`
* `Who ate the apple?`

The node reads the paragraphs already retrieved. It does not scan the whole index, and it does not add a vector. The joined sentence may contain only tokens from the source sentence, plus `the`, `a`, `an`, `was`, `were`, `is`, `are`, `did`, and `that`. `answer` stays the checked sentence. When the frame question is the only optional step, `reply["text"]` is the joined sentence.

Two stored colors, locations, or agents for the same question produce no value. A question that names a year uses a frame only when that year is the frame's time span. `better`, `worse`, and a comparison do not enter this node.

`eat` / `ate` / `eaten` is in the realizer's closed irregular list so the apple sentence can round-trip. The join is not stored as a new proposition.

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
