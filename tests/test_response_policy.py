"""Request depth is distinct from factual intent and evidence validity."""
from types import SimpleNamespace
import threading

import numpy as np
import pytest

from cpu_llm.response_policy import classify_response_request


@pytest.mark.parametrize('question, detail, query', [
    ('Briefly explain the Cedar.', 'brief', 'Tell me about the Cedar.'),
    ('Explain the Cedar in detail.', 'detailed', 'Tell me about the Cedar'),
    ('Tell me about the Cedar in detail.', 'detailed', 'Tell me about the Cedar'),
    ('Give a comprehensive overview of the Cedar.', 'detailed', 'Tell me about the Cedar.'),
    ('What color is the Cedar in detail?', 'detailed', 'What color is the Cedar'),
    ('In one sentence: What color is the Cedar?', 'standard', 'What color is the Cedar?'),
])
def test_explicit_style_is_separated_from_the_question(question, detail, query):
    plan = classify_response_request(question)
    assert plan['detail'] == detail
    assert plan['content_query'] == query
    assert plan['explicit']


@pytest.mark.parametrize('question', [
    'What color is the Cedar?', 'Why does the lobster have short claws?',
    'What is a long lifespan?', 'What is detailed balance?',
    'What is a short answer?', 'Describe "a comprehensive overview".',
    'Check this refund:\nAmount: 25.00\nCurrency: USD',
])
def test_subject_attributes_and_quoted_terms_do_not_change_depth(question):
    plan = classify_response_request(question)
    assert plan['detail'] == 'standard'
    assert plan['content_query'] == question


def test_item_counts_clamp_work_and_word_limits_are_not_claimed_enforced():
    plan = classify_response_request('Explain the Cedar in three bullet points.')
    assert plan['mode'] == 'overview'
    assert plan['format'] == 'bullets'
    assert plan['item_budget'] == 3
    assert plan['content_query'] == 'Tell me about the Cedar'
    assert classify_response_request('List the Cedar facts in 1000 items.')['item_budget'] == 20
    assert classify_response_request('List the Cedar facts in 0 items.')['item_budget'] == 1
    word_plan = classify_response_request('Explain the Cedar in 50 words.')
    assert word_plan['requested_limits'] == {'words': 50}
    assert word_plan['word_limit_enforced'] is False
    assert classify_response_request('Tell me about the Cedar briefly.')['mode'] == 'overview'


def test_latest_explicit_depth_wins_and_negated_style_is_not_a_command():
    assert classify_response_request('Explain the Cedar briefly, then in detail.')['detail'] == 'detailed'
    assert classify_response_request('Explain the Cedar; do not be brief.')['detail'] == 'standard'


def test_required_join_is_not_truncated_to_one_sentence():
    from cpu_llm.model01.generator import generate
    plan = classify_response_request('In one sentence: What does the Cedar have?')
    rows = [('t', 'The Cedar is a municipal ferry.'),
            ('r', 'Every municipal ferry has a life raft.'),
            ('o', 'The Cedar has a diesel engine.')]
    result = generate(plan['content_query'], rows)
    assert all(text in result['text'] for _, text in rows)


def test_planned_overview_does_not_prepend_an_unbounded_old_answer():
    from cpu_llm.agents.reply import compose_reply
    plan = classify_response_request('Briefly explain the Cedar.')
    text = 'The Cedar is white.'
    result = compose_reply(dict(message=plan['content_query'], guard_decision='allow',
        summarize=True, response_plan=plan, answer='The Cedar has a diesel engine.',
        brief=dict(summary=text), related=[dict(chunk_id='c', chunk_text=text)]))
    assert result['text'] == 'Summary:\n' + text
    assert 'diesel' not in result['text']


