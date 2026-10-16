"""A color is spoken only when that word is a slice of a round-tripped sentence."""

from types import SimpleNamespace

import numpy as np

from cpu_llm.agents.reply import compose_reply
from cpu_llm.memory.frames import frame_from_chunk, frame_trigger, resolve_frames
from cpu_llm.pipeline import _after_compare, _after_shine, _assimilation, _frame


APPLE = "John ate a yellow apple in his house."
DATED = "John ate a yellow apple in his house in 2019."


def test_a_plain_question_does_not_enter_the_frame_agent():
    assert frame_trigger("What is the European lobster?") == []
    assert frame_trigger("Is a red apple better than a yellow apple?") == []
    assert frame_trigger("Compare the European lobster and Robert Boulter.") == []
    assert _after_shine({}) == "reply"
    assert _after_shine({"frame": True, "compare": True}) == "compare"
    assert _after_compare({"frame": True}) == "frame"
    assert _after_shine({"frame": True}) == "frame"
    assert _after_shine({"delivery_blocked": True, "frame": True}) == "reply"


def test_the_apple_sentence_keeps_color_and_location_as_source_slices():
    frame = frame_from_chunk("apple-1", APPLE)
    assert frame is not None
    sentence = frame["sentence"]
    assert frame["color"]["text"] == "yellow"
    assert sentence[frame["color"]["start"] : frame["color"]["end"]] == "yellow"
    assert frame["location"]["text"] == "in his house"
    assert frame["agent"]["text"] == "John"
    assert frame["patient"]["text"] == "apple"
    assert "owner" not in frame
    assert frame_from_chunk("apple-2", "John did not eat a yellow apple in his house.") is None
    assert frame_from_chunk("apple-3", "John ate no yellow apple in his house.") is None


def test_the_color_question_is_answered_from_the_stored_span():
    frame = frame_from_chunk("apple-1", APPLE)
    result = resolve_frames("What color was the apple John ate?", [frame])
    assert result["ok"] is True
    assert result["text"] == "The apple John ate was yellow."
    assert "owns" not in result["text"]
    where = resolve_frames("Where did John eat the apple?", [frame])
    assert where["text"] == "John ate the apple in his house."
    assert "owns" not in where["text"]
    who = resolve_frames("Who ate the apple?", [frame])
    assert who["text"] == "John ate the apple."


def test_a_different_year_and_a_second_color_do_not_pick_a_winner():
    dated = frame_from_chunk("apple-2019", DATED)
    assert dated["time"]["text"] == "in 2019"
    assert resolve_frames("What color was the apple John ate in 2020?", [dated])["ok"] is False
    assert resolve_frames("What color was the apple John ate in 2019?", [dated])["value"] == "yellow"
    yellow = frame_from_chunk("apple-yellow", "The apple was yellow.")
    red = frame_from_chunk("apple-red", "The apple was red.")
    conflict = resolve_frames("What color was the apple?", [yellow, red])
    assert conflict["abstained"] is True
    assert conflict["value"] == ""
    assert conflict["text"] == "Two stored sentences state different colors."


def test_the_frame_node_speaks_the_join_and_stores_the_record_on_the_chunk():
    result = _frame(None)(
        {
            "message": "What color was the apple John ate?",
            "frame_reasons": ["the prompt asks for a color written in a stored sentence"],
            "passages": [{"document_id": "apple-1", "chunk_text": APPLE}],
        }
    )
    assert result["frame_result"]["text"] == "The apple John ate was yellow."
    assert "proposition" not in result
    store = SimpleNamespace(find_node_by_label=lambda _text: None)
    op = _assimilation(store, "apple-1", APPLE, np.zeros(4), None, {}, {})
    assert op.node.attributes["event_frame"]["color"]["text"] == "yellow"


def test_a_frame_question_is_spoken_as_the_joined_sentence():
    reply = compose_reply(
        {
            "message": "What color was the apple John ate?",
            "guard_decision": "allow",
            "frame": True,
            "answer": "John ate a yellow apple in his house.",
            "frame_result": resolve_frames("What color was the apple John ate?", [frame_from_chunk("apple-1", APPLE)]),
        }
    )
    assert reply["text"] == "The apple John ate was yellow."
    assert reply["body"] == "John ate a yellow apple in his house."
    assert reply["text"] != reply["body"]


SELLER = "The apple seller ate a yellow apple in his house."
FALLBACK = "I don't have enough grounded evidence to answer that confidently."


