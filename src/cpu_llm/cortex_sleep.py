"""Offline consolidation of lexical links already stored in the graph.

This runs when the caller asks for a sleep cycle. It reads nodes from the
SQLite graph, compares the relational channel of the stored tensors, and
asks PrismCognition whether the stored propositions contradict.

A link is written only when three checks hold:

* the nodes share a taxonomy category from ingestion
* the cosine of the relational channel, [384:512], is above 0.75
* PrismCognition's ruin on that pair stays at or below its threshold

Ruin is 1 when the pair is a contradiction and 0 otherwise. There is no
bilinear map and no SVD in PrismCognition. An opposing relational slice
fails the cosine check, so those terms are not merged.

The write updates ``related_terms`` on both nodes and adds one
``TAXONOMIC_LINK`` edge. The node embedding is copied through unchanged.
The same cycle judges stored copula claims with PrismCognition and writes
``INSTANCE_OF`` word edges for the claims it accepts. A chained claim whose
child tensor lies in the parent cone becomes ``SUBCLASS_OF``.
When a vector database and relation edges are supplied, the same cycle
writes the second- and third-hand signature into the relational tail of
each stored tensor. The dense core is not part of that write. Concept
nodes are not written back into that database.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
from prismcortex.models import DeltaOp, Edge, Operation, StateDelta
from vectorprism.tensor_contract import PSMTensorContract

from cpu_llm.cognition.adapter import PrismCognitionSubspaceAdapter
from cpu_llm.ir.schema import EIRProposition

_RELATIONAL = PSMTensorContract.RELATIONAL
_COHERENCE = 0.75
_LINK = "TAXONOMIC_LINK"


class CortexSleepConsolidator:
    def __init__(
        self,
        memory_store: Any,
        cognition_adapter: PrismCognitionSubspaceAdapter | None = None,
        vector_db: Any | None = None,
        relation_edges: list[Any] | None = None,
    ) -> None:
        self.store = memory_store
        self.cognition = cognition_adapter or PrismCognitionSubspaceAdapter()
        self.vector_db = vector_db
        self.relation_edges = relation_edges

    def run_sleep_cycle(self, max_pairs: int = 500) -> int:
        nodes = list(self.store.all_nodes())
        if len(nodes) < 2:
            self._consolidate_words()
            self._upgrade_vectors()
            return 0
        formed = 0
        seen: set[tuple[str, str]] = set()
        for node in nodes[: max(0, max_pairs)]:
            tensor = _embedding(node)
            if tensor is None:
                continue
            neighbors = self.store.retrieve(tensor.tolist(), k=5)
            for candidate in neighbors.nodes:
                if candidate.id == node.id:
                    continue
                pair = tuple(sorted((node.id, candidate.id)))
                if pair in seen or self._already_linked(node.id, candidate.id):
                    seen.add(pair)
                    continue
                seen.add(pair)
                other = _embedding(candidate)
                if other is None:
                    continue
                if not _shared_category(node, candidate):
                    continue
                if _relational_cosine(tensor, other) <= _COHERENCE:
                    continue
                if self._ruined(node, candidate, tensor, other):
                    continue
                self._write_link(node.id, candidate.id)
                formed += 1
        self._consolidate_words()
        self._upgrade_vectors()
        return formed

    def _consolidate_words(self) -> int:
        from cpu_llm.consolidation.sleep import consolidate_word_relations

        return consolidate_word_relations(self.store, self.cognition)

    def _upgrade_vectors(self) -> int:
        if self.vector_db is None or not self.relation_edges:
            return 0
        from cpu_llm.relations import sign_and_store

        rows = []
        for node in self.store.all_nodes():
            if getattr(node, "kind", "") == "concept" or not node.embedding:
                continue
            rows.append((node.id, node.label, np.asarray(node.embedding, dtype=np.float32)))
        return sign_and_store(self.vector_db, rows, self.relation_edges)

    def _already_linked(self, left_id: str, right_id: str) -> bool:
        for edge in self.store.all_edges():
            if edge.relation != _LINK or not edge.is_current:
                continue
            if {edge.src, edge.dst} == {left_id, right_id}:
                return True
        return False

    def _ruined(self, left: Any, right: Any, tensor_a: np.ndarray, tensor_b: np.ndarray) -> bool:
        proposition_a = _proposition(left)
        proposition_b = _proposition(right)
        if proposition_a is None or proposition_b is None:
            return False
        result = self.cognition.deliberate(
            tensor_a,
            [proposition_a, proposition_b],
            [tensor_a, tensor_b],
            "cpu-llm",
        )
        return result.ruin_distance > self.cognition.ruin_threshold

    def _write_link(self, left_id: str, right_id: str) -> None:
        fresh = {node.id: node for node in self.store.all_nodes()}
        left = fresh[left_id]
        right = fresh[right_id]
        left_attributes = _with_related(left.attributes, right.label)
        right_attributes = _with_related(right.attributes, left.label)
        edge_id = "taxonomic-" + hashlib.sha256(f"{left.id}|{right.id}".encode("utf-8")).hexdigest()[:16]
        self.store.apply(
            StateDelta(
                ops=[
                    DeltaOp(
                        operation=Operation.ASSIMILATE,
                        node=left.model_copy(update={"attributes": left_attributes}),
                        reason="sleep taxonomic link",
                    ),
                    DeltaOp(
                        operation=Operation.ASSIMILATE,
                        node=right.model_copy(update={"attributes": right_attributes}),
                        reason="sleep taxonomic link",
                    ),
                    DeltaOp(
                        operation=Operation.ASSIMILATE,
                        edge=Edge(id=edge_id, src=left.id, dst=right.id, relation=_LINK),
                        reason="sleep taxonomic link",
                    ),
                ]
            )
        )


def _embedding(node: Any) -> np.ndarray | None:
    if not node.embedding:
        return None
    vector = np.asarray(node.embedding, dtype=np.float32).reshape(-1)
    if vector.size != PSMTensorContract.TOTAL_DIM:
        return None
    return vector


def _shared_category(left: Any, right: Any) -> bool:
    return bool(_categories(left) & _categories(right))


def _categories(node: Any) -> set[str]:
    tags = node.attributes.get("taxonomy_tags") or []
    found: set[str] = set()
    if not isinstance(tags, list):
        return found
    for tag in tags:
        if isinstance(tag, dict) and tag.get("category"):
            found.add(str(tag["category"]))
    return found


def _relational_cosine(left: np.ndarray, right: np.ndarray) -> float:
    part_a = left[_RELATIONAL.start : _RELATIONAL.end].astype(np.float64)
    part_b = right[_RELATIONAL.start : _RELATIONAL.end].astype(np.float64)
    norm_a = float(np.linalg.norm(part_a))
    norm_b = float(np.linalg.norm(part_b))
    if norm_a == 0.0 or norm_b == 0.0 or not np.isfinite(norm_a) or not np.isfinite(norm_b):
        return 0.0
    score = float(np.dot(part_a, part_b) / (norm_a * norm_b))
    if not np.isfinite(score):
        return 0.0
    return score


def _proposition(node: Any) -> EIRProposition | None:
    raw = node.attributes.get("proposition")
    if isinstance(raw, dict):
        return EIRProposition.model_validate(raw)
    return None


def _with_related(attributes: dict[str, Any], label: str) -> dict[str, Any]:
    updated = dict(attributes)
    related = {str(term) for term in (updated.get("related_terms") or [])}
    related.add(label)
    updated["related_terms"] = sorted(related)
    return updated
