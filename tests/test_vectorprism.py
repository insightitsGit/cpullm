"""Encode and search go through VectorPrism, using the checkpoint its trainer wrote."""

import json
from pathlib import Path

from cpu_llm.retrieval import VectorPrismIndex, default_checkpoint

CHECKPOINT = default_checkpoint()
DOCUMENTS = Path(__file__).resolve().parent / "data" / "documents.example.jsonl"


def test_the_checkpoint_is_packaged_with_the_library():
    assert CHECKPOINT.is_file()
    assert CHECKPOINT.parent.parent.name == "cpu_llm"


def test_readme_search_returns_the_hyperbolic_chunk(tmp_path: Path):
    index = VectorPrismIndex(CHECKPOINT, tmp_path / "corpus.npz")
    for line in DOCUMENTS.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        assert index.upsert(row["document_id"], row["chunk_text"]) == 1
    hits = index.search("Why use hyperbolic embeddings?", top_k=3)
    assert hits[0]["document_id"] == "doc_hyper"
    assert hits[0]["tensor_1024d"].shape == (1024,)
    assert "taxonomy" in hits[0]["chunk_text"]
