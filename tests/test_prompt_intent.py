from types import SimpleNamespace

import numpy as np
import pytest

from cpu_llm.agents.reply import compose_reply
from cpu_llm.knowledge_graph import KnowledgeGraph
from cpu_llm.model01.generator import generate
from cpu_llm.pipeline import _retrieve
from cpu_llm.prompt_intent import route_prompt, select_channel_answer, rank_channel_hits


def test_six_independent_intents_and_disabled_vector_heads():
    intent = route_prompt('What kind of animal is the coastal moth?', query_tensor=np.ones(1024),
                          enabled_channels={'dense': True}, prototypes={name: np.ones(1024) for name in ('dense', 'hyperbolic')})
    assert len(intent['channels']) == 6
    assert intent['channels']['hyperbolic']['active']
    assert intent['channels']['relational']['active']
    assert intent['channels']['hyperbolic']['prototype_score'] is None
    assert intent['channels']['dense']['prototype_score'] == pytest.approx(1.)
    assert intent['requested'] == dict(relation='is_a', direction='subject', entity='coastal moth')
    assert route_prompt('Compare the moth versus the butterfly')['channels']['disentangled']['active']
    assert route_prompt('Who is Ada North?')['channels']['identity']['active']


@pytest.mark.parametrize('question, expected', [
    ('What kind of animal is the coastal moth?', 'Caligo marina, known as the coastal moth, is a species of insect.'),
    ('Where does the coastal moth live?', 'Caligo marina lives in Norway.'),
    ('What color is the coastal moth?', 'Caligo marina is blue.'),
])
def test_same_entity_different_intent_selects_different_sentence(question, expected):
    chunks = [('wiki', 'Caligo marina, known as the coastal moth, is a species of insect. Caligo marina lives in Norway. Caligo marina is blue.'),
              ('noise', 'The red fox is a mammal. The red fox is red.')]
    result = generate(question, chunks)
    assert result['text'] == expected and result['verified']
    reply = compose_reply(dict(message=question, guard_decision='allow', related=[dict(chunk_id=i, chunk_text=p) for i,p in chunks]))
    assert expected in reply['text']
    assert 'red fox' not in reply['text']


def test_causal_direction_and_same_channel_are_not_enough():
    chunks = [dict(document_id='rain', text='Heavy rain causes flooding.'),
              dict(document_id='fire', text='Sparks cause fires.')]
    answer = select_channel_answer('What causes flooding?', chunks)
    assert answer['text'] == 'Heavy rain causes flooding.'
    assert select_channel_answer('What causes heavy rain?', chunks)['answer_status'] == 'insufficient_evidence'
    assert select_channel_answer('What causes earthquakes?', chunks)['answer_status'] == 'insufficient_evidence'
    why = select_channel_answer('Why does the European lobster turn red?', [dict(text='The European lobster turns red because cooking changes its pigments.')])
    assert why['answer_status'] == 'answered'
    assert 'because cooking' in why['text']


def test_an_explicit_average_is_quoted_and_an_individual_does_not_inherit_it():
    average = 'The average display loom lives for 3 years.'
    asked = select_channel_answer('How long does the average display loom live?', [dict(document_id='avg', text=average)])
    assert asked['answer_status'] == 'answered'
    assert asked['text'] == average
    assert asked['decision']['request']['quantifier_scope'] == 'aggregate'
    assert asked['decision']['proof'][0]['document_id'] == 'avg'
    individual = select_channel_answer('How long does the Wicker live?', [
        dict(document_id='kind', text='The Wicker is a survey loom.'),
        dict(document_id='rule', text='Every survey loom lives for 11 years.'),
        dict(document_id='avg', text=average),
    ])
    assert individual['answer_status'] == 'answered'
    assert '11 years' in individual['text']
    assert '3 years' not in individual['text']
    assert individual['decision']['request']['quantifier_scope'] == 'individual'


def test_an_alias_color_proof_includes_the_identity_premise():
    alias = 'Caligo marina, known as the coastal moth, is a species of insect.'
    color = 'Caligo marina is blue.'
    answer = select_channel_answer('What color is the coastal moth?', [
        dict(document_id='alias', text=alias),
        dict(document_id='color', text=color),
    ])
    assert answer['answer_status'] == 'answered'
    assert answer['text'] == color
    proof = {(step['document_id'], step['role']) for step in answer['decision']['proof']}
    assert ('alias', 'identity') in proof
    assert ('color', 'premise') in proof
    assert {item['document_id'] for item in answer['supporting_evidence']} == {'alias'}