def test_a_shine_rejection_stays_the_delivered_sentence():
    state = {
        "message": "What color was the apple John ate?",
        "guard_decision": "allow",
        "frame": True,
        "shine_ok": False,
        "shine_enforced": True,
        "answer": FALLBACK,
        "passages": [{"document_id": "review-1", "chunk_text": APPLE}],
    }
    assert _after_shine(state) == "reply"
    state.update(_frame(None)(state))
    assert compose_reply(state)["text"] == FALLBACK
    blocked = compose_reply(
        {
            "message": "What color was the apple John ate?",
            "guard_decision": "allow",
            "delivery_blocked": "audit",
            "frame": True,
            "answer": None,
            "related": [{"chunk_id": "review-1", "chunk_text": APPLE, "score": 1.0}],
            "frame_result": {"status": "answered", "verified": True, "text": "The apple John ate was yellow."},
        }
    )
    assert blocked["text"] == "The checked sentence was withheld because it did not match the stored proposition."
    mixed = compose_reply(
        {
            "message": "What color was the apple John ate?",
            "guard_decision": "allow",
            "frame": True,
            "summarize": True,
            "answer": APPLE,
            "brief": {"summary": APPLE},
            "frame_result": resolve_frames("What color was the apple John ate?", [frame_from_chunk("apple-1", APPLE)]),
        }
    )
    assert mixed["text"].startswith(APPLE)
    assert "Event:\nThe apple John ate was yellow." in mixed["text"]


def test_nested_objects_conditions_and_the_wrong_apple_are_not_events():
    picture = "John ate a picture of the apple in his house."
    attached = "John ate the apple with Mary in his house."
    conditional = "John ate a yellow apple if Mary cooked dinner."
    assert frame_from_chunk("picture", picture) is None
    assert frame_from_chunk("attached", attached) is None
    assert frame_from_chunk("conditional", conditional) is None
    for source, question in (
        (picture, "Who ate the apple?"),
        (attached, "Who ate the apple?"),
        (conditional, "Who ate the dinner?"),
    ):
        result = resolve_frames(question, [])
        reply = compose_reply(
            {"message": question, "guard_decision": "allow", "frame": True, "answer": source, "frame_result": result}
        )
        assert result["status"] == "missing"
        assert "John ate the apple." not in reply["text"]
        assert "John ate the dinner." not in reply["text"]
        assert reply["text"] == result["text"]
    seller = frame_from_chunk("review-offsets", SELLER)
    assert seller is not None
    assert seller["patient"] == {"role": "patient", "text": "apple", "start": 30, "end": 35}
    assert seller["sentence"][4:9] == "apple"
    assert seller["patient"]["start"] != 4
    assert seller["object"]["text"] == "a yellow apple"
    assert seller["color"]["start"] == 23


def test_a_prefixed_year_and_present_evidence_do_not_answer_a_past_question():
    undated = frame_from_chunk("apple-1", APPLE)
    prefixed = resolve_frames("In 2020, what color was the apple John ate?", [undated])
    assert prefixed["status"] == "missing"
    assert prefixed["value"] == ""
    assert prefixed["text"] == "No stored sentence states that color in 2020."
    assert compose_reply(
        {
            "message": "In 2020, what color was the apple John ate?",
            "guard_decision": "allow",
            "frame": True,
            "answer": APPLE,
            "frame_result": prefixed,
        }
    )["text"] == prefixed["text"]
    present = frame_from_chunk("present", "The apple is yellow.")
    past_question = resolve_frames("What color was the apple?", [present])
    assert past_question["status"] == "missing"
    assert past_question["text"] == "No stored sentence states that color in the past."
    assert "yellow" not in past_question["text"]
    plural = frame_from_chunk("plural", "The apples were yellow.")
    assert resolve_frames("What color was the apples?", [plural])["text"] == "The apples were yellow."
    odd = resolve_frames("On Tuesday, what color was the apple John ate?", [undated])
    assert odd["status"] == "unsupported"
    assert "yellow" not in compose_reply(
        {
            "message": "On Tuesday, what color was the apple John ate?",
            "guard_decision": "allow",
            "frame": True,
            "answer": APPLE,
            "frame_result": odd,
        }
    )["text"]


def test_a_missing_color_is_the_reply_and_not_the_source_sentence():
    plain = "John ate an apple in his house."
    frame = frame_from_chunk("plain", plain)
    assert frame is not None
    assert frame["color"] is None
    result = resolve_frames("What color was the apple John ate?", [frame])
    assert result["status"] == "missing"
    assert result["abstained"] is True
    reply = compose_reply(
        {
            "message": "What color was the apple John ate?",
            "guard_decision": "allow",
            "frame": True,
            "answer": plain,
            "frame_result": result,
        }
    )
    assert reply["text"] == "No stored sentence states that color in the past."
    assert reply["body"] == plain
    beside = compose_reply(
        {
            "message": "What color was the apple John ate?",
            "guard_decision": "allow",
            "frame": True,
            "summarize": True,
            "answer": plain,
            "brief": {"summary": plain},
            "frame_result": result,
        }
    )
    assert beside["text"].startswith(plain)
    assert "Event:\nNo stored sentence states that color in the past." in beside["text"]
