"""Opt-in full Appliance/encoder/PostgreSQL regression on fictional facts."""
import os
import uuid

import pytest

from cpu_llm.access import CallerContext
from cpu_llm.pipeline import Appliance

pytestmark = pytest.mark.skipif(os.environ.get('CPU_LLM_LIVE_TESTS') != '1',
    reason='set CPU_LLM_LIVE_TESTS=1 with a disposable PostgreSQL database')


@pytest.fixture(scope='module')
def appliance():
    with Appliance(namespace='join_audit_' + uuid.uuid4().hex[:8]) as app:
        app.index_chunks([
            ('join-type', 'The fictional lobster is a fictional crustacean.'),
            ('join-rule', 'Every fictional crustacean lives for 12 years.'),
            ('alias', 'Caligo marina, known as the coastal moth, is an insect.'),
            ('place', 'Caligo marina lives in Norway.'),
            ('color', 'Caligo marina is blue.'),
        ])
        yield app


def test_live_membership_join_cites_both_premises(appliance):
    result = appliance.ask('How long does the fictional lobster live?')
    assert not result.get('__partial__') and not result.get('__node_error__')
    assert result['answer_status'] in {'answered','evidence_quote'}
    assert {'join-type','join-rule'} <= {item['document_id'] for item in result['answer_evidence']}
    assert '12 years' in result['reply']['text']


def test_live_join_requires_authorization_for_each_premise(appliance):
    caller = CallerContext.make(appliance.tenant_id, 'alice', ['join-type'])
    missing = appliance.ask('How long does the fictional lobster live?', caller=caller)
    assert missing['answer_status'] == 'insufficient_evidence'
    assert '12 years' not in missing['reply']['text']
    caller = CallerContext.make(appliance.tenant_id, 'alice', ['join-type','join-rule'])
    answered = appliance.ask('How long does the fictional lobster live?', caller=caller)
    assert '12 years' in answered['reply']['text']


def test_live_repeated_corrections_retire_each_version_and_its_tags():
    """Version intervals and resonance tags, with the tag store explicitly on.

    The appliance default leaves resonance tags off. This check opts in so the
    live correction still proves the current tag row and the closed interval.
    """
    original, middle, latest = ('The fictional beetle is blue.',
                                'The fictional beetle is red.',
                                'The fictional beetle is green.')
    base = 'review-history-p0001'
    with Appliance(namespace='join_audit_tags_' + uuid.uuid4().hex[:8], resonance_tags=True) as appliance:
        _repeated_correction(appliance, base, original, middle, latest)


def _repeated_correction(appliance, base, original, middle, latest):
    appliance.catalog_chunks([(base, original)])
    with appliance.index.db.conn.cursor() as cursor:
        cursor.execute('UPDATE psm_document_embeddings SET valid_timestamp = %s WHERE document_id = %s',
                       (1700010000, base))
    appliance.index.db.conn.commit()
    first = appliance.correct(base, original, middle, actor_id='editor', timestamp=1700010100)
    second = appliance.correct(base, middle, latest, actor_id='editor', timestamp=1700010200)
    candidates = appliance.index.current_chunks_by_ids([base, first['new_id'], second['new_id']])
    assert {row['document_id'] for row in candidates} == {second['new_id']}
    units = appliance.resonance_tags._load(None)
    assert {row['doc_id'] for row in units if row['doc_id'].startswith(base)} == {second['new_id']}
    with appliance.index.db.conn.cursor() as cursor:
        cursor.execute('SELECT valid_to_timestamp FROM psm_document_embeddings WHERE document_id = %s',
                       (first['new_id'],))
        assert cursor.fetchone()[0] == 1700010200
    assert 'red' in appliance.ask('What color is the fictional beetle?', as_of=1700010150)['reply']['text']
    assert 'green' in appliance.ask('What color is the fictional beetle?')['reply']['text']


