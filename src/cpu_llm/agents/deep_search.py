"""Every chunk a deep-search prompt can reach, with none removed.

The seeds are the prompt's content words, not the words that asked for the
search. A seed keeps every paragraph stored under it, in every article. The
relation walk then keeps every paragraph of the words one, two, and three
edges further. The checked sentence is not replaced.
"""

from __future__ import annotations

from typing import Any

from cpu_llm.catalog import article_slug
from cpu_llm.channels import _content_words
from cpu_llm.relations import relation_hands

_NOT_SEEDS = frozenset(
    "deep search deeply everywhere possible possibilities dive look all".split()
)


def collect_possibilities(
    message: str,
    word_tags: dict[str, dict[str, list[str]]],
    edges: list[Any] | None = None,
) -> dict[str, Any]:
    """Return every paragraph the seeds and their relation hands name."""
    seeds = [word for word in _content_words(message) if word not in _NOT_SEEDS]
    found: dict[str, dict[str, Any]] = {}
    for seed in seeds:
        _add_word(found, word_tags, seed, "word")
    hands = {1: [], 2: [], 3: []}
    if edges and seeds:
        hands = relation_hands(edges, seeds, limit=100_000)
        for hand, words in hands.items():
            for word in words:
                _add_word(found, word_tags, word, f"hand-{hand}")
    possibilities = [found[document_id] for document_id in sorted(found)]
    return {
        "seeds": seeds,
        "count": len(possibilities),
        "hands": {str(hand): list(words) for hand, words in hands.items()},
        "possibilities": possibilities,
    }


def _add_word(
    found: dict[str, dict[str, Any]],
    word_tags: dict[str, dict[str, list[str]]],
    word: str,
    via: str,
) -> None:
    for document_ids in (word_tags.get(word) or {}).values():
        for document_id in document_ids:
            item = found.setdefault(
                document_id,
                {
                    "document_id": document_id,
                    "article": article_slug(document_id),
                    "matched_words": [],
                    "via": [],
                },
            )
            if word not in item["matched_words"]:
                item["matched_words"].append(word)
            if via not in item["via"]:
                item["via"].append(via)
