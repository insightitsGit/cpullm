"""Abductive bridge between Nammade comparisons and hypothesis generation."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from cpu_llm.abductive_bridge import (
    AbductiveBridgeNode,
    RelationalBridge,
    SIDM,
    _allowed_symbols,
    intervals_disjoint,
    extract_constraints,
)
from cpu_llm.pipeline import Appliance
from cpu_llm.research_hypotheses import resolve_hypotheses

OPEN_QUERY = (
    "How can self-interacting dark matter form cores in dwarf galaxies "
    "without violating the Bullet Cluster merger bound?"
)
CLOSED_QUERY = (
    "Can a single velocity-dependent self-interacting dark matter model explain "
    "dwarf-galaxy cores and satisfy Bullet Cluster merger constraints?"
)
DWARF = (
    "Dwarf-galaxy SIDM cores require a cross section per mass ≳ 2 cm²/g "
    "at low relative velocity."
)
CLUSTER = (
    "Bullet Cluster merger bounds require a cross section per mass < 1.25 cm²/g "
    "at high relative velocity."
)


def comparisons(*chunks):
    return [
        {"source_id": f"chunk-{index}", "span_text": text}
        for index, text in enumerate(chunks, 1)
    ]


def test_open_gap_emits_an_inverse_velocity_candidate_and_a_scaling_test():
    rows = comparisons(DWARF, CLUSTER)
    bridge, options = resolve_hypotheses(OPEN_QUERY, rows, [])

    assert bridge.status == "BRIDGED"
    candidate = bridge.candidate
    assert candidate is not None
    assert candidate.mediating_variable == "relative_velocity"
    assert candidate.proposed_relation == "inverse_monotonic"
    assert candidate.shared_observable == "cross_section_per_mass"
    assert candidate.anchor_chunk_ids == ["chunk-1", "chunk-2"]
    assert candidate.claim_status == "UNVERIFIED_HYPOTHESIS"
    assert DWARF in candidate.regime_a_constraint
    assert CLUSTER in candidate.regime_b_constraint

    assert options[0]["origin"] == "abductive_bridge"
    assert options[0]["claim_status"] == "UNVERIFIED_HYPOTHESIS"
    assert "velocity-dependent" in options[0]["test"]
    assert "scaling" in options[0]["test"]
    assert "decreases as relative velocity increases" in options[0]["prediction"]


def test_closed_premise_keeps_the_stated_model_and_the_bridge_as_separate_options():
    rows = comparisons(DWARF, CLUSTER)
    bridge, options = resolve_hypotheses(CLOSED_QUERY, rows, [])

    assert bridge.status == "BRIDGED"
    assert [item["origin"] for item in options] == ["prompt_premise", "abductive_bridge"]
    assert "velocity-dependent" in options[0]["prediction"]
    assert "Parameter-space check" in options[0]["test"]
    assert "checks only the premise" in options[0]["test"]
    assert "decreases as" not in options[0]["prediction"]
    assert "decreases as relative velocity increases" in options[1]["prediction"]

    existing = dict(document_id="review", qualification="hypothesis", prediction="already compiled", test="existing protocol")
    again, with_existing = resolve_hypotheses(CLOSED_QUERY, rows, [existing])
    assert again.status == "BRIDGED"
    assert with_existing[0] == existing
    assert [item["origin"] for item in with_existing[1:]] == ["prompt_premise", "abductive_bridge"]


def test_equal_regime_values_abstain_without_a_mediating_variable():
    rows = comparisons(
        "SIDM cores require a cross section per mass ≳ 3 cm²/g at a relative velocity of 1000 km/s.",
        "SIDM mergers require a cross section per mass < 0.2 cm²/g at a relative velocity of 1000 km/s.",
    )
    bridge = AbductiveBridgeNode().execute("self-interacting dark matter", rows)

    assert bridge.status == "INSUFFICIENT_EVIDENCE"
    assert bridge.candidate is None
    assert "mediating_variable" not in bridge.model_dump()
    assert "relative_velocity" not in (bridge.abstention_reason or "")
    assert "temperature" not in (bridge.abstention_reason or "")
    assert "halo_mass" not in (bridge.abstention_reason or "")


def test_tension_without_a_regime_mark_does_not_invent_a_variable():
    rows = comparisons(
        "SIDM requires a cross section per mass ≳ 2 cm²/g.",
        "SIDM requires a cross section per mass < 0.4 cm²/g.",
    )
    allowed = _allowed_symbols(SIDM, rows[0]["span_text"], rows[1]["span_text"])
    bridge = AbductiveBridgeNode().execute("self-interacting dark matter", rows)

    assert "cross_section_per_mass" in allowed
    assert "relative_velocity" not in allowed
    assert bridge.status == "INSUFFICIENT_EVIDENCE"
    assert bridge.candidate is None


def test_overlapping_constant_bounds_are_not_a_bridge():
    rows = comparisons(
        "Dwarf-galaxy SIDM cores require a cross section per mass ≳ 1 cm²/g at low relative velocity.",
        "Bullet Cluster merger bounds require a cross section per mass < 1.25 cm²/g at high relative velocity.",
    )
    parsed = extract_constraints(OPEN_QUERY, rows)
    assert not intervals_disjoint(parsed[0], parsed[1])
    bridge = AbductiveBridgeNode().execute(OPEN_QUERY, rows)
    assert bridge.status == "NO_GAP"
    assert bridge.candidate is None


def test_direct_monotonic_when_the_higher_regime_requires_the_larger_value():
    rows = comparisons(
        "Dwarf-galaxy SIDM cores require a cross section per mass < 0.2 cm²/g at low relative velocity.",
        "Bullet Cluster merger bounds require a cross section per mass ≳ 3 cm²/g at high relative velocity.",
    )
    bridge = AbductiveBridgeNode().execute(OPEN_QUERY, rows)
    assert bridge.status == "BRIDGED"
    assert bridge.candidate.proposed_relation == "direct_monotonic"


def test_a_later_comparison_can_contradict_the_candidate_without_promoting_it():
    rows = comparisons(
        DWARF,
        CLUSTER,
        "At high relative velocity SIDM still requires a cross section per mass ≳ 5 cm²/g.",
    )
    bridge = AbductiveBridgeNode().execute(OPEN_QUERY, rows)
    assert bridge.status == "BRIDGED"
    assert bridge.candidate.claim_status == "UNVERIFIED_HYPOTHESIS"
    assert bridge.contradiction_source_ids == ["chunk-3"]
    _bridge, options = resolve_hypotheses(OPEN_QUERY, rows, [])
    option = next(item for item in options if item["origin"] == "abductive_bridge")
    assert "chunk-3" in option["test"]
    assert "do not promote" in option["test"]


def test_unknown_quantities_do_not_become_a_candidate():
    rows = comparisons(
        "The widget flux is ≳ 4 gizmos in the cold case.",
        "The widget flux is < 0.1 gizmos in the hot case.",
    )
    bridge = AbductiveBridgeNode().execute("How are these widget fluxes related?", rows)
    assert bridge.status == "NO_GAP"
    assert bridge.candidate is None


def test_schema_rejects_a_third_anchor_and_a_promoted_claim():
    with pytest.raises(ValidationError):
        RelationalBridge(
            anchor_chunk_ids=["a", "b", "c"],
            shared_observable="cross_section_per_mass",
            regime_a_constraint="a",
            regime_b_constraint="b",
            mediating_variable="relative_velocity",
            proposed_relation="inverse_monotonic",
        )
    with pytest.raises(ValidationError):
        RelationalBridge(
            anchor_chunk_ids=["a", "b"],
            shared_observable="cross_section_per_mass",
            regime_a_constraint="a",
            regime_b_constraint="b",
            mediating_variable="relative_velocity",
            proposed_relation="inverse_monotonic",
            claim_status="measured fact",
        )


def appliance(chunks):
    app = object.__new__(Appliance)
    app.tenant_id = "test"
    app.small_talk = False
    app.guard = SimpleNamespace(check=lambda _text: SimpleNamespace(decision="allow"))
    rows = [dict(document_id=f"doc-p{index:04}", chunk_text=text) for index, text in enumerate(chunks, 1)]
    app.index = SimpleNamespace(strict_source_rows=Mock(return_value=(rows, 123)))
    return app


def test_research_prompt_runs_the_bridge_between_nammade_and_hypotheses():
    app = appliance([DWARF, CLUSTER])
    result = app.ask(
        "Research how can self-interacting dark matter form cores in dwarf galaxies "
        "without violating the Bullet Cluster merger bound."
    )
    bridge = result["abductive_bridge"]
    assert bridge["status"] == "BRIDGED"
    assert bridge["candidate"]["mediating_variable"] == "relative_velocity"
    assert bridge["candidate"]["proposed_relation"] == "inverse_monotonic"
    assert bridge["candidate"]["claim_status"] == "UNVERIFIED_HYPOTHESIS"
    assert result["research_options"][0]["origin"] == "abductive_bridge"
    assert "velocity-dependent" in result["research_options"][0]["test"]
    assert result["research_methods"]["abductive_bridge"] == {"status": "BRIDGED", "promotion": "blocked"}
    assert "abductive_bridge" in result["routing"]["post_stages"]
    assert "not a stored fact" in result["reply"]["text"]


def test_research_reply_shows_why_the_bounds_overlap_or_cannot():
    app = appliance([
        "Self-interacting dark matter simulations require a cross section per mass ≳ 1 cm²/g to form cores in dwarf galaxies.",
        "The Bullet Cluster analysis reports an upper bound of 1.25 square centimeters per gram at 68 percent confidence on the dark matter cross section per mass.",
        "A cluster merger sample limits the dark matter cross section per mass to < 0.47 cm²/g at 95 percent confidence.",
        "The boiling point of water is 100 C.",
    ])
    result = app.ask(
        "Research how can self-interacting dark matter form cores in dwarf galaxies "
        "without violating the Bullet Cluster merger bound?"
    )
    text = result["reply"]["text"]
    assert "Overlap [1, 1.25] cm²/g" in text
    assert "No new mechanism was added" in text
    assert "No shared value" in text
    assert "less than 0.47 cm²/g" in text
    assert "UNVERIFIED_HYPOTHESIS" in text
    assert "[doc-p0001]" in text and "[doc-p0003]" in text
    assert "boiling point" not in text.casefold()


def test_named_model_on_the_research_path_keeps_the_premise_and_the_bridge():
    app = appliance([DWARF, CLUSTER])
    result = app.ask(
        "Research can a single velocity-dependent self-interacting dark matter model explain "
        "dwarf-galaxy cores and satisfy Bullet Cluster merger constraints."
    )
    assert result["abductive_bridge"]["status"] == "BRIDGED"
    assert [item["origin"] for item in result["research_options"]] == ["prompt_premise", "abductive_bridge"]
    assert "separate option" in result["reply"]["text"]
    assert "(Stated premise)" in result["reply"]["text"]
    assert "(Abductive bridge)" in result["reply"]["text"]


def test_overlapping_and_disjoint_bounds_are_separate_options():
    rows = comparisons(
        "Self-interacting dark matter simulations require a cross section per mass ≳ 1 cm²/g to form cores in dwarf galaxies.",
        "The Bullet Cluster analysis reports an upper bound of 1.25 square centimeters per gram at 68 percent confidence on the dark matter cross section per mass.",
        "A cluster merger sample limits the dark matter cross section per mass to < 0.47 cm²/g at 95 percent confidence.",
    )
    bridge, options = resolve_hypotheses(OPEN_QUERY, rows, [])
    assert bridge.status == "BRIDGED"
    assert [item["origin"] for item in options] == ["abductive_bridge", "compatible_bounds", "compatible_bounds"]
    assert options[0]["claim_status"] == "UNVERIFIED_HYPOTHESIS"
    assert "< 0.47" in options[0]["test"]
    assert options[1]["claim_status"] == "CONSISTENCY_CHECK"
    assert options[1]["provenance"]["decision"] == "no_new_mechanism"
    assert options[1]["provenance"]["interval"] == "[1, 1.25] cm²/g"
    assert "No new mechanism was added" in options[1]["provenance"]["summary"]
    assert "overlap on [1, 1.25] cm²/g" in options[1]["provenance"]["summary"]
    assert "1.25" in options[1]["test"]
    assert "does not introduce a mediating variable" in options[1]["test"]
    assert options[0]["provenance"]["decision"] == "unverified_hypothesis"
    assert "less than 0.47 cm²/g" in options[0]["provenance"]["summary"]
    assert "UNVERIFIED_HYPOTHESIS" in options[0]["provenance"]["summary"]
    assert "not a stored fact" in options[0]["provenance"]["summary"]
    assert options[0]["provenance"]["steps"][-1]["result"] == "empty"
    assert "tighter ceiling" in options[2]["provenance"]["summary"]
    assert options[2]["provenance"]["interval"] == "(-∞, 0.47) cm²/g"

    _closed, closed_options = resolve_hypotheses(CLOSED_QUERY, rows, [])
    assert [item["origin"] for item in closed_options] == [
        "prompt_premise", "abductive_bridge", "compatible_bounds", "compatible_bounds",
    ]
