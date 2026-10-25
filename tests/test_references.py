import re
from types import SimpleNamespace
import threading
import numpy as np

from cpu_llm.references import ReferenceSessions
from cpu_llm.clarification import ClarificationLoop, scoped_session


class Backend:
    def analyze(self, context, prompt):
        choices = ['the European lobster', 'the American lobster'] if 'American' in context else ['the European lobster']
        if len(choices) != 1:
            return [], choices
        match = re.search(r'\bit\b', prompt)
        return ([dict(start=match.start(), end=match.end(), antecedent=choices[0], replacement=choices[0], backend='test')] if match else []), choices


def test_reference_uses_scoped_context_and_preserves_original_and_binding():
    sessions = ReferenceSessions(Backend())
    sessions.prepare('Tell me about the European lobster.', key='a')
    result = sessions.prepare('Where does it live?', key='a')
    assert result['query'] == 'Where does the European lobster live?'
    assert result['original'] == 'Where does it live?' and result['bindings']
    assert sessions.prepare('Where does it live?', key='b')['status'] == 'needs_clarification'
    assert sessions.prepare('Where does it live?')['status'] == 'needs_clarification'


def test_ambiguity_asks_and_user_confirmation_resumes_original_question():
    sessions = ReferenceSessions(Backend())
    sessions.prepare('Tell me about the European lobster and the American lobster.', key='a')
    unresolved = sessions.prepare('Where does it live?', key='a', continuation=dict(criteria='location'))
    assert unresolved['slot'] == 'reference'
    assert len(unresolved['candidates']) == 2
    assert sessions.prepare('yes', key='a')['status'] == 'needs_clarification'
    resolved = sessions.prepare('American lobster', key='a')
    assert resolved['query'] == 'Where does the American lobster live?'
    assert resolved['continuation']['criteria'] == 'location'


def test_without_model_named_confirmation_is_explicit_not_automatic_inference():
    sessions = ReferenceSessions()
    sessions.prepare('Tell me about the European lobster.', key='a')
    assert sessions.prepare('Where does it live?', key='a')['status'] == 'needs_clarification'
    result = sessions.prepare('European lobster', key='a')
    assert result['query'] == 'Where does European lobster live?'
    assert result['bindings'][0]['backend'] == 'user-confirmed'


def test_expiry_budgets_and_scope_changes_do_not_reuse_private_context():
    now = [0]
    sessions = ReferenceSessions(Backend(), ttl=10, limit=1, clock=lambda:now[0])
    a = scoped_session('t', 'a', {'one'}, 'same', None)
    b = scoped_session('t', 'a', {'two'}, 'same', None)
    sessions.prepare('Tell me about the European lobster.', key=a)
    assert sessions.prepare('Where does it live?', key=b)['status'] == 'needs_clarification'
    now[0] = 11
    assert sessions.prepare('Where does it live?', key=a)['status'] == 'needs_clarification'
    sessions.prepare('yes', key=a)
    assert sessions.prepare('yes', key=a)['status'] == 'insufficient_information'


def test_backend_error_or_forged_antecedent_never_becomes_a_binding():
    backend = SimpleNamespace(analyze=lambda context,prompt: ([dict(start=11,end=13,antecedent='private crab',replacement='private crab')], []))
    sessions = ReferenceSessions(backend)
    sessions.prepare('Tell me about the European lobster.', key='a')
    assert sessions.prepare('Where does it live?', key='a')['status'] == 'needs_clarification'


def test_appliance_resolves_before_embedding_and_reply_and_clarifies_ambiguity():
    from cpu_llm.pipeline import Appliance
    appliance = Appliance.__new__(Appliance)
    appliance.tenant_id = 'test'
    appliance._bound = threading.local()
    appliance.clarifications = ClarificationLoop()
    appliance.references = ReferenceSessions(Backend())
    appliance.word_tags = {}
    encoded = []
    appliance.index = SimpleNamespace(encode_query=lambda text: encoded.append(text) or np.zeros(1024))
    appliance.format_sense = SimpleNamespace(classify=lambda text: None)
    appliance.graph = SimpleNamespace(invoke=lambda state: dict(guard_decision='allow', reply=dict(text='Source-based reply.'), related=[]))
    appliance.ask('Tell me about the European lobster.', session_id='a')
    result = appliance.ask('Where does it live?', session_id='a')
    assert encoded[-1] == 'Where does the European lobster live?'
    assert result['original_message'] == 'Where does it live?'
    assert result['reference_resolution']['bindings']
    unresolved = appliance.ask('Where does it live?', session_id='other')
    assert unresolved['needs_clarification'] and unresolved['clarification']['slot'] == 'reference'
