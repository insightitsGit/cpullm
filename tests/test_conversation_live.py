import os
import uuid
import pytest
from cpu_llm.pipeline import Appliance
from cpu_llm.access import CallerContext

pytestmark=pytest.mark.skipif(os.environ.get('CPU_LLM_LIVE_TESTS')!='1',reason='requires disposable PostgreSQL')


def test_social_and_mixed_requests_preserve_real_strict_scope():
    with Appliance(namespace='conversation_'+uuid.uuid4().hex[:8],strict_evidence=True,prompt_backend='rules') as app:
        app.upsert('conversation-public-p0001','The strength of Fictional Luma is 0.75 mg.')
        app.upsert('conversation-private-p0001','The strength of Fictional Luma is 2 mg.')
        caller=CallerContext.make(app.tenant_id,'reader',['conversation-public-p'])
        social=app.ask('Who are you?',caller=caller)
        assert social['answer_status']=='conversation' and not social['answer_evidence']
        result=app.ask('Hi, What is the strength of Fictional Luma?',caller=caller)
        assert result['answer_status']=='evidence_quote'
        assert {p['document_id'] for p in result['answer_evidence']}=={'conversation-public-p0001'}
        assert '0.75 mg' in result['reply']['text'] and '2 mg' not in result['reply']['text']
        assert app.ask('Hello, can I take Fictional Luma?',caller=caller)['answer_status']=='unsupported'
        assert app.ask('Who are you?',caller=caller,small_talk=False)['answer_status']=='unsupported'
