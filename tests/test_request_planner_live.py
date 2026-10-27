"""Independent question retrieval through the real CPU/pgvector pipeline."""
import os
import uuid
import pytest

from cpu_llm.pipeline import Appliance
from cpu_llm.access import CallerContext
from cpu_llm.documents import SourceDocument

pytestmark = pytest.mark.skipif(os.environ.get('CPU_LLM_LIVE_TESTS') != '1',
    reason='requires cached encoder and a disposable PostgreSQL database')


@pytest.fixture(scope='module')
def app():
    with Appliance(namespace='request_plan_' + uuid.uuid4().hex[:8]) as instance:
        instance.ingest(SourceDocument('iris-guide', (
            'The Iris is a ferry.', 'The Iris is white.',
            'The Iris is found in Norway.', 'Every ferry lives for 30 years.')))
        instance.ingest(SourceDocument('iris-private', ('The Iris is blue.',)))
        yield instance


def test_scoped_questions_have_separate_intents_and_complete_join_evidence(app):
    caller = CallerContext.make(app.tenant_id, 'alice', ['iris-guide-p'])
    result = app.ask('What color is the Iris, where does it live, and how long does it live? Answer in three bullets.', caller=caller)
    tasks = result['task_results']
    assert len(tasks) == 3
    assert result['judgment']['complete']
    assert ['has_color', 'lives_in', 'has_lifespan'] == [
        row['result']['judgment']['relation'] for row in tasks]
    assert 'white' in tasks[0]['result']['reply']['text']
    assert 'Norway' in tasks[1]['result']['reply']['text']
    assert '30 years' in tasks[2]['result']['reply']['text']
    assert {'iris-guide-p0001', 'iris-guide-p0004'} <= {
        item['document_id'] for item in tasks[2]['result']['answer_evidence']}
    assert 'blue' not in result['reply']['text']
    assert all(row['status'] in {'answered', 'evidence_quote'} for row in tasks)


def test_missing_subquestion_does_not_silently_disappear(app):
    caller = CallerContext.make(app.tenant_id, 'alice', ['iris-guide-p'])
    result = app.ask('What color is the Iris? What does it have?', caller=caller)
    assert result['status'] == 'partial'
    assert 'white' in result['reply']['text']
    assert result['task_results'][1]['status'] == 'insufficient_evidence'
    assert 'do not settle' in result['task_results'][1]['result']['reply']['text']


def test_separate_style_command_does_not_pollute_a_single_factual_query(app):
    caller = CallerContext.make(app.tenant_id, 'alice', ['iris-guide-p'])
    result = app.ask('What color is the Iris? Answer in one bullet.', caller=caller)
    assert result['judgment']['complete']
    assert result['task_results'][0]['result']['judgment']['entity'] == 'iris'
    assert 'white' in result['reply']['text']
    assert result['reply']['text'].startswith('- ')


def test_original_session_resumes_reference_then_runs_remaining_question(app):
    caller = CallerContext.make(app.tenant_id, 'alice', ['iris-guide-p'])
    first = app.ask('Where does it live? How long does the Iris live?', session_id='multi-ref', caller=caller)
    assert first['needs_clarification']
    assert first['clarification']['task_id'] == 'q1'
    assert first['task_results'][1]['status'] == 'pending'
    resumed = app.ask('the Iris', session_id='multi-ref', caller=caller)
    assert resumed['judgment']['complete']
    assert 'Norway' in resumed['task_results'][0]['result']['reply']['text']
    assert '30 years' in resumed['task_results'][1]['result']['reply']['text']


def test_long_background_does_not_displace_question_embeddings(app):
    caller = CallerContext.make(app.tenant_id, 'alice', ['iris-guide-p'])
    prompt = ('Context: ' + 'This document discusses maintenance. ' * 200 + 'The Iris is a ferry.'
              '\nQuestions:\n1. What color is it?\n2. Where does it live?')
    result = app.ask(prompt, caller=caller)
    assert result['judgment']['complete']
    assert 'white' in result['task_results'][0]['result']['reply']['text']
    assert 'Norway' in result['task_results'][1]['result']['reply']['text']
    assert all(len(task['query']) < 40 for task in result['request_plan']['tasks'])
