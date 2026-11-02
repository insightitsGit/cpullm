from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cpu_llm.pipeline import Appliance
from cpu_llm.strict_evidence import requested
from cpu_llm.serve import _dispatch
from cpu_llm.access import CallerContext


def appliance(*facts, strict=False):
    app = object.__new__(Appliance)
    app.tenant_id = 'cpu-llm'
    app.strict_evidence = strict
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision='allow'))
    app.index = SimpleNamespace(strict_source_rows=Mock(return_value=(
        [dict(document_id=f'doc-{i}', chunk_text=text) for i, text in enumerate(facts)], 123)))
    return app


def test_quotes_exact_decimal_and_never_dispatches_generators(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('normal pipeline invoked')
    monkeypatch.setattr('cpu_llm.request_planner.dispatch_request', forbidden)
    app = appliance('The strength of DemoMed is 0.75 mg.')
    result = app.ask('What is the strength of DemoMed?', strict_evidence=True,
        realization='evidence_neural', style='friendly', imagine=True, math=True)
    assert result['answer_status'] == 'evidence_quote'
    proof = result['answer_evidence'][0]
    assert proof['document_id'] == 'doc-0'
    assert proof['quote'] == 'The strength of DemoMed is 0.75 mg.'
    assert len(proof['chunk_sha256']) == 64
    assert proof['end'] - proof['start'] == len(proof['quote'])
    assert result['answer'] is None
    assert result['audit_passed'] is False
    assert result['evidence_policy']['learned_generation'] is False


def test_decimal_conflicts_are_not_rounded_away():
    result = appliance('The strength of DemoMed is 0.75 mg.',
                       'The strength of DemoMed is 0.25 mg.').ask(
                           'What is the strength of DemoMed?', strict_evidence=True)
    assert result['answer_status'] == 'conflicting'
    assert len(result['answer_evidence']) == 2
    assert '0.75' not in result['reply']['text']


@pytest.mark.parametrize('query', ['Can I take DemoMed?', 'What is the dose of it?',
    'What is the strength of DemoMed? And what is its dose?',
    'What is the strength of DemoMed if I am pregnant?'])
def test_unsupported_does_not_retrieve_or_infer(query):
    app = appliance()
    assert app.ask(query, strict_evidence=True)['answer_status'] == 'unsupported'
    app.index.strict_source_rows.assert_not_called()


def test_missing_multisentence_overflow_and_scope():
    app = appliance('The strength of DemoMed is 1 mg. Another condition applies.')
    assert app.ask('What is the strength of DemoMed?', strict_evidence=True)['answer_status'] == 'insufficient_evidence'
    app.index.strict_source_rows.side_effect = ValueError('limit')
    assert app.ask('What is the strength of DemoMed?', strict_evidence=True)['evidence_policy']['scan_complete'] is False
    app = appliance()
    caller = CallerContext.make('cpu-llm', 'alice', ['public-p'])
    app.ask('What is the strength of DemoMed?', strict_evidence=True, caller=caller, as_of=99)
    app.index.strict_source_rows.assert_called_once_with(caller.allowed_sources, as_of=99)


def test_floor_prompt_activation_and_raw_guard():
    app = appliance(strict=True)
    assert app.ask('What is the strength of DemoMed?', strict_evidence=False)['evidence_policy']['enabled']
    app = appliance()
    assert app.ask('[strict-evidence]\nWhat is the strength of DemoMed?')['evidence_policy']['enabled']
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision='block'))
    assert app.ask('[strict-evidence]\nWhat is the strength of DemoMed?')['answer_status'] == 'blocked'


@pytest.mark.parametrize('message', ['"[strict-evidence]"', '```\n[strict-evidence]\n```',
    'Do not use [strict-evidence]', 'A source says [strict-evidence]'])
def test_data_does_not_enable_mode(message):
    assert requested(message, False)[0] is False


def test_http_enable_wins_and_invalid_flags_fail():
    entry = SimpleNamespace(ask=Mock(return_value={}))
    _dispatch(entry, '/v1/ask', 'secret', dict(message='question', strict_evidence=False), evidence_mode='strict')
    assert entry.ask.call_args.kwargs['strict_evidence'] is True
    _dispatch(entry, '/v1/ask', 'secret', dict(message='question', strict_evidence=False), evidence_mode='standard', require_strict=True)
    assert entry.ask.call_args.kwargs['strict_evidence'] is True
    with pytest.raises(ValueError):
        _dispatch(entry, '/v1/ask', 'secret', dict(message='question', strict_evidence='false'))
    with pytest.raises(ValueError):
        _dispatch(entry, '/v1/ask', 'secret', dict(message='question'), evidence_mode='typo')
    with pytest.raises(ValueError):
        requested('question', 'true')
