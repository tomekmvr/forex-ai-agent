from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from src.execution.base import (
    AccountSnapshot,
    PositionSnapshot,
    TradeExecutionResult,
    TradeHistoryRecord,
)


def snapshot_to_payload(snapshot: Any) -> dict[str, Any]:
    return {
        "source_name": snapshot.source_name,
        "status_message": snapshot.status_message,
        "live_connected": snapshot.live_connected,
        "market_prices": market_prices_to_payload(snapshot.market_prices),
        "account_snapshot": snapshot.account_snapshot.to_record(),
        "positions": [position.to_record() for position in snapshot.positions],
        "trade_history": [trade_history_to_payload(item) for item in snapshot.trade_history],
    }


def snapshot_from_payload(payload: dict[str, Any]) -> Any:
    from src.execution.adapters import BrokerDataSnapshot

    return BrokerDataSnapshot(
        source_name=str(payload["source_name"]),
        status_message=str(payload["status_message"]),
        live_connected=bool(payload["live_connected"]),
        market_prices=market_prices_from_payload(payload.get("market_prices", [])),
        account_snapshot=AccountSnapshot(**payload["account_snapshot"]),
        positions=tuple(PositionSnapshot(**item) for item in payload.get("positions", [])),
        trade_history=tuple(trade_history_from_payload(item) for item in payload.get("trade_history", [])),
    )


def trade_execution_result_to_payload(result: TradeExecutionResult) -> dict[str, Any]:
    return result.to_record()


def trade_execution_result_from_payload(payload: dict[str, Any]) -> TradeExecutionResult:
    return TradeExecutionResult(**payload)


def trade_history_to_payload(record: TradeHistoryRecord) -> dict[str, Any]:
    payload = record.to_record()
    payload["timestamp"] = record.timestamp.isoformat()
    return payload


def trade_history_from_payload(payload: dict[str, Any]) -> TradeHistoryRecord:
    item = dict(payload)
    item["timestamp"] = datetime.fromisoformat(item["timestamp"])
    return TradeHistoryRecord(**item)


def market_prices_to_payload(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []

    payload_frame = frame.reset_index().copy()
    if "timestamp" not in payload_frame.columns:
        first_column = payload_frame.columns[0]
        payload_frame = payload_frame.rename(columns={first_column: "timestamp"})
    payload_frame["timestamp"] = pd.to_datetime(payload_frame["timestamp"], utc=True).dt.strftime(
        "%Y-%m-%dT%H:%M:%S%z"
    )
    return payload_frame.to_dict(orient="records")


def market_prices_from_payload(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame.set_index("timestamp")