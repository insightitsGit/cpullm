"""Frontier/Deepen v2 (docs/frontier-deepen-v2-spec.md)."""
import pytest

from cpu_llm.deepen import run_deepen
from cpu_llm.frontier import artefact_reason, run_frontier


@pytest.fixture(autouse=True)
def regex_parser(monkeypatch):
    monkeypatch.setenv('FRONTIER_PARSER', 'regex')


def rows_of(*texts, prefix='doc'):
    return [dict(document_id=f'{prefix}{i}-p0001', chunk_text=text) for i, text in enumerate(texts, 1)]


# ------------------------------------------------------------------ 1. artefact filter

@pytest.mark.parametrize('term, reason', [
    ('D. Implications for Future Processors', 'header'),
    ('IV. Results', 'header'),
    ('3.2 Noise model', 'header'),
    ('Fig. 3', 'header'),
    ('S. Bravyi', 'author_name'),
    ('Tothebestofour knowledge', 'merged_words'),
    ('theavailabilityofnoisyintermediate scalequantum devices', 'merged_words'),
    ('less than 10 mEh', 'comparator_quantity'),
    ('majority of error', 'partitive'),
    ('Recent experiments', 'meta_noun'),
    ('issues', 'meta_noun'),
    ('definition', 'meta_noun'),
    ('line of work', 'meta_noun'),
])
def test_artefacts_are_detected(term, reason):
    assert artefact_reason(term) == reason


@pytest.mark.parametrize('term', [
    'surface code', 'weight decay', 'Cosmic rays', 'Integrated Information Theory', 'T1 decay', 'qLDPC codes',
    'photothermal effects', 'prior knowledge', 'transmission line', 'mid - circuit measurements',
    'low weight Pauli operators', 'Gottesman construction of fault tolerant schemes', 'existing hardware',
    'U(1) symmetry', 'MWPM decoder', 'thermodynamically stable phases',
])
def test_real_terms_are_kept(term):
    assert artefact_reason(term) is None


def test_frontier_rejects_candidates_built_on_artefacts():
    rows = rows_of('Recent experiments increase memory bandwidth.',
                   'Memory bandwidth drives inference throughput.',
                   'HBM supply constrains memory bandwidth.')
    receipt = run_frontier('memory bandwidth', rows)
    texts = ' '.join(h['text'] for h in receipt['hypotheses'])
    assert 'Recent experiments' not in texts
    assert receipt['candidates_rejected'].get('pre_thinker:artefact', 0) >= 1
    assert any('HBM supply' in h['text'] for h in receipt['hypotheses'])


def test_deepen_skips_artefact_controls():
    rows = rows_of('HBM supply constrains memory bandwidth.',
                   'Memory bandwidth drives inference throughput.',
                   'Recent advances increase inference throughput.',
                   'Batch size limits inference throughput.')
    receipt = run_deepen('HBM supply may increase inference throughput through memory bandwidth.', rows)
    terms = [c['term'] for c in receipt['confounders']]
    assert 'Batch size' in terms and not any(artefact_reason(t) for t in terms)


# ------------------------------------------------------------------ 2. composition gate

CHAIN = 'memory bandwidth may increase serving revenue through inference throughput.'


def test_bridged_contrary_evidence_is_a_bridge_mismatch_and_quarantined():
    rows = rows_of('Memory bandwidth increases inference throughput.',
                   'DRAM bandwidth reduces inference throughput.',
                   'Inference throughput increases serving revenue.')
    receipt = run_deepen(CHAIN, rows)
    assert receipt['links'][0]['status'] == 'bridge_mismatch'
    assert receipt['verdict'] == 'bridge_mismatch'
    assert receipt['lead_status'] == 'needs_semantic_resolution'
    plan = receipt['test_plan']
    assert plan['design'] == 'resolve_first' and plan['blocked_design'] == 'mediation'
    assert plan['manipulate'] == [] and plan['readiness'] == 'needs_input'
    assert any('DRAM bandwidth' in step for step in plan['steps'])


