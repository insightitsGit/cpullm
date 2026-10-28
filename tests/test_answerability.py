"""A retrieved sentence answers a question only when it states the asked relation."""

from cpu_llm.agents.reply import compose_reply
from cpu_llm.answerability import assess, eligible_hits
from cpu_llm.realizer.ranker import apply_realization

_UNSETTLED = "The retrieved passages do not settle that."
_KESTREL = "The harbor kestrel is a small coastal falcon."
_EATS = "The harbor kestrel eats small fish."
_NESTS = "The harbor kestrel nests in coastal cliffs."
_APPLE = "John ate a yellow apple in his house."
_CLASS = "Business class is allowed for flights over six hours."
_PARIS_FLIGHT = "The flight from Boston to Paris takes eight hours."
_CHICAGO = "The flight from Boston to Chicago takes two hours."
_SEVEN = [_KESTREL, _NESTS, _EATS, _APPLE, _CLASS, _PARIS_FLIGHT, _CHICAGO]
_CAPITAL = "The capital of France is Paris."
_CAPITAL_ALT = "Paris is the capital of France."
_LYON = "Lyon is the capital of France."
_AREA = (
    "France Area is headed by a director and is responsible for France "
    "(including the island of Corsica)."
)
_FINANCIAL = "The financial capital of the firm is nine million."
_MANILA = "Manila is the capital of the Philippines."
_LOBSTER = (
    "Homarus gammarus, known as the European lobster or common lobster, "
    "is a species of clawed lobster from the eastern Atlantic Ocean."
)


def _chunks(*rows: tuple[str, str]) -> list[dict[str, str]]:
    return [{"document_id": document_id, "text": text} for document_id, text in rows]


def _state(message: str, rows: list[tuple[str, str]], **extra) -> dict:
    related = [
        {"chunk_id": document_id, "chunk_text": text, "score": 0.4}
        for document_id, text in rows
    ]
    state = {
        "message": message,
        "guard_decision": "allow",
        "related": related,
    }
    state.update(extra)
    return state


def test_france_capital_on_the_seven_paragraphs_abstains():
    rows = [(f"feature-notes-p000{index}", text) for index, text in enumerate(_SEVEN, start=1)]
    reply = compose_reply(
        _state(
            "What is the capital of France?",
            rows,
            answer=f"{_KESTREL} it eats small fish. {_CLASS}",
            audit_passed=True,
            shine_ok=True,
            cognition_status="deliberated",
        )
    )
    assert reply["answer_status"] == "insufficient_evidence"
    assert reply["text"] == _UNSETTLED
    assert reply["answer_evidence"] == []
    assert reply["verification_scope"] == "query"
    assert "kestrel" not in reply["text"].casefold()
    assert "business class" not in reply["text"].casefold()
    assert "Paris" not in reply["text"]
    assert reply["producer"] == "answerability"
    assert [item["span"] for item in reply["retrieved_candidates"]] == list(_SEVEN)


def test_an_explicit_capital_sentence_is_the_answer_and_the_citation():
    reply = compose_reply(
        _state(
            "What is the capital of France?",
            [("bird", _KESTREL), ("capital-1", _CAPITAL)],
            answer=_CAPITAL,
            audit_passed=True,
        )
    )
    assert reply["answer_status"] == "answered"
    assert reply["text"] == _CAPITAL
    assert reply["answer_evidence"] == [{"document_id": "capital-1", "span": _CAPITAL}]
    assert "kestrel" not in reply["text"].casefold()


def test_shared_words_do_not_state_the_capital_relation():
    decision = assess(
        "What is the capital of France?",
        _chunks(("area", _AREA), ("money", _FINANCIAL), ("manila", _MANILA)),
    )
    assert decision is not None
    assert decision["answer_status"] == "insufficient_evidence"
    assert decision["text"] == _UNSETTLED
    assert "Paris" not in decision["text"]
    assert "Manila" not in decision["text"]
    assert "nine million" not in decision["text"]


