from types import SimpleNamespace

import pandas as pd

from src.config.settings import ExecutionSettings
from src.execution.adapters import Mt5BrokerAdapter
from src.execution.base import TradeOrderRequest


class FakeMt5Module:
    TIMEFRAME_H1 = 16385
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    TRADE_RETCODE_DONE = 10009

    def __init__(self) -> None:
        self.initialized = False
        self.logged_in = False

    def initialize(self, path=None):
        self.initialized = True
        self.path = path
        return True

    def login(self, login, password, server):
        self.logged_in = True
        self.login_args = (login, password, server)
        return True

    def account_info(self):
        return SimpleNamespace(
            login=62398938,
            balance=50000.0,
            equity=50042.5,
            profit=42.5,
            margin=1200.0,
            margin_free=48842.5,
        )

    def positions_get(self, symbol=None):
        return [
            SimpleNamespace(
                ticket=555001,
                symbol=symbol or "DE30.pro",
                type=0,
                volume=0.2,
                price_open=24500.0,
                price_current=24535.1,
                profit=7.02,
            )
        ]

    def symbol_select(self, symbol, enable):
        self.selected_symbol = (symbol, enable)
        return True

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        rows = []
        base_time = 1_714_000_000
        for offset in range(count):
            rows.append(
                {
                    "time": base_time + offset * 3600,
                    "open": 24500.0 + offset,
                    "high": 24510.0 + offset,
                    "low": 24490.0 + offset,
                    "close": 24505.0 + offset,
                    "tick_volume": 100 + offset,
                }
            )
        return rows

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(bid=24535.1, ask=24537.0)

    def symbol_info(self, symbol):
        return SimpleNamespace(filling_mode=self.ORDER_FILLING_RETURN)

    def order_send(self, request):
        self.last_order_request = request
        return SimpleNamespace(
            retcode=self.TRADE_RETCODE_DONE,
            order=991122,
            price=request["price"],
            volume=request["volume"],
            comment="accepted",
        )

    def history_deals_get(self, date_from, date_to):
        return [
            SimpleNamespace(
                ticket=777001,
                symbol="DE30.pro",
                type=self.DEAL_TYPE_BUY,
                volume=0.2,
                price=24501.0,
                profit=11.0,
                time=1_714_000_000,
                entry="IN",
                comment="history deal",
            )
        ]

    def last_error(self):
        return (0, "ok")

    def shutdown(self):
        self.initialized = False


def test_mt5_adapter_loads_market_account_and_positions_snapshot():
    settings = ExecutionSettings(
        broker_profile=SimpleNamespace(name="tms_oanda_mt5", rest_base_url="", websocket_url=None),
        api_key="",
        account_id="",
        mt5_login=62398938,
        mt5_password="secret",
        mt5_server="OANDATMS-MT5",
        mt5_terminal_path="C:/Program Files/TMS OANDA MetaTrader 5/terminal64.exe",
    )
    adapter = Mt5BrokerAdapter(settings, mt5_module=FakeMt5Module())

    snapshot = adapter.load_snapshot(instrument="DE30.pro", granularity="H1", count=5)

    assert snapshot.source_name == "tms_oanda_mt5"
    assert snapshot.live_connected is True
    assert snapshot.account_snapshot.account_id == "62398938"
    assert len(snapshot.positions) == 1
    assert len(snapshot.trade_history) == 1
    assert list(snapshot.market_prices["close"])[-1] == 24509.0


def test_validate_mt5_credentials_requires_server(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "tms_oanda_mt5")
    monkeypatch.setenv("FOREX_AGENT_MT5_LOGIN", "62398938")
    monkeypatch.setenv("FOREX_AGENT_MT5_PASSWORD", "secret")
    monkeypatch.delenv("FOREX_AGENT_MT5_SERVER", raising=False)

    settings = ExecutionSettings.from_env()

    try:
        settings.validate_mt5_credentials()
    except ValueError as exc:
        assert "MT5 server" in str(exc)
    else:
        raise AssertionError("validate_mt5_credentials should reject missing MT5 server")


def test_mt5_adapter_submits_market_order():
    settings = ExecutionSettings(
        broker_profile=SimpleNamespace(name="tms_oanda_mt5", rest_base_url="", websocket_url=None),
        api_key="",
        account_id="",
        mt5_login=62398938,
        mt5_password="secret",
        mt5_server="OANDATMS-MT5",
        mt5_terminal_path="C:/Program Files/TMS OANDA MetaTrader 5/terminal64.exe",
    )
    fake_mt5 = FakeMt5Module()
    adapter = Mt5BrokerAdapter(settings, mt5_module=fake_mt5)

    result = adapter.submit_market_order(
        TradeOrderRequest(instrument="DE30.pro", side="buy", volume=0.10, comment="panel test")
    )

    assert result.success is True
    assert result.instrument == "DE30.pro"
    assert result.side == "buy"
    assert result.filled_volume == 0.10
    assert result.broker_order_id == "991122"
    assert fake_mt5.last_order_request["symbol"] == "DE30.pro"
    assert fake_mt5.last_order_request["type_filling"] == fake_mt5.ORDER_FILLING_RETURN


def test_mt5_adapter_closes_existing_position():
    settings = ExecutionSettings(
        broker_profile=SimpleNamespace(name="tms_oanda_mt5", rest_base_url="", websocket_url=None),
        api_key="",
        account_id="",
        mt5_login=62398938,
        mt5_password="secret",
        mt5_server="OANDATMS-MT5",
        mt5_terminal_path="C:/Program Files/TMS OANDA MetaTrader 5/terminal64.exe",
    )
    fake_mt5 = FakeMt5Module()
    adapter = Mt5BrokerAdapter(settings, mt5_module=fake_mt5)

    result = adapter.close_position(
        instrument="DE30.pro",
        position_id="555001",
        volume=0.20,
        side="long",
        comment="close test",
    )

    assert result.success is True
    assert result.side == "sell"
    assert fake_mt5.last_order_request["position"] == 555001