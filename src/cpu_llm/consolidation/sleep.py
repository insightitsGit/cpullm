"""Judge the relation between words that a stored claim already names.

PrismRAG groups the words of a passage under one category. PrismCognition
does not contain a bilinear map and does not invent a subclass tree. It can
reject a pair of claims that contradict, and it can accept one affirmative
copula.

Sleep keeps that copula. Each content word in the subject is an instance of
each content word in the object, written as ``INSTANCE_OF``. When a second
stored copula names that object as its subject, and the child tensor sits in
the parent's Poincaré cone, the shared word is ``SUBCLASS_OF`` the parent's
object. The cone does not create that edge on its own.

An identity question can then read the accepted copula from the word nodes
when the retrieved paragraph has no proposition of its own.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
from prismcortex.models import DeltaOp, Edge, Node, Operation, Provenance, StateDelta

from cpu_llm.channels import _content_words
from cpu_llm.cognition.adapter import PrismCognitionSubspaceAdapter, poincare_slice
from cpu_llm.geometry.poincare import is_in_entailment_cone
from cpu_llm.ir.schema import EIRProposition, Polarity

_INSTANCE = "INSTANCE_OF"
_SUBCLASS = "SUBCLASS_OF"
_COPULA = "be"


def consolidate_word_relations(
    store: Any,
    cognition: PrismCognitionSubspaceAdapter | None = None,
) -> int:
    """Write word relations cognition accepted. Return how many new edges were added."""
    checker = cognition or PrismCognitionSubspaceAdapter()
    claims = _copula_claims(store)
    accepted = []
    for claim in claims:
        judged = _accepted(checker, claim, claims)
        if judged is not None:
            accepted.append(judged)
    definitions: dict[str, list[dict[str, Any]]] = {}
    relations: dict[str, list[dict[str, Any]]] = {}
    edges: list[Edge] = []
    for node, proposition, tensor, checked in accepted:
        _remember_instance(node, proposition, checked.ruin_distance, definitions, relations, edges)
    for child in accepted:
        for parent in accepted:
            if child[1].proposition_id == parent[1].proposition_id:
                continue
            if not cone_includes(parent[2], child[2]):
                continue
            _remember_subclass(child[1], parent[1], parent[0].id, relations, edges)
    return _commit(store, definitions, relations, edges)


def lexical_evidence(store: Any, message: str) -> list[tuple[EIRProposition, np.ndarray]]:
    """Accepted definitions whose passage contains the question and whose claim names one of its words.

    A question that is not asking what something is returns nothing. The
    tensor is the source chunk's stored embedding.
    """
    if not is_identity_question(message):
        return []
    wanted = set(_content_words(message))
    if not wanted:
        return []
    nodes = {node.id: node for node in store.all_nodes()}
    found: list[tuple[EIRProposition, np.ndarray]] = []
    seen: set[str] = set()
    for node in nodes.values():
        if getattr(node, "kind", "") != "concept":
            continue
        for item in node.attributes.get("definitions") or []:
            if not isinstance(item, dict):
                continue
            passage = set(item.get("passage_words") or [])
            claim = set(item.get("claim_words") or [])
            if not wanted.issubset(passage) or not (wanted & claim):
                continue
            raw = item.get("proposition")
            if not isinstance(raw, dict):
                continue
            proposition = EIRProposition.model_validate(raw)
            if proposition.proposition_id in seen:
                continue
            source = nodes.get(str(item.get("source_id")))
            tensor = _embedding(source) if source is not None else None
            if tensor is None:
                continue
            seen.add(proposition.proposition_id)
            found.append((proposition, tensor))
    return found


def is_identity_question(message: str) -> bool:
    text = " ".join(message.casefold().split())
    return text.startswith(("what is ", "what are ", "who is ", "who are "))


def cone_includes(parent: np.ndarray, child: np.ndarray) -> bool:
    """True when both hyperbolic slices lie in the unit ball and the child is inside the parent cone."""
    parent_point = poincare_slice(parent)
    child_point = poincare_slice(child)
    if parent_point is None or child_point is None:
        return False
    return is_in_entailment_cone(parent_point, child_point)


def _copula_claims(store: Any) -> list[tuple[Any, EIRProposition, np.ndarray]]:
    found: list[tuple[Any, EIRProposition, np.ndarray]] = []
    for node in store.all_nodes():
        if getattr(node, "kind", "") == "concept":
            continue
        proposition = _proposition(node)
        tensor = _embedding(node)
        if proposition is None or tensor is None or not _is_copula(proposition):
            continue
        found.append((node, proposition, tensor))
    return found


def _accepted(
    cognition: PrismCognitionSubspaceAdapter,
    claim: tuple[Any, EIRProposition, np.ndarray],
    claims: list[tuple[Any, EIRProposition, np.ndarray]],
) -> tuple[Any, EIRProposition, np.ndarray, Any] | None:
    node, proposition, tensor = claim
    if proposition.polarity is not Polarity.AFFIRMATIVE:
        return None
    for _other_node, other, other_tensor in claims:
        if other.proposition_id == proposition.proposition_id or not _same_atom(proposition, other):
            continue
        opposed = cognition.deliberate(
            tensor,
            [proposition, other],
            [tensor, other_tensor],
            "cpu-llm",
        )
        if opposed.ruin_distance > cognition.ruin_threshold:
            return None
    checked = cognition.deliberate(tensor, [proposition], [tensor], "cpu-llm")
    if checked.abstention_triggered or checked.ruin_distance > cognition.ruin_threshold:
        return None
    return node, proposition, tensor, checked


def _remember_instance(
    node: Any,
    proposition: EIRProposition,
    ruin: float,
    definitions: dict[str, list[dict[str, Any]]],
    relations: dict[str, list[dict[str, Any]]],
    edges: list[Edge],
) -> None:
    subject_words = _content_words(proposition.subject.raw_text)
    object_words = _content_words(proposition.object_target.raw_text if proposition.object_target else "")
    if not subject_words or not object_words:
        return
    definition = {
        "proposition": proposition.model_dump(mode="json"),
        "source_id": node.id,
        "relation": _INSTANCE,
        "cognition": "COMPATIBLE",
        "ruin_distance": float(ruin),
        "passage_words": sorted(set(_content_words(str(node.label)))),
        "claim_words": sorted(set(subject_words) | set(object_words)),
        "categories": sorted(_categories(node)),
        "cone_inclusion": False,
    }
    for word in sorted(set(subject_words) | set(object_words)):
        definitions.setdefault(word, []).append(definition)
    for left in subject_words:
        for right in object_words:
            relations.setdefault(left, []).append(
                _row(right, _INSTANCE, proposition.proposition_id, ruin, cone=False)
            )
            edges.append(
                _edge(left, right, _INSTANCE, proposition.proposition_id, node.id, ruin, cone=False)
            )


def _remember_subclass(
    child: EIRProposition,
    parent: EIRProposition,
    parent_id: str,
    relations: dict[str, list[dict[str, Any]]],
    edges: list[Edge],
) -> None:
    if child.object_target is None or parent.subject is None or parent.object_target is None:
        return
    shared = set(_content_words(child.object_target.raw_text)) & set(_content_words(parent.subject.raw_text))
    upper = _content_words(parent.object_target.raw_text)
    for word in sorted(shared):
        for parent_word in upper:
            relations.setdefault(word, []).append(
                _row(parent_word, _SUBCLASS, parent.proposition_id, 0.0, cone=True)
            )
            edges.append(
                _edge(word, parent_word, _SUBCLASS, parent.proposition_id, parent_id, 0.0, cone=True)
            )


def _commit(
    store: Any,
    definitions: dict[str, list[dict[str, Any]]],
    relations: dict[str, list[dict[str, Any]]],
    edges: list[Edge],
) -> int:
    current = {node.id: node for node in store.all_nodes()}
    existing_edges = {edge.id for edge in store.all_edges()}
    ops: list[DeltaOp] = []
    words = sorted(set(definitions) | set(relations))
    for word in words:
        node_id = f"word:{word}"
        previous = current.get(node_id)
        attributes = _merged_attributes(previous, definitions.get(word, []), relations.get(word, []))
        if previous is not None and previous.attributes == attributes and previous.kind == "concept":
            continue
        ops.append(
            DeltaOp(
                operation=Operation.ASSIMILATE,
                node=Node(id=node_id, label=node_id, kind="concept", embedding=None, attributes=attributes),
                reason="sleep word relation",
            )
        )
    fresh = 0
    for edge in edges:
        if edge.id in existing_edges:
            continue
        existing_edges.add(edge.id)
        fresh += 1
        ops.append(
            DeltaOp(operation=Operation.ASSIMILATE, edge=edge, reason="sleep word relation")
        )
    if ops:
        store.apply(StateDelta(ops=ops))
    return fresh


def _merged_attributes(
    previous: Any,
    definitions: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> dict[str, Any]:
    attributes = dict(previous.attributes) if previous is not None else {}
    stored_definitions = [item for item in (attributes.get("definitions") or []) if isinstance(item, dict)]
    stored_relations = [item for item in (attributes.get("relations") or []) if isinstance(item, dict)]
    attributes["definitions"] = _dedupe(stored_definitions + definitions, ("source_id", "relation"))
    attributes["relations"] = _dedupe(stored_relations + relations, ("term", "relation", "proposition_id"))
    return attributes


def _dedupe(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        if fields == ("source_id", "relation"):
            proposition = row.get("proposition")
            proposition_id = proposition.get("proposition_id") if isinstance(proposition, dict) else None
            key = (proposition_id, row.get("source_id"), row.get("relation"))
        else:
            key = tuple(row.get(field) for field in fields)
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def _row(term: str, relation: str, proposition_id: str, ruin: float, *, cone: bool) -> dict[str, Any]:
    return {
        "term": term,
        "relation": relation,
        "cognition": "COMPATIBLE",
        "ruin_distance": float(ruin),
        "proposition_id": proposition_id,
        "cone_inclusion": cone,
    }


def _edge(
    left: str,
    right: str,
    relation: str,
    proposition_id: str,
    source_id: str,
    ruin: float,
    *,
    cone: bool,
) -> Edge:
    digest = hashlib.sha256(f"{relation}|{left}|{right}|{proposition_id}".encode("utf-8")).hexdigest()[:16]
    return Edge(
        id=f"{relation.lower()}-{digest}",
        src=f"word:{left}",
        dst=f"word:{right}",
        relation=relation,
        weight=1.0,
        confidence=1.0 if ruin <= 0.0 else max(0.0, 1.0 - float(ruin)),
        provenance=Provenance(
            source_id=source_id,
            modality="CONE" if cone else "COMPATIBLE",
            raw_ref=proposition_id,
            agent_id="prism-cognition",
        ),
    )


def _is_copula(proposition: EIRProposition) -> bool:
    return (
        proposition.predicate.lemma.casefold() == _COPULA
        and proposition.object_target is not None
        and bool(proposition.subject.raw_text.strip())
    )


def _same_atom(left: EIRProposition, right: EIRProposition) -> bool:
    if left.subject.lemma.casefold() != right.subject.lemma.casefold():
        return False
    if left.predicate.lemma.casefold() != right.predicate.lemma.casefold():
        return False
    left_object = None if left.object_target is None else left.object_target.lemma.casefold()
    right_object = None if right.object_target is None else right.object_target.lemma.casefold()
    return left_object == right_object


def _proposition(node: Any) -> EIRProposition | None:
    raw = node.attributes.get("proposition")
    if isinstance(raw, dict):
        return EIRProposition.model_validate(raw)
    return None


def _embedding(node: Any) -> np.ndarray | None:
    if node is None or not node.embedding:
        return None
    vector = np.asarray(node.embedding, dtype=np.float32).reshape(-1)
    if vector.size != 1024:
        return None
    return vector


def _categories(node: Any) -> set[str]:
    tags = node.attributes.get("taxonomy_tags") or []
    found: set[str] = set()
    if not isinstance(tags, list):
        return found
    for tag in tags:
        if isinstance(tag, dict) and tag.get("category"):
            found.add(str(tag["category"]))
    return found
