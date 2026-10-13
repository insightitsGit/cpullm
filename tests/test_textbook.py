"""The shipped primer is original text and sits beside WikiText."""

from cpu_llm.clauses import proposition_from_chunk
from cpu_llm.documents import replace_prefix, SourceDocument
from cpu_llm.ingest import SOURCE_PREFIX, TEXTBOOK_PREFIX
from cpu_llm.source import corpus_dir, textbook_chunks, textbook_path, validation_chunks


def test_wikitext_is_shipped_inside_the_package():
    assert corpus_dir().parent.name == "data"
    assert corpus_dir().parent.parent.name == "cpu_llm"
    chunks = validation_chunks()
    assert len(chunks) == 1841
    assert chunks[0][0].startswith("wikitext2-")


def test_the_primer_is_a_separate_source_from_wikitext():
    assert textbook_path().is_file()
    chunks = textbook_chunks()
    assert len(chunks) >= 40
    ids = [document_id for document_id, _title, _text in chunks]
    assert len(set(ids)) == len(ids)
    assert all(document_id.startswith("artificial-intelligence-md-") for document_id in ids)
    assert TEXTBOOK_PREFIX == replace_prefix(SourceDocument("artificial-intelligence.md", ()))
    assert not TEXTBOOK_PREFIX.startswith(SOURCE_PREFIX)
    assert "original text written for the cpu-llm index" in chunks[0][2]


def test_every_primer_paragraph_stores_a_repeatable_sentence():
    missed = []
    for document_id, _title, text in textbook_chunks():
        if proposition_from_chunk(document_id, text) is None:
            missed.append(text.split(". ")[0])
    assert missed == []
