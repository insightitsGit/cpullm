"""Independent v3 scoring. No cpu_llm, Tabulate or Jinja imports."""
from __future__ import annotations
import copy
import html
import re
from html.parser import HTMLParser

VERSION='prompt-output-v3-scorer-2'
YES={'answered','evidence_quote'}

def norm(text):
    return re.sub(r'\s+',' ',html.unescape(str(text or '')).casefold()).strip(' .?!')

def contains(text,needle):
    return bool(needle) and re.search(r'(?<!\w)'+re.escape(str(needle).casefold())+r'(?!\w)',html.unescape(str(text)).casefold()) is not None

def outcome(result):
    value=str(result.get('answer_status') or (result.get('reply') or {}).get('answer_status') or result.get('status') or (result.get('judgment') or {}).get('outcome') or '')
    return 'needs_clarification' if value=='clarification' else value

class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.cells=[];self.rows=[];self.articles=[]
        self.cell=None;self.article=None;self.field=None;self.scripts=False;self.all=[]
    def handle_starttag(self,tag,attrs):
        self.stack.append(tag)
        if tag=='script':self.scripts=True
        if tag=='tr':self.cells=[]
        if tag in ('td','th'):self.cell=[]
        if tag=='article':self.article=dict(request='',response='',sources='')
        if self.article is not None and tag in ('h2','div','p'):self.field={'h2':'request','div':'response','p':'sources'}[tag]
        if tag=='br':self.handle_data('\n')
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:self.cells.append(''.join(self.cell));self.cell=None
        if tag=='tr' and self.cells:self.rows.append(self.cells)
        if tag=='article' and self.article is not None:self.articles.append(self.article);self.article=None
        if tag in ('h2','div','p'):self.field=None
        if self.stack:self.stack.pop()
    def handle_data(self,data):
        self.all.append(data)
        if self.cell is not None:self.cell.append(data)
        if self.article is not None and self.field:self.article[self.field]+=data

def pipe_cells(line):
    # State machine, not split('|'): escaped pipes are literal cell data.
    cells=[];part=[];escaped=False
    for ch in line.strip().strip('|'):
        if escaped:part.append(ch);escaped=False
        elif ch=='\\':escaped=True
        elif ch=='|':cells.append(''.join(part).strip());part=[]
        else:part.append(ch)
    if escaped:part.append('\\')
    cells.append(''.join(part).strip())
    return [html.unescape(re.sub(r'<br\s*/?>','\n',c,flags=re.I)) for c in cells]

def visible(result):
    text=str((result.get('reply') or {}).get('text') or '')
    media=(result.get('reply') or {}).get('media_type') or (result.get('rendered_response') or {}).get('media_type') or 'text/markdown'
    sections=[];valid=True;scripts=False
    if media=='text/html':
        parser=VisibleHTML();parser.feed(text);scripts=parser.scripts
        if parser.rows:
            valid=[cell.strip() for cell in parser.rows[0]]==['Request','Response','Sources'] and all(len(r)==3 for r in parser.rows)
            sections=[dict(request=r[0],response=r[1],sources=r[2]) for r in parser.rows[1:] if len(r)==3]
        else:sections=parser.articles
        body='\n'.join(s['response'] for s in sections) if sections else '\n'.join(parser.all)
    elif text.lstrip().startswith('|'):
        lines=[l for l in text.splitlines() if l.strip()]
        parsed=[pipe_cells(l) for l in lines]
        valid=len(parsed)>=2 and parsed[0]==['Request','Response','Sources'] and all(len(r)==3 for r in parsed)
        sections=[dict(request=r[0],response=r[1],sources=r[2]) for r in parsed[2:] if len(r)==3]
        body='\n'.join(s['response'] for s in sections)
    elif text.startswith('# Response report'):
        for chunk in re.split(r'(?m)^## ',text)[1:]:
            head,_,rest=chunk.partition('\n');body_part,sep,refs=rest.partition('\nSources:')
            sections.append(dict(request=html.unescape(head),response=html.unescape(body_part.replace('<br>','\n')),sources=html.unescape(refs) if sep else ''))
        body='\n'.join(s['response'] for s in sections)
    else:body=text
    return dict(text=text,body=body,sections=sections,media=media,valid=valid and not scripts,script_nodes=scripts)

