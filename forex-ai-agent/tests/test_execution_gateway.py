from src.config.settings import ExecutionSettings
from src.execution.gateway import MarketGateway


def test_execution_settings_from_env(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "ibkr_client_portal")
    monkeypatch.setenv("FOREX_AGENT_API_KEY", "secret")
    monkeypatch.setenv("FOREX_AGENT_ACCOUNT_ID", "DU123456")
    monkeypatch.setenv("FOREX_AGENT_REQUEST_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("FOREX_AGENT_VERIFY_SSL", "false")

    settings = ExecutionSettings.from_env()

    assert settings.broker_name == "ibkr_client_portal"
    assert settings.websocket_url == "wss://localhost:5000/v1/api/ws"
    assert settings.auth_headers()["Authorization"] == "Bearer secret"
    assert settings.request_timeout_seconds == 45.0
    assert settings.verify_ssl is False


def test_parse_oanda_candles_returns_ordered_dataframe():
    payload = {
        "candles": [
            {
                "time": "2026-05-08T10:05:00.000000000Z",
                "volume": 12,
                "complete": True,
                "mid": {"o": "1.1010", "h": "1.1025", "l": "1.1005", "c": "1.1020"},
            },
            {
                "time": "2026-05-08T10:00:00.000000000Z",
                "volume": 9,
                "complete": True,
                "mid": {"o": "1.1000", "h": "1.1015", "l": "1.0995", "c": "1.1010"},
            },
        ]
    }

    frame = MarketGateway.parse_oanda_candles(payload, instrument="EUR_USD")

    assert list(frame["close"]) == [1.1010, 1.1020]
    assert frame.iloc[0]["instrument"] == "EUR_USD"
    assert frame.iloc[1]["volume"] == 12