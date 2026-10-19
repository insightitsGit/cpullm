"""Scaled-integer amounts for finance validation.

Floats are refused. A JSON number with a fraction is a float, and accepting
one would make the same request produce different integers on different
machines. Strings and whole integers are exact.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Any

RATIO_SCALE = 6
AMOUNT_SCALE = 6
_DIVISION_PRECISION = 60

ROUNDING_MODES = {
    "ROUND_HALF_UP": ROUND_HALF_UP,
    "ROUND_HALF_EVEN": ROUND_HALF_EVEN,
    "ROUND_DOWN": ROUND_DOWN,
}
DEFAULT_ROUNDING = "ROUND_HALF_UP"
_STRIP = str.maketrans("", "", "$,\u00a0 ")


class FinanceInputError(ValueError):
    """The request named a value the check cannot use."""


def parse_amount(raw: Any, *, scale: int = AMOUNT_SCALE) -> int:
    """Parse a human amount to a scaled integer.

    An int is a count of whole units. A string may include a thousands
    separator, a leading currency sign, a trailing ``x``, or accounting
    parentheses. A float is refused.
    """
    if isinstance(raw, bool):
        raise FinanceInputError("A boolean is not an amount.")
    if isinstance(raw, float):
        raise FinanceInputError("A float is not an amount. Pass a decimal string or a whole integer.")
    if isinstance(raw, int):
        return raw * (10**scale)
    if isinstance(raw, Decimal):
        value = raw
    elif isinstance(raw, str):
        cleaned = raw.strip().translate(_STRIP)
        if cleaned.endswith(("x", "X")):
            cleaned = cleaned[:-1]
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        if not cleaned:
            raise FinanceInputError("An amount is empty.")
        try:
            value = Decimal(cleaned)
        except InvalidOperation:
            raise FinanceInputError(f"{raw!r} is not a decimal amount.") from None
    else:
        raise FinanceInputError(f"Cannot parse an amount of type {type(raw).__name__}.")
    if not value.is_finite():
        raise FinanceInputError("An amount must be finite.")
    shifted = value.scaleb(scale)
    if shifted != shifted.to_integral_value():
        raise FinanceInputError(
            f"{raw!r} has more precision than scale {scale} can store. "
            "The extra digits are not rounded away."
        )
    return int(shifted)


def format_amount(value_scaled: int, *, scale: int = AMOUNT_SCALE, currency: str = "USD") -> str:
    quantum = Decimal(1).scaleb(-scale)
    value = Decimal(value_scaled).scaleb(-scale).quantize(quantum)
    sign = "-" if value < 0 else ""
    whole = abs(value).to_integral_value(rounding=ROUND_DOWN)
    cents = (abs(value) - whole).scaleb(2).to_integral_value(rounding=ROUND_HALF_UP)
    return f"{sign}{currency} {int(whole):,}.{int(cents):02d}"


def format_ratio(value_scaled: int, *, scale: int = RATIO_SCALE, places: int = 2) -> str:
    value = Decimal(value_scaled).scaleb(-scale)
    shown = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return f"{shown}x"


def divide(
    numerator_scaled: int,
    denominator_scaled: int,
    *,
    result_scale: int = RATIO_SCALE,
    rounding: str = DEFAULT_ROUNDING,
) -> int:
    """Scaled division. Input scales cancel when they already match."""
    if denominator_scaled == 0:
        raise FinanceInputError("A ratio against a zero denominator is refused.")
    mode = ROUNDING_MODES.get(rounding)
    if mode is None:
        raise FinanceInputError(f"Unknown rounding mode {rounding!r}.")
    with localcontext() as ctx:
        ctx.prec = _DIVISION_PRECISION
        quotient = Decimal(numerator_scaled) / Decimal(denominator_scaled)
        scaled = quotient.scaleb(result_scale).quantize(Decimal(1), rounding=mode)
    return int(scaled)


def add(*values_scaled: int) -> int:
    total = 0
    for value in values_scaled:
        if isinstance(value, float):
            raise FinanceInputError("A float is not an amount.")
        total += int(value)
    return total


def apply_percentage_cap(
    value_scaled: int,
    *,
    basis_scaled: int,
    percent_scaled: int,
    percent_scale: int = RATIO_SCALE,
) -> tuple[int, bool]:
    """Cap ``value_scaled`` at a percentage of ``basis_scaled``.

    Returns the applied amount and whether the cap bound it.
    """
    with localcontext() as ctx:
        ctx.prec = _DIVISION_PRECISION
        cap = (Decimal(basis_scaled) * Decimal(percent_scaled).scaleb(-percent_scale)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    cap_int = int(cap)
    if value_scaled > cap_int:
        return cap_int, True
    return value_scaled, False


def compare(left_scaled: int, comparator: str, right_scaled: int) -> bool:
    if comparator == "lte":
        return left_scaled <= right_scaled
    if comparator == "gte":
        return left_scaled >= right_scaled
    if comparator == "lt":
        return left_scaled < right_scaled
    if comparator == "gt":
        return left_scaled > right_scaled
    if comparator == "eq":
        return left_scaled == right_scaled
    raise FinanceInputError(f"Unknown comparator {comparator!r}.")


def headroom(computed_scaled: int, comparator: str, threshold_scaled: int) -> int:
    """Signed distance to the limit. Positive means the test passed."""
    if comparator in ("lte", "lt"):
        return threshold_scaled - computed_scaled
    if comparator in ("gte", "gt"):
        return computed_scaled - threshold_scaled
    if comparator == "eq":
        return -abs(computed_scaled - threshold_scaled)
    raise FinanceInputError(f"Unknown comparator {comparator!r}.")
