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
    assert set(SPEC['paths'])=={'/v1/ask','/v1/ingest','/v1/correct','/v1/delete','/v1/chunks','/v1/delete-chunk'}
    assert 'style' not in fields
    header=SPEC['paths']['/v1/ask']['post']['parameters'][0]
    assert header['name']=='X-CPU-LLM-Evidence-Mode'
    assert header['schema']['enum']==['strict','standard']


def test_chunk_management_routes_forward_payloads():
    entry = SimpleNamespace(
        chunk_inventory=lambda secret, source, **page: (secret, source, page),
        delete_chunk=lambda secret, document_id, confirmation: (secret, document_id, confirmation),
    )
    assert _dispatch(entry, '/v1/chunks', 'team', {'source': 'notes.pdf', 'limit': 2, 'offset': 5}) == (
        200, ('team', 'notes.pdf', {'limit': 2, 'offset': 5}),
    )
    assert _dispatch(entry, '/v1/delete-chunk', 'team', {'document_id': 'notes-p0001'}) == (
        200, ('team', 'notes-p0001', None),
    )
    assert _dispatch(entry, '/v1/delete-chunk', 'team', {
        'document_id': 'notes-p0001', 'confirmation': 'token',
    }) == (200, ('team', 'notes-p0001', 'token'))

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
