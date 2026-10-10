"""Every validation paragraph is one chunk, with tokenizer marks removed."""

from cpu_llm.source import detokenize, validation_chunks


def test_markers_and_contractions_are_restored():
    assert detokenize("M @-@ 82") == "M-82"
    assert detokenize("a , b") == "a, b"
    assert detokenize("men 's team") == "men's team"
    assert detokenize("does n't") == "doesn't"


def test_validation_split_emits_every_paragraph():
    chunks = validation_chunks()
    titles = {title for _doc_id, title, _text in chunks}
    lobster = [text for _doc_id, title, text in chunks if title == "Homarus gammarus"]
    assert len(titles) == 60
    assert len(chunks) == 1841
    assert len(lobster) > 1
    assert "European lobster" in lobster[0]
    assert len({doc_id for doc_id, _, _ in chunks}) == 1841
    blob = "\n".join(text for _, _, text in chunks)
    assert " @-@" not in blob
    assert " 's" not in blob