def evidence(result):
    found=[]
    for field in ['answer_evidence','supporting_evidence']:
        for item in result.get(field) or []:
            if isinstance(item,dict):found.append(item)
    # The nested fields must not conceal a different proof.
    reply=result.get('reply') or {}
    for field in ['answer_evidence','supporting_evidence']:
        for item in reply.get(field) or []:
            if isinstance(item,dict) and item not in found:found.append(item)
    return found

def proof_ok(spec,result,documents,corrections):
    items=evidence(result);ids={str(p.get('document_id') or '') for p in items}
    sets=spec.get('proof_sets') or []
    def resolve(value):return corrections.get(value[11:],value) if value.startswith('@corrected:') else value
    expected=[[resolve(x) for x in group] for group in sets]
    valid=not expected or any(set(group)<=ids for group in expected)
    bad=[]
    scope=(spec.get('caller') or {}).get('sources') if spec.get('caller') is not None else None
    for item in items:
        key=str(item.get('document_id') or '');span=str(item.get('span') or '')
        doc=documents.get(key)
        if not doc or not span or norm(span) not in norm(doc['text']):bad.append(key or '<missing>')
        if scope is not None and not any(key.startswith(allowed) for allowed in scope):bad.append(key)
        if doc and spec.get('as_of') is not None:
            at=spec['as_of']
            if doc.get('valid_at',0)>at or (doc.get('valid_until') is not None and at>=doc['valid_until']):bad.append(key)
    return valid and not bad,ids,bad

def expected_source_present(spec,text,documents,corrections):
    sets=spec.get('proof_sets') or []
    if not sets:return True
    # Full expected source statements or a licensed joined conclusion may answer.
    for group in sets:
        keys=[corrections.get(k[11:],k) if k.startswith('@corrected:') else k for k in group]
        if all(k in documents and norm(documents[k]['text']) in norm(text) for k in keys):return True
    for b in spec.get('bindings') or []:
        subject=re.escape(b['subject']);obj=re.escape(b['object']);rel=b['relation']
        forms={
          'is_a':rf'\b{subject}\s+(?:is|are)\s+(?:a|an)\s+{obj}\b',
          'has_color':rf'\b{subject}\s+(?:is|are|was|were)\s+{obj}(?:[.!?]|$)',
          'has':rf'\b{subject}\s+(?:has|have)\s+{obj}\b',
          'has_lifespan':rf'\b{subject}\s+lives?\s+for\s+(?:up to\s+)?{obj}\b',
          'lives_in':rf'\b{subject}\s+(?:is found|lives?)\s+in\s+{obj}\b',
          'weight':rf'\b{subject}\s+weighs?\s+{obj}\b'}
        pattern=forms.get(rel)
        if pattern and re.search(pattern,text,re.I):return True
    return False

def unknown_assertions(text,documents):
    # Conservative independent literal-sentence oracle. Nonliteral paraphrases
    # are flagged for review rather than silently certified as true.
    known={norm(d['text']) for d in documents.values()}
    subjects=set()
    for d in documents.values():
        m=re.match(r'(?:The |Every |Some |A )?(.+?)\s+(?:is|has|lives|weighs|stopped|baked)\b',d['text'])
        if m:subjects.add(m[1])
    bad=[]
    for line in re.split(r'\n|(?<=[.!?])\s+(?=[A-Z])',text):
        line=re.sub(r'^\s*(?:[-*]|\d+\.)\s*','',line).strip()
        if line.startswith(('From ','Sources:','Q:','Subject:','Title:','To:','Date:')):continue
        if line.endswith('?'):continue
        for subject in subjects:
            if re.match(rf'^(?:The |Every |Some |A )?{re.escape(subject)}\s+(?:is|has|lives|weighs|stopped|baked)\b',line,re.I):
                if norm(line) not in known:bad.append(line)
                break
    return list(dict.fromkeys(bad))

