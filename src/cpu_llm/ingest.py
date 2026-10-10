"""Insert a source of truth and save its chunks.

Training here means the catalog step. The source is split into paragraphs,
VectorPrism encodes each paragraph, and pgvector stores the text with its
1024-d tensor. Running it again replaces the previous rows for that source.
"""

from __future__ import annotations

from cpu_llm.retrieval import VectorPrismIndex, default_checkpoint
from cpu_llm.source import validation_chunks

SOURCE_PREFIX = "wikitext2-"


def ingest_source(
    index: VectorPrismIndex,
    chunks: list[tuple[str, str]],
    *,
    replace_prefix: str | None = None,
) -> int:
    return index.save_chunks(chunks, replace_prefix=replace_prefix)


def ingest_wikitext(index: VectorPrismIndex) -> int:
    chunks = [(document_id, text) for document_id, _title, text in validation_chunks()]
    return ingest_source(index, chunks, replace_prefix=SOURCE_PREFIX)


def main() -> None:
    index = VectorPrismIndex(default_checkpoint(), backend="pgvector")
    saved = ingest_wikitext(index)
    print(f"saved {saved} chunks to pgvector under {SOURCE_PREFIX}")


if __name__ == "__main__":
    main()
