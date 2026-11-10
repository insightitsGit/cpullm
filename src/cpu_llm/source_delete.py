"""Remove one ingested source from the vector index, the graph, the word index, and resonance tags.

The PrismResonance ledger and the shared word-relation file are left in place.
Those records are not keyed by document id, so deleting them here would either
miss rows or drop edges that other sources still use. Resonance tags are keyed
by paragraph id and are removed for this source only.
"""

from __future__ import annotations

import json
import hashlib
import hmac
import secrets
import time
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


def erase_graph_prefix(store: Any, prefix: str, *, exact: bool = False) -> dict[str, Any]:
    """Hard-remove graph nodes whose ids start with ``prefix``, and edges that touch them.

    PrismCortex forgets a node only when its provenance source matches and no
    remaining edge points at it. Nodes are stamped with this prefix and the
    touching edges are stamped the same way, then ``forget_source`` erases both.
    Output-format nodes stay, because their ids do not use a document prefix.
    """
    def matches(value):
        return str(value) == prefix if exact else matches_prefix(str(value), prefix)

    nodes = [node for node in store.all_nodes() if matches(node.id)]
    edges = [
        edge
        for edge in store.all_edges()
        if matches(edge.src) or matches(edge.dst)
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
    remaining = [node.id for node in store.all_nodes() if matches(node.id)]
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
    resonance_tags: Any = None,
) -> dict[str, Any]:
    """Delete one source from the index, the graph, the word index, and resonance tags."""
    from cpu_llm.word_taxonomy import drop_document_prefix

    prefix = source_prefix(source)
    vector_rows = int(index.delete_prefix(prefix))
    graph = erase_graph_prefix(memory, prefix)
    word_ids = drop_document_prefix(word_tags, prefix)
    if word_tags_path is not None:
        word_tags_path.parent.mkdir(parents=True, exist_ok=True)
        word_tags_path.write_text(json.dumps(word_tags), encoding="utf-8")
    tag_counts = (
        resonance_tags.delete_prefix(prefix)
        if resonance_tags is not None
        else {"units": 0, "words": 0}
    )
    return {
        "prefix": prefix,
        "vector_rows": vector_rows,
        "nodes_erased": graph["nodes_erased"],
        "edges_erased": graph["edges_erased"],
        "nodes_remaining": graph["nodes_remaining"],
        "word_ids": word_ids,
        "resonance_tags": {"units": int(tag_counts["units"]), "words": int(tag_counts["words"])},
        "resonance": "unchanged",
        "word_relations": "unchanged",
    }


def control_chunk_delete(app, document_id, confirmation=None, *, caller=None):
    """Preview or confirm removal of one exact, unchanged PostgreSQL row."""
    from cpu_llm.access import SourceForbidden, require_admin, source_allowed
    from cpu_llm.pipeline import _caller_for, _resonance_store
    from cpu_llm.word_taxonomy import drop_document_prefix

    if (not isinstance(document_id, str) or not is_paragraph_id(document_id)
            or not is_source_prefix(prefix_of(document_id))):
        raise ValueError("Provide an exact chunk ID, such as notes-p0001.")
    context = _caller_for(app, caller)
    require_admin(context)
    if context is not None and not source_allowed(document_id, context.allowed_sources):
        raise SourceForbidden("that chunk is outside this caller's scope")
    conn = getattr(app.index.db, "conn", None)
    if conn is None:
        raise ValueError("Chunk deletion requires PostgreSQL.")
    caller_id = None if context is None else context.caller_id
    key = app.__dict__.setdefault("_chunk_delete_key", secrets.token_bytes(32))
    with conn.transaction(), conn.cursor() as cursor:
        cursor.execute(
            "SELECT chunk_text, xmin::text FROM psm_document_embeddings WHERE document_id = %s FOR UPDATE",
            (document_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return dict(status="chunk_not_found", document_id=document_id)
        text, revision = row
        digest = hashlib.sha256(text.encode()).hexdigest()

        def sign(expires):
            payload = json.dumps([app.tenant_id, caller_id, document_id, revision, digest, expires])
            return hmac.digest(key, payload.encode(), "sha256").hex()

        now = int(time.time())
        if confirmation is None:
            expires = str(now + 300)
            return dict(status="confirmation_required", document_id=document_id, preview=text[:400],
                        chunk_sha256=digest, expires_in_seconds=300, confirmation=f"{expires}.{sign(expires)}")
        expires, separator, signature = confirmation.partition(".") if isinstance(confirmation, str) else ("", "", "")
        if (not separator or not expires.isascii() or not expires.isdecimal() or len(expires) > 12
                or int(expires) <= now or not signature.isascii()
                or not hmac.compare_digest(signature, sign(expires))):
            return dict(status="invalid_confirmation", document_id=document_id)
        cursor.execute("DELETE FROM psm_document_embeddings WHERE document_id = %s", (document_id,))
        graph = erase_graph_prefix(app.memory, document_id, exact=True)
        if graph["nodes_remaining"]:
            raise RuntimeError("Chunk graph cleanup did not complete.")
        if getattr(app, "knowledge_graph", None) is not None:
            app.knowledge_graph.replace([(document_id, "")])
        tags = _resonance_store(app)
        if tags is not None:
            tags.delete_prefix(document_id, exact=True)
        drop_document_prefix(app.word_tags, document_id, exact=True)
        if app.word_tags_path is not None:
            app.word_tags_path.write_text(json.dumps(app.word_tags), encoding="utf-8")
    return dict(status="deleted", document_id=document_id, vector_rows=1, **graph)
