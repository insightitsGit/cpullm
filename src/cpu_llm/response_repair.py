"""Post-retrieval evidence gaps and explicit, source-grounded reinterpretation.

Never change a factual target silently. Alternatives are supported question
forms evaluated against the same permitted retrieval, not imagined facts.
"""
from cpu_llm.answerability import assess, parse_query
from cpu_llm.prompt_intent import route_prompt


def inspect_gap(message, result, *, confirmed=False):
    judgment = result.get('judgment') or {}
    if judgment.get('outcome') != 'insufficient_evidence':
        return None
    if (result.get('delivery_blocked') or result.get('shine_ok') is False or result.get('shine_enforced')
            or result.get('__partial__') or result.get('__node_error__')
            or result.get('guard_decision') not in (None, 'allow')):
        return None
    if any(result.get(flag) for flag in ('draft', 'math', 'finance', 'creative', 'summarize', 'list', 'explain')):
        return None
    parsed = parse_query(message) or {}
    requested = (route_prompt(message).get('requested') or {})
    entity = requested.get('entity') or parsed.get('subject') or parsed.get('entity')
    if not entity:
        return None
    rows = []
    seen = set()
    for row in list(result.get('passages') or []) + list(result.get('related') or []):
        text = row.get('chunk_text') or row.get('text') or ''
        key = (row.get('document_id') or row.get('chunk_id'), text)
        if not text or key in seen:
            continue
        seen.add(key)
        rows.append(dict(document_id=key[0] or f'passage-{len(rows)}', text=text))
    options = []
    templates = [
        ('identity', f'Who is {entity}?'),
        ('activity', f'What did {entity} do?'),
        ('current activity', f'What does {entity} do?'),
        ('location', f'Where does {entity} live?'),
        ('color', f'What color is {entity}?'),
        ('possessions', f'What does {entity} have?'),
        ('lifespan', f'How long does {entity} live?'),
    ]
    for label, query in templates:
        decision = assess(query, rows)
        if decision and decision['answer_status'] in {'answered', 'evidence_quote'}:
            options.append(dict(label=label, query=query))
    broad_definition = parsed.get('kind') == 'definition' and message.strip().casefold().startswith('what ')
    ask = broad_definition and not confirmed and bool(options)
    if ask:
        # Identity is a possible intended question, not a fact inferred from an action.
        options = [dict(label='identity', query=f'Who is {entity}?')] + [o for o in options if o['label'] != 'identity'][:3]
    return dict(schema='post-retrieval-gap-v1', requested_entity=entity,
                requested_relation=requested.get('relation') or parsed.get('kind'),
                reason='intent_confirmation' if ask else 'missing_evidence',
                ask=ask, confirmed=confirmed, options=options,
                evidence_role='retrieved alternatives do not establish the original answer')
