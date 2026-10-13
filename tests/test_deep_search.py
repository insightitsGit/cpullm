"""A deep-search prompt keeps every chunk the words can reach."""

import json

import numpy as np

from cpu_llm.agents.deep_search import collect_possibilities
from cpu_llm.classifier import deep_search_trigger
from cpu_llm.pipeline import _deep
from cpu_llm.relations import relation_hands
from prismrag_patch.store.types import GraphEdge


def test_a_plain_question_does_not_ask_for_deep_search():
    assert deep_search_trigger("What is the European lobster?") == []
    assert deep_search_trigger("Search the index for lobster") == []


def test_deep_search_keeps_every_matching_chunk():
    assert deep_search_trigger("Deep search the European lobster.") == [
        "the prompt asks for a deep search"
    ]
    tags = {
        "lobster": {
            "homarus-gammarus": ["wikitext2-homarus-gammarus-p0001", "wikitext2-homarus-gammarus-p0003"],
            "other-article": ["wikitext2-other-article-p0001"],
        },
        "clawed": {"homarus-gammarus": ["wikitext2-homarus-gammarus-p0009"]},
        "ceramics": {"tikal": ["wikitext2-tikal-p0004"]},
    }
    edges = [GraphEdge("lobster", "clawed", "rule", 1.0), GraphEdge("clawed", "ceramics", "rule", 1.0)]
    found = collect_possibilities("Deep search lobster", tags, edges)
    assert found["seeds"] == ["lobster"]
    ids = [item["document_id"] for item in found["possibilities"]]
    assert ids == [
        "wikitext2-homarus-gammarus-p0001",
        "wikitext2-homarus-gammarus-p0003",
        "wikitext2-homarus-gammarus-p0009",
        "wikitext2-other-article-p0001",
        "wikitext2-tikal-p0004",
    ]
    by_id = {item["document_id"]: item for item in found["possibilities"]}
    assert by_id["wikitext2-other-article-p0001"]["via"] == ["word"]
    assert "hand-2" in by_id["wikitext2-tikal-p0004"]["via"]
    assert relation_hands(edges, ["lobster"], limit=100_000)[2] == ["ceramics"]


def test_the_deep_node_keeps_numeric_arrays_off_the_graph_state(tmp_path):
    class Database:
        def get_by_ids(self, ids):
            return [
                {
                    "document_id": ids[0],
                    "chunk_text": "Homarus gammarus is a species of clawed lobster.",
                    "tensor_1024d": np.zeros(4, dtype=np.float32),
                }
            ]

    class Index:
        db = Database()

    class Box:
        relations_path = tmp_path / "edges.json"
        word_tags = {"lobster": {"homarus": ["doc-1"]}}
        index = Index()
        _deep_tensors: dict = {}

    box = Box()
    result = _deep(box)({"message": "Deep search lobster", "comparison_sides": []})
    json.dumps(result)
    assert "tensor_1024d" not in result["possibilities"][0]
    assert result["possibilities"][0]["chunk_text"].startswith("Homarus")
    assert "doc-1" in box._deep_tensors
