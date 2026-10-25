"""Contracts at boundaries between conversation, retrieval, and delivery."""
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from cpu_llm.clarification import ClarificationLoop, scoped_session
from cpu_llm.pipeline import Appliance, _hits_for_named_article, _retrieve
from cpu_llm.references import ReferenceSessions


@pytest.fixture
def appliance():
    instance = Appliance.__new__(Appliance)
    instance.tenant_id = 'test'
    instance._bound = threading.local()
    instance.clarifications = ClarificationLoop()
    instance.references = ReferenceSessions()
    instance.word_tags = {}
    instance.index = SimpleNamespace(encode_query=lambda text: np.zeros(1024))
    instance.format_sense = SimpleNamespace(classify=lambda text: None)
    instance.graph = SimpleNamespace(invoke=lambda state: dict(
        guard_decision='allow', answer_status='answered', answer_evidence=[
            dict(document_id='old', span='A prior answer.')], verification_scope='query',
        reply=dict(text='A prior answer.'), related=[], passages=[]))
    return instance


def test_cancel_clears_both_conversation_stores(appliance):
    appliance.ask('Tell me about the European lobster.', session_id='chat')
    appliance.ask('Which lobster is best?', session_id='chat')
    assert appliance.ask('cancel', session_id='chat')['status'] == 'cancelled'
    key = scoped_session('test', None, None, 'chat', None)
    assert key not in appliance.references.states
    assert key not in appliance.clarifications.pending


@pytest.mark.parametrize('failure', [
    {'__partial__': True}, {'__node_error__': 'retrieve'},
    {'grammar_ok': False}, {'delivery_blocked': 'audit'},
    {'shine_ok': False}, {'guard_decision': 'block'},
])
def test_ranking_followup_cannot_replace_execution_failure_or_delivery_hold(appliance, failure):
    appliance.graph.invoke = lambda state: dict(reply=dict(text='Withheld.'), related=[], **failure)
    result = appliance.ask('Which lobster is best for taste?', session_id='chat')
    assert result['reply']['text'] == 'Withheld.'
    assert not result.get('needs_clarification')


def test_ranking_clarification_clears_prior_answer_metadata(appliance):
    result = appliance.ask('Which lobster is best for taste?', session_id='chat')
    assert result['answer'] is None
    assert result['answer_status'] == result['reply']['answer_status'] == 'needs_clarification'
    assert result['answer_evidence'] == []
    assert result['verification_scope'] is None


def test_ranking_quote_replaces_prior_answer_metadata(appliance):
    appliance.graph.invoke = lambda state: dict(guard_decision='allow', related=[], passages=[
        dict(document_id='guide', chunk_text='The European lobster is best for taste.')],
        answer_status='answered', answer_evidence=[], verification_scope='query', audit_passed=True)
    result = appliance.ask('Which lobster is best for taste?', session_id='chat')
    assert result['answer_status'] == result['reply']['answer_status'] == 'evidence_quote'
    assert result['answer_evidence'] == result['reply']['answer_evidence']
    assert result['verification_scope'] == 'source_attribution'
    assert result['audit_passed'] is False


def test_reference_then_typo_keeps_the_actual_original_prompt(appliance, monkeypatch):
    import cpu_llm.typos
    appliance.references = ReferenceSessions(SimpleNamespace(analyze=lambda context, prompt: ([
        dict(start=11, end=13, antecedent='the European lobster', replacement='the European lobster')], [])))
    appliance.ask('Tell me about the European lobster.', session_id='chat')
    monkeypatch.setattr(cpu_llm.typos, 'correct_message',
        lambda message, *args, **kwargs: (message.replace('livve', 'live'), ['livve']))
    result = appliance.ask('Where does it livve?', session_id='chat')
    assert result['original_message'] == 'Where does it livve?'
    assert result['resolved_query'] == 'Where does the European lobster live?'


def test_history_retrieval_does_not_fetch_current_article_or_tag_rows(monkeypatch):
    import cpu_llm.pipeline as pipeline
    def forbidden(*args, **kwargs):
        raise AssertionError('current-only expansion must not run for history')
    monkeypatch.setattr(pipeline, '_hits_for_named_article', forbidden)
    monkeypatch.setattr(pipeline, '_with_tagged_paragraphs', forbidden)
    index = SimpleNamespace(encode_query=lambda message: np.zeros(1024),
        search=lambda *args, **kwargs: [], db=SimpleNamespace())
    instance = SimpleNamespace(index=index, _turn=dict(as_of=123),
        memory=SimpleNamespace(_nodes={}, _edges={}))
    result = _retrieve(instance)({'message': 'Tell me about Mount Elbert.'})
    assert result['passages'] == []


def test_forbidden_article_lead_cannot_discard_authorized_hits():
    lead = dict(document_id='wikitext2-mount-elbert-p0001', chunk_text='Private lead.')
    index = SimpleNamespace(lead_for_slug=lambda slug: lead if slug == 'mount-elbert' else None)
    hits = [dict(document_id='public-guide', chunk_text='Public evidence.')]
    assert _hits_for_named_article(index, 'Tell me about Mount Elbert.', hits, {'public'}) is None


