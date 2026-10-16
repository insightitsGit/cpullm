# cpu-llm design v1.8: copy realizer

**Status:** Superseded. The implementation design is [v1.9, the realizer](cpu-llm-v1.9-realizer.md). This file remains the record of the pointer constraint. No training code, no checkpoint, and no change to the spoken path.

**Depends on:** [design v1.8, stage 1](cpu-llm-v1.8-semantic-memory.md). The frame grammar there is the input language of this model. This document does not widen that grammar.

**Successor proposal:** [evidence-conditioned realizer v1.9](cpu-llm-v1.9-evidence-conditioned-realizer-proposal.md). That note keeps the copy constraint and adds a claim plan, a construction grammar, and an independent checker. If both are accepted, v1.9 is the build order: the non-neural contract first, then a ranker, then a decoder. This document is the scoring rule inside that decoder, not a second model that replaces `surface.py`.

**Package:** 1.7.1 until a release is cut. This document is a design version, not a PyPI version.

**Author:** Amin Parva (AI Architect & Staff Applied AI Engineer)

**Date:** 2026-10-16

A sentence should be built from the words and roles retrieval already kept. The first state of the model is that frame. It is not a sample from a Gaussian, and it is not a prompt that a general decoder continues.

---

## 1. Why a model at all

`SemanticSurfaceRealizer` already speaks a sentence from a proposition, and the stage-1 frame speaker already speaks a handful of color, location, and agent sentences. Both are templates. A new clause shape needs a new template.

The copy realizer is a small CPU model that learns the order, the function words, and the verb inflection of sentences whose content words are already bound to frame spans. It is a student of the current realizer and of the source sentence. It is not a second writer with its own vocabulary.

---

## 2. The constraint

At every generation step the distribution is:

```text
pointers into the frame's role spans  ∪  a closed function-word list
```

There is no draw from `randn`. There is no softmax over a general wordpiece vocabulary. A content word that is not one of the retrieved role spans has probability zero.

The function-word list for the first version is the one stage 1 already permits in a color sentence: `the`, `a`, `an`, `was`. Additions to that list are a grammar change, reviewed with the frame tests, not something training is free to discover.

The verb may be replaced only by a form from `cpu_llm.realizer.inflect.forms` for the frame's lemma. `ate` may surface as `ate`. It may not surface as a synonym.

---

## 3. Input

The only training and inference input is one `stage1-v2` event frame:

| Field | Use |
|-------|-----|
| `agent`, `predicate`, `patient`, `color`, `location`, `time` | The copy pointers. A missing role is an empty node, not a guessed word. |
| `subject`, `object` | The spans that must contain the agent and the patient or color. |
| `predicate.lemma`, `predicate.tense` | The inflection table and the tense the question is allowed to ask. |
| `sentence` | The reconstruction target. Offsets in the frame are relative to this sentence. |
| `proposition_id`, `document_id` | Provenance. They are not tokens. |

Relation hands, taxonomy tags, and neighboring chunks are not extra input words. A word that failed the stage-1 grammar, including a noun inside `a picture of the apple` or `if Mary cooked dinner`, never becomes a pointer.

Each present role is encoded as:

```text
frozen vector of that span's own text  +  a learned role id
```

The frozen vector comes from the encoder the appliance already uses, `sentence-transformers/all-mpnet-base-v2`, run on CPU. The role id is a learned vector for `agent`, `predicate`, `patient`, `color`, `location`, or `time`. The word itself is not learned from noise. The role id only says which slot the retrieved word fills.

One graph step then mixes a role with the roles the grammar already tied to it:

```text
predicate — agent
predicate — patient
patient — color
predicate — location
predicate — time
```

That step is a single linear mix over those edges. It is not a bilinear relation matrix, and it does not create a new edge because two vectors are near each other.

---

## 4. Decoder

The decoder is an ordering model over the pointer set.

1. Start from the encoded frame. The start symbol is that graph, not a random vector.
2. At step `t`, score the unused content pointers and the function-word list.
3. Append the chosen token. A content pointer can be used once. Function words can repeat only where the teacher sentence repeats them.
4. Stop at the end of the teacher sentence, or at a fixed step cap equal to the teacher length plus the function words it contains.

Beam search stays inside that same set. There is no temperature sample in the delivered path. The delivered candidate is the highest-scoring sequence that also passes the checks in section 7.

For the supported past color sentence the teacher is:

```text
The apple John ate was yellow.
```

Pointers: `apple`, `John`, `ate`, `yellow`. Function word: `The`, `was`. The model is learning that order. It is not learning the word `yellow` from a language-model prior.

A finite-state mask sits on top of that distribution. The mask is the stage-1 clause, not a general English grammar. While the subject span is unfinished, the only allowed tokens are the remaining tokens of that span, in order. The verb inflection is allowed only after the subject is closed. A location or time span is allowed only after the object is closed. A token the mask rejects has probability zero even if the network scored it.

