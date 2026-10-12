"""An imagined passage from one article's stored tensors.

The shortlist names the articles. Every paragraph of those articles is loaded.
PrismResonance scores each paragraph against the question. A paragraph whose
interference is not positive is left out. The paragraphs that stay are ordered
by a walk along their dense cores: each step is the nearest unused paragraph.
The sentence copied from a paragraph is one already written there. The words
named on a step are the question's content words that occur in that sentence.

This is not a cause, a measurement, or a proposition, and it is not the
checked sentence.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from vectorprism.tensor_contract import PSMTensorContract

from cpu_llm.catalog import article_slug
from cpu_llm.channels import _best_sentence, _content_words, _cosine, _slice

_NOTE = (
    "Each sentence is copied from a paragraph of an article the shortlist already named. "
    "PrismResonance keeps a paragraph whose interference with the question is positive. "
    "Dense-core cosine orders those paragraphs. The link is that the tensors sit near each other."
)
_EMPTY = "The shortlist named no article, so there is nothing to connect."
_SILENT = "None of the loaded paragraphs interfered with the question."


def compose_imagination(
    message: str,
    chunks: list[dict[str, Any]],
    resonance: dict[str, float],
) -> dict[str, Any]:
    """Walk ``chunks`` whose resonance scores are positive.

    ``chunks`` carry ``document_id``, ``chunk_text``, and ``tensor``.
    ``resonance`` maps a document id to the PrismResonance score.
    """
    if not chunks:
        return _result([], [], _EMPTY)
    kept: list[dict[str, Any]] = []
    for chunk in chunks:
        document_id = str(chunk["document_id"])
        score = resonance.get(document_id)
        if score is None or not np.isfinite(score) or float(score) <= 0.0:
            continue
        tensor = np.asarray(chunk["tensor"], dtype=np.float64).reshape(-1)
        kept.append(
            {
                "document_id": document_id,
                "chunk_text": str(chunk["chunk_text"]),
                "tensor": tensor,
                "resonance": float(score),
            }
        )
    if not kept:
        return _result(_articles(chunks), [], _SILENT, loaded=len(chunks))
    ordered = _walk(kept)
    links: list[dict[str, Any]] = []
    keywords: list[str] = []
    sentences: list[str] = []
    for item in ordered:
        sentence = _best_sentence(item["chunk_text"], message)
        words = _shared_keywords(message, sentence)
        for word in words:
            if word not in keywords:
                keywords.append(word)
        cosine = item["cosine_to_previous"]
        links.append(
            {
                "chunk_id": item["document_id"],
                "resonance": item["resonance"],
                "cosine_to_previous": None if cosine is None else float(cosine),
                "sentence": sentence,
                "keywords": words,
            }
        )
        if sentence:
            sentences.append(sentence)
    return _result(_articles(chunks), links, _NOTE, loaded=len(chunks), keywords=keywords, text=" ".join(sentences))


def _result(
    articles: list[str],
    links: list[dict[str, Any]],
    note: str,
    *,
    loaded: int = 0,
    keywords: list[str] | None = None,
    text: str = "",
) -> dict[str, Any]:
    return {
        "triggered": True,
        "articles": articles,
        "loaded": loaded,
        "links": links,
        "keywords": list(keywords or []),
        "text": text,
        "note": note,
    }


def _articles(chunks: list[dict[str, Any]]) -> list[str]:
    slugs: list[str] = []
    for chunk in chunks:
        slug = article_slug(str(chunk["document_id"]))
        if slug not in slugs:
            slugs.append(slug)
    return slugs


def _shared_keywords(message: str, sentence: str) -> list[str]:
    present = set(_content_words(sentence))
    words: list[str] = []
    for word in _content_words(message):
        if word in present and word not in words:
            words.append(word)
    return words


def _dense(tensor: np.ndarray) -> np.ndarray:
    return _slice(tensor, PSMTensorContract.DENSE_CORE)


def _walk(kept: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remaining = sorted(kept, key=lambda item: (-item["resonance"], item["document_id"]))
    start = remaining.pop(0)
    start["cosine_to_previous"] = None
    ordered = [start]
    while remaining:
        current = _dense(ordered[-1]["tensor"])
        best_at = 0
        best_rank: tuple[float, str] | None = None
        best_cosine = None
        for index, item in enumerate(remaining):
            cosine = _cosine(current, _dense(item["tensor"]))
            rank = (-(cosine if cosine is not None else -2.0), item["document_id"])
            if best_rank is None or rank < best_rank:
                best_rank = rank
                best_at = index
                best_cosine = cosine
        chosen = remaining.pop(best_at)
        chosen["cosine_to_previous"] = best_cosine
        ordered.append(chosen)
    return ordered
