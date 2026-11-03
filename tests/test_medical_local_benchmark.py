import importlib.util
from pathlib import Path

path=Path(__file__).resolve().parents[1]/'tools/benchmarks/medical_local.py'
spec=importlib.util.spec_from_file_location('medical_local',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_balanced_domains_unique_cases_and_distinct_task_types():
    cases=module.cases()
    assert len(cases)==len({c['id'] for c in cases})==32
    assert sum(c['domain']=='medication' for c in cases)==16
    assert sum(c['domain']=='healthcare' for c in cases)==16
    assert {'conflict','refusal','fact','calculation','comparison'} <= {c['outcome'] for c in cases}


def test_common_scorer_accepts_equivalent_numeric_format_and_normal_status():
    case=dict(outcome='calculation',values=['10.500'],required_sources=[])
    result=dict(answer_status='answered',reply=dict(text='12*0.875 = 10.5.'))
    assert module.score(case,result,[])['ok']
    result['reply']['text']='The result is 10.5001.'
    assert not module.score(case,result,[])['ok']


def test_plain_record_and_hashed_proofs_are_scored_equally_and_scope_checked():
    case=dict(outcome='fact',values=['compound K'],required_sources=[0])
    rows=[dict(document_id='public-p0001',chunk_text='The recorded allergy of Case Alder is compound K.')]
    result=dict(answer_status='evidence_quote',reply=dict(text=rows[0]['chunk_text']),
                answer_evidence=[dict(document_id='public-p0001',span=rows[0]['chunk_text'])])
    assert module.score(case,result,rows)['ok']
    result['answer_evidence'][0]['document_id']='private-p0001'
    assert not module.score(case,result,rows)['ok']


def test_always_refuse_is_not_a_success_and_missing_proof_is_separate():
    case=dict(outcome='fact',values=['compound K'],required_sources=[0])
    rows=[dict(document_id='public-p0001',chunk_text='compound K')]
    result=dict(answer_status='unsupported',reply=dict(text='No answer.'))
    assert not module.score(case,result,rows)['ok']
    result=dict(answer_status='answered',reply=dict(text='compound K'))
    verdict=module.score(case,result,rows)
    assert verdict['task_success']
    assert not verdict['ok']


def test_ordinary_clarification_envelope_is_a_valid_nonanswer():
    case=dict(outcome='refusal',values=[],required_sources=[])
    response=dict(status='needs_clarification',reply=dict(text='Which entity do you mean?'))
    assert module.score(case,response,[])['ok']


def test_visible_arithmetic_with_a_held_decision_is_not_full_contract_success():
    case=dict(outcome='calculation',values=['10.500'],required_sources=[])
    response=dict(judgment=dict(outcome='insufficient_evidence'),reply=dict(text='Math: 12*0.875 = 10.5.'))
    score=module.score(case,response,[])
    assert score['checks']['visible_value']
    assert not score['checks']['outcome']
    assert not score['ok']
