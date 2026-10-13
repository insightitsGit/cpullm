"""Prompt triggers that sit beside the grounded turn.

A descriptive question stays on the fixed chain. Creative writing runs only
when this classifier names a reason, or when the caller turns it on.
"""

from __future__ import annotations

import re

_REASONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:imagine|imagined|imagination)\b", re.IGNORECASE),
        "the prompt asks for an imagined scene",
    ),
    (
        re.compile(r"\bwhat if\b", re.IGNORECASE),
        "the prompt asks for an imagined scene",
    ),
    (
        re.compile(r"\b(?:story|stories|tale|tales|narrative|narrate)\b", re.IGNORECASE),
        "the prompt asks for a story",
    ),
    (
        re.compile(r"\b(?:poem|fiction|fictional)\b", re.IGNORECASE),
        "the prompt asks for fiction",
    ),
    (
        re.compile(r"\bcreative writing\b|\bcreatively\b", re.IGNORECASE),
        "the prompt asks for creative writing",
    ),
)

_DEEP_REASONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bdeep search\b", re.IGNORECASE),
        "the prompt asks for a deep search",
    ),
    (
        re.compile(r"\bsearch deeply\b|\bsearch all\b|\blook everywhere\b", re.IGNORECASE),
        "the prompt asks for a deep search",
    ),
    (
        re.compile(r"\ball possible\b|\ball possibilities\b", re.IGNORECASE),
        "the prompt asks for every possibility",
    ),
)

CALLER_REASON = "the caller turned creative writing on"
DEEP_CALLER_REASON = "the caller turned deep search on"


def creative_writing_trigger(message: str, *, forced: bool = False) -> list[str]:
    """Reasons to leave the fixed chain and walk the article.

    The list is empty for a plain question. ``forced`` records that the caller
    turned the step on, and the wording of the prompt is still classified.
    """
    reasons: list[str] = []
    if forced:
        reasons.append(CALLER_REASON)
    for pattern, reason in _REASONS:
        if reason in reasons:
            continue
        if pattern.search(message or ""):
            reasons.append(reason)
    return reasons


def deep_search_trigger(message: str, *, forced: bool = False) -> list[str]:
    """Reasons to return every matching chunk instead of one ranked sentence.

    A plain question stays on the shortlist. ``forced`` records that the caller
    turned the wider search on.
    """
    reasons: list[str] = []
    if forced:
        reasons.append(DEEP_CALLER_REASON)
    for pattern, reason in _DEEP_REASONS:
        if reason in reasons:
            continue
        if pattern.search(message or ""):
            reasons.append(reason)
    return reasons
