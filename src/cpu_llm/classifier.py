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

_SUMMARY_REASONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:summarize|summarise|summary)\b", re.IGNORECASE),
        "the prompt asks for a summary",
    ),
    (
        re.compile(r"\b(?:tl;dr|tldr|in short|main points|most important|briefly)\b", re.IGNORECASE),
        "the prompt asks for a summary",
    ),
)
_EXPLAIN_REASONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:explain|why|how come|what caused)\b", re.IGNORECASE),
        "the prompt asks for an explanation",
    ),
)
_LIST_REASONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:list|enumerate|bullet points|bullets)\b", re.IGNORECASE),
        "the prompt asks for a list",
    ),
)
_SOURCE_REASONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:cite|citation|citations|sources)\b", re.IGNORECASE),
        "the prompt asks for sources",
    ),
)
_MATH_REASONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\d\s*(?:[+\-*/^×÷]|plus|minus|times|multiplied by|divided by)\s*\d", re.IGNORECASE),
        "the prompt contains an arithmetic expression",
    ),
    (
        re.compile(
            r"\d\s*(?:\*\*|\^)\s*\d|\d\s+(?:to\s+the\s+power\s+of|raised\s+to(?:\s+the\s+power\s+of)?)\s+\d"
            r"|\d\s+(?:squared|cubed)\b",
            re.IGNORECASE,
        ),
        "the prompt asks for a power",
    ),
    (
        re.compile(r"\d(?:\.\d+)?\s*(?:%|percent)\s+of\s+\d", re.IGNORECASE),
        "the prompt asks for a percentage",
    ),
    (
        re.compile(r"\b(?:square\s+root\s+of|sqrt)\s*\(?\s*\d", re.IGNORECASE),
        "the prompt asks for a square root",
    ),
    (
        re.compile(
            r"\b(?:sum|product|average|mean)\s+of\s+\d+(?:\.\d+)?"
            r"(?:\s*(?:,\s*(?:and\s+)?|and\s+)\d+(?:\.\d+)?)+",
            re.IGNORECASE,
        ),
        "the prompt asks for a calculation over a list of numbers",
    ),
)
MATH_CALLER_REASON = "the caller turned math on"


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


def summary_trigger(message: str) -> list[str]:
    """Reasons to keep the highest-weighted stored sentences."""
    return _matched(message, _SUMMARY_REASONS)


def explain_trigger(message: str) -> list[str]:
    """Reasons to speak a stored cause. This does not turn discovery on."""
    return _matched(message, _EXPLAIN_REASONS)


def list_trigger(message: str) -> list[str]:
    """Reasons to speak the ranked sentences one per line."""
    return _matched(message, _LIST_REASONS)


def source_trigger(message: str) -> list[str]:
    """Reasons to name the paragraphs the sentences came from."""
    return _matched(message, _SOURCE_REASONS)


def finance_trigger(message: str, *, forced: bool = False) -> list[str]:
    """Reasons to run RefundProof, LedgerCovenant, or Ledgerlock.

    A definition question stays on the retrieved sentence. ``forced`` records
    that the caller turned the check on.
    """
    from cpu_llm.finance.triggers import finance_trigger as _finance_trigger

    return _finance_trigger(message, forced=forced)


def math_trigger(message: str, *, forced: bool = False) -> list[str]:
    """Reasons to evaluate arithmetic instead of only retrieving a sentence.

    A plain question, including one that merely contains a year or a measurement,
    stays off this path. ``forced`` records that the caller turned the step on.
    """
    reasons: list[str] = []
    if forced:
        reasons.append(MATH_CALLER_REASON)
    reasons.extend(_matched(message, _MATH_REASONS))
    return reasons


def _matched(message: str, table: tuple[tuple[re.Pattern[str], str], ...]) -> list[str]:
    reasons: list[str] = []
    for pattern, reason in table:
        if reason in reasons:
            continue
        if pattern.search(message or ""):
            reasons.append(reason)
    return reasons
