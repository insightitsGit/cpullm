"""PrismAgenticPay corporate policy refuses a blocked vendor."""

from prismagenticpay.core.evaluator import PrismThinkerPaymentEvaluator
from prismagenticpay.domain.models import AuthorityState, MerchantIdentity, PaymentProposal
from prismagenticpay.policies.corporate import CORPORATE_POLICY_VERSION, default_corporate_policies

from cpu_llm.pipeline import evaluate_payment


def _proposal() -> PaymentProposal:
    return PaymentProposal(
        transaction_id="tx-blocked",
        amount_cents=2500,
        currency="USD",
        merchant=MerchantIdentity(
            merchant_id="merchant-1",
            merchant_name="Blocked Vendor",
            mcc="5734",
            domain="vendor.example",
        ),
        category="software",
        agent_id="agent-1",
        principal_id="principal-1",
        mandate_id="mandate-1",
        mandate_type="closed_payment",
        mandate_hash="a" * 64,
        idempotency_nonce="nonce-1",
    )


def _authority(status: str) -> AuthorityState:
    return AuthorityState(
        transaction_cap_cents=100_000,
        session_remaining_cents=100_000,
        daily_remaining_cents=100_000,
        mandate_remaining_cents=100_000,
        vendor_status=status,
        tier="standard",
    )


def test_blocked_vendor_is_refused():
    evaluator = PrismThinkerPaymentEvaluator(default_corporate_policies())
    outcome = evaluate_payment(evaluator, _proposal(), _authority("blocked"))
    assert outcome.directive == "REFUSE"
    assert CORPORATE_POLICY_VERSION == "1.1.0"
