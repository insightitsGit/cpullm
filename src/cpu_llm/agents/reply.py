"""Turn the finished retrieval into a short reply.

The spoken text is the checked sentence, then any imagined passage. The
preface, the open questions, the follow-ups, the next steps, and the six
channel readings stay on the reply for the caller. They are not written into
the spoken text. A follow-up that is not in the retrieved passages is not produced.
The checked sentence, when one exists, stays the body. This node does not
write a new conclusion. A question in the answerability contract is spoken
from sentences that state its relation, or the turn says the passages do not
settle it. A ranking question keeps that sentence and adds whether a retrieved
sentence states the order. A retrieval score is not a ranking. A request that
asks for a document follows a format from the output catalog, and that
document replaces the checked sentence.
"""

from __future__ import annotations

import re
from typing import Any

from cpu_llm.memory.frames import frame_reply_text

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
    assessment = _query_assessment(state)
    body = _body(state)
    closing = _closing(state)
    follow_ups = _follow_ups(state, body)
    next_steps = _next_steps(state)
    lines = [body]
    math_result = state.get("math_result") or {}
    math_text = str(math_result.get("text") or "").strip()
    finance_result = state.get("finance_result") or {}
    finance_text = str(finance_result.get("text") or "").strip()
    draft = _draft(state)
    math_only = (
        bool(math_text)
        and state.get("math") is True
        and draft is None
        and not finance_text
        and not _other_agent(state)
        and not _delivery_holds(state)
    )
    finance_only = (
        bool(finance_text)
        and state.get("finance") is True
        and draft is None
        and not math_text
        and not _other_agent(state)
        and not _delivery_holds(state)
    )
    frame_text = frame_reply_text(state)
    frame_only = (
        bool(frame_text)
        and draft is None
        and not _other_agent(state)
        and not math_text
        and not finance_text
    )
    situation = None if draft is not None else _situation(state, math_only=math_only, frame_only=frame_only)
    situation_owns = situation is not None and not _unchecked_gap(situation, state)
    if math_only:
        lines = [math_text]
    elif finance_only:
        lines = [finance_text]
    elif frame_only:
        lines = [frame_text]
    elif draft is not None:
        lines = [draft["text"]]
    elif situation_owns:
        lines = [situation["text"]]
    owned = math_only or finance_only or frame_only or draft is not None or situation_owns
    if owned:
        assessment = None
    elif assessment is not None and assessment.get("replaces_body"):
        lines = [assessment["text"]]
        body = assessment["text"]
        follow_ups = _follow_ups(state, body)
    elif assessment is None and not _brief_requested(state):
        spoken = _model01_sentence(state) or _scoped_quote(state)
        if spoken:
            lines = [spoken]
            body = spoken
    preface = _preface(state, assessment)
    ranking = None if lines and "Ranking:" in lines[0] else _ranking(state, lines[0] if lines else "")
    if ranking is not None:
        lines.extend(["", "Ranking:", ranking["text"]])
    brief = state.get("brief") or {}
    report = state.get("channel_report") or {}
    if draft is None:
        if state.get("summarize") is True:
            lines.extend(["", "Summary:", brief.get("summary") or "No stored sentence to summarize."])
        if state.get("explain") is True:
            lines.extend(["", "Explanation:", brief.get("explanation") or "No stored sentence states a cause."])
        if state.get("list") is True:
            lines.extend(["", "List:", brief.get("list") or "No stored sentence to list."])
        if state.get("sources") is True:
            source_ids = list(brief.get("sources") or [])
            if assessment is not None:
                source_ids = [item["document_id"] for item in assessment.get("answer_evidence") or []]
            lines.extend(["", "Sources:"])
            lines.extend(f"- {document_id}" for document_id in source_ids)
            if not source_ids:
                lines.append("No stored paragraph was used.")
        imagined = ""
        if not state.get("delivery_blocked"):
            imagined = str((state.get("imagination") or {}).get("text") or "").strip()
        covered = list((state.get("comparison") or {}).get("sides") or [])
        if covered:
            lines.extend(["", "Comparison:"])
            for side in covered:
                lines.append(f"{side.get('label')}:")
                lines.append(str(side.get("text") or "").strip() or "No stored sentence for this side.")
        if imagined:
            lines.extend(["", "Imagined passage:", imagined])
        possibilities = list(state.get("possibilities") or [])
        if possibilities:
            lines.extend(["", f"Possibilities ({len(possibilities)}):"])
            lines.extend(_possibility_lines(possibilities))
        if math_text and not math_only:
            lines.extend(["", "Math:", math_text])
        if finance_text and not finance_only:
            lines.extend(["", "Finance:", finance_text])
        if frame_text and not frame_only:
            lines.extend(["", "Event:", frame_text])
    reply = {
        "preface": preface,
        "body": body,
        "closing": closing,
        "follow_ups": follow_ups,
        "next_steps": next_steps,
        "discovery_suggested": bool(report.get("discovery_suggested")),
        "situation": situation,
        "draft": draft,
        "ranking": ranking,
        "text": "\n".join(lines).strip(),
    }
    if assessment is not None:
        reply["answer_status"] = assessment["answer_status"]
        reply["answer_evidence"] = list(assessment.get("answer_evidence") or [])
        reply["verification_scope"] = assessment.get("verification_scope")
        reply["retrieved_candidates"] = list(assessment.get("retrieved_candidates") or [])
        reply["producer"] = "answerability"
        reply["query"] = assessment.get("query")
        reply["original_query"] = assessment.get("original_query")
        if assessment.get("supported_text"):
            reply["supported_text"] = assessment["supported_text"]
    return reply


