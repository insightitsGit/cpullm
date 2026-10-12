"""Insert a source of truth and save its chunks.

Training stores each paragraph in pgvector and, when the first sentence can
be repeated by the realizer, stores that proposition on the graph node.
Running it again replaces the previous rows for that source.
"""

from __future__ import annotations

from cpu_llm.clauses import propositions_for
from cpu_llm.pipeline import Appliance
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


def train_wikitext(appliance: Appliance) -> tuple[int, int]:
    """Save the validation split and register every repeatable sentence."""
    chunks = [(document_id, text) for document_id, _title, text in validation_chunks()]
    propositions = propositions_for(chunks)
    stored = appliance.catalog_chunks(chunks, propositions, replace_prefix=SOURCE_PREFIX)
    return stored, len(propositions)


def main() -> None:
    appliance = Appliance(default_checkpoint())
    try:
        stored, propositions = train_wikitext(appliance)
        print(f"saved {stored} chunks under {SOURCE_PREFIX}, with {propositions} stored propositions")
    finally:
        appliance.close()


if __name__ == "__main__":
    main()
