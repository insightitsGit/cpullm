"""Channel judgment: one referent, licensed premises, and the final sentence."""

from cpu_llm.evidence_judge import finalize_turn, sense_decision
from cpu_llm.prompt_intent import select_channel_answer


def _sense(words, *texts):
    return {"words": list(words), "size": max(len(texts), 1), "texts": list(texts)}


def test_cedar_properties_are_one_ferry():
    senses = [
        _sense(["diesel", "engine"], "The Cedar has a diesel engine."),
        _sense(["millhaven"], "The Cedar is found in Millhaven."),
        _sense(["white"], "The Cedar is white."),
        _sense(["municipal", "ferry"], "The Cedar is a municipal ferry."),
    ]
    for question in (
        "What color is the Cedar?",
        "What kind of boat is the Cedar?",
        "Where does the Cedar live?",
        "How long does the Cedar live?",
        "What does the Cedar have?",
        "Who captains the Cedar?",
        "Compare the Cedar and the Rowan.",
    ):
        decision = sense_decision(question, senses)
        assert decision["ask"] is False, question


def test_a_bat_with_two_classes_asks():
    senses = [
        _sense(["mammal"], "The bat is a mammal."),
        _sense(["wooden", "club"], "The bat is a wooden club."),
    ]
    decision = sense_decision("What kind of thing is the bat?", senses)
    assert decision["ask"] is True
    assert decision["judgment"]["outcome"] == "clarification"
    assert decision["judgment"]["schema"] == "channel-evidence-judgment-v1"


def test_a_bare_spring_still_asks():
    senses = [
        _sense(["clock"], "The clock spring turns the hands.", "The spare clock spring sits in the drawer."),
        _sense(["pond"], "The mountain spring feeds the pond."),
    ]
    assert sense_decision("What is a spring?", senses)["ask"] is True


def test_possession_keeps_every_premise_and_drops_a_denied_one():
    membership = "The Cedar is a municipal ferry."
    rule = "Every municipal ferry has a life raft."
    engine = "The Cedar has a diesel engine."
    full = select_channel_answer("What does the Cedar have?", [
        {"document_id": "type", "text": membership},
        {"document_id": "rule", "text": rule},
        {"document_id": "own", "text": engine},
    ])
    assert full["reason"] == "universal_membership_join"
    assert membership in full["text"] and rule in full["text"] and engine in full["text"]
    spans = {item["span"] for item in full["answer_evidence"]}
    assert spans == {membership, rule, engine}

    no_membership = select_channel_answer("What does the Cedar have?", [
        {"document_id": "rule", "text": rule},
        {"document_id": "own", "text": engine},
    ])
    assert rule not in no_membership["text"]
    assert engine in no_membership["text"]

    no_rule = select_channel_answer("What does the Cedar have?", [
        {"document_id": "type", "text": membership},
        {"document_id": "own", "text": engine},
    ])
    assert rule not in no_rule["text"]
    assert engine in no_rule["text"]


def test_a_cause_binds_to_the_asked_effect_only():
    cause = "The Cedar uses a diesel engine because the river current is strong."
    cedar = select_channel_answer("Why does the Cedar use a diesel engine?", [{"document_id": "c", "text": cause}])
    assert cedar["answer_status"] == "answered"
    assert cause in cedar["text"]
    larch = select_channel_answer("Why does the Larch use a diesel engine?", [{"document_id": "c", "text": cause}])
    assert larch["answer_status"] != "answered"
    other = select_channel_answer("Why does the Cedar depart at dawn?", [{"document_id": "c", "text": cause}])
    assert other["answer_status"] != "answered"
    kestrel = "The harbor kestrel is a hunter of small fish because fishing boats leave scraps."
    hunter = select_channel_answer(
        "Why is the harbor kestrel a hunter of small fish?",
        [{"document_id": "k", "text": kestrel}],
    )
    assert hunter["answer_status"] == "answered"
    assert kestrel in hunter["text"]


