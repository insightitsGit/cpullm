"""The local service checks the bearer secret before it opens a turn."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from cpu_llm.access import AuthenticationError, SourceForbidden
from cpu_llm.entry import Entry, secret_sha256
from cpu_llm.serve import LocalService


def _post(port: int, path: str, payload: dict, secret: str | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if secret is not None:
        headers["Authorization"] = f"Bearer {secret}"
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_a_plaintext_secret_file_is_refused(tmp_path):
    path = tmp_path / "secrets.json"
    path.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "id": "alice",
                        "secret": "visible-secret",
                        "tenant_id": "tenant_alpha",
                        "caller_id": "alice",
                        "allowed_sources": ["alpha-p"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(AuthenticationError) as caught:
        Entry(path, lambda _tenant: None)
    assert "secret_sha256" in str(caught.value)
    assert "Traceback" not in str(caught.value)
    assert "visible-secret" not in str(caught.value)


def test_the_service_rejects_a_bad_bearer_before_the_appliance(tmp_path):
    path = tmp_path / "secrets.json"
    path.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "id": "alice",
                        "secret_sha256": secret_sha256("alpha-secret"),
                        "tenant_id": "tenant_alpha",
                        "caller_id": "alice",
                        "allowed_sources": ["alpha-p"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    calls: list[str] = []

    class Appliance:
        def ask(self, message, caller=None, **kwargs):
            calls.append(message)
            return {"reply": {"text": "The stored sentence."}, "answer": "The stored sentence."}

        def delete_source(self, source):
            raise SourceForbidden("that source is outside this caller's scope")

    service = LocalService(Entry(path, lambda _tenant: Appliance()), port=0)
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    try:
        missing = _post(service.port, "/v1/ask", {"message": "What is the lobster?"})
        wrong = _post(service.port, "/v1/ask", {"message": "What is the lobster?"}, secret="other-secret")
        accepted = _post(service.port, "/v1/ask", {"message": "What is the lobster?"}, secret="alpha-secret")
        forbidden = _post(service.port, "/v1/delete", {"source": "beta-notes"}, secret="alpha-secret")
    finally:
        service.close()
        thread.join(2)
    assert missing[0] == 401
    assert wrong[0] == 401
    assert "Traceback" not in json.dumps(wrong[1])
    assert calls == ["What is the lobster?"]
    assert accepted[0] == 200
    assert accepted[1]["answer"] == "The stored sentence."
    assert "alpha-secret" not in json.dumps(accepted[1])
    assert forbidden[0] == 403
    assert forbidden[1]["error"] == "source_forbidden"
