"""A credential check in front of ingest, ask, correct, and delete_source.

The check runs before typo correction and before the query is encoded. The
secret file stores SHA-256 digests, not the secrets:

```json
{"credentials":[{"id":"alice","secret_sha256":"<hex>","tenant_id":"tenant_alpha","caller_id":"alice","allowed_sources":["alpha-p"]}]}
```

``secret_sha256`` is the hex digest from ``secret_sha256(secret)``. A file
that contains the secret itself is refused. The presented secret is hashed
and compared with ``hmac.compare_digest``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cpu_llm.access import AuthenticationError, CallerContext, SourceForbidden, source_allowed
from cpu_llm.pipeline import _namespace_slug
from cpu_llm.source_delete import source_prefix


class Entry:
    def __init__(self, secrets_path: str | Path, appliance_for: Callable[[str], Any]) -> None:
        self._rows = _load(Path(secrets_path))
        self._appliance_for = appliance_for

    def authenticate(self, secret: str) -> CallerContext:
        presented = _digest(secret or "")
        matched: dict[str, Any] | None = None
        for row in self._rows:
            if hmac.compare_digest(presented, _stored_digest(row)):
                matched = row
                break
        if matched is None:
            raise AuthenticationError("the credential was not accepted")
        try:
            tenant = _namespace_slug(str(matched.get("tenant_id") or ""))
        except ValueError as exc:
            raise AuthenticationError("the credential was not accepted") from exc
        sources = matched.get("allowed_sources") or []
        if not isinstance(sources, list):
            raise AuthenticationError("the credential was not accepted")
        return CallerContext.make(
            tenant,
            str(matched.get("caller_id") or matched.get("id") or ""),
            sources,
        )

    def ask(self, secret: str, message: str, **kwargs: Any) -> dict[str, Any]:
        context = self.authenticate(secret)
        return self._appliance_for(context.tenant_id).ask(message, caller=context, **kwargs)

    def ingest(self, secret: str, source: Any) -> dict[str, Any]:
        context = self.authenticate(secret)
        prefix = source_prefix(source if isinstance(source, str) else getattr(source, "name", ""))
        _require_source(context, prefix)
        return self._appliance_for(context.tenant_id).ingest(source)

    def correct(self, secret: str, document_id: str, prior_sentence: str, new_sentence: str, **kwargs: Any) -> dict[str, Any]:
        context = self.authenticate(secret)
        _require_source(context, source_prefix(document_id))
        return self._appliance_for(context.tenant_id).correct(
            document_id,
            prior_sentence,
            new_sentence,
            caller=context,
            **kwargs,
        )

    def delete_source(self, secret: str, source: str) -> dict[str, Any]:
        context = self.authenticate(secret)
        _require_source(context, source_prefix(source))
        return self._appliance_for(context.tenant_id).delete_source(source)


def _require_source(context: CallerContext, prefix: str) -> None:
    if not source_allowed(prefix, context.allowed_sources):
        raise SourceForbidden("that source is outside this caller's scope")


def secret_sha256(secret: str) -> str:
    """Hex SHA-256 digest to store in the credential file."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _digest(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


def _stored_digest(row: dict[str, Any]) -> bytes:
    if "secret" in row:
        raise AuthenticationError("the credential file must store secret_sha256, not the secret")
    text = str(row.get("secret_sha256") or "")
    try:
        digest = bytes.fromhex(text)
    except ValueError as exc:
        raise AuthenticationError("the credential was not accepted") from exc
    if len(digest) != hashlib.sha256().digest_size:
        raise AuthenticationError("the credential was not accepted")
    return digest


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise AuthenticationError("the credential file is missing")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    rows = loaded.get("credentials") if isinstance(loaded, dict) else None
    if not isinstance(rows, list) or not rows:
        raise AuthenticationError("the credential file has no credentials")
    kept = [row for row in rows if isinstance(row, dict)]
    for row in kept:
        _stored_digest(row)
    return kept
