"""Opt-in analyses of explicitly structured, source-bound evidence records.

No document text is executed and no statistical/explanatory result is a proof.
"""
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
import math
import re


def _record_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Structured evidence contains a duplicate JSON key.')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f'Nonstandard JSON constant {value} is not evidence.')


@dataclass(frozen=True)
class EvidenceAnalysisRequest:
    mode: str
    source_ids: tuple[str, ...]

    def __post_init__(self):
        if self.mode not in {'temporal', 'inductive', 'abductive'}:
            raise ValueError('Unsupported structured inference mode.')
        if not isinstance(self.source_ids, (tuple, list)) or not 1 <= len(self.source_ids) <= 256:
            raise ValueError('Select 1 to 256 explicit source chunk IDs.')
        if any(not isinstance(value, str) or not re.fullmatch(r'[\w.-]{1,200}', value)
               for value in self.source_ids) or len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError('Source IDs must be distinct explicit chunk IDs.')
        object.__setattr__(self, 'source_ids', tuple(sorted(self.source_ids)))


def analysis_request(message, option=None):
    if isinstance(option, dict) and option.get('mode') in {'temporal', 'inductive', 'abductive'}:
        try:
            return EvidenceAnalysisRequest(**option)
        except TypeError as exc:
            raise ValueError('Structured inference requires only mode and source_ids.') from exc
    if option is not None:
        return None
    match = re.fullmatch(r'(Temporal|Induction|Abduction):\s*sources:\s*([\w., -]+)', message.strip(), re.I)
    if match:
        mode = {'temporal': 'temporal', 'induction': 'inductive', 'abduction': 'abductive'}[match[1].lower()]
        return EvidenceAnalysisRequest(mode, tuple(value.strip() for value in match[2].split(',')))
    return None


def analyze(rows, request, *, snapshot=None, scope=None):
    from cpu_llm.access import source_allowed
    from cpu_llm.inference import digest

    selected = [row for row in rows if row['document_id'] in request.source_ids
                and source_allowed(row['document_id'], scope)]
    receipt = dict(schema='structured-inference-v1', mode=request.mode,
                   request=asdict(request), snapshot=snapshot,
                   scope=sorted(scope) if scope is not None else None,
                   verdict='INSUFFICIENT_SUPPORT', claim_status='UNRESOLVED', evidence=[])
    receipt['request']['source_ids'] = list(request.source_ids)
    if {row['document_id'] for row in selected} != set(request.source_ids) or len(selected) != len(request.source_ids):
        receipt['reason'] = 'The authorized snapshot does not contain every selected source exactly once.'
    else:
        try:
            records = []
            for row in sorted(selected, key=lambda r: r['document_id']):
                text = row['chunk_text']
                if len(text) > 65536:
                    raise ValueError('A structured record exceeds 65536 characters.')
                record = json.loads(text, object_pairs_hook=_record_object, parse_constant=_invalid_constant)
                if not isinstance(record, dict) or record.get('schema') != 'inference-record-v1':
                    raise ValueError('Each source chunk must contain one inference-record-v1 JSON object.')
                records.append(record)
                receipt['evidence'].append(dict(document_id=row['document_id'], span=text, start=0,
                    end=len(text), chunk_sha256=hashlib.sha256(text.encode()).hexdigest(),
                    source_version=row.get('source_version')))
            if request.mode == 'temporal':
                receipt.update(_temporal(records))
            elif request.mode == 'inductive':
                receipt.update(_inductive(records))
            else:
                from cpu_llm.abductive_bridge import AbductiveBridgeNode
                receipt.update(AbductiveBridgeNode().compare_explanations(records))
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            receipt['reason'] = str(exc)
    receipt['audit_hash'] = digest(receipt)
    return receipt


def _temporal(records):
    if len(records) != 2 or any(r.get('kind') != 'interval' for r in records):
        raise ValueError('Temporal analysis requires exactly two interval records.')
    intervals = []
    for record in records:
        values = [record[key] for key in ('start', 'end')]
        if any(not isinstance(v, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v) for v in values):
            raise ValueError('Temporal intervals require explicit ISO calendar dates YYYY-MM-DD.')
        start, end = map(date.fromisoformat, values)
        if end < start:
            raise ValueError('An interval end precedes its start.')
        intervals.append((start, end))
    left, right = intervals
    low, high = max(left[0], right[0]), min(left[1], right[1])
    return dict(verdict='CALCULATED', claim_status='TEMPORAL_CALCULATION',
                policy='closed calendar-date intervals; no timezone or current-validity inference',
                overlaps=low <= high,
                intersection=[low.isoformat(), high.isoformat()] if low <= high else None,
                first_before_second=left[1] < right[0], second_before_first=right[1] < left[0])


def _inductive(records):
    if any(r.get('kind') != 'bernoulli' or type(r.get('success')) is not bool for r in records):
        raise ValueError('Induction requires explicit Bernoulli observations with boolean success.')
    groups = {r.get('population') for r in records}
    identifiers = [r.get('observation_id') for r in records]
    if len(groups) != 1 or not all(isinstance(v, str) and v for v in (*groups, *identifiers)):
        raise ValueError('Observations require one explicit population and nonempty observation IDs.')
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Duplicate observations cannot be counted as independent samples.')
    n, successes = len(records), sum(r['success'] for r in records)
    p, z = successes / n, 1.959963984540054
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n)) / denominator
    radius = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denominator
    return dict(verdict='ESTIMATED', claim_status='STATISTICAL_ESTIMATE', sample_size=n,
                successes=successes, population=next(iter(groups)), proportion=p,
                interval_95=[max(0., center-radius), min(1., center+radius)],
                policy='Wilson score interval; assumes independent Bernoulli observations',
                limitation='Sampling bias and independence are not verified; no universal or causal conclusion.')
