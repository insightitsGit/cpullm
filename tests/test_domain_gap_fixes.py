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

def test_normalized_weight_binds_the_requested_subject_and_cites_its_measurement():
    from cpu_llm.answerability import assess
    from cpu_llm.typos import correct_message

    query = normalize_question("How much does the Kestrel weigh?")["query"]
    assert correct_message(query, {"weighs": 1, "kestrel": 1}) == (query, [])
    distractor = dict(document_id="other", chunk_text="The fish weighs 2 pounds.")
    assert assess(query, [distractor])["answer_status"] == "insufficient_evidence"
    measurement = dict(document_id="weight", chunk_text="The Kestrel weighs 18 pounds.")
    result = assess(query, [distractor, measurement])
    assert result["answer_status"] == "answered"
    assert result["answer_evidence"] == [
        {"document_id": "weight", "span": "The Kestrel weighs 18 pounds."}
    ]

def test_color_selection_requires_evidence_for_the_requested_entity():
    from cpu_llm.prompt_intent import select_channel_answer

    def row(key, text):
        return dict(document_id=key, chunk_text=text)

    query = "What color is the Index?"
    wrong = row("wrong", "The Heddle is umber.")
    identity = row("type", "The Index is a finder.")
    pearl = row("pearl", "The Index is pearl.")
    assert select_channel_answer(query, [wrong, identity])["answer_status"] == "insufficient_evidence"
    assert select_channel_answer(query, [wrong, identity, pearl])["answer_status"] == "answered"
    assert select_channel_answer(query, [pearl, row("red", "The Index is red.")])["answer_status"] == "conflicting"


def test_explicit_location_quote_keeps_quote_intent_and_named_subject():
    result = normalize_question("Quote the sentence that says where the Kestrel lives.")
    assert result["query"] == "Where does the Kestrel live?"
    assert result["quote_requested"] is True
