"""Request satisfaction and proof are invariant across names and producers."""
import pytest

from cpu_llm.answerability import assess
from cpu_llm.agents.reply import compose_reply
from cpu_llm.evidence_judge import finalize_turn
from cpu_llm.prompt_intent import select_channel_answer
from cpu_llm.response_policy import classify_response_request
from cpu_llm.request_planner import separate_request


def rows(*texts):
    return [dict(chunk_id=f'doc-p{i:04}', chunk_text=text) for i, text in enumerate(texts, 1)]


@pytest.mark.parametrize('name', ['Aster', 'Boreal', 'Cypress'])
def test_every_factual_producer_is_checked_for_the_requested_relation(name):
    source = f'The {name} is a survey instrument.'
    wrong = f'The {name} is found in Norway.'
    for ordered in (rows(source, wrong), rows(wrong, source)):
        result = finalize_turn(dict(message=f'What is the {name}?', answer=wrong,
            answer_status='answered', audit_passed=True, guard_decision='allow',
            reply=dict(text=wrong, body=wrong), related=ordered), None)
        assert result['judgment']['outcome'] == 'insufficient_evidence'
        assert wrong not in result['reply']['text']
        assert result['answer'] is None and not result['answer_evidence']
        assert result['judgment']['answer_decision']['outcome'] == 'insufficient_evidence'
        assert result['judgment']['answer_decision']['proof'] == []
        reply = compose_reply(dict(message=f'What is the {name}?', answer=wrong,
            audit_passed=True, guard_decision='allow', related=ordered))
        assert source in reply['text'] and wrong not in reply['text']


def test_identity_copulas_remain_answers_but_actions_and_adjectives_do_not():
    source = 'The European lobster is Homarus gammarus.'
    assert assess('What is the European lobster?', [source])['text'] == source
    for source in ['Mary baked a cake.', 'Mary is ready.', 'Mary is Blue Today.',
                   'Mary repaired a boat known as the Cedar, which is a ferry.']:
        assert assess('Who is Mary?', [source])['answer_status'] == 'insufficient_evidence'
    assert assess('Who is Mary?', ['Mary is also known as Dana.'])['answer_status'] == 'answered'


@pytest.mark.parametrize('verb,past', [('stop', 'stopped'), ('drift', 'drifted'), ('dim', 'dimmed'), ('start', 'started')])
def test_cause_normalization_preserves_the_whole_effect(verb, past):
    source = f'The Aster {past} because its battery failed.'
    answer = select_channel_answer(f'Why did the Aster {verb}?', rows(source))
    assert answer['answer_status'] == 'answered'
    assert source in answer['text']
    assert select_channel_answer(f'Why did the Boreal {verb}?', rows(source))['answer_status'] == 'insufficient_evidence'
    assert select_channel_answer('Why did the Aster turn?', rows(source))['answer_status'] == 'insufficient_evidence'


@pytest.mark.parametrize('verb', ['have', 'contain', 'include', 'possess'])
def test_declared_possession_wording_shares_the_same_complete_join(verb):
    answer = assess(f'What does the Aster {verb}?', rows(
        'The Aster is a survey instrument.', 'Every survey instrument has a lens.'))
    assert answer['answer_status'] == 'answered'
    assert len(answer['decision']['proof']) == 2


def test_attribute_slots_never_answer_with_a_neighboring_type_or_ranking():
    for attribute, source, value in [('shape', 'The case is round.', 'round'),
                                      ('material', 'The case is brass.', 'brass')]:
        answer = assess(f'What {attribute} is the case?', [source, 'The case is a container.'])
        assert answer['text'] == source
        final = finalize_turn(dict(message=f'What {attribute} is the case?', answer_status='answered',
            reply=dict(text=source, body=source), related=rows(source)), None)
        assert final['judgment']['outcome'] == 'answered'
        assert final['answer_evidence'] and final['judgment']['request_contract']['relation'] == 'attribute:'+attribute
    assert assess('What material is the case?', ['The case is copper.'])['answer_status'] == 'insufficient_evidence'
    assert assess('What material is the case?', ['The material of the case is copper.'])['answer_status'] == 'answered'


def test_unchanged_specialist_output_publishes_only_the_selected_sources():
    source = 'The Aster is white.'
    result = finalize_turn(dict(message='Summarize the Aster.', guard_decision='allow', summarize=True,
        answer_status='answered', brief=dict(summary=source, sources=['doc-p0001']),
        reply=dict(text='Summary:\n'+source, body=source), related=rows(source, 'The Boreal is blue.')), None)
    assert result['reply']['text'] == 'Summary:\n'+source
    assert {item['document_id'] for item in result['answer_evidence']} == {'doc-p0001'}
    assert result['reply']['answer_evidence'] == result['answer_evidence']


def test_definition_commands_use_the_same_definition_and_proof_contract():
    for question in ['Define survey instrument.', 'What does survey instrument mean?']:
        answer = assess(question, ['A survey instrument is a logged device.'])
        assert answer['answer_status'] == 'answered'
        assert answer['decision']['request']['relation'] == 'is_a'


def test_presentation_prefixes_do_not_create_extra_tasks_or_change_the_slot():
    plan = separate_request('In one sentence, what is the Aster?')
    assert plan['status'] == 'single'
    assert classify_response_request('Overview: Where does the Aster live?')['content_query'] == 'Where does the Aster live?'
    assert classify_response_request('Give a detailed account of the Aster color.')['content_query'] == 'What color is the Aster?'
    assert classify_response_request('Briefly list the Aster color.')['content_query'] == 'What color is the Aster?'


def test_creative_words_in_factual_subjects_are_not_instructions():
    from cpu_llm.classifier import creative_writing_trigger
    for text in ['What is the story archive?', 'What color is the poem cover?',
                 'Do not write a poem. What is the Aster?']:
        assert not creative_writing_trigger(text)
    assert creative_writing_trigger('Write a poem about the Aster.')
