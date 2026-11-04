"""Proof-bound cycle sentences. A path never licenses an unstated shortcut."""
from __future__ import annotations

import hashlib
import re
from .cycle_exploration import key

PREFIX = 'The source records describe a closed lexical path: '


def parse_cycle_prompt(message, *, seed_override=None):
    """Only whole explicit requests; quoted/negative/background text is not control."""
    if re.search(r'["“”`\n]', message):
        return None
    standalone=re.fullmatch(
        r'(?:please\s+)?(?:show|find|explore|explain|describe)\s+(?:me\s+)?(?:the\s+)?'
        r'(?:documented\s+)?(?:relationship\s+)?(?:loops|cycles)\s+'
        r'(?:through|for|around|involving)\s+([\w][\w -]{0,239})[.!?]?', message.strip(), re.I)
    if standalone:
        return dict(query=message, options=dict(seed=standalone[1].strip()))
    suffix=re.fullmatch(r'(.+?)(?:,\s*|;\s*|\s+)(?:including|with|and show)\s+'
        r'(?:the\s+)?(?:relationship\s+)?(?:loops|cycles)'
        r'(?:\s+(?:through|for)\s+([\w][\w -]{0,239}))?[.!?]?', message.strip(), re.I)
    if suffix:
        from .document_workflow import plan_document
        plan=plan_document(suffix[1])
        if plan is not None:
            seed=seed_override or suffix[2] or plan['topic']
            if not seed_override and not suffix[2] and re.search(r'\band\b',seed,re.I):
                raise ValueError('For multiple topics, name a loop seed: including relationship loops through Alpha.')
            return dict(query=suffix[1],options=dict(seed=seed.strip()))
    return None


def validate_cycle_sources(cycle, rows):
    """Validate path/proofs independently before allowing prose OR literal fallback."""
    from .knowledge_graph import extract_facts
    edges=cycle['edges']
    if len(edges)<2:
        return False
    source_rows={r['document_id']:r['chunk_text'] for r in rows}
    visited=set()
    for i,edge in enumerate(edges):
        if edge.get('proof',{}).get('document_id')!=edge['document_id']:
            return False
        for p in [edge.get('proof',{}),*edge.get('additional_proofs',[])]:
            chunk=source_rows.get(p.get('document_id'))
            start,end=p.get('start'),p.get('end')
            if chunk is None or type(start) is not int or type(end) is not int or not 0<=start<end<=len(chunk):
                return False
            if chunk[start:end]!=p.get('quote') or hashlib.sha256(chunk.encode()).hexdigest()!=p.get('chunk_sha256'):
                return False
            facts=extract_facts(p['document_id'],p['quote'])
            if not any((key(f.subject),f.relation,key(f.object))==(edge['source'],edge['relation'],edge['target']) for f in facts):
                return False
        if edge['source']!=key(edge['subject']) or edge['target']!=key(edge['object']):
            return False
        if edge['target']!=edges[(i+1)%len(edges)]['source'] or edge['source'] in visited:
            return False
        visited.add(edge['source'])
    return not all(e['relation']=='alias_of' for e in edges)


def verify_cycle_sentence(text, cycle, rows):
    """Parse the generated clauses and recover each ordered source statement."""
    if not validate_cycle_sources(cycle,rows) or not text.startswith(PREFIX) or not text.endswith('.'):
        return False
    clauses=text[len(PREFIX):-1].split('; ')
    edges=cycle['edges']
    if len(clauses)!=len(edges):
        return False
    return all(e['proof']['quote'].endswith('.') and ';' not in e['proof']['quote'] and
               clause==e['proof']['quote'][:-1] for clause,e in zip(clauses,edges))