def test_live_five_digit_source_is_scoped_and_deleted_without_prefix_collision(appliance):
    wanted, neighbor = 'review-large-p10000', 'review-large-policy-p10000'
    appliance.catalog_chunks([(wanted, 'The fictional orchid is purple.'),
                              (neighbor, 'The fictional orchid is yellow.')])
    rows = appliance.index.search_allowed('What color is the fictional orchid?', {'review-large-p'}, top_k=20)
    assert {row['document_id'] for row in rows} == {wanted}
    appliance.delete_source('review-large')
    assert not appliance.index.db.get_by_ids([wanted])
    assert appliance.index.db.get_by_ids([neighbor])


def test_live_paraphrase_and_alias_keep_identity_provenance(appliance):
    result = appliance.ask('Where would I encounter the coastal moth?')
    assert 'Norway' in result['reply']['text']
    assert result['prompt_intent']['dictionary']['status'] == 'expanded'
    assert 'alias' in {item['document_id'] for item in result['supporting_evidence']}


def test_live_criteria_reference_confirmation_and_missing_fact(appliance):
    assert appliance.ask('Which lobster is best?', session_id='ranking')['clarification']['slot'] == 'criteria'
    assert appliance.ask('taste', session_id='ranking')['clarification']['slot'] == 'evidence'
    assert appliance.ask('cancel', session_id='ranking')['status'] == 'cancelled'
    assert appliance.ask('Where does it live?', session_id='reference')['clarification']['slot'] == 'reference'
    confirmed = appliance.ask('coastal moth', session_id='reference')
    assert 'Norway' in confirmed['reply']['text']
    missing = appliance.ask('How long does the coastal moth live?')
    assert missing['answer_status'] == 'insufficient_evidence'


def test_live_contradicting_universal_rule_is_not_hidden(appliance):
    appliance.index_chunks([('join-direct','The fictional lobster lives for 6 years.')])
    result = appliance.ask('How long does the fictional lobster live?')
    assert result['answer_status'] == 'conflicting'
    assert result['answer'] is None


def test_live_replacement_and_deletion_remove_join_premises(appliance):
    from cpu_llm.documents import SourceDocument
    question = 'How long does the fictional crab live?'
    appliance.ingest(SourceDocument('lifecycle', (
        'The fictional crab is a fictional arthropod.',
        'Every fictional arthropod lives for 9 years.')))
    assert '9 years' in appliance.ask(question)['reply']['text']
    appliance.ingest(SourceDocument('lifecycle', ('The fictional crab is a fictional arthropod.',)))
    assert appliance.ask(question)['answer_status'] == 'insufficient_evidence'
    appliance.delete_source('lifecycle')
    assert not any(f.document_id.startswith('lifecycle-p') for f in
        appliance.knowledge_graph.neighborhood('fictional crab'))


def test_live_correction_times_and_restart_keep_version_intervals(appliance):
    from cpu_llm.retrieval import VectorPrismIndex, default_checkpoint
    original, corrected = 'The fictional newt is blue.', 'The fictional newt is red.'
    appliance.catalog_chunks([('history-p0001', original)])
    with appliance.index.db.conn.cursor() as cursor:
        cursor.execute('UPDATE psm_document_embeddings SET valid_timestamp = %s WHERE document_id = %s',
                       (1700000000, 'history-p0001'))
    appliance.index.db.conn.commit()
    change = appliance.correct('history-p0001', original, corrected, actor_id='editor', timestamp=1700000100)
    old = appliance.ask('What color is the fictional newt?', as_of=1700000050)
    new = appliance.ask('What color is the fictional newt?', as_of=1700000150)
    assert 'blue' in old['reply']['text'] and 'red' not in old['reply']['text']
    assert 'red' in new['reply']['text'] and 'blue' not in new['reply']['text']
    # A fresh index has no in-process _history flag. It still excludes the old row.
    reopened = VectorPrismIndex(default_checkpoint(), backend='pgvector', dsn=appliance.index.dsn)
    try:
        hits = reopened.search('What color is the fictional newt?', top_k=20)
    finally:
        reopened.db.conn.close()
    ids = {row['document_id'] for row in hits}
    assert change['new_id'] in ids and 'history-p0001' not in ids
