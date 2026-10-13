"""Split a comparison into its topics and keep each topic's own chunks.

A prompt is a comparison when it names at least two topics and asks to
compare them. Each topic is then read on its own. A stored article title
loads that article. Otherwise the topic keeps every paragraph tagged with
its words. Paragraphs of the other topic are not borrowed, and a topic with
nothing stored stays empty.
"""

from __future__ import annotations

import re
from typing import Any

from cpu_llm.catalog import article_slug, title_slugs
from cpu_llm.channels import _content_words

_IS_COMPARISON = re.compile(
    r"\b(?:compare|comparing|comparison|difference|different|versus|vs\.?)\b",
    re.IGNORECASE,
)
_SPLIT = re.compile(
    r"\b(?:difference between|different from|different than|compared with|compared to|comparison of|versus|vs\.?|and)\b|,",
    re.IGNORECASE,
)
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
_FILLER = frozenset(
    """
    what which who how why when where is are was were be been being do does did
    a an the of to and or in on for with from by between among than about please
    tell me deep search imagine imagined imagination creatively versus vs
    summarize summary briefly explain why list cite source sources
    compare comparing comparison difference different
    """.split()
)


def comparison_sides(message: str) -> list[str]:
    """The topics a comparison names, in the order written.

    An empty list means the prompt is not a comparison. ``different`` with
    only one topic is not a comparison.
    """
    if not _IS_COMPARISON.search(message or ""):
        return []
    sides: list[str] = []
    for piece in _SPLIT.split(message or ""):
        label = _clean(piece)
        if len(label) < 3 or label in sides:
            continue
        if not any(len(word) >= 3 for word in label.split()):
            continue
        sides.append(label)
    if len(sides) < 2:
        return []
    return sides


def possibilities_by_side(
    sides: list[str],
    word_tags: dict[str, dict[str, list[str]]],
    edges: list[Any] | None = None,
    index: Any | None = None,
) -> dict[str, Any]:
    """Every paragraph of each topic, tagged with that topic.

    ``edges`` is accepted so a deep-search call can pass the relation graph.
    The relation walk is not used here: a neighbor of one word is not the
    other topic, and it is not this topic either.
    """
    del edges
    possibilities: list[dict[str, Any]] = []
    seeds: list[dict[str, Any]] = []
    for side in sides:
        words = list(_content_words(side))
        seeds.append({"side": side, "seeds": words})
        if index is not None:
            rows = rows_for_side(index, word_tags, side)
            ids = [str(row["document_id"]) for row in rows]
        else:
            ids = topic_paragraph_ids(side, word_tags)
        for document_id in ids:
            possibilities.append(
                {
                    "document_id": document_id,
                    "article": article_slug(document_id),
                    "matched_words": words,
                    "via": ["topic"],
                    "side": side,
                }
            )
    return {
        "seeds": seeds,
        "hands": {},
        "count": len(possibilities),
        "possibilities": possibilities,
    }


def rows_for_side(
    index: Any,
    word_tags: dict[str, dict[str, list[str]]],
    side: str,
) -> list[dict[str, Any]]:
    """Paragraphs that belong to ``side`` and not to a neighboring topic.

    The first stored article title wins. A topic with no stored title keeps
    the paragraphs tagged with its own words, without the relation walk.
    """
    words = set(_content_words(side))
    for slug in title_slugs(side):
        slug_words = set(slug.split("-"))
        if words and len(slug_words) < len(words):
            continue
        lead = index.lead_for_slug(slug)
        if lead is None:
            continue
        return list(index.chunks_for_articles([str(lead["document_id"])]))
    ids = topic_paragraph_ids(side, word_tags)
    if not ids or not hasattr(index.db, "get_by_ids"):
        return []
    return list(index.db.get_by_ids(ids))


def topic_paragraph_ids(side: str, word_tags: dict[str, dict[str, list[str]]]) -> list[str]:
    """Paragraphs tagged with this topic.

    Two words keep only paragraphs tagged with both. A single word keeps
    every paragraph tagged with it. Nothing is added from a relation edge.
    """
    groups: list[set[str]] = []
    for word in _content_words(side):
        found: set[str] = set()
        for document_ids in (word_tags.get(word) or {}).values():
            found.update(document_ids)
        if found:
            groups.append(found)
    if not groups:
        return []
    if len(groups) >= 2:
        shared = set.intersection(*groups)
        if shared:
            return sorted(shared)
    return sorted(min(groups, key=len))


def _clean(piece: str) -> str:
    words = _WORD.findall(piece or "")
    while words and words[0].casefold() in _FILLER:
        words.pop(0)
    while words and words[-1].casefold() in _FILLER:
        words.pop()
    return " ".join(words)
