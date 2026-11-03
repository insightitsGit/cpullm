"""A local HTTP service in front of ``Entry``.

The process binds to ``127.0.0.1`` unless the operator names another host.
The caller sends the secret in ``Authorization: Bearer``. The secret file
stores only SHA-256 digests. A failure is the typed error dict. The body
does not include a traceback.
"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from cpu_llm.access import AccessError, AuthenticationError, SourceForbidden, StorageError
from cpu_llm.documents import SourceDocument
from cpu_llm.entry import Entry

_ASK_FIELDS = ("discover", "imagine", "deep", "math", "finance", "as_of", "session_id", "strict_evidence", "small_talk")


class UnknownRoute(Exception):
    """The request named a path this service does not provide."""


class LocalService:
    """One process serving ask, ingest, correct, and delete_source."""

    def __init__(self, entry: Entry, host: str = "127.0.0.1", port: int = 8765, *, strict_evidence: bool = False, small_talk: bool = True) -> None:
        if type(strict_evidence) is not bool:
            raise ValueError('strict_evidence must be a boolean')
        if type(small_talk) is not bool:
            raise ValueError('small_talk must be a boolean')
        self.entry = entry
        self.host = host
        self._httpd = ThreadingHTTPServer((host, port), _handler(entry, strict_evidence=strict_evidence, small_talk=small_talk))
        self.port = int(self._httpd.server_address[1])

    def serve_forever(self) -> None:
        self._httpd.serve_forever()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve cpu-llm on a local port.")
    parser.add_argument("--secrets", required=True, help="JSON file of secret_sha256 credentials")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument('--strict-evidence', action='store_true', help='Require literal source evidence for every ask')
    parser.add_argument('--no-small-talk', action='store_true', help='Disable built-in conversational replies and greeting normalization')
    parser.add_argument('--reference-backend', choices=['coreferee', 'fastcoref'])
    parser.add_argument('--prompt-backend', choices=['auto', 'rules', 'spacy'], default='auto')
    parser.add_argument(
        "--ingest-root",
        default=None,
        help="Directory that path ingestion may read. Required for source paths.",
    )
    args = parser.parse_args()
    appliances: dict[str, Any] = {}
    cache_lock = threading.Lock()

    def build(tenant: str) -> Any:
        from cpu_llm.pipeline import Appliance

        return Appliance(
            namespace=None if tenant == "cpu-llm" else tenant,
            reference_backend=args.reference_backend,
            prompt_backend=args.prompt_backend,
            small_talk=not args.no_small_talk,
        )

    def appliance_for(tenant: str) -> Any:
        return cached_appliance(appliances, cache_lock, tenant, build)

    service = LocalService(
        Entry(args.secrets, appliance_for, ingest_root=args.ingest_root),
        host=args.host,
        port=args.port,
        strict_evidence=args.strict_evidence,
        small_talk=not args.no_small_talk,
    )
    try:
        service.serve_forever()
    finally:
        service.close()
        for appliance in appliances.values():
            appliance.close()


def _handler(entry: Entry, *, strict_evidence: bool = False, small_talk: bool = True) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:  # noqa: N802 — stdlib handler name
            try:
                secret = _bearer(self.headers.get("Authorization"))
                payload = _json_body(self)
                status, body = _dispatch(entry, self.path, secret, payload,
                    evidence_mode=self.headers.get('X-CPU-LLM-Evidence-Mode'), require_strict=strict_evidence, allow_small_talk=small_talk)
            except UnknownRoute as exc:
                status, body = 404, {"error": "not_found", "message": str(exc)}
            except AccessError as exc:
                status, body = _access_status(exc), exc.as_dict()
            except ValueError as exc:
                status, body = 400, {"error": "bad_request", "message": str(exc)}
            encoded = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, fmt: str, *args: Any) -> None:
            return None

    return Handler


def _dispatch(entry: Entry, path: str, secret: str, payload: dict[str, Any], *, evidence_mode=None, require_strict=False, allow_small_talk=True) -> tuple[int, dict[str, Any]]:
    if path == "/v1/ask":
        message = str(payload.get("message") or "")
        if not message:
            raise ValueError("a message is required")
        kwargs = {key: payload[key] for key in _ASK_FIELDS if key in payload}
        if evidence_mode is not None and evidence_mode not in ('strict', 'standard'):
            raise ValueError('X-CPU-LLM-Evidence-Mode must be strict or standard')
        if 'strict_evidence' in kwargs and type(kwargs['strict_evidence']) is not bool:
            raise ValueError('strict_evidence must be a boolean')
        if 'small_talk' in kwargs and type(kwargs['small_talk']) is not bool:
            raise ValueError('small_talk must be a boolean')
        if not allow_small_talk:
            kwargs['small_talk'] = False
        if require_strict or evidence_mode == 'strict':
            kwargs['strict_evidence'] = True
        return 200, entry.ask(secret, message, **kwargs)
    if path == "/v1/ingest":
        return 200, entry.ingest(secret, _source(payload))
    if path == "/v1/delete":
        source = str(payload.get("source") or "")
        if not source:
            raise ValueError("a source is required")
        return 200, entry.delete_source(secret, source)
    if path == "/v1/correct":
        if "timestamp" not in payload:
            raise ValueError("a timestamp is required")
        return 200, entry.correct(
            secret,
            str(payload.get("document_id") or ""),
            str(payload.get("prior_sentence") or ""),
            str(payload.get("new_sentence") or ""),
            actor_id=str(payload.get("actor_id") or ""),
            timestamp=int(payload["timestamp"]),
        )
    raise UnknownRoute("that path is not served")


def cached_appliance(
    cache: dict[str, Any],
    lock: threading.Lock,
    tenant: str,
    factory: Callable[[str], Any],
) -> Any:
    """Build one appliance per tenant. A duplicate build is closed."""
    found = cache.get(tenant)
    if found is not None:
        return found
    with lock:
        found = cache.get(tenant)
        if found is not None:
            return found
        created = factory(tenant)
        current = cache.get(tenant)
        if current is not None:
            close = getattr(created, "close", None)
            if close is not None:
                close()
            return current
        cache[tenant] = created
        return created


def _source(payload: dict[str, Any]) -> Any:
    paragraphs = payload.get("paragraphs")
    if isinstance(paragraphs, list):
        name = str(payload.get("name") or "")
        if not name:
            raise ValueError("a document name is required")
        return SourceDocument(name, tuple(str(item) for item in paragraphs))
    source = payload.get("source")
    if isinstance(source, str) and source:
        return source
    raise ValueError("a source path or a document body is required")


def _json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    raw = handler.rfile.read(length) if length else b""
    try:
        loaded = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("the request body is not JSON") from exc
    if not isinstance(loaded, dict):
        raise ValueError("the request body must be an object")
    return loaded


def _bearer(header: str | None) -> str:
    text = header or ""
    prefix = "bearer "
    if text.lower().startswith(prefix):
        return text[len(prefix) :].strip()
    raise AuthenticationError("the credential was not accepted")


def _access_status(exc: AccessError) -> int:
    if isinstance(exc, AuthenticationError):
        return 401
    if isinstance(exc, StorageError):
        return 503
    if isinstance(exc, SourceForbidden):
        return 403
    return 403
