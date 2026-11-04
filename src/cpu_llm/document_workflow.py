"""Bounded document planning and quotation-only composition from scoped snapshots.

Section labels organize source records; they never assert inferred architecture.
No source text is executed or paraphrased. Coverage is structural, not source truth.
"""
from __future__ import annotations

import hashlib
import html
import re

SCHEMA = 'document-plan-v1'
MAX_DOCUMENT_UNITS = 500
MAX_DOCUMENT_WORDS = 20000
_REQUEST = re.compile(
    r'^(?:please\s+)?(?:(?:can|could|would) you\s+)?'
    r'(?:write|draft|compose|create|prepare|produce|give(?: me)?|provide(?: me)?)\s+'
    r'(?:an?\s+)?(?P<depth>detailed|comprehensive|thorough|full|long|brief|short|concise|in-depth)?\s*'
    r'(?P<genre>design document|design doc|report|article|overview|document|email|letter|memo|proposal|specification|briefing|summary)\s+'
    r'(?:about|on|of|for)\s+(?P<topic>.+?)[.!?]*$', re.I)
_SECTIONS = {
    'overview': ('Overview', 'Details', 'Limitations'),
    'report': ('Overview', 'Operations', 'Limitations'),
    'article': ('Overview', 'Details', 'Limitations'),
    'design': ('Overview', 'Requirements', 'Architecture', 'Interfaces', 'Operations', 'Limitations', 'Validation'),
}
_CUES = {
    'Mechanism': r'\b(?:by|through|using|process|steps)\b',
    'Relationships': r'\b(?:uses|has|requires|depends on|is a|causes)\b',
    'Reasons': r'\b(?:because|causes|due to)\b',
    'Requirements': r'\b(?:requires?|must|shall|approval|requirements?)\b',
    'Architecture': r'\b(?:database|postgresql|storage|components?|architecture|uses?|stores?)\b',
    'Interfaces': r'\b(?:api|endpoint|interface|protocol|http|request|response)\b',
    'Operations': r'\b(?:backup|restore|restoration|runs?|retains?|retention|operators?|audit|events?|deletion|failures?)\b',
    'Limitations': r'\b(?:not|never|cannot|unsupported|limits?|risks?|failover|unless|except)\b',
    'Validation': r'\b(?:verif\w*|validat\w*|tests?|checksums?|checks?)\b',
}
for _genre in ('document', 'email', 'letter', 'memo', 'proposal', 'specification', 'briefing', 'summary'):
    _SECTIONS[_genre] = ('Overview', 'Details', 'Limitations')