def _query_assessment(state: dict[str, Any]) -> dict[str, Any] | None:
    """Delivery status for a question this contract can bind.

    A blocked guard or an earlier Shine, audit, or grammar hold stays in
    place. Ranking questions stay with the ranking notice.
    """
    if state.get("guard_decision") not in (None, "allow"):
        return None
    if state.get("delivery_blocked") or state.get("shine_enforced") or state.get("shine_ok") is False:
        return None
    from cpu_llm.answerability import assess, supported_answer
    from cpu_llm.ranking import ranking_question

    message = state.get("message") or ""
    if ranking_question(message):
        return None
    rows = []
    seen: set[str] = set()
    for item in list(state.get("passages") or []) + list(state.get("related") or []):
        document_id = str(item.get("document_id") or item.get("chunk_id") or "")
        text = str(item.get("chunk_text") or item.get("text") or "").strip()
        if not text or document_id in seen:
            continue
        seen.add(document_id)
        rows.append({"document_id": document_id or f"passage-{len(rows)}", "text": text})
    decision = assess(message, rows)
    if decision is None:
        return None
    original = state.get("original_message")
    if isinstance(original, str) and original.strip() and original.strip() != message.strip():
        decision["original_query"] = original.strip()
    else:
        decision["original_query"] = None
    prior = state.get("prior_message")
    if isinstance(prior, str) and prior.strip():
        decision["prior_query"] = prior.strip()
    if decision["answer_status"] in {"insufficient_evidence", "conflicting"}:
        decision["replaces_body"] = True
        decision["verification_scope"] = "query"
        return decision
    spoken = supported_answer(message, str(state.get("answer") or ""))
    audited = state.get("audit_passed") is True and bool(spoken)
    if audited:
        decision["answer_status"] = "answered"
        decision["text"] = spoken
        decision["supported_text"] = spoken
        decision["verification_scope"] = "query"
        decision["replaces_body"] = spoken.strip() != str(state.get("answer") or "").strip()
        if decision.get("kind") != "sources":
            decision["answer_evidence"] = _evidence_in_text(decision.get("answer_evidence") or [], spoken or "")
        return decision
    decision["answer_status"] = "evidence_quote"
    decision["verification_scope"] = "retrieval"
    decision["supported_text"] = ""
    decision["text"] = _evidence_preview(decision.get("answer_evidence") or [])
    body = _body(state)
    decision["replaces_body"] = not _preview_already_shown(body, decision.get("answer_evidence") or [])
    return decision


