from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from cpu_llm.access import CallerContext
from cpu_llm.invention import NOTE, invention_seed
from cpu_llm.pipeline import Appliance


def appliance(extra=()):
    app = object.__new__(Appliance)
    app.tenant_id = 'test'
    app.small_talk = False
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision='allow'))
    rows = [dict(document_id=f'helios-p{i:04}', chunk_text=text) for i, text in enumerate([
        'Helios is a backup service.', 'Helios uses PostgreSQL for metadata.',
        'Helios stores encrypted backups.', *extra], 1)]
    pipeline = SimpleNamespace(encode_texts=lambda labels: np.ones((len(labels), 1024)),
                               enabled_channels={'dense': True, 'identity': True})
    app.index = SimpleNamespace(strict_source_rows=Mock(return_value=(rows, 123)), pipeline=pipeline)
    return app


@pytest.mark.parametrize('prompt', [
    'Imagine Helios.', 'imagine helios', 'Imagine a new design from the relationships around Helios.',
    'Create a new concept from Helios.',
    'Invent a new concept from Helios.',
    'Invention: Helios.', 'Invention for Helios.',
    'Create something new from the input terms Helios and encrypted backups.',
])
def test_triggers_compose_a_cited_hypothesis_with_six_channels(prompt):
    app = appliance()
    result = app.ask(prompt)
    receipt = result['invention']
    assert receipt['triggered'] and receipt['potentially_nondeterministic']
    assert result['answer_evidence'] == []
    [idea] = receipt['proposals']
    assert idea['qualification'] == 'hypothesis'
    assert 'encryption-key version in PostgreSQL metadata' in idea['proposal']
    assert {p['document_id'] for p in idea['premises']} == {'helios-p0002', 'helios-p0003'}
    assert {p['relation'] for p in receipt['relationships']} == {'is_a', 'uses', 'stores'}
    assert len(idea['channels']) == 6 and idea['channels']['dense']['vector_score'] is not None
    assert not any(channel['symbolic_supported'] for channel in idea['channels'].values())
    assert result['reply']['text'].endswith(NOTE)
    app.index.strict_source_rows.assert_called_once()


@pytest.mark.parametrize('prompt', [
    'Imagine a story about Helios.', 'Imagine a new story about Helios.',
    'What new concepts exist for Helios?', 'Do not invent a new concept.',
    'Explain "Create a new concept from Helios".', 'new',
    'What does invention mean?', 'Invention history of Helios',
])
def test_other_intents_do_not_trigger_invention(prompt):
    assert invention_seed(prompt) is None


def test_api_and_strict_precedence():
    app = appliance()
    assert app.ask('Helios', invent=True)['invention']['proposals']
    app.index.strict_source_rows.reset_mock()
    result = app.ask('Create a new concept from Helios.', strict_evidence=True)
    assert result['answer_status'] == 'unsupported' and 'invention' not in result
    app.index.strict_source_rows.assert_not_called()


def test_story_request_keeps_existing_route():
    app = appliance()
    app._ask_single = Mock(return_value=dict(answer_status='answered', reply=dict(text='Story route.')))
    assert 'invention' not in app.ask('Imagine a story about Helios.')
    app._ask_single.assert_called_once()
    app.index.strict_source_rows.assert_not_called()


def test_factual_response_has_no_invention_note():
    app = appliance()
    app._ask_single = Mock(return_value=dict(answer_status='answered', reply=dict(text='Helios is a backup service.')))
    result = app.ask('What is Helios?')
    assert NOTE not in result['reply']['text'] and 'invention' not in result


def test_existing_relationship_is_suppressed_and_empty_run_has_note():
    app = appliance(['PostgreSQL already tracks encryption key versions for encrypted backups.'])
    result = app.ask('Create a new concept from Helios.')
    assert result['invention']['proposals'] == []
    assert result['reply']['text'].endswith(NOTE)


def test_taxonomy_adds_category_premises_with_their_own_subject():
    app = appliance(['A backup service uses a retention catalog.'])
    result = app.ask('Imagine Helios.')
    assert result['invention']['taxonomy'] == ['backup service']
    assert any(premise['subject'] == 'A backup service' and premise['object'] == 'a retention catalog'
               for proposal in result['invention']['proposals'] for premise in proposal['premises'])
    assert result['answer_evidence'] == []


def test_scoped_snapshot_excludes_unauthorized_premises():
    app = appliance()
    caller = CallerContext.make('test', 'user', {'helios-p0002'})
    result = app.ask('Imagine Helios.', caller=caller, as_of=42)
    assert not result['invention']['proposals']
    assert {p['document_id'] for p in result['invention']['relationships']} == {'helios-p0002'}
    app.index.strict_source_rows.assert_called_once_with(caller.allowed_sources, as_of=42)


def test_mixed_request_routes_once_and_discloses_after_html_layout():
    app = appliance()
    app._ask_single = Mock(return_value=dict(answer_status='answered', reply=dict(text='Helios is a backup service.')))
    result = app.ask('What is Helios? Create a new concept from Helios. Use an HTML table.')
    assert len(result['task_results']) == 2
    assert result['invention']['task_ids'] == ['q2']
    assert result['reply']['text'].count(NOTE) == 1
    assert result['reply']['text'].endswith(f'<p>{NOTE}</p>')
    app._ask_single.assert_called_once()
    app.index.strict_source_rows.assert_called_once()


def test_partial_run_still_discloses():
    app = appliance()
    app.index.strict_source_rows.side_effect = ValueError('snapshot limit')
    result = app.ask('Imagine Helios.')
    assert not result['invention']['complete']
    assert result['reply']['text'].endswith(NOTE)
