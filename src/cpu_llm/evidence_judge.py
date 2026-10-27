"""One delivery decision for a turn, then PrismShine checks that text.

Channel similarity routes. It does not prove a fact. The judgment names the
requested entity and relationship, the premises that were accepted, and whether
the sentence about to be returned is still that decision. A later producer
cannot put a different sentence in the public answer.
"""

from __future__ import annotations

import re
from typing import Any

SCHEMA = "channel-evidence-judgment-v1"

_SENTENCE = re.compile(r"[^.!?]+[.!?]?")
_FIXED = (
    "this question type is not supported yet.",
    "the retrieved passages do not settle that.",
    "i don't have enough grounded evidence to answer that confidently.",
    "no stored sentence names who did that.",
    "which meaning do you mean?",
)
_SPECIALISTS = ("summarize", "math", "finance", "frame", "draft", "creative", "list", "sources")


def _blank(**extra: Any) -> dict[str, Any]:
    judgment = {
        "schema": SCHEMA,
        "entity": None,
        "relation": None,
        "direction": None,
        "channels": [],
        "outcome": "insufficient_evidence",
        "reasons": [],
        "evidence": [],
        "supporting": [],
        "verification": "unverified",
    }
    judgment.update(extra)
    return judgment


def _channels(intent: dict | None) -> list[dict[str, Any]]:
    """Recognized forms and enabled heads stay separate. Scores are not proof."""
    shown = []
    for name, channel in ((intent or {}).get("channels") or {}).items():
        if not channel.get("rule_supported") and not channel.get("head_enabled"):
            continue
        shown.append({
            "channel": name,
            "rule_supported": bool(channel.get("rule_supported")),
            "head_enabled": bool(channel.get("head_enabled")),
            "prototype_score": channel.get("prototype_score"),
            "basis": channel.get("basis"),
        })
    return shown


def _facts(senses: list[dict]) -> list[Any]:
    from cpu_llm.knowledge_graph import extract_facts

    found = []
    for sense in senses:
        for text in sense.get("texts") or []:
            found.extend(extract_facts("sense", text))
    return found


def _classes_compete(facts: list[Any]) -> list[str]:
    """Two stored classes of one name compete unless a source links them."""
    from cpu_llm.prompt_intent import _entity_key

    by_subject: dict[str, set[str]] = {}
    links: set[tuple[str, str]] = set()
    for fact in facts:
        if fact.relation != "is_a":
            continue
        subject, obj = _entity_key(fact.subject), _entity_key(fact.object)
        by_subject.setdefault(subject, set()).add(obj)
        links.add((subject, obj))
    reasons = []
    for subject, objects in by_subject.items():
        pending = list(objects)
        if len(pending) < 2:
            continue
        for index, left in enumerate(pending):
            for right in pending[index + 1:]:
                if (left, right) in links or (right, left) in links:
                    continue
                reasons.append(f"{subject} is stored as both {left} and {right}")
    return reasons


def sense_decision(message: str, senses: list[dict]) -> dict[str, Any]:
    """Whether these clusters are different things or facts about one thing.

    Cluster size is not a meaning. An attribute question is not a meaning.
    A clarification is returned only when the stored classes disagree or the
    question never names one referent.
    """
    from cpu_llm.comparison import comparison_sides
    from cpu_llm.prompt_intent import route_prompt
    from cpu_llm.resonance_groups import content_words

    intent = route_prompt(message)
    request = intent.get("requested") or {}
    reasons = _classes_compete(_facts(senses))
    if len(comparison_sides(message)) >= 2:
        reasons = ["the question already names each side"]
        ask = False
    elif reasons:
        ask = True
    elif request:
        ask = False
        reasons = ["the clusters do not disagree on the requested relation"]
    else:
        words = content_words(message)
        ask = len(words) <= 1 and len(senses) >= 2
        reasons = ["the question does not name one referent"] if ask else ["one named entity"]
    judgment = _blank(
        entity=request.get("entity"),
        relation=request.get("relation"),
        direction=request.get("direction"),
        channels=_channels(intent),
        outcome="clarification" if ask else "insufficient_evidence",
        reasons=reasons,
        verification="sense_gate",
    )
    return {"ask": ask, "judgment": judgment}


