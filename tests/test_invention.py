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
    'Guess: Helios.', 'Take a guess about Helios.', 'Could you speculate about Helios?',
    'Hypothesize about Helios.', 'Brainstorm ideas for Helios.',
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
    'Guess the dosage for Helios.', 'What is your guess about Helios?',
    'Do not guess about Helios.', 'Explain "Guess: Helios".',
])
def test_other_intents_do_not_trigger_invention(prompt):
    assert invention_seed(prompt) is None


def test_follow_up_carries_typed_edges_and_expands_from_new_source_terms():
    app = appliance(('PostgreSQL uses write-ahead logging.', 'Write-ahead logging uses segment files.'))
    initial = app.ask('Invention: Helios', session_id='design')
    [idea] = initial['invention']['proposals']
    first = app.ask('Can you explain more?', session_id='design')
    second = app.ask('Go deeper.', session_id='design')

    for result in (first, second):
        assert result['invention']['proposals'] == [idea]
        assert result['answer_evidence'] == []
        assert result['reply']['text'].count(NOTE) == 1
        assert all(p['qualification'] == 'source_statement' for p in result['invention']['relationships'])
    assert idea['qualification'] == 'hypothesis'
    assert (idea['subject'], idea['relation'], idea['object']) == (
        'PostgreSQL', 'could_coordinate_with', 'encrypted backups',
    )
    assert 'write-ahead logging' in first['reply']['text']
    assert 'segment files' not in first['reply']['text']
    assert 'segment files' in second['reply']['text']
    assert 'operating conditions fixed' in second['reply']['text']


def test_cosmology_follow_up_builds_a_question_from_a_directed_source_chain():
    app = appliance()
    docs = [
        'Vesper Array uses pulsar timing residuals for drift detection.',
        'Vesper Array stores simulated gravitational-wave events.',
        'Pulsar timing residuals reveal clock drift.',
        'Clock drift affects event timestamps.',
    ]
    app.index.strict_source_rows.return_value = (
        [dict(document_id=f'cosmos-{i}', chunk_text=text) for i, text in enumerate(docs)], 123,
    )
    app.ask('Invention: Vesper Array.', session_id='cosmos')
    first = app.ask('Can you explain more?', session_id='cosmos')
    second = app.ask('Go deeper.', session_id='cosmos')
    assert 'Can Pulsar timing residuals estimate clock drift' in first['reply']['text']
    assert 'event timestamps' not in first['reply']['text']
    assert 'improve event timestamps' in second['reply']['text']
    assert 'with and without the correction' in second['reply']['text']
    assert second['answer_evidence'] == []
    assert second['reply']['text'].endswith(NOTE)


def test_follow_up_asks_which_proposal_then_remembers_the_selection():
    app = appliance(('Helios uses a scheduler.',))
    app.ask('Invention: Helios', session_id='design')
    question = app.ask('Tell me more.', session_id='design')
    assert question['needs_clarification']
    selection = app.ask('Explain proposal 2.', session_id='design')
    assert selection['invention']['proposal_number'] == 2
    assert app.ask('Tell me more.', session_id='design')['invention']['proposal_number'] == 2


def test_flattened_mechanism_table_expands_a_named_model_and_asks_on_broad_topic():
    app = appliance()
    chunk = ('| Model | Proposed Mechanism | Test | | --- | --- | --- | '
             '| Leptogenesis | Heavy neutrinos decay and the resulting processes convert into a baryon asymmetry ($B$). | Neutrinoless double-beta decay. | '
             '| Electroweak Baryogenesis | A first-order transition drives the system out of thermal equilibrium. | Measure transition effects. |')
    bound = 'A simulated experiment reports a neutrinoless double-beta decay half-life lower bound of 100 years.'
    app.index.strict_source_rows.return_value = ([
        dict(document_id='physics', chunk_text=chunk),
        dict(document_id='lab', chunk_text=bound),
    ], 123)
    broad = app.ask('Invention: Baryogenesis.')
    assert broad['needs_clarification']
    assert 'Leptogenesis, Electroweak Baryogenesis' in broad['reply']['text']
    focused = app.ask('Invention: Leptogenesis.')
    assert focused['status'] == 'hypotheses'
    assert 'A parameter region for Leptogenesis may reproduce the observed baryon asymmetry' in focused['reply']['text']
    assert 'An empty overlap excludes the tested parameter range' in focused['reply']['text']
    [constraint] = focused['invention']['research_brief']['empirical_constraints']
    assert constraint['quote'] == bound
    assert constraint['document_id'] == 'lab'
    assert focused['invention']['research_brief']['qualification'] == 'hypothesis'
    [hypothesis] = focused['invention']['proposals']
    assert 'constraint_scan' not in hypothesis
    assert len(hypothesis['channels']) == 6
    assert not hypothesis['channels']['causal']['symbolic_supported']
    assert focused['answer_evidence'] == []
    [source] = focused['invention']['research_context']
    assert chunk[source['start']:source['end']] == source['quote']

    app.index.strict_source_rows.return_value = ([dict(document_id='physics', chunk_text=chunk)], 123)
    automatic = app.ask('Invention: Leptogenesis.', session_id='boundary')
    [hypothesis] = automatic['invention']['proposals']
    scan = hypothesis['constraint_scan']
    assert scan['sampled'] == 4000
    assert scan['refined_crossing']['binding_limit'] == 'eta_B'
    assert 'Automatic scan' in automatic['reply']['text']
    assert 'Lowest passing sampled point' in app.ask('Can you explain more?', session_id='boundary')['reply']['text']
    assert 'Bisection on a fixed slice' in app.ask('Go deeper.', session_id='boundary')['reply']['text']


