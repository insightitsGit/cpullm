"""Request-local evidence, the claim plan, and a derivation.

A span is a slice of one record. Two copies of the same word stay two span
ids. Nothing in this module chooses a sentence.
"""

from __future__ import annotations

from dataclasses import dataclass

from cpu_llm.ir.schema import EIRProposition

SCHEMA = "n0-v1"


@dataclass(frozen=True)
class Span:
    span_id: str
    record_id: str
    role: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Record:
    record_id: str
    kind: str
    document_id: str
    source: str
    spans: tuple[Span, ...]
    proposition: EIRProposition | None = None
    frame: dict | None = None
    lemma: str = ""
    tense: str = ""


@dataclass(frozen=True)
class Bundle:
    records: tuple[Record, ...]
    causal_edges: tuple[tuple[str, str], ...] = ()
    completeness: str = "shortlist-only"

    def record(self, record_id: str) -> Record | None:
        for item in self.records:
            if item.record_id == record_id:
                return item
        return None

    def span(self, span_id: str) -> Span | None:
        for item in self.records:
            for span in item.spans:
                if span.span_id == span_id:
                    return span
        return None


@dataclass(frozen=True)
class Plan:
    plan_id: str
    mode: str
    question: str
    record_ids: tuple[str, ...]
    required_roles: tuple[str, ...]
    forbidden_roles: tuple[str, ...]
    tense: str
    status: str
    non_answer: str
    frame_kind: str = ""


@dataclass(frozen=True)
class Action:
    kind: str
    construction_id: str
    span_id: str = ""
    surface: str = ""
    role: str = ""


@dataclass(frozen=True)
class Derivation:
    derivation_id: str
    construction_id: str
    record_id: str
    actions: tuple[Action, ...]
    allowed_roles: tuple[str, ...]
    required_roles: tuple[str, ...]


def replay(actions: tuple[Action, ...]) -> str:
    """The sentence the actions print. The checker requires this exact string."""
    parts: list[str] = []
    for action in actions:
        if action.kind in {"COPY", "EMIT_GRAMMAR", "INFLECT"}:
            parts.append(action.surface)
    return "".join(parts)
