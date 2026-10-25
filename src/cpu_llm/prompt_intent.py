"""Prompt -> six independent channel intents -> source-backed sentence selection.

Rules describe recognized intent; vector prototype similarities are soft
signals from enabled heads, not proof that an intention or fact is true.
"""
from __future__ import annotations

import re
import numpy as np
from cpu_llm.connection_channels import CHANNEL_SLICES, channel_similarity

PROTOTYPE_TEXTS = {
    'dense': 'Find passages relevant to this subject.',
    'relational': 'Which relationship or attribute connects these entities?',
    'disentangled': 'What distinguishes these subjects and their attributes?',
    'hyperbolic': 'What kind or category does this entity belong to?',
    'identity': 'Who or what is this entity also known as?',
    'causal': 'What causes this effect and why does it happen?',
}


def _name(text):
    text = ' '.join(text.casefold().strip(' .?!').split())
    return re.sub(r'^(?:the|an|a)\s+', '', text)


def _requested(message):
    patterns = [
        ('has_lifespan', 'subject', r'how long (?:does|do|can) (?P<entity>.+?) live'),
        ('has_lifespan', 'subject', r'how many years (?:does|do|can) (?P<entity>.+?) live'),
        ('has_lifespan', 'subject', r'what is the (?:lifespan|longevity) of (?P<entity>.+)'),
        ('is_a', 'subject', r'what (?:kind|type|sort)(?: of [\w -]+?)? (?:is|are) (?P<entity>.+)'),
        ('has_color', 'subject', r'what colou?r (?:is|are) (?P<entity>.+)'),
        ('lives_in', 'subject', r'where (?:does|do) (?P<entity>.+?) (?:live|reside)'),
        ('has', 'subject', r'what (?:does|do) (?P<entity>.+?) have'),
        ('causes', 'object', r'what causes (?P<entity>.+)'),
        ('causes', 'subject', r'what (?:does|do) (?P<entity>.+?) cause'),
        ('causes', 'object', r'why (?:does|do|did) (?P<entity>.+)'),
    ]
    text = ' '.join(message.strip().rstrip('?.!').split())
    for relation, direction, pattern in patterns:
        match = re.fullmatch(pattern, text, re.I)
        if match and not re.search(r"\b(?:not|never|if)\b|n't", match['entity'], re.I):
            return dict(relation=relation, direction=direction, entity=_name(match['entity']))
    return None


def route_prompt(message, *, query_tensor=None, enabled_channels=None, prototypes=None, causal_matrix=None):
    """Evaluate every channel; retain evidence and vector availability separately."""
    from cpu_llm.query_dictionary import interpret_prompt
    dictionary = interpret_prompt(message)
    interpreted = dictionary['canonical']
    text = ' '.join(interpreted.lower().split())
    request = _requested(interpreted)
    cues = {
        'dense': bool(text.strip()),
        'relational': request is not None or bool(re.search(r'\b(?:whose|where|attribute|relationship|has|have)\b', text)),
        'disentangled': bool(re.search(r'\b(?:compare|difference|different|distinguish|versus)\b', text)),
        'hyperbolic': bool(re.search(r'\b(?:kind|type|category|taxonomy|class|belongs? to)\b', text)),
        'identity': bool(re.match(r'(?:who|what) (?:is|are)\b', text) or re.search(r'\b(?:name|known as|identity)\b', text)),
        'causal': bool(re.search(r'\b(?:why|causes?|because|effect|reason)\b', text)),
    }
    if request and request['relation'] == 'is_a':
        cues['hyperbolic'] = True
    flags = enabled_channels or {}
    query = np.asarray(query_tensor).reshape(-1) if query_tensor is not None else None
    channels = {}
    for name, region in CHANNEL_SLICES.items():
        score = None
        prototype = (prototypes or {}).get(name)
        if flags.get(name) and query is not None and query.shape == (1024,) and prototype is not None:
            proto = np.asarray(prototype).reshape(-1)
            if proto.shape == (1024,):
                a, b = query[region.start:region.end], proto[region.start:region.end]
                if np.isfinite(a).all() and np.isfinite(b).all():
                    score = channel_similarity(name, query, proto, causal_matrix)
                    if score is not None and not np.isfinite(score):
                        score = None
        soft = max(0., score or 0.) if name in {'dense', 'disentangled'} else float(np.exp(min(0., score))) if score is not None else 0.
        channels[name] = dict(active=cues[name], rule_supported=cues[name], head_enabled=bool(flags.get(name)),
                              prototype_score=score, weight=float(cues[name]) + soft * 0.25,
                              basis='recognized prompt form' if cues[name] else 'no explicit prompt cue')
    return dict(schema='prompt-intent-v1', channels=channels, requested=request, dictionary=dictionary,
                vector_scope='enabled-head prototype scores are uncalibrated soft routing signals')


def _entity_key(text):
    words = _name(text).split()
    if words and words[-1].endswith('s') and not words[-1].endswith('ss'):
        words[-1] = words[-1][:-1]
    return ' '.join(words)


def _equivalent(left, right):
    return _entity_key(left) == _entity_key(right)


