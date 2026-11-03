import json
import threading
from types import SimpleNamespace
from urllib.request import Request,urlopen
import pytest
from cpu_llm.serve import LocalService,_dispatch
from test_conversation import app


@pytest.mark.parametrize('enabled,expected',[(True,'conversation'),(False,'unsupported')])
def test_http_default_and_disable_floor(enabled,expected):
    built=app()
    entry=SimpleNamespace(ask=lambda secret,message,**kwargs:built.ask(message,**kwargs))
    server=LocalService(entry,port=0,strict_evidence=True,small_talk=enabled)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        request=Request(f'http://127.0.0.1:{server.port}/v1/ask',
            data=json.dumps(dict(message='Who are you?',small_talk=True)).encode(),
            headers={'Authorization':'Bearer test-only','Content-Type':'application/json'})
        with urlopen(request,timeout=5) as response:result=json.load(response)
        assert result['answer_status']==expected
        assert result['evidence_policy']['enabled']
    finally:server.close();thread.join(timeout=5)


def test_http_rejects_nonboolean_smalltalk():
    with pytest.raises(ValueError):_dispatch(SimpleNamespace(),'/v1/ask','secret',dict(message='hi',small_talk='false'))
