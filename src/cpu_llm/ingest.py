"""Insert a source of truth and save its chunks.

Training stores each paragraph in pgvector and, when the first sentence can
be repeated by the realizer, stores that proposition on the graph node.
Running it again replaces the previous rows for that source.
"""

from __future__ import annotations

from cpu_llm.clauses import propositions_for
from cpu_llm.documents import SourceDocument, replace_prefix
from cpu_llm.pipeline import Appliance
from cpu_llm.retrieval import VectorPrismIndex, default_checkpoint
from cpu_llm.source import finance_chunks, test_chunks, textbook_chunks, validation_chunks

SOURCE_PREFIX = "wikitext2-"
TEST_PREFIX = "wikitext2test-"
TEXTBOOK_PREFIX = replace_prefix(SourceDocument("artificial-intelligence.md", ()))
FINANCE_PREFIX = replace_prefix(SourceDocument("finance-validation.md", ()))


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


def train_textbook(appliance: Appliance) -> tuple[int, int]:
    """Save the shipped artificial-intelligence primer.

    The primer uses its own id prefix, so this does not replace WikiText.
    """
    return _train_split(appliance, textbook_chunks(), TEXTBOOK_PREFIX)


def train_finance(appliance: Appliance) -> tuple[int, int]:
    """Save the finance validation sentences.

    The file uses its own id prefix, so this does not replace WikiText or the primer.
    """
    return _train_split(appliance, finance_chunks(), FINANCE_PREFIX)


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
            _report(*train_wikitext_test(appliance), TEST_PREFIX)
        elif "--textbook" in sys.argv:
            _report(*train_textbook(appliance), TEXTBOOK_PREFIX)
        elif "--finance" in sys.argv:
            _report(*train_finance(appliance), FINANCE_PREFIX)
        else:
            _report(*train_wikitext(appliance), SOURCE_PREFIX)
            _report(*train_textbook(appliance), TEXTBOOK_PREFIX)
            _report(*train_finance(appliance), FINANCE_PREFIX)
    finally:
        appliance.close()


def _report(stored: int, propositions: int, prefix: str) -> None:
    print(f"saved {stored} chunks under {prefix}, with {propositions} stored propositions")


if __name__ == "__main__":
    main()
