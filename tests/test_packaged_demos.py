import json
from pathlib import Path
import tomllib
from cpu_llm import __version__
from cpu_llm.demo import load_dataset,verify


def test_release_version_and_healthcare_resource_stay_in_sync():
    root=Path(__file__).resolve().parents[1]
    project=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))
    assert project['project']['version']==__version__
    original=json.loads((root/'examples/healthcare/dataset.json').read_text(encoding='utf-8'))
    assert load_dataset('healthcare')==original


def test_packaged_demo_resources_have_valid_proof_references():
    for kind in ('healthcare','conversation'):
        data=load_dataset(kind)
        assert data['synthetic'] and not data['clinical_validation']
        ids={f"{d['name']}-p{i:04d}" for d in data['documents'] for i,_ in enumerate(d['paragraphs'],1)}
        assert len(data['questions'])==12
        assert all(set(q['expected_proofs'])<=ids for q in data['questions'])


def test_social_output_does_not_pass_without_its_distinct_kind():
    question=load_dataset('conversation')['questions'][0]
    result=dict(answer_status='conversation',reply=dict(text='hello'),answer=None,
                answer_evidence=[],audit_passed=False,evidence_policy=dict(learned_generation=False))
    assert not verify(question,result,{})['passed']
    result['response_kind']='conversation'
    assert verify(question,result,{})['passed']
