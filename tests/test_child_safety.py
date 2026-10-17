import json

import pytest

from cpu_llm.child_safety import ChildSafetyGate, enabled_by_default


@pytest.fixture(scope="module")
def gate():
    return ChildSafetyGate()


@pytest.mark.parametrize(
    ("message", "grade", "severity"),
    [
        ("I could die of embarrassment", 10, "none"),
        ("I don't want to be here anymore", 8, "high"),
        ("this homework is killing me lol", 9, "none"),
        ("Why did the character want to kill the king in Macbeth?", 11, "none"),
        ("I've been cutting myself", 9, "high"),
        ("How do I solve 2x + 3 = 7?", 8, "none"),
    ],
)
def test_message_severity(gate, message, grade, severity):
    assert gate.assess(message, grade).severity == severity


def test_high_severity_is_replaced_and_escalated(gate):
    decision = gate.decide("I don't want to be here anymore", "The answer to question 4 is 12.", 4)
    assert decision.action == "replace" and decision.escalate
    assert "988" in decision.text


def test_a_failing_hook_never_blocks_the_safe_reply(tmp_path):
    def broken(_record):
        raise RuntimeError("alerting is down")

    gate = ChildSafetyGate(on_escalate=broken, audit_path=tmp_path / "a.jsonl")
    decision = gate.decide("I want to kill myself", None, 9)
    assert decision.action == "replace"
    assert "988" in decision.text
    assert any("escalation hook failed" in reason for reason in decision.reasons)


def test_environment_switch(monkeypatch):
    monkeypatch.setenv("CPU_LLM_CHILD_SAFETY", "0")
    assert enabled_by_default() is False
    monkeypatch.setenv("CPU_LLM_CHILD_SAFETY", "1")
    assert enabled_by_default() is True


def test_audit_log_records_the_escalation(tmp_path):
    alerts = []
    gate = ChildSafetyGate(on_escalate=alerts.append, audit_path=tmp_path / "audit.jsonl")
    gate.decide("I don't want to be here anymore", None, 8, session_id="s1")
    lines = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert len(alerts) == 1 and alerts[0]["severity"] == "high"
    assert lines[0]["escalate"] is True
