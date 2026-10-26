"""Say whether the retrieved passages state the ranking the question asks for.

A retrieval score is not a ranking. A sentence counts only when the stored
text itself names an order, and when it shares a topic word with the question.
"""

from __future__ import annotations

import re
from typing import Any

_ASK = re.compile(
    r"\b(?:best|worst|better|worse|highest|lowest|finest|greatest|"
    r"superior|inferior|rank(?:s|ed|ing)?|outranks?|outranked)\b",
    re.IGNORECASE,
)
_STATED = re.compile(
    r"\b(?:best|worst|better|worse|highest|lowest|finest|greatest|"
    r"superior|inferior|rank(?:s|ed|ing)?|outranks?|outranked|number one|no\. 1)\b",
    re.IGNORECASE,
)
_ABBREVIATION = re.compile(
    r"\b(?:No|Mr|Mrs|Ms|Dr|St|Jr|Sr|vs|etc|Fig|Prof|Gen|Col|Capt|Lt|Sgt|Mt)\.$|\b[A-Z]\.$"
)
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{3,}")
_TOPIC_SKIP = frozenset(
    """
    best worst better worse highest lowest finest greatest superior inferior
    rank ranks ranked ranking outrank outranks outranked
    what which who how why when where this that these those with from into
    about there here most more less very much many
    """.split()
)
_ABSENT = "The retrieved passages do not state a ranking. The sentence above is what they do state."
_NONE = "No passage was retrieved, so no ranking is stored for this question."
_ALREADY = "The sentence above states the stored ranking."


def ranking_question(message: str) -> bool:
    """True when the prompt asks for an order, such as best, worst, or ranked."""
    return bool(_ASK.search(message or ""))


def ranking_notice(message: str, chunks: list[str], *, spoken: str = "") -> dict[str, Any] | None:
    """The stored ranking, or an explicit statement that none was retrieved.

    ``None`` means the prompt is not a ranking question. A sentence from
    another topic is left out, even when that sentence names something as best.
    """
    if not ranking_question(message):
        return None
    texts = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
    topic = _topic_words(message)
    stated: list[str] = []
    for text in texts:
        for sentence in _sentences(text):
            if _STATED.search(sentence) is None:
                continue
            if topic and not _overlaps(topic, sentence):
                continue
            if sentence not in stated:
                stated.append(sentence)
    if stated:
        reflected = _already_spoken(spoken, stated)
        return {
            "status": "stated",
            "sentences": stated,
            "text": _ALREADY if reflected else " ".join(stated),
        }
    return {
        "status": "absent",
        "sentences": [],
        "text": _NONE if not texts else _ABSENT,
    }


def plural_stem(word: str) -> str:
    """One stem for a singular and its plural.

    ``ferries`` and ``ferry`` meet. Stripping every trailing ``s`` turns
    ``ferries`` into ``ferrie``, which does not.
    """
    token = word.casefold()
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("es") and token[-3] in "sxz":
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _topic_words(message: str) -> set[str]:
    return {
        plural_stem(token)
        for token in _WORD.findall(message or "")
        if token.casefold() not in _TOPIC_SKIP
    }


def _overlaps(topic: set[str], sentence: str) -> bool:
    words = {plural_stem(token) for token in _WORD.findall(sentence)}
    return bool(topic & words)


def _already_spoken(spoken: str, sentences: list[str]) -> bool:
    folded = (spoken or "").casefold()
    return all(sentence.casefold() in folded for sentence in sentences)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences: list[str] = []
    buffer = ""
    for part in parts:
        buffer = f"{buffer} {part}".strip() if buffer else part
        if _ABBREVIATION.search(buffer) is None:
            sentences.append(buffer)
            buffer = ""
    if buffer:
        sentences.append(buffer)
    return sentences
