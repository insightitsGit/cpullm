"""Replace a stored sentence with a new one that round-trips.

The old graph node stays. The new node is a different id. Supersession is an
edge. ``ACCOMMODATE`` closes an existing edge's ``valid_to`` and inserts the
replacement edge. It does not retire a node. The vector row uses
``valid_to_timestamp``. A question without ``as_of`` reads the open interval.
``as_of`` reads a closed interval only for a source the caller may already read.
Two live wordings of the same record, with no supersession edge, stay
contested.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from prismcortex.models import DeltaOp, Edge, Node, Operation, Provenance, StateDelta

from cpu_llm.clauses import proposition_from_chunk


def apply_correction(
    memory: Any,
    index: Any,
    *,
    document_id: str,
    prior_sentence: str,
    new_sentence: str,
    actor_id: str,
    timestamp: int,
) -> dict[str, Any]:
    """Store ``new_sentence`` beside ``document_id`` and close the old vector row."""
    nodes = getattr(memory, "_nodes", {})
    if not isinstance(nodes, dict) or document_id not in nodes:
        raise ValueError("the prior sentence is not stored on that document")
    replaced = _live_id(memory, document_id)
    live = nodes.get(replaced)
    located = memory.find_node_by_label(prior_sentence) if hasattr(memory, "find_node_by_label") else None
    if live is None or located != replaced or str(live.label) != prior_sentence:
        raise ValueError("the prior sentence is not stored on that document")
    body = new_sentence.strip()
    if not body.endswith("."):
        body = f"{body}."
    if proposition_from_chunk(f"{document_id}-next", body) is None:
        raise ValueError("the new sentence does not round-trip")
    new_id = f"{document_id}-v{int(timestamp)}"
    if isinstance(nodes, dict) and new_id in nodes:
        raise ValueError("a correction with that timestamp is already stored")
    provenance = Provenance(source_id=document_id, agent_id=actor_id)
    when = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    new_node = Node(
        id=new_id,
        kind="chunk",
        label=body,
        embedding=None,
        attributes={"base_id": document_id, "actor_id": actor_id},
        provenance=provenance,
    )
    edge = Edge(
        id=f"{new_id}-supersedes",
        src=new_id,
        dst=replaced,
        relation="SUPERSEDES",
        valid_from=when,
        provenance=provenance,
    )
    ops = [DeltaOp(operation=Operation.ASSIMILATE, node=new_node, reason="correction")]
    previous = _current_supersession(memory, replaced)
    if previous is not None:
        ops.append(
            DeltaOp(
                operation=Operation.ACCOMMODATE,
                edge=edge,
                target_id=previous,
                reason="correction",
            )
        )
    else:
        ops.append(DeltaOp(operation=Operation.ASSIMILATE, edge=edge, reason="correction"))
    memory.apply(StateDelta(ops=ops))
    if hasattr(index, "retire_document"):
        index.retire_document(replaced, int(timestamp))
    if hasattr(index, "save_version"):
        index.save_version(new_id, body, int(timestamp))
    elif hasattr(index, "save_chunks"):
        index.save_chunks([(new_id, body)])
    return {
        "document_id": document_id,
        "new_id": new_id,
        "actor_id": actor_id,
        "timestamp": int(timestamp),
        "prior_kept": document_id in getattr(memory, "_nodes", {}),
    }


def conflict_among(memory: Any, hits: list[dict[str, Any]]) -> dict[str, str] | None:
    """Two live wordings of one record, quoted from the stored labels."""
    nodes = getattr(memory, "_nodes", None)
    edges = getattr(memory, "_edges", None)
    if not isinstance(nodes, dict) or not isinstance(edges, dict):
        return None
    superseded = {
        edge.dst
        for edge in edges.values()
        if getattr(edge, "relation", "") == "SUPERSEDES"
    }
    groups: dict[str, list[Any]] = {}
    for node in nodes.values():
        base = str((node.attributes or {}).get("base_id") or node.id)
        groups.setdefault(base, []).append(node)
    hit_ids = {str(hit.get("document_id") or "") for hit in hits}
    for base, members in groups.items():
        live = [node for node in members if node.id not in superseded]
        if len(live) < 2:
            continue
        if not any(node.id in hit_ids or base in hit_ids for node in live):
            continue
        labels = [str(node.label) for node in live[:2]]
        return {
            "verdict": "CONTESTED",
            "text": f'Two stored sentences conflict: "{labels[0]}" "{labels[1]}"',
        }
    return None


def _live_id(memory: Any, document_id: str) -> str:
    nodes = getattr(memory, "_nodes", {})
    edges = getattr(memory, "_edges", {})
    superseded = {
        edge.dst
        for edge in edges.values()
        if getattr(edge, "relation", "") == "SUPERSEDES"
    } if isinstance(edges, dict) else set()
    if isinstance(nodes, dict):
        for node in nodes.values():
            base = str((node.attributes or {}).get("base_id") or node.id)
            if base == document_id and node.id not in superseded:
                return node.id
    return document_id


def _current_supersession(memory: Any, source_id: str) -> str | None:
    edges = getattr(memory, "_edges", {})
    if not isinstance(edges, dict):
        return None
    for edge in edges.values():
        if (
            getattr(edge, "relation", "") == "SUPERSEDES"
            and edge.src == source_id
            and getattr(edge, "valid_to", None) is None
        ):
            return edge.id
    return None
