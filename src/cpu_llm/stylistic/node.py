"""A real ChorusGraph output subgraph producing a verified companion sentence.

The existing reply, status, audit fields and evidence remain unchanged.
"""
from functools import lru_cache
from chorusgraph.core import START, END, Graph
from chorusgraph.core.node import dict_node_adapter
from .contracts import snapshot, validate_profile
from .verifier import verify_compound
from .profiles import options
from .lexicon import lexicon

def _clause(frame,spec):
    ranked=lexicon().rank(frame.relation,spec)
    if not ranked:return None
    score,kind,index,affinity=ranked[0]
    inner='the '+frame.subject[4:] if frame.subject.startswith('The ') else frame.subject
    leading='The '+frame.subject[4:] if frame.subject.startswith('the ') else frame.subject
    forms={
        'formal-color-v1':f'The color of {inner} is {frame.value}.',
        'plain-color-v2':f'{leading} is {frame.value}.',
        'friendly-location-v1':f'You can find {inner} in {frame.value}.',
        'plain-location-v2':f'{leading} is found in {frame.value}.',
        'shape-predicate-v2':f'{leading} has {"an" if frame.value=="oval" else "a"} {frame.value} shape.',
        'shape-attribute-v2':f'The shape of {inner} is {frame.value}.',
        'material-predicate-v2':f'{leading} is made of {frame.value}.',
        'material-attribute-v2':f'The material of {inner} is {frame.value}.',
        'weight-predicate-v2':f'{leading} weighs {frame.value}.',
        'weight-attribute-v2':f'The weight of {inner} is {frame.value}.',
    }
    return dict(text=forms[kind],construction_id=kind,input_fingerprint=frame.fingerprint,proof=frame.proof,
                score=score,score_components=lexicon().explain(index,spec),
                tone_alignment='supported' if affinity else 'neutral_fallback')

def _generate(state):
    frames=state['frames'];spec=state['spec']
    clauses=[_clause(frame,spec) for frame in frames]
    if any(c is None for c in clauses):return dict(candidate=None,style_nodes=['stylistic'])
    sentences=[]
    for start in range(0,len(clauses),spec.clauses_per_sentence):
        parts=[]
        for i,clause in enumerate(clauses[start:start+spec.clauses_per_sentence]):
            text=clause['text'][:-1]
            if i and text.startswith(('The ','You ')):text=text[0].lower()+text[1:]
            parts.append(text)
        sentences.append(', and '.join(parts)+'.')
    proof=tuple(sorted(set(p for f in frames for p in f.proof)))
    return dict(candidate=dict(text=' '.join(sentences),clauses=clauses,proof=proof),style_nodes=['stylistic'])

def _verify(state):
    candidate=state.get('candidate')
    errors=verify_compound(state['frames'],candidate,state['spec'],state['sentence_budget']) if candidate else ('unsupported_construction',)
    return dict(style_errors=list(errors),style_nodes=state['style_nodes']+['style_verify'])

@lru_cache(maxsize=1)
def _graph():
    graph=Graph(tenant_id='cpu_llm_style',graph_id='stylistic_companion_v2')
    graph.add_node('stylistic',dict_node_adapter(_generate,hop='stylistic'))
    graph.add_node('style_verify',dict_node_adapter(_verify,hop='style_verify'))
    graph.add_edge(START,'stylistic');graph.add_edge('stylistic','style_verify');graph.add_edge('style_verify',END)
    return graph.compile()

def apply_style(result, profile):
    validate_profile(profile)
    if profile is None:return result
    if result.get('document'):
        from .document import apply_document_style
        return apply_document_style(result,profile)
    spec=options(profile)
    output=dict(result)
    if (result.get('guard_decision') not in (None,'allow') or result.get('delivery_blocked')
        or result.get('__partial__') or result.get('__node_error__')):
        output['stylistic']=dict(schema='style-result-v2',status='skipped',profile=spec.tone,
            publication='companion_only',executed_nodes=[],reason='canonical_turn_not_eligible')
        return output
    # Child snapshots have already passed canonical finalization. Do not style
    # aggregate text or transfer one child's proof into another child.
    if result.get('task_results'):
        output['task_results']=[dict(task,result=apply_style(task['result'],profile))
                                if isinstance(task.get('result'),dict) else dict(task)
                                for task in result['task_results']]
        fallback=dict(schema='style-result-v2',status='children',profile=spec.tone,publication='companion_only')
        output['stylistic']=fallback
        frames=tuple(snapshot(t.get('result') or {}) for t in result['task_results'])
        if (result.get('needs_clarification') or result.get('answer_status') not in (None,'answered','evidence_quote')
            or not frames or len(frames)>8 or any(f is None for f in frames)):
            fallback['reason']='incomplete_or_unsupported_children';return output
        key=lambda f:f.subject.casefold().removeprefix('the ')
        if len({key(f) for f in frames})!=1:
            fallback['reason']='multiple_subjects';return output
        values={}
        for frame in frames:
            if frame.relation in values and values[frame.relation]!=frame.value:
                fallback['reason']='conflicting_values';return output
            values[frame.relation]=frame.value
    else:
        frame=snapshot(result)
        frames=(frame,) if frame is not None else ()
    metadata=dict(schema='style-result-v2',profile=spec.tone,publication='companion_only',executed_nodes=[])
    if not frames:
        output['stylistic']=dict(metadata,status='skipped',reason='no_supported_immutable_frame')
        return output
    if spec.tone_bit&spec.prohibited_risks:
        output['stylistic']=dict(metadata,status='skipped',reason='relationship_tone_conflict');return output
    budget=spec.max_sentences
    plan=result.get('response_plan') or {}
    if type(plan.get('sentence_budget')) is int:budget=min(budget,plan['sentence_budget'])
    if len(frames)>budget*spec.clauses_per_sentence:
        output['stylistic']=dict(metadata,status='skipped',reason='budget_cannot_preserve_all_claims');return output
    state=_graph().invoke(dict(frames=frames,spec=spec,sentence_budget=budget))
    metadata['executed_nodes']=state.get('style_nodes',[])
    if state.get('__partial__') or state.get('__node_error__') or 'style_errors' not in state:
        output['stylistic']=dict(metadata,status='rejected',reason='style_execution_failure')
    elif state['style_errors']:
        output['stylistic']=dict(metadata,status='skipped' if state['style_errors']==['unsupported_construction'] else 'rejected',
                                reasons=state['style_errors'])
    else:
        candidate=state['candidate']
        canonical=' '.join(f.canonical for f in frames)
        clauses=candidate['clauses']
        output['stylistic']=dict(metadata,status='generated' if candidate['text']!=canonical else 'unchanged',text=candidate['text'],
            construction_id=clauses[0]['construction_id'] if len(clauses)==1 else 'related-conjunction-v2',
            input_fingerprint=clauses[0]['input_fingerprint'] if len(clauses)==1 else None,
            verification=dict(schema='style-verification-v2',verified=True,method='closed_inverse_grammar',claim_count=len(frames)),
            tone_alignment='supported' if all(c['tone_alignment']=='supported' for c in clauses) else 'neutral_fallback',
            sentence_count=(len(frames)+spec.clauses_per_sentence-1)//spec.clauses_per_sentence,
            claims=[dict(subject=f.subject,relation=f.relation,value=f.value,construction_id=c['construction_id'],
                score=c['score'],score_components=c['score_components'],tone_alignment=c['tone_alignment'],
                proof=[dict(document_id=k,span=s) for k,s in f.proof]) for f,c in zip(frames,clauses)],
            proof=[dict(document_id=key,span=span) for key,span in candidate['proof']])
    return output
