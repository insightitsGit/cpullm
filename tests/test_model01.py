"""Model01 writes a checked sentence and does not train without two teachers."""

from dataclasses import replace

from cpu_llm.agents.reply import compose_reply
from cpu_llm.model01.corpus import collect_pairs, load_pairs, save_pairs
from cpu_llm.model01.generator import apply_model01, generate
from cpu_llm.model01.train import survey, train

_SPECIES = (
    "Homarus gammarus, known as the European lobster or common lobster, "
    "is a species of clawed lobster from the eastern Atlantic Ocean, "
    "Mediterranean Sea and parts of the Black Sea."
)
_RANKED = "The European lobster is the best lobster in Europe."


def test_model01_names_the_prompt_and_the_stored_records():
    result = generate("What did Mary bake?", [("mary", "Mary baked a cake.")])
    assert result["model_id"] == "model01"
    assert result["model_name"] == "Model01 sentence generator"
    assert result["checkpoint_id"] is None
    assert result["mode"] == "model01"
    assert result["inputs"]["prompt"] == "What did Mary bake?"
    assert result["inputs"]["evidence"]
    assert result["text"]
    assert "best" not in result["text"].casefold()
    for word in result["text"].replace(".", "").split():
        if word.casefold() in {"mary", "baked", "a", "cake"}:
            assert word.casefold() in "mary baked a cake"


def test_model01_quotes_a_stored_ranking_and_states_a_gap():
    stated = generate(
        "what is the best lobster in eroupe?",
        [("species", _SPECIES), ("ranked", _RANKED)],
    )
    assert _RANKED in stated["text"]
    assert stated["checkpoint_id"] is None
    missing = generate("what is the best lobster in eroupe?", [("species", _SPECIES)])
    assert "do not state a ranking" in missing["text"]
    assert "is the best" not in missing["text"]
    assert "Homarus gammarus" in missing["text"]


def test_a_rejected_delivery_is_not_replaced_by_model01():
    update = apply_model01(
        {
            "message": "What did Mary bake?",
            "delivery_blocked": "audit",
            "related": [{"chunk_id": "mary", "chunk_text": "Mary baked a cake."}],
            "reply": {"text": "The checked sentence was withheld."},
        }
    )
    assert "reply" not in update
    assert update["model01"]["checkpoint_id"] is None


def test_a_checked_sentence_is_kept_and_an_invented_ranking_is_not():
    apple = "John ate a yellow apple in his house."
    pairs = collect_pairs(
        [
            ("mary", "Mary baked a cake.", "unit"),
            ("apple", apple, "unit"),
            ("ranked", _RANKED, "unit"),
            ("species", _SPECIES, "unit"),
        ]
    )
    cake = next(pair for pair in pairs if pair.document_id == "mary" and pair.kind == "proposition")
    assert cake.gold_text == "Mary baked a cake."
    assert "best" not in cake.gold_text.casefold()
    color = next(pair for pair in pairs if pair.document_id == "apple" and pair.prompt.startswith("What color"))
    assert color.gold_text == "The apple John ate was yellow."
    ranking = next(pair for pair in pairs if pair.kind == "ranking")
    assert _RANKED in ranking.gold_text
    assert ranking.document_id == "ranked"
    species = [pair for pair in pairs if pair.document_id == "species" and pair.kind == "ranking"]
    assert species == []


def test_a_pair_round_trips_through_postgres():
    pair = collect_pairs([("mary-db", "Mary baked a cake.", "unit")])[0]
    stored = replace(pair, model_id="model01-test")
    save_pairs([stored])
    try:
        found = load_pairs(model_id="model01-test")
        assert [item.gold_text for item in found] == ["Mary baked a cake."]
        assert found[0].split == "unit"
        assert found[0].prompt == "What is Mary?"
    finally:
        _delete_test_rows()


def _delete_test_rows() -> None:
    import psycopg

    from cpu_llm.model01.corpus import TABLE
    from cpu_llm.retrieval import LOCAL_PG_DSN

    with psycopg.connect(LOCAL_PG_DSN) as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"DELETE FROM {TABLE} WHERE model_id = %s", ("model01-test",))
        conn.commit()


def test_model01_binds_a_whole_name_and_keeps_a_short_name():
    from cpu_llm.agents.reply import compose_reply
    from cpu_llm.pipeline import _model01, _passages_for_sentence

    related = [
        {"chunk_id": "bird", "chunk_text": "The harbor kestrel is a small coastal falcon."},
        {"chunk_id": "picnic", "chunk_text": "The picnic was held beside a harbor."},
        {"chunk_id": "ada", "chunk_text": "Ada is a mathematician."},
        {"chunk_id": "policy", "chunk_text": "Business class is allowed for flights over six hours."},
    ]
    bird = _passages_for_sentence("Tell me about the harbor kestrel.", related)
    ada = _passages_for_sentence("Tell me about Ada.", related)
    assert [item["chunk_id"] for item in bird] == ["bird"]
    assert [item["chunk_id"] for item in ada] == ["ada"]
    broad = "Business class is allowed for flights over six hours. The picnic was held beside a harbor."
    for question, kept in (
        ("Tell me about the harbor kestrel.", "kestrel"),
        ("Tell me about Ada.", "Ada"),
    ):
        state = {
            "message": question,
            "guard_decision": "allow",
            "related": related,
            "answer": broad,
        }
        state.update(_model01(state))
        reply = compose_reply(state)
        assert kept in reply["text"]
        assert "picnic" not in reply["text"].casefold()
        assert "business class" not in reply["text"].casefold()


