"""VectorPrism encode and search, as the README specifies it.

The caller supplies chunk_text. This module does not split documents and does
not accept a foreign embedding. Ingest and query both use one frozen
sentence-transformer and one VectorPrism checkpoint, then
PSMRetrievalEngine.search.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pyarrow  # noqa: F401  # must load before torch; otherwise pyarrow faults on this machine

from vectorprism.base_encoder import SentenceTransformerEncoder
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

    def search(self, query: str, top_k: int = 5, *, query_tensor: object | None = None):
        """Nearest chunks for ``query``.

        Pass ``query_tensor`` when the caller already encoded ``query``. The
        scan then uses that 1024-d vector instead of encoding again.
        """
        vector = self.encode_query(query) if query_tensor is None else query_tensor
        return self.engine.search(vector, query, top_k=top_k)

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


def _like_prefix(stem: str) -> str:
    escaped = stem.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped + "%"


def _chunk_row(row) -> dict:
    return {
        "document_id": row[0],
        "chunk_text": row[1],
        "tensor_1024d": _as_float32_vector(row[2]),
    }


def _enable_pgvector(dsn: str) -> None:
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
