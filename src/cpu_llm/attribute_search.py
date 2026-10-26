"""One bounded retrieval repair round for a recognized missing attribute."""
from cpu_llm.access import keep_allowed
from cpu_llm.knowledge_graph import extract_facts
from cpu_llm.prompt_intent import _alias_paths, _equivalent, select_channel_answer

ATTRIBUTE_TERMS = {
    'has_lifespan': 'lifespan longevity age years lived',
    'lives_in': 'habitat geographic range location lives in',
    'has_color': 'color colour hue appearance',
    'has': 'parts features possessions has',
}


def retrieve_missing_attribute(index, message, hits, intent, *, allowed=None, as_of=None):
    request = intent.get('requested') or {}
    report = dict(status='not_applicable', queries=[], joins=[], budget=dict(max_queries=3, hits_per_query=5))
    if request.get('relation') not in ATTRIBUTE_TERMS:
        return hits, report
    if allowed is not None and not allowed:
        return [], dict(report, status='insufficient_evidence')
    hits = keep_allowed(hits, allowed)
    decision = select_channel_answer(message, hits, intent=intent)
    # A direct possession does not exhaust "what does it have": a membership
    # can still license an "every … has …" rule. A lifespan or a color is one
    # value, so a direct fact stays settled and does not search again.
    direct_possession = (
        request.get('relation') == 'has'
        and decision
        and decision['answer_status'] == 'answered'
        and decision.get('reason') != 'universal_membership_join'
    )
    if decision and decision['answer_status'] in {'answered', 'conflicting'} and not direct_possession:
        return hits, dict(report, status='already_settled')
    def connections(rows):
        facts = [fact for row in rows for fact in extract_facts(row['document_id'], row.get('chunk_text') or '')]
        names = _alias_paths(request['entity'], facts)
        return [fact for fact in facts if fact.relation == 'is_a' and any(_equivalent(name, fact.subject) for name in names)]
    memberships = connections(hits)
    terms = ATTRIBUTE_TERMS[request['relation']]
    queries = list(dict.fromkeys(f'{subject} {terms}' for subject in [request['entity']] + [fact.object for fact in memberships]))
    merged = list(hits)
    seen = {row['document_id'] for row in hits}
    executed = []
    while queries and len(executed) < 3:
        query = queries.pop(0)
        executed.append(query)
        tensor = index.encode_query(query)
        if allowed is None:
            rows = index.search(query, top_k=5, query_tensor=tensor, as_of=as_of)
        else:
            rows = index.search_allowed(query, set(allowed), top_k=5, query_tensor=tensor, as_of=as_of)
        for row in keep_allowed(rows, allowed):
            if row['document_id'] not in seen:
                merged.append(row)
                seen.add(row['document_id'])
        settled = select_channel_answer(message, merged, intent=intent)
        memberships = connections(merged)
        # A repair query can reveal a previously missing membership edge.
        # Re-plan within the same fixed budget; never start an unbounded loop.
        for membership in memberships:
            query = f'{membership.object} {terms}'
            if query not in executed and query not in queries:
                queries.append(query)
        if settled['answer_status'] not in {'answered', 'conflicting'}:
            continue
        if request.get('relation') == 'has' and settled.get('reason') != 'universal_membership_join':
            if any(f'{membership.object} {terms}' not in executed for membership in memberships):
                continue
        break
    decision = select_channel_answer(message, merged, intent=intent)
    return merged, dict(report, status=decision['answer_status'], queries=executed,
                        answer_reason=decision['reason'], answer_evidence=decision.get('answer_evidence', []),
                        supporting_evidence=decision.get('supporting_evidence', []),
                        joins=[dict(subject=f.subject, relation=f.relation, object=f.object,
                                    document_id=f.document_id, sentence=f.sentence) for f in memberships])