def plan_document(message):
    """Recognize explicit genres, not quoted titles or ordinary factual questions."""
    from cpu_llm.stylistic.profiles import extract_style_request
    message=extract_style_request(message)['query']
    from cpu_llm.output_rendering import extract_layout
    layout = extract_layout(message)
    text = layout['content_query'].strip()
    deep_requested=False
    deep_prefix=re.match(r'^(?:please\s+)?(?:do|run|perform|use)\s+(?:a\s+)?deep search\s+(?:and|to)\s+(.+)$',text,re.I)
    if deep_prefix:
        deep_requested=True;text=deep_prefix[1]
    deep_suffix=re.search(r'[.;]\s*(?:please\s+)?(?:use|run|perform)\s+(?:a\s+)?deep search[.!]*$',text,re.I)
    if deep_suffix:
        deep_requested=True;text=text[:deep_suffix.start()]
    page = 1
    snapshot_as_of = None
    stamp = re.search(r'\s*[,;]\s*as of\s+(\d{1,20})\s*[.!?]*$', text, re.I)
    if stamp:
        snapshot_as_of=int(stamp[1]); text=text[:stamp.start()]
    match = re.search(r'\s*[,;]\s*page\s+(\d{1,5})\s*[.!?]*$', text, re.I)
    if match:
        page = int(match[1]); text = text[:match.start()]
    # Explicit recipient is a draft presentation field, never authority to send.
    recipient = None
    email = re.match(r'^(.*?\b(?:email|letter))\s+to\s+([\w @.\'-]{1,100})\s+about\s+(.+)$', text, re.I)
    if email:
        recipient = email[2].strip()
        text = email[1] + ' about ' + email[3]
    match = _REQUEST.fullmatch(text)
    if not match:
        return None
    genre = match['genre'].lower()
    if genre == 'overview':
        if layout['format'] != 'report' and not (page>1 and snapshot_as_of is not None):
            return None
    if genre.startswith('design'): genre = 'design'
    topic = match['topic'].strip(' .!?')
    topic=re.sub(r'^the topic (?:of )?', '',topic,flags=re.I)
    topic=re.sub(r'\s+with (?:source citations|sources|citations)$','',topic,flags=re.I)
    requested_sections = None
    outline = re.search(r',\s*(?:covering|including|include)\s+(.+)$', topic, re.I)
    if outline:
        requested_sections=[s.strip().title() for s in re.split(r',|\band\b',outline[1],flags=re.I) if s.strip()]
        if len(requested_sections)>10 or any(len(s)>60 for s in requested_sections):return None
        topic=topic[:outline.start()].strip()
    # Attribute lists remain independently judged factual tasks.
    if re.match(r'(?:the )?(?:colou?r|habitat|shape|material|weight)\b', topic, re.I):
        return None
    limit = re.search(r'\s+in\s+(\d{1,5})\s+(sentences?|words?|items?|bullets?)\s*$', topic, re.I)
    limits = {}
    if limit:
        limits['words' if limit[2].lower().startswith('word') else 'units'] = int(limit[1])
        topic = topic[:limit.start()].strip()
    # Explicit empty/ambiguous multi-instruction scope must not become source facts.
    if not topic or len(topic) > 240 or re.search(r'[\n?;]|\b(?:and then|also write)\b', topic, re.I):
        return None
    depth = (match['depth'] or '').lower()
    brief = depth in {'brief', 'short', 'concise'}
    word_target = min(MAX_DOCUMENT_WORDS, max(1, limits.get('words',
        120 if brief else 1000 if depth else 400)))
    budget = min(MAX_DOCUMENT_UNITS, max(1, limits.get('units', MAX_DOCUMENT_UNITS)))
    if 'units' in limits: word_target = None
    return dict(schema=SCHEMA, genre=genre, topic=topic, sections=list(dict.fromkeys(['Overview', *(requested_sections or _SECTIONS[genre][1:])])),
        detail='brief' if depth in {'brief', 'short', 'concise'} else 'detailed', recipient=recipient,
        unit_budget=budget, word_target=word_target, requested_limits=limits, page=max(1, min(page, 10000)),
        format=layout['format'] or 'report', output_media=layout['output_media'],
        retrieval_budget=40, source_scan_limit=10000, text_scan_limit=8_000_000, snapshot_as_of=snapshot_as_of,
        composition='attributed_source_quotes', proposed_decisions=False, deep_requested=deep_requested)


def _words(text):
    return set(re.findall(r'[\w]+', text.casefold())) - {'the', 'a', 'an', 'of', 'and', 'for', 'about'}


def plan_long_overview(message):
    """Use attributed documents for long, whole-topic overviews as well as genres."""
    from cpu_llm.response_policy import classify_response_request
    response=classify_response_request(message)
    if response['mode']!='overview' or not response['flags']['long_response']:
        return None
    match=re.fullmatch(r'(?:tell me about|describe)\s+(.+?)[.!?]*',response['content_query'],re.I)
    if not match or re.search(r'[?;\n]',match[1]): return None
    plan=plan_document('Write a detailed article about '+match[1]+'.')
    if plan is None:return None
    plan.update(genre='overview', sections=list(_SECTIONS['overview']),
        unit_budget=MAX_DOCUMENT_UNITS,
        format=response['format'], output_media=response['output_media'])
    limits=response['requested_limits']
    if 'sentences' in limits:
        plan['unit_budget']=min(MAX_DOCUMENT_UNITS,max(1,limits['sentences']))
        plan['word_target']=None
    elif 'items' in limits:
        plan['unit_budget']=min(MAX_DOCUMENT_UNITS,max(1,limits['items']))
        plan['word_target']=None
    elif 'words' in limits:
        plan['unit_budget']=MAX_DOCUMENT_UNITS
        plan['word_target']=min(MAX_DOCUMENT_WORDS,max(1,limits['words']))
    plan['requested_limits']=dict(limits)
    return plan


