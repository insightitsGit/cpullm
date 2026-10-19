"""Finance checks are optional agents. A definition question does not enter them."""

import hashlib
import json

from cpu_llm.agents.finance import run_finance
from cpu_llm.agents.reply import compose_reply
from cpu_llm.clauses import proposition_from_chunk
from cpu_llm.classifier import finance_trigger
from cpu_llm.finance import validate_message
from cpu_llm.finance.ledgercovenant import decide, solve_addbacks
from cpu_llm.ingest import FINANCE_PREFIX, SOURCE_PREFIX, TEXTBOOK_PREFIX
from cpu_llm.pipeline import _after_math, _after_shine, _finance
from cpu_llm.source import finance_chunks


REFUND = """
Review this RefundProof finding.
vendor: Northwind
invoice: INV-100
tax charged: 120.0000
correct tax: 40.0000
deadline: ACTIONABLE
"""

COVENANT = """
Decide this LedgerCovenant test.
test date: 2026-03-31
comparator: lte
threshold: 4.50
numerator: compliance_certificate 9000000
numerator: audited_financials 9100000
denominator: compliance_certificate 2000000
"""

LOCK = """
Attest this Ledgerlock field.
document type: w2_stip
document id: w2-1
document text: Wages 84210.00
field: w2_box1_wages 84210.00 confidence 0.99 span 6-14
"""


def test_a_plain_question_does_not_ask_for_finance():
    assert finance_trigger("What is the European lobster?") == []
    assert finance_trigger("What is RefundProof?") == []
    assert finance_trigger("What is LedgerCovenant?") == []
    assert finance_trigger("What is Ledgerlock?") == []
    assert finance_trigger(REFUND)
    assert finance_trigger(COVENANT)
    assert finance_trigger(LOCK)
    assert _after_shine({}) == "reply"
    assert _after_shine({"finance": True, "compare": True}) == "compare"
    assert _after_shine({"finance": True}) == "finance"
    assert _after_shine({"math": True, "finance": True}) == "math"
    assert _after_math({"finance": True}) == "finance"
    assert _after_math({}) == "reply"
    assert _after_shine({"delivery_blocked": True, "finance": True}) == "finance"
    assert _after_shine({"delivery_blocked": True, "finance": True, "guard_decision": "block"}) == "reply"
    assert _after_shine({"delivery_blocked": True, "frame": True}) == "reply"
    assert _after_shine({"frame": True}) == "frame"


def test_refundproof_keeps_unverified_dollars_out_of_the_actionable_total():
    result = validate_message(REFUND)
    check = result["checks"][0]
    assert check["verdict"] in {"REVIEWED", "BLOCKED"}
    assert check["findings"][0]["recoverable_amount"] == "80.0000"
    assert check["findings"][0]["evidence_status"] == "unverified"
    assert check["findings"][0]["approval_blocked"]
    assert check["totals"]["actionable_by_currency"] == {}
    assert check["totals"]["potential_by_currency"] == {"USD": "80.0000"}
    assert "not tax advice" in check["text"]
    assert "proposition" not in check


def test_refundproof_verifies_bytes_and_still_does_not_approve():
    source = b"invoice INV-100 tax line"
    rule = b"rule version 2024.1 resale"
    message = f"""
    Review this RefundProof finding.
    vendor: Northwind
    invoice: INV-100
    tax charged: 120.0000
    correct tax: 40.0000
    deadline: ACTIONABLE
    state: POTENTIAL_OVERPAYMENT
    source hash: {hashlib.sha256(source).hexdigest()}
    rule hash: {hashlib.sha256(rule).hexdigest()}
    rule version: 2024.1
    source bytes: {source.decode()}
    rule bytes: {rule.decode()}
    """
    check = validate_message(message)["checks"][0]
    assert check["findings"][0]["evidence_status"] == "verified"
    assert check["findings"][0]["approval_blocked"] == ""
    assert "Ready for a human reviewer" in check["text"]
    assert check["findings"][0]["eligible_actionable"] is False
    assert check["totals"]["actionable_by_currency"] == {}


