"""Research quality annotations preserve breadth, evidence and authorization."""
from types import SimpleNamespace
from unittest.mock import Mock
import hashlib

import pytest

from cpu_llm.cycle_exploration import Budget
from cpu_llm.deepen import run_deepen
from cpu_llm.frontier import FrontierLimits, run_frontier
from cpu_llm.pipeline import Appliance
from cpu_llm.serve import _dispatch


@pytest.fixture(autouse=True)
def parser(monkeypatch):
    monkeypatch.setenv('FRONTIER_PARSER', 'regex')


def rows(*texts):
    return [dict(document_id=f'paper-{hashlib.sha256(text.encode()).hexdigest()[:12]}-p0001', chunk_text=text) for text in texts]


SOURCE = rows('Memory bandwidth increases inference throughput.',
              'Inference throughput increases serving revenue.',
              'Batch size increases inference throughput.')
HYPOTHESIS = 'Memory bandwidth may increase serving revenue through inference throughput.'


def app_for(source=SOURCE):
    app = object.__new__(Appliance)
    app.tenant_id, app.small_talk = 'test', False
    app.guard = SimpleNamespace(check=Mock(return_value=SimpleNamespace(decision='allow')))
    app.index = SimpleNamespace(strict_source_rows=Mock(return_value=(source, 123)))
    return app


def test_component_support_does_not_certify_composition_or_interaction():
    receipt = run_deepen('Memory bandwidth and batch size may jointly drive inference throughput.', SOURCE)
    assert receipt['verdict'] == 'all_links_supported'
    assert receipt['composition']['status'] == 'conditional'
    assert receipt['composition']['scientific_validity'] == 'not_established'
    assert receipt['composition']['interaction']['status'] == 'untested'
    assert 'does not refute individual effects' in receipt['test_plan']['fails_if']
    assert receipt['test_plan']['interaction_test']['contrast'] == 'Y11 - Y10 - Y01 + Y00'


def test_shared_head_collision_is_visible_without_pruning_candidate():
    source = rows('Chunked prefill increases memory access.',
                  'Compute access increases institutional divergence.')
    receipt = run_deepen('Chunked prefill may increase institutional divergence through memory access.', source)
    assert receipt['links'][1]['status'] == 'supported'  # legacy link verdict retained
    assert receipt['composition']['status'] == 'requires_review'
    bridge = receipt['composition']['bridges'][0]
    assert bridge['source_term'] == 'Compute access' and bridge['requested'] == 'memory access'
    assert bridge['citation']['quote'] == source[1]['chunk_text']


def test_explicit_settings_and_qualified_statements_survive():
    source = rows('Memory bandwidth increases inference throughput under light load.\nWorkload: short prompts',
                  'Inference throughput increases serving revenue.\nWorkload: long prompts')
    receipt = run_deepen(HYPOTHESIS, source)
    composition = receipt['composition']
    assert composition['status'] == 'requires_review'
    assert composition['scope_differences'] == [dict(field='workload', values=['long prompts', 'short prompts'],
        reason='Different source settings; establish transferability before combining effects.')]
    assert 'under light load' in composition['qualifications'][0]['citation']['quote']
    proof = composition['qualifications'][0]['citation']
    original = source[0]['chunk_text']
    assert original[proof['start']:proof['end']] == proof['quote']
    assert len(proof['chunk_sha256']) == 64


def test_quantifier_is_not_silently_dropped_from_review():
    source = rows('Memory bandwidth increases inference throughput for some workloads.',
                  'Inference throughput increases serving revenue.')
    result = run_deepen(HYPOTHESIS, source)
    assert any('some workloads' in q['citation']['quote'] for q in result['composition']['qualifications'])


def test_candidate_controls_need_role_review():
    source = SOURCE + rows('Batch size increases memory bandwidth.',
                           'Memory bandwidth increases cooling demand.',
                           'Cooling demand increases serving revenue.')
    receipt = run_deepen(HYPOTHESIS, source)
    controls = {c['term']: c for c in receipt['confounders']}
    assert controls['Cooling demand']['role'] == 'possible_downstream_variable'
    assert controls['Cooling demand']['downstream_evidence']
    convergent = run_deepen('Memory bandwidth and batch size may jointly drive inference throughput.',
        SOURCE + rows('Ambient temperature increases memory bandwidth.',
                      'Ambient temperature increases inference throughput.',
                      'Power capacity increases inference throughput.'))
    controls = {c['term']: c for c in convergent['confounders']}
    assert controls['Ambient temperature']['role'] == 'candidate_shared_cause'
    assert controls['Power capacity']['role'] == 'outcome_predictor'
    assert 'before adjustment' in convergent['test_plan']['steps'][1]