def test_ask_passes_the_plan_and_content_query_to_the_graph():
    from cpu_llm.clarification import ClarificationLoop
    from cpu_llm.references import ReferenceSessions
    from cpu_llm.pipeline import Appliance
    app = Appliance.__new__(Appliance)
    app.tenant_id = 'test'
    app._bound = threading.local()
    app.clarifications, app.references = ClarificationLoop(), ReferenceSessions()
    app.word_tags = {}
    encoded, states = [], []
    app.index = SimpleNamespace(encode_query=lambda text: encoded.append(text) or np.zeros(1024))
    app.format_sense = SimpleNamespace(classify=lambda text: None)
    def graph(state):
        states.append(state)
        return dict(state, answer_status='insufficient_evidence', answer=None,
                    reply=dict(text='The retrieved passages do not settle that.',
                               answer_status='insufficient_evidence'))
    app.graph = SimpleNamespace(invoke=graph)
    result = app.ask('Explain the Cedar in detail.')
    assert encoded == ['Tell me about the Cedar']
    assert states[0]['summarize'] and not states[0]['explain']
    assert result['response_plan']['sentence_budget'] == 8
    assert app._turn['response_plan']['retrieval_budget'] == 12
    assert result['original_message'] == 'Explain the Cedar in detail.'
    assert result['resolved_query'] == 'Tell me about the Cedar'

    # A presentation control word must not be corrected to a corpus noun.
    app.word_tags = {'bell': {}, 'cedar': {}}
    result = app.ask('Explain the Cedar in detail.')
    assert result['resolved_query'] == 'Tell me about the Cedar'
    assert result['typos'] == []

    result = app.ask('Explain the Cedar in detail? Explain the Rowan in detail? Answer in three sentences.')
    assert [state['response_plan']['sentence_budget'] for state in states[-2:]] == [2, 1]
    assert [state['response_plan']['item_budget'] for state in states[-2:]] == [2, 1]
    assert result['response_plan']['combined_budget']['optional_unit_budget'] == 3


@pytest.mark.parametrize('prompt, expected, kind', [
    ('Briefly explain the Cedar.', 1, 'summary'),
    ('Explain the Cedar in detail.', 8, 'summary'),
    ('Explain the Cedar in three bullet points.', 3, 'list'),
    ('Explain the Cedar in detail.', 2, 'shared_summary'),
])
def test_brief_producer_uses_the_classified_budget(prompt, expected, kind, monkeypatch):
    from cpu_llm.pipeline import _brief
    from cpu_llm.realizer.surface import SemanticSurfaceRealizer
    import cpu_llm.pipeline as pipeline
    import cpu_llm.agents.summarize as summarize
    texts = ['The Cedar has a bell.', 'The Cedar has a deck.', 'The Cedar has a cabin.',
             'The Cedar has a roof.', 'The Cedar has a ramp.', 'The Cedar has a window.',
             'The Cedar has a door.', 'The Cedar has a mast.', 'The Cedar has a rail.']
    rows = [dict(document_id=f'notes-p{i:04}', chunk_text=text, tensor_1024d=np.zeros(1024))
            for i, text in enumerate(texts, 1)]
    monkeypatch.setattr(pipeline, '_brief_rows', lambda *args: rows)
    monkeypatch.setattr(pipeline, '_stored_proposition', lambda *args: None)
    monkeypatch.setattr(summarize, 'rank_by_cognition', lambda props, tensors: props)
    app = SimpleNamespace(_turn={}, memory=SimpleNamespace(find_node_by_label=lambda text: None),
                          cognition=SimpleNamespace(deliberate=lambda q, props, *args: props),
                          realizer=SemanticSurfaceRealizer(),
                          auditor=SimpleNamespace(audit_delivered_output=lambda *args: True))
    plan = classify_response_request(prompt)
    if kind == 'shared_summary':
        plan['sentence_budget'] = 2
        kind = 'summary'
    result = _brief(app)(dict(message=plan['content_query'], tenant_id='test', response_plan=plan,
                             summarize=kind == 'summary', list=kind == 'list'))
    assert result['brief'][kind].count('.') == expected
    assert len(result['brief']['sources']) == expected


def test_requested_bullets_use_one_budgeted_list():
    from cpu_llm.agents.reply import compose_reply
    plan = classify_response_request('Give me three bullet points about the Cedar.')
    lines = ['The Cedar has a bell.', 'The Cedar has a deck.', 'The Cedar has a cabin.']
    reply = compose_reply(dict(message=plan['content_query'], guard_decision='allow',
        response_plan=plan, list=True, brief=dict(list='\n'.join(lines)),
        related=[dict(chunk_id=str(i), chunk_text=text) for i, text in enumerate(lines)]))
    assert reply['text'] == 'List:\n' + '\n'.join('- ' + text for text in lines)


def test_judge_accepts_bullet_presentation_but_rejects_changed_claims():
    from cpu_llm.evidence_judge import finalize_turn
    proof = 'The Cedar has a bell.\nThe Cedar has a deck.'
    def check(text):
        return finalize_turn(dict(message='Tell me about the Cedar.', guard_decision='allow',
            list=True, answer_status='answered', answer=None,
            brief=dict(list=proof), reply=dict(body=proof, text=text, answer_status='answered')), None)
    valid = check('List:\n- The Cedar has a bell.\n- The Cedar has a deck.')
    assert valid['reply']['text'].count('\n- ') == 2
    assert valid['judgment']['outcome'] == 'answered'
    invalid = check('List:\n- The Cedar has a bell.\n- The Cedar does not have a deck.')
    assert 'does not' not in invalid['reply']['text']
