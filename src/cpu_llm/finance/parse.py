"""Read a finance request from a question.

A JSON object is the full form. Labeled lines cover the same fields when the
question names one check. Missing labels stay missing. They are not filled in.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_KV = re.compile(r"^([A-Za-z][A-Za-z0-9 _/-]*?)\s*:\s*(.*)$")
_NUMERATOR = re.compile(r"^(numerator|denominator)\s*:\s*([A-Za-z_]+)\s+(\S+)\s*$", re.IGNORECASE)
_FIELD = re.compile(
    r"^field\s*:\s*(\S+)\s+(\S+)\s+confidence\s+(\S+)(?:\s+span\s+(\d+)\s*-\s*(\d+))?\s*$",
    re.IGNORECASE,
)
_ADDBACK = re.compile(
    r"^add-back\s*:\s*(\S+)\s+claimed\s+(\S+)\s+cap\s+(\S+)\s+of\s+(result|base)\s*$",
    re.IGNORECASE,
)
_HEADERS = {
    "refundproof": "refundproof",
    "ledgercovenant": "ledgercovenant",
    "ledgerlock": "ledgerlock",
}
_REFUND_KEYS = {
    "vendor": "vendor",
    "invoice": "invoice_number",
    "invoice number": "invoice_number",
    "line": "invoice_line",
    "invoice line": "invoice_line",
    "currency": "currency",
    "document type": "document_type",
    "tax charged": "tax_charged",
    "correct tax": "correct_tax",
    "deadline": "deadline_status",
    "deadline status": "deadline_status",
    "state": "state",
    "duplicate": "duplicate_status",
    "duplicate status": "duplicate_status",
    "source hash": "source_hash",
    "rule hash": "rule_hash",
    "rule version": "rule_version",
    "registered rule version": "registered_rule_version",
    "source bytes": "source_bytes",
    "rule bytes": "rule_bytes",
    "reviewer": "reviewer_email",
    "reviewer email": "reviewer_email",
    "reviewed at": "reviewed_at",
    "theory": "theory",
}
_COVENANT_KEYS = {
    "test date": "test_date",
    "comparator": "comparator",
    "threshold": "threshold",
    "rounding": "rounding",
    "currency": "currency",
    "max iterations": "max_iterations",
    "add-back base": "addback_base",
    "base": "addback_base",
}
_LOCK_KEYS = {
    "document type": "document_type",
    "document id": "document_id",
    "document text": "document_text",
}


def parse_sections(message: str, products: list[str]) -> dict[str, dict[str, Any]]:
    """Sections for the products this turn is running."""
    payload = extract_json(message)
    if payload is not None and _looks_like_request(payload):
        return _from_json(payload, products)
    return _from_lines(message, products)


def _looks_like_request(payload: dict[str, Any]) -> bool:
    keys = {str(key).casefold().replace("_", "") for key in payload}
    known = {
        "product",
        "refundproof",
        "ledgercovenant",
        "ledgerlock",
        "findings",
        "vendor",
        "taxcharged",
        "numerator",
        "threshold",
        "fields",
        "documenttype",
        "addback",
        "provisions",
    }
    return bool(keys & known)


def extract_json(message: str) -> dict[str, Any] | None:
    fence = _FENCE.search(message or "")
    blob = fence.group(1) if fence else _balanced_object(message or "")
    if not blob:
        return None
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def _balanced_object(message: str) -> str | None:
    start = message.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(message[start:], start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return message[start : index + 1]
    return None


def _from_json(payload: dict[str, Any], products: list[str]) -> dict[str, dict[str, Any]]:
    sections: dict[str, dict[str, Any]] = {}
    product = str(payload.get("product") or "").strip().lower()
    if product in _HEADERS:
        sections[product] = _normalize(product, payload)
    for name in _HEADERS:
        raw = payload.get(name)
        if isinstance(raw, dict):
            sections[name] = _normalize(name, raw)
    if not sections and products:
        only = products[0]
        sections[only] = _normalize(only, payload)
    return {name: sections[name] for name in products if name in sections}


def _normalize(product: str, raw: dict[str, Any]) -> dict[str, Any]:
    if product == "refundproof":
        findings = raw.get("findings")
        if isinstance(findings, list):
            return {"findings": findings}
        if any(key in raw for key in ("vendor", "taxCharged", "tax_charged")):
            return {"findings": [raw]}
        return {"findings": []}
    if product == "ledgercovenant":
        section = dict(raw)
        if "testDate" in section and "test_date" not in section:
            section["test_date"] = section["testDate"]
        add_back = section.get("addBack") or section.get("add_back")
        if isinstance(add_back, dict):
            section.setdefault("addback_base", add_back.get("base"))
            section.setdefault("addbacks", add_back.get("components") or [])
        provisions = []
        for item in section.get("provisions") or []:
            if isinstance(item, dict):
                provisions.append(_provision_dict(item))
        section["provisions"] = provisions
        if isinstance(section.get("waiver"), str):
            section["waiver"] = section["waiver"].strip().casefold() in {"1", "true", "yes", "y"}
        return section
    fields = raw.get("fields") or []
    return {
        "document_type": raw.get("document_type") or raw.get("documentType"),
        "document_id": raw.get("document_id") or raw.get("documentId"),
        "document_text": raw.get("document_text", raw.get("documentText")),
        "fields": fields,
    }


def _provision_dict(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("id") or raw.get("version_id") or raw.get("versionId"),
        "doc_type": raw.get("doc_type") or raw.get("docType") or raw.get("doc"),
        "valid_from": raw.get("valid_from") or raw.get("validFrom"),
        "valid_to": raw.get("valid_to") or raw.get("validTo"),
        "amends": raw.get("amends") or raw.get("amends_version_id") or raw.get("amendsVersionId"),
        "specificity": raw.get("specificity") or 0,
        "operation": raw.get("operation"),
    }


def _from_lines(message: str, products: list[str]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {name: _empty(name) for name in products}
    current = products[0] if len(products) == 1 else None
    finding: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal finding
        if finding and current == "refundproof":
            buckets["refundproof"]["findings"].append(finding)
        finding = None

    for raw_line in (message or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        header = _header(line)
        if header is not None:
            flush()
            if header in buckets:
                current = header
            continue
        if line == "---":
            flush()
            continue
        if current is None or current not in buckets:
            continue
        if current == "refundproof":
            parsed = _KV.match(line)
            if parsed is None:
                continue
            key = _REFUND_KEYS.get(parsed.group(1).strip().casefold())
            if key is None:
                continue
            if key == "vendor" and finding and finding.get("vendor"):
                flush()
            if finding is None:
                finding = {}
            finding[key] = parsed.group(2).strip()
            continue
        if current == "ledgercovenant":
            _apply_covenant(buckets["ledgercovenant"], line)
            continue
        _apply_lock(buckets["ledgerlock"], line)
    flush()
    return buckets


def _empty(product: str) -> dict[str, Any]:
    if product == "refundproof":
        return {"findings": []}
    if product == "ledgercovenant":
        return {"numerator": [], "denominator": [], "provisions": [], "addbacks": []}
    return {"fields": []}


def _header(line: str) -> str | None:
    token = line.strip().casefold().rstrip(":.")
    first = token.split()[0] if token else ""
    if token in _HEADERS:
        return _HEADERS[token]
    if first in _HEADERS and len(token.split()) == 1:
        return _HEADERS[first]
    return None


def _apply_covenant(section: dict[str, Any], line: str) -> None:
    special = _NUMERATOR.match(line)
    if special:
        kind = special.group(1).casefold()
        section[kind].append({"source": special.group(2).casefold(), "value": special.group(3)})
        return
    if line.casefold().startswith("provision:"):
        section["provisions"].append(_provision_line(line.split(":", 1)[1].strip()))
        return
    addback = _ADDBACK.match(line)
    if addback:
        section["addbacks"].append(
            {
                "key": addback.group(1),
                "claimed": addback.group(2),
                "cap_percent": addback.group(3),
                "basis": addback.group(4).casefold(),
            }
        )
        return
    parsed = _KV.match(line)
    if parsed is None:
        return
    label = parsed.group(1).strip().casefold()
    value = parsed.group(2).strip()
    if label == "waiver":
        section["waiver"] = value.casefold() in {"1", "true", "yes", "y"}
        return
    key = _COVENANT_KEYS.get(label)
    if key == "max_iterations":
        section[key] = int(value)
        return
    if key:
        section[key] = value


def _provision_line(value: str) -> dict[str, Any]:
    parts = value.split()
    item: dict[str, Any] = {"id": parts[0]}
    if len(parts) > 1:
        item["doc_type"] = parts[1]
    if len(parts) > 2:
        item["valid_from"] = parts[2]
    rest = parts[3:]
    index = 0
    if rest and re.fullmatch(r"\d{4}-\d{2}-\d{2}", rest[0]):
        item["valid_to"] = rest[0]
        index = 1
    while index < len(rest):
        key = rest[index].casefold()
        if key in {"amends", "specificity", "operation"} and index + 1 < len(rest):
            if key == "specificity":
                item[key] = int(rest[index + 1])
            else:
                item[key] = rest[index + 1]
            index += 2
            continue
        index += 1
    return item


def _apply_lock(section: dict[str, Any], line: str) -> None:
    field = _FIELD.match(line)
    if field:
        item: dict[str, Any] = {
            "field_id": field.group(1),
            "value": field.group(2),
            "confidence": field.group(3),
        }
        if field.group(4) is not None:
            item["span_start"] = int(field.group(4))
            item["span_end"] = int(field.group(5))
        section["fields"].append(item)
        return
    parsed = _KV.match(line)
    if parsed is None:
        return
    key = _LOCK_KEYS.get(parsed.group(1).strip().casefold())
    if key:
        section[key] = parsed.group(2).strip()
