# Technical Architecture Specification: `cpu-llm` (v1.6.1 Correctness & Soundness Patch)

> Versioned historical specification. Start with [the current design](current-design.md)
> for the current request lifecycle and verification boundaries.

> The implementation of this specification is in `src/cpu_llm`.
> Phase 1 is the EIR schema and `PrismCognitionSubspaceAdapter`.
> Phase 2 is `SemanticSurfaceRealizer` and `EpistemicEntailmentAuditor`.
> Acceptance checks are `tests/test_invariants.py`.
>
> Two corrections are applied in the engine, where the code blocks below
> do not match the stated rules. Inclusion uses the Ganea entailment cone
> when a tensor is a point inside the Poincaré ball. A rule condition is
> evaluated as true, false, or unknown. Contradiction follows the modality
> matrix. Ruin is 1 or 0 from that matrix. There is no random bilinear map.
>
> Phase 2 follows the clause rules in section 4. The sentence is the one
> those rules emit. It is not passed through a grammar rewriter, and the
> auditor does not load a parser model. The auditor checks polarity,
> modality, voice, the condition threshold, the subject, and the predicate.
>
> Section 7 is the cpu-llm 1.7.0 lexical layer. It records how PrismRAG,
> PrismResonance, PrismCognition, and PrismCortex sleep attach relations
> to words, write those relations into the stored tensors, and answer an
> identity question from that graph. Where section 1 describes a bilinear
> map or an O(1) subclass test, section 7 is the behavior the code runs.
>
> Document orders, the semantic format trigger, and engine scale are a
> later contract. They are specified in
> `docs/cpu-llm-output-formats-and-scale.md` and implemented in
> `formats.py`, `format_sense.py`, and `scale.py`. Sections 1 through 7
> are unchanged by that contract.



**System Designation:** `cpu-llm` (Epistemic Vector-Native Appliance)

**Specification Level:** Level-3 Deterministic Execution Contract

**Hardware Invariant:** 100% CPU-Native. OpenBLAS/AVX-512 execution. Zero GPU/CUDA dependencies (`torch.cuda.is_available() == False` asserted at engine initialization).

**Install contract:** `pyproject.toml` is authoritative. The pins this tree runs are `vectorprism[encoder,postgres]==0.1.3`, `chorusgraph==1.3.0`, `prismguard==0.1.10`, `prismcognition==2.1.0`, `prismrag-patch==0.2.1`, `prismresonance==0.3.0`, `prismcortex==0.4.1`, `prismmanifest==0.3.4`, `prismshine==0.2.2`, `prismthinker==1.1.0`, and `prismagenticpay==1.2.0`. PrismThinker and PrismAgenticPay are required: the appliance imports Thinker at load and constructs the payment evaluator for every turn.

---

## 1. Concrete Architecture of the Vector Deliberation Engine

In a pure symbolic engine, evaluating high-order horn clauses across $N$ facts is $O(N^k)$ combinatorial matching. When $N > 500$, CPU symbolic provers stall.

In `cpu-llm`, the **Subspace Coordinate Space acts as a Geometric Pre-Filter for Inference Search**:

1. **Hyperbolic Subspace ($\mathbb{D}^{128}$):** Transitive taxonomy containment ($\text{SubClassOf}$) is directly computed via Poincaré distance cones in $\mathcal{O}(1)$ time per pair. Symbolic deduction is invoked **only** on candidate entity pairs $(\mathbf{u}, \mathbf{v})$ where $d_{\mathbb{D}}(\mathbf{u}, \mathbf{v}) < \epsilon_{\text{poinc}}$.
2. **Causal Cones ($\mathbb{R}^{128}$):** Potential causal precursors are pre-screened by the asymmetric metric cone $\mathbf{u}^T \mathbf{\Omega} \mathbf{v} > 0$.
3. **Symbolic Soundness Proof:** Symbolic resolution runs **only** on the geometrically viable candidates, proving soundness and assigning derivation rules.

