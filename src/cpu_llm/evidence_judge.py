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
_SPECIALISTS = ("summarize", "explain", "math", "finance", "frame", "draft", "creative", "list", "sources")
_UNSETTLED = "The retrieved passages do not settle that."
_HEADING = re.compile(
    r"^(?:summary|explanation|list|sources|math|finance|event|comparison|imagined passage|ranking|possibilities(?: \(\d+\))?)\s*:$",
    re.IGNORECASE,
)
_ATTRIB_ONLY = re.compile(r"^from\s+\S+:$", re.IGNORECASE)
_ATTRIB_CLAIM = re.compile(r"^from\s+\S+:\s*(.+)$", re.IGNORECASE | re.DOTALL)
_LEADING_HEADING = re.compile(
    r"^(?:summary|explanation|list|sources|math|finance|event|comparison|imagined passage|ranking|possibilities(?: \(\d+\))?)\s*:\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)


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


def _specialist_proof(result: dict[str, Any]) -> str:
    """Text the specialist itself produced. A flag without this text is not a proof."""
    brief = result.get("brief") if isinstance(result.get("brief"), dict) else {}
    parts: list[str] = []
    if result.get("summarize") is True:
        parts.append(str(brief.get("summary") or ""))
    if result.get("explain") is True:
        parts.append(str(brief.get("explanation") or ""))
    if result.get("list") is True:
        parts.append(str(brief.get("list") or ""))
    if result.get("sources") is True:
        parts.extend(str(item) for item in list(brief.get("sources") or []))
    if result.get("math") is True:
        parts.append(str((result.get("math_result") or {}).get("text") or ""))
    if result.get("finance") is True:
        parts.append(str((result.get("finance_result") or {}).get("text") or ""))
    if result.get("frame") is True:
        parts.append(str((result.get("frame_result") or {}).get("text") or ""))
    if result.get("draft") is True:
        draft = result.get("draft")
        if not isinstance(draft, dict):
            draft = (result.get("reply") or {}).get("draft") if isinstance(result.get("reply"), dict) else {}
        parts.append(str((draft or {}).get("text") or ""))
    if result.get("creative") is True:
        parts.append(str((result.get("imagination") or {}).get("text") or ""))
    checked = str(result.get("answer") or "").strip()
    if checked and any(result.get(flag) is True for flag in ("summarize", "explain", "list", "sources")):
        parts.append(checked)
    return " ".join(part.strip() for part in parts if part and str(part).strip())


def _specialist_evidence(result):
    """Producer-selected IDs only; a neighbor is not an accepted citation."""
    selected = set((result.get('brief') or {}).get('sources') or [])
    draft = (result.get('reply') or {}).get('draft') or {}
    if isinstance(draft, dict):
        selected.update(draft.get('sources') or [])
    evidence = []
    for row in _rows(result):
        if row['document_id'] in selected:
            evidence.append(dict(document_id=row['document_id'], span=row['text']))
    return evidence


def judge_delivery(result: dict[str, Any]) -> dict[str, Any]:
    """The structured decision for text the pipeline has already retrieved.

    This does not search. Rows are the turn's authorized passages.
    """
    from cpu_llm.prompt_intent import route_prompt
    from cpu_llm.answerability import assess
    from cpu_llm.semantic import request_contract

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
    if status == 'unsupported':
        return _blank(outcome='unsupported', reasons=['unsupported_producer_contract'], verification='not_a_factual_claim')
    contract = request_contract(message, intent)
    # Specialized producers own explicit math/document/event/overview tasks,
    # not ordinary factual slots accidentally routed through another node.
    specialist = any(result.get(flag) is True for flag in ('math', 'finance', 'draft', 'creative', 'frame'))
    specialist = specialist or (contract is None and any(result.get(flag) is True for flag in _SPECIALISTS))
    if specialist and request.get("relation") is None:
        proof = _specialist_proof(result)
        if proof:
            return _blank(
                channels=_channels(intent),
                outcome=status or "answered",
                reasons=["specialist_contract"],
                verification="specialist_contract",
                licensed_text=proof,
                evidence=_specialist_evidence(result),
            )
    rows = _rows(result)
    if contract is not None:
        request = contract.as_dict()
        selected = assess(message, rows, intent=intent) if rows else {
            "answer_status": "insufficient_evidence",
            "reason": "no_matching_channel_relation",
        }
        if selected.get("answer_status") not in {"answered", "conflicting", "evidence_quote", "needs_clarification"}:
            return _blank(
                entity=request.get("entity"),
                relation=request.get("relation"),
                direction=request.get("direction"),
                channels=_channels(intent),
                outcome="insufficient_evidence",
                reasons=[str(selected.get("reason") or "no_matching_channel_relation"), "selector_rejected"],
                verification="selector_rejected",
            )
    else:
        selected = None
        from cpu_llm.ranking import ranking_question
        if re.match(r'^(?:what|who|where|why|how|when|which)\b', message, re.I) and not ranking_question(message):
            return _blank(outcome='insufficient_evidence', reasons=['unsupported_factual_binding', 'selector_rejected'],
                          verification='selector_rejected', channels=_channels(intent))
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
    if selected and selected.get('answer_status') == 'needs_clarification':
        return _blank(outcome='clarification', reasons=['unresolved_meaning'], verification='not_a_factual_claim',
                      licensed_text=selected.get('text', ''), channels=_channels(intent))
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
        request_contract=contract.as_dict() if contract else None,
        answer_decision=(selected or {}).get('decision'),
    )


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE.findall(text or "") if part.strip()]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip(" .")


