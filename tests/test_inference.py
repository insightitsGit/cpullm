import hashlib
import pytest
from copy import deepcopy
from types import SimpleNamespace

from cpu_llm.inference import InferenceRequest, deduce, digest, execute_inference, verify_proof


def rows(*texts):
    return [dict(document_id=f"doc-p{int(hashlib.sha256(text.encode()).hexdigest()[:10], 16):012d}", chunk_text=text) for index, text in enumerate(texts, 1)]


def test_two_hop_order_and_replayed_source_proof():
    source = rows("The elephant is bigger than the donkey.", "The donkey is bigger than the cat.")
    request = InferenceRequest("the elephant", "bigger_than", "the cat")
    receipt = deduce(source, request, snapshot=42, scope=["doc-p"])
    assert receipt["verdict"] == "ENTAILED_BY_RULES"
    assert len(receipt["proof"]) == 3
    assert verify_proof(receipt["proof"], source, request)
    assert deduce(source[::-1], request, snapshot=42, scope=["doc-p"]) == receipt
    damaged = deepcopy(receipt["proof"])
    damaged[0]["source"]["span"] = "An unrelated sentence."
    damaged[0]["id"] = digest({k: v for k, v in damaged[0].items() if k != "id"})
    assert not verify_proof(damaged, source, request)
    changed = rows("The elephant is smaller than the donkey.", "The donkey is bigger than the cat.")
    assert not verify_proof(receipt["proof"], changed, request)


def test_universal_membership_keeps_rule_and_membership_sources():
    request = InferenceRequest("Kestrel", "has", "radio")
    source = rows("The Kestrel is a rescue cutter.", "Every rescue cutter has a radio.")
    assert deduce(source, request)["verdict"] == "ENTAILED_BY_RULES"
    assert deduce(source[:1], request)["verdict"] == "INSUFFICIENT_SUPPORT"
    assert deduce(rows("The Kestrel is a rescue cutter.", "Some rescue cutters have a radio."), request)["verdict"] == "INSUFFICIENT_SUPPORT"


def test_conflict_blocks_source_and_derived_conclusions_but_not_unrelated_ones():
    request = InferenceRequest("elephant", "bigger_than", "cat")
    source = rows("The elephant is bigger than the donkey.", "The donkey is bigger than the cat.")
    assert deduce(source + rows("The cat is bigger than the elephant."), request)["verdict"] == "CONFLICT"
    assert deduce(source + rows("The elephant is not bigger than the donkey."), request)["verdict"] == "CONFLICT"
    unrelated = rows("The whale is bigger than the fish.", "The whale is not bigger than the fish.")
    assert deduce(source + unrelated, request)["verdict"] == "ENTAILED_BY_RULES"


def test_resource_limit_and_hop_limit_are_visible():
    source = rows("The elephant is bigger than the donkey.", "The donkey is bigger than the cat.")
    assert deduce(source, InferenceRequest("elephant", "bigger_than", "cat", max_predicates=1))["verdict"] == "BUDGET_EXHAUSTED"
    assert deduce(source, InferenceRequest("elephant", "bigger_than", "cat", max_states=1))["verdict"] == "BUDGET_EXHAUSTED"
    assert deduce(source, InferenceRequest("elephant", "bigger_than", "cat", max_hops=1))["verdict"] == "ENTAILED_BY_RULES"


def test_public_route_blocks_strict_and_returns_citations():
    from cpu_llm.pipeline import Appliance

    app = object.__new__(Appliance)
    app.tenant_id = "test"
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision="allow"))
    source = rows("The elephant is bigger than the donkey.", "The donkey is bigger than the cat.")
    app.index = SimpleNamespace(strict_source_rows=lambda allowed, as_of=None: (source, as_of))
    response = app.ask("Infer whether the elephant is bigger than the cat.", as_of=42)
    assert response["answer_status"] == "derived_inference"
    assert len(response["evidence_panel"]["sources"]) == 2
    assert response["inference"]["snapshot"] == 42
    assert app.ask("Infer whether the elephant is bigger than the cat.", strict_evidence=True)["answer_status"] == "unsupported"

def test_scope_and_snapshot_are_bound_to_the_proof_and_audit():
    from cpu_llm.access import CallerContext
    from cpu_llm.pipeline import Appliance

    app = object.__new__(Appliance)
    app.tenant_id = "test"
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision="allow"))
    calls = []
    sources = [
        dict(document_id="public-p0001", chunk_text="The elephant is bigger than the donkey."),
        dict(document_id="secret-p0001", chunk_text="The donkey is bigger than the cat."),
    ]

    def snapshot(allowed, as_of=None):
        calls.append((allowed, as_of))
        return sources, as_of

    app.index = SimpleNamespace(strict_source_rows=snapshot)
    context = CallerContext(tenant_id="test", caller_id="reader", request_id="request", allowed_sources=frozenset({"public-p"}))
    query = "Infer whether the elephant is bigger than the cat."
    result = app.ask(query, caller=context, as_of=42)
    assert result["answer_status"] == "insufficient_evidence"
    assert result["answer_evidence"] == []
    assert calls == [(context.allowed_sources, 42)]
    assert "secret" not in str(result)
    one = deduce(sources, InferenceRequest("elephant", "bigger_than", "cat"), snapshot=42)
    two = deduce(sources, InferenceRequest("elephant", "bigger_than", "cat"), snapshot=43)
    assert one["audit_hash"] != two["audit_hash"]


def test_qualifications_and_cycle_limits_do_not_create_assertions():
    source = rows("If rain arrives the elephant is bigger than the cat.",
                  "The elephant might be bigger than the cat.")
    request = InferenceRequest("elephant", "bigger_than", "cat")
    assert deduce(source, request)["verdict"] == "INSUFFICIENT_SUPPORT"
    cyclic = rows("The elephant is bigger than the donkey.", "The donkey is bigger than the elephant.")
    result = deduce(cyclic, InferenceRequest("elephant", "bigger_than", "cat", max_operations=1))
    assert result["verdict"] == "BUDGET_EXHAUSTED"
    assert result["conclusion"] is None
    from cpu_llm.inference import request_from
    with pytest.raises(ValueError):
        request_from("question", {"mode": "inductive"})
    with pytest.raises(ValueError):
        request_from("question", {"subject": "elephant", "relation": "bigger_than", "object": "cat", "rules": []})

def test_result_replay_rejects_a_changed_conclusion_and_duplicate_versions():
    from cpu_llm.inference import verify_receipt

    source = rows("The elephant is bigger than the cat.")
    request = InferenceRequest("elephant", "bigger_than", "cat")
    receipt = deduce(source, request)
    assert verify_receipt(receipt, source)
    changed = deepcopy(receipt)
    changed["conclusion"][2] = "whale"
    assert not verify_receipt(changed, source)
    with pytest.raises(ValueError, match="one active version"):
        deduce(source + source, request)
