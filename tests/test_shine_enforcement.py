from cpu_llm.grounding import shine_gate, unmatched_measurements, verify_grounding

RELATED = [{
    "chunk_id": "c1",
    "score": 0.86,
    "category": "homarus-gammarus",
    "chunk_text": (
        "Homarus gammarus is a species of clawed lobster. It weighs up to 6 kilograms "
        "and is up to 60 centimetres long."
    ),
}]


def _check(answer):
    return verify_grounding(
        shine_gate(),
        question="What is the European lobster?",
        answer=answer,
        related=RELATED,
        query_category=None,
        abstention=False,
    )


def test_a_grounded_sentence_is_delivered():
    result = _check("Homarus gammarus is a species of clawed lobster.")
    assert result["shine_enforced"] is False
    assert result["answer"] == "Homarus gammarus is a species of clawed lobster."


def test_ungrounded_sentences_are_withheld():
    for answer in (
        "Homarus gammarus weighs up to 60 kilograms.",
        "Homarus gammarus is the national animal of France and lives for 300 years.",
        "The Eiffel Tower is 330 metres tall.",
    ):
        result = _check(answer)
        assert result["shine_enforced"] is True, answer
        assert result["answer"] != answer


def test_a_number_must_keep_its_unit():
    passages = [RELATED[0]["chunk_text"]]
    assert unmatched_measurements("It is up to 60 centimetres long.", passages) == []
    assert unmatched_measurements("It weighs up to 60 kilograms.", passages) == ["60 kg"]
