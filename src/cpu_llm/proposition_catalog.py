"""Propositions supplied with a source chunk.

WikiText paragraphs are not parsed into these records. A record is added
here only when its clause is already written in that chunk. The realizer
then turns the record into a sentence. An open quantifier is used because
the paragraph says "is", and the ALL template would say "All ... are".
"""

from __future__ import annotations

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

HOMARUS_DOCUMENT_ID = "wikitext2-homarus-gammarus-p0001"


def homarus_definition() -> EIRProposition:
    return EIRProposition(
        proposition_id="prop_homarus_gammarus_def",
        polarity=Polarity.AFFIRMATIVE,
        modality=Modality.DECLARATIVE,
        quantifier=Quantifier(qtype=QuantifierType.UNSPECIFIED),
        subject=TypedEntity(raw_text="Homarus gammarus", lemma="Homarus gammarus", is_plural=False),
        predicate=TypedPredicate(lemma="be", tense="PRESENT", voice="ACTIVE"),
        object_target=TypedEntity(raw_text="a species of clawed lobster", lemma="species", is_plural=False),
        epistemic_status=EpistemicStatus.RETRIEVED_FACT,
        epistemic_weight=1.0,
    )


def supplied_propositions() -> dict[str, EIRProposition]:
    return {HOMARUS_DOCUMENT_ID: homarus_definition()}