---

## 5. Pointer-generator form

The ordering model can be written as a pointer-generator. This is the form to implement if section 11 keeps a learned decoder. The symbols below are the frame, not a 32,000-word lexicon.

The input nodes are the role spans that are present:

```text
X = [ agent span, predicate span, patient span, color span, location span, time span ]
```

A missing role is omitted. `H` is the encoded nodes from section 3. `s_t` is the decoder state at step `t`.

Functional vocabulary `V_func` is the closed list in section 2. Copy distribution `P_copy` puts mass only on nodes whose span text is the candidate token:

```text
P_vocab(y_t) = softmax(W_v s_t + b_v)           over V_func only
a_t          = softmax(s_t^T W_a H)            over the role nodes
P_copy(y_t)  = sum of a_t,i for nodes i whose span is y_t
lambda_t     = sigmoid(w_s^T s_t + w_h^T c_t + b)
P(y_t)       = (1 - lambda_t) P_vocab(y_t) + lambda_t P_copy(y_t)
```

`c_t` is the attention mix of `H`. `lambda_t` chooses between a function word and a copied span. It does not open a third vocabulary.

The stage-1 automaton then builds a mask `M_t` that is 1 only for tokens legal in the partial string:

```text
P_constrained(y_t) = P(y_t) M_t(y_t) / sum_y P(y) M_t(y)
```

If the mask is all zeros, the candidate is abandoned. The reply is the stage-1 non-answer.

`V_func` is not a list of about 250 connectives. Words such as `because`, `whereas`, and `known as` state a relation. They enter `V_func` only when a later grammar stores that relation as a role. Until then they stay at probability zero.

---

## 6. Teacher and training pairs

A pair is kept only when `frame_from_chunk` returns a `stage1-v2` frame and the source sentence is the frame's `sentence`. That is the pair `(frame, sentence)`.

Two teachers:

1. The source sentence, tokenized with the same pointer-or-function rule. If a token is neither a role span nor a function word, the pair is dropped. The model is not trained to emit it.
2. The current template sentence from the frame speaker, when one exists (`past_color`, `past_location`, `past_agent`). The template is the licensed form. The source sentence is the reconstruction target only when every content token is a pointer.

The loss is cross-entropy on the teacher tokens, with the illegal vocabulary entries masked to zero before the softmax. A reconstruction that would require a word outside the pointer set is not a training example.

No new hand labels are required for the clause shapes stage 1 already accepts. WikiText and the primer contribute a pair only when their first sentence round-trips and matches that grammar. The apple sentence contributes a pair once it is ingested. Ingestion does not change the encoder.

Proposed first training setup, all of it open to revision before any run:

| Choice | Proposed value |
|--------|----------------|
| Device | CPU only. The process keeps the existing CUDA refusal. |
| Parameters | Role ids plus one graph mix plus one ordering layer. No new pretrained decoder. |
| Optimizer | Adam, learning rate `1e-3`, batch of frames that fit in memory. |
| Steps | One pass over the accepted pairs, then a held-out tenth of those pairs. |
| Initialization | Role ids small; no `randn` input at train or test time. |

These numbers are placeholders. They are not a result.

---

## 7. Delivery

The network does not write `reply["text"]` by itself.

1. The frame must already be `verified` under the stage-1 rules, including tense, year, and span containment.
2. Every content token in the candidate must be a pointer into that frame. The check is the pointer identity, not "the string occurs somewhere in the paragraph."
3. `EpistemicEntailmentAuditor`, PrismManifest, and PrismShine still judge the checked sentence in `answer`. They are not retargeted onto a looser sentence.
4. `frame_verified` on the candidate is separate from `audit_passed` on `answer`.
5. A Shine rejection, an audit block, or a grammar block remains the spoken text.
6. The candidate is not stored as a new proposition and is not written back into `event_frame`.

If no candidate passes, the reply is the stage-1 non-answer (`missing`, `conflicting`, or `unsupported`). The model does not get a second try with a larger vocabulary.

---

## 8. What this model will not learn

Training on accepted frames does not create roles the grammar refused.

| Source | Why it stays a non-answer |
|--------|---------------------------|
| `John ate a picture of the apple in his house.` | No frame, so no pointers. |
| `John ate a yellow apple if Mary cooked dinner.` | The condition is outside the clause. |
| `John ate the apple with Mary in his house.` | `with Mary` is not a role. |
| `In 2020, what color was the apple John ate?` against an undated frame | The year is a query constraint, not a word the model may ignore. |
| `The apple is yellow.` asked in the past | Tense is a gate in front of the decoder. |
| `his house` | Location pointer only. No ownership node exists to copy. |

A later grammar stage can add a role. Until that role is stored on the frame, the copy realizer has nothing to point at.

