"""Speak an answer from the passages this turn already retrieved.

Event-frame questions stay with semantic memory. A question about a rule,
a measurement, or a cause is answered from those passages: the regex reader
first, then the trained extractor and writer when the regex finds no rule.
Neither path stores a new proposition. A question the passages do not cover
returns nothing, and the caller keeps the retrieved sentence.
"""

from __future__ import annotations

import re
from typing import Any, Optional

_DECISION = re.compile(
    r"^(?:why|can|could|may|might|should|must)\b"
    r"|\b(?:allowed|required|forbidden|prohibited|permit(?:ted)?)\b",
    re.I,
)
_RULE_CUE = re.compile(
    r"\b(?:allowed|required|forbidden|prohibited|because|permit(?:ted)?|must|may not|shall)\b",
    re.I,
)


def situation_from_chunks(
    question: str,
    chunks: list[str],
    *,
    extractor=None,
    retrieve=None,
) -> Optional[dict[str, Any]]:
    """YES, NO, CONTESTED, UNKNOWN, or CAUSE grounded in ``chunks``. None when no rule applies."""
    texts = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
    if not texts or not question.strip():
        return None
    from fact_bridge import answer, model_root

    result = answer(question, texts, extractor=extractor, retrieve=retrieve)
    if (
        result.verdict == "NONE"
        and extractor is None
        and _DECISION.search(question)
        and _RULE_CUE.search("\n".join(texts))
        and model_root() is not None
    ):
        result = answer(question, texts, retrieve=retrieve, ml=True)
    if result.verdict == "NONE":
        return None
    return {
        "verdict": result.verdict,
        "text": result.text,
        "because": list(result.because),
        "wording": dict(result.wording or {}),
    }


def retrieved_chunks(state: dict[str, Any]) -> list[str]:
    """Passage text already on the turn, in retrieval order, without duplicates."""
    texts: list[str] = []
    seen: set[str] = set()
    for row in list(state.get("passages") or []) + list(state.get("related") or []):
        text = str(row.get("chunk_text") or "").strip()
        if text and text not in seen:
            seen.add(text)
            texts.append(text)
    return texts