def _section(text, genre):
    if re.search(r'\bis (?:a|an)\b', text, re.I): return 'Overview'
    order = ['Limitations', 'Requirements', 'Interfaces', 'Validation', 'Architecture', 'Operations']
    available = _SECTIONS[genre]
    for name in order:
        if name in available and re.search(_CUES[name], text, re.I): return name
    if 'Details' in available: return 'Details'
    return 'Overview'


def _page_records(ordered, plan):
    """Stable atomic pages, measured in source-body words rather than citations."""
    target = plan.get('word_target')
    cursor = 0
    for page in range(1, plan['page'] + 1):
        selected, words, chars = [], 0, 0
        start = cursor
        while cursor < len(ordered) and len(selected) < plan['unit_budget']:
            row = ordered[cursor]
            size = len(row['chunk_text'])
            if size > 200000:
                raise ValueError('document output exceeds atomic quotation text limit')
            if selected and chars + size > 200000:
                break
            selected.append(row); cursor += 1
            words += len(row['chunk_text'].split()); chars += size
            if target is not None and words >= target:
                break
        if page == plan['page']:
            return selected, start, cursor, words
        if cursor == start:
            break
    return [], cursor, cursor, 0


def update_length_coverage(document):
    """Measure composed content separately from titles, citations and notices."""
    words = sum(len(p['text'].split()) for s in document['sections'] for p in s.get('prose', []))
    words += sum(len(q['quote'].split()) for s in document['sections']
                 for q in s.get('literal_quotes', s['quotes']))
    c, plan = document['coverage'], document['plan']
    target = plan.get('word_target')
    c['body_word_count'] = words
    c['effective_word_target'] = target
    requested=plan['requested_limits']
    desired_words=requested.get('words',target)
    desired_units=requested.get('units',requested.get('sentences',requested.get('items',plan['unit_budget'])))
    c['effective_target_met'] = words>=target if target is not None else c['included_chunks']>=plan['unit_budget']
    c['length_target_met'] = words>=desired_words if desired_words is not None else c['included_chunks']>=desired_units
    c['word_shortfall'] = max(0, desired_words - words) if desired_words is not None else 0
    c['item_shortfall'] = max(0,desired_units-c['included_chunks']) if target is None else 0
    c['requested_budget_clamped'] = (desired_words>target if target is not None else desired_units>plan['unit_budget'])
    c['length_required']=bool(requested) or plan['detail']=='detailed'
    c['length_stop_reason'] = ('target_met' if c['length_target_met'] else
        'operator_limit' if c['requested_budget_clamped'] and c['effective_target_met'] else
        'page_budget' if c['has_more'] else 'evidence_exhausted')


def _md(value):
    return re.sub(r'([\\`*{}\[\]()#+!|_])', r'\\\1', html.escape(str(value),quote=False))


