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
