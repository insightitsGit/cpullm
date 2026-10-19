"""Answers spoken from retrieved passages: memory for a role, the models for a rule."""

from cpu_llm.agents.reply import compose_reply
from cpu_llm.memory.frames import frame_from_chunk, resolve_frames

POLICIES = [
    "Business class is allowed for flights over six hours.",
    "A flight from Los Angeles to Tokyo is about eleven hours.",
    "A flight from Los Angeles to Phoenix takes 2 hours.",
    "Employees may book business class because long flights cause fatigue.",
]
APPLE = "John ate a yellow apple in his house."


def _state(message: str, chunks: list[str]) -> dict:
    return {
        "message": message,
        "guard_decision": "allow",
        "related": [{"chunk_id": f"c{i}", "chunk_text": text} for i, text in enumerate(chunks)],
    }


def test_a_retrieved_rule_is_spoken_as_yes_no_unknown_and_cause():
    yes = compose_reply(_state("Can I fly business class from Los Angeles to Tokyo?", POLICIES))
    no = compose_reply(_state("Can I fly business class from Los Angeles to Phoenix?", POLICIES))
    unknown = compose_reply(_state("Can I fly business class from Los Angeles to Paris?", POLICIES))
    cause = compose_reply(_state("Why may employees book business class?", POLICIES))
    assert yes["situation"]["verdict"] == "YES" and yes["text"].startswith("Yes.") and "11 hours" in yes["text"]
    assert no["situation"]["verdict"] == "UNKNOWN" and "2 hours" in no["text"] and "only" not in no["text"].casefold()
    assert unknown["situation"]["verdict"] == "UNKNOWN" and unknown["text"].lower().startswith("it depends")
    assert cause["situation"]["verdict"] == "CAUSE" and "long flights cause fatigue" in cause["text"]
    assert "Business class is allowed" in yes["body"]


def test_two_retrieved_rules_are_spoken_as_a_conflict():
    reply = compose_reply(
        _state(
            "Is a permit required for the truck at the dock?",
            [
                "A permit is required for trucks over 2 tons.",
                "A permit is forbidden for trucks over 5 tons.",
                "The truck at the dock weighs 6 tons.",
            ],
        )
    )
    assert reply["situation"]["verdict"] == "CONTESTED"
    assert "conflict" in reply["text"]


def test_a_role_question_stays_with_the_event_frame():
    reply = compose_reply(
        {
            "message": "What color was the apple John ate?",
            "guard_decision": "allow",
            "frame": True,
            "answer": APPLE,
            "related": [{"chunk_id": "apple-1", "chunk_text": APPLE}],
            "frame_result": resolve_frames("What color was the apple John ate?", [frame_from_chunk("apple-1", APPLE)]),
        }
    )
    assert reply["text"] == "The apple John ate was yellow."
    assert reply["situation"] is None


def test_a_decision_the_passages_do_not_cover_is_not_a_quotation():
    reply = compose_reply(
        _state(
            "Can I bring my dog?",
            ["Business class is allowed for flights over six hours."],
        )
    )
    assert reply["situation"]["verdict"] == "NONE"
    assert reply["text"] == "The retrieved passages do not settle that."
    assert "Business class" not in reply["text"]


def test_a_passage_with_no_rule_stays_the_retrieved_sentence():
    reply = compose_reply(
        _state(
            "What is the European lobster?",
            ["Homarus gammarus, known as the European lobster, is a species of clawed lobster."],
        )
    )
    assert reply["situation"] is None
    assert "European lobster" in reply["text"]


def test_a_paraphrase_uses_the_trained_extractor_when_it_is_present():
    import pytest

    pytest.importorskip("transformers")
    from fact_bridge import model_root

    if model_root() is None:
        pytest.skip("no trained extractor checkpoint")
    reply = compose_reply(
        _state(
            "Is a crane required for the crate in bay 4?",
            [
                "A crane is required for shipments heavier than 2 tons.",
                "The crate in bay 4 weighs 3 tons.",
                "A crate is a shipment.",
            ],
        )
    )
    assert reply["situation"]["verdict"] == "YES"
    assert "3" in reply["text"]
