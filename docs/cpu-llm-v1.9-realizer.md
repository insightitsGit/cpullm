# cpu-llm design v1.9: the realizer

**Status:** Final design. N0, the plan, the constructions, and the checker, is implemented. No checkpoint is trained. The default `ask` path does not call this realizer. `account=True` or `realization="evidence_neural"` opts in, and the neural request falls back to this grammar because no checkpoint exists. A document order is not this realizer. It is specified in [output formats and scale](cpu-llm-output-formats-and-scale.md).

**Date:** 2026-10-16

**Package:** 1.7.1 until a release is cut. This document is a design version, not a PyPI version.

**Author:** Amin Parva (AI Architect & Staff Applied AI Engineer)

**Baseline:** `859955d`, plus the stage-1 frame work in the working tree. The frame schema in code is `stage1-v2`.

**This document replaces, for implementation, the three notes it was drawn from:**

* [Copy realizer](cpu-llm-v1.8-copy-realizer.md), the pointer constraint.
* The 2026-10-16 pointer-generator note, recorded in section 12 of that file. A soft gate between a function-word softmax and a copy distribution, under a finite-state mask.
* [Evidence-conditioned proposal](cpu-llm-v1.9-evidence-conditioned-realizer-proposal.md), the claim plan, the action vocabulary, and the independent checker.

Those three stay in the tree as the review record. Build from this file.

**Depends on:** [semantic memory v1.8, stage 1](cpu-llm-v1.8-semantic-memory.md). Stage 1 still excludes a generative model at ingest. This design revises only the wording step, and only after the non-neural contract in section 6 exists.

---

## 1. The model

The better model is a **construction ranker over a claim plan**.

A deterministic planner reads the question and every authorized record the turn already holds, and writes a claim plan. An attributed grammar turns that plan into a small set of legal clauses, one clause per record. Each clause is a derivation: a construction id, then actions that copy a source span, inflect a verb the plan already authorized, or emit a grammar symbol the construction already licensed. The spoken passage is those clauses in an order the records already justify. The ranker does not merge two records into one new claim.

The network, when it is used, scores those derivations. It does not score words from a vocabulary. It does not open a span the plan did not bind. If the grammar returns one derivation, the network is not called. If it returns none, the reply is the stage-1 non-answer.

That is stronger than a pointer-generator, and smaller than a graph decoder.

A pointer-generator still has a distribution over tokens. A gate can prefer a content word at the moment the sentence needs `was`, and a mask has to cancel it afterward. Two occurrences of `apple` collapse if the copy distribution sums positions that share a string. The construction ranker never faces that choice. The grammar state names the next action type, and each action names a span id, not a string.

A byte-level GRU and a typed message-passing encoder are a later scorer, and only if ranking whole derivations fails to prefer the sentence people actually want. They are not the first model. Most supported questions have one legal sentence today. A network cannot improve a set of size one.

---

## 2. What each earlier design contributed

| Design | Kept | Not kept |
|--------|------|----------|
| Copy realizer | Content words are pointers into role spans. Function words are a closed list. No Gaussian sentence seed. `surface.py` stays the speaker for ordinary propositions. An absent checkpoint uses the template. | A token decoder that orders pointers itself. The frozen retrieval vector as the meaning of a role. Training before a second legal construction exists. |
| Pointer-generator note | Copying is explicit. Illegal next tokens have probability zero before the sample. CPU inference may be packaged without a trainer. The auditor stays in front of delivery. | The relational slice `[384:512]` as a predicate code. Relation hands as words. A function list of about 250 tokens, including `because` and `whereas`. Replacing `surface.py`. A Transformer of width 256 as the first model. Any file size or latency written before a measurement. The sample module that returns vocabulary logits and never computes a copy distribution. |
| Evidence-conditioned proposal | The claim plan. Actions instead of a word softmax. A checker that replays the derivation and does not trust the network. Query text is not evidence. `in his house` is not ownership. Cross-sentence joins wait for entity identity. Opt-in neural path. Untrained weights are refused. Random scores, in a test harness, still cannot leave the grammar. | A byte GRU, two message-passing layers, and a 256-unit action decoder as the first thing to train. The 2–8 million parameter budget, the 10,000–50,000 example range, and the latency target, until a run measures them. WebNLG as a grounding proof. |

The shipped retrieval tensor is unchanged. Dense core `[16:384]` retrieves. The relation head is off. The tail `[480:512]` is a signature of length 0.05. It is not an input to this realizer.

---

## 3. Three objects

### Evidence

One request-local snapshot of the shortlist the turn already retrieved. Completeness is shortlist-only. Each record keeps its own id, and a word bound to one record cannot fill a role in another.

