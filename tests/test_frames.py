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
