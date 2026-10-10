"""VectorPrism encode and search, as the README specifies it.

The caller supplies chunk_text. This module does not split documents and does
not accept a foreign embedding. Ingest and query both use one frozen
sentence-transformer and one VectorPrism checkpoint, then
PSMRetrievalEngine.search.
"""

from __future__ import annotations

import os
from pathlib import Path

import pyarrow  # noqa: F401  # must load before torch; otherwise pyarrow faults on this machine

from vectorprism.base_encoder import SentenceTransformerEncoder
from vectorprism.checkpointing import load_checkpoint
from vectorprism.db_client import PgVectorClient
from vectorprism.db_factory import make_db
from vectorprism.ingest_pipeline import IngestDocument, VectorPrismIngestPipeline
from vectorprism.retrieval_engine import PSMRetrievalEngine

ENCODER_NAME = "sentence-transformers/all-mpnet-base-v2"
LOCAL_PG_DSN = "postgresql://vectorprism:vectorprism@localhost:5433/vectorprism"


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

    def search(self, query: str, top_k: int = 5):
        return self.engine.search(self.encode_query(query), query, top_k=top_k)


def _enable_pgvector(dsn: str) -> None:
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
