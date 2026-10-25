"""Remove one ingested source from the vector index, the graph, and the word index.

The resonance ledger and the shared word-relation file are left in place.
Those records are not keyed by document id, so deleting them here would either
miss rows or drop edges that other sources still use.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prismcortex.models import DeltaOp, Operation, Provenance, StateDelta

from cpu_llm.source_ids import is_paragraph_id, is_source_prefix, matches_prefix, prefix_of


def source_prefix(source: str) -> str:
    """Id prefix ingest uses for ``source``.

    A file name is slugged the same way as ingest. A document id or an id
    prefix that already ends in ``-p`` is used as that prefix.
    """
    name = str(source or "").strip().replace("\\", "/").rsplit("/", 1)[-1]
    if not name:
        raise ValueError("a source name or id prefix is required")
    if is_paragraph_id(name):
        return prefix_of(name)
    if is_source_prefix(name):
        return name
    from cpu_llm.documents import SourceDocument, replace_prefix

    prefix = replace_prefix(SourceDocument(name, ()))
    if not is_source_prefix(prefix):
        raise ValueError("the source name does not make a document id prefix")
    return prefix


def erase_graph_prefix(store: Any, prefix: str) -> dict[str, Any]:
    """Hard-remove graph nodes whose ids start with ``prefix``, and edges that touch them.

    PrismCortex forgets a node only when its provenance source matches and no
    remaining edge points at it. Nodes are stamped with this prefix and the
    touching edges are stamped the same way, then ``forget_source`` erases both.
    Output-format nodes stay, because their ids do not use a document prefix.
    """
    nodes = [node for node in store.all_nodes() if matches_prefix(str(node.id), prefix)]
    edges = [
        edge
        for edge in store.all_edges()
        if matches_prefix(str(edge.src), prefix) or matches_prefix(str(edge.dst), prefix)
    ]
    provenance = Provenance(source_id=prefix)
    ops: list[DeltaOp] = []
    for edge in edges:
        ops.append(
            DeltaOp(
                operation=Operation.ASSIMILATE,
                edge=edge.model_copy(update={"provenance": provenance}),
                reason="stamp source edge for delete",
            )
        )
    for node in nodes:
        ops.append(
            DeltaOp(
                operation=Operation.ASSIMILATE,
                node=node.model_copy(update={"provenance": provenance}),
                reason="stamp source node for delete",
            )
        )
    if ops:
        store.apply(StateDelta(ops=ops))
    receipt = store.forget_source(prefix) if ops else {"nodes_erased": 0, "edges_erased": 0}
    remaining = [node.id for node in store.all_nodes() if matches_prefix(str(node.id), prefix)]
    return {
        "nodes_erased": int(receipt.get("nodes_erased") or 0),
        "edges_erased": int(receipt.get("edges_erased") or 0),
        "nodes_remaining": remaining,
    }


def delete_stored_source(
    index: Any,
    memory: Any,
    word_tags: dict[str, dict[str, list[str]]],
    word_tags_path: Path | None,
    source: str,
) -> dict[str, Any]:
    """Delete one source from the index, the graph, and the word index."""
    from cpu_llm.word_taxonomy import drop_document_prefix

    prefix = source_prefix(source)
    vector_rows = int(index.delete_prefix(prefix))
    graph = erase_graph_prefix(memory, prefix)
    word_ids = drop_document_prefix(word_tags, prefix)
    if word_tags_path is not None:
        word_tags_path.parent.mkdir(parents=True, exist_ok=True)
        word_tags_path.write_text(json.dumps(word_tags), encoding="utf-8")
    return {
        "prefix": prefix,
        "vector_rows": vector_rows,
        "nodes_erased": graph["nodes_erased"],
        "edges_erased": graph["edges_erased"],
        "nodes_remaining": graph["nodes_remaining"],
        "word_ids": word_ids,
        "resonance": "unchanged",
        "word_relations": "unchanged",
    }
