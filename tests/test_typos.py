"""A typo is rewritten only when one stored chunk word is clearly nearer."""

from cpu_llm.typos import correct_message

WORDS = {
    "lobster": {},
    "lobsters": {},
    "receive": {},
    "shipment": {},
    "european": {},
    "flight": {},
    "from": {},
    "tokyo": {},
    "permit": {},
    "permits": {},
}


def test_a_one_edit_typo_is_rewritten_before_retrieval():
    text, changes = correct_message("What is the Europen lobstor?", WORDS)
    assert text == "What is the European lobster?"
    assert changes == [{"from": "Europen", "to": "European"}, {"from": "lobstor", "to": "lobster"}]


def test_a_stored_word_is_not_replaced_by_its_plural():
    text, changes = correct_message("What is a lobster?", WORDS)
    assert text == "What is a lobster?"
    assert changes == []


def test_a_low_cosine_neighbor_is_left_alone():
    text, changes = correct_message("The form arrived from the toyko office.", WORDS)
    assert text == "The form arrived from the toyko office."
    assert changes == []


def test_two_equally_close_words_are_not_a_guess():
    tied = {"abcde": {}, "abcdf": {}}
    text, changes = correct_message("See abcdg today.", tied)
    assert text == "See abcdg today."
    assert changes == []


def test_a_question_verb_is_not_rewritten_into_its_inflection():
    text, changes = correct_message("Where does the harbor kestrel nest?", {"nests": {}, "kestrel": {}})
    assert text == "Where does the harbor kestrel nest?"
    assert changes == []


def test_color_is_not_rewritten_to_the_corpus_spelling():
    text, changes = correct_message("What color was the banana John ate?", {"colour": {}, "yellow": {}})
    assert text == "What color was the banana John ate?"
    assert changes == []
    other, other_changes = correct_message("What colour was the banana John ate?", {"color": {}, "yellow": {}})
    assert other == "What colour was the banana John ate?"
    assert other_changes == []


def test_an_empty_index_leaves_the_question():
    text, changes = correct_message("What is the lobstor?", {})
    assert text == "What is the lobstor?"
    assert changes == []

def test_explicit_attribute_typo_does_not_depend_on_corpus_vocabulary():
    assert correct_message("What clor is the Peregrine?", {}) == (
        "What color is the Peregrine?", [{"from": "clor", "to": "color"}]
    )
    assert correct_message("What is the wieght of the Peregrine?", {"weighs": {}}) == (
        "What is the weight of the Peregrine?", [{"from": "wieght", "to": "weight"}]
    )


def test_attribute_repair_stays_inside_explicit_question_slots():
    text = "What is the Clor?"
    assert correct_message(text, {}) == (text, [])
    assert correct_message("What color is the Peregrnie?", {"peregrine": {}}) == (
        "What color is the Peregrine?", [{"from": "Peregrnie", "to": "Peregrine"}]
    )

def test_short_color_transposition_requires_question_shape_and_stored_color():
    query = "Is the Peregrine ohcre?"
    assert correct_message(query, {"ochre": {}}) == (
        "Is the Peregrine ochre?", [{"from": "ohcre", "to": "ochre"}]
    )
    assert correct_message(query, {}) == (query, [])
    assert correct_message(query, {"ohcre": {}, "ochre": {}}) == (query, [])


def test_two_swaps_repair_color_only_when_the_value_is_supported_by_vocabulary():
    query = "Is the Peregrine orche?"
    assert correct_message(query, {"ochre": {}}) == (
        "Is the Peregrine ochre?", [{"from": "orche", "to": "ochre"}]
    )
    assert correct_message(query, {"red": {}}) == (query, [])
