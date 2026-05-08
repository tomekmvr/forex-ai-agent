from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class BrokerProfile:
    name: str
    rest_base_url: str
    websocket_url: Optional[str]


BROKER_PROFILES = {
    "ibkr_client_portal": BrokerProfile(
        name="ibkr_client_portal",
        rest_base_url="https://localhost:5000/v1/api",
        websocket_url="wss://localhost:5000/v1/api/ws",
    ),
    "oanda_practice": BrokerProfile(
        name="oanda_practice",
        rest_base_url="https://api-fxpractice.oanda.com",
        websocket_url=None,
    ),
    "oanda_live": BrokerProfile(
        name="oanda_live",
        rest_base_url="https://api-fxtrade.oanda.com",
        websocket_url=None,
    ),
    "tms_oanda_mt5": BrokerProfile(
        name="tms_oanda_mt5",
        rest_base_url="",
        websocket_url=None,
    ),
}


@dataclass(frozen=True)
class ExecutionSettings:
    broker_profile: BrokerProfile
    api_key: str
    account_id: str
    mt5_login: Optional[int] = None
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_terminal_path: str = ""
    mt5_relay_url: str = ""
    mt5_relay_token: str = ""
    request_timeout_seconds: float = 30.0
    verify_ssl: bool = True

    @property
    def rest_base_url(self) -> str:
        return self.broker_profile.rest_base_url

    @property
    def websocket_url(self) -> Optional[str]:
        return self.broker_profile.websocket_url

    @property
    def broker_name(self) -> str:
        return self.broker_profile.name

    @classmethod
    def from_env(cls, prefix: str = "FOREX_AGENT") -> "ExecutionSettings":
        profile_name = os.getenv(f"{prefix}_BROKER_PROFILE", "ibkr_client_portal")
        if profile_name not in BROKER_PROFILES:
            supported = ", ".join(sorted(BROKER_PROFILES))
            raise ValueError(
                f"Unsupported broker profile '{profile_name}'. Supported profiles: {supported}."
            )

        broker_profile = BROKER_PROFILES[profile_name]
        api_key = os.getenv(f"{prefix}_API_KEY", "")
        account_id = os.getenv(f"{prefix}_ACCOUNT_ID", "")
        mt5_login_raw = os.getenv(f"{prefix}_MT5_LOGIN", "").strip()
        mt5_login = int(mt5_login_raw) if mt5_login_raw else None
        mt5_password = os.getenv(f"{prefix}_MT5_PASSWORD", "")
        mt5_server = os.getenv(f"{prefix}_MT5_SERVER", "")
        mt5_terminal_path = os.getenv(f"{prefix}_MT5_TERMINAL_PATH", "")
        mt5_relay_url = os.getenv(f"{prefix}_MT5_RELAY_URL", "").strip()
        mt5_relay_token = os.getenv(f"{prefix}_MT5_RELAY_TOKEN", "")
        timeout = float(os.getenv(f"{prefix}_REQUEST_TIMEOUT_SECONDS", "30"))
        verify_ssl = os.getenv(f"{prefix}_VERIFY_SSL", "true").lower() in {
            "1",
            "true",
            "yes",
        }

        return cls(
            broker_profile=broker_profile,
            api_key=api_key,
            account_id=account_id,
            mt5_login=mt5_login,
            mt5_password=mt5_password,
            mt5_server=mt5_server,
            mt5_terminal_path=mt5_terminal_path,
            mt5_relay_url=mt5_relay_url,
            mt5_relay_token=mt5_relay_token,
            request_timeout_seconds=timeout,
            verify_ssl=verify_ssl,
        )

    def validate_credentials(self) -> None:
        if self.broker_name == "tms_oanda_mt5":
            self.validate_mt5_credentials()
            return
        if not self.api_key:
            raise ValueError("Missing API key. Set FOREX_AGENT_API_KEY in the environment or .env file.")
        if not self.account_id:
            raise ValueError("Missing account ID. Set FOREX_AGENT_ACCOUNT_ID in the environment or .env file.")

    def validate_mt5_credentials(self) -> None:
        if self.has_mt5_relay:
            return
        if self.mt5_login is None:
            raise ValueError("Missing MT5 login. Set FOREX_AGENT_MT5_LOGIN in the environment or .env file.")
        if not self.mt5_password:
            raise ValueError("Missing MT5 password. Set FOREX_AGENT_MT5_PASSWORD in the environment or .env file.")
        if not self.mt5_server:
            raise ValueError("Missing MT5 server. Set FOREX_AGENT_MT5_SERVER in the environment or .env file.")

    @property
    def is_mt5_profile(self) -> bool:
        return self.broker_name == "tms_oanda_mt5"

    @property
    def has_mt5_relay(self) -> bool:
        return bool(self.mt5_relay_url)

    def auth_headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    def require_websocket(self) -> str:
        if not self.websocket_url:
            raise ValueError(
                f"Broker profile '{self.broker_name}' does not expose a WebSocket endpoint. "
                "Use a profile backed by WebSockets for live execution."
            )
        return self.websocket_url
