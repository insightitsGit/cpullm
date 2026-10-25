from cpu_llm.clarification import ClarificationLoop, scoped_session, supported_ranking


def test_asks_for_criteria_then_preserves_user_choice():
    loop = ClarificationLoop()
    first = loop.prepare('Which lobster is best?', key='a')
    assert first['status'] == 'needs_clarification' and first['slot'] == 'criteria'
    ready = loop.prepare('taste', key='a')
    assert ready['criteria'] == 'taste'
    assert 'Which lobster is best' in ready['query']
    assert loop.prepare('What is the lobster?', key='a')['query'] == 'What is the lobster?'


def test_no_implicit_shared_session_or_scope_leak():
    loop = ClarificationLoop()
    a = scoped_session('tenant', 'alice', {'public'}, 'chat', None)
    b = scoped_session('tenant', 'bob', {'public'}, 'chat', None)
    c = scoped_session('tenant', 'alice', {'private'}, 'chat', None)
    loop.prepare('Which lobster is best?', key=a)
    assert loop.prepare('taste', key=b) == dict(status='ready', query='taste')
    assert loop.prepare('taste', key=c) == dict(status='ready', query='taste')
    loop.prepare('Which lobster is best?')
    assert loop.prepare('taste') == dict(status='ready', query='taste')


def test_loop_is_bounded_expiring_and_cancellable():
    now = [0]
    loop = ClarificationLoop(clock=lambda: now[0], ttl=10, max_sessions=1)
    loop.prepare('Which lobster is best?', key='a')
    loop.prepare('yes', key='a')
    assert loop.prepare('yes', key='a')['status'] == 'insufficient_information'
    loop.prepare('Which lobster is best?', key='a')
    assert loop.prepare('cancel', key='a')['status'] == 'cancelled'
    loop.prepare('Which lobster is best?', key='a')
    now[0] = 11
    assert loop.prepare('taste', key='a')['status'] == 'ready'
    assert 'criteria' not in loop.prepare('taste', key='a')


def test_criterion_is_not_evidence_and_wrong_criterion_cannot_answer():
    loop = ClarificationLoop()
    loop.prepare('Which lobster is best?', key='a')
    plan = loop.prepare('taste', key='a')
    assert not supported_ranking(plan, [dict(document_id='a', chunk_text='The European lobster is best for size.')])
    outcome = loop.need_evidence(plan, key='a')
    assert outcome['slot'] == 'evidence'
    supplied = loop.prepare('Source: The European lobster is best for taste.', key='a')
    evidence = supported_ranking(supplied, [dict(document_id='user-provided', chunk_text=supplied['user_source'])])
    assert evidence[0]['document_id'] == 'user-provided'
    assert not supported_ranking(plan, [dict(document_id='a', chunk_text='The European lobster is not best for taste.')])
    assert not supported_ranking(plan, [dict(document_id='a', chunk_text='The crab is best for taste.')])


def test_a_short_criterion_is_not_a_new_question():
    loop = ClarificationLoop()
    loop.prepare('Which lobster is best?', key='a')
    taste = loop.prepare('how it tastes', key='a')
    assert taste['status'] == 'ready'
    assert taste['criteria'] == 'it tastes'
    assert 'clarification_abandoned' not in taste
    loop.prepare('Which lobster is best?', key='b')
    cost = loop.prepare('what it costs', key='b')
    assert cost['status'] == 'ready' and cost['criteria'] == 'what it costs'
    loop.prepare('Which lobster is best?', key='c')
    price = loop.prepare('by price', key='c')
    assert price['status'] == 'ready' and price['criteria'] == 'price'
    loop.prepare('Which lobster is best?', key='d')
    fresh = loop.prepare('Which lobster is cheapest?', key='d')
    assert fresh['clarification_abandoned'] is True
    assert fresh['query'] == 'Which lobster is cheapest?'
    assert 'Which lobster is best' not in fresh['query']


def test_explicit_criterion_does_not_need_a_first_question():
    plan = ClarificationLoop().prepare('Which lobster is best for taste?')
    assert plan['criteria'] == 'taste' and plan['status'] == 'ready'


def test_ask_returns_clarification_before_any_encoder_or_database_access():
    from cpu_llm.pipeline import Appliance
    from types import SimpleNamespace
    appliance = Appliance.__new__(Appliance)
    appliance.tenant_id = 'test'
    appliance.clarifications = ClarificationLoop()
    result = appliance.ask('Which lobster is best?', session_id='a')
    assert result['needs_clarification'] is True
    assert result['answer'] is None and result['passages'] == []


def test_appliance_full_clarify_criteria_evidence_loop_preserves_attribution():
    from cpu_llm.pipeline import Appliance
    from types import SimpleNamespace
    import threading
    import numpy as np
    appliance = Appliance.__new__(Appliance)
    appliance.tenant_id = 'test'
    appliance._bound = threading.local()
    appliance.clarifications = ClarificationLoop()
    appliance.word_tags = {}
    appliance.index = SimpleNamespace(encode_query=lambda text: np.zeros(1024))
    appliance.format_sense = SimpleNamespace(classify=lambda text: None)
    appliance.graph = SimpleNamespace(invoke=lambda state: dict(guard_decision='allow', passages=[
        dict(document_id='wiki', chunk_text='The European lobster is best for size.')], related=[]))
    first = appliance.ask('Which lobster is best?', session_id='a')
    assert first['clarification']['slot'] == 'criteria'
    second = appliance.ask('taste', session_id='a')
    assert second['clarification']['slot'] == 'evidence' and second['answer'] is None
    third = appliance.ask('Source: The European lobster is best for taste.', session_id='a')
    assert third['reply']['text'].startswith('From user-provided:')
    assert third['status'] == 'evidence_quote' and third['answer'] is None
    # Clarification cannot override a later guard refusal.
    appliance.graph = SimpleNamespace(invoke=lambda state: dict(guard_decision='block', reply=dict(text='Blocked.'), related=[]))
    blocked = appliance.ask('Which lobster is best for taste?', session_id='b')
    assert blocked['reply']['text'] == 'Blocked.'


def test_http_forwards_explicit_session_to_authenticated_entry():
    from cpu_llm.serve import _dispatch
    from types import SimpleNamespace
    calls = []
    def ask(secret, message, **kwargs):
        calls.append((secret, message, kwargs))
        return dict(needs_clarification=True)
    status, result = _dispatch(SimpleNamespace(ask=ask), '/v1/ask', 'credential',
        dict(message='Which lobster is best?', session_id='chat-a'))
    assert status == 200 and calls[0][2]['session_id'] == 'chat-a'


def test_numeric_criteria_and_cross_clause_rankings_are_not_ignored():
    plan = ClarificationLoop().prepare('Which lobster is best for meals under 20 dollars?')
    assert not supported_ranking(plan, [dict(document_id='a', chunk_text='The lobster is best for meals under 50 dollars.')])
    assert not supported_ranking(plan, [dict(document_id='a', chunk_text='The lobster is best for size, but crab is best for meals under 20 dollars.')])
