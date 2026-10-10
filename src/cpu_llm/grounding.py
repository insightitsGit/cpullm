"""PrismShine verdict over the retrieved paragraphs and any realized sentence.

The Tier-4 judge stays off. Tier-3 span ONNX stays off until its artifact is
exported; handbook signatures and the numeric copy check still run.
"""

from __future__ import annotations

from typing import Any

from prismshine.config import ShineConfig
from prismshine.dropin import should_halt
from prismshine.evidence.builder import bundle_from_dict
from prismshine.gate import ShineGate

SHINE_FALLBACK = "I don't have enough grounded evidence to answer that confidently."


def shine_gate() -> ShineGate:
    return ShineGate.build(
        profile="default",
        strictness="standard",
        judge=None,
        config=ShineConfig(judge_provider=None, disable_tier3=True),
    )


def verify_grounding(
    gate: ShineGate,
    *,
    question: str,
    answer: str | None,
    related: list[dict[str, Any]],
    query_category: str | None,
    abstention: bool,
) -> dict[str, Any]:
    preload = [
        {
            "chunk_id": str(item["chunk_id"]),
            "text": str(item["chunk_text"]),
            "source": "retrieval",
            "retrieval_score": float(item["score"]) if item.get("score") is not None else None,
            "metadata": {"category": item.get("category")},
        }
        for item in related
        if str(item.get("chunk_text") or "").strip()
    ]
    if not preload:
        preload = [{"chunk_id": "empty", "text": "(no preload)", "source": "system"}]
    trace = []
    if not related:
        trace.append(
            {
                "hop": "retrieve",
                "kind": "retrieval",
                "status": "empty",
                "scores": {},
                "detail": {"n_chunks": 0, "top_k": 5},
            }
        )
    else:
        categories = [item.get("category") for item in related if item.get("category")]
        chunk_category = categories[0] if categories else None
        if query_category:
            for category in categories:
                if category != query_category:
                    chunk_category = category
                    break
        scores = [float(item["score"]) for item in related if item.get("score") is not None]
        trace.append(
            {
                "hop": "retrieve",
                "kind": "retrieval",
                "status": "ok",
                "scores": {"constructive_score": max(scores) if scores else 0.0},
                "detail": {
                    "n_chunks": len(related),
                    "top_k": 5,
                    "category": chunk_category,
                    "rule_chain": [{"category": category} for category in categories],
                },
            }
        )
    bundle, feedback = bundle_from_dict(
        {
            "run_id": "cpu-llm",
            "tenant_id": "cpu-llm",
            "question": question or " ",
            "answer": answer,
            "preload": preload,
            "trace": trace,
            "node_state": {"query_category": query_category} if query_category else {},
            "declared_sections": ["must_ground"],
        }
    )
    verdict = gate.verify(bundle)
    halted = should_halt(verdict, "block")
    delivered = answer
    if halted and answer and not abstention:
        delivered = SHINE_FALLBACK
    return {
        "shine_decision": verdict.decision,
        "shine_resolution_gate": verdict.resolution_gate,
        "shine_signatures": [hit.id for hit in verdict.signatures],
        "shine_ok": not halted,
        "shine_enforced": bool(halted and answer and not abstention),
        "answer": delivered,
        "shine_notes": feedback,
    }