def test_refundproof_blocks_a_hash_mismatch_an_expired_deadline_and_a_duplicate():
    source = b"source"
    rule = b"rule"
    good_hash = hashlib.sha256(source).hexdigest()
    message = f"""
    Review this RefundProof finding.
    vendor: Northwind
    invoice: INV-100
    tax charged: 10.0000
    correct tax: 0.0000
    deadline: EXPIRED
    source hash: {good_hash}
    rule hash: {hashlib.sha256(rule).hexdigest()}
    rule version: 2024.1
    registered rule version: 2024.2
    source bytes: source
    rule bytes: rule
    ---
    vendor: Northwind
    invoice: INV-200
    tax charged: 10.0000
    correct tax: 4.0000
    deadline: ACTIONABLE
    ---
    vendor: Northwind
    invoice: INV-200
    line: 2
    tax charged: 8.0000
    correct tax: 1.0000
    deadline: ACTIONABLE
    """
    # The second and third findings differ by line, so they are not duplicates.
    # A same-line pair is checked below.
    check = validate_message(message)["checks"][0]
    assert check["findings"][0]["evidence_status"] == "mismatched"
    assert check["totals"]["potential_by_currency"].get("USD") == "13.0000"

    duplicate = validate_message(
        """
        Review this RefundProof finding.
        vendor: Northwind
        invoice: INV-200
        tax charged: 10.0000
        correct tax: 4.0000
        deadline: ACTIONABLE
        ---
        vendor: Northwind
        invoice: INV-200
        tax charged: 9.0000
        correct tax: 1.0000
        deadline: ACTIONABLE
        """
    )["checks"][0]
    assert {row["duplicate_status"] for row in duplicate["findings"]} == {"suspected"}
    assert duplicate["totals"]["potential_by_currency"] == {}
    assert duplicate["totals"]["actionable_by_currency"] == {}


def test_refundproof_tracks_recovery_only_after_a_persisted_reviewer():
    source = b"source-bytes"
    rule = b"rule-bytes"
    message = f"""
    Review this RefundProof finding.
    vendor: Northwind
    invoice: INV-9
    tax charged: 15.5000
    correct tax: 5.5000
    deadline: EXPIRING_SOON
    state: REVIEW_APPROVED
    reviewer: alex@example.com
    reviewed at: 2026-03-01
    source hash: {hashlib.sha256(source).hexdigest()}
    rule hash: {hashlib.sha256(rule).hexdigest()}
    rule version: 2024.1
    source bytes: {source.decode()}
    rule bytes: {rule.decode()}
    """
    check = validate_message(message)["checks"][0]
    assert check["findings"][0]["recovery_blocked"] == ""
    assert check["findings"][0]["eligible_actionable"] is True
    assert check["totals"]["actionable_by_currency"] == {"USD": "10.0000"}


def test_a_credit_note_is_not_a_recovery_packet():
    check = validate_message(
        """
        Review this RefundProof finding.
        vendor: Northwind
        invoice: CN-1
        document type: credit_note
        tax charged: -12.0000
        correct tax: 0
        """
    )["checks"][0]
    assert check["findings"][0]["credit_amount"] == "12.0000"
    assert check["findings"][0]["recoverable_amount"] == "0.0000"
    assert "not ordinary recovery packets" in check["findings"][0]["recovery_blocked"]
    assert check["totals"]["actionable_by_currency"] == {}


def test_a_float_tax_amount_is_refused():
    payload = {
        "product": "refundproof",
        "findings": [
            {
                "vendor": "Northwind",
                "invoiceNumber": "INV-1",
                "taxCharged": 10.5,
                "correctTax": "4.0000",
            }
        ],
    }
    check = validate_message("Review this RefundProof finding.\n" + json.dumps(payload))["checks"][0]
    assert check["findings"][0]["verdict"] == "INPUT_INVALID"
    assert "float" in check["findings"][0]["text"].casefold()


def test_ledgercovenant_uses_the_higher_source_and_refuses_a_tie():
    check = validate_message(COVENANT)["checks"][0]
    assert check["verdict"] == "COMPLIANT"
    assert check["numerator"]["source"] == "compliance_certificate"
    assert "audited_financials" in check["numerator"]["outranked"]
    assert "4.50x" in check["text"]
    assert "does not declare a default" in check["text"]

    conflict = validate_message(
        """
        Decide this LedgerCovenant test.
        comparator: lte
        threshold: 4.50
        numerator: compliance_certificate 9000000
        numerator: compliance_certificate 9100000
        denominator: compliance_certificate 2000000
        """
    )["checks"][0]
    assert conflict["verdict"] == "FACT_CONFLICT"
    assert "not an average" in conflict["text"]
    assert "COMPLIANT" not in conflict["text"]


