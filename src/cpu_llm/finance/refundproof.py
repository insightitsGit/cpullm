"""Sales and use tax overpayment review.

The rules follow the RefundProof pilot: decimal tax, a SHA-256 binding before
anything can be called digest-verified, a persisted human approval before
recovery, and exclusion of expired, uncertain, duplicate, and unverified
dollars from actionable totals. This node does not approve a finding and does
not file a return.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation
from typing import Any

FINDING_STATES = {
    "INGESTED",
    "FACTS_INCOMPLETE",
    "ANALYSIS_READY",
    "POTENTIAL_OVERPAYMENT",
    "CHALLENGED",
    "EVIDENCE_REQUESTED",
    "REVIEW_APPROVED",
    "REVIEW_REJECTED",
    "ROUTE_SELECTED",
    "VENDOR_REQUEST_READY",
    "VENDOR_CONTACTED",
    "VENDOR_RESPONDED",
    "ASSIGNMENT_REQUESTED",
    "ASSIGNMENT_RECEIVED",
    "AUTHORITY_PACKET_READY",
    "SUBMITTED_EXTERNALLY",
    "CREDIT_MEMO_RECEIVED",
    "RECOVERED",
    "DENIED",
    "EXPIRED",
}
INITIAL_STATES = {
    "INGESTED",
    "FACTS_INCOMPLETE",
    "ANALYSIS_READY",
    "POTENTIAL_OVERPAYMENT",
    "CHALLENGED",
}
REVIEWABLE_STATES = INITIAL_STATES | {"EVIDENCE_REQUESTED"}
RECOVERY_EVENTS = {
    "ROUTE_SELECTED",
    "VENDOR_REQUEST_READY",
    "VENDOR_CONTACTED",
    "VENDOR_RESPONDED",
    "ASSIGNMENT_REQUESTED",
    "ASSIGNMENT_RECEIVED",
    "AUTHORITY_PACKET_READY",
    "SUBMITTED_EXTERNALLY",
    "CREDIT_MEMO_RECEIVED",
    "RECOVERED",
    "DENIED",
}
ACTIONABLE_STATES = {"REVIEW_APPROVED"} | (RECOVERY_EVENTS - {"CREDIT_MEMO_RECEIVED", "RECOVERED", "DENIED"})
DEADLINE_STATES = {
    "ACTIONABLE",
    "EXPIRING_SOON",
    "DEADLINE_UNCERTAIN",
    "EXPIRED",
    "EXCEPTION_REVIEW_REQUIRED",
}
ACTIONABLE_DEADLINES = {"ACTIONABLE", "EXPIRING_SOON"}
POTENTIAL_DEADLINES = ACTIONABLE_DEADLINES | {"DEADLINE_UNCERTAIN"}
CURRENCIES = {"USD", "CAD", "EUR", "GBP", "AUD", "MXN"}
DOCUMENT_TYPES = {"invoice", "credit_note"}
MONEY_QUANTUM = Decimal("0.0001")
MONEY_LIMIT = Decimal("9999999999999999.9999")
LIMITATION = (
    "Digest verification means the registered bytes hash to the stated SHA-256 and the rule "
    "version matches. It is not tax advice, proof the document is authentic, or a guarantee of recovery."
)


class RefundInputError(ValueError):
    """One finding cannot be normalized."""


def hash_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def identity_key(vendor: str, invoice_number: str, invoice_line: str | None) -> str:
    vendor_norm = " ".join(vendor.strip().lower().split())
    invoice_norm = " ".join(invoice_number.strip().upper().split())
    line_norm = " ".join((invoice_line or "").strip().lower().split())
    return f"{vendor_norm}|{invoice_norm}|{line_norm}"


def normalize_sha256(value: Any, field: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text.startswith("sha256:"):
        text = text[7:]
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise RefundInputError(f"{field} must be 64 hex characters, optionally prefixed with sha256:.")
    return text


def parse_money(value: Any, field: str) -> Decimal:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise RefundInputError(f"{field} is required. A missing amount is not zero.")
    if isinstance(value, bool) or isinstance(value, float):
        raise RefundInputError(f"{field} must be a decimal string. A JSON float is not accepted.")
    text = str(value).strip().replace(",", "").replace("$", "")
    if text.lower() in {"nan", "infinity", "inf", "+inf", "-infinity", "-inf"}:
        raise RefundInputError(f"{field} must be a finite decimal amount.")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise RefundInputError(f"{field} must be a finite decimal amount.") from None
    if not amount.is_finite():
        raise RefundInputError(f"{field} must be a finite decimal amount.")
    try:
        quantized = amount.quantize(MONEY_QUANTUM)
    except InvalidOperation:
        raise RefundInputError(f"{field} must be a finite decimal amount.") from None
    if quantized != amount:
        raise RefundInputError(f"{field} supports at most 4 decimal places.")
    if abs(quantized) > MONEY_LIMIT:
        raise RefundInputError(f"{field} exceeds the supported range.")
    return quantized


def _clean(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RefundInputError(f"{field} is required.")
    return text


def _bytes(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    text = str(value)
    if text == "":
        return None
    return text.encode("utf-8")


def normalize_finding(data: dict[str, Any], index: int) -> dict[str, Any]:
    """Normalize one finding. Raises before any total includes it."""
    vendor = _clean(data.get("vendor"), "vendor")
    invoice_number = _clean(data.get("invoice_number", data.get("invoiceNumber")), "invoice")
    invoice_line = str(data.get("invoice_line") or data.get("invoiceLine") or "").strip() or None
    document_type = str(data.get("document_type") or data.get("documentType") or "invoice").strip().lower()
    if document_type not in DOCUMENT_TYPES:
        raise RefundInputError("document type must be invoice or credit_note.")
    currency = str(data.get("currency") or "USD").strip().upper()
    if currency not in CURRENCIES:
        raise RefundInputError(f"currency must be one of {', '.join(sorted(CURRENCIES))}.")
    charged = parse_money(data.get("tax_charged", data.get("taxCharged")), "tax charged")
    correct = parse_money(data.get("correct_tax", data.get("correctTax")), "correct tax")
    if document_type == "invoice":
        if charged < 0 or correct < 0:
            raise RefundInputError(
                "An invoice records tax charged and correct tax as zero or positive. "
                "A tax credit uses document type credit_note."
            )
        recoverable = max(Decimal("0"), charged - correct).quantize(MONEY_QUANTUM)
        credit_amount = None
    else:
        if charged > 0:
            raise RefundInputError("A credit note records tax charged as zero or a negative credit.")
        if correct != 0:
            raise RefundInputError("A credit note records the credit in tax charged and requires correct tax 0.")
        recoverable = Decimal("0.0000")
        credit_amount = abs(charged)
    deadline = str(data.get("deadline_status") or data.get("deadlineStatus") or "DEADLINE_UNCERTAIN").strip()
    if deadline not in DEADLINE_STATES:
        raise RefundInputError("Invalid deadline status.")
    state = str(data.get("state") or "POTENTIAL_OVERPAYMENT").strip()
    if state not in FINDING_STATES:
        raise RefundInputError(f"Unknown finding state {state}.")
    duplicate = str(data.get("duplicate_status") or data.get("duplicateStatus") or "unique").strip().lower()
    if duplicate not in {"unique", "suspected", "excluded"}:
        raise RefundInputError("duplicate status must be unique, suspected, or excluded.")
    source_hash = normalize_sha256(data.get("source_hash", data.get("sourceHash")), "source hash")
    rule_hash = normalize_sha256(data.get("rule_hash", data.get("ruleHash")), "rule hash")
    rule_version = str(data.get("rule_version") or data.get("ruleVersion") or "").strip() or None
    registered_version = str(
        data.get("registered_rule_version") or data.get("registeredRuleVersion") or ""
    ).strip() or rule_version
    reviewer = str(data.get("reviewer_email") or data.get("reviewerEmail") or data.get("reviewer") or "").strip() or None
    reviewed_at = str(data.get("reviewed_at") or data.get("reviewedAt") or "").strip() or None
    return {
        "index": index,
        "vendor": vendor,
        "invoice_number": invoice_number,
        "invoice_line": invoice_line,
        "identity_key": identity_key(vendor, invoice_number, invoice_line),
        "document_type": document_type,
        "currency": currency,
        "tax_charged": charged,
        "correct_tax": correct,
        "recoverable_amount": recoverable,
        "credit_amount": credit_amount,
        "deadline_status": deadline,
        "state": state,
        "duplicate_status": duplicate,
        "rule_version": rule_version,
        "registered_rule_version": registered_version,
        "source_hash": source_hash,
        "rule_hash": rule_hash,
        "source_bytes": _bytes(data.get("source_bytes", data.get("sourceBytes"))),
        "rule_bytes": _bytes(data.get("rule_bytes", data.get("ruleBytes"))),
        "reviewer_email": reviewer,
        "reviewed_at": reviewed_at,
        "theory": (str(data.get("theory")).strip() if data.get("theory") else None),
    }


def _same_opportunity(existing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    for field in (
        "identity_key",
        "document_type",
        "currency",
        "deadline_status",
        "source_hash",
        "rule_hash",
        "rule_version",
    ):
        if (existing.get(field) or None) != (incoming.get(field) or None):
            return False
    return existing["tax_charged"] == incoming["tax_charged"] and existing["correct_tax"] == incoming["correct_tax"]


def mark_duplicates(rows: list[dict[str, Any]]) -> None:
    """A second different body for the same invoice line is suspected, not summed twice."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("duplicate_status") == "excluded":
            continue
        groups.setdefault(row["identity_key"], []).append(row)
    for group in groups.values():
        if len(group) == 1:
            continue
        first = group[0]
        if all(_same_opportunity(first, other) for other in group[1:]):
            for other in group[1:]:
                other["duplicate_status"] = "replay"
                other["duplicate_of"] = first["index"]
            continue
        for row in group:
            row["duplicate_status"] = "suspected"


