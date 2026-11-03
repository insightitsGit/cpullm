import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('healthcare_demo',ROOT/'examples/healthcare/run_demo.py')
demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)


def test_demo_expected_sources_exist_and_ids_are_unique():
    data=json.loads(demo.DATASET.read_text(encoding='utf-8'))
    assert data['synthetic'] and not data['clinical_validation']
    sources={f"{d['name']}-p{i:04d}":p for d in data['documents'] for i,p in enumerate(d['paragraphs'],1)}
    assert len(sources)==11
    assert len({q['id'] for q in data['questions']})==12
    assert all(set(q['expected_proofs']) <= sources.keys() for q in data['questions'])


def test_demo_checker_does_not_accept_missing_proofs_or_wrong_values():
    data=json.loads(demo.DATASET.read_text(encoding='utf-8'))
    question=data['questions'][0]
    result=dict(answer_status='evidence_quote',reply=dict(text='0.75 mg; 750 mcg'),
                evidence_policy=dict(learned_generation=False),answer_evidence=[])
    assert not demo.check(question,result,{})['passed']
    result['reply']['text']='0.25 mg'
    assert not demo.check(question,result,{})['checks']['visible_values']
