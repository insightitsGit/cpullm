"""Exact document-id boundaries for one ingested source.

A source prefix such as ``hr-p`` matches ``hr-p0001`` and a correction id
``hr-p0001-v<timestamp>``. It does not match ``hr-policy-p0001``.
"""

from __future__ import annotations

import re

_PREFIX = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*-p\Z")
_PARAGRAPH = re.compile(r"(.+-p)[0-9]{4}(?:-v[0-9]+)?\Z")


def is_source_prefix(value: str) -> bool:
    """True when ``value`` is an ingest prefix ending in ``-p``."""
    return bool(_PREFIX.fullmatch(str(value)))


def is_paragraph_id(value: str) -> bool:
    """True when ``value`` is one paragraph id, including a correction version."""
    return bool(_PARAGRAPH.fullmatch(str(value)))


def prefix_of(document_id: str) -> str:
    """The source prefix of one paragraph id."""
    matched = _PARAGRAPH.fullmatch(str(document_id))
    if matched is None:
        raise ValueError("a paragraph id is required")
    return matched.group(1)


def id_in_prefix(document_id: str, prefix: str) -> bool:
    """True when ``document_id`` is a paragraph of ``prefix`` and nothing longer."""
    if not is_source_prefix(prefix):
        return False
    return bool(re.fullmatch(re.escape(str(prefix)) + r"[0-9]{4}(?:-v[0-9]+)?", str(document_id)))


def matches_prefix(document_id: str, prefix: str) -> bool:
    """Source prefixes use the paragraph boundary. Other prefixes stay a leading match.

    Catalog probes and correction-version stems are not source prefixes. They
    keep the previous leading match so those maintenance deletes still find
    their rows.
    """
    if is_source_prefix(prefix):
        return id_in_prefix(document_id, prefix)
    return str(document_id).startswith(str(prefix))


def postgres_id_pattern(prefix: str) -> str:
    """PostgreSQL regular expression for every paragraph of ``prefix``."""
    if not is_source_prefix(prefix):
        raise ValueError("source prefix must look like a document id prefix ending in -p")
    return "^" + str(prefix) + "[0-9]{4}(-v[0-9]+)?$"