```
                    [ 1024d Subspace Coordinates ]
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       Poincaré Subspace               Causal Subspace
       (128d Poincaré Ball)            (128d Minkowski Cone)
                 │                               │
       $d_{\mathbb{D}}(u, v) < \epsilon$       $u^T \Omega v > 0$
                 │                               │
                 └───────────────┬───────────────┘
                                 │ Candidate Pair Filtering
                                 ▼
                 [ Symbolic Soundness Proof Gate ]
                 • Antecedent validation
                 • Temporal interval intersection
                 • Modus Ponens derivation

```

---

## 2. EIR v1.3.1 Canonical Schema

This patch introduces explicit antecedent/consequent decomposition, status markers for conditional vs. activated obligations, and strict temporal interval comparisons.

```python
# src/cpu_llm/ir/schema.py
from __future__ import annotations
from enum import Enum
from typing import List, Optional, Union, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class Polarity(str, Enum):
    AFFIRMATIVE = "AFFIRMATIVE"
    NEGATIVE = "NEGATIVE"

class NegationScope(str, Enum):
    NONE = "NONE"
    PREDICATE = "PREDICATE"
    ENTIRE_PROPOSITION = "ENTIRE_PROPOSITION"
    OBJECT_ONLY = "OBJECT_ONLY"

class Modality(str, Enum):
    DECLARATIVE = "DECLARATIVE"
    OBLIGATIVE  = "OBLIGATIVE"
    PERMISSIVE  = "PERMISSIVE"
    PROBABILISTIC = "PROBABILISTIC"
    COUNTERFACTUAL = "COUNTERFACTUAL"

class QuantifierType(str, Enum):
    UNSPECIFIED = "UNSPECIFIED"
    ALL = "ALL"
    SOME = "SOME"
    NONE = "NONE"
    EXACTLY = "EXACTLY"
    AT_LEAST = "AT_LEAST"
    AT_MOST = "AT_MOST"

class Quantifier(BaseModel):
    model_config = ConfigDict(frozen=True)
    qtype: QuantifierType = QuantifierType.UNSPECIFIED
    value: Optional[float] = None

class LogicalOperator(str, Enum):
    AND = "AND"
    OR  = "OR"
    NOT = "NOT"
    GT  = "GT"
    LT  = "LT"
    GTE = "GTE"
    LTE = "LTE"
    EQ  = "EQ"

class LogicalExpressionNode(BaseModel):
    model_config = ConfigDict(frozen=True)
    operator: LogicalOperator
    operands: Optional[List[LogicalExpressionNode]] = None
    metric_name: Optional[str] = None
    threshold_value: Optional[Union[float, str]] = None
    unit: Optional[str] = None

class EpistemicStatus(str, Enum):
    RETRIEVED_FACT = "RETRIEVED_FACT"
    ACTIVATED_CONCLUSION = "ACTIVATED_CONCLUSION"     # All conditions satisfied & obligation holds
    CONDITIONAL_DERIVATION = "CONDITIONAL_DERIVATION" # Conclusion holds IF unproven condition holds
    HYPOTHESIS = "HYPOTHESIS"
    UNRESOLVED_CONTRADICTION = "UNRESOLVED_CONTRADICTION"
    ABSTENTION = "ABSTENTION"

class EdgeType(str, Enum):
    INFERENCE_DEPENDENCY = "INFERENCE_DEPENDENCY"
    CAUSAL_RELATION = "CAUSAL_RELATION"
    TEMPORAL_PRECEDENCE = "TEMPORAL_PRECEDENCE"
    CONTRADICTION = "CONTRADICTION"

class TypedGraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_id: str
    target_id: str
    edge_type: EdgeType

class SourceSpan(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_uri: str
    start_char: int
    end_char: int
    literal_text: str

class TypedEntity(BaseModel):
    model_config = ConfigDict(frozen=True)
    raw_text: str
    lemma: str
    is_plural: bool
    qualifiers: List[str] = Field(default_factory=list)

class TypedPredicate(BaseModel):
    model_config = ConfigDict(frozen=True)
    lemma: str
    tense: Literal["PAST", "PRESENT", "FUTURE"] = "PRESENT"
    aspect: Literal["SIMPLE", "PERFECT", "PROGRESSIVE"] = "SIMPLE"
    voice: Literal["ACTIVE", "PASSIVE"] = "ACTIVE"

class TemporalInterval(BaseModel):
    model_config = ConfigDict(frozen=True)
    valid_from: Optional[int] = None  # UNIX timestamp or integer year
    valid_to: Optional[int] = None

    def overlaps(self, other: Optional[TemporalInterval]) -> bool:
        if other is None:
            return True
        self_start = self.valid_from if self.valid_from is not None else float("-inf")
        self_end = self.valid_to if self.valid_to is not None else float("inf")
        other_start = other.valid_from if other.valid_from is not None else float("-inf")
        other_end = other.valid_to if other.valid_to is not None else float("inf")
        return max(self_start, other_start) <= min(self_end, other_end)

class DerivationTrace(BaseModel):
    model_config = ConfigDict(frozen=True)
    inference_rule: str
    premise_ids: List[str] = Field(default_factory=list)
    singular_values: List[float] = Field(default_factory=list)
    ruin_distance: float = 1.0

class EIRProposition(BaseModel):
    model_config = ConfigDict(frozen=True)
    proposition_id: str
    source_span: Optional[SourceSpan] = None
    polarity: Polarity = Polarity.AFFIRMATIVE
    negation_scope: NegationScope = NegationScope.NONE
    modality: Modality = Modality.DECLARATIVE
    quantifier: Quantifier = Field(default_factory=Quantifier)
    subject: TypedEntity
    predicate: TypedPredicate
    object_target: Optional[TypedEntity] = None
    condition_tree: Optional[LogicalExpressionNode] = None
    temporal_interval: Optional[TemporalInterval] = None
    epistemic_status: EpistemicStatus = EpistemicStatus.RETRIEVED_FACT
    epistemic_weight: float = Field(ge=0.0, le=1.0)
    derivation: Optional[DerivationTrace] = None
```

