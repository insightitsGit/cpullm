from cpu_llm.external_fallback import ExternalLLMFallback


def test_external_fallback_requires_opt_in_and_one_credential():
    unsupported = dict(answer_status="unsupported", guard_decision="allow")
    calls = []

    def generate(prompt, token):
        calls.append((prompt, token))
        return "Provider text"

    assert ExternalLLMFallback(generate, api_key="key").apply("test", unsupported) is unsupported
    assert ExternalLLMFallback(generate, enabled=True).apply("test", unsupported) is unsupported
    assert ExternalLLMFallback(generate, enabled=True, oidc_access_token=lambda: "").apply("test", unsupported) is unsupported
    assert not calls
    node = ExternalLLMFallback(generate, enabled=True, oidc_access_token=lambda: "token")
    assert node.apply("test", dict(unsupported, answer_status="insufficient_evidence"))["answer_status"] == "insufficient_evidence"
    assert node.apply("test", dict(unsupported, guard_decision="block"))["guard_decision"] == "block"
    result = node.apply("test", unsupported)
    assert calls == [("test", "token")]
    assert result["answer_status"] == "external_unverified"
    assert result["answer_evidence"] == []
    assert "did not verify" in result["reply"]["text"]
