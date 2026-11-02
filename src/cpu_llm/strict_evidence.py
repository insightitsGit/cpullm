"""Fail-closed literal evidence lookup, independent of generative nodes.

This verifies quotation and provenance, never the clinical truth of a source.
"""
from __future__ import annotations

import re
import hashlib

_CONTROL = re.compile(r"\A\s*\[strict-evidence\][ \t]*(?:\r?\n|$)", re.I)
_QUESTION = re.compile(r"What is the ([a-z][a-z -]{0,60}) of ([A-Za-z0-9][A-Za-z0-9 -]{0,100})\?", re.I)


def requested(message: str, enabled: bool) -> tuple[bool, str]:
    if type(enabled) is not bool:
        raise ValueError("strict_evidence must be a boolean")
    match = _CONTROL.match(message)
    return enabled or match is not None, message[match.end():] if match else message


def answer(appliance, message, *, caller=None, as_of=None):
    from cpu_llm.pipeline import _caller_for
    from cpu_llm.access import source_allowed

    context = _caller_for(appliance, caller)
    allowed = None if context is None else context.allowed_sources
    result = dict(message=message, original_message=message, tenant_id=appliance.tenant_id,
                  request_id=None if context is None else context.request_id,
                  answer=None, answer_status="unsupported",
                  answer_evidence=[], audit_passed=False,
                  evidence_policy=dict(version="strict-evidence-v1", enabled=True,
                      allowed_sources=None if allowed is None else sorted(allowed),
                      learned_generation=False, clinical_validation=False,
                      source_truth_verified=False,
                      conflict_detection='exact-template values only',
                      disabled_nodes=['fact_bridge', 'realizer', 'stylistic', 'reference_resolution', 'specialists'],
                      stateless=True, scan_complete=False),
                  reply=dict(text="Strict evidence mode requires a single explicit question: What is the <attribute> of <named entity>?"))
    decision = appliance.guard.check(message)
    result['guard_decision'] = decision.decision
    if decision.decision != 'allow':
        result.update(answer_status='blocked', reply=dict(text='Request blocked.'))
        return result
    _, query = requested(message, True)
    match = _QUESTION.fullmatch(query.strip())
    # Never discard conditions or resolve pronouns by guessing.
    if not match or re.search(r'\b(?:it|this|that|they|them|if|when|unless|not|and|or)\b', query, re.I):
        return result
    attribute, entity = match.groups()
    pattern = re.compile(r'The ' + re.escape(attribute) + r' of ' + re.escape(entity) + r' is (.+?)[.!]?$', re.I)
    try:
        rows, when = appliance.index.strict_source_rows(allowed, as_of=as_of)
    except (ValueError, RuntimeError):
        result.update(answer_status='insufficient_evidence', reply=dict(text='Evidence scan unavailable or exceeds the strict scan limit; no answer selected.'))
        return result
    result['evidence_policy'].update(scan_complete=True, as_of=when, scanned_chunks=len(rows))
    values = set()
    for row in rows:
        if not source_allowed(row['document_id'], allowed):
            raise RuntimeError('strict source scope violation')
        # Whole chunks only: no partial sentence can remove a qualifier.
        text = row['chunk_text'].strip()
        fact = pattern.fullmatch(text)
        if not fact:
            continue
        value = fact[1]
        if re.search(r'(?<!\d)\.|\.(?!\d)|[!?\n]', value):
            continue
        values.add(value)
        start = row['chunk_text'].index(text)
        result['answer_evidence'].append(dict(document_id=row['document_id'], quote=text,
            start=start, end=start + len(text),
            chunk_sha256=hashlib.sha256(row['chunk_text'].encode('utf-8')).hexdigest()))
    if not values:
        result.update(answer_status='insufficient_evidence', reply=dict(text='No matching literal source fact found; no answer selected.'))
    elif len(values) > 1:
        result.update(answer_status='conflicting', reply=dict(text='Source evidence conflicts; no answer selected.'))
    else:
        result.update(answer_status='evidence_quote', reply=dict(text='Source quotations (not clinically validated):\n' + '\n'.join(
            f"[{proof['document_id']}] {proof['quote']}" for proof in result['answer_evidence'])))
    return result