def compose_document(plan, rows, *, strict=False, snapshot=None):
    """Pure, testable composition. Each atomic quotation has exact chunk provenance."""
    from cpu_llm.strict_evidence_engine import facts_from, name, value_key
    wanted = _words(plan['topic'])
    candidates = []
    seen = set()
    for row in rows:
        text = str(row.get('chunk_text') or '')
        # Topic-token coverage is an explicit lexical contract, not inferred membership.
        match_sets = plan.get('research_topic_sets')
        matched = (any(set(t).issubset(_words(text)) for t in match_sets if t)
                   if match_sets else wanted and wanted.issubset(_words(text)))
        matched = matched or row['document_id'] in plan.get('research_document_ids', ())
        if not matched or not text.strip(): continue
        if text in seen: continue
        seen.add(text)
        section=_section(text, plan['genre'])
        if section not in plan['sections']: section='Overview'
        for title in plan['sections']:
            if title not in _SECTIONS[plan['genre']] and (
                re.search(_CUES[title],text,re.I) if title in _CUES else _words(title).issubset(_words(text))):
                section=title;break
        candidates.append(dict(row, section=section))
    candidates.sort(key=lambda r: str(r['document_id']))
    # Interleave sections so budget pressure cannot silently erase all later sections.
    groups = {s: [r for r in candidates if r['section'] == s] for s in plan['sections']}
    ordered = []
    while any(groups.values()):
        for section in plan['sections']:
            if groups[section]: ordered.append(groups[section].pop(0))
    selected, start, end, _ = _page_records(ordered, plan)
    if sum(len(r['chunk_text']) for r in selected)>200_000:
        raise ValueError('document output exceeds atomic quotation text limit')
    sections = [dict(title=s, quotes=[], status='missing') for s in plan['sections']]
    for section in sections:
        section['status'] = 'omitted' if any(r['section']==section['title'] for r in candidates) else 'missing'
    evidence = []
    for row in selected:
        text = row['chunk_text']
        proof = dict(document_id=row['document_id'], quote=text, span=text, start=0, end=len(text),
            chunk_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest())
        evidence.append(proof)
        section = next(s for s in sections if s['title'] == row['section'])
        section['quotes'].append(proof); section['status'] = 'supported'
    # Recognized attribute conflicts are exposed with both source versions intact.
    facts, _, _ = facts_from(candidates)
    values = {}
    for fact in facts:
        key = (fact['entity'], fact['attribute'])
        values.setdefault(key, set()).add(value_key(fact['value']))
    conflicts = [dict(entity=k[0], attribute=k[1]) for k,v in values.items() if len(v)>1]
    missing = [s['title'] for s in sections if s['status']=='missing']
    omitted = [s['title'] for s in sections if s['status']=='omitted']
    has_more = end < len(ordered)
    status = 'insufficient_evidence' if not selected else 'partial' if missing or has_more or conflicts or plan['page']>1 else 'evidence_quote'
    coverage = dict(scope='lexical topic matches in bounded authorized snapshot; section labels are organizational',
        source_truth_verified=False, section_coverage_complete=bool(selected) and not missing and not omitted,
        missing_sections=missing, omitted_sections=omitted, matched_chunks=len(candidates), included_chunks=len(selected),
        conflicts=conflicts, conflict_detection='recognized attribute forms only; arbitrary prose conflicts not resolved',
        has_more=has_more, next_page=plan['page']+1 if has_more else None,
        word_limit_enforced=False, sentence_limit_enforced=False,
        budget_scope='atomic source chunks; qualifiers and source text are never truncated',
        snapshot=snapshot)
    document = dict(schema='evidence-document-v1', plan=plan, sections=sections, coverage=coverage)
    update_length_coverage(document)
    if selected and coverage['length_required'] and not coverage['length_target_met']:
        status='partial'
    text = render_document(document)
    coverage['rendered_word_count'] = len(text.split())
    coverage['requested_budget_exceeded'] = bool(plan['requested_limits'].get('words') is not None and
        coverage['body_word_count'] > plan['requested_limits']['words'])
    return dict(answer=None, answer_status=status, status=status, audit_passed=False,
        answer_evidence=evidence, supporting_evidence=[], document=document,
        judgment=dict(schema='document-judgment-v1', outcome=status, verification='source_quote_provenance',
            complete=not missing and not omitted and not has_more and not conflicts and bool(selected) and (coverage['length_target_met'] or not coverage['length_required'])),
        reply=dict(text=text, body=text, format=plan['format'], media_type=plan['output_media']),
        evidence_policy=dict(version='document-quotes-v1', enabled=strict, learned_generation=False,
            source_truth_verified=False, clinical_validation=False),
        rendered_response=dict(schema='rendered-document-v1', text=text, format=plan['format'],
            media_type=plan['output_media'], verification='layout of exact source quotations'),
        routing=dict(schema='flag-routing-contract-v1', executed_nodes=[],
            post_stages=['document_plan', 'document_snapshot', 'document_coverage', 'document_render']))