def _rows(result: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    seen: set[str] = set()
    for item in list(result.get("passages") or []) + list(result.get("related") or []):
        document_id = str(item.get("document_id") or item.get("chunk_id") or "")
        text = str(item.get("chunk_text") or item.get("text") or "").strip()
        if not text or document_id in seen:
            continue
        seen.add(document_id)
        rows.append({"document_id": document_id or f"passage-{len(rows)}", "text": text})
    return rows


def _spans(result: dict[str, Any], selected: dict | None) -> tuple[list[dict], list[dict], str]:
    evidence = list((selected or {}).get("answer_evidence") or result.get("answer_evidence") or [])
    supporting = list((selected or {}).get("supporting_evidence") or result.get("supporting_evidence") or [])
    licensed = str((selected or {}).get("text") or "")
    reply = result.get("reply") if isinstance(result.get("reply"), dict) else {}
    if not licensed:
        licensed = str(reply.get("supported_text") or reply.get("body") or result.get("answer") or "")
    kept_evidence = []
    for item in evidence:
        if isinstance(item, dict):
            kept_evidence.append({
                "document_id": str(item.get("document_id") or ""),
                "span": str(item.get("span") or item.get("chunk_text") or ""),
            })
    kept_supporting = []
    for item in supporting:
        if isinstance(item, dict):
            kept_supporting.append({
                "document_id": str(item.get("document_id") or ""),
                "span": str(item.get("span") or ""),
            })
    return kept_evidence, kept_supporting, licensed.strip()


def judge_delivery(result: dict[str, Any]) -> dict[str, Any]:
    """The structured decision for text the pipeline has already retrieved.

    This does not search. Rows are the turn's authorized passages.
    """
    from cpu_llm.prompt_intent import route_prompt, select_channel_answer

    message = str(result.get("resolved_query") or result.get("message") or "")
    intent = result.get("prompt_intent") or route_prompt(message)
    request = (intent or {}).get("requested") or {}
    if result.get("guard_decision") not in (None, "allow"):
        return _blank(outcome="blocked", reasons=["guard_hold"], verification="held", channels=_channels(intent))
    if result.get("access_error"):
        return _blank(outcome="blocked", reasons=[str(result.get("access_error"))], verification="held")
    if result.get("needs_clarification"):
        return _blank(
            entity=request.get("entity"), relation=request.get("relation"), direction=request.get("direction"),
            channels=_channels(intent), outcome="clarification",
            reasons=[str((result.get("clarification") or {}).get("slot") or "clarification")],
            verification="not_a_factual_claim",
        )
    reply = result.get("reply") if isinstance(result.get("reply"), dict) else {}
    status = str(result.get("answer_status") or reply.get("answer_status") or "")
    if any(result.get(flag) is True for flag in _SPECIALISTS) and request.get("relation") is None:
        return _blank(
            channels=_channels(intent),
            outcome=status or "answered",
            reasons=["specialist_contract"],
            verification="specialist_contract",
        )
    selected = None
    rows = _rows(result)
    if request and rows:
        selected = select_channel_answer(message, rows, intent=intent)
    if selected and selected.get("answer_status") not in {"answered", "conflicting", "evidence_quote"}:
        selected = None
    evidence, supporting, licensed = _spans(result, selected)
    outcome = {
        "answered": "answered",
        "evidence_quote": "evidence_quote",
        "conflicting": "conflicting",
        "unsupported": "unsupported",
        "missing": "insufficient_evidence",
        "insufficient_evidence": "insufficient_evidence",
        "blocked": "blocked",
    }.get(status, "insufficient_evidence" if not licensed else "answered")
    reasons = [str((selected or {}).get("reason") or status or "no_channel_relation")]
    if selected and selected.get("answer_status") == "conflicting":
        outcome = "conflicting"
    return _blank(
        entity=request.get("entity"),
        relation=request.get("relation"),
        direction=request.get("direction"),
        channels=_channels(intent),
        outcome=outcome,
        reasons=reasons,
        evidence=evidence,
        supporting=supporting,
        verification="structural",
        licensed_text=licensed,
    )


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE.findall(text or "") if part.strip()]


