"""Evidence gaps are checked after retrieval; intent changes require confirmation."""
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from cpu_llm.answerability import assess
from cpu_llm.clarification import ClarificationLoop
from cpu_llm.pipeline import Appliance, _reply
from cpu_llm.references import ReferenceSessions
from cpu_llm.response_repair import inspect_gap


def app_with(*sentences):
    app = Appliance.__new__(Appliance)
    app.tenant_id = 'repair-test'
    app._bound = threading.local()
    app.clarifications, app.references = ClarificationLoop(), ReferenceSessions()
    app.word_tags = {}
    app.index = SimpleNamespace(encode_query=lambda text: np.zeros(1024))
    app.format_sense = SimpleNamespace(classify=lambda text: None)
    rows = [dict(chunk_id=f'notes-p{i:04}', chunk_text=text) for i, text in enumerate(sentences, 1)]
    def graph(state):
        state = dict(state, related=rows, guard_decision='allow', answer=None, audit_passed=False)
        return dict(state, **_reply(state))
    app.graph = SimpleNamespace(invoke=graph)
    return app


@pytest.mark.parametrize('name,action', [('Mary', 'baked a cake'), ('Ada North', 'built a boat'), ('the rover', 'crossed a bridge')])
def test_public_confirmation_changes_intent_only_after_user_chooses(name, action):
    sentence = f'{name} {action}.'
    app = app_with(sentence)
    first = app.ask(f'What is {name}?', session_id='chat')
    assert first['needs_clarification']
    assert first['post_retrieval']['reason'] == 'intent_confirmation'
    assert first['answer'] is None and not first['answer_evidence']
    assert len(first['clarification']['options']) == 2
    resumed = app.ask('activity', session_id='chat')
    assert not resumed.get('needs_clarification')
    assert sentence in resumed['reply']['text']
    assert resumed['judgment']['outcome'] in {'answered', 'evidence_quote'}
    assert not app.clarifications.pending


def test_identity_confirmation_cannot_invent_an_occupation_or_repeat_question():
    app = app_with('Mary baked a cake.')
    app.ask('What is Mary?', session_id='chat')
    result = app.ask('1', session_id='chat')
    assert result['judgment']['outcome'] == 'insufficient_evidence'
    assert not result.get('needs_clarification')
    assert result['post_retrieval']['confirmed']
    assert 'baker' not in result['reply']['text']
    assert not app.clarifications.pending


@pytest.mark.parametrize('fact,label,expected', [
    ('The Cedar is found in Norway.', 'location', 'Norway'),
    ('The Cedar is blue.', 'color', 'blue'),
    ('The Cedar has a bell.', 'possessions', 'bell'),
    ('The Cedar lives for 30 years.', 'lifespan', '30 years'),
])
def test_evidence_driven_options_use_the_same_loop_for_other_relations(fact, label, expected):
    app = app_with(fact)
    first = app.ask('What is the Cedar?', session_id='s')
    # Only offer source-backed alternatives, plus explicit identity confirmation.
    assert first['needs_clarification']
    assert label in [item['label'] for item in first['clarification']['options']]
    answer = app.ask(label, session_id='s')
    assert expected in answer['reply']['text']
    assert not answer.get('needs_clarification')


def test_post_retrieval_pending_choice_cannot_cross_callers():
    from cpu_llm.access import CallerContext
    app = app_with('Mary baked a cake.')
    alice = CallerContext.make(app.tenant_id, 'alice', ['notes-p'])
    bob = CallerContext.make(app.tenant_id, 'bob', ['notes-p'])
    app.ask('What is Mary?', session_id='same', caller=alice)
    other = app.ask('2', session_id='same', caller=bob)
    assert 'Mary baked' not in other['reply']['text']
    resumed = app.ask('2', session_id='same', caller=alice)
    assert 'Mary baked a cake.' in resumed['reply']['text']


