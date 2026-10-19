"""A paraphrase is a document order only when the encoder says so, and the decision is cached."""

import numpy as np
from chorusgraph.persistence.sqlite_graph_store import SqliteGraphStore

from cpu_llm.agents.reply import compose_reply
from cpu_llm.format_sense import SENSE_MARGIN, FormatSense
from cpu_llm.formats import parse_order
from cpu_llm.retrieval import VectorPrismIndex, default_checkpoint


def _encode(texts: list[str]) -> np.ndarray:
    rows = []
    for text in texts:
        if text.startswith("Put together an email"):
            rows.append([1.0, 0.0, 0.0])
        elif text == "Write an email about the late shipment.":
            rows.append([0.95, 0.1, 0.0])
        elif text == "What is the late shipment?":
            rows.append([0.2, 0.9, 0.0])
        elif text.startswith("What is an email"):
            rows.append([0.0, 0.0, 1.0])
        elif text == "Write an email.":
            rows.append([0.15, 0.0, 0.2])
        else:
            rows.append([0.0, 1.0, 0.0])
    return np.asarray(rows, dtype=np.float64)


def test_a_paraphrase_is_cached_in_the_chorusgraph_database(tmp_path):
    calls: list[int] = []

    def encode(texts: list[str]) -> np.ndarray:
        calls.append(len(texts))
        return _encode(texts)

    path = tmp_path / "graph.db"
    store = SqliteGraphStore(path, tenant_id="cpu-llm")
    try:
        sense = FormatSense(store, encode)
        assert parse_order("Put together an email about the late shipment.") is None
        first = sense.classify("Put together an email about the late shipment.")
        assert first is not None
        assert first.format_id == "email"
        assert first.topic == "the late shipment"
        assert calls == [3]
        second = sense.classify("Put together an email about the late shipment.")
        assert second is not None and second.format_id == "email" and second.topic == "the late shipment"
        assert calls == [3]
        assert sense.classify("What is an email?") is None
        assert len(calls) == 2
        assert sense.classify("What is an email?") is None
        assert len(calls) == 2
        row = store._conn.execute("SELECT format_id, topic FROM format_sense_cache").fetchall()
        assert ("email", "the late shipment") in row
        assert ("", "") in [(item[0], item[1]) for item in row]
    finally:
        store.close()

    reopened = SqliteGraphStore(path, tenant_id="cpu-llm")
    try:
        cached = FormatSense(reopened, encode)
        again = cached.classify("Put together an email about the late shipment.")
        assert again is not None and again.format_id == "email" and again.topic == "the late shipment"
        assert calls == [3, 3]
    finally:
        reopened.close()


def test_the_reply_uses_a_semantic_order():
    reply = compose_reply(
        {
            "message": "Put together an email about the late shipment.",
            "guard_decision": "allow",
            "draft_order": {"format": "email", "topic": "the late shipment"},
            "related": [
                {
                    "chunk_id": "c0",
                    "chunk_text": "The letter is addressed to Dana Chen. The late shipment left the dock on Monday.",
                }
            ],
        }
    )
    assert reply["text"].startswith("Email\nTo: Dana Chen")
    assert "The late shipment left the dock on Monday." in reply["text"]
    assert reply["draft"]["format"] == "email"


def test_the_real_encoder_accepts_a_paraphrase_and_rejects_a_question(tmp_path):
    index = VectorPrismIndex(default_checkpoint(), store=tmp_path / "vectors", backend="memory")
    store = SqliteGraphStore(tmp_path / "graph.db", tenant_id="cpu-llm")

    def encode(texts: list[str]):
        return index.pipeline.encoder.encode(list(texts))

    try:
        sense = FormatSense(store, encode)
        email = sense.classify("Put together an email about the late shipment.")
        essay = sense.classify("Whip up a short essay regarding the docking delay.")
        assert email is not None and email.format_id == "email" and email.topic == "the late shipment"
        assert essay is not None and essay.format_id == "essay" and essay.topic == "the docking delay"
        assert sense.classify("What is an email?") is None
        assert sense.classify("What is the European lobster?") is None
        assert sense.classify("Can I fly business class to Tokyo?") is None
        assert sense.classify("I need a writeup on the late shipment.") is None
        assert sense.classify("The late shipment left the dock on Monday.") is None
        assert SENSE_MARGIN == 0.15
    finally:
        store.close()
