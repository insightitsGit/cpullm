"""Choose which retrieved propositions are realized, and in which order.

A named article stays inside that article. An open question keeps a neighbor
only when the neighbor shares a content word with the question. An identity
question then leads with an affirmative copula whose subject names one of
those words. Later events stay after that sentence. No relation is invented
for a sentence the chunk did not already store.
"""

from __future__ import annotations

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
    return _definitions_first(message, chosen, propositions)


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


def _definitions_first(
    message: str,
    document_ids: list[str],
    propositions: dict[str, EIRProposition],
) -> list[str]:
    if not is_identity_question(message):
        return document_ids
    words = set(_content_words(message))
    primary = [document_id for document_id in document_ids if _defines(propositions[document_id], words)]
    primary_ids = set(primary)
    return primary + [document_id for document_id in document_ids if document_id not in primary_ids]


def _defines(proposition: EIRProposition, words: set[str]) -> bool:
    if proposition.polarity is not Polarity.AFFIRMATIVE or proposition.predicate.lemma != "be":
        return False
    subject = set(_content_words(proposition.subject.raw_text))
    return bool(words & subject)
