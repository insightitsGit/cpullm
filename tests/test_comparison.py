"""A comparison keeps every named topic, in each prompt mode."""

from cpu_llm.agents.reply import compose_reply
from cpu_llm.classifier import creative_writing_trigger, deep_search_trigger
from cpu_llm.comparison import comparison_sides, possibilities_by_side, rows_for_side
from cpu_llm.pipeline import _after_deep, _after_imagine, _after_shine, _possibility_rows
from prismrag_patch.store.types import GraphEdge


def test_a_plain_question_is_not_a_comparison():
    assert comparison_sides("What is the European lobster?") == []
    assert comparison_sides("Describe a different lobster.") == []


def test_comparison_prompts_name_each_topic():
    assert comparison_sides("Compare Mount Elbert and Mount Everest.") == [
        "Mount Elbert",
        "Mount Everest",
    ]
    assert comparison_sides(
        "What is the difference between the European lobster and the American lobster?"
    ) == ["European lobster", "American lobster"]
    assert comparison_sides("lobster vs crab") == ["lobster", "crab"]
    assert comparison_sides("Compare oak, elm, and ash.") == ["oak", "elm", "ash"]
    assert comparison_sides("Deep search compare lobster and crab.") == ["lobster", "crab"]


def test_each_topic_keeps_its_own_chunks_and_a_missing_topic_stays_empty():
    tags = {
        "lobster": {"homarus-gammarus": ["wikitext2-homarus-gammarus-p0001", "wikitext2-homarus-gammarus-p0003"]},
        "european": {
            "homarus-gammarus": ["wikitext2-homarus-gammarus-p0001"],
            "settlers": ["wikitext2-settlers-p0004"],
        },
        "clawed": {"homarus-gammarus": ["wikitext2-homarus-gammarus-p0009"]},
        "crab": {"cancer-pagurus": ["wikitext2-cancer-pagurus-p0001"]},
    }
    edges = [GraphEdge("lobster", "clawed", "rule", 1.0)]
    found = possibilities_by_side(["European lobster", "crab"], tags, edges)
    lobster = [item["document_id"] for item in found["possibilities"] if item["side"] == "European lobster"]
    crab = [item["document_id"] for item in found["possibilities"] if item["side"] == "crab"]
    assert lobster == ["wikitext2-homarus-gammarus-p0001"]
    assert "wikitext2-settlers-p0004" not in lobster
    assert "wikitext2-homarus-gammarus-p0009" not in lobster
    assert crab == ["wikitext2-cancer-pagurus-p0001"]
    elk = [
        item
        for item in possibilities_by_side(["lobster", "elk"], tags, edges)["possibilities"]
        if item["side"] == "elk"
    ]
    assert elk == []


def test_a_named_article_does_not_load_the_other_topic():
    class _Index:
        def lead_for_slug(self, slug):
            if slug == "mount-elbert":
                return {"document_id": "wikitext2-mount-elbert-p0001"}
            return None

        def chunks_for_articles(self, document_ids):
            assert document_ids == ["wikitext2-mount-elbert-p0001"]
            return [
                {"document_id": "wikitext2-mount-elbert-p0001", "chunk_text": "Mount Elbert is the highest summit of the Rocky Mountains."},
                {"document_id": "wikitext2-mount-elbert-p0002", "chunk_text": "The mountain stands in Colorado."},
            ]

    rows = rows_for_side(_Index(), {}, "Mount Elbert")
    assert [row["document_id"] for row in rows] == [
        "wikitext2-mount-elbert-p0001",
        "wikitext2-mount-elbert-p0002",
    ]


def test_the_three_prompt_modes_still_have_a_place_for_a_comparison():
    assert _after_shine({"compare": True}) == "compare"
    assert _after_shine({"compare": True, "deep": True}) == "deep"
    assert _after_shine({"compare": True, "creative": True}) == "gather"
    assert _after_shine({}) == "reply"


def test_a_prompt_that_names_two_agents_runs_both():
    deep_compare = "Deep search compare lobster and crab."
    assert deep_search_trigger(deep_compare)
    assert comparison_sides(deep_compare) == ["lobster", "crab"]
    assert creative_writing_trigger(deep_compare) == []
    assert _after_shine({"deep": True, "compare": True}) == "deep"
    assert _after_deep({"deep": True, "compare": True}) == "compare"

    creative_compare = "Imagine a comparison of the European lobster and the American lobster."
    assert creative_writing_trigger(creative_compare)
    assert comparison_sides(creative_compare) == ["European lobster", "American lobster"]
    assert _after_shine({"creative": True, "compare": True}) == "gather"
    assert _after_imagine({"creative": True, "compare": True}) == "compare"

    deep_creative = "Imagine a deep search of the European lobster."
    assert deep_search_trigger(deep_creative)
    assert creative_writing_trigger(deep_creative)
    assert comparison_sides(deep_creative) == []
    assert _after_deep({"deep": True, "creative": True}) == "gather"
    assert _after_imagine({"deep": True, "creative": True, "compare": True}) == "compare"
    assert _after_deep({"deep": True}) == "reply"


def test_the_next_agent_keeps_each_topic_from_the_deep_search():
    state = {
        "possibilities": [
            {"document_id": "lobster-1", "chunk_text": "The European lobster is Homarus gammarus.", "side": "lobster"},
            {"document_id": "crab-1", "chunk_text": "The crab is Cancer pagurus.", "side": "crab"},
        ]
    }
    assert [row["document_id"] for row in _possibility_rows(state, "lobster")] == ["lobster-1"]
    assert [row["document_id"] for row in _possibility_rows(state, "crab")] == ["crab-1"]


def test_the_reply_speaks_each_side():
    reply = compose_reply(
        {
            "message": "Compare Mount Elbert and Mount Everest.",
            "answer": "Mount Elbert is the highest summit of the Rocky Mountains.",
            "guard_decision": "allow",
            "related": [{"chunk_id": "wikitext2-mount-elbert-p0001", "chunk_text": "Mount Elbert is the highest summit of the Rocky Mountains."}],
            "comparison": {
                "sides": [
                    {"label": "Mount Elbert", "text": "Mount Elbert is the highest summit of the Rocky Mountains."},
                    {"label": "Mount Everest", "text": ""},
                ]
            },
        }
    )
    assert reply["body"] == "Mount Elbert is the highest summit of the Rocky Mountains."
    assert "Comparison:" in reply["text"]
    assert "Mount Elbert:" in reply["text"]
    assert "Mount Everest:" in reply["text"]
    assert "No stored sentence for this side." in reply["text"]
