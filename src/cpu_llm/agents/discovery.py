"""Discovery Loop, stages 1 through 4.

The agent records what the turn already established. It does not add a
conclusion, and it does not call a model. Stage 5 was not in the protocol
text that defined this agent, so the loop stops before scale shifting.
"""

from __future__ import annotations

import re
from typing import Any

PROTOCOL_VERSION = "1.0"
INVARIANT = "Reality and evidence have the final veto."

_PERSPECTIVES: dict[str, tuple[str, ...]] = {
    "individual_humans": ("human", "person", "patient", "individual"),
    "groups": ("society", "group", "community"),
    "institutions": ("institution", "government", "agency"),
    "artificial_agents": ("agent",),
    "animals": ("animal", "species"),
    "ecosystems": ("ecosystem", "ecology"),
    "engineered_systems": ("machine", "engine", "device"),
    "planetary": ("planet", "cosmic", "climate"),
}


def run_discovery(state: dict[str, Any]) -> dict[str, Any]:
    claim = state.get("message") or ""
    related = list(state.get("related") or [])
    questions = [str(item) for item in state.get("gather_questions") or []]
    evidence_text = " ".join(item.get("chunk_text") or "" for item in related)
    return {
        "protocol": "discovery-loop",
        "version": PROTOCOL_VERSION,
        "invariant": INVARIANT,
        "stages_completed": [1, 2, 3, 4],
        "stopped_before": "Stage 5: Scale Shifting",
        "claim": _claim(claim, related, state),
        "assumptions": _assumptions(state),
        "information": _information(claim, related, questions, state),
        "perspectives": _perspectives(f"{claim} {evidence_text}"),
    }


def _claim(claim: str, related: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": claim,
        "true_if": [
            "A proposition paired with the retrieved tensor is realized and the auditor accepts the sentence.",
            "Every number in that sentence matches a PrismManifest evidence span.",
        ],
        "false_if": [
            "The prompt is blocked.",
            "Deliberation reports a contradiction.",
            "The sentence contains a number that is not an evidence span.",
            "PrismThinker returns refuse.",
        ],
        "scope": {
            "tenant_id": state.get("tenant_id") or "cpu-llm",
            "evidence_ids": [item.get("chunk_id") for item in related],
        },
    }


def _assumptions(state: dict[str, Any]) -> list[dict[str, str]]:
    items = [
        {
            "kind": "technical",
            "text": "Retrieval rank is topical relevance. It is not authority.",
        }
    ]
    if state.get("cognition_status") == "needs_evidence_propositions":
        items.append(
            {
                "kind": "logical",
                "text": "A retrieved chunk is not a proposition, and it is not treated as one.",
            }
        )
    if state.get("grammar_span_ids"):
        items.append(
            {
                "kind": "mathematical",
                "text": "A number in the sentence is allowed only when its canonical value matches an evidence span.",
            }
        )
    if state.get("thinker_directive") == "gather":
        items.append(
            {
                "kind": "empirical",
                "text": "An unresolved gather question is missing information, not an observation.",
            }
        )
    return items


def _information(
    claim: str,
    related: list[dict[str, Any]],
    questions: list[str],
    state: dict[str, Any],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        {"kind": "hypothesis", "text": claim, "provenance": "user"},
    ]
    for item in related:
        rows.append(
            {
                "kind": "reported",
                "text": item.get("chunk_text") or "",
                "provenance": str(item.get("chunk_id") or "vectorprism"),
            }
        )
    status = state.get("cognition_status")
    if status == "deliberated" and state.get("abstention_triggered"):
        rows.append(
            {
                "kind": "unknown",
                "text": state.get("answer") or "",
                "provenance": "deliberation",
            }
        )
    elif status == "deliberated" and state.get("answer"):
        kind = "interpretation" if float(state.get("ruin_distance") or 0) == 0 else "unknown"
        rows.append({"kind": kind, "text": state.get("answer") or "", "provenance": "realizer"})
    for question in questions:
        rows.append({"kind": "unknown", "text": question, "provenance": "prismthinker"})
    return rows


def _perspectives(text: str) -> list[dict[str, str]]:
    folded = text.casefold()
    selected: list[dict[str, str]] = []
    for name, words in _PERSPECTIVES.items():
        hits = [word for word in words if re.search(rf"\b{re.escape(word)}\b", folded)]
        if hits:
            selected.append({"perspective": name, "named_in_evidence": ", ".join(hits)})
    return selected