def assess_evidence(row: dict[str, Any]) -> dict[str, Any]:
    """A stated hash without the bytes is unverified. Disagreeing bytes are mismatched."""
    source_hash = row.get("source_hash")
    rule_hash = row.get("rule_hash")
    rule_version = row.get("rule_version")
    base = {
        "legal_validity": "not_determined",
        "evidence_limitation": LIMITATION,
        "evidence_claim": None,
    }
    if not source_hash or not rule_hash or not rule_version:
        return {
            **base,
            "evidence_status": "unverified",
            "block_reason": (
                "Approval is blocked until a source digest, a rule digest, and a rule version are present. "
                "A blank binding is not evidence."
            ),
        }
    if row.get("source_bytes") is None or row.get("rule_bytes") is None:
        return {
            **base,
            "evidence_status": "unverified",
            "block_reason": "No registered bytes were supplied for this finding. A well-formed hash is not evidence.",
        }
    source_digest = hash_bytes(row["source_bytes"])
    rule_digest = hash_bytes(row["rule_bytes"])
    if source_digest != source_hash or rule_digest != rule_hash:
        return {
            **base,
            "evidence_status": "mismatched",
            "block_reason": "The supplied bytes do not hash to the digest on the finding.",
        }
    if (row.get("registered_rule_version") or "") != rule_version:
        return {
            **base,
            "evidence_status": "mismatched",
            "block_reason": "The rule version does not match the registered rule.",
        }
    return {
        **base,
        "evidence_status": "verified",
        "evidence_claim": "digest_verified",
        "block_reason": "",
    }


