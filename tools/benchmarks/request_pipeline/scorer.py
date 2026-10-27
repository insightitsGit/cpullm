"""Score request-pipeline results. This module does not import cpu_llm."""

from __future__ import annotations

SCORER_VERSION = "request-pipeline-scorer-v1"

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


def public_fields(result: dict) -> str:
    """Text a caller can read as the answer. Diagnostics stay out."""
    reply = result.get("reply") if isinstance(result.get("reply"), dict) else {}
    parts = [
        _text(result.get("answer")),
        _text(reply.get("text")),
        _text(reply.get("body")),
        _text(reply.get("supported_text")),
    ]
    for task in result.get("task_results") or []:
        child = task.get("result") if isinstance(task, dict) else None
        if isinstance(child, dict):
            child_reply = child.get("reply") if isinstance(child.get("reply"), dict) else {}
            parts.append(_text(child.get("answer")))
            parts.append(_text(child_reply.get("text")))
            parts.append(_text(child_reply.get("body")))
    return "\n".join(part for part in parts if part)


def _walk_ids(value, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"document_id", "chunk_id", "id", "source_id"} and isinstance(item, str):
                found.add(item)
            else:
                _walk_ids(item, found)
    elif isinstance(value, list):
        for item in value:
            _walk_ids(item, found)


def evidence_ids(result: dict) -> set[str]:
    found: set[str] = set()
    for key in ("answer_evidence", "supporting_evidence", "evidence"):
        _walk_ids(result.get(key), found)
    reply = result.get("reply") if isinstance(result.get("reply"), dict) else {}
    for key in ("answer_evidence", "supporting_evidence", "evidence"):
        _walk_ids(reply.get(key), found)
    for task in result.get("task_results") or []:
        if isinstance(task, dict):
            _walk_ids(task.get("result"), found)
    return {item for item in found if item}


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


def score_case(case: dict, result: dict, trace: list[dict] | None = None, corrections: dict[str, str] | None = None) -> dict:
    """Return separated verdicts. A long required proof is not a word-limit failure."""
    corrections = corrections or {}
    expected = case.get("outcome") or "answer"
    actual = map_outcome(result)
    text = public_fields(result)
    claims = [item for item in case.get("claims") or [] if item]
    missing_claims = [claim for claim in claims if not _contains(text, claim)]
    forbidden = [item for item in case.get("forbidden") or [] if item and _contains(text, item)]
    endorsed = _endorsed(result, text)
    false_assertion = bool(forbidden) and (endorsed or any(marker in item for item in forbidden for marker in ("seal-",)))
    # A private marker is a disclosure even inside a refusal, except when the
    # refusal text does not actually contain it. Presence was already tested.
    marker_leak = any("seal-" in item for item in forbidden)
    if marker_leak:
        false_assertion = True
    proof_sets = _resolve(case.get("proof_sets") or [], corrections)
    cited = evidence_ids(result)
    retrieved = retrieval_ids(trace)
    proof_cited = _proof_hit(proof_sets, cited)
    proof_retrieved = _proof_hit(proof_sets, retrieved)
    retrieved_then_lost = proof_retrieved is True and proof_cited is False and expected in {"answer", "quote", "partial"}
    answer_like = expected in {"answer", "quote", "partial"}
    omission = bool(missing_claims) and answer_like
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
        if "task_allocations" in budget and combined.get("task_allocations") not in (None, budget["task_allocations"]):
            budget_notes.append("allocation mismatch")
        if "optional_unit_budget" in budget and combined.get("optional_unit_budget") not in (None, budget["optional_unit_budget"]):
            budget_notes.append("optional budget mismatch")
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
    optional_overflow = bool(result.get("optional_overflow"))
    outcome_ok = actual == expected or (expected == "answer" and actual == "quote" and not missing_claims)
    if expected == "partial":
        outcome_ok = actual in {"partial", "answer", "quote"} and not missing_claims
    proof_ok = True
    if answer_like and proof_sets and not missing_claims:
        if proof_cited is False:
            proof_ok = False
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
        "optional_exceeds_ceiling",
        {"id": "fix-optional", "outcome": "answer", "claims": ["amber"], "proof_sets": [["wh-public-p0002"]], "forbidden": []},
        _result("The Vesper is amber. The dock is open.", evidence=evidence, optional_overflow=True),
        False,
        optional_overflow=True,
        false_assertion=False,
    )
    check(
        "silent_omission",
        {"id": "fix-silent", "outcome": "partial", "claims": ["gray", "white"], "proof_sets": [["s", "a"]]},
        _result("The Sextant is gray.", outcome="answered", complete=True, evidence=[{"document_id": "s"}]),
        False,
        silent_task_loss=True,
        omission=True,
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