def test_paraphrase_and_alias_still_bind():
    city = assess("Which city is the capital of France?", [_CAPITAL_ALT])
    assert city is not None and city["answer_status"] == "answered"
    assert city["text"] == _CAPITAL_ALT
    possessive = assess("What is France's capital?", [_CAPITAL])
    assert possessive is not None and possessive["text"] == _CAPITAL
    lobster = assess("What is the common lobster?", [_LOBSTER])
    assert lobster is not None and lobster["answer_status"] == "answered"
    assert "Homarus gammarus" in lobster["text"]


def test_wrong_entity_attribute_tense_negation_and_condition_do_not_answer():
    question = "What is the capital of France?"
    for sentence in (
        "Paris is the capital of Germany.",
        "The population of France is 67 million.",
        "The capital of France was Paris.",
        "Paris is not the capital of France.",
        "Paris is the capital of France if the treaty holds.",
    ):
        decision = assess(question, [sentence])
        assert decision is not None
        assert decision["answer_status"] == "insufficient_evidence"
        assert decision["text"] == _UNSETTLED


def test_conflicting_capitals_do_not_pick_a_winner_in_either_order():
    first = assess("What is the capital of France?", [_CAPITAL_ALT, _LYON])
    second = assess("What is the capital of France?", [_LYON, _CAPITAL_ALT])
    assert first is not None and second is not None
    assert first["answer_status"] == second["answer_status"] == "conflicting"
    assert first["text"] == second["text"]
    assert "Paris is the capital of France." in first["text"]
    assert "Lyon is the capital of France." in first["text"]
    assert first["text"].startswith(_UNSETTLED)


def test_duplicate_statements_are_one_value():
    decision = assess("What is the capital of France?", [_CAPITAL, _CAPITAL_ALT])
    assert decision is not None
    assert decision["answer_status"] == "answered"
    assert "Lyon" not in decision["text"]
    assert len(decision["answer_evidence"]) == 2


def test_a_sentence_that_was_not_retrieved_is_not_used():
    held_back = _CAPITAL
    decision = assess("What is the capital of France?", [_KESTREL, _CLASS])
    assert decision is not None
    assert decision["answer_status"] == "insufficient_evidence"
    assert held_back not in decision["text"]
    assert "Paris" not in decision["text"]
    empty = assess("What is the capital of France?", [])
    assert empty is not None
    assert empty["text"] == "No passage was retrieved."


def test_unrelated_round_trip_does_not_replace_the_binding_sentence():
    reply = compose_reply(
        _state(
            "What is the capital of France?",
            [("class", _CLASS), ("capital-1", _CAPITAL)],
            answer=_CLASS,
            audit_passed=True,
        )
    )
    assert reply["answer_status"] == "evidence_quote"
    assert reply["verification_scope"] == "retrieval"
    assert _CAPITAL in reply["text"]
    assert _CLASS not in reply["text"]
    assert "capital-1" in reply["text"]


def test_a_typo_rewrite_and_a_prior_turn_stay_visible():
    reply = compose_reply(
        _state(
            "What is the capital of France?",
            [(f"p{index}", text) for index, text in enumerate(_SEVEN)],
            original_message="What is the capital of Frnace?",
            prior_message="Tell me about the harbor kestrel.",
            answer=_KESTREL,
            audit_passed=True,
        )
    )
    assert reply["answer_status"] == "insufficient_evidence"
    assert reply["query"] == "What is the capital of France?"
    assert reply["original_query"] == "What is the capital of Frnace?"
    assert "Paris" not in reply["text"]
    follow = assess("What about its capital?", [_CAPITAL])
    assert follow is None


def test_sources_for_the_kestrel_do_not_list_the_flights():
    rows = [
        ("feature-notes-p0001", _KESTREL),
        ("feature-notes-p0003", _EATS),
        ("feature-notes-p0002", _NESTS),
        ("feature-notes-p0007", _CHICAGO),
        ("feature-notes-p0006", _PARIS_FLIGHT),
    ]
    reply = compose_reply(
        _state(
            "Cite sources for the harbor kestrel.",
            rows,
            sources=True,
            answer=f"{_KESTREL} it eats small fish.",
            audit_passed=True,
            brief={"sources": [row[0] for row in rows]},
        )
    )
    assert "feature-notes-p0006" not in reply["text"]
    assert "feature-notes-p0007" not in reply["text"]
    assert "feature-notes-p0001" in reply["text"]
    assert "feature-notes-p0002" in reply["text"]
    assert "feature-notes-p0003" in reply["text"]
    assert _CLASS not in reply["text"]


