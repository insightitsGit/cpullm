"""Checked interval joins over explicitly structured, cited claims."""
import hashlib
import json
import re
from fractions import Fraction

_PREFIX = 'CrossDomain claim: '
_KEYS = ('topic', 'quantity', 'conditions', 'convention')
_UNITS = {
    '1': ('1', 0), 'eV': ('eV', 0), 'meV': ('eV', -3), 'keV': ('eV', 3),
    'MeV': ('eV', 6), 'GeV': ('eV', 9), 'kg': ('kg', 0), 'g': ('kg', -3),
    'mg': ('kg', -6), 'm': ('m', 0), 'cm': ('m', -2), 'mm': ('m', -3),
    'km': ('m', 3),
}


def _label(value):
    return ' '.join(value.casefold().split()) if isinstance(value, str) else ''


def _endpoint(value, exponent):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'[+-]?\d{1,24}(?:\.\d{1,24})?(?:[eE][+-]?\d{1,2})?', value):
        raise ValueError('Endpoints must be bounded decimal strings.')
    return Fraction(value) * Fraction(10) ** exponent


def _interval(claim):
    unit = claim.get('unit')
    if not isinstance(unit, str) or unit not in _UNITS or not _label(claim.get('interval_basis')):
        raise ValueError('Each numerical claim needs a supported unit and an interval basis.')
    base, exponent = _UNITS[unit]
    low, high = (_endpoint(claim.get(key), exponent) for key in ('lower', 'upper'))
    if low is None or high is None:
        if claim['role'] != 'bound' or low is high:
            raise ValueError('Provide both uncertainty endpoints, or at least one endpoint for a bound.')
    elif low > high:
        raise ValueError('An interval has reversed endpoints.')
    return base, low, high


def compare_claims(rows, requested, topic):
    """Return no match for the legacy path, or a checked/unresolved structured join."""
    claims = {domain: [] for domain in requested}
    for row in rows:
        document, chunk = row['document_id'], row['chunk_text']
        domain = document.split('-', 1)[0].casefold()
        domain = 'mathematics' if domain == 'math' else domain
        if domain not in claims or not chunk.startswith(_PREFIX) or len(chunk) > 2000:
            continue
        try:
            claim = json.loads(chunk[len(_PREFIX):])
        except (ValueError, RecursionError):
            continue
        if isinstance(claim, dict) and _label(claim.get('topic')) == _label(topic):
            claims[domain].append((claim, row))
    if not any(claims.values()):
        return None
    if any(len(matches) != 1 for matches in claims.values()):
        domains = ', '.join(domain for domain, matches in claims.items() if len(matches) != 1)
        return f'Provide exactly one matching structured claim in each of these KBs: {domains}.', None

    selected = [claims[domain][0] for domain in requested]
    signatures = {tuple(_label(claim.get(key)) for key in _KEYS) for claim, _ in selected}
    if len(signatures) != 1 or not all(next(iter(signatures))):
        return 'The claims need matching quantity, conditions, and convention.', None
    roles = [claim.get('role') for claim, _ in selected]
    numeric_roles = [role for role in roles if role != 'method']
    if (numeric_roles not in (['prediction', 'bound'], ['bound', 'prediction'], ['measurement', 'measurement'])
            or roles.count('method') > 1 or ('prediction' in roles and 'method' not in roles)):
        return 'Provide a prediction, bound, and method, or two measurements with an optional method.', None
    if any(claim.get('operation') != 'compare_intervals' for claim, _ in selected if claim['role'] == 'method'):
        return 'The method must cite the supported compare_intervals operation.', None
    numeric = [(claim, row) for claim, row in selected if claim['role'] != 'method']
    try:
        intervals = [_interval(claim) for claim, _ in numeric]
    except ValueError as exc:
        return str(exc), None
    if (intervals[0][0] != intervals[1][0]
            or _label(numeric[0][0]['interval_basis']) != _label(numeric[1][0]['interval_basis'])):
        return 'The numerical claims need compatible units and matching interval bases.', None

    if 'prediction' in roles:
        if numeric[0][0]['role'] == 'bound':
            intervals.reverse()
        _, low, high = intervals[0]
        _, floor, ceiling = intervals[1]
        if (floor is not None and high < floor) or (ceiling is not None and low > ceiling):
            outcome = 'outside_bound'
        elif (floor is None or low >= floor) and (ceiling is None or high <= ceiling):
            outcome = 'within_bound'
        else:
            outcome = 'overlaps_bound'
        interval_roles = ('prediction', 'bound')
    else:
        _, low, high = intervals[0]
        _, other_low, other_high = intervals[1]
        outcome = 'disjoint_intervals' if high < other_low or other_high < low else 'overlapping_intervals'
        interval_roles = ('measurement', 'measurement')

    premises = []
    for domain, (claim, row) in zip(requested, selected):
        quote = row['chunk_text']
        premises.append(dict(domain=domain, role=claim['role'], document_id=row['document_id'], quote=quote,
                             start=0, end=len(quote), chunk_sha256=hashlib.sha256(quote.encode()).hexdigest()))
    normalized = [dict(role=role, unit=unit, lower=None if low is None else str(low),
                       upper=None if high is None else str(high))
                  for role, (unit, low, high) in zip(interval_roles, intervals)]
    return None, dict(key='structured_claim:compare_intervals', operation='compare_intervals/v1',
                      outcome=outcome, normalized_intervals=normalized, premises=premises)
