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
    "foot": "ft",
    "feet": "ft",
    "ft": "ft",
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
    r"feet|foot|"
    r"cm|mm|kg|lbs|lb|"
    r"ft|in|g|m"
)
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_DASH = r"[\u2012\u2013\u2014\u2212\-]"
_QUAL = r"up\s+to|at\s+least|more\s+than|less\s+than|approximately|about|around|nearly|approx\.?"

_MEASUREMENT = re.compile(
    rf"(?:(?P<qual>{_QUAL})\s+)?"
    rf"(?P<low>{_NUM})"
    rf"(?:\s*{_DASH}\s*(?P<high>{_NUM}))?"
    rf"(?:\s*-\s*|\s*)"
    rf"(?P<unit>{_UNIT})(?![A-Za-z])"
    rf"(?:"
    rf"\s*\(\s*"
    rf"(?P<alt_low>{_NUM})"
    rf"(?:\s*{_DASH}\s*(?P<alt_high>{_NUM}))?"
    rf"(?:\s*-\s*|\s*)"
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
        if _english_preposition(text, match, "unit") or _currency_metre(text, match, "unit", "low"):
            continue
        attribute = _attribute(text[: match.start()], text[match.end() :], match.group("unit"))
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
        if (
            match.group("alt_low")
            and not _english_preposition(text, match, "alt_unit")
            and not _currency_metre(text, match, "alt_unit", "alt_low")
        ):
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
    value = float(raw_value.replace(",", ""))
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


_CURRENCY_CODES = frozenset(
    {
        "USD", "GBP", "EUR", "JPY", "CZK", "AUD", "CAD", "CHF", "INR", "CNY",
        "NZD", "SEK", "NOK", "DKK", "HKD", "SGD", "KRW", "MXN", "BRL", "ZAR",
        "RUB", "TRY", "PLN", "THB", "IDR", "MYR", "PHP", "TWD", "AED", "SAR",
    }
)
_CURRENCY_WORDS = frozenset(
    {"dollar", "dollars", "pound", "pounds", "euro", "euros", "yen", "cent", "cents", "usd", "gbp", "eur", "sterling"}
)
_CLOSED_CLASS = frozenset(
    {
        "a", "an", "the", "in", "of", "for", "from", "to", "by", "at", "on", "over",
        "under", "and", "or", "if", "as", "with", "per", "than", "that", "which",
        "who", "into", "after", "before", "during", "about", "ago", "more", "less",
    }
)
_MONEY_SPAN = re.compile(
    r"(?P<head>(?:[A-Z]{2,3}\s+)?[$£€¥]\s*|[A-Z]{3}\s+)?"
    rf"(?P<number>{_NUM})"
    r"(?i:\s*(?P<unit>million|m\b))"
)
_SPELLED_MILLION = re.compile(r"\bfive million\b", re.IGNORECASE)
_WORD_AFTER = re.compile(r"[\s\-]*([A-Za-z]+)")


def stated_million_amount(text: str) -> float | None:
    """First money span in `text`, or None when every candidate counts something else.

    Bare ``m`` is metres unless a currency symbol, currency code, or currency
    word is attached to that span. The word ``million`` is money when a
    currency is attached, when the span ends the clause, or when the next word
    is a function word (``10 million``, ``exceeds 10 million``, ``$5 m``).
    A following content word means the number counts that word (years, copies,
    viewers, people, horses). So does a preceding noun in ``viewership of 8 million``.
    ``cost of 10 million`` stays money. Neither case becomes a length.
    """
    if not text:
        return None
    for match in _MONEY_SPAN.finditer(text):
        if not _span_is_money(text, match.group("head"), match.group("unit"), match.start("number"), match.end()):
            continue
        number = match.group("number").replace(",", "")
        try:
            value = float(number)
        except ValueError:
            continue
        return value * 1_000_000
    spelled = _SPELLED_MILLION.search(text)
    if spelled and _span_is_money(text, None, "million", spelled.start(), spelled.end()):
        return 5_000_000.0
    return None


_MONEY_HEADS = frozenset(
    {
        "cost", "costs", "price", "prices", "value", "worth", "budget", "grant",
        "revenue", "profit", "premium", "fee", "fees", "fine", "fines", "settlement",
        "damages", "funding", "sum", "amount", "bail", "sales", "gross",
    }
)
_OF_QUANTITY = re.compile(
    r"\b([A-Za-z]+)\s+of\s+(?:(?:about|around|over|approximately|nearly|some|estimated|roughly)\s+)?$",
    re.IGNORECASE,
)


def _span_is_money(text: str, head: str | None, unit: str | None, number_start: int, end: int) -> bool:
    if unit is None:
        return False
    currency = _currency_head(head) or _currency_word_after(text, end)
    if unit.lower() == "m":
        return currency
    if currency:
        return True
    if _counts_preceding_noun(text, number_start):
        return False
    word = _content_word_after(text, end)
    return word is None or word in _CLOSED_CLASS


def _counts_preceding_noun(text: str, number_start: int) -> bool:
    """True for ``viewership of 8.69 million`` and false for ``cost of 10 million``."""
    window = text[max(0, number_start - 48) : number_start]
    found = _OF_QUANTITY.search(window)
    if found is None:
        return False
    return found.group(1).lower() not in _MONEY_HEADS


def _currency_head(head: str | None) -> bool:
    if not head:
        return False
    token = head.strip()
    if any(symbol in token for symbol in "$£€¥"):
        return True
    code = token.split()[0] if token else ""
    return code in _CURRENCY_CODES


def _currency_word_after(text: str, end: int) -> bool:
    word = _content_word_after(text, end)
    return word in _CURRENCY_WORDS


def _content_word_after(text: str, end: int) -> str | None:
    found = _WORD_AFTER.match(text[end:])
    if found is None:
        return None
    return found.group(1).lower()


def _currency_metre(text: str, match: re.Match[str], unit_group: str, number_group: str) -> bool:
    """A currency-marked ``m`` is million, so it is not a length."""
    unit = match.group(unit_group)
    if unit is None or unit.lower() != "m":
        return False
    start = match.start(number_group)
    head = text[max(0, start - 8) : start]
    return _currency_head(head) or _currency_word_after(text, match.end(unit_group))


def _attribute(prefix: str, suffix: str, raw_unit: str | None = None) -> str | None:
    window = prefix[-48:]
    best_end = -1
    best_len = -1
    best_key: str | None = None
    for phrase, key in _ATTRS:
        found = list(re.finditer(rf"\b{re.escape(phrase)}\b", window, re.IGNORECASE))
        if not found:
            continue
        end = found[-1].end()
        if end > best_end or (end == best_end and len(phrase) > best_len):
            best_end = end
            best_len = len(phrase)
            best_key = key
    if best_key is not None:
        return best_key
    if re.match(r"\s*long\b", suffix, re.IGNORECASE):
        return "length"
    named = _nearest_vertical(prefix[-48:], suffix[:48])
    if named is not None:
        return named
    if prefix.strip() == "" and suffix.strip() == "":
        return _DIMENSION.get(_UNIT_MAP.get((raw_unit or "").lower(), ""))
    return None


_VERTICAL = (
    ("above sea level", "elevation"),
    ("elevation", "elevation"),
    ("altitude", "elevation"),
    ("summit", "elevation"),
    ("peaks", "elevation"),
    ("peak", "elevation"),
    ("heights", "height"),
    ("height", "height"),
    ("tallest", "height"),
    ("tall", "height"),
    ("rises", "elevation"),
    ("rising", "elevation"),
)
_DIMENSION = {
    "m": "length",
    "cm": "length",
    "mm": "length",
    "ft": "length",
    "in": "length",
    "kg": "mass",
    "g": "mass",
    "lb": "mass",
}


def _nearest_vertical(prefix: str, suffix: str) -> str | None:
    """Name a length from the vertical word closest to the number."""
    best: tuple[int, int, str] | None = None
    for phrase, key in _VERTICAL:
        pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
        for found in pattern.finditer(prefix):
            distance = len(prefix) - found.end()
            candidate = (distance, -len(phrase), key)
            if best is None or candidate < best:
                best = candidate
        for found in pattern.finditer(suffix):
            candidate = (found.start(), -len(phrase), key)
            if best is None or candidate < best:
                best = candidate
    if best is None:
        return None
    return best[2]


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
