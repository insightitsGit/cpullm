"""Evidence joins: applicability, identity provenance, direction, and conflicts."""
from itertools import permutations
import sqlite3

import pytest

from cpu_llm.knowledge_graph import KnowledgeGraph
from cpu_llm.model01.generator import generate
from cpu_llm.prompt_intent import select_channel_answer


@pytest.mark.parametrize('question,rule', [
    ('How long does the fictional moth live?', 'Every fictional insect lives for 12 months.'),
    ('Where does the fictional moth live?', 'Every fictional insect lives in Norway.'),
    ('What color is the fictional moth?', 'Every fictional insect is blue.'),
    ('What does the fictional moth have?', 'Every fictional insect has wings.'),
])
def test_membership_join_matches_an_independent_sql_join(tmp_path, question, rule):
    # Fictional data. SQL is a test oracle; production selection is a bounded
    # evidence join over extracted facts, not a general SQL query interpreter.
    source = [('member', 'The fictional moth is a fictional insect.'), ('rule', rule),
              ('noise', 'Every fictional fish lives for 80 years.')]
    graph = KnowledgeGraph(tmp_path / 'facts.db')
    graph.replace(source)
    with sqlite3.connect(graph.path) as db:
        rows = db.execute("""
            SELECT m.document_id, r.document_id
            FROM facts AS m INNER JOIN facts AS r
              ON lower(m.object) = lower(substr(r.subject, 7))
            WHERE m.subject = 'The fictional moth' AND m.relation = 'is_a'
              AND r.subject LIKE 'Every %' AND r.relation != 'is_a'
        """).fetchall()
    assert rows == [('member', 'rule')]
    answer = select_channel_answer(question, [dict(document_id=i, text=t) for i,t in source])
    assert answer['answer_status'] == 'answered'
    assert answer['reason'] == 'universal_membership_join'
    assert {item['document_id'] for item in answer['answer_evidence']} == set(rows[0])
    assert generate(question, source)['verified']


@pytest.mark.parametrize('group', [
    'Some fictional insects live for 12 months.',
    'Fictional insects live for 12 months.',
    'Most fictional insects live for 12 months.',
    'If fictional insects live for 12 months.',
    'Every fictional insect might live for 12 months.',
    'Every fictional fish lives for 12 months.',
])
def test_unlicensed_class_fact_cannot_become_an_individual_answer(group):
    answer = generate('How long does the fictional moth live?', [
        ('member', 'The fictional moth is a fictional insect.'), ('rule', group)])
    assert answer['status'] == 'missing' and not answer['verified']


def test_join_can_match_an_explicit_class_alias_and_retains_its_premise():
    chunks = [('member', 'The fictional moth is a test insect.'),
              ('alias', 'Test insect, known as the fictional insect, is a category.'),
              ('rule', 'Every fictional insect lives for 12 months.')]
    answer = select_channel_answer('How long does the fictional moth live?', [
        dict(document_id=i, text=t) for i,t in chunks])
    assert answer['answer_status'] == 'answered'
    assert {item['document_id'] for item in answer['answer_evidence']} == {'member','alias','rule'}


def test_alias_binding_keeps_identity_evidence_without_changing_the_answer_sentence():
    chunks = [dict(document_id='alias', text='Caligo marina, known as the coastal moth, is an insect.'),
              dict(document_id='place', text='Caligo marina lives in Norway.')]
    answer = select_channel_answer('Where does the coastal moth live?', chunks)
    assert answer['text'] == 'Caligo marina lives in Norway.'
    assert {item['document_id'] for item in answer['answer_evidence']} == {'place'}
    assert {item['document_id'] for item in answer['supporting_evidence']} == {'alias'}


def test_alias_depth_is_bounded_independently_of_row_order():
    aliases = [('a', 'Alpha moth, known as beta moth, is an insect.'),
               ('b', 'Beta moth, known as gamma moth, is an insect.'),
               ('c', 'Gamma moth, known as delta moth, is an insect.')]
    for order in permutations(aliases):
        chunks = [dict(document_id=i, text=t) for i,t in order]
        distant = select_channel_answer('Where does alpha moth live?', chunks + [
            dict(document_id='place', text='Delta moth lives in Norway.')])
        assert distant['answer_status'] == 'insufficient_evidence'
        nearby = select_channel_answer('Where does alpha moth live?', chunks + [
            dict(document_id='place', text='Gamma moth lives in Norway.')])
        assert nearby['answer_status'] == 'answered'
        assert {item['document_id'] for item in nearby['answer_evidence'] + nearby['supporting_evidence']} == {'a','b','place'}


@pytest.mark.parametrize('question,direct,rule', [
    ('What color is the fictional moth?', 'The fictional moth is blue.', 'Every fictional insect is red.'),
    ('How long does the fictional moth live?', 'The fictional moth lives for 6 months.',
     'Every fictional insect lives for 12 months.'),
])
def test_direct_fact_cannot_hide_a_conflicting_applicable_universal_rule(question, direct, rule):
    answer = generate(question, [('member','The fictional moth is a fictional insect.'),
                                 ('direct',direct), ('rule',rule)])
    assert answer['status'] == 'conflicting' and not answer['verified']


def test_membership_is_not_reversed_or_shared_between_sibling_entities():
    source = [('type','The fictional moth is a fictional insect.'),
              ('sibling','The fictional beetle is a fictional insect.'),
              ('age','The fictional beetle lives for 12 months.')]
    for entity in ('fictional moth','fictional insect'):
        answer = generate(f'How long does the {entity} live?', source)
        assert answer['status'] == 'missing' and not answer['verified']


def test_join_preserves_numeric_bounds_and_units_without_inventing_an_exact_age():
    source = [('member', 'The fictional moth is a fictional insect.'),
              ('rule', 'Every fictional insect lives for up to 12 months.')]
    answer = generate('How long does the fictional moth live?', source)
    assert answer['verified'] and 'up to 12 months' in answer['text']
    assert '1 year' not in answer['text']


def test_unimplemented_transitive_inferences_do_not_become_facts():
    ancestry = [('member', 'The fictional moth is a fictional insect.'),
                ('class', 'The fictional insect is a fictional animal.'),
                ('rule', 'Every fictional animal lives for 12 months.')]
    assert generate('How long does the fictional moth live?', ancestry)['status'] == 'missing'
    causes = [dict(document_id='a', text='Heavy rain causes flooding.'),
              dict(document_id='b', text='Flooding causes erosion.')]
    result = select_channel_answer('What does heavy rain cause?', causes)
    assert result['answer_status'] == 'answered' and 'erosion' not in result['text']
