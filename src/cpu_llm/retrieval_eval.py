"""Hit-rate@5 and spoken attribution for a labelled retrieval set.

Hit-rate@5 is 1 when at least one relevant document id is among the five
retrieved ids. It is not set-overlap recall. Spoken attribution is 1 when the
spoken sentence was realized from a relevant document id. A spoken distractor
is a miss. This module records the commit, the machine, and the command. It
does not declare a pass threshold.
"""

from __future__ import annotations

from typing import Any


def measure(cases: list[dict[str, Any]], *, commit: str, machine: str, command: str) -> dict[str, Any]:
    """Score ``cases`` and return the record. An empty list scores nothing."""
    if not cases:
        return {
            "cases": 0,
            "hit_rate_at_5": None,
            "spoken_attribution": None,
            "commit": commit,
            "machine": machine,
            "command": command,
        }
    hits = 0
    attributed = 0
    for case in cases:
        relevant = {str(item) for item in case.get("relevant_ids") or []}
        retrieved = [str(item) for item in case.get("retrieved_ids") or []][:5]
        hits += int(bool(relevant & set(retrieved)))
        spoken = str(case.get("spoken_document_id") or "")
        attributed += int(bool(spoken) and spoken in relevant)
    count = len(cases)
    return {
        "cases": count,
        "hit_rate_at_5": hits / count,
        "spoken_attribution": attributed / count,
        "commit": commit,
        "machine": machine,
        "command": command,
    }