def _chrome(sentence: str) -> bool:
    raw = sentence.strip()
    if not raw or _HEADING.match(raw) or _ATTRIB_ONLY.match(raw):
        return True
    if raw.endswith(":") and " is " not in raw.casefold() and not re.search(r"\d", raw):
        return True
    return False


def _fixed(sentence: str) -> bool:
    folded = _norm(sentence)
    return any(folded == _norm(phrase) for phrase in _FIXED)


def _licensed_norms(licensed: str, evidence: list[dict]) -> set[str]:
    norms = {_norm(sentence) for sentence in _sentences(licensed)}
    for item in evidence:
        norms.update(_norm(sentence) for sentence in _sentences(str(item.get("span") or "")))
    norms.discard("")
    return norms


def _claim_sentences(sentence: str) -> list[str]:
    """The claim inside one surface sentence, after an attribution line or heading."""
    # Markdown list markers are presentation, not part of the licensed claim.
    # Requiring whitespace preserves negative numbers and decimal quantities.
    list_marker = r"^(?:[-*+]|\d+[.)])\s+"
    raw = re.sub(list_marker, '', sentence.strip())
    match = _ATTRIB_CLAIM.match(raw) or _LEADING_HEADING.match(raw)
    if match:
        rest = match.group(1).strip()
        return [re.sub(list_marker, '', part.strip()) for part in _sentences(rest)] if rest else []
    return [raw]


def _unlicensed(text: str, norms: set[str]) -> list[str]:
    """Claims that are not exactly a licensed sentence.

    A longer sentence that merely contains the licensed words is a different
    claim. Negation and an added clause therefore do not inherit the license.
    """
    rejected = []
    for sentence in _sentences(text):
        if _chrome(sentence) or _fixed(sentence):
            continue
        for claim in _claim_sentences(sentence):
            if _chrome(claim) or _fixed(claim):
                continue
            if _norm(claim) not in norms:
                rejected.append(claim.strip())
    return rejected


def _without_unlicensed(text: str, norms: set[str]) -> tuple[str, list[str]]:
    """Drop unlicensed claims. A heading stays with the licensed sentence under it."""
    removed: list[str] = []
    kept_lines: list[str] = []
    for line in text.splitlines():
        if not line.strip() or _chrome(line.strip()):
            kept_lines.append(line)
            continue
        if not _unlicensed(line, norms):
            kept_lines.append(line)
            continue
        kept = [sentence.strip() for sentence in _sentences(line) if not _unlicensed(sentence, norms)]
        removed.extend(sentence.strip() for sentence in _sentences(line) if _unlicensed(sentence, norms))
        if kept:
            kept_lines.append(" ".join(kept))
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip()
    return cleaned, removed


def _reply_of(result: dict[str, Any]) -> dict[str, Any]:
    reply = result.get("reply")
    return dict(reply) if isinstance(reply, dict) else {}


def _note_rejected(result: dict[str, Any], reply: dict[str, Any]) -> None:
    result["rejected_candidate"] = {
        "text": reply.get("text"),
        "body": reply.get("body"),
        "supported_text": reply.get("supported_text"),
        "answer_evidence": list(reply.get("answer_evidence") or []),
        "supporting_evidence": list(reply.get("supporting_evidence") or []),
    }


