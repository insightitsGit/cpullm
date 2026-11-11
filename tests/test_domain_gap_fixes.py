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


def test_color_lookup_accepts_known_colors_and_explicit_custom_values():
    from cpu_llm.prompt_intent import select_channel_answer

    query = "What color is the Peregrine?"
    for sentence, expected in (
        ("The Peregrine is ochre.", "answered"),
        ("The Peregrine is ocher.", "answered"),
        ("The color of the Peregrine is Harbor-47.", "answered"),
        ("The Peregrine is Harbor-47.", "insufficient_evidence"),
        ("The Peregrine is a rescue cutter.", "insufficient_evidence"),
    ):
        result = select_channel_answer(query, [dict(document_id="source", chunk_text=sentence)])
        assert result["answer_status"] == expected
        if expected == "answered":
            assert result["answer_evidence"] == [{"document_id": "source", "span": sentence}]


def test_explicit_location_quote_keeps_quote_intent_and_named_subject():
    result = normalize_question("Quote the sentence that says where the Kestrel lives.")
    assert result["query"] == "Where does the Kestrel live?"
    assert result["quote_requested"] is True

def test_color_confirmation_requires_exact_subject_and_polarity():
    from cpu_llm.answerability import assess

    rows = [
        dict(document_id="rank", chunk_text="The Sable is the best survey pane for color."),
        dict(document_id="other", chunk_text="The Reed is lilac."),
        dict(document_id="negative", chunk_text="The Sable is not lilac."),
    ]
    query = "Is the Sable lilac?"
    assert assess(query, rows[:2])["answer_status"] == "insufficient_evidence"
    assert assess(query, rows)["answer_evidence"] == [
        {"document_id": "negative", "span": "The Sable is not lilac."}
    ]
    positive = dict(document_id="positive", chunk_text="The Sable is lilac.")
    assert assess(query, rows + [positive])["answer_status"] == "conflicting"


def test_trailing_maximum_is_a_budget_and_not_part_of_the_entity():
    from cpu_llm.response_policy import classify_response_request

    plan = classify_response_request("What color is the Ibis? Use at most two sentences.")
    assert plan["content_query"] == "What color is the Ibis?"
    assert plan["sentence_budget"] == 2

def test_explicit_shared_color_question_creates_two_independent_tasks():
    from cpu_llm.request_planner import separate_request

    plan = separate_request("What color is the Kestrel and the Ibis?")
    assert [task["query"] for task in plan["tasks"]] == [
        "What color is the Kestrel", "What color is the Ibis",
    ]


def test_repetitive_suffix_keeps_both_questions_and_meaningful_suffixes():
    from cpu_llm.request_planner import separate_request

    prompt = "What color is the Spool? What is the Wicker?"
    plan = separate_request(prompt + " " + "e" * 950)
    assert [task["query"] for task in plan["tasks"]] == [
        "What color is the Spool", "What is the Wicker",
    ]
    padded = "What is the Wicker? " + "e" * 1001
    prefix = "What color is the Spool? "
    assert separate_request(prefix + padded[:1000])["status"] == "multi"
    assert separate_request(prefix + padded[:1001])["status"] == "limit_exceeded"
    assert "content_query" not in separate_request("What is the Wicker? If it is fictional, say so.")


def test_class_definition_requires_evidence_about_the_class_itself():
    from cpu_llm.answerability import assess

    instance = "The Gnomon is a survey peg."
    definition = "A survey peg is a measuring instrument."
    assert assess("What is a survey peg?", [instance])["answer_status"] == "insufficient_evidence"
    assert assess("What is a survey peg?", [instance, definition])["text"] == definition