def _alias_paths(entity, facts, *, max_hops=2):
    """Explicit identity paths, bounded independently of source row order."""
    paths = {_entity_key(entity): []}
    for _ in range(max_hops):
        previous = dict(paths)
        for fact in facts:
            if fact.relation != 'alias_of' or 'identity' not in fact.channels:
                continue
            left, right = _entity_key(fact.subject), _entity_key(fact.object)
            for origin, target in ((left, right), (right, left)):
                if origin in previous and target not in paths:
                    paths[target] = previous[origin] + [fact]
        if len(paths) == len(previous):
            break
    return paths


def select_channel_answer(message, chunks, *, intent=None):
    """Only a matching entity, direction, relation AND channel can answer."""
    from cpu_llm.knowledge_graph import extract_facts
    intent = intent or route_prompt(message)
    request = intent['requested']
    if request is None:
        return None
    facts = []
    for index, row in enumerate(chunks):
        if isinstance(row, str):
            document_id, text = f'chunk-{index}', row
        else:
            document_id = str(row.get('document_id') or row.get('chunk_id') or f'chunk-{index}')
            text = str(row.get('text') or row.get('chunk_text') or '')
        facts.extend(extract_facts(document_id, text))
    # Alias equivalence only; shared taxonomy is not identity. Preserve the
    # identity premises used to bind the question to the source's name.
    aliases = _alias_paths(request['entity'], facts)
    names = set(aliases)
    channel = {'is_a': 'hyperbolic', 'causes': 'causal'}.get(request['relation'], 'relational')
    def matches(name, value):
        if request['relation'] == 'causes' and request['direction'] == 'object':
            # Match the complete effect, allowing simple verb agreement.
            def words(text):
                return [word[:-1] if word.endswith('s') and not word.endswith('ss') else word for word in _name(text).split()]
            return words(name) == words(value)
        return _equivalent(name, value)
    selected = [fact for fact in facts if fact.relation == request['relation'] and channel in fact.channels
                and any(matches(name, getattr(fact, request['direction'])) for name in names)]
    alias_evidence = [edge for fact in selected for name in names
                      if matches(name, getattr(fact, request['direction'])) for edge in aliases[name]]
    joins = []
    if request['relation'] in {'has_lifespan', 'has_color', 'lives_in', 'has'}:
        memberships = [fact for fact in facts if fact.relation == 'is_a'
                       and any(_equivalent(name, fact.subject) for name in names)]
        for membership in memberships:
            types = _alias_paths(membership.object, facts)
            for fact in facts:
                universal = re.fullmatch(r'(?:all|every)\s+(.+)', fact.subject, re.I)
                if (fact.relation == request['relation'] and channel in fact.channels
                        and universal and _entity_key(universal[1]) in types):
                    selected.append(fact)
                    joins.append(membership)
                    joins.extend(types[_entity_key(universal[1])])
                    alias_evidence.extend(aliases[_entity_key(membership.subject)])
    if request['relation'] == 'is_a' and selected:
        # Prefer an explicit taxonomic definition over descriptions such as
        # "is a highly esteemed food" elsewhere in the same article.
        selected = sorted(selected, key=lambda fact: 'is a species of' not in fact.sentence.casefold())[:1]
    base = dict(query=message, kind='channel', prompt_intent=intent, retrieved_candidates=[
        dict(document_id=f.document_id, span=f.sentence) for f in facts], answer_evidence=[], verification_scope='query')
    if not selected:
        return dict(base, answer_status='insufficient_evidence', reason='no_matching_channel_relation',
                    text='The retrieved passages do not settle that.')
    values = {_name(f.object) for f in selected}
    evidence = list({(f.document_id, f.sentence): dict(document_id=f.document_id, span=f.sentence)
                     for f in joins + selected}.values())
    base['supporting_evidence'] = list({(f.document_id, f.sentence): dict(document_id=f.document_id, span=f.sentence)
                                       for f in alias_evidence}.values())
    if request['relation'] in {'has_color', 'has_lifespan'} and len(values) > 1:
        return dict(base, answer_status='conflicting', reason='conflicting_channel_values', answer_evidence=evidence,
                    text='The retrieved passages do not settle that. Stored sentences conflict: ' + ' '.join(f.sentence for f in selected))
    return dict(base, answer_status='answered', reason='universal_membership_join' if joins else 'channel_relation_stated', answer_evidence=evidence,
                text=' '.join(dict.fromkeys(f.sentence for f in joins + selected)))


def rank_channel_hits(hits, intent):
    """Prioritize requested relationships, preserving dense order for equal matches."""
    request = intent.get('requested')
    context = [dict(text=str(hit.get('chunk_text') or ''), document_id=str(hit.get('document_id') or '')) for hit in hits]
    selected = select_channel_answer('', context, intent=intent) if request else None
    answer_ids = {item['document_id'] for item in selected.get('answer_evidence', [])} if selected else set()
    def score(hit):
        edges = hit.get('graph_evidence') or []
        # A shared channel alone cannot outrank evidence answering the query.
        exact = hit.get('document_id') in answer_ids
        weight = sum(intent['channels'][name]['weight'] for edge in edges for name in edge.get('channels', [])
                     if name in intent['channels'])
        return (exact, weight)
    return sorted(hits, key=score, reverse=True)
