from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import platform
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Optional

import httpx
import pandas as pd
import structlog

from src.config.settings import ExecutionSettings
from src.execution.base import (
    AccountSnapshot,
    PositionSnapshot,
    TradeExecutionResult,
    TradeHistoryRecord,
    TradeOrderRequest,
)
from src.execution.gateway import MarketGateway
from src.execution.relay_payloads import (
    snapshot_from_payload,
    trade_execution_result_from_payload,
)

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - optional runtime dependency
    mt5 = None


@dataclass(frozen=True)
class BrokerDataSnapshot:
    source_name: str
    status_message: str
    live_connected: bool
    market_prices: pd.DataFrame
    account_snapshot: AccountSnapshot
    positions: tuple[PositionSnapshot, ...]
    trade_history: tuple[TradeHistoryRecord, ...] = field(default_factory=tuple)


class BrokerAdminAdapter(ABC):
    @abstractmethod
    def load_snapshot(self, *, instrument: str, granularity: str, count: int) -> BrokerDataSnapshot:
        raise NotImplementedError

    def submit_market_order(self, order: TradeOrderRequest) -> TradeExecutionResult:
        raise NotImplementedError(f"{self.__class__.__name__} does not support market order submission.")

    def close_position(
        self,
        *,
        instrument: str,
        position_id: str,
        volume: float,
        side: str,
        comment: str = "",
    ) -> TradeExecutionResult:
        raise NotImplementedError(f"{self.__class__.__name__} does not support position closing.")


class DemoBrokerAdapter(BrokerAdminAdapter):
    def __init__(self, base_balance: float = 100_000.0) -> None:
        self.base_balance = base_balance

    def load_snapshot(self, *, instrument: str, granularity: str, count: int) -> BrokerDataSnapshot:
        index = pd.date_range(end=pd.Timestamp.now("UTC").floor("h"), periods=count, freq="h")
        base = pd.Series(range(count), index=index, dtype=float)
        close = 1.08 + base * 0.00035 + (base % 5) * 0.00012
        market_prices = pd.DataFrame({"close": close}, index=index)
        entry_price = float(market_prices["close"].iloc[-10])
        current_price = float(market_prices["close"].iloc[-1])
        units = 25_000.0
        unrealized_pnl = (current_price - entry_price) * units
        positions = (
            PositionSnapshot(
                instrument=instrument,
                side="long",
                units=units,
                entry_price=entry_price,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=0.0,
                position_id="demo-position-1",
            ),
        )
        trade_history = (
            TradeHistoryRecord(
                ticket_id="demo-deal-1",
                instrument=instrument,
                side="buy",
                volume=units,
                price=entry_price,
                profit=unrealized_pnl,
                timestamp=index[-10].to_pydatetime(),
                entry_type="demo",
                comment="Demo seeded trade",
            ),
        )
        account = AccountSnapshot(
            broker="demo",
            account_id="demo-account",
            balance=self.base_balance,
            equity=self.base_balance + unrealized_pnl,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=0.0,
            margin_used=0.0,
            margin_available=self.base_balance + unrealized_pnl,
        )
        return BrokerDataSnapshot(
            source_name="demo",
            status_message=f"Demo data generated locally for {instrument} on {granularity}.",
            live_connected=False,
            market_prices=market_prices,
            account_snapshot=account,
            positions=positions,
            trade_history=trade_history,
        )

    def submit_market_order(self, order: TradeOrderRequest) -> TradeExecutionResult:
        return TradeExecutionResult(
            success=True,
            broker="demo",
            instrument=order.instrument,
            side=order.side,
            requested_volume=order.volume,
            filled_volume=order.volume,
            executed_price=0.0,
            broker_order_id="demo-order",
            status_code="DRY_RUN",
            message="Demo adapter simulated market order submission.",
            request_payload=order.to_record(),
        )

    def close_position(
        self,
        *,
        instrument: str,
        position_id: str,
        volume: float,
        side: str,
        comment: str = "",
    ) -> TradeExecutionResult:
        close_side = "sell" if side.lower() == "long" else "buy"
        return TradeExecutionResult(
            success=True,
            broker="demo",
            instrument=instrument,
            side=close_side,
            requested_volume=volume,
            filled_volume=volume,
            executed_price=0.0,
            broker_order_id=position_id or "demo-close-order",
            status_code="DRY_RUN_CLOSE",
            message="Demo adapter simulated position close.",
            request_payload={
                "instrument": instrument,
                "position_id": position_id,
                "volume": volume,
                "side": side,
                "comment": comment,
            },
        )


