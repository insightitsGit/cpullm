"""Check a derivation without calling the ranker again.

Replaying the actions has to reproduce the candidate. A copied span has to be
the same slice as the snapshot. A word from a word-edge or a tag stays in
that clause unless the same characters are already a span of the other record.
"""

from __future__ import annotations

import re

from cpu_llm.realizer.evidence_schema import Bundle, Derivation, Plan, replay
from cpu_llm.realizer.inflect import forms

_NUMBER = re.compile(r"\d+")
_TOKEN = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")


def check_derivation(bundle: Bundle, plan: Plan, derivation: Derivation) -> list[str]:
    """Reasons the derivation is illegal. An empty list means it passed."""
    reasons: list[str] = []
    record = bundle.record(derivation.record_id)
    if record is None:
        return ["the derivation names a record that is not in the plan"]
    if derivation.record_id not in plan.record_ids and plan.record_ids:
        reasons.append("the derivation is not a record this plan licensed")
    actions = derivation.actions
    if not actions or actions[0].kind != "CHOOSE_CONSTRUCTION" or actions[-1].kind != "STOP":
        reasons.append("a derivation starts by choosing a construction and ends when that construction is closed")
    copied_roles: list[str] = []
    for action in actions:
        if action.kind == "COPY":
            span = bundle.span(action.span_id)
            if span is None or span.record_id != record.record_id:
                reasons.append("a copied span is not a binding of this record")
                continue
            if record.source[span.start : span.end] != span.text or span.text != action.surface:
                reasons.append("a copied span does not match the snapshot")
            if action.role != span.role:
                reasons.append("a copied span was used for a different role")
            if span.role not in derivation.allowed_roles:
                reasons.append(f"the construction does not allow the {span.role} role")
            if span.role in plan.forbidden_roles:
                reasons.append(f"the plan forbids the {span.role} role")
            copied_roles.append(span.role)
        elif action.kind == "INFLECT":
            allowed = set(forms(record.lemma).values()) if record.lemma else set()
            if action.surface not in allowed:
                reasons.append("an inflection is not a licensed form of the stored lemma")
        elif action.kind not in {"CHOOSE_CONSTRUCTION", "EMIT_GRAMMAR", "STOP"}:
            reasons.append("the derivation uses an action the grammar does not define")
    for role in derivation.required_roles:
        if role not in copied_roles:
            reasons.append(f"the required {role} role was not copied")
    if record.kind == "frame" and plan.tense and record.tense != plan.tense:
        reasons.append("the frame tense is not the tense the question asked for")
    candidate = replay(actions)
    for number in _NUMBER.findall(candidate):
        if not any(number in action.surface for action in actions if action.kind == "COPY"):
            reasons.append("a number in the sentence is not inside a copied span")
    return reasons


def check_passage(bundle: Bundle, plan: Plan, chosen: list[Derivation]) -> list[str]:
    """Check every clause, then refuse a hand or tag word donated into another clause."""
    reasons: list[str] = []
    for derivation in chosen:
        reasons.extend(check_derivation(bundle, plan, derivation))
    foreign = _foreign_words(bundle, chosen)
    for derivation in chosen:
        record = bundle.record(derivation.record_id)
        if record is None or record.kind in {"word_edge", "tag"}:
            continue
        own: set[str] = set()
        for action in derivation.actions:
            if action.kind == "COPY":
                own.update(token.casefold() for token in _TOKEN.findall(action.surface))
        leaked = foreign - own
        candidate = replay(derivation.actions)
        for token in _TOKEN.findall(candidate):
            if token.casefold() in leaked:
                reasons.append("a word-edge or tag word was copied into another clause")
                break
    return reasons


def _foreign_words(bundle: Bundle, chosen: list[Derivation]) -> set[str]:
    words: set[str] = set()
    for derivation in chosen:
        record = bundle.record(derivation.record_id)
        if record is None or record.kind not in {"word_edge", "tag"}:
            continue
        for span in record.spans:
            words.add(span.text.casefold())
    return words
