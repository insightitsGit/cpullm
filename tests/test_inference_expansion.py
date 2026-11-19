import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from cpu_llm.inference import InferenceRequest, PreparedInference, attach_inference, deduce, verify_receipt
from test_inference import rows


@pytest.mark.parametrize('texts,target', [
    (['The Kestrel is a cutter.', 'Every cutter is a vessel.', 'Every vessel has a radio.'],
     ('Kestrel', 'has', 'radio')),
    (['Every cutter is a vessel.', 'Every vessel is a vehicle.'], ('cutter', 'subclass_of', 'vehicle')),
    (['The pump is a physical part of the engine.', 'The engine is a physical part of the ship.',
      'The ship is located in the dock.'], ('pump', 'located_in', 'dock')),
    (['The pump is a physical part of the engine.'], ('engine', 'physically_contains', 'pump')),
    (['The Kestrel is a cutter.', 'Every cutter requires a radio.'], ('Kestrel', 'requires', 'radio')),
])
def test_new_rules_replay_and_bind_sources(texts, target):
    source = rows(*texts)
    result = deduce(source, InferenceRequest(*target))
    assert result['verdict'] == 'ENTAILED_BY_RULES'
    assert verify_receipt(json.loads(json.dumps(result)), source)
    assert deduce(source[::-1], InferenceRequest(*target)) == result
    changed = deepcopy(source)
    changed[0]['chunk_text'] = 'Unrelated data.'
    assert not verify_receipt(result, changed)


def test_no_statistical_inheritance_or_arbitrary_transitivity():
    source = rows('The Kestrel is a cutter.', 'The average cutter has a radio.')
    assert deduce(source, InferenceRequest('Kestrel', 'has', 'radio'))['verdict'] == 'INSUFFICIENT_SUPPORT'
    source = rows('The pump is located in the engine.', 'The engine is located in the dock.')
    assert deduce(source, InferenceRequest('pump', 'located_in', 'dock'))['verdict'] == 'INSUFFICIENT_SUPPORT'
    with pytest.raises(ValueError):
        InferenceRequest('pump', 'related_to', 'dock')


def test_taxonomic_negative_premise_blocks_proof():
    source = rows('The Kestrel is a cutter.', 'Every cutter is a vessel.',
                  'The Kestrel is not a vessel.', 'Every vessel has a radio.')
    assert deduce(source, InferenceRequest('Kestrel', 'has', 'radio'))['verdict'] == 'CONFLICT'


def test_physical_part_cycles_and_negated_containment_are_conflicts():
    source = rows('The pump is a physical part of the engine.', 'The engine is a physical part of the pump.')
    assert deduce(source, InferenceRequest('pump', 'physical_part_of', 'engine'))['verdict'] == 'CONFLICT'
    source = rows('The pump is a physical part of the engine.', 'The engine does not physically contain the pump.')
    assert deduce(source, InferenceRequest('engine', 'physically_contains', 'pump'))['verdict'] == 'CONFLICT'
    source = rows('The Kestrel is a cutter.', 'Every cutter has a radio.', 'The Kestrel does not have a radio.')
    assert deduce(source, InferenceRequest('Kestrel', 'has', 'radio'))['verdict'] == 'CONFLICT'


def test_prepared_context_reuses_extraction_and_closure_and_freezes_input():
    import cpu_llm.inference as module
    source = rows('The elephant is bigger than the donkey.', 'The donkey is bigger than the cat.')
    with patch.object(module, '_extracted', wraps=module._extracted) as extraction, \
         patch.object(module, '_closure', wraps=module._closure) as closure:
        prepared = PreparedInference(source, snapshot=12)
        a = prepared.deduce(InferenceRequest('elephant', 'bigger_than', 'cat'))
        prepared.deduce(InferenceRequest('elephant', 'bigger_than', 'donkey'))
        assert extraction.call_count == closure.call_count == 1
        source[0]['chunk_text'] = 'Changed.'
        assert prepared.deduce(InferenceRequest('elephant', 'bigger_than', 'cat')) == a
        prepared.deduce(InferenceRequest('elephant', 'bigger_than', 'cat', max_states=1))
        assert closure.call_count == 2
        damaged = prepared.deduce(InferenceRequest('elephant', 'bigger_than', 'cat'))
        damaged['proof'][0]['conclusion'][0] = 'tampered'
        damaged['rules'].clear()
        assert prepared.deduce(InferenceRequest('elephant', 'bigger_than', 'cat')) == a


def record_rows(records):
    return [dict(document_id=f'data-p{i:04}', chunk_text=json.dumps(dict(schema='inference-record-v1', **r)))
            for i, r in enumerate(records)]


def ask_records(mode, records, **kwargs):
    from cpu_llm.pipeline import Appliance
    source = record_rows(records)
    app = object.__new__(Appliance)
    app.tenant_id = 'test'
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision='allow'))
    app.index = SimpleNamespace(strict_source_rows=lambda allowed, as_of=None: (source, as_of))
    options = dict(mode=mode, source_ids=[r['document_id'] for r in source])
    return app.ask('Analyze the selected records.', inference=options, **kwargs), source