def test_frame_math_and_ranking_producers_keep_their_answers():
    frame = compose_reply(
        {
            "message": "What color was the apple John ate?",
            "guard_decision": "allow",
            "frame": True,
            "frame_result": {"status": "answered", "verified": True, "text": "The apple John ate was yellow."},
            "related": [{"chunk_id": "apple", "chunk_text": _APPLE}],
        }
    )
    assert frame["text"] == "The apple John ate was yellow."
    assert "answer_status" not in frame
    from cpu_llm.agents.math import solve_math

    math = compose_reply(
        {
            "message": "What is 2 + 2?",
            "guard_decision": "allow",
            "math": True,
            "math_result": solve_math("What is 2 + 2?"),
            "answer": _KESTREL,
        }
    )
    assert math["text"] == "2+2 = 4."
    assert "answer_status" not in math
    ranked = compose_reply(
        _state(
            "what is the best lobster in eroupe?",
            [("species", _LOBSTER)],
            answer=_LOBSTER,
            audit_passed=True,
        )
    )
    assert "answer_status" not in ranked
    assert "Ranking:" in ranked["text"]
    assert _LOBSTER in ranked["text"]


def test_opt_in_realization_does_not_replace_an_abstention():
    rows = [(f"p{index}", text) for index, text in enumerate(_SEVEN)]
    state = _state(
        "What is the capital of France?",
        rows,
        answer=f"{_KESTREL} {_CLASS}",
        audit_passed=True,
        shine_ok=True,
    )
    reply = compose_reply(state)
    state["reply"] = reply
    state["answer_status"] = reply["answer_status"]
    extra = apply_realization(state, realization="evidence_neural", account=True)
    assert reply["text"] == _UNSETTLED
    assert "reply" not in extra or extra["reply"]["text"] == _UNSETTLED


def test_zero_overlap_is_not_permission_to_realize_every_hit():
    hits = [{"document_id": f"p{index}", "chunk_text": text} for index, text in enumerate(_SEVEN)]
    assert eligible_hits("What is the capital of France?", hits) == []
    assert eligible_hits("What is the harbor kestrel?", hits) == hits[:3]


def test_a_blocked_delivery_is_not_turned_into_an_answer():
    reply = compose_reply(
        _state(
            "What is the capital of France?",
            [("capital-1", _CAPITAL)],
            answer=_CAPITAL,
            audit_passed=True,
            shine_ok=False,
        )
    )
    assert "answer_status" not in reply
    assert reply["text"] == _CAPITAL


def test_binding_beats_returning_the_first_passage_on_the_frozen_set():
    fixtures = _frozen_fixtures()
    candidate = _score(fixtures, _candidate)
    baseline_a = _score(fixtures, _passage_baseline)
    baseline_b = _score(fixtures, _first_passage_as_answer)
    assert candidate["answerable"] == 6
    assert candidate["coverage"] == 6
    assert candidate["unsupported"] == 0
    assert candidate["unanswerable"] == 9
    assert candidate["conflicts"] == 2
    assert candidate["conflict_correct"] == 2
    assert baseline_a == {
        "answerable": 6,
        "unanswerable": 9,
        "coverage": 0,
        "unsupported": 0,
        "conflicts": 2,
        "conflict_correct": 0,
        "citation_hits": 0,
    }
    assert baseline_b["coverage"] == 5
    assert baseline_b["unsupported"] == 8
    assert baseline_b["conflict_correct"] == 0
    assert baseline_b["citation_hits"] == 5
    assert candidate["citation_hits"] == candidate["coverage"]


