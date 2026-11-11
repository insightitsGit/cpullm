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
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from cpu_llm.access import AuthenticationError, CallerContext, SourceForbidden, require_admin, source_allowed
from cpu_llm.documents import SourceDocument, open_source, replace_prefix
from cpu_llm.pipeline import _namespace_slug
from cpu_llm.source_delete import source_prefix


class Entry:
    def __init__(
        self,
        secrets_path: str | Path,
        appliance_for: Callable[[str], Any],
        *,
        ingest_root: str | Path | None = None,
        audit_path: str | Path | None = None,
        audit_retention_days: int | None = None,
    ) -> None:
        self._secrets_path = Path(secrets_path).resolve()
        _load(self._secrets_path)
        if audit_retention_days is not None and audit_path is None:
            raise ValueError("Audit retention requires an audit path.")
        from cpu_llm.mutation_audit import MutationAudit

        self._audit = MutationAudit(audit_path, retention_days=audit_retention_days) if audit_path else None
        self._appliance_for = appliance_for
        self._ingest_root = None if ingest_root is None else Path(ingest_root).resolve()

    def authenticate(self, secret: str) -> CallerContext:
        presented = _digest(secret or "")
        matched: dict[str, Any] | None = None
        try:
            rows = _load(self._secrets_path)
        except (OSError, ValueError) as exc:
            raise AuthenticationError("the credential file could not be loaded") from exc
        for row in rows:
            if hmac.compare_digest(presented, _stored_digest(row)):
                matched = row
                break
        if matched is None or matched.get("revoked", False) is not False:
            raise AuthenticationError("the credential was not accepted")
        try:
            tenant = _namespace_slug(str(matched.get("tenant_id") or ""))
        except ValueError as exc:
            raise AuthenticationError("the credential was not accepted") from exc
        sources = matched.get("allowed_sources") or []
        role = matched.get("role", "reader")
        if not isinstance(sources, list) or role not in ("reader", "admin"):
            raise AuthenticationError("the credential was not accepted")
        return CallerContext.make(
            tenant,
            str(matched.get("caller_id") or matched.get("id") or ""),
            sources,
            role=role,
        )

    def ask(self, secret: str, message: str, **kwargs: Any) -> dict[str, Any]:
        context = self.authenticate(secret)
        return self._appliance_for(context.tenant_id).ask(message, caller=context, **kwargs)

    def ingest(self, secret: str, source: Any) -> dict[str, Any]:
        context = self.authenticate(secret)
        documents = self._documents_for_ingest(source)
        for document in documents:
            _require_source(context, replace_prefix(document))
        return self._mutate(context, "ingest", [replace_prefix(document) for document in documents],
                            lambda: self._appliance_for(context.tenant_id).ingest(documents))

    def _mutate(self, context, operation, targets, action):
        if self._audit is None:
            return action()
        with self._audit.record(context, operation, targets) as receipt:
            result = action()
            if isinstance(result, dict):
                receipt["status"] = result.get("status")
            return result

    def _documents_for_ingest(self, source: Any) -> list[SourceDocument]:
        if isinstance(source, (str, Path)):
            return open_source(Path(source), path_check=self._confine)
        if isinstance(source, SourceDocument):
            return open_source(source)
        if isinstance(source, Iterable) and not isinstance(source, (bytes, bytearray)):
            documents: list[SourceDocument] = []
            for item in source:
                documents.extend(self._documents_for_ingest(item))
            if not documents:
                raise ValueError("the source has no paragraphs")
            return documents
        return open_source(source)

    def _confine(self, path: Path) -> Path:
        """Resolve a server path and keep it inside the configured ingest root."""
        if self._ingest_root is None:
            raise SourceForbidden("path ingest is not enabled on this service")
        resolved = path.resolve()
        if not resolved.is_relative_to(self._ingest_root):
            raise SourceForbidden("that path is outside the ingest root")
        return resolved

    def correct(self, secret: str, document_id: str, prior_sentence: str, new_sentence: str, **kwargs: Any) -> dict[str, Any]:
        context = self.authenticate(secret)
        _require_source(context, source_prefix(document_id))
        return self._mutate(context, "correct", [document_id], lambda: self._appliance_for(context.tenant_id).correct(
            document_id,
            prior_sentence,
            new_sentence,
            caller=context,
            **kwargs,
        ))

    def chunk_inventory(self, secret: str, source=None, *, limit=50, offset=0):
        context = self.authenticate(secret)
        return self._appliance_for(context.tenant_id).chunk_inventory(
            source, limit=limit, offset=offset, caller=context)

    def delete_chunk(self, secret: str, document_id: str, confirmation: str | None = None) -> dict[str, Any]:
        context = self.authenticate(secret)
        require_admin(context)
        _require_source(context, document_id)
        action = lambda: self._appliance_for(context.tenant_id).delete_chunk(
            document_id, confirmation=confirmation, caller=context)
        if confirmation is None:
            return action()
        return self._mutate(context, "delete_chunk", [document_id], action)

    def delete_source(self, secret: str, source: str) -> dict[str, Any]:
        context = self.authenticate(secret)
        require_admin(context)
        _require_source(context, source_prefix(source))
        return self._mutate(context, "delete_source", [source_prefix(source)],
                            lambda: self._appliance_for(context.tenant_id).delete_source(source))


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