def test_a_name_keeps_its_internal_words():
    from cpu_llm.agents.reply import compose_reply
    from cpu_llm.pipeline import _model01, _passages_for_sentence, _prompt_entity

    related = [
        {"chunk_id": "bank", "chunk_text": "Bank of America is a bank."},
        {"chunk_id": "department", "chunk_text": "Research and Development is a department."},
        {"chunk_id": "bird", "chunk_text": "The harbor kestrel is a small coastal falcon."},
        {"chunk_id": "picnic", "chunk_text": "The picnic was held beside a harbor."},
        {"chunk_id": "ada", "chunk_text": "Ada is a mathematician."},
    ]
    assert _prompt_entity("Tell me about Bank of America.") == "Bank of America"
    assert _prompt_entity("Tell me about Research and Development.") == "Research and Development"
    assert [item["chunk_id"] for item in _passages_for_sentence("Tell me about Bank of America.", related)] == ["bank"]
    assert [item["chunk_id"] for item in _passages_for_sentence("Tell me about Research and Development.", related)] == ["department"]
    for question, kept in (
        ("Tell me about Bank of America.", "Bank of America is a bank."),
        ("Tell me about Research and Development.", "Research and Development is a department."),
        ("Tell me about Ada.", "Ada is a mathematician."),
        ("Tell me about the harbor kestrel.", "The harbor kestrel is a small coastal falcon."),
    ):
        state = {"message": question, "guard_decision": "allow", "related": related, "answer": "The picnic was held beside a harbor."}
        state.update(_model01(state))
        reply = compose_reply(state)
        assert kept in reply["text"]
        assert "picnic" not in reply["text"].casefold()


def test_model01_does_not_copy_an_unrelated_passage():
    from cpu_llm.pipeline import _model01

    update = _model01(
        {
            "message": "What is Mary?",
            "guard_decision": "allow",
            "related": [
                {"chunk_id": "mary", "chunk_text": "Mary baked a cake."},
                {"chunk_id": "other", "chunk_text": "Kinberg supported a number of changes to the liturgy."},
            ],
        }
    )
    assert update["model01"]["text"] == "Mary baked a cake."
    assert "Kinberg" not in update["model01"]["text"]


def test_model01_is_the_step_before_the_reply():
    from cpu_llm.pipeline import _after_finance, _after_math, _after_shine

    assert _after_shine({}) == "model01"
    assert _after_math({}) == "model01"
    assert _after_finance({}) == "model01"
    assert _after_shine({"guard_decision": "block"}) == "reply"
    reply = compose_reply(
        {
            "message": "What did Mary bake?",
            "guard_decision": "allow",
            "answer": "Mary baked a cake.",
            "related": [{"chunk_id": "mary", "chunk_text": "Mary baked a cake.", "score": 0.9}],
            "model01": {"verified": True, "text": "Mary baked a cake.", "mode": "model01"},
        }
    )
    assert reply["text"] == "Mary baked a cake."
    ranked = compose_reply(
        {
            "message": "what is the best lobster?",
            "guard_decision": "allow",
            "answer": _SPECIES,
            "related": [{"chunk_id": "species", "chunk_text": _SPECIES, "score": 0.9}],
            "model01": {
                "verified": True,
                "text": f"{_SPECIES}\n\nRanking:\nThe retrieved passages do not state a ranking.",
            },
        }
    )
    assert ranked["text"].count("Ranking:") == 1


def test_model01_keeps_the_ranking_sentence_and_drops_a_topic_neighbor():
    from cpu_llm.agents.reply import compose_reply

    species = "Homarus gammarus is a species of clawed lobster."
    ranked = "The European lobster is the best lobster in Europe."
    reply = compose_reply(
        {
            "message": "what is the best lobster in europe?",
            "guard_decision": "allow",
            "answer": f"{ranked} {species}",
            "related": [
                {"chunk_id": "ranked", "chunk_text": ranked},
                {"chunk_id": "species", "chunk_text": species},
            ],
            "model01": {"verified": True, "text": f"{ranked} {species}"},
        }
    )
    assert ranked in reply["text"]
    assert species not in reply["text"]
    assert "Ranking:" in reply["text"]
    summary = compose_reply(
        {
            "message": "Summarize the European lobster.",
            "guard_decision": "allow",
            "summarize": True,
            "answer": ranked,
            "brief": {"summary": ranked},
            "model01": {"verified": True, "text": f"{species} {ranked}"},
            "related": [{"chunk_id": "ranked", "chunk_text": ranked}],
        }
    )
    assert summary["text"].startswith(ranked)
    assert species not in summary["text"]
    assert "Summary:" in summary["text"]


def test_training_stops_when_every_plan_has_one_sentence():
    report = survey(
        [
            ("mary", "Mary baked a cake."),
            ("species", _SPECIES),
            ("ranked", _RANKED),
        ]
    )
    assert report.max_derivations == 1
    assert report.ready is False
    assert report.checkpoint_written is False
    assert "no choice to learn" in report.reason
    shipped = train()
    assert shipped.model_name == "Model01 sentence generator"
    assert shipped.paragraphs > 4000
    assert shipped.propositions > 3000
    assert shipped.max_derivations == 1
    assert shipped.ready is False
    assert shipped.checkpoint_written is False
