"""A supplied proposition realizes the clause already written in its chunk."""

from cpu_llm.audit.entailment import EpistemicEntailmentAuditor
from cpu_llm.proposition_catalog import homarus_definition
from cpu_llm.realizer.surface import SemanticSurfaceRealizer
from cpu_llm.source import validation_chunks

SENTENCE = "Homarus gammarus is a species of clawed lobster."


def test_homarus_proposition_realizes_the_clause_in_the_paragraph():
    text = next(chunk for document_id, _title, chunk in validation_chunks() if document_id == "wikitext2-homarus-gammarus-p0001")
    proposition = homarus_definition()
    assert proposition.subject.raw_text in text
    assert proposition.object_target is not None
    assert proposition.object_target.raw_text in text
    sentence, delivered = SemanticSurfaceRealizer().synthesize([proposition], [])
    assert sentence == SENTENCE
    assert EpistemicEntailmentAuditor().audit_delivered_output(delivered, [proposition]) is True
