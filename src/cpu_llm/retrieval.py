"""VectorPrism encode and search, as the README specifies it.

The caller supplies chunk_text. This module does not split documents and does
not accept a foreign embedding. Ingest and query both use one frozen
sentence-transformer and one VectorPrism checkpoint, then
PSMRetrievalEngine.search.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pyarrow  # noqa: F401  # must load before torch; otherwise pyarrow faults on this machine

import numpy as np
from vectorprism.base_encoder import SentenceTransformerEncoder
from vectorprism.tensor_contract import PSMTensorContract
from vectorprism.db_client import _as_float32_vector
from vectorprism.checkpointing import load_checkpoint
from vectorprism.db_client import PgVectorClient
from vectorprism.db_factory import make_db
from vectorprism.ingest_pipeline import IngestDocument, VectorPrismIngestPipeline
from vectorprism.retrieval_engine import PSMRetrievalEngine

ENCODER_NAME = "sentence-transformers/all-mpnet-base-v2"
_PARAGRAPH = re.compile(r"-p\d+$")
LOCAL_PG_DSN = "postgresql://vectorprism:vectorprism@localhost:5433/vectorprism"


def default_checkpoint() -> Path:
    """Trained projection shipped inside the package.

    A checkout that still keeps the file at the repository root is accepted
    so older layouts keep working.
    """
    packaged = Path(__file__).resolve().parent / "checkpoints" / "vectorprism.pt"
    if packaged.is_file():
        return packaged
    return Path(__file__).resolve().parents[2] / "checkpoints" / "vectorprism.pt"


class VectorPrismIndex:
    def __init__(
        self,
        checkpoint: Path,
        store: Path | None = None,
        *,
        backend: str = "memory",
        dsn: str | None = None,
    ) -> None:
        loaded = load_checkpoint(checkpoint, map_location="cpu")
        encoder = SentenceTransformerEncoder(ENCODER_NAME, device="cpu")
        if backend == "pgvector":
            target = dsn or os.environ.get("VECTORPRISM_PG_DSN") or LOCAL_PG_DSN
            _enable_pgvector(target)
            self.db = PgVectorClient(target)
            self.db.ensure_schema()
            _widen_dense_beam(self.db)
        elif backend == "memory":
            if store is None:
                raise ValueError("a memory backend needs a store path")
            self.db = make_db("memory", store=str(store), autoload=False)
        else:
            raise ValueError(f"backend must be memory or pgvector, not {backend}")
        self.pipeline = VectorPrismIngestPipeline(
            encoder=encoder,
            adapter=loaded["adapter"],
            db=self.db,
            model_version=loaded["model_version"],
            enabled_channels=loaded.get("enabled_channels"),
        )
        self.engine = PSMRetrievalEngine(
            db_client=self.db,
            causal_matrix=loaded["causal_matrix"],
            hard_truth_filter=False,
            model_version=loaded["model_version"],
        )

    def upsert(self, document_id: str, chunk_text: str) -> int:
        return self.pipeline.upsert_documents(
            [IngestDocument(document_id=document_id, chunk_text=chunk_text)]
        )

    def encode_chunk(self, chunk_text: str):
        return self.pipeline.encode_texts([chunk_text])[0]

    def encode_query(self, query: str):
        return self.pipeline.encode_query(query)

    def intent_for(self, query: str, *, query_tensor=None):
        """Reuse the prompt tensor and lazily cache six routing prototypes."""
        from cpu_llm.prompt_intent import PROTOTYPE_TEXTS, route_prompt
        if not hasattr(self, '_intent_prototypes'):
            vectors = self.pipeline.encode_texts(list(PROTOTYPE_TEXTS.values()))
            self._intent_prototypes = dict(zip(PROTOTYPE_TEXTS, vectors))
        vector = self.encode_query(query) if query_tensor is None else query_tensor
        return route_prompt(query, query_tensor=vector, enabled_channels=self.pipeline.enabled_channels,
                            prototypes=self._intent_prototypes, causal_matrix=self.engine.causal_matrix)

    def search(self, query: str, top_k: int = 5, *, query_tensor: object | None = None, as_of: int | None = None):
        """Nearest chunks for ``query``.

        Pass ``query_tensor`` when the caller already encoded ``query``. The
        scan then uses that 1024-d vector instead of encoding again.
        """
        vector = self.encode_query(query) if query_tensor is None else query_tensor
        flags = getattr(self.pipeline, "enabled_channels", None) or {}
        auxiliary = ("relational", "disentangled", "hyperbolic", "causal")
        dense_only = not any(_channel_on(flags, name) for name in auxiliary)
        fetch = max(top_k, 32) if dense_only else top_k
        when = _as_of(self, as_of)
        if when is None:
            hits = self.engine.search(vector, query, top_k=fetch)
        else:
            hits = self.engine.search(vector, query, top_k=fetch, as_of=when)
        if dense_only:
            hits = _order_by_dense_core(hits, vector)
        return hits[:top_k]

    def search_allowed(
        self,
        query: str,
        allowed: frozenset[str] | set[str],
        top_k: int = 5,
        *,
        query_tensor: object | None = None,
        as_of: int | None = None,
    ) -> list[dict]:
        """Nearest chunks whose document id is inside ``allowed``.

        The installed ``RetrievalEngine.search`` cannot take a document-id
        predicate. This query adds that predicate to the WHERE clause, then
        orders by the dense-core distance and applies LIMIT. A forbidden row
        therefore cannot fill the five. ``allowed`` empty returns nothing and
        does not scan.
        """
        scope = frozenset(allowed)
        if not scope:
            return []
        if not hasattr(self.db, "conn"):
            raise ValueError("a source scope requires the pgvector backend")
        vector = self.encode_query(query) if query_tensor is None else query_tensor
        clause, clause_params = _allowed_clause(scope)
        _widen_dense_beam(self.db)
        query_vector = np.asarray(vector, dtype=np.float32).reshape(-1)
        dense = PSMTensorContract.DENSE_CORE
        dense_slice = query_vector[dense.start : dense.end]
        flags = getattr(self.pipeline, "enabled_channels", None) or {}
        auxiliary = ("relational", "disentangled", "hyperbolic", "causal")
        dense_only = not any(_channel_on(flags, name) for name in auxiliary)
        fetch = max(top_k, 32) if dense_only else top_k
        where = "epistemic_truth >= %s AND anchor_dist <= %s AND " + clause
        params: list[object] = [0.0, 0.85, *clause_params]
        model_version = getattr(self.engine, "model_version", None)
        if model_version is not None:
            where += " AND model_version = %s"
            params.append(int(model_version))
        when = _as_of(self, as_of)
        if when is not None:
            where += " AND valid_timestamp <= %s AND (valid_to_timestamp IS NULL OR valid_to_timestamp > %s)"
            params.extend([when, when])
        params.extend([dense_slice, fetch])
        with self.db.conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT document_id, chunk_text, tensor_1024d
                FROM psm_document_embeddings
                WHERE {where}
                ORDER BY dense_core_slice <=> %s
                LIMIT %s
                """,
                tuple(params),
            )
            rows = cursor.fetchall()
        hits = [_chunk_row(row) for row in rows]
        hits = [hit for hit in hits if _row_in_scope(str(hit["document_id"]), scope)]
        if dense_only:
            hits = _order_by_dense_core(hits, vector)
        for hit in hits:
            if "final_score" not in hit:
                hit["final_score"] = 0.0
        return hits[:top_k]

    def retire_document(self, document_id: str, timestamp: int) -> None:
        """Close the open validity interval of one vector row.

        Later searches pass ``as_of`` so a closed row drops out of the current
        interval. The row stays in the table.
        """
        self._history = True
        if not hasattr(self.db, "conn"):
            retired = getattr(self, "_retired", None)
            if retired is None:
                self._retired = {}
            self._retired[document_id] = int(timestamp)
            return
        with self.db.conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE psm_document_embeddings
                SET valid_to_timestamp = %s
                WHERE document_id = %s AND valid_to_timestamp IS NULL
                """,
                (int(timestamp), document_id),
            )
        self.db.conn.commit()

    def chunks_for_articles(self, document_ids: list[str]) -> list[dict]:
        """Every stored paragraph of the articles named by ``document_ids``.

        A paragraph id such as ``wikitext2-homarus-gammarus-p0001`` loads every
        row with that article stem. An id with no paragraph suffix loads that
        row alone. This does not scan the rest of the index.
        """
        if not hasattr(self.db, "conn"):
            return []
        exact: list[str] = []
        prefixes: list[str] = []
        for document_id in document_ids:
            if _PARAGRAPH.search(document_id):
                stem = _PARAGRAPH.sub("-p", document_id)
                if stem not in prefixes:
                    prefixes.append(stem)
            elif document_id not in exact:
                exact.append(document_id)
        found: dict[str, dict] = {}
        with self.db.conn.cursor() as cursor:
            for document_id in exact:
                cursor.execute(
                    """
                    SELECT document_id, chunk_text, tensor_1024d
                    FROM psm_document_embeddings
                    WHERE document_id = %s
                    """,
                    (document_id,),
                )
                for row in cursor.fetchall():
                    found[row[0]] = _chunk_row(row)
            for stem in prefixes:
                cursor.execute(
                    """
                    SELECT document_id, chunk_text, tensor_1024d
                    FROM psm_document_embeddings
                    WHERE document_id LIKE %s ESCAPE '\\'
                    ORDER BY document_id
                    """,
                    (_like_prefix(stem),),
                )
                for row in cursor.fetchall():
                    found[row[0]] = _chunk_row(row)
        return [found[key] for key in sorted(found)]

    def lead_for_slug(self, slug: str) -> dict | None:
        """The stored lead paragraph whose article slug is ``slug``.

        Validation ids and test-split ids are both accepted. A slug that is
        not a stored title returns nothing.
        """
        if not hasattr(self.db, "conn"):
            return None
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            return None
        document_ids = [f"wikitext2-{slug}-p0001", f"wikitext2test-{slug}-p0001"]
        with self.db.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT document_id, chunk_text, tensor_1024d
                FROM psm_document_embeddings
                WHERE document_id = ANY(%s)
                ORDER BY document_id
                LIMIT 1
                """,
                (document_ids,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        hit = _chunk_row(row)
        hit["final_score"] = 1.0
        return hit

    def save_chunks(self, chunks: list[tuple[str, str]], *, replace_prefix: str | None = None) -> int:
        """Encode chunk_text with VectorPrism and store the 1024-d rows.

        ``replace_prefix`` deletes previous rows for that source before insert,
        so a second training run replaces the old chunks instead of leaving them.
        """
        if replace_prefix:
            if not hasattr(self.db, "conn"):
                raise ValueError("replacing a source requires the pgvector backend")
            with self.db.conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM psm_document_embeddings WHERE document_id LIKE %s",
                    (replace_prefix + "%",),
                )
        if not chunks:
            return 0
        documents = [
            IngestDocument(document_id=document_id, chunk_text=chunk_text)
            for document_id, chunk_text in chunks
        ]
        return self.pipeline.upsert_documents(documents, batch_size=32)

    def delete_prefix(self, prefix: str) -> int:
        """Delete stored rows whose document id starts with ``prefix``.

        ``prefix`` is the ingest id prefix, such as ``notes-p``. The match is a
        bound SQL LIKE prefix. A prefix that is not that shape is refused
        before the database is touched.
        """
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*-p", prefix):
            raise ValueError("source prefix must look like a document id prefix ending in -p")
        if not hasattr(self.db, "conn"):
            raise ValueError("deleting a source requires the pgvector backend")
        with self.db.conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM psm_document_embeddings WHERE document_id LIKE %s",
                (prefix + "%",),
            )
            deleted = cursor.rowcount
        return int(deleted or 0)


