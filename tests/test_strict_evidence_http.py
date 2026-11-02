import json
import threading
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from cpu_llm.serve import LocalService


@pytest.mark.parametrize('floor,header,expected', [(False, 'strict', True), (True, 'standard', True), (False, 'standard', False)])
def test_actual_header_reaches_entry_and_floor_cannot_be_disabled(floor, header, expected):
    entry = SimpleNamespace(ask=lambda secret, message, **kwargs: dict(strict=kwargs.get('strict_evidence', False)))
    service = LocalService(entry, port=0, strict_evidence=floor)
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(f'http://127.0.0.1:{service.port}/v1/ask',
            data=json.dumps(dict(message='question', strict_evidence=False)).encode(),
            headers={'Authorization': 'Bearer test-only', 'Content-Type': 'application/json',
                     'X-CPU-LLM-Evidence-Mode': header})
        with urlopen(request, timeout=5) as response:
            assert json.load(response)['strict'] is expected
        request.headers['X-cpu-llm-evidence-mode'] = 'typo'
        with pytest.raises(HTTPError) as error:
            urlopen(request, timeout=5)
        assert error.value.code == 400
    finally:
        service.close()
        thread.join(timeout=5)
