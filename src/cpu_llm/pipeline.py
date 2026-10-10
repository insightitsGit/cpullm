"""One turn of the CPU text path.

ChorusGraph orders the steps. There is no language-model client in this module.

Training stores a caller-supplied chunk in three places: VectorPrism writes the
1024-d tensor to pgvector, PrismResonance keeps the dense-channel amplitude and
sleeps so co-activated chunks can find each other, and PrismCortex records the
chunk as a graph node.

A prompt then runs:

1. PrismGuard checks the prompt.
2. VectorPrism returns the nearest chunks and their tensors.
3. PrismResonance ranks those chunks by dense-channel interference. The header
   is a packed timestamp, not a coordinate, so it is not part of the amplitude.
   VectorPrism already chose this shortlist, so the coherence shield does not
   drop a hit whose cosine is merely moderate.
4. PrismRAG labels each retrieved chunk with the article slug already in its
   document id, and labels the prompt only when that slug's token is in the prompt.
5. PrismThinker reads the ranked chunks as evidence and names what is missing.
   A payment proposal is evaluated with PrismAgenticPay's corporate policy.
6. The design's deliberation adapter runs when evidence propositions are
   present, and when the retrieval is empty. The surface realizer turns that
   result into a sentence, and the auditor checks the sentence.
7. PrismShine checks the retrieval trace and, when a sentence exists, the
   sentence against those paragraphs. The judge stays off. An abstention
   sentence is kept. Any other blocked sentence is replaced.
8. A reply node adds a preface, follow-ups, and next steps taken from the
   passages and the open questions. It leaves the checked sentence unchanged.

A proposition is stored only when the source supplies one. VectorPrism's
offline heuristic extractor can add a causal graph and numeric attributes
from the retrieved texts. A measurement written in a chunk, such as a body
length in centimetres, is copied onto that chunk alone, and "up to" stays
a maximum in the claim's provenance. A policy rule and an objective are
not inferred from those texts. PrismManifest's span grammar then allows only numeric
tokens that were cut from those chunks. The signed tool gate is separate
and needs an Ed25519 keyring.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
from vectorprism.tensor_contract import PSMTensorContract
from chorusgraph.core import END, START, Graph
from chorusgraph.core.node import dict_node_adapter
from chorusgraph.persistence.sqlite_graph_store import SqliteGraphStore
from prismcortex.models import DeltaOp, Node, Operation, StateDelta
from prismguard.runtime.factory import create_checker_rules_only
from prismresonance import FrequencyFamily, PrismResonance
from prismthinker import PrismThinker
from prismthinker.adapters.chorusgraph import to_chorusgraph
from prismthinker.adapters.vectorprism import RetrievedDocument, from_vectorprism

from cpu_llm.agents.discovery import run_discovery
from cpu_llm.agents.reply import compose_reply
from cpu_llm.audit.entailment import EpistemicEntailmentAuditor
from cpu_llm.catalog import label_retrieval
from cpu_llm.cognition.adapter import PrismCognitionSubspaceAdapter
from cpu_llm.grounding import shine_gate, verify_grounding
from cpu_llm.ir.schema import EIRProposition
from cpu_llm.manifest_spans import answer_numbers_allowed, build_span_grammar, canonical_values
from cpu_llm.measurements import extract_stated_measurements
from cpu_llm.realizer.surface import SemanticSurfaceRealizer
from cpu_llm.retrieval import VectorPrismIndex

TENSOR_DIM = 1024


def resonance_amplitude(tensor: np.ndarray) -> np.ndarray:
    """Unit dense core in the 1024-d layout. The header is not an embedding.

    VectorPrism stores a unix timestamp in header slots 3 and 4 by reinterpreting
    the integer bits as float32. That bit pattern is about 1e26, and a float32
    dot product of two such headers overflows to infinity. The dense core is the
    trained channel and is already a unit vector. The other five channels are
    still initialization; the disentangled slice alone has a norm near 12, so
    mixing it in would rank that noise and drop the real matches under the
    coherence shield.
    """
    vector = np.asarray(tensor, dtype=np.float64).reshape(-1)
    if vector.shape != (TENSOR_DIM,):
        raise ValueError(f"expected a {TENSOR_DIM}-d tensor, got {vector.shape}")
    dense = PSMTensorContract.DENSE_CORE
    part = vector[dense.start : dense.end]
    norm = float(np.linalg.norm(part))
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError("dense channel is not a finite non-zero vector")
    amplitude = np.zeros(TENSOR_DIM, dtype=np.float32)
    amplitude[dense.start : dense.end] = (part / norm).astype(np.float32)
    return amplitude


def default_checkpoint() -> Path:
    from cpu_llm.retrieval import default_checkpoint as checkpoint

    return checkpoint()


class Appliance:
    def __init__(self, checkpoint: Path | None = None, *, dsn: str | None = None) -> None:
        self.index = VectorPrismIndex(
            checkpoint or default_checkpoint(),
            backend="pgvector",
            dsn=dsn,
        )
        self.guard = create_checker_rules_only()
        self.thinker = PrismThinker()
        self.cognition = PrismCognitionSubspaceAdapter()
        self.realizer = SemanticSurfaceRealizer()
        self.auditor = EpistemicEntailmentAuditor()
        self.shine = shine_gate()
        self.payment_policy = _payment_evaluator()
        cache = Path(".chorusgraph") / "cpu-llm"
        cache.mkdir(parents=True, exist_ok=True)
        self.resonance = PrismResonance.create(
            embedding_dim=TENSOR_DIM,
            onnx_path=cache / "resonance_1024.onnx",
            state_path=cache / "resonance_state.db",
            coherence_threshold=-1.0,
            auto_sleep=False,
        )
        self.memory = SqliteGraphStore(cache / "graph_store.db", tenant_id="cpu-llm")
        self._turn: dict[str, Any] | None = None
        self.graph = _compile(self)

    def index_chunks(
        self,
        chunks: list[tuple[str, str]],
        propositions: dict[str, EIRProposition] | None = None,
    ) -> int:
        """Store source chunks. The caller has already split the source.

        A proposition stored under a document id is the symbolic form of that
        chunk. Retrieval can then deliberate it. A chunk with no proposition
        stays text evidence.
        """
        bound = propositions or {}
        for document_id, chunk_text in chunks:
            self.index.upsert(document_id, chunk_text)
            tensor = np.asarray(self.index.encode_chunk(chunk_text), dtype=np.float32).reshape(-1)
            self.resonance.ingest(
                document_id,
                resonance_amplitude(tensor),
                frequency=FrequencyFamily.NEUTRAL,
            )
            _remember_chunk(self.memory, document_id, chunk_text, tensor, bound.get(document_id))
        self.resonance.sleep()
        return len(chunks)

    def upsert(self, document_id: str, chunk_text: str) -> int:
        return self.index_chunks([(document_id, chunk_text)])

    def ask(
        self,
        message: str,
        propositions: list[EIRProposition] | None = None,
        *,
        discover: bool = False,
        payment: Any | None = None,
        authority: Any | None = None,
    ) -> dict[str, Any]:
        if (payment is None) != (authority is None):
            raise ValueError("a payment turn needs both a proposal and an authority snapshot")
        self._turn = {
            "propositions": list(propositions or []),
            "payment": payment,
            "authority": authority,
        }
        return self.graph.invoke(
            {"message": message, "tenant_id": "cpu-llm", "discover": discover}
        )


def _remember_chunk(
    store: SqliteGraphStore,
    document_id: str,
    chunk_text: str,
    tensor: np.ndarray,
    proposition: EIRProposition | None,
) -> None:
    if store.find_node_by_label(chunk_text) is not None:
        return
    attributes: dict[str, Any] = {}
    if proposition is not None:
        attributes["proposition"] = proposition.model_dump(mode="json")
    store.apply(
        StateDelta(
            ops=[
                DeltaOp(
                    operation=Operation.ASSIMILATE,
                    node=Node(
                        id=document_id,
                        label=chunk_text,
                        kind="chunk",
                        embedding=[float(value) for value in tensor],
                        attributes=attributes,
                    ),
                    reason="vectorprism chunk",
                )
            ]
        )
    )


def _stored_proposition(store: SqliteGraphStore, chunk_text: str, tensor: np.ndarray) -> EIRProposition | None:
    subgraph = store.retrieve([float(value) for value in tensor], k=4)
    for node in subgraph.nodes:
        if node.label != chunk_text:
            continue
        raw = node.attributes.get("proposition")
        if isinstance(raw, dict):
            return EIRProposition.model_validate(raw)
    return None


def _compile(appliance: Appliance):
    graph = Graph(tenant_id="cpu-llm", graph_id="appliance")
    graph.add_node("guard", dict_node_adapter(_guard(appliance), hop="guard"))
    graph.add_node("retrieve", dict_node_adapter(_retrieve(appliance), hop="retrieve"))
    graph.add_node("resonate", dict_node_adapter(_resonate(appliance), hop="resonate"))
    graph.add_node("catalog", dict_node_adapter(_catalog(appliance), hop="catalog"))
    graph.add_node("spans", dict_node_adapter(_spans(appliance), hop="spans"))
    graph.add_node("think", dict_node_adapter(_think(appliance), hop="think"))
    graph.add_node("cognize", dict_node_adapter(_cognize(appliance), hop="cognize"))
    graph.add_node("grammar", dict_node_adapter(_grammar(appliance), hop="grammar"))
    graph.add_node("shine", dict_node_adapter(_shine(appliance), hop="shine"))
    graph.add_node("reply", dict_node_adapter(_reply, hop="reply"))
    graph.add_node("discover", dict_node_adapter(_discover(appliance), hop="discover"))
    graph.add_edge(START, "guard")
    graph.add_conditional_edges("guard", _after_guard, {"retrieve": "retrieve", "reply": "reply"})
    graph.add_edge("retrieve", "resonate")
    graph.add_edge("resonate", "catalog")
    graph.add_edge("catalog", "spans")
    graph.add_edge("spans", "think")
    graph.add_edge("think", "cognize")
    graph.add_edge("cognize", "grammar")
    graph.add_edge("grammar", "shine")
    graph.add_edge("shine", "reply")
    graph.add_conditional_edges("reply", _after_reply, {"discover": "discover", "end": END})
    graph.add_edge("discover", END)
    return graph.compile()


def _guard(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        result = appliance.guard.check(state.get("message") or "")
        update: dict[str, Any] = {
            "guard_decision": result.decision,
            "guard_category": result.matched_category,
        }
        if result.decision != "allow":
            update["answer"] = "The prompt was blocked by PrismGuard."
        return update

    return node


def _after_guard(state: dict[str, Any]) -> str:
    if state.get("guard_decision") == "allow":
        return "retrieve"
    return "reply"


def _reply(state: dict[str, Any]) -> dict[str, Any]:
    return {"reply": compose_reply(state)}


def _after_reply(state: dict[str, Any]) -> str:
    if state.get("discover") is True and state.get("guard_decision") == "allow":
        return "discover"
    return "end"


def _catalog(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        labeled = label_retrieval(state.get("message") or "", list(state.get("related") or []))
        return {
            "related": labeled["related"],
            "query_category": labeled["query_category"],
            "rag_hits": labeled["rag_hits"],
            "rag_retrieval_mode": labeled["rag_retrieval_mode"],
        }

    return node


def _shine(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        checked = verify_grounding(
            appliance.shine,
            question=state.get("message") or "",
            answer=state.get("answer"),
            related=list(state.get("related") or []),
            query_category=state.get("query_category"),
            abstention=bool(state.get("abstention_triggered")),
        )
        update = {
            "shine_decision": checked["shine_decision"],
            "shine_resolution_gate": checked["shine_resolution_gate"],
            "shine_signatures": checked["shine_signatures"],
            "shine_ok": checked["shine_ok"],
            "shine_enforced": checked["shine_enforced"],
        }
        if checked["answer"] is not None:
            update["answer"] = checked["answer"]
        return update

    return node


def _payment_evaluator():
    from prismagenticpay.core.evaluator import PrismThinkerPaymentEvaluator
    from prismagenticpay.policies.corporate import default_corporate_policies

    return PrismThinkerPaymentEvaluator(default_corporate_policies())


def evaluate_payment(evaluator, proposal, authority):
    """Run the corporate policy with a fresh authority snapshot.

    PrismAgenticPay withholds a fact that has no source timestamp. The
    snapshot just taken is the source, with the library's own freshness record.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    facts = evaluator._structured_facts(proposal, authority)
    metadata = evaluator._fresh_metadata(facts, now)
    return evaluator.evaluate_proposal(proposal, authority, fact_metadata=metadata, now=now)


