"""Real scoped/time-valid quotation documents; opt-in PostgreSQL integration."""
import os
import uuid
import pytest
from cpu_llm.pipeline import Appliance
from cpu_llm.access import CallerContext

pytestmark=pytest.mark.skipif(os.environ.get('CPU_LLM_LIVE_TESTS')!='1',reason='requires disposable PostgreSQL and cached encoder')

def test_live_documents_scope_time_formats_strict_and_continuation():
    corpus=[('doclive-p0001','Helios is a backup service.'),
            ('doclive-p0002','Helios uses PostgreSQL for metadata.'),
            ('doclive-p0003','Helios stores encrypted backups.'),
            ('doclive-p0004','Helios verifies backup checksums.'),
            ('doclive-p0005','Helios does not support regional failover.'),
            ('private-p0001','Helios has a secret internal token ABC123.')]
    with Appliance(namespace='doclive_'+uuid.uuid4().hex[:10],prompt_backend='rules',small_talk=False) as app:
        app.catalog_chunks(corpus)
        caller=CallerContext.make(app.tenant_id,'reader',['doclive-p'])
        normal=app.ask('Write a detailed report about Helios.',caller=caller)
        assert len(normal['answer_evidence'])==5
        assert 'ABC123' not in str(normal)
        strict=app.ask('Write a detailed report about Helios.',caller=caller,strict_evidence=True,style='friendly')
        assert strict['answer_evidence']==normal['answer_evidence']
        assert 'stylistic' not in strict and strict['evidence_policy']['enabled']
        html=app.ask('Write a detailed report about Helios as an HTML table.',caller=caller)
        assert html['answer_evidence']==normal['answer_evidence']
        assert '<table>' in html['reply']['text']
        plain_article=app.ask('Write a detailed article about Helios.',caller=caller)
        friendly=app.ask('Write a detailed article about Helios in a friendly tone.',caller=caller)
        assert friendly['stylistic']['verification']['verified']
        assert friendly['stylistic']['verification']['claim_count']==5
        assert friendly['tone_request']['effective_tone']=='friendly'
        assert 'ABC123' not in str(friendly)
        assert friendly['answer_evidence']==plain_article['answer_evidence']
        strict_friendly=app.ask('Write a detailed article about Helios in a friendly tone.',caller=caller,strict_evidence=True)
        assert 'stylistic' not in strict_friendly
        assert strict_friendly['tone_request']['disabled_by_strict']
        past=app.ask('Write a report about Helios.',caller=caller,as_of=0)
        assert past['answer_status']=='insufficient_evidence'
        denied=app.ask('Write a report about Helios.',caller=CallerContext.make(app.tenant_id,'none',[]))
        assert not denied['answer_evidence']
        first=app.ask('Write a report about Helios in 3 items.',caller=caller)
        second=app.ask(first['document']['coverage']['continuation_prompt'],caller=caller)
        assert len(first['answer_evidence'])==3 and len(second['answer_evidence'])==2
        assert not {p['document_id'] for p in first['answer_evidence']} & {p['document_id'] for p in second['answer_evidence']}
