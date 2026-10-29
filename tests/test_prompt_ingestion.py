"""Interpretations preserve request meaning and never become source evidence."""
import pytest

from cpu_llm.prompt_ingestion import PromptInterpreter, SpacyPromptBackend, normalize_question
from cpu_llm.request_planner import separate_request


@pytest.mark.parametrize('text,expected', [
    ('Could you tell me what color the Aster is?', 'what color is the Aster?'),
    ("I'd like to know where the Aster lives.", 'where does the Aster live?'),
    ('I was wondering how long the Aster lives.', 'how long does the Aster live?'),
    ('Please tell me who Mary is.', 'who is Mary?'),
    ('Can you explain what the Aster is?', 'what is the Aster?'),
    ('Tell me the material of the Aster.', 'What material is the Aster?'),
])
def test_human_questions_compile_without_changing_literal_subjects(text, expected):
    result = PromptInterpreter().interpret(text)
    assert result['input_text'] == text
    assert result['query'] == expected
    assert result['transformations'] and result['request']
    assert result['evidence_role'] == 'user request, not verified evidence'


@pytest.mark.parametrize('text', [
    'Could you tell me whether the Aster is safe?',
    'Why does the Aster not stop?',
    'Could you tell me where the Aster lives if it is sick?',
    'Can the Aster live without water?',
    'What color is every Aster?',
    'I want only the average lifespan of the Aster.',
    'Summarize "Could you tell me where the Aster lives?"',
    'Context: the Aster lives in Norway. Can I eat it?',
    'Subtotal: 10\nTax: 2\nTotal: 12',
])
def test_scope_modality_conditions_and_background_are_not_paraphrased_away(text):
    result = normalize_question(text)
    assert result['query'] == text
    assert result['transformations'] == []


def test_explicit_field_list_creates_separate_tasks_with_original_provenance():
    raw = 'Tell me the color, habitat, and lifespan of the Aster.'
    plan = separate_request(raw)
    assert plan['status'] == 'multi'
    assert [task['query'] for task in plan['tasks']] == [
        'What color is the Aster', 'Where does the Aster live', 'How long does the Aster live']
    assert all(task['interpretation']['derivation'] == 'explicit_fields' for task in plan['tasks'])
    for task in plan['tasks']:
        assert raw[task['source_start']:task['source_end']] == task['text']


def test_unknown_field_is_not_silently_omitted():
    plan = separate_request('Tell me the color and friendliness of the Aster.')
    assert plan['status'] == 'needs_clarification'
    assert 'friendliness' in plan['reason']
    assert plan['tasks'] == []


def test_two_entities_in_field_list_require_disambiguation():
    plan = separate_request('Tell me the color and habitat of the Aster and Boreal.')
    assert plan['status'] == 'needs_clarification'


def test_indirect_compound_question_keeps_reference_binding():
    plan = separate_request('Could you tell me what color the Aster is and where it lives?')
    assert plan['status'] == 'multi'
    assert [task['query'] for task in plan['tasks']] == ['what color is the Aster', 'where does aster live']
    assert plan['tasks'][1]['bindings'][0]['antecedent'] == 'aster'


def test_annotations_are_not_rewrite_authority_or_evidence():
    class Backend:
        def annotate(self, text):
            return dict(backend='test', spans=[dict(text='untrusted parser guess')])
    result = PromptInterpreter(Backend()).interpret('What color is the Aster?')
    assert result['query'] == 'What color is the Aster?'
    assert result['request']['entity'] == 'aster'
    assert result['annotations']['spans']
    assert 'answer_evidence' not in result


def test_dependency_proposal_must_account_for_every_request_token():
    raw = 'Give me information about the color of the Aster.'
    class Backend:
        def annotate(self, text):
            return dict(backend='test', candidates=[dict(attribute_start=text.index('the color'),
                attribute_end=text.index(' of'), entity_start=text.index('the Aster'),
                entity_end=text.index('the Aster') + len('the Aster'))])
    interpreter = PromptInterpreter(Backend())
    assert interpreter.interpret(raw)['query'] == 'What color is the Aster?'
    for text in [raw[:-1] + ' in Norway.', raw[:-1] + ' if it is sick.', raw[:-1] + ' and Boreal.']:
        assert interpreter.interpret(text)['query'] == text


def test_configured_missing_parser_is_explicit(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'spacy', None)
    with pytest.raises(RuntimeError, match=r'cpu-llm\[prompt_nlp\]'):
        SpacyPromptBackend().annotate('What color is the Aster?')


def test_auto_backend_reports_missing_assets_and_explicit_rules_do_not_probe(monkeypatch):
    import cpu_llm.prompt_ingestion as module
    monkeypatch.setattr(module.importlib.util, 'find_spec', lambda name: None)
    result = PromptInterpreter().interpret('What color is the Aster?')
    assert result['backend_policy'] == 'auto' and result['fallback_reason']
    assert result['annotations']['backend'] == 'rules'
    def forbidden(name):
        raise AssertionError('explicit rules must not inspect optional model packages')
    monkeypatch.setattr(module.importlib.util, 'find_spec', forbidden)
    assert PromptInterpreter('rules').interpret('Who is Mary?')['fallback_reason'] is None


def test_parser_field_lists_reach_request_planning_without_losing_unknown_fields():
    class Backend:
        def annotate(self, text):
            return dict(backend='test', spans=[dict(kind='noun_phrase', text='the color')])
    interpreter = PromptInterpreter(Backend())
    plan = separate_request('Give me information about the color and habitat of the Aster.', interpreter=interpreter)
    assert [t['query'] for t in plan['tasks']] == ['What color is the Aster', 'Where does the Aster live']
    plan = separate_request('Give me information about the color and friendliness of the Aster.', interpreter=interpreter)
    assert plan['status'] == 'needs_clarification' and 'friendliness' in plan['reason']
