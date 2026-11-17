"""Presentation and explicit execution of cited research options."""

import re


def requested_model(query):
    constant = bool(re.search(
        r"\b(?:constant[- ]cross[- ]section|velocity[- ]independent)\b", query, re.I
    ))
    velocity = bool(re.search(r"\bvelocity[- ]dependent\b", query, re.I))
    if constant and velocity:
        return "comparison"
    if constant:
        return "constant_cross_section"
    return "velocity_dependent" if velocity else "unspecified"


def research_workspace(query, options, invention, bridge):
    model = requested_model(query)
    cards = []
    for source, candidates in (("hypothesis", options), ("innovation", invention)):
        for index, option in enumerate(candidates, 1):
            hypothesis = option.get("qualification") == "hypothesis"
            card = dict(
                id=f"{source}-{index}", method=source,
                origin=option.get("origin", source),
                claim_status=option.get("claim_status") or ("UNVERIFIED_HYPOTHESIS" if hypothesis else "CONSISTENCY_CHECK"),
                prediction=option.get("prediction") or option.get("proposal"),
                test=option.get("test"),
                premises=option.get("premises", []),
                provenance=option.get("provenance"),
                relation_to_request=option.get("relation_to_request", "source_context"),
                status="awaiting_inputs" if hypothesis and option.get("premises") else "reference_only",
                missing_inputs=["trusted predictor", "parameter grid", "sourced observable limits"] if hypothesis else [],
            )
            if "plain_view" in option:
                card["plain"] = option["plain_view"]
            if "scan_requirements" in option:
                card["scan_requirements"] = option["scan_requirements"]
                card["missing_inputs"].append("independent dwarf-galaxy fit threshold")
            cards.append(card)
    return dict(schema="research-workspace-v1", requested_model=model,
                conflict_status=bridge.get("status"), cards=cards, preferred_view="technical")


def run_research_test(workspace, card_id, *, model=None, predict=None, axes=(),
                      observable_units=None, limits=()):
    """Run a selected card with a trusted, application-supplied Python adapter."""
    from cpu_llm.constraint_evaluator import scan_constraints

    card = next((item for item in workspace.get("cards", ()) if item["id"] == card_id), None)
    if card is None or card["status"] != "awaiting_inputs" or not card["premises"]:
        raise ValueError("Select a cited, executable research card.")
    limits = tuple(limits)
    missing = []
    if not isinstance(model, str) or not model.strip() or not callable(predict):
        missing.append("trusted predictor and model name")
    if not axes:
        missing.append("parameter grid")
    if not observable_units or not limits:
        missing.append("sourced observable limits")
    exclusive_upper = frozenset()
    if requirements := card.get("scan_requirements"):
        if not any(limit.observable == "dwarf_fit_score" for limit in limits):
            missing.append("independent dwarf-galaxy fit threshold")
        exclusive_upper = frozenset(limit.id for limit in limits if limit.observable == "cluster_cross_section"
                   and limit.unit == "cm²/g" and limit.upper == requirements["upper"]
                   and limit.source == requirements["source_id"])
        if not exclusive_upper:
            missing.append("cited cluster cross-section bound")
    if missing:
        return dict(status="missing_inputs", card_id=card_id, missing_inputs=missing)
    result = scan_constraints(model, predict, axes, observable_units, limits,
                              exclusive_upper_ids=exclusive_upper)
    if exclusive_upper:
        result["exclusive_upper_limit_ids"] = sorted(exclusive_upper)
    return dict(status=result["status"], card_id=card_id, prediction=card["prediction"],
                claim_status=card["claim_status"], scope="supplied_model_and_sampled_grid", scan=result)
