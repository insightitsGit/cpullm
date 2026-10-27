"""Choose a derivation the grammar already listed.

No checkpoint is shipped. One legal derivation is spoken as written. Several
legal derivations break ties by construction id. Uniform scores, used only in
tests, stay inside that same set. An untrained file is refused.

The question selects the plan. It is not a span, and a retrieval score is not
a ranking. A ranking question always keeps the licensed clause and a ranking
clause: a copied stored order, or the grammar sentence that says no order is
stored. Scores are not asked to choose that clause, and they cannot drop it.
"""

from __future__ import annotations

from typing import Any
from dataclasses import replace

from cpu_llm.ranking import ranking_question
from cpu_llm.realizer.constructions import attach_ranking, bundle_from_chunks, derivations_for, plan_for
from cpu_llm.realizer.derivation_check import check_passage
from cpu_llm.realizer.evidence_schema import SCHEMA, Bundle, Derivation, replay

CHECKPOINT_ID = None


class UntrainedCheckpoint(RuntimeError):
    """A realization checkpoint is not loaded, and a fresh one is not served."""


def load_checkpoint(_path: str) -> None:
    raise UntrainedCheckpoint("no trained realization checkpoint is shipped")


def select(alternatives: list[Derivation], scores: list[float] | str | None = None) -> Derivation | None:
    """The chosen derivation is always one of ``alternatives``."""
    if not alternatives:
        return None
    if len(alternatives) == 1 or scores is None:
        return _tie(alternatives)
    if scores == "uniform":
        return _tie(alternatives)
    if not isinstance(scores, list) or len(scores) != len(alternatives):
        return _tie(alternatives)
    ranked = sorted(range(len(alternatives)), key=lambda index: (-scores[index], _key(alternatives[index])))
    return alternatives[ranked[0]]


def realize(
    bundle: Bundle,
    question: str,
    *,
    account: bool = False,
    scores: list[float] | str | None = None,
    delivery_rejected: bool = False,
) -> dict[str, Any]:
    """The checked passage for this plan. A rejected delivery is not replaced."""
    plan = plan_for(bundle, question, account=account)
    mode = "deterministic_fallback" if CHECKPOINT_ID is None else "evidence_neural"
    if delivery_rejected:
        return _result(plan, "blocked", "", False, mode, ["delivery was already rejected"])
    if not account:
        from cpu_llm.answerability import assess
        from cpu_llm.realizer.constructions import _quote_record, _ids_plan

        rows = []
        for index, passage in enumerate(bundle.passages):
            document_id = next((record.document_id for record in bundle.records
                                if record.source and record.source in passage), f"passage-{index}")
            rows.append({"document_id": document_id, "text": passage})
        decision = assess(question, rows)
        if decision is not None:
            if decision["answer_status"] == "needs_clarification":
                return _result(plan, "needs_clarification", "", False, mode, ["needs_clarification"])
            if decision["answer_status"] != "answered":
                status = "conflicting" if decision["answer_status"] == "conflicting" else "missing"
                return _result(plan, status, decision["text"], False, mode, [status])
            records = []
            for index, evidence in enumerate(decision["answer_evidence"]):
                record = _quote_record(f"query-{index}-{evidence['document_id']}", evidence["span"])
                if record is not None:
                    records.append(replace(record, document_id=evidence["document_id"]))
            bundle = replace(bundle, records=tuple(records))
            plan = _ids_plan(bundle, question, "question", [record.record_id for record in records])
    groups = [] if plan.status != "answered" else derivations_for(bundle, plan)
    chosen: list[Derivation] = []
    for group in groups:
        pick = select(group, scores)
        if pick is not None:
            chosen.append(pick)
    if plan.status == "answered" and plan.record_ids and len(chosen) != len(plan.record_ids):
        return _result(plan, "blocked", plan.non_answer, False, mode, ["a licensed record had no legal derivation"])
    spoken = " ".join(replay(item.actions) for item in chosen)
    if ranking_question(question):
        attached = attach_ranking(bundle, plan, question, spoken)
        if attached is not None:
            bundle, plan, derivation = attached
            chosen.append(derivation)
    if plan.status != "answered" and not chosen:
        return _result(plan, plan.status, plan.non_answer, False, mode, [plan.status or "missing"])
    reasons = check_passage(bundle, plan, chosen)
    if reasons:
        return _result(plan, "blocked", "", False, mode, reasons)
    clauses = [replay(item.actions) for item in chosen]
    if plan.non_answer:
        clauses.append(plan.non_answer)
    text = " ".join(clause for clause in clauses if clause).strip()
    if not text:
        return _result(plan, "missing", "No verified epistemic evidence available.", False, mode, ["missing"])
    if plan.status != "answered":
        return _result(plan, plan.status, text, False, mode, [plan.status or "missing"], chosen)
    return _result(plan, "answered", text, True, mode, [], chosen)