def _evidence_in_text(evidence: list[dict[str, Any]], spoken: str) -> list[dict[str, Any]]:
    folded = spoken.casefold()
    kept = [item for item in evidence if str(item.get("span") or "").casefold() in folded]
    return kept or list(evidence)


def _evidence_preview(evidence: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in evidence:
        document_id = item.get("document_id") or "passage"
        lines.append(f"From {document_id}:\n{item.get('span') or ''}".strip())
    return "\n".join(lines)


def _preview_already_shown(body: str, evidence: list[dict[str, Any]]) -> bool:
    folded = body.casefold()
    if not evidence:
        return False
    return all(str(item.get("span") or "").casefold() in folded for item in evidence)


def _unchecked_gap(situation: dict[str, Any], state: dict[str, Any]) -> bool:
    """A rule reader that found nothing does not erase a checked sentence."""
    if situation.get("verdict") != "NONE":
        return False
    return bool(str(state.get("answer") or "").strip())


def _brief_requested(state: dict[str, Any]) -> bool:
    """A summary, explanation, or list is the requested text, so Model01 does not replace it."""
    return state.get("summarize") is True or state.get("explain") is True or state.get("list") is True


def _model01_sentence(state: dict[str, Any]) -> str:
    """The verified Model01 sentence, when no specialist and no block owns the turn."""
    if state.get("guard_decision") not in (None, "allow") or _delivery_holds(state):
        return ""
    outcome = state.get("model01") or {}
    if outcome.get("verified") is not True:
        return ""
    return _one_licensed_sentence(str(outcome.get("text") or "").strip())


def _one_licensed_sentence(text: str) -> str:
    """Keep the sentence that states the asked fact, and a ranking line already checked.

    A second stored sentence that only shares a topic word is not added.
    """
    if not text:
        return ""
    head, marker, tail = text.partition("\n\nRanking:\n")
    from cpu_llm.ranking import _STATED, _sentences

    pieces = _sentences(head)
    if len(pieces) <= 1 and not marker:
        return text
    chosen = next((item for item in pieces if _STATED.search(item)), pieces[0] if pieces else head.strip())
    if marker:
        return f"{chosen}\n\nRanking:\n{tail.strip()}"
    return chosen


def _scoped_quote(state: dict[str, Any]) -> str:
    """A named entity that Model01 could not realize stays on its own passages.

    The earlier body can still contain every retrieved neighbor. That body is
    not the answer once the prompt has named one entity.
    """
    if state.get("guard_decision") not in (None, "allow") or _delivery_holds(state):
        return ""
    outcome = state.get("model01") or {}
    if not outcome.get("scoped_entity"):
        return ""
    texts: list[str] = []
    for item in outcome.get("scoped_passages") or []:
        text = str(item.get("chunk_text") or "").strip()
        if text and text not in texts:
            texts.append(text)
    if not texts:
        return "The retrieved passages do not settle that."
    return _one_licensed_sentence(texts[0])


def _ranking(state: dict[str, Any], spoken: str) -> dict[str, Any] | None:
    """The stored order, or a statement that the passages do not give one."""
    if state.get("guard_decision") not in (None, "allow"):
        return None
    from cpu_llm.answering import retrieved_chunks
    from cpu_llm.ranking import ranking_notice

    return ranking_notice(state.get("message") or "", retrieved_chunks(state), spoken=spoken)


def _draft(state: dict[str, Any]) -> dict[str, Any] | None:
    """A formatted document when the request asks for one."""
    if state.get("guard_decision") not in (None, "allow"):
        return None
    if _delivery_holds(state):
        return None
    from cpu_llm.formats import DraftOrder, render_draft

    rows = list(state.get("passages") or []) + list(state.get("related") or [])
    preset = state.get("draft_order")
    order = None
    if isinstance(preset, dict) and preset.get("format"):
        order = DraftOrder(str(preset["format"]), str(preset.get("topic") or ""))
    return render_draft(state.get("message") or "", rows, order)


def _situation(state: dict[str, Any], *, math_only: bool, frame_only: bool) -> dict[str, Any] | None:
    """A rule answer from the retrieved passages. Memory, math, and a blocked delivery stay as they are."""
    if state.get("guard_decision") not in (None, "allow"):
        return None
    if _delivery_holds(state) or math_only or frame_only or _other_agent(state):
        return None
    conflict = state.get("correction_conflict")
    if isinstance(conflict, dict) and conflict.get("text"):
        return conflict
    from cpu_llm.answering import retrieved_chunks, situation_from_chunks

    return situation_from_chunks(state.get("message") or "", retrieved_chunks(state))


def _possibility_lines(possibilities: list[dict[str, Any]]) -> list[str]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for item in possibilities:
        side = str(item.get("side") or "")
        if side not in grouped:
            grouped[side] = []
            order.append(side)
        grouped[side].append(item)
    if order == [""]:
        return [_possibility_item(item) for item in possibilities]
    lines: list[str] = []
    for side in order:
        items = grouped[side]
        lines.append(f"{side or 'Other'} ({len(items)}):")
        lines.extend(_possibility_item(item) for item in items)
    return lines


def _possibility_item(item: dict[str, Any]) -> str:
    words = ", ".join(item.get("matched_words") or [])
    return f"- {item.get('document_id')} [{words}]"


def _delivery_holds(state: dict[str, Any]) -> bool:
    """Shine, audit, and grammar rejections stay the spoken text."""
    if state.get("delivery_blocked") or state.get("shine_enforced"):
        return True
    return state.get("shine_ok") is False


def _other_agent(state: dict[str, Any]) -> bool:
    """True when another optional agent also has something to say."""
    if any(state.get(flag) is True for flag in ("deep", "creative", "compare", "summarize", "explain", "list", "sources")):
        return True
    return bool(state.get("possibilities") or state.get("comparison") or state.get("imagination") or state.get("brief"))


def _preface(state: dict[str, Any], assessment: dict[str, Any] | None = None) -> str:
    message = (state.get("message") or "").strip()
    if state.get("guard_decision") not in (None, "allow"):
        return f"I stopped on “{message}” before looking anything up."
    related = list(state.get("related") or [])
    if not related:
        return f"I looked for “{message}” and the index returned no passage."
    if assessment is not None and assessment.get("replaces_body"):
        count = len(related)
        label = _category(related)
        where = f" labeled {label}" if label else ""
        noun = "passage" if count == 1 else "passages"
        score = related[0].get("score")
        closest = f" The closest match scores {float(score):.2f}." if isinstance(score, (int, float)) else ""
        status = assessment.get("answer_status")
        if status == "conflicting":
            return f"I found {count} {noun}{where}.{closest} The stored sentences do not agree."
        if status == "evidence_quote":
            return (
                f"I found {count} {noun}{where}.{closest} "
                "The sentence below is a retrieved passage, not a checked answer."
            )
        return f"I found {count} {noun}{where}.{closest} They do not settle the question."
    count = len(related)
    label = _category(related)
    where = f" labeled {label}" if label else ""
    noun = "passage" if count == 1 else "passages"
    score = related[0].get("score")
    closest = f" The closest match scores {float(score):.2f}." if isinstance(score, (int, float)) else ""
    if state.get("delivery_blocked") == "audit":
        return (
            f"I found {count} {noun}{where}.{closest} "
            "The checked sentence was withheld because it did not match the stored proposition."
        )
    if state.get("delivery_blocked") == "grammar":
        return (
            f"I found {count} {noun}{where}.{closest} "
            "The checked sentence was withheld because a number in it is not in the retrieved passages."
        )
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
    if state.get("delivery_blocked") == "audit":
        return "The checked sentence was withheld because it did not match the stored proposition."
    if state.get("delivery_blocked") == "grammar":
        return "The checked sentence was withheld because a number in it is not in the retrieved passages."
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
