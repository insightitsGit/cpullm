"""Phrases that start a finance validation.

A definition question stays on the retrieved sentence. The check runs when
the question names the product together with the action, or when it already
includes the fields that check reads.
"""

from __future__ import annotations

import re

CALLER_REASON = "the caller turned finance validation on"

_DEFINITION = re.compile(r"(?is)^\s*what\s+(?:is|are)\b")
_REFUND = re.compile(
    r"\brefundproof\b[\s\S]{0,80}\b(?:review|check|validate|finding|recover|recovery|deadline)\b"
    r"|\b(?:review|check|validate|recover)\b[\s\S]{0,80}\brefundproof\b"
    r"|\btax charged\b[\s\S]{0,200}\bcorrect tax\b"
    r"|\bcorrect tax\b[\s\S]{0,200}\btax charged\b",
    re.IGNORECASE,
)
_COVENANT = re.compile(
    r"\bledgercovenant\b[\s\S]{0,80}\b(?:decide|decision|test|calculate|threshold|numerator|provision|add-?back|ratio)\b"
    r"|\b(?:decide|calculate|test)\b[\s\S]{0,60}\bledgercovenant\b"
    r"|\b(?:covenant test|covenant decision|leverage covenant|add-?back cap)\b"
    r"|\bnumerator\s*:"
    r"|\badd-back base\s*:",
    re.IGNORECASE,
)
_LOCK = re.compile(
    r"\bledgerlock\b[\s\S]{0,80}\b(?:attest|attestation|gate|accept|refuse|span|confidence|field)\b"
    r"|\b(?:attest|attestation)\b[\s\S]{0,60}\bledgerlock\b"
    r"|\b(?:mortgage attestation|loan-system update|los write)\b"
    r"|\bfield\s*:\s*\S+\s+\S+\s+confidence\b"
    r"|\bdocument type\s*:\s*(?:w2_stip|paystub_stip|bank_statement_stip|f1040_stip)\b",
    re.IGNORECASE,
)


def finance_trigger(message: str, *, forced: bool = False) -> list[str]:
    """Reasons to run a finance check. Empty for a plain or definition question."""
    return [reason for _product, reason in select_finance(message, forced=forced)]


def select_finance(message: str, *, forced: bool = False) -> list[tuple[str, str]]:
    """``(product, reason)`` pairs. ``caller`` records that the flag was set."""
    selected: list[tuple[str, str]] = []
    if forced:
        selected.append(("caller", CALLER_REASON))
    if _definition_only(message):
        return selected
    text = message or ""
    if _REFUND.search(text):
        selected.append(("refundproof", "the prompt asks for a RefundProof tax review"))
    if _COVENANT.search(text):
        selected.append(("ledgercovenant", "the prompt asks for a LedgerCovenant decision"))
    if _LOCK.search(text):
        selected.append(("ledgerlock", "the prompt asks for a Ledgerlock attestation"))
    return selected


def products_from(selected: list[tuple[str, str]]) -> list[str]:
    names: list[str] = []
    for product, _reason in selected:
        if product == "caller" or product in names:
            continue
        names.append(product)
    return names


def _definition_only(message: str) -> bool:
    text = (message or "").strip()
    if _DEFINITION.match(text) is None:
        return False
    return ":" not in text and "{" not in text