| Record the turn can hold | What the passage may say from it |
|--------------------------|----------------------------------|
| An `EIRProposition` that round-tripped through `SemanticSurfaceRealizer` | The clause that realizer already builds: subject, predicate, object, quantifier, polarity, modality, and a condition tree when the proposition stores one. |
| A stored `CAUSAL_RELATION` edge between two of those propositions | `Consequently` on the following clause, and only then. |
| A `stage1-v2` frame, when the question is a color, location, or agent question | The frame constructions in section 4. |
| A source sentence that became neither a proposition nor a frame | That sentence copied whole. No new subject, verb, and object are cut out of it. |
| A math result, when the math node ran | `{expression} = {value}.` The calculation is not stored as a proposition. |
| Relation hands | A separate clause that copies those words and says they share a stored word-edge. Not `is`, `causes`, or `located in`. |
| A taxonomy category tag | A separate clause that copies the category string and calls it a tag. Not `X is a Y`. |
| The dense core and the relational tail | Nothing. They are not words. |

A `stage1-v2` frame is affirmative, declarative, and active because the extractor refused negation, conditions, and extra attachments. That is a property of the grammar, not a default applied to arbitrary prose.

`his` inside a location span is copied as part of that span. It is not resolved to the agent. Compare, brief, deep, and imagine keep the sections they already write. This ranker does not rewrite them into the factual clause.

### Claim plan

The planner is deterministic. It chooses which of the records above the question licenses, before any score is computed.

A plain question licenses the audited propositions in the shortlist, in the topological order `SemanticSurfaceRealizer` already uses. It does not also speak relation hands or category tags. A frame question licenses the frame. A math question licenses the calculation. A full account is a separate plan: every authorized record in the shortlist, each as its own clause, still without mixing their words. That plan is opt-in. It is not the default `ask`.

For `What color was the apple John ate?` against `John ate a yellow apple in his house.` the plan is:

```text
query: color, patient apple, agent John, predicate eat, tense PAST
required: color of that patient, with that agent and predicate
omitted: location, because the question does not ask for it
forbidden: ownership, cause, comparison, a new time, a second event
```

Missing, conflicting, ambiguous, and unsupported outcomes return the existing visible non-answer. The ranker is not called. A year in the question that the frame does not carry is a missing outcome, not a span the model may skip. Present evidence does not satisfy a past color question.

One name in two documents is two mentions. This design does not join them.

### Wording

The ranker may choose among constructions the grammar has already approved for that plan. It may not choose polarity, a date, a winner, a synonym, or a connective such as `because`.

---

## 4. Actions

A derivation is a sequence of actions. There is no `GENERATE_CONTENT_WORD` action.

| Action | What it may do |
|--------|----------------|
| `CHOOSE_CONSTRUCTION` | Pick a construction whose signature matches the plan. |
| `COPY` | Copy one bound span by span id and role. The rendered text is the source substring. |
| `INFLECT` | A form from `cpu_llm.realizer.inflect.forms` for the frame lemma, and only when that construction authorizes the change. If the source surface already fits, copy it. |
| `EMIT_GRAMMAR` | A symbol that construction places at that step: `the`, `a`, `an`, `was`, or `that` when a relative-clause construction has been approved. |
| `STOP` | Legal only when every required role is covered and the construction is closed. |

`apple` in the subject and `apple` in the object are different span ids. The ranker cannot add their scores.

The constructions, one family per record:

* Proposition: the clause `SemanticSurfaceRealizer` already speaks for that proposition, including `Consequently` only across a stored causal edge.
* Source quote: the whole sentence, when no proposition and no frame exists.
* Math: the calculation sentence, when the math node returned a value.
* Word-edge: `These words share a stored word-edge: {hand words}.` The hand words are copied. The clause cannot be attached to a proposition as a relative.
* Tag: `Stored tag: {category}.` The category string is copied.

The frame constructions are the sentences stage 1 already speaks:

* past color, one-word agent: `The {patient} {agent} {verb} was {color}.`
* past color, copula: `The {patient} {verb} {color}.`
* past location: `{agent} {verb} the {patient} {location}.`
* past agent: `{agent} {verb} the {patient}.`

A second color construction, `The {patient} that {agent} {verb} was {color}.`, is allowed only after the grammar and the checker accept `that` as a relative marker and not as a new claim. Until that construction exists, the color plan has one derivation and the network stays idle.

Multi-word agents stay on the current template refusal for color until a construction states how to order that span. The ranker does not invent the order.

---

## 5. Scoring

Legal derivations are produced by the grammar first. Call that set `D(plan)`.

```text
score(d) = ranker(plan, derivation d)
choice   = argmax over D(plan), with construction id as the tie break
```

If `|D(plan)|` is 0, abstain. If it is 1, take that derivation and do not load a checkpoint.

The ranker's features are the plan and the derivation: which construction, which span ids, which grammar symbols. They are not a sample from `randn`, and they are not the relational slice. Training-time weight initialization may be seeded. That seed is not a fact.

Decoding does not use temperature or nucleus sampling. The same checkpoint and the same plan should choose the same derivation. Bitwise equality across different CPU kernels is not promised.

A test-only harness replaces the ranker with uniform scores. Every sentence that harness accepts must still be one of `D(plan)`. That is the safety test. An untrained checkpoint is never served.

---

## 6. Checker

The checker does not call the ranker again.