def test_a_diet_question_uses_the_eating_sentence_and_not_the_nest():
    reply = compose_reply(
        _state(
            "What does the harbor kestrel eat?",
            [("nest", _NESTS), ("eat", _EATS), ("kind", _KESTREL)],
            answer=f"{_EATS} it is a small coastal falcon.",
            audit_passed=True,
        )
    )
    assert "eats small fish" in reply["text"]
    assert "coastal cliffs" not in reply["text"]
    assert [item["document_id"] for item in reply["answer_evidence"]] == ["eat"]
    heron = assess(
        "What does the blue heron eat?",
        [_EATS, "The blue heron eats small fish."],
    )
    assert heron is not None and heron["answer_status"] == "answered"
    assert heron["text"] == "The blue heron eats small fish."


def test_a_nesting_question_quotes_that_birds_place():
    kestrel = assess(
        "Where does the harbor kestrel nest?",
        [_KESTREL, _EATS, _NESTS, "The blue heron nests in tall trees."],
    )
    heron = assess(
        "Where does the blue heron nest?",
        [_NESTS, "The blue heron nests in tall trees.", "The blue heron eats small fish."],
    )
    assert kestrel is not None and "coastal cliffs" in kestrel["text"]
    assert "tall trees" not in kestrel["text"]
    assert heron is not None and "tall trees" in heron["text"]
    assert "coastal cliffs" not in heron["text"]
    reply = compose_reply(
        _state(
            "Where does the harbor kestrel nest?",
            [("kind", _KESTREL), ("eat", _EATS), ("nest", _NESTS)],
            answer=f"{_KESTREL} it eats small fish.",
            audit_passed=True,
        )
    )
    assert "coastal cliffs" in reply["text"]
    assert "eats small fish" not in reply["text"]


def test_a_nested_clause_does_not_bind_the_outer_subject():
    fish_nests = "The harbor kestrel eats a fish that nests in coastal cliffs."
    heron_eats = "The harbor kestrel watches a heron eat small fish."
    fish_weighs = "The harbor kestrel watches a fish that weighs two kilograms."
    nest = assess("Where does the harbor kestrel nest?", [fish_nests])
    watched = assess("What does the harbor kestrel eat?", [heron_eats])
    weight = assess("How much does the harbor kestrel weigh?", [fish_weighs])
    assert nest is not None and nest["answer_status"] == "insufficient_evidence"
    assert watched is not None and watched["answer_status"] == "insufficient_evidence"
    assert weight is not None and weight["answer_status"] == "insufficient_evidence"
    direct = assess("Where does the harbor kestrel nest?", [_NESTS])
    diet = assess("What does the harbor kestrel eat?", [_EATS])
    own_meal = assess("What does the harbor kestrel eat?", [fish_nests])
    assert direct is not None and direct["answer_status"] == "answered" and "coastal cliffs" in direct["text"]
    assert diet is not None and diet["answer_status"] == "answered" and diet["text"] == _EATS
    assert own_meal is not None and own_meal["answer_status"] == "answered" and own_meal["text"] == fish_nests


def test_a_missing_weight_is_not_the_birds_definition_or_another_animals_weight():
    reply = compose_reply(
        _state(
            "How much does the harbor kestrel weigh?",
            [
                ("kind", _KESTREL),
                ("eat", _EATS),
                ("lobster", "The European lobster weighs nine kilograms."),
            ],
            answer=f"{_KESTREL} it eats small fish. The European lobster weighs nine kilograms.",
            audit_passed=True,
        )
    )
    assert reply["answer_status"] == "insufficient_evidence"
    assert reply["text"] == _UNSETTLED
    assert "lobster" not in reply["text"].casefold()
    assert "falcon" not in reply["text"].casefold()


