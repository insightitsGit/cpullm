"""Variable types for Deepen test plans: what can be varied, what is fixed, what is a stressor, what is measured.

A design depends on what each variable is. Pauli weight is a property of the observable, not a dial, so a 2x2
factorial that "varies" it is invalid; the right design compares strata. Types come from a small cue lexicon over
stemmed terms (``term_key``), with the head noun deciding outcome metrics. A user definition may set the type
explicitly: ``definitions={"<term>": {"type": "observable_property"}}``. Unknown stays unknown; nothing is guessed.
"""
from __future__ import annotations

from cpu_llm.frontier import term_head, term_key

TYPES = ('intervention', 'observable_property', 'noise_channel', 'outcome_metric', 'unknown')

_NOISE_PHRASES = tuple(term_key(p) for p in ('dielectric loss', 'ohmic loss', 'photon loss', 'two-level system',
                                               'two level system', 'flux noise', 'charge noise'))
# Fixed phrases first: "weight decay" is a training choice even though "weight" alone is a property.
_INTERVENTION_PHRASES = tuple(term_key(p) for p in (
    'weight decay', 'learning rate', 'batch size', 'code distance', 'sample size', 'number of samples',
    'number of shots', 'mid-circuit measurement', 'error mitigation', 'noise injection', 'data augmentation',
    'training data', 'distillation speed', 'distillation rate'))
_OUTCOME_HEADS = frozenset(term_key(w) for w in '''rate rates fidelity fidelities threshold thresholds cost costs
    overhead overheads variance accuracy latency throughput generalization generalisation performance scaling
    probability efficiency yield time lifetime runtime error errors infidelity gap loss_value score revenue
    advantage trainability expressivity coherence quality utility'''.split())
_NOISE = frozenset(term_key(w) for w in '''noise decoherence radiation cosmic ray rays leakage crosstalk drift defect
    defects quasiparticle quasiparticles burst bursts fluctuation fluctuations dephasing relaxation tls
    impurity impurities heating'''.split())
_PROPERTY = frozenset(term_key(w) for w in '''weight locality degree dimension dimensionality connectivity geometry
    symmetry topology girth observable observables hamiltonian lattice graph spectrum entanglement structure
    rank sparsity curvature landscape'''.split())
_INTERVENTION = frozenset(term_key(w) for w in '''initialization initialisation pretraining measurement measurements
    reset distillation decoding decoder decoders mitigation pulse pulses pipelining encoding scheme protocol
    strategy training optimization optimizer optimiser ansatz ansatzes pooling conversion shuttling cultivation
    compilation scheduling calibration feedback quantization pruning augmentation curriculum sample samples shot
    shots budget regularization dropout injection filter filtering erasure suppression correction'''.split())


def classify(term, definition=None):
    """Return one of ``TYPES`` for ``term``; an explicit ``definition['type']`` wins."""
    if isinstance(definition, dict) and definition.get('type') in TYPES:
        return definition['type']
    key = term_key(term or '')
    if not key:
        return 'unknown'
    # A fixed phrase decides only when it ends the term: "error mitigation cost" is a cost, not a mitigation.
    if any(phrase and key.endswith(phrase) for phrase in _INTERVENTION_PHRASES):
        return 'intervention'
    if any(phrase and key.endswith(phrase) for phrase in _NOISE_PHRASES):
        return 'noise_channel'
    words = set(key.split())
    if term_head(key) in _OUTCOME_HEADS and not words & _NOISE - {term_key('error')}:
        return 'outcome_metric'
    if words & _NOISE:
        return 'noise_channel'
    if words & _PROPERTY:
        return 'observable_property'
    if words & _INTERVENTION:
        return 'intervention'
    if term_head(key) in _OUTCOME_HEADS:
        return 'outcome_metric'
    return 'unknown'


def route(pattern, types):
    """Choose a design from the pattern and the variable types; return (design, reason)."""
    a, b, c = types.get('a'), types.get('b'), types.get('c')
    fixed = {'observable_property'}
    stressor = {'noise_channel'}
    if pattern == 'convergent':
        if a == 'intervention' and b == 'intervention':
            return '2x2 factorial', 'Both factors are interventions that can be set to two levels each.'
        if {a, b} & {'intervention'} and {a, b} & (fixed | stressor):
            return 'stratified', ('One factor is a fixed property or a noise source: vary the intervention within '
                                  'strata of the other factor (or with noise injected at two levels) and compare the '
                                  'effects across strata.')
        if {a, b} <= fixed | stressor:
            return 'observational_regime_map', ('Neither factor can be set directly: compare instances across '
                                                'regimes of both factors; no manipulation.')
        return '2x2 factorial', 'Factor types are unknown; confirm both can be manipulated before running a factorial.'
    if pattern in {'chain', 'direct'}:
        if a in fixed:
            return 'stratified', ('The exposure is a fixed property: select instances at several levels of it '
                                  'rather than manipulating it.')
        if a in stressor:
            return 'mediation' if pattern == 'chain' else 'intervention', (
                'The exposure is a noise source: inject it at controlled levels or select naturally exposed runs.')
        return ('mediation' if pattern == 'chain' else 'intervention'), 'The exposure can be manipulated directly.'
    if c in fixed | stressor:
        return 'observational_regime_map', 'The common driver cannot be set directly; compare instances across its levels.'
    return 'common cause', 'The common driver can be manipulated directly.'
