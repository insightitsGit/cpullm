"""Evidence-backed covenant calculation.

Precedence, source authority, scaled-integer ratios, and add-back fixed points
follow the LedgerCovenant rules. Two surviving provisions stay ambiguous. Two
equal-rank figures that disagree stay a conflict. An elapsed test is a breach
observation, not a declaration of default.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from cpu_llm.finance.money import (
    AMOUNT_SCALE,
    RATIO_SCALE,
    FinanceInputError,
    add,
    apply_percentage_cap,
    compare,
    divide,
    format_amount,
    format_ratio,
    headroom,
    parse_amount,
)

LIMITATION = (
    "This decision is the arithmetic and the precedence trace for the figures supplied. "
    "It is not legal advice and it does not declare a default."
)
LATTICE_VERSION = "lattice_v1"
LATTICE = {
    "compliance_certificate": 100,
    "audited_financials": 90,
    "reviewed_financials": 70,
    "management_accounts": 50,
    "system_export": 40,
    "analyst_override": 30,
    "correspondence": 20,
}
DOC_AUTHORITY = {
    "amendment": 100,
    "amendment_and_restatement": 95,
    "waiver": 90,
    "side_letter": 80,
    "credit_agreement": 70,
    "compliance_certificate": 40,
    "financials": 30,
    "correspondence": 10,
    "other": 0,
}
PRECEDENCE_VERSION = "precedence_policy_v1"
OPEN_ENDED_DAYS = 4_000_000
COMPARATORS = frozenset({"lte", "gte", "lt", "gt", "eq"})
MAX_ITERATIONS = 1024


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_instant(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _window_days(candidate: dict[str, Any]) -> int:
    start = _as_instant(candidate.get("valid_from"))
    end = _as_instant(candidate.get("valid_to"))
    if start is None or end is None:
        return OPEN_ENDED_DAYS
    return max((end - start).days, 0)


def _applicable(candidates: list[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    kept = []
    for candidate in candidates:
        start = _as_instant(candidate.get("valid_from"))
        end = _as_instant(candidate.get("valid_to"))
        if start is not None and start.date() > as_of:
            continue
        if end is not None and end.date() < as_of:
            continue
        kept.append(candidate)
    return kept


def _authority(candidate: dict[str, Any]) -> int:
    doc_type = str(candidate.get("doc_type") or "").strip().lower()
    if doc_type:
        return int(DOC_AUTHORITY.get(doc_type, 0))
    return int(candidate.get("document_authority_rank") or 0)


def resolve_provisions(candidates: list[dict[str, Any]], *, as_of: Any) -> dict[str, Any]:
    """Run amendment lineage, temporal narrowness, document authority, then specificity.

    Recording order does not choose a survivor. A tie remains AMBIGUOUS.
    """
    target = _as_date(as_of)
    applicable = _applicable(candidates, target)
    trace: dict[str, Any] = {
        "precedence_policy_version": PRECEDENCE_VERSION,
        "as_of": target.isoformat(),
        "allow_recorded_at_tiebreak": False,
        "candidates_considered": len(candidates),
        "candidates_applicable": len(applicable),
        "rungs": [],
    }
    if not applicable:
        trace["outcome"] = "UNRESOLVED_MISSING_DOCUMENT"
        trace["note"] = "No provision is valid on the test date."
        return {"status": "UNRESOLVED_MISSING_DOCUMENT", "governing": None, "candidates": [], "trace": trace}

    survivors = list(applicable)
    lineage_cycle = False
    amended_ids = {item.get("amends") for item in survivors if item.get("amends")}
    before = len(survivors)
    next_rows = [item for item in survivors if item.get("id") not in amended_ids]
    if not next_rows:
        lineage_cycle = True
        note = "lineage_cycle"
    elif len(next_rows) < before:
        survivors = next_rows
        note = f"superseded {before - len(survivors)} amended version(s)"
    else:
        note = None
    trace["rungs"].append({"rung": "AMENDMENT_LINEAGE", "survivors_after": len(survivors), "discriminator": note})

    if not lineage_cycle and len(survivors) > 1:
        narrowest = min(_window_days(item) for item in survivors)
        narrowed = [item for item in survivors if _window_days(item) == narrowest]
        temporal_note = f"narrowest window {narrowest}d" if len(narrowed) < len(survivors) else None
        survivors = narrowed
        trace["rungs"].append(
            {"rung": "TEMPORAL", "survivors_after": len(survivors), "discriminator": temporal_note}
        )
    if not lineage_cycle and len(survivors) > 1:
        top = max(_authority(item) for item in survivors)
        ranked = [item for item in survivors if _authority(item) == top]
        authority_note = f"authority rank {top}" if len(ranked) < len(survivors) else None
        survivors = ranked
        trace["rungs"].append(
            {"rung": "DOCUMENT_AUTHORITY", "survivors_after": len(survivors), "discriminator": authority_note}
        )
    if not lineage_cycle and len(survivors) > 1:
        top_spec = max(int(item.get("specificity") or 0) for item in survivors)
        specific = [item for item in survivors if int(item.get("specificity") or 0) == top_spec]
        spec_note = f"specificity {top_spec}" if len(specific) < len(survivors) else None
        survivors = specific
        trace["rungs"].append(
            {"rung": "SPECIFICITY", "survivors_after": len(survivors), "discriminator": spec_note}
        )
    trace["rungs"].append({"rung": "RECORDED_AT", "discriminator": "tiebreak_not_permitted", "survivors_after": len(survivors)})

    names = [str(item.get("id")) for item in survivors]
    if len(survivors) == 1 and not lineage_cycle:
        trace["outcome"] = "RESOLVED"
        trace["governing_id"] = survivors[0].get("id")
        return {"status": "RESOLVED", "governing": survivors[0], "candidates": names, "trace": trace}
    trace["outcome"] = "AMBIGUOUS"
    trace["note"] = (
        "Amendment lineage forms a cycle."
        if lineage_cycle
        else f"{len(survivors)} provisions survive the precedence ladder."
    )
    return {"status": "AMBIGUOUS", "governing": None, "candidates": names, "trace": trace}


def resolve_fact(readings: list[dict[str, Any]], *, fact_key: str) -> dict[str, Any]:
    """Highest source authority wins. Equal authority with different values is a conflict."""
    prepared: list[dict[str, Any]] = []
    for index, reading in enumerate(readings):
        source = str(reading.get("source") or reading.get("source_type") or "").strip().lower()
        prepared.append(
            {
                "index": index,
                "id": reading.get("id") or f"{fact_key}-{index + 1}",
                "source": source,
                "rank": int(LATTICE.get(source, 0)),
                "value_scaled": parse_amount(reading.get("value"), scale=AMOUNT_SCALE),
                "currency": str(reading.get("currency") or "USD").upper(),
                "recorded_at": reading.get("recorded_at") or reading.get("recordedAt"),
            }
        )
    if not prepared:
        return {
            "status": "MISSING",
            "value_scaled": None,
            "source": None,
            "currency": None,
            "id": None,
            "note": f"No {fact_key} figure was supplied.",
            "outranked": [],
        }
    def sort_key(row: dict[str, Any]) -> tuple[int, str, int]:
        stamp = row.get("recorded_at")
        stamp_text = "9999-12-31T23:59:59+00:00" if not stamp else str(stamp)
        return (-row["rank"], stamp_text, row["index"])

    ranked = sorted(prepared, key=sort_key)
    top = ranked[0]["rank"]
    contenders = [row for row in ranked if row["rank"] == top]
    losers = [row for row in ranked if row["rank"] < top]
    currencies = {row["currency"] for row in contenders}
    if len(currencies) > 1:
        return {
            "status": "CONFLICT",
            "value_scaled": None,
            "source": None,
            "currency": None,
            "id": None,
            "note": f"Top-authority {fact_key} sources use different currencies {sorted(currencies)}.",
            "outranked": [row["source"] for row in losers],
        }
    values = {row["value_scaled"] for row in contenders}
    if len(values) > 1:
        return {
            "status": "CONFLICT",
            "value_scaled": None,
            "source": contenders[0]["source"],
            "currency": contenders[0]["currency"],
            "id": None,
            "note": (
                f"{len(contenders)} {contenders[0]['source']} figures differ. "
                "Equal authority is not an average."
            ),
            "outranked": [row["source"] for row in losers],
            "contender_ids": [row["id"] for row in contenders],
        }
    winner = contenders[0]
    return {
        "status": "RESOLVED",
        "value_scaled": winner["value_scaled"],
        "source": winner["source"],
        "currency": winner["currency"],
        "id": winner["id"],
        "rank": top,
        "lattice_version": LATTICE_VERSION,
        "note": f"{winner['source']} outranks " + ", ".join(row["source"] for row in losers) if losers else f"{winner['source']} is the only figure.",
        "outranked": [row["source"] for row in losers],
        "corroboration_count": len(contenders) - 1,
    }


def solve_addbacks(
    *,
    base: Any,
    components: list[dict[str, Any]],
    max_iterations: int = MAX_ITERATIONS,
    currency: str = "USD",
) -> dict[str, Any]:
    """Least fixed point of add-back caps. A pass that does not settle is refused."""
    base_scaled = parse_amount(base, scale=AMOUNT_SCALE)
    normalized: list[dict[str, Any]] = []
    for index, component in enumerate(components):
        basis = str(component.get("basis") or "post").strip().lower()
        if basis in {"result", "post", "post_addback"}:
            basis = "post"
        elif basis in {"base", "pre"}:
            basis = "base"
        elif basis != "amount":
            raise FinanceInputError("An add-back basis must be result, base, or amount.")
        claimed = parse_amount(component.get("claimed"), scale=AMOUNT_SCALE)
        item: dict[str, Any] = {
            "key": str(component.get("key") or f"component-{index + 1}"),
            "basis": basis,
            "claimed_scaled": claimed,
        }
        if basis == "amount":
            item["cap_scaled"] = parse_amount(component.get("cap"), scale=AMOUNT_SCALE)
        else:
            percent = component.get("cap_percent", component.get("capPercent", component.get("percent")))
            item["percent_scaled"] = _percent(percent)
        normalized.append(item)
    iterates: list[dict[str, int]] = []
    current = base_scaled
    converged = False
    for iteration in range(1, max_iterations + 1):
        running = base_scaled
        for item in normalized:
            if item["basis"] == "amount":
                if item["claimed_scaled"] > item["cap_scaled"]:
                    applied, capped = item["cap_scaled"], True
                else:
                    applied, capped = item["claimed_scaled"], False
            else:
                basis_scaled = current if item["basis"] == "post" else base_scaled
                applied, capped = apply_percentage_cap(
                    item["claimed_scaled"],
                    basis_scaled=basis_scaled,
                    percent_scaled=item["percent_scaled"],
                )
            item["applied_scaled"] = applied
            item["was_capped"] = capped
            running = add(running, applied)
        iterates.append({"iteration": iteration, "basis_scaled": current, "result_scaled": running})
        if running == current:
            converged = True
            break
        current = running
    if not converged:
        raise FinanceInputError(
            "The add-back definition did not settle. The last pass is not reported as the amount."
        )
    return {
        "status": "SETTLED",
        "result_scaled": current,
        "currency": currency,
        "iterations": len(iterates),
        "binding_caps": [item["key"] for item in normalized if item.get("was_capped")],
        "iterates": iterates,
        "display": format_amount(current, currency=currency),
    }


def _percent(raw: Any) -> int:
    """Parse ``20`` or ``20%`` as 0.20 at ratio scale."""
    if isinstance(raw, bool) or isinstance(raw, float):
        raise FinanceInputError("A cap percent must be a whole percent such as 20 or 20%.")
    text = str(raw).strip()
    has_sign = text.endswith("%")
    body = text[:-1].strip() if has_sign else text
    try:
        number = Decimal(body)
    except InvalidOperation:
        raise FinanceInputError(f"{raw!r} is not a cap percent.") from None
    if number <= 1 and not has_sign:
        raise FinanceInputError("Write the cap as a percent, such as 20%.")
    return parse_amount(body, scale=RATIO_SCALE) // 100


def _select_threshold(schedules: list[dict[str, Any]], test_date: date) -> dict[str, Any]:
    covering = []
    for row in schedules:
        start = _as_date(row["effective_from"])
        end = _as_date(row["effective_to"]) if row.get("effective_to") else None
        if start > test_date:
            continue
        if end is not None and end < test_date:
            continue
        covering.append(row)
    if not covering:
        raise FinanceInputError(f"No threshold covers {test_date.isoformat()}.")
    if len(covering) > 1:
        raise FinanceInputError(
            f"{len(covering)} threshold rows cover {test_date.isoformat()}. Choosing one would set a commercial term."
        )
    return covering[0]


def decide(request: dict[str, Any]) -> dict[str, Any]:
    """Resolve provisions, facts, and the ratio. A gap stops the decision."""
    if not request:
        return _incomplete("LedgerCovenant needs a comparator, a threshold, and the figures being tested.")
    try:
        return _decide(request)
    except (FinanceInputError, ValueError) as exc:
        return {
            "product": "ledgercovenant",
            "completed": True,
            "verdict": "INPUT_INVALID",
            "text": f"LedgerCovenant: INPUT_INVALID. {exc} {LIMITATION}",
            "limitation": LIMITATION,
        }


def _incomplete(message: str) -> dict[str, Any]:
    return {
        "product": "ledgercovenant",
        "completed": False,
        "verdict": "INCOMPLETE",
        "text": f"LedgerCovenant: INCOMPLETE. {message} {LIMITATION}",
        "limitation": LIMITATION,
    }


def _refuse(verdict: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "product": "ledgercovenant",
        "completed": True,
        "verdict": verdict,
        "text": f"LedgerCovenant: {verdict}. {message} {LIMITATION}",
        "limitation": LIMITATION,
        **extra,
    }


def _decide(request: dict[str, Any]) -> dict[str, Any]:
    provisions = list(request.get("provisions") or [])
    resolution = None
    if provisions:
        if not request.get("test_date") and not request.get("testDate"):
            return _incomplete("A provision list needs a test date.")
        resolution = resolve_provisions(provisions, as_of=request.get("test_date") or request.get("testDate"))
        if resolution["status"] != "RESOLVED":
            names = ", ".join(resolution.get("candidates") or []) or "none"
            return _refuse(
                resolution["status"],
                f"The governing provision was not settled ({names}). No ratio was computed.",
                provisions=resolution,
            )
        if str(resolution["governing"].get("operation") or "").upper() == "DELETE":
            return _refuse(
                "NOT_APPLICABLE",
                "The governing version deletes this obligation. No test was run.",
                provisions=resolution,
            )

    derivation = None
    components = list(request.get("addbacks") or request.get("components") or [])
    if request.get("addback_base") is not None or request.get("base") is not None or components:
        base = request.get("addback_base", request.get("base"))
        if base is None:
            return _incomplete("An add-back cap needs a base amount.")
        derivation = solve_addbacks(
            base=base,
            components=components,
            max_iterations=int(request.get("max_iterations") or MAX_ITERATIONS),
            currency=str(request.get("currency") or "USD"),
        )

    numerator_rows = list(request.get("numerator") or [])
    denominator_rows = list(request.get("denominator") or [])
    threshold = request.get("threshold")
    schedules = list(request.get("schedules") or [])
    if threshold is None and not schedules and derivation is not None and not numerator_rows:
        return {
            "product": "ledgercovenant",
            "completed": True,
            "verdict": "SETTLED",
            "text": (
                f"LedgerCovenant: SETTLED. The add-back fixed point is {derivation['display']} "
                f"after {derivation['iterations']} passes. "
                f"Binding caps: {', '.join(derivation['binding_caps']) or 'none'}. {LIMITATION}"
            ),
            "derivation": derivation,
            "provisions": resolution,
            "limitation": LIMITATION,
        }
    if threshold is None and not schedules:
        return _incomplete("A covenant test needs a threshold.")
    if not numerator_rows and derivation is None:
        return _incomplete("A covenant test needs a numerator.")

    comparator = str(request.get("comparator") or "lte").strip().lower()
    if comparator not in COMPARATORS:
        raise FinanceInputError(f"Unknown comparator {comparator!r}.")
    rounding = str(request.get("rounding") or "ROUND_HALF_UP")
    test_date = request.get("test_date") or request.get("testDate")
    if schedules:
        if not test_date:
            return _incomplete("A threshold schedule needs a test date.")
        chosen = _select_threshold(schedules, _as_date(test_date))
        threshold = chosen.get("threshold")
    obligation = "RATIO" if denominator_rows else "ABSOLUTE"
    if derivation is not None and not numerator_rows:
        numerator = {
            "status": "RESOLVED",
            "value_scaled": derivation["result_scaled"],
            "source": "add_back_fixed_point",
            "currency": derivation["currency"],
            "id": "derivation",
            "note": "The numerator is the settled add-back amount.",
            "outranked": [],
        }
    else:
        numerator = resolve_fact(numerator_rows, fact_key="numerator")
    if numerator["status"] != "RESOLVED":
        return _refuse(f"FACT_{numerator['status']}", numerator["note"], numerator=numerator, provisions=resolution)
    denominator = None
    if obligation == "RATIO":
        denominator = resolve_fact(denominator_rows, fact_key="denominator")
        if denominator["status"] != "RESOLVED":
            return _refuse(
                f"FACT_{denominator['status']}",
                denominator["note"],
                numerator=numerator,
                denominator=denominator,
                provisions=resolution,
            )
        computed = divide(
            numerator["value_scaled"],
            denominator["value_scaled"],
            result_scale=RATIO_SCALE,
            rounding=rounding,
        )
        threshold_scaled = parse_amount(threshold, scale=RATIO_SCALE)
        shown_computed = format_ratio(computed)
        shown_threshold = format_ratio(threshold_scaled)
    else:
        computed = numerator["value_scaled"]
        threshold_scaled = parse_amount(threshold, scale=AMOUNT_SCALE)
        shown_computed = format_amount(computed, currency=numerator["currency"])
        shown_threshold = format_amount(threshold_scaled, currency=numerator["currency"])
    passed = compare(computed, comparator, threshold_scaled)
    outcome = "COMPLIANT" if passed else "BREACH"
    waiver = request.get("waiver")
    if outcome == "BREACH" and waiver:
        outcome = "WAIVED"
    slack = headroom(computed, comparator, threshold_scaled)
    source_note = numerator["note"]
    if denominator is not None:
        source_note = f"{source_note} Denominator: {denominator['note']}"
    waiver_note = " A waiver keeps the breach on the record and does not make the test compliant." if outcome == "WAIVED" else ""
    return {
        "product": "ledgercovenant",
        "completed": True,
        "verdict": outcome,
        "text": (
            f"LedgerCovenant: {outcome}. The computed value is {shown_computed} and the test is "
            f"{comparator} {shown_threshold}. {source_note}{waiver_note} {LIMITATION}"
        ),
        "computed_scaled": computed,
        "threshold_scaled": threshold_scaled,
        "headroom_scaled": slack,
        "numerator": numerator,
        "denominator": denominator,
        "derivation": derivation,
        "provisions": resolution,
        "obligation": obligation,
        "limitation": LIMITATION,
    }
