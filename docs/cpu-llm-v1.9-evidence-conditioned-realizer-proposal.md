# Proposal v1.9: evidence-conditioned neural sentence realization

**Date:** 2026-10-16  
**Status:** Folded into [v1.9, the realizer](cpu-llm-v1.9-realizer.md). The claim plan and the checker are kept. The byte-level graph decoder is not the first model. No model implemented or trained.  
**Baseline inspected:** `859955d`  
**Design version:** v1.9 proposal, not a package version.  
**Predecessors:** [semantic memory v1.8](cpu-llm-v1.8-semantic-memory.md), [copy realizer v1.8](cpu-llm-v1.8-copy-realizer.md), [correctness handoff HO-cpullm-002](handoff-v1.8-frame-correctness-review.md).

## 1. Decision

Build an **Evidence-Conditioned Graph Realizer (ECGR)**: a small supervised graph encoder and constrained action decoder. It learns how to arrange and express an approved meaning using retrieved spans. It does not learn which unsupported facts to add.

The key constraint is stronger than a retrieved-word vocabulary:

> Every output action must be licensed by an approved claim plan, and every content span must identify its evidence and semantic role.

A neural network scores legal sentence constructions, role-specific span pointers, and licensed morphological choices. A deterministic attributed grammar defines what those actions mean. An independent checker validates the action derivation and rendered text before delivery.

This is a real learned surface realizer, with learned parameters, supervised training, and composition over new inputs. Its first release deliberately offers a bounded language of sentence forms. It will not provide unrestricted paraphrasing. Extending expressiveness means adding and validating new constructions, then teaching the model to choose among them.

### Relationship to the previous design

v1.8 explicitly excludes a generative model at phrasing time. This proposal intentionally revises that restriction in response to the requested direction. It preserves CPU inference, explicit evidence, role bindings, provenance, conservative abstention, and authoritative delivery gates. It does not silently change the existing accepted contract.

The current code at `859955d` uses `stage1-v2` frames, a closed extraction grammar, source-relative role captures, explicit frame outcomes, and rejection-aware composition. Those are the starting boundary. The earlier review's seven failures remain required regression fixtures; this proposal does not assert that they still reproduce after that patch, or certify that patch's full correctness.

The copy-realizer note is the smaller sibling of this proposal. It scores an order over role pointers and a short function-word list. This proposal keeps that copy constraint and puts three things in front of it: an approved claim plan, an attributed grammar of constructions, and a checker that does not trust the network. A pointer-generator that also samples new content words, a relational-slice embedding, or a replacement of `surface.py` stays out. Those were already refused in the copy-realizer note. N0 in section 10 is the first build. The learned decoder is N2, and only after a ranker shows that a network chooses among licensed sentences better than the template.

## 2. What “start from retrieved words and relations” means

At inference, the generator receives an evidence graph, not a random latent vector. Its state is initialized from the selected source nodes, verified relation edges, approved claim plan, and parsed query. It cannot initialize an answer from an empty evidence graph.

```text
query + retrieved passages
        |
versioned frame/EIR validation
        |
query binding + conflict/scope checks
        |
approved claim plan with source spans
        |
span encoder + typed graph encoder
        |
evidence-derived decoder initial state
        |
learned scores over grammar-legal actions
        |
span copying + licensed morphology + grammar realization
        |
derivation check + candidate grounding/numeric checks
        |
authoritative delivery gate -> reply
```

Distinguish three kinds of randomness:

- **Training initialization:** learned weights may use ordinary seeded initialization. This is a numerical starting point for learning, not a representation of a source fact. A trained, versioned checkpoint is mandatory for neural serving.
- **Inference state:** computed from the current approved evidence and query. No `torch.randn` sentence seed, noise vector, VAE latent, or diffusion noise is used.
- **Decoding:** use deterministic beam search or argmax with stable tie-breaking; no temperature/top-p sampling. Fixed checkpoints and the same runtime configuration should be reproducible. Do not promise bitwise equality across different CPU kernels or quantization backends.

The existing untrained VectorPrism relation/hyperbolic/causal heads must not define factual edges. Dense vectors can retrieve candidates. Stored frame roles and accepted EIR derivations authorize claims. The new graph encoder is trained specifically for realization; its attention weights are not evidence or new relations.

## 3. Separate evidence, meaning, and wording

### Evidence bundle

An immutable request-local snapshot containing:

- Source ID, revision/hash, chunk ID, exact sentence, and sentence offset within the chunk.
- Role spans with sentence-relative character offsets and exact surface strings.
- Frame schema/extractor version and proposition ID.
- Explicit predicate tense/aspect/voice, polarity, modality, negation scope, quantifier, temporal scope, and conditions when supported.
- Caller/tenant context when available. This field does not implement tenant isolation by itself.
- Candidate-retrieval scope. Stage 1 must label completeness as shortlist-only, not corpus-complete.

Missing semantic fields must be classified through the validated schema. Do not treat absent polarity/modality fields in arbitrary input as permission to assume affirmative facthood. A `stage1-v2` adapter can mark an accepted simple clause as affirmative declarative because its extraction grammar establishes that restricted case.

### Approved claim plan

A deterministic planner binds the query to an event and chooses what can be stated. For a color query on the apple example it specifies:

```text
plan_id: p1
query: color(patient=apple, agent=John, predicate=eat, tense=PAST)
event: e1
source: John ate a yellow apple in his house.
bindings:
  agent -> source span John
  predicate -> source span ate [lemma=eat, tense=PAST]
  patient -> source span apple
  color -> source span yellow, attached to e1.patient
required meaning:
  color(patient_of(e1), yellow)
  identifying restriction: agent(e1, John), predicate(e1, eat, PAST)
allowed omission:
  location, because this query does not require it
forbidden additions:
  ownership, cause, comparison, new entity identity, unsupported time
```

The plan includes required versus optional semantic units, exact allowed transformations, event identities, source dependencies, and a canonical semantic representation. It must not select a fact because the neural model finds it likely. When evidence is missing, conflicting, ambiguous, unsupported, rejected, or over resource limits, return an explicit outcome before generation.

Reusing a name such as John across documents does not establish identity. Cross-sentence joins remain unavailable until v1.8's entity-resolution work establishes a justified identity link. Combining claims also requires compatible event, time, modality, and condition scope. Unknown temporal bounds must follow a documented rule; absence is not a license to invent a date.

### Wording policy

The first model may choose sentence construction, legal constituent order, and span realization. It cannot choose polarity, certainty, a new date, a winner, or a causal connective. These are semantic choices owned by the plan.

Preserve unresolved possessives exactly. `in his house` does not establish that John owns the house or even that `his` resolves to John.

## 4. Model architecture

### 4.1 Dynamic span memory

Represent content with exact source-span pointers. Keep two views:

1. A byte/character representation of each source token for learned scoring, including unseen names and numbers.
2. The untouched source substring for copying and provenance.

No unknown-token substitution is allowed when rendering copied text. Byte embeddings and a small bidirectional GRU produce token vectors. Pool token vectors within a span; append role type, source/event membership, position, tense/scope features, and whether the query requests the role. The original bytes remain available even if a scoring representation is truncated; if bounds prevent reliable representation, decline the neural path rather than silently truncate evidence.

The query encoding can influence order and style, but query words do not become copyable factual evidence. Prompt instructions inside source text are data, not decoder instructions or grammar productions.

### 4.2 Typed graph encoder

Use a small relation-aware message-passing network over explicit event, entity/mention, attribute, and source nodes. An attribute belongs to a particular mention/event binding, not merely a matching noun string. Introduce reverse edges for information flow with distinct labels; they do not reverse the underlying factual relation.

One possible update is:

```text
h_i^0 = project(span_features_i, role_i, scope_i, query_match_i)
m_i^l = sum over (j,r,i) in E of normalized_weight(j,r,i) * W_r^l h_j^l
h_i^(l+1) = LayerNorm(h_i^l + MLP_l([h_i^l ; m_i^l]))
```

Use a shared base projection plus low-rank relation adapters to control parameter count. Labels such as `AGENT_OF`, `PATIENT_OF`, `COLOR_OF`, `LOCATED_AT`, and `TIME_OF` describe verified stored bindings. A dense similarity or learned edge score cannot mint any of those edges.

### 4.3 Evidence-derived decoder state

```text
g = attention_pool(H, approved_plan, query_encoding)
s_0 = tanh(W_init [g ; query_encoding ; plan_encoding])
```

Only the approved graph enters factual memory. If required evidence is absent, do not compute an answer from a default zero or random graph. Return the planner's visible non-answer.

A one-layer GRU action decoder reads its prior action, grammar-state features, plan coverage, and graph attention. Neural scores determine preference among currently legal actions.