1. The span ids in the derivation are the plan's bindings, and the slices still match the snapshot.
2. Replaying the actions yields the candidate string exactly.
3. The required roles are present. No forbidden role was added. Tense matches the plan.
4. Numeric tokens in the candidate are the supporting span, not a digit found elsewhere in the shortlist.
5. PrismShine and the entailment auditor still judge their existing objects. A copied sentence does not skip them. Shine is not a proof that the construction is faithful.
6. A Shine rejection, an audit block, or a grammar block is the spoken text. The candidate cannot replace it.

`verified` on a frame means the stage-1 checks passed. `realization_verified` means this checker passed. Neither one means the source paragraph is true. `audit_passed` keeps its current meaning on `answer`. `answer` stays the checked sentence. `reply["text"]` carries the permitted realization, or the non-answer.

The candidate is not stored as a proposition and is not written into `event_frame`.

---

## 7. Build order

### N0. Contract, no network

Records for the evidence bundle, the plan, the derivation, and the checker. The grammar emits a clause for every record type in section 3, using the sentences the current speakers already produce. Tests include the seven frame regressions, a proposition that is not a frame, a source sentence with no proposition, a math result kept off the proposition store, a word-edge clause that cannot donate a word to a factual clause, and a uniform-score harness. This stage is the deliverable that makes a later network safe. It is not optional.

### N1. Rank the derivations

Train the ranker only after at least one plan has two checker-approved derivations. The teacher is the preferred derivation, not a paragraph. Loss is the log probability of that derivation given the plan. A second legal derivation is not an error.

If held-out preferences do not move, stop. Do not add a decoder to rescue a tie the grammar already explains.

### N2. An action decoder, only if N1 is too coarse

If constituent order inside one construction needs a learned choice, the decoder scores the next legal action, not the next word. The mask is `A(plan, grammar state)`, and every other action has probability zero. The pointer-generator equations apply inside that set: copy mass on the bound span ids, grammar-symbol mass on `EMIT_GRAMMAR`, and no third vocabulary.

A one-layer scorer is the first attempt. A wider Transformer, a byte GRU, or ONNX packaging waits until that scorer is measured and is still short. Size and latency are reported from the run. They are not specified here.

---

## 8. Training data

A pair is `(plan, accepted derivation)`. It is kept only when every content span in the derivation is a pointer into the record that licensed that clause. A frame clause still requires `frame_from_chunk` to have accepted the sentence. A proposition clause still requires the round-trip through `SemanticSurfaceRealizer`.

The template sentence is the first teacher. A human alternative is a second teacher only when it is one of the approved constructions. A sentence that needs a word outside the pointer set is dropped, not truncated into an unknown token.

WikiText and the primer contribute a pair only when the first sentence is a `stage1-v2` frame. No external structured-to-text corpus is required for N0 or N1, and a score on such a corpus would not prove this checker.

Splits are by source document, before surface variants of the same fact are expanded.

---

## 9. API

The default stays the deterministic template.

```python
appliance.ask(question)                              # unchanged
appliance.ask(question, realization="evidence_neural")  # opt-in, after N1
```

`realization="evidence_neural"` with a missing, untrained, or schema-mismatched checkpoint uses the template when the plan is still approved, and uses the non-answer when the plan was rejected. The result names which path spoke. A rejected plan has no fallback sentence from the network.

---

## 10. Where the code would go

N0 is the modules below, except `ranker.py`, which only selects among derivations the grammar already produced. It does not train.

```text
src/cpu_llm/realizer/evidence_schema.py    bundle, plan, derivation
src/cpu_llm/realizer/constructions.py      the stage-1 constructions and action legality
src/cpu_llm/realizer/derivation_check.py   the checker in section 6
src/cpu_llm/realizer/ranker.py             N1, after two derivations exist
tests/test_evidence_realizer.py            grammar, uniform scores, the seven regressions
```

`src/cpu_llm/realizer/surface.py` stays. Query time does not import a training framework. The package still refuses an already-initialized CUDA runtime.

---

## 11. Acceptance

N0 is accepted when:

* the apple color, location, and agent sentences match the sentences stage 1 already speaks
* a proposition that is not a frame is spoken as the clause `SemanticSurfaceRealizer` already speaks
* a full account lists each licensed record as its own clause, and a hand word does not appear inside the proposition clause
* the seven frame regressions still abstain or answer as they do now
* a uniform ranker cannot emit a word that is not a bound span or a licensed grammar symbol
* a Shine rejection is still the fallback sentence
* a plain question still ends on the checked sentence, not on the full account

N1 is accepted only when, in addition, a held-out preference among two or more legal derivations improves on always picking the template, and the factual meaning is unchanged. BLEU is not that test.

---

## 12. Still out of scope

* Stages 2 through 5 of semantic memory: negation and conditions as frames, entity ids, a durable role index, tenants and deletion.
* A pretrained generative decoder, GPU training, or a CUDA path.
* Bilinear `M_rel`, neural coreference, a new modality, or a larger retrieval vector.
* Relation hands or taxonomy tags used as a fact. They may appear only in the word-edge clause and the tag clause. Vector proximity still contributes no words.
* Writing the realized sentence back into the index.
* Persian, access-control lists, and a comparison that picks a winner the store does not state.