def approval_gate(row: dict[str, Any]) -> str:
    """Whether a person could record approval. This function does not approve."""
    if row.get("duplicate_status") in {"suspected", "replay"}:
        return "Approval is blocked while this invoice line is an unresolved duplicate."
    if row.get("state") not in REVIEWABLE_STATES:
        return f"Review is not available from state {row.get('state')}."
    if row.get("evidence_status") != "verified":
        return str(row.get("block_reason") or "Evidence is not digest-verified.")
    return ""


def recovery_gate(row: dict[str, Any]) -> str:
    if row.get("document_type") not in (None, "invoice"):
        return "Credit notes are recorded amounts, not ordinary recovery packets."
    if not row.get("reviewer_email") or not row.get("reviewed_at"):
        return "Recovery requires a persisted human approval. A state name is not approval."
    if row.get("state") not in ACTIONABLE_STATES:
        return f"Recovery cannot start from state {row.get('state')}."
    if row.get("duplicate_status") != "unique":
        return "Recovery is blocked until the duplicate invoice line is resolved."
    deadline = row.get("deadline_status")
    if deadline not in ACTIONABLE_DEADLINES:
        return (
            f"Deadline status {deadline} is not eligible for an ordinary recovery packet. "
            "The finding stays readable."
        )
    if row.get("evidence_status") != "verified":
        return "Recovery is blocked because the evidence binding is not digest-verified. " + str(
            row.get("block_reason") or ""
        )
    return ""


def eligible_actionable(row: dict[str, Any]) -> bool:
    return (
        row.get("document_type") == "invoice"
        and row.get("duplicate_status") == "unique"
        and row.get("evidence_status") == "verified"
        and row.get("deadline_status") in ACTIONABLE_DEADLINES
        and row.get("state") in ACTIONABLE_STATES
        and row.get("currency") in CURRENCIES
        and bool(row.get("reviewer_email"))
        and bool(row.get("reviewed_at"))
    )


def eligible_potential(row: dict[str, Any]) -> bool:
    return (
        row.get("document_type") == "invoice"
        and row.get("duplicate_status") == "unique"
        and row.get("evidence_status") != "mismatched"
        and row.get("deadline_status") in POTENTIAL_DEADLINES
        and row.get("state") in INITIAL_STATES
        and row.get("currency") in CURRENCIES
    )


def _add(bucket: dict[str, Decimal], currency: str, amount: Decimal) -> None:
    bucket[currency] = bucket.get(currency, Decimal("0.0000")) + amount


def _fmt(bucket: dict[str, Decimal]) -> dict[str, str]:
    return {key: format(value.quantize(MONEY_QUANTUM), "f") for key, value in sorted(bucket.items())}


def totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actionable: dict[str, Decimal] = {}
    potential: dict[str, Decimal] = {}
    for row in rows:
        if row.get("duplicate_status") == "replay":
            continue
        amount = Decimal(str(row.get("recoverable_amount") or "0")).quantize(MONEY_QUANTUM)
        currency = str(row.get("currency") or "USD")
        if eligible_actionable(row):
            _add(actionable, currency, amount)
        elif eligible_potential(row):
            _add(potential, currency, amount)
    actionable_fmt = _fmt(actionable)
    return {
        "actionable_by_currency": actionable_fmt,
        "potential_by_currency": _fmt(potential),
        "actionable_total": actionable_fmt.get("USD", "0.0000"),
        "actionable_total_scope": "USD",
    }


def _money(amount: Decimal) -> str:
    return format(amount.quantize(MONEY_QUANTUM), "f")


def review(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Review every finding in the request and total only the eligible dollars."""
    if not findings:
        return {
            "product": "refundproof",
            "completed": False,
            "verdict": "INCOMPLETE",
            "text": (
                "RefundProof needs at least one finding with vendor, invoice, tax charged, and correct tax. "
                + LIMITATION
            ),
            "findings": [],
            "totals": totals([]),
            "limitation": LIMITATION,
        }
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, raw in enumerate(findings, start=1):
        if not isinstance(raw, dict):
            errors.append({"index": index, "verdict": "INPUT_INVALID", "text": "A finding must be an object."})
            continue
        try:
            rows.append(normalize_finding(raw, index))
        except RefundInputError as exc:
            errors.append({"index": index, "verdict": "INPUT_INVALID", "text": str(exc)})
    mark_duplicates(rows)
    spoken: list[str] = []
    detailed: list[dict[str, Any]] = []
    for row in rows:
        evidence = assess_evidence(row)
        row["evidence_status"] = evidence["evidence_status"]
        row["block_reason"] = evidence["block_reason"]
        approval_block = approval_gate(row)
        recovery_block = recovery_gate(row)
        label = f"{row['vendor']} {row['invoice_number']}"
        if row.get("invoice_line"):
            label = f"{label} line {row['invoice_line']}"
        if row["document_type"] == "credit_note":
            amount_text = f"credit {_money(row['credit_amount'] or Decimal('0'))} {row['currency']}"
        else:
            amount_text = f"recoverable {_money(row['recoverable_amount'])} {row['currency']}"
        if row.get("duplicate_status") == "replay":
            status = "replay of an earlier identical finding, not added again"
        elif approval_block and recovery_block:
            status = approval_block
        elif recovery_block:
            status = "Ready for a human reviewer. " + recovery_block
        else:
            status = "Recovery can be tracked because the finding already names a reviewer and a review time."
        spoken.append(f"{label}: {amount_text}. Evidence is {row['evidence_status']}. {status}")
        detailed.append(
            {
                "index": row["index"],
                "vendor": row["vendor"],
                "invoice_number": row["invoice_number"],
                "invoice_line": row["invoice_line"],
                "identity_key": row["identity_key"],
                "document_type": row["document_type"],
                "currency": row["currency"],
                "tax_charged": _money(row["tax_charged"]),
                "correct_tax": _money(row["correct_tax"]),
                "recoverable_amount": _money(row["recoverable_amount"]),
                "credit_amount": None if row["credit_amount"] is None else _money(row["credit_amount"]),
                "deadline_status": row["deadline_status"],
                "state": row["state"],
                "duplicate_status": row["duplicate_status"],
                "evidence_status": row["evidence_status"],
                "approval_blocked": approval_block,
                "recovery_blocked": recovery_block,
                "eligible_actionable": eligible_actionable(row),
                "eligible_potential": eligible_potential(row),
            }
        )
    for error in errors:
        spoken.append(f"Finding {error['index']}: {error['text']}")
        detailed.append(error)
    rolled = totals(rows)
    actionable = ", ".join(f"{currency} {amount}" for currency, amount in rolled["actionable_by_currency"].items())
    potential = ", ".join(f"{currency} {amount}" for currency, amount in rolled["potential_by_currency"].items())
    if not actionable:
        actionable = "none"
    if not potential:
        potential = "none"
    text = (
        "RefundProof: "
        + " ".join(spoken)
        + f" Actionable total {actionable}. Potential total {potential}. "
        + LIMITATION
    )
    completed = bool(rows) and not errors
    verdict = "REVIEWED" if completed else "INPUT_INVALID"
    if rows and all(item.get("approval_blocked") for item in detailed if "approval_blocked" in item):
        verdict = "BLOCKED" if completed else verdict
    return {
        "product": "refundproof",
        "completed": bool(rows) or bool(errors),
        "verdict": verdict if rows or errors else "INCOMPLETE",
        "text": text,
        "findings": detailed,
        "totals": rolled,
        "limitation": LIMITATION,
    }
