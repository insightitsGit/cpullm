"""Independent channel predicates for a source-backed connection.

Membership is multi-label, not a choice of one channel. Symbolic evidence and
calibrated vector matches are recorded separately. A missing evaluation is
unknown, never a positive result. Epistemic truth is header metadata, not a
seventh semantic slice and not implied by finding a sentence.
"""
from __future__ import annotations

import math
import re
import numpy as np
from vectorprism.tensor_contract import PSMTensorContract as C
from cpu_llm.geometry.poincare import poincare_distance

CHANNEL_SLICES = {
    'dense': C.DENSE_CORE, 'relational': C.RELATIONAL,
    'disentangled': C.DISENTANGLED, 'hyperbolic': C.HYPERBOLIC,
    'identity': C.IDENTITY, 'causal': C.CAUSAL_TIME,
}
_RELATIONS = {'is_a', 'alias_of', 'lives_in', 'has_color', 'has', 'causes', 'differs_from'}


def relational_connection(fact) -> bool:
    return fact.relation in _RELATIONS


def taxonomy_connection(fact) -> bool:
    return fact.relation == 'is_a'


def identity_connection(fact) -> bool:
    return fact.relation == 'alias_of'


def causal_connection(fact) -> bool:
    return fact.relation == 'causes'


def contrast_connection(fact) -> bool:
    return fact.relation == 'differs_from'


_PREDICATES = {
    'relational': (relational_connection, 'explicit source relation'),
    'hyperbolic': (taxonomy_connection, 'explicit type membership; not a geometry claim'),
    'identity': (identity_connection, 'explicit alias; not an anchor-distance claim'),
    'causal': (causal_connection, 'explicit directed cause'),
    # A contrast is evidence relevant to separating meanings, not proof that
    # a disabled VIB head has learned independent latent factors.
    'disentangled': (contrast_connection, 'explicit contrast; not a learned-factor claim'),
}


def _vector(value):
    if value is None:
        return None
    vector = np.asarray(value, dtype=np.float64)
    # Header timestamps/bitmasks use bit reinterpretation, not float scores.
    if vector.shape != (C.TOTAL_DIM,) or not np.isfinite(vector[C.HEADER.end:]).all():
        return None
    return vector


def channel_similarity(name, left, right, causal_matrix=None):
    """Score one channel with its own metric; larger scores mean closer."""
    region = CHANNEL_SLICES[name]
    a, b = left[region.start:region.end], right[region.start:region.end]
    if name in {'dense', 'disentangled'}:
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        return float(a @ b / norm) if norm > 0 else None
    if name in {'relational', 'identity'}:
        return -float(np.linalg.norm(a - b))
    if name == 'hyperbolic':
        if np.linalg.norm(a) >= 1 or np.linalg.norm(b) >= 1:
            return None
        return -float(poincare_distance(a, b))
    if causal_matrix is not None:
        matrix = np.asarray(causal_matrix, dtype=np.float64)
        if matrix.shape == (region.length, region.length) and np.isfinite(matrix).all():
            return float(a @ matrix @ b)
    return None


def evaluate_connection(fact, *, enabled_channels=None, left_tensor=None,
                        right_tensor=None, thresholds=None, causal_matrix=None):
    """Evaluate all six functions. Thresholds must come from caller calibration.

    Numeric scores use higher-is-closer convention (distances are negated).
    Disabled heads do not vote even if their tensor positions contain numbers.
    `active` means a supported channel association, not a proved world fact.
    """
    flags, thresholds = enabled_channels or {}, thresholds or {}
    left, right = _vector(left_tensor), _vector(right_tensor)
    source = ' ' + ' '.join(fact.sentence.casefold().split()) + ' '
    def present(value):
        value = ' '.join(value.casefold().split())
        return bool(value) and re.search(rf'(?<!\w){re.escape(value)}(?!\w)', source) is not None
    evidence = bool(fact.document_id and present(fact.subject) and present(fact.object))
    signals = {}
    for name in CHANNEL_SLICES:
        predicate, basis = _PREDICATES.get(name, (lambda _: False, 'requires calibrated dense similarity'))
        symbolic = evidence and predicate(fact)
        enabled = bool(flags.get(name, False))
        score = channel_similarity(name, left, right, causal_matrix) if enabled and left is not None and right is not None else None
        if score is not None and not math.isfinite(score):
            score = None
        threshold = thresholds.get(name)
        if threshold is not None and (not isinstance(threshold, (int, float)) or not math.isfinite(threshold)):
            raise ValueError(f'{name} threshold must be finite')
        matched = bool(score >= threshold) if score is not None and threshold is not None else None
        active = True if symbolic or matched is True else False if matched is False else None
        signals[name] = dict(active=active, symbolic_supported=bool(symbolic),
                             vector_match=matched, vector_score=score, head_enabled=enabled,
                             vector_threshold=threshold,
                             basis=basis if symbolic else 'no symbolic support',
                             vector_status='disabled' if not enabled else 'unavailable' if score is None
                             else 'uncalibrated' if threshold is None else 'evaluated')
    return dict(schema='connection-channels-v1', channels=signals, epistemic=dict(source_supported=evidence, truth_score=None,
                                               basis='source attribution does not establish truth'))
