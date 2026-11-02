"""Real SQL scope, validity and overflow checks; no encoder required."""
import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('CPU_LLM_LIVE_TESTS') != '1', reason='requires disposable PostgreSQL')


def test_strict_snapshot_scopes_before_limit_and_preserves_history():
    import psycopg
    from cpu_llm.retrieval import VectorPrismIndex
    with psycopg.connect(os.environ['VECTORPRISM_PG_DSN']) as conn:
        with conn.cursor() as cursor:
            cursor.execute('CREATE TEMP TABLE psm_document_embeddings (document_id text, chunk_text text, valid_timestamp bigint, valid_to_timestamp bigint)')
            cursor.executemany('INSERT INTO psm_document_embeddings VALUES (%s,%s,%s,%s)', [
                ('private-p0001', 'private', 1, None),
                ('public-p0001', 'old', 1, 100),
                ('public-p0001', 'new', 100, None),
                ('publicity-p0001', 'wrong prefix', 1, None)])
        index = object.__new__(VectorPrismIndex)
        index.db = SimpleNamespace(conn=conn)
        rows, when = index.strict_source_rows({'public-p'}, as_of=99, max_rows=1)
        assert rows == [dict(document_id='public-p0001', chunk_text='old')]
        assert when == 99
        assert index.strict_source_rows({'public-p'}, as_of=100, max_rows=1)[0] == [dict(document_id='public-p0001', chunk_text='new')]
        assert index.strict_source_rows(set(), as_of=100)[0] == []
        with pytest.raises(ValueError, match='limit'):
            index.strict_source_rows(None, as_of=100, max_rows=1)


def test_real_appliance_strict_lookup_cannot_reach_normal_graph(monkeypatch):
    import uuid
    from cpu_llm.pipeline import Appliance
    from cpu_llm.access import CallerContext
    def forbidden(*args, **kwargs):
        raise AssertionError('normal graph reached')
    monkeypatch.setattr('cpu_llm.request_planner.dispatch_request', forbidden)
    with Appliance(namespace='strict_' + uuid.uuid4().hex[:8], strict_evidence=True,
                   prompt_backend='rules') as app:
        app.upsert('private-p0001', 'The strength of DemoMed is 0.25 mg.')
        app.upsert('public-p0001', 'The strength of DemoMed is 0.75 mg.')
        caller = CallerContext.make(app.tenant_id, 'reader', ['public-p'])
        result = app.ask('What is the strength of DemoMed?', caller=caller,
                         strict_evidence=False, realization='model01')
        assert result['answer_status'] == 'evidence_quote'
        assert len(result['answer_evidence']) == 1
        assert result['answer_evidence'][0]['document_id'] == 'public-p0001'
        result = app.ask('What is the strength of DemoMed?')
        assert result['answer_status'] == 'conflicting'