---

## 3. Deliberation Engine: Scope-Aware Contradiction & Conditional Deduction

Resolves P0-3 & P0-4:

* **Scope-Aware Contradiction:** Proposition pairs only constitute a contradiction if:
1. Subjects, predicates, and objects match semantically.
2. Modality is mutually exclusive (e.g., `DECLARATIVE` vs `DECLARATIVE` with opposite polarity).
3. `temporal_interval.overlaps()` evaluates to `True`.


* **Universal Deduction with Conditions:** Evaluates whether conditions attached to a rule are proven by instance facts. If unproven, emits `CONDITIONAL_DERIVATION` (not an unconditional obligation).

The implementation is `src/cpu_llm/cognition/adapter.py`. It does not build a random bilinear map and it does not run an SVD.

* Contradiction is the modality matrix on one atom whose times overlap. Ruin is 1 for that pair and 0 otherwise.
* A universal affirmative rule applies to an instance only when the instance is an unconditional retrieved fact or an already activated conclusion, its quantifier is unspecified, and it is an affirmative declarative copula whose object matches the rule subject.
* A hypothesis, a non-membership quantifier, or a conditional membership that is not yet proven does not establish the premise. An unproven condition on the instance is carried into the conclusion as `CONDITIONAL_DERIVATION`.
* Premise intervals that do not overlap produce no conclusion. Overlapping intervals are intersected onto the derived proposition. A metric observation outside that window does not prove the condition.
* When both tensors are points in the Poincaré ball, the instance must lie in the rule's entailment cone. The cone test is O(d). It does not by itself create a taxonomy edge.

## 4. Surface Realizer & Round-Trip Entailment Auditor

Resolves P0-1, P0-2, and P0-5:

1. **Sentence Boundary Preservation:** Every clause terminates with an explicit period (`.`).
2. **Proposition ids:** A delivered map is keyed by the proposition id, including ids such as `prop_none_quant`. No parser reads the sentence.
3. **Round-Trip Semantics:** The auditor checks polarity, modality, voice, tense, the condition threshold, the subject, the predicate, and the object against the proposition.

The implementation is `src/cpu_llm/realizer/surface.py` and `src/cpu_llm/audit/entailment.py`.

The realizer does not load spaCy, LanguageTool, or a dependency parser, and it does not rewrite the clause with a grammar tool. Each clause is the controlled sentence for that proposition and ends with a period.