def test_exact_contrary_evidence_stays_contested_and_is_quarantined():
    rows = rows_of('Memory bandwidth increases inference throughput.',
                   'Memory bandwidth reduces inference throughput in other studies.',
                   'Inference throughput increases serving revenue.')
    receipt = run_deepen(CHAIN, rows)
    assert receipt['verdict'] == 'contested'
    assert receipt['lead_status'] == 'contested_tension'
    assert receipt['test_plan']['design'] == 'resolve_first'
    assert any('Weigh the contrary evidence' in step for step in receipt['test_plan']['steps'])


def test_clean_chain_is_testable_with_its_experiment():
    rows = rows_of('Memory bandwidth increases inference throughput.',
                   'Inference throughput increases serving revenue.')
    receipt = run_deepen(CHAIN, rows)
    assert receipt['verdict'] == 'all_links_supported'
    assert receipt['lead_status'] == 'testable'
    assert receipt['test_plan']['design'] == 'mediation'


def test_modifier_bridge_is_reviewed_but_not_quarantined():
    rows = rows_of('Faster memory bandwidth increases inference throughput.',
                   'Inference throughput increases serving revenue.')
    receipt = run_deepen(CHAIN, rows)
    assert {b['kind'] for b in receipt['composition']['bridges']} == {'modifier'}
    assert receipt['lead_status'] == 'needs_review'
    assert receipt['test_plan']['design'] == 'mediation'


def test_frontier_checks_carry_the_lead_status():
    rows = rows_of('HBM supply constrains memory bandwidth.',
                   'Memory bandwidth drives inference throughput.',
                   'Inference throughput drives serving revenue.')
    receipt = run_frontier('memory bandwidth', rows, deepen_top=3)
    checked = [h['check'] for h in receipt['hypotheses'] if h.get('check')]
    assert checked and all(c['lead_status'] for c in checked)


# ------------------------------------------------------------------ 3-4. coverage gaps and suggested procedures

def test_thin_coverage_is_reported_as_a_coverage_gap():
    rows = rows_of('Two-level system defects are common in superconducting qubits.',
                   'Dielectric loss limits qubit coherence.')
    receipt = run_deepen('Two-level system defects may reduce qubit coherence through dielectric loss.', rows)
    assert receipt['verdict'] in {'partly_supported', 'unsupported'}
    gap = receipt['links'][0]['coverage']
    assert gap['gap'] and gap['short_source_share'] == 1.0
    assert receipt['lead_status'] == 'coverage_gap'
    assert receipt['research_actions'][0]['id'] == 'add_sources'


def test_setups_become_cited_suggestions_without_changing_readiness():
    rows = rows_of('Memory bandwidth increases inference throughput.',
                   'Inference throughput increases serving revenue.',
                   'We measured inference throughput on a synthetic benchmark across batch sizes.')
    receipt = run_deepen(CHAIN, rows)
    suggestions = receipt['test_plan']['suggested_procedures']
    assert suggestions['inference throughput'][0]['qualification'] == 'suggested_not_validated'
    assert receipt['test_plan']['readiness'] == 'needs_input'


# ------------------------------------------------------------------ 5. variable typing and design routing

from cpu_llm.variable_types import classify  # noqa: E402


@pytest.mark.parametrize('term, kind', [
    ('low weight Pauli operators', 'observable_property'), ('samples', 'intervention'),
    ('chemical initialization', 'intervention'), ('mid - circuit measurements', 'intervention'),
    ('weight decay', 'intervention'), ('Cosmic rays', 'noise_channel'), ('dielectric loss', 'noise_channel'),
    ('leakage', 'noise_channel'), ('logical error rates', 'outcome_metric'), ('qubit coherence', 'outcome_metric'),
    ('error mitigation cost', 'outcome_metric'), ('Hamiltonian locality', 'observable_property'),
])
def test_variables_are_typed(term, kind):
    assert classify(term) == kind


def test_a_fixed_property_routes_to_a_stratified_design():
    rows = rows_of('Low weight Pauli operators constrain error mitigation.',
                   'Samples constrain error mitigation.')
    receipt = run_deepen('low weight Pauli operators and samples may jointly constrain error mitigation.', rows)
    plan = receipt['test_plan']
    assert plan['design'] == 'stratified'
    assert plan['manipulate'] == ['samples'] and plan['strata'] == ['low weight Pauli operators']
    assert plan['variable_types']['a'] == 'observable_property' and plan['design_reason']


