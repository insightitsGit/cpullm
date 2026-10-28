"""Score request-pipeline results. This module does not import cpu_llm."""

from __future__ import annotations

import re

SCORER_VERSION = "request-pipeline-scorer-v2.1"

# Accepted proof lives only on these fields. Retrieval, related rows, and
# diagnostic ids are not citations.
_EVIDENCE_KEYS = ("answer_evidence", "supporting_evidence", "evidence")

_OUTCOME_MAP = {
    "answered": "answer",
    "answer": "answer",
    "evidence_quote": "quote",
    "quote": "quote",
    "clarification": "clarification",
    "needs_clarification": "clarification",
    "conflicting": "conflict",
    "conflict": "conflict",
    "insufficient_evidence": "insufficient",
    "insufficient": "insufficient",
    "missing": "insufficient",
    "unsupported": "unsupported",
    "blocked": "blocked",
    "partial": "partial",
    "pending": "pending",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "limit_exceeded": "budget_refusal",
    "budget_refusal": "budget_refusal",
}


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def public_fields(result: dict, *, include_children: bool = True) -> str:
    """Text a caller can read as the answer. Diagnostics stay out."""
    reply = result.get("reply") if isinstance(result.get("reply"), dict) else {}
    parts = [
        _text(result.get("answer")),
        _text(reply.get("text")),
        _text(reply.get("body")),
        _text(reply.get("supported_text")),
    ]
    if include_children:
        for task in result.get("task_results") or []:
            child = task.get("result") if isinstance(task, dict) else None
            if isinstance(child, dict):
                child_reply = child.get("reply") if isinstance(child.get("reply"), dict) else {}
                parts.append(_text(child.get("answer")))
                parts.append(_text(child_reply.get("text")))
                parts.append(_text(child_reply.get("body")))
    return "\n".join(part for part in parts if part)


def _evidence_ids_from(result: dict, found: set[str], *, include_children: bool) -> None:
    """Collect citation ids from accepted evidence only."""
    if not isinstance(result, dict):
        return
    reply = result.get("reply") if isinstance(result.get("reply"), dict) else {}
    for source in (result, reply):
        for key in _EVIDENCE_KEYS:
            for item in source.get(key) or []:
                if not isinstance(item, dict):
                    continue
                document_id = item.get("document_id") or item.get("chunk_id")
                if isinstance(document_id, str) and document_id:
                    found.add(document_id)
    if not include_children:
        return
    for task in result.get("task_results") or []:
        if isinstance(task, dict):
            _evidence_ids_from(task.get("result") or {}, found, include_children=True)


def evidence_ids(result: dict, *, include_children: bool = True) -> set[str]:
    found: set[str] = set()
    _evidence_ids_from(result, found, include_children=include_children)
    return found


def retrieval_ids(trace: list[dict] | None) -> set[str] | None:
    if trace is None:
        return None
    found: set[str] = set()
    for event in trace:
        if event.get("event") not in {"search", "search_allowed"}:
            continue
        for item in event.get("ids") or []:
            found.add(str(item))
    return found


def map_outcome(result: dict) -> str:
    plan = result.get("request_plan") if isinstance(result.get("request_plan"), dict) else {}
    if plan.get("status") == "limit_exceeded" or result.get("status") == "limit_exceeded":
        return "budget_refusal"
    if result.get("guard_decision") == "block" or result.get("answer_status") == "blocked" or result.get("status") == "blocked":
        return "blocked"
    if result.get("access_error"):
        return "blocked"
    if result.get("needs_clarification") or result.get("status") == "needs_clarification":
        return "clarification"
    if result.get("status") in {"cancelled", "canceled"}:
        return "cancelled"
    judgment = result.get("judgment") if isinstance(result.get("judgment"), dict) else {}
    raw = judgment.get("outcome") or result.get("answer_status") or result.get("status") or "unknown"
    return _OUTCOME_MAP.get(str(raw), "unknown")


def _contains(text: str, needle: str) -> bool:
    return needle.casefold() in text.casefold()


def _endorsed(result: dict, text: str) -> bool:
    """A conflict quotation or a clarification option is not an endorsed fact."""
    outcome = map_outcome(result)
    if outcome in {"clarification", "conflict", "blocked", "budget_refusal", "cancelled"}:
        return False
    folded = text.casefold()
    if "do not settle" in folded or "stored sentences conflict" in folded:
        return False
    return outcome in {"answer", "quote", "partial"}


