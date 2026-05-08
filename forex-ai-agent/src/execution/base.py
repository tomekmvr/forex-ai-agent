from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class Candle:
    instrument: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    is_complete: bool

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketEvent:
    instrument: str
    event_type: str
    timestamp: Optional[datetime]
    payload: dict[str, Any]


@dataclass(frozen=True)
class PositionSnapshot:
    instrument: str
    side: str
    units: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    position_id: str = ""

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AccountSnapshot:
    broker: str
    account_id: str
    balance: float
    equity: float
    unrealized_pnl: float
    realized_pnl: float
    margin_used: float
    margin_available: float

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TradeOrderRequest:
    instrument: str
    side: str
    volume: float
    comment: str = ""

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TradeExecutionResult:
    success: bool
    broker: str
    instrument: str
    side: str
    requested_volume: float
    filled_volume: float
    executed_price: float
    broker_order_id: str
    status_code: str
    message: str
    request_payload: dict[str, Any]

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TradeHistoryRecord:
    ticket_id: str
    instrument: str
    side: str
    volume: float
    price: float
    profit: float
    timestamp: datetime
    entry_type: str
    comment: str = ""

    def to_record(self) -> dict[str, Any]:
        return asdict(self)
