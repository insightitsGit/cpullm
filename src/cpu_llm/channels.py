"""Six readings of one retrieved shortlist.

Dense cosine is the trained rank. The other five heads are read with the
method that belongs to that channel: a stored proposition, a word that only
one passage uses, Poincaré distance inside the unit ball, a name written in
both the prompt and a passage, and a sentence that states a cause.

A disabled head is not ranked by its slice. An identity anchor that is still
zero is not a domain score. Nothing in this module writes a sentence that
was not already in a retrieved passage.
"""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
from vectorprism.tensor_contract import PSMTensorContract

from cpu_llm.geometry.poincare import poincare_distance

_STOP = frozenset(
    """
    a an the of to and or in on for with from by as is are was were be been being
    this that these those it its their his her they them you your we our not no nor
    but if then than into over after before about above below such only also just
    when where what which who whom how why can may known other during between across
    per via using used have has had does did done there here most more less very
    much many few
    """.split()
)
_CAUSE = re.compile(r"\b(?:because|due to|caused|therefore)\b", re.IGNORECASE)
_WHY = re.compile(r"\b(?:why|how)\b", re.IGNORECASE)
_COMPARE = re.compile(r"\b(?:compare|comparison|difference|different|versus|vs)\b", re.IGNORECASE)
_CAUSE_ASK = re.compile(r"\b(?:cause|effect|because)\b", re.IGNORECASE)
_NAME = re.compile(r"\b[A-Z][A-Za-z'-]{3,}\b")

_SPECS: dict[str, tuple[str, str]] = {
    "dense": ("cosine", "Dense semantic core"),
    "relational": ("stored proposition", "Relational group"),
    "disentangled": ("words unique to one passage", "Disentangled terms"),
    "hyperbolic": ("poincare distance", "Hyperbolic taxonomy"),
    "identity": ("shared names", "Identity anchor"),
    "causal": ("stated cause", "Causal time"),
}


def read_channel(
    name: str,
    message: str,
    passages: list[dict[str, Any]],
    *,
    query_tensor: np.ndarray | None = None,
    propositions: dict[str, Any] | None = None,
    enabled: bool = False,
    anchor_set: bool = False,
    anchor: np.ndarray | None = None,
) -> dict[str, Any]:
    method, title = _SPECS[name]
    if name == "dense":
        return _dense(message, passages, query_tensor, enabled, method, title)
    if name == "relational":
        return _relational(message, passages, propositions or {}, enabled, method, title)
    if name == "disentangled":
        return _disentangled(passages, enabled, method, title)
    if name == "hyperbolic":
        return _hyperbolic(passages, query_tensor, enabled, method, title)
    if name == "identity":
        return _identity(message, passages, enabled, anchor_set, anchor, method, title)
    if name == "causal":
        return _causal(message, passages, enabled, method, title)
    raise KeyError(name)


def judge_readings(
    message: str,
    readings: list[dict[str, Any]],
    categories: list[str],
) -> dict[str, Any]:
    reasons = complexity_reasons(message, categories)
    lines = ["Six readings of the retrieved passages:"]
    for reading in readings:
        lines.append(f"{reading['title']}. {reading['note']} {reading['detail']}")
    lines.append(
        "The checked sentence stays the one realized from stored propositions. "
        "These readings do not replace it and do not add a sentence that was not written in a retrieved passage."
    )
    if reasons:
        joined = "; ".join(reasons)
        lines.append(
            f"This topic looks complicated: {joined}. "
            "The discovery loop can record the claim, the assumptions, and what is still unknown. "
            "It stays off until you ask for it."
        )
    return {
        "readings": readings,
        "discovery_suggested": bool(reasons),
        "discovery_reasons": reasons,
        "text": "\n".join(lines),
    }


def complexity_reasons(message: str, categories: list[str]) -> list[str]:
    reasons: list[str] = []
    if _WHY.search(message):
        reasons.append("the prompt asks why or how")
    if _COMPARE.search(message):
        reasons.append("the prompt asks for a comparison")
    if _CAUSE_ASK.search(message):
        reasons.append("the prompt asks about a cause")
    if message.count("?") > 1:
        reasons.append("the prompt contains more than one question")
    distinct = {item for item in categories if item}
    if reasons and len(distinct) > 1:
        reasons.append("the passages come from more than one article")
    return reasons


def _dense(message, passages, query_tensor, enabled, method, title) -> dict[str, Any]:
    note = "Trained dense core, ranked by cosine." if enabled else "The dense channel is off in this checkpoint."
    if not passages:
        return _row("dense", method, title, enabled, True, None, None, note, "The index returned no passage.")
    if query_tensor is None:
        return _row("dense", method, title, enabled, True, None, None, note, "The query tensor was not available.")
    query = _slice(query_tensor, PSMTensorContract.DENSE_CORE)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for passage in passages:
        score = _cosine(query, _slice(passage["tensor"], PSMTensorContract.DENSE_CORE))
        if score is None:
            continue
        ranked.append((score, passage))
    if not ranked:
        return _row("dense", method, title, enabled, True, None, None, note, "The dense slices were empty.")
    ranked.sort(key=lambda item: (-item[0], item[1]["document_id"]))
    score, passage = ranked[0]
    sentence = _best_sentence(passage["chunk_text"], message)
    detail = f"The closest trained passage is {passage['document_id']}: “{sentence}”"
    return _row("dense", method, title, enabled, True, passage["document_id"], score, note, detail)


