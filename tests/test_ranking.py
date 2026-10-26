"""A best or ranking question reports a stored order, or says that none is stored."""

from cpu_llm.agents.reply import compose_reply
from cpu_llm.ranking import ranking_notice
from cpu_llm.realizer.constructions import bundle_from_chunks
from cpu_llm.realizer.ranker import realize

_SPECIES = (
    "Homarus gammarus, known as the European lobster or common lobster, "
    "is a species of clawed lobster from the eastern Atlantic Ocean, "
    "Mediterranean Sea and parts of the Black Sea."
)
_RANKED = "The European lobster is the best lobster in Europe."
_OTHER = "Paris is the best city in France."


def _state(message: str, chunks: list[str], answer: str | None = None) -> dict:
    related = [
        {"chunk_id": f"doc-{index}", "score": 0.9 - (index * 0.1), "chunk_text": text}
        for index, text in enumerate(chunks)
    ]
    state = {
        "message": message,
        "guard_decision": "allow",
        "cognition_status": "deliberated" if answer else "needs_evidence_propositions",
        "related": related,
    }
    if answer is not None:
        state["answer"] = answer
        state["audit_passed"] = True
    return state


def test_a_best_question_without_a_stored_order_says_what_is_missing():
    reply = compose_reply(_state("what is the best lobster in eroupe?", [_SPECIES], answer=_SPECIES))
    assert reply["body"] == _SPECIES
    assert reply["ranking"]["status"] == "absent"
    assert "do not state a ranking" in reply["text"]
    assert _SPECIES in reply["text"]
    assert "0.9" not in reply["ranking"]["text"]
    assert "is the best" not in reply["text"]


def test_a_stored_ranking_is_quoted_as_written():
    reply = compose_reply(
        _state("what is the best lobster in eroupe?", [_SPECIES, _RANKED], answer=_SPECIES)
    )
    assert reply["body"] == _SPECIES
    assert reply["ranking"]["status"] == "stated"
    assert reply["ranking"]["sentences"] == [_RANKED]
    assert _RANKED in reply["text"]


def test_a_ranking_already_spoken_is_not_rewritten():
    notice = ranking_notice("What is the best lobster?", [_RANKED], spoken=_RANKED)
    assert notice is not None
    assert notice["status"] == "stated"
    assert notice["text"] == "The sentence above states the stored ranking."
    assert "Paris" not in notice["text"]


def test_a_ranking_about_another_topic_is_not_the_answer():
    reply = compose_reply(_state("what is the best lobster in eroupe?", [_SPECIES, _OTHER], answer=_SPECIES))
    assert reply["ranking"]["status"] == "absent"
    assert _OTHER not in reply["text"].split("Ranking:", 1)[-1]
    assert _SPECIES in reply["text"]


def test_an_empty_shortlist_announces_that_no_ranking_was_retrieved():
    reply = compose_reply(
        {
            "message": "Which lobster ranks first?",
            "guard_decision": "allow",
            "answer": "No passage was retrieved.",
            "related": [],
        }
    )
    assert reply["ranking"]["status"] == "absent"
    assert "no ranking is stored" in reply["ranking"]["text"]


def test_a_definition_question_has_no_ranking_section():
    reply = compose_reply(_state("What is the European lobster?", [_SPECIES]))
    assert reply["ranking"] is None
    assert "Ranking:" not in reply["text"]


def test_the_ranker_copies_a_stored_order_and_ignores_its_score():
    bundle = bundle_from_chunks(
        [("species", _SPECIES), ("ranked", _RANKED)],
    )
    result = realize(bundle, "what is the best lobster in eroupe?", scores="uniform")
    assert result["model_checkpoint_id"] is None
    assert result["mode"] == "deterministic_fallback"
    assert "stored_ranking" in result["construction_ids"] or "ranking_gap" in result["construction_ids"]
    assert _RANKED in result["text"]
    assert "do not state a ranking" not in result["text"]
    assert "0." not in result["text"]


def test_the_ranker_says_when_the_passages_do_not_state_an_order():
    bundle = bundle_from_chunks([("species", _SPECIES)])
    result = realize(bundle, "what is the best lobster in eroupe?", scores=[0.99])
    assert result["verified"] is True
    assert "ranking_gap" in result["construction_ids"]
    assert "do not state a ranking" in result["text"]
    assert "is the best" not in result["text"]
    assert _SPECIES.split(",")[0] in result["text"]


def test_a_definition_does_not_grow_a_ranking_clause_in_the_ranker():
    result = realize(bundle_from_chunks([("species", _SPECIES)]), "What is the European lobster?")
    assert "Ranking:" not in result["text"]
    assert "ranking_gap" not in result["construction_ids"]
    assert "stored_ranking" not in result["construction_ids"]


def test_a_plural_topic_matches_the_singular_in_the_question():
    notice = ranking_notice(
        "Which ferry is best for fuel economy?",
        ["The Cedar is best for fuel economy among Millhaven ferries."],
    )
    assert notice is not None
    assert notice["status"] == "stated"
    assert "Millhaven ferries" in notice["text"]
