from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cpu_llm.classifier import specialist_plan
from cpu_llm.hypothesis_routes import natural_deepen_target, natural_frontier_topic
from cpu_llm.pipeline import Appliance


@pytest.fixture(autouse=True)
def regex_parser(monkeypatch):
    monkeypatch.setenv('FRONTIER_PARSER', 'regex')


ROWS = [dict(document_id=f'doc{i}-p0001', chunk_text=text) for i, text in enumerate([
    'Memory bandwidth limits inference throughput.', 'Inference throughput drives serving revenue.',
    'HBM supply constrains memory bandwidth.', 'Batch size limits inference throughput.',
    'Quantization reduces serving revenue in some deployments.'], 1)]


def appliance():
    app = object.__new__(Appliance)
    app.tenant_id = 'test'
    app.small_talk = False
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision='allow'))
    app.index = SimpleNamespace(strict_source_rows=Mock(return_value=(ROWS, 123)))
    return app


@pytest.mark.parametrize('message, topic', [
    ('Explore the open questions of AI energy bottlenecks.', 'AI energy bottlenecks'),
    ('Could you please map the hypothesis space for grokking?', 'grokking'),
    ('What unexplored connections exist around memory bandwidth?', 'memory bandwidth'),
    ('Which untested mechanisms are there behind benign overfitting?', 'benign overfitting'),
    ('Find untested hypotheses about integrated information theory.', 'integrated information theory'),
    ('Suggest some non-obvious ideas about inference throughput.', 'inference throughput'),
    ("What don't we know about grokking?", 'grokking'),
    ('What does the literature not know about implicit bias?', 'implicit bias'),
    ('What might be true about AI compute cost that no paper states?', 'AI compute cost'),
    ('Frontier hypotheses about training data supply.', 'training data supply'),
    ("I'd like to know what unexplored connections exist around grokking.", 'grokking'),
    ('I was wondering what hidden mechanisms exist behind double descent?', 'double descent'),
])
def test_natural_prompts_route_to_frontier(message, topic):
    assert natural_frontier_topic(message) == topic
    plan = specialist_plan(message)
    assert plan['primary_candidate'] == 'frontier' and plan['seeds']['frontier'] == topic


@pytest.mark.parametrize('message, hypothesis', [
    ('Check this hypothesis: memory bandwidth may constrain serving revenue through inference throughput.',
     'memory bandwidth may constrain serving revenue through inference throughput'),
    ('Could you test the idea that batch size and quantization may jointly constrain serving revenue?',
     'batch size and quantization may jointly constrain serving revenue'),
    ('Is it plausible that HBM supply may constrain inference throughput through memory bandwidth?',
     'HBM supply may constrain inference throughput through memory bandwidth'),
])
def test_natural_prompts_route_to_deepen(message, hypothesis):
    assert natural_deepen_target(message) == hypothesis
    assert specialist_plan(message)['primary_candidate'] == 'deepen'


@pytest.mark.parametrize('message', [
    'What is the frontier of AI?', 'Explain grokking.', 'Is it true that the Kestrel has a radio?',
    'Check the report about Helios.', 'What do we know about grokking?', 'Tell me about open questions.',
])
def test_ordinary_questions_are_not_claimed(message):
    plan = specialist_plan(message)
    assert plan['seeds']['frontier'] is None and plan['seeds']['deepen'] is None


@pytest.mark.parametrize('message, owner', [
    ('Generate new hypotheses about grokking.', 'invention'),        # an existing invention trigger
    ('Propose a testable hypothesis about memory bandwidth.', 'invention'),
    ('Brainstorm ideas for Helios.', 'invention'),
    ('Investigate unexplored connections around grokking.', 'research'),
    ('Research the open questions of grokking.', 'research'),
    ('Nammade: light speed.', 'nammade'), ('CrossDomain: elephant', 'crossdomin'),
    ('Imagine Helios.', 'invention'), ('Invention: Fernhouse.', 'invention'),
])
def test_existing_routes_keep_their_prompts(message, owner):
    plan = specialist_plan(message)
    assert plan['primary_candidate'] == owner
    assert plan['seeds']['frontier'] is None and plan['seeds']['deepen'] is None


def test_ask_routes_natural_prompts_end_to_end():
    app = appliance()
    frontier = app.ask('What unexplored connections exist around inference throughput?')
    assert frontier['frontier']['topic'] == 'inference throughput' and frontier['answer_status'] in {
        'hypotheses', 'shortage'}
    deepen = app.ask('Check this hypothesis: HBM supply may constrain inference throughput through memory bandwidth.')
    assert deepen['answer_status'] == 'deepened' and deepen['deepen']['pattern'] == 'chain'


def test_numbered_follow_up_selects_a_frontier_hypothesis_in_the_session():
    app = appliance()
    first = app.ask('Frontier: inference throughput.', session_id='s1')
    second_hypothesis = first['frontier']['hypotheses'][1]
    follow_up = app.ask('Deepen idea 2.', session_id='s1')
    assert follow_up['answer_status'] == 'deepened'
    assert follow_up['deepen']['terms']['c'] in second_hypothesis['text']
    assert app.ask('Check hypothesis #9.', session_id='s1')['answer_status'] == 'needs_clarification'
    assert 'session_id' in app.ask('Deepen idea 1.')['reply']['text']
    assert 'Frontier' in app.ask('Deepen idea 1.', session_id='other')['reply']['text']