### 4.4 Action space

Use structured actions rather than an unrestricted word softmax:

- `CHOOSE_CONSTRUCTION(id)`: select a vetted construction whose semantic signature unifies with the plan.
- `COPY(span_id, role_binding_id)`: copy the exact substring for a licensed role.
- `INFLECT(predicate_id, features)`: use the existing inflector only for transformations explicitly authorized by the construction and source semantics. Prefer the source surface when it already fits. Unknown or ambiguous forms fail safely.
- `EMIT_GRAMMAR(symbol_id)`: emit punctuation or closed grammatical material at the construction's prescribed position and features.
- `END_CLAUSE` / `STOP`: legal only after required semantic units and grammatical obligations are satisfied.

During the MVP, no `GENERATE_CONTENT_WORD` action exists. Synonyms, new adjectives, new content verbs, pronoun substitution, and free discourse connectives are unavailable. Names, quantities, units, and critical prepositions remain bound spans. An alternative preposition can change meaning and is not a harmless grammatical variant.

Articles, auxiliaries, negation, and connectives also carry meaning. They may not be emitted simply because they occur on a general allowlist. Each use is licensed by a construction with explicit definiteness, agreement, tense, polarity, and discourse constraints. The grammar may retain existing accepted v1.8 constructions; adding or weakening definiteness requires a documented rule.

### 4.5 Constrained probability and decoding

Let `A(P, q_t)` be the set of actions allowed by plan `P` and attributed grammar state `q_t`:

```text
score_t(a) = neural_score(s_t, graph, action_embedding(a), plan)
p_t(a) = exp(score_t(a)) / sum_{b in A(P,q_t)} exp(score_t(b))
         for a in A(P,q_t); zero otherwise
```

The mask removes invalid construction IDs, spans bound to the wrong role/event, altered temporal scope, unauthorized negation, unsupported attributes, and premature STOP. Keep actions for repeated surface strings distinct by span and binding ID. Do not collapse `apple` pointers from subject and object into one token probability.

Initial decoder settings: beam width 4, at most 64 semantic actions, at most 128 rendered tokens. These are proposed bounds, not tuned results. A word copied inside a longer span still counts against the output-token budget. If no complete permitted derivation fits, return an explicit `generation_exhausted` reason; do not return a partial sentence. Stable tie-breaking uses construction ID and source/span order.

The language of legal derivations defines possible factual content. Model scores cannot enlarge that language. A poorly trained or accidentally random scoring model should degrade ordering/fluency or trigger fallback, not gain access to an unsupported role. This property is conditional on correct extraction, planning, grammar, and checking.

## 5. Worked examples

### Color

Evidence: `John ate a yellow apple in his house.`

The plan authorizes only the yellow attribute attached to the apple in John's eating event. The decoder can learn to prefer, when both constructions have been approved:

```text
The apple John ate was yellow.
The apple that John ate was yellow.
```

`that` is licensed by the relative-clause construction. The model cannot emit red, infer ownership, or switch ate to will eat. Its first action selects an evidence-bound construction; its initial hidden state was already computed from the graph. This is what it means to start from retrieved content even when the first printed token is grammatical `The`.

### Location

Question: `Where did John eat the apple?`

A construction may retain the full licensed object phrase and produce `John ate a yellow apple in his house.` A shorter form consistent with the existing v1.8 contract can be supported only through an explicit object-reference transformation. Do not let the model independently discard modifiers or change indefinite to definite reference.

### Required abstention

- `John ate a picture of the apple.` does not authorize eating the apple.
- An undated event does not satisfy a query explicitly asking about 2020.
- `The apple is yellow.` does not prove a past color.
- A rejected delivery cannot be replaced by a neural sentence.
- `John ate an apple. The apple was yellow.` remains unsupported as a cross-sentence join until mention identity is established.
- Two agents or locations may represent distinct events; keep ambiguity separate from proved contradiction.

## 6. Verification and safety boundary

The verifier receives the immutable evidence bundle, approved plan, action trace, and candidate text. It must:

1. Validate source revisions and exact source span slices against the current snapshot.
2. Validate relation bindings and allowed transformations using explicit IDs, not word overlap.
3. Independently reconstruct the derivation's semantics and check required-plan coverage plus absence of added claims. Compare time, tense, modality, polarity, negation scope, quantifier, and conditions.
4. Replay the approved actions through a deterministic renderer and require exact candidate-text equality. Reject arbitrary post-editing or text accompanied by an unrelated certificate.
5. Run numeric checks against the candidate's actual supporting spans, with relation binding for subject, quantity, and unit. A digit found elsewhere in the retrieval set is insufficient.
6. Run candidate-specific grounding checks with its supporting passages. Preserve the existing final delivery policy.
7. At reply composition, enforce the final delivery status again and allow only verified candidate text.

