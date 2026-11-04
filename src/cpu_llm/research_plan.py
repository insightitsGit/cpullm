"""Bounded research questions are instructions, never knowledge-base facts."""
from __future__ import annotations

import hashlib
import json
import re

SCHEMA = 'research-plan-v1'
MAX_QUESTIONS = 16
FACETS = {
    'definition': ('What is documented about {topic}?', None),
    'properties': ('What properties and capabilities of {topic} are documented?', None),
    'relationships': ('Which relationships involving {topic} are explicitly documented?', None),
    'mechanism': ('How does the documented process involving {topic} work?', 'relationships'),
    'cause': ('Is an explicit reason or cause involving {topic} documented?', 'relationships'),
    'limitations': ('What conditions, exceptions or limitations apply to {topic}?', None),
    'validation': ('What checks or validation of {topic} are documented?', None),
}
VOCABULARY = {
    'genre': ('design document', 'specification', 'article', 'report', 'document', 'draft',
              'email', 'letter', 'memo', 'proposal', 'briefing', 'summary', 'overview'),
    'depth': ('in-depth', 'comprehensive', 'detailed', 'thorough', 'brief', 'concise', 'short'),
    'research': ('what', 'who', 'when', 'where', 'how', 'why', 'explain', 'investigate', 'describe'),
    'connection': ('related to', 'connected to', 'depends on', 'belongs to', 'member of',
                   'type of', 'uses', 'requires', 'affects', 'causes'),
    'comparison': ('compare', 'versus', 'differences', 'similarities', 'advantages', 'disadvantages'),
    'layout': ('executive summary', 'numbered list', 'table', 'bullets', 'sections', 'steps',
               'citations', 'references', 'markdown', 'html'),
    'audience_tone': ('technical', 'executive', 'beginner', 'formal', 'neutral', 'friendly'),
    'constraint': ('must not', 'source-only', 'as of', 'only', 'exclude', 'without', 'before',
                   'after', 'within', 'must', 'except', 'unless', 'if', 'not', 'never'),
}


def _masked(text):
    return re.sub(r'```[\s\S]*?```|"[^"\n]*"|“[^”\n]*”',
                  lambda m: ' ' * len(m[0]), text)


def build_research_plan(message, document_plan, *, strict=False):
    """Compile a recognized deliverable; templates do not infer facts or criteria."""
    topic = document_plan['topic']
    masked = _masked(message)
    controls = []
    for group, words in VOCABULARY.items():
        for word in words:
            for m in re.finditer(r'(?<!\w)' + re.escape(word) + r'(?!\w)', masked, re.I):
                controls.append(dict(group=group, value=m[0], start=m.start(), end=m.end(),
                                     origin='explicit_prompt', interpreted=False))
    controls.sort(key=lambda c: (c['start'], c['end'], c['group']))
    facets = ['definition', 'properties', 'relationships', 'mechanism', 'limitations']
    if document_plan['genre'] == 'design':
        facets.append('validation')
    # Causes are investigated only when explicitly requested, not for every article.
    if re.search(r'\b(?:why|causes?|reasons?)\b', masked, re.I):
        facets.append('cause')
    if strict:
        facets = ['definition', 'properties', 'limitations']
    excluded = set()
    for words, facet in [('why|cause|causes|reason|reasons', 'cause'),
                         ('how|mechanism|mechanisms', 'mechanism'),
                         ('relationship|relationships|connections', 'relationships')]:
        if re.search(r'\b(?:do not|don\x27t|never|without|exclude)\s+(?:(?:explain|discuss|include)\s+)?(?:' + words + r')\b', masked, re.I):
            excluded.add(facet)
    facets = [f for f in facets if f not in excluded]
    facets = [f for f in facets if FACETS[f][1] is None or FACETS[f][1] in facets]
    questions = [dict(id=f'q{i+1}', facet=f, text=FACETS[f][0].format(topic=topic),
                      origin='template_suggestion', required=False,
                      prerequisites=[FACETS[f][1]] if FACETS[f][1] else [],
                      status='pending', evidence_ids=[]) for i, f in enumerate(facets[:MAX_QUESTIONS])]
    clarifications = []
    if re.fullmatch(r'(?:it|this|that|them|this document|that document)', topic, re.I):
        clarifications.append('Which named subject or document should this request cover?')
    if re.search(r'\bbest\b', topic, re.I):
        clarifications.append('What criteria should determine best?')
    expanded = (f"Prepare a {document_plan['detail']} {document_plan['genre']} about {topic}. "
                'Preserve the original scope and constraints. Investigate these questions without '
                'assuming their premises are true:\n' + '\n'.join(q['text'] for q in questions) +
                '\nUse only supported evidence; retain conflicts and missing information. '
                'Do not infer causes or new transitive facts. Do not send a draft.')
    plan = dict(schema=SCHEMA, original_prompt=message, topic=topic,
                genre=document_plan['genre'], requirements=controls, questions=questions,
                recipient=document_plan.get('recipient'), sending_authorized=False,
                expanded_prompt=expanded, clarifications=clarifications,
                status='needs_clarification' if clarifications else 'planned',
                strict=strict, max_questions=MAX_QUESTIONS,
                retrieval_strategy='one_bounded_authorized_snapshot',
                semantic_interpretation='curated_templates; unknown constraints retained in original_prompt')
    plan['plan_hash'] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    return plan


