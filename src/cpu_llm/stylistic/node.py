"""A real ChorusGraph output subgraph producing a verified companion sentence.

The existing reply, status, audit fields and evidence remain unchanged in v1.
"""
from functools import lru_cache
from chorusgraph.core import START, END, Graph
from chorusgraph.core.node import dict_node_adapter
from .contracts import snapshot, validate_profile
from .verifier import verify

def _generate(state):
    frame=state['frame'];profile=state['profile']
    subject='the '+frame.subject[4:] if frame.subject.startswith('The ') else frame.subject
    if profile=='formal' and frame.relation=='has_color':
        text=f'The color of {subject} is {frame.value}.';kind='formal-color-v1'
    elif profile=='friendly' and frame.relation=='lives_in':
        text=f'You can find {subject} in {frame.value}.';kind='friendly-location-v1'
    else:return dict(candidate=None,style_nodes=['stylistic'])
    return dict(candidate=dict(text=text,construction_id=kind,input_fingerprint=frame.fingerprint,
                              proof=frame.proof),style_nodes=['stylistic'])

def _verify(state):
    candidate=state.get('candidate')
    errors=verify(state['frame'],candidate,state['profile']) if candidate else ('unsupported_construction',)
    return dict(style_errors=list(errors),style_nodes=state['style_nodes']+['style_verify'])

@lru_cache(maxsize=1)
def _graph():
    graph=Graph(tenant_id='cpu_llm_style',graph_id='stylistic_companion_v1')
    graph.add_node('stylistic',dict_node_adapter(_generate,hop='stylistic'))
    graph.add_node('style_verify',dict_node_adapter(_verify,hop='style_verify'))
    graph.add_edge(START,'stylistic');graph.add_edge('stylistic','style_verify');graph.add_edge('style_verify',END)
    return graph.compile()

def apply_style(result, profile):
    validate_profile(profile)
    if profile is None:return result
    output=dict(result)
    # Child snapshots have already passed canonical finalization. Do not style
    # aggregate text or transfer one child's proof into another child.
    if result.get('task_results'):
        output['task_results']=[dict(task,result=apply_style(task['result'],profile))
                                if isinstance(task.get('result'),dict) else dict(task)
                                for task in result['task_results']]
        output['stylistic']=dict(schema='style-result-v1',status='children',profile=profile,publication='companion_only')
        return output
    frame=snapshot(result)
    metadata=dict(schema='style-result-v1',profile=profile,publication='companion_only',executed_nodes=[])
    if frame is None:
        output['stylistic']=dict(metadata,status='skipped',reason='no_supported_immutable_frame')
        return output
    state=_graph().invoke(dict(frame=frame,profile=profile))
    metadata['executed_nodes']=state.get('style_nodes',[])
    if state.get('__partial__') or state.get('__node_error__') or 'style_errors' not in state:
        output['stylistic']=dict(metadata,status='rejected',reason='style_execution_failure')
    elif state['style_errors']:
        output['stylistic']=dict(metadata,status='skipped' if state['style_errors']==['unsupported_construction'] else 'rejected',
                                reasons=state['style_errors'])
    else:
        candidate=state['candidate']
        output['stylistic']=dict(metadata,status='generated',text=candidate['text'],
            construction_id=candidate['construction_id'],input_fingerprint=frame.fingerprint,
            verification=dict(schema='style-verification-v1',verified=True,method='closed_inverse_grammar'),
            proof=[dict(document_id=key,span=span) for key,span in frame.proof])
    return output
