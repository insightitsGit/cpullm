"""Which retrieved propositions are spoken, and which sentence leads."""

from cpu_llm.assembly import realization_order
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


def _proposition(document_id: str, subject: str, lemma: str, object_text: str) -> EIRProposition:
    return EIRProposition(
        proposition_id=f"prop-{document_id}",
        polarity=Polarity.AFFIRMATIVE,
        modality=Modality.DECLARATIVE,
        quantifier=Quantifier(qtype=QuantifierType.UNSPECIFIED),
        subject=TypedEntity(raw_text=subject, lemma=subject, is_plural=False),
        predicate=TypedPredicate(lemma=lemma, tense="PRESENT", voice="ACTIVE"),
        object_target=TypedEntity(raw_text=object_text, lemma=object_text, is_plural=False),
        epistemic_status=EpistemicStatus.RETRIEVED_FACT,
        epistemic_weight=1.0,
    )


def test_an_identity_question_leads_with_the_definition():
    hits = [
        {
            "document_id": "wikitext2test-robert-boulter-p0005",
            "chunk_text": "In 2006 Boulter starred in the play Citizenship written by Mark Ravenhill.",
        },
        {
            "document_id": "wikitext2test-robert-boulter-p0001",
            "chunk_text": "Robert Boulter is an English film, television and theatre actor.",
        },
    ]
    propositions = {
        "wikitext2test-robert-boulter-p0005": _proposition(
            "wikitext2test-robert-boulter-p0005",
            "In 2006 Boulter",
            "star",
            "in the play Citizenship written by Mark Ravenhill",
        ),
        "wikitext2test-robert-boulter-p0001": _proposition(
            "wikitext2test-robert-boulter-p0001",
            "Robert Boulter",
            "be",
            "an English film, television and theatre actor",
        ),
    }
    assert realization_order("What is Robert Boulter?", hits, propositions) == [
        "wikitext2test-robert-boulter-p0001",
        "wikitext2test-robert-boulter-p0005",
    ]


def test_an_open_question_drops_neighbors_that_share_no_query_word():
    hits = [
        {
            "document_id": "doc_hyper",
            "chunk_text": "Hyperbolic embeddings place taxonomy children near their parents.",
        },
        {
            "document_id": "wikitext2test-temnospondyli-p0020",
            "chunk_text": "Temnospondyli became a commonly used name at the turn of the century.",
        },
        {
            "document_id": "wikitext2test-kirby-s-block-ball-p0002",
            "chunk_text": "Reviewers considered the game an improvement on the Breakout formula.",
        },
    ]
    propositions = {
        "wikitext2test-temnospondyli-p0020": _proposition(
            "wikitext2test-temnospondyli-p0020",
            "Temnospondyli",
            "become",
            "a commonly used name at the turn of the century",
        ),
        "wikitext2test-kirby-s-block-ball-p0002": _proposition(
            "wikitext2test-kirby-s-block-ball-p0002",
            "Reviewers",
            "consider",
            "the game an improvement on the Breakout formula",
        ),
    }
    assert realization_order("Why use hyperbolic embeddings?", hits, propositions) == []
    propositions["doc_hyper"] = _proposition(
        "doc_hyper",
        "Hyperbolic embeddings",
        "place",
        "taxonomy children near their parents",
    )
    assert realization_order("Why use hyperbolic embeddings?", hits, propositions) == ["doc_hyper"]