def _proof_hit(proof_sets: list[list[str]], found: set[str] | None) -> bool | None:
    if found is None:
        return None
    if not proof_sets:
        return None
    return any(set(proof) <= found for proof in proof_sets if proof)


def _resolve(proof_sets: list[list[str]], corrections: dict[str, str]) -> list[list[str]]:
    resolved = []
    for proof in proof_sets or []:
        row = []
        for item in proof:
            if isinstance(item, str) and item.startswith("<corrected:") and item.endswith(">"):
                row.append(corrections.get(item[11:-1], item))
            else:
                row.append(item)
        resolved.append(row)
    return resolved


def _budget(result: dict) -> dict:
    plan = result.get("response_plan") if isinstance(result.get("response_plan"), dict) else {}
    request_plan = result.get("request_plan") if isinstance(result.get("request_plan"), dict) else {}
    combined = plan.get("combined_budget") or request_plan.get("combined_budget") or {}
    return combined if isinstance(combined, dict) else {}


def _child_budgets(result: dict) -> dict[str, int]:
    found = {}
    for task in result.get("task_results") or []:
        if not isinstance(task, dict):
            continue
        child = task.get("result") if isinstance(task.get("result"), dict) else {}
        child_plan = child.get("response_plan") if isinstance(child.get("response_plan"), dict) else {}
        if "combined_task_budget" in child_plan:
            found[str(task.get("id"))] = child_plan["combined_task_budget"]
    return found


def _repeated_heading(result: dict) -> bool:
    plan = result.get("request_plan") if isinstance(result.get("request_plan"), dict) else {}
    reply = result.get("reply") if isinstance(result.get("reply"), dict) else {}
    text = _text(reply.get("text"))
    for task in plan.get("tasks") or []:
        query = _text(task.get("query")).strip()
        if len(query) < 12:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == query or stripped.endswith(": " + query):
                return True
    return False


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]


def _negated(sentence: str) -> bool:
    return re.search(r"\b(?:not|never|no)\b|n't", sentence, re.I) is not None


def _sentence_quantifier(sentence: str) -> str:
    """Quantifier of the claim, including a sentence wrapped in a citation prefix."""
    if re.search(r"\b(?:some|most|many|several|few)\b", sentence, re.I):
        return "some"
    if re.search(r"\bevery\b|\ball\b", sentence, re.I):
        return "every"
    return "direct"


def _has_word(sentence: str, word: str) -> bool:
    if not word:
        return True
    return re.search(rf"\b{re.escape(word)}\b", sentence, re.I) is not None


def _relation_cue(sentence: str, relation: str) -> bool:
    if relation in {"", "has_color", "is_a"}:
        if relation == "is_a":
            return re.search(r"\b(?:is|are)\s+(?:a|an)\b", sentence, re.I) is not None
        if relation == "has_color":
            return re.search(r"\b(?:is|are|was|were)\b", sentence, re.I) is not None
        return True
    if relation == "lives_in":
        return re.search(r"\b(?:found|live|lives|resides?)\b", sentence, re.I) is not None
    if relation == "has":
        return re.search(r"\b(?:has|have)\b", sentence, re.I) is not None
    if relation == "best":
        return re.search(r"\bbest\b", sentence, re.I) is not None
    return True


def _ordered(sentence: str, binding: dict, *, subject_first: bool) -> bool:
    subject = str(binding.get("subject") or "")
    obj = str(binding.get("object") or "")
    if not subject or not obj:
        return True
    folded = sentence.casefold()
    subject_at = folded.find(subject.casefold())
    object_at = folded.find(obj.casefold())
    if subject_at < 0 or object_at < 0:
        return False
    return subject_at < object_at if subject_first else object_at < subject_at