def _frozen_fixtures() -> list[dict]:
    seven = _chunks(*[(f"p{index}", text) for index, text in enumerate(_SEVEN)])
    return [
        {"family": "answerable", "question": "What is the capital of France?", "chunks": _chunks(("bird", _KESTREL), ("capital-1", _CAPITAL)), "expect": "answered", "cite": "capital-1"},
        {"family": "answerable", "question": "Which city is the capital of France?", "chunks": _chunks(("capital-1", _CAPITAL_ALT)), "expect": "answered", "cite": "capital-1"},
        {"family": "answerable", "question": "What is France's capital?", "chunks": _chunks(("capital-1", _CAPITAL)), "expect": "answered", "cite": "capital-1"},
        {"family": "answerable", "question": "What is the harbor kestrel?", "chunks": _chunks(("k1", _KESTREL), ("k2", _EATS), ("class", _CLASS)), "expect": "answered", "cite": "k1"},
        {"family": "answerable", "question": "What is the common lobster?", "chunks": _chunks(("species", _LOBSTER)), "expect": "answered", "cite": "species"},
        {"family": "answerable", "question": "What is the capital of France?", "chunks": _chunks(("a", _CAPITAL), ("b", _CAPITAL_ALT)), "expect": "answered", "cite": "a"},
        {"family": "unanswerable", "question": "What is the capital of France?", "chunks": seven, "expect": "insufficient_evidence"},
        {"family": "unanswerable", "question": "What is the capital of France?", "chunks": _chunks(("area", _AREA), ("money", _FINANCIAL), ("manila", _MANILA)), "expect": "insufficient_evidence"},
        {"family": "unanswerable", "question": "What is the capital of France?", "chunks": _chunks(("de", "Paris is the capital of Germany.")), "expect": "insufficient_evidence"},
        {"family": "unanswerable", "question": "What is the capital of France?", "chunks": _chunks(("pop", "The population of France is 67 million.")), "expect": "insufficient_evidence"},
        {"family": "unanswerable", "question": "What is the capital of France?", "chunks": _chunks(("old", "The capital of France was Paris.")), "expect": "insufficient_evidence"},
        {"family": "unanswerable", "question": "What is the capital of France?", "chunks": _chunks(("neg", "Paris is not the capital of France.")), "expect": "insufficient_evidence"},
        {"family": "unanswerable", "question": "What is the capital of France?", "chunks": _chunks(("if", "Paris is the capital of France if the treaty holds.")), "expect": "insufficient_evidence"},
        {"family": "unanswerable", "question": "What is the capital of France?", "chunks": [], "expect": "insufficient_evidence"},
        {"family": "unanswerable", "question": "What is the capital of France?", "chunks": _chunks(("bird", _KESTREL)), "expect": "insufficient_evidence"},
        {"family": "conflict", "question": "What is the capital of France?", "chunks": _chunks(("a", _CAPITAL_ALT), ("b", _LYON)), "expect": "conflicting"},
        {"family": "conflict", "question": "What is the capital of France?", "chunks": _chunks(("b", _LYON), ("a", _CAPITAL_ALT)), "expect": "conflicting"},
    ]


def _candidate(fixture: dict) -> dict:
    decision = assess(fixture["question"], fixture["chunks"])
    assert decision is not None
    return decision


def _passage_baseline(fixture: dict) -> dict:
    chunks = fixture["chunks"]
    if not chunks:
        return {"answer_status": "insufficient_evidence", "text": "No passage was retrieved.", "answer_evidence": []}
    top = chunks[0]
    return {
        "answer_status": "retrieval_only",
        "text": f"Passage: {top['text']}",
        "answer_evidence": [],
    }


def _first_passage_as_answer(fixture: dict) -> dict:
    chunks = fixture["chunks"]
    if not chunks:
        return {"answer_status": "insufficient_evidence", "text": "No passage was retrieved.", "answer_evidence": []}
    top = chunks[0]
    return {
        "answer_status": "answered",
        "text": top["text"],
        "answer_evidence": [{"document_id": top["document_id"], "span": top["text"]}],
    }


def _score(fixtures: list[dict], predict) -> dict[str, int]:
    coverage = unsupported = conflicts = conflict_correct = citations = 0
    answerable = unanswerable = 0
    for fixture in fixtures:
        predicted = predict(fixture)
        status = predicted["answer_status"]
        if fixture["family"] == "answerable":
            answerable += 1
            if _covers(fixture, predicted):
                coverage += 1
                if _span_cited(predicted, fixture["cite"]):
                    citations += 1
        elif fixture["family"] == "unanswerable":
            unanswerable += 1
            if status == "answered":
                unsupported += 1
        elif fixture["family"] == "conflict":
            conflicts += 1
            if status == "conflicting" and predicted["text"].startswith(_UNSETTLED):
                conflict_correct += 1
    return {
        "answerable": answerable,
        "unanswerable": unanswerable,
        "coverage": coverage,
        "unsupported": unsupported,
        "conflicts": conflicts,
        "conflict_correct": conflict_correct,
        "citation_hits": citations,
    }


