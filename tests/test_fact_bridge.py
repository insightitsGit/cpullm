"""Cited rule answers over sentences the caller already has. No database."""

from fact_bridge import answer

POLICIES = {
    "original": [
        "Business class is allowed for flights over six hours.",
        "Economy class is required for flights under six hours.",
    ],
    "reworded": [
        "Flights longer than 6 hours may use business class.",
        "If a flight is under six hours, economy class is required.",
    ],
    "reworded 2": [
        "For flights of more than six hours, business class is permitted.",
        "Flights under 6 hours must use economy class.",
    ],
}
FACTS = [
    "A flight from Los Angeles to Tokyo is about eleven hours.",
    "A flight from Los Angeles to Phoenix takes 2 hours.",
    "Employees may book business class because long flights cause fatigue.",
]
QUESTIONS = [
    ("Can I fly business class from Los Angeles to Tokyo?", "YES"),
    ("Can I fly business class from Los Angeles to Phoenix?", "NO"),
    ("Is economy class required from Los Angeles to Phoenix?", "YES"),
    ("Is economy class required from Los Angeles to Tokyo?", "NO"),
    ("Can I fly business class from Los Angeles to Paris?", "UNKNOWN"),
    ("Why may employees book business class?", "CAUSE"),
    ("Can I bring my dog to the office?", "NONE"),
]


def test_each_policy_wording_keeps_the_same_verdicts():
    for policy in POLICIES.values():
        for question, expected in QUESTIONS:
            result = answer(question, policy + FACTS, child_safety=False)
            assert result.verdict == expected, question
            if expected in {"YES", "NO", "CAUSE"}:
                assert result.because


def test_each_verdict_has_its_own_sentence():
    chunks = POLICIES["original"] + FACTS
    yes = answer("Can I fly business class from Los Angeles to Tokyo?", chunks, child_safety=False)
    no = answer("Can I fly business class from Los Angeles to Phoenix?", chunks, child_safety=False)
    unknown = answer("Can I fly business class from Los Angeles to Paris?", chunks, child_safety=False)
    cause = answer("Why may employees book business class?", chunks, child_safety=False)
    none = answer("Can I bring my dog to the office?", chunks, child_safety=False)
    contested = answer(
        "Is a permit required for the truck at the dock?",
        [
            "A permit is required for trucks over 2 tons.",
            "A permit is forbidden for trucks over 5 tons.",
            "The truck at the dock weighs 6 tons.",
        ],
        child_safety=False,
    )
    assert yes.text.startswith("Yes.") and "11 hours" in yes.text and "over 6 hours" in yes.text
    assert no.text.startswith("No.") and "2 hours" in no.text
    assert unknown.text.startswith("It depends")
    assert cause.text.startswith("Because long flights cause fatigue")
    assert none.verdict == "NONE" and "couldn't find a rule" in none.text
    assert contested.verdict == "CONTESTED" and "conflict" in contested.text
    assert {yes.wording["path"], no.wording["path"]} == {"deterministic"}


def test_a_purchase_joins_an_expense_rule_and_a_named_laptop_joins_its_rule():
    receipts = answer(
        "Are receipts required for the purchase from Staples?",
        [
            "Receipts are required for expenses of at least $25.",
            "A purchase from Staples costs $25.",
        ],
        child_safety=False,
    )
    small = answer(
        "Are receipts required for the purchase from Starbucks?",
        [
            "Receipts are required for expenses of at least $25.",
            "A purchase from Starbucks costs $6.",
        ],
        child_safety=False,
    )
    laptop = answer(
        "Does the new MacBook Pro need IT approval?",
        [
            "Laptops costing more than $2,000 need IT approval.",
            "The new MacBook Pro costs $2,499.",
        ],
        child_safety=False,
    )
    premium = answer(
        "Can I book premium economy on our flight to London?",
        [
            "Employees traveling internationally for more than 8 hours are eligible to book premium economy.",
            "Our flight to London takes roughly 10 hours.",
        ],
        child_safety=False,
    )
    assert receipts.verdict == "YES" and "25" in receipts.text
    assert small.verdict == "NO" and "6" in small.text
    assert laptop.verdict == "YES" and ("2,499" in laptop.text or "2499" in laptop.text)
    assert premium.verdict == "YES" and "10" in premium.text


def test_a_paraphrase_the_regex_misses_is_read_when_the_model_is_present():
    pytest = __import__("pytest")
    pytest.importorskip("transformers")
    from fact_bridge import model_root

    if model_root() is None:
        pytest.skip("no trained extractor checkpoint")
    chunks = [
        "A crane is required for shipments heavier than 2 tons.",
        "The crate in bay 4 weighs 3 tons.",
        "A crate is a shipment.",
    ]
    question = "Is a crane required for the crate in bay 4?"
    plain = answer(question, chunks, child_safety=False)
    learned = answer(question, chunks, child_safety=False, ml=True)
    assert plain.verdict == "NONE"
    assert learned.verdict == "YES"
    assert "3" in learned.text and learned.wording["path"] in {"model", "deterministic"}
