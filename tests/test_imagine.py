"""Creative writing is a classifier trigger and a dense-core walk."""

import numpy as np
from vectorprism.tensor_contract import PSMTensorContract

from cpu_llm.agents.imagine import compose_imagination
from cpu_llm.classifier import CALLER_REASON, creative_writing_trigger


def _tensor(*values: float) -> np.ndarray:
    dense = PSMTensorContract.DENSE_CORE
    tensor = np.zeros(1024, dtype=np.float64)
    vector = np.zeros(dense.end - dense.start, dtype=np.float64)
    vector[: len(values)] = values
    tensor[dense.start : dense.end] = vector
    return tensor


def test_a_plain_question_does_not_trigger_creative_writing():
    assert creative_writing_trigger("What is the European lobster?") == []
    assert creative_writing_trigger("Why use hyperbolic embeddings?") == []
    assert creative_writing_trigger("How long does the fictional lobster live?") == []


def test_imagine_story_and_what_if_are_classified():
    assert creative_writing_trigger("Imagine the European lobster.") == [
        "the prompt asks for an imagined scene"
    ]
    assert creative_writing_trigger("What if the lobster crossed the Atlantic?") == [
        "the prompt asks for an imagined scene"
    ]
    assert "the prompt asks for a story" in creative_writing_trigger("Tell a story about the lobster.")
    assert "the prompt asks for fiction" in creative_writing_trigger("Write a poem about the claws.")
    forced = creative_writing_trigger("What is the European lobster?", forced=True)
    assert forced == [CALLER_REASON]


def test_the_walk_keeps_positive_resonance_and_copies_sentences():
    near = "The European lobster lives in the Atlantic Ocean."
    far = "A blue whale sings in the deep ocean."
    lead = "The European lobster is Homarus gammarus."
    chunks = [
        {"document_id": "wikitext2-homarus-gammarus-p0002", "chunk_text": near, "tensor": _tensor(1.0, 0.0)},
        {"document_id": "wikitext2-homarus-gammarus-p0009", "chunk_text": far, "tensor": _tensor(-1.0, 0.0)},
        {"document_id": "wikitext2-homarus-gammarus-p0001", "chunk_text": lead, "tensor": _tensor(0.9, 0.1)},
    ]
    imagined = compose_imagination(
        "Imagine the European lobster.",
        chunks,
        {
            "wikitext2-homarus-gammarus-p0001": 0.8,
            "wikitext2-homarus-gammarus-p0002": 0.4,
            "wikitext2-homarus-gammarus-p0009": -0.3,
        },
    )
    assert imagined["loaded"] == 3
    assert imagined["articles"] == ["homarus-gammarus"]
    assert [item["chunk_id"] for item in imagined["links"]] == [
        "wikitext2-homarus-gammarus-p0001",
        "wikitext2-homarus-gammarus-p0002",
    ]
    assert imagined["links"][0]["cosine_to_previous"] is None
    assert imagined["links"][1]["cosine_to_previous"] > 0.9
    assert imagined["links"][0]["sentence"] == lead
    assert imagined["links"][1]["sentence"] == near
    assert "lobster" in imagined["keywords"]
    assert far not in imagined["text"]
    assert imagined["text"] == f"{lead} {near}"


def test_an_empty_shortlist_connects_nothing():
    imagined = compose_imagination("Imagine a lobster.", [], {})
    assert imagined["triggered"] is True
    assert imagined["links"] == []
    assert imagined["text"] == ""
    assert "nothing to connect" in imagined["note"]
