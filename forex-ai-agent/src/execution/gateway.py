from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any, Callable, Iterable, Optional, Sequence

import httpx
import pandas as pd
import structlog
from websocket import WebSocketApp

from src.config.settings import ExecutionSettings
from src.execution.base import AccountSnapshot, Candle, MarketEvent, PositionSnapshot


class MarketGateway:
    """Historical REST client plus WebSocket live transport.

    Historical candles are implemented against the OANDA v20 REST shape.
    The live transport is broker-agnostic and expects a WebSocket endpoint,
    which makes it suitable for deployments such as IBKR Client Portal.
    """

    def __init__(self, settings: ExecutionSettings) -> None:
        self.settings = settings
        self.logger = structlog.get_logger(__name__).bind(
            component="market_gateway",
            broker=settings.broker_name,
        )
        self._client = httpx.Client(
            base_url=settings.rest_base_url,
            timeout=settings.request_timeout_seconds,
            verify=settings.verify_ssl,
            headers={
                "Content-Type": "application/json",
                **settings.auth_headers(),
            },
        )
        self._ws_app: Optional[WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None

    def fetch_oanda_candles(
        self,
        instrument: str,
        granularity: str,
        count: int = 500,
        price_component: str = "M",
    ) -> pd.DataFrame:
        self.logger.info(
            "reasoning_trace",
            step="fetch_historical_candles",
            instrument=instrument,
            granularity=granularity,
            count=count,
            price_component=price_component,
            transport="rest",
        )
        response = self._client.get(
            f"/v3/instruments/{instrument}/candles",
            params={
                "granularity": granularity,
                "count": count,
                "price": price_component,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return self.parse_oanda_candles(payload, instrument)

    def fetch_oanda_account_summary(self) -> AccountSnapshot:
        self.logger.info(
            "reasoning_trace",
            step="fetch_oanda_account_summary",
            account_id=self.settings.account_id,
            transport="rest",
        )
        response = self._client.get(f"/v3/accounts/{self.settings.account_id}/summary")
        response.raise_for_status()
        return self.parse_oanda_account_summary(response.json(), self.settings)

    def fetch_oanda_open_positions(self, current_prices: Optional[dict[str, float]] = None) -> list[PositionSnapshot]:
        self.logger.info(
            "reasoning_trace",
            step="fetch_oanda_open_positions",
            account_id=self.settings.account_id,
            transport="rest",
        )
        response = self._client.get(f"/v3/accounts/{self.settings.account_id}/openPositions")
        response.raise_for_status()
        return self.parse_oanda_open_positions(response.json(), current_prices=current_prices or {})

    @staticmethod
    def parse_oanda_candles(payload: dict[str, Any], instrument: str) -> pd.DataFrame:
        candles = []
        for raw_candle in payload.get("candles", []):
            mid = raw_candle.get("mid") or {}
            candle = Candle(
                instrument=instrument,
                timestamp=datetime.fromisoformat(raw_candle["time"].replace("Z", "+00:00")),
                open=float(mid["o"]),
                high=float(mid["h"]),
                low=float(mid["l"]),
                close=float(mid["c"]),
                volume=int(raw_candle.get("volume", 0)),
                is_complete=bool(raw_candle.get("complete", False)),
            )
            candles.append(candle.to_record())

        frame = pd.DataFrame(candles)
        if frame.empty:
            return frame

        frame = frame.sort_values("timestamp").set_index("timestamp")
        return frame

    @staticmethod
    def parse_oanda_account_summary(
        payload: dict[str, Any],
        settings: ExecutionSettings,
    ) -> AccountSnapshot:
        account = payload.get("account", {})
        return AccountSnapshot(
            broker=settings.broker_name,
            account_id=account.get("id", settings.account_id),
            balance=float(account.get("balance", 0.0)),
            equity=float(account.get("NAV", account.get("balance", 0.0))),
            unrealized_pnl=float(account.get("unrealizedPL", 0.0)),
            realized_pnl=float(account.get("pl", 0.0)),
            margin_used=float(account.get("marginUsed", 0.0)),
            margin_available=float(account.get("marginAvailable", 0.0)),
        )

    @staticmethod
    def parse_oanda_open_positions(
        payload: dict[str, Any],
        current_prices: dict[str, float],
    ) -> list[PositionSnapshot]:
        positions = []
        for raw_position in payload.get("positions", []):
            instrument = raw_position.get("instrument", "UNKNOWN")
            latest_price = float(current_prices.get(instrument, 0.0))
            for side_name in ("long", "short"):
                side_payload = raw_position.get(side_name, {})
                units = float(side_payload.get("units", 0.0))
                if units == 0:
                    continue
                entry_price = float(side_payload.get("averagePrice", latest_price))
                direction = "long" if units > 0 else "short"
                positions.append(
                    PositionSnapshot(
                        instrument=instrument,
                        side=direction,
                        units=abs(units),
                        entry_price=entry_price,
                        current_price=latest_price or entry_price,
                        unrealized_pnl=float(side_payload.get("unrealizedPL", 0.0)),
                        realized_pnl=float(side_payload.get("pl", 0.0)),
                    )
                )
        return positions

    def connect_live_prices(
        self,
        subscription_message: dict[str, Any],
        on_event: Callable[[MarketEvent], None],
        instruments: Optional[Sequence[str]] = None,
        on_error: Optional[Callable[[Any], None]] = None,
    ) -> WebSocketApp:
        websocket_url = self.settings.require_websocket()
        instrument_list = list(instruments or subscription_message.get("instruments", []))
        self.logger.info(
            "reasoning_trace",
            step="subscribe_live_prices",
            instruments=instrument_list,
            transport="websocket",
            websocket_url=websocket_url,
        )

        headers = [f"Authorization: Bearer {self.settings.api_key}"] if self.settings.api_key else []

        def _on_message(_: WebSocketApp, message: str) -> None:
            parsed_message = json.loads(message)
            event = self._build_market_event(parsed_message, instrument_list)
            on_event(event)

        def _on_open(ws: WebSocketApp) -> None:
            ws.send(json.dumps(subscription_message))

        def _on_error(_: WebSocketApp, error: Any) -> None:
            self.logger.error("websocket_error", error=str(error))
            if on_error is not None:
                on_error(error)

        self._ws_app = WebSocketApp(
            websocket_url,
            header=headers,
            on_open=_on_open,
            on_message=_on_message,
            on_error=_on_error,
        )
        self._ws_thread = threading.Thread(
            target=self._ws_app.run_forever,
            kwargs={"sslopt": {"cert_reqs": 0} if not self.settings.verify_ssl else {}},
            daemon=True,
            name="market-gateway-websocket",
        )
        self._ws_thread.start()
        return self._ws_app

    def close(self) -> None:
        self.logger.info("reasoning_trace", step="close_market_gateway")
        if self._ws_app is not None:
            self._ws_app.close()
        self._client.close()

    @staticmethod
    def _build_market_event(
        payload: dict[str, Any],
        instruments: Iterable[str],
    ) -> MarketEvent:
        instrument = payload.get("symbol") or payload.get("instrument")
        if instrument is None:
            instrument = next(iter(instruments), "UNKNOWN")

        raw_timestamp = payload.get("time") or payload.get("timestamp")
        parsed_timestamp = None
        if raw_timestamp:
            parsed_timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))

        event_type = payload.get("type", "price_update")
        return MarketEvent(
            instrument=instrument,
            event_type=event_type,
            timestamp=parsed_timestamp,
            payload=payload,
        )
