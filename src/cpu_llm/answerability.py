"""Bind a question to sentences that state the relation it asks for.

Retrieval can return a neighbor, and a later audit can confirm that a
sentence matches its stored proposition. Neither of those establishes that
the sentence answers the question. This module handles a declared set of
question shapes. A ranking question, a sum, a rule, and an event-frame
question stay with their own producers.

Nothing here is filled in from outside the sentences the caller supplies.
"""

from __future__ import annotations

import re
from typing import Any

from cpu_llm.ranking import ranking_question

_UNSETTLED = "The retrieved passages do not settle that."
_NONE = "No passage was retrieved."
_WHAT = re.compile(
    r"^(?P<kind>what|who)\s+(?P<copula>is|are|was|were)\s+(?P<rest>.+?)\s*\??$",
    re.IGNORECASE,
)
_WHICH = re.compile(
    r"^which\s+(?P<head>[a-z][a-z ]{0,40}?)\s+is\s+the\s+(?P<attr>[a-z][a-z ]{0,40}?)\s+of\s+(?P<entity>.+?)\s*\??$",
    re.IGNORECASE,
)
_ATTR_OF = re.compile(
    r"^(?:(?P<head>[a-z][a-z ]{0,40}?)\s+is\s+)?the\s+(?P<attr>[a-z][a-z ]{0,40}?)\s+of\s+(?P<entity>.+)$",
    re.IGNORECASE,
)
_ATTR_POSS = re.compile(
    r"^(?P<entity>.+?)'s\s+(?P<attr>[a-z][a-z ]{0,40})$",
    re.IGNORECASE,
)
_SOURCES = re.compile(
    r"^(?:cite\s+)?sources?\s+for\s+(?P<rest>.+?)\s*\??$",
    re.IGNORECASE,
)
_NEGATED = re.compile(r"\b(?:not|never|no|n't)\b", re.IGNORECASE)
_CONDITIONAL = re.compile(r"\bif\b", re.IGNORECASE)
_DETERMINER = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)
_ABBREVIATION = re.compile(
    r"\b(?:No|Mr|Mrs|Ms|Dr|St|Jr|Sr|vs|etc|Fig|Prof|Gen|Col|Capt|Lt|Sgt|Mt)\.$|\b[A-Z]\.$"
)


def parse_query(message: str) -> dict[str, str] | None:
    """The supported shape of ``message``, or None when this module does not own it."""
    if ranking_question(message):
        return None
    text = " ".join((message or "").strip().split())
    if not text:
        return None
    sources = _SOURCES.match(text)
    if sources:
        subject = _subject_phrase(sources.group("rest"))
        if not subject:
            return None
        return {"kind": "sources", "subject": subject, "raw": text}
    which = _WHICH.match(text)
    if which:
        return {
            "kind": "attribute",
            "attribute": _phrase(which.group("attr")),
            "entity": _phrase(which.group("entity")),
            "tense": "present",
            "raw": text,
        }
    matched = _WHAT.match(text)
    if matched is None:
        return None
    rest = _phrase(matched.group("rest"))
    tense = "past" if matched.group("copula").casefold() in {"was", "were"} else "present"
    if not re.search(r"[A-Za-z]", rest):
        return None
    possessive = _ATTR_POSS.match(rest)
    if possessive:
        return {
            "kind": "attribute",
            "attribute": _phrase(possessive.group("attr")),
            "entity": _phrase(possessive.group("entity")),
            "tense": tense,
            "raw": text,
        }
    attribute = _ATTR_OF.match(rest)
    if attribute:
        return {
            "kind": "attribute",
            "attribute": _phrase(attribute.group("attr")),
            "entity": _phrase(attribute.group("entity")),
            "tense": tense,
            "raw": text,
        }
    return {"kind": "definition", "subject": _subject_phrase(rest), "tense": tense, "raw": text}


def assess(message: str, chunks: list[Any]) -> dict[str, Any] | None:
    """Whether the supplied sentences state the asked relation.

    ``None`` means the question is outside this contract. ``answered`` means
    the sentences state one value. It does not mean a later audit ran, and it
    does not mean the source is true.
    """
    plan = parse_query(message)
    if plan is None:
        return None
    rows = [_row(chunk, index) for index, chunk in enumerate(chunks)]
    rows = [row for row in rows if row["text"]]
    retrieved = [{"document_id": row["document_id"], "span": row["text"]} for row in rows]
    base = {
        "query": plan["raw"],
        "kind": plan["kind"],
        "retrieved_candidates": retrieved,
        "answer_evidence": [],
        "verification_scope": "query",
    }
    if not rows:
        return {
            **base,
            "answer_status": "insufficient_evidence",
            "reason": "none_retrieved",
            "text": _NONE,
        }
    if plan["kind"] == "attribute":
        return {**base, **_attribute_decision(plan, rows)}
    bindings = _subject_bindings(plan, rows)
    if not bindings:
        return {
            **base,
            "answer_status": "insufficient_evidence",
            "reason": "no_binding",
            "text": _UNSETTLED,
        }
    sentences = _unique([item["span"] for item in bindings])
    return {
        **base,
        "answer_status": "answered",
        "reason": "subject_stated",
        "text": " ".join(sentences),
        "answer_evidence": bindings,
    }


