"""Each channel reads the shortlist with its own method, and the detail node does not invent a sentence."""

import numpy as np
from vectorprism.tensor_contract import PSMTensorContract

from cpu_llm.channels import complexity_reasons, judge_readings, read_channel
from cpu_llm.ir.schema import (
    EIRProposition,
    EpistemicStatus,
    Modality,
    Polarity,
    Quantifier,
    QuantifierType,
    TypedEntity,
    TypedPredicate,
)


def _tensor(region, values) -> np.ndarray:
    vector = np.zeros(PSMTensorContract.TOTAL_DIM, dtype=np.float64)
    vector[region.start : region.end] = values
    return vector


def _passage(document_id: str, text: str, tensor: np.ndarray) -> dict:
    return {"document_id": document_id, "chunk_text": text, "tensor": tensor}


def _proposition(subject: str, target: str) -> EIRProposition:
    return EIRProposition(
        proposition_id="prop-test",
        polarity=Polarity.AFFIRMATIVE,
        modality=Modality.DECLARATIVE,
        quantifier=Quantifier(qtype=QuantifierType.UNSPECIFIED),
        subject=TypedEntity(raw_text=subject, lemma=subject, is_plural=False),
        predicate=TypedPredicate(lemma="be", tense="PRESENT", voice="ACTIVE"),
        object_target=TypedEntity(raw_text=target, lemma=target, is_plural=False),
        epistemic_status=EpistemicStatus.RETRIEVED_FACT,
        epistemic_weight=1.0,
    )


def test_dense_cosine_quotes_the_matching_passage():
    region = PSMTensorContract.DENSE_CORE
    direction = np.zeros(region.length)
    direction[0] = 1.0
    other = np.zeros(region.length)
    other[1] = 1.0
    lead = "The European lobster is Homarus gammarus."
    passages = [
        _passage("lead", lead, _tensor(region, direction)),
        _passage("other", "A distant sentence about roads.", _tensor(region, other)),
    ]
    reading = read_channel("dense", "What is the European lobster?", passages, query_tensor=_tensor(region, direction), enabled=True)
    assert reading["document_id"] == "lead"
    assert reading["used_for_answer"] is True
    assert lead in reading["detail"]


def test_disabled_relational_head_uses_the_stored_proposition():
    text = "The European lobster is Homarus gammarus."
    proposition = _proposition("The European lobster", "Homarus gammarus")
    passages = [_passage("lead", text, np.zeros(1024))]
    reading = read_channel(
        "relational",
        "What is the European lobster?",
        passages,
        propositions={"lead": proposition},
        enabled=False,
    )
    assert reading["used_for_answer"] is False
    assert "off in this checkpoint" in reading["note"]
    assert "The European lobster" in reading["detail"]
    assert "Homarus gammarus" in reading["detail"]


def test_a_passage_without_a_stated_cause_is_not_given_one():
    passages = [_passage("lead", "The European lobster is Homarus gammarus.", np.zeros(1024))]
    reading = read_channel("causal", "What is the European lobster?", passages, enabled=False)
    assert reading["detail"] == "No retrieved passage states a cause."
    assert "bilinear" in reading["note"]


def test_causal_channel_quotes_the_because_sentence():
    sentence = "The pots work because the lobster enters them."
    passages = [_passage("cause", sentence, np.zeros(1024))]
    reading = read_channel("causal", "What is the European lobster?", passages, enabled=False)
    assert sentence in reading["detail"]


def test_hyperbolic_distance_is_refused_outside_the_unit_ball():
    region = PSMTensorContract.HYPERBOLIC
    outside = np.ones(region.length)
    passages = [_passage("lead", "The European lobster is Homarus gammarus.", _tensor(region, outside))]
    reading = read_channel(
        "hyperbolic",
        "What is the European lobster?",
        passages,
        query_tensor=_tensor(region, outside),
        enabled=False,
    )
    assert reading["document_id"] is None
    assert reading["detail"] == (
        "The hyperbolic slices are outside the open unit ball, so no taxonomic distance was computed."
    )


def test_hyperbolic_distance_ranks_a_point_inside_the_ball():
    region = PSMTensorContract.HYPERBOLIC
    query = np.zeros(region.length)
    query[0] = 0.2
    near = np.zeros(region.length)
    near[0] = 0.25
    far = np.zeros(region.length)
    far[0] = 0.7
    passages = [
        _passage("far", "A far point.", _tensor(region, far)),
        _passage("near", "A near point.", _tensor(region, near)),
    ]
    reading = read_channel("hyperbolic", "Where is the point?", passages, query_tensor=_tensor(region, query), enabled=False)
    assert reading["document_id"] == "near"
    assert "No class name was read" in reading["detail"]


def test_exclusive_words_come_from_one_passage():
    passages = [
        _passage("lead", "The European lobster is Homarus gammarus.", np.zeros(1024)),
        _passage("cause", "The pots work because the lobster enters them.", np.zeros(1024)),
    ]
    reading = read_channel("disentangled", "What is the European lobster?", passages, enabled=False)
    assert reading["document_id"] in {"lead", "cause"}
    words = reading["detail"].split(": ", 1)[1].rstrip(".").split(", ")
    chosen = next(item["chunk_text"] for item in passages if item["document_id"] == reading["document_id"])
    other = next(item["chunk_text"] for item in passages if item["document_id"] != reading["document_id"])
    for word in words:
        assert word in chosen.casefold()
        assert word not in other.casefold()


def test_a_why_comparison_suggests_discovery_without_a_new_fact():
    assert complexity_reasons("What is the European lobster?", ["homarus-gammarus", "homarus-americanus"]) == []
    reasons = complexity_reasons(
        "Why is the European lobster different from the American lobster?",
        ["homarus-gammarus", "homarus-americanus"],
    )
    assert "the prompt asks why or how" in reasons
    assert "the prompt asks for a comparison" in reasons
    assert "the passages come from more than one article" in reasons
    readings = [
        read_channel("dense", "Why is the European lobster different?", [], enabled=True),
        read_channel("causal", "Why is the European lobster different?", [], enabled=False),
    ]
    report = judge_readings("Why is the European lobster different?", readings, ["homarus-gammarus"])
    assert report["discovery_suggested"] is True
    assert "discovery loop" in report["text"]
    assert "It stays off until you ask for it." in report["text"]
