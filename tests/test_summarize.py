"""A summary keeps the claims PrismCognition weighted highest."""

import numpy as np

from cpu_llm.agents.reply import compose_reply
from cpu_llm.agents.summarize import cause_first, rank_by_cognition, topic_words
from cpu_llm.classifier import explain_trigger, list_trigger, source_trigger, summary_trigger
from cpu_llm.cognition.adapter import PrismCognitionSubspaceAdapter
from cpu_llm.clauses import proposition_from_chunk
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
from cpu_llm.pipeline import _after_compare, _after_deep, _after_shine


def _fact(proposition_id: str, polarity: Polarity, modality: Modality, obj: str) -> EIRProposition:
    return EIRProposition(
        proposition_id=proposition_id,
        polarity=polarity,
        modality=modality,
        quantifier=Quantifier(qtype=QuantifierType.UNSPECIFIED),
        subject=TypedEntity(raw_text="lobster", lemma="lobster", is_plural=False),
        predicate=TypedPredicate(lemma="be", tense="PRESENT", voice="ACTIVE"),
        object_target=TypedEntity(raw_text=obj, lemma=obj, is_plural=False),
        epistemic_status=EpistemicStatus.RETRIEVED_FACT,
        epistemic_weight=1.0,
    )


def test_a_plain_question_does_not_ask_for_a_summary():
    assert summary_trigger("What is the European lobster?") == []
    assert explain_trigger("What is the European lobster?") == []
    assert list_trigger("What is the European lobster?") == []
    assert source_trigger("What is the European lobster?") == []
    assert topic_words("Summarize that.") == []
    assert topic_words("Summarize the European lobster.") == ["european", "lobster"]


def test_the_other_prompt_shapes_are_recognized_without_turning_discovery_on():
    assert summary_trigger("Summarize the European lobster.") == ["the prompt asks for a summary"]
    assert explain_trigger("Why use hyperbolic embeddings?") == ["the prompt asks for an explanation"]
    assert list_trigger("List the European lobster facts.") == ["the prompt asks for a list"]
    assert source_trigger("Cite the sources.") == ["the prompt asks for sources"]
    assert _after_shine({"summarize": True}) == "brief"
    assert _after_deep({"deep": True, "summarize": True}) == "brief"
    assert _after_compare({"summarize": True, "explain": True}) == "brief"
    assert _after_deep({"deep": True}) == "model01"


def test_cognition_puts_the_untensed_claim_ahead_of_a_modal_tension():
    steady = _fact("steady", Polarity.AFFIRMATIVE, Modality.DECLARATIVE, "marine")
    stated = _fact("stated", Polarity.AFFIRMATIVE, Modality.DECLARATIVE, "clawed")
    hedged = _fact("hedged", Polarity.NEGATIVE, Modality.PROBABILISTIC, "clawed")
    query = np.zeros(4, dtype=np.float64)
    query[0] = 1.0
    tensors = [np.eye(4)[index] for index in range(3)]
    result = PrismCognitionSubspaceAdapter().deliberate(query, [stated, hedged, steady], tensors, "cpu-llm")
    by_id = {item.proposition_id: item.epistemic_weight for item in result.grounded_propositions}
    assert by_id["steady"] == 1.0
    assert by_id["stated"] == 0.5
    assert by_id["hedged"] == 0.5
    ranked = rank_by_cognition(result, {"stated": tensors[0], "hedged": tensors[1], "steady": tensors[2]})
    assert ranked[0].proposition_id == "steady"


def test_a_closer_tensor_wins_a_weight_tie_and_a_contradiction_summarizes_nothing():
    near = proposition_from_chunk("near", "The European lobster is Homarus gammarus.")
    far = proposition_from_chunk("far", "Homarus gammarus is a species of clawed lobster.")
    assert near is not None and far is not None
    query = np.zeros(4, dtype=np.float64)
    query[0] = 1.0
    near_tensor = np.array([1.0, 0.0, 0.0, 0.0])
    far_tensor = np.array([0.0, 1.0, 0.0, 0.0])
    result = PrismCognitionSubspaceAdapter().deliberate(query, [far, near], [far_tensor, near_tensor], "cpu-llm")
    ranked = rank_by_cognition(
        result,
        {far.proposition_id: far_tensor, near.proposition_id: near_tensor},
    )
    assert ranked[0].proposition_id == near.proposition_id

    left = _fact("yes", Polarity.AFFIRMATIVE, Modality.DECLARATIVE, "clawed")
    right = _fact("no", Polarity.NEGATIVE, Modality.DECLARATIVE, "clawed")
    conflict = PrismCognitionSubspaceAdapter().deliberate(
        query,
        [left, right],
        [near_tensor, far_tensor],
        "cpu-llm",
    )
    assert conflict.ruin_distance == 1.0
    assert rank_by_cognition(conflict, {}) == []


def test_an_explanation_keeps_only_a_stored_cause():
    cause = _fact("cause", Polarity.AFFIRMATIVE, Modality.DECLARATIVE, "pressure")
    other = _fact("other", Polarity.AFFIRMATIVE, Modality.DECLARATIVE, "marine")
    kept = cause_first([other, cause], {"cause": "The hull failed because of pressure.", "other": "The lobster is marine."})
    assert [item.proposition_id for item in kept] == ["cause"]


def test_the_reply_speaks_the_summary_and_leaves_a_plain_answer_alone():
    summary = compose_reply(
        {
            "message": "Summarize the European lobster.",
            "answer": "The European lobster is Homarus gammarus.",
            "guard_decision": "allow",
            "summarize": True,
            "related": [{"chunk_id": "p1", "chunk_text": "The European lobster is Homarus gammarus."}],
            "brief": {"summary": "The European lobster is Homarus gammarus.", "sources": ["p1"]},
        }
    )
    assert summary["text"].index("Summary:") > summary["text"].index(summary["body"])
    plain = compose_reply(
        {
            "message": "What is the European lobster?",
            "answer": "The European lobster is Homarus gammarus.",
            "guard_decision": "allow",
            "related": [{"chunk_id": "p1", "chunk_text": "The European lobster is Homarus gammarus."}],
        }
    )
    assert plain["text"] == plain["body"]
    assert "Summary:" not in plain["text"]
