"""Model01 writes a checked sentence and does not train without two teachers."""

from dataclasses import replace

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
