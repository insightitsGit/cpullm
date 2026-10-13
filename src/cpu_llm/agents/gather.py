"""Gather every paragraph of the creative article and rank its words.

The shortlist names the article. This node loads the rest of that article,
not only the lead paragraph. It collects the content words of those
paragraphs and ranks them by how often they sit in a paragraph that shares
the prompt's words. The checked sentence is not written here.
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np

from cpu_llm.catalog import article_slug
from cpu_llm.channels import _content_words, _cosine, _slice
from cpu_llm.word_taxonomy import category_number
from vectorprism.tensor_contract import PSMTensorContract

_MOST = 32


def realize_ranked_paragraphs(
    message: str,
    rows: list[dict[str, Any]],
    pool: dict[str, Any],
    proposition_for,
    realizer,
    auditor,
    *,
    numbers_allowed=None,
    vary: bool = False,
    rng: random.Random | None = None,
    avoid: set[str] | None = None,
) -> dict[str, Any]:
    """Realize the ranked paragraphs with the sentence function, then check each one.

    A paragraph is skipped when it has no proposition the realizer can repeat,
    when the auditor rejects the sentence, or when a number in it is not in
    the gathered paragraphs. The checked answer is left alone. With ``vary``,
    each call draws a different order and a different subset of the sentences
    that passed those checks.
    """
    by_id = {str(row["document_id"]): row for row in rows}
    chosen = [item for item in pool.get("paragraphs") or [] if item.get("relevance", 0) > 0]
    if not chosen:
        chosen = list(pool.get("paragraphs") or [])[:1]
    links: list[dict[str, Any]] = []
    sentences: list[str] = []
    for item in chosen:
        document_id = str(item["document_id"])
        row = by_id.get(document_id)
        if row is None:
            continue
        text = str(row.get("chunk_text") or "")
        proposition = proposition_for(document_id, text, row.get("tensor_1024d"))
        if proposition is None:
            continue
        sentence, delivered = realizer.synthesize([proposition], [])
        if not sentence or not auditor.audit_delivered_output(delivered, [proposition]):
            continue
        if numbers_allowed is not None and not numbers_allowed(sentence):
            continue
        prompt = set(_content_words(message))
        keywords = [word for word in _content_words(sentence) if word in prompt]
        links.append(
            {
                "chunk_id": document_id,
                "sentence": sentence,
                "keywords": keywords,
                "relevance": item.get("relevance", 0),
            }
        )
    if vary:
        links = _varied_passage(links, rng or random.SystemRandom(), set(avoid or ()))
    sentences = [item["sentence"] for item in links]
    return {
        "text": " ".join(sentences),
        "links": links,
        "realized": len(sentences),
        "varied": vary,
    }


def _varied_passage(
    links: list[dict[str, Any]],
    rng: random.Random,
    avoid: set[str],
) -> list[dict[str, Any]]:
    """Pick an arrangement that is not one already returned for this prompt."""
    if len(links) < 2:
        return links
    limit = min(len(links), 3)
    for _ in range(48):
        count = rng.randint(1, limit)
        picks = rng.sample(list(links), count)
        if _passage(picks) not in avoid:
            return picks
    for shift in range(len(links)):
        rotated = links[shift:] + links[:shift]
        for count in range(1, limit + 1):
            picks = rotated[:count]
            if _passage(picks) not in avoid:
                return picks
    return links


def _passage(links: list[dict[str, Any]]) -> str:
    return " ".join(item["sentence"] for item in links)


def gather_article(
    message: str,
    chunks: list[dict[str, Any]],
    query: np.ndarray | None = None,
) -> dict[str, Any]:
    """Rank the words and paragraphs in ``chunks`` against ``message``.

    ``chunks`` carry ``document_id`` and ``chunk_text``. A ``tensor`` is used
    only as a dense-core tie break. Every chunk stays in the group.
    """
    prompt = list(dict.fromkeys(_content_words(message)))
    prompt_set = set(prompt)
    articles: list[str] = []
    paragraphs: list[dict[str, Any]] = []
    locations: dict[str, list[str]] = {}
    for chunk in chunks:
        document_id = str(chunk["document_id"])
        slug = article_slug(document_id)
        if slug not in articles:
            articles.append(slug)
        words = list(dict.fromkeys(_content_words(str(chunk.get("chunk_text") or ""))))
        present = set(words)
        shared = [word for word in prompt if word in present]
        cosine = _dense_cosine(query, chunk.get("tensor") or chunk.get("tensor_1024d"))
        paragraphs.append(
            {
                "document_id": document_id,
                "article": slug,
                "relevance": len(shared),
                "prompt_words": shared,
                "cosine": cosine,
            }
        )
        for word in words:
            locations.setdefault(word, [])
            if document_id not in locations[word]:
                locations[word].append(document_id)
    supporting = {item["document_id"] for item in paragraphs if item["relevance"] > 0}
    if not supporting:
        supporting = {item["document_id"] for item in paragraphs}
    ranked_words = []
    for word, document_ids in locations.items():
        support = sum(1 for document_id in document_ids if document_id in supporting)
        score = support + (2 if word in prompt_set else 0)
        ranked_words.append((score, word, document_ids))
    ranked_words.sort(key=lambda item: (-item[0], item[1]))
    paragraphs.sort(
        key=lambda item: (
            -item["relevance"],
            -(item["cosine"] if item["cosine"] is not None else -2.0),
            item["document_id"],
        )
    )
    return {
        "articles": articles,
        "categories": {slug: category_number(slug) for slug in articles},
        "paragraph_count": len(paragraphs),
        "word_count": len(ranked_words),
        "paragraphs": paragraphs,
        "most_relevant": [
            {"word": word, "score": score, "paragraphs": len(document_ids)}
            for score, word, document_ids in ranked_words[:_MOST]
        ],
    }


def _dense_cosine(query: np.ndarray | None, tensor: Any) -> float | None:
    if query is None or tensor is None:
        return None
    left = _slice(np.asarray(query, dtype=np.float64).reshape(-1), PSMTensorContract.DENSE_CORE)
    right = _slice(np.asarray(tensor, dtype=np.float64).reshape(-1), PSMTensorContract.DENSE_CORE)
    return _cosine(left, right)
