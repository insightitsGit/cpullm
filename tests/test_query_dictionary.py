from types import SimpleNamespace
import numpy as np
import pytest

from cpu_llm.query_dictionary import interpret_prompt
from cpu_llm.prompt_intent import route_prompt
from cpu_llm.model01.generator import generate
from cpu_llm.pipeline import _retrieve


@pytest.mark.parametrize('question, source', [
    ('Where would I encounter the coastal moth?', 'The coastal moth lives in Norway.'),
    ('Where does the coastal moth dwell?', 'The coastal moth lives in Norway.'),
    ('What hue is the coastal moth?', 'The coastal moth is blue.'),
    ('Which category does the coastal moth belong to?', 'The coastal moth is a species of insect.'),
    ('What brings about flooding?', 'Heavy rain causes flooding.'),
])
def test_equivalent_expressions_answer_from_original_evidence(question, source):
    assert interpret_prompt(question)['status'] == 'expanded'
    result = generate(question, [('a', source)])
    assert result['text'] == source and result['verified']


@pytest.mark.parametrize('question', [
    'Where would I not encounter the coastal moth?',
    'What hue is the coastal moth if it is wet?',
    'Where would I encounter that lobster?',
    'Where would I encounter the bank?',
])
def test_negation_conditions_references_and_ambiguous_senses_are_not_expanded(question):
    result = interpret_prompt(question)
    assert not result['variants'] and result['canonical'] == question


def test_antonyms_are_labeled_without_becoming_synonyms():
    question = 'Is business class allowed?'
    result = interpret_prompt(question)
    assert result['canonical'] == question and result['variants'] == []
    assert result['terms'] == [dict(word='allowed', relation='antonym', target='forbidden', sense='permission')]


def test_missing_fact_is_still_missing_after_dictionary_expansion():
    result = generate('Where would I encounter the coastal moth?', [('a', 'The coastal moth is blue.')])
    assert result['status'] == 'missing' and not result['verified']


def test_variant_is_encoded_with_same_scope_and_original_prompt_is_preserved(monkeypatch):
    import cpu_llm.pipeline as pipeline
    monkeypatch.setattr(pipeline, '_hits_for_named_article', lambda *args: None)
    monkeypatch.setattr(pipeline, '_with_tagged_paragraphs', lambda a, m, h: h)
    encoded, searches = [], []
    def encode(text):
        encoded.append(text)
        return np.zeros(1024)
    def search(text, allowed, **kwargs):
        searches.append((text, allowed, kwargs['as_of']))
        return [] if 'encounter' in text else [dict(document_id='public-a', chunk_text='The coastal moth lives in Norway.', final_score=.8)]
    index = SimpleNamespace(encode_query=encode, search_allowed=search, db=SimpleNamespace())
    appliance = SimpleNamespace(index=index, _turn=dict(allowed_sources={'public-a'}, as_of=123),
                                memory=SimpleNamespace(_nodes={}, _edges={}))
    question = 'Where would I encounter the coastal moth?'
    result = _retrieve(appliance)({'message': question})
    assert encoded == [question, 'Where does the coastal moth live?']
    assert all(scope == {'public-a'} and timestamp == 123 for _,scope,timestamp in searches)
    assert result['prompt_intent']['dictionary']['original'] == question
    assert result['passages'][0]['document_id'] == 'public-a'
    assert len(route_prompt(question)['channels']) == 6


def test_dictionary_and_attribute_repair_work_together_through_reply(monkeypatch):
    import cpu_llm.pipeline as pipeline
    from cpu_llm.agents.reply import compose_reply
    monkeypatch.setattr(pipeline, '_hits_for_named_article', lambda *args: None)
    monkeypatch.setattr(pipeline, '_with_tagged_paragraphs', lambda a,m,h: h)
    calls = []
    def search(query, **kwargs):
        calls.append(query)
        text = 'The coastal moth lives in Norway.' if 'habitat' in query else 'The coastal moth is an insect.'
        return [dict(document_id='place' if 'habitat' in query else 'type', chunk_text=text, final_score=.5)]
    index = SimpleNamespace(encode_query=lambda q: np.zeros(1024), search=search, db=SimpleNamespace())
    appliance = SimpleNamespace(index=index, _turn={}, memory=SimpleNamespace(_nodes={}, _edges={}))
    question = 'Where would I encounter the coastal moth?'
    result = _retrieve(appliance)({'message': question})
    assert result['attribute_search']['status'] == 'answered'
    assert len(calls) == 3
    reply = compose_reply(dict(message=question, guard_decision='allow', **result))
    assert reply['text'] == 'From place:\nThe coastal moth lives in Norway.'
