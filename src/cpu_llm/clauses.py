"""Cut one proposition from a chunk only when the realizer repeats its sentence.

The subject, the verb, and the object are slices of the first sentence. A
record is kept only when joining those slices again is that same sentence.
A paragraph with no such sentence stays text, and no triple is invented for it.
"""

from __future__ import annotations

import re

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
from cpu_llm.realizer.inflect import _IRREGULAR, forms
from cpu_llm.realizer.surface import SemanticSurfaceRealizer

_REALIZER = SemanticSurfaceRealizer()

_COPULA = {
    "is": ("be", False, "PRESENT"),
    "are": ("be", True, "PRESENT"),
    "was": ("be", False, "PAST"),
    "were": ("be", True, "PAST"),
}
_HAVE = {
    "has": ("have", False, "PRESENT"),
    "have": ("have", True, "PRESENT"),
    "had": ("have", False, "PAST"),
}
_NOT_VERBS = frozenset(
    """
    as at of in on for with from by to and or nor but if than that which who whom
    when where into over after before about between during without within across
    per via not no nor its their his her this these those known also only just
    such than then very more most other another
    """.split()
)


def proposition_from_chunk(document_id: str, text: str) -> EIRProposition | None:
    sentence = _first_sentence(text)
    body = sentence.rstrip(".!?").strip()
    if not body:
        return None
    tokens = body.split()
    for subject, lemma, plural, tense, object_text in _candidates(tokens):
        proposition = EIRProposition(
            proposition_id=f"prop-{document_id}",
            polarity=Polarity.AFFIRMATIVE,
            modality=Modality.DECLARATIVE,
            quantifier=Quantifier(qtype=QuantifierType.UNSPECIFIED),
            subject=TypedEntity(raw_text=subject, lemma=subject, is_plural=plural),
            predicate=TypedPredicate(lemma=lemma, tense=tense, voice="ACTIVE"),
            object_target=TypedEntity(raw_text=object_text, lemma=object_text, is_plural=False),
            epistemic_status=EpistemicStatus.RETRIEVED_FACT,
            epistemic_weight=1.0,
        )
        realized, _delivered = _REALIZER.synthesize([proposition], [])
        if realized == f"{body}." and subject in text and object_text in text:
            return proposition
    return None


def propositions_for(chunks: list[tuple[str, str]]) -> dict[str, EIRProposition]:
    found: dict[str, EIRProposition] = {}
    for document_id, text in chunks:
        proposition = proposition_from_chunk(document_id, text)
        if proposition is not None:
            found[document_id] = proposition
    return found


def _candidates(tokens: list[str]) -> list[tuple[str, str, bool, str, str]]:
    grouped: dict[str, list[tuple[str, str, bool, str, str]]] = {"copula": [], "have": [], "marked": []}
    for index, token in enumerate(tokens):
        if index == 0 or index == len(tokens) - 1:
            continue
        low = token.casefold()
        if low in _NOT_VERBS:
            continue
        subject = " ".join(tokens[:index])
        object_text = " ".join(tokens[index + 1 :])
        if not subject or not object_text:
            continue
        if low in _COPULA:
            lemma, plural, tense = _COPULA[low]
            grouped["copula"].append((subject, lemma, plural, tense, object_text))
            continue
        if low in _HAVE:
            lemma, plural, tense = _HAVE[low]
            grouped["have"].append((subject, lemma, plural, tense, object_text))
            continue
        parsed = _inflected(low)
        if parsed is not None:
            lemma, plural, tense = parsed
            grouped["marked"].append((subject, lemma, plural, tense, object_text))
    return grouped["copula"] + grouped["have"] + grouped["marked"]


def _inflected(token: str) -> tuple[str, bool, str] | None:
    for lemma, table in _IRREGULAR.items():
        if token == table["present_3s"] and token != lemma:
            return lemma, False, "PRESENT"
        if token == table["past"] and token != lemma:
            plural = table["past"] != table["past_pl"] and token == table["past_pl"]
            return lemma, plural, "PAST"
    if token.endswith("ied") and len(token) > 4:
        lemma = token[:-3] + "y"
        if forms(lemma)["past"] == token and lemma != token:
            return lemma, False, "PAST"
    if token.endswith("ed") and len(token) > 3:
        for lemma in (token[:-1], token[:-2]):
            if lemma and lemma != token and forms(lemma)["past"] == token:
                return lemma, False, "PAST"
    return None


_ABBREVIATION = re.compile(
    r"\b(?:No|Mr|Mrs|Ms|Dr|St|Jr|Sr|vs|etc|Fig|Prof|Gen|Col|Capt|Lt|Sgt|Mt)\.$|\b[A-Z]\.$"
)


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = ""
    for part in parts:
        kept = f"{kept} {part}".strip() if kept else part
        if _ABBREVIATION.search(kept) is None:
            break
    return kept.strip()