def _publish(
    result: dict[str, Any],
    *,
    text: str,
    status: str,
    evidence: list[dict],
    supporting: list[dict],
    scope: str,
    answer: str | None,
) -> dict[str, Any]:
    previous = _reply_of(result)
    _note_rejected(result, previous)
    reply = dict(previous)
    reply["text"] = text
    reply["body"] = text
    reply["supported_text"] = "" if answer is None else answer
    reply["answer_status"] = status
    reply["answer_evidence"] = list(evidence)
    reply["supporting_evidence"] = list(supporting)
    reply["verification_scope"] = scope
    result["reply"] = reply
    result["answer"] = answer
    result["answer_status"] = status
    result["audit_passed"] = False
    result["answer_evidence"] = list(evidence)
    result["supporting_evidence"] = list(supporting)
    result["verification_scope"] = scope
    result["needs_clarification"] = False
    return result


def _withhold(result: dict[str, Any], judgment: dict[str, Any], reason: str) -> dict[str, Any]:
    _publish(
        result,
        text=_UNSETTLED,
        status="insufficient_evidence",
        evidence=[],
        supporting=[],
        scope="held",
        answer=None,
    )
    judgment["outcome"] = "insufficient_evidence"
    reasons = list(judgment.get("reasons") or [])
    if reason not in reasons:
        reasons.append(reason)
    judgment["reasons"] = reasons
    if judgment.get("verification") != "selector_rejected":
        judgment["verification"] = "rejected_replacement"
    judgment["evidence"] = []
    judgment["supporting"] = []
    if judgment.get('answer_decision'):
        judgment['answer_decision'] = dict(judgment['answer_decision'],
            outcome='insufficient_evidence', reason=reason, text=_UNSETTLED, proof=[])
    return result


def _render_conflict(result: dict[str, Any], judgment: dict[str, Any]) -> dict[str, Any]:
    """A conflict is the public reply. It is not an asserted color or value."""
    _publish(
        result,
        text=str(judgment.get("licensed_text") or _UNSETTLED),
        status="conflicting",
        evidence=list(judgment.get("evidence") or []),
        supporting=list(judgment.get("supporting") or []),
        scope="query",
        answer=None,
    )
    return result