def render_document(document):
    """Render one evidence representation in all formats, without selecting new facts."""
    plan, sections = document['plan'], document['sections']
    if plan['genre'] in {'email', 'letter'} and plan['format'] in {'report', 'prose'}:
        return _render_email(document)
    styled=document.get('presentation')=='verified_prose_with_literal_fallback'
    note = ('Verified prose constructed from source claims; unrecognized records remain attributed quotations. '
            if styled else 'Source quotations; design decisions are not inferred. ')
    note += 'Missing sections are not stated in the selected evidence.'
    title = f"{plan['topic']} — {plan['genre'].title()}"
    rows = [(s['title'], ('Source quotation: ' if styled else '')+q['quote'], q['document_id']) for s in sections for q in s.get('literal_quotes',s['quotes'])]
    if styled:
        rows += [(s['title'],'Derived prose: '+p['text'],', '.join(p['source_ids'])) for s in sections for p in s.get('prose',[])]
    rows += [(s['title'], _section_gap(s), '') for s in sections if not s['quotes']]
    if plan['output_media'] == 'text/html':
        e = html.escape
        if plan['format'] == 'table':
            from tabulate import tabulate
            body = tabulate(rows, headers=['Section','Source quotation','Source'], tablefmt='html', disable_numparse=True)
        elif plan['format'] in {'bullets','numbered'}:
            tag='ol' if plan['format']=='numbered' else 'ul'
            body=f'<{tag}>'+''.join(f'<li><strong>{e(s)}</strong>: {e(q)} [{e(i)}]</li>' for s,q,i in rows)+f'</{tag}>'
        else:
            body=''.join(f'<section><h2>{e(s["title"])}</h2>'+(''.join(
                f'<p>{e(p["text"])}</p><p>Sources: {e(", ".join(p["source_ids"]))}</p>' for p in s.get('prose',[]))+''.join(
                f'<blockquote>{e(q["quote"])}</blockquote><p>Source: {e(q["document_id"])}</p>' for q in s.get('literal_quotes',s['quotes']))
                or '<p>'+e(_section_gap(s))+'</p>')+'</section>' for s in sections)
        text=f'<article><h1>{e(title)}</h1><p>{e(note)}</p>{body}</article>'
    else:
        lines=['# '+_md(title), '', note, '']
        if plan['format']=='table':
            from tabulate import tabulate
            lines.append(tabulate([[_md(v).replace('\n','<br>') for v in r] for r in rows],
                headers=['Section','Source quotation','Source'],tablefmt='github',disable_numparse=True))
        elif plan['format'] in {'bullets','numbered'}:
            for i,(s,q,d) in enumerate(rows,1):lines.append(f'{str(i)+"." if plan["format"]=="numbered" else "-"} {_md(s)}: {_md(q)} [{_md(d)}]')
        else:
            for section in sections:
                lines.extend(['## '+section['title'], ''])
                for p in section.get('prose',[]):lines.extend([_md(p['text']),'','Sources: '+', '.join(_md(i) for i in p['source_ids']),''])
                for q in section.get('literal_quotes',section['quotes']):lines.extend(['> '+_md(q['quote']).replace('\n','\n> '), '', 'Source: '+_md(q['document_id']), ''])
                if not section['quotes']: lines.extend([_section_gap(section),''])
        text='\n'.join(lines)
    if document['coverage']['has_more']:
        # Preserve the page size so continuation never skips or repeats records.
        outline=', '.join(plan['sections'])
        target = plan.get('word_target')
        size = f'{target} words' if target is not None and plan['unit_budget']==MAX_DOCUMENT_UNITS else f'{plan["unit_budget"]} items'
        recipient = ' to '+plan['recipient'] if plan.get('recipient') else ''
        next_prompt=f'Write a {plan["genre"] if plan["genre"]!="design" else "design document"}{recipient} about {plan["topic"]} in {size}, including {outline}, page {plan["page"]+1}.'
        stamp=(document['coverage'].get('snapshot') or {}).get('as_of')
        if stamp is not None: next_prompt=next_prompt.rstrip('.')+f', as of {stamp}.'
        layout={'report':'report','table':'table','bullets':'bullet points','numbered':'numbered list'}.get(plan['format'])
        if layout:
            media='HTML' if plan['output_media']=='text/html' else 'Markdown'
            next_prompt=next_prompt.rstrip('.')+f' as a {media} {layout}.'
        document['coverage']['continuation_prompt']=next_prompt
        text += ('<p>'+html.escape('More evidence available. Continue: '+next_prompt)+'</p>' if plan['output_media']=='text/html' else '\n\nMore evidence available. Continue: '+next_prompt)
    if document['coverage']['conflicts']:
        warning='Recognized conflicting source attributes exist; no value was selected as authoritative.'
        text+=('<p>'+warning+'</p>' if plan['output_media']=='text/html' else '\n\n'+warning)
    research_gaps = document['coverage'].get('research_required_missing_facets', [])
    if research_gaps:
        warning='Research evidence not found for: '+', '.join(research_gaps)+'. No explanation was invented.'
        text+=('<p>'+html.escape(warning)+'</p>' if plan['output_media']=='text/html' else '\n\n'+warning)
    if plan['requested_limits'].get('words') and not document['coverage']['length_target_met']:
        warning=f"Requested length not reached: {document['coverage']['body_word_count']} source-backed body words; {document['coverage']['length_stop_reason']}. No padding was added."
        text+=('<p>'+html.escape(warning)+'</p>' if plan['output_media']=='text/html' else '\n\n'+warning)
    return text


