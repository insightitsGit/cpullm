"""Run the finance checks on a turn.

The node does not write a proposition. The reply speaks the check when the
question asked for nothing else.
"""

from __future__ import annotations

from typing import Any

from cpu_llm.finance import validate_message
from cpu_llm.finance.triggers import CALLER_REASON


def run_finance(message: str, *, reasons: list[str] | None = None) -> dict[str, Any]:
    forced = CALLER_REASON in (reasons or [])
    return validate_message(message, forced=forced)
