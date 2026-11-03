import pytest
from cpu_llm.finance import validate_message
from cpu_llm.finance.triggers import owns_structured_request
from cpu_llm.prompt_ingestion import normalize_question


def test_structured_specialist_ownership_does_not_capture_definitions():
    assert owns_structured_request('Review this RefundProof finding.\ntax charged: 1')
    assert owns_structured_request('Decide this LedgerCovenant test.\nnumerator: audited_financials 1')
    assert not owns_structured_request('What is RefundProof?')
    assert not owns_structured_request('What is this threshold?')


@pytest.mark.parametrize('places', [None, 2, 6])
def test_ratio_never_hides_decision_precision(places):
    prompt = 'Decide this LedgerCovenant test.\nthreshold: 4.5\nnumerator: compliance_certificate 9000001\ndenominator: compliance_certificate 2000000\n'
    if places is not None:
        prompt += f'ratio places: {places}\n'
    result = validate_message(prompt)
    assert 'BREACH' in result['text']
    assert '4.500001x' in result['text']
    assert '4.500000x' in result['text']


def test_conversational_color_is_normalized_without_dropping_conditions():
    assert normalize_question('Please give me information about the color of the Virel.')['query'] == 'What color is the Virel?'
    text = 'Please give me information about the color of the Virel if wet.'
    assert normalize_question(text)['query'] == text