def _discover(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        return {"discovery": run_discovery(state)}

    return node


def _retrieve(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        message = state.get("message") or ""
        hits = appliance.index.search(message, top_k=5)
        turn = appliance._turn or {}
        turn["query_tensor"] = np.asarray(appliance.index.encode_query(message), dtype=np.float32).reshape(-1)
        turn["hits"] = hits
        appliance._turn = turn
        return {
            "passages": [
                {
                    "document_id": hit["document_id"],
                    "chunk_text": hit["chunk_text"],
                    "final_score": float(hit["final_score"]),
                }
                for hit in hits
            ]
        }

    return node


def _resonate(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        turn = appliance._turn or {}
        hits = turn.get("hits") or []
        if not hits:
            return {"related": []}
        ids = [hit["document_id"] for hit in hits]
        amplitudes = np.stack(
            [
                resonance_amplitude(hit["tensor_1024d"])
                for hit in hits
            ]
        )
        query_amplitude = resonance_amplitude(turn["query_tensor"])
        for chunk_id, amplitude in zip(ids, amplitudes):
            appliance.resonance.ingest(chunk_id, amplitude, frequency=FrequencyFamily.NEUTRAL)
        ranked = appliance.resonance.query(
            query_amplitude,
            FrequencyFamily.NEUTRAL,
            ids,
            amplitudes,
            flat=True,
        )
        by_id = {hit["document_id"]: hit for hit in hits}
        related = []
        for hit in ranked:
            source = by_id.get(hit.chunk_id)
            if source is None:
                continue
            score = float(hit.score)
            if not math.isfinite(score):
                raise RuntimeError(f"resonance score for {hit.chunk_id} is not finite")
            related.append(
                {
                    "chunk_id": hit.chunk_id,
                    "score": score,
                    "chunk_text": source["chunk_text"],
                }
            )
        turn["related_ids"] = [item["chunk_id"] for item in related]
        appliance._turn = turn
        return {"related": related}

    return node


def _structure_metadata(related: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Causal edges and numeric attributes from VectorPrism's offline extractor."""
    if len(related) < 1:
        return {}
    from vectorprism.structure_extract import extract_structure

    extracted = extract_structure(
        {item["chunk_id"]: item["chunk_text"] for item in related},
        backend="heuristic",
    )
    causal = _causal_metadata(extracted.causal_edges)
    metadata: dict[str, dict[str, Any]] = {}
    for item in related:
        meta: dict[str, Any] = {}
        if causal is not None:
            meta["causal_graph"] = causal
        metadata[item["chunk_id"]] = meta
    for row in extracted.relational_attrs:
        claims = {
            key: float(value)
            for key, value in row.get("attributes", {}).items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        if not claims:
            continue
        meta = metadata.setdefault(str(row["doc_id"]), {})
        meta["numeric_claims"] = claims
        meta["facts"] = claims
    _attach_literal_measurements(metadata, related)
    return metadata


def _attach_literal_measurements(
    metadata: dict[str, dict[str, Any]],
    related: list[dict[str, Any]],
) -> None:
    """Copy stated measurements onto the chunk that contains them."""
    for item in related:
        claims, provenance = extract_stated_measurements(item["chunk_text"])
        if not claims:
            continue
        meta = metadata.setdefault(item["chunk_id"], {})
        numeric = dict(meta.get("numeric_claims") or {})
        facts = dict(meta.get("facts") or {})
        kept: dict[str, Any] = {}
        for key, value in claims.items():
            if key in numeric:
                continue
            numeric[key] = value
            facts.setdefault(key, value)
            kept[key] = provenance[key]
        if not kept:
            continue
        meta["numeric_claims"] = numeric
        meta["facts"] = facts
        qualifiers = dict(meta.get("numeric_qualifiers") or {})
        qualifiers.update(kept)
        meta["numeric_qualifiers"] = qualifiers


def _causal_metadata(edges: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not edges:
        return None
    nodes: list[str] = []
    causal_edges: list[dict[str, Any]] = []
    for edge in edges:
        source = str(edge["earlier_doc_id"])
        target = str(edge["later_doc_id"])
        for node in (source, target):
            if node not in nodes:
                nodes.append(node)
        causal_edges.append(
            {"source": source, "target": target, "edge_id": f"{source}->{target}", "signed": 1}
        )
    return {"nodes": nodes, "edges": causal_edges}


def _spans(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        related = [
            {"chunk_id": item["chunk_id"], "chunk_text": item["chunk_text"]}
            for item in state.get("related") or []
        ]
        index, mask = build_span_grammar(related)
        turn = appliance._turn or {}
        turn["span_index"] = index
        turn["span_mask"] = mask
        appliance._turn = turn
        return {
            "grammar_span_ids": list(mask.allowed_ids),
            "grammar_values": canonical_values(index),
        }

    return node


def _grammar(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        answer = state.get("answer")
        if not answer:
            return {"grammar_ok": True}
        turn = appliance._turn or {}
        index = turn.get("span_index")
        mask = turn.get("span_mask")
        if index is None or mask is None:
            return {"grammar_ok": False}
        return {"grammar_ok": answer_numbers_allowed(answer, index, mask)}

    return node


def _think(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        related = list(state.get("related") or [])
        metadata = _structure_metadata(related)
        documents = [
            RetrievedDocument(
                id=item["chunk_id"],
                text=item["chunk_text"],
                source="vectorprism",
                score=float(item["score"]),
                metadata=metadata.get(item["chunk_id"], {}),
            )
            for item in related
        ]
        context = from_vectorprism(state.get("message") or "", documents)
        envelope = to_chorusgraph(appliance.thinker.evaluate(context))
        update: dict[str, Any] = {
            "thinker_directive": envelope.directive.value,
            "gather_questions": list(envelope.gather_questions),
            "numeric_claims": {
                chunk_id: meta["numeric_claims"]
                for chunk_id, meta in metadata.items()
                if meta.get("numeric_claims")
            },
            "numeric_qualifiers": {
                chunk_id: meta["numeric_qualifiers"]
                for chunk_id, meta in metadata.items()
                if meta.get("numeric_qualifiers")
            },
        }
        turn = appliance._turn or {}
        proposal = turn.get("payment")
        authority = turn.get("authority")
        if proposal is not None and authority is not None:
            from prismagenticpay.policies.corporate import CORPORATE_POLICY_VERSION

            outcome = evaluate_payment(appliance.payment_policy, proposal, authority)
            update["payment_directive"] = outcome.directive
            update["payment_allowed_tools"] = list(outcome.allowed_tools)
            update["payment_gather_fact_keys"] = list(outcome.gather_fact_keys)
            update["policy_version"] = CORPORATE_POLICY_VERSION
        return update

    return node


def _cognize(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        turn = appliance._turn or {}
        propositions: list[EIRProposition] = list(turn.get("propositions") or [])
        related_ids = list(turn.get("related_ids") or [])
        hits = {hit["document_id"]: hit for hit in turn.get("hits") or []}
        if not propositions and related_ids:
            paired_ids: list[str] = []
            paired: list[EIRProposition] = []
            for chunk_id in related_ids:
                hit = hits.get(chunk_id)
                if hit is None:
                    continue
                stored = _stored_proposition(
                    appliance.memory,
                    hit["chunk_text"],
                    np.asarray(hit["tensor_1024d"], dtype=np.float32).reshape(-1),
                )
                if stored is None:
                    continue
                paired_ids.append(chunk_id)
                paired.append(stored)
            if not paired:
                return {"cognition_status": "needs_evidence_propositions"}
            propositions = paired
            related_ids = paired_ids
            turn["related_ids"] = paired_ids
            appliance._turn = turn
        if propositions and len(related_ids) != len(propositions):
            return {
                "cognition_status": "proposition_tensor_mismatch",
                "proposition_count": len(propositions),
                "tensor_count": len(related_ids),
            }
        hits = {hit["document_id"]: hit for hit in turn.get("hits") or []}
        tensors = [
            np.asarray(hits[chunk_id]["tensor_1024d"], dtype=np.float32).reshape(-1) for chunk_id in related_ids
        ]
        query = turn.get("query_tensor")
        if query is None:
            query = np.zeros(TENSOR_DIM, dtype=np.float32)
        result = appliance.cognition.deliberate(
            query,
            propositions,
            tensors,
            state.get("tenant_id") or "cpu-llm",
        )
        sentence, delivered = appliance.realizer.synthesize(result.grounded_propositions, result.graph_edges)
        audited = appliance.auditor.audit_delivered_output(delivered, result.grounded_propositions)
        return {
            "cognition_status": "deliberated",
            "answer": sentence,
            "audit_passed": audited,
            "abstention_triggered": result.abstention_triggered,
            "ruin_distance": result.ruin_distance,
            "audit_trace_id": result.audit_trace_id,
        }

    return node
