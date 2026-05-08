from src.admin.ui_defaults import build_runtime_hint, resolve_default_execution_mode, resolve_default_source_mode


def test_resolve_default_source_mode_prefers_demo_for_linux_mt5_without_relay(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "tms_oanda_mt5")
    monkeypatch.delenv("FOREX_AGENT_MT5_RELAY_URL", raising=False)
    monkeypatch.delenv("FOREX_AGENT_ADMIN_SOURCE_MODE", raising=False)

    assert resolve_default_source_mode() == "demo"


def test_resolve_default_source_mode_honors_explicit_override(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_ADMIN_SOURCE_MODE", "broker")

    assert resolve_default_source_mode() == "broker"


def test_resolve_default_execution_mode_defaults_to_paper(monkeypatch):
    monkeypatch.delenv("FOREX_AGENT_ADMIN_EXECUTION_MODE", raising=False)

    assert resolve_default_execution_mode() == "paper"


def test_build_runtime_hint_describes_linux_mt5_limit(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "tms_oanda_mt5")
    monkeypatch.delenv("FOREX_AGENT_MT5_RELAY_URL", raising=False)

    hint = build_runtime_hint("demo")

    assert "trybie demo" in hint