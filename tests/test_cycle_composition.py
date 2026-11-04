from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from cpu_llm.cycle_exploration import explore_snapshot
from cpu_llm.cycle_composition import compose_cycles,verify_cycle_sentence,parse_cycle_prompt,PREFIX


def rows():
    return [dict(document_id=f'cycle-p{i:04}',chunk_text=t) for i,t in enumerate([
        'Alpha causes Beta.','Beta causes Alpha.','Beta causes Gamma.','Gamma causes Alpha.'],1)]


def appliance():
    from cpu_llm.pipeline import Appliance
    app=object.__new__(Appliance)
    app.tenant_id='t';app.small_talk=False;app.strict_evidence=False
    app.guard=SimpleNamespace(check=lambda _:SimpleNamespace(decision='allow'))
    app.index=SimpleNamespace(strict_source_rows=Mock(return_value=(rows(),123)))
    return app


def test_composes_each_closed_path_in_order_with_all_channel_receipts():
    search=explore_snapshot('Alpha',rows())
    result=compose_cycles(search,rows())
    assert result['consumed_cycles']==2
    for s,c in zip(result['sentences'],search['cycles']):
        assert s['verified'] and verify_cycle_sentence(s['text'],c,rows())
        assert len(s['channel_assessments'])==len(c['edges'])
    assert PREFIX+'Alpha causes Beta; Beta causes Gamma; Gamma causes Alpha.' in [s['text'] for s in result['sentences']]
    assert {p['document_id'] for p in result['evidence']}=={r['document_id'] for r in rows()}


@pytest.mark.parametrize('mutation',['shortcut','reverse','number','proof','order'])
def test_changed_path_or_source_is_rejected(mutation):
    c=deepcopy(explore_snapshot('Alpha',rows())['cycles'][-1])
    text=compose_cycles({'cycles':[c]},rows())['sentences'][0]['text']
    if mutation=='shortcut':text=PREFIX+'Alpha causes Gamma; Gamma causes Alpha.'
    elif mutation=='reverse':text=text.replace('Alpha causes Beta','Beta causes Alpha')
    elif mutation=='number':text=text.replace('Alpha causes Beta','Alpha causes 10 Beta')
    elif mutation=='proof':c['edges'][0]['proof']['start']=1
    else:c['edges'].reverse()
    assert not verify_cycle_sentence(text,c,rows())
    if mutation in {'proof','order'}:
        assert not compose_cycles({'cycles':[c]},rows())['sentences']


def test_invalid_duplicate_proof_cannot_enter_prose_evidence():
    c=deepcopy(explore_snapshot('Alpha',rows())['cycles'][0])
    c['edges'][0]['additional_proofs']=[dict(c['edges'][0]['proof'],quote='invented')]
    assert compose_cycles({'cycles':[c]},rows())['sentences']==[]


@pytest.mark.parametrize('prompt',[
    'Show relationship loops for Alpha.', 'Explore the documented loops through Alpha.',
    'Find cycles around Alpha.', 'Please explain the relationship loops involving Alpha.',
])
def test_easy_standalone_trigger(prompt):
    app=appliance();r=app.ask(prompt)
    assert r['cycle_composition']['consumed_cycles']==2
    assert PREFIX in r['reply']['text']


@pytest.mark.parametrize('prompt',[
    'Do not show relationship loops for Alpha.', 'What does "Show loops for Alpha" mean?',
    'Alpha is a product. Show loops for Alpha.', 'Write an article about Alpha without loops.',
])
def test_negative_quoted_and_background_text_are_not_triggers(prompt):
    assert parse_cycle_prompt(prompt) is None


def test_document_consumes_cycles_after_style_from_one_snapshot():
    app=appliance()
    r=app.ask('Write a detailed report about Alpha, including relationship loops through Alpha in a friendly tone.')
    assert r['cycle_composition']['consumed_cycles']==2
    assert '## Relationship loops' in r['reply']['text']
    assert 'Beta causes Gamma; Gamma causes Alpha' in r['reply']['text']
    assert {p['document_id'] for p in r['answer_evidence']}=={x['document_id'] for x in rows()}
    assert 'Cycle source quotations' in r['rendered_response']['canonical_text']
    app.index.strict_source_rows.assert_called_once_with(None,as_of=None)


def test_document_api_and_prompt_override_and_scope():
    from cpu_llm.access import CallerContext
    app=appliance()
    # A provider that violates the scope must fail before any document is rendered.
    caller=CallerContext.make('t','user',{'cycle-p0001'})
    with pytest.raises(RuntimeError,match='scope violation'):
        app.ask('Write a report about Alpha.',cycle_search={'seed':'Alpha'},caller=caller,as_of=42)
    app.index.strict_source_rows=Mock(return_value=(rows()[:1],42))
    r=app.ask('Write a report about Alpha.',cycle_search={'seed':'Alpha'},caller=caller,as_of=42)
    assert not r['cycle_exploration']['cycles']
    app.index.strict_source_rows.assert_called_once_with(caller.allowed_sources,as_of=42)
    app=appliance()
    r=app.ask('Show loops for Other.',cycle_search={'seed':'Alpha'})
    assert r['cycle_exploration']['seed']=='Alpha' and r['cycle_composition']['consumed_cycles']==2
    r=app.ask('Write a report about Alpha and Beta, including loops.',cycle_search={'seed':'Alpha'})
    assert r['cycle_exploration']['seed']=='Alpha' and r['cycle_composition']['consumed_cycles']==2


def test_strict_floor_blocks_prompt_and_document_loops_without_reading():
    app=appliance();app.strict_evidence=True
    for prompt in ['Show loops for Alpha.','Write a report about Alpha, including loops through Alpha.']:
        r=app.ask(prompt)
        assert r['answer_status']=='unsupported'
    app.index.strict_source_rows.assert_not_called()


def test_prose_budget_omits_whole_paths_with_an_explicit_receipt():
    r=compose_cycles(explore_snapshot('Alpha',rows()),rows(),char_budget=1)
    assert r['presentation_truncated'] and r['omitted_cycles']==2 and not r['sentences']


def test_http_text_trigger_and_operator_strict_floor():
    from cpu_llm.serve import _dispatch
    app=appliance()
    entry=SimpleNamespace(ask=lambda secret,message,**kwargs:app.ask(message,**kwargs))
    code,r=_dispatch(entry,'/v1/ask','test-only',{'message':'Show relationship loops for Alpha.'})
    assert code==200 and r['cycle_composition']['consumed_cycles']==2
    app.index.strict_source_rows.reset_mock()
    _,r=_dispatch(entry,'/v1/ask','test-only',{'message':'Show loops for Alpha.'},require_strict=True)
    assert r['answer_status']=='unsupported'
    app.index.strict_source_rows.assert_not_called()


def test_multi_statement_chunk_spans_are_checked_against_original_chunk_hash():
    data=[dict(document_id='a',chunk_text='Alpha is a process. Alpha causes Beta.'),
          dict(document_id='b',chunk_text='Beta causes Alpha.')]
    search=explore_snapshot('Alpha',data)
    r=compose_cycles(search,data)
    assert r['sentences'][0]['verified']
    assert any(p['start']>0 for p in r['evidence'])


def test_canonical_view_keeps_noncycle_literal_document_records():
    app=appliance()
    app.index.strict_source_rows.return_value=(rows()+[dict(document_id='extra',chunk_text='Alpha synchronizes nightly.')],123)
    r=app.ask('Write a report about Alpha, including loops through Alpha.')
    assert 'Alpha synchronizes nightly.' in r['rendered_response']['canonical_text']
