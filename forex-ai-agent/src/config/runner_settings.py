from __future__ import annotations

import os
from dataclasses import dataclass

from src.config.ai_settings import AISettings
from src.config.settings import ExecutionSettings


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AgentRunnerSettings:
    source_mode: str = "broker"
    execution_mode: str = "paper"
    enable_live_execution: bool = False
    instrument: str = "DE30.pro"
    granularity: str = "H1"
    periods: int = 120
    equity: float = 100_000.0
    session_start_equity: float = 100_000.0
    current_equity: float = 100_000.0
    win_probability: float = 0.57
    payoff_ratio: float = 1.8
    failure_probability: float = 0.08
    decision_threshold: float = 0.15
    order_volume: float = 0.10
    units_per_volume: float = 0.0
    volume_step: float = 0.01
    poll_interval_seconds: int = 300
    close_opposite_positions: bool = True
    allow_same_side_reentry: bool = False
    run_once: bool = False
    comment_prefix: str = "Forex AI Agent Runner"

    @classmethod
    def from_env(cls, prefix: str = "FOREX_AGENT_RUNNER") -> "AgentRunnerSettings":
        return cls(
            source_mode=os.getenv(f"{prefix}_SOURCE_MODE", "broker").strip().lower(),
            execution_mode=os.getenv(f"{prefix}_EXECUTION_MODE", "paper").strip().lower(),
            enable_live_execution=_as_bool(os.getenv(f"{prefix}_ENABLE_LIVE_EXECUTION", "false")),
            instrument=os.getenv(f"{prefix}_INSTRUMENT", "DE30.pro").strip(),
            granularity=os.getenv(f"{prefix}_GRANULARITY", "H1").strip().upper(),
            periods=int(os.getenv(f"{prefix}_PERIODS", "120")),
            equity=float(os.getenv(f"{prefix}_EQUITY", "100000")),
            session_start_equity=float(os.getenv(f"{prefix}_SESSION_START_EQUITY", "100000")),
            current_equity=float(os.getenv(f"{prefix}_CURRENT_EQUITY", "100000")),
            win_probability=float(os.getenv(f"{prefix}_WIN_PROBABILITY", "0.57")),
            payoff_ratio=float(os.getenv(f"{prefix}_PAYOFF_RATIO", "1.8")),
            failure_probability=float(os.getenv(f"{prefix}_FAILURE_PROBABILITY", "0.08")),
            decision_threshold=float(os.getenv(f"{prefix}_DECISION_THRESHOLD", "0.15")),
            order_volume=float(os.getenv(f"{prefix}_ORDER_VOLUME", "0.10")),
            units_per_volume=float(os.getenv(f"{prefix}_UNITS_PER_VOLUME", "0")),
            volume_step=float(os.getenv(f"{prefix}_VOLUME_STEP", "0.01")),
            poll_interval_seconds=int(os.getenv(f"{prefix}_POLL_INTERVAL_SECONDS", "300")),
            close_opposite_positions=_as_bool(os.getenv(f"{prefix}_CLOSE_OPPOSITE_POSITIONS", "true"), True),
            allow_same_side_reentry=_as_bool(os.getenv(f"{prefix}_ALLOW_SAME_SIDE_REENTRY", "false")),
            run_once=_as_bool(os.getenv(f"{prefix}_RUN_ONCE", "false")),
            comment_prefix=os.getenv(f"{prefix}_COMMENT_PREFIX", "Forex AI Agent Runner").strip(),
        )

    def validate(self) -> None:
        if self.source_mode not in {"auto", "demo", "broker"}:
            raise ValueError("source_mode must be one of: auto, demo, broker.")
        if self.execution_mode not in {"paper", "live"}:
            raise ValueError("execution_mode must be either 'paper' or 'live'.")
        if self.execution_mode == "live" and not self.enable_live_execution:
            raise ValueError(
                "Live runner mode requires FOREX_AGENT_RUNNER_ENABLE_LIVE_EXECUTION=true."
            )
        if self.order_volume <= 0:
            raise ValueError("order_volume must be positive.")
        if self.volume_step <= 0:
            raise ValueError("volume_step must be positive.")
        if self.periods < 40:
            raise ValueError("periods must be at least 40.")
        if self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive.")

        if self.execution_mode == "live" and self.source_mode == "demo":
            raise ValueError("Live runner mode requires broker-backed source data, not demo mode.")

        if self.source_mode == "broker":
            execution_settings = ExecutionSettings.from_env()
            execution_settings.validate_credentials()

            if self.units_per_volume <= 0:
                raise ValueError(
                    "Broker runner mode requires FOREX_AGENT_RUNNER_UNITS_PER_VOLUME to map risk units to broker volume."
                )

            if execution_settings.is_mt5_profile and not execution_settings.has_mt5_relay:
                if not execution_settings.mt5_terminal_path:
                    raise ValueError(
                        "MT5 runner mode requires FOREX_AGENT_MT5_TERMINAL_PATH when no relay is configured."
                    )

        if self.execution_mode == "live":
            ai_settings = AISettings.from_env()
            if not ai_settings.enabled:
                raise ValueError(
                    "Live runner mode requires OpenAI supervisor configuration via OPENAI_API_KEY "
                    "or FOREX_AGENT_OPENAI_API_KEY."
                )
            if ai_settings.decision_mode != "supervisor":
                raise ValueError(
                    "Live runner mode requires FOREX_AGENT_AI_DECISION_MODE=supervisor."
                )