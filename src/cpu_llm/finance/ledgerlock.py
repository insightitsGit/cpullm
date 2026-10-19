"""Mortgage extracted-number attestation before a loan-system update.

ACCEPT, REVIEW, and REFUSE follow the Ledgerlock gate and the extraction
floors. The digest here is SHA-256 of the canonical decision. It is not an
Ed25519 AuditBundle, not underwriting, and not a write to a loan system.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any

LIMITATION = (
    "This gate attests the extracted number against the span and the confidence floors. "
    "It is not underwriting, not a document-authenticity check, and not a loan-system write. "
    "The digest is SHA-256, not an Ed25519 signature."
)
ACCEPT_CONFIDENCE = Decimal("0.90")
REVIEW_CONFIDENCE = Decimal("0.60")
OCR_FLOORS = {
    "w2_stip": Decimal("0.98"),
    "f1040_stip": Decimal("0.97"),
    "paystub_stip": Decimal("0.95"),
    "bank_statement_stip": Decimal("0.92"),
}
REQUIRED_FIELDS = {
    "w2_stip": ("w2_box1_wages",),
    "paystub_stip": ("paystub_ytd_gross",),
    "bank_statement_stip": ("bank_stmt_ending_balance",),
    "f1040_stip": ("f1040_line11_agi",),
}
INJECTION_MARKER = "INJECTION_DETECTED"


class LockInputError(ValueError):
    """A field cannot be attested."""


def _confidence(raw: Any) -> Decimal:
    if isinstance(raw, bool) or isinstance(raw, float):
        raise LockInputError("Confidence must be a decimal string. A JSON float is not accepted.")
    if isinstance(raw, int):
        raise LockInputError("Confidence must be a decimal string such as 0.99.")
    text = str(raw).strip()
    if not text:
        raise LockInputError("Confidence is required.")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise LockInputError(f"{raw!r} is not a confidence.") from None
    if not value.is_finite() or value < 0 or value > 1:
        raise LockInputError("Confidence must be from 0 to 1.")
    return value


def _canonical(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _span_holds(document: str, start: int, end: int, value: str) -> str:
    if start < 0 or end < start or end > len(document):
        return "REFUSE"
    window = document[start:end]
    needle = value.replace(",", "").replace("$", "").strip()
    haystack = window.replace(",", "").replace("$", "")
    if needle and needle in haystack:
        return "MATCH"
    return "MISMATCH"


def _field_decision(field: dict[str, Any], document_type: str, document: str | None) -> dict[str, Any]:
    field_id = str(field.get("field_id") or field.get("fieldId") or "").strip()
    if not field_id:
        raise LockInputError("Each field needs a field id.")
    value = field.get("value", field.get("extracted_value", field.get("extractedValue")))
    if value is None or (isinstance(value, str) and not value.strip()):
        raise LockInputError(f"{field_id} needs an extracted value.")
    if isinstance(value, float) or isinstance(value, bool):
        raise LockInputError(f"{field_id} value must be a decimal string.")
    shown = str(value).strip()
    confidence = _confidence(field.get("confidence", field.get("ocr_confidence", field.get("ocrConfidence"))))
    floor = OCR_FLOORS[document_type]
    span = field.get("span")
    start = field.get("span_start", field.get("spanStart"))
    end = field.get("span_end", field.get("spanEnd"))
    if isinstance(span, str) and "-" in span and start is None:
        left, right = span.split("-", 1)
        start, end = left.strip(), right.strip()
    if start is None or end is None:
        span_status = "MISSING"
        start_i = end_i = None
    else:
        start_i = int(start)
        end_i = int(end)
        if document is None:
            span_status = "UNCHECKED"
        else:
            span_status = _span_holds(document, start_i, end_i, shown)
    if INJECTION_MARKER in shown:
        status = "REFUSE"
        reason = "The field is marked as an injection and is refused."
    elif confidence < floor:
        status = "REFUSE"
        reason = f"Confidence {confidence} is below the {document_type} extraction floor {floor}."
    elif confidence < REVIEW_CONFIDENCE:
        status = "REFUSE"
        reason = f"Confidence {confidence} is below the review floor {REVIEW_CONFIDENCE}."
    elif span_status == "MISMATCH":
        status = "REFUSE"
        reason = "The source span does not contain the extracted value."
    elif span_status == "REFUSE":
        status = "REFUSE"
        reason = "The source span is outside the document text."
    elif confidence < ACCEPT_CONFIDENCE or span_status in {"MISSING", "UNCHECKED"}:
        status = "REVIEW"
        if span_status == "MISSING":
            reason = "A field without a source span cannot be accepted for a loan-system update."
        elif span_status == "UNCHECKED":
            reason = "Document text was not supplied, so the span was not checked."
        else:
            reason = f"Confidence {confidence} is below the accept floor {ACCEPT_CONFIDENCE}."
    else:
        status = "ACCEPT"
        reason = f"Confidence {confidence} clears the extraction floor and the value is inside the span."
    return {
        "field_id": field_id,
        "value": shown,
        "confidence": format(confidence, "f"),
        "span_start": start_i,
        "span_end": end_i,
        "span_status": span_status,
        "status": status,
        "reason": reason,
    }


def _aggregate(statuses: list[str]) -> str:
    if not statuses or any(status == "REFUSE" for status in statuses):
        return "REFUSE"
    if any(status == "REVIEW" for status in statuses):
        return "REVIEW"
    return "ACCEPT"


def attest(request: dict[str, Any]) -> dict[str, Any]:
    """Attest extracted fields. A missing required field is a refusal."""
    if not request:
        return _incomplete()
    document_type = str(request.get("document_type") or request.get("documentType") or "").strip().lower()
    if document_type not in REQUIRED_FIELDS:
        known = ", ".join(sorted(REQUIRED_FIELDS))
        return {
            "product": "ledgerlock",
            "completed": True,
            "verdict": "REFUSE",
            "text": f"Ledgerlock: REFUSE. Document type must be one of {known}. {LIMITATION}",
            "limitation": LIMITATION,
        }
    document = request.get("document_text", request.get("documentText"))
    if document is not None:
        document = str(document)
    if document and INJECTION_MARKER in document:
        return {
            "product": "ledgerlock",
            "completed": True,
            "verdict": "REFUSE",
            "text": f"Ledgerlock: REFUSE. The document is marked as an injection. {LIMITATION}",
            "limitation": LIMITATION,
        }
    fields = list(request.get("fields") or [])
    if not fields:
        return _incomplete()
    try:
        decided = [_field_decision(field, document_type, document) for field in fields]
    except (LockInputError, TypeError, ValueError) as exc:
        return {
            "product": "ledgerlock",
            "completed": True,
            "verdict": "INPUT_INVALID",
            "text": f"Ledgerlock: INPUT_INVALID. {exc} {LIMITATION}",
            "limitation": LIMITATION,
        }
    present = {item["field_id"] for item in decided}
    missing = [name for name in REQUIRED_FIELDS[document_type] if name not in present]
    if missing:
        verdict = "REFUSE"
        missing_text = f" Required fields missing: {', '.join(missing)}."
    else:
        verdict = _aggregate([item["status"] for item in decided])
        missing_text = ""
    digest = _canonical(
        {
            "document_type": document_type,
            "document_id": request.get("document_id") or request.get("documentId"),
            "verdict": verdict,
            "fields": decided,
        }
    )
    lines = [
        f"{item['field_id']} {item['value']} is {item['status']}. {item['reason']}"
        for item in decided
    ]
    return {
        "product": "ledgerlock",
        "completed": True,
        "verdict": verdict,
        "text": (
            f"Ledgerlock: {verdict}. "
            + " ".join(lines)
            + missing_text
            + f" Attestation digest sha256:{digest}. {LIMITATION}"
        ),
        "fields": decided,
        "digest": digest,
        "document_type": document_type,
        "limitation": LIMITATION,
    }


def _incomplete() -> dict[str, Any]:
    known = ", ".join(sorted(REQUIRED_FIELDS))
    return {
        "product": "ledgerlock",
        "completed": False,
        "verdict": "INCOMPLETE",
        "text": (
            "Ledgerlock needs a document type, the document text, and each field id, value, "
            f"confidence, and span. Document types: {known}. {LIMITATION}"
        ),
        "limitation": LIMITATION,
    }
