"""Rewrite a question word only when a stored chunk word is the nearest spelling.

The retrieval encoder's cosine finds a neighbor in meaning. A misspelling is a
neighbor in spelling, so each word is a vector of character pairs and triples,
and the score is the cosine of those vectors. The candidates are the content
words already stored from chunks. A word that is already stored is left as
written. A word is rewritten only when the nearest stored word is one edit
away, including one transposition, the cosine clears the floor measured below,
and the next candidate is at least ``TYPO_MARGIN`` farther.

Measured on these pairs before the floor was set to 0.45:

* lobstor / lobster 0.667, recieve / receive 0.533, shipmnet / shipment 0.588
* flihgt / flight 0.462, which still clears the floor
* form / from 0.222 and toyko / tokyo 0.364, which stay uncorrected
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from cpu_llm.channels import _STOP

TYPO_MIN_COSINE = 0.45
TYPO_MARGIN = 0.05
_TOKEN = re.compile(r"[A-Za-z]{4,}")
_cache_key: tuple[str, int, int] | None = None
_cache_grams: dict[str, Counter[str]] = {}
_cache_lengths: dict[int, list[str]] = {}


def correct_message(
    message: str,
    word_index: dict[str, Any] | None,
    *,
    tenant_id: str = "cpu-llm",
) -> tuple[str, list[dict[str, str]]]:
    """Return the rewritten question and each replacement ``{"from", "to"}``.

    ``tenant_id`` selects the cache. One tenant's vocabulary is not reused for
    another tenant in the same process.
    """
    text = message or ""
    grams, lengths = _vocabulary(word_index, tenant_id)
    if not grams:
        return text, []
    parts: list[str] = []
    changes: list[dict[str, str]] = []
    cursor = 0
    for match in _TOKEN.finditer(text):
        token = match.group(0)
        parts.append(text[cursor : match.start()])
        cursor = match.end()
        folded = token.casefold()
        if folded in grams or folded in _STOP:
            parts.append(token)
            continue
        chosen = _nearest(folded, grams, lengths)
        if chosen is None:
            parts.append(token)
            continue
        written = _match_case(token, chosen)
        parts.append(written)
        changes.append({"from": token, "to": written})
    parts.append(text[cursor:])
    return "".join(parts), changes


def _vocabulary(
    word_index: dict[str, Any] | None,
    tenant_id: str = "cpu-llm",
) -> tuple[dict[str, Counter[str]], dict[int, list[str]]]:
    global _cache_key, _cache_grams, _cache_lengths
    if not word_index:
        return {}, {}
    key = (tenant_id, id(word_index), len(word_index))
    if key == _cache_key:
        return _cache_grams, _cache_lengths
    grams: dict[str, Counter[str]] = {}
    lengths: dict[int, list[str]] = {}
    for word in word_index:
        if not isinstance(word, str) or not word.isalpha() or len(word) < 4:
            continue
        folded = word.casefold()
        if folded in grams or folded in _STOP:
            continue
        grams[folded] = _grams(folded)
        lengths.setdefault(len(folded), []).append(folded)
    _cache_key = key
    _cache_grams = grams
    _cache_lengths = lengths
    return grams, lengths


def _nearest(
    token: str,
    grams: dict[str, Counter[str]],
    lengths: dict[int, list[str]],
) -> str | None:
    query = _grams(token)
    scored: list[tuple[float, str]] = []
    for length in (len(token) - 1, len(token), len(token) + 1):
        if length < 4:
            continue
        for word in lengths.get(length, ()):
            if _damerau(token, word) != 1:
                continue
            scored.append((_cosine(query, grams[word]), word))
    if not scored:
        return None
    scored.sort(reverse=True)
    best, word = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    if best < TYPO_MIN_COSINE or best - second < TYPO_MARGIN:
        return None
    return word


def _grams(word: str) -> Counter[str]:
    padded = f"#{word}#"
    counts: Counter[str] = Counter()
    for size in (2, 3):
        for index in range(len(padded) - size + 1):
            counts[f"{size}:{padded[index : index + size]}"] += 1
    return counts


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    dot = sum(value * right.get(gram, 0) for gram, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _damerau(left: str, right: str) -> int:
    rows = len(left) + 1
    cols = len(right) + 1
    table = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        table[i][0] = i
    for j in range(cols):
        table[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if left[i - 1] == right[j - 1] else 1
            table[i][j] = min(table[i - 1][j] + 1, table[i][j - 1] + 1, table[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and left[i - 1] == right[j - 2] and left[i - 2] == right[j - 1]:
                table[i][j] = min(table[i][j], table[i - 2][j - 2] + 1)
    return table[-1][-1]


def _match_case(token: str, word: str) -> str:
    if token.isupper():
        return word.upper()
    if token[:1].isupper():
        return word[:1].upper() + word[1:]
    return word
