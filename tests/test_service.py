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
        missing_path = _post(service.port, "/v1/missing", {"message": "hello"}, secret="alpha-secret")
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
    assert missing_path[0] == 404
    assert missing_path[1]["message"] == "that path is not served"


def _credential(path, sources):
    path.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "id": "alice",
                        "secret_sha256": secret_sha256("alpha-secret"),
                        "tenant_id": "tenant_alpha",
                        "caller_id": "alice",
                        "allowed_sources": sources,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


class _Recording:
    def __init__(self):
        self.ingested = []

    def ingest(self, source):
        self.ingested.append(source)
        return {"documents": len(source)}


def test_path_ingest_checks_the_root_and_every_document(tmp_path):
    root = tmp_path / "inbox"
    outside = tmp_path / "private"
    root.mkdir()
    outside.mkdir()
    (outside / "notes.txt").write_text("A private note.\n", encoding="utf-8")
    (root / "notes.txt").write_text("A public note.\n", encoding="utf-8")
    mixed = root / "mixed"
    mixed.mkdir()
    (mixed / "notes.txt").write_text("A public note.\n", encoding="utf-8")
    (mixed / "other.txt").write_text("Another note.\n", encoding="utf-8")
    secrets = tmp_path / "secrets.json"
    _credential(secrets, ["notes-p"])
    appliance = _Recording()
    entry = Entry(secrets, lambda _tenant: appliance, ingest_root=root)
    with pytest.raises(SourceForbidden):
        entry.ingest("alpha-secret", outside / "notes.txt")
    with pytest.raises(SourceForbidden):
        entry.ingest("alpha-secret", mixed)
    link = root / "notes.txt"
    try:
        link.symlink_to(outside / "notes.txt")
    except OSError:
        link.write_text("A linked note.\n", encoding="utf-8")
        outside_resolved = (outside / "notes.txt").resolve()
        original_resolve = type(link).resolve

        def _resolved(self, *args, **kwargs):
            if self == link:
                return outside_resolved
            return original_resolve(self, *args, **kwargs)

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(type(link), "resolve", _resolved)
        try:
            with pytest.raises(SourceForbidden, match="outside the ingest root"):
                entry.ingest("alpha-secret", link)
        finally:
            monkeypatch.undo()
    else:
        with pytest.raises(SourceForbidden, match="outside the ingest root"):
            entry.ingest("alpha-secret", link)
    assert appliance.ingested == []
    closed = Entry(secrets, lambda _tenant: appliance)
    with pytest.raises(SourceForbidden):
        closed.ingest("alpha-secret", root / "notes.txt")
    receipt = entry.ingest("alpha-secret", root / "notes.txt")
    assert receipt["documents"] == 1
    assert len(appliance.ingested) == 1


def test_http_ingest_refuses_a_path_outside_the_root(tmp_path):
    root = tmp_path / "inbox"
    outside = tmp_path / "private"
    root.mkdir()
    outside.mkdir()
    target = outside / "notes.txt"
    target.write_text("A private note.\n", encoding="utf-8")
    secrets = tmp_path / "secrets.json"
    _credential(secrets, ["notes-p"])
    appliance = _Recording()
    service = LocalService(Entry(secrets, lambda _tenant: appliance, ingest_root=root), port=0)
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    try:
        refused = _post(service.port, "/v1/ingest", {"source": str(target)}, secret="alpha-secret")
        body = _post(
            service.port,
            "/v1/ingest",
            {"name": "notes", "paragraphs": ["A public note."]},
            secret="alpha-secret",
        )
    finally:
        service.close()
        thread.join(2)
    assert refused[0] == 403
    assert body[0] == 200
    assert len(appliance.ingested) == 1


def test_one_tenant_builds_one_appliance():
    import time

    from cpu_llm.serve import cached_appliance

    cache = {}
    lock = threading.Lock()
    calls = []

    def factory(tenant):
        calls.append(tenant)
        time.sleep(0.05)
        return object()

    threads = [
        threading.Thread(target=lambda: cached_appliance(cache, lock, "t", factory))
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert calls == ["t"]
    assert len(cache) == 1


def test_turns_for_one_session_do_not_overlap():
    import time

    from cpu_llm.pipeline import Appliance

    appliance = Appliance.__new__(Appliance)
    current = []
    seen = []

    def work():
        with appliance._session_turn("s"):
            current.append(1)
            seen.append(len(current))
            time.sleep(0.01)
            current.pop()

    threads = [threading.Thread(target=work) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert seen
    assert max(seen) == 1