def test_missing_measurements_are_requirements_not_invented_numbers():
    result = run_deepen(HYPOTHESIS, SOURCE)
    plan = result['test_plan']
    assert plan['readiness'] == 'needs_input' and not plan['executed']
    assert any(m.get('term') == 'serving revenue' and m['requirement'] == 'measurement procedure'
               for m in plan['missing_requirements'])
    assert plan['protocol'] == {}
    assert all(v['definition'] == {} for v in plan['variables'])


def test_measurement_hints_are_cited_without_becoming_validated_definitions():
    source = SOURCE + rows('We measured inference throughput in tokens per second on a fixed workload.')
    receipt = run_deepen(HYPOTHESIS, source)
    variable = next(v for v in receipt['test_plan']['variables'] if v['term'] == 'inference throughput')
    hint = next(c for c in variable['source_hints'] if 'tokens per second' in c['quote'])
    assert hint['qualification'] == 'measurement_hint_not_validated_definition'
    assert variable['definition'] == {} and 'measurement procedure' in variable['missing']
    assert hint['quote'] == source[-1]['chunk_text'][hint['start']:hint['end']]


def configured_request():
    return dict(hypothesis=HYPOTHESIS, definitions={
        'memory bandwidth': dict(levels=['low', 'high'], feasible=True),
        'inference throughput': dict(measurement='completed output tokens / elapsed time', unit='tokens/s'),
        'serving revenue': dict(measurement='sum of settled serving invoices', unit='USD/day'),
    }, protocol=dict(replicates=10, acceptance_criterion='pre-registered effect interval'))


def test_user_definitions_make_plan_reviewable_not_scientifically_valid():
    result = run_deepen(configured_request(), SOURCE)
    plan = result['test_plan']
    assert plan['readiness'] == 'specified_for_review'
    assert plan['missing_requirements'] == [] and plan['protocol']['replicates'] == 10
    assert all(v['provenance'] == 'user_supplied_assumption' for v in plan['variables'])
    assert plan['statistical_validity'] == 'not_established'
    assert result['claim_status'] == 'UNVERIFIED_HYPOTHESIS' and result['index_write'] is False


@pytest.mark.parametrize('options', [
    {'unexpected': True}, {'definitions': []}, {'novelty': 'yes'}, {'external_review': True},
    {'definitions': {'A': {'levels': ['same', 'same']}}}, {'definitions': {'A': {'feasible': 1}}},
    {'protocol': {'replicates': True}}, {'protocol': {'replicates': 0}},
    {'definitions': {'A': {'unit': 3}}}, {'definitions': {'A': {'guess': 'x'}}},
    {'definitions': {'Typo not in hypothesis': {'unit': 'USD'}}},
])
def test_invalid_envelopes_clarify_before_reading_sources(options):
    app = app_for()
    result = app.ask('Review.', deepen=dict(hypothesis=HYPOTHESIS, **options))
    assert result['answer_status'] == 'needs_clarification'
    app.index.strict_source_rows.assert_not_called()


def test_novelty_is_separate_opt_in_and_cannot_certify_absence():
    reviewer = Mock()
    receipt = run_deepen(HYPOTHESIS, SOURCE, literature_reviewer=reviewer)
    assert receipt['novelty_review']['kb_status'] == 'not_requested'
    reviewer.assert_not_called()
    source = SOURCE + rows('We studied memory bandwidth, inference throughput and serving revenue in one benchmark.')
    receipt = run_deepen(dict(hypothesis=HYPOTHESIS, novelty=True), source, literature_reviewer=reviewer)
    review = receipt['novelty_review']
    assert review['kb_status'] == 'potential_overlap'
    assert review['matches'][0]['qualification'] == 'potential_overlap_not_equivalence'
    assert review['scientific_novelty'] == 'not_established'
    reviewer.assert_not_called()
    review = run_deepen(dict(hypothesis=HYPOTHESIS, novelty=True), SOURCE)['novelty_review']
    assert review['kb_status'] == 'no_overlap_found_in_snapshot'
    assert review['scientific_novelty'] == 'not_established'


def test_operator_reviewer_requires_request_opt_in_and_retains_external_provenance():
    reviewer = Mock(return_value=[dict(title='Prior work', url='https://example.org/paper', excerpt='A relevant study.')])
    app = app_for()
    app.literature_reviewer = reviewer
    receipt = app.ask('Review.', deepen=dict(hypothesis=HYPOTHESIS, novelty=True, external_review=True))['deepen']
    assert receipt['novelty_review']['external_status'] == 'reviewed_candidates'
    assert receipt['novelty_review']['external_matches'][0]['qualification'] == 'external_overlap_candidate_not_kb_evidence'
    assert reviewer.call_args.kwargs['max_results'] == 6
    assert reviewer.call_args.kwargs['timeout_seconds'] > 0
    assert not any('https://' in p['quote'] for p in receipt['links'][0]['support'])


