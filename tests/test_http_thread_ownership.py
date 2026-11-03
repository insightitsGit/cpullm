"""A cached tenant's thread-affine state must work across separate clients."""
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
import json
import sqlite3
import threading
from types import SimpleNamespace
from urllib.request import Request,urlopen
from cpu_llm.serve import LocalService

def test_separate_clients_share_sqlite_owner_thread_and_serialize():
    state={};lock=threading.Lock()
    def ask(secret,message,**kwargs):
        with lock:
            if 'conn' not in state:
                state['conn']=sqlite3.connect(':memory:')
                state['owner']=threading.get_ident()
        try:
            state['conn'].execute('SELECT 1').fetchone()
            return dict(ok=True,owner=threading.get_ident())
        except sqlite3.ProgrammingError:
            return dict(ok=False,reason='cross_thread_sqlite')
    service=LocalService(SimpleNamespace(ask=ask),port=0)
    def serve():
        try:service.serve_forever()
        finally:
            if 'conn' in state:state['conn'].close()
    owner=threading.Thread(target=serve,daemon=True);owner.start()
    def request(i):
        req=Request(f'http://127.0.0.1:{service.port}/v1/ask',data=json.dumps(dict(message=str(i))).encode(),
            headers={'Authorization':'Bearer test-only','Content-Type':'application/json'})
        with urlopen(req,timeout=10) as response:return json.load(response)
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:responses=list(pool.map(request,range(8)))
        assert all(r['ok'] for r in responses),responses
        assert {r['owner'] for r in responses}=={state['owner']}
    finally:service.close();owner.join(timeout=5)

def test_idle_keepalive_cannot_hold_the_serial_server():
    service=LocalService(SimpleNamespace(ask=lambda *a,**k:dict(ok=True)),port=0)
    owner=threading.Thread(target=service.serve_forever,daemon=True);owner.start()
    first=HTTPConnection('127.0.0.1',service.port,timeout=5)
    second=HTTPConnection('127.0.0.1',service.port,timeout=5)
    try:
        headers={'Authorization':'Bearer test-only','Content-Type':'application/json'}
        first.request('POST','/v1/ask',body=json.dumps(dict(message='first')),headers=headers)
        response=first.getresponse();assert json.loads(response.read())['ok']
        assert response.getheader('Connection')=='close'
        second.request('POST','/v1/ask',body=json.dumps(dict(message='second')),headers=headers)
        assert json.loads(second.getresponse().read())['ok']
    finally:
        first.close();second.close();service.close();owner.join(timeout=5)