* Obligative clauses use `must`. Permissive clauses use `may`.
* Probabilistic clauses use `probably`. Counterfactual clauses use `would`. A sentence that drops those words is not accepted as that modality.
* An active past negative uses `did not`. An active present negative uses `does not` or `do not`.
* The auditor checks polarity, modality, voice, tense, the condition threshold, the subject, an inflection of the predicate, and the object's words. Replacing the object fails the check. The auditor does not load a parser.

## 5. Verification Acceptance Suite (`tests/test_invariants.py`)

Run `tests/test_invariants.py`. That file is the suite. The sketch below is the original acceptance shape; it is not a second implementation.

```python
# tests/test_invariants.py
import pytest
import numpy as np
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic import BaseModel

from cpu_llm.cognition.adapter import PrismCognitionSubspaceAdapter
from cpu_llm.realizer.surface import SemanticSurfaceRealizer
from cpu_llm.audit.entailment import EpistemicEntailmentAuditor
from cpu_llm.boundary.manifest import TrustedKeyringRegistry, PrismManifestBoundary
from cpu_llm.ir.schema import (
    EIRProposition, Polarity, Modality, Quantifier, QuantifierType,
    TypedEntity, TypedPredicate, EpistemicStatus, TemporalInterval,
    LogicalExpressionNode, LogicalOperator
)

class SampleContract(BaseModel):
    action_type: str
    tenant_id: str
    output_text_hash: str
    audit_trace_id: str

def test_sound_deductive_inference_and_condition_separation():
    """Validates that rules with unproven conditions yield CONDITIONAL_DERIVATION."""
    adapter = PrismCognitionSubspaceAdapter()

    # Rule: All approved suppliers must undergo an audit if revenue exceeds 10.
    rule = EIRProposition(
        proposition_id="rule_cond",
        polarity=Polarity.AFFIRMATIVE,
        modality=Modality.OBLIGATIVE,
        quantifier=Quantifier(qtype=QuantifierType.ALL),
        subject=TypedEntity(raw_text="approved suppliers", lemma="supplier", is_plural=True, qualifiers=["approved"]),
        predicate=TypedPredicate(lemma="undergo", tense="PRESENT", voice="ACTIVE"),
        object_target=TypedEntity(raw_text="an audit", lemma="audit", is_plural=False),
        condition_tree=LogicalExpressionNode(
            operator=LogicalOperator.GT,
            metric_name="revenue",
            threshold_value=10.0,
            unit="M"
        ),
        epistemic_weight=1.0
    )

    fact = EIRProposition(
        proposition_id="fact_supp_x",
        polarity=Polarity.AFFIRMATIVE,
        modality=Modality.DECLARATIVE,
        subject=TypedEntity(raw_text="Supplier X", lemma="Supplier X", is_plural=False),
        predicate=TypedPredicate(lemma="be", tense="PRESENT", voice="ACTIVE"),
        object_target=TypedEntity(raw_text="an approved supplier", lemma="supplier", is_plural=False, qualifiers=["approved"]),
        epistemic_weight=1.0
    )

    dummy_t = [np.ones(1024, dtype=np.float32) * 0.1, np.ones(1024, dtype=np.float32) * 0.1]
    res = adapter.deliberate(np.zeros(1024, dtype=np.float32), [rule, fact], dummy_t, "tenant_test")

    derived = [p for p in res.grounded_propositions if p.epistemic_status == EpistemicStatus.CONDITIONAL_DERIVATION]
    assert len(derived) == 1, "Must derive a conditional derivation because revenue threshold is not proven!"
    assert derived[0].condition_tree is not None

def test_scope_aware_temporal_contradiction_isolation():
    """Validates that non-overlapping temporal intervals DO NOT trigger a contradiction."""
    adapter = PrismCognitionSubspaceAdapter()

    # Statement 1: Approved in 2024
    p1 = EIRProposition(
        proposition_id="prop_2024",
        polarity=Polarity.AFFIRMATIVE,
        modality=Modality.DECLARATIVE,
        subject=TypedEntity(raw_text="Supplier X", lemma="Supplier X", is_plural=False),
        predicate=TypedPredicate(lemma="approve", tense="PAST", voice="PASSIVE"),
        temporal_interval=TemporalInterval(valid_from=2024, valid_to=2024),
        epistemic_weight=1.0
    )

    # Statement 2: Not approved in 2026
    p2 = EIRProposition(
        proposition_id="prop_2026",
        polarity=Polarity.NEGATIVE,
        modality=Modality.DECLARATIVE,
        subject=TypedEntity(raw_text="Supplier X", lemma="Supplier X", is_plural=False),
        predicate=TypedPredicate(lemma="approve", tense="PRESENT", voice="PASSIVE"),
        temporal_interval=TemporalInterval(valid_from=2026, valid_to=2026),
        epistemic_weight=1.0
    )

    dummy_t = [np.ones(1024, dtype=np.float32) * 0.1, np.ones(1024, dtype=np.float32) * 0.1]
    res = adapter.deliberate(np.zeros(1024, dtype=np.float32), [p1, p2], dummy_t, "tenant_test")

    # Non-overlapping intervals must not trigger UNRESOLVED_CONTRADICTION
    assert res.ruin_distance == 0.0
    assert not any(p.epistemic_status == EpistemicStatus.UNRESOLVED_CONTRADICTION for p in res.grounded_propositions)

def test_generalized_anchor_regex_and_terminal_punctuation():
    """Validates that arbitrary IDs (e.g. prop_none_quant) parse correctly and clauses have periods."""
    realizer = SemanticSurfaceRealizer()
    auditor = EpistemicEntailmentAuditor()

    prop = EIRProposition(
        proposition_id="prop_none_quant",
        polarity=Polarity.AFFIRMATIVE,
        modality=Modality.PERMISSIVE,
        quantifier=Quantifier(qtype=QuantifierType.NONE),
        subject=TypedEntity(raw_text="patient", lemma="patient", is_plural=False),
        predicate=TypedPredicate(lemma="discontinue", tense="PRESENT", voice="ACTIVE"),
        object_target=TypedEntity(raw_text="therapy", lemma="therapy", is_plural=False),
        epistemic_weight=1.0
    )

    text, delivered_map = realizer.synthesize([prop], [])
    assert text.endswith(".")
    assert "prop_none_quant" in delivered_map
    assert auditor.audit_delivered_output(delivered_map, [prop]) is True
```