def test_a_one_word_color_answers_and_two_colors_conflict():
    copper = select_channel_answer('What color is the Kestrel?', [dict(document_id='c', text='The Kestrel is copper.')])
    assert copper['answer_status'] == 'answered'
    assert copper['text'] == 'The Kestrel is copper.'
    conflict = select_channel_answer('What color is the Kestrel?', [
        dict(document_id='public', text='The Kestrel is copper.'),
        dict(document_id='restricted', text='The Kestrel is crimson.'),
    ])
    assert conflict['answer_status'] == 'conflicting'
    assert 'copper' in conflict['text'] and 'crimson' in conflict['text']


def test_missing_or_conflicting_attribute_does_not_become_a_definition():
    result = generate('What color is the coastal moth?', [('a', 'The coastal moth is an insect.')])
    assert result['status'] == 'missing' and not result['verified']
    conflict = generate('What color is the coastal moth?', [('a', 'The coastal moth is blue.'), ('b', 'The coastal moth is red.')])
    assert conflict['status'] == 'conflicting' and not conflict['verified']


def test_alias_bridges_remain_available_when_prioritizing_requested_channel(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'facts.db')
    graph.replace([('alias', 'Caligo marina, known as the coastal moth, is a species of insect.'),
                   ('place', 'Caligo marina lives in Norway.'), ('color', 'Caligo marina is blue.')])
    facts = graph.neighborhood('Where does the coastal moth live?', intent=route_prompt('Where does the coastal moth live?'))
    assert {'alias', 'place'} <= {fact.document_id for fact in facts}
    assert graph.neighborhood('Where does the coastal moth live?', allowed={'place'}, intent=route_prompt('Where does the coastal moth live?')) == []


def test_full_retrieval_node_routes_expands_ranks_and_reply_selects(tmp_path, monkeypatch):
    import cpu_llm.pipeline as pipeline
    monkeypatch.setattr(pipeline, '_hits_for_named_article', lambda *args: None)
    monkeypatch.setattr(pipeline, '_with_tagged_paragraphs', lambda appliance, message, hits: hits)
    texts = {'alias': 'Caligo marina, known as the coastal moth, is a species of insect.',
             'place': 'Caligo marina lives in Norway.', 'noise': 'The red fox is a mammal.'}
    graph = KnowledgeGraph(tmp_path / 'facts.db')
    graph.replace(list(texts.items()))
    def row(key):
        return dict(document_id=key, chunk_text=texts[key], tensor_1024d=np.zeros(1024), final_score=.9)
    database = SimpleNamespace(get_by_ids=lambda ids: [row(key) for key in ids])
    index = SimpleNamespace(db=database, encode_query=lambda message: np.zeros(1024), search=lambda *args, **kwargs: [row('noise')])
    appliance = SimpleNamespace(index=index, knowledge_graph=graph, _turn={}, memory=SimpleNamespace(_nodes={}, _edges={}))
    question = 'Where does the coastal moth live?'
    result = _retrieve(appliance)({'message': question})
    assert result['prompt_intent']['requested']['relation'] == 'lives_in'
    assert result['passages'][0]['document_id'] == 'place'
    reply = compose_reply(dict(message=question, guard_decision='allow', passages=result['passages']))
    assert 'Caligo marina lives in Norway.' in reply['text'] and 'red fox' not in reply['text']


def test_vector_prototypes_are_cached_and_existing_prompt_encoding_is_reused():
    from cpu_llm.retrieval import VectorPrismIndex
    index = VectorPrismIndex.__new__(VectorPrismIndex)
    batches = []
    def encode(texts):
        batches.append(texts)
        return np.ones((len(texts), 1024)) * .01
    index.pipeline = SimpleNamespace(encode_texts=encode, enabled_channels={'dense': True})
    index.engine = SimpleNamespace(causal_matrix=None)
    for _ in range(2):
        result = index.intent_for('What causes flooding?', query_tensor=np.ones(1024) * .01)
        assert result['channels']['causal']['active']
        assert result['channels']['causal']['prototype_score'] is None
    assert len(batches) == 1 and len(batches[0]) == 6


def test_supported_channel_answer_survives_unsupported_frame_and_empty_rule_reader(monkeypatch):
    import cpu_llm.answering as answering
    monkeypatch.setattr(answering, 'situation_from_chunks', lambda *args: dict(verdict='NONE', text='No rule.'))
    reply = compose_reply(dict(message='What color is the coastal moth?', guard_decision='allow',
        frame=True, frame_result=dict(status='unsupported', text='Unsupported frame.'),
        passages=[dict(document_id='wiki', chunk_text='The coastal moth is blue.')]))
    assert reply['text'] == 'From wiki:\nThe coastal moth is blue.'


def test_taxonomy_selects_definition_instead_of_article_descriptions():
    result = generate('What kind of animal is the coastal moth?', [('wiki',
        'The coastal moth is a highly valued specimen. The coastal moth is a species of insect. The coastal moth is a local attraction.')])
    assert result['text'] == 'The coastal moth is a species of insect.'