---

## 9. Proposed code, after this design is accepted

Nothing in this list exists yet.

```text
src/cpu_llm/realizer/copy.py     frame to pointer set, teacher tokens, masked step
src/cpu_llm/realizer/copy_train.py
                                 one CPU pass over accepted frames
tests/test_copy_realizer.py      pointer mask, rejected sources, apple order
```

`SemanticSurfaceRealizer` in `src/cpu_llm/realizer/surface.py` stays the speaker for ordinary propositions. The copy realizer does not replace that file. It runs only after a verified `stage1-v2` frame exists. A missing checkpoint means the template path, not a silent random initialization at query time.

Packaging the accepted checkpoint as ONNX is an implementation choice for CPU inference, so query time does not need a training framework. Size and latency are measured after a real run. They are not specified here.

---

## 10. How to tell it worked

On a held-out set of accepted frames:

* Every delivered content word is a role span from that frame.
* The apple color, location, and agent sentences match the template sentences stage 1 already speaks.
* The rejected sources in section 7 still abstain.
* A Shine rejection is still the fallback sentence.
* A plain question that never builds a frame still ends on the checked sentence.
* Latency is reported on the same machine class as the v1.7 measurements, after load, for the template path and the copy path separately.

An example test passing is not a claim about sentences outside the grammar.

---

## 11. Decisions to revise before implementation

These are the choices most likely to change in review.

1. **Function words.** Is `was` the only copula the model may insert, or may it also insert `were`, `is`, and `are` when the frame tense is that form? A list of about 250 connectives, including `because` and `whereas`, is not the default. Those words assert relations stage 1 does not store.
2. **Two teachers.** Should the loss follow the source sentence, the template sentence, or both only when they are identical?
3. **Multi-word agents.** `The apple seller` is a legal agent span. The template color sentence is defined for a one-word agent. Should the copy model be allowed to order that longer agent, or should multi-word agents stay on the template refusal until a template exists?
4. **Graph step.** Is the one linear mix worth training, or should the first model be pointers plus order only, with the role id as a bias? A 2-layer Transformer of width 256 is a later option if the linear mix cannot order the licensed sentences. It is not the first model.
5. **Where it sits.** The proposal is beside the template speaker, used only when a verified frame exists. It does not replace `SemanticSurfaceRealizer` for ordinary propositions.
6. **Checkpoint.** Who accepts the file, where it lives, and what happens when it is absent. The proposal is: absent checkpoint, template path.

---

## 12. What was taken from the 2026-10-16 pointer-generator note

A review note proposed a constrained neural surface realizer: a pointer-generator, a closed function vocabulary, a finite-state mask, CPU inference, and the auditor kept in front of delivery. The Gemini note that was meant to sit beside it was not in the request, so it is not reviewed here.

Taken into this design:

* The decoder distribution is a mix of a function-word softmax and a copy distribution over the input nodes, with a gate `lambda_t` between them.
* A finite-state mask `M_t` zeros every token the partial sentence is not allowed to say next. The mask is the stage-1 clause.
* The first state is the verified frame. It is not Gaussian noise and not a general-vocabulary sample.
* Inference may be packaged so the query path does not load a trainer. ONNX is one way to do that. No size or latency is claimed for a file that does not exist.
* `EpistemicEntailmentAuditor` and PrismShine still see the spoken sentence. A copied span does not skip them.

Left out, because they fight the frame rules or the shipped checkpoint:

* The relational slice `[384:512]` as the meaning of the predicate. In the shipped checkpoint that head is off. The dense core `[16:384]` is the trained search rank. The relation signature is only the tail `[480:512]`, length 0.05, and it is not a predicate embedding for generation. Role text is encoded with the frozen sentence encoder. The role id says which slot it fills.
* Relation hands as decoder input. Those hands are co-occurrence rings. They are not agent, patient, or color.
* Replacing `surface.py`. The template realizer remains the path for a proposition that is not a stage-1 frame, and the fallback when no copy checkpoint is loaded.
* A function vocabulary of about 250 tokens that includes `because`, `whereas`, and `known as`. Those are claims. They are not punctuation.
* A sample PyTorch module that adds a projected relational vector onto token embeddings and returns vocabulary logits. That module does not implement `P_copy`. It is not the model in section 5.
* Any latency, file size, or test-count claim for this network. Those numbers were not measured.

---

## 13. Out of scope

* A pretrained generative decoder, including any model whose first state is Gaussian noise.
* GPU training or a CUDA path.
* Bilinear `M_rel`, neural coreference, or a new modality.
* Using vector proximity, relation hands, or taxonomy tags as words the decoder may say.
* Writing the generated sentence back into the index as a proposition.
* Stages 2 through 5 of the frame design: negation and conditions as frames, entity ids, a durable role index, tenants and deletion.
