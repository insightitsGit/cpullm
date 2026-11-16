"""Explicit Nammade scan over the caller's authorized snapshot.

``Nammade: <query>`` or ``ask(..., nammade=True)`` runs the equilibrium node.
The reply quotes relevant stored spans. Channel labels stay in the diagnostic
receipt, and strict evidence mode does not run this route.
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np

from cpu_llm.nammade.encode import EncodedSpan, encode_chunk, encode_query
from cpu_llm.nammade.node import NammadeEquilibriumNode
from cpu_llm.nammade.store import store_spans
from cpu_llm.nammade.types import NammadeEvaluation, ResourceBudget

_COMMAND = re.compile(
    r"^(?:please\s+)?nammade(?:\s+equilibrium)?\s*:\s*(.*?)\s*$",
    re.IGNORECASE,
)
_RESEARCH = re.compile(
    r"^(?:please\s+)?(?:(?:can|could|would) you\s+)?"
    r"(?:research\s+(?!report\b|article\b|paper\b)|investigate\s+)(.+)$",
    re.IGNORECASE,
)
DISCLAIMER = (
    "Nammade equilibrium scan. Channel labels compare the query with stored spans. "
    "They do not verify a physical law."
)


def nammade_seed(message: str, *, forced: bool = False) -> str | None:
    """Return the query text, ``''`` when the subject is missing, or None for another route."""
    text = (message or "").strip().rstrip(".!?").strip()
    match = _COMMAND.fullmatch(text)
    if match:
        return match.group(1).strip()
    return text if forced else None


def research_scan_seed(message: str) -> str | None:
    match = _RESEARCH.fullmatch(message.strip())
    return match[1].strip().rstrip(".!?") if match else None


def attach_research_scan(app, response, message, query, *, caller, as_of, kappa, snapshot=None):
    """Attach a diagnostic receipt without changing the research outcome or proof."""
    if not query or response.get("answer_status") not in {
        "answered", "evidence_quote", "hypotheses", "research_question", "partial", "insufficient_evidence",
    }:
        return response
    scan = execute_nammade(app, message, query, caller=caller, as_of=as_of, kappa=kappa, _source_snapshot=snapshot)
    if "nammade" in scan:
        response["nammade"] = dict(scan["nammade"], mode="research_diagnostics", outcome=scan["answer_status"])
        stages = response.setdefault("routing", {}).setdefault("post_stages", [])
        if "nammade_equilibrium" not in stages:
            stages.append("nammade_equilibrium")
    return response


def evaluation_record(item: NammadeEvaluation) -> dict[str, Any]:
    record = {
        "source_id": item.source_id,
        "span_text": item.span_text,
        "span_hash": item.span_hash,
        "regime": item.regime.value,
        "claim": claim_label(item.candidate_density),
        "displacement_norm": item.displacement_norm,
        "volumetric_residual": item.volumetric_residual,
        "cycle_phase_ratio": item.cycle_phase_ratio,
        "candidate_density": item.candidate_density,
        "is_polarity_bridge": item.is_polarity_bridge,
    }
    if item.dense_similarity is not None:
        record["dense_similarity"] = item.dense_similarity
    return record


def claim_label(density: float) -> str:
    """Name the ingestion band. The name is a label, not a physical measurement."""
    if density <= -10:
        return "frontier"
    if density <= -5:
        return "prediction"
    if density < 0:
        return "hypothesis"
    if density >= 10:
        return "invariant"
    if density >= 4:
        return "measured"
    return "source statement"


def _reply(query, kappa: float, frame: dict[str, Any], skipped: int) -> str:
    lines = [
        DISCLAIMER,
        (
            f"Query channel: a={query.a:.6g} b={query.b:.6g} c={query.c:.6g} "
            f"d={query.d:.6g} kappa={kappa:.6g}"
        ),
        f"Frontier status: {frame['nammade_frontier_status'].value}",
        f"Static equilibrium: {'yes' if frame['has_static_equilibrium'] else 'no'}",
        f"Polarity bridges: {frame['polarity_bridges_found']}",
    ]
    evaluations = frame["nammade_evaluations"]
    if not evaluations:
        lines.append("No evaluation was emitted.")
    for item in evaluations:
        bridge = "polarity bridge" if item.is_polarity_bridge else "no polarity bridge"
        dense = "" if item.dense_similarity is None else f" dense={item.dense_similarity:.4f}"
        lines.append(
            f"[{item.source_id}] {item.regime.value} claim={claim_label(item.candidate_density)}{dense} "
            f"residual={item.volumetric_residual:.6g} distance={item.displacement_norm:.6g} "
            f"density={item.candidate_density:.6g} {bridge}"
        )
        lines.append(f"“{item.span_text}”")
    if skipped:
        lines.append(f"Skipped {skipped} explicit span{'s' if skipped != 1 else ''} that failed the channel contract.")
    relations = frame.get("nammade_word_relations") or []
    if relations:
        lines.append("Word relations from the Nammade channel:")
    for item in relations:
        bridge = " polarity bridge" if item.get("polarity_bridge") else ""
        lines.append(
            f"{item['left']} {item['kind']} {item['right']} "
            f"a={item['a']:.6g} b={item['b']:.6g} c={item['c']:.6g} d={item['d']:.6g}{bridge}"
        )
    return "\n".join(lines)


def _word_relations(spans: list[EncodedSpan], query: str) -> list[dict[str, Any]]:
    from cpu_llm.channels import _content_words
    from cpu_llm.nammade.relations import relations_for_query

    return relations_for_query(spans, _content_words(query))


def _dense_scores(app, query: str, spans: list[EncodedSpan], *, allowed, as_of) -> dict[str, float] | None:
    """Cosine of each lexical span the trained dense core placed in the shortlist.

    ``None`` means this caller has no encoder, so the residual cap remains the gate.
    An empty dict means the encoder ran and no lexical span was retrieved.
    """
    if not any(not span.explicit for span in spans):
        return None
    index = getattr(app, "index", None)
    search = getattr(index, "search" if allowed is None else "search_allowed", None)
    encode_query = getattr(index, "encode_query", None)
    if not callable(search) or not callable(encode_query):
        return None
    try:
        query_tensor = encode_query(query)
        scope = () if allowed is None else (allowed,)
        hits = search(query, *scope, top_k=32, query_tensor=query_tensor, as_of=as_of)
    except (TypeError, ValueError, RuntimeError, OSError):
        return None
    if not isinstance(hits, list):
        return None
    from cpu_llm.pipeline import _dense_similarity

    scores: dict[str, float] = {}
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        document_id = str(hit.get("document_id") or "")
        cosine = _dense_similarity(query_tensor, hit.get("tensor_1024d"))
        if document_id and cosine is not None:
            scores[document_id] = cosine
    return scores


def execute_nammade(
    app,
    message: str,
    query: str,
    *,
    caller=None,
    as_of=None,
    strict: bool = False,
    kappa: float = 1.0,
    budget: ResourceBudget | None = None,
    _source_snapshot=None,
    _snapshot_only: bool = False,
) -> dict[str, Any]:
    from cpu_llm.invention import _snapshot
    from cpu_llm.pipeline import _caller_for

    def result(status: str, body: str, **receipt: Any) -> dict[str, Any]:
        response = {
            "message": message,
            "tenant_id": app.tenant_id,
            "status": status,
            "answer_status": status,
            "answer": None,
            "answer_evidence": [],
            "audit_passed": False,
            "reply": {"text": body, "body": body},
            "needs_clarification": status == "needs_clarification",
        }
        if receipt:
            response["nammade"] = {"triggered": True, "node": "nammade_equilibrium", **receipt}
            response["routing"] = {"post_stages": ["nammade_equilibrium"]}
        return response

    context = _caller_for(app, caller)
    allowed = None if context is None else context.allowed_sources
    if app.guard.check(message).decision != "allow" or (allowed is not None and not allowed):
        return result("blocked", "Request blocked.")
    if strict:
        return result("unsupported", "Strict evidence mode disables the Nammade equilibrium scan.")
    if not query or len(query) > 1000:
        return result("needs_clarification", "Name the proposition to compare with the Nammade channel.")
    try:
        from cpu_llm.nammade.channel import require_kappa

        stiffness = require_kappa(kappa)
    except ValueError:
        return result("needs_clarification", "Nammade stiffness kappa must be a finite number greater than 0.")

    import psycopg

    try:
        rows, when = _snapshot(app, allowed, as_of) if _source_snapshot is None else _source_snapshot
    except (RuntimeError, ValueError, psycopg.Error):
        return result("partial", "The Nammade source snapshot is unavailable.", evaluations=[], as_of=None)

    spans: list[EncodedSpan] = []
    skipped = 0
    for row in rows:
        try:
            spans.append(encode_chunk(row["document_id"], row["chunk_text"]))
        except (ValueError, KeyError, TypeError):
            skipped += 1
    query_channel = encode_query(query)
    from cpu_llm.retrieval import DENSE_CORE_FLOOR

    from cpu_llm.channels import _content_words

    scores = None if _snapshot_only else _dense_scores(app, query, spans, allowed=allowed, as_of=when)

    def topic_words(text):
        words = set(_content_words(text))
        if "κ" in text or "kappa" in words:
            words.add("stiffness")
        if {"scalar", "equilibrium", "condition"} <= words:
            words.add("residual")
        if "root" in words or "roots" in words:
            words.add("vanish")
        return words - {"what", "why", "how", "role", "could", "does"}

    topic = topic_words(query)
    overlap = {span.source_id: len(topic & topic_words(span.span_text)) for span in spans}
    from cpu_llm.research_hypotheses import sidm_boundary_option

    boundary = sidm_boundary_option(query, rows)
    boundary_ids = {item["document_id"] for item in boundary["premises"]} if boundary else set()
    spans = [
        span for span in spans if span.explicit
        or (any(line.strip() and not line.lstrip().startswith("#") for line in span.span_text.splitlines())
            and (span.source_id in boundary_ids or overlap[span.source_id]
                 or (scores or {}).get(span.source_id, 0) >= DENSE_CORE_FLOOR))
    ]
    if spans:
        channels = np.stack([span.channel.as_channel_vec() for span in spans]).astype(np.float32, copy=False)
    else:
        channels = np.zeros((0, 4), dtype=np.float32)
    metadata = []
    for span in spans:
        row: dict[str, Any] = {
            "source_id": span.source_id,
            "span_text": span.span_text,
            "span_hash": span.span_hash,
        }
        if not span.explicit:
            cosine = (scores or {}).get(span.source_id)
            row["dense_gated"] = True
            row["force_admit"] = True
            row["topic_overlap"] = overlap[span.source_id]
            row["boundary_premise"] = span.source_id in boundary_ids
            if cosine is not None:
                row["dense_similarity"] = cosine
        metadata.append(row)
    incoming: dict[str, Any] = {
        "nammade_query_channel": query_channel,
    }
    frame = NammadeEquilibriumNode(
        {"nammade_channels": channels, "metadata": metadata},
        kappa=stiffness,
    ).execute(incoming, budget or ResourceBudget())
    stored = False
    connection = getattr(getattr(app, "index", None), "db", None)
    connection = getattr(connection, "conn", None)
    if not _snapshot_only and connection is not None and spans:
        stored = store_spans(connection, spans)
    evaluations = [evaluation_record(item) for item in frame["nammade_evaluations"]]
    selected_ids = {item["source_id"] for item in evaluations}
    relations = _word_relations([span for span in spans if span.source_id in selected_ids], query)
    frame["nammade_word_relations"] = relations
    evidence = [
        dict(document_id=item["source_id"], span=item["span_text"], span_hash=item["span_hash"])
        for item in evaluations[:3]
    ]
    diagnostics = _reply(query_channel, stiffness, frame, skipped)
    excerpts = "\n\n".join(f"[{item['document_id']}] {item['span']}" for item in evidence)
    body = f"Relevant source excerpts\n\n{excerpts}" if evidence else "No relevant source passage was found."
    response = result(
        "nammade" if evidence else "insufficient_evidence",
        f"{body}\n\n{DISCLAIMER}",
        kappa=stiffness,
        query_channel={"a": query_channel.a, "b": query_channel.b, "c": query_channel.c, "d": query_channel.d},
        evaluations=evaluations,
        has_static_equilibrium=frame["has_static_equilibrium"],
        polarity_bridges_found=frame["polarity_bridges_found"],
        frontier_status=frame["nammade_frontier_status"].value,
        word_relations=relations,
        relation_scope="Lexical co-occurrence and span polarity only",
        diagnostics=diagnostics,
        skipped_spans=skipped,
        stored=stored,
        as_of=when,
    )
    response["answer_evidence"] = evidence
    response["verification_scope"] = "source_attribution" if evidence else None
    response["reply"].update(answer_evidence=evidence, answer_status=response["answer_status"],
                             verification_scope=response["verification_scope"])
    return response