@pytest.mark.parametrize('provider', [None, lambda **_: [dict(title='x', url='file:///secret', excerpt='x')],
                                     lambda **_: (_ for _ in ()).throw(Exception('sensitive error'))])
def test_unconfigured_or_failed_reviewer_does_not_invent_review(provider):
    result = run_deepen(dict(hypothesis=HYPOTHESIS, novelty=True, external_review=True), SOURCE,
                        literature_reviewer=provider)
    assert result['novelty_review']['external_status'] in {'not_configured', 'unavailable_or_invalid'}
    assert result['novelty_review']['external_matches'] == []


def test_reviewer_deadline_is_part_of_shared_budget():
    tick = [0]
    budget = Budget(FrontierLimits(max_seconds=10), clock=lambda: tick[0])
    def reviewer(**kwargs):
        tick[0] = 11
        return []
    result = run_deepen(dict(hypothesis=HYPOTHESIS, novelty=True, external_review=True), SOURCE,
                        literature_reviewer=reviewer, budget=budget)
    assert result['incomplete'] and result['stop_reason'] == 'deadline'
    assert result['verdict'] == 'incomplete'


def test_followups_focus_different_requirements_and_eventually_request_input():
    app = app_for()
    first = app.ask('Review.', deepen=HYPOTHESIS, session_id='one')
    actions = first['deepen']['research_actions']
    focuses = []
    for _ in actions:
        response = app.ask('Go deeper.', session_id='one')
        progress = response['deepen']['progress']
        assert progress['status'] == 'focused_requirement'
        assert not progress['new_source_evidence'] and not progress['requirements_resolved']
        focuses.append(progress['focus']['id'])
        assert 'No new source content' in response['reply']['text']
        assert 'Test plan (' not in response['reply']['text']  # no repeated full plan
    assert len(set(focuses)) == len(focuses)
    final = app.ask('Explain more.', session_id='one')
    assert final['deepen']['progress']['status'] == 'needs_more_data'
    assert 'Supply definitions' in final['reply']['text']


def test_followups_detect_source_changes_and_are_session_scoped():
    app = app_for()
    app.ask('Review.', deepen=HYPOTHESIS, session_id='one')
    from cpu_llm.hypothesis_routes import recall_deepen
    from cpu_llm.invention import invention_session
    assert recall_deepen(app, invention_session(app, None, 'other', None)) is None
    app.index.strict_source_rows.return_value = (SOURCE + rows('We measured memory bandwidth in a new experiment.'), 124)
    response = app.ask('Go deeper.', session_id='one')
    assert response['deepen']['progress']['new_source_evidence']
    # Strict/guard precede even recall and optional external calls.
    app.index.strict_source_rows.reset_mock()
    assert app.ask('Go deeper.', session_id='one', strict_evidence=True)['answer_status'] == 'unsupported'
    app.index.strict_source_rows.assert_not_called()
    app.guard.check.return_value = SimpleNamespace(decision='block')
    assert app.ask('Go deeper.', session_id='one')['answer_status'] == 'blocked'


def test_new_frontier_supersedes_old_deepen_focus():
    app = app_for()
    app.ask('Review.', deepen=HYPOTHESIS, session_id='one')
    app.ask('Frontier: inference throughput.', session_id='one')
    from cpu_llm.hypothesis_routes import recall_deepen
    from cpu_llm.invention import invention_session
    assert recall_deepen(app, invention_session(app, None, 'one', None)) is None


def test_external_adapter_is_not_called_when_strict_or_blocked():
    app = app_for()
    app.literature_reviewer = Mock()
    request = dict(hypothesis=HYPOTHESIS, novelty=True, external_review=True)
    assert app.ask('Review.', deepen=request, strict_evidence=True)['answer_status'] == 'unsupported'
    app.guard.check.return_value = SimpleNamespace(decision='block')
    assert app.ask('Review.', deepen=request)['answer_status'] == 'blocked'
    app.literature_reviewer.assert_not_called()
    app.index.strict_source_rows.assert_not_called()


def test_breadth_and_scores_unchanged_by_leading_annotations():
    source = SOURCE + rows('HBM supply increases memory bandwidth.',
                           'Inference throughput increases research funding.',
                           'Research funding increases model quality.')
    plain = run_frontier('inference throughput', source, deepen_top=0)
    checked = run_frontier('inference throughput', source, deepen_top=10)
    assert len(plain['hypotheses']) > 1
    assert [(h['id'], h['text'], h['scores']) for h in plain['hypotheses']] == [
        (h['id'], h['text'], h['scores']) for h in checked['hypotheses']]
    assert all('composition' in h['check'] for h in checked['hypotheses'][:10])


def test_http_accepts_research_envelope():
    entry = SimpleNamespace(ask=lambda secret, message, **kwargs: kwargs)
    assert _dispatch(entry, '/v1/ask', 'token', dict(message='Review.', deepen=configured_request()))[1]['deepen'] == configured_request()
