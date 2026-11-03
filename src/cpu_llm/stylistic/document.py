"""Lossless document sentence construction with an independent inverse grammar.

Friendly wording is generated from the source's predicate, not retrieved as a
phrase. Unrecognized atomic chunks remain visibly attributed source quotations.
"""
from dataclasses import dataclass, asdict
from functools import lru_cache
import hashlib
import re
from chorusgraph.core import START, END, Graph
from chorusgraph.core.node import dict_node_adapter
from .profiles import options, StyleOptions
from .lexicon import lexicon

# Whole, single-clause predicates only. Adjuncts and numbers stay inside the
# immutable predicate; no synonyms, causal connectors or omitted qualifications.
_VERBS=r'(?:is|stores|uses|verifies|retains|runs|supports|records|requires|reports|has|weighs|does not support)'
_RISK=re.compile(r'\b(?:if|unless|when|except|although|because|which|who|that|and|or|but|may|might|must|shall|should|suspected|uncertain|approximately|average|it|they|them|their|this|these)\b',re.I)

@dataclass(frozen=True)
class Claim:
    subject: str
    predicate: str
    source: str
    document_id: str
    fingerprint: str

def claim_from(quote,topic):
    text=quote['quote']
    if len(text)>600 or '\n' in text or _RISK.search(text):return None
    topic=re.sub(r'^the\s+','',topic,flags=re.I)
    match=re.fullmatch(rf'(?P<subject>(?:the )?{re.escape(topic)}) (?P<predicate>{_VERBS}) (?P<tail>[^.!?]+)\.',text,re.I)
    if not match:return None
    predicate=match['predicate']+' '+match['tail']
    digest=hashlib.sha256(text.encode()).hexdigest()
    if quote.get('chunk_sha256')!=digest or quote.get('start')!=0 or quote.get('end')!=len(text):return None
    return Claim(match['subject'],predicate,text,quote['document_id'],digest)

def _generate(state):
    # One subject per paragraph. The first sentence establishes an explicit
    # antecedent; subsequent 'It' is licensed only for that same subject.
    items=[]
    friendly=state['friendly']
    for group in state['groups']:
        claims=group['claims'];sentences=[]
        for start in range(0,len(claims),state['spec'].clauses_per_sentence):
            batch=claims[start:start+state['spec'].clauses_per_sentence]
            predicates=[("doesn't "+c.predicate[len('does not '):])
                if friendly and c.predicate.startswith('does not ') else c.predicate for c in batch]
            subject='It' if friendly and state['allow_pronoun'] and start else batch[0].subject
            text=subject+' '+' and '.join(predicates)+'.'
            sentences.append(dict(text=text,claims=[asdict(c) for c in batch],construction=state['construction']))
        items.append(dict(title=group['title'],sentences=sentences,quotes=group['quotes']))
    return dict(candidate=items,executed_nodes=['stylistic'])

def verify_sentence(text,claims,*,antecedent=None,friendly=False,allow_pronoun=False):
    """Parse output independently and recover every source predicate exactly."""
    if not claims or len({c.subject for c in claims})!=1:return ('mixed_subjects',)
    # Subject may contain spaces: explicitly strip the immutable subject or the
    # narrowly licensed pronoun before parsing the remainder.
    subject=claims[0].subject
    if text.startswith(subject+' '):body=text[len(subject)+1:]
    elif friendly and allow_pronoun and antecedent==subject and text.startswith('It '):body=text[3:]
    else:return ('subject_or_antecedent_changed',)
    if not body.endswith('.'):return ('sentence_boundary_changed',)
    body=body[:-1]
    predicates=body.split(' and ')
    if friendly:predicates=[('does not '+p[len("doesn't "):]) if p.startswith("doesn't ") else p for p in predicates]
    if predicates!=[c.predicate for c in claims]:return ('claim_or_qualifier_changed',)
    for c in claims:
        if c.source!=c.subject+' '+c.predicate+'.' or hashlib.sha256(c.source.encode()).hexdigest()!=c.fingerprint:
            return ('source_changed',)
    return ()

def _verify(state):
    errors=[];count=0
    if len(state['candidate'])!=len(state['groups']):errors.append('section_coverage_changed')
    for expected,actual in zip(state['groups'],state['candidate']):
        recovered=[];antecedent=None
        if expected['title']!=actual['title'] or expected['quotes']!=actual['quotes']:errors.append('quote_or_section_changed')
        for sentence in actual['sentences']:
            if sentence['construction']!=state['construction']:errors.append('construction_changed')
            claims=[Claim(**c) for c in sentence['claims']]
            errors.extend(verify_sentence(sentence['text'],claims,antecedent=antecedent,friendly=state['friendly'],allow_pronoun=state['allow_pronoun']))
            recovered.extend(claims);count+=1
            antecedent=claims[0].subject if claims else None
        if recovered!=expected['claims']:errors.append('claim_coverage_changed')
    if count+sum(len(g['quotes']) for g in state['groups'])>state['spec'].max_sentences:errors.append('budget_cannot_preserve_all_claims')
    return dict(errors=list(dict.fromkeys(errors)),executed_nodes=['stylistic','style_verify'])

