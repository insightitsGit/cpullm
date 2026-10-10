"""Named measurements copied from a paragraph, with no unit conversion.

A claim is recorded only when the paragraph states both a number and a
physical unit, and a nearby word names what was measured. "up to" stays a
maximum in the provenance. The claim value stays the number that was written.
"""

from __future__ import annotations

import re
from typing import Any

_UNIT_MAP = {
    "centimetre": "cm",
    "centimetres": "cm",
    "centimeter": "cm",
    "centimeters": "cm",
    "cm": "cm",
    "millimetre": "mm",
    "millimetres": "mm",
    "millimeter": "mm",
    "millimeters": "mm",
    "mm": "mm",
    "metre": "m",
    "metres": "m",
    "meter": "m",
    "meters": "m",
    "m": "m",
    "kilogram": "kg",
    "kilograms": "kg",
    "kg": "kg",
    "gram": "g",
    "grams": "g",
    "g": "g",
    "inch": "in",
    "inches": "in",
    "in": "in",
    "pound": "lb",
    "pounds": "lb",
    "lb": "lb",
    "lbs": "lb",
}

_UNIT = (
    r"centimetres|centimetre|centimeters|centimeter|"
    r"millimetres|millimetre|millimeters|millimeter|"
    r"kilograms|kilogram|"
    r"metres|metre|meters|meter|"
    r"inches|inch|"
    r"pounds|pound|"
    r"grams|gram|"
    r"cm|mm|kg|lbs|lb|"
    r"in|g|m"
)
_NUM = r"\d+(?:\.\d+)?"
_DASH = r"[\u2012\u2013\u2014\u2212\-]"
_QUAL = r"up\s+to|at\s+least|more\s+than|less\s+than|approximately|about|around|nearly|approx\.?"

_MEASUREMENT = re.compile(
    rf"(?:(?P<qual>{_QUAL})\s+)?"
    rf"(?P<low>{_NUM})"
    rf"(?:\s*{_DASH}\s*(?P<high>{_NUM}))?"
    rf"\s*"
    rf"(?P<unit>{_UNIT})(?![A-Za-z])"
    rf"(?:"
    rf"\s*\(\s*"
    rf"(?P<alt_low>{_NUM})"
    rf"(?:\s*{_DASH}\s*(?P<alt_high>{_NUM}))?"
    rf"\s*"
    rf"(?P<alt_unit>{_UNIT})(?![A-Za-z])"
    rf"\s*\)"
    rf")?",
    re.IGNORECASE,
)

_ATTRS = (
    ("body length", "body_length"),
    ("carapace length", "carapace_length"),
    ("weighing", "weight"),
    ("weighs", "weight"),
        ("weigh", "weight"),
        ("weight", "weight"),
        ("mass", "mass"),
        ("length", "length"),
    )

_ENGLISH_IN = re.compile(
    r"\s+(?:the|a|an|this|that|these|those|which|order)\b",
    re.IGNORECASE,
)


def extract_literal_numeric_claims(text: str) -> dict[str, float]:
    """Named floats for measurements written in `text`."""
    return extract_stated_measurements(text)[0]


def measurement_provenance(text: str) -> dict[str, dict[str, Any]]:
    """Qualifier, bound, and source span for each named measurement."""
    return extract_stated_measurements(text)[1]


def extract_stated_measurements(text: str) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    claims: dict[str, float] = {}
    provenance: dict[str, dict[str, Any]] = {}
    if not text:
        return claims, provenance
    for match in _MEASUREMENT.finditer(text):
        if _english_preposition(text, match, "unit"):
            continue
        attribute = _attribute(text[: match.start()], text[match.end() :])
        if attribute is None:
            continue
        qualifier = _qualifier(match.group("qual"))
        if qualifier == "exact" and match.group("high") is None:
            inherited = _prefix_qualifier(text[: match.start()])
            if inherited is not None:
                qualifier = inherited
        context = text[match.start() : match.end()]
        _record_pair(
            claims,
            provenance,
            text,
            attribute,
            match,
            "unit",
            "low",
            "high",
            qualifier,
            context,
        )
        if match.group("alt_low") and not _english_preposition(text, match, "alt_unit"):
            _record_pair(
                claims,
                provenance,
                text,
                attribute,
                match,
                "alt_unit",
                "alt_low",
                "alt_high",
                qualifier,
                context,
            )
    return claims, provenance


