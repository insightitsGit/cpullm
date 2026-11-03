"""Fail-closed literal evidence lookup, independent of generative nodes.

This verifies quotation and provenance, never the clinical truth of a source.
"""
from __future__ import annotations

import re

_CONTROL = re.compile(r"\A\s*\[strict-evidence\][ \t]*(?:\r?\n|$)", re.I)


def requested(message: str, enabled: bool) -> tuple[bool, str]:
    if type(enabled) is not bool:
        raise ValueError("strict_evidence must be a boolean")
    match = _CONTROL.match(message)
    return enabled or match is not None, message[match.end():] if match else message


def answer(appliance, message, *, caller=None, as_of=None):
    from cpu_llm.strict_evidence_engine import answer as execute
    return execute(appliance, message, caller=caller, as_of=as_of)
