"""Usability fixes: loud snapshot failures, state directory, doctor, ask CLI, result helpers."""
import contextlib
from types import SimpleNamespace
from unittest.mock import Mock

import psycopg
import pytest

from cpu_llm import ask_cli, doctor, results
from cpu_llm.pipeline import Appliance, resolve_state_dir


def appliance(error):
    app = object.__new__(Appliance)
    app.tenant_id = 'test'
    app.small_talk = False
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision='allow'))
    app.index = SimpleNamespace(strict_source_rows=Mock(side_effect=error))
    return app


@pytest.mark.parametrize('route, kwargs', [('frontier', dict(frontier=True)),
                                           ('deepen', dict(deepen='A may reduce C through B.'))])
def test_an_unreachable_database_is_reported_as_unavailable(route, kwargs):
    reply = appliance(psycopg.OperationalError('down')).ask('barren plateaus', **kwargs)
    assert reply['answer_status'] == 'unavailable'
    assert reply['error']['kind'] == 'storage_unavailable' and 'cpu-llm-doctor' in reply['reply']['text']
    with pytest.raises(results.IncompleteResult):
        results.require_complete(reply)


def test_a_size_limit_stays_partial():
    reply = appliance(ValueError('snapshot limit')).ask('barren plateaus', frontier=True)
    assert reply['answer_status'] == 'partial' and reply['error']['kind'] == 'snapshot_limit'


def test_state_dir_order(tmp_path, monkeypatch):
    monkeypatch.delenv('CPU_LLM_STATE_DIR', raising=False)
    assert resolve_state_dir(tmp_path / 'a') == (tmp_path / 'a').resolve()
    monkeypatch.setenv('CPU_LLM_STATE_DIR', str(tmp_path / 'b'))
    assert resolve_state_dir() == (tmp_path / 'b').resolve()
    assert resolve_state_dir(tmp_path / 'c') == (tmp_path / 'c').resolve()
    monkeypatch.delenv('CPU_LLM_STATE_DIR')
    monkeypatch.chdir(tmp_path)
    assert resolve_state_dir() == (tmp_path / '.chorusgraph').resolve()


class _Conn:
    def __init__(self, version):
        self.version = version

    def execute(self, sql, *args):
        if 'pg_extension' in sql:
            return SimpleNamespace(fetchone=lambda: None if self.version is None else (self.version,))
        if 'pg_available_extensions' in sql:
            return SimpleNamespace(fetchone=lambda: ('0.8.0',))
        return SimpleNamespace(fetchall=lambda: [('ns_quantum',), ('ns_pipeline_test_1',)])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_doctor_reports_database_problems_with_fixes():
    def refuse(*a, **k):
        raise psycopg.OperationalError('refused')
    down = doctor.check_database('postgresql://x', connect=refuse)
    assert down[0][0] == 'FAIL' and 'VECTORPRISM_PG_DSN' in down[0][3]
    old = doctor.check_database('postgresql://x', connect=lambda *a, **k: _Conn('0.6.0'))
    assert ('FAIL', 'pgvector') == old[1][:2] and 'subvector' in old[1][3]
    good = doctor.check_database('postgresql://x', connect=lambda *a, **k: _Conn('0.8.7'))
    assert good[1][0] == 'OK' and good[2][2] == 'quantum'
    missing = doctor.check_database('postgresql://x', connect=lambda *a, **k: _Conn(None))
    assert missing[1][0] == 'FAIL' and 'CREATE EXTENSION' in missing[1][3]


def test_doctor_encoder_and_state_dir(tmp_path):
    (tmp_path / 'hub' / 'models--sentence-transformers--all-mpnet-base-v2').mkdir(parents=True)
    assert doctor.check_encoder({'HF_HOME': str(tmp_path), 'HF_HUB_OFFLINE': '1'})[0] == 'OK'
    assert doctor.check_encoder({'HF_HOME': str(tmp_path / 'none'), 'XDG_CACHE_HOME': str(tmp_path / 'none')})[0] == 'WARN'
    assert doctor.check_state_dir(tmp_path / 'state')[0] == 'OK'


def test_ask_cli_options_and_exit_codes():
    parse = lambda *argv: ask_cli.build_options(SimpleNamespace(**{**dict(
        strict=False, session_id=None, screen=False, frontier=False, max_seconds=None, shortlist=None,
        deepen=False, novelty=False, message='m'), **dict(argv)}))
    assert parse(('screen', True), ('shortlist', 8)) == {'frontier': {'screen': {'shortlist': 8}}}
    assert parse(('frontier', True)) == {'frontier': True}
    assert parse(('deepen', True), ('novelty', True)) == {'deepen': {'hypothesis': 'm', 'novelty': True}}
    assert ask_cli.exit_code({'answer_status': 'unavailable'}) == 2
    assert ask_cli.exit_code({'answer_status': 'hypotheses', 'frontier': {'incomplete': True}}) == 3
    assert ask_cli.exit_code({'answer_status': 'hypotheses', 'frontier': {'incomplete': False}}) == 0
    with pytest.raises(SystemExit):
        ask_cli.main(['--namespace', 'x', '--deepen', '--screen', 'm'])


def test_result_helpers():
    reply = {'answer_status': 'hypotheses', 'frontier': {'incomplete': False, 'hypotheses': [
        {'text': 'a', 'citations': [{'document_id': 'd1', 'quote': 'q'}], 'check': {'lead_status': 'testable'}},
        {'text': 'b', 'citations': [], 'check': {'lead_status': 'needs_review'}},
        {'text': 'c', 'citations': []}]}}
    assert results.require_complete(reply) is reply
    assert [h['text'] for h in results.shortlist(reply)] == ['a']
    assert results.lead_status({'deepen': {'lead_status': 'coverage_gap'}}) == 'coverage_gap'
    assert results.citations(results.hypotheses(reply)[0]) == [('d1', 'q')]
    with pytest.raises(results.IncompleteResult):
        results.require_complete({'answer_status': 'partial', 'frontier': {}})
    assert results.require_complete({'answer_status': 'partial', 'frontier': {}}, allow_partial=True)


def test_missing_main_guard_failure_names_the_fix(monkeypatch):
    from cpu_llm import thinker_pool
    monkeypatch.setattr(thinker_pool.WarmEvaluatorPool, '_spawn', lambda self, name: None)
    monkeypatch.setattr(thinker_pool.WarmEvaluatorPool, '_await_ready',
                        lambda self, names, timeout: {n: 'worker exited during startup (1)' for n in names})
    monkeypatch.setattr(thinker_pool.WarmEvaluatorPool, '_shutdown_locked', lambda self: None)
    with pytest.raises(RuntimeError, match='__name__ == "__main__"'):
        thinker_pool.WarmEvaluatorPool(SimpleNamespace(model_dump=lambda mode: {}))
