"""Full retrieval/judge/output-node smoke test, deliberately separate from fixtures."""
import os
import uuid
import pytest
from cpu_llm.pipeline import Appliance
from cpu_llm.access import CallerContext

pytestmark=pytest.mark.skipif(os.environ.get('CPU_LLM_LIVE_TESTS')!='1',reason='requires disposable PostgreSQL and cached encoder')

def test_live_style_and_default_keep_canonical_content():
    with Appliance(namespace='style_'+uuid.uuid4().hex[:8],prompt_backend='rules') as app:
        app.catalog_chunks([
            ('style-demo-p0001','The Aster is blue.'),
            ('style-demo-p0002','The Aster is found in coastal waters.'),
        ])
        for prompt,profile,expected in [
            ('What color is the Aster?','formal','The color of the Aster is blue.'),
            ('Where does the Aster live?','friendly','You can find the Aster in coastal waters.'),
        ]:
            app.clear_session_state();normal=app.ask(prompt)
            app.clear_session_state();styled=app.ask(prompt,style=profile)
            assert 'stylistic' not in normal
            assert styled['stylistic']['status']=='generated'
            assert styled['stylistic']['text']==expected
            assert styled['reply']['text']==normal['reply']['text']
            assert styled['judgment']==normal['judgment']
            assert styled['answer_evidence']==normal['answer_evidence']
        blocked=app.ask('What color is the Aster?',style='formal',
            caller=CallerContext.make(app.tenant_id,'nobody',[]))
        assert blocked['stylistic']['status']=='skipped'
        assert 'text' not in blocked['stylistic']
