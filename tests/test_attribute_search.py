from types import SimpleNamespace
import numpy as np
import pytest

from cpu_llm.attribute_search import retrieve_missing_attribute
from cpu_llm.model01.generator import generate
from cpu_llm.prompt_intent import route_prompt


def row(key, text):
    return dict(document_id=key, chunk_text=text, final_score=.5)


def test_second_search_uses_subject_then_verified_class_and_stops_at_direct_fact():
    initial = [row('type', 'The coastal moth is an insect.')]
    calls = []
    def search(query, **kwargs):
        calls.append(query)
        return [row('age', 'The coastal moth lives for up to 12 months.')] if query.startswith('insect ') else []
    index = SimpleNamespace(encode_query=lambda q: np.zeros(1024), search=search)
    question = 'How long does the coastal moth live?'
    found, report = retrieve_missing_attribute(index, question, initial, route_prompt(question))
    assert len(calls) == 2 and calls[1].startswith('insect lifespan')
    assert report['status'] == 'answered'
    answer = generate(question, [(r['document_id'], r['chunk_text']) for r in found])
    assert answer['text'] == 'The coastal moth lives for up to 12 months.'


@pytest.mark.parametrize('group_fact', [
    'Some insects live for 12 months.', 'Insects live for 12 months.',
    'The average lifespan of insects is 12 months.',
])
def test_category_data_is_not_automatically_species_data(group_fact):
    result = generate('How long does the coastal moth live?', [
        ('type', 'The coastal moth is an insect.'), ('group', group_fact)])
    assert result['status'] == 'missing' and not result['verified']


def test_explicit_universal_rule_preserves_both_join_premises():
    # Synthetic rule fixture, not a biological claim.
    source = [('type', 'The fictional moth is a fictional insect.'),
              ('rule', 'All fictional insects live for 12 months.')]
    result = generate('How long does the fictional moth live?', source)
    assert result['verified']
    assert all(sentence in result['text'] for _, sentence in source)
    reverse = generate('How long does the fictional insect live?', [
        ('type', 'The fictional moth is a fictional insect.'),
        ('age', 'The fictional moth lives for 12 months.')])
    assert reverse['status'] == 'missing'


def test_repair_preserves_access_scope_time_and_does_not_leak_forbidden_rows():
    calls = []
    def scoped(query, allowed, **kwargs):
        calls.append((allowed, kwargs['as_of']))
        return [row('secret', 'The coastal moth lives for 12 months.')]
    index = SimpleNamespace(encode_query=lambda q: np.zeros(1024), search_allowed=scoped)
    question = 'How long does the coastal moth live?'
    found, report = retrieve_missing_attribute(index, question, [row('public-type', 'The coastal moth is an insect.')],
        route_prompt(question), allowed={'public'}, as_of=123)
    assert calls and all(scope == {'public'} and time == 123 for scope,time in calls)
    assert all(r['document_id'].startswith('public') for r in found)
    assert report['status'] == 'insufficient_evidence'
    calls.clear()
    retrieve_missing_attribute(index, question, [], route_prompt(question), allowed=set())
    assert calls == []


def test_settled_or_conflicting_facts_do_not_trigger_repair():
    def fail(*args, **kwargs):
        raise AssertionError('no retry should be needed')
    index = SimpleNamespace(encode_query=fail, search=fail)
    q = 'How long does the coastal moth live?'
    _, report = retrieve_missing_attribute(index, q, [row('a', 'The coastal moth lives for 12 months.')], route_prompt(q))
    assert report['status'] == 'already_settled'
    conflict = generate(q, [('a', 'The coastal moth lives for 12 months.'), ('b', 'The coastal moth lives for 6 months.')])
    assert conflict['status'] == 'conflicting'


def test_repair_replans_when_first_retry_discovers_type_membership():
    calls = []
    def search(query, **kwargs):
        calls.append(query)
        return [row('type', 'The fictional moth is a fictional insect.')] if len(calls) == 1 else [
            row('age', 'All fictional insects live for 12 months.')]
    index = SimpleNamespace(encode_query=lambda q: np.zeros(1024), search=search)
    q = 'How long does the fictional moth live?'
    found, trace = retrieve_missing_attribute(index, q, [], route_prompt(q))
    assert calls[1].startswith('fictional insect lifespan')
    assert trace['answer_reason'] == 'universal_membership_join'
    assert len(trace['answer_evidence']) == 2


@pytest.mark.parametrize('question, terms, source', [
    ('Where does the coastal moth live?', 'habitat', 'The coastal moth lives in Norway.'),
    ('What color is the coastal moth?', 'color', 'The coastal moth is blue.'),
    ('What does the coastal moth have?', 'parts', 'The coastal moth has wings.'),
])
def test_other_supported_attributes_have_a_second_retrieval(question, terms, source):
    calls = []
    def search(query, **kwargs):
        calls.append(query)
        return [row('answer', source)]
    index = SimpleNamespace(encode_query=lambda q: np.zeros(1024), search=search)
    found, trace = retrieve_missing_attribute(index, question, [], route_prompt(question))
    assert terms in calls[0]
    assert trace['status'] == 'answered' and len(calls) == 1
    assert generate(question, [(r['document_id'], r['chunk_text']) for r in found])['text'] == source


def test_a_direct_possession_still_loads_the_universal_rule():
    initial = [
        row('own', 'The fictional moth has a long proboscis.'),
        row('type', 'The fictional moth is a fictional insect.'),
    ]
    calls = []

    def search(query, **kwargs):
        calls.append(query)
        if query.startswith('fictional insect '):
            return [row('rule', 'All fictional insects have wings.')]
        return []

    index = SimpleNamespace(encode_query=lambda q: np.zeros(1024), search=search)
    question = 'What does the fictional moth have?'
    found, report = retrieve_missing_attribute(index, question, initial, route_prompt(question))
    assert any(call.startswith('fictional insect ') for call in calls)
    assert report['answer_reason'] == 'universal_membership_join'
    text = generate(question, [(r['document_id'], r['chunk_text']) for r in found])['text']
    assert 'long proboscis' in text
    assert 'wings' in text
    assert 'fictional insect' in text


@pytest.mark.parametrize('question, rule', [
    ('Where does the fictional moth live?', 'All fictional insects live in Norway.'),
    ('What color is the fictional moth?', 'All fictional insects are blue.'),
    ('What does the fictional moth have?', 'All fictional insects have wings.'),
])
def test_other_attributes_require_explicit_universal_applicability(question, rule):
    membership = ('type', 'The fictional moth is a fictional insect.')
    answer = generate(question, [membership, ('rule', rule)])
    assert answer['verified'] and membership[1] in answer['text'] and rule in answer['text']
    unsupported = generate(question, [membership, ('some', rule.replace('All ', 'Some '))])
    assert unsupported['status'] == 'missing'