def compose_cycles(search, rows, *, char_budget=100000, edge_budget=500):
    """Consume all returned paths that fit; whole paths and proofs stay atomic."""
    sentences=[];evidence=[];seen=set();used=0;edge_count=0;omitted=0
    for cycle in search['cycles']:
        if len(cycle['edges'])+edge_count>edge_budget:
            omitted+=1;continue
        if not validate_cycle_sources(cycle,rows):
            omitted+=1;continue
        edges=cycle['edges']
        clauses=[e.get('proof',{}).get('quote','')[:-1] for e in edges]
        text=PREFIX+'; '.join(clauses)+'.'
        verified=verify_cycle_sentence(text,cycle,rows)
        if not verified:
            # Unsupported punctuation/grammar remains literal, never simplified.
            text='Source quotations along a lexical path:\n'+'\n'.join(
                '['+e['document_id']+'] '+e.get('proof',{}).get('quote','') for e in edges)
        proofs=[]
        for e in edges:
            for p in [e.get('proof'),*e.get('additional_proofs',[])]:
                if p is not None:
                    proofs.append(p)
        size=len(text)+sum(len(p['quote']) for p in proofs)
        if used+size>char_budget or edge_count+len(proofs)>edge_budget:
            omitted+=1;continue
        used+=size;edge_count+=len(proofs)
        sentences.append(dict(text=text,verified=verified,
            method='cycle_clause_and_source_span_verifier' if verified else 'literal_path_fallback',
            edge_ids=[e['id'] for e in edges],source_ids=list(dict.fromkeys(p['document_id'] for p in proofs)),
            channel_assessments=[e['channels'] for e in edges],qualification='lexical_candidate',
            source_truth_verified=False))
        for p in proofs:
            identity=(p['document_id'],p['start'],p['end'])
            if identity not in seen:
                seen.add(identity);evidence.append(p)
    return dict(schema='cycle-composition-v1',sentences=sentences,evidence=evidence,
                consumed_cycles=len(sentences),omitted_cycles=omitted,
                presentation_truncated=bool(omitted),new_inferred_facts=[])


def attach_document_cycles(result, search, composition):
    """Attach after neutral/explicit style so path clauses cannot be rewritten."""
    import html
    original_text=result['reply']['text']
    result['cycle_exploration']=search
    result['cycle_composition']=composition
    blocks=[s['text']+'\nSources: '+', '.join(s['source_ids']) for s in composition['sentences']]
    if not blocks:
        blocks=['No qualifying loop could be included within the authorized snapshot and response budget.']
    if not search['complete']:
        blocks.append('Cycle search incomplete: '+search['stop_reason']+'.')
    if composition['omitted_cycles']:
        blocks.append(str(composition['omitted_cycles'])+' discovered cycles omitted by validation or response limits.')
    blocks.append('Paths use exact labels; word senses and source truth are not independently verified.')
    if result['document']['plan']['output_media']=='text/html':
        suffix='<section><h2>Relationship loops</h2>'+''.join('<p>'+html.escape(b)+'</p>' for b in blocks)+'</section>'
    else:
        suffix='\n\n## Relationship loops\n\n'+'\n\n'.join(blocks)
    result['reply']['text']+=suffix
    result['reply']['body']=result['reply']['text']
    result['rendered_response']['text']=result['reply']['text']
    literal='\n\nCycle source quotations:\n'+'\n'.join('['+p['document_id']+'] '+p['quote'] for p in composition['evidence'])
    result['rendered_response']['canonical_text']=result['rendered_response'].get('canonical_text',original_text)+literal
    known={(p['document_id'],p['start'],p['end']) for p in result['answer_evidence']}
    result['answer_evidence'].extend(p for p in composition['evidence'] if (p['document_id'],p['start'],p['end']) not in known)
    coverage=result['document']['coverage']
    coverage.update(cycle_count=len(search['cycles']),cycle_count_presented=composition['consumed_cycles'],
        cycle_search_complete=search['complete'],cycle_presentation_truncated=composition['presentation_truncated'],
        rendered_word_count=len(result['reply']['text'].split()))
    coverage['cycle_body_word_count']=sum(len(s['text'].split()) for s in composition['sentences'])
    coverage['combined_body_word_count']=coverage['body_word_count']+coverage['cycle_body_word_count']
    if not search['cycles'] or not search['complete'] or composition['presentation_truncated']:
        result['judgment']['complete']=False
        if result['answer_status']=='evidence_quote':
            result['answer_status']=result['status']=result['judgment']['outcome']='partial'
    result['routing']['post_stages'].extend(['cycle_snapshot','cycle_explore','cycle_compose','cycle_verify'])
    return result