def _relational(message, passages, propositions, enabled, method, title) -> dict[str, Any]:
    note = (
        "Stored propositions are read from the graph."
        if enabled
        else "The relational head is off in this checkpoint, so its slice was not used as a rank. Stored propositions are read instead."
    )
    if not passages:
        return _row("relational", method, title, enabled, False, None, None, note, "The index returned no passage.")
    prompt_words = set(_content_words(message))
    best: tuple[int, str, str, str] | None = None
    for passage in passages:
        proposition = propositions.get(passage["document_id"])
        if proposition is None:
            continue
        subject = proposition.subject.raw_text
        target = proposition.object_target.raw_text if proposition.object_target is not None else ""
        if subject not in passage["chunk_text"] or (target and target not in passage["chunk_text"]):
            continue
        shared = prompt_words & set(_content_words(f"{subject} {target}"))
        if not shared:
            continue
        candidate = (len(shared), passage["document_id"], subject, target)
        if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and candidate[1] < best[1]):
            best = candidate
    if best is None:
        return _row(
            "relational",
            method,
            title,
            enabled,
            False,
            None,
            None,
            note,
            "No stored proposition shares a word with the prompt.",
        )
    _count, document_id, subject, target = best
    detail = f"A stored proposition in {document_id} names “{subject}” and “{target}”."
    return _row("relational", method, title, enabled, False, document_id, float(_count), note, detail)


def _disentangled(passages, enabled, method, title) -> dict[str, Any]:
    note = (
        "Words that occur in only one passage are listed."
        if enabled
        else "The disentangled head is off in this checkpoint, so its slice was not used as a rank. Words that occur in only one passage are listed instead."
    )
    if not passages:
        return _row("disentangled", method, title, enabled, False, None, None, note, "The index returned no passage.")
    bags = {passage["document_id"]: set(_content_words(passage["chunk_text"])) for passage in passages}
    exclusive: dict[str, list[str]] = {}
    for document_id, words in bags.items():
        others = set().union(*(bag for key, bag in bags.items() if key != document_id))
        exclusive[document_id] = sorted(words - others, key=len, reverse=True)
    ranked = sorted(exclusive.items(), key=lambda item: (-len(item[1]), item[0]))
    document_id, words = ranked[0]
    if not words:
        return _row(
            "disentangled",
            method,
            title,
            enabled,
            False,
            None,
            None,
            note,
            "The passages do not contain a word that the others lack.",
        )
    shown = words[:4]
    detail = f"Only {document_id} uses these words: {', '.join(shown)}."
    return _row("disentangled", method, title, enabled, False, document_id, float(len(words)), note, detail)


def _hyperbolic(passages, query_tensor, enabled, method, title) -> dict[str, Any]:
    note = (
        "Poincaré distance is defined only inside the open unit ball, and it is not a class name."
        if enabled
        else "The hyperbolic head is off in this checkpoint. Poincaré distance is still checked, and only inside the open unit ball."
    )
    if not passages or query_tensor is None:
        detail = "The index returned no passage." if not passages else "The query tensor was not available."
        return _row("hyperbolic", method, title, enabled, False, None, None, note, detail)
    query = _slice(query_tensor, PSMTensorContract.HYPERBOLIC)
    if float(np.linalg.norm(query)) >= 1.0:
        return _row(
            "hyperbolic",
            method,
            title,
            enabled,
            False,
            None,
            None,
            note,
            "The hyperbolic slices are outside the open unit ball, so no taxonomic distance was computed.",
        )
    ranked: list[tuple[float, str]] = []
    for passage in passages:
        point = _slice(passage["tensor"], PSMTensorContract.HYPERBOLIC)
        distance = poincare_distance(query, point)
        if math.isfinite(distance):
            ranked.append((distance, passage["document_id"]))
    if not ranked:
        return _row(
            "hyperbolic",
            method,
            title,
            enabled,
            False,
            None,
            None,
            note,
            "The hyperbolic slices are outside the open unit ball, so no taxonomic distance was computed.",
        )
    ranked.sort()
    distance, document_id = ranked[0]
    detail = (
        f"The closest hyperbolic point is {document_id}, at distance {distance:.3f}. "
        "No class name was read from that slice."
    )
    return _row("hyperbolic", method, title, enabled, False, document_id, distance, note, detail)