def _allowed(sentence: str, licensed: str, evidence: list[dict]) -> bool:
    folded = sentence.casefold().strip(" -:")
    if not folded or folded.endswith(":"):
        return True
    if any(folded.startswith(fixed) or fixed in folded for fixed in _FIXED):
        return True
    if folded.startswith("from ") and ":" in folded:
        return True
    if licensed and folded in licensed.casefold():
        return True
    for item in evidence:
        span = str(item.get("span") or "").casefold()
        if span and (folded in span or span in folded):
            return True
    return False


def _without_unlicensed(text: str, licensed: str, evidence: list[dict]) -> tuple[str, list[str]]:
    removed: list[str] = []

    def replace(match: re.Match[str]) -> str:
        sentence = match.group(0)
        if _allowed(sentence, licensed, evidence):
            return sentence
        removed.append(sentence.strip())
        return ""

    cleaned = _SENTENCE.sub(replace, text)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, removed


def _reject_unlicensed(result: dict[str, Any], judgment: dict[str, Any]) -> dict[str, Any]:
    """Drop a sentence the decision did not license.

    A replacement of the decision is withheld. An appended sentence is removed
    and the licensed body stays. Attribution lines and section headings are
    not claims.
    """
    if judgment.get("verification") == "specialist_contract":
        return result
    if judgment.get("outcome") in {"clarification", "blocked", "unsupported", "conflicting", "insufficient_evidence"}:
        return result
    reply = result.get("reply") if isinstance(result.get("reply"), dict) else {}
    text = str(reply.get("text") or "")
    body = str(reply.get("body") or "").strip()
    licensed = str(judgment.get("licensed_text") or "").strip()
    if not licensed:
        return result
    evidence = list(judgment.get("evidence") or [])
    if body and body in text:
        head, _, tail = text.partition(body)
        body_extra = [sentence for sentence in _sentences(body) if not _allowed(sentence, licensed, evidence)]
        if not body_extra:
            cleaned_tail, removed = _without_unlicensed(tail, licensed, evidence)
            if not removed:
                return result
            reply = dict(reply)
            reply["text"] = f"{head}{body}\n\n{cleaned_tail}".strip() if cleaned_tail else f"{head}{body}".strip()
            result["reply"] = reply
            judgment["reasons"] = list(judgment.get("reasons") or []) + ["appended_text_removed"]
            return result
    else:
        body_extra = [sentence for sentence in _sentences(text) if not _allowed(sentence, licensed, evidence)]
        if not body_extra:
            return result
    withheld = "The retrieved passages do not settle that."
    reply = dict(reply)
    reply["text"] = withheld
    reply["body"] = withheld
    reply["answer_status"] = "insufficient_evidence"
    reply["answer_evidence"] = []
    reply["supporting_evidence"] = []
    result["reply"] = reply
    result["answer"] = None
    result["answer_status"] = "insufficient_evidence"
    result["answer_evidence"] = []
    result["supporting_evidence"] = []
    result["audit_passed"] = False
    result["needs_clarification"] = False
    judgment["outcome"] = "insufficient_evidence"
    judgment["reasons"] = list(judgment.get("reasons") or []) + ["final_text_not_in_evidence"]
    judgment["verification"] = "rejected_replacement"
    judgment["evidence"] = []
    return result


