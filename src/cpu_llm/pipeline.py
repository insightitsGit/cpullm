"""One turn of the CPU text path.

ChorusGraph orders the steps. There is no language-model client in this module.

Training stores a caller-supplied chunk in three places: VectorPrism writes the
1024-d tensor to pgvector, PrismResonance keeps that tensor in the catalog and
sleeps so co-activated chunks can find each other, and PrismCortex records the
chunk as a graph node.

A prompt then runs:

1. PrismGuard checks the prompt.
2. VectorPrism returns the nearest chunks and their tensors.
3. PrismResonance ranks those chunks against the query tensor.
4. PrismThinker reads the ranked chunks as evidence and names what is missing.
5. The design's deliberation adapter runs when evidence propositions are
   present, and when the retrieval is empty. The surface realizer turns that
   result into a sentence, and the auditor checks the sentence.

A proposition is stored only when the source supplies one. VectorPrism's
offline heuristic extractor can add a causal graph and numeric attributes
from the retrieved texts. A policy rule and an objective are not inferred
from those texts. PrismManifest's span grammar then allows only numeric
tokens that were cut from those chunks. The signed tool gate is separate
and needs an Ed25519 keyring.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from chorusgraph.core import END, START, Graph
from chorusgraph.core.node import dict_node_adapter
from chorusgraph.persistence.sqlite_graph_store import SqliteGraphStore
from prismcortex.models import DeltaOp, Node, Operation, StateDelta
from prismguard.runtime.factory import create_checker_rules_only
from prismresonance import FrequencyFamily, PrismResonance
from prismthinker import PrismThinker
from prismthinker.adapters.chorusgraph import to_chorusgraph
from prismthinker.adapters.vectorprism import RetrievedDocument, from_vectorprism

from cpu_llm.audit.entailment import EpistemicEntailmentAuditor
from cpu_llm.cognition.adapter import PrismCognitionSubspaceAdapter
from cpu_llm.ir.schema import EIRProposition
from cpu_llm.manifest_spans import answer_numbers_allowed, build_span_grammar, canonical_values
from cpu_llm.realizer.surface import SemanticSurfaceRealizer
from cpu_llm.retrieval import VectorPrismIndex

TENSOR_DIM = 1024


def default_checkpoint() -> Path:
    return Path(__file__).resolve().parents[2] / "checkpoints" / "vectorprism.pt"


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
        cache = Path(".chorusgraph") / "cpu-llm"
        cache.mkdir(parents=True, exist_ok=True)
        self.resonance = PrismResonance.create(
            embedding_dim=TENSOR_DIM,
            onnx_path=cache / "resonance_1024.onnx",
            state_path=cache / "resonance_state.db",
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
            self.resonance.ingest(document_id, tensor, frequency=FrequencyFamily.NEUTRAL)
            _remember_chunk(self.memory, document_id, chunk_text, tensor, bound.get(document_id))
        self.resonance.sleep()
        return len(chunks)

    def upsert(self, document_id: str, chunk_text: str) -> int:
        return self.index_chunks([(document_id, chunk_text)])

    def ask(self, message: str, propositions: list[EIRProposition] | None = None) -> dict[str, Any]:
        self._turn = {"propositions": list(propositions or [])}
        return self.graph.invoke({"message": message, "tenant_id": "cpu-llm"})


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
    graph.add_node("spans", dict_node_adapter(_spans(appliance), hop="spans"))
    graph.add_node("think", dict_node_adapter(_think(appliance), hop="think"))
    graph.add_node("cognize", dict_node_adapter(_cognize(appliance), hop="cognize"))
    graph.add_node("grammar", dict_node_adapter(_grammar(appliance), hop="grammar"))
    graph.add_edge(START, "guard")
    graph.add_conditional_edges("guard", _after_guard, {"retrieve": "retrieve", "end": END})
    graph.add_edge("retrieve", "resonate")
    graph.add_edge("resonate", "spans")
    graph.add_edge("spans", "think")
    graph.add_edge("think", "cognize")
    graph.add_edge("cognize", "grammar")
    graph.add_edge("grammar", END)
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
    return "end"


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
            [np.asarray(hit["tensor_1024d"], dtype=np.float32).reshape(-1) for hit in hits]
        )
        for chunk_id, amplitude in zip(ids, amplitudes):
            appliance.resonance.ingest(chunk_id, amplitude, frequency=FrequencyFamily.NEUTRAL)
        ranked = appliance.resonance.query(
            turn["query_tensor"],
            FrequencyFamily.NEUTRAL,
            ids,
            amplitudes,
        )
        by_id = {hit["document_id"]: hit for hit in hits}
        related = []
        for hit in ranked:
            source = by_id.get(hit.chunk_id)
            if source is None:
                continue
            related.append(
                {
                    "chunk_id": hit.chunk_id,
                    "score": float(hit.score),
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
    return metadata


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
        return {
            "thinker_directive": envelope.directive.value,
            "gather_questions": list(envelope.gather_questions),
        }

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
