"""Direct location forms found missing during the response-case review."""
import pytest

from cpu_llm.answerability import assess
from cpu_llm.agents.reply import compose_reply


@pytest.mark.parametrize('question,sentence', [
    ('Where does the brindle kite winter?', 'The brindle kite winters on the chalk cliff.'),
    ('Where does the cinder owl hunt?', 'The cinder owl hunts above the dry canal.'),
    ('Where does the marigold moth rest?', 'The marigold moth rests under the iron bridge.'),
    ('Where does the harbor kestrel nest?', 'The harbor kestrel nests near the coast.'),
    ('Where does the harbor kestrel nest?', 'The harbor kestrel nests inside the tower.'),
])
def test_location_prepositions_keep_the_same_subject_and_predicate(question, sentence):
    rows = [dict(document_id='guide', chunk_text=sentence)]
    decision = assess(question, rows)
    assert decision['answer_status'] == 'answered'
    reply = compose_reply(dict(message=question, guard_decision='allow', passages=rows))
    assert sentence in reply['text']
    assert reply['answer_evidence'] == [dict(document_id='guide', span=sentence)]


@pytest.mark.parametrize('sentence', [
    'The brindle kite winters after breeding.',
    'The brindle kite watches a crow winter on the chalk cliff.',
    'The crow winters on the chalk cliff.',
    'The brindle kite does not winter on the chalk cliff.',
])
def test_time_subordinate_other_subject_and_negation_are_not_location_answers(sentence):
    decision = assess('Where does the brindle kite winter?', [dict(document_id='guide', chunk_text=sentence)])
    assert decision['answer_status'] == 'insufficient_evidence'
