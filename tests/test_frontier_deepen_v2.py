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
