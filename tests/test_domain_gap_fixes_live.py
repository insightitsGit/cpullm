import os
import uuid
import pytest
from cpu_llm.pipeline import Appliance

pytestmark = pytest.mark.skipif(os.environ.get('CPU_LLM_LIVE_TESTS') != '1', reason='requires disposable PostgreSQL')


@pytest.fixture(scope='module')
def app():
    with Appliance(namespace='domain_gaps_' + uuid.uuid4().hex[:8], prompt_backend='rules') as built:
        built.catalog_chunks([('virel-p0001', 'The Virel is blue.'),
                              ('virel-p0002', 'The material of the Virel is brass.')])
        yield built


@pytest.mark.parametrize('forced', [False, True])
@pytest.mark.parametrize('prompt,expected', [
    ('Review this RefundProof finding.\nvendor: Fictional\ninvoice: TEST-1\ntax charged: 2.0000\ncorrect tax: 1.0000\ncurrency: USD\ndeadline: ACTIONABLE\n', 'recoverable 1.0000 USD'),
    ('Decide this LedgerCovenant test.\nthreshold: 4.5\nnumerator: compliance_certificate 9000001\ndenominator: compliance_certificate 2000000\n', '4.500001x'),
    ('Decide this LedgerCovenant test.\nnumerator: compliance_certificate 2\n', 'threshold'),
    ('Decide this LedgerCovenant test.\nthreshold: 4.5\nnumerator: compliance_certificate 1\ndenominator: compliance_certificate 0\n', 'zero'),
])
def test_specialist_owns_structured_payload_through_public_api(app, prompt, expected, forced):
    app.clear_session_state()
    result = app.ask(prompt, finance=forced)
    text = result['reply']['text']
    assert expected.casefold() in text.casefold()
    assert 'Which entity do you mean?' not in text


def test_rules_color_regression_uses_requested_relation(app):
    app.clear_session_state()
    result = app.ask('Please give me information about the color of the Virel.')
    assert 'blue' in result['reply']['text']
    assert 'brass' not in result['reply']['text']


def test_inline_supplied_numbers_reach_math_without_losing_context(app):
    from test_numeric_comparison import INLINE
    app.clear_session_state()
    result = app.ask(INLINE)
    assert '3375 mg exceeds' in result['reply']['text']
    assert '3000 mg' in result['reply']['text']
    assert 'not treatment advice' in result['reply']['text']