class OandaBrokerAdapter(BrokerAdminAdapter):
    def __init__(self, settings: ExecutionSettings) -> None:
        self.settings = settings

    def load_snapshot(self, *, instrument: str, granularity: str, count: int) -> BrokerDataSnapshot:
        gateway = MarketGateway(self.settings)
        try:
            market_prices = gateway.fetch_oanda_candles(
                instrument=instrument,
                granularity=granularity,
                count=count,
            )
            latest_price = 0.0 if market_prices.empty else float(market_prices["close"].iloc[-1])
            account = gateway.fetch_oanda_account_summary()
            positions = gateway.fetch_oanda_open_positions(current_prices={instrument: latest_price})
        finally:
            gateway.close()

        return BrokerDataSnapshot(
            source_name=self.settings.broker_name,
            status_message=f"Loaded broker snapshot for {instrument} from {self.settings.broker_name}.",
            live_connected=True,
            market_prices=market_prices,
            account_snapshot=account,
            positions=tuple(positions),
        )


class Mt5BrokerAdapter(BrokerAdminAdapter):
    _TIMEFRAME_MAP = {
        "M1": "TIMEFRAME_M1",
        "M5": "TIMEFRAME_M5",
        "M15": "TIMEFRAME_M15",
        "M30": "TIMEFRAME_M30",
        "H1": "TIMEFRAME_H1",
        "H4": "TIMEFRAME_H4",
        "D": "TIMEFRAME_D1",
        "W1": "TIMEFRAME_W1",
        "MN": "TIMEFRAME_MN1",
    }

    def __init__(self, settings: ExecutionSettings, mt5_module: Optional[Any] = None) -> None:
        self.settings = settings
        self.mt5 = mt5_module if mt5_module is not None else mt5
        self.logger = structlog.get_logger(__name__).bind(component="mt5_broker_adapter")

    def load_snapshot(self, *, instrument: str, granularity: str, count: int) -> BrokerDataSnapshot:
        self.settings.validate_mt5_credentials()
        module = self._require_mt5_module()
        if not self._initialize(module):
            raise RuntimeError(f"MT5 initialize failed: {module.last_error()}")

        try:
            authorized = module.login(
                self.settings.mt5_login,
                password=self.settings.mt5_password,
                server=self.settings.mt5_server,
            )
            if not authorized:
                raise RuntimeError(f"MT5 login failed: {module.last_error()}")

            market_prices = self._fetch_rates(module, instrument=instrument, granularity=granularity, count=count)
            account = self._fetch_account(module)
            positions = self._fetch_positions(module, instrument=instrument)
            trade_history = self._fetch_trade_history(module, instrument=instrument)
        finally:
            module.shutdown()

        return BrokerDataSnapshot(
            source_name=self.settings.broker_name,
            status_message=f"Loaded broker snapshot for {instrument} from MT5 server {self.settings.mt5_server}.",
            live_connected=True,
            market_prices=market_prices,
            account_snapshot=account,
            positions=tuple(positions),
            trade_history=tuple(trade_history),
        )

    def submit_market_order(self, order: TradeOrderRequest) -> TradeExecutionResult:
        self.settings.validate_mt5_credentials()
        module = self._require_mt5_module()
        if not self._initialize(module):
            raise RuntimeError(f"MT5 initialize failed: {module.last_error()}")

        try:
            authorized = module.login(
                self.settings.mt5_login,
                password=self.settings.mt5_password,
                server=self.settings.mt5_server,
            )
            if not authorized:
                raise RuntimeError(f"MT5 login failed: {module.last_error()}")

            if not module.symbol_select(order.instrument, True):
                raise RuntimeError(f"MT5 symbol_select failed for {order.instrument}: {module.last_error()}")

            tick = module.symbol_info_tick(order.instrument)
            if tick is None:
                raise RuntimeError(f"MT5 symbol_info_tick failed for {order.instrument}: {module.last_error()}")
            tick_record = self._coerce_record(tick)

            side = order.side.lower()
            order_type = module.ORDER_TYPE_BUY if side == "buy" else module.ORDER_TYPE_SELL
            price = float(tick_record.ask if side == "buy" else tick_record.bid)
            filling_mode = self._resolve_order_filling(module, order.instrument)

            request = {
                "action": module.TRADE_ACTION_DEAL,
                "symbol": order.instrument,
                "volume": float(order.volume),
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": 20260508,
                "comment": order.comment or "Forex AI Agent Admin",
                "type_time": module.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }
            result = module.order_send(request)
            if result is None:
                raise RuntimeError(f"MT5 order_send failed for {order.instrument}: {module.last_error()}")

            result_record = self._coerce_record(result)
            retcode = str(getattr(result_record, "retcode", "UNKNOWN"))
            success = retcode == str(module.TRADE_RETCODE_DONE)
            filled_volume = float(getattr(result_record, "volume", order.volume))
            executed_price = float(getattr(result_record, "price", price))
            broker_order_id = str(getattr(result_record, "order", getattr(result_record, "deal", "")))
            message = str(getattr(result_record, "comment", "")) or (
                "Order executed successfully." if success else "Order rejected by MT5."
            )
            self.logger.info(
                "reasoning_trace",
                step="submit_mt5_market_order",
                instrument=order.instrument,
                side=side,
                requested_volume=order.volume,
                retcode=retcode,
                success=success,
            )
            return TradeExecutionResult(
                success=success,
                broker=self.settings.broker_name,
                instrument=order.instrument,
                side=side,
                requested_volume=order.volume,
                filled_volume=filled_volume,
                executed_price=executed_price,
                broker_order_id=broker_order_id,
                status_code=retcode,
                message=message,
                request_payload=request,
            )
        finally:
            module.shutdown()

    def close_position(
        self,
        *,
        instrument: str,
        position_id: str,
        volume: float,
        side: str,
        comment: str = "",
    ) -> TradeExecutionResult:
        close_side = "sell" if side.lower() == "long" else "buy"
        order = TradeOrderRequest(
            instrument=instrument,
            side=close_side,
            volume=volume,
            comment=comment or f"Close position {position_id}",
        )
        self.settings.validate_mt5_credentials()
        module = self._require_mt5_module()
        if not self._initialize(module):
            raise RuntimeError(f"MT5 initialize failed: {module.last_error()}")

        try:
            authorized = module.login(
                self.settings.mt5_login,
                password=self.settings.mt5_password,
                server=self.settings.mt5_server,
            )
            if not authorized:
                raise RuntimeError(f"MT5 login failed: {module.last_error()}")

            if not module.symbol_select(order.instrument, True):
                raise RuntimeError(f"MT5 symbol_select failed for {order.instrument}: {module.last_error()}")

            tick = module.symbol_info_tick(order.instrument)
            if tick is None:
                raise RuntimeError(f"MT5 symbol_info_tick failed for {order.instrument}: {module.last_error()}")
            tick_record = self._coerce_record(tick)
            order_type = module.ORDER_TYPE_BUY if close_side == "buy" else module.ORDER_TYPE_SELL
            price = float(tick_record.ask if close_side == "buy" else tick_record.bid)
            filling_mode = self._resolve_order_filling(module, order.instrument)

            request = {
                "action": module.TRADE_ACTION_DEAL,
                "symbol": order.instrument,
                "volume": float(order.volume),
                "type": order_type,
                "position": int(position_id),
                "price": price,
                "deviation": 20,
                "magic": 20260508,
                "comment": order.comment,
                "type_time": module.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }
            result = module.order_send(request)
            if result is None:
                raise RuntimeError(f"MT5 order_send failed for {order.instrument}: {module.last_error()}")

            result_record = self._coerce_record(result)
            retcode = str(getattr(result_record, "retcode", "UNKNOWN"))
            success = retcode == str(module.TRADE_RETCODE_DONE)
            filled_volume = float(getattr(result_record, "volume", order.volume))
            executed_price = float(getattr(result_record, "price", price))
            broker_order_id = str(getattr(result_record, "order", getattr(result_record, "deal", "")))
            message = str(getattr(result_record, "comment", "")) or (
                "Position closed successfully." if success else "Position close rejected by MT5."
            )
            self.logger.info(
                "reasoning_trace",
                step="close_mt5_position",
                instrument=instrument,
                position_id=position_id,
                requested_volume=volume,
                retcode=retcode,
                success=success,
            )
            return TradeExecutionResult(
                success=success,
                broker=self.settings.broker_name,
                instrument=order.instrument,
                side=close_side,
                requested_volume=volume,
                filled_volume=filled_volume,
                executed_price=executed_price,
                broker_order_id=broker_order_id,
                status_code=retcode,
                message=message,
                request_payload=request,
            )
        finally:
            module.shutdown()

    def _require_mt5_module(self) -> Any:
        if self.mt5 is None:
            system_name = platform.system()
            raise RuntimeError(
                "MetaTrader5 Python package is not available. Run this adapter with a Windows Python environment on the same machine as the MT5 terminal"
                f". Current platform: {system_name}."
            )
        return self.mt5

    def _initialize(self, module: Any) -> bool:
        terminal_path = self.settings.mt5_terminal_path or None
        if terminal_path:
            return bool(module.initialize(path=terminal_path))
        return bool(module.initialize())

    def _fetch_account(self, module: Any) -> AccountSnapshot:
        account_info = module.account_info()
        if account_info is None:
            raise RuntimeError(f"MT5 account_info failed: {module.last_error()}")
        account = self._coerce_record(account_info)
        return AccountSnapshot(
            broker=self.settings.broker_name,
            account_id=str(account.login),
            balance=float(getattr(account, "balance", 0.0)),
            equity=float(getattr(account, "equity", getattr(account, "balance", 0.0))),
            unrealized_pnl=float(getattr(account, "profit", 0.0)),
            realized_pnl=float(getattr(account, "profit", 0.0)),
            margin_used=float(getattr(account, "margin", 0.0)),
            margin_available=float(getattr(account, "margin_free", 0.0)),
        )

    def _fetch_positions(self, module: Any, instrument: str) -> list[PositionSnapshot]:
        positions = module.positions_get(symbol=instrument)
        if positions is None:
            return []
        records = []
        for position in positions:
            item = self._coerce_record(position)
            side = "long" if int(getattr(item, "type", 0)) == 0 else "short"
            records.append(
                PositionSnapshot(
                    instrument=str(getattr(item, "symbol", instrument)),
                    side=side,
                    units=float(getattr(item, "volume", 0.0)),
                    entry_price=float(getattr(item, "price_open", 0.0)),
                    current_price=float(getattr(item, "price_current", getattr(item, "price_open", 0.0))),
                    unrealized_pnl=float(getattr(item, "profit", 0.0)),
                    realized_pnl=0.0,
                    position_id=str(getattr(item, "ticket", "")),
                )
            )
        return records

    def _fetch_trade_history(self, module: Any, instrument: str) -> list[TradeHistoryRecord]:
        date_to = datetime.now(timezone.utc)
        date_from = date_to - timedelta(days=7)
        deals = module.history_deals_get(date_from, date_to)
        if deals is None:
            return []

        history = []
        for deal in deals:
            item = self._coerce_record(deal)
            symbol = str(getattr(item, "symbol", ""))
            if symbol != instrument:
                continue
            side_code = int(getattr(item, "type", 0))
            side = "buy" if side_code == getattr(module, "DEAL_TYPE_BUY", 0) else "sell"
            timestamp_raw = getattr(item, "time", 0)
            timestamp = datetime.fromtimestamp(timestamp_raw, tz=timezone.utc)
            history.append(
                TradeHistoryRecord(
                    ticket_id=str(getattr(item, "ticket", "")),
                    instrument=symbol,
                    side=side,
                    volume=float(getattr(item, "volume", 0.0)),
                    price=float(getattr(item, "price", 0.0)),
                    profit=float(getattr(item, "profit", 0.0)),
                    timestamp=timestamp,
                    entry_type=str(getattr(item, "entry", "deal")),
                    comment=str(getattr(item, "comment", "")),
                )
            )
        return history

    def _fetch_rates(self, module: Any, *, instrument: str, granularity: str, count: int) -> pd.DataFrame:
        if not module.symbol_select(instrument, True):
            raise RuntimeError(f"MT5 symbol_select failed for {instrument}: {module.last_error()}")

        timeframe_name = self._TIMEFRAME_MAP.get(granularity, "TIMEFRAME_H1")
        timeframe = getattr(module, timeframe_name)
        rates = module.copy_rates_from_pos(instrument, timeframe, 0, count)
        if rates is None:
            raise RuntimeError(f"MT5 copy_rates_from_pos failed for {instrument}: {module.last_error()}")

        frame = pd.DataFrame(list(rates))
        if frame.empty:
            return frame
        frame["timestamp"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        frame = frame.rename(
            columns={
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "tick_volume": "volume",
            }
        )
        frame["instrument"] = instrument
        frame["is_complete"] = True
        return frame[["instrument", "timestamp", "open", "high", "low", "close", "volume", "is_complete"]].set_index(
            "timestamp"
        )

    def _resolve_order_filling(self, module: Any, instrument: str) -> int:
        symbol_info_func = getattr(module, "symbol_info", None)
        if callable(symbol_info_func):
            symbol_info = symbol_info_func(instrument)
            if symbol_info is not None:
                filling_mode = getattr(self._coerce_record(symbol_info), "filling_mode", None)
                if isinstance(filling_mode, int):
                    return filling_mode

        for attribute_name in ("ORDER_FILLING_RETURN", "ORDER_FILLING_IOC", "ORDER_FILLING_FOK"):
            filling_value = getattr(module, attribute_name, None)
            if isinstance(filling_value, int):
                return filling_value

        raise RuntimeError(f"MT5 filling mode could not be resolved for {instrument}.")

    @staticmethod
    def _coerce_record(record: Any) -> Any:
        if hasattr(record, "_asdict"):
            return SimpleNamespace(**record._asdict())
        if isinstance(record, dict):
            return SimpleNamespace(**record)
        return record


class Mt5RelayBrokerAdapter(BrokerAdminAdapter):
    def __init__(self, settings: ExecutionSettings, client: Optional[httpx.Client] = None) -> None:
        self.settings = settings
        self.client = client or httpx.Client(
            base_url=settings.mt5_relay_url,
            timeout=settings.request_timeout_seconds,
            verify=settings.verify_ssl,
        )

    def load_snapshot(self, *, instrument: str, granularity: str, count: int) -> BrokerDataSnapshot:
        payload = self._request(
            "GET",
            "/snapshot",
            params={"instrument": instrument, "granularity": granularity, "count": count},
        )
        return snapshot_from_payload(payload)

    def submit_market_order(self, order: TradeOrderRequest) -> TradeExecutionResult:
        payload = self._request("POST", "/orders/market", json=order.to_record())
        return trade_execution_result_from_payload(payload)

    def close_position(
        self,
        *,
        instrument: str,
        position_id: str,
        volume: float,
        side: str,
        comment: str = "",
    ) -> TradeExecutionResult:
        payload = self._request(
            "POST",
            "/positions/close",
            json={
                "instrument": instrument,
                "position_id": position_id,
                "volume": volume,
                "side": side,
                "comment": comment,
            },
        )
        return trade_execution_result_from_payload(payload)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = kwargs.pop("headers", {})
        if self.settings.mt5_relay_token:
            headers["X-Relay-Token"] = self.settings.mt5_relay_token
        response = self.client.request(method, path, headers=headers, **kwargs)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            if detail:
                raise RuntimeError(f"MT5 relay request failed: {detail}") from exc
            raise RuntimeError(f"MT5 relay request failed with status {exc.response.status_code}.") from exc
        return response.json()


def build_mt5_admin_adapter(
    settings: ExecutionSettings,
    *,
    client: Optional[httpx.Client] = None,
    mt5_module: Optional[Any] = None,
) -> BrokerAdminAdapter:
    if settings.has_mt5_relay:
        return Mt5RelayBrokerAdapter(settings, client=client)
    return Mt5BrokerAdapter(settings, mt5_module=mt5_module)