The checker must not merely call the neural model again or trust `verified=True` from a producer. Implement semantic checking as a separate module and test it using mutated traces/text. Shared schema definitions are fine; test shared renderer/grammar logic to detect common errors. Replaying a trace is necessary but insufficient without checking its semantics against the source plan.

The existing `EpistemicEntailmentAuditor` audits realized EIR clauses and is lexical; it is not a proof checker for new neural constructions. Keep it for its existing domain and add a construction/derivation checker. Shine is additional defense, not a guarantee of semantic correctness.

This system can establish faithfulness to validated evidence within its supported grammar. It cannot prove the source is true, that the extractor understood arbitrary prose, that retrieval found all contradictory evidence, or that the constrained grammar is bug-free.

### Failure and fallback policy

- Missing/conflicting/ambiguous/unsupported evidence: use the structured visible non-answer. No model can fill it.
- Source revision mismatch, invalid plan, failed proof, or final grounding rejection: withhold; no fallback may bypass that rejection.
- Model unavailable, timeout, or no complete candidate, with a still-valid approved plan and no rejection: the existing deterministic realizer may produce an independently verified fallback. Label the path used.
- An untrained or schema-incompatible checkpoint: refuse the neural path. Never serve freshly initialized parameters.

## 7. Training plan

### Training item

Each example contains a validated evidence graph, parsed query, approved plan, one or more accepted action traces and sentences, and explicit outcome/rejection labels. Train on graph-to-action pairs; raw paragraphs alone are not sufficient labels. Keep source licenses and data provenance with every training split.

Start with the current supported color/location/agent cases and deterministic realizer outputs. Synthetic examples must be generated from known structured records and parsed/checked back into the intended semantics. Add human-written, independently annotated alternatives that are expressible in approved constructions. Otherwise the network would merely imitate one existing template and provide little benefit.

An initial experiment can use 10,000–50,000 synthetic examples and 500–2,000 human-reviewed alternatives, subject to learning curves and annotation quality. These are planning ranges, not demonstrated sufficient dataset sizes. No external dataset is required to make the first prototype run.

Use source/document-disjoint and entity/graph-skeleton-disjoint held-out splits. Split before producing surface variants so one fact's variants cannot leak across training and test. Include OOV names and relation combinations in the held-out set.

Public structured-to-text data such as WebNLG can support later fluency experiments after license review and schema mapping. It does not automatically meet the project's exact-source-span constraint, and benchmark scores on it do not validate this system's grounding contract.

### Loss

Primary objective:

```text
L_action = -sum_t log p(a_t_gold | evidence, plan, a_<t)
L = L_action + lambda * L_preference
```

`L_preference` optionally ranks human-preferred legal variants above grammatical but awkward legal variants. Use multiple accepted traces or minimum-risk selection to avoid treating all valid alternatives as errors. Tune the loss weighting on held-out data.

Do not hide safety failures inside a learned loss penalty: invalid actions remain impossible under the runtime grammar. Adversarial source/graph mutations test extraction/planning/verification. If a separate learned evidence selector is introduced later, it needs its own calibrated evaluation and cannot replace these hard checks.

### Adversarial evaluation

Retain all HO-cpullm-002 cases. Add role-swapped graphs, repeated nouns, attribute swaps across events, missing roles, contradictory and merely multiple events, date placement, unit/number swaps, negation scope, unknown names, conditional scope, source instructions, stale revisions, truncated evidence, rejected delivery, and mixed optional-agent replies.

Test the constraint system with uniform/random neural scores in a test-only harness. Every accepted output must still belong to the approved semantic language. This tests that the learned ranking is not carrying the safety contract. It does not authorize an untrained model in production.

## 8. CPU design budget and evidence required

A reasonable first configuration to implement and measure:

- Token/byte embedding dimension 64; span features projected to 192–256 dimensions.
- Two typed graph-message layers, with shared projections and small relation adapters.
- One 256-unit GRU decoder and a dynamic span-pointer scorer.
- At most 64 selected graph nodes and 512 source tokens per generation request.
- Single approved event per sentence initially; no free multi-event aggregation.