@lru_cache(maxsize=1)
def _graph():
    graph=Graph(tenant_id='cpu_llm_style',graph_id='document_style_v1')
    graph.add_node('stylistic',dict_node_adapter(_generate,hop='stylistic'))
    graph.add_node('style_verify',dict_node_adapter(_verify,hop='style_verify'))
    graph.add_edge(START,'stylistic');graph.add_edge('stylistic','style_verify');graph.add_edge('style_verify',END)
    return graph.compile()

def apply_document_style(result,profile):
    from copy import deepcopy
    from cpu_llm.document_workflow import render_document
    output=deepcopy(result);document=output['document'];spec=options(profile)
    if isinstance(profile,str):
        spec=StyleOptions(tone=profile,max_sentences=min(20,document['plan']['unit_budget']))
    meta=dict(schema='document-style-v1',profile=spec.tone,executed_nodes=[],publication='verified_document_derivation')
    if result.get('evidence_policy',{}).get('enabled'):
        output['stylistic']=dict(meta,status='skipped',reason='strict_evidence');return output
    if result.get('guard_decision') not in (None,'allow') or document['coverage']['conflicts']:
        output['stylistic']=dict(meta,status='skipped',reason='held_or_conflicting_document');return output
    if spec.tone_bit & spec.prohibited_risks:
        output['stylistic']=dict(meta,status='skipped',reason='relationship_tone_conflict');return output
    groups=[]
    evidence={p['document_id']:p for p in output['answer_evidence']}
    quotes=[q for s in document['sections'] for q in s['quotes']]
    if len(quotes)!=len(evidence) or {q['document_id'] for q in quotes}!=set(evidence):
        output['stylistic']=dict(meta,status='rejected',reason='document_proof_coverage_changed');return output
    for section in document['sections']:
        claims=[];quotes=[]
        for quote in section['quotes']:
            if (evidence.get(quote['document_id'])!=quote or quote.get('start')!=0 or quote.get('end')!=len(quote['quote'])
                or quote['chunk_sha256']!=hashlib.sha256(quote['quote'].encode()).hexdigest()):
                output['stylistic']=dict(meta,status='rejected',reason='document_proof_mismatch');return output
            claim=claim_from(quote,document['plan']['topic'])
            if claim is None:quotes.append(quote)
            else:claims.append(claim)
        groups.append(dict(title=section['title'],claims=claims,quotes=quotes))
    if not any(g['claims'] for g in groups):
        output['stylistic']=dict(meta,status='skipped',reason='no_supported_document_constructions');return output
    ranked=lexicon().rank('document:predicate',spec)
    if not ranked:
        output['stylistic']=dict(meta,status='skipped',reason='no_licensed_document_construction');return output
    score,construction,index,affinity=ranked[0]
    friendly=construction=='document-friendly-predicate-v1'
    effective='friendly' if friendly else 'formal'
    identities=[c.predicate for g in groups for c in g['claims'] if c.predicate.startswith('is a')]
    nonhuman=re.compile(r'is an? (?:backup service|service|system|library|application|tool|device|product|process|database|server|program|platform)')
    allow_pronoun=bool(identities) and all(nonhuman.fullmatch(p) for p in identities)
    state=_graph().invoke(dict(groups=groups,spec=spec,friendly=friendly,allow_pronoun=allow_pronoun,construction=construction))
    if state.get('__partial__') or state.get('__node_error__') or 'errors' not in state or state['errors']:
        output['stylistic']=dict(meta,status='rejected',reason='document_style_verification_failed',reasons=state.get('errors',[]));return output
    for section,candidate in zip(document['sections'],state['candidate']):
        section['prose']=[dict(text=s['text'],kind='verified_derivation',
            source_ids=[c['document_id'] for c in s['claims']]) for s in candidate['sentences']]
        section['literal_quotes']=candidate['quotes']
    document['presentation']='verified_prose_with_literal_fallback'
    document['tone_alignment']='supported' if affinity else 'neutral_fallback'
    canonical=output['reply']['text'];text=render_document(document)
    output['reply'].update(text=text,body=text)
    output['rendered_response'].update(text=text,canonical_text=canonical,verification='inverse-verified predicate composition plus attributed literal quotes')
    claim_count=sum(len(g['claims']) for g in groups)
    output['stylistic']=dict(meta,status='generated' if text!=canonical else 'unchanged',text=text,
        effective_tone=effective,
        construction_id=construction,score=score,score_components=lexicon().explain(index,spec),
        executed_nodes=state['executed_nodes'],tone_alignment=document['tone_alignment'],
        verification=dict(verified=True,method='document_inverse_grammar',claim_count=claim_count,
            retained_literal_quotes=sum(len(g['quotes']) for g in groups)),proof=deepcopy(output['answer_evidence']))
    output['judgment']['verification']='source_quotes_and_inverse_verified_document_constructions'
    document['coverage']['rendered_word_count']=len(text.split())
    limit=document['plan']['requested_limits'].get('words')
    document['coverage']['requested_budget_exceeded']=limit is not None and len(text.split())>limit
    output.setdefault('routing',{}).setdefault('post_stages',[]).extend(['stylistic','style_verify','document_render'])
    return output
