"""Finance validation checks a caller can run from a question.

RefundProof reviews a sales-tax finding. LedgerCovenant decides a covenant
from the supplied figures. Ledgerlock attests an extracted mortgage number.
The spoken result is that check. It is not stored as a proposition.
"""

from __future__ import annotations

from typing import Any

from cpu_llm.finance.ledgercovenant import decide
from cpu_llm.finance.ledgerlock import attest
from cpu_llm.finance.parse import parse_sections
from cpu_llm.finance.refundproof import review
from cpu_llm.finance.triggers import finance_trigger, products_from, select_finance

__all__ = ["finance_trigger", "select_finance", "validate_message"]


def validate_message(message: str, *, forced: bool = False) -> dict[str, Any]:
    """Run every finance check the question asked for.

    ``triggered`` is false for a plain question, including "What is RefundProof?".
    A forced call with no product named says which checks exist.
    """
    selected = select_finance(message, forced=forced)
    products = products_from(selected)
    reasons = [reason for _product, reason in selected]
    if not products:
        text = ""
        if forced:
            text = (
                "Name RefundProof, LedgerCovenant, or Ledgerlock and include the fields that check needs."
            )
        return {
            "triggered": bool(forced),
            "reasons": reasons,
            "products": [],
            "text": text,
            "checks": [],
        }
    try:
        sections = parse_sections(message, products)
        checks: list[dict[str, Any]] = []
        for product in products:
            section = sections.get(product) or {}
            if product == "refundproof":
                checks.append(review(list(section.get("findings") or [])))
            elif product == "ledgercovenant":
                checks.append(decide(section))
            else:
                checks.append(attest(section))
    except (TypeError, ValueError) as exc:
        return {
            "triggered": True,
            "reasons": reasons,
            "products": products,
            "text": f"The finance check could not read the request. {exc}",
            "checks": [],
        }
    return {
        "triggered": True,
        "reasons": reasons,
        "products": products,
        "text": "\n\n".join(str(item.get("text") or "") for item in checks).strip(),
        "checks": checks,
    }
