"""Opt-in external answer node for unsupported single-turn requests."""

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class ExternalLLMFallback:
    """An application-owned provider adapter and exactly one credential source."""

    generate: Callable[[str, str], str]
    enabled: bool = False
    api_key: str | None = field(default=None, repr=False)
    oidc_access_token: Callable[[], str | None] | None = field(default=None, repr=False)

    def apply(self, prompt: str, result: dict) -> dict:
        if (
            not self.enabled
            or result.get("answer_status") != "unsupported"
            or result.get("guard_decision") != "allow"
            or result.get("access_error")
            or result.get("needs_clarification")
            or result.get("task_results")
        ):
            return result
        if (self.api_key is None) == (self.oidc_access_token is None):
            return result
        try:
            token = self.api_key if self.oidc_access_token is None else self.oidc_access_token()
            if not isinstance(token, str) or not token.strip():
                return result
            text = self.generate(prompt, token.strip())
        except Exception:
            # Preserve the engine's response on authentication or provider failure.
            return result
        if not isinstance(text, str) or not text.strip():
            return result
        return dict(
            status="external_unverified",
            answer_status="external_unverified",
            reply=dict(
                text=text.strip() + "\n\nExternal model response. CPU-LLM did not verify it against sources.",
                answer_status="external_unverified",
            ),
            audit_passed=False,
            answer_evidence=[],
            supporting_evidence=[],
            external_llm=dict(used=True, verification="unverified"),
        )