def test_reference_confirmation_updates_ranking_topic_as_well_as_query(appliance):
    appliance.graph.invoke = lambda state: dict(guard_decision='allow', related=[], passages=[
        dict(document_id='guide', chunk_text='The European lobster is best for taste.')])
    first = appliance.ask('Which of them is best for taste?', session_id='chat')
    assert first['clarification']['slot'] == 'reference'
    result = appliance.ask('European lobster', session_id='chat')
    assert result['status'] == 'evidence_quote'
    assert 'From guide:' in result['reply']['text']


def test_repair_trace_retains_membership_found_in_the_successful_retry():
    from cpu_llm.attribute_search import retrieve_missing_attribute
    from cpu_llm.prompt_intent import route_prompt
    question = 'How long does the fictional moth live?'
    index = SimpleNamespace(encode_query=lambda text: np.zeros(1024), search=lambda *args, **kwargs: [
        dict(document_id='type', chunk_text='The fictional moth is a fictional insect.'),
        dict(document_id='rule', chunk_text='All fictional insects live for 12 months.')])
    _, report = retrieve_missing_attribute(index, question, [], route_prompt(question))
    assert report['answer_reason'] == 'universal_membership_join'
    assert report['joins'][0]['document_id'] == 'type'


@pytest.mark.parametrize('turn', [dict(allowed_sources={'public-guide'}), dict(as_of=123)])
def test_specialist_expansion_stays_in_this_turns_authorized_historical_rows(turn, monkeypatch):
    import cpu_llm.pipeline as pipeline
    def forbidden(*args, **kwargs):
        raise AssertionError('legacy global/current lookup must not run')
    monkeypatch.setattr(pipeline, 'rows_for_side', forbidden)
    row = dict(document_id='public-guide', chunk_text='The fictional moth is blue.',
        tensor_1024d=np.zeros(1024))
    instance = SimpleNamespace(_turn=dict(turn, hits=[row]), _deep_tensors={},
        _previous_ids=['private-guide'], word_tags={}, index=SimpleNamespace(
            chunks_for_articles=forbidden, db=SimpleNamespace(get_by_ids=forbidden)))
    state = dict(message='Summarize the fictional moth.', related=[
        dict(chunk_id='public-guide', chunk_text=row['chunk_text'])])
    assert pipeline._brief_rows(instance, state) == [row]
    assert pipeline._rows_for_agent(instance, state, 'fictional moth') == [row]
    assert pipeline._gather(instance)(state)['creative_pool']['paragraph_count'] == 1
    deep = pipeline._deep(instance)(state)
    assert [item['document_id'] for item in deep['possibilities']] == ['public-guide']
    assert deep['deep_hands'] == {}
    instance._turn['hits'] = []
    assert pipeline._brief_rows(instance, state) == []
    assert pipeline._rows_for_agent(instance, state, 'fictional moth') == []
    assert pipeline._gather(instance)(state)['creative_pool']['paragraph_count'] == 0


def test_scoped_cognition_does_not_fall_back_to_global_lexical_memory(monkeypatch):
    import cpu_llm.pipeline as pipeline
    import cpu_llm.assembly
    def forbidden(*args, **kwargs):
        raise AssertionError('global lexical evidence must not be used')
    monkeypatch.setattr(pipeline, '_stored_proposition', lambda *args: None)
    monkeypatch.setattr(cpu_llm.assembly, 'realization_order', lambda *args: [])
    monkeypatch.setattr(pipeline, '_lexical_evidence', forbidden)
    instance = SimpleNamespace(memory=object(), _turn=dict(allowed_sources={'public-guide'},
        related_ids=['public-guide'], hits=[dict(document_id='public-guide',
            chunk_text='Unparsed text.', tensor_1024d=np.zeros(1024))]))
    result = pipeline._cognize(instance)({'message': 'What is the fictional moth?'})
    assert result['cognition_status'] == 'needs_evidence_propositions'


def test_empty_scope_refuses_before_conversation_state_changes(appliance):
    from cpu_llm.access import CallerContext
    caller = CallerContext.make('test', 'alice', [])
    result = appliance.ask('Which lobster is best?', caller=caller, session_id='chat')
    assert result['access_error'] == 'allowed_sources_empty'
    assert not appliance.clarifications.pending and not appliance.references.states


def test_ranking_uses_the_corrected_topic_and_reports_the_query_that_was_encoded(appliance):
    appliance.word_tags = {'lobster': {}}
    encoded = []
    appliance.index.encode_query = lambda text: encoded.append(text) or np.zeros(1024)
    appliance.graph.invoke = lambda state: dict(guard_decision='allow', related=[], passages=[
        dict(document_id='guide', chunk_text='The European lobster is best for taste.')])
    result = appliance.ask('Which lobstor is best for taste?', session_id='chat')
    assert result['status'] == 'evidence_quote'
    assert result['original_message'] == 'Which lobstor is best for taste?'
    assert result['resolved_query'] == encoded[-1]
