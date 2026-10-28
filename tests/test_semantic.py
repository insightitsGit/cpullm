"""Quantifier scope and type obligations stay on the shared decision."""

from cpu_llm.semantic import compile_request, discharges_type, quantifier_scope, scope_allows


def test_scopes_do_not_inherit_each_other():
    assert quantifier_scope("average display loom") == "aggregate"
    assert quantifier_scope("every survey loom") == "universal"
    assert quantifier_scope("Wicker") == "individual"
    assert scope_allows("individual", "Wicker", "The average display loom") is False
    assert scope_allows("aggregate", "average display loom", "The average display loom") is True
    assert scope_allows("aggregate", "average display loom", "Every survey loom") is False
    request = compile_request({"entity": "average display loom", "relation": "has_lifespan", "direction": "subject"})
    assert request.quantifier_scope == "aggregate"
    assert request.schema == "answer-request-v1"


def test_a_place_sentence_does_not_discharge_a_type_request():
    assert discharges_type("The Reed is a display pane.")
    assert discharges_type("Ada North is the harbor archivist.")
    assert not discharges_type("The Reed is found in Rim.")
    assert not discharges_type("The Reed is copper.")
    assert not discharges_type("The Sable is the best survey pane for color.")
