"""Real parser/retrieval/layout/session integration, with fresh fictional facts."""
import os
import importlib.util
import uuid
import pytest
from cpu_llm.pipeline import Appliance
from cpu_llm.access import CallerContext

pytestmark=pytest.mark.skipif(os.environ.get('CPU_LLM_LIVE_TESTS')!='1',reason='requires disposable PostgreSQL and cached parser/encoder assets')

@pytest.fixture(scope='module',params=['rules','spacy'])
def scenario_app(request):
    if request.param=='spacy' and (importlib.util.find_spec('spacy') is None or importlib.util.find_spec('en_core_web_sm') is None):
        pytest.skip('requires the real optional spaCy parser and en_core_web_sm assets')
    with Appliance(namespace='style_sessions_'+uuid.uuid4().hex[:8],prompt_backend=request.param,
                   resonance_tags=False,reference_backend=None) as app:
        app.catalog_chunks([
            ('scenario-layout-p0001','The Teral is green.'),
            ('scenario-layout-p0002','The Teral is found in Silver Bay.'),
        ])
        yield app

def caller(app):return CallerContext.make(app.tenant_id,'reader',['scenario-layout-p'])

@pytest.mark.parametrize('layout',['a Markdown table','an HTML table','a Markdown report','an HTML report'])
def test_layout_keeps_canonical_content_and_verified_companion(scenario_app,layout):
    app=scenario_app;scope=caller(app)
    query=f'Tell me the color and habitat of the Teral as {layout}.'
    app.clear_session_state();baseline=app.ask(query,caller=scope)
    app.clear_session_state();styled=app.ask(query,caller=scope,style='friendly')
    assert baseline['reply']['text']==styled['reply']['text']
    assert baseline['answer_evidence']==styled['answer_evidence']
    assert baseline['judgment']==styled['judgment']
    assert 'stylistic' not in baseline
    assert styled['stylistic']['status']=='generated'
    assert styled['stylistic']['text']=='The Teral is green, and you can find the Teral in Silver Bay.'
    assert styled['stylistic']['verification']['claim_count']==2
    assert {p['document_id'] for p in styled['stylistic']['proof']}=={'scenario-layout-p0001','scenario-layout-p0002'}

def test_clarification_resume_preserves_layout_and_complete_proof(scenario_app):
    app=scenario_app;scope=caller(app)
    query='What color is it? Where does the Teral live? Please use a Markdown table.'
    app.clear_session_state()
    first=app.ask(query,session_id='plain',caller=scope)
    baseline=app.ask('Teral',session_id='plain',caller=scope)
    app.clear_session_state()
    pending=app.ask(query,session_id='styled',caller=scope,style='friendly')
    assert first.get('needs_clarification') and pending.get('needs_clarification')
    assert pending['stylistic']['status']=='children' and 'text' not in pending['stylistic']
    styled=app.ask('Teral',session_id='styled',caller=scope,style='friendly')
    assert styled['reply']['text']==baseline['reply']['text']
    assert styled['answer_evidence']==baseline['answer_evidence']
    assert styled['stylistic']['status']=='generated'
    assert styled['stylistic']['verification']['claim_count']==2

def test_style_does_not_enter_pending_session_state(scenario_app):
    app=scenario_app;app.clear_session_state();scope=caller(app)
    app.ask('What color is it? Where does the Teral live?',session_id='no-leak',caller=scope,style='friendly')
    completed=app.ask('Teral',session_id='no-leak',caller=scope)
    assert completed['answer_status']=='answered'
    assert 'stylistic' not in completed
    assert all('stylistic' not in task.get('result',{}) for task in completed.get('task_results',[]))

def test_cancel_cannot_reuse_a_factual_style_candidate(scenario_app):
    app=scenario_app;app.clear_session_state();scope=caller(app)
    app.ask('What color is it?',session_id='cancel',caller=scope,style='friendly')
    cancelled=app.ask('cancel',session_id='cancel',caller=scope,style='friendly')
    assert cancelled.get('status')=='cancelled' or cancelled.get('answer_status')=='cancelled'
    assert cancelled['stylistic']['status']=='skipped'
    assert 'text' not in cancelled['stylistic']

def test_successful_style_is_request_local(scenario_app):
    app=scenario_app;app.clear_session_state();scope=caller(app)
    styled=app.ask('What color is the Teral?',session_id='local',caller=scope,style='formal')
    assert styled['stylistic']['status']=='generated'
    ordinary=app.ask('Where does the Teral live?',session_id='local',caller=scope)
    assert 'stylistic' not in ordinary