def test_temporal_calendar_intersection_and_strict_guard():
    records = [dict(kind='interval', start='2026-01-01', end='2026-01-31'),
               dict(kind='interval', start='2026-01-31', end='2026-02-28')]
    response, source = ask_records('temporal', records, as_of=42)
    receipt = response['inference']
    assert receipt['intersection'] == ['2026-01-31', '2026-01-31']
    assert receipt['claim_status'] == 'TEMPORAL_CALCULATION'
    assert verify_receipt(json.loads(json.dumps(receipt)), source)
    assert len(response['evidence_panel']['sources']) == 2
    assert ask_records('temporal', records, strict_evidence=True)[0]['answer_status'] == 'unsupported'
    records[1]['start'] = '2027-01-01'
    assert ask_records('temporal', records)[0]['answer_status'] == 'insufficient_evidence'


def test_induction_counts_unique_observations_and_uncertainty():
    records = [dict(kind='bernoulli', observation_id=str(i), population='batch-a', success=i < 5)
               for i in range(10)]
    response, source = ask_records('inductive', records)
    receipt = response['inference']
    assert receipt['sample_size'] == 10 and receipt['successes'] == 5
    assert receipt['interval_95'] == pytest.approx([.23659309, .76340691])
    assert response['answer_status'] == 'statistical_estimate'
    assert verify_receipt(receipt, source)
    records[1]['observation_id'] = '0'
    assert ask_records('inductive', records)[0]['answer_status'] == 'insufficient_evidence'


def test_abduction_compares_alternatives_without_promoting_the_winner():
    records = [dict(kind='observation', id='O1', description='The measured spectrum has a peak.'),
               dict(kind='explanation', id='H1', description='Candidate material effect.', explains=['O1'],
                    contradicts=[], test='Repeat using another material.'),
               dict(kind='explanation', id='H2', description='Candidate detector effect.', explains=[],
                    contradicts=['O1'], test='Repeat using another detector.')]
    response, source = ask_records('abductive', records)
    receipt = response['inference']
    assert receipt['candidates'][0]['id'] == 'H1'
    assert receipt['claim_status'] == 'UNVERIFIED_HYPOTHESIS'
    assert 'unverified hypotheses' in response['reply']['text']
    assert verify_receipt(receipt, source)
    records[-1]['explains'] = ['nonexistent']
    assert ask_records('abductive', records)[0]['answer_status'] == 'insufficient_evidence'


def test_analysis_scope_does_not_disclose_missing_records():
    from cpu_llm.evidence_analysis import EvidenceAnalysisRequest, analyze
    source = record_rows([dict(kind='interval', start='2026-01-01', end='2026-01-02')])
    receipt = analyze(source, EvidenceAnalysisRequest('temporal', ['data-p0000']), scope=[])
    assert receipt['verdict'] == 'INSUFFICIENT_SUPPORT'
    assert not receipt['evidence']


@pytest.mark.parametrize('text', [
    '{"schema":"inference-record-v1","kind":"bernoulli","population":"trial","observation_id":"1","success":true,"success":false}',
    '{"schema":"inference-record-v1","kind":"bernoulli","population":"trial","observation_id":"1","success":NaN}',
])
def test_ambiguous_or_nonstandard_json_is_rejected(text):
    from cpu_llm.evidence_analysis import analyze, EvidenceAnalysisRequest
    receipt = analyze([dict(document_id='data-p0000', chunk_text=text)],
                      EvidenceAnalysisRequest('inductive', ['data-p0000']))
    assert receipt['verdict'] == 'INSUFFICIENT_SUPPORT'


@pytest.mark.parametrize('mode,records', [
    ('temporal', [dict(kind='interval', start='2026-02-30', end='2026-03-01')]*2),
    ('temporal', [dict(kind='interval', start='2026-01-01T00:00Z', end='2026-03-01')]*2),
    ('inductive', [dict(kind='bernoulli', observation_id='A', population='trial', success=1)]),
    ('inductive', [dict(kind='bernoulli', observation_id='A', population='trial', success=True),
                   dict(kind='bernoulli', observation_id='B', population='other', success=False)]),
    ('abductive', [dict(kind='observation', id='O1', description='Observed.')]),
])
def test_invalid_analysis_inputs_do_not_produce_conclusions(mode, records):
    response, _ = ask_records(mode, records)
    assert response['answer_status'] == 'insufficient_evidence'
    assert response['inference']['claim_status'] == 'UNRESOLVED'


def test_new_prompt_routes_are_explicit_and_quoted_background_is_not_a_trigger():
    from cpu_llm.inference import request_from
    assert request_from('Is Kestrel a member of vessel?').relation == 'member_of'
    assert request_from('Does Kestrel require radio?').relation == 'requires'
    assert request_from('Temporal: sources: data-p0000, data-p0001').mode == 'temporal'
    assert request_from('Explain "Temporal: sources: data-p0000"') is None


