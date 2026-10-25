"""Answers must select the asked fact rather than repeat the retrieved article."""

import pytest

from cpu_llm.agents.reply import compose_reply
from cpu_llm.answerability import assess
from cpu_llm.model01.generator import generate


@pytest.mark.parametrize("question", ["Who is Ada North?", "What is Ada North?"])
def test_named_identity_keeps_only_the_definition(question):
    definition = "Ada North is an English theatre actor."
    paragraph = definition + " Ada North appeared in a television series in 2004."
    chunks = [("actor", paragraph), ("noise", "The river flows through a valley.")]
    result = generate(question, chunks)
    assert result["text"] == definition
    assert result["verified"] is True
    reply = compose_reply({"message": question, "guard_decision": "allow",
                           "related": [{"chunk_id": i, "chunk_text": p} for i, p in chunks]})
    assert reply["text"] == "From actor:\n" + definition


def test_missing_attribute_does_not_become_a_biography():
    result = generate("What is Ada North's favorite food?", [("actor", "Ada North is an actor.")])
    assert result["status"] == "missing"
    assert result["verified"] is False
    assert result["text"] == "The retrieved passages do not settle that."


def test_species_range_can_be_stated_in_a_definition_with_an_alias():
    sentence = "Caligo marina, known as the coastal moth, is a species of moth from northern Norway."
    result = generate("Where does the coastal moth live?", [("moth", sentence)])
    assert result["text"] == sentence
    assert result["verified"] is True
    unrelated = assess("Where does the mountain moth live?", [{"text": sentence}])
    assert unrelated["answer_status"] == "insufficient_evidence"


def test_later_sentence_is_selected_and_conflicting_values_stay_unverified():
    result = generate("What is Ada North's birthplace?", [
        ("actor", "Ada North is an actor. Ada North's birthplace is Leeds.")])
    assert result["text"] == "Ada North's birthplace is Leeds."
    assert result["verified"] is True
    conflict = generate("What is Ada North's birthplace?", [
        ("one", "Ada North's birthplace is Leeds."),
        ("two", "Ada North's birthplace is York.")])
    assert conflict["status"] == "conflicting"
    assert conflict["verified"] is False


def test_rejected_delivery_is_not_replaced_with_a_quote():
    result = generate("Who is Ada North?", [("actor", "Ada North is an actor.")], delivery_rejected=True)
    assert result["status"] == "blocked"
    assert result["text"] == ""