def test_unstructured_topic_chunks_yield_cited_research_question_without_claiming_edges():
    app = appliance()
    app.index.strict_source_rows.return_value = ([
        dict(document_id='physics-1', chunk_text='Researchers investigate baryogenesis as an open problem.'),
        dict(document_id='physics-2', chunk_text='The literature discusses competing scenarios for baryogenesis.'),
    ], 123)
    result = app.ask('Invention: Baryogenesis.')
    assert result['status'] == 'research_question'
    assert not result['answer_evidence']
    assert not result['invention']['proposals']
    assert [p['document_id'] for p in result['invention']['research_context']] == ['physics-1', 'physics-2']
    assert result['reply']['text'].endswith(NOTE)


def test_follow_up_revalidates_cited_sources():
    app = appliance()
    app.ask('Invention: Helios', session_id='design')
    rows, when = app.index.strict_source_rows.return_value
    app.index.strict_source_rows.return_value = (rows[:-1], when)
    result = app.ask('Elaborate.', session_id='design')
    assert result['status'] == 'insufficient_evidence'
    assert 'The cited sources changed' in result['reply']['text']
    assert not result['answer_evidence']


def test_crossdomin_requires_two_authorized_domains_and_matching_conventions():
    app = appliance()
    rows = [
        dict(document_id='physics-seesaw-p0001',
             chunk_text='The Casas-Ibarra matrix is complex orthogonal and satisfies R^T R = I.'),
        dict(document_id='mathematics-rotation-p0001',
             chunk_text='For complex z, the rotation built from cos(z) and sin(z) is complex orthogonal and satisfies R^T R = I.'),
    ]
    app.index.strict_source_rows.return_value = (rows, 123)
    prompt = 'CrossDomin: Casas-Ibarra.'
    result = app.ask(prompt)
    assert result['routing']['post_stages'] == ['crossdomin']
    [join] = result['invention']['joins']
    assert [p['domain'] for p in join['premises']] == ['physics', 'mathematics']
    assert result['invention']['check']['passed']
    assert not result['answer_evidence']
    assert result['reply']['text'].endswith(NOTE)
    caller = CallerContext.make(app.tenant_id, 'reader', ['physics-seesaw-p'])
    assert app.ask(prompt, caller=caller)['status'] == 'insufficient_evidence'
    assert app.ask(prompt, strict_evidence=True)['status'] == 'unsupported'
    rows[1]['chunk_text'] = rows[1]['chunk_text'].replace('R^T R', 'R† R')
    assert app.ask(prompt)['status'] == 'insufficient_evidence'


def test_crossdomin_joins_seven_user_selected_kbs_and_rejects_an_eighth():
    from cpu_llm.documents import SourceDocument, chunks_for

    app = appliance()
    names = ['physics', 'math', 'algebra', 'numerics', 'modeling', 'methods', 'verification']
    rows = []
    for name in names:
        text = ('For complex z, a rotation built from cos(z) and sin(z) is complex orthogonal and satisfies R^T R = I.'
                if name == 'math' else 'The Casas-Ibarra matrix is complex orthogonal and satisfies R^T R = I.')
        rows.extend(dict(document_id=key, chunk_text=chunk)
                    for key, chunk in chunks_for(SourceDocument(f'{name}-notes', (text,))))
    app.index.strict_source_rows.return_value = (rows, 123)
    prompt = 'CrossDomin: Casas-Ibarra using KBs: ' + ', '.join(names)
    result = app.ask(prompt)
    assert result['status'] == 'hypotheses'
    [join] = result['invention']['joins']
    assert len(join['premises']) == 7
    assert len({p['document_id'] for p in join['premises']}) == 7
    natural = 'Research Casas-Ibarra using KBs: physics, math, numerics.'
    assert app.ask(natural)['invention']['requested_domains'] == ['physics', 'mathematics', 'numerics']
    assert app.ask(prompt + ', extra')['status'] == 'needs_clarification'
    app.index.strict_source_rows.return_value = (rows[:-1], 123)
    missing = app.ask(prompt)
    assert missing['status'] == 'insufficient_evidence'
    assert missing['invention']['missing_domains'] == ['verification']
    assert 'Ingest a source with the missing premise' in missing['reply']['text']


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
