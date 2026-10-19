"""Generate one sentence from the prompt and the stored meaning.

Model01 does not sample a new content word. The prompt chooses the task.
Each content word is copied from a licensed span. A ranking prompt adds the
stored order, or the fixed sentence that says the passages do not state one.
No checkpoint is loaded. This module does not import torch.
"""

from __future__ import annotations

from typing import Any

from cpu_llm.realizer.constructions import bundle_from_chunks
from cpu_llm.realizer.ranker import realize

MODEL_ID = "model01"
MODEL_NAME = "Model01 sentence generator"


def generate(
    question: str,
    chunks: list[tuple[str, str]],
    *,
    attributes: dict[str, dict] | None = None,
    math_result: dict | None = None,
    causal_edges: list | None = None,
    delivery_rejected: bool = False,
) -> dict[str, Any]:
    """The checked sentence for this prompt and these stored paragraphs."""
    bundle = bundle_from_chunks(
        chunks,
        attributes=attributes,
        math_result=math_result,
        causal_edges=causal_edges,
    )
    outcome = realize(bundle, question, delivery_rejected=delivery_rejected)
    outcome["model_id"] = MODEL_ID
    outcome["model_name"] = MODEL_NAME
    outcome["mode"] = "model01"
    outcome["checkpoint_id"] = None
    outcome["inputs"] = describe_inputs(question, bundle)
    return outcome


def describe_inputs(question: str, bundle: Any) -> dict[str, Any]:
    """The two inputs Model01 reads: the prompt, then the stored records."""
    evidence = []
    for record in bundle.records:
        proposition = record.proposition
        evidence.append(
            {
                "record_id": record.record_id,
                "kind": record.kind,
                "sentence": record.source,
                "roles": [span.role for span in record.spans],
                "epistemic_weight": None if proposition is None else proposition.epistemic_weight,
                "polarity": None if proposition is None else proposition.polarity.value,
            }
        )
    return {"prompt": question, "evidence": evidence}


def apply_model01(state: dict[str, Any]) -> dict[str, Any]:
    """Attach Model01's sentence. A rejected delivery stays the spoken text."""
    rejected = bool(state.get("delivery_blocked") or state.get("shine_enforced") or state.get("shine_ok") is False)
    chunks = [
        (str(item.get("chunk_id") or ""), str(item.get("chunk_text") or ""))
        for item in state.get("related") or []
        if item.get("chunk_id") and item.get("chunk_text")
    ]
    attributes = {
        document_id: item["attributes"]
        for item in state.get("related") or []
        if isinstance(item.get("attributes"), dict)
        for document_id in [str(item.get("chunk_id") or "")]
        if document_id
    }
    outcome = generate(
        str(state.get("message") or ""),
        chunks,
        attributes=attributes or None,
        math_result=state.get("math_result") if isinstance(state.get("math_result"), dict) else None,
        delivery_rejected=rejected,
    )
    update: dict[str, Any] = {"model01": outcome}
    if rejected or _leave_reply(state) or not outcome.get("text"):
        return update
    reply = dict(state.get("reply") or {})
    reply["text"] = outcome["text"]
    update["reply"] = reply
    return update


def _leave_reply(state: dict[str, Any]) -> bool:
    """Keep a reply another agent already filled and Model01 does not know."""
    flags = ("finance", "summarize", "explain", "list", "sources", "deep", "creative", "compare", "draft")
    if any(state.get(flag) is True for flag in flags):
        return True
    return bool(state.get("possibilities") or state.get("comparison") or state.get("imagination") or state.get("brief"))
