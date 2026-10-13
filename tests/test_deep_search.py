"""A deep-search prompt keeps every chunk the words can reach."""

from cpu_llm.agents.deep_search import collect_possibilities
from cpu_llm.classifier import deep_search_trigger
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