def _section_gap(section):
    return ('Evidence exists but was omitted from this page by the response budget.'
            if section.get('status')=='omitted' else 'Not stated in the selected evidence.')


def _render_email(document):
    """Draft-only email presentation; sourced body, no invented sender or action."""
    plan = document['plan']
    paragraphs = []
    sources = []
    for section in document['sections']:
        for p in section.get('prose', []):
            paragraphs.append(p['text']+' ['+', '.join(p['source_ids'])+']')
        for q in section.get('literal_quotes', section['quotes']):
            paragraphs.append('Source quotation: '+q['quote']+' ['+q['document_id']+']')
        sources.extend(q['document_id'] for q in section['quotes'])
    if not paragraphs:
        paragraphs=['No supported content was found for this draft.']
    if document['coverage']['has_more']:
        # Reuse the normal continuation generator with an isolated report view.
        from copy import deepcopy
        view = deepcopy(document); view['plan']['genre']='document'; view['plan']['recipient']=None
        render_document(view)
        follow=view['coverage']['continuation_prompt']
        follow=follow.replace('Write a document about ', 'Write a '+plan['genre']+
            (' to '+plan['recipient'] if plan.get('recipient') else '')+' about ',1)
        document['coverage']['continuation_prompt']=follow
        paragraphs.append('Additional evidence omitted by the requested response budget. Continue: '+follow)
    gaps=document['coverage'].get('research_required_missing_facets', [])
    if gaps:
        paragraphs.append('Research evidence not found for: '+', '.join(gaps)+'.')
    if document['coverage']['conflicts']:
        paragraphs.append('Conflicting source attributes remain unresolved; no value was chosen.')
    if plan['requested_limits'].get('words') and not document['coverage']['length_target_met']:
        paragraphs.append(f"Requested length not reached: {document['coverage']['body_word_count']} source-backed body words; {document['coverage']['length_stop_reason']}. No padding was added.")
    subject='Subject: '+plan['topic']
    greeting='Hello'+(' '+plan['recipient'] if plan.get('recipient') else '')+','
    if plan['output_media']=='text/html':
        return '<article>'+''.join('<p>'+html.escape(p)+'</p>' for p in [subject,greeting,*paragraphs,'Regards,'])+'</article>'
    return '\n\n'.join(_md(p) for p in [subject,greeting,*paragraphs,'Regards,'])