---

## 6. Execution Directives for Cursor

1. **Deploy Patches:** Update `src/cpu_llm/ir/schema.py`, `src/cpu_llm/cognition/adapter.py`, `src/cpu_llm/realizer/surface.py`, and `src/cpu_llm/audit/entailment.py`.
2. **Execute Invariant Suite:** Run `pytest tests/test_invariants.py -v`.
3. **Assert CPU Isolation:** Confirm all tests run without GPU calls:
```bash
CUDA_VISIBLE_DEVICES="" python -m pytest tests/test_invariants.py
```

---

## 7. Lexical relations (cpu-llm 1.7.0)

Words carry the relations. A paragraph proposition is still the symbolic form of one chunk when the caller stored one. Sleep compiles the relations those claims name, and an identity question can read them when the retrieved paragraph has none.

The 1024-d layout is unchanged:

| Slice | Range | Role in this layer |
| --- | --- | --- |
| Header | `[0:16]` | Bitmask, truth, anchor distance, time, model version |
| Dense core | `[16:384]` | Trained retrieval channel. Resonance amplitudes use this slice |
| Relational | `[384:512]` | Chunk-to-chunk cosine at sleep. The last 32 values hold the hand signature |
| Disentangled | `[512:640]` | Unchanged by this layer |
| Hyperbolic | `[640:768]` | Poincaré cone for a chained copula. The head in the checkpoint is off; a point is used only when its norm is inside the open unit ball |
| Identity | `[768:896]` | Unchanged. The anchor is still zero |
| Causal time | `[896:1024]` | Unchanged. This layer does not invent a causal edge |

### 7.1 Ingestion

`IngestTaxonomyIndexer` (`src/cpu_llm/taxonomy.py`) runs from `Appliance.index_chunks` and `Appliance.catalog_chunks`.

