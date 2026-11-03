"""The published OpenAPI file must match the existing server's actual controls."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from cpu_llm.serve import _ASK_FIELDS, _dispatch

SPEC=json.loads((Path(__file__).resolve().parents[1]/'docs/openapi.json').read_text())

def test_ask_fields_and_routes_match_the_server():
    fields=SPEC['components']['schemas']['AskRequest']['properties']
    assert set(fields)=={'message',*_ASK_FIELDS}
    assert set(SPEC['paths'])=={'/v1/ask','/v1/ingest','/v1/correct','/v1/delete'}
    assert 'style' not in fields
    header=SPEC['paths']['/v1/ask']['post']['parameters'][0]
    assert header['name']=='X-CPU-LLM-Evidence-Mode'
    assert header['schema']['enum']==['strict','standard']

@pytest.mark.parametrize('name',['ordinaryDocument','strictDocument','strictLookup'])
def test_documented_ask_examples_reach_entry(name):
    payload=SPEC['paths']['/v1/ask']['post']['requestBody']['content']['application/json']['examples'][name]['value']
    entry=SimpleNamespace(ask=lambda secret,message,**kwargs:dict(message=message,options=kwargs))
    code,result=_dispatch(entry,'/v1/ask','test-only',payload)
    assert code==200 and result['message']==payload['message']
    assert result['options'].get('strict_evidence',False)==payload.get('strict_evidence',False)

def test_documented_strict_floor_and_unknown_field_behavior():
    entry=SimpleNamespace(ask=lambda secret,message,**kwargs:kwargs)
    code,result=_dispatch(entry,'/v1/ask','test-only',dict(message='question',strict_evidence=False,style='friendly'),evidence_mode='standard',require_strict=True)
    assert result['strict_evidence'] is True and 'style' not in result
    with pytest.raises(ValueError):
        _dispatch(entry,'/v1/ask','test-only',dict(message='question',strict_evidence='yes'))
