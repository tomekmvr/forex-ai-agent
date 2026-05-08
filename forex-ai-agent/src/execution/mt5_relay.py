from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.config.settings import ExecutionSettings
from src.execution.base import TradeOrderRequest
from src.execution.relay_payloads import (
    snapshot_to_payload,
    trade_execution_result_to_payload,
)


def serve_mt5_relay(settings: ExecutionSettings, host: str, port: int) -> None:
    from src.execution.adapters import Mt5BrokerAdapter

    adapter = Mt5BrokerAdapter(settings)
    relay_token = settings.mt5_relay_token
    if not relay_token:
        raise ValueError("FOREX_AGENT_MT5_RELAY_TOKEN is required before starting the MT5 relay.")

    class Mt5RelayRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"status": "ok", "broker": settings.broker_name})
                return
            if parsed.path == "/snapshot":
                self._require_token()
                params = parse_qs(parsed.query)
                instrument = params.get("instrument", ["DE30.pro"])[0]
                granularity = params.get("granularity", ["H1"])[0]
                count = int(params.get("count", ["120"])[0])
                snapshot = adapter.load_snapshot(instrument=instrument, granularity=granularity, count=count)
                self._send_json(200, snapshot_to_payload(snapshot))
                return
            self._send_json(404, {"error": f"Unknown endpoint: {parsed.path}"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            self._require_token()
            payload = self._read_json_body()
            if parsed.path == "/orders/market":
                result = adapter.submit_market_order(TradeOrderRequest(**payload))
                self._send_json(200, trade_execution_result_to_payload(result))
                return
            if parsed.path == "/positions/close":
                result = adapter.close_position(
                    instrument=str(payload["instrument"]),
                    position_id=str(payload["position_id"]),
                    volume=float(payload["volume"]),
                    side=str(payload["side"]),
                    comment=str(payload.get("comment", "")),
                )
                self._send_json(200, trade_execution_result_to_payload(result))
                return
            self._send_json(404, {"error": f"Unknown endpoint: {parsed.path}"})

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_json_body(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            if not raw_body:
                return {}
            return json.loads(raw_body.decode("utf-8"))

        def _require_token(self) -> None:
            header_token = self.headers.get("X-Relay-Token", "")
            if header_token != relay_token:
                self._send_json(401, {"error": "Unauthorized relay request."})
                raise PermissionError("Unauthorized relay request.")

        def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def handle_one_request(self) -> None:
            try:
                super().handle_one_request()
            except PermissionError:
                return
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})

    server = ThreadingHTTPServer((host, port), Mt5RelayRequestHandler)
    print(f"MT5 relay listening on http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    settings = ExecutionSettings.from_env()
    settings.validate_mt5_credentials()
    host = os.getenv("FOREX_AGENT_MT5_RELAY_BIND_HOST", "127.0.0.1")
    port = int(os.getenv("FOREX_AGENT_MT5_RELAY_BIND_PORT", "8765"))
    serve_mt5_relay(settings, host=host, port=port)


if __name__ == "__main__":
    main()