"""Explicit supplied-number comparisons, never a clinical suitability decision."""
from decimal import Decimal
import re

_N = r'[+-]?\d{1,24}(?:\.\d{1,12})?'
_U = r'(?:mcg|mg|kg|g|mL|L)'
_SIMPLE = re.compile(rf'Does (?P<amount>{_N}) (?P<unit>{_U}) exceed (?P<limit>{_N}) (?P<limit_unit>{_U})\?')
_INLINE = re.compile(rf'A (?:fictional )?(?:label|policy|rule) states a maximum [a-z ]{{1,60}} of '
    rf'(?P<limit>{_N}) (?P<limit_unit>{_U})\. Does a supplied total of (?P<amount>{_N}) '
    rf'(?P<unit>{_U}) exceed that (?:label |policy |rule )?limit\?')


def compare_prompt(message):
    if re.search(r'\b(?:if|unless|when|except|not)\b|["`“”]', message, re.I):
        return None
    match = _SIMPLE.fullmatch(message.strip()) or _INLINE.fullmatch(message.strip())
    # No inferred unit conversion or case-folding of unit symbols in this grammar.
    if not match or match['unit'] != match['limit_unit']:
        return None
    amount, limit = Decimal(match['amount']), Decimal(match['limit'])
    exceeds = amount > limit
    text = (f"{match['amount']} {match['unit']} " + ('exceeds' if exceeds else 'does not exceed') +
            f" the supplied limit of {match['limit']} {match['unit']}. Numeric comparison only; not treatment advice.")
    return dict(ok=True, operation='greater_than', operands=[match['amount'], match['limit']],
                unit=match['unit'], value=str(exceeds).lower(), display=text, text=text,
                expression=f"{match['amount']} > {match['limit']}", clinical_validation=False)