def test_channel_preparation_is_shared_then_invalidated():
    from cpu_llm.pipeline import _channel
    app = SimpleNamespace(_turn={}, index=SimpleNamespace(pipeline=SimpleNamespace(enabled_channels={})), memory=None)
    state = dict(related=[dict(chunk_id='x', chunk_text='X', score=1)])
    with patch('cpu_llm.pipeline._passages', return_value=[]) as passages, \
         patch('cpu_llm.pipeline._identity_anchor', return_value=(False, None)) as anchor, \
         patch('cpu_llm.pipeline.read_channel', return_value={}):
        for channel in ('dense', 'relational', 'disentangled', 'hyperbolic', 'identity', 'causal'):
            _channel(app, channel)(state)
        assert passages.call_count == anchor.call_count == 1
        state['related'][0]['chunk_text'] = 'Changed'
        _channel(app, 'dense')(state)
        assert passages.call_count == anchor.call_count == 2


def test_crossdomain_deduction_uses_only_selected_prefixes():
    from cpu_llm.crossdomin import execute_cross_domain
    source = [dict(document_id='physics-p0001', chunk_text='The elephant is bigger than the donkey.'),
              dict(document_id='biology-p0001', chunk_text='The donkey is bigger than the cat.')]
    app = SimpleNamespace(tenant_id='test', guard=SimpleNamespace(check=lambda _: SimpleNamespace(decision='allow')),
                          index=SimpleNamespace(strict_source_rows=lambda allowed, as_of=None: (source, 42)))
    response = execute_cross_domain(app, 'CrossDomain: elephant', 'elephant')
    assert response['research_inference']['receipts'] == []
    source[1]['document_id'] = 'mathematics-p0001'
    response = execute_cross_domain(app, 'CrossDomain: elephant', 'elephant')
    assert response['research_inference']['receipts'][0]['verdict'] == 'ENTAILED_BY_RULES'


def test_explicit_inference_does_not_silently_override_specialists():
    from cpu_llm.pipeline import Appliance
    app = object.__new__(Appliance)
    with pytest.raises(ValueError, match='separately'):
        app.ask('Infer whether elephant is bigger than cat.', invent=True)


def test_natural_question_parser_failure_falls_through_and_explicit_failure_clarifies():
    from cpu_llm.inference import request_from
    from cpu_llm.pipeline import Appliance
    assert request_from('Does the contract have a $5,000 cap?') is None
    assert request_from('Does the policy have some exclusions?') is None
    app = object.__new__(Appliance)
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision='allow'))
    response = app.ask('Infer whether the contract has a $5,000 cap.')
    assert response['answer_status'] == 'needs_clarification'


def test_natural_question_keeps_normal_answering_and_strict_quotation():
    from cpu_llm.pipeline import Appliance
    source = rows('The Kestrel carries a VHF radio.')
    app = object.__new__(Appliance)
    app.tenant_id = 'test'
    app.small_talk = False
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision='allow'))
    app.index = SimpleNamespace(strict_source_rows=lambda allowed, as_of=None: (source, 42))
    normal = dict(answer_status='answered', reply=dict(text='Normal answering retained.'))
    with patch('cpu_llm.request_planner.dispatch_request', return_value=normal) as dispatch:
        response = app.ask('Does the Kestrel have a radio?')
        assert response['reply']['text'] == 'Normal answering retained.'
        assert dispatch.call_count == 1
    strict = dict(answer_status='evidence_quote', reply=dict(text='Strict quotation retained.'))
    with patch('cpu_llm.strict_evidence.answer', return_value=strict) as quote, \
         patch('cpu_llm.inference.execute_inference', side_effect=AssertionError('strict inference invoked')):
        response = app.ask('Does the Kestrel have a radio?', strict_evidence=True)
        assert response['answer_status'] == 'evidence_quote'
        assert quote.call_count == 1


def test_abbreviation_newline_does_not_abort_unrelated_inference():
    source = rows('Dr.\nSmith is a surgeon.', 'The elephant is bigger than the donkey.',
                  'The donkey is bigger than the cat.')
    assert deduce(source, InferenceRequest('elephant', 'bigger_than', 'cat'))['verdict'] == 'ENTAILED_BY_RULES'


def test_explicit_negative_is_distinct_from_missing_support():
    source = rows('The Kestrel does not have a radio.')
    receipt = deduce(source, InferenceRequest('Kestrel', 'has', 'radio'))
    assert receipt['verdict'] == 'CONTRADICTED_BY_RULES'
    assert verify_receipt(receipt, source)
    assert deduce(source, InferenceRequest('Kestrel', 'has', 'radar'))['verdict'] == 'INSUFFICIENT_SUPPORT'


@pytest.mark.parametrize('message,owner', [
    ('Nammade: elephant', 'nammade'), ('CrossDomain: elephant', 'crossdomin'),
    ('Invent a new concept from elephant', 'invention'), ('Research elephant', 'research'),
    ('What is a research vessel?', None), ('Do not invent a new concept from elephant', None),
])
def test_specialist_plan_has_one_primary_candidate(message, owner):
    from cpu_llm.classifier import specialist_plan
    assert specialist_plan(message)['primary_candidate'] == owner
