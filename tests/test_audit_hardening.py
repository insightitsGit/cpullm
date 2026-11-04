import io
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from cpu_llm.strict_evidence_engine import value_key
from cpu_llm.serve import _json_body, MAX_REQUEST_BYTES

@pytest.mark.parametrize('left,right', [('1','1.0'),('1 mg','1 milligram'),('1 mg','0.001 g'),('1 mL','1 milliliter')])
def test_exact_equivalence(left,right):
    assert value_key(left)==value_key(right)

@pytest.mark.parametrize('left,right', [('1','1 mg'),('1 mg','1 mL'),('1 mg','1.000001 mg'),('cold','Cold'),('1 mg if needed','1 mg'),('not 1 mg','1 mg')])
def test_distinctions_retained(left,right):
    assert value_key(left)!=value_key(right)

@pytest.mark.parametrize('headers', [{'Content-Length':'-1'}, {'Content-Length':str(MAX_REQUEST_BYTES+1)}, {'Transfer-Encoding':'chunked'}, {'Content-Length':'oops'}])
def test_body_rejected_before_read(headers):
    stream=Mock()
    with pytest.raises(ValueError): _json_body(SimpleNamespace(headers=headers,rfile=stream))
    stream.read.assert_not_called()

def test_truncated_body_rejected():
    with pytest.raises(ValueError):
        _json_body(SimpleNamespace(headers={'Content-Length':'20'},rfile=io.BytesIO(b'{}')))

def test_learned_writer_requires_opt_in(monkeypatch):
    from cpu_llm.answering import situation_from_chunks
    result=SimpleNamespace(verdict='NONE',text='',because=[],wording={})
    answer=Mock(return_value=result)
    monkeypatch.setattr('fact_bridge.answer',answer)
    monkeypatch.setattr('fact_bridge.model_root',lambda: 'compatible-model')
    monkeypatch.delenv('CPU_LLM_ALLOW_LEARNED_WRITER',raising=False)
    situation_from_chunks('Can I enter?', ['Entry is allowed.'])
    assert answer.call_count==1
    monkeypatch.setenv('CPU_LLM_ALLOW_LEARNED_WRITER','1')
    situation_from_chunks('Can I enter?', ['Entry is allowed.'])
    assert answer.call_count==3
    assert answer.call_args.kwargs['ml'] is True


def test_child_safety_controls_warn_even_on_early_return():
    from cpu_llm.pipeline import _warn_unsupported_child_safety
    with pytest.warns(RuntimeWarning, match='not applied'):
        _warn_unsupported_child_safety(child_safety=True)
    with pytest.warns(RuntimeWarning, match='not applied'):
        _warn_unsupported_child_safety(grade=5)
    with pytest.raises(ValueError):
        _warn_unsupported_child_safety(child_safety='yes')


def test_slow_body_releases_serial_server(monkeypatch):
    import socket, threading, json
    from http.client import HTTPConnection
    from cpu_llm.serve import LocalService
    monkeypatch.setattr('cpu_llm.serve.CLIENT_READ_TIMEOUT_SECONDS', 0.15)
    service=LocalService(SimpleNamespace(ask=lambda *a,**k: {'ok': True}),port=0)
    thread=threading.Thread(target=service.serve_forever,daemon=True); thread.start()
    slow=socket.create_connection(('127.0.0.1',service.port),timeout=3)
    good=HTTPConnection('127.0.0.1',service.port,timeout=3)
    try:
        slow.sendall(b'POST /v1/ask HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer test\r\nContent-Length: 100\r\n\r\n{')
        assert b'408' in slow.recv(4096)
        good.request('POST','/v1/ask',body=json.dumps({'message':'hello'}),headers={'Authorization':'Bearer test'})
        response=good.getresponse()
        assert response.status==200 and json.loads(response.read())['ok']
    finally:
        slow.close(); good.close(); service.close(); thread.join(timeout=3)


@pytest.mark.parametrize('alternative', ['1.0', '1.000'])
def test_numeric_equivalence_retains_both_proofs(alternative):
    from test_strict_evidence import appliance
    result=appliance('The count of Demo is 1.',f'The count of Demo is {alternative}.').ask(
        'What is the count of Demo?',strict_evidence=True)
    assert result['answer_status']=='evidence_quote'
    assert len(result['answer_evidence'])==2
