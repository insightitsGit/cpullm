"""Decide whether Model01 has a training signal. No weights are written.

A training pair is one plan with two checker-approved sentences. The shipped
grammar emits one sentence per record. Until a plan has two, training stops
and no checkpoint file is created.
"""

from __future__ import annotations

from dataclasses import dataclass

from cpu_llm.model01.generator import MODEL_ID, MODEL_NAME
from cpu_llm.realizer.constructions import _question_for, bundle_from_chunks, derivations_for, plan_for


@dataclass(frozen=True)
class TrainingSurvey:
    model_id: str
    model_name: str
    paragraphs: int
    propositions: int
    frames: int
    plans: int
    max_derivations: int
    ready: bool
    checkpoint_written: bool
    reason: str


def train(chunks: list[tuple[str, str]] | None = None) -> TrainingSurvey:
    """Survey the pairs and write nothing.

    ``chunks`` defaults to the shipped WikiText splits, the primer, and the
    finance paragraphs. A ready survey still writes no file: a second legal
    sentence is not a preference label.
    """
    rows = shipped_paragraphs() if chunks is None else chunks
    return survey(rows)


def survey(chunks: list[tuple[str, str]]) -> TrainingSurvey:
    """Count licensed sentences. The largest group size is the training signal."""
    paragraphs = 0
    propositions = 0
    frames = 0
    plans = 0
    max_derivations = 0
    for document_id, text in chunks:
        if not document_id or not str(text or "").strip():
            continue
        paragraphs += 1
        bundle = bundle_from_chunks([(document_id, text)])
        propositions += sum(record.kind == "proposition" for record in bundle.records)
        frames += sum(record.kind == "frame" for record in bundle.records)
        counted = _count_plan(bundle, "What is recorded?")
        plans += counted[0]
        max_derivations = max(max_derivations, counted[1])
        frame = next((record.frame for record in bundle.records if record.kind == "frame" and record.frame), None)
        if frame is None:
            continue
        for kind in ("past_color", "past_location", "past_agent"):
            counted = _count_plan(bundle, _question_for(kind, frame))
            plans += counted[0]
            max_derivations = max(max_derivations, counted[1])
    ready = max_derivations >= 2
    if not ready:
        reason = "every plan has one legal sentence, so Model01 has no choice to learn"
    else:
        reason = "two legal sentences exist, and no preferred-derivation labels were supplied"
    return TrainingSurvey(
        model_id=MODEL_ID,
        model_name=MODEL_NAME,
        paragraphs=paragraphs,
        propositions=propositions,
        frames=frames,
        plans=plans,
        max_derivations=max_derivations,
        ready=ready,
        checkpoint_written=False,
        reason=reason,
    )


def shipped_paragraphs() -> list[tuple[str, str]]:
    """WikiText validation and test, the primer, and the finance paragraphs."""
    from cpu_llm.source import finance_chunks, test_path, textbook_chunks, validation_path, wikitext_chunks

    rows: list[tuple[str, str]] = []
    for chunk in (
        wikitext_chunks(validation_path(), prefix="wikitext2")
        + wikitext_chunks(test_path(), prefix="wikitext2test")
        + textbook_chunks()
        + finance_chunks()
    ):
        rows.append((chunk[0], chunk[2]))
    return rows


def _count_plan(bundle, question: str) -> tuple[int, int]:
    plan = plan_for(bundle, question)
    if plan.status != "answered":
        return 0, 0
    groups = derivations_for(bundle, plan)
    if not groups:
        return 0, 0
    return 1, max(len(group) for group in groups)