Target model size: approximately 2–8 million parameters, depending on character encoder, vocabulary/features, and graph adapters. This is an engineering budget, not a parameter count from an implemented model. FP32 weights alone would occupy about 8–32 MB; runtime tensors and framework memory are additional. Report actual count, resident memory, and cold/warm startup.

Evaluate FP32 first. Consider CPU quantization only after semantic and ranking regression tests; quantization can change candidate ordering. A proposed target for added warm realization latency is p95 under 100 ms on the project's previously measured CPU, but there is no measurement yet. Measure against the deterministic realizer and include end-to-end retrieval, verification, fallback rate, thread settings, and concurrency separately. Do not infer latency from parameter count.

No change to the 1024-d retrieval tensor is required. The graph encoder's hidden dimension is a separate representation trained for wording, not a replacement for stored provenance or retrieval.

## 9. Pipeline and API integration

Factor the current `_frame` work into evidence resolution/plan construction and rendering, so neural realization receives a plan rather than reverse-engineering the already joined sentence. Avoid training a decoder to parse its own predecessor's output.

Keep the base cognition/audit path and existing preliminary rejection checks. For an approved frame plan:

```text
base checks
 -> frame plan
 -> neural realization candidate (opt-in)
 -> derivation verification
 -> candidate numeric/grounding checks
 -> final delivery decision
 -> reply
```

Early rejection remains authoritative; a later candidate cannot erase it. If the base checks are unsuitable for frame queries, redesign that policy explicitly rather than bypassing a rejection. Creative, comparison, summary, math, and frame outputs retain separate provenance/verification states; do not describe the whole reply as audited based on one component.

Suggested opt-in API, preserving deterministic default behavior:

```python
result = appliance.ask(question, realization="evidence_neural")
# Existing default remains realization="deterministic".
```

Proposed additional result fields:

```text
realization_result:
  status: answered | missing | ambiguous | conflicting | unsupported | blocked
  mode: evidence_neural | deterministic_fallback
  candidate_text: internal/debug text, not automatically deliverable
  text: deliverable text only when verified and allowed; otherwise visible non-answer
  verified: bool
  plan_id, evidence_revision_hash, construction_version
  model_checkpoint_id, extractor_schema
  evidence_ids, span_bindings, action_trace, derivation
  reason_codes, latency_ms
```

Keep sensitive trace details behind the appropriate caller visibility policy when tenant isolation is added. `verified` means checked against the evidence contract; it is not source truth or confidence. Debug candidates must not leak through `reply.text` or optional Event sections after a block.

`answer` retains its current checked-EIR meaning. `reply.text` delivers the permitted realization. `audit_passed` continues to describe its current scope; introduce `realization_verified` and per-component delivery metadata instead of overloading it. Adapt legacy `frame_result` fields compatibly and document any changes.

## 10. Implementation stages and suggested modules

### N0 — Contract and non-neural baseline

Create typed evidence/plan/derivation records, the attributed construction grammar, and the independent checker. Expose more than one vetted construction where possible. Test with fixed/random scores; measure the existing deterministic baseline. This is a prerequisite, not the learned model deliverable.

### N1 — Small learned candidate ranker

Train the graph encoder to rank complete vetted realizations as a low-risk baseline and validate the data pipeline. If it does not improve held-out human fluency/preferences or useful variant selection, do not claim a need for a more complex decoder.

### N2 — Learned constrained action decoder

Train the GRU/pointer decoder and compare against N1. It composes legal actions, enabling constituent-level choices rather than ranking a fixed list. Release only when it improves wording or useful coverage without semantic regression. If a single construction is legal, recognize that the network has no useful choice and can use the verified deterministic path.

### N3 — Broader grammar and memory integration

Add conditions, uncertainty, negation, new languages, and multi-record joins only when the corresponding semantic-memory capabilities and verification rules exist. A decoder cannot compensate for missing entity resolution or an absent role index. Define tenant/source lifecycle behavior before multi-user deployment.

Suggested new implementation locations (proposed, not created by this design):

```text
src/cpu_llm/realizer/evidence_schema.py      immutable evidence, plans, traces
src/cpu_llm/realizer/constructions.py        attributed grammar and action legality
src/cpu_llm/realizer/evidence_encoder.py     byte/span and typed graph encoder
src/cpu_llm/realizer/neural.py               ranker/GRU pointer decoder
src/cpu_llm/realizer/derivation_check.py      independent semantic/text verification
src/cpu_llm/training/realization_data.py     annotated graph/action corpus tooling
src/cpu_llm/training/train_realizer.py       reproducible supervised training
tests/test_evidence_realizer.py             grammar, model, and rejection cases
```

