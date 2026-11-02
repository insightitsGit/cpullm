"""Full retrieval/judge/output-node smoke test, deliberately separate from fixtures."""
import os
import uuid
import pytest
from cpu_llm.pipeline import Appliance
from cpu_llm.access import CallerContext
from cpu_llm.stylistic import StyleOptions

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

def test_live_style_composes_five_independent_retrievals():
    with Appliance(namespace='style_long_'+uuid.uuid4().hex[:8],prompt_backend='rules') as app:
        app.catalog_chunks([
            ('style-long-p0001','The Aster is blue.'),
            ('style-long-p0002','The Aster is found in coastal waters.'),
            ('style-long-p0003','The shape of the Aster is round.'),
            ('style-long-p0004','The material of the Aster is steel.'),
            ('style-long-p0005','The weight of the Aster is 12.5 pounds.'),
        ])
        result=app.ask('Tell me the color, habitat, shape, material, and weight of the Aster.',
            style=StyleOptions(tone='friendly',max_sentences=3))
        side=result['stylistic']
        assert side['status']=='generated',(side,[(t.get('query'),t['result'].get('answer_status'),t['result'].get('judgment')) for t in result['task_results']])
        assert side['verification']['claim_count']==5
        assert len(side['proof'])==5
        assert side['sentence_count']==3
        for value in ('blue','coastal waters','round','steel','12.5 pounds'):assert value in side['text']
        assert len(result['task_results'])==5
        assert {p['document_id'] for p in side['proof']}=={f'style-long-p{i:04d}' for i in range(1,6)}
