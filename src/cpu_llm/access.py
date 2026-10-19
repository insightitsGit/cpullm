"""Who is asking, and which stored sources that caller may read.

An empty source set means this caller may read nothing. ``None`` means the
caller did not set a scope, which is the single-tenant appliance. A failed
credential or a schema that cannot be opened is a typed error. The message
does not include a traceback.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

_SOURCE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class AccessError(Exception):
    """A caller-facing refusal. ``as_dict`` is the body a caller may keep."""

    code = "access_error"

    def as_dict(self) -> dict[str, str]:
        return {"error": self.code, "message": str(self)}


class AuthenticationError(AccessError):
    code = "authentication_failed"


class TenantNotFoundError(AccessError):
    code = "tenant_not_found"


class StorageError(AccessError):
    code = "storage_unavailable"


class SourceForbidden(AccessError):
    code = "source_forbidden"


@dataclass(frozen=True)
class CallerContext:
    tenant_id: str
    caller_id: str
    allowed_sources: frozenset[str]
    request_id: str

    @staticmethod
    def make(
        tenant_id: str,
        caller_id: str,
        allowed_sources: frozenset[str] | set[str] | list[str],
        request_id: str | None = None,
    ) -> "CallerContext":
        sources = frozenset(str(item) for item in allowed_sources)
        for item in sources:
            if not _SOURCE.fullmatch(item):
                raise ValueError("an allowed source must be a document id or an id prefix")
        return CallerContext(
            tenant_id=tenant_id,
            caller_id=caller_id,
            allowed_sources=sources,
            request_id=request_id or uuid.uuid4().hex,
        )


def source_allowed(document_id: str, allowed: frozenset[str] | list[str] | None) -> bool:
    """True when ``document_id`` is inside the caller's source scope.

    ``None`` is the unscoped appliance. An empty scope allows nothing.
    """
    if allowed is None:
        return True
    text = str(document_id)
    for item in allowed:
        if text == item or text.startswith(item):
            return True
    return False


def keep_allowed(rows: list[dict], allowed: frozenset[str] | list[str] | None) -> list[dict]:
    """Drop rows whose document id is outside ``allowed``. ``None`` keeps every row."""
    if allowed is None:
        return list(rows)
    return [row for row in rows if source_allowed(str(row.get("document_id") or ""), allowed)]