def binding_status(sentence: str, binding: dict) -> str:
    """How one endorsed sentence relates to one gold binding.

    This matcher does not import the library. ``match`` means the sentence
    states the binding. ``contradiction`` means it uses the same words with
    the wrong entity, relation, direction, polarity, or quantifier.
    """
    subject = str(binding.get("subject") or "")
    obj = str(binding.get("object") or "")
    polarity = str(binding.get("polarity") or "affirmative")
    direction = str(binding.get("direction") or "subject")
    quantifier = str(binding.get("quantifier") or "direct")
    relation = str(binding.get("relation") or "")
    has_subject = _has_word(sentence, subject)
    has_object = _has_word(sentence, obj)
    sentence_quantifier = _sentence_quantifier(sentence)
    if quantifier == "direct" and sentence_quantifier == "every" and has_object and not has_subject:
        return "needs_membership"
    if quantifier == "direct" and sentence_quantifier != "direct" and has_object and not has_subject:
        return "contradiction"
    # The value was stated, but not about the asked entity.
    if has_object and not has_subject:
        return "contradiction"
    if not has_subject or not has_object:
        return "absent"
    if polarity == "affirmative" and _negated(sentence):
        return "contradiction"
    if polarity == "negative" and not _negated(sentence):
        return "contradiction"
    subject_first = direction != "object"
    if not _ordered(sentence, binding, subject_first=subject_first):
        return "contradiction"
    if not _relation_cue(sentence, relation):
        return "contradiction"
    if quantifier in {"some", "every"} and sentence_quantifier != quantifier:
        return "contradiction"
    if quantifier == "direct" and sentence_quantifier != "direct":
        return "contradiction"
    return "match"


def _membership_join(sentences: list[str], binding: dict) -> bool:
    """A direct fact is licensed when the answer states membership and the every-rule.

    This does not import the library. ``some`` and ``average`` never license
    an individual here.
    """
    subject = str(binding.get("subject") or "")
    obj = str(binding.get("object") or "")
    if not subject or not obj:
        return False
    kinds = []
    for sentence in sentences:
        found = re.search(r"\bevery\s+(.+?)\s+(?:lives|has|have)\b", sentence, re.I)
        if found and _has_word(sentence, obj):
            kinds.append(found.group(1).strip())
    for sentence in sentences:
        if not _has_word(sentence, subject):
            continue
        for kind in kinds:
            if re.search(rf"\b(?:is|are)\s+(?:a|an)\s+{re.escape(kind)}\b", sentence, re.I):
                return True
    return False


def _binding_verdict(text: str, bindings: list[dict]) -> tuple[list[dict], list[dict]]:
    sentences = _sentences(text)
    missed = []
    contradicted = []
    for binding in bindings:
        statuses = [binding_status(sentence, binding) for sentence in sentences]
        if "match" in statuses:
            continue
        if "contradiction" in statuses:
            contradicted.append(binding)
        elif "needs_membership" in statuses and _membership_join(sentences, binding):
            continue
        elif "needs_membership" in statuses:
            contradicted.append(binding)
        else:
            missed.append(binding)
    return missed, contradicted