def _record_pair(
    claims: dict[str, float],
    provenance: dict[str, dict[str, Any]],
    text: str,
    attribute: str,
    match: re.Match[str],
    unit_group: str,
    low_group: str,
    high_group: str,
    qualifier: str,
    context: str,
) -> None:
    raw_unit = match.group(unit_group)
    if raw_unit is None:
        return
    unit = _UNIT_MAP.get(raw_unit.lower())
    if unit is None:
        return
    raw_high = match.group(high_group)
    is_range = raw_high is not None
    _put(
        claims,
        provenance,
        text,
        attribute,
        unit,
        match.group(low_group),
        match.start(low_group),
        match.end(low_group),
        "low" if is_range else "point",
        qualifier,
        context,
        is_range,
    )
    if is_range:
        _put(
            claims,
            provenance,
            text,
            attribute,
            unit,
            raw_high,
            match.start(high_group),
            match.end(high_group),
            "high",
            qualifier,
            context,
            True,
        )


def _put(
    claims: dict[str, float],
    provenance: dict[str, dict[str, Any]],
    text: str,
    attribute: str,
    unit: str,
    raw_value: str,
    start: int,
    end: int,
    bound: str,
    qualifier: str,
    context: str,
    is_range: bool,
) -> None:
    source = text[start:end]
    if source != raw_value or raw_value not in context:
        return
    key = f"{attribute}_{unit}" if bound == "point" else f"{attribute}_{unit}_{'min' if bound == 'low' else 'max'}"
    value = float(raw_value)
    final = key
    suffix = 2
    while final in claims and claims[final] != value:
        final = f"{key}_{suffix}"
        suffix += 1
    kind = qualifier
    if qualifier == "exact" and is_range:
        kind = "minimum" if bound == "low" else "maximum"
    claims[final] = value
    provenance[final] = {
        "qualifier": kind,
        "bound": bound,
        "start": start,
        "end": end,
        "source": source,
        "context": context,
        "unit": unit,
        "attribute": attribute,
    }


def _attribute(prefix: str, suffix: str) -> str | None:
    window = prefix[-48:].lower()
    best_end = -1
    best_len = -1
    best_key: str | None = None
    for phrase, key in _ATTRS:
        at = window.rfind(phrase)
        if at < 0:
            continue
        end = at + len(phrase)
        if end > best_end or (end == best_end and len(phrase) > best_len):
            best_end = end
            best_len = len(phrase)
            best_key = key
    if best_key is not None:
        return best_key
    if re.match(r"\s*long\b", suffix, re.IGNORECASE):
        return "length"
    return None


def _prefix_qualifier(prefix: str) -> str | None:
    window = prefix[-64:].lower()
    best_at = -1
    best: str | None = None
    for phrase, kind in (
        ("up to", "maximum"),
        ("grown to", "maximum"),
        ("grows to", "maximum"),
        ("grow to", "maximum"),
        ("at least", "minimum"),
        ("minimum", "minimum"),
        ("maximum", "maximum"),
        ("approximately", "approximate"),
        ("about", "approximate"),
        ("around", "approximate"),
    ):
        at = window.rfind(phrase)
        if at > best_at:
            best_at = at
            best = kind
    return best


def _qualifier(raw: str | None) -> str:
    if not raw:
        return "exact"
    text = re.sub(r"\s+", " ", raw.lower()).strip().rstrip(".")
    if text in {"about", "approximately", "around", "nearly", "approx"}:
        return "approximate"
    if text in {"at least", "more than"}:
        return "minimum"
    if text in {"up to", "less than"}:
        return "maximum"
    return "exact"


def _english_preposition(text: str, match: re.Match[str], group: str) -> bool:
    unit = match.group(group)
    if unit is None or unit.lower() != "in":
        return False
    return _ENGLISH_IN.match(text[match.end(group) :]) is not None