def ensure_namespace_vectors(index: VectorPrismIndex, namespace: str) -> None:
    """Copy the vector table into ``ns_<namespace>`` when it is not there yet.

    ``search_path`` lists the tenant schema first and ``public`` second. An
    unqualified ``CREATE TABLE IF NOT EXISTS`` finds the public table and
    does not make a tenant table. Inserts would then land in ``public`` and
    both tenants would read one index. This creates the tenant table from
    the public table's shape so later reads and writes stay in the tenant schema.
    """
    schema = f"ns_{namespace}"
    with index.db.conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = 'psm_document_embeddings'
            """,
            (schema,),
        )
        if cursor.fetchone():
            return
        cursor.execute(
            f'CREATE TABLE "{schema}".psm_document_embeddings '
            "(LIKE public.psm_document_embeddings INCLUDING ALL)"
        )
    index.db.conn.commit()


def _as_of(index: VectorPrismIndex, as_of: int | None) -> int | None:
    if as_of is not None:
        return int(as_of)
    if getattr(index, "_history", False):
        return int(time.time())
    return None


def _allowed_clause(allowed: frozenset[str]) -> tuple[str, list[object]]:
    """A bound predicate for document ids. It belongs in WHERE, before LIMIT."""
    exact: list[str] = []
    likes: list[str] = []
    params: list[object] = []
    for item in sorted(allowed):
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*-p", item):
            likes.append("document_id LIKE %s ESCAPE '\\'")
            params.append(_like_prefix(item))
        elif re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item):
            exact.append(item)
        else:
            raise ValueError("an allowed source must be a document id or an id prefix ending in -p")
    parts: list[str] = []
    if exact:
        parts.append("document_id = ANY(%s)")
        params.insert(0, exact)
    parts.extend(likes)
    if not parts:
        raise ValueError("an allowed source must be a document id or an id prefix ending in -p")
    return "(" + " OR ".join(parts) + ")", params


def _row_in_scope(document_id: str, allowed: frozenset[str]) -> bool:
    return any(document_id == item or document_id.startswith(item) for item in allowed)


def _like_prefix(stem: str) -> str:
    escaped = stem.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped + "%"


def _chunk_row(row) -> dict:
    return {
        "document_id": row[0],
        "chunk_text": row[1],
        "tensor_1024d": _as_float32_vector(row[2]),
    }


def _widen_dense_beam(db) -> None:
    """Ask HNSW to visit enough dense neighbors to return the true one.

    The default beam omitted a stored paragraph whose dense core was the
    nearest match. Only that core is a trained channel, so the beam has to
    be wide enough for the later dense ordering to see it.
    """
    conn = getattr(db, "conn", None)
    if conn is None:
        return
    with conn.cursor() as cursor:
        cursor.execute("SET hnsw.ef_search = 400")


def _channel_on(flags, name: str) -> bool:
    if isinstance(flags, dict):
        return bool(flags.get(name))
    return bool(getattr(flags, name, False))


def _order_by_dense_core(hits: list, query) -> list:
    """Rank by the trained dense core. Untrained channel slices do not vote."""
    query_vector = np.asarray(query, dtype=np.float64).reshape(-1)
    dense = PSMTensorContract.DENSE_CORE
    query_slice = query_vector[dense.start : dense.end]
    query_norm = float(np.linalg.norm(query_slice)) or 1.0

    def score(hit) -> float:
        tensor = hit.get("tensor_1024d")
        if tensor is None:
            return 0.0
        vector = np.asarray(tensor, dtype=np.float64).reshape(-1)
        if vector.size < dense.end:
            return 0.0
        part = vector[dense.start : dense.end]
        part_norm = float(np.linalg.norm(part)) or 1.0
        value = float(np.dot(part, query_slice) / (part_norm * query_norm))
        return value if np.isfinite(value) else 0.0

    return sorted(hits, key=score, reverse=True)


def _enable_pgvector(dsn: str) -> None:
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