def eligible_hits(message: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Hits that state the asked relation.

    ``None`` leaves the caller on its previous selection. An empty list means
    this question was recognized and none of the hits state it.
    """
    plan = parse_query(message)
    if plan is None:
        return None
    kept: list[dict[str, Any]] = []
    for hit in hits:
        text = str(hit.get("chunk_text") or hit.get("text") or "")
        if _text_binds(plan, text):
            kept.append(hit)
    return kept


def supporting_ids(message: str, hits: list[dict[str, Any]]) -> list[str] | None:
    """Document ids that state the asked subject or relation, in retrieval order.

    ``None`` means this module does not own the question. An empty list means
    it does, and none of the hits support it.
    """
    chosen = eligible_hits(message, hits)
    if chosen is None:
        return None
    ids: list[str] = []
    for hit in chosen:
        document_id = str(hit.get("document_id") or hit.get("chunk_id") or "")
        if document_id and document_id not in ids:
            ids.append(document_id)
    return ids


def supported_answer(message: str, answer: str) -> str | None:
    """The part of an audited answer that stays on the asked subject.

    A pronoun sentence stays only while the previous kept sentence is still
    about that subject. A sentence about something else is left out.
    """
    plan = parse_query(message)
    if plan is None:
        return None
    kept: list[str] = []
    armed = False
    for sentence in _sentences(answer or ""):
        if _text_binds(plan, sentence):
            kept.append(sentence)
            armed = True
            continue
        if armed and re.match(r"^(?:it|they|he|she|this|that)\b", sentence, re.IGNORECASE):
            kept.append(sentence)
            continue
        armed = False
    if not kept:
        return None
    return " ".join(kept)


def _attribute_decision(plan: dict[str, str], rows: list[dict[str, str]]) -> dict[str, Any]:
    found: list[dict[str, str]] = []
    for row in rows:
        for sentence in _sentences(row["text"]):
            value = _attribute_value(plan, sentence)
            if value is None:
                continue
            found.append({"document_id": row["document_id"], "span": sentence, "value": value})
    if not found:
        return {
            "answer_status": "insufficient_evidence",
            "reason": "no_binding",
            "text": _UNSETTLED,
        }
    by_value: dict[str, list[dict[str, str]]] = {}
    for item in found:
        by_value.setdefault(item["value"].casefold(), []).append(item)
    if len(by_value) > 1:
        spans = _unique([item["span"] for item in found])
        spans = sorted(spans, key=str.casefold)
        quoted = " ".join(f'"{span}"' for span in spans)
        return {
            "answer_status": "conflicting",
            "reason": "distinct_values",
            "text": f"{_UNSETTLED} Stored sentences conflict: {quoted}",
            "answer_evidence": [
                {"document_id": item["document_id"], "span": item["span"]}
                for item in sorted(found, key=lambda item: item["span"].casefold())
            ],
        }
    evidence = [{"document_id": item["document_id"], "span": item["span"]} for item in found]
    return {
        "answer_status": "answered",
        "reason": "relation_stated",
        "text": found[0]["span"],
        "answer_evidence": evidence,
    }


def _subject_bindings(plan: dict[str, str], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    subject = plan.get("subject") or ""
    bindings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        for sentence in _sentences(row["text"]):
            if not _subject_sentence(subject, sentence):
                continue
            key = (row["document_id"], sentence)
            if key in seen:
                continue
            seen.add(key)
            bindings.append({"document_id": row["document_id"], "span": sentence})
    return bindings


def _text_binds(plan: dict[str, str], text: str) -> bool:
    if plan["kind"] == "attribute":
        return any(_attribute_value(plan, sentence) is not None for sentence in _sentences(text))
    subject = plan.get("subject") or ""
    return any(_subject_sentence(subject, sentence) for sentence in _sentences(text))


def _attribute_value(plan: dict[str, str], sentence: str) -> str | None:
    if _NEGATED.search(sentence) or _CONDITIONAL.search(sentence):
        return None
    attribute = re.escape(plan["attribute"].casefold())
    entity = re.escape(plan["entity"].casefold())
    copula = "was" if plan.get("tense") == "past" else "is"
    folded = " ".join(sentence.split())
    patterns = (
        rf"\bthe {attribute} of {entity} {copula} (?P<value>[^.?!]+)",
        rf"\b{entity}'s {attribute} {copula} (?P<value>[^.?!]+)",
        rf"^(?P<value>.+?) {copula} the {attribute} of {entity}[.?!]?$",
    )
    for pattern in patterns:
        matched = re.search(pattern, folded, re.IGNORECASE)
        if matched is None:
            continue
        value = matched.group("value").strip(" .")
        if value:
            return value
    return None


def _subject_sentence(subject: str, sentence: str) -> bool:
    phrase = _subject_phrase(subject)
    if not phrase or _NEGATED.search(sentence) or _CONDITIONAL.search(sentence):
        return False
    if not _complete_phrase(sentence, phrase):
        return False
    folded = sentence.casefold()
    known = re.search(r"\bknown as\b", folded)
    if known and _complete_phrase(sentence[known.start() :], phrase):
        return True
    return re.match(rf"^(?:(?:the|a|an)\s+)?{re.escape(phrase)}\b", folded) is not None


def _complete_phrase(text: str, phrase: str) -> bool:
    matched = re.search(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE)
    if matched is None:
        return False
    nxt = re.match(r"\s+([A-Za-z][A-Za-z'-]*)", text[matched.end() :])
    return not (nxt is not None and nxt.group(1)[:1].isupper())


def _row(chunk: Any, index: int) -> dict[str, str]:
    if isinstance(chunk, str):
        return {"document_id": f"chunk-{index}", "text": chunk.strip()}
    text = str(chunk.get("text") or chunk.get("chunk_text") or "").strip()
    document_id = str(chunk.get("document_id") or chunk.get("chunk_id") or f"chunk-{index}")
    return {"document_id": document_id, "text": text}


def _phrase(text: str) -> str:
    return " ".join((text or "").strip().strip(" ?.!").split())


def _subject_phrase(text: str) -> str:
    return _DETERMINER.sub("", _phrase(text)).strip()


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


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
    return [sentence for sentence in sentences if sentence]
