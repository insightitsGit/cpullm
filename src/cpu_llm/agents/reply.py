"""Turn the finished retrieval into a short reply.

The preface, the follow-ups, and the next steps are filled from this turn:
the passages that were retrieved, the measurements named in them, and the
questions PrismThinker left open. A follow-up that is not in those passages
is not produced. The checked sentence, when one exists, stays the body.
The six channel readings, when the detail node wrote them, are appended
after that sentence. This node does not write a new conclusion.
"""

from __future__ import annotations

import re
from typing import Any

_STOP = frozenset(
    """
    a an the of to and or in on for with from by as is are was were be been being
    this that these those it its their his her they them you your we our not no nor
    but if then than into over after before about above below such only also just
    when where what which who whom how why can may known other during between across
    per via using used have has had does did done into than each both some any
    there here most more less very much many few
    """.split()
)

_OPEN = {
    "no numeric observations": "The retrieved passages do not state a measurement.",
    "no numeric threshold on hypothesis or objective": "There is no target to compare the stated measurements against.",
    "causal_graph is required": "No cause is stated in the retrieved passages.",
    "no PolicyRule objects provided": "No policy rule was provided.",
    "ObjectiveSpec is required": "No objective was provided.",
    "missing treatment/outcome binding": "The causal graph has no treatment or outcome binding.",
}


def compose_reply(state: dict[str, Any]) -> dict[str, Any]:
    preface = _preface(state)
    body = _body(state)
    closing = _closing(state)
    follow_ups = _follow_ups(state, body)
    next_steps = _next_steps(state)
    lines = [preface, "", body]
    if closing:
        lines.extend(["", closing])
    if follow_ups:
        lines.extend(["", "You could follow up on:"])
        lines.extend(f"- {item}" for item in follow_ups)
    if next_steps:
        lines.extend(["", "What would make the next step checkable:"])
        lines.extend(f"{index}. {item}" for index, item in enumerate(next_steps, start=1))
    report = state.get("channel_report") or {}
    if report.get("text"):
        lines.extend(["", str(report["text"])])
    imagined = str((state.get("imagination") or {}).get("text") or "").strip()
    if imagined:
        lines.extend(["", "Imagined passage:", imagined])
    return {
        "preface": preface,
        "body": body,
        "closing": closing,
        "follow_ups": follow_ups,
        "next_steps": next_steps,
        "discovery_suggested": bool(report.get("discovery_suggested")),
        "text": "\n".join(lines).strip(),
    }


def _preface(state: dict[str, Any]) -> str:
    message = (state.get("message") or "").strip()
    if state.get("guard_decision") not in (None, "allow"):
        return f"I stopped on “{message}” before looking anything up."
    related = list(state.get("related") or [])
    if not related:
        return f"I looked for “{message}” and the index returned no passage."
    count = len(related)
    label = _category(related)
    where = f" labeled {label}" if label else ""
    noun = "passage" if count == 1 else "passages"
    score = related[0].get("score")
    closest = f" The closest match scores {float(score):.2f}." if isinstance(score, (int, float)) else ""
    if state.get("shine_enforced"):
        return f"I found {count} {noun}{where}.{closest} The grounding check replaced the sentence."
    if state.get("answer") and not state.get("abstention_triggered"):
        return (
            f"I found {count} {noun}{where}.{closest} "
            "The sentence below is the one checked against a stored proposition."
        )
    if state.get("cognition_status") == "needs_evidence_propositions":
        return (
            f"I found {count} {noun}{where}.{closest} "
            "I am quoting the closest passage, because none of them was stored as a proposition."
        )
    if state.get("abstention_triggered"):
        return f"I looked for “{message}” and there was not enough evidence to state one."
    return f"I found {count} {noun}{where}.{closest}"


def _body(state: dict[str, Any]) -> str:
    if state.get("guard_decision") not in (None, "allow"):
        return state.get("answer") or "The prompt was blocked by PrismGuard."
    answer = state.get("answer")
    if isinstance(answer, str) and answer.strip():
        return answer.strip()
    related = list(state.get("related") or [])
    if not related:
        return "No passage was retrieved."
    return _quote(related[0])


def _quote(item: dict[str, Any]) -> str:
    text = (item.get("chunk_text") or "").strip()
    label = item.get("chunk_id") or item.get("document_id") or "passage"
    category = item.get("category")
    where = f"{label}, {category}" if category else str(label)
    return f"From {where}:\n{text}"


def _closing(state: dict[str, Any]) -> str:
    parts: list[str] = []
    directive = state.get("payment_directive")
    if directive:
        parts.append(f"The payment check returned {directive}.")
    open_items = [_open_phrase(str(item)) for item in state.get("gather_questions") or []]
    if open_items:
        parts.append("Still open: " + " ".join(open_items))
    return " ".join(parts)


def _open_phrase(question: str) -> str:
    prose = _OPEN.get(question)
    if prose is not None:
        return prose
    text = question.strip()
    if not text:
        return ""
    if text[-1] not in ".?":
        text += "."
    return text[0].upper() + text[1:]


