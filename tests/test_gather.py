"""The creative gather keeps every paragraph of the article and ranks its words."""

from cpu_llm.agents.gather import gather_article


def test_the_group_includes_paragraphs_that_do_not_name_the_prompt():
    chunks = [
        {"document_id": "wikitext2-homarus-gammarus-p0001", "chunk_text": "The European lobster is Homarus gammarus."},
        {"document_id": "wikitext2-homarus-gammarus-p0002", "chunk_text": "The European lobster lives in the Atlantic Ocean."},
        {"document_id": "wikitext2-homarus-gammarus-p0003", "chunk_text": "A blue whale sings in the deep ocean."},
    ]
    pool = gather_article("Imagine the European lobster.", chunks)
    assert pool["articles"] == ["homarus-gammarus"]
    assert pool["categories"]["homarus-gammarus"] == 738691
    assert pool["paragraph_count"] == 3
    assert pool["word_count"] >= 8
    assert [item["document_id"] for item in pool["paragraphs"]][:2] == [
        "wikitext2-homarus-gammarus-p0001",
        "wikitext2-homarus-gammarus-p0002",
    ]
    assert pool["paragraphs"][-1]["document_id"] == "wikitext2-homarus-gammarus-p0003"
    assert pool["paragraphs"][-1]["relevance"] == 0
    words = [item["word"] for item in pool["most_relevant"]]
    assert words.index("lobster") < words.index("whale")
    assert "sings" in words


def test_ranked_paragraphs_are_realized_and_the_unrelated_one_is_not():
    from cpu_llm.agents.gather import realize_ranked_paragraphs
    from cpu_llm.audit.entailment import EpistemicEntailmentAuditor
    from cpu_llm.clauses import proposition_from_chunk
    from cpu_llm.realizer.surface import SemanticSurfaceRealizer

    chunks = [
        {"document_id": "wikitext2-homarus-gammarus-p0001", "chunk_text": "The European lobster is Homarus gammarus."},
        {"document_id": "wikitext2-homarus-gammarus-p0002", "chunk_text": "Homarus gammarus is a species of clawed lobster."},
        {"document_id": "wikitext2-homarus-gammarus-p0003", "chunk_text": "The European lobster lives along the coast."},
        {"document_id": "wikitext2-homarus-gammarus-p0004", "chunk_text": "A blue whale sings in the deep ocean."},
    ]
    pool = gather_article("Imagine the European lobster.", chunks)

    def proposition_for(document_id: str, text: str, _tensor: object) -> object:
        return proposition_from_chunk(document_id, text)

    realized = realize_ranked_paragraphs(
        "Imagine the European lobster.",
        chunks,
        pool,
        proposition_for,
        SemanticSurfaceRealizer(),
        EpistemicEntailmentAuditor(),
    )
    assert realized["text"] == (
        "The European lobster is Homarus gammarus. "
        "Homarus gammarus is a species of clawed lobster."
    )
    assert "blue whale" not in realized["text"]
    assert "coast" not in realized["text"]
    assert realized["realized"] == 2


def test_the_same_creative_query_draws_a_different_passage():
    import random

    from cpu_llm.agents.gather import realize_ranked_paragraphs
    from cpu_llm.audit.entailment import EpistemicEntailmentAuditor
    from cpu_llm.clauses import proposition_from_chunk
    from cpu_llm.realizer.surface import SemanticSurfaceRealizer

    chunks = [
        {"document_id": "wikitext2-homarus-gammarus-p0001", "chunk_text": "The European lobster is Homarus gammarus."},
        {"document_id": "wikitext2-homarus-gammarus-p0002", "chunk_text": "Homarus gammarus is a species of clawed lobster."},
        {"document_id": "wikitext2-homarus-gammarus-p0003", "chunk_text": "The European lobster lives along the coast."},
        {"document_id": "wikitext2-homarus-gammarus-p0004", "chunk_text": "A blue whale sings in the deep ocean."},
    ]
    pool = gather_article("Imagine the European lobster.", chunks)
    allowed = {
        "The European lobster is Homarus gammarus.",
        "Homarus gammarus is a species of clawed lobster.",
    }

    def proposition_for(document_id: str, text: str, _tensor: object) -> object:
        return proposition_from_chunk(document_id, text)

    def draw(seed: int, avoid: set[str] | None = None) -> str:
        realized = realize_ranked_paragraphs(
            "Imagine the European lobster.",
            chunks,
            pool,
            proposition_for,
            SemanticSurfaceRealizer(),
            EpistemicEntailmentAuditor(),
            vary=True,
            rng=random.Random(seed),
            avoid=avoid,
        )
        assert "blue whale" not in realized["text"]
        assert "coast" not in realized["text"]
        sentences = [part if part.endswith(".") else f"{part}." for part in realized["text"].split(". ")]
        assert sentences
        assert set(sentences) <= allowed
        return realized["text"]

    draws = {draw(seed) for seed in range(8)}
    assert len(draws) > 1
    first = draw(0)
    assert draw(0, avoid={first}) != first