def finalize_turn(result: dict[str, Any], gate: Any | None) -> dict[str, Any]:
    """Apply the judgment to the text leaving ask(), then Shine-check that text.

    An earlier audit does not survive a replaced sentence. Shine does not run
    a second search and cannot restore a sentence the judgment rejected.
    """
    if result.get("judgment") and result.get("needs_clarification"):
        result["answer"] = None
        result["audit_passed"] = False
        return result
    if result.get("abstention_triggered"):
        # The graph already returned the abstention sentence. A second Shine
        # call with abstention cleared would replace that sentence.
        result["judgment"] = _blank(outcome="insufficient_evidence", reasons=["empty_retrieval"], verification="abstention")
        result["shine_final"] = {"role": "final_deliverable", "applied": False, "reason": "abstention"}
        return result
    judgment = judge_delivery(result)
    result = _reject_unlicensed(result, judgment)
    reply = result.get("reply") if isinstance(result.get("reply"), dict) else {}
    if judgment.get("verification") != "specialist_contract" and gate is not None and judgment["outcome"] in {"answered", "evidence_quote"}:
        from cpu_llm.grounding import verify_grounding

        body = str(reply.get("body") or reply.get("supported_text") or reply.get("text") or "")
        scores: dict[str, Any] = {}
        for item in list(result.get("related") or []) + list(result.get("passages") or []):
            if item.get("score") is None:
                continue
            for key in (item.get("chunk_id"), item.get("document_id"), item.get("chunk_text"), item.get("text")):
                if key:
                    scores[str(key)] = item.get("score")
        related = []
        for index, item in enumerate(judgment.get("evidence") or []):
            span = str(item.get("span") or "")
            if not span:
                continue
            document_id = str(item.get("document_id") or f"evidence-{index}")
            related.append({
                "chunk_id": document_id,
                "chunk_text": span,
                "score": scores.get(document_id, scores.get(span)),
            })
        claim = str(judgment.get("licensed_text") or "").strip()
        shown = body or str(reply.get("text") or "")
        # The graph already grounded this claim. Attribution lines around a
        # quote are not a new answer, so they do not get a second, harsher bundle.
        if result.get("shine_ok") is True and claim and claim.casefold() in shown.casefold():
            result["shine_final"] = {
                "role": "final_deliverable",
                "decision": result.get("shine_decision"),
                "resolution_gate": result.get("shine_resolution_gate"),
                "ok": True,
                "reused_graph_verdict": True,
            }
            result["judgment"] = {key: value for key, value in judgment.items() if key != "licensed_text"}
            return result
        if claim:
            body = claim
        if related and all(item.get("score") is None for item in related) and result.get("shine_ok") is not False:
            result["shine_final"] = {
                "role": "final_deliverable",
                "applied": False,
                "reason": "retrieval_score_absent",
            }
            result["judgment"] = {key: value for key, value in judgment.items() if key != "licensed_text"}
            return result
        checked = verify_grounding(
            gate,
            question=str(result.get("message") or " "),
            answer=body,
            related=related,
            query_category=result.get("query_category"),
            abstention=False,
        )
        result["shine_final"] = {
            "decision": checked["shine_decision"],
            "resolution_gate": checked["shine_resolution_gate"],
            "ok": checked["shine_ok"],
            "role": "final_deliverable",
        }
        if checked["shine_ok"] is False:
            result["answer"] = None
            result["audit_passed"] = False
            result["answer_status"] = "insufficient_evidence"
            result["answer_evidence"] = []
            result["supporting_evidence"] = []
            reply = dict(reply)
            reply["text"] = checked["answer"] or reply.get("text")
            reply["answer_status"] = "insufficient_evidence"
            result["reply"] = reply
            judgment["outcome"] = "insufficient_evidence"
            judgment["verification"] = "shine_held"
            judgment["reasons"] = list(judgment.get("reasons") or []) + ["shine_final_hold"]
    elif judgment.get("verification") == "specialist_contract":
        result["shine_final"] = {"role": "specialist_contract", "applied": False}
    result["judgment"] = {key: value for key, value in judgment.items() if key != "licensed_text"}
    if judgment.get("verification") in {"rejected_replacement", "shine_held"}:
        result["answer"] = None
        result["audit_passed"] = False
    return result
