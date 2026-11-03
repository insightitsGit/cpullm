"""Keep the manual's public prompt recipes connected to implemented controls."""
import json
from pathlib import Path
import pytest
from cpu_llm.document_workflow import plan_document
from cpu_llm.response_policy import classify_response_request
from cpu_llm.stylistic.profiles import extract_style_request

ROOT=Path(__file__).resolve().parents[1]
SPEC=json.loads((ROOT/'docs/document-generation-findings.json').read_text(encoding='utf-8'))

@pytest.mark.parametrize('case',SPEC['prompt_cases'],ids=lambda case:case['prompt'])
def test_manual_prompt_contract(case):
    tone=extract_style_request(case['prompt'])
    plan=plan_document(case['prompt'])
    assert tone['tone']==case['tone']
    assert plan['topic']==case['topic']
    assert plan['genre']==case['genre']
    assert plan['format']==case['format']
    assert plan['output_media']==case['media']
    response=classify_response_request(case['prompt'])
    assert response['content_query']==case['topic']
    assert response['document']['topic']==case['topic']

def test_findings_references_are_real():
    for requirement in SPEC['requirements']:
        assert (ROOT/requirement['test']).is_file()
    for key in ('manual','specification'):
        assert (ROOT/SPEC[key]).is_file()
