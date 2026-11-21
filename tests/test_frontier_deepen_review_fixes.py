"""Semantic, validation, guard and shared-budget regressions for ec71024 review."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cpu_llm.cycle_exploration import Budget
from cpu_llm.deepen import run_deepen, read_hypothesis
from cpu_llm.frontier import FrontierLimits, build_graph, run_frontier
from cpu_llm.pipeline import Appliance


@pytest.fixture(autouse=True)
def regex_parser(monkeypatch):
    monkeypatch.setenv('FRONTIER_PARSER', 'regex')


def rows(*texts):
    return [dict(document_id=f'paper{i}-p0001', chunk_text=text) for i, text in enumerate(texts)]


def appliance(source):
    app = object.__new__(Appliance)
    app.tenant_id, app.small_talk = 'review', False
    app.guard = SimpleNamespace(check=Mock(return_value=SimpleNamespace(decision='allow')))
    app.index = SimpleNamespace(strict_source_rows=Mock(return_value=(source, 123)))
    return app


@pytest.mark.parametrize('first,second,verb,status', [
    ('reduces', 'increases', 'increase', 'contradicted'),
    ('increases', 'reduces', 'increase', 'contradicted'),
    ('reduces', 'reduces', 'increase', 'consistent'),
    ('increases', 'increases', 'increase', 'consistent'),
    ('reduces', 'increases', 'reduce', 'consistent'),
])
def test_text_direction_is_checked_by_composing_the_entire_path(first, second, verb, status):
    source = rows(f'Memory bandwidth {first} inference throughput.',
                  f'Inference throughput {second} serving revenue.')
    result = run_deepen(f'Memory bandwidth may {verb} serving revenue through inference throughput.', source)
    assert result['direction_check']['status'] == status
    assert result['verdict'] == ('contested' if status == 'contradicted' else 'all_links_supported')
    assert result['claim_status'] == 'UNVERIFIED_HYPOTHESIS' and result['promotion'] == 'blocked'


def test_convergent_text_does_not_call_opposing_effects_jointly_positive():
    source = rows('Memory bandwidth increases serving revenue.', 'Power costs reduce serving revenue.')
    result = run_deepen('Memory bandwidth and power costs may jointly drive serving revenue.', source)
    assert result['verdict'] == 'contested'
    assert result['links'][1]['counter_count'] == 1


def test_negation_retains_predicate_identity_and_source_receipt():
    source = rows('Memory bandwidth increases inference throughput.',
                  'Inference throughput increases serving revenue.',
                  'Memory bandwidth does not reduce inference throughput.')
    result = run_deepen('Memory bandwidth may increase serving revenue through inference throughput.', source)
    assert result['links'][0]['status'] == 'supported'
    assert result['links'][0]['counter_count'] == 0
    assert result['links'][0]['negations'][0]['relation'] == 'decreases'
    retained = run_frontier('memory bandwidth serving revenue', source)
    assert any(h['pattern'] == 'chain' for h in retained['hypotheses'])
    source[-1]['chunk_text'] = 'Memory bandwidth does not increase inference throughput.'
    result = run_deepen('Memory bandwidth may increase serving revenue through inference throughput.', source)
    counter = result['links'][0]['counter'][0]
    assert result['links'][0]['status'] == 'contested'
    assert counter['document_id'] == 'paper2-p0001' and counter['relation'] == 'increases'
    text = source[-1]['chunk_text']
    assert counter['quote'] == text[counter['start']:counter['end']]
    assert len(counter['chunk_sha256']) == 64


def test_three_edge_hypotheses_survive_dict_text_leading_checks_and_followups():
    source = rows('Memory bandwidth increases inference throughput.',
                  'Inference throughput increases serving revenue.',
                  'Serving revenue increases research funding.')
    frontier = run_frontier('memory bandwidth research funding', source,
                            limits=FrontierLimits(max_path_edges=3), deepen_top=10)
    h = next(h for h in frontier['hypotheses'] if len(h['via']) == 2)
    assert len(h['check']['links']) == 3
    for value in (h, h['text']):
        result = run_deepen(value, source)
        assert result['path_nodes'] == ['Memory bandwidth', 'inference throughput', 'serving revenue', 'research funding']
        assert len(result['links']) == 3
        assert result['verdict'] == 'all_links_supported'
        assert result['test_plan']['mediators'] == ['inference throughput', 'serving revenue']
    app = appliance(source)
    response = app.ask('Frontier: memory bandwidth research funding.', session_id='three',
                       frontier={'limits': {'max_path_edges': 3}})
    index = next(i for i, item in enumerate(response['frontier']['hypotheses'], 1) if len(item['via']) == 2)
    result = app.ask(f'Deepen idea {index}.', session_id='three')
    assert len(result['deepen']['links']) == 3


def test_citation_order_and_bridge_annotations_do_not_drop_links():
    source = rows('Memory bandwidth increases inference throughput.',
                  'Inference throughput reduces serving revenue.')
    h = next(h for h in run_frontier('memory bandwidth serving revenue', source)['hypotheses']
             if h['pattern'] == 'chain')
    first = run_deepen(h, source)
    h['citations'].reverse()
    second = run_deepen(h, source)
    assert first['links'] == second['links']
    assert first['direction_check'] == second['direction_check']
    spec = read_hypothesis('Memory bandwidth may increase research funding through inference throughput '
                           '(read as inference throughput) and then serving revenue (read as serving revenue).')
    assert spec.links() == [('Memory bandwidth', 'inference throughput'),
                            ('inference throughput', 'serving revenue'), ('serving revenue', 'research funding')]


@pytest.mark.parametrize('overrides', [
    {'via': [1]}, {'via': 'memory bandwidth'}, {'via': [{}]}, {'anchors': 'not-a-list'},
    {'pattern': []}, {'relation': []}, {'citations': [None]}, {'citations': [{}]},
    {'text': 3}, {'anchors': ['HBM supply']},
])
def test_malformed_hypothesis_objects_clarify_without_loading_sources(overrides):
    app = appliance([])
    hypothesis = dict(pattern='chain', anchors=['HBM supply', 'serving revenue'], via=['memory bandwidth'])
    hypothesis.update(overrides)
    result = app.ask('Examine this.', deepen=hypothesis)
    assert result['answer_status'] == 'needs_clarification'
    app.index.strict_source_rows.assert_not_called()


@pytest.mark.parametrize('session', [False, True])
def test_numbered_followup_guard_and_strict_policy_precede_recall(session):
    source = rows('Memory bandwidth increases inference throughput.', 'Inference throughput increases serving revenue.')
    app = appliance(source)
    if session:
        app.ask('Frontier: memory bandwidth serving revenue.', session_id='s')
    app.guard.check.return_value = SimpleNamespace(decision='deny')
    app.index.strict_source_rows.reset_mock()
    assert app.ask('Deepen idea 1.', session_id='s')['answer_status'] == 'blocked'
    app.index.strict_source_rows.assert_not_called()
    app.guard.check.return_value = SimpleNamespace(decision='allow')
    assert app.ask('Deepen idea 1.', session_id='s', strict_evidence=True)['answer_status'] == 'unsupported'
    app.strict_evidence = True
    assert app.ask('Deepen idea 99.', session_id='s')['answer_status'] == 'unsupported'
    app.index.strict_source_rows.assert_not_called()


def test_leading_deadline_is_recorded_without_losing_generated_candidates(monkeypatch):
    import cpu_llm.frontier as module
    source = rows('Memory bandwidth increases inference throughput.', 'Inference throughput increases serving revenue.')
    tick = [0.]
    original = module._check_leading
    def expire(*args):
        tick[0] = 100.
        return original(*args)
    monkeypatch.setattr(module, '_check_leading', expire)
    result = run_frontier('memory bandwidth', source, clock=lambda: tick[0], deepen_top=5)
    assert result['hypotheses'] and result['candidate_search_complete']
    assert result['incomplete'] and result['stop_reason'] == 'leading_check:deadline'
    assert result['leading_check']['checked'] == 0 and not result['leading_check']['complete']
    assert 'Candidate enumeration completed' in module.format_reply(result)
    app = appliance(source)
    monkeypatch.setattr(module, 'run_frontier', lambda *args, **kwargs: deepcopy(result))
    response = app.ask('Frontier: memory bandwidth')
    assert response['judgment']['complete'] is False


def test_child_scan_uses_the_parent_deadline_and_reports_partial_links(monkeypatch):
    import cpu_llm.deepen as module
    source = rows('Memory bandwidth increases inference throughput.', 'Inference throughput increases serving revenue.')
    graph = build_graph(source, Budget(FrontierLimits()))
    tick = [0.]
    budget = Budget(FrontierLimits(max_seconds=1), clock=lambda: tick[0])
    budget.counters = dict(rounds=4, candidates=12, edges=2, bytes=100)
    original = module._link_evidence
    def expire(*args):
        result = original(*args)
        tick[0] = 2.
        return result
    monkeypatch.setattr(module, '_link_evidence', expire)
    receipt = run_deepen('Memory bandwidth may increase serving revenue through inference throughput.',
                         source, graph=graph, budget=budget)
    assert receipt['verdict'] == 'incomplete' and receipt['stop_reason'] == 'deadline'
    assert len(receipt['links']) == 1
    assert receipt['budget_used']['candidates'] == 12 and receipt['budget_used']['seconds'] == 2.


def test_encoder_overrun_is_detected_and_does_not_validate_an_unchecked_bridge():
    import numpy as np
    import cpu_llm.frontier as module
    source = rows('HBM supply constrains memory bandwidth.', 'Wider memory bandwidth increases throughput.')
    graph = build_graph(source, Budget(FrontierLimits()))
    tick = [0.]
    budget = Budget(FrontierLimits(max_seconds=1), clock=lambda: tick[0])
    budget.counters = dict(rounds=0, candidates=0, edges=0, bytes=0)
    def encode(terms):
        tick[0] = 2.
        return np.ones((len(terms), 2))
    with pytest.raises(module.StopSearch, match='deadline'):
        module._similarity(encode, list(graph.edges.values()), budget)


def test_direction_and_all_sources_are_not_promoted_to_truth():
    source = rows('Memory bandwidth increases inference throughput.', 'Inference throughput increases serving revenue.')
    app = appliance(source)
    result = app.ask('Deepen: Memory bandwidth may increase serving revenue through inference throughput.')
    assert result['deepen']['direction_check']['status'] == 'consistent'
    assert result['audit_passed'] is False and result['answer'] is None
    assert result['deepen']['promotion'] == 'blocked' and result['deepen']['index_write'] is False