def _enforce_licensed(result: dict[str, Any], judgment: dict[str, Any]) -> dict[str, Any]:
    """Keep a sentence only when it is exactly licensed, including its polarity."""
    if judgment.get("outcome") in {"clarification", "blocked", "unsupported", "insufficient_evidence"}:
        return result
    licensed = str(judgment.get("licensed_text") or "").strip()
    if not licensed:
        return result
    norms = _licensed_norms(licensed, list(judgment.get("evidence") or []))
    reply = _reply_of(result)
    text = str(reply.get("text") or "")
    body = str(reply.get("body") or "").strip()
    subject = body or text
    if _unlicensed(subject, norms):
        if judgment.get("verification") == "specialist_contract":
            _publish(
                result,
                text=licensed,
                status=str(judgment.get("outcome") or "answered"),
                evidence=list(judgment.get("evidence") or []),
                supporting=list(judgment.get("supporting") or []),
                scope="specialist_contract",
                answer=licensed,
            )
            judgment["reasons"] = list(judgment.get("reasons") or []) + ["specialist_text_replaced"]
            return result
        return _withhold(result, judgment, "final_text_not_in_evidence")
    cleaned, removed = _without_unlicensed(text, norms)
    if not removed:
        return result
    reasons = list(judgment.get("reasons") or [])
    if body and body in text:
        head, _, tail = text.partition(body)
        if _unlicensed(head, norms):
            reasons.append("prefixed_text_removed")
        if _unlicensed(tail, norms):
            reasons.append("appended_text_removed")
    else:
        reasons.append("appended_text_removed")
    judgment["reasons"] = reasons
    reply = dict(reply)
    reply["text"] = cleaned
    if str(reply.get("supported_text") or "") and _unlicensed(str(reply.get("supported_text") or ""), norms):
        reply["supported_text"] = body if body and not _unlicensed(body, norms) else ""
    reply["answer_evidence"] = list(judgment.get("evidence") or [])
    reply["supporting_evidence"] = list(judgment.get("supporting") or [])
    result["reply"] = reply
    result["answer_evidence"] = list(judgment.get("evidence") or [])
    result["supporting_evidence"] = list(judgment.get("supporting") or [])
    if result.get("answer") and _unlicensed(str(result.get("answer") or ""), norms):
        result["answer"] = None
        result["audit_passed"] = False
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
    if judgment.get('outcome') == 'clarification':
        if not result.get('needs_clarification'):
            result = _publish(result, text=judgment.get('licensed_text') or 'Please clarify the intended meaning.',
                              status='needs_clarification', evidence=[], supporting=[], scope=None, answer=None)
            result['needs_clarification'] = True
            result['clarification'] = dict(slot='sense', text=result['reply']['text'])
    elif judgment.get("outcome") == "conflicting":
        result = _render_conflict(result, judgment)
    elif judgment.get("verification") == "selector_rejected":
        result = _withhold(result, judgment, "selector_rejected")
    else:
        result = _enforce_licensed(result, judgment)
    if judgment.get('outcome') in {'answered', 'evidence_quote', 'conflicting'}:
        # Even when the text was unchanged, publish the same complete proof the
        # judge accepted. Previously only rewritten replies received these IDs.
        result['answer_evidence'] = list(judgment.get('evidence') or [])
        result['supporting_evidence'] = list(judgment.get('supporting') or [])
        result.setdefault('reply', {})['answer_evidence'] = result['answer_evidence']
        result['reply']['supporting_evidence'] = result['supporting_evidence']
    if judgment.get("verification") == "specialist_contract" and judgment.get("verification") != "rejected_replacement":
        result["shine_final"] = {"role": "specialist_contract", "checked": True}
        result["judgment"] = {key: value for key, value in judgment.items() if key != "licensed_text"}
        return result
    reply = result.get("reply") if isinstance(result.get("reply"), dict) else {}
    if (
        judgment.get("verification") == "structural"
        and gate is not None
        and judgment["outcome"] in {"answered", "evidence_quote"}
    ):
        from cpu_llm.grounding import verify_grounding

        shown = str(reply.get("text") or "")
        delivered = [
            claim.strip()
            for sentence in _sentences(shown)
            if not _chrome(sentence) and not _fixed(sentence)
            for claim in _claim_sentences(sentence)
            if not _chrome(claim) and not _fixed(claim)
        ]
        licensed_norms = _licensed_norms(
            str(judgment.get("licensed_text") or ""),
            list(judgment.get("evidence") or []),
        )
        delivered_norms = [_norm(claim) for claim in delivered]
        if any(item not in licensed_norms for item in delivered_norms):
            result = _withhold(result, judgment, "final_text_not_in_evidence")
        elif result.get("shine_ok") is True and delivered_norms and all(item in licensed_norms for item in delivered_norms):
            result["shine_final"] = {
                "role": "final_deliverable",
                "decision": result.get("shine_decision"),
                "resolution_gate": result.get("shine_resolution_gate"),
                "ok": True,
                "reused_graph_verdict": True,
            }
            result["judgment"] = {key: value for key, value in judgment.items() if key != "licensed_text"}
            return result
        else:
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
            if related and all(item.get("score") is None for item in related) and result.get("shine_ok") is not False:
                result["shine_final"] = {
                    "role": "final_deliverable",
                    "applied": False,
                    "reason": "retrieval_score_absent",
                }
            else:
                checked = verify_grounding(
                    gate,
                    question=str(result.get("message") or " "),
                    answer=" ".join(delivered) or shown,
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
                    _publish(
                        result,
                        text=str(checked.get("answer") or shown),
                        status="insufficient_evidence",
                        evidence=[],
                        supporting=[],
                        scope="held",
                        answer=None,
                    )
                    judgment["outcome"] = "insufficient_evidence"
                    judgment["verification"] = "shine_held"
                    judgment["reasons"] = list(judgment.get("reasons") or []) + ["shine_final_hold"]
                    judgment["evidence"] = []
                    judgment["supporting"] = []
                    if judgment.get('answer_decision'):
                        judgment['answer_decision'] = dict(judgment['answer_decision'],
                            outcome='insufficient_evidence', reason='shine_final_hold',
                            text=str(checked.get('answer') or shown), proof=[])
    result["judgment"] = {key: value for key, value in judgment.items() if key != "licensed_text"}
    if judgment.get("verification") in {"rejected_replacement", "shine_held"}:
        result["answer"] = None
        result["audit_passed"] = False
    return result