def _follow_ups(state: dict[str, Any], body: str, limit: int = 3) -> list[str]:
    question_words = _words(state.get("message") or "")
    suggestions: list[str] = []
    used: set[str] = set()
    quoted_focus = False
    for item in list(state.get("related") or []):
        text = item.get("chunk_text") or ""
        for sentence in _sentences(text):
            focus = _focus(sentence, question_words, used)
            if focus is None:
                continue
            in_quote = sentence.casefold() in body.casefold() or focus.casefold() in body.casefold()
            if in_quote:
                if quoted_focus:
                    continue
                suggestions.append(f"Within the quoted passage, {focus} is something you can ask about next.")
                quoted_focus = True
            else:
                suggestions.append(f"Another passage mentions {focus}: “{_trim(sentence)}”")
            used.add(focus.casefold())
            if len(suggestions) >= limit:
                return suggestions
    return suggestions


def _next_steps(state: dict[str, Any]) -> list[str]:
    questions = [str(item) for item in state.get("gather_questions") or []]
    phrases = _claim_phrases(state)
    steps: list[str] = []
    for question in questions:
        if question == "no numeric threshold on hypothesis or objective" and phrases:
            steps.append(
                "Name a target for one of the measurements these passages state: " + "; ".join(phrases) + "."
            )
        elif question == "no numeric observations":
            steps.append("A checkable measurement has to be written in a retrieved passage.")
        elif question == "causal_graph is required":
            steps.append("A causal step needs a source that states one event because of another.")
        elif question == "no PolicyRule objects provided":
            steps.append("Supply a policy rule if this turn should be allowed or refused.")
        elif question == "ObjectiveSpec is required":
            steps.append("Supply an objective if a measurement should be scored against a target.")
        elif question == "missing treatment/outcome binding":
            steps.append("Name the treatment and the outcome on the causal graph.")
        else:
            phrase = _open_phrase(question)
            if phrase:
                steps.append(phrase)
    return steps[:4]


def _claim_phrases(state: dict[str, Any], limit: int = 6) -> list[str]:
    claims = state.get("numeric_claims") or {}
    qualifiers = state.get("numeric_qualifiers") or {}
    order = [item.get("chunk_id") for item in state.get("related") or []]
    seen: list[str] = [chunk_id for chunk_id in order if chunk_id in claims]
    seen.extend(chunk_id for chunk_id in claims if chunk_id not in seen)
    phrases: list[str] = []
    for chunk_id in seen:
        chunk_qualifiers = qualifiers.get(chunk_id) or {}
        for key, value in claims[chunk_id].items():
            record = chunk_qualifiers.get(key) or {}
            phrases.append(_claim_phrase(str(key), value, record.get("qualifier"), record.get("bound")))
            if len(phrases) >= limit:
                return phrases
    return phrases


def _claim_phrase(key: str, value: Any, qualifier: str | None, bound: str | None) -> str:
    base = re.sub(r"_\d+$", "", key)
    end = None
    if base.endswith("_min"):
        end = "low end"
        base = base[: -len("_min")]
    elif base.endswith("_max"):
        end = "high end"
        base = base[: -len("_max")]
    name, _, unit = base.rpartition("_")
    if not name:
        name, unit = unit, ""
    number = int(value) if isinstance(value, (int, float)) and float(value).is_integer() else value
    label = f"{name.replace('_', ' ')} {number}"
    if unit:
        label = f"{label} {unit}"
    notes = [note for note in (qualifier, end if bound in {"low", "high"} else None) if note]
    if notes:
        label = f"{label} ({', '.join(notes)})"
    return label


def _focus(sentence: str, question_words: set[str], used: set[str]) -> str | None:
    words = [token for token in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", sentence) if token.casefold() not in _STOP]
    for match in re.finditer(r"\b([A-Z][A-Za-z'-]{3,})\s+([A-Z][A-Za-z'-]{3,})\b", sentence):
        left, right = match.group(1), match.group(2)
        if left.casefold() in _STOP or right.casefold() in _STOP:
            continue
        if left.casefold() in question_words or right.casefold() in question_words:
            continue
        pair = f"{left} {right}"
        if pair.casefold() in used:
            continue
        return pair
    chosen: str | None = None
    for token in words:
        key = token.casefold()
        if key in question_words or key in used or len(token) < 5 or key.endswith("ly"):
            continue
        if chosen is None or len(token) > len(chosen):
            chosen = token
    return chosen


def _words(text: str) -> set[str]:
    return {token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text) if token.casefold() not in _STOP}


def _sentences(text: str) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    parts: list[str] = []
    for part in raw:
        if parts and re.search(r"\b[A-Z]\.$", parts[-1]):
            parts[-1] = f"{parts[-1]} {part}"
        else:
            parts.append(part)
    return [part.strip() for part in parts if part.strip()]


def _trim(text: str, limit: int = 180) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def _category(related: list[dict[str, Any]]) -> str | None:
    for item in related:
        category = item.get("category")
        if category:
            return str(category)
    return None
