from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AISettings:
    provider: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    request_timeout_seconds: float = 20.0
    decision_mode: str = "supervisor"
    enabled: bool = False

    @classmethod
    def from_env(cls, prefix: str = "FOREX_AGENT") -> "AISettings":
        provider = os.getenv(f"{prefix}_AI_PROVIDER", "openai").strip().lower()
        openai_api_key = os.getenv("OPENAI_API_KEY", "") or os.getenv(f"{prefix}_OPENAI_API_KEY", "")
        openai_model = os.getenv(f"{prefix}_OPENAI_MODEL", "gpt-4.1-mini").strip()
        timeout = float(os.getenv(f"{prefix}_AI_TIMEOUT_SECONDS", "20"))
        decision_mode = os.getenv(f"{prefix}_AI_DECISION_MODE", "supervisor").strip().lower()
        enabled = provider == "openai" and bool(openai_api_key)
        if decision_mode not in {"advisory", "supervisor"}:
            raise ValueError("FOREX_AGENT_AI_DECISION_MODE must be either 'advisory' or 'supervisor'.")
        return cls(
            provider=provider,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            request_timeout_seconds=timeout,
            decision_mode=decision_mode,
            enabled=enabled,
        )