def apply_realization(
    state: dict[str, Any],
    *,
    realization: str,
    account: bool,
    memory: Any | None = None,
    causal_edges: list | None = None,
) -> dict[str, Any]:
    """Attach the checked passage. The default reply is left untouched by the caller."""
    rejected = _delivery_rejected(state)
    bundle = _bundle_from_state(state, memory=memory, causal_edges=causal_edges or [])
    outcome = realize(
        bundle,
        str(state.get("message") or ""),
        account=account,
        delivery_rejected=rejected,
    )
    if realization == "evidence_neural":
        outcome["mode"] = "deterministic_fallback"
    else:
        outcome["mode"] = "deterministic"
    update: dict[str, Any] = {"realization_result": outcome}
    if rejected or not _speaks(state, realization, account, outcome):
        if rejected:
            reply = state.get("reply") or {}
            outcome["text"] = str(reply.get("text") or "")
            outcome["verified"] = False
            outcome["candidate_text"] = ""
        return update
    reply = dict(state.get("reply") or {})
    reply["text"] = outcome["text"]
    update["reply"] = reply
    return update


def _speaks(state: dict[str, Any], realization: str, account: bool, outcome: dict[str, Any]) -> bool:
    reply = state.get("reply") or {}
    if reply.get("answer_status") in {"insufficient_evidence", "conflicting", "evidence_quote", "answered"}:
        return False
    if outcome["status"] not in {"answered", "missing", "ambiguous", "conflicting", "unsupported"}:
        return False
    if not outcome["text"]:
        return False
    if _other_agent(state):
        return False
    if account:
        return True
    return realization == "evidence_neural" and (state.get("frame") is True or state.get("math") is True)


def _bundle_from_state(state: dict[str, Any], *, memory: Any | None, causal_edges: list) -> Bundle:
    chunks: list[tuple[str, str]] = []
    attributes: dict[str, dict] = {}
    for item in state.get("related") or []:
        document_id = str(item.get("chunk_id") or "")
        text = str(item.get("chunk_text") or "")
        if not document_id or not text:
            continue
        chunks.append((document_id, text))
        stored = _stored_attributes(memory, text)
        supplied = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
        attributes[document_id] = {**stored, **supplied}
    return bundle_from_chunks(
        chunks,
        attributes=attributes,
        math_result=state.get("math_result") if isinstance(state.get("math_result"), dict) else None,
        causal_edges=causal_edges,
    )


def _stored_attributes(memory: Any | None, chunk_text: str) -> dict:
    if memory is None or not hasattr(memory, "find_node_by_label") or not hasattr(memory, "all_nodes"):
        return {}
    node_id = memory.find_node_by_label(chunk_text)
    if node_id is None:
        return {}
    for node in memory.all_nodes():
        if node.id == node_id and node.label == chunk_text:
            raw = getattr(node, "attributes", None) or {}
            return dict(raw)
    return {}


def _delivery_rejected(state: dict[str, Any]) -> bool:
    if state.get("delivery_blocked") or state.get("shine_enforced"):
        return True
    return state.get("shine_ok") is False


def _other_agent(state: dict[str, Any]) -> bool:
    if any(state.get(flag) is True for flag in ("deep", "creative", "compare", "summarize", "explain", "list", "sources")):
        return True
    return bool(state.get("possibilities") or state.get("comparison") or state.get("imagination") or state.get("brief"))


def _result(
    plan,
    status: str,
    text: str,
    verified: bool,
    mode: str,
    reasons: list[str],
    chosen: list[Derivation] | None = None,
) -> dict[str, Any]:
    chosen = chosen or []
    bindings = []
    for derivation in chosen:
        for action in derivation.actions:
            if action.kind != "COPY":
                continue
            bindings.append(
                {
                    "span_id": action.span_id,
                    "role": action.role,
                    "text": action.surface,
                    "record_id": derivation.record_id,
                }
            )
    return {
        "status": status,
        "mode": mode,
        "text": text if verified or status in {"missing", "ambiguous", "conflicting", "unsupported"} else "",
        "candidate_text": text if verified else "",
        "verified": verified,
        "plan_id": plan.plan_id,
        "construction_version": SCHEMA,
        "model_checkpoint_id": CHECKPOINT_ID,
        "construction_ids": [item.construction_id for item in chosen],
        "evidence_ids": [item.record_id for item in chosen],
        "span_bindings": bindings,
        "reason_codes": reasons,
        "realization_verified": verified,
    }


def _tie(alternatives: list[Derivation]) -> Derivation:
    return min(alternatives, key=_key)


def _key(derivation: Derivation) -> tuple[str, str]:
    return (derivation.construction_id, derivation.derivation_id)