- The category is the article slug in the document id. A PrismRAG object is asked for `resolve_category` only when that method exists and returns a value.
- Terms are the content words of the chunk: tokens of four or more letters, with the stop list in `channels._content_words` removed. A fixed window of the first eight tokens is not used, because a later word such as “peat” would be dropped.
- Each term becomes a `LexicalTaxonomyTag`: `term`, `category`, `resonance_key` `{category}:{term}`, and `channel_index` 16.
- PrismResonance registers that key and the legacy key `tag:{category}:{term}`. The amplitude is the unit-norm dense core placed in a 1024-d vector. The header and the other channels of that amplitude are zero, so a packed timestamp cannot dominate the dot product. `record_co_activation` ties the marker to the document id.
- The graph node stores `taxonomy_tags` beside any supplied `proposition`, plus `relation_hands` and `related_terms`. The node embedding is the tensor that was stored, including a relation tail when one was written.
- WikiText paragraphs are not parsed into propositions. `proposition_from_chunk` keeps a record only when the realizer repeats that chunk’s first sentence. A caller-supplied proposition, such as `homarus_definition`, is stored under its document id.

Recall of a tagged paragraph (`word_taxonomy.recall_document_ids`) stays inside the articles already in the shortlist. An empty shortlist stays empty. A query word that is already written in a retrieved paragraph does not pull another article. The category number is not written into `relational[0]`. That integer pulled unrelated paragraphs into why-questions.

### 7.2 Second and third hand

PrismRAG connects words that share a category and expands a search two hops. It does not label the hops, and it stops before a third hand. `src/cpu_llm/relations.py` walks the same undirected edges one hand at a time.

- Hand 1 shares an edge with a seed word from the passage or the prompt.
- Hand 2 is the next ring. Hand 3 is the ring after that.
- Seeds are not listed again. Each hand is alphabetical and stops at 8 words.
- A word that appears in more than 12 paragraphs is not a bridge. Each word keeps at most 8 partners, the rarer ones first.
- Passage edges are the rule edges between content words that share a paragraph. `build_graph` is not run on the full vocabulary: the similarity matrix of that call is quadratic in the number of word nodes.
- The edge list is `.chorusgraph/cpu-llm/word_relations.json`. The word index is `.chorusgraph/cpu-llm/word_tags.json`.

Training (`index_chunks`, `catalog_chunks`) merges the new passage edges into that file and writes a signature into the stored tensor. The signature is a hashed signed bag of `{hand}:{word}` in the last 32 values of the relational channel, `[480:512]`, scaled by hand (1.0, 0.5, 0.25) and L2-normalized to length 0.05. The dense core and `relational[0]` stay as VectorPrism encoded them. An empty hand list leaves the tensor unchanged. The tail is a stored trace. It is not decoded back into words. The walk that names the words reads the edge list.

Creation mode uses hands 2 and 3 only. After the imagined passage has walked the named article, `_creation_relations` loads at most four stored paragraphs per hand, skipping document ids already in that walk. Those sentences are appended to `imagination["text"]` and recorded on `imagination["relations"]`. They are not added to `links` or `articles`, so the article lock on the creative walk stays the named article.

### 7.3 Sleep

`Appliance.sleep()` builds `CortexSleepConsolidator` with the SQLite graph, the cognition adapter, the vector database, and the edges in `word_relations.json`. One cycle does three writes.

**Chunk links.** For pairs that share a taxonomy category, the cosine of the full relational channel `[384:512]` must be above 0.75. When both nodes have a proposition, `PrismCognitionSubspaceAdapter.deliberate` must keep ruin at or below its threshold (default 0.85). Ruin is 1 when the pair is a contradiction on the modality matrix and 0 otherwise. There is no bilinear map and no SVD. An opposing relational slice fails the cosine check. The cycle then writes bidirectional `related_terms` (the other node’s label) and one `TAXONOMIC_LINK` edge. The node embedding is copied through unchanged.

**Word relations.** `consolidate_word_relations` (`src/cpu_llm/consolidation/sleep.py`) reads stored copulas only: predicate lemma `be`, an object, affirmative polarity. It does not invent a proposition from a WikiText paragraph.

