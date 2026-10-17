"""Arithmetic is a separate agent. A plain question does not enter it."""

from cpu_llm.agents.math import solve_math
from cpu_llm.agents.reply import compose_reply
from cpu_llm.classifier import math_trigger
from cpu_llm.pipeline import _after_brief, _after_compare, _after_shine, _math


def test_a_plain_question_does_not_ask_for_math():
    assert math_trigger("What is the European lobster?") == []
    assert math_trigger("Compare the European lobster and Robert Boulter.") == []
    assert math_trigger("The peak is 4,399 m.") == []
    assert math_trigger("What is 17 times 24?")
    assert math_trigger("What is the sum of 1, 2, and 3?")
    assert _after_shine({}) == "reply"
    assert _after_shine({"math": True, "compare": True}) == "compare"
    assert _after_compare({"math": True, "compare": True}) == "math"
    assert _after_brief({"math": True}) == "math"
    assert _after_shine({"math": True}) == "math"
    assert _after_shine({"delivery_blocked": True, "math": True}) == "math"
    assert _after_shine({"delivery_blocked": True, "math": True, "guard_decision": "block"}) == "reply"
    assert _after_shine({"delivery_blocked": True}) == "reply"


def test_the_math_agent_evaluates_the_expression():
    assert solve_math("What is 17 times 24?")["value"] == "408"
    assert solve_math("What is (3 + 5) * 2?")["value"] == "16"
    assert solve_math("What is 15% of 80?")["value"] == "12"
    assert solve_math("What is the square root of 144?")["value"] == "12"
    assert solve_math("What is the sum of 1, 2, and 3?")["value"] == "6"
    assert solve_math("What is the average of 2, 4, and 6?")["value"] == "4"
    assert solve_math("What is 2^10?")["value"] == "1024"
    assert solve_math("What is 2 to the power of 10?")["value"] == "1024"
    assert solve_math("What is 3 raised to 4?")["value"] == "81"
    assert solve_math("What is 10 squared?")["value"] == "100"
    assert solve_math("What is 3 cubed?")["value"] == "27"
    assert math_trigger("What is 2 ** 10?")
    assert math_trigger("Ford was founded in 1903 and has 2 plants.") == []
    assert solve_math("What is 1,000 + 2?")["value"] == "1002"
    assert solve_math("What is 5 minus 12?")["value"] == "-7"
    failed = solve_math("What is 1 / 0?")
    assert failed["ok"] is False
    assert failed["value"] == ""


def test_the_math_node_keeps_the_calculation_off_the_proposition_store():
    result = _math(None)({"message": "What is 2 + 2?", "math_reasons": ["the prompt contains an arithmetic expression"]})
    assert result["math_result"]["value"] == "4"
    assert "proposition" not in result


def test_a_math_question_is_spoken_as_the_calculation():
    reply = compose_reply(
        {
            "message": "What is 2 + 2?",
            "guard_decision": "allow",
            "math": True,
            "answer": "The European lobster is Homarus gammarus.",
            "math_result": solve_math("What is 2 + 2?"),
        }
    )
    assert reply["text"] == "2+2 = 4."
    assert reply["body"] == "The European lobster is Homarus gammarus."


def test_math_sits_beside_another_agent_instead_of_replacing_it():
    reply = compose_reply(
        {
            "message": "Summarize the lobster and what is 2 + 2?",
            "guard_decision": "allow",
            "math": True,
            "summarize": True,
            "answer": "The European lobster is Homarus gammarus.",
            "brief": {"summary": "The European lobster is Homarus gammarus."},
            "math_result": solve_math("What is 2 + 2?"),
        }
    )
    assert reply["text"].startswith("The European lobster is Homarus gammarus.")
    assert "Summary:" in reply["text"]
    assert "Math:\n2+2 = 4." in reply["text"]