@pytest.mark.parametrize('question', ['Who is Mary?', 'What color is Mary?', 'How long does Mary live?'])
def test_clear_intent_is_a_missing_fact_not_a_forced_reinterpretation(question):
    result = app_with('Mary baked a cake.').ask(question)
    assert result['judgment']['outcome'] == 'insufficient_evidence'
    assert not result.get('needs_clarification')
    assert result['post_retrieval']['reason'] == 'missing_evidence'


def test_no_evidence_does_not_create_speculative_interpretations():
    result = app_with().ask('What is Mary?')
    assert not result.get('needs_clarification')
    assert result['post_retrieval']['options'] == []


def test_stateless_selection_must_be_rephrased_and_stores_no_pending_state():
    app = app_with('Mary baked a cake.')
    result = app.ask('What is Mary?')
    assert result['needs_clarification']
    assert 'full question' in result['reply']['text']
    assert not app.clarifications.pending


@pytest.mark.parametrize('choice', ['2', 'What did Mary do?'])
def test_compound_pauses_resumes_and_preserves_budget_and_all_tasks(choice):
    app = app_with('Mary baked a cake.', 'The Cedar is found in Norway.')
    first = app.ask('What is Mary? Where does the Cedar live? Answer in two sentences.', session_id='chat')
    assert first['task_results'][1]['status'] == 'pending'
    budget = first['response_plan']['combined_budget']
    resumed = app.ask(choice, session_id='chat')
    assert len(resumed['task_results']) == 2
    assert resumed['judgment']['complete']
    assert 'Mary baked a cake.' in resumed['reply']['text']
    assert 'Norway' in resumed['reply']['text']
    assert resumed['response_plan']['combined_budget'] == budget


def test_interpretation_attempts_cancel_expiry_and_new_questions():
    now = [0]
    loop = ClarificationLoop(clock=lambda: now[0])
    options = [dict(label='identity', query='Who is Mary?'), dict(label='activity', query='What did Mary do?')]
    loop.need_interpretation('What is Mary?', options, key='s')
    assert loop.prepare('yes', key='s')['status'] == 'needs_clarification'
    assert loop.prepare('maybe', key='s')['status'] == 'insufficient_information'
    loop.need_interpretation('What is Mary?', options, key='s')
    assert loop.prepare('cancel', key='s')['status'] == 'cancelled'
    loop.need_interpretation('What is Mary?', options, key='s')
    assert loop.prepare('What color is the boat?', key='s')['clarification_abandoned']
    loop.need_interpretation('What is Mary?', options, key='s')
    now[0] = 1801
    assert loop.prepare('2', key='s')['query'] == '2'


@pytest.mark.parametrize('text', ['Mary is a baker.', 'Mary has a bell.', 'Mary might bake a cake.',
                                  'Mary did not bake a cake.', 'If Mary baked a cake.', 'John baked a cake.',
                                  'Mary bakes cakes.'])
def test_activity_question_does_not_quote_roles_possessions_or_uncertain_other_actions(text):
    assert assess('What did Mary do?', [text])['answer_status'] == 'insufficient_evidence'


def test_holds_and_conflicts_never_open_an_interpretation_loop():
    for outcome in ['conflicting', 'blocked', 'unsupported', 'answered']:
        assert inspect_gap('What is Mary?', dict(judgment=dict(outcome=outcome))) is None
    assert inspect_gap('What is Mary?', dict(judgment=dict(outcome='insufficient_evidence'), shine_ok=False)) is None
    assert inspect_gap('What is Mary?', dict(judgment=dict(outcome='insufficient_evidence'), __partial__=True)) is None


def test_current_activity_confirmation_keeps_tense():
    app = app_with('Mary bakes cakes.')
    first = app.ask('What is Mary?', session_id='s')
    assert 'current activity' in [option['label'] for option in first['clarification']['options']]
    answer = app.ask('current activity', session_id='s')
    assert 'Mary bakes cakes.' in answer['reply']['text']
    assert assess('What does Mary do?', ['Mary baked a cake.'])['answer_status'] == 'insufficient_evidence'