- PrismCognition deliberates the claim. A second stored claim with the same subject, predicate, and object and a contradicting polarity blocks the link. Nothing is written for that pair.
- A claim that survives writes an `INSTANCE_OF` edge from each content word of the subject to each content word of the object. `homarus` → `lobster` for the stored European-lobster definition. Provenance `agent_id` is `prism-cognition` and modality is `COMPATIBLE`.
- Concept nodes use id and label `word:{term}`, kind `concept`, and no embedding, so they do not enter the chunk nearest-neighbor scan and they are not upserted into pgvector. Attributes hold `definitions` (the proposition, source chunk, passage words, claim words, category, ruin) and `relations` (the other term, the edge type, the judgment).
- `SUBCLASS_OF` is written only when a second accepted copula names an object word of the child as its subject, and `cone_includes` is true: both hyperbolic slices are inside the open unit ball and the child lies in the parent’s Ganea cone. The edge runs from that shared word to a content word of the parent’s object (`lobster` → `crustacean`). Provenance modality is `CONE`. Equal norms, a point outside the ball, or the cone alone do not create this edge. The cone test is O(d) per pair. It does not by itself prove a taxonomy edge.

**Vector tail.** When the cycle was given a vector database and relation edges, `sign_and_store` writes the same 0.05 hand signature onto chunk tensors. Concept nodes are skipped. The dense core is not part of that write.

A second cycle does not add a chunk link that is already present, and it does not add a word edge whose id is already stored.

### 7.4 Identity questions

`_cognize` still deliberates a proposition stored on a retrieved chunk, and a caller-supplied proposition list, before anything else.

When the shortlist has no stored proposition, and the question starts with “what is”, “what are”, “who is”, or “who are”, `lexical_evidence` reads the concept nodes:

- Every content word of the question must occur in the definition’s passage words, so “European” and “lobster” both have to be in the source chunk.
- At least one of those words must occur in the subject or the object of the stored copula.
- The tensor deliberated is that source chunk’s embedding.
- The realizer and the entailment auditor then run as on any other deliberated claim.

“What is the European lobster?” can therefore realize “Homarus gammarus is a species of clawed lobster.” from the word `lobster` after sleep, even when the retrieved paragraph is a different sentence with no proposition. “Why use hyperbolic embeddings?” does not take this path. A contradicted copula is not in the graph, so the question stays `needs_evidence_propositions`.

### 7.5 What this layer does not do

- It does not train the relational, disentangled, hyperbolic, or causal VectorPrism heads. Dense remains the trained retrieval channel.
- It does not decode the 32-d tail back into words.
- It does not call PrismThinker to invent a word link.
- It does not promote a “because” sentence into a causal edge, and it does not invent an `ObjectiveSpec` or a numeric target.
- It does not parse the WikiText paragraphs that have no round-tripping proposition into copulas. Those paragraphs stay text until a proposition is supplied.

### 7.6 Files and checks

| Path | Role |
| --- | --- |
| `src/cpu_llm/taxonomy.py` | Category tags and resonance keys at ingestion |
| `src/cpu_llm/relations.py` | Three-hand walk, passage edges, relational-tail signature |
| `src/cpu_llm/word_taxonomy.py` | Word index and tagged-paragraph recall |
| `src/cpu_llm/cortex_sleep.py` | Chunk `TAXONOMIC_LINK`, then word consolidation, then the tail upgrade |
| `src/cpu_llm/consolidation/sleep.py` | `INSTANCE_OF`, `SUBCLASS_OF`, and identity lookup |
| `src/cpu_llm/pipeline.py` | Training writes, `Appliance.sleep`, creation append, `_cognize` fallback |
| `tests/test_word_taxonomy.py` | Tags, recall bounds, no category integer in the stored tensor |
| `tests/test_relations.py` | Hands, tail norm 0.05, creation rows, sleep tail write |
| `tests/test_cortex_sleep.py` | Shared-category link, opposing polarity, contradiction ruin |
| `tests/test_lexical_relations.py` | Instance edge, identity answer, blocked contradiction, cone subclass |

## 8. Document orders and scale

Section 7 does not describe a document order or a second engine. That contract is [output formats and scale](cpu-llm-output-formats-and-scale.md).

A named format lays retrieved sentences into a fixed field list. PrismCortex stores the format record with no embedding. A paraphrase is accepted only when the frozen retrieval encoder prefers "Write {format} about {topic}" over "What is {topic}?" by at least 0.15, and that decision is cached in the ChorusGraph database. One thinker turn still owns the five heads. Another waiting turn is another engine, placed on this server or another server by `EngineManager`, and the chunk catalog moves on a CHORUS fabric frame.
