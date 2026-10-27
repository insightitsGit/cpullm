"""Opt-in full pipeline validation of user-requested response budgets."""
import os
import uuid
import pytest

from cpu_llm.pipeline import Appliance
from cpu_llm.documents import SourceDocument

pytestmark = pytest.mark.skipif(os.environ.get('CPU_LLM_LIVE_TESTS') != '1',
    reason='requires cached encoder and disposable PostgreSQL database')


@pytest.fixture(scope='module')
def app():
    with Appliance(namespace='response_policy_' + uuid.uuid4().hex[:8]) as instance:
        instance.ingest(SourceDocument('meridian-guide', tuple(
            f'The Meridian has a {part}.' for part in
            ['bell', 'deck', 'cabin', 'roof', 'ramp', 'window', 'door', 'mast', 'rail'])))
        yield instance


def test_live_brief_and_detailed_overviews_have_different_verified_budgets(app):
    short = app.ask('Briefly explain the Meridian.')
    detailed = app.ask('Explain the Meridian in detail.')
    assert short['response_plan']['sentence_budget'] == 1
    assert detailed['response_plan']['sentence_budget'] == 8
    assert short['brief']['summary'].count('.') == 1
    assert detailed['brief']['summary'].count('.') > 1
    assert detailed['brief']['summary'].count('.') <= 8
    assert short['reply']['text'].count('.') == 1
    assert len(detailed['reply']['text']) > len(short['reply']['text'])
    assert not short.get('__partial__') and not detailed.get('__partial__')
    assert short['judgment']['outcome'] in {'answered', 'evidence_quote'}
    assert detailed['judgment']['outcome'] in {'answered', 'evidence_quote'}


def test_live_requested_bullet_limit_is_applied_without_padding(app):
    result = app.ask('Explain the Meridian in three bullet points.')
    assert result['response_plan']['item_budget'] == 3
    assert result['brief']['list'].count('.') == 3
    assert result['reply']['text'].count('\n- ') == 3
    assert result['judgment']['outcome'] in {'answered', 'evidence_quote'}
