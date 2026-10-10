"""Training stores a proposition only when the realizer repeats the sentence."""

from cpu_llm.clauses import proposition_from_chunk, propositions_for
from cpu_llm.source import validation_chunks


def test_homarus_lead_repeats_its_first_sentence():
    text = next(
        chunk
        for document_id, _title, chunk in validation_chunks()
        if document_id == "wikitext2-homarus-gammarus-p0001"
    )
    proposition = proposition_from_chunk("wikitext2-homarus-gammarus-p0001", text)
    assert proposition is not None
    assert proposition.predicate.lemma == "be"
    assert proposition.subject.raw_text in text
    assert proposition.object_target is not None
    assert proposition.object_target.raw_text in text
    assert proposition.object_target.raw_text.startswith("a species of clawed lobster")


def test_a_sentence_without_a_finite_verb_is_not_invented():
    text = "Adult animals along the shelf at those depths."
    assert proposition_from_chunk("doc-plain", text) is None


def test_an_abbreviation_does_not_cut_the_sentence():
    text = (
        "Following the outbreak of World War II, No. 1 Squadron was engaged "
        "in convoy escort and maritime reconnaissance duties off south-eastern Australia."
    )
    proposition = proposition_from_chunk("doc-squadron", text)
    assert proposition is not None
    assert proposition.predicate.lemma == "be"
    assert proposition.predicate.tense == "PAST"
    assert "No. 1 Squadron" in proposition.subject.raw_text


def test_past_copula_repeats_was():
    text = "Headlam was Officer Commanding North-Western Area in 1946."
    proposition = proposition_from_chunk("doc-headlam", text)
    assert proposition is not None
    assert proposition.predicate.tense == "PAST"
    assert proposition.predicate.lemma == "be"


def test_validation_catalog_covers_repeatable_sentences_only():
    chunks = [(document_id, text) for document_id, _title, text in validation_chunks()]
    found = propositions_for(chunks)
    assert "wikitext2-homarus-gammarus-p0001" in found
    assert len(found) < len(chunks)
    assert len(found) > 1400
