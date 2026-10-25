import json
import sqlite3

import numpy as np
import pytest

from cpu_llm.connection_channels import CHANNEL_SLICES, evaluate_connection
from cpu_llm.knowledge_graph import Fact, KnowledgeGraph, extract_facts
from cpu_llm.pipeline import _with_graph_paragraphs
from types import SimpleNamespace


def test_one_entity_has_several_independent_channels_and_epistemic_is_separate(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'facts.db')
    graph.replace([('notes', 'Caligo marina, known as the coastal moth, is a species of insect. Caligo marina causes damage. Caligo marina differs from the forest moth.')])
    memberships = graph.word_channels('Caligo marina')
    assert all(memberships[name] for name in ('relational', 'hyperbolic', 'identity', 'causal', 'disentangled'))
    assert memberships['dense'] == []
    alias = next(f for f in graph.neighborhood('coastal moth') if f.relation == 'alias_of')
    assert alias.channels == {'relational', 'identity'}
    assert alias.channel_assessment['channels']['identity']['head_enabled'] is False
    assert alias.channel_assessment['channels']['identity']['vector_status'] == 'disabled'
    assert alias.channel_assessment['epistemic']['truth_score'] is None
    assert 'epistemic' not in alias.channel_assessment['channels']
    assert graph.word_channels('coastal moth', allowed=set())['identity'] == []


def test_disabled_or_uncalibrated_heads_do_not_turn_true_from_numbers():
    fact = Fact('moth', 'has_color', 'blue', 'a', 'The moth is blue.')
    tensor = np.ones(1024) * 0.01
    disabled = evaluate_connection(fact, left_tensor=tensor, right_tensor=tensor,
                                   thresholds={name: -1 for name in CHANNEL_SLICES})
    assert disabled['channels']['dense']['active'] is None
    assert disabled['channels']['dense']['vector_score'] is None
    enabled = evaluate_connection(fact, enabled_channels={'dense': True}, left_tensor=tensor, right_tensor=tensor)
    assert enabled['channels']['dense']['vector_status'] == 'uncalibrated'
    assert enabled['channels']['dense']['active'] is None
    assert enabled['channels']['relational']['active'] is True


def test_all_six_vector_predicates_can_be_evaluated_without_exclusive_assignment():
    fact = Fact('moth', 'has_color', 'blue', 'a', 'The moth is blue.')
    tensor = np.ones(1024) * 0.01
    result = evaluate_connection(fact, enabled_channels={name: True for name in CHANNEL_SLICES},
        left_tensor=tensor, right_tensor=tensor, thresholds={name: -0.1 for name in CHANNEL_SLICES},
        causal_matrix=np.eye(128))
    assert set(result['channels']) == set(CHANNEL_SLICES)
    assert all(signal['vector_match'] is True for signal in result['channels'].values())
    assert all(signal['active'] is True for signal in result['channels'].values())
    assert result['epistemic']['truth_score'] is None
    # Geometry has a domain; finite but out-of-ball vectors are not evidence.
    bad = evaluate_connection(fact, enabled_channels={'hyperbolic': True},
        left_tensor=np.ones(1024), right_tensor=np.ones(1024), thresholds={'hyperbolic': 0})
    assert bad['channels']['hyperbolic']['vector_match'] is None


def test_persistence_channel_filtering_and_word_lookup(tmp_path):
    path = tmp_path / 'facts.db'
    graph = KnowledgeGraph(path, enabled_channels={'dense': True}, encode_texts=lambda texts: np.ones((len(texts), 1024)) * 0.01,
                           thresholds={'dense': 0.8})
    graph.replace([('notes', 'The coastal moth is a species of insect. The coastal moth causes damage.')])
    reopened = KnowledgeGraph(path)
    facts = reopened.neighborhood('coastal moth', channels={'hyperbolic'})
    assert len(facts) == 1 and facts[0].relation == 'is_a'
    assert 'dense' in facts[0].channels
    assert reopened.word_channels('moth')['causal']
    with sqlite3.connect(path) as conn:
        payload = json.loads(conn.execute('SELECT channel_data FROM facts LIMIT 1').fetchone()[0])
    assert payload['channels']['dense']['vector_match'] is True


def test_legacy_schema_migrates_and_source_mismatch_is_not_supported(tmp_path):
    path = tmp_path / 'old.db'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE facts (subject TEXT, relation TEXT, object TEXT, document_id TEXT, sentence TEXT)')
        conn.execute("INSERT INTO facts VALUES ('moth','is_a','insect','a','The moth is an insect.')")
    assert 'hyperbolic' in KnowledgeGraph(path).neighborhood('moth')[0].channels
    forged = evaluate_connection(Fact('moth', 'alias_of', 'fox', 'a', 'The moth is blue.'))
    assert forged['channels']['identity']['active'] is None
    assert forged['epistemic']['source_supported'] is False
    with pytest.raises(ValueError):
        evaluate_connection(Fact('moth', 'has_color', 'blue', 'a', 'The moth is blue.'), thresholds={'dense': float('nan')})


def test_causality_keeps_direction_and_uncertain_claims_are_not_positive():
    facts = extract_facts('a', 'Heavy rain causes flooding. Heavy rain might cause flooding.')
    assert len(facts) == 1
    assert facts[0].subject == 'Heavy rain' and facts[0].object == 'flooding'
    assert facts[0].channels == {'causal', 'relational'}


def test_already_retrieved_hit_keeps_score_and_gains_channel_evidence(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'facts.db')
    sentence = 'The coastal moth is a species of insect.'
    graph.replace([('a', sentence)])
    def no_fetch(ids):
        raise AssertionError('existing evidence must not be fetched again')
    appliance = SimpleNamespace(knowledge_graph=graph, index=SimpleNamespace(db=SimpleNamespace(get_by_ids=no_fetch)))
    hit = dict(document_id='a', chunk_text=sentence, final_score=0.87)
    rows = _with_graph_paragraphs(appliance, 'coastal moth', [hit])
    assert rows[0]['final_score'] == 0.87
    assert rows[0]['graph_evidence'][0]['channels'] == ['hyperbolic', 'relational']
    assert rows[0]['graph_evidence'][0]['channel_assessment']['epistemic']['truth_score'] is None
