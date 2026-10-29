import pytest

from cpu_llm.output_rendering import extract_layout, render_response
from cpu_llm.prompt_ingestion import PromptInterpreter
from cpu_llm.request_planner import separate_request


@pytest.mark.parametrize('text', [
    'What is a table?', 'Describe "as a table".',
    'Explain the Aster not in a table.', 'Explain the Aster not as a table.',
    'Where is data stored in a table?',
])
def test_table_subject_quoted_text_and_negation_are_not_format_commands(text):
    assert extract_layout(text)['format'] is None
    assert extract_layout(text)['content_query'] == text


def test_parser_and_planner_share_the_format_contract_and_source_offsets():
    text = 'Show the color and habitat of the Aster as a table.'
    parsed = PromptInterpreter('rules').interpret(text)
    assert parsed['output_format'] == 'table' and len(parsed['queries']) == 2
    plan = separate_request(text, interpreter=PromptInterpreter('rules'))
    assert plan['presentation']['format'] == 'table'
    assert [t['query'] for t in plan['tasks']] == ['What color is the Aster', 'Where does the Aster live']
    for task in plan['tasks']:
        assert text[task['source_start']:task['source_end']] == task['text']


def test_table_layout_keeps_original_values_proof_and_escapes_source_markup():
    source = dict(document_id='source-0012', span='The value is 0012 | <script>bad</script>.')
    text = 'From source-0012:\n' + source['span']
    result = dict(message='What is the value?', response_plan=dict(format='table'),
        judgment=dict(outcome='evidence_quote'), answer_status='evidence_quote',
        answer_evidence=[source], reply=dict(text=text, body=text))
    rendered = render_response(result)
    assert rendered['rendered_response']['rows'][0]['response'] == text
    assert rendered['reply']['body'] == text and rendered['answer_evidence'] == [source]
    assert '0012' in rendered['reply']['text'] and r'\|' in rendered['reply']['text']
    assert '<script>' not in rendered['reply']['text'] and '&lt;script&gt;' in rendered['reply']['text']


def test_pending_and_missing_tasks_are_never_filled_by_the_renderer():
    result = dict(message='Questions', response_plan=dict(format='table'),
        judgment=dict(outcome='needs_clarification'), answer_status='needs_clarification',
        reply=dict(text='Which one?'), task_results=[
            dict(query='Where does it live?', status='needs_clarification',
                 result=dict(reply=dict(text='Which one?'), answer_evidence=[])),
            dict(query='What color is the Aster?', status='pending')])
    output = render_response(result)
    assert output['answer_status'] == 'needs_clarification'
    assert output['rendered_response']['rows'][1]['status'] == 'pending'
    assert output['rendered_response']['rows'][1]['evidence'] == []
    assert 'Pending' in output['reply']['text']


@pytest.mark.parametrize('directive,kind,media', [
    ('as a Markdown table', 'table', 'text/markdown'),
    ('as an HTML table', 'table', 'text/html'),
    ('as an HTML report', 'report', 'text/html'),
    ('as a report', 'report', 'text/markdown'),
    ('as bullet points', 'bullets', 'text/markdown'),
    ('as a numbered list', 'numbered', 'text/markdown'),
])
def test_prompt_format_flags_match_interpreter_and_response_policy(directive, kind, media):
    from cpu_llm.response_policy import classify_response_request
    text = 'What color is the Aster ' + directive + '?'
    plan = classify_response_request(text)
    interpreted = PromptInterpreter('rules').interpret(text)
    assert plan['flags'][kind] and plan['flags']['template_requested']
    assert plan['flags']['html'] == (media == 'text/html')
    assert plan['format'] == interpreted['output_format'] == kind
    assert plan['output_media'] == interpreted['output_media'] == media
    assert plan['content_query'] == 'What color is the Aster'


@pytest.mark.parametrize('kind', ['table', 'report'])
def test_html_templates_escape_values_without_evaluating_source_template_syntax(kind):
    source = '{{ 7 * 7 }} <script>bad</script> 0012'
    evidence = dict(document_id='proof-0012', span=source)
    result = dict(message='What is the value?', response_plan=dict(format=kind, output_media='text/html'),
        judgment=dict(outcome='evidence_quote'), answer_status='evidence_quote',
        answer_evidence=[evidence], reply=dict(text=source, body=source))
    output = render_response(result)
    assert output['reply']['media_type'] == 'text/html'
    assert output['rendered_response']['renderer'] == 'jinja2'
    assert '{{ 7 * 7 }}' in output['reply']['text'] and '0012' in output['reply']['text']
    assert '<script>' not in output['reply']['text'] and '&lt;script&gt;' in output['reply']['text']
    assert output['answer_evidence'] == [evidence]
    assert output['rendered_response']['rows'][0]['response'] == source
