from types import SimpleNamespace

import httpx
import pytest

from src.config.settings import ExecutionSettings
from src.execution.adapters import Mt5RelayBrokerAdapter, build_mt5_admin_adapter
from src.execution.mt5_relay import serve_mt5_relay


def test_build_mt5_admin_adapter_prefers_relay_when_url_present():
    settings = ExecutionSettings(
        broker_profile=SimpleNamespace(name="tms_oanda_mt5", rest_base_url="", websocket_url=None),
        api_key="",
        account_id="",
        mt5_relay_url="http://127.0.0.1:8765",
    )

    adapter = build_mt5_admin_adapter(settings)

    assert isinstance(adapter, Mt5RelayBrokerAdapter)


def test_validate_mt5_credentials_requires_relay_token(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "tms_oanda_mt5")
    monkeypatch.setenv("FOREX_AGENT_MT5_RELAY_URL", "http://127.0.0.1:8765")
    monkeypatch.delenv("FOREX_AGENT_MT5_RELAY_TOKEN", raising=False)

    settings = ExecutionSettings.from_env()

    with pytest.raises(ValueError, match="relay token"):
        settings.validate_mt5_credentials()


def test_mt5_relay_adapter_loads_snapshot_and_sends_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Relay-Token"] == "relay-secret"
        assert request.url.path == "/snapshot"
        return httpx.Response(
            200,
            json={
                "source_name": "tms_oanda_mt5",
                "status_message": "relay ok",
                "live_connected": True,
                "market_prices": [
                    {
                        "timestamp": "2026-01-01T00:00:00+0000",
                        "instrument": "DE30.pro",
                        "open": 24500.0,
                        "high": 24510.0,
                        "low": 24490.0,
                        "close": 24505.0,
                        "volume": 100,
                        "is_complete": True,
                    }
                ],
                "account_snapshot": {
                    "broker": "tms_oanda_mt5",
                    "account_id": "62398938",
                    "balance": 50000.0,
                    "equity": 50042.5,
                    "unrealized_pnl": 42.5,
                    "realized_pnl": 42.5,
                    "margin_used": 1200.0,
                    "margin_available": 48842.5,
                },
                "positions": [
                    {
                        "instrument": "DE30.pro",
                        "side": "long",
                        "units": 0.2,
                        "entry_price": 24500.0,
                        "current_price": 24535.1,
                        "unrealized_pnl": 7.02,
                        "realized_pnl": 0.0,
                        "position_id": "555001",
                    }
                ],
                "trade_history": [],
            },
        )

    settings = ExecutionSettings(
        broker_profile=SimpleNamespace(name="tms_oanda_mt5", rest_base_url="", websocket_url=None),
        api_key="",
        account_id="",
        mt5_relay_url="http://127.0.0.1:8765",
        mt5_relay_token="relay-secret",
    )
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=settings.mt5_relay_url)
    adapter = Mt5RelayBrokerAdapter(settings, client=client)

    snapshot = adapter.load_snapshot(instrument="DE30.pro", granularity="H1", count=1)

    assert snapshot.source_name == "tms_oanda_mt5"
    assert snapshot.live_connected is True
    assert snapshot.account_snapshot.account_id == "62398938"
    assert len(snapshot.positions) == 1
    assert float(snapshot.market_prices["close"].iloc[-1]) == 24505.0


def test_mt5_relay_server_requires_token_before_start():
    settings = ExecutionSettings(
        broker_profile=SimpleNamespace(name="tms_oanda_mt5", rest_base_url="", websocket_url=None),
        api_key="",
        account_id="",
        mt5_login=62398938,
        mt5_password="secret",
        mt5_server="OANDATMS-MT5",
        mt5_relay_token="",
    )

    with pytest.raises(ValueError, match="FOREX_AGENT_MT5_RELAY_TOKEN"):
        serve_mt5_relay(settings, host="127.0.0.1", port=8765)