def score_case(case: dict, result: dict, trace: list[dict] | None = None, corrections: dict[str, str] | None = None, *, measured_optional_units: int | None = None) -> dict:
    """Return separated verdicts. A long required proof is not a word-limit failure."""
    corrections = corrections or {}
    expected = case.get("outcome") or "answer"
    actual = map_outcome(result)
    separate_children = bool(case.get("children"))
    text = public_fields(result, include_children=not separate_children)
    claims = [item for item in case.get("claims") or [] if item]
    missing_claims = [claim for claim in claims if not _contains(text, claim)]
    forbidden = [item for item in case.get("forbidden") or [] if item and _contains(text, item)]
    endorsed = _endorsed(result, text)
    false_assertion = bool(forbidden) and (endorsed or any(marker in item for item in forbidden for marker in ("seal-",)))
    answer_like = expected in {"answer", "quote", "partial"}
    bindings = [item for item in case.get("bindings") or [] if isinstance(item, dict)]
    binding_misses: list[dict] = []
    binding_contradictions: list[dict] = []
    if bindings and endorsed:
        binding_misses, binding_contradictions = _binding_verdict(text, bindings)
        if binding_contradictions:
            false_assertion = True
            missing_claims = []
        elif binding_misses and answer_like:
            missing_claims = [str(item.get("object") or item.get("subject") or "binding") for item in binding_misses]
    # A private marker is a disclosure even inside a refusal, except when the
    # refusal text does not actually contain it. Presence was already tested.
    marker_leak = any("seal-" in item for item in forbidden)
    if marker_leak:
        false_assertion = True
    proof_sets = _resolve(case.get("proof_sets") or [], corrections)
    cited = evidence_ids(result, include_children=not separate_children)
    retrieved = retrieval_ids(trace)
    proof_cited = _proof_hit(proof_sets, cited)
    proof_retrieved = _proof_hit(proof_sets, retrieved)
    retrieved_then_lost = proof_retrieved is True and proof_cited is False and expected in {"answer", "quote", "partial"}
    omission = bool(missing_claims) and answer_like and not binding_contradictions
    appropriate_abstention = expected in {"insufficient", "unsupported"} and actual == expected and not false_assertion
    unnecessary_clarification = expected in {"answer", "quote", "partial"} and actual == "clarification"
    appropriate_clarification = expected == "clarification" and actual == "clarification" and not marker_leak
    recognized_conflict = expected == "conflict" and actual == "conflict" and not missing_claims and not marker_leak
    contract_disagreement = False
    if expected == "conflict" and actual in {"answer", "quote"} and missing_claims and forbidden:
        # Quoted only one side of a stored disagreement.
        contract_disagreement = False
    if result.get("contract_disagreement"):
        contract_disagreement = True
    budget = case.get("budget") or {}
    combined = _budget(result)
    budget_notes = []
    hard_limit_failure = False
    if budget:
        if combined.get("hard_limit") is True or combined.get("word_limit_enforced") is True:
            hard_limit_failure = True
            budget_notes.append("response declared a hard limit")
        if "task_allocations" in budget and combined.get("task_allocations") != budget["task_allocations"]:
            budget_notes.append("allocation missing" if combined.get("task_allocations") is None else "allocation mismatch")
        if "optional_unit_budget" in budget and combined.get("optional_unit_budget") != budget["optional_unit_budget"]:
            budget_notes.append("optional budget missing" if combined.get("optional_unit_budget") is None else "optional budget mismatch")
        if budget.get("coverage_override") and combined.get("budget_overridden_for_coverage") is not True:
            budget_notes.append("coverage override missing")
        children = _child_budgets(result)
        if budget.get("task_allocations") and children:
            for task_id, share in budget["task_allocations"].items():
                if task_id in children and children[task_id] != share:
                    budget_notes.append(f"child ceiling {task_id}")
        if budget.get("local_detailed_capped") and combined.get("optional_unit_budget") is not None:
            for ceiling in children.values():
                if ceiling > combined["optional_unit_budget"]:
                    budget_notes.append("local detailed bypassed the shared ceiling")
    if budget.get("proof_may_exceed"):
        hard_limit_failure = False
    word_limit_failure = hard_limit_failure and not budget.get("proof_may_exceed")
    silent_task_loss = False
    judgment = result.get("judgment") if isinstance(result.get("judgment"), dict) else {}
    if answer_like and omission and judgment.get("complete") is True and actual in {"answer", "quote"}:
        silent_task_loss = True
    if answer_like and case.get("budget", {}) and case["budget"].get("task_count"):
        plan = result.get("request_plan") if isinstance(result.get("request_plan"), dict) else {}
        tasks = plan.get("tasks") or []
        if tasks and len(tasks) < case["budget"]["task_count"] and actual not in {"budget_refusal", "clarification", "blocked"}:
            silent_task_loss = True
    repeated = _repeated_heading(result)
    # A runtime flag is not a measurement. Overflow counts only when the
    # runner supplies an independent unit total.
    if measured_optional_units is None:
        optional_overflow = False
        overflow_measurement = "unavailable"
    else:
        ceiling = combined.get("optional_unit_budget")
        optional_overflow = ceiling is not None and int(measured_optional_units) > int(ceiling)
        overflow_measurement = "measured"
    outcome_ok = actual == expected or (expected == "answer" and actual == "quote" and not missing_claims)
    if expected == "partial":
        outcome_ok = actual in {"partial", "answer", "quote"} and not missing_claims
    proof_ok = True
    if answer_like and proof_sets and not missing_claims:
        if proof_cited is False:
            proof_ok = False
    child_failures = []
    for spec in case.get("children") or []:
        if not isinstance(spec, dict):
            continue
        found = None
        for task in result.get("task_results") or []:
            if isinstance(task, dict) and task.get("id") == spec.get("id"):
                found = task.get("result") if isinstance(task.get("result"), dict) else {}
        if found is None:
            child_failures.append(spec.get("id"))
            continue
        child_case = dict(spec)
        child_case.pop("children", None)
        if not score_case(child_case, found, None, corrections)["ok"]:
            child_failures.append(spec.get("id"))
    ok = (
        outcome_ok
        and not false_assertion
        and not omission
        and not unnecessary_clarification
        and not silent_task_loss
        and not word_limit_failure
        and not budget_notes
        and not repeated
        and not optional_overflow
        and proof_ok
        and not child_failures
        and not (marker_leak)
    )
    if expected == "clarification":
        ok = appropriate_clarification and not budget_notes
    if expected in {"insufficient", "unsupported"}:
        ok = appropriate_abstention and not omission
    if expected == "conflict":
        ok = recognized_conflict
    if expected in {"blocked", "budget_refusal", "cancelled", "pending"}:
        ok = actual == expected and not marker_leak
    return {
        "scorer_version": SCORER_VERSION,
        "id": case.get("id"),
        "expected": expected,
        "actual": actual,
        "raw_status": result.get("status") or result.get("answer_status"),
        "ok": ok,
        "false_assertion": false_assertion,
        "omission": omission,
        "missing_claims": missing_claims,
        "appropriate_abstention": appropriate_abstention,
        "unnecessary_clarification": unnecessary_clarification,
        "appropriate_clarification": appropriate_clarification,
        "recognized_conflict": recognized_conflict,
        "contract_disagreement": contract_disagreement,
        "proof_cited": proof_cited,
        "proof_retrieved": proof_retrieved,
        "retrieved_then_lost": retrieved_then_lost,
        "silent_task_loss": silent_task_loss,
        "word_limit_failure": word_limit_failure,
        "budget_notes": budget_notes,
        "repeated_heading": repeated,
        "optional_overflow": optional_overflow,
        "overflow_measurement": overflow_measurement,
        "binding_contradictions": binding_contradictions,
        "forbidden_hits": forbidden,
        "excluded_from_accuracy": contract_disagreement,
    }