def select_research_rows(plan, rows):
    """Select independently named topics without requiring every word in one chunk.

    Original rows remain atomic. Relations do not license transitive conclusions.
    A compound title is split only on an explicit conjunction between named sides.
    """
    topics = re.split(r'\s+and\s+', plan['topic'], flags=re.I)
    tokens = [set(re.findall(r'\w+', t.casefold())) - {'the', 'a', 'an', 'of'} for t in topics]
    selected = [r for r in rows if any(t and t.issubset(set(re.findall(r'\w+', r['chunk_text'].casefold()))) for t in tokens)]
    # Follow a single layer of explicit source relations for additional research
    # evidence. This does not transfer class properties to an individual.
    from cpu_llm.knowledge_graph import extract_facts
    anchors = set()
    for row in selected:
        for fact in extract_facts(row['document_id'], row['chunk_text']):
            subject = set(re.findall(r'\w+', fact.subject.casefold())) - {'the', 'a', 'an', 'of'}
            if any(t and t == subject for t in tokens):
                anchors.add(fact.object)
            if len(anchors) >= 32:
                break
        if len(anchors) >= 32:
            break
    anchors = sorted(anchors)[:32]
    known_ids = {r['document_id'] for r in selected}
    for row in rows:
        if row['document_id'] in known_ids:
            continue
        if any(re.search(r'(?<!\w)' + re.escape(a) + r'(?!\w)', row['chunk_text'], re.I) for a in anchors):
            selected.append(row); known_ids.add(row['document_id'])
    plan['research_leads'] = dict(labels=anchors, hop_limit=1,
                                  basis='explicit source relations; not inferred facts')
    # Coverage is candidate evidence availability, not a verified answer to a question.
    patterns = {'definition': r'\bis (?:a|an)\b', 'properties': r'.',
                'relationships': r'\b(?:uses|has|requires|depends on|is a|causes)\b',
                'mechanism': r'\b(?:by|through|using|process|steps)\b',
                'cause': r'\b(?:because|causes|due to)\b',
                'limitations': r'\b(?:not|never|cannot|unless|except|only|if|limit)\b',
                'validation': r'\b(?:test|verify|validate|checksum)\w*\b'}
    for q in plan['questions']:
        ids = [r['document_id'] for r in selected if re.search(patterns[q['facet']], r['chunk_text'], re.I)]
        q.update(status='candidate_evidence' if ids else 'missing', evidence_ids=ids)
        if q['prerequisites'] and not any(other['facet'] in q['prerequisites'] and other['evidence_ids'] for other in plan['questions']):
            q.update(status='prerequisite_missing', evidence_ids=[])
    plan['coverage'] = dict(selected_chunks=len(selected), question_answers_verified=False,
                            missing_facets=[q['facet'] for q in plan['questions'] if not q['evidence_ids']])
    return selected
