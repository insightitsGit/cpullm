"""Choose which retrieved propositions are realized, and in which order.

A named article stays inside that article. An open question keeps a neighbor
only when the neighbor shares a content word with the question. An identity
question then speaks a definition, then present attributes, then a past event.
A repeated subject is pronominalized by the realizer only when the whole
subject is the same entity again. A neural coreference model is not used:
it can attach a pronoun to the wrong noun, and it can drop a date that was
part of the subject. No relation is invented for a sentence the chunk did
not already store.
"""

from __future__ import annotations

import re
from typing import Any

from cpu_llm.catalog import article_slug, title_slugs
from cpu_llm.channels import _content_words
from cpu_llm.consolidation.sleep import is_identity_question
from cpu_llm.ir.schema import EIRProposition, Polarity


def realization_order(
    message: str,
    hits: list[dict[str, Any]],
    propositions: dict[str, EIRProposition],
) -> list[str]:
    """Document ids to realize. Empty when the on-topic passages have no proposition."""
    chosen = [
        str(hit["document_id"])
        for hit in _in_scope(message, hits)
        if str(hit["document_id"]) in propositions
    ]
    return _by_discourse(message, chosen, propositions)


def _in_scope(message: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    named = set(title_slugs(message))
    if named:
        kept = [hit for hit in hits if article_slug(str(hit["document_id"])) in named]
        if kept:
            return kept
    words = set(_content_words(message))
    if not words:
        return list(hits)
    matched = [
        hit
        for hit in hits
        if words & set(_content_words(str(hit.get("chunk_text") or "")))
    ]
    return matched if matched else list(hits)


_YEAR = re.compile(r"\b(?:1[89]|20)\d{2}\b")


def _by_discourse(
    message: str,
    document_ids: list[str],
    propositions: dict[str, EIRProposition],
) -> list[str]:
    """Definition, then attributes, then events. Other questions keep retrieval order."""
    if not is_identity_question(message):
        return document_ids
    words = set(_content_words(message))
    ranked = sorted(
        enumerate(document_ids),
        key=lambda item: (_band(propositions[item[1]], words), item[0]),
    )
    return [document_id for _index, document_id in ranked]


def _band(proposition: EIRProposition, words: set[str]) -> int:
    if _defines(proposition, words):
        return 0
    if proposition.predicate.tense == "PAST" or _mentions_year(proposition):
        return 2
    return 1


def _mentions_year(proposition: EIRProposition) -> bool:
    parts = [proposition.subject.raw_text]
    if proposition.object_target is not None:
        parts.append(proposition.object_target.raw_text)
    return _YEAR.search(" ".join(parts)) is not None


def _defines(proposition: EIRProposition, words: set[str]) -> bool:
    if proposition.polarity is not Polarity.AFFIRMATIVE or proposition.predicate.lemma != "be":
        return False
    subject = set(_content_words(proposition.subject.raw_text))
    return bool(words & subject)