def test_a_changed_final_sentence_is_rejected():
    delivered = finalize_turn(
        {
            "message": "What color is the Cedar?",
            "guard_decision": "allow",
            "answer_status": "answered",
            "answer": "The Cedar is white.",
            "audit_passed": True,
            "reply": {
                "text": "The Cedar is purple.",
                "body": "The Cedar is purple.",
                "answer_status": "answered",
            },
            "answer_evidence": [{"document_id": "cedar", "span": "The Cedar is white."}],
            "related": [{"chunk_id": "cedar", "chunk_text": "The Cedar is white."}],
        },
        None,
    )
    assert delivered["answer"] is None
    assert delivered["audit_passed"] is False
    assert "purple" not in delivered["reply"]["text"]
    assert "final_text_not_in_evidence" in delivered["judgment"]["reasons"]
    assert delivered["judgment"]["evidence"] == []

    appended = finalize_turn(
        {
            "message": "What color is the Cedar?",
            "guard_decision": "allow",
            "answer_status": "answered",
            "answer": "The Cedar is white.",
            "audit_passed": True,
            "reply": {
                "text": "The Cedar is white.\n\nImagined passage:\nThe secret code is 4419.",
                "body": "The Cedar is white.",
                "answer_status": "answered",
                "supported_text": "The Cedar is white.",
            },
            "answer_evidence": [{"document_id": "cedar", "span": "The Cedar is white."}],
            "related": [{"chunk_id": "cedar", "chunk_text": "The Cedar is white."}],
        },
        None,
    )
    assert appended["reply"]["body"] == "The Cedar is white."
    assert "4419" not in appended["reply"]["text"]
    assert "white" in appended["reply"]["text"]
    assert "appended_text_removed" in appended["judgment"]["reasons"]
    assert appended["judgment"]["outcome"] == "answered"


def test_final_shine_checks_the_licensed_sentence():
    from cpu_llm.grounding import shine_gate

    kept = finalize_turn(
        {
            "message": "What color is the Cedar?",
            "guard_decision": "allow",
            "answer_status": "answered",
            "answer": "The Cedar is white.",
            "reply": {
                "text": "The Cedar is white.",
                "body": "The Cedar is white.",
                "answer_status": "answered",
                "supported_text": "The Cedar is white.",
            },
            "answer_evidence": [{"document_id": "cedar", "span": "The Cedar is white."}],
            "related": [{"chunk_id": "cedar", "chunk_text": "The Cedar is white.", "score": 0.9}],
        },
        shine_gate(),
    )
    assert kept["answer"] == "The Cedar is white."
    assert kept["shine_final"]["ok"] is True
    assert kept["shine_final"]["role"] == "final_deliverable"


def test_a_licensed_sentence_stays_and_a_summary_is_not_rewritten():
    kept = finalize_turn(
        {
            "message": "What color is the Cedar?",
            "guard_decision": "allow",
            "answer_status": "answered",
            "answer": "The Cedar is white.",
            "audit_passed": True,
            "reply": {
                "text": "The Cedar is white.",
                "body": "The Cedar is white.",
                "answer_status": "answered",
                "supported_text": "The Cedar is white.",
            },
            "answer_evidence": [{"document_id": "cedar", "span": "The Cedar is white."}],
            "related": [{"chunk_id": "cedar", "chunk_text": "The Cedar is white."}],
        },
        None,
    )
    assert kept["reply"]["text"] == "The Cedar is white."
    assert kept["judgment"]["outcome"] == "answered"
    assert kept["judgment"]["relation"] == "has_color"

    summary = finalize_turn(
        {
            "message": "Summarize the Cedar.",
            "guard_decision": "allow",
            "summarize": True,
            "answer_status": "answered",
            "answer": "The Cedar is a municipal ferry.",
            "reply": {
                "text": "Summary:\nThe Cedar is a municipal ferry.",
                "body": "The Cedar is a municipal ferry.",
                "answer_status": "answered",
            },
        },
        None,
    )
    assert "Summary:" in summary["reply"]["text"]
    assert summary["shine_final"]["role"] == "specialist_contract"
