from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AISettings:
    provider: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    request_timeout_seconds: float = 20.0
    enabled: bool = False

    @classmethod
    def from_env(cls, prefix: str = "FOREX_AGENT") -> "AISettings":
        provider = os.getenv(f"{prefix}_AI_PROVIDER", "openai").strip().lower()
        openai_api_key = os.getenv("OPENAI_API_KEY", "") or os.getenv(f"{prefix}_OPENAI_API_KEY", "")
        openai_model = os.getenv(f"{prefix}_OPENAI_MODEL", "gpt-4.1-mini").strip()
        timeout = float(os.getenv(f"{prefix}_AI_TIMEOUT_SECONDS", "20"))
        enabled = provider == "openai" and bool(openai_api_key)
        return cls(
            provider=provider,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            request_timeout_seconds=timeout,
            enabled=enabled,
        )