Checkpoint metadata must bind weights to model architecture, training-data manifest, grammar/construction version, frame schema, and evaluation report. Load verified local artifacts only; generation must not modify weights or persistent semantic memory.

## 11. Release acceptance

- All applicable existing invariant/frame/reply tests pass; all seven review regressions remain covered.
- Zero accepted unsupported semantic mutations on the curated adversarial release set. Report its size and categories; this is not a universal guarantee.
- Exact required-role/scope coverage, correct number/unit binding, and exact provenance span alignment on that set.
- No answer for missing required evidence; no candidate or fallback bypasses a rejection.
- Improved held-out human preference or fluency over deterministic realization, with preserved factual meaning. Report baseline, sample size, uncertainty, and annotator procedure. BLEU/ROUGE alone do not establish faithfulness.
- Held-out entity/source/relation-combination performance, fallback/abstention rates, measured CPU latency, actual parameter count/memory, and behavior with OOV names and bounds exhaustion.
- Real ingest -> retrieve -> plan -> generate -> verify -> reply tests, including source revision change and mixed-mode composition.
- No release without a trained compatible checkpoint and explicit support-matrix documentation.

## 12. Research basis and limits of the analogy

- [See, Liu, and Manning, 2017: Get To The Point](https://aclanthology.org/P17-1099/) introduces a pointer-generator that copies source words while also generating new words. This proposal borrows explicit copying but removes the unrestricted content-word generator in the first release. Copying alone is not a semantic guarantee.
- [Hokamp and Liu, 2017: Lexically Constrained Decoding](https://aclanthology.org/P17-1141/) constrains output to include required subsequences. ECGR additionally constrains roles, scope, constructions, and derivations; lexical inclusion is insufficient for the project's correctness contract.
- [Hajdik et al., 2019: Neural Text Generation from Rich Semantic Representations](https://aclanthology.org/N19-1235/) studies realization from structured semantic representations. It supports the graph-to-text direction; its results do not validate this proposed architecture or its CPU budget.
- [Gardent et al., 2017: The WebNLG Challenge](https://aclanthology.org/W17-3518/) provides a structured-data-to-text benchmark. Its pairs are not automatically span-grounded training examples for this project.

The specific ECGR architecture, restrictions, model size, data ranges, and latency targets above are proposed engineering choices. They have not been experimentally validated. The first deliverable should be an executable contract and measured baseline, followed by a trained prototype with an evaluation report.

## 13. Resolve these details with the companion copy-realizer design

Before implementation, agree on one execution contract across this proposal and the v1.8 copy-realizer note:

- **Query input:** A frame can support source reconstruction, color, location, and agent answers. Encode the requested task/claim plan; a frame alone does not distinguish their different teachers.
- **Inference termination:** Teachers exist only during training. Replace any teacher-length or teacher-repetition rule at inference with grammar completion, required-plan coverage, licensed span reuse, and fixed resource caps.
- **Span versus token actions:** This proposal copies a whole span per action. A token-level alternative must track position within a multiword span and force contiguous completion. Equating a multiword node directly to one next-token symbol is incomplete.
- **Pointer identity:** Keep event, role, and span IDs even when strings are identical. Do not collapse distinct mentions into one surface-token probability before binding verification.
- **Span encoder cost:** Frozen MPNet vectors per role are an alternative to the proposed small byte/span encoder. Batch and cache revision-bound encodings, then benchmark CPU cost and quality rather than assuming repeated encoder calls are negligible.
- **Candidate checks:** Checks performed on the original `answer` do not verify the new spoken candidate. Resolve the companion delivery section and its summary with explicit candidate-specific verification plus the derivation checker.
- **Morphology:** Membership in an inflection table does not authorize a tense change. Require construction-specific agreement, tense, reference, and polarity rules.
- **Training usefulness:** A single deterministic teacher can demonstrate imitation, not improved phrasing. Split by source/entity before augmentation, include meaningful licensed alternatives, and select training duration by validation.

Ordinary language decoders do not generally start from Gaussian noise either. The distinguishing property here is an evidence-bound action language and verified meaning plan, not the absence of `randn` alone.
