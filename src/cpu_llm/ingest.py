"""Insert a source of truth and save its chunks.

Training stores each paragraph in pgvector and, when the first sentence can
be repeated by the realizer, stores that proposition on the graph node.
Running it again replaces the previous rows for that source.
"""

from __future__ import annotations

from cpu_llm.clauses import propositions_for
from cpu_llm.pipeline import Appliance
from cpu_llm.retrieval import VectorPrismIndex, default_checkpoint
from cpu_llm.source import test_chunks, validation_chunks

SOURCE_PREFIX = "wikitext2-"
TEST_PREFIX = "wikitext2test-"


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
    return _train_split(appliance, validation_chunks(), SOURCE_PREFIX)


def train_wikitext_test(appliance: Appliance) -> tuple[int, int]:
    """Save the test split and register every repeatable sentence.

    This is a second set of Good and Featured articles. It does not replace
    the validation rows.
    """
    return _train_split(appliance, test_chunks(), TEST_PREFIX)


def _train_split(
    appliance: Appliance,
    rows: list[tuple[str, str, str]],
    prefix: str,
) -> tuple[int, int]:
    chunks = [(document_id, text) for document_id, _title, text in rows]
    propositions = propositions_for(chunks)
    stored = appliance.catalog_chunks(chunks, propositions, replace_prefix=prefix)
    return stored, len(propositions)


def main() -> None:
    import sys

    appliance = Appliance(default_checkpoint())
    try:
        if "--test" in sys.argv:
            stored, propositions = train_wikitext_test(appliance)
            prefix = TEST_PREFIX
        else:
            stored, propositions = train_wikitext(appliance)
            prefix = SOURCE_PREFIX
        print(f"saved {stored} chunks under {prefix}, with {propositions} stored propositions")
    finally:
        appliance.close()


if __name__ == "__main__":
    main()
