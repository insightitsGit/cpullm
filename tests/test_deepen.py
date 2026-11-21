from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cpu_llm.deepen import deepen_seed, parse_hypothesis, run_deepen, test_plan as plan_for
from cpu_llm.frontier import run_frontier
from cpu_llm.invention import NOTE
from cpu_llm.pipeline import Appliance
from cpu_llm.serve import _dispatch


@pytest.fixture(autouse=True)
def regex_parser(monkeypatch):
    monkeypatch.setenv('FRONTIER_PARSER', 'regex')


def rows_of(*texts):
    return [dict(document_id=f'doc{i}-p0001', chunk_text=text) for i, text in enumerate(texts, 1)]


CORPUS = rows_of(
    'Memory bandwidth limits inference throughput.',
    'Inference throughput drives serving revenue.',
    'HBM supply constrains memory bandwidth.',
    'Batch size limits inference throughput.',
    'We measured inference throughput on a synthetic benchmark across batch sizes.',
    'Faster memory bandwidth should raise inference throughput for large models.',
    'Quantization reduces serving revenue in some deployments.',
)
HBM = ['HBM supply', 'inference throughput']


def appliance(rows):
    app = object.__new__(Appliance)
    app.tenant_id = 'test'
    app.small_talk = False
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision='allow'))
    app.index = SimpleNamespace(strict_source_rows=Mock(return_value=(rows, 123)))
    return app


def test_prompt_trigger_and_text_forms():
    assert deepen_seed('Deepen: A may constrain C through B.') == 'A may constrain C through B'
    assert deepen_seed('What does deepen mean?') is None
    assert parse_hypothesis('memory bandwidth may increase serving revenue through inference throughput.')[:4] == (
        'chain', 'memory bandwidth', 'inference throughput', 'serving revenue')
    assert parse_hypothesis('energy and data may jointly constrain training, so relieving one may shift the '
                            'bottleneck to the other.')[:4] == ('convergent', 'energy', 'data', 'training')
    assert parse_hypothesis('Gains in grokking from symmetries may be offset by weight decay.')[:4] == (
        'convergent', 'symmetries', 'weight decay', 'grokking')
    assert parse_hypothesis('chip prices and power use may move together because both depend on demand.')[:4] == (
        'divergent', 'chip prices', 'power use', 'demand')
    with pytest.raises(ValueError):
        parse_hypothesis('Tell me about grokking.')


def test_a_frontier_hypothesis_deepens_link_by_link():
    frontier = run_frontier('inference', CORPUS)
    chain = next(h for h in frontier['hypotheses'] if h['pattern'] == 'chain' and h['anchors'] == HBM)
    receipt = run_deepen(chain, CORPUS)
    assert receipt['claim_status'] == 'UNVERIFIED_HYPOTHESIS' and receipt['promotion'] == 'blocked'
    assert receipt['pattern'] == 'chain' and len(receipt['links']) == 2
    assert [link['status'] for link in receipt['links']] == ['supported', 'supported']
    assert receipt['verdict'] == 'all_links_supported'
    assert any('should raise inference throughput' in p['quote'] for p in receipt['predictions'])
    assert any('synthetic benchmark' in s['quote'] for s in receipt['setups'])
    assert {c['term'] for c in receipt['confounders']} >= {'Batch size'}
    plan = receipt['test_plan']
    assert plan['design'] == 'mediation' and plan['mediator'] == 'memory bandwidth'
    assert 'Batch size' in plan['controls'] and plan['fails_if']


def test_counter_evidence_marks_a_link_contested():
    rows = CORPUS + rows_of('Memory bandwidth reduces inference throughput under thermal throttling.')
    hypothesis = next(h for h in run_frontier('inference', CORPUS)['hypotheses'] if h['anchors'] == HBM)
    receipt = run_deepen(hypothesis, rows)
    assert receipt['links'][1]['status'] == 'contested' and receipt['verdict'] == 'contested'
    assert receipt['links'][1]['counter_count'] >= 1
    # The text form carries no expected relation, so the same link counts only as support.
    text = run_deepen('HBM supply may constrain inference throughput through memory bandwidth.', rows)
    assert text['links'][1]['status'] == 'supported'


def test_missing_links_and_plans_for_pairs():
    receipt = run_deepen('photosynthesis and rainfall may jointly drive serving revenue.', CORPUS)
    assert receipt['links'][0]['status'] == 'missing' and receipt['verdict'] == 'unsupported'
    assert plan_for('convergent', 'A', 'B', 'C', [])['design'] == '2x2 factorial'
    assert plan_for('divergent', 'A', 'B', 'C', [])['design'] == 'common cause'


def test_ask_runs_deepen_and_never_writes():
    app = appliance(CORPUS)
    result = app.ask('Deepen: HBM supply may constrain inference throughput through memory bandwidth.')
    assert result['answer_status'] == 'deepened' and result['deepen']['links']
    assert result['reply']['text'].endswith(NOTE) and 'Test plan (mediation)' in result['reply']['text']
    assert result['routing']['post_stages'] == ['deepen_snapshot', 'deepen_links', 'deepen_evidence', 'deepen_plan']
    hypothesis = run_frontier('inference', CORPUS)['hypotheses'][0]
    assert appliance(CORPUS).ask('deepen this', deepen=hypothesis)['answer_status'] == 'deepened'


def test_strict_mode_bad_input_and_conflicts():
    app = appliance(CORPUS)
    assert app.ask('Deepen: A may constrain C through B.', strict_evidence=True)['answer_status'] == 'unsupported'
    app.index.strict_source_rows.assert_not_called()
    assert app.ask('Deepen: tell me more.')['answer_status'] == 'needs_clarification'
    with pytest.raises(ValueError, match='separately'):
        app.ask('Deepen: A may constrain C through B.', frontier=True)
    with pytest.raises(ValueError):
        app.ask('x', deepen=3)


def test_http_forwards_and_validates_deepen():
    entry = SimpleNamespace(ask=lambda secret, message, **kwargs: kwargs)
    assert _dispatch(entry, '/v1/ask', 't', dict(message='x', deepen='A may constrain C through B.'))[1] == dict(
        deepen='A may constrain C through B.')
    with pytest.raises(ValueError):
        _dispatch(entry, '/v1/ask', 't', dict(message='x', deepen=5))