def test_two_surviving_provisions_stay_ambiguous():
    check = validate_message(
        """
        Decide this LedgerCovenant test.
        test date: 2026-06-30
        comparator: lte
        threshold: 4.50
        numerator: compliance_certificate 9000000
        denominator: compliance_certificate 2000000
        provision: v1 credit_agreement 2024-01-01
        provision: v2 amendment 2025-01-01 amends v1
        """
    )["checks"][0]
    assert check["verdict"] == "COMPLIANT"
    assert check["provisions"]["governing"]["id"] == "v2"

    ambiguous = validate_message(
        """
        Decide this LedgerCovenant test.
        test date: 2026-06-30
        comparator: lte
        threshold: 4.50
        numerator: compliance_certificate 9000000
        denominator: compliance_certificate 2000000
        provision: v1 amendment 2024-01-01
        provision: v2 amendment 2025-01-01
        """
    )["checks"][0]
    assert ambiguous["verdict"] == "AMBIGUOUS"
    assert "No ratio was computed" in ambiguous["text"]
    assert ambiguous["verdict"] != "COMPLIANT"


def test_a_lineage_cycle_and_a_deleted_obligation_do_not_invent_a_ratio():
    cycle = validate_message(
        """
        Decide this LedgerCovenant test.
        test date: 2026-06-30
        comparator: lte
        threshold: 4.50
        numerator: compliance_certificate 9000000
        denominator: compliance_certificate 2000000
        provision: v1 amendment 2024-01-01 amends v2
        provision: v2 amendment 2025-01-01 amends v1
        """
    )["checks"][0]
    assert cycle["verdict"] == "AMBIGUOUS"
    assert "No ratio was computed" in cycle["text"]

    deleted = validate_message(
        """
        Decide this LedgerCovenant test.
        test date: 2026-06-30
        comparator: lte
        threshold: 4.50
        numerator: compliance_certificate 9000000
        denominator: compliance_certificate 2000000
        provision: v1 credit_agreement 2024-01-01
        provision: v2 amendment 2025-01-01 amends v1 operation DELETE
        """
    )["checks"][0]
    assert deleted["verdict"] == "NOT_APPLICABLE"
    assert "No test was run" in deleted["text"]


def test_an_identical_finding_is_counted_once():
    check = validate_message(
        """
        Review this RefundProof finding.
        vendor: Northwind
        invoice: INV-1
        tax charged: 10.0000
        correct tax: 4.0000
        deadline: ACTIONABLE
        ---
        vendor: Northwind
        invoice: INV-1
        tax charged: 10.0000
        correct tax: 4.0000
        deadline: ACTIONABLE
        """
    )["checks"][0]
    assert [row["duplicate_status"] for row in check["findings"]] == ["unique", "replay"]
    assert check["totals"]["potential_by_currency"] == {"USD": "6.0000"}


def test_a_breach_with_a_waiver_stays_a_breach_on_the_record():
    check = validate_message(
        """
        Decide this LedgerCovenant test.
        comparator: lte
        threshold: 4.00
        waiver: yes
        numerator: compliance_certificate 10000000
        denominator: compliance_certificate 2000000
        """
    )["checks"][0]
    assert check["verdict"] == "WAIVED"
    assert "does not make the test compliant" in check["text"]


def test_an_unsettled_add_back_is_refused_and_a_settled_one_is_exact():
    settled = solve_addbacks(
        base="1000000",
        components=[{"key": "restructuring", "claimed": "300000", "cap_percent": "20%", "basis": "result"}],
    )
    assert settled["display"] == "USD 1,250,000.00"
    assert settled["status"] == "SETTLED"
    spoken = validate_message(
        """
        Decide this LedgerCovenant add-back cap.
        add-back base: 1000000
        add-back: restructuring claimed 300000 cap 20% of result
        """
    )["checks"][0]
    assert spoken["verdict"] == "SETTLED"
    assert "USD 1,250,000.00" in spoken["text"]

    refused = validate_message(
        """
        Decide this LedgerCovenant add-back cap.
        add-back base: 1000000
        max iterations: 1
        add-back: restructuring claimed 300000 cap 20% of result
        """
    )["checks"][0]
    assert refused["verdict"] == "INPUT_INVALID"
    assert "did not settle" in refused["text"]


def test_overlapping_thresholds_are_not_chosen():
    payload = {
        "product": "ledgercovenant",
        "testDate": "2026-03-31",
        "comparator": "lte",
        "schedules": [
            {"effective_from": "2026-01-01", "effective_to": "2026-12-31", "threshold": "4.50"},
            {"effective_from": "2026-01-01", "threshold": "4.00"},
        ],
        "numerator": [{"source": "compliance_certificate", "value": "1"}],
        "denominator": [{"source": "compliance_certificate", "value": "1"}],
    }
    check = validate_message("Decide this LedgerCovenant test.\n" + json.dumps(payload))["checks"][0]
    assert check["verdict"] == "INPUT_INVALID"
    assert "commercial term" in check["text"]