def test_two_unlinked_classes_ask_and_the_numbered_choice_is_stored():
    from cpu_llm.answerability import chosen_class
    from cpu_llm.clarification import ClarificationLoop
    from cpu_llm.pipeline import _class_clarification

    rows = [
        {"document_id": "survey", "text": "The Lumen is a survey mark."},
        {"document_id": "display", "text": "The Lumen is a display mark."},
    ]
    decision = assess("What is the Lumen?", rows)
    assert decision["answer_status"] == "needs_clarification"
    assert "1. survey, mark" in decision["text"]
    assert "2. display, mark" in decision["text"]
    assert "The Lumen is a display mark." not in decision["text"]
    reply = compose_reply({
        "message": "What is the Lumen?",
        "guard_decision": "allow",
        "answer": "The Lumen is a display mark.",
        "audit_passed": True,
        "related": [{"chunk_id": item["document_id"], "chunk_text": item["text"]} for item in rows],
    })
    assert reply["answer_status"] == "needs_clarification"
    assert "Which meaning do you mean?" in reply["text"]
    assert "The Lumen is a display mark." not in reply["text"]

    loop = ClarificationLoop()
    asked = _class_clarification(
        type("App", (), {"clarifications": loop})(),
        "What is the Lumen?",
        {"related": [{"chunk_id": item["document_id"], "chunk_text": item["text"]} for item in rows]},
        "chat",
    )
    assert asked["slot"] == "sense"
    assert loop.pending
    ready = loop.prepare("1", key="chat")
    assert ready["status"] == "ready"
    assert ready["sense"]["words"] == ["survey", "mark"]
    with chosen_class(" ".join(ready["sense"]["words"])):
        picked = assess(ready["question"], rows)
    assert picked["answer_status"] == "answered"
    assert picked["text"] == "The Lumen is a survey mark."
    assert "display mark" not in picked["text"]


def test_one_class_is_still_the_definition():
    rows = [{"document_id": "kind", "text": "The Vesper is a survey rover."}]
    decision = assess("What is the Vesper?", rows)
    assert decision["answer_status"] == "answered"
    assert decision["text"] == "The Vesper is a survey rover."


def test_a_missing_selected_class_is_not_replaced_by_the_other_meaning():
    from cpu_llm.answerability import chosen_class

    rows = [{"document_id": "display", "text": "The Lumen is a display mark."}]
    with chosen_class("survey mark"):
        decision = assess("What is the Lumen?", rows)
        reply = compose_reply({
            "message": "What is the Lumen?",
            "guard_decision": "allow",
            "answer": "The Lumen is a display mark.",
            "audit_passed": True,
            "related": [{"chunk_id": "display", "chunk_text": "The Lumen is a display mark."}],
        })
    assert decision["answer_status"] == "insufficient_evidence"
    assert decision["reason"] == "chosen_class_missing"
    assert decision["text"] == _UNSETTLED
    assert "display mark" not in decision["text"]
    assert reply["answer_status"] == "insufficient_evidence"
    assert reply["text"] == _UNSETTLED
    assert "display mark" not in reply["text"]


def test_the_selected_class_answers_when_only_that_sentence_was_retrieved():
    from cpu_llm.answerability import chosen_class

    rows = [{"document_id": "survey", "text": "The Lumen is a survey mark."}]
    with chosen_class("survey mark"):
        decision = assess("What is the Lumen?", rows)
    assert decision["answer_status"] == "answered"
    assert decision["reason"] == "chosen_class"
    assert decision["text"] == "The Lumen is a survey mark."


def _covers(fixture: dict, predicted: dict) -> bool:
    if predicted["answer_status"] != "answered":
        return False
    for item in fixture["chunks"]:
        if item["document_id"] == fixture["cite"] and item["text"] in predicted["text"]:
            return True
    return False


def _span_cited(predicted: dict, document_id: str) -> bool:
    for item in predicted.get("answer_evidence") or []:
        if item["document_id"] == document_id and item["span"] and item["span"] in predicted["text"]:
            return True
    return False
