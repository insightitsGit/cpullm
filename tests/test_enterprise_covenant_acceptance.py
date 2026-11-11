"""Fictional gold decisions for the initial covenant pilot workflow."""
from decimal import Decimal, ROUND_HALF_UP

import pytest

from cpu_llm.finance import validate_message


@pytest.mark.parametrize(("numerator", "verdict"), [
    (8_999_998, "COMPLIANT"),
    (9_000_000, "COMPLIANT"),
    (9_000_001, "BREACH"),
])
def test_covenant_pilot_threshold_and_rounding(numerator, verdict):
    denominator = 2_000_000
    expected = (Decimal(numerator) / denominator).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    [check] = validate_message(
        f"Decide this LedgerCovenant test.\ncomparator: lte\nthreshold: 4.50\nratio places: 6\n"
        f"numerator: compliance_certificate {numerator}\ndenominator: compliance_certificate {denominator}"
    )["checks"]
    assert check["computed_scaled"] == int(expected * 1_000_000)
    assert check["verdict"] == verdict
    assert check["numerator"]["source"] == check["denominator"]["source"] == "compliance_certificate"


@pytest.mark.parametrize(("fields", "verdict"), [
    ("numerator: compliance_certificate 2", "INCOMPLETE"),
    ("threshold: 4.5\nnumerator: compliance_certificate 1\ndenominator: compliance_certificate 0", "INPUT_INVALID"),
    ("threshold: 4.5\nnumerator: compliance_certificate 9\n"
     "numerator: compliance_certificate 10\ndenominator: compliance_certificate 2", "FACT_CONFLICT"),
])
def test_covenant_pilot_withholds_invalid_or_conflicting_inputs(fields, verdict):
    [check] = validate_message(f"Decide this LedgerCovenant test.\n{fields}")["checks"]
    assert check["verdict"] == verdict
    assert check.get("computed_scaled") is None