def _identity(message, passages, enabled, anchor_set, anchor, method, title) -> dict[str, Any]:
    if anchor_set and anchor is not None:
        note = "Distance to the identity anchor is a soft signal, not a fact about the passage."
    else:
        note = "The identity anchor is unset, so that distance was not used. Shared names are read from the text."
    if not enabled:
        note = "The identity channel is off in this checkpoint. " + note
    if not passages:
        return _row("identity", method, title, enabled, False, None, None, note, "The index returned no passage.")
    prompt_words = set(_content_words(message))
    best: tuple[int, str, list[str], float | None] | None = None
    for passage in passages:
        names = _shared_names(message, passage, prompt_words)
        distance = _anchor_distance(passage["tensor"], anchor) if anchor_set and anchor is not None else None
        candidate = (len(names), passage["document_id"], names, distance)
        if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and candidate[1] < best[1]):
            best = candidate
    assert best is not None
    count, document_id, names, distance = best
    if count == 0:
        return _row("identity", method, title, enabled, False, None, distance, note, "No name in the prompt is written in these passages.")
    detail = f"The prompt and {document_id} both name {', '.join(names)}."
    if distance is not None:
        detail = f"{detail} Anchor distance {distance:.3f}."
    return _row("identity", method, title, enabled, False, document_id, distance if distance is not None else float(count), note, detail)


def _causal(message, passages, enabled, method, title) -> dict[str, Any]:
    note = (
        "A sentence is quoted only when it states a cause."
        if enabled
        else "The causal head is off in this checkpoint, so the bilinear score was not used. A sentence is quoted only when it states a cause."
    )
    if not passages:
        return _row("causal", method, title, enabled, False, None, None, note, "The index returned no passage.")
    prompt_words = set(_content_words(message))
    found: list[tuple[int, str, str]] = []
    for passage in passages:
        for sentence in _sentences(passage["chunk_text"]):
            if _CAUSE.search(sentence) is None:
                continue
            if sentence not in passage["chunk_text"]:
                continue
            shared = len(prompt_words & set(_content_words(sentence)))
            found.append((shared, passage["document_id"], sentence))
    if not found:
        return _row("causal", method, title, enabled, False, None, None, note, "No retrieved passage states a cause.")
    found.sort(key=lambda item: (-item[0], item[1]))
    _shared, document_id, sentence = found[0]
    detail = f"{document_id} states: “{sentence}”"
    return _row("causal", method, title, enabled, False, document_id, float(_shared), note, detail)


def _shared_names(message: str, passage: dict[str, Any], prompt_words: set[str]) -> list[str]:
    text = passage["chunk_text"]
    folded = text.casefold()
    names: list[str] = []
    for match in _NAME.finditer(text):
        token = match.group(0)
        if token.casefold() in _STOP or token.casefold() not in prompt_words:
            continue
        if token not in names:
            names.append(token)
    slug = passage["document_id"].casefold().replace("_", "-")
    for part in re.split(r"[^a-z0-9]+", slug):
        if len(part) < 4 or part in _STOP or part not in prompt_words:
            continue
        if part not in folded:
            continue
        if part not in {name.casefold() for name in names}:
            names.append(part)
    return names


def _anchor_distance(tensor: np.ndarray, anchor: np.ndarray) -> float | None:
    point = _slice(tensor, PSMTensorContract.IDENTITY)
    target = np.asarray(anchor, dtype=np.float64).reshape(-1)
    if point.shape != target.shape:
        return None
    distance = float(np.linalg.norm(point - target))
    if not math.isfinite(distance):
        return None
    return distance


def _best_sentence(text: str, message: str) -> str:
    prompt_words = set(_content_words(message))
    choices = _sentences(text) or [text.strip()]
    best = choices[0]
    best_score = -1
    for sentence in choices:
        score = len(prompt_words & set(_content_words(sentence)))
        if score > best_score:
            best = sentence
            best_score = score
    return best


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    merged: list[str] = []
    for part in parts:
        if merged and re.search(r"\b[A-Z]\.$", merged[-1]):
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return [part.strip() for part in merged if part.strip()]


def _content_words(text: str) -> list[str]:
    return [
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text)
        if token.casefold() not in _STOP
    ]


def _slice(tensor: np.ndarray, region) -> np.ndarray:
    vector = np.asarray(tensor, dtype=np.float64).reshape(-1)
    return vector[region.start : region.end]


def _cosine(left: np.ndarray, right: np.ndarray) -> float | None:
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm == 0.0 or right_norm == 0.0 or not math.isfinite(left_norm) or not math.isfinite(right_norm):
        return None
    value = float(np.dot(left, right) / (left_norm * right_norm))
    if not math.isfinite(value):
        return None
    return value


def _row(channel, method, title, enabled, used_for_answer, document_id, score, note, detail) -> dict[str, Any]:
    return {
        "channel": channel,
        "method": method,
        "title": title,
        "enabled": enabled,
        "used_for_answer": used_for_answer,
        "document_id": document_id,
        "score": None if score is None else float(score),
        "note": note,
        "detail": detail,
    }
