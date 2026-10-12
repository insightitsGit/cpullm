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

CALLER_REASON = "the caller turned creative writing on"


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
