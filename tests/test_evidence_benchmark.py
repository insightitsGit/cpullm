import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'tools/benchmarks/evidence_v2.py'
spec = importlib.util.spec_from_file_location('evidence_benchmark', path)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_frozen_case_ids_unique_and_baseline_does_not_read_gold():
    cases = benchmark.cases()
    assert len({c['id'] for c in cases}) == len(cases)
    assert len(cases) >= 40
    case = dict(query='Calculate 0.1 + 0.2.', status='deliberately-wrong', value='999')
    assert benchmark.baseline(case, [])['calculation']['display'] == '0.3'


def test_scorer_requires_proof_and_visible_value():
    case = dict(status='evidence_quote', value='1 mg', task_statuses=None)
    verdict = benchmark.score(case, dict(answer_status='evidence_quote', reply=dict(text='1 mg')), [])
    assert not verdict['ok']
    case = dict(status='derived_calculation', value='0.3', task_statuses=None)
    assert not benchmark.score(case, dict(answer_status='derived_calculation', calculation=dict(display='0.3000')), [])['ok']