def execute_document(app, message, plan, *, caller=None, as_of=None, strict=False, style=None, cycle_options=None):
    from cpu_llm.pipeline import _caller_for
    from cpu_llm.access import source_allowed
    import psycopg
    context = _caller_for(app, caller)
    allowed = None if context is None else context.allowed_sources
    if cycle_options is not None:
        from cpu_llm.cycle_exploration import validate_cycle_options
        cycle_seed,cycle_limits=validate_cycle_options(cycle_options)
    decision = app.guard.check(message+('\n'+cycle_seed if cycle_options is not None else '')).decision
    if decision != 'allow':
        return dict(answer_status='blocked', status='blocked', guard_decision=decision,
            answer=None,audit_passed=False,answer_evidence=[],reply=dict(text='Request blocked.'))
    if strict and cycle_options is not None:
        return dict(answer_status='unsupported',status='unsupported',answer=None,audit_passed=False,
                    answer_evidence=[],reply=dict(text='Cycle exploration is disabled in strict evidence mode.'))
    if strict and plan['genre'] not in {'article', 'report', 'design', 'overview'}:
        return dict(answer_status='unsupported', status='unsupported', answer=None,
            audit_passed=False, answer_evidence=[], reply=dict(text='This document genre is not supported in strict mode.'))
    research = None
    if not strict:
        from cpu_llm.research_plan import build_research_plan
        research = build_research_plan(message, plan)
        if research['clarifications']:
            return dict(answer_status='needs_clarification', status='needs_clarification',
                needs_clarification=True, answer=None, audit_passed=False, answer_evidence=[],
                research_plan=research, reply=dict(text=' '.join(research['clarifications'])))
    try:
        rows, when = app.index.strict_source_rows(allowed, as_of=as_of if as_of is not None else plan.get('snapshot_as_of'))
        if len(rows)>plan['source_scan_limit'] or sum(len(r['chunk_text']) for r in rows)>plan['text_scan_limit']:
            raise ValueError('document snapshot limit')
    except (ValueError, RuntimeError, psycopg.Error):
        return dict(answer_status='insufficient_evidence', status='insufficient_evidence',answer=None,
            audit_passed=False,answer_evidence=[],reply=dict(text='Document evidence scan unavailable or exceeds its limit; no document selected.'))
    if any(not source_allowed(r['document_id'], allowed) for r in rows):
        raise RuntimeError('document source scope violation')
    scanned_chunks = len(rows)
    snapshot_rows=rows
    if research is not None:
        from cpu_llm.research_plan import select_research_rows
        rows = select_research_rows(research, rows)
        plan = dict(plan, research_topic_sets=[sorted(_words(t)) for t in
                    re.split(r'\s+and\s+', plan['topic'], flags=re.I)],
                    research_document_ids=[r['document_id'] for r in rows])
    try:
        result=compose_document(plan, rows, strict=strict, snapshot=dict(as_of=when, scanned_chunks=scanned_chunks))
    except ValueError:
        return dict(answer_status='insufficient_evidence', status='insufficient_evidence',answer=None,
            audit_passed=False,answer_evidence=[],reply=dict(text='Atomic document quotations exceed the output limit; ingest smaller complete records or narrow the topic.'))
    result.update(message=message, original_message=message,tenant_id=app.tenant_id,guard_decision='allow')
    if research is not None:
        result['research_plan'] = research
        result['routing']['post_stages'].insert(0, 'research_plan')
        result['research_plan']['snapshot'] = dict(as_of=when)
        result['research_plan']['budget'] = dict(snapshot_reads=1, replan_passes=0,
            source_scan_limit=plan['source_scan_limit'], text_scan_limit=plan['text_scan_limit'])
        gaps=research['coverage']['missing_facets']
        result['document']['coverage']['research_missing_facets']=gaps
        result['document']['coverage']['research_coverage_complete']=not gaps
        required_gaps=research['coverage']['required_missing_facets']
        result['document']['coverage']['research_required_missing_facets']=required_gaps
        if required_gaps:
            result['judgment']['complete']=False
            if result['answer_status']=='evidence_quote':
                result['answer_status']=result['status']=result['judgment']['outcome']='partial'
        text=render_document(result['document'])
        result['reply'].update(text=text,body=text)
        result['rendered_response']['text']=text
        from cpu_llm.stylistic.document import compose_verified_document
        result=compose_verified_document(result)
    if not strict and style is not None:
        from cpu_llm.stylistic import apply_style
        result=apply_style(result,style)
    if cycle_options is not None:
        from cpu_llm.cycle_exploration import explore_snapshot
        from cpu_llm.cycle_composition import compose_cycles,attach_document_cycles
        search=explore_snapshot(cycle_seed,snapshot_rows,limits=cycle_limits,allowed=allowed,
            tenant_id=app.tenant_id,snapshot=dict(as_of=when))
        remaining_chars=max(0,200000-sum(len(p['quote']) for p in result['answer_evidence']))
        remaining_edges=max(0,MAX_DOCUMENT_UNITS-len(result['answer_evidence']))
        composition=compose_cycles(search,snapshot_rows,char_budget=min(100000,remaining_chars),edge_budget=remaining_edges)
        result=attach_document_cycles(result,search,composition)
    return result