def test_a_zero_denominator_is_refused():
    check = decide(
        {
            "comparator": "lte",
            "threshold": "4.50",
            "numerator": [{"source": "compliance_certificate", "value": "10"}],
            "denominator": [{"source": "compliance_certificate", "value": "0"}],
        }
    )
    assert check["verdict"] == "INPUT_INVALID"
    assert "zero denominator" in check["text"]


def test_ledgerlock_accepts_reviews_and_refuses_from_the_span_and_the_floor():
    accepted = validate_message(LOCK)["checks"][0]
    assert accepted["verdict"] == "ACCEPT"
    assert accepted["digest"]
    assert "sha256:" in accepted["text"]
    assert "not a loan-system write" in accepted["text"]
    assert "Ed25519" in accepted["limitation"]

    below_floor = validate_message(
        """
        Attest this Ledgerlock field.
        document type: w2_stip
        document text: Wages 84210.00
        field: w2_box1_wages 84210.00 confidence 0.96 span 6-14
        """
    )["checks"][0]
    assert below_floor["verdict"] == "REFUSE"
    assert "extraction floor" in below_floor["text"]

    missing_span = validate_message(
        """
        Attest this Ledgerlock field.
        document type: w2_stip
        document text: Wages 84210.00
        field: w2_box1_wages 84210.00 confidence 0.99
        """
    )["checks"][0]
    assert missing_span["verdict"] == "REVIEW"
    assert "source span" in missing_span["text"]

    mismatch = validate_message(
        """
        Attest this Ledgerlock field.
        document type: w2_stip
        document text: Wages 84210.00
        field: w2_box1_wages 100.00 confidence 0.99 span 6-14
        """
    )["checks"][0]
    assert mismatch["verdict"] == "REFUSE"
    assert "does not contain" in mismatch["text"]

    floated = {
        "product": "ledgerlock",
        "documentType": "w2_stip",
        "documentText": "Wages 84210.00",
        "fields": [{"fieldId": "w2_box1_wages", "value": "84210.00", "confidence": 0.99, "spanStart": 6, "spanEnd": 14}],
    }
    refused_float = validate_message("Attest this Ledgerlock field.\n" + json.dumps(floated))["checks"][0]
    assert refused_float["verdict"] == "INPUT_INVALID"
    assert "float" in refused_float["text"].casefold()

    injected = validate_message(
        """
        Attest this Ledgerlock field.
        document type: w2_stip
        document text: INJECTION_DETECTED
        field: w2_box1_wages 84210.00 confidence 0.99 span 0-4
        """
    )["checks"][0]
    assert injected["verdict"] == "REFUSE"


def test_the_finance_node_does_not_store_a_proposition():
    result = _finance(None)({"message": REFUND, "finance_reasons": finance_trigger(REFUND)})
    assert result["finance_result"]["checks"][0]["findings"][0]["recoverable_amount"] == "80.0000"
    assert "proposition" not in result


def test_a_finance_question_is_spoken_as_the_check():
    reply = compose_reply(
        {
            "message": REFUND,
            "guard_decision": "allow",
            "finance": True,
            "answer": "The European lobster is Homarus gammarus.",
            "finance_result": validate_message(REFUND),
        }
    )
    assert reply["text"].startswith("RefundProof:")
    assert "80.0000" in reply["text"]
    assert "Homarus" not in reply["text"]
    assert reply["body"] == "The European lobster is Homarus gammarus."


def test_finance_sits_beside_another_agent():
    reply = compose_reply(
        {
            "message": "Summarize the lobster and review this RefundProof finding.",
            "guard_decision": "allow",
            "finance": True,
            "summarize": True,
            "answer": "The European lobster is Homarus gammarus.",
            "brief": {"summary": "The European lobster is Homarus gammarus."},
            "finance_result": run_finance(REFUND),
        }
    )
    assert reply["text"].startswith("The European lobster is Homarus gammarus.")
    assert "Summary:" in reply["text"]
    assert "Finance:\nRefundProof:" in reply["text"]


def test_the_finance_knowledge_base_is_its_own_source():
    chunks = finance_chunks()
    assert len(chunks) == 14
    ids = [document_id for document_id, _title, _text in chunks]
    assert len(set(ids)) == len(ids)
    assert all(document_id.startswith("finance-validation-md-") for document_id in ids)
    assert FINANCE_PREFIX == "finance-validation-md-p"
    assert not FINANCE_PREFIX.startswith(SOURCE_PREFIX)
    assert FINANCE_PREFIX != TEXTBOOK_PREFIX
    missed = []
    for document_id, _title, text in chunks:
        if proposition_from_chunk(document_id, text) is None:
            missed.append(text.split(". ")[0])
    assert missed == []
