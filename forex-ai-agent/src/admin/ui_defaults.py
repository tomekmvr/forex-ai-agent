from __future__ import annotations

import os
import platform

from src.config.settings import ExecutionSettings


def resolve_default_source_mode() -> str:
    configured_mode = os.getenv("FOREX_AGENT_ADMIN_SOURCE_MODE", "").strip().lower()
    if configured_mode in {"auto", "demo", "broker"}:
        return configured_mode

    try:
        settings = ExecutionSettings.from_env()
    except Exception:
        return "auto"

    if platform.system() == "Linux" and settings.is_mt5_profile and not settings.has_mt5_relay:
        return "demo"
    return "auto"


def resolve_default_execution_mode() -> str:
    configured_mode = os.getenv("FOREX_AGENT_ADMIN_EXECUTION_MODE", "").strip().lower()
    if configured_mode in {"paper", "live"}:
        return configured_mode
    return "paper"


def build_runtime_hint(source_mode: str) -> str:
    try:
        settings = ExecutionSettings.from_env()
    except Exception:
        return ""

    if platform.system() == "Linux" and settings.is_mt5_profile and not settings.has_mt5_relay:
        if source_mode == "demo":
            return "Linux wykryl profil MT5 bez relay, dlatego panel startuje domyslnie w trybie demo."
        return "Lokalne MT5 nie jest wspierane na Linux bez relay HTTP do Windows."
    return ""