def test_two_interventions_keep_the_factorial():
    rows = rows_of('Chemical initialization increases trainability.',
                   'Mid-circuit measurements increase trainability.')
    receipt = run_deepen('chemical initialization and mid-circuit measurements may jointly drive trainability.', rows)
    assert receipt['test_plan']['design'] == '2x2 factorial'


def test_a_user_type_overrides_the_lexicon():
    rows = rows_of('Low weight Pauli operators constrain error mitigation.',
                   'Samples constrain error mitigation.')
    receipt = run_deepen({'hypothesis': 'low weight Pauli operators and samples may jointly constrain error mitigation.',
                          'definitions': {'low weight Pauli operators': {'type': 'intervention'}}}, rows)
    assert receipt['test_plan']['design'] == '2x2 factorial'


# ------------------------------------------------------------------ 6-8, 11. screen, drift, reserve, axiom sources

from cpu_llm.frontier import FrontierLimits, validate_frontier_option  # noqa: E402

_UP = ['wafer', 'lithography', 'packaging', 'substrate', 'cooling', 'transformer', 'turbine', 'permit']
_DOWN = ['training', 'inference', 'serving', 'research', 'deployment', 'evaluation']


def hub_corpus():
    texts = [f'{name.title()} supply limits accelerator capacity.' for name in _UP]
    texts += [f'Accelerator capacity drives {name} throughput.' for name in _DOWN]
    texts += ['Accelerator capacity drives overall performance.'] * 1
    texts += [f'Performance matters for {name} teams.' for name in _UP]
    return rows_of(*texts)


def test_screen_drops_generic_entries_and_reranks():
    rows = hub_corpus()
    plain = run_frontier('wafer supply', rows)
    screened = run_frontier('wafer supply', rows, screen={'shortlist': 5}, deepen_top=0)
    info = screened['screen']
    assert info['applied'] and info['dropped_generic'] >= 1
    assert set(info['dropped_ids']) & {h['id'] for h in plain['hypotheses']}
    keys = [0.6 * h['scores']['deductive_relevance'] + 0.4 * h['scores']['novelty'] for h in screened['hypotheses']]
    assert keys == sorted(keys, reverse=True)
    checked = [h['check'] for h in screened['hypotheses'] if h.get('check')]
    assert len(checked) == 5 and all(c['novelty_kb'] != 'not_requested' for c in checked)


def test_screen_option_is_validated():
    assert validate_frontier_option({'screen': True})['screen'] == {'shortlist': 15}
    assert validate_frontier_option({'screen': {'shortlist': 8}})['screen'] == {'shortlist': 8}
    with pytest.raises(ValueError):
        validate_frontier_option({'screen': {'shortlist': 99}})
    assert validate_frontier_option(True).get('screen') is None


def test_topic_match_reports_drift():
    rows = hub_corpus()
    receipt = run_frontier('accelerator capacity', rows)
    assert receipt['topic_match']['on_topic_share'] is not None
    drifted = run_frontier('wafer throughput', rows)
    match = drifted['topic_match']
    assert set(match) >= {'focus_terms', 'matched_chunks', 'on_topic_share', 'drift_warning'}


def test_generation_stops_early_to_leave_time_for_checks():
    def run(deepen_top):
        ticks = iter(range(100_000))
        return run_frontier('accelerator capacity', hub_corpus(), deepen_top=deepen_top,
                            limits=FrontierLimits(max_seconds=40), clock=lambda: next(ticks) * 0.1)
    reserved = run(2)
    assert reserved['stop_reason'] == 'generation_time_reserved' and not reserved['candidate_search_complete']
    assert run(0)['candidate_search_complete']     # no checks requested: no reserve


def test_axiom_only_candidates_are_dropped():
    rows = rows_of('HBM supply constrains memory bandwidth.', 'Memory bandwidth drives inference throughput.',
                   prefix='review') + rows_of('Inference throughput drives serving revenue.', prefix='paper')
    with_axioms = run_frontier('memory bandwidth', rows, axiom_sources=('review',))
    assert with_axioms['candidates_rejected'].get('pre_thinker:axiom_only', 0) >= 1
    for h in with_axioms['hypotheses']:
        assert any(not c['document_id'].startswith('review') for c in h['citations'])