def _result(text: str, *, outcome="answered", evidence=None, answer=None, budget=None, tasks=None, complete=None, status=None, optional_overflow=False) -> dict:
    evidence = evidence or []
    result = {
        "answer": answer if answer is not None else text,
        "answer_status": status or outcome,
        "status": status or outcome,
        "needs_clarification": outcome == "needs_clarification",
        "audit_passed": outcome == "answered",
        "reply": {"text": text, "body": text, "answer_evidence": evidence},
        "answer_evidence": evidence,
        "judgment": {"outcome": outcome, "complete": complete},
        "optional_overflow": optional_overflow,
    }
    if budget is not None:
        result["response_plan"] = {"combined_budget": budget, "word_limit_enforced": False}
        result["request_plan"] = {"combined_budget": budget, "tasks": tasks or []}
    return result


def selftest() -> list[dict]:
    """Deliberately good and bad fixtures. None of these call the appliance."""
    fixtures = []

    def check(name, case, result, expect_ok, **flags):
        verdict = score_case(case, result, flags.pop("trace", None))
        failures = []
        if verdict["ok"] is not expect_ok:
            failures.append(f"ok {verdict['ok']} expected {expect_ok}")
        for key, value in flags.items():
            if verdict.get(key) is not value:
                failures.append(f"{key}={verdict.get(key)} expected {value}")
        fixtures.append({"name": name, "passed": not failures, "failures": failures, "verdict": verdict})

    evidence = [{"document_id": "wh-public-p0002", "text": "The Vesper is amber."}]
    check(
        "complete",
        {"id": "fix-complete", "outcome": "answer", "claims": ["amber"], "proof_sets": [["wh-public-p0002"]], "forbidden": ["cobalt-seal-771"]},
        _result("The Vesper is amber.", evidence=evidence),
        True,
        false_assertion=False,
        omission=False,
    )
    check(
        "partial",
        {"id": "fix-partial", "outcome": "partial", "claims": ["gray", "white"], "proof_sets": [["wh-public-p0008", "wh-public-p0009"]]},
        _result("The Sextant is gray.", outcome="partial", status="partial", evidence=[{"document_id": "wh-public-p0008"}], complete=False),
        False,
        omission=True,
        false_assertion=False,
    )
    check(
        "wrong_entity",
        {"id": "fix-wrong", "outcome": "answer", "claims": ["amber"], "proof_sets": [["wh-public-p0002"]], "forbidden": ["white"]},
        _result("The Nacre is white.", evidence=[{"document_id": "wh-public-p0010"}]),
        False,
        false_assertion=True,
    )
    check(
        "reversed_claim",
        {"id": "fix-reversed", "outcome": "quote", "claims": ["not blue"], "forbidden": ["is blue"]},
        _result("The Vesper is blue.", outcome="evidence_quote"),
        False,
        false_assertion=True,
    )
    check(
        "alternative_proof",
        {"id": "fix-alt", "outcome": "answer", "claims": ["17 years"], "proof_sets": [["a", "b"], ["c"]]},
        _result("The Vesper lives for 17 years.", evidence=[{"document_id": "c"}]),
        True,
        proof_cited=True,
    )
    check(
        "missing_premise",
        {"id": "fix-premise", "outcome": "answer", "claims": ["17 years"], "proof_sets": [["kind", "rule"]]},
        _result("The Vesper lives for 17 years.", evidence=[{"document_id": "kind"}]),
        False,
        proof_cited=False,
        false_assertion=False,
    )
    check(
        "conflict_quote",
        {"id": "fix-conflict", "outcome": "conflict", "claims": ["amber", "red"], "forbidden": ["cobalt-seal-771"]},
        _result("The retrieved passages do not settle that. Stored sentences conflict: The Vesper is amber. The Vesper is red.", outcome="conflicting", answer=None, status="conflicting"),
        True,
        recognized_conflict=True,
        false_assertion=False,
    )
    check(
        "clarification_options",
        {"id": "fix-clarify", "outcome": "clarification", "claims": [], "forbidden": ["Orinth"]},
        _result("Which place do you mean: Orinth or Docklane?", outcome="needs_clarification", answer=None, status="needs_clarification"),
        True,
        appropriate_clarification=True,
        false_assertion=False,
    )
    check(
        "private_marker",
        {"id": "fix-leak", "outcome": "insufficient", "forbidden": ["cobalt-seal-771"]},
        _result("The seal code is cobalt-seal-771.", outcome="insufficient_evidence", answer=None, status="insufficient_evidence"),
        False,
        false_assertion=True,
    )
    check(
        "aggregate_partial",
        {"id": "fix-aggregate", "outcome": "partial", "claims": ["gray", "white"], "proof_sets": [["s", "a"]]},
        {
            "answer": None,
            "audit_passed": False,
            "status": "partial",
            "answer_status": "partial",
            "reply": {"text": "1. The Sextant is gray.\n\n2. The Astrolabe is white.", "body": "1. The Sextant is gray.\n\n2. The Astrolabe is white."},
            "answer_evidence": [{"document_id": "s"}, {"document_id": "a"}],
            "judgment": {"schema": "request-judgment-v1", "outcome": "partial", "complete": False},
            "request_plan": {"tasks": [{"id": "q1", "query": "What color is the Sextant?"}, {"id": "q2", "query": "What color is the Astrolabe?"}]},
        },
        True,
        repeated_heading=False,
    )
    long_proof = (
        "The Helion is a survey telescope. Every survey telescope lives for 22 years. "
        "The membership and the universal rule are both required, so this answer is longer than one sentence."
    )
    check(
        "proof_exceeds_budget",
        {"id": "fix-proof-budget", "outcome": "answer", "claims": ["22 years", "survey telescope"], "proof_sets": [["h", "r"]], "budget": {"hard_limit": False, "word_limit_enforced": False, "proof_may_exceed": True}},
        _result(long_proof, evidence=[{"document_id": "h"}, {"document_id": "r"}], budget={"optional_unit_budget": 1, "hard_limit": False, "word_limit_enforced": False, "task_allocations": {"q1": 1}}),
        True,
        word_limit_failure=False,
    )
    check(
        "runtime_overflow_flag_is_not_a_measurement",
        {"id": "fix-optional-flag", "outcome": "answer", "claims": ["amber"], "proof_sets": [["wh-public-p0002"]], "forbidden": []},
        _result("The Vesper is amber.", evidence=evidence, optional_overflow=True),
        True,
        optional_overflow=False,
        overflow_measurement="unavailable",
        false_assertion=False,
    )
    flag_only = score_case(
        {"id": "fix-measured-overflow", "outcome": "answer", "claims": ["amber"], "proof_sets": [["wh-public-p0002"]], "budget": {"optional_unit_budget": 1}},
        _result("The Vesper is amber.", evidence=evidence, budget={"optional_unit_budget": 1, "task_allocations": {"q1": 1}}),
        measured_optional_units=2,
    )
    fixtures.append({
        "name": "optional_exceeds_ceiling",
        "passed": flag_only["ok"] is False and flag_only["optional_overflow"] is True and flag_only["overflow_measurement"] == "measured",
        "failures": [] if flag_only["ok"] is False else [flag_only],
        "verdict": flag_only,
    })
    check(
        "silent_omission",
        {"id": "fix-silent", "outcome": "partial", "claims": ["gray", "white"], "proof_sets": [["s", "a"]]},
        _result("The Sextant is gray.", outcome="answered", complete=True, evidence=[{"document_id": "s"}]),
        False,
        silent_task_loss=True,
        omission=True,
        false_assertion=False,
    )
    color = {"subject": "Helion", "relation": "has_color", "object": "gray", "direction": "subject", "polarity": "affirmative", "quantifier": "direct"}
    check(
        "binding_match",
        {"id": "fix-bind-match", "outcome": "answer", "claims": ["gray"], "bindings": [color], "proof_sets": [["helion-color"]]},
        _result("The Helion is gray.", evidence=[{"document_id": "helion-color"}]),
        True,
        false_assertion=False,
        omission=False,
    )
    check(
        "binding_wrong_entity",
        {"id": "fix-bind-entity", "outcome": "answer", "claims": ["gray"], "bindings": [color], "proof_sets": [["helion-color"]]},
        _result("The Nacre is gray.", evidence=[{"document_id": "helion-color"}]),
        False,
        false_assertion=True,
    )
    check(
        "binding_wrong_relation",
        {"id": "fix-bind-relation", "outcome": "answer", "claims": ["gray"], "bindings": [color], "proof_sets": [["helion-color"]]},
        _result("The Helion has gray.", evidence=[{"document_id": "helion-color"}]),
        False,
        false_assertion=True,
    )
    check(
        "binding_reversed_direction",
        {"id": "fix-bind-direction", "outcome": "answer", "bindings": [{"subject": "Sextant", "relation": "lives_in", "object": "Orinth", "direction": "subject", "polarity": "affirmative", "quantifier": "direct"}], "proof_sets": [["place"]]},
        _result("Orinth is found in the Sextant.", evidence=[{"document_id": "place"}]),
        False,
        false_assertion=True,
    )
    check(
        "binding_negated_claim",
        {"id": "fix-bind-negated", "outcome": "answer", "claims": ["gray"], "bindings": [color], "proof_sets": [["helion-color"]]},
        _result("The Helion is not gray.", evidence=[{"document_id": "helion-color"}]),
        False,
        false_assertion=True,
    )
    check(
        "binding_licensed_every_join",
        {"id": "fix-bind-every", "outcome": "answer", "bindings": [{"subject": "Kestrel", "relation": "has_lifespan", "object": "19 years", "direction": "subject", "polarity": "affirmative", "quantifier": "direct"}], "proof_sets": [["kind", "rule"]]},
        _result("From kind:\nThe Kestrel is a survey skiff.\nFrom rule:\nEvery survey skiff lives for 19 years.", evidence=[{"document_id": "kind"}, {"document_id": "rule"}]),
        True,
        false_assertion=False,
        omission=False,
    )
    check(
        "binding_every_without_membership",
        {"id": "fix-bind-every-bare", "outcome": "answer", "bindings": [{"subject": "Kestrel", "relation": "has_lifespan", "object": "19 years", "direction": "subject", "polarity": "affirmative", "quantifier": "direct"}], "proof_sets": [["rule"]]},
        _result("Every survey skiff lives for 19 years.", evidence=[{"document_id": "rule"}]),
        False,
        false_assertion=True,
    )
    check(
        "binding_unlicensed_quantifier",
        {"id": "fix-bind-some", "outcome": "answer", "bindings": [{"subject": "Nacre", "relation": "has", "object": "beacon", "direction": "subject", "polarity": "affirmative", "quantifier": "direct"}], "proof_sets": [["some-beacon"]]},
        _result("Some display rovers have a beacon.", evidence=[{"document_id": "some-beacon"}]),
        False,
        false_assertion=True,
    )
    check(
        "retrieval_only_proof",
        {"id": "fix-related", "outcome": "answer", "claims": ["gray"], "bindings": [color], "proof_sets": [["helion-color"]]},
        {"answer": "The Helion is gray.", "answer_status": "answered", "status": "answered", "audit_passed": True, "reply": {"text": "The Helion is gray.", "body": "The Helion is gray."}, "related": [{"document_id": "helion-color"}], "retrieved_candidates": [{"document_id": "helion-color"}]},
        False,
        proof_cited=False,
        false_assertion=False,
    )
    check(
        "missing_budget_metadata",
        {"id": "fix-budget-missing", "outcome": "answer", "claims": ["amber"], "proof_sets": [["wh-public-p0002"]], "budget": {"task_allocations": {"q1": 1}}},
        _result("The Vesper is amber.", evidence=evidence),
        False,
    )
    check(
        "child_related_is_not_proof",
        {"id": "fix-child-related", "outcome": "partial", "claims": ["gray"], "proof_sets": [["child-gold"]], "children": [{"id": "q2", "outcome": "answer", "bindings": [color], "proof_sets": [["child-gold"]]}]},
        {"answer": None, "audit_passed": False, "status": "partial", "answer_status": "partial", "reply": {"text": "The Sextant is gray."}, "answer_evidence": [], "task_results": [{"id": "q2", "result": {"answer": "The Helion is gray.", "answer_status": "answered", "reply": {"text": "The Helion is gray."}, "related": [{"document_id": "child-gold"}]}}], "judgment": {"outcome": "partial", "complete": False}},
        False,
        proof_cited=False,
    )
    place = {"subject": "Sextant", "relation": "lives_in", "object": "Orinth", "direction": "subject", "polarity": "affirmative", "quantifier": "direct"}
    check(
        "child_words_do_not_answer_the_parent",
        {"id": "fix-child-pool", "outcome": "partial", "claims": ["Orinth"], "bindings": [place], "proof_sets": [["sextant-place"]], "children": [{"id": "q2", "outcome": "answer", "claims": ["yellow"], "bindings": [{"subject": "Azimuth", "relation": "has_color", "object": "yellow", "direction": "subject", "polarity": "affirmative", "quantifier": "direct"}], "proof_sets": [["azimuth-color"]]}]},
        {"answer": "The Sextant is gray.", "answer_status": "partial", "status": "partial", "audit_passed": False, "reply": {"text": "The Sextant is gray."}, "answer_evidence": [], "task_results": [{"id": "q2", "result": {"answer": "The Azimuth is yellow. The Sextant is found in Orinth.", "answer_status": "answered", "reply": {"text": "The Azimuth is yellow. The Sextant is found in Orinth."}, "answer_evidence": [{"document_id": "azimuth-color"}, {"document_id": "sextant-place"}]}}], "judgment": {"outcome": "partial", "complete": False}},
        False,
        omission=True,
        proof_cited=False,
        false_assertion=False,
    )
    check(
        "retrieved_then_lost",
        {"id": "fix-lost", "outcome": "answer", "claims": ["amber"], "proof_sets": [["wh-public-p0002"]]},
        _result("I don't have enough grounded evidence to answer that confidently.", outcome="insufficient_evidence", answer=None, status="insufficient_evidence"),
        False,
        trace=[{"event": "search", "ids": ["wh-public-p0002"]}],
        proof_retrieved=True,
        retrieved_then_lost=True,
        false_assertion=False,
    )
    failed = [item["name"] for item in fixtures if not item["passed"]]
    if failed:
        raise RuntimeError(f"scorer selftest failed: {failed} {[item for item in fixtures if not item['passed']]}")
    return fixtures
