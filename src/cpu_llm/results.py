"""Small helpers for reading ``Appliance.ask`` results without digging through nested dictionaries.

    from cpu_llm.results import require_complete, hypotheses, lead_status, shortlist

    reply = require_complete(app.ask("Frontier: barren plateaus.", frontier={"screen": True}))
    for item in shortlist(reply):                       # Frontier entries whose check is ``testable``
        print(item["text"], lead_status(item))

The raw dictionaries stay the contract; these functions only read them.
"""
from __future__ import annotations

UNUSABLE = ('unavailable', 'blocked')


class IncompleteResult(RuntimeError):
    """Raised by ``require_complete`` when a reply cannot be used as a complete answer."""

    def __init__(self, message, response):
        super().__init__(message)
        self.response = response


def _receipt(response):
    for key in ('frontier', 'deepen'):
        if isinstance(response.get(key), dict):
            return response[key]
    return None


def require_complete(response, *, allow_partial=False):
    """Return ``response``, or raise ``IncompleteResult`` when storage was unavailable, the request was blocked,
    or (unless ``allow_partial``) a budget stopped the work."""
    status = response.get('answer_status')
    if status in UNUSABLE:
        raise IncompleteResult(f'{status}: {response.get("reply", {}).get("text", "")}', response)
    receipt = _receipt(response) or {}
    if not allow_partial and (status == 'partial' or receipt.get('incomplete')):
        raise IncompleteResult(f'incomplete ({receipt.get("stop_reason") or status})', response)
    return response


def hypotheses(response):
    """Frontier entries of a reply (an empty list for other routes)."""
    return list((response.get('frontier') or {}).get('hypotheses') or [])


def lead_status(item_or_response):
    """The ``lead_status`` of a Frontier entry's check or of a Deepen reply; None when it was not checked."""
    if 'deepen' in item_or_response and isinstance(item_or_response['deepen'], dict):
        return item_or_response['deepen'].get('lead_status')
    if 'lead_status' in item_or_response:
        return item_or_response['lead_status']
    return (item_or_response.get('check') or {}).get('lead_status')


def shortlist(response, statuses=('testable',)):
    """Frontier entries whose Deepen check has one of ``statuses`` (unchecked entries are left out)."""
    return [item for item in hypotheses(response) if lead_status(item) in statuses]


def citations(item):
    """(document_id, quote) pairs of a Frontier entry or a Deepen link."""
    found = item.get('citations') or item.get('support') or []
    return [(c['document_id'], c['quote']) for c in found if 'document_id' in c and 'quote' in c]
