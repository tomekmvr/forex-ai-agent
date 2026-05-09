from src.config.ai_settings import AISettings
from src.config.settings import ExecutionSettings


def test_validate_credentials_requires_account_id(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "oanda_practice")
    monkeypatch.setenv("FOREX_AGENT_API_KEY", "secret")
    monkeypatch.delenv("FOREX_AGENT_ACCOUNT_ID", raising=False)

    settings = ExecutionSettings.from_env()

    try:
        settings.validate_credentials()
    except ValueError as exc:
        assert "account ID" in str(exc)
    else:
        raise AssertionError("validate_credentials should reject missing account ID")


def test_validate_credentials_accepts_complete_oanda_configuration(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "oanda_practice")
    monkeypatch.setenv("FOREX_AGENT_API_KEY", "secret")
    monkeypatch.setenv("FOREX_AGENT_ACCOUNT_ID", "101-001-1234567-001")

    settings = ExecutionSettings.from_env()

    settings.validate_credentials()


def test_validate_mt5_credentials_accepts_relay_configuration(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "tms_oanda_mt5")
    monkeypatch.setenv("FOREX_AGENT_MT5_RELAY_URL", "http://127.0.0.1:8765")
    monkeypatch.delenv("FOREX_AGENT_MT5_LOGIN", raising=False)
    monkeypatch.delenv("FOREX_AGENT_MT5_PASSWORD", raising=False)
    monkeypatch.delenv("FOREX_AGENT_MT5_SERVER", raising=False)

    settings = ExecutionSettings.from_env()

    settings.validate_mt5_credentials()
    assert settings.has_mt5_relay is True


def test_ai_settings_default_to_supervisor_mode_when_openai_enabled(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.delenv("FOREX_AGENT_AI_DECISION_MODE", raising=False)

    settings = AISettings.from_env()

    assert settings.enabled is True
    assert settings.decision_mode == "supervisor"


def test_ai_settings_reject_invalid_decision_mode(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("FOREX_AGENT_AI_DECISION_MODE", "invalid")

    try:
        AISettings.from_env()
    except ValueError as exc:
        assert "AI_DECISION_MODE" in str(exc)
    else:
        raise AssertionError("AISettings.from_env should reject unsupported decision modes")