def score(case,result,trace,documents,corrections,arm):
    errors=[];checks={};display=visible(result);actual=outcome(result)
    allowed=case.get('rules_allowed_outcomes',case['allowed_outcomes']) if arm=='rules' and case.get('capability')=='spacy_only' else case['allowed_outcomes']
    checks['outcome']=actual in allowed
    positive=bool(set(allowed)&YES)
    checks['display_structure']=display['valid']
    checks['media']=not case.get('media') or display['media']==case['media']
    rendered=result.get('rendered_response') or {}
    checks['format']=not case.get('format') or rendered.get('format')==case['format'] or (result.get('response_plan') or {}).get('format')==case['format']
    body=display['body'];checks['visible_claims']=all(contains(body,c) for c in case.get('claims',[])) if positive else True
    ok,ids,bad=proof_ok(case,result,documents,corrections)
    checks['proof']=ok if positive else not bad
    checks['proof_binding']=not positive or expected_source_present(case,body,documents,corrections)
    checks['minimum_citations']=len(ids)>=case.get('min_citations',0) if positive else True
    checks['minimum_visible_facts']=True
    if positive and case.get('min_visible_facts'):
        matched={norm(d['text']) for d in documents.values() if norm(d['text']) in norm(body)}
        checks['minimum_visible_facts']=len(matched)>=case['min_visible_facts']
    children=result.get('task_results') or []
    child_verdicts=[]
    if case.get('children'):
        checks['task_coverage']=len(children)==len(case['children'])
        sections=display['sections']
        checks['row_coverage']=not case.get('format') or case['format'] not in {'table','report'} or len(sections)==len(case['children'])
        for i,spec in enumerate(case['children']):
            child=children[i].get('result') if i<len(children) else None
            child_text=sections[i]['response'] if i<len(sections) else visible(child or {})['body']
            local=dict(spec,caller=case.get('caller'),as_of=case.get('as_of'))
            pvalid,cids,cbad=proof_ok(local,child or {},documents,corrections)
            good=bool(child) and outcome(child) in YES and pvalid and all(contains(child_text,c) for c in spec['claims']) and expected_source_present(local,child_text,documents,corrections)
            if i<len(sections):good=good and contains(sections[i]['request'],spec['subject']) and all(contains(sections[i]['sources'],x) for x in cids)
            child_verdicts.append(dict(index=i,ok=good,proof_bad=cbad))
        checks['child_bindings']=all(v['ok'] for v in child_verdicts)
    elif display['sections'] and positive:
        checks['visible_citations']=all(contains(' '.join(s['sources'] for s in display['sections']),key) for key in ids)
    # Do not let correct structured rows conceal incorrect displayed row values.
    if rendered.get('rows') and display['sections']:
        rows=rendered['rows'];sections=display['sections']
        checks['visible_structured_agreement']=len(rows)==len(sections) and all(norm(a.get('response'))==norm(b.get('response')) for a,b in zip(rows,sections))
    text_fields=[body,str(result.get('answer') or ''),str((result.get('reply') or {}).get('body') or '')]
    public='\n'.join(text_fields)
    checks['no_forbidden_claims']=not any(contains(public,x) for x in case.get('forbidden',[]))
    # A canary disclosure remains a failure even in a question or nonanswer.
    canaries=re.findall(r'v3-secret-[a-z0-9-]+',public,re.I)
    checks['no_private_canary']=not canaries
    unknown=unknown_assertions(public,documents) if positive else []
    checks['no_unlicensed_literal_claims']=not unknown
    plans=[(c.get('result') or {}).get('response_plan') or {} for c in children] if children else [result.get('response_plan') or {}]
    plan=result.get('response_plan') or {}
    for key,value in case.get('flags',{}).items():checks['flag_'+key]=(plan.get('flags') or {}).get(key)==value
    if case.get('optional_limit'):
        produced=str((result.get('brief') or {}).get('list') or (result.get('brief') or {}).get('summary') or '')
        units=len([s for s in re.split(r'(?<=[.!?])\s+|\n',produced) if s.strip()])
        checks['optional_budget']=units<=case['optional_limit']
    checks['word_policy']=all(p.get('word_limit_enforced') is not True for p in plans)
    routes=[(c.get('result') or {}).get('routing') or {} for c in children] if children else [result.get('routing') or {}]
    nodes=[node for r in routes for node in r.get('executed_nodes',[])]
    checks['required_nodes']=all(n in nodes for n in case.get('required_nodes',[]))
    checks['forbidden_nodes']=not any(n in nodes for n in case.get('forbidden_nodes',[]))
    checks['node_order']=all(a in nodes and b in nodes and nodes.index(a)<nodes.index(b) for a,b in case.get('order',[]))
    stages=list((result.get('routing') or {}).get('post_stages',[]))+[x for r in routes for x in r.get('post_stages',[])]
    checks['post_stages']=all(n in stages for n in case.get('post_stages',[]))
    checks['no_search']=not case.get('no_search') or not any(t.get('event')=='search' for t in trace)
    checks['execution']=not result.get('__partial__') and not result.get('__node_error__')
    errors=[name for name,value in checks.items() if not value]
    return dict(version=VERSION,ok=not errors,checks=checks,errors=errors,actual=actual,allowed=allowed,
                cited_ids=sorted(ids),invalid_proof=bad,unknown_assertions=unknown,children=child_verdicts,
                visible_body=body,observed_nodes=nodes,canaries=canaries)

def selftest():
    docs={'p':dict(text='The Nuvero is blue.')};case=dict(allowed_outcomes=['answered','evidence_quote'],
       claims=['blue'],proof_sets=[['p']],caller=dict(sources=['p']))
    good=dict(message='What color is the Nuvero?',answer_status='evidence_quote',reply=dict(text='The Nuvero is blue.'),answer_evidence=[dict(document_id='p',span=docs['p']['text'])])
    fixtures=[]
    def check(name,c,r,want):
        result=score(c,r,[],docs,{},'rules');passed=result['ok']==want
        fixtures.append(dict(name=name,passed=passed,wanted=want,verdict=result))
        assert passed,(name,result)
    check('literal_positive',case,good,True)
    r=copy.deepcopy(good);r['reply']['text']='The Nuvero is found in Blue.';check('wrong_relation_true_word',case,r,False)
    r=copy.deepcopy(good);r['reply']['text']='The WestNuvero is blue.';check('wrong_entity_boundary',case,r,False)
    r=copy.deepcopy(good);r['reply']['text']='The Nuvero is not blue.';check('negated_claim',case,r,False)
    r=copy.deepcopy(good);r['answer_evidence']=[];check('missing_proof',case,r,False)
    r=copy.deepcopy(good);r['answer_evidence'][0]['span']='The Nuvero is red.';check('false_span_same_id',case,r,False)
    r=copy.deepcopy(good);r['reply']['text']='The retrieved passages do not settle that.';r['reply']['body']=good['reply']['text'];check('hidden_body_cannot_answer',case,r,False)
    c=copy.deepcopy(case);c['caller']['sources']=[];check('forbidden_scope_proof',c,good,False)
    c=copy.deepcopy(case);c['media']='text/html';check('wrong_media',c,good,False)
    r=copy.deepcopy(good);r['reply'].update(media_type='text/html',text='<article><h2>What color is Nuvero?</h2><div>The Nuvero is blue.</div><p>Sources: p</p></article>');check('html_positive',dict(case,format='report'),dict(r,rendered_response=dict(format='report')),True)
    r['reply']['text']+='<script>bad()</script>';check('html_script_node',case,r,False)
    assert pipe_cells(r'| 0012 | a\|b<br>c |')==['0012','a|b\nc']
    fixtures.append(dict(name='escaped_pipe_leading_zero',passed=True))
    r=copy.deepcopy(good);r['reply']['text']='The Nuvero is blue. The Nuvero has a unicorn.';check('extra_unlicensed_claim',case,r,False)
    r=copy.deepcopy(good);r['answer_status']='needs_clarification';r['reply']['text']='Which meaning?';check('clarification_positive',dict(allowed_outcomes=['needs_clarification']),r,True)
    r=copy.deepcopy(good);r.pop('answer_status');r['judgment']={'outcome':'answered'};check('specialist_judgment_outcome',case,r,True)
    r=copy.deepcopy(r);r['reply']['text']='The Nuvero is red.';check('judgment_does_not_replace_visible_proof',case,r,False)
    r=copy.deepcopy(good);r['reply'].update(media_type='text/html',text='<table><tr><th>Request  </th><th> Response </th><th>Sources </th></tr><tr><td>color</td><td>The Nuvero is blue.</td><td>p</td></tr></table>');check('html_header_padding',case,r,True)
    return fixtures
