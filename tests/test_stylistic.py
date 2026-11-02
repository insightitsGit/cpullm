import copy
import pytest

from cpu_llm.stylistic import apply_style
from cpu_llm.stylistic.contracts import snapshot
from cpu_llm.stylistic.verifier import verify

def accepted(relation='has_color',text='The Aster is blue.'):
    proof=[dict(document_id='manual-p0001',span=text)]
    request=dict(entity='aster',relation=relation,direction='subject',polarity='affirmative',quantifier_scope='individual')
    return dict(reply=dict(text=text,body=text),answer_status='answered',audit_passed=True,
        answer_evidence=copy.deepcopy(proof),judgment=dict(outcome='answered',verification='structural',
        evidence=copy.deepcopy(proof),answer_decision=dict(outcome='answered',request=request,text=text,proof=proof)))

@pytest.mark.parametrize('profile,relation,text,expected',[
    ('formal','has_color','The Aster is blue.','The color of the Aster is blue.'),
    ('friendly','lives_in','The Aster is found in coastal waters.','You can find the Aster in coastal waters.'),
])
def test_real_graph_generates_new_sentence_without_mutating_canonical(profile,relation,text,expected):
    original=accepted(relation,text);before=copy.deepcopy(original)
    result=apply_style(original,profile)
    assert result['stylistic']['text']==expected
    assert result['stylistic']['text']!=text
    assert result['stylistic']['executed_nodes']==['stylistic','style_verify']
    assert result['stylistic']['verification']['verified']
    assert original==before
    assert {k:v for k,v in result.items() if k!='stylistic'}==before

def test_disabled_returns_original_and_does_not_compile_graph(monkeypatch):
    import cpu_llm.stylistic.node as module
    monkeypatch.setattr(module,'_graph',lambda:pytest.fail('disabled style compiled graph'))
    result=accepted();assert apply_style(result,None) is result

@pytest.mark.parametrize('change',[
    lambda r:r['judgment'].update(outcome='conflicting'),
    lambda r:r.update(needs_clarification=True),
    lambda r:r.update(__node_error__='error'),
    lambda r:r.update(shine_ok=False),
    lambda r:r['judgment']['answer_decision']['request'].update(polarity='negative'),
    lambda r:r['judgment']['answer_decision']['request'].update(entity='another'),
    lambda r:r['judgment']['answer_decision']['request'].update(quantifier_scope='all'),
    lambda r:r['judgment']['answer_decision']['proof'].append(dict(document_id='other',span='Other fact.')),
    lambda r:r['judgment'].update(evidence=[]),
    lambda r:r['judgment']['answer_decision'].update(text='The Aster is blue if it is wet.'),
])
def test_unsafe_or_incomplete_frames_do_not_enter_node(change):
    result=accepted();change(result)
    output=apply_style(result,'formal')
    assert output['stylistic']['status']=='skipped'
    assert output['stylistic']['executed_nodes']==[]
    assert 'text' not in output['stylistic']
    assert output['reply']==result['reply']

@pytest.mark.parametrize('text',[
    'The color of The Aster is red.',
    'The color of The Other is blue.',
    'The color of The Aster is not blue.',
    'The color of The Aster is blue. It is beautiful.',
    'The color of The Aster is blue unless it rains.',
])
def test_independent_verifier_rejects_changed_or_added_claims(text):
    frame=snapshot(accepted());candidate=dict(text=text,construction_id='formal-color-v1',
        input_fingerprint=frame.fingerprint,proof=frame.proof)
    assert 'meaning_or_coverage_changed' in verify(frame,candidate,'formal')

def test_proof_and_stale_input_rejected():
    frame=snapshot(accepted())
    candidate=dict(text='The color of the Aster is blue.',construction_id='formal-color-v1',input_fingerprint='old',proof=())
    assert set(verify(frame,candidate,'formal'))=={'stale_input','proof_changed'}

def test_batch_isolation_and_unsupported_profile_construction():
    one=accepted();two=accepted('lives_in','The Aster is found in coastal waters.')
    result=dict(task_results=[dict(id='a',result=one),dict(id='b',result=two)])
    output=apply_style(result,'formal')
    assert output['task_results'][0]['result']['stylistic']['status']=='generated'
    assert output['task_results'][1]['result']['stylistic']['status']=='unchanged'
    assert result['task_results'][0]['result']==one

@pytest.mark.parametrize('value',['unknown-tone','',False,{},['formal']])
def test_invalid_profile_is_explicit(value):
    with pytest.raises(ValueError):apply_style(accepted(),value)

def test_public_api_calls_node_after_dispatch_before_render(monkeypatch):
    from cpu_llm.pipeline import Appliance
    import cpu_llm.request_planner as planner
    import cpu_llm.output_rendering as rendering
    monkeypatch.setattr(planner,'dispatch_request',lambda *args:accepted())
    monkeypatch.setattr(rendering,'render_response',lambda result:result)
    app=object.__new__(Appliance)
    assert 'stylistic' not in app.ask('What color is Aster?')
    assert app.ask('What color is Aster?',style='formal')['stylistic']['status']=='generated'

def test_tampered_graph_candidate_is_rejected_without_changing_reply(monkeypatch):
    import cpu_llm.stylistic.node as module
    generate=module._generate
    def corrupt(state):
        delta=generate(state)
        delta['candidate']['text']='The color of the Aster is red.'
        return delta
    module._graph.cache_clear()
    try:
        monkeypatch.setattr(module,'_generate',corrupt)
        original=accepted();result=apply_style(original,'formal')
        assert result['stylistic']['status']=='rejected'
        assert 'text' not in result['stylistic']
        assert result['reply']==original['reply']
    finally:
        module._graph.cache_clear()

def test_shared_graph_keeps_concurrent_inputs_isolated():
    from concurrent.futures import ThreadPoolExecutor
    def run(color):
        result=apply_style(accepted(text=f'The Aster is {color}.'),'formal')
        assert result['stylistic']['text']==f'The color of the Aster is {color}.'
        return result['stylistic']['input_fingerprint']
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(run,['red','blue','green','white']*4))
    assert len(set(results))==4
