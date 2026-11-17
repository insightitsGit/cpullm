from types import SimpleNamespace

import pytest

from cpu_llm.prismlexicon import adapt_output, lexical_delivery


@pytest.mark.parametrize("source,expected", [
    ("A bright light appeared.", "A strong light appeared."),
    ("A bright student answered.", "A clever student answered."),
    ("A bright future is possible.", "A bright future is possible."),
    ("They reside in Oslo.", "They live in Oslo."),
    ("She resides in Oslo.", "She lives in Oslo."),
    ("She resided in Oslo.", "She lived in Oslo."),
    ("The values reside in memory.", "The values reside in memory."),
    ("It may happen prior to dawn.", "It may happen before dawn."),
])
def test_context_and_approved_forms(source, expected):
    adapted = adapt_output(source, "A2")
    assert adapted["text"] == expected
    assert adapted == adapt_output(source, "A2")
    assert all(change["cefr_level"] == "unknown" for change in adapted["applied_changes"])


def test_protected_content_and_rollback():
    protected = '“A bright student.” [source-1] `prior to` https://example.com/prior 10 mg, 95%, 2026-11-16.'
    text = "A bright light appeared. " + protected
    assert adapt_output(text, "auto")["text"] == "A strong light appeared. " + protected
    assert adapt_output(text, "A1", protected_spans=[(2, 8)])["text"] == text
    assert not adapt_output(text, "A1", protected_spans=[(-1, 2)])["integrity_passed"]
    assert adapt_output(text, "C2")["text"] == text
    with pytest.raises(ValueError):
        adapt_output(text, "unknown")


def test_delivery_runs_after_answer_and_keeps_evidence_and_research():
    calls = []
    proof = [{"span": "The bright student may visit."}]

    @lexical_delivery
    def ask(self, message, **kwargs):
        calls.append(message)
        return dict(answer_status="answered", answer_evidence=proof, reply={
            "text": "A bright light appeared. The bright student may visit.",
            "body": "A bright light appeared. The bright student may visit.",
        }, **getattr(self, "extra", {}))

    config = SimpleNamespace(prismlexicon=True)
    result = ask(config, "What happened? Use simple English.")
    assert calls == ["What happened?"]
    assert result["reply"]["text"] == "A strong light appeared. The bright student may visit."
    assert result["reply"]["original_text"] == result["reply"]["body"]
    assert result["answer_evidence"] is proof
    config.extra = {"invention": {"proposals": ["unchanged"]}}
    research = ask(config, "Investigate light", target_level="A2")
    assert research["prismlexicon"]["abstentions"] == ["protected_response"]
    assert research["invention"]["proposals"] == ["unchanged"]
    assert "prismlexicon" not in ask(SimpleNamespace(), "What happened?", target_level="A2")

def test_http_level_is_validated_and_forwarded():
    from unittest.mock import Mock

    from cpu_llm.serve import _dispatch

    entry = SimpleNamespace(ask=Mock(return_value={"reply": {"text": "answer"}}))
    status, _ = _dispatch(entry, "/v1/ask", "test", {"message": "Question?", "target_level": "a2"})
    assert status == 200
    entry.ask.assert_called_once_with("test", "Question?", target_level="A2")
    with pytest.raises(ValueError):
        _dispatch(entry, "/v1/ask", "test", {"message": "Question?", "target_